"""Readiness, bounded real-provider runs, candidate collection and pending-safe reporting."""
import argparse
import hmac
import json
import math
import os
import hashlib
import subprocess
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import httpx

from . import datasets, evaluation, training, independent_review, budgets, sources
from .ranking import score
from .reporting import redact, save
from .store import connect, migrate, rows, now, uid

SPEC_VERSION = 'real-source-pilot-v1'


def credentials():
    return {'serpapi': bool(os.getenv('SERPAPI_API_KEY', '').strip()),
            'administrator': len(os.getenv('INVESTIGATION_ADMIN_TOKEN', '')) >= 24}


def authorize(token):
    expected = os.getenv('INVESTIGATION_ADMIN_TOKEN', '')
    if len(expected) < 24 or not hmac.compare_digest(expected, token or ''):
        raise ValueError('Valid administrator token required. No credential value is included in this report.')


def eligibility(data):
    if data['dataset']['state'] != 'frozen':
        return {'eligible': False, 'reason': 'not measured: independent review and freezing pending'}
    if data['dataset']['synthetic']:
        return {'eligible': False, 'reason': 'Synthetic dataset excluded'}
    try:
        data = datasets.load(data['dataset']['id'])
    except ValueError:
        return {'eligible': False, 'reason': 'Frozen snapshot integrity check failed'}
    with connect() as db:
        if db.execute('SELECT 1 FROM evaluation_holdout_locks WHERE dataset_id=?', (data['dataset']['id'],)).fetchone():
            return {'eligible': False, 'reason': 'Final audit consumed; development closed'}
    train = datasets.ranking_rows(data, 'train')
    development = datasets.ranking_rows(data, 'validation')
    try:
        training.enough(train + development, list(range(len(train))), list(range(len(train), len(train) + len(development))),
                        len({c['component'] for c in data['cases'] if c['split'] != 'holdout'}))
        return {'eligible': True, 'train_examples': len(train), 'development_examples': len(development), 'holdout_used': False}
    except ValueError:
        return {'eligible': False, 'reason': 'Insufficient approved train/development labels or independent groups',
                'train_examples': len(train), 'development_examples': len(development), 'holdout_used': False}


def readiness(initialize=False, api_url=None, frontend_url=None):
    existed = Path(os.getenv('INVESTIGATION_DB', 'deepfake.db')).is_file()
    if initialize:
        migrate()
    result = {'report_version': SPEC_VERSION, 'created_at': now(), 'credentials': credentials(),
              'database': {'existed_before': existed, 'initialized': existed or initialize},
              'provider_status': 'configured, live validation not implied' if credentials()['serpapi'] else 'blocked: SERPAPI_API_KEY missing',
              'reviewed_accuracy': 'not measured', 'services': {}}
    if existed or initialize:
        with connect() as db:
            result['database']['migrations'] = [r[0] for r in db.execute('SELECT version FROM investigation_migrations ORDER BY version')]
            if 3 not in result['database']['migrations']:
                result['database']['status'] = 'migration required; run readiness --initialize'
                return redact(result)
            result['counts'] = {table: db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] for table in
                                ('investigations', 'evidence_items', 'evaluation_cases', 'independent_reviews')}
            result['approved_feedback'] = rows(db, "SELECT dimension,COUNT(*) AS count FROM feedback WHERE approval='approved' GROUP BY dimension")
            result['approved_evaluation_labels'] = rows(db, "SELECT dimension,COUNT(*) AS count FROM evaluation_labels WHERE status='approved' GROUP BY dimension")
            active = db.execute('SELECT model_id FROM active_ranker').fetchone()[0]
            result['active_model'] = active
            result['effective_model'] = score([0, 0, 0, 1, 1], active)[1]
            result['worker_last_observation'] = rows(db, 'SELECT observed_at,mode FROM worker_observations ORDER BY observed_at DESC LIMIT 1')
            result['job_counts'] = rows(db, 'SELECT state,COUNT(*) AS count FROM investigation_jobs GROUP BY state')
            ids = [r[0] for r in db.execute('SELECT id FROM evaluation_datasets')]
        result['evaluation_eligibility'] = {identifier: eligibility(datasets.load(identifier, frozen=False)) for identifier in ids}
    for name, url, suffix in [('api', api_url, '/api/learning'), ('frontend', frontend_url, '/')]:
        if url:
            try:
                response = httpx.get(url.rstrip('/') + suffix, timeout=5, follow_redirects=False, trust_env=False)
                result['services'][name] = {'http_status': response.status_code}
            except httpx.HTTPError:
                result['services'][name] = {'status': 'unavailable'}
    if api_url:
        if credentials()['administrator']:
            try:
                r = httpx.get(api_url.rstrip('/') + '/api/admin/evaluations', headers={'Authorization': 'Bearer ' + os.environ['INVESTIGATION_ADMIN_TOKEN']}, timeout=5, follow_redirects=False, trust_env=False)
                result['services']['administrator'] = {'http_status': r.status_code}
            except httpx.HTTPError:
                result['services']['administrator'] = {'status': 'unavailable'}
        else:
            result['services']['administrator'] = {'status': 'blocked: administrator token missing'}
    return redact(result)


