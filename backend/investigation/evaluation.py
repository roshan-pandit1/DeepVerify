"""Stage-separated validation and one-shot frozen-holdout audits."""
import argparse
import hmac
import json
import os
import math
from collections import Counter

from . import datasets, training
from .ranking import baseline, FEATURE_VERSION
from .stance import GuardedRules, LegacyRules, VERSION as STANCE_VERSION
from .sources import VERSION as EXTRACTION_VERSION
from .store import connect, migrate, rows, now, uid

VERSION = 'stage-evaluation-v1'


def classification(truth, predictions, labels):
    matrix = {a: {p: 0 for p in labels} for a in labels}
    for actual, predicted in zip(truth, predictions):
        matrix[actual][predicted] += 1
    per_class = {}
    for label in labels:
        tp = matrix[label][label]
        actual = sum(matrix[label].values())
        predicted = sum(matrix[a][label] for a in labels)
        precision = tp / predicted if predicted else 0.0
        recall = tp / actual if actual else 0.0
        per_class[label] = {'precision': precision, 'recall': recall,
                            'f1': 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
                            'support': actual}
    return {'samples': len(truth), 'label_distribution': dict(Counter(truth)), 'per_class': per_class,
            'macro_f1': sum(x['f1'] for x in per_class.values()) / len(labels) if truth else None,
            'confusion_matrix': matrix, 'status': 'measured' if truth else 'insufficient data',
            'zero_division_policy': 'zero; macro-F1 includes all declared classes'}


def model_scorer(model_id, dataset_id):
    if model_id == 'baseline-v1':
        return baseline, 'baseline-v1', None
    model = training.load_model(model_id)
    if model.get('evaluation_dataset_id') != dataset_id:
        raise ValueError('Candidate must be trained on this frozen dataset; legacy or unrelated candidates cannot use its holdout')
    if model['feature_version'] != FEATURE_VERSION:
        raise ValueError('Candidate feature version mismatch')
    if len(model['coefficients']) != 5 or not all(math.isfinite(x) for x in model['coefficients'] + [model['intercept']]):
        raise ValueError('Invalid candidate coefficients')
    return lambda x: sum(a * b for a, b in zip(x, model['coefficients'])) + model['intercept'], datasets.digest(model), model


