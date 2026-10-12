"""Blind first-pass packets, independent opinions, and explicit human adjudication."""
import json
import math
import csv
from pathlib import Path
from collections import Counter, defaultdict

from . import datasets
from .store import connect, rows, now, uid

PROTOCOL = 'blind-independent-review-v1'


def manage(dataset_id):
    with connect() as db:
        datasets.require(db, dataset_id, draft=True)
        db.execute('INSERT OR IGNORE INTO pilot_dataset_policies VALUES (?,?,?)', (dataset_id, PROTOCOL, now()))


def assign_subset(dataset_id):
    """At least 20% of collected claim groups, selected before any opinions are submitted."""
    with connect() as db:
        datasets.require(db, dataset_id, draft=True)
        cases = rows(db, 'SELECT id, related_group FROM evaluation_cases WHERE dataset_id=?', (dataset_id,))
        groups = sorted({c['related_group'] for c in cases}, key=datasets.digest)
        selected = set(groups[:math.ceil(len(groups) * .2)])
        for c in cases:
            db.execute('INSERT INTO pilot_case_policies VALUES (?,?) ON CONFLICT(case_id) DO UPDATE SET required_reviewers=MAX(required_reviewers, excluded.required_reviewers)',
                       (c['id'], 2 if c['related_group'] in selected else 1))


def latest(db, case_id, target, dimension):
    records = rows(db, 'SELECT * FROM independent_reviews WHERE case_id=? AND target=? AND dimension=? ORDER BY created_at, id', (case_id, target, dimension))
    by_reviewer = {r['reviewer']: r for r in records}
    return sorted(by_reviewer.values(), key=lambda r: r['reviewer'])


def validate_target(db, case_id, target, dimension, label):
    case = db.execute('SELECT * FROM evaluation_cases WHERE id=?', (case_id,)).fetchone()
    if not case:
        raise ValueError('Evaluation case not found')
    datasets.require(db, case['dataset_id'], draft=True)
    policy = db.execute('SELECT * FROM pilot_case_policies WHERE case_id=?', (case_id,)).fetchone()
    if not policy:
        raise ValueError('This case is not assigned to the independent-review protocol')
    if dimension not in datasets.LABELS or label not in datasets.LABELS[dimension]:
        raise ValueError('Invalid independent label')
    evidence = json.loads(case['snapshot_json'])['evidence']
    if (dimension == 'sufficiency' and target) or (dimension != 'sufficiency' and target not in {e['id'] for e in evidence}):
        raise ValueError('Invalid review target')
    return case, policy


def submit(case_id, target, dimension, label, reviewer, reason):
    reviewer = reviewer.strip().casefold()
    if len(reviewer) < 3 or len(reason.strip()) < 5:
        raise ValueError('Actual reviewer identifier and substantive reason required')
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        validate_target(db, case_id, target, dimension, label)
        previous = [r for r in latest(db, case_id, target, dimension) if r['reviewer'] == reviewer]
        if previous and previous[0]['label'] == label and previous[0]['reason'] == reason:
            return {'status': 'already recorded', 'review_id': previous[0]['id']}
        identifier = uid()
        db.execute('INSERT INTO independent_reviews VALUES (?,?,?,?,?,?,?,?)',
                   (identifier, case_id, target, dimension, label, reviewer, reason, now()))
        # Changed opinions invalidate old adjudicated labels. History itself is append-preserved.
        db.execute("UPDATE evaluation_labels SET status='superseded' WHERE case_id=? AND target=? AND dimension=? AND status='approved'", (case_id, target, dimension))
        return {'status': 'opinion recorded; approval pending adjudication', 'review_id': identifier}


def adjudicate(case_id, target, dimension, label, adjudicator, reason):
    adjudicator = adjudicator.strip().casefold()
    if len(adjudicator) < 3 or len(reason.strip()) < 5:
        raise ValueError('Actual adjudicator and rationale required')
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        _, policy = validate_target(db, case_id, target, dimension, label)
        reviews = latest(db, case_id, target, dimension)
        if len(reviews) < policy['required_reviewers']:
            raise ValueError('Required independent reviews are missing; no approval created')
        if policy['required_reviewers'] >= 2 and adjudicator in {r['reviewer'] for r in reviews}:
            raise ValueError('Double-reviewed cases require an adjudicator distinct from contributing reviewers')
        identifier = uid()
        db.execute('INSERT INTO review_adjudications VALUES (?,?,?,?,?,?,?,?,?)',
                   (identifier, case_id, target, dimension, label, adjudicator, reason, datasets.digest(reviews), now()))
    datasets.label(case_id, target, dimension, label, adjudicator, 'approved', reason, adjudication_id=identifier)
    return {'status': 'adjudicated', 'adjudication_id': identifier}