def validation_plans():
    asof = date.today().isoformat()
    return [
        {'group_id': 'validation-chemistry', 'assertion': 'The chemical symbol for gold is Au.', 'temporal_context': 'Timeless chemistry assertion', 'categories': ['supported'], 'topic': 'science', 'difficulty': 'straightforward'},
        {'group_id': 'validation-government', 'assertion': f'As of {asof}, Keir Starmer is the prime minister of the United Kingdom.', 'temporal_context': asof, 'categories': ['time-sensitive'], 'topic': 'civics', 'difficulty': 'temporal'},
        {'group_id': 'validation-antibiotics', 'assertion': 'Antibiotics are effective against viral infections in most people.', 'temporal_context': asof, 'categories': ['qualification', 'mixed'], 'topic': 'health', 'difficulty': 'qualified or conflicting'},
        {'group_id': 'validation-mars', 'assertion': 'A permanent human settlement on Mars will open by 2030.', 'temporal_context': 'Prospective statement, as of ' + asof, 'categories': ['insufficient'], 'topic': 'space', 'difficulty': 'insufficient evidence probe'},
    ]


def validate_spec(spec):
    if spec.get('version') != SPEC_VERSION or not isinstance(spec.get('cases'), list) or len(spec['cases']) > 60:
        raise ValueError('Use a real-source-pilot-v1 specification with at most 60 candidate groups')
    seen = set()
    for p in spec['cases']:
        if not all(isinstance(p.get(k), str) and p[k].strip() for k in ('group_id', 'assertion', 'temporal_context', 'topic', 'difficulty')):
            raise ValueError('Every plan needs group_id, assertion, temporal_context, topic and difficulty')
        if p['group_id'] in seen or not 5 <= len(p['assertion']) <= 1500:
            raise ValueError('Duplicate group or invalid assertion size')
        seen.add(p['group_id'])
        if not p.get('categories') or not set(p['categories']) <= datasets.CATEGORIES:
            raise ValueError('Unknown or missing coverage category')
    return spec


