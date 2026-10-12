"""Non-executable article extraction and offset-addressed passage selection."""
import hashlib
import http.client
import json
import os
import re
import socket
import time
from typing import Protocol

from bs4 import BeautifulSoup

from .ingestion import fetch_document, FetchFailure
from .ranking import tokens
from .store import now, uid

VERSION = 'article-dom-v1'
PASSAGE_VERSION = 'paragraph-window-v1'


class SourceProvider(Protocol):
    version: str
    def fetch(self, url: str) -> dict: ...


def extract(document):
    soup = BeautifulSoup(document['body'], 'html.parser')
    # Read metadata as data only. Never evaluate page scripts, including JSON-LD.
    structured = []
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            value = json.loads(script.get_text())
            structured.extend(value if isinstance(value, list) else [value])
        except (ValueError, TypeError):
            pass
    nodes = []
    for value in structured:
        if isinstance(value, dict):
            nodes.append(value)
            nodes.extend(x for x in value.get('@graph', []) if isinstance(x, dict))
    if any(str(x.get('isAccessibleForFree', '')).lower() == 'false' for x in nodes):
        raise FetchFailure('paywall', 'Publisher marks this content as access-restricted.', document['final_url'])
    visible = soup.get_text(' ', strip=True).lower()
    if soup.select('[class*="paywall"], [id*="paywall"]') or any(x in visible[:3000] for x in ('subscribe to continue reading', 'sign in to continue reading')):
        raise FetchFailure('paywall', 'An access barrier was detected; using the search snippet.', document['final_url'])
    if any(x in visible[:1000] for x in ('verify you are human', 'checking your browser', 'enable javascript and cookies to continue')):
        raise FetchFailure('blocked', 'A browser challenge was detected; scripts were not executed.', document['final_url'])
    title_node = soup.find('h1') or soup.find('title')
    title = title_node.get_text(' ', strip=True) if title_node else ''
    date, date_method = None, None
    meta = soup.select_one('meta[property="article:published_time"], meta[name="datePublished"], meta[name="pubdate"]')
    if meta:
        date, date_method = meta.get('content'), 'publisher-meta'
    if not date:
        date = next((x.get('datePublished') for x in nodes if isinstance(x.get('datePublished'), str)), None)
        date_method = 'publisher-jsonld' if date else None
    if not date:
        tag = soup.select_one('time[datetime]')
        if tag:
            date, date_method = tag.get('datetime'), 'time-element (may not be publication date)'
    for node in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'form', 'noscript']):
        node.decompose()
    root = soup.find('article')
    article_types = {'Article', 'NewsArticle', 'BlogPosting', 'Report'}
    article_meta = any(bool(article_types & set(x.get('@type', []) if isinstance(x.get('@type'), list) else [x.get('@type')])) for x in nodes)
    if root is None and article_meta:
        root = soup.find('main') or soup.find('body')
    if root is None:
        raise FetchFailure('non_article', 'No article container or article metadata found. No full-source extraction claimed.', document['final_url'])
    blocks = [' '.join(p.get_text(' ', strip=True).split()) for p in root.find_all(['p', 'blockquote']) if not p.find_parent('blockquote')]
    blocks = [x for x in blocks if x]
    text = '\n\n'.join(blocks)
    if len(text) < 120 or not title:
        raise FetchFailure('extraction_failed', 'Article title or substantial paragraph text is missing.', document['final_url'])
    if any(len(x) > 12000 for x in blocks) or len(text) > 200000:
        raise FetchFailure('extraction_failed', 'Article layout exceeds supported paragraph/text limits.', document['final_url'])
    return {'title': title[:1000], 'main_text': text, 'publication_date': date,
            'date_method': date_method, 'content_hash': hashlib.sha256(text.encode()).hexdigest(),
            'body_hash': hashlib.sha256(document['body']).hexdigest(),
            'final_url': document['final_url'], 'status': 'extracted', 'error': None}


class PublicArticle:
    version = VERSION

    def fetch(self, url):
        return extract(fetch_document(url))


