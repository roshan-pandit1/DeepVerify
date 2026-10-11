"""Reviewed-only batch ranking. JSON coefficients avoid executable model serialization."""
import argparse
import hashlib
import hmac
import json
import math
import os
import re
from collections import defaultdict

from .ranking import FEATURE_VERSION, FEATURES, artifact_dir, baseline, tokens
from .store import connect, migrate, now, uid, rows

DATASET_VERSION = 'approved-live-relevance-v1'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def eligible_data(db):
    data = rows(db, '''SELECT f.id AS feedback_id, f.label, a.claim_id, a.id AS assertion_id,
        a.assertion_text, e.id AS evidence_id, e.content_snippet, d.canonical_url, d.features
        FROM feedback f JOIN evidence_items e ON f.evidence_id=e.id
        JOIN evidence_details d ON e.id=d.evidence_id JOIN assertions a ON e.assertion_id=a.id
        WHERE f.approval='approved' AND f.dimension='relevance' AND d.fixture=0 ORDER BY f.id''')
    for row in data:
        row['features'] = json.loads(row['features'])
        row['label'] = int(row['label'] == 'relevant')
    return data


def grouped_split(data):
    """Connected components: investigation, related text, canonical source OR duplicate passage.

    Transitive connections cannot cross the split. Deliberately conservative lexical
    relatedness is a baseline, not a guarantee of semantic paraphrase detection.
    """
    parent = list(range(len(data)))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    words = [tokens(r['assertion_text']) for r in data]
    passages = [' '.join(re.findall(r'\w+', r['content_snippet'].lower())) for r in data]
    for i, a in enumerate(data):
        for j in range(i):
            b = data[j]
            similarity = len(words[i] & words[j]) / max(1, len(words[i] | words[j]))
            if (a['claim_id'] == b['claim_id'] or a['canonical_url'] == b['canonical_url']
                    or passages[i] == passages[j] or similarity >= 0.35):
                parent[root(i)] = root(j)
    groups = defaultdict(list)
    for i in range(len(data)):
        groups[root(i)].append(i)
    components = sorted(groups.values(), key=lambda g: digest(sorted(data[i]['feedback_id'] for i in g)))
    count = max(1, math.ceil(len(components) * 0.3))
    test = sorted(i for group in components[:count] for i in group)
    train = sorted(i for group in components[count:] for i in group)
    return train, test, len(components)


def enough(data, train, test, groups):
    queries = defaultdict(list)
    for i in test:
        queries[data[i]['assertion_id']].append(data[i]['label'])
    if (len(data) < 40 or groups < 8 or len(train) < 20 or len(queries) < 3
            or any(len(labels) < 5 or 1 not in labels for labels in queries.values())
            or {data[i]['label'] for i in train} != {0, 1}
            or {data[i]['label'] for i in test} != {0, 1}):
        raise ValueError('collecting reviewed feedback: need >=40 live examples, >=8 independent groups, >=20 training examples, both labels in each split, and >=3 evaluation assertions with >=5 sources and a relevant source each.')


def metrics(data, indices, scorer):
    queries = defaultdict(list)
    for i in indices:
        queries[data[i]['assertion_id']].append(data[i])
    precisions, ndcgs = [], []
    for examples in queries.values():
        ranked = sorted(examples, key=lambda r: (-scorer(r['features']), r['evidence_id']))
        labels = [r['label'] for r in ranked[:5]]
        ideal = sorted([r['label'] for r in examples], reverse=True)[:5]
        dcg = lambda values: sum(v / math.log2(i + 2) for i, v in enumerate(values))
        precisions.append(sum(labels) / 5)
        ndcgs.append(dcg(labels) / dcg(ideal) if dcg(ideal) else 0)
    return {'precision@5': sum(precisions) / max(1, len(precisions)),
            'ndcg@5': sum(ndcgs) / max(1, len(ndcgs)), 'assertions': len(queries), 'examples': len(indices)}


def eligible_metrics(base, candidate):
    return (candidate['assertions'] >= 3 and candidate['precision@5'] >= base['precision@5']
            and candidate['ndcg@5'] >= base['ndcg@5'] + 0.01)


def write(name, data):
    directory = artifact_dir()
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / name
    temporary = directory / (name + '.tmp')
    temporary.write_text(json.dumps(data, indent=2, sort_keys=True))
    temporary.replace(target)


def export():
    with connect() as db:
        data = eligible_data(db)
    dataset = {'version': DATASET_VERSION, 'feature_version': FEATURE_VERSION, 'examples': data}
    identifier = digest(dataset)
    write(f'dataset-{identifier}.json', dataset)
    return {'dataset_id': identifier, 'examples': len(data), 'path': str(artifact_dir() / f'dataset-{identifier}.json')}


def load_dataset(identifier):
    if not re.fullmatch('[a-f0-9]{64}', identifier):
        raise ValueError('Use the dataset_id returned by export')
    dataset = json.loads((artifact_dir() / f'dataset-{identifier}.json').read_text())
    if digest(dataset) != identifier or dataset['feature_version'] != FEATURE_VERSION:
        raise ValueError('Dataset integrity/version check failed')
    with connect() as db:
        if dataset['examples'] != eligible_data(db):
            raise ValueError('Approved feedback changed. Export a fresh dataset before training or promotion.')
    return dataset['examples']


