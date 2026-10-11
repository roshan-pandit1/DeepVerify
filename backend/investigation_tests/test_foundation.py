import json
import sqlite3
import time

import pytest
from fastapi.testclient import TestClient

from investigation.api import app
from investigation import worker, retrieval, training
from investigation.ingestion import destination
from investigation.ranking import baseline, score
from investigation.store import connect, migrate


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('INVESTIGATION_DB', str(tmp_path / 'test.db'))
    monkeypatch.setenv('INVESTIGATION_ARTIFACTS', str(tmp_path / 'artifacts'))
    monkeypatch.setenv('INVESTIGATION_ADMIN_TOKEN', 'test-administrator-token-at-least-24')
    monkeypatch.delenv('SERPAPI_API_KEY', raising=False)
    with TestClient(app) as client:
        yield client


AUTH = {'Authorization': 'Bearer test-administrator-token-at-least-24'}


def create(client, text='The Aurora Observatory opened in Oslo in 2024.', provider='offline'):
    response = client.post('/api/investigations', json={'text': text, 'provider': provider})
    assert response.status_code == 201, response.text
    return response.json()


def finished(client, **kwargs):
    item = create(client, **kwargs)
    assert client.post(f"/api/investigations/{item['claim_id']}/run").status_code == 200
    assert worker.run_once()
    return client.get(f"/api/investigations/{item['claim_id']}").json()


@pytest.mark.parametrize('text', ['', '     ', 'x' * 12001, 'Is this true?'])
def test_invalid_input(client, text):
    assert client.post('/api/investigations', json={'text': text}).status_code == 422


@pytest.mark.parametrize('url', ['file:///etc/passwd', 'http://127.0.0.1', 'http://169.254.169.254/', 'http://[::1]/', 'https://user:pass@example.com', 'http://example.com:8080/'])
def test_private_urls_blocked(url):
    with pytest.raises(ValueError):
        destination(url)


def test_mixed_dns_blocked(monkeypatch):
    monkeypatch.setattr('socket.getaddrinfo', lambda *a, **k: [(2, 1, 6, '', ('8.8.8.8', 80)), (2, 1, 6, '', ('10.0.0.1', 80))])
    with pytest.raises(ValueError):
        destination('http://example.org')


def test_unavailable_and_retry(client):
    item = finished(client, provider='serpapi')
    assert item['stage'] == 'partial'
    assert 'SERPAPI_API_KEY' in item['searches'][0]['error']
    assert item['assertions'][0]['assessment'] == 'insufficient evidence'
    assert item['assertions'][0]['evidence'] == []
    assert client.post(f"/api/investigations/{item['claim_id']}/run").status_code == 200


def test_empty_and_failed_retrieval(client, monkeypatch):
    monkeypatch.setattr(retrieval.Offline, 'search', lambda *a: [])
    item = finished(client)
    assert item['stage'] == 'complete'
    assert item['assertions'][0]['assessment'] == 'insufficient evidence'
    def fail(*args):
        raise retrieval.Unavailable('Provider timeout; retry later')
    monkeypatch.setattr(retrieval.Offline, 'search', fail)
    item = finished(client)
    assert item['stage'] == 'partial'
    assert item['searches'][0]['error'] == 'Provider timeout; retry later'


def test_association_dedup_and_edits(client, monkeypatch):
    original = retrieval.Offline.search
    monkeypatch.setattr(retrieval.Offline, 'search', lambda self, q: original(self, q) * 3)
    item = create(client)
    texts = ['Aurora opened in Oslo in 2024.', 'Mercury has no moons.']
    assert client.put(f"/api/investigations/{item['claim_id']}/assertions", json={'assertions': texts}).status_code == 200
    client.post(f"/api/investigations/{item['claim_id']}/run")
    worker.run_once()
    result = client.get(f"/api/investigations/{item['claim_id']}").json()
    for assertion in result['assertions']:
        assert len(assertion['evidence']) == 1
        assert assertion['evidence'][0]['assertion_id'] == assertion['id']
    assert result['assertions'][0]['evidence'][0]['predicted_stance'] == 'needing review'
    assert result['assertions'][1]['evidence'][0]['predicted_stance'] == 'unrelated'
    assert client.put(f"/api/investigations/{item['claim_id']}/assertions", json={'assertions': texts}).status_code == 409


def test_restart_and_lease_fencing(client):
    item = create(client)
    client.post(f"/api/investigations/{item['claim_id']}/run")
    old = worker.reserve()
    assert old and worker.reserve() is None
    with connect() as db:
        db.execute('UPDATE investigation_jobs SET lease_until=?', (time.time() - 1,))
    # A new API client and worker recover DB state without process-local task state.
    with TestClient(app) as restarted:
        assert restarted.get(f"/api/investigations/{item['claim_id']}").json()['stage'] == 'retrieving'
    assert worker.run_once()
    with connect() as db:
        assert not worker.owned(db, *old)
    result = client.get(f"/api/investigations/{item['claim_id']}").json()
    assert result['stage'] == 'complete'
    assert result['job']['attempts'] == 2
    assert not worker.run_once()


