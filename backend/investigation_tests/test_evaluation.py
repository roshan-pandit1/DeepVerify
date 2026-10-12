"""Synthetic simulations only; reviewer names/labels below are test fixtures, not people."""
import json

import pytest

from investigation import datasets, evaluation, training, splitting
from investigation.store import connect, now, uid, migrate
from test_foundation import client, create, AUTH


def case_fixture(client, dataset_id, index=0):
    # Emulate live-record shape in isolated temporary SQLite; never export these as real data.
    item = create(client, f'Topic{index} event{index} location{index}.', provider='serpapi')
    a = item['assertions'][0]['id']
    with connect() as db:
        db.execute("UPDATE investigations SET stage='complete' WHERE claim_id=?", (item['claim_id'],))
        for j in range(6):
            e = uid()
            db.execute('INSERT INTO evidence_items VALUES (?,?,?,?,?,?,?,?)',
                       (e, a, 'SYNTHETIC TEST SOURCE', f'https://example.org/{index}/{j}', f'text{index} passage{j}', 'NEUTRAL', 0, now()))
            db.execute('INSERT INTO evidence_details VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                       (e, f'https://example.org/{index}/{j}', '2024', 'simulated-live-test-only', 'search snippet', 0,
                        'needing review', 'test-only', 'Synthetic simulation', 0, 'baseline-v1', json.dumps([float(1-j % 2), 0, 0, 1, 1])))
    return datasets.add(dataset_id, a, f'fixture-topic-{index}', 'Synthetic as-of 2024', [sorted(datasets.CATEGORIES)[index % 7]])


def approve_case(identifier):
    with connect() as db:
        case = db.execute('SELECT snapshot_json FROM evaluation_cases WHERE id=?', (identifier,)).fetchone()
    evidence = json.loads(case['snapshot_json'])['evidence']
    datasets.label(identifier, '', 'sufficiency', 'insufficient', 'SYNTHETIC-TEST-REVIEWER', 'approved', 'Synthetic pipeline check only')
    for e in evidence:
        label = int(e['source_url'].split('/')[-1]) % 2
        for dimension, value in [('relevance', 'relevant' if label else 'irrelevant'), ('stance', 'supporting' if label else 'unrelated'), ('citation', 'needs review')]:
            datasets.label(identifier, e['id'], dimension, value, 'SYNTHETIC-TEST-REVIEWER', 'approved', 'Synthetic pipeline check only')


def test_unreviewed_dimensions_cannot_freeze_or_train(client):
    identifier = datasets.create('test-only-pending', '1')
    case = case_fixture(client, identifier)
    with connect() as db:
        snapshot = json.loads(db.execute('SELECT snapshot_json FROM evaluation_cases WHERE id=?', (case,)).fetchone()[0])
    e = snapshot['evidence'][0]['id']
    datasets.label(case, e, 'relevance', 'relevant', 'SYNTHETIC-TEST-REVIEWER', 'proposed', 'Synthetic proposal only')
    with pytest.raises(ValueError, match='sufficiency'):
        datasets.freeze(identifier)
    with pytest.raises(ValueError, match='frozen'):
        training.train_reviewed(identifier)
    datasets.label(case, '', 'sufficiency', 'insufficient', 'SYNTHETIC-TEST-REVIEWER', 'approved', 'Synthetic sufficiency review')
    with pytest.raises(ValueError, match='separate approved'):
        datasets.freeze(identifier)
    assert datasets.approved(datasets.load(identifier, frozen=False)['cases'][0], e, 'relevance') is None


def test_prior_relevance_approval_never_approves_evaluation_stance(client):
    first = datasets.create('SYNTHETIC feedback provenance', '1')
    case_fixture(client, first)
    case = datasets.load(first, frozen=False)['cases'][0]
    evidence_id = case['snapshot']['evidence'][0]['id']
    f = client.post(f'/api/evidence/{evidence_id}/feedback', json={'reviewer': 'SYNTHETIC-TEST', 'dimension': 'relevance', 'label': 'relevant'}).json()
    assert client.post(f"/api/admin/feedback/{f['id']}/review", headers=AUTH, json={'decision': 'approved', 'reason': 'Synthetic boundary check'}).status_code == 200
    second = datasets.create('SYNTHETIC new independent review', '1')
    datasets.add(second, case['assertion_id'], 'fixture-topic-0', 'Synthetic as-of 2024', ['supported'])
    captured = datasets.load(second, frozen=False)['cases'][0]
    assert captured['snapshot']['evidence'][0]['approved_feedback_at_capture']
    assert captured['reviews'] == []
    assert datasets.approved(captured, evidence_id, 'stance') is None
    with pytest.raises(ValueError, match='sufficiency'):
        datasets.freeze(second)


def test_synthetic_dataset_cannot_train_or_promote(client):
    identifier = datasets.create('synthetic', '1', synthetic=True)
    case = case_fixture(client, identifier)
    approve_case(case)
    datasets.freeze(identifier)
    with pytest.raises(ValueError, match='Synthetic'):
        training.train_reviewed(identifier)
    result = evaluation.evaluate(identifier)
    assert result['synthetic']
    assert result['ranking']['status'].startswith('insufficient data')
    assert not result['ranking']['promotion_gate_passed']
    assert result['stance']['candidate']['macro_f1'] is None


