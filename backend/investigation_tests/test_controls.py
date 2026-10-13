"""No live requests: exercise shared policy through HTTP and separate processes."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import httpx
import pytest

from investigation import controls, worker, retrieval, sources
from investigation.api import app
from investigation.boundary import WorkspaceBoundary
from investigation.store import connect, migrate
from test_foundation import client, create, TestClient


def set_limits(**changes):
    with connect() as db:
        values = controls.policy(db)
        values.update(changes)
        db.execute('UPDATE workspace_policy SET policy_json=? WHERE singleton=1', (json.dumps(values),))


def external_request(path, address='203.0.113.4', headers=None, method='GET', content=None):
    async def request():
        transport = httpx.ASGITransport(app=app, client=(address, 12345))
        async with httpx.AsyncClient(transport=transport, base_url='http://127.0.0.1') as session:
            return await session.request(method, path, headers=headers, content=content)
    return asyncio.run(request())


@pytest.mark.parametrize('path', ['/api/investigations', '/api/investigations/unknown', '/api/sources/unknown', '/api/learning', '/api/admin/feedback', '/docs', '/openapi.json'])
def test_local_boundary_covers_reads_and_docs(client, path):
    assert external_request(path).status_code == 403
    assert external_request(path, headers={'X-Forwarded-For': '127.0.0.1'}).status_code == 403


def test_host_origin_and_admin_boundaries(client):
    assert client.get('/api/investigations', headers={'Host': 'evil.example'}).status_code == 403
    assert client.post('/api/investigations', headers={'Origin': 'https://evil.example'}, json={'text': 'A valid claim.'}).status_code == 403
    assert client.get('/api/admin/feedback').status_code == 403
    allowed = client.options('/api/investigations', headers={'Origin': 'http://localhost:3000', 'Access-Control-Request-Method': 'POST'})
    assert allowed.status_code == 200
    assert allowed.headers['access-control-allow-origin'] == 'http://localhost:3000'


def test_private_gateway_token_cannot_authorize_admin(client, monkeypatch, caplog):
    secret = 'SYNTHETIC-private-workspace-token-1234567890'
    monkeypatch.setenv('INVESTIGATION_DEPLOYMENT', 'private')
    monkeypatch.setenv('INVESTIGATION_ALLOWED_HOSTS', '127.0.0.1')
    monkeypatch.setenv('INVESTIGATION_TRUSTED_PROXY_CIDRS', '10.5.0.2/32')
    monkeypatch.setenv('INVESTIGATION_WORKSPACE_TOKEN', secret)
    controls.validate_boundary()
    assert external_request('/api/investigations', '10.5.0.2').status_code == 403
    headers = {'X-Workspace-Token': secret}
    assert external_request('/api/investigations', '10.5.0.3', headers).status_code == 403
    assert external_request('/api/investigations', '10.5.0.2', headers).status_code == 200
    assert external_request('/api/admin/feedback', '10.5.0.2', {**headers, 'Authorization': 'Bearer ' + secret}).status_code == 403
    assert external_request('/api/admin/feedback', '10.5.0.2', {**headers, 'Authorization': 'Bearer test-administrator-token-at-least-24'}).status_code == 200
    assert secret not in caplog.text


def test_private_startup_requires_explicit_boundary(client, monkeypatch):
    monkeypatch.setenv('INVESTIGATION_DEPLOYMENT', 'private')
    monkeypatch.delenv('INVESTIGATION_WORKSPACE_TOKEN', raising=False)
    with pytest.raises(ValueError, match='distinct'):
        controls.validate_boundary()
    monkeypatch.setenv('INVESTIGATION_DEPLOYMENT', 'public')
    with pytest.raises(ValueError, match='not supported'):
        controls.validate_boundary()


def test_request_and_submission_rejection_persist(client):
    set_limits(requests_per_minute=2)
    assert client.get('/api/investigations').status_code == 200
    assert client.get('/api/investigations').status_code == 200
    assert client.get('/api/investigations').status_code == 429
    # A second client/process shares the durable counter, not its own allowance.
    assert external_request('/api/investigations', '127.0.0.1').status_code == 429
    set_limits(requests_per_minute=100, submissions_per_hour=1)
    create(client)
    assert client.post('/api/investigations', json={'text': 'Another valid claim.', 'provider': 'offline'}).status_code == 429


def test_queue_rejection_is_atomic_and_retains_draft(client):
    set_limits(queue=1)
    a, b = create(client), create(client)
    assert client.post(f"/api/investigations/{a['claim_id']}/run").status_code == 200
    assert client.post(f"/api/investigations/{b['claim_id']}/run").status_code == 429
    assert client.get(f"/api/investigations/{b['claim_id']}").json()['stage'] == 'draft'


def test_declared_and_streamed_body_limits_before_parsing(client):
    set_limits(request_bytes=32)
    assert client.post('/api/investigations', content=b'x' * 33).status_code == 413
    async def run():
        calls = 0
        async def forbidden(scope, receive, send):
            pytest.fail('Oversized request reached application parser')
        async def receive():
            nonlocal calls
            calls += 1
            return {'type': 'http.request', 'body': b'x' * 20, 'more_body': True}
        messages = []
        async def send(message): messages.append(message)
        scope = {'type': 'http', 'method': 'POST', 'path': '/api/investigations', 'client': ('127.0.0.1', 1234), 'headers': [(b'host', b'127.0.0.1')]}
        await WorkspaceBoundary(forbidden)(scope, receive, send)
        assert messages[0]['status'] == 413 and calls == 2
    asyncio.run(run())
    with connect() as db:
        assert db.execute('SELECT COUNT(*) FROM workspace_request_leases').fetchone()[0] == 0


def test_request_concurrency_and_expired_lease_recovery(client):
    set_limits(active_requests=1)
    lease, _ = controls.admit_request()
    assert client.get('/api/investigations').status_code == 429
    with connect() as db:
        db.execute('UPDATE workspace_request_leases SET expires=?', (time.time() - 1,))
    assert client.get('/api/investigations').status_code == 200
    controls.release_request(lease)


def test_worker_rechecks_budget_after_queueing(client, monkeypatch):
    item = create(client, provider='serpapi')
    client.post(f"/api/investigations/{item['claim_id']}/run")
    set_limits(daily_cost_microusd=0)
    monkeypatch.setattr(retrieval.SerpAPI, 'search', lambda *a: pytest.fail('Budget-exhausted worker made a provider request'))
    assert worker.run_once()
    report = client.get(f"/api/investigations/{item['claim_id']}").json()
    assert report['stage'] == 'partial'
    assert 'provider-cost budget' in report['searches'][0]['error']
    assert client.post(f"/api/investigations/{item['claim_id']}/run").status_code == 429


def test_missing_cost_bound_disables_live_but_not_offline(client):
    set_limits(search_cost_microusd=0)
    item = create(client, provider='serpapi')
    assert client.post(f"/api/investigations/{item['claim_id']}/run").status_code == 503
    offline = create(client)
    assert client.post(f"/api/investigations/{offline['claim_id']}/run").status_code == 200
    assert worker.run_once()


def test_configured_input_limits_at_api_and_worker(client, monkeypatch):
    item = create(client)
    client.post(f"/api/investigations/{item['claim_id']}/run")
    set_limits(claim_chars=10, assertion_chars=10)
    assert client.post('/api/investigations', json={'text': 'This claim is too long.', 'provider': 'offline'}).status_code == 422
    monkeypatch.setattr(retrieval.Offline, 'search', lambda *a: pytest.fail('Oversized stored assertion was processed'))
    worker.run_once()
    assert 'input limits' in client.get(f"/api/investigations/{item['claim_id']}").json()['searches'][0]['error']


def test_provider_and_source_budget_across_competing_processes(client):
    set_limits(searches_per_day=2, daily_cost_microusd=20000, sources_per_day=2)
    code = '''from investigation.controls import reserve_external, LimitExceeded
import sys
try:
    reserve_external(sys.argv[1])
    print('reserved')
except LimitExceeded:
    print('blocked')
'''
    def attempt(kind):
        return subprocess.run([sys.executable, '-c', code, kind], capture_output=True, text=True, check=True).stdout.strip()
    for kind in ('search', 'source'):
        with ThreadPoolExecutor(max_workers=4) as pool:
            outcomes = list(pool.map(attempt, [kind] * 4))
        assert outcomes.count('reserved') == 2 and outcomes.count('blocked') == 2
    # Migration/startup cannot reset cost reservations.
    migrate()
    with connect() as db:
        assert controls.count(db, 'search', 0) == 2


def test_worker_concurrency_across_processes_and_fencing(client):
    set_limits(workers=1)
    for _ in range(3):
        item = create(client)
        client.post(f"/api/investigations/{item['claim_id']}/run")
    code = 'from investigation.worker import reserve; print(bool(reserve()))'
    def reserve(_):
        return subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, check=True).stdout.strip()
    with ThreadPoolExecutor(max_workers=3) as pool:
        outcomes = list(pool.map(reserve, range(3)))
    assert outcomes.count('True') == 1
    with connect() as db:
        job = db.execute("SELECT claim_id,owner FROM investigation_jobs WHERE state='running'").fetchone()
        db.execute('UPDATE investigation_jobs SET lease_until=0')
    with pytest.raises(controls.LimitExceeded, match='lease lost'):
        controls.reserve_external('search', job['claim_id'], job['owner'])
    assert worker.reserve() is not None


def test_source_budget_prevents_url_submission_fetch(client, monkeypatch):
    set_limits(sources_per_day=1)
    controls.reserve_external('source')
    monkeypatch.setattr('investigation.api.fetch_article', lambda *a: pytest.fail('Source budget bypassed'))
    response = client.post('/api/investigations', json={'text': 'https://example.org/article', 'input_type': 'url'})
    assert response.status_code == 429


def test_policy_mismatch_requires_explicit_reconfiguration(client, monkeypatch):
    controls.reserve_external('search')
    monkeypatch.setenv('INVESTIGATION_LIMIT_SEARCHES_PER_DAY', '50')
    with pytest.raises(ValueError, match='differ'):
        controls.initialize()
    controls.configure()
    controls.initialize()
    with connect() as db:
        assert controls.count(db, 'search', 0) == 1
        assert controls.policy(db)['searches_per_day'] == 50


def test_exhausted_source_budget_keeps_honest_snippet(client, monkeypatch):
    set_limits(sources_per_day=1)
    controls.reserve_external('source')
    monkeypatch.setenv('SOURCE_EXTRACTION_PROVIDER', 'public-article')
    monkeypatch.setattr(sources, 'fetch_document', lambda *a: pytest.fail('Source budget bypassed'))
    item = {**retrieval.Offline().search('claim')[0], 'fixture': False}
    result = sources.enrich(item, 'Mercury has no moons.')
    assert result['source']['status'] == 'budget_exhausted'
    assert result['kind'] == 'search snippet fallback'
    assert result['passage'] == item['passage']


def test_cancellation_releases_request_slot(client):
    async def run():
        started = asyncio.Event()
        async def application(scope, receive, send):
            started.set()
            await asyncio.Event().wait()
        async def receive():
            return {'type': 'http.request', 'body': b'', 'more_body': False}
        async def send(message): pass
        scope = {'type': 'http', 'method': 'GET', 'path': '/', 'client': ('127.0.0.1', 1), 'headers': [(b'host', b'127.0.0.1')]}
        task = asyncio.create_task(WorkspaceBoundary(application)(scope, receive, send))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    asyncio.run(run())
    with connect() as db:
        assert db.execute('SELECT COUNT(*) FROM workspace_request_leases').fetchone()[0] == 0