def start_run(kind, spec, token, execute=False, max_searches=4, per_query_sources=3, unit_cost=None, max_cost=.1, dataset_id=None):
    validate_spec(spec)
    if not (1 <= max_searches <= 60 and 1 <= per_query_sources <= 10 and math.isfinite(max_cost) and 0 < max_cost <= 10):
        raise ValueError('Limits: 1–60 searches, 1–10 source fetches/query, and positive budget up to $10')
    if unit_cost is not None and (not math.isfinite(unit_cost) or not 0 < unit_cost <= 10):
        raise ValueError('Provide a positive finite per-search upper cost estimate from your provider plan')
    blocked = []
    if not credentials()['serpapi']:
        blocked.append('SERPAPI_API_KEY missing; supplied Supabase configuration cannot authorize SerpAPI')
    if not credentials()['administrator']:
        blocked.append('INVESTIGATION_ADMIN_TOKEN missing or too short')
    if unit_cost is None:
        blocked.append('Per-search cost bound not supplied; account pricing is not assumed')
    if not execute:
        blocked.append('Execution not requested; use --execute with explicit request/cost limits')
    if not spec['cases']:
        blocked.append('Benchmark specification is unpopulated; no completed cases invented')
    if blocked:
        return {'status': 'blocked', 'kind': kind, 'created_at': now(), 'blockers': blocked,
                'search_requests': 0, 'source_fetches': 0, 'actual_cases': 0, 'approved_labels': 0,
                'accuracy': 'not measured', 'fixtures_used': False,
                'limits': {'max_searches': max_searches, 'sources_per_query': per_query_sources, 'max_cost_usd': max_cost, 'unit_cost_usd': unit_cost},
                'planned_categories': sorted({c for p in spec['cases'] for c in p['categories']})}
    authorize(token)
    if dataset_id:
        with connect() as db:
            datasets.require(db, dataset_id, draft=True)
            if not db.execute('SELECT 1 FROM pilot_dataset_policies WHERE dataset_id=?', (dataset_id,)).fetchone():
                raise ValueError('Collection requires a dataset initialized with the independent pilot protocol')
            existing = {json.loads(r[0])['group_id'] for r in db.execute('SELECT j.plan_json FROM pilot_jobs j JOIN pilot_runs r ON r.id=j.run_id WHERE r.dataset_id=?', (dataset_id,))}
    else:
        existing = set()
    plans = [p for p in spec['cases'] if p['group_id'] not in existing][:max_searches]
    if not plans:
        return {'status': 'nothing new to collect', 'actual_cases': 0, 'accuracy': 'not measured'}
    if len(plans) * unit_cost > max_cost + 1e-9:
        raise ValueError('Requested searches exceed the declared cost cap; lower the batch size')
    # Prepared in one transaction; a concurrently running worker cannot acquire unbounded jobs.
    from .api import add_assertions
    run_id = uid()
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('INSERT INTO pilot_runs VALUES (?,?,?,?,?,?,?,?,?,?)',
                   (run_id, kind, now(), json.dumps(spec), max_searches, max_searches * per_query_sources + (1 if kind == 'live-validation' else 0), unit_cost, max_cost, 'queued', dataset_id))
        for p in plans:
            claim_id = uid()
            db.execute('INSERT INTO claims VALUES (?,?,?,?,?,?,?)', (claim_id, p['assertion'], 'TEXT', p['assertion'], 'EXTRACTED', now(), now()))
            db.execute('INSERT INTO investigations VALUES (?,?,?,?,?,?,?)', (claim_id, 'queued', 'serpapi', None, 'lexical-jaccard-v1', p['assertion'], now()))
            add_assertions(db, claim_id, [p['assertion']])
            db.execute('INSERT INTO pilot_jobs VALUES (?,?,?,?,?)', (claim_id, run_id, json.dumps(p), per_query_sources, None))
            db.execute("INSERT INTO investigation_jobs(claim_id,state) VALUES (?,'queued')", (claim_id,))
    if kind == 'live-validation':
        # A real public non-article probe; never represented as retrieved evidence or gold truth.
        probe_url = 'https://example.com/'
        budgets.reserve(run_id, 'source', probe_url)
        probe = sources.enrich({'title': 'Operational non-article probe', 'url': probe_url, 'passage': '', 'publication_date': None,
                                'method': 'direct-operational-probe', 'kind': 'probe only', 'fixture': False}, 'Public article extraction probe')
        spec['operational_probe'] = {'url': probe_url, 'result': probe['source'], 'latency_ms': probe['latency_ms'], 'used_as_evidence': False}
        with connect() as db:
            db.execute('UPDATE pilot_runs SET specification=? WHERE id=?', (json.dumps(redact(spec)), run_id))
    # Real independent processes, bounded iterations, and shared durable state.
    process_failure = None
    for _ in plans:
        try:
            subprocess.run([sys.executable, '-m', 'investigation.worker', '--once', '--run-id', run_id],
                           timeout=60 + per_query_sources * 30, check=True, capture_output=True)
        except subprocess.SubprocessError:
            process_failure = 'Worker process interrupted or failed. Inspect persisted job/search state; recover after lease expiry within the remaining budget.'
            break
    if dataset_id:
        capture(run_id)
    report = run_report(run_id)
    if process_failure:
        report['worker_process_failure'] = process_failure
    return report


