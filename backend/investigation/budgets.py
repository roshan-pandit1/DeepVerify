"""Durable reservations count attempts, including crashes; no automatic refund/retry spend."""
from .store import connect, now, uid
from .retrieval import Unavailable


def policy(claim_id):
    with connect() as db:
        row = db.execute('SELECT * FROM pilot_jobs WHERE claim_id=?', (claim_id,)).fetchone()
        return dict(row) if row else None


def reserve(run_id, kind, reference):
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        run = db.execute('SELECT * FROM pilot_runs WHERE id=?', (run_id,)).fetchone()
        if not run or kind not in {'search', 'source'}:
            raise Unavailable('Invalid live-validation budget')
        count = db.execute('SELECT COUNT(*) FROM pilot_requests WHERE run_id=? AND kind=?', (run_id, kind)).fetchone()[0]
        limit = run['max_searches'] if kind == 'search' else run['max_sources']
        if count >= limit or (kind == 'search' and (count + 1) * run['unit_cost'] > run['max_cost'] + 1e-9):
            raise Unavailable('Live-validation request/cost limit reached. No additional request was issued.')
        db.execute('INSERT INTO pilot_requests VALUES (?,?,?,?,?)', (uid(), run_id, kind, reference, now()))
