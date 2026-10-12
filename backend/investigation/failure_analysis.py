"""Traceable development errors; unknown recall/staleness is never invented."""
import json
from collections import Counter, defaultdict

from . import datasets
from .ranking import baseline
from .stance import GuardedRules
from .store import connect, rows, uid, now

KINDS = {'relevant_missed', 'irrelevant_top5', 'incorrect_stance', 'insufficient_overstatement',
         'stale_source', 'duplicate_source', 'extraction_failure', 'misleading_context'}


def observe(case_id, target, kind, detail, reviewer):
    if kind not in KINDS or len(detail.strip()) < 10 or len(reviewer.strip()) < 3:
        raise ValueError('Provide a valid failure category, traceable observation and real reviewer identifier')
    with connect() as db:
        case = db.execute('SELECT * FROM evaluation_cases WHERE id=?', (case_id,)).fetchone()
        if not case:
            raise ValueError('Case not found')
        if case['split'] == 'holdout':
            raise ValueError('Development failure tooling cannot inspect holdout cases; use the existing final audit only')
        snapshot = json.loads(case['snapshot_json'])
        if target and target not in {e['id'] for e in snapshot['evidence']}:
            raise ValueError('Target is not part of this case')
        identifier = uid()
        db.execute('INSERT INTO failure_observations VALUES (?,?,?,?,?,?,?)', (identifier, case_id, target, kind, detail, reviewer.strip().casefold(), now()))
    return {'observation_id': identifier, 'status': 'pending independent confirmation'}


def confirm(identifier, decision, reviewer, reason):
    if decision not in {'confirmed', 'rejected'} or len(reason.strip()) < 5 or len(reviewer.strip()) < 3:
        raise ValueError('Confirmation requires decision, actual reviewer and reason')
    with connect() as db:
        observed = db.execute('SELECT * FROM failure_observations WHERE id=?', (identifier,)).fetchone()
        if not observed or observed['reviewer'] == reviewer.strip().casefold():
            raise ValueError('A different reviewer must confirm or reject this observation')
        db.execute('INSERT INTO failure_observation_reviews VALUES (?,?,?,?,?,?)', (uid(), identifier, decision, reviewer.strip().casefold(), reason, now()))
    return {'status': decision}


def analyze(dataset_id=None):
    pending = {'status': 'not measured: failure analysis pending approved development cases', 'findings': [],
               'recommendations': [], 'hypotheses_are_not_observations': True}
    if not dataset_id:
        return pending
    data = datasets.load(dataset_id, frozen=False)
    if data['dataset']['state'] != 'frozen':
        return {**pending, 'dataset_id': dataset_id}
    data = datasets.load(dataset_id)
    with connect() as db:
        if db.execute('SELECT 1 FROM evaluation_holdout_locks WHERE dataset_id=?', (dataset_id,)).fetchone():
            return {**pending, 'status': 'development closed after final audit; use previously saved findings', 'dataset_id': dataset_id}
    cases = [c for c in data['cases'] if c['split'] == 'validation']
    if not cases:
        return {**pending, 'dataset_id': dataset_id}
    findings = []
    def record(kind, case, e, explanation):
        source = e.get('source') or {}
        findings.append({'kind': kind, 'case_id': case['id'], 'assertion_id': case['assertion_id'],
                         'evidence_id': e.get('id'), 'url': e.get('source_url'), 'source_id': source.get('source_id'),
                         'content_hash': source.get('content_hash'), 'explanation': explanation})
    for c in cases:
        s = c['snapshot']
        ranked = sorted(s['evidence'], key=lambda e: (-baseline(json.loads(e['features'])), e['id']))
        seen = set()
        for position, e in enumerate(ranked, 1):
            relevant = datasets.approved(c, e['id'], 'relevance')
            truth = datasets.approved(c, e['id'], 'stance')
            predicted = GuardedRules().classify(s['assertion_text'], e['content_snippet'], (e.get('source') or {}).get('context', ''))['stance']
            if position <= 5 and relevant == 'irrelevant':
                record('irrelevant_top5', c, e, f'Baseline position {position}; approved irrelevant label')
            if position > 5 and relevant == 'relevant':
                record('relevant_missed', c, e, f'Relevant retrieved passage below cutoff at position {position}; not a claim about search recall')
            if predicted != truth:
                record('stance_abstention' if predicted == 'needing review' else 'incorrect_stance', c, e, f'{predicted} versus independently approved {truth}')
            source = e.get('source') or {}
            identity = source.get('content_hash') or e['canonical_url']
            if identity in seen:
                record('duplicate_source', c, e, 'Repeated canonical URL or exact extracted-text hash within this assertion')
            seen.add(identity)
            if source and source.get('status') not in {'extracted', 'offline', 'disabled', 'legacy_not_attempted'}:
                record('extraction_failure', c, e, f"Recorded source extraction outcome: {source.get('status')}")
        if datasets.approved(c, '', 'sufficiency') == 'insufficient' and s['assessment'] != 'insufficient evidence':
            record('insufficient_overstatement', c, {}, 'Captured assessment is stronger than the independently approved sufficiency judgment')
    with connect() as db:
        for c in cases:
            for item in rows(db, 'SELECT * FROM failure_observations WHERE case_id=?', (c['id'],)):
                review = db.execute('SELECT * FROM failure_observation_reviews WHERE observation_id=? ORDER BY created_at DESC,id DESC LIMIT 1', (item['id'],)).fetchone()
                if review and review['decision'] == 'confirmed':
                    e = next((e for e in c['snapshot']['evidence'] if e['id'] == item['target']), {})
                    source = e.get('source') or {}
                    findings.append({**item, 'url': e.get('source_url'), 'source_id': source.get('source_id'),
                                     'content_hash': source.get('content_hash'), 'confirmation': dict(review),
                                     'basis': 'independently confirmed human observation'})
    counts = Counter(f['kind'] for f in findings)
    suggestions = {'irrelevant_top5': 'Inspect the cited irrelevant top-ranked passages and their lexical/entity features before altering the ranker.',
                   'incorrect_stance': 'Review the cited entity, scope, negation and attribution errors before changing stance rules.',
                   'insufficient_overstatement': 'Revisit the source-based sufficiency threshold for the cited overstated assertions.',
                   'extraction_failure': 'Inspect recorded failure categories and affected layouts; do not bypass access restrictions.',
                   'duplicate_source': 'Review the cited source groups and syndication before counting independent support.',
                   'stale_source': 'Use the confirmed temporal findings to design a source freshness policy.',
                   'misleading_context': 'Inspect the confirmed missing-context examples before changing passage windows.'}
    return {'status': 'observed development findings', 'dataset_id': dataset_id, 'dataset_version': data['dataset']['version'],
            'synthetic': bool(data['dataset']['synthetic']), 'development_cases': len(cases), 'holdout_used': False,
            'findings': findings, 'counts': dict(counts), 'recommendations': [suggestions[k] for k in counts if k in suggestions][:3],
            'limitations': ['True search recall requires independently identified missing reference sources; top-k misses here are within the collected pool.',
                            'Source age alone is not staleness. Stale-source and misleading-context findings require independently confirmed human observations.']}
