"""Replaceable, conservative passage interpretation; ranking is never truth confidence."""
import os
import re
from typing import Protocol

from .extraction import metadata
from .ranking import tokens

VERSION = 'guarded-passage-rules-v2'


class StanceClassifier(Protocol):
    version: str
    def classify(self, assertion: str, passage: str, context: str = '') -> dict: ...


def baseline(assertion, passage):
    return 'needing review' if tokens(assertion) & tokens(passage) else 'unrelated'


class GuardedRules:
    version = VERSION

    def classify(self, assertion, passage, context=''):
        reasons = []
        a, p = metadata(assertion), metadata(passage)
        negation = lambda text: bool(re.search(r"\b(?:not|no|never|neither|without)\b|n't\b", text.lower()))
        if negation(assertion) != negation(passage):
            reasons.append('Negation differs; scope must be reviewed, not assumed contradictory.')
        if a['dates'] and (set(a['dates']) != set(p['dates'])):
            reasons.append('Date mismatch or missing assertion date in passage; temporal relevance needs review.')
        if a['locations'] and set(a['locations']) != set(p['locations']):
            reasons.append('Location mismatch or missing location; do not transfer findings between places.')
        entities = lambda values: {x for x in values if x not in {'The', 'In', 'It', 'This', 'An', 'According'}}
        if entities(a['entities']) - entities(p['entities']):
            reasons.append('Assertion entities are missing or differ; entity resolution needs review.')
        if re.search(r'["“”]|\b(?:said|claimed|alleged|reported|according to)\b', passage + ' ' + context, re.I):
            reasons.append('Quoted/attributed statement or context: reporting a claim does not establish it.')
        if re.search(r'\b(?:today|currently|now|latest)\b', assertion, re.I):
            reasons.append('Time-sensitive assertion: establish an as-of date and source freshness.')
        stance = 'needing review'
        if not reasons:
            stance = baseline(assertion, passage)
            reasons.append('No shared factual terms; lexical triage only.' if stance == 'unrelated' else
                           'Passage shares factual terms, but lexical overlap cannot establish entailment or contradiction.')
        return {'stance': stance, 'method': self.version, 'explanation': ' '.join(reasons)}


class LegacyRules:
    version = 'conservative-lexical-triage-v1'

    def classify(self, assertion, passage, context=''):
        return {'stance': baseline(assertion, passage), 'method': self.version,
                'explanation': 'Lexical triage only; no semantic support or contradiction inferred.'}


def classifier():
    # No external model required; optional implementations must implement the protocol.
    name = os.getenv('STANCE_CLASSIFIER', 'guarded-rules')
    if name == 'legacy':
        return LegacyRules()
    if name != 'guarded-rules':
        raise ValueError('Unknown STANCE_CLASSIFIER. Configure guarded-rules or legacy.')
    return GuardedRules()


def classify(assertion, passage):
    result = classifier().classify(assertion, passage)
    return result['stance'], result['explanation']