def check_approval(db, case_id, target, dimension, value, adjudication_id):
    policy = db.execute('SELECT 1 FROM pilot_case_policies WHERE case_id=?', (case_id,)).fetchone()
    if not policy:
        return
    decision = db.execute('SELECT * FROM review_adjudications WHERE id=? AND case_id=? AND target=? AND dimension=? AND label=?',
                          (adjudication_id, case_id, target, dimension, value)).fetchone()
    if not decision or decision['reviews_hash'] != datasets.digest(latest(db, case_id, target, dimension)):
        raise ValueError('Pilot labels require current explicit adjudication; direct approval is not allowed')


def validate_freeze(db, cases):
    groups = {c['related_group'] for c in cases}
    double_groups = set()
    for c in cases:
        policy = db.execute('SELECT required_reviewers FROM pilot_case_policies WHERE case_id=?', (c['id'],)).fetchone()
        if not policy:
            raise ValueError('Every pilot case must have a review assignment')
        if policy[0] >= 2:
            double_groups.add(c['related_group'])
        targets = [('', 'sufficiency')] + [(e['id'], d) for e in c['snapshot']['evidence'] for d in ('relevance', 'stance', 'citation')]
        for target, dim in targets:
            reviews = latest(db, c['id'], target, dim)
            label = datasets.approved(c, target, dim)
            decision = db.execute('SELECT * FROM review_adjudications WHERE case_id=? AND target=? AND dimension=? AND label=? AND reviews_hash=? ORDER BY created_at DESC LIMIT 1',
                                  (c['id'], target, dim, label, datasets.digest(reviews))).fetchone()
            if len(reviews) < policy[0] or not decision:
                raise ValueError('Independent review or adjudication pending; dataset cannot be frozen')
            if policy[0] >= 2 and decision['adjudicator'] in {r['reviewer'] for r in reviews}:
                raise ValueError('Double-reviewed case needs a separate adjudicator')
    if len(double_groups) < math.ceil(len(groups) * .2):
        raise ValueError('Assign and double-review at least 20% of pilot claim groups before freezing')


def packet(dataset_id, phase='initial'):
    if phase not in {'initial', 'citation'}:
        raise ValueError('Packet phase must be initial or citation')
    data = datasets.load(dataset_id, frozen=False)
    result = {'protocol': PROTOCOL, 'dataset_id': dataset_id, 'dataset_version': data['dataset']['version'],
              'synthetic': bool(data['dataset']['synthetic']), 'phase': phase, 'cases': [],
              'instructions': 'Initial review hides predictions and other opinions. Citation review is a separate pass against the captured assessment. Never infer gold labels from sampling tags.'}
    with connect() as db:
        for c in data['cases']:
            s = c['snapshot']
            policy = db.execute('SELECT required_reviewers FROM pilot_case_policies WHERE case_id=?', (c['id'],)).fetchone()
            item = {'case_id': c['id'], 'assertion': s['assertion_text'], 'claim_group': c['related_group'],
                    'temporal_context': c['temporal_context'], 'required_reviewers': policy[0] if policy else 1,
                    'label_dimensions': ['citation'] if phase == 'citation' else ['relevance', 'stance', 'sufficiency'], 'evidence': []}
            if phase == 'citation':
                item['captured_assessment'] = s['assessment']
            # Shuffle deterministically by ID, independent of ranking and labels.
            for e in sorted(s['evidence'], key=lambda e: datasets.digest([c['id'], e['id']])):
                source = e.get('source') or {}
                item['evidence'].append({'evidence_id': e['id'], 'source_group': e.get('source_group_id', e['canonical_url']),
                    'title': e['source_name'], 'url': e['source_url'], 'final_url': source.get('final_url'),
                    'passage': e['content_snippet'], 'context': source.get('context'), 'kind': e['passage_kind'],
                    'publication_date': e['publication_date'], 'retrieved_at': e['retrieved_at'],
                    'content_hash': source.get('content_hash'), 'body_hash': source.get('body_hash'),
                    'source_id': source.get('source_id'), 'start_offset': source.get('start_offset'), 'end_offset': source.get('end_offset'),
                    'extraction_status': source.get('status'), 'extraction_error': source.get('error')})
            result['cases'].append(item)
    return result


