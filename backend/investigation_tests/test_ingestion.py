import pytest

from investigation import ingestion


class Socket:
    def close(self):
        pass


class Response:
    def __init__(self, status=200, headers=None, chunks=None):
        self.status = status
        self.headers = headers or {'Content-Type': 'text/html'}
        self.chunks = iter(chunks or [b'<article>Mercury has no moons.</article>'])

    def getheader(self, key, default=None):
        return self.headers.get(key, default)

    def read1(self, size):
        return next(self.chunks, b'')


def setup(monkeypatch, responses):
    connected = []
    requests = []
    iterator = iter(responses)
    monkeypatch.setattr(ingestion.socket, 'getaddrinfo', lambda host, *a, **k: [(2, 1, 6, '', ('127.0.0.1' if host == 'internal' else '8.8.8.8', 80))])
    def connect(address, **kwargs):
        connected.append(address)
        return Socket()
    monkeypatch.setattr(ingestion.socket, 'create_connection', connect)
    class Connection:
        def __init__(self, *a, **k):
            pass
        def request(self, *args, **kwargs):
            requests.append((args, kwargs))
        def getresponse(self):
            return next(iterator)
        def close(self):
            pass
    monkeypatch.setattr(ingestion.http.client, 'HTTPConnection', Connection)
    return connected, requests


def test_dns_pinned_and_untrusted_scripts_removed(monkeypatch):
    connected, requests = setup(monkeypatch, [Response(chunks=[b'<article>Mercury has no moons.<script>steal()</script></article>'])])
    assert ingestion.fetch_article('http://example.org/article?q=1') == 'Mercury has no moons.'
    assert connected == [('8.8.8.8', 80)]
    assert requests[0][0] == ('GET', '/article?q=1')
    assert requests[0][1]['headers']['Host'] == 'example.org'


def test_private_redirect_blocked_before_connection(monkeypatch):
    connected, _ = setup(monkeypatch, [Response(302, {'Location': 'http://internal/secret'})])
    with pytest.raises(ValueError, match='blocked'):
        ingestion.fetch_article('http://example.org')
    assert len(connected) == 1


def test_response_size_and_redirect_limit(monkeypatch):
    setup(monkeypatch, [Response(chunks=[b'a' * 600000, b'b' * 600000])])
    with pytest.raises(ValueError, match='1 MB'):
        ingestion.fetch_article('http://example.org')
    setup(monkeypatch, [Response(302, {'Location': '/again'}) for _ in range(4)])
    with pytest.raises(ValueError, match='redirects'):
        ingestion.fetch_article('http://example.org')