def capture(run_id):
    with connect() as db:
        run = db.execute('SELECT * FROM pilot_runs WHERE id=?', (run_id,)).fetchone()
        if not run or not run['dataset_id']:
            raise ValueError('This run is not a benchmark collection')
        jobs = rows(db, 'SELECT j.*, i.stage FROM pilot_jobs j JOIN investigations i ON i.claim_id=j.claim_id WHERE run_id=?', (run_id,))
    for job in jobs:
        if job['case_id'] or job['stage'] not in {'complete', 'partial'}:
            continue
        plan = json.loads(job['plan_json'])
        with connect() as db:
            assertion = db.execute('SELECT id FROM assertions WHERE claim_id=?', (job['claim_id'],)).fetchone()[0]
            old = db.execute('SELECT id FROM evaluation_cases WHERE dataset_id=? AND assertion_id=?', (run['dataset_id'], assertion)).fetchone()
        case_id = old[0] if old else datasets.add(run['dataset_id'], assertion, plan['group_id'], plan['temporal_context'], plan['categories'])
        with connect() as db:
            datasets.require(db, run['dataset_id'], draft=True)
            c = db.execute('SELECT snapshot_json FROM evaluation_cases WHERE id=?', (case_id,)).fetchone()
            if old and (db.execute('SELECT 1 FROM independent_reviews WHERE case_id=?', (case_id,)).fetchone()
                        or db.execute('SELECT 1 FROM evaluation_labels WHERE case_id=?', (case_id,)).fetchone()):
                raise ValueError('Interrupted capture already has reviews; preserve it and resolve manually before recapturing')
            snapshot = json.loads(c[0])
            snapshot['collection'] = {'specification_version': SPEC_VERSION, 'run_id': run_id, 'topic': plan['topic'], 'difficulty': plan['difficulty']}
            for e in snapshot['evidence']:
                source = e.get('source') or {}
                e['source_group_id'] = 'source-' + (source.get('content_hash') or datasets.digest(e['canonical_url']))
            snapshot['candidate_snapshot_hash'] = datasets.digest({k: v for k, v in snapshot.items() if k != 'candidate_snapshot_hash'})
            db.execute('UPDATE evaluation_cases SET snapshot_json=? WHERE id=?', (json.dumps(snapshot), case_id))
            db.execute('UPDATE pilot_jobs SET case_id=? WHERE claim_id=?', (case_id, job['claim_id']))
    independent_review.assign_subset(run['dataset_id'])


def run_report(run_id):
    with connect() as db:
        row = db.execute('SELECT * FROM pilot_runs WHERE id=?', (run_id,)).fetchone()
        if not row:
            raise ValueError('Run not found')
        run = dict(row)
        spec = json.loads(run.pop('specification'))
        counts = {r['kind']: r['n'] for r in rows(db, 'SELECT kind,COUNT(*) AS n FROM pilot_requests WHERE run_id=? GROUP BY kind', (run_id,))}
        jobs = rows(db, 'SELECT p.claim_id,p.case_id,i.stage FROM pilot_jobs p JOIN investigations i ON i.claim_id=p.claim_id WHERE p.run_id=?', (run_id,))
        searches = rows(db, '''SELECT s.*, o.latency_ms FROM searches s LEFT JOIN search_observations o ON s.id=o.search_id
                              WHERE s.claim_id IN (SELECT claim_id FROM pilot_jobs WHERE run_id=?)''', (run_id,))
        evidence = rows(db, '''SELECT e.id,e.assertion_id,e.source_url,e.content_snippet,d.passage_kind,p.source_id,p.start_offset,p.end_offset,
                       p.context,s.final_url,s.content_hash,s.body_hash,s.main_text,s.retrieved_at,s.method,s.status,s.error,o.latency_ms
                       FROM evidence_items e JOIN evidence_details d ON d.evidence_id=e.id JOIN source_passages p ON p.evidence_id=e.id
                       JOIN source_documents s ON s.id=p.source_id LEFT JOIN source_observations o ON o.source_id=s.id
                       JOIN assertions a ON a.id=e.assertion_id WHERE a.claim_id IN (SELECT claim_id FROM pilot_jobs WHERE run_id=?)''', (run_id,))
    for e in evidence:
        text = e.pop('main_text')
        e['traceability_verified'] = (hashlib.sha256(text.encode()).hexdigest() == e['content_hash'] and text[e['start_offset']:e['end_offset']] == e['content_snippet']) if e['status'] == 'extracted' else None
    finished = all(j['stage'] in {'complete', 'partial'} for j in jobs)
    return redact({'run': run, 'status': 'completed with recorded outcomes' if finished else 'pending worker', 'jobs': jobs,
                   'requests_reserved': counts, 'declared_cost_upper_usd': counts.get('search', 0) * run['unit_cost'],
                   'pricing_limitation': 'Caller-supplied per-query price bound, not a provider billing statement; reservations include failures/crashes.',
                   'maximum_source_http_requests': run['max_sources'] * 4, 'searches': searches, 'evidence': evidence,
                   'operational_probe': spec.get('operational_probe'), 'fixtures_used': False,
                   'extraction_outcomes': dict(Counter(e['status'] for e in evidence)), 'reviewed_accuracy': 'not measured by operational validation'})


