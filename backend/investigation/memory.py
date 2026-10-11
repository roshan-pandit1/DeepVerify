from typing import Protocol
from .ranking import tokens
from .store import rows


class Embedding(Protocol):
    version: str
    def encode(self, text: str): ...


class LexicalMemory:
    version = 'lexical-jaccard-v1'

    def encode(self, text):
        return tokens(text)


def related(db, claim_id):
    current = db.execute('SELECT * FROM investigations WHERE claim_id=?', (claim_id,)).fetchone()
    if not current:
        return []
    encoder = LexicalMemory()
    a = encoder.encode(current['memory_text'])
    candidates = []
    for row in rows(db, 'SELECT * FROM investigations WHERE claim_id != ? AND provider=?', (claim_id, current['provider'])):
        b = encoder.encode(row['memory_text'])
        similarity = len(a & b) / max(1, len(a | b))
        if similarity > 0.1:
            candidates.append({**row, 'similarity': similarity, 'method': encoder.version,
                               'reuse': 'Related research reference only; evidence is freshly retrieved for every run.'})
    return sorted(candidates, key=lambda r: (-r['similarity'], r['claim_id']))[:5]