def test_three_way_training_evaluation_and_one_shot_holdout(client):
    identifier = datasets.create('SYNTHETIC simulation of live workflow', '1', seed=19)
    for i in range(15):
        approve_case(case_fixture(client, identifier, i))
    frozen = datasets.freeze(identifier)
    data = datasets.load(identifier)
    assert frozen['cases'] == 15
    assert len(datasets.ranking_rows(data, 'train')) == 54
    assert len(datasets.ranking_rows(data, 'validation')) == 18
    assert len(datasets.ranking_rows(data, 'holdout')) == 18
    for a in data['cases']:
        for b in data['cases']:
            assert a['split'] == b['split'] or not splitting.connected(a, b)
    with pytest.raises(ValueError, match='Frozen'):
        datasets.label(data['cases'][0]['id'], '', 'sufficiency', 'sufficient', 'TEST', 'approved', 'Must not modify frozen labels')
    trained = training.train_reviewed(identifier)
    model_id = trained['model_id']
    model = training.load_model(model_id)
    holdout_ids = {r['feedback_id'] for r in datasets.ranking_rows(data, 'holdout')}
    assert not holdout_ids & set(model['train_example_ids'] + model['validation_example_ids'])
    result = evaluation.evaluate(identifier, model_id)
    assert result['ranking']['baseline']['examples'] == result['ranking']['candidate']['examples'] == 18
    assert len(result['ranking']['identical_example_ids']) == 18
    assert result['stance']['candidate']['samples'] == 18
    assert result['sufficiency']['candidate']['per_class']['insufficient']['support'] == 3
    assert result['ranking']['promotion_gate_passed']
    with pytest.raises(ValueError, match='validation'):
        evaluation.evaluate(identifier, model_id, 'holdout')
    training.promote(model_id)
    failed = training.train_reviewed(identifier)['model_id']
    artifact = training.load_model(failed)
    artifact['coefficients'] = [.7, .2, .1, 0, 0]
    artifact['intercept'] = 0
    training.write(f'{failed}.json', artifact)
    with pytest.raises(ValueError, match='Promotion rejected'):
        training.promote(failed)
    with connect() as db:
        assert db.execute('SELECT model_id FROM active_ranker').fetchone()[0] == model_id
    audited = evaluation.evaluate(identifier, model_id, 'holdout')
    assert not audited['ranking']['promotion_gate_passed']
    assert evaluation.evaluate(identifier, model_id, 'holdout')['report_id'] == audited['report_id']
    with pytest.raises(ValueError, match='already consumed'):
        evaluation.evaluate(identifier, 'baseline-v1', 'holdout')
    with pytest.raises(ValueError, match='Final holdout'):
        training.train_reviewed(identifier)
    with pytest.raises(ValueError, match='Final holdout'):
        training.promote(failed)
    training.rollback('baseline-v1')
    training.rollback(model_id)
    assert client.get('/api/admin/evaluations').status_code == 403
    view = client.get('/api/admin/evaluations', headers=AUTH).json()
    assert view['reports'] and view['datasets']


def test_transitive_syndication_and_topic_split_isolation():
    cases = [{'id': str(i), 'related_group': f'group{i}', 'snapshot': {'claim_id': str(i),
              'assertion_text': f'topic{i} fact{i} event{i}', 'evidence': [{'canonical_url': f'https://example.org/{i}',
                'content_snippet': f'passage{i}', 'source': {'content_hash': f'hash{i}'}}]}} for i in range(10)]
    cases[1]['related_group'] = cases[0]['related_group']
    cases[2]['snapshot']['evidence'][0]['canonical_url'] = cases[1]['snapshot']['evidence'][0]['canonical_url']
    cases[3]['snapshot']['evidence'][0]['source']['content_hash'] = cases[2]['snapshot']['evidence'][0]['source']['content_hash']
    cases[4]['snapshot']['evidence'][0]['content_snippet'] = cases[3]['snapshot']['evidence'][0]['content_snippet']
    assignments = splitting.assign(cases, 17)
    assert len({assignments[str(i)] for i in range(5)}) == 1
    assert assignments == splitting.assign(cases, 17)


def test_existing_feedback_cannot_train_on_reserved_evaluation_sources(client):
    identifier = datasets.create('SYNTHETIC reservation simulation', '1')
    for i in range(5):
        approve_case(case_fixture(client, identifier, i))
    datasets.freeze(identifier)
    data = datasets.load(identifier)
    reserved = next(c for c in data['cases'] if c['split'] == 'holdout')
    e = reserved['snapshot']['evidence'][0]
    with connect() as db:
        db.execute('INSERT INTO feedback VALUES (?,?,?,?,?,?,?)', (uid(), e['id'], 'TEST-REVIEWER', 'relevance', 'relevant', now(), 'approved'))
        assert training.eligible_data(db) == []
    with pytest.raises(ValueError, match='collecting reviewed feedback'):
        training.train_reviewed(identifier)


def test_metric_confusion_and_insufficient_case_counts():
    result = evaluation.classification(['insufficient', 'sufficient', 'insufficient'],
                                       ['insufficient', 'insufficient', 'sufficient'], ['sufficient', 'insufficient'])
    assert result['confusion_matrix']['insufficient']['insufficient'] == 1
    assert result['per_class']['insufficient']['recall'] == .5
    assert result['per_class']['insufficient']['precision'] == .5
    assert result['macro_f1'] == .25


def test_migration_two_keeps_feedback_memory_and_active_model(client):
    item = create(client)
    with connect() as db:
        before = db.execute('SELECT memory_text FROM investigations WHERE claim_id=?', (item['claim_id'],)).fetchone()[0]
        db.execute("UPDATE active_ranker SET model_id='baseline-v1'")
    migrate(); migrate()
    with connect() as db:
        assert db.execute('SELECT memory_text FROM investigations WHERE claim_id=?', (item['claim_id'],)).fetchone()[0] == before
        assert db.execute('SELECT model_id FROM active_ranker').fetchone()[0] == 'baseline-v1'
        assert {r[0] for r in db.execute('SELECT version FROM investigation_migrations')} == {1, 2, 3}