def benchmark_status(dataset_id=None):
    if not dataset_id:
        return {'status': 'not measured', 'actual_cases': 0, 'approved_labels': 0, 'missing_labels': None,
                'reason': 'No candidate benchmark dataset selected', 'ranking': None, 'stance': None, 'sufficiency': None, 'citation_support': None,
                'candidate_comparison': 'not measured', 'promotion_decision': 'not attempted; active model unchanged'}
    data = datasets.load(dataset_id, frozen=False)
    required = sum(1 + len(c['snapshot']['evidence']) * 3 for c in data['cases'])
    approved = sum(r['status'] == 'approved' for c in data['cases'] for r in c['reviews'])
    return {'status': 'ready for approved evaluation' if data['dataset']['state'] == 'frozen' else 'not measured',
            'dataset_id': dataset_id, 'version': data['dataset']['version'], 'actual_cases': len(data['cases']),
            'approved_labels': approved, 'required_labels': required, 'missing_labels': required - approved,
            'class_balance': {d: dict(Counter(r['label'] for c in data['cases'] for r in c['reviews'] if r['dimension'] == d and r['status'] == 'approved')) for d in datasets.LABELS},
            'eligibility': eligibility(data), 'accuracy': 'not measured until approved frozen data is evaluated',
            'candidate_comparison': 'not measured by readiness/status', 'promotion_decision': 'not attempted by status; active model unchanged',
            'agreement': independent_review.agreement(dataset_id)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--token', default=None)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('readiness'); p.add_argument('--initialize', action='store_true'); p.add_argument('--api-url'); p.add_argument('--frontend-url')
    for command in ('live-validate', 'collect'):
        p = sub.add_parser(command); p.add_argument('--execute', action='store_true'); p.add_argument('--max-searches', type=int, default=4)
        p.add_argument('--sources-per-query', type=int, default=3 if command == 'live-validate' else 8); p.add_argument('--unit-cost-usd', type=float); p.add_argument('--max-cost-usd', type=float, default=.1)
        if command == 'collect':
            p.add_argument('--spec', required=True); p.add_argument('--dataset')
    p = sub.add_parser('init-benchmark'); p.add_argument('--name', default='real-source-pilot'); p.add_argument('--version', required=True)
    p = sub.add_parser('capture'); p.add_argument('run_id')
    p = sub.add_parser('run-report'); p.add_argument('run_id')
    p = sub.add_parser('packet'); p.add_argument('dataset'); p.add_argument('--phase', choices=['initial','citation'], default='initial')
    p = sub.add_parser('submit-sheet'); p.add_argument('path'); p.add_argument('--reviewer', required=True)
    for command in ('review', 'adjudicate'):
        p = sub.add_parser(command); p.add_argument('case'); p.add_argument('--target', default=''); p.add_argument('--dimension', choices=sorted(datasets.LABELS), required=True)
        p.add_argument('--label', required=True); p.add_argument('--reviewer', required=True); p.add_argument('--reason', required=True)
    p = sub.add_parser('agreement'); p.add_argument('dataset')
    p = sub.add_parser('status'); p.add_argument('--dataset')
    p = sub.add_parser('evaluate'); p.add_argument('dataset'); p.add_argument('--model', default='baseline-v1')
    p = sub.add_parser('failures'); p.add_argument('--dataset')
    p = sub.add_parser('observe'); p.add_argument('case'); p.add_argument('--target', default=''); p.add_argument('--kind', required=True); p.add_argument('--reviewer', required=True); p.add_argument('--detail', required=True)
    p = sub.add_parser('confirm-observation'); p.add_argument('observation'); p.add_argument('--decision', choices=['confirmed','rejected'], required=True); p.add_argument('--reviewer', required=True); p.add_argument('--reason', required=True)
    args = parser.parse_args()
    try:
        if args.command == 'readiness':
            result = readiness(args.initialize, args.api_url, args.frontend_url)
        else:
            migrate()
            if args.command in {'live-validate', 'collect'}:
                spec = {'version': SPEC_VERSION, 'cases': validation_plans()} if args.command == 'live-validate' else json.loads(Path(args.spec).read_text())
                if args.command == 'collect' and args.execute and not args.dataset and credentials()['serpapi'] and credentials()['administrator']:
                    raise ValueError('Initialize and select a pilot dataset before collection')
                result = start_run('live-validation' if args.command == 'live-validate' else 'collection', spec, args.token,
                                   args.execute, args.max_searches, args.sources_per_query, args.unit_cost_usd, args.max_cost_usd, getattr(args, 'dataset', None))
            elif args.command == 'status':
                if args.dataset:
                    authorize(args.token)
                result = benchmark_status(args.dataset)
            elif args.command == 'failures':
                if args.dataset:
                    authorize(args.token)
                from .failure_analysis import analyze
                result = analyze(args.dataset)
            else:
                authorize(args.token)
                if args.command == 'init-benchmark':
                    identifier = datasets.create(args.name, args.version, seed=17)
                    independent_review.manage(identifier)
                    result = {'dataset_id': identifier, 'actual_cases': 0, 'approved_labels': 0, 'status': 'unpopulated candidate benchmark'}
                elif args.command == 'capture':
                    capture(args.run_id); result = run_report(args.run_id)
                elif args.command == 'run-report':
                    result = run_report(args.run_id)
                elif args.command == 'packet':
                    result = independent_review.packet(args.dataset, args.phase)
                    directory = training.artifact_dir() / 'pilot-reports'
                    directory.mkdir(parents=True, exist_ok=True)
                    independent_review.write_sheet(result, directory / f'review-{args.dataset}-{args.phase}.csv')
                elif args.command == 'submit-sheet':
                    result = independent_review.submit_sheet(args.path, args.reviewer)
                elif args.command == 'review':
                    result = independent_review.submit(args.case, args.target, args.dimension, args.label, args.reviewer, args.reason)
                elif args.command == 'adjudicate':
                    result = independent_review.adjudicate(args.case, args.target, args.dimension, args.label, args.reviewer, args.reason)
                elif args.command == 'agreement':
                    result = independent_review.agreement(args.dataset)
                elif args.command == 'observe':
                    from .failure_analysis import observe
                    result = observe(args.case, args.target, args.kind, args.detail, args.reviewer)
                elif args.command == 'confirm-observation':
                    from .failure_analysis import confirm
                    result = confirm(args.observation, args.decision, args.reviewer, args.reason)
                else:
                    status = benchmark_status(args.dataset)
                    result = evaluation.evaluate(args.dataset, args.model, 'validation') if status['status'] == 'ready for approved evaluation' else status
        name = args.command + ('-' + args.dataset + '-' + args.phase if args.command == 'packet' else '')
        print(json.dumps(save(name, result), indent=2))
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        parser.exit(1, str(redact(str(exc))) + '\n')


if __name__ == '__main__':
    main()
