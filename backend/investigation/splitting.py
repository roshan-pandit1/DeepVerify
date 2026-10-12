"""Conservative transitive isolation, including manually reviewed topic groups."""
import hashlib
import json
import re

from .ranking import tokens

VERSION = 'topic-source-components-v2'


def normalized(text):
    return ' '.join(re.findall(r'\w+', text.lower()))


def links(case):
    snapshot = case.get('snapshot', case)
    keys = {('claim', snapshot['claim_id'])}
    if case.get('related_group'):
        keys.add(('topic', case['related_group'].strip().lower()))
    for e in snapshot.get('evidence', []):
        if e.get('source_group_id'):
            keys.add(('source_group', e['source_group_id']))
        source = e.get('source') or {}
        for url in (e.get('canonical_url'), source.get('final_url')):
            if url:
                keys.add(('url', url.rstrip('/')))
        if source.get('content_hash'):
            keys.add(('document', source['content_hash']))
        if e.get('content_snippet'):
            keys.add(('passage', normalized(e['content_snippet'])))
    return keys


def connected(a, b):
    if links(a) & links(b):
        return True
    ta = tokens(a.get('snapshot', a)['assertion_text'])
    tb = tokens(b.get('snapshot', b)['assertion_text'])
    return len(ta & tb) / max(1, len(ta | tb)) >= .35


def components(cases):
    parent = list(range(len(cases)))
    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for i in range(len(cases)):
        for j in range(i):
            if connected(cases[i], cases[j]):
                parent[root(i)] = root(j)
    groups = {}
    for i, case in enumerate(cases):
        groups.setdefault(root(i), []).append(case)
    return list(groups.values())


def assign(cases, seed):
    groups = components(cases)
    groups.sort(key=lambda group: hashlib.sha256(json.dumps([seed, sorted(c['id'] for c in group)]).encode()).hexdigest())
    # Three-way partition, with at least one group in validation/holdout when possible.
    n = len(groups)
    held = max(1, n // 5) if n >= 3 else 0
    assignments = {}
    for i, group in enumerate(groups):
        split = 'holdout' if i < held else 'validation' if i < held * 2 else 'train'
        component = hashlib.sha256(json.dumps(sorted(c['id'] for c in group)).encode()).hexdigest()
        for case in group:
            assignments[case['id']] = (split, component)
    return assignments