class SnippetsOnly:
    version = 'snippets-only-v1'

    def fetch(self, url):
        raise FetchFailure('disabled', 'Source fetching disabled by SOURCE_EXTRACTION_PROVIDER.', url)


def provider():
    name = os.getenv('SOURCE_EXTRACTION_PROVIDER', 'public-article')
    if name == 'public-article':
        return PublicArticle()
    if name == 'snippets-only':
        return SnippetsOnly()
    raise FetchFailure('unavailable', 'Unknown SOURCE_EXTRACTION_PROVIDER; use public-article or snippets-only.')


def select_passage(text, assertion):
    paragraphs = text.split('\n\n')
    query = tokens(assertion)
    index = max(range(len(paragraphs)), key=lambda i: len(query & tokens(paragraphs[i])) / max(1, len(query)))
    start = sum(len(p) + 2 for p in paragraphs[:index])
    end = start + len(paragraphs[index])
    left = max(0, index - 1)
    right = min(len(paragraphs), index + 2)
    context_start = sum(len(p) + 2 for p in paragraphs[:left])
    context_end = sum(len(p) + 2 for p in paragraphs[:right]) - 2
    return {'passage': text[start:end], 'start_offset': start, 'end_offset': end,
            'context': text[context_start:context_end], 'context_start': context_start, 'context_end': context_end}


def enrich(item, assertion, unavailable_reason=None):
    started = time.monotonic()
    source = {'id': uid(), 'source_url': item['url'], 'final_url': item['url'], 'retrieved_at': now(),
              'method': VERSION, 'status': 'unavailable', 'title': item['title'], 'main_text': '',
              'publication_date': None, 'date_method': None, 'content_hash': None, 'body_hash': None, 'error': None}
    try:
        if unavailable_reason:
            raise FetchFailure('budget_exhausted', unavailable_reason)
        if item['fixture']:
            raise FetchFailure('offline', 'Offline fixture: no live source fetch was attempted.')
        fetcher = provider()
        source['method'] = fetcher.version
        source.update(fetcher.fetch(item['url']))
        source['retrieved_at'] = now()
        selected = select_passage(source['main_text'], assertion)
        return {**item, **selected, 'latency_ms': int((time.monotonic() - started) * 1000), 'title': source['title'], 'publication_date': source['publication_date'],
                'kind': 'extracted article passage', 'source': source, 'search_snippet': item['passage']}
    except (FetchFailure, OSError, http.client.HTTPException, ValueError, TypeError) as exc:
        category = exc.category if isinstance(exc, FetchFailure) else 'timeout' if isinstance(exc, (socket.timeout, TimeoutError)) else 'fetch_failed'
        source.update(status=category, error=str(exc) if isinstance(exc, FetchFailure) else 'Source fetch/extraction failed; search snippet retained.')
        source['retrieved_at'] = now()
        if isinstance(exc, FetchFailure) and exc.final_url:
            source['final_url'] = exc.final_url
        return {**item, 'latency_ms': int((time.monotonic() - started) * 1000), 'kind': item['kind'] if item['fixture'] else 'search snippet fallback', 'source': source,
                'search_snippet': item['passage'], 'context': '', 'start_offset': None, 'end_offset': None,
                'context_start': None, 'context_end': None}


def persist(db, evidence_id, assertion_id, item):
    s = item['source']
    db.execute('INSERT INTO source_documents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
               tuple(s[k] for k in ('id', 'source_url', 'final_url', 'retrieved_at', 'method', 'status',
                                    'title', 'main_text', 'publication_date', 'date_method', 'content_hash', 'body_hash', 'error')) + (int(item['fixture']),))
    db.execute('INSERT INTO source_passages VALUES (?,?,?,?,?,?,?,?,?,?)',
               (evidence_id, s['id'], assertion_id, item['start_offset'], item['end_offset'],
                item['context'], item['context_start'], item['context_end'], item['search_snippet'], PASSAGE_VERSION))
    db.execute('INSERT INTO source_observations VALUES (?,?)', (s['id'], item.get('latency_ms', 0)))