def report(data, partition, model_id='baseline-v1'):
    scorer, model_hash, model = model_scorer(model_id, data['dataset']['id'])
    if model and model['evaluation_dataset_hash'] != data['dataset']['frozen_hash']:
        raise ValueError('Candidate dataset hash mismatch')
    if model and (model['train_example_ids'] != [r['feedback_id'] for r in datasets.ranking_rows(data, 'train')]
                  or model['validation_example_ids'] != [r['feedback_id'] for r in datasets.ranking_rows(data, 'validation')]):
        raise ValueError('Candidate split membership mismatch')
    cases = [c for c in data['cases'] if c['split'] == partition]
    ranking = datasets.ranking_rows(data, partition)
    counts = Counter(r['assertion_id'] for r in ranking)
    qualified = {k for k, v in counts.items() if v >= 5}
    judged = [r for r in ranking if r['assertion_id'] in qualified]
    indices = list(range(len(judged)))
    b = training.metrics(judged, indices, baseline) if judged else None
    candidate = training.metrics(judged, indices, scorer) if judged else None
    example_ids = [r['feedback_id'] for r in judged]
    eligible = bool(b and candidate and training.eligible_metrics(b, candidate) and not data['dataset']['synthetic'])
    actual, guarded, legacy, extraction, citation = [], [], [], [], []
    sufficient_truth, sufficiency_predicted = [], []
    for c in cases:
        s = c['snapshot']
        sufficient_truth.append(datasets.approved(c, '', 'sufficiency'))
        sufficiency_predicted.append('insufficient' if s['assessment'] == 'insufficient evidence' else 'sufficient')
        for e in s['evidence']:
            source = e.get('source') or {}
            context = source.get('context', '')
            actual.append(datasets.approved(c, e['id'], 'stance'))
            guarded.append(GuardedRules().classify(s['assertion_text'], e['content_snippet'], context)['stance'])
            legacy.append(LegacyRules().classify(s['assertion_text'], e['content_snippet'], context)['stance'])
            extraction.append(source.get('status', 'legacy_not_attempted'))
            if s['assessment'] != 'insufficient evidence':
                citation.append(datasets.approved(c, e['id'], 'citation'))
    stance_labels = ['supporting', 'contradicting', 'unrelated', 'needing review']
    citations = Counter(citation)
    resolved = citations['justified'] + citations['not justified']
    attempted = [x for x in extraction if x not in {'offline', 'disabled', 'unavailable', 'legacy_not_attempted'}]
    return {'evaluation_version': VERSION, 'created_at': now(), 'dataset_id': data['dataset']['id'],
            'dataset_version': data['dataset']['version'], 'dataset_hash': data['dataset']['frozen_hash'],
            'synthetic': bool(data['dataset']['synthetic']), 'partition': partition, 'seed': data['dataset']['seed'],
            'model_id': model_id, 'model_hash': model_hash,
            'methods': {'ranking_baseline': 'baseline-v1', 'features': FEATURE_VERSION, 'stance': STANCE_VERSION,
                        'stance_baseline': 'conservative-lexical-triage-v1', 'extraction': EXTRACTION_VERSION,
                        'sufficiency': 'captured-reviewed-source-policy-v1', 'split': data['split_method']},
            'counts': {'cases': len(cases), 'evidence': len(actual), 'groups': len({c['component'] for c in cases}),
                       'dataset_cases': len(data['cases']), 'partitions': dict(Counter(c['split'] for c in data['cases']))},
            'coverage_categories': dict(Counter(tag for c in cases for tag in c['categories'])),
            'missing_coverage_categories': sorted(datasets.CATEGORIES - {tag for c in cases for tag in c['categories']}),
            'ranking': {'status': 'measured' if judged else 'insufficient data: need five judged sources per assertion',
                        'baseline': b, 'candidate': candidate, 'identical_example_ids': example_ids,
                        'example_fingerprint': datasets.digest(example_ids), 'excluded_short_queries': len(counts) - len(qualified),
                        'label_distribution': dict(Counter(r['label'] for r in judged)),
                        'promotion_gate_passed': eligible, 'gate_partition': 'validation only'},
            'stance': {'baseline': classification(actual, legacy, stance_labels),
                       'candidate': classification(actual, guarded, stance_labels)},
            'extraction': {'source_candidates': len(extraction), 'attempts': len(attempted), 'successes': extraction.count('extracted'),
                           'success_rate': extraction.count('extracted') / len(attempted) if attempted else None,
                           'categories': dict(Counter(extraction)), 'status': 'measured' if attempted else 'insufficient data: no extraction attempts',
                           'baseline': {'method': 'search-snippet-only', 'full_source_passages': 0}},
            'sufficiency': {'candidate': classification(sufficient_truth, sufficiency_predicted, ['sufficient', 'insufficient']),
                            'baseline': classification(sufficient_truth, ['insufficient'] * len(cases), ['sufficient', 'insufficient'])},
            'citation_support': {'reviewed_citations': len(citation), 'labels': dict(citations), 'resolved': resolved,
                                 'justified_rate': citations['justified'] / resolved if resolved else None,
                                 'status': 'measured' if resolved else 'insufficient data'},
            'limitations': [
                'Synthetic results are functionality checks, never real-world quality evidence.' if data['dataset']['synthetic'] else 'Results apply only to this reviewed sample; no population accuracy claim.',
                'Ranking reorders a fixed judged retrieval pool; it does not measure web recall or improve query generation.',
                'Extraction success is recorded fetch/parser status, not a human judgment of extraction fidelity.',
                'Rule stance classifiers are conservative and may abstain; all classes, including absent classes, enter macro-F1.',
                'Sufficiency evaluates captured report assessments; citation support is an independent human-reviewed audit, not a ranking score.',
                'Topic groups require human review; lexical matching cannot guarantee detection of every paraphrase or syndicated rewrite.',
                'Holdout is reserved for one final audit, never model selection or promotion.']}


def save(report, identifier):
    training.write(f'evaluation-{identifier}.json', report)
    lines = ['# DeepVerify stage evaluation', '', f"Dataset: {report['dataset_id']} / {report['dataset_version']}",
             f"Partition: {report['partition']} | Synthetic: {report['synthetic']} | Seed: {report['seed']}",
             f"Cases: {report['counts']['cases']} | Evidence: {report['counts']['evidence']}",
             f"Ranker: {report['model_id']}", '', '## Ranking (same examples)',
             f"Baseline: {json.dumps(report['ranking']['baseline'])}", f"Candidate: {json.dumps(report['ranking']['candidate'])}",
             f"Validation ranking gate: {report['ranking']['promotion_gate_passed']}", '', '## Stance',
             json.dumps(report['stance'], indent=2), '', '## Extraction', json.dumps(report['extraction'], indent=2),
             '', '## Sufficiency', json.dumps(report['sufficiency'], indent=2), '', '## Citation support',
             json.dumps(report['citation_support'], indent=2), '', '## Limitations', *['- ' + x for x in report['limitations']]]
    directory = training.artifact_dir()
    (directory / f'evaluation-{identifier}.md').write_text('\n'.join(lines))


