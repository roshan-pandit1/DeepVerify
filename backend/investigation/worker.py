"""Durable leased jobs. Run separately: python -m investigation.worker."""
import argparse
import json
import time
import os

from . import retrieval, sources, budgets
from .ranking import features, score
from .review import update_assessments
from .stance import classifier
from .store import connect, migrate, now, uid, rows, audit

LEASE_SECONDS = 120


def reserve(run_id=None):
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        job = db.execute("""SELECT * FROM investigation_jobs WHERE (state='queued' OR (state='running' AND lease_until < ?))
                            AND (? IS NULL OR claim_id IN (SELECT claim_id FROM pilot_jobs WHERE run_id=?)) ORDER BY rowid LIMIT 1""",
                         (time.time(), run_id, run_id)).fetchone()
        if not job:
            return None
        owner = uid()
        db.execute("UPDATE investigation_jobs SET state='running', owner=?, lease_until=?, attempts=attempts+1 WHERE claim_id=?", (owner, time.time() + LEASE_SECONDS, job['claim_id']))
        db.execute("UPDATE investigations SET stage='retrieving', error=NULL WHERE claim_id=?", (job['claim_id'],))
        audit(db, job['claim_id'], 'worker lease', 'Job acquired; completed assertion searches survive worker restarts.')
        return job['claim_id'], owner


def owned(db, claim_id, owner):
    return db.execute("SELECT 1 FROM investigation_jobs WHERE claim_id=? AND owner=? AND state='running'", (claim_id, owner)).fetchone()


