"""Paired development estimates; never independently opens a holdout."""
import random
from collections import defaultdict

from . import training

VERSION = 'paired-component-bootstrap-v1'


def compare(examples, scorer, component_by_assertion, categories_by_assertion, seed=17, draws=2000):
    queries = defaultdict(list)
    for row in examples:
        queries[row['assertion_id']].append(row)
    pairs = []
    for assertion, rows in sorted(queries.items()):
        indices = list(range(len(rows)))
        base = training.metrics(rows, indices, training.baseline)
        candidate = training.metrics(rows, indices, scorer)
        pairs.append({'assertion_id': assertion, 'component': component_by_assertion[assertion],
                      'categories': categories_by_assertion.get(assertion, []), 'examples': len(rows),
                      'precision@5_delta': candidate['precision@5'] - base['precision@5'],
                      'ndcg@5_delta': candidate['ndcg@5'] - base['ndcg@5']})
    groups = defaultdict(list)
    for pair in pairs:
        groups[pair['component']].append(pair)
    categories = {}
    for category in sorted({c for p in pairs for c in p['categories']}):
        subset = [p for p in pairs if category in p['categories']]
        categories[category] = {'assertions': len(subset), 'precision@5_delta': sum(p['precision@5_delta'] for p in subset) / len(subset),
                                'ndcg@5_delta': sum(p['ndcg@5_delta'] for p in subset) / len(subset),
                                'regressed_assertions': [p['assertion_id'] for p in subset if p['precision@5_delta'] < 0 or p['ndcg@5_delta'] < 0]}
    intervals = {}
    rng = random.Random(seed)
    values = list(groups.values())
    if len(values) >= 3:
        samples = {'precision@5_delta': [], 'ndcg@5_delta': []}
        for _ in range(draws):
            picked = [p for group in rng.choices(values, k=len(values)) for p in group]
            for metric in samples:
                samples[metric].append(sum(p[metric] for p in picked) / len(picked))
        for metric, estimates in samples.items():
            estimates.sort()
            intervals[metric] = [estimates[int(draws * .025)], estimates[min(draws - 1, int(draws * .975))]]
    demonstrated = bool(intervals and intervals['ndcg@5_delta'][0] > 0 and intervals['precision@5_delta'][0] >= 0)
    return {'method': VERSION, 'seed': seed, 'bootstrap_draws': draws, 'independent_components': len(groups),
            'paired_assertions': len(pairs), 'pairs': pairs, 'category_regressions': categories,
            'mean_deltas': {metric: sum(p[metric] for p in pairs) / len(pairs) if pairs else None for metric in ('precision@5_delta', 'ndcg@5_delta')},
            'percentile_95_intervals': intervals,
            'status': 'demonstrated on development sample' if demonstrated else 'inconclusive' if pairs else 'not measured',
            'improvement_demonstrated': demonstrated,
            'limitations': 'Paired resampling of connected claim/source components, not individual passages. >=3 groups only permits computation, not statistical adequacy. Small, selected pilots and repeated development selection bias uncertainty estimates.'}