def agreement(dataset_id):
    data = datasets.load(dataset_id, frozen=False)
    dimensions = defaultdict(list)
    unresolved = []
    with connect() as db:
        for c in data['cases']:
            targets = [('', 'sufficiency')] + [(e['id'], d) for e in c['snapshot']['evidence'] for d in ('relevance', 'stance', 'citation')]
            for target, dim in targets:
                opinions = latest(db, c['id'], target, dim)
                if len(opinions) >= 2:
                    # First two distinct reviewers by identifier, deterministic; counts disclosed.
                    dimensions[dim].append((opinions[0]['label'], opinions[1]['label']))
                if len({r['label'] for r in opinions}) > 1:
                    gold = datasets.approved(c, target, dim)
                    unresolved.append({'case_id': c['id'], 'target': target, 'dimension': dim,
                                       'opinions': [{'reviewer': r['reviewer'], 'label': r['label']} for r in opinions],
                                       'status': 'adjudicated (disagreement retained)' if gold is not None else 'unresolved'})
    output = {}
    for dim in datasets.LABELS:
        pairs = dimensions[dim]
        n = len(pairs)
        observed = sum(a == b for a, b in pairs) / n if n else None
        left, right = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
        expected = sum(left[k] * right[k] for k in set(left) | set(right)) / n ** 2 if n else 0
        output[dim] = {'paired_items': n, 'agreement': observed,
                       'cohen_kappa': (observed - expected) / (1 - expected) if n >= 10 and expected < 1 else None,
                       'status': 'measured' if n >= 10 and expected < 1 else 'not measured: need >=10 paired items and nondegenerate marginals'}
    return {'protocol': PROTOCOL, 'dimensions': output, 'disagreements': unresolved,
            'limitations': 'First two distinct reviewers per item; pooled kappa is descriptive when reviewer pairs vary. Passage labels within a claim are correlated; no independence or population-reliability claim.'}


def write_sheet(packet, path):
    """Blank, prediction-free CSV response sheet. Never prefill a proposed label."""
    with Path(path).open('w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=['dataset_id', 'case_id', 'target', 'dimension', 'label', 'reason'])
        writer.writeheader()
        for c in packet['cases']:
            targets = [('', 'sufficiency')] if packet['phase'] == 'initial' else []
            targets += [(e['evidence_id'], d) for e in c['evidence'] for d in (['relevance', 'stance'] if packet['phase'] == 'initial' else ['citation'])]
            for target, dimension in targets:
                writer.writerow({'dataset_id': packet['dataset_id'], 'case_id': c['case_id'], 'target': target, 'dimension': dimension, 'label': '', 'reason': ''})


def submit_sheet(path, reviewer):
    path = Path(path)
    if path.stat().st_size > 5_000_000:
        raise ValueError('Review sheet exceeds 5 MB')
    with path.open(newline='') as file:
        items = list(csv.DictReader(file))
    if len(items) > 10000:
        raise ValueError('Review sheet exceeds 10,000 responses')
    selected = [r for r in items if r.get('label', '').strip()]
    # Validate the complete filled subset before writing any opinions.
    with connect() as db:
        for r in selected:
            case, _ = validate_target(db, r['case_id'], r['target'], r['dimension'], r['label'])
            if case['dataset_id'] != r['dataset_id'] or len(r['reason'].strip()) < 5:
                raise ValueError('Sheet has a mismatched dataset or missing review reason')
    for r in selected:
        submit(r['case_id'], r['target'], r['dimension'], r['label'], reviewer, r['reason'])
    return {'status': 'opinions recorded; none automatically approved', 'responses': len(selected), 'blank_rows_skipped': len(items) - len(selected)}
