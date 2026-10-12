"""Synthetic functionality tests. No real reviewer identities or live-provider results."""
import json
import logging
import os
import subprocess

import httpx
import pytest

from investigation import pilot, datasets, independent_review as reviews, budgets, worker, sources, retrieval, reporting, evaluation, training
from investigation.comparison import compare
from investigation.failure_analysis import analyze
from investigation.store import connect, migrate, now, uid
from test_foundation import client
from test_evaluation import case_fixture, approve_case
from test_sources import HTML


def test_readiness_and_missing_credentials_never_fabricate_cases(client, monkeypatch):
    monkeypatch.delenv('INVESTIGATION_ADMIN_TOKEN', raising=False)
    report = pilot.readiness()
    assert report['database']['initialized']
    assert report['credentials'] == {'serpapi': False, 'administrator': False}
    assert report['counts']['evaluation_cases'] == 0
    assert report['active_model'] == 'baseline-v1'
    assert report['reviewed_accuracy'] == 'not measured'
    monkeypatch.setattr(sources, 'enrich', lambda *a: pytest.fail('No network operation is allowed when blocked'))
    blocked = pilot.start_run('live-validation', {'version': pilot.SPEC_VERSION, 'cases': pilot.validation_plans()}, None, True, unit_cost=.01)
    assert blocked['status'] == 'blocked' and blocked['search_requests'] == 0
    assert not blocked['fixtures_used']
    with connect() as db:
        assert db.execute('SELECT COUNT(*) FROM pilot_runs').fetchone()[0] == 0
    assert pilot.benchmark_status()['status'] == 'not measured'
    assert analyze()['findings'] == []


def test_reports_and_provider_logs_redact_secrets(client, monkeypatch, caplog, tmp_path):
    secret = 'SYNTHETIC-SECRET-DO-NOT-LOG-12345'
    monkeypatch.setenv('SERPAPI_API_KEY', secret)
    saved = reporting.save('redaction-test', {'url': 'https://example.org/?api_key=' + secret, 'error': secret, 'token': secret})
    assert secret not in json.dumps(saved)
    caplog.set_level(logging.INFO)
    original_client = httpx.Client
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json={'organic_results': []}))
    monkeypatch.setattr(httpx, 'Client', lambda **kw: original_client(transport=transport, **kw))
    assert retrieval.SerpAPI().search('Synthetic secret-redaction test') == []
    assert secret not in caplog.text
    assert secret not in (training.artifact_dir() / 'pilot-reports/redaction-test.json').read_text()
    assert secret not in (training.artifact_dir() / 'pilot-reports/redaction-test.md').read_text()


def test_budget_reservations_survive_restart_and_cap_cost(client):
    identifier = uid()
    with connect() as db:
        db.execute('INSERT INTO pilot_runs VALUES (?,?,?,?,?,?,?,?,?,?)', (identifier, 'test', now(), '{}', 2, 1, .01, .01, 'queued', None))
    budgets.reserve(identifier, 'search', 'first')
    migrate()
    with pytest.raises(retrieval.Unavailable, match='limit'):
        budgets.reserve(identifier, 'search', 'after restart')
    budgets.reserve(identifier, 'source', 'first source')
    with pytest.raises(retrieval.Unavailable):
        budgets.reserve(identifier, 'source', 'second source')


def test_candidate_collection_preserves_source_provenance_and_no_approvals(client, monkeypatch):
    monkeypatch.setenv('SERPAPI_API_KEY', 'SYNTHETIC-NETWORK-MOCK-KEY')
    monkeypatch.setenv('SOURCE_EXTRACTION_PROVIDER', 'public-article')
    monkeypatch.setattr(sources, 'fetch_document', lambda url: {'body': HTML, 'final_url': url + '/final'})
    monkeypatch.setattr(retrieval.SerpAPI, 'search', lambda self, query: [{'title': 'Synthetic test source', 'url': 'https://example.org/source',
        'passage': 'Synthetic search snippet.', 'publication_date': None, 'method': 'mock-provider', 'kind': 'search snippet', 'fixture': False}])
    monkeypatch.setattr(pilot.subprocess, 'run', lambda args, **kw: worker.run_once(args[-1]))
    identifier = datasets.create('SYNTHETIC collection simulation', '1')
    reviews.manage(identifier)
    result = pilot.start_run('collection', {'version': pilot.SPEC_VERSION, 'cases': pilot.validation_plans()[:1]},
        os.environ['INVESTIGATION_ADMIN_TOKEN'], True, max_searches=1, per_query_sources=1, unit_cost=.01, max_cost=.01, dataset_id=identifier)
    assert result['requests_reserved'] == {'search': 1, 'source': 1}
    assert result['declared_cost_upper_usd'] == .01
    assert result['evidence'][0]['traceability_verified']
    data = datasets.load(identifier, frozen=False)
    assert len(data['cases']) == 1
    c = data['cases'][0]
    assert c['snapshot']['candidate_snapshot_hash']
    assert c['snapshot']['evidence'][0]['source_group_id'].startswith('source-')
    assert c['snapshot']['evidence'][0]['source']['content_hash']
    assert c['reviews'] == []
    assert c['independent_review']['required_reviewers'] == 2
    assert pilot.benchmark_status(identifier)['approved_labels'] == 0
    assert analyze(identifier)['status'].startswith('not measured')