def run_once(run_id=None):
    with connect() as db:
        db.execute('INSERT OR REPLACE INTO worker_observations VALUES (?,?,?)', (str(os.getpid()), now(), 'worker iteration observed; not proof of continuous liveness'))
    job = reserve(run_id)
    if not job:
        return False
    claim_id, owner = job
    limits = budgets.policy(claim_id)
    with connect() as db:
        assertions = rows(db, 'SELECT * FROM assertions WHERE claim_id=? ORDER BY rowid', (claim_id,))
        provider_name = db.execute('SELECT provider FROM investigations WHERE claim_id=?', (claim_id,)).fetchone()['provider']
    for assertion in assertions:
        search_id = uid()
        with connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if not owned(db, claim_id, owner):
                return True
            if db.execute("SELECT 1 FROM searches WHERE assertion_id=? AND state='complete'", (assertion['id'],)).fetchone():
                continue
            db.execute("UPDATE searches SET state='interrupted', error='Worker interrupted; search retried' WHERE assertion_id=? AND state='running'", (assertion['id'],))
            db.execute('UPDATE investigation_jobs SET lease_until=? WHERE claim_id=?', (time.time() + LEASE_SECONDS, claim_id))
            db.execute('INSERT INTO searches VALUES (?,?,?,?,?,?,?,?)', (search_id, claim_id, assertion['id'], assertion['assertion_text'], provider_name, now(), 'running', None))
        try:
            if limits:
                budgets.reserve(limits['run_id'], 'search', search_id)
            started = time.monotonic()
            try:
                results = retrieval.provider(provider_name).search(assertion['assertion_text'])
            finally:
                with connect() as db:
                    db.execute('INSERT OR REPLACE INTO search_observations VALUES (?,?)', (search_id, int((time.monotonic() - started) * 1000)))
            if limits:
                results = results[:limits['max_sources']]
            prepared, seen = [], set()
            for item in results:
                url = retrieval.canonical(item['url'])
                if url in seen:
                    continue
                seen.add(url)
                # Each bounded fetch renews the lease; never hold a DB transaction over network IO.
                with connect() as db:
                    if not owned(db, claim_id, owner):
                        return True
                    db.execute('UPDATE investigation_jobs SET lease_until=? WHERE claim_id=? AND owner=?',
                               (time.time() + LEASE_SECONDS, claim_id, owner))
                unavailable = None
                if limits and not item['fixture']:
                    try:
                        budgets.reserve(limits['run_id'], 'source', url)
                    except retrieval.Unavailable as exc:
                        unavailable = str(exc)
                prepared.append((sources.enrich(item, assertion['assertion_text'], unavailable), url))
            with connect() as db:
                db.execute('BEGIN IMMEDIATE')
                if not owned(db, claim_id, owner):
                    return True
                active = db.execute('SELECT model_id FROM active_ranker WHERE singleton=1').fetchone()['model_id']
                for item, url in prepared:
                    if db.execute('''SELECT 1 FROM evidence_items e JOIN evidence_details d ON e.id=d.evidence_id
                                     WHERE e.assertion_id=? AND d.canonical_url=?''', (assertion['id'], url)).fetchone():
                        continue
                    evidence_id = uid()
                    x = features(assertion['assertion_text'], item['passage'], item['publication_date'])
                    rank, ranker = score(x, active)
                    classification = classifier().classify(assertion['assertion_text'], item['passage'], item['context'])
                    db.execute('INSERT INTO evidence_items VALUES (?,?,?,?,?,?,?,?)',
                               (evidence_id, assertion['id'], item['title'], item['url'], item['passage'], 'NEUTRAL', 0.0, now()))
                    db.execute('INSERT INTO evidence_details VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                               (evidence_id, url, item['publication_date'], item['method'], item['kind'], rank,
                                classification['stance'], classification['method'], classification['explanation'], int(item['fixture']), ranker, json.dumps(x)))
                    sources.persist(db, evidence_id, assertion['id'], item)
                db.execute("UPDATE searches SET state='complete', retrieved_at=? WHERE id=?", (now(), search_id))
                update_assessments(db, claim_id)
                audit(db, claim_id, 'retrieval', f"Assertion {assertion['id']}: {len(prepared)} distinct source URLs; {provider_name}")
        except Exception as exc:
            error = str(exc) if isinstance(exc, retrieval.Unavailable) else 'Retrieval processing failed. Check worker configuration and retry.'
            with connect() as db:
                if not owned(db, claim_id, owner):
                    return True
                state = 'unavailable' if isinstance(exc, retrieval.Unavailable) else 'failed'
                db.execute('UPDATE searches SET state=?, error=?, retrieved_at=? WHERE id=?', (state, error, now(), search_id))
                audit(db, claim_id, 'retrieval failure', error)
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        if not owned(db, claim_id, owner):
            return True
        failures = db.execute("SELECT COUNT(*) FROM assertions a WHERE claim_id=? AND NOT EXISTS (SELECT 1 FROM searches s WHERE s.assertion_id=a.id AND s.state='complete')", (claim_id,)).fetchone()[0]
        stage = 'partial' if failures else 'complete'
        error = 'Some searches are unavailable or failed. Inspect search audit, configure the provider, then retry.' if failures else None
        db.execute('UPDATE investigations SET stage=?, error=?, memory_text=? WHERE claim_id=?', (stage, error, ' '.join(a['assertion_text'] for a in assertions), claim_id))
        db.execute("UPDATE claims SET status='COMPLETED', updated_at=? WHERE id=?", (now(), claim_id))
        db.execute("UPDATE investigation_jobs SET state='done', lease_until=0 WHERE claim_id=?", (claim_id,))
        update_assessments(db, claim_id)
        audit(db, claim_id, 'assessment', 'Assertion-level sufficiency assessed separately from relevance ranking and source stance.')
        audit(db, claim_id, 'memory updated', 'lexical-jaccard-v1; stored assertions, searches, evidence and assessments. No model training.')
    return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--run-id', help='Only process jobs belonging to this bounded pilot/validation run')
    args = parser.parse_args()
    migrate()
    if args.once:
        run_once(args.run_id)
    else:
        while True:
            if not run_once(args.run_id):
                time.sleep(2)
