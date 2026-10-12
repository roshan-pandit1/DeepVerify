"""Public-only, DNS-pinned URL fetching. Redirects are independently validated."""
import ipaddress
import socket
import ssl
import http.client
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from urllib.parse import urlsplit, urljoin

from bs4 import BeautifulSoup

MAX_BYTES = 1_000_000
DNS_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix='public-dns')


class FetchFailure(ValueError):
    def __init__(self, category, message, final_url=None):
        super().__init__(message)
        self.category = category
        self.final_url = final_url


def destination(url):
    parts = urlsplit(url)
    if parts.scheme not in ('http', 'https') or not parts.hostname or parts.username or parts.password:
        raise ValueError('Use a public HTTP/HTTPS URL without credentials.')
    port = parts.port or (443 if parts.scheme == 'https' else 80)
    if port not in (80, 443):
        raise ValueError('Only public web ports 80 and 443 are allowed.')
    future = DNS_POOL.submit(socket.getaddrinfo, parts.hostname, port, type=socket.SOCK_STREAM)
    try:
        addresses = list({x[4][0] for x in future.result(timeout=3)})
    except TimeoutError as exc:
        future.cancel()
        raise FetchFailure('timeout', 'Public URL DNS lookup timed out. Submit the claim as text.', url) from exc
    ips = [ipaddress.ip_address(a) for a in addresses]
    if not ips or any(not ip.is_global or ip.is_reserved or ip.is_multicast for ip in ips):
        raise ValueError('Private, reserved, and non-public destinations are blocked.')
    return parts, port, addresses[0]


def fetch_document(url):
    deadline = time.monotonic() + 20
    for _ in range(4):
        try:
            parts, port, address = destination(url)
        except FetchFailure:
            raise
        except ValueError as exc:
            raise FetchFailure('unsafe_destination', str(exc), url) from exc
        except OSError as exc:
            raise FetchFailure('dns_failed', 'Public source hostname could not be resolved.', url) from exc
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise FetchFailure('timeout', 'Article fetch timed out.', url)
        conn = http.client.HTTPConnection(parts.hostname, port, timeout=min(5, remaining))
        # Connect to the validated address, with TLS verified against the original hostname.
        try:
            sock = socket.create_connection((address, port), timeout=min(5, remaining))
        except OSError as exc:
            raise FetchFailure('timeout' if isinstance(exc, socket.timeout) else 'network_error', 'Source connection failed.', url) from exc
        try:
            if parts.scheme == 'https':
                sock = ssl.create_default_context().wrap_socket(sock, server_hostname=parts.hostname)
            conn.sock = sock
            target = (parts.path or '/') + ('?' + parts.query if parts.query else '')
            conn.request('GET', target, headers={'Host': parts.netloc, 'User-Agent': 'DeepVerify/1.0', 'Accept-Encoding': 'identity'})
            response = conn.getresponse()
            if response.status in (301, 302, 303, 307, 308):
                url = urljoin(url, response.getheader('Location', ''))
                continue
            if response.status != 200:
                category = 'blocked' if response.status in (401, 403, 429) else 'paywall' if response.status == 402 else 'http_error'
                raise FetchFailure(category, f'Article returned HTTP {response.status}. No access restrictions were bypassed.', url)
            if response.getheader('Content-Encoding', 'identity') != 'identity':
                raise FetchFailure('unsupported_format', 'Compressed article responses are unsupported.', url)
            if 'text/html' not in response.getheader('Content-Type', '') and 'text/plain' not in response.getheader('Content-Type', ''):
                raise FetchFailure('unsupported_format', 'Only HTML or plain-text articles are supported.', url)
            chunks, total = [], 0
            while True:
                if time.monotonic() >= deadline:
                    raise FetchFailure('timeout', 'Article fetch exceeded the time limit.', url)
                if hasattr(sock, 'settimeout'):
                    sock.settimeout(min(5, max(.01, deadline - time.monotonic())))
                chunk = response.read1(16384)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_BYTES:
                    raise FetchFailure('size_limit', 'Article exceeds the 1 MB response limit.', url)
                chunks.append(chunk)
            return {'body': b''.join(chunks), 'final_url': url, 'content_type': response.getheader('Content-Type', '')}
        except (OSError, http.client.HTTPException) as exc:
            raise FetchFailure('timeout' if isinstance(exc, socket.timeout) else 'network_error', 'Source response failed.', url) from exc
        finally:
            conn.close()
            sock.close()
    raise FetchFailure('redirect_limit', 'Too many article redirects.', url)


def fetch_article(url):
    document = fetch_document(url)
    soup = BeautifulSoup(document['body'], 'html.parser')
    for node in soup(['script', 'style', 'nav', 'header', 'footer']):
        node.decompose()
    text = (soup.find('article') or soup.find('main') or soup).get_text(' ', strip=True)
    if len(text) > 12000:
        raise ValueError('Article text exceeds 12,000 characters. Submit a focused excerpt.')
    return text