def evaluate(identifier, model_id='baseline-v1', partition='validation'):
    if partition not in {'validation', 'holdout'}:
        raise ValueError('Only validation or final holdout may be evaluated')
    data = datasets.load(identifier)
    _, model_hash, _ = model_scorer(model_id, identifier)
    audit_key = datasets.digest([model_hash, VERSION, STANCE_VERSION, EXTRACTION_VERSION])
    report_id = uid()
    if partition == 'validation':
        with connect() as db:
            if db.execute('SELECT 1 FROM evaluation_holdout_locks WHERE dataset_id=?', (identifier,)).fetchone():
                raise ValueError('Final audit already started; validation is closed. Read persisted reports instead.')
    if partition == 'holdout':
        with connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if model_id != 'baseline-v1' and not db.execute("SELECT 1 FROM model_decisions WHERE model_id=? AND action='promote'", (model_id,)).fetchone():
                raise ValueError('Select/promote the candidate using validation before its one-shot holdout audit')
            lock = db.execute('SELECT * FROM evaluation_holdout_locks WHERE dataset_id=?', (identifier,)).fetchone()
            if lock:
                if lock['model_hash'] != audit_key:
                    raise ValueError('Frozen holdout already consumed by another model/method. Do not tune against or reuse it.')
                old = db.execute('SELECT report_json FROM evaluation_reports WHERE id=?', (lock['report_id'],)).fetchone()
                if not old:
                    raise ValueError('Holdout audit was interrupted; its reservation is retained to prevent repeated exposure.')
                return json.loads(old['report_json'])
            db.execute('INSERT INTO evaluation_holdout_locks VALUES (?,?,?,?)', (identifier, audit_key, report_id, now()))
    result = report(data, partition, model_id)
    result['report_id'] = report_id
    # A holdout audit can never authorize promotion, regardless of its metric values.
    if partition == 'holdout':
        result['ranking']['promotion_gate_passed'] = False
    with connect() as db:
        db.execute('INSERT INTO evaluation_reports VALUES (?,?,?,?,?,?)', (report_id, identifier, partition, model_id, json.dumps(result), now()))
    save(result, report_id)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--token', required=True)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('create'); p.add_argument('--name', required=True); p.add_argument('--version', required=True); p.add_argument('--seed', type=int, default=17); p.add_argument('--synthetic', action='store_true')
    p = sub.add_parser('add'); p.add_argument('dataset'); p.add_argument('--assertion', required=True); p.add_argument('--group', required=True); p.add_argument('--temporal-context', required=True); p.add_argument('--categories', nargs='+', required=True, choices=sorted(datasets.CATEGORIES))
    p = sub.add_parser('label'); p.add_argument('case'); p.add_argument('--target', default=''); p.add_argument('--dimension', required=True, choices=sorted(datasets.LABELS)); p.add_argument('--label', required=True); p.add_argument('--reviewer', required=True); p.add_argument('--status', required=True, choices=['proposed','approved','rejected']); p.add_argument('--reason', required=True)
    p = sub.add_parser('freeze'); p.add_argument('dataset')
    p = sub.add_parser('export'); p.add_argument('dataset')
    p = sub.add_parser('evaluate'); p.add_argument('dataset'); p.add_argument('--model', default='baseline-v1'); p.add_argument('--partition', choices=['validation','holdout'], default='validation')
    args = parser.parse_args()
    expected = os.getenv('INVESTIGATION_ADMIN_TOKEN', '')
    if len(expected) < 24 or not hmac.compare_digest(expected, args.token):
        parser.error('Valid administrator token required')
    migrate()
    try:
        if args.command == 'create':
            result = {'dataset_id': datasets.create(args.name, args.version, args.seed, args.synthetic)}
        elif args.command == 'add':
            result = {'case_id': datasets.add(args.dataset, args.assertion, args.group, args.temporal_context, args.categories)}
        elif args.command == 'label':
            datasets.label(args.case, args.target, args.dimension, args.label, args.reviewer, args.status, args.reason)
            result = {'status': 'recorded; independent dimension review only'}
        elif args.command == 'freeze':
            result = datasets.freeze(args.dataset)
        elif args.command == 'export':
            data = datasets.load(args.dataset, frozen=False)
            training.write(f'review-dataset-{args.dataset}.json', data)
            result = {'path': str(training.artifact_dir() / f'review-dataset-{args.dataset}.json'), 'state': data['dataset']['state']}
        else:
            result = evaluate(args.dataset, args.model, args.partition)
        print(json.dumps(result, indent=2))
    except (ValueError, OSError) as exc:
        parser.exit(1, str(exc) + '\n')


if __name__ == '__main__':
    main()
