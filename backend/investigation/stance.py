from .ranking import features


def classify(assertion, passage):
    relevance = features(assertion, passage, None)[0]
    if relevance == 0:
        return 'unrelated', 'No shared factual terms; lexical triage only, not a semantic judgment.'
    return 'needing review', 'Lexical relevance cannot establish support or contradiction. A reviewed stance is required.'
