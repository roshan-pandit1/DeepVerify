"""Immutable evaluation snapshots; no machine prediction is approved ground truth."""
import hashlib
import json

from . import splitting
from .store import connect, rows, now, uid

FORMAT = 'reviewed-investigation-v1'
CATEGORIES = {'supported', 'contradicted', 'mixed', 'time-sensitive', 'insufficient', 'relevant-not-entailing', 'duplicate-syndicated'}
LABELS = {'relevance': {'relevant', 'irrelevant'}, 'stance': {'supporting', 'contradicting', 'unrelated', 'needing review'},
          'sufficiency': {'sufficient', 'insufficient'}, 'citation': {'justified', 'not justified', 'needs review'}}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def create(name, version, seed=17, synthetic=False):
    if not name.strip() or not version.strip():
        raise ValueError('Dataset name and version are required')
    identifier = uid()
    with connect() as db:
        db.execute('INSERT INTO evaluation_datasets VALUES (?,?,?,?,?,?,?,?,?)',
                   (identifier, name, version, FORMAT, seed, int(synthetic), 'draft', now(), None))
    return identifier


def require(db, identifier, draft=False):
    row = db.execute('SELECT * FROM evaluation_datasets WHERE id=?', (identifier,)).fetchone()
    if not row:
        raise ValueError('Evaluation dataset not found')
    if draft and row['state'] != 'draft':
        raise ValueError('Frozen datasets cannot be edited. Create a new version.')
    return dict(row)


def add(identifier, assertion_id, related_group, temporal_context, categories):
    if not related_group.strip() or not temporal_context.strip() or not categories or not set(categories) <= CATEGORIES:
        raise ValueError('Provide a reviewed topic group, temporal context, and valid coverage categories')
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        dataset = require(db, identifier, draft=True)
        assertion = db.execute('SELECT a.*, d.assessment, d.explanation FROM assertions a JOIN assertion_details d ON d.assertion_id=a.id WHERE a.id=?', (assertion_id,)).fetchone()
        if not assertion:
            raise ValueError('Assertion not found')
        investigation = db.execute('SELECT provider, stage FROM investigations WHERE claim_id=?', (assertion['claim_id'],)).fetchone()
        if not investigation or investigation['stage'] not in {'complete', 'partial'}:
            raise ValueError('Capture completed or partial reports, not drafts or in-progress investigations')
        if not dataset['synthetic'] and investigation['provider'] == 'offline':
            raise ValueError('Offline investigations belong only in explicitly synthetic datasets')
        snapshot = dict(assertion)
        snapshot['evidence'] = rows(db, '''SELECT e.*, d.* FROM evidence_items e JOIN evidence_details d ON d.evidence_id=e.id
                                        WHERE e.assertion_id=? ORDER BY e.id''', (assertion_id,))
        for e in snapshot['evidence']:
            s = db.execute('''SELECT p.*, s.* FROM source_passages p JOIN source_documents s ON s.id=p.source_id
                              WHERE p.evidence_id=?''', (e['id'],)).fetchone()
            e['source'] = dict(s) if s else None
            if e['fixture'] and not dataset['synthetic']:
                raise ValueError('Synthetic evidence cannot enter a real dataset')
            e['approved_feedback_at_capture'] = rows(db, "SELECT * FROM feedback WHERE evidence_id=? AND approval='approved'", (e['id'],))
            # Feedback is provenance/proposal, not automatic approval of any evaluation dimension.
        identifier_case = uid()
        db.execute('INSERT INTO evaluation_cases VALUES (?,?,?,?,?,?,?,?,?)',
                   (identifier_case, identifier, assertion_id, related_group.strip().lower(), temporal_context, json.dumps(categories), json.dumps(snapshot), None, None))
    return identifier_case


def label(case_id, target, dimension, value, reviewer, status, reason):
    if dimension not in LABELS or value not in LABELS[dimension] or status not in {'proposed', 'approved', 'rejected'}:
        raise ValueError('Invalid label, dimension, or approval status')
    if not reviewer.strip() or len(reason.strip()) < 5:
        raise ValueError('Actual reviewer identity and review reason required; do not invent provenance')
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        case = db.execute('SELECT * FROM evaluation_cases WHERE id=?', (case_id,)).fetchone()
        if not case:
            raise ValueError('Evaluation case not found')
        require(db, case['dataset_id'], draft=True)
        snapshot = json.loads(case['snapshot_json'])
        allowed = {e['id'] for e in snapshot['evidence']}
        if (dimension == 'sufficiency' and target != '') or (dimension != 'sufficiency' and target not in allowed):
            raise ValueError('Sufficiency targets the assertion (empty target); other dimensions target a captured evidence ID')
        if status in {'approved', 'rejected'}:
            db.execute("UPDATE evaluation_labels SET status='superseded' WHERE case_id=? AND target=? AND dimension=? AND status='approved'", (case_id, target, dimension))
        db.execute('INSERT INTO evaluation_labels VALUES (?,?,?,?,?,?,?,?,?)',
                   (uid(), case_id, target, dimension, value, reviewer, status, reason, now()))


