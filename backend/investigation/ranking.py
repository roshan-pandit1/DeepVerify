import json
import math
import os
import re
from pathlib import Path

from .extraction import metadata

FEATURE_VERSION = 'lexical-entities-temporal-v1'
FEATURES = ['lexical_overlap', 'entity_overlap', 'temporal_match', 'date_missing', 'semantic_missing']


def tokens(text):
    return set(re.findall(r'\b\w{3,}\b', text.lower())) - {'the', 'and', 'was', 'that', 'for', 'with', 'has', 'are'}


def features(assertion, passage, date):
    a, b = tokens(assertion), tokens(passage)
    ma, mb = metadata(assertion), metadata(passage)
    ea, eb = set(ma['entities']), set(mb['entities'])
    years = set(ma['dates'])
    return [len(a & b) / max(1, len(a)), len(ea & eb) / max(1, len(ea)),
            float(bool(years) and any(y in (date or '') or y in passage for y in years)),
            float(not date), 1.0]


def baseline(x):
    return 0.7 * x[0] + 0.2 * x[1] + 0.1 * x[2]


def artifact_dir():
    return Path(os.getenv('INVESTIGATION_ARTIFACTS', 'investigation-data'))


def score(x, model_id='baseline-v1'):
    if model_id == 'baseline-v1':
        return baseline(x), model_id
    try:
        data = json.loads((artifact_dir() / f'{model_id}.json').read_text())
        if data['feature_version'] != FEATURE_VERSION:
            raise ValueError('feature version mismatch')
        if len(x) != len(data['coefficients']):
            raise ValueError('feature count mismatch')
        z = sum(a * b for a, b in zip(x, data['coefficients'])) + data['intercept']
        return 1 / (1 + math.exp(-max(-700, min(700, z)))), model_id
    except (OSError, ValueError, KeyError):
        return baseline(x), 'baseline-v1 (artifact unavailable)'