def train(identifier):
    from sklearn.linear_model import LogisticRegression
    import sklearn
    data = load_dataset(identifier)
    train_ids, test_ids, groups = grouped_split(data)
    enough(data, train_ids, test_ids, groups)
    model = LogisticRegression(random_state=17, max_iter=1000, class_weight='balanced')
    model.fit([data[i]['features'] for i in train_ids], [data[i]['label'] for i in train_ids])
    model_id = 'candidate-' + uid()
    artifact = {'model_id': model_id, 'created_at': now(), 'dataset_id': identifier,
                'feature_version': FEATURE_VERSION, 'features': FEATURES, 'sklearn_version': sklearn.__version__,
                'coefficients': model.coef_[0].tolist(), 'intercept': float(model.intercept_[0]),
                'train_indices': train_ids, 'test_indices': test_ids, 'groups': groups}
    write(f'{model_id}.json', artifact)
    return {'model_id': model_id, 'train_examples': len(train_ids), 'test_examples': len(test_ids), 'groups': groups}


def load_model(model_id):
    if not re.fullmatch(r'candidate-[a-f0-9-]{36}', model_id):
        raise ValueError('Invalid candidate ID')
    return json.loads((artifact_dir() / f'{model_id}.json').read_text())


def evaluate(model_id):
    model = load_model(model_id)
    data = load_dataset(model['dataset_id'])
    train_ids, test_ids, groups = grouped_split(data)
    enough(data, train_ids, test_ids, groups)
    if train_ids != model['train_indices'] or test_ids != model['test_indices'] or model['feature_version'] != FEATURE_VERSION:
        raise ValueError('Split or feature version mismatch')
    if len(model['coefficients']) != len(FEATURES) or not all(math.isfinite(x) for x in model['coefficients'] + [model['intercept']]):
        raise ValueError('Invalid candidate coefficients')
    candidate = lambda x: sum(a * b for a, b in zip(x, model['coefficients'])) + model['intercept']
    base, result = metrics(data, test_ids, baseline), metrics(data, test_ids, candidate)
    report = {'model_id': model_id, 'model_hash': digest(model), 'dataset_id': model['dataset_id'],
              'evaluated_at': now(), 'groups': groups, 'train_examples': len(train_ids),
              'baseline': base, 'candidate': result, 'eligible': eligible_metrics(base, result),
              'limitations': 'Offline reviewed relevance only; lexical related-claim grouping can miss paraphrases. Small-data metrics are not real-world accuracy. No stance training. Fixed holdout must not be repeatedly tuned against.'}
    write(f'{model_id}.evaluation.json', report)
    with connect() as db:
        db.execute('INSERT INTO model_evaluations VALUES (?,?,?,?)', (uid(), model_id, json.dumps(report, sort_keys=True), now()))
    return report


def promote(model_id):
    # Recompute rather than trusting a supplied evaluation report or stale approval state.
    report = evaluate(model_id)
    if not report['eligible']:
        with connect() as db:
            db.execute('INSERT INTO model_decisions VALUES (?,?,?,?)', (uid(), model_id, 'promotion rejected: failed evaluation', now()))
        raise ValueError('Promotion rejected: candidate must improve NDCG@5 by >=0.01 without reducing precision@5.')
    activate(model_id, 'promote')
    return report


def activate(model_id, action):
    with connect() as db:
        db.execute('UPDATE active_ranker SET model_id=? WHERE singleton=1', (model_id,))
        db.execute('INSERT INTO model_decisions VALUES (?,?,?,?)', (uid(), model_id, action, now()))


def rollback(model_id):
    if model_id != 'baseline-v1':
        load_model(model_id)
        with connect() as db:
            if not db.execute("SELECT 1 FROM model_decisions WHERE model_id=? AND action='promote'", (model_id,)).fetchone():
                raise ValueError('Rollback requires a previously promoted model')
    activate(model_id, 'rollback')
    return {'active_ranker': model_id}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['export', 'train', 'evaluate', 'promote', 'rollback'])
    parser.add_argument('identifier', nargs='?', default='baseline-v1')
    parser.add_argument('--token', required=True, help='Must match INVESTIGATION_ADMIN_TOKEN')
    args = parser.parse_args()
    expected = os.getenv('INVESTIGATION_ADMIN_TOKEN', '')
    if len(expected) < 24 or not hmac.compare_digest(expected, args.token):
        parser.error('Valid administrator token required')
    migrate()
    try:
        actions = {'export': export, 'train': train, 'evaluate': evaluate, 'promote': promote, 'rollback': rollback}
        result = actions[args.command]() if args.command == 'export' else actions[args.command](args.identifier)
        print(json.dumps(result, indent=2))
    except (ValueError, OSError) as exc:
        parser.exit(1, str(exc) + '\n')


if __name__ == '__main__':
    main()