def snapshot(db, identifier):
    dataset = require(db, identifier)
    cases = rows(db, 'SELECT * FROM evaluation_cases WHERE dataset_id=? ORDER BY id', (identifier,))
    for c in cases:
        c['snapshot'] = json.loads(c.pop('snapshot_json'))
        c['categories'] = json.loads(c['categories'])
        c['reviews'] = rows(db, 'SELECT * FROM evaluation_labels WHERE case_id=? ORDER BY created_at, id', (c['id'],))
    return {'dataset': dataset, 'split_method': splitting.VERSION, 'cases': cases}


def approved(case, target, dimension):
    return next((r['label'] for r in reversed(case['reviews']) if r['target'] == target and r['dimension'] == dimension and r['status'] == 'approved'), None)


def freeze(identifier):
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        require(db, identifier, draft=True)
        data = snapshot(db, identifier)
        if not data['cases']:
            raise ValueError('Cannot freeze an empty dataset; evaluation pending human review')
        for c in data['cases']:
            if approved(c, '', 'sufficiency') is None:
                raise ValueError('Every assertion requires separately approved sufficiency labels')
            for e in c['snapshot']['evidence']:
                if any(approved(c, e['id'], d) is None for d in ('relevance', 'stance', 'citation')):
                    raise ValueError('Every evidence item requires separate approved relevance, stance and citation labels')
        assignments = splitting.assign(data['cases'], data['dataset']['seed'])
        # New versions cannot quietly move previously exposed/held-out topics across partitions.
        prior = rows(db, '''SELECT c.* FROM evaluation_cases c JOIN evaluation_datasets d ON d.id=c.dataset_id
                           WHERE d.state='frozen' AND d.synthetic=?''', (data['dataset']['synthetic'],))
        for p in prior:
            p['snapshot'] = json.loads(p['snapshot_json'])
        for c in data['cases']:
            split, component = assignments[c['id']]
            if any(splitting.connected(c, p) and split != p['split'] for p in prior):
                raise ValueError('Cross-version split conflict: related topics/sources already belong to another partition. Use disjoint data or revise grouping.')
            if split == 'holdout' and any(splitting.connected(c, p) and p['split'] == 'holdout' for p in prior):
                raise ValueError('A frozen holdout topic/source cannot be copied into a new dataset for repeated evaluation')
            db.execute('UPDATE evaluation_cases SET split=?, component=? WHERE id=?', (split, component, c['id']))
        db.execute("UPDATE evaluation_datasets SET state='frozen' WHERE id=?", (identifier,))
        frozen = snapshot(db, identifier)
        fingerprint = digest(frozen)
        db.execute('UPDATE evaluation_datasets SET frozen_hash=? WHERE id=?', (fingerprint, identifier))
    return {'dataset_id': identifier, 'frozen_hash': fingerprint, 'cases': len(data['cases'])}


def load(identifier, frozen=True):
    with connect() as db:
        data = snapshot(db, identifier)
    if frozen:
        if data['dataset']['state'] != 'frozen':
            raise ValueError('Evaluation pending: dataset must be reviewed and frozen first')
        expected = data['dataset']['frozen_hash']
        data['dataset']['frozen_hash'] = None
        if digest(data) != expected:
            raise ValueError('Frozen dataset integrity check failed')
        data['dataset']['frozen_hash'] = expected
    return data


def ranking_rows(data, partition):
    result = []
    for c in data['cases']:
        if c['split'] != partition:
            continue
        for e in c['snapshot']['evidence']:
            relevance = approved(c, e['id'], 'relevance')
            if relevance is None:
                continue
            result.append({'feedback_id': c['id'] + ':' + e['id'], 'claim_id': c['snapshot']['claim_id'],
                           'assertion_id': c['assertion_id'], 'assertion_text': c['snapshot']['assertion_text'],
                           'evidence_id': e['id'], 'content_snippet': e['content_snippet'],
                           'canonical_url': e['canonical_url'], 'features': json.loads(e['features']),
                           'label': int(relevance == 'relevant')})
    return result


def exclude_reserved(data, db):
    reserved = rows(db, '''SELECT c.* FROM evaluation_cases c JOIN evaluation_datasets d ON d.id=c.dataset_id
                          WHERE d.state='frozen' AND d.synthetic=0 AND c.split IN ('holdout','validation')''')
    for c in reserved:
        c['snapshot'] = json.loads(c['snapshot_json'])
    wrapped = [{'id': r['feedback_id'], 'snapshot': {'claim_id': r['claim_id'], 'assertion_text': r['assertion_text'],
                'evidence': [{'canonical_url': r['canonical_url'], 'content_snippet': r['content_snippet'], 'source': r.get('source')}]}} for r in data]
    # Include all training candidates in the graph, so indirect links to reserved data are excluded too.
    excluded = set()
    reserved_ids = {c['id'] for c in reserved}
    for group in splitting.components(wrapped + reserved):
        if any(c['id'] in reserved_ids for c in group):
            excluded.update(c['id'] for c in group)
    return [r for r in data if r['feedback_id'] not in excluded]
