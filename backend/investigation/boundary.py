"""ASGI boundary before JSON parsing; protects every route, including reads and docs."""
import asyncio
import anyio
from starlette.responses import JSONResponse

from . import controls


class WorkspaceBoundary:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        lease = None
        response_started = False
        async def tracked_send(message):
            nonlocal response_started
            if message['type'] == 'http.response.start':
                response_started = True
            await send(message)
        try:
            controls.authorize_scope(scope)
            lease, limits = await anyio.to_thread.run_sync(controls.admit_request)
            headers = dict(scope.get('headers', []))
            try:
                length = int(headers.get(b'content-length', b'0'))
                if length < 0:
                    raise ValueError
            except ValueError:
                raise controls.LimitExceeded('Invalid Content-Length.', 400) from None
            if length > limits['request_bytes']:
                raise controls.LimitExceeded('Request body exceeds the workspace byte limit.', 413)
            async def read_body():
                body = bytearray()
                while True:
                    message = await receive()
                    if message['type'] == 'http.disconnect':
                        raise controls.LimitExceeded('Request interrupted.', 400)
                    chunk = message.get('body', b'')
                    if len(body) + len(chunk) > limits['request_bytes']:
                        raise controls.LimitExceeded('Request body exceeds the workspace byte limit.', 413)
                    body.extend(chunk)
                    if not message.get('more_body', False):
                        return bytes(body)
            try:
                body = await asyncio.wait_for(read_body(), 15)
            except asyncio.TimeoutError:
                raise controls.LimitExceeded('Request body timed out.', 408) from None
            delivered = False
            async def buffered_receive():
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {'type': 'http.request', 'body': body, 'more_body': False}
                return await receive()
            # Deadlines bound the request lease; network fetches also have their own bounds.
            await asyncio.wait_for(self.app(scope, buffered_receive, tracked_send), 60)
        except controls.LimitExceeded as exc:
            await JSONResponse({'detail': str(exc)}, status_code=exc.status,
                               headers={'Retry-After': '60'} if exc.status == 429 else {})(scope, receive, send)
        except asyncio.TimeoutError:
            if response_started:
                raise
            await JSONResponse({'detail': 'Workspace request timed out.'}, status_code=504)(scope, receive, send)
        finally:
            if lease:
                with anyio.CancelScope(shield=True):
                    await anyio.to_thread.run_sync(controls.release_request, lease)