def test_feedback_approval_history_and_no_fixture_training(client):
    item = finished(client)
    evidence = item['assertions'][0]['evidence'][0]
    path = f"/api/evidence/{evidence['id']}/feedback"
    body = {'reviewer': 'session-12345', 'dimension': 'stance', 'label': 'supporting'}
    response = client.post(path, json=body).json()
    assert client.post(path, json=body).json()['id'] == response['id']
    review_path = f"/api/admin/feedback/{response['id']}/review"
    decision = {'decision': 'approved', 'reason': 'Reviewed synthetic passage for workflow testing'}
    assert client.post(review_path, json=decision).status_code == 403
    assert client.get('/api/admin/feedback').status_code == 403
    assert client.get(f"/api/investigations/{item['claim_id']}").json()['assertions'][0]['assessment'] == 'insufficient evidence'
    assert client.post(review_path, json=decision, headers=AUTH).status_code == 200
    result = client.get(f"/api/investigations/{item['claim_id']}").json()
    assert result['assertions'][0]['assessment'] == 'supported'
    assert result['assertions'][0]['evidence'][0]['predicted_stance'] == 'needing review'
    with TestClient(app) as restarted:
        assert len(restarted.get('/api/admin/feedback', headers=AUTH).json()['review_history']) == 1
    correction = client.post(path, json={**body, 'label': 'contradicting'}).json()
    client.post(f"/api/admin/feedback/{correction['id']}/review", json=decision, headers=AUTH)
    assert len(client.get('/api/admin/feedback', headers=AUTH).json()['review_history']) == 3
    with connect() as db:
        assert training.eligible_data(db) == []


def test_memory_and_baseline(client):
    first = finished(client)
    second = create(client, 'The Aurora Observatory opened in Oslo in 2024. Aurora is fictional.')
    assert second['related'][0]['claim_id'] == first['claim_id']
    assert second['related'][0]['method'] == 'lexical-jaccard-v1'
    live = create(client, provider='serpapi')
    assert live['related'] == []
    assert score([0, 0, 0, 1, 1])[0] == 0
    assert score([1, 1, 1, 0, 1])[0] == pytest.approx(1)
    assert score([1, 0, 0, 1, 1], 'candidate-missing')[0] == baseline([1, 0, 0, 1, 1])
    assert client.get('/api/learning').json()['status'] == 'collecting reviewed feedback'


def test_insufficient_training_and_promotion(client):
    exported = training.export()
    with pytest.raises(ValueError, match='collecting reviewed feedback'):
        training.train(exported['dataset_id'])
    assert not training.eligible_metrics({'precision@5': .8, 'ndcg@5': .8}, {'precision@5': .7, 'ndcg@5': .9, 'assertions': 5})
    assert not training.eligible_metrics({'precision@5': .8, 'ndcg@5': .8}, {'precision@5': .8, 'ndcg@5': .8, 'assertions': 5})
    with pytest.raises(ValueError):
        training.promote('../fake')
    assert training.rollback('baseline-v1')['active_ranker'] == 'baseline-v1'


def test_leakage_components():
    data = [dict(feedback_id=str(i), claim_id=str(i), assertion_id=str(i),
                 assertion_text=f'topic{i} fact{i} location{i}', canonical_url=f'https://example.org/{i}',
                 content_snippet=f'unique passage {i}') for i in range(12)]
    data[1]['claim_id'] = data[0]['claim_id']
    data[2]['canonical_url'] = data[1]['canonical_url']
    data[3]['content_snippet'] = data[2]['content_snippet']
    data[4]['assertion_text'] = data[3]['assertion_text']
    train, test, groups = training.grouped_split(data)
    assert groups == 8
    assert set(range(5)).issubset(train) or set(range(5)).issubset(test)
    assert not set(train) & set(test)
    assert training.grouped_split(data) == (train, test, groups)


def test_additive_migration_preserves_legacy_records(tmp_path, monkeypatch):
    path = tmp_path / 'legacy.db'
    monkeypatch.setenv('INVESTIGATION_DB', str(path))
    db = sqlite3.connect(path)
    db.executescript('''
    CREATE TABLE claims(id TEXT PRIMARY KEY, raw_input TEXT, input_type TEXT, normalized_text TEXT, status TEXT, created_at TEXT, updated_at TEXT);
    CREATE TABLE assertions(id TEXT PRIMARY KEY, claim_id TEXT, assertion_text TEXT, entity_names_json TEXT, confidence_weight REAL, created_at TEXT);
    CREATE TABLE evidence_items(id TEXT PRIMARY KEY, assertion_id TEXT, source_name TEXT, source_url TEXT, content_snippet TEXT, stance TEXT, credibility_score REAL, retrieved_at TEXT);
    CREATE TABLE audit_log_entries(id TEXT PRIMARY KEY, claim_id TEXT, stage_name TEXT, input_summary TEXT, output_summary TEXT, execution_time_ms INTEGER, timestamp TEXT);
    INSERT INTO claims VALUES ('old','surviving claim','TEXT','old text','COMPLETED','2020','2020');
    INSERT INTO assertions VALUES ('assertion','old','surviving assertion','[]',0.7,'2020');
    INSERT INTO evidence_items VALUES ('evidence','assertion','source','https://example.org','surviving evidence','SUPPORTS',0.8,'2020');
    INSERT INTO audit_log_entries VALUES ('audit','old','legacy','input','output',10,'2020');
    ''')
    tables = ['claims', 'assertions', 'evidence_items', 'audit_log_entries']
    before = {t: db.execute(f'SELECT * FROM {t}').fetchall() for t in tables}
    db.close()
    migrate()
    migrate()
    db = sqlite3.connect(path)
    assert before == {t: db.execute(f'SELECT * FROM {t}').fetchall() for t in tables}
    db.close()
