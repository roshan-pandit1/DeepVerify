import pytest

from investigation import retrieval, worker, training
from investigation.stance import GuardedRules, LegacyRules
from investigation.store import connect
from test_foundation import client, create, AUTH


@pytest.mark.parametrize('classifier', [GuardedRules(), LegacyRules()])
@pytest.mark.parametrize('passage', ['Mercury has no moons.', 'Mercury has many moons.', 'Bananas contain potassium.'])
def test_builtin_automation_never_asserts_entailment(classifier, passage):
    assert classifier.classify('Mercury has no moons.', passage)['stance'] in {'unrelated', 'needing review'}


def test_only_approved_stance_changes_assessment_never_relevance_training(client, monkeypatch):
    source = {'title': 'Synthetic policy test', 'url': 'https://example.org/synthetic',
              'passage': 'Mercury has no moons.', 'publication_date': None,
              'method': 'synthetic-network-mock', 'kind': 'search snippet', 'fixture': False}
    monkeypatch.setattr(retrieval.SerpAPI, 'search', lambda *a: [source])
    item = create(client, 'Mercury has no moons.', 'serpapi')
    identifier = item['claim_id']
    client.post(f'/api/investigations/{identifier}/run')
    worker.run_once()
    report = client.get(f'/api/investigations/{identifier}').json()
    assertion = report['assertions'][0]
    evidence = assertion['evidence'][0]
    assert assertion['assessment'] == 'insufficient evidence'
    assert evidence['feedback'] == []
    feedback = client.post(f"/api/evidence/{evidence['id']}/feedback", json={
        'reviewer': 'synthetic-reviewer', 'dimension': 'stance', 'label': 'supporting'}).json()
    assert client.get(f'/api/investigations/{identifier}').json()['assertions'][0]['assessment'] == 'insufficient evidence'
    client.post(f"/api/admin/feedback/{feedback['id']}/review", headers=AUTH,
                json={'decision': 'approved', 'reason': 'Synthetic workflow policy check only'})
    reviewed = client.get(f'/api/investigations/{identifier}').json()['assertions'][0]
    assert reviewed['assessment'] == 'supported'
    assert reviewed['evidence'][0]['predicted_stance'] == evidence['predicted_stance']
    with connect() as db:
        assert training.eligible_data(db) == []
