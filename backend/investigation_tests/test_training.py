"""Synthetic functionality checks only. These examples demonstrate no real accuracy."""
import json

import pytest

from investigation import training
from investigation.ranking import artifact_dir, score
from investigation.store import connect, migrate


@pytest.fixture
def dataset(tmp_path, monkeypatch):
    monkeypatch.setenv('INVESTIGATION_DB', str(tmp_path / 'training.db'))
    monkeypatch.setenv('INVESTIGATION_ARTIFACTS', str(tmp_path / 'artifacts'))
    migrate()
    data = []
    for group in range(12):
        for item in range(6):
            label = item % 2
            data.append({'feedback_id': f'{group}-{item}', 'claim_id': str(group), 'assertion_id': str(group),
                         'assertion_text': f'entity{group} event{group} location{group}',
                         'evidence_id': f'{group}-{item}', 'content_snippet': f'passage{group} item{item}',
                         'canonical_url': f'https://example.org/{group}/{item}',
                         'features': [float(1 - label), 0, 0, 1, 1], 'label': label})
    monkeypatch.setattr(training, 'eligible_data', lambda db: data)
    return data


def test_batch_train_evaluate_promote_rollback(dataset):
    exported = training.export()
    candidate = training.train(exported['dataset_id'])
    report = training.evaluate(candidate['model_id'])
    assert report['baseline']['examples'] == report['candidate']['examples'] == 24
    assert report['train_examples'] == 48
    assert report['groups'] == 12
    assert report['eligible']
    assert report['candidate']['ndcg@5'] > report['baseline']['ndcg@5']
    training.promote(candidate['model_id'])
    assert score([0, 0, 0, 1, 1], candidate['model_id'])[1] == candidate['model_id']
    training.rollback('baseline-v1')
    training.rollback(candidate['model_id'])
    with connect() as db:
        assert db.execute('SELECT COUNT(*) FROM model_decisions').fetchone()[0] == 3
        assert db.execute('SELECT COUNT(*) FROM model_evaluations').fetchone()[0] == 2


def test_failed_evaluation_rejects_promotion(dataset):
    candidate = training.train(training.export()['dataset_id'])['model_id']
    path = artifact_dir() / f'{candidate}.json'
    model = json.loads(path.read_text())
    model['coefficients'] = [.7, .2, .1, 0, 0]
    model['intercept'] = 0
    path.write_text(json.dumps(model))
    assert not training.evaluate(candidate)['eligible']
    with pytest.raises(ValueError, match='Promotion rejected'):
        training.promote(candidate)
    with connect() as db:
        assert db.execute('SELECT model_id FROM active_ranker').fetchone()[0] == 'baseline-v1'


def test_revoked_or_changed_labels_invalidate_candidate(dataset):
    identifier = training.export()['dataset_id']
    candidate = training.train(identifier)['model_id']
    dataset.pop()
    with pytest.raises(ValueError, match='Approved feedback changed'):
        training.promote(candidate)


def test_tampered_dataset_and_unknown_rollback(dataset):
    exported = training.export()
    path = artifact_dir() / f"dataset-{exported['dataset_id']}.json"
    content = json.loads(path.read_text())
    content['examples'][0]['label'] = 9
    path.write_text(json.dumps(content))
    with pytest.raises(ValueError, match='integrity'):
        training.train(exported['dataset_id'])
    with pytest.raises((ValueError, FileNotFoundError)):
        training.rollback('candidate-00000000-0000-0000-0000-000000000000')


def test_insufficient_data_cannot_promote_even_with_candidate_file(dataset):
    dataset[:] = dataset[:6]
    identifier = training.export()['dataset_id']
    candidate = 'candidate-00000000-0000-0000-0000-000000000000'
    training.write(f'{candidate}.json', {'model_id': candidate, 'dataset_id': identifier})
    with pytest.raises(ValueError, match='collecting reviewed feedback'):
        training.promote(candidate)
    with connect() as db:
        assert db.execute('SELECT model_id FROM active_ranker').fetchone()[0] == 'baseline-v1'