def test_worker_failure_keeps_durable_pending_run_without_leaking_command(client, monkeypatch):
    monkeypatch.setenv('SERPAPI_API_KEY', 'SYNTHETIC-NETWORK-MOCK-KEY')
    def interrupted(*args, **kwargs):
        raise subprocess.TimeoutExpired('SYNTHETIC-SENSITIVE-COMMAND', 1)
    monkeypatch.setattr(pilot.subprocess, 'run', interrupted)
    result = pilot.start_run('collection', {'version': pilot.SPEC_VERSION, 'cases': pilot.validation_plans()[:1]},
        os.environ['INVESTIGATION_ADMIN_TOKEN'], True, max_searches=1, unit_cost=.01, max_cost=.01)
    assert result['status'] == 'pending worker'
    assert result['worker_process_failure']
    assert result['requests_reserved'] == {}
    assert 'SYNTHETIC-SENSITIVE-COMMAND' not in json.dumps(result)


def test_blind_packets_and_blank_sheet_do_not_reveal_predictions(client, tmp_path):
    identifier = datasets.create('SYNTHETIC blinded review', '1')
    case_fixture(client, identifier)
    reviews.manage(identifier); reviews.assign_subset(identifier)
    packet = reviews.packet(identifier)
    text = json.dumps(packet)
    for field in ('predicted_stance', 'ranker', 'relevance', 'approved_feedback_at_capture', 'captured_assessment'):
        assert '"' + field + '":' not in text
    assert 'captured_assessment' in reviews.packet(identifier, 'citation')['cases'][0]
    path = tmp_path / 'blank.csv'
    reviews.write_sheet(packet, path)
    result = reviews.submit_sheet(path, 'SYNTHETIC-REVIEWER-A')
    assert result['responses'] == 0
    assert result['blank_rows_skipped'] == 13


def test_disagreement_requires_adjudication_and_stays_in_history(client):
    identifier = datasets.create('SYNTHETIC disagreement', '1')
    case = case_fixture(client, identifier)
    reviews.manage(identifier); reviews.assign_subset(identifier)
    data = datasets.load(identifier, frozen=False)
    target = data['cases'][0]['snapshot']['evidence'][0]['id']
    reviews.submit(case, target, 'relevance', 'relevant', 'SYNTHETIC-REVIEWER-A', 'Synthetic relevance opinion')
    with pytest.raises(ValueError, match='missing'):
        reviews.adjudicate(case, target, 'relevance', 'relevant', 'SYNTHETIC-ADJUDICATOR', 'Synthetic decision')
    reviews.submit(case, target, 'relevance', 'irrelevant', 'SYNTHETIC-REVIEWER-B', 'Synthetic disagreement')
    assert reviews.agreement(identifier)['disagreements'][0]['status'] == 'unresolved'
    with pytest.raises(ValueError, match='direct approval'):
        datasets.label(case, target, 'relevance', 'relevant', 'SYNTHETIC-OPERATOR', 'approved', 'Cannot bypass protocol')
    with pytest.raises(ValueError, match='distinct'):
        reviews.adjudicate(case, target, 'relevance', 'relevant', 'SYNTHETIC-REVIEWER-A', 'Synthetic decision')
    reviews.adjudicate(case, target, 'relevance', 'relevant', 'SYNTHETIC-ADJUDICATOR', 'Synthetic decision after considering both opinions')
    assert reviews.agreement(identifier)['disagreements'][0]['status'].startswith('adjudicated')
    assert len(datasets.load(identifier, frozen=False)['cases'][0]['independent_review']['opinions']) == 2
    reviews.submit(case, target, 'relevance', 'irrelevant', 'SYNTHETIC-REVIEWER-A', 'Synthetic amended opinion')
    assert datasets.approved(datasets.load(identifier, frozen=False)['cases'][0], target, 'relevance') is None
    with pytest.raises(ValueError, match='pending'):
        datasets.freeze(identifier)


def test_independent_approval_snapshot_and_legacy_frozen_hash_stability(client):
    old = datasets.create('SYNTHETIC preserved frozen', '1')
    old_case = case_fixture(client, old, 99)
    approve_case(old_case)
    old_hash = datasets.freeze(old)['frozen_hash']
    migrate()
    assert datasets.load(old)['dataset']['frozen_hash'] == old_hash
    identifier = datasets.create('SYNTHETIC independent review complete', '1')
    case = case_fixture(client, identifier, 5)
    reviews.manage(identifier); reviews.assign_subset(identifier)
    c = datasets.load(identifier, frozen=False)['cases'][0]
    labels = [('', 'sufficiency', 'insufficient')]
    labels += [(e['id'], dim, label) for e in c['snapshot']['evidence'] for dim, label in [('relevance','relevant'), ('stance','needing review'), ('citation','needs review')]]
    for target, dim, label in labels:
        for person in ('SYNTHETIC-REVIEWER-A', 'SYNTHETIC-REVIEWER-B'):
            reviews.submit(case, target, dim, label, person, 'Synthetic protocol test only')
        reviews.adjudicate(case, target, dim, label, 'SYNTHETIC-ADJUDICATOR', 'Synthetic protocol test only')
    frozen = datasets.freeze(identifier)
    assert datasets.load(identifier)['dataset']['frozen_hash'] == frozen['frozen_hash']
    with pytest.raises(ValueError, match='Frozen'):
        reviews.submit(case, '', 'sufficiency', 'sufficient', 'SYNTHETIC-REVIEWER-A', 'Cannot change frozen review')


