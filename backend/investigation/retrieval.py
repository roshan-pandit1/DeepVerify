import os
import logging
from typing import Protocol
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

import httpx


class Unavailable(Exception):
    pass


class Provider(Protocol):
    def search(self, query: str) -> list[dict]: ...


def canonical(url):
    p = urlsplit(url)
    if p.scheme not in ('https', 'http') or not p.hostname or p.username or p.password:
        raise ValueError('Provider returned an invalid source URL')
    p.port  # Reject malformed ports before any fetch.
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path.rstrip('/'),
                      urlencode(sorted((k, v) for k, v in parse_qsl(p.query) if not k.startswith('utm_'))), ''))


class SerpAPI:
    def search(self, query):
        key = os.getenv('SERPAPI_API_KEY', '')
        if not key:
            raise Unavailable('SERPAPI_API_KEY is missing. Configure it or create an explicitly offline investigation.')
        try:
            # HTTPX informational request logs include URL query credentials. Never emit those.
            logging.getLogger('httpx').setLevel(logging.WARNING)
            logging.getLogger('httpcore').setLevel(logging.WARNING)
            with httpx.Client(timeout=12, trust_env=False) as client:
                response = client.get('https://serpapi.com/search.json', params={
                    'engine': 'google', 'q': query, 'num': 10, 'api_key': key})
                response.raise_for_status()
                data = response.json()
            if data.get('error'):
                raise Unavailable('SerpAPI rejected the search. Check provider quota and credentials.')
            results = data.get('organic_results', [])
            if not isinstance(results, list):
                raise Unavailable('SerpAPI returned an invalid results collection.')
            # Do not let one malformed provider item fail the whole paid search.
            return [{'title': x.get('title', 'Untitled source'), 'url': x.get('link'),
                     'passage': x.get('snippet'), 'publication_date': x.get('date'),
                     'method': 'serpapi-google', 'kind': 'search snippet', 'fixture': False}
                    if isinstance(x, dict) else x for x in results[:10]]
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            # Do not persist exception URLs: provider credentials occur in query parameters.
            raise Unavailable('SerpAPI retrieval failed. Check network, quota, and credentials; retry the investigation.') from exc


class Offline:
    def search(self, query):
        return [{'title': 'OFFLINE FIXTURE — fictional observatory log',
                 'url': 'https://example.org/offline/observatory',
                 'passage': 'In 2024, the fictional Aurora Observatory opened in Oslo. This is synthetic development data.',
                 'publication_date': '2024-01-01', 'method': 'offline-fixture-v1',
                 'kind': 'synthetic fixture snippet', 'fixture': True}]


def provider(name):
    if name == 'offline':
        return Offline()
    if name == 'serpapi':
        return SerpAPI()
    raise Unavailable('Unknown retrieval provider. Choose serpapi or offline.')


def validate_result(item):
    if not isinstance(item, dict):
        raise ValueError('invalid_result')
    for name, maximum in [('title', 1000), ('url', 8000), ('passage', 20000), ('method', 100), ('kind', 100)]:
        value = item.get(name)
        if not isinstance(value, str) or not value.strip() or len(value) > maximum:
            raise ValueError('invalid_result')
    if not isinstance(item.get('fixture'), bool):
        raise ValueError('invalid_result')
    date = item.get('publication_date')
    if date is not None and (not isinstance(date, str) or len(date) > 200):
        raise ValueError('invalid_result')
    return canonical(item['url'])
