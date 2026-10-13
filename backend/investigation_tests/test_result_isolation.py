import json
import sqlite3
import stat

from investigation import retrieval, worker, sources
from investigation.store import connect
from test_foundation import client, create


def execute(client, monkeypatch, results):
    monkeypatch.setattr(retrieval.Offline, 'search', lambda *a: results)
    item = create(client)
    client.post(f"/api/investigations/{item['claim_id']}/run")
    worker.run_once()
    return client.get(f"/api/investigations/{item['claim_id']}").json()


def result(url='https://example.org/good'):
    return {**retrieval.Offline().search('claim')[0], 'url': url}


def test_mixed_results_retain_success_and_deduplicate(client, monkeypatch):
    good = result()
    report = execute(client, monkeypatch, [good, {'url': 'file:///secret'}, None, good])
    assert report['stage'] == 'partial'
    assert report['searches'][0]['state'] == 'partial'
    assert len(report['assertions'][0]['evidence']) == 1
    assert len(report['result_failures']) == 2


def test_all_invalid_fail_without_evidence(client, monkeypatch):
    report = execute(client, monkeypatch, [None, {**result(), 'url': 'https://example.org:bad'}])
    assert report['stage'] == 'partial'
    assert report['searches'][0]['state'] == 'failed'
    assert report['assertions'][0]['evidence'] == []


def test_persistence_failure_rolls_back_only_one_result(client, monkeypatch, tmp_path):
    good, other = result(), result('https://example.org/other')
    original = sources.persist
    def fail_one(db, evidence, assertion, item):
        original(db, evidence, assertion, item)
        if item['url'] == good['url']:
            raise sqlite3.IntegrityError('SENSITIVE-SOURCE-TEXT-AND-TOKEN')
    monkeypatch.setattr(sources, 'persist', fail_one)
    report = execute(client, monkeypatch, [good, other, other])
    assert report['searches'][0]['state'] == 'partial'
    assert [e['source_url'] for e in report['assertions'][0]['evidence']] == [other['url']]
    with connect() as db:
        assert db.execute('SELECT COUNT(*) FROM source_documents').fetchone()[0] == 1
        assert db.execute('SELECT COUNT(*) FROM evidence_items').fetchone()[0] == 1
    from investigation.ranking import artifact_dir
    log = artifact_dir() / 'diagnostics/worker.jsonl'
    assert stat.S_IMODE(log.stat().st_mode) == 0o600
    assert 'SENSITIVE-SOURCE-TEXT-AND-TOKEN' not in log.read_text() + json.dumps(report)
    assert 'IntegrityError' in log.read_text()


def test_provider_failure_and_successful_retry_preserve_evidence(client, monkeypatch):
    good = result()
    report = execute(client, monkeypatch, [good, None])
    claim = report['claim_id']
    first_id = report['assertions'][0]['evidence'][0]['id']
    def unavailable(*args):
        raise retrieval.Unavailable('Provider unavailable')
    monkeypatch.setattr(retrieval.Offline, 'search', unavailable)
    client.post(f'/api/investigations/{claim}/run')
    worker.run_once()
    assert client.get(f'/api/investigations/{claim}').json()['searches'][-1]['state'] == 'unavailable'
    monkeypatch.setattr(retrieval.Offline, 'search', lambda *a: [good, good])
    client.post(f'/api/investigations/{claim}/run')
    worker.run_once()
    final = client.get(f'/api/investigations/{claim}').json()
    assert final['stage'] == 'complete'
    assert [e['id'] for e in final['assertions'][0]['evidence']] == [first_id]