def test_paired_uncertainty_inconclusive_and_example_identity():
    examples = []
    for g in range(4):
        for j in range(6):
            # Three improving groups and one regressing group: a positive point estimate
            # can still have an inconclusive component-level interval.
            examples.append({'assertion_id': str(g), 'evidence_id': f'{g}-{j}', 'features': [j,0,0,1,1], 'label': int(j < 3) if g else int(j >= 3)})
    result = compare(examples, lambda x: -x[0], {str(g): str(g) for g in range(4)}, {str(g): ['qualification'] for g in range(4)}, 17)
    assert result['status'] == 'inconclusive'
    assert not result['improvement_demonstrated']
    assert result['mean_deltas']['ndcg@5_delta'] > 0
    base = training.metrics(examples, list(range(len(examples))), training.baseline)
    candidate = training.metrics(examples, list(range(len(examples))), lambda x: -x[0])
    assert training.eligible_metrics(base, candidate)  # Old point gate alone would pass.
    assert result['paired_assertions'] == 4
    assert sum(p['examples'] for p in result['pairs']) == len(examples)
    assert result == compare(examples, lambda x: -x[0], {str(g): str(g) for g in range(4)}, {str(g): ['qualification'] for g in range(4)}, 17)
    assert result['category_regressions']['qualification']['regressed_assertions']


def test_short_queries_not_measured_and_holdout_cannot_be_development(client):
    identifier = datasets.create('SYNTHETIC short queries', '1')
    case = case_fixture(client, identifier)
    approve_case(case)
    datasets.freeze(identifier)
    report = evaluation.evaluate(identifier)
    assert report['accuracy_status'] == 'not measured'
    assert report['ranking']['baseline'] is None
    evaluation.evaluate(identifier, partition='holdout')
    with pytest.raises(ValueError, match='closed'):
        evaluation.evaluate(identifier)
    assert 'closed' in analyze(identifier)['status']


def test_observed_failures_require_confirmation_and_exclude_holdout(client):
    from investigation.failure_analysis import observe, confirm
    identifier = datasets.create('SYNTHETIC failure observations', '1')
    for i in range(5):
        approve_case(case_fixture(client, identifier, i))
    datasets.freeze(identifier)
    data = datasets.load(identifier)
    c = next(c for c in data['cases'] if c['split'] == 'validation')
    holdout = next(c for c in data['cases'] if c['split'] == 'holdout')
    target = c['snapshot']['evidence'][0]['id']
    observation = observe(c['id'], target, 'stale_source', 'Synthetic test-only temporal error observation', 'SYNTHETIC-OBSERVER')
    assert not any(f['kind'] == 'stale_source' for f in analyze(identifier)['findings'])
    with pytest.raises(ValueError, match='different reviewer'):
        confirm(observation['observation_id'], 'confirmed', 'SYNTHETIC-OBSERVER', 'Synthetic confirmation')
    confirm(observation['observation_id'], 'confirmed', 'SYNTHETIC-CONFIRMER', 'Synthetic independently confirmed error')
    finding = next(f for f in analyze(identifier)['findings'] if f['kind'] == 'stale_source')
    assert finding['url'] == c['snapshot']['evidence'][0]['source_url']
    with pytest.raises(ValueError, match='holdout'):
        observe(holdout['id'], '', 'stale_source', 'Must not expose held-out evidence in development', 'SYNTHETIC-OBSERVER')


def test_agreement_is_calculated_only_with_enough_paired_reviews(client):
    identifier = datasets.create('SYNTHETIC paired agreement', '1')
    for i in range(2):
        case_fixture(client, identifier, i)
    reviews.manage(identifier); reviews.assign_subset(identifier)
    for index, c in enumerate(datasets.load(identifier, frozen=False)['cases']):
        for j, e in enumerate(c['snapshot']['evidence']):
            label = 'relevant' if j % 2 else 'irrelevant'
            reviews.submit(c['id'], e['id'], 'relevance', label, 'SYNTHETIC-REVIEWER-A', 'Synthetic paired opinion')
            second = 'relevant' if index == 0 and j == 0 else label
            reviews.submit(c['id'], e['id'], 'relevance', second, 'SYNTHETIC-REVIEWER-B', 'Synthetic paired opinion')
    result = reviews.agreement(identifier)
    assert result['dimensions']['relevance']['paired_items'] == 12
    assert result['dimensions']['relevance']['cohen_kappa'] == pytest.approx(5 / 6)
    assert result['dimensions']['stance']['cohen_kappa'] is None
    assert len(result['disagreements']) == 1
