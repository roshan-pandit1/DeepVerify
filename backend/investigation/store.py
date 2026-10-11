import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()


def now():
    return datetime.now(timezone.utc).isoformat()


def uid():
    return str(uuid.uuid4())


@contextmanager
def connect():
    db = sqlite3.connect(os.getenv('INVESTIGATION_DB', 'deepfake.db'), timeout=30)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA journal_mode=WAL')
    try:
        with db:
            yield db
    finally:
        db.close()


def migrate():
    # Existing SQLAlchemy column names and enum storage values are preserved.
    with connect() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS claims (
          id TEXT PRIMARY KEY, raw_input TEXT NOT NULL, input_type TEXT NOT NULL,
          normalized_text TEXT, status TEXT NOT NULL, created_at TEXT, updated_at TEXT);
        CREATE TABLE IF NOT EXISTS assertions (
          id TEXT PRIMARY KEY, claim_id TEXT NOT NULL REFERENCES claims(id),
          assertion_text TEXT NOT NULL, entity_names_json TEXT, confidence_weight REAL NOT NULL,
          created_at TEXT);
        CREATE TABLE IF NOT EXISTS evidence_items (
          id TEXT PRIMARY KEY, assertion_id TEXT NOT NULL REFERENCES assertions(id),
          source_name TEXT NOT NULL, source_url TEXT, content_snippet TEXT NOT NULL,
          stance TEXT NOT NULL, credibility_score REAL NOT NULL, retrieved_at TEXT);
        CREATE TABLE IF NOT EXISTS audit_log_entries (
          id TEXT PRIMARY KEY, claim_id TEXT NOT NULL REFERENCES claims(id), stage_name TEXT NOT NULL,
          input_summary TEXT NOT NULL, output_summary TEXT NOT NULL, execution_time_ms INTEGER NOT NULL,
          timestamp TEXT);
        CREATE TABLE IF NOT EXISTS investigation_migrations (version INTEGER PRIMARY KEY, applied_at TEXT);
        CREATE TABLE IF NOT EXISTS investigations (
          claim_id TEXT PRIMARY KEY REFERENCES claims(id), stage TEXT NOT NULL, provider TEXT NOT NULL,
          error TEXT, memory_version TEXT NOT NULL, memory_text TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS assertion_details (
          assertion_id TEXT PRIMARY KEY REFERENCES assertions(id), dates TEXT NOT NULL, locations TEXT NOT NULL,
          assessment TEXT NOT NULL DEFAULT 'insufficient evidence', explanation TEXT NOT NULL DEFAULT 'Awaiting retrieval');
        CREATE TABLE IF NOT EXISTS investigation_jobs (
          claim_id TEXT PRIMARY KEY REFERENCES claims(id), state TEXT NOT NULL,
          lease_until REAL NOT NULL DEFAULT 0, owner TEXT, attempts INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS searches (
          id TEXT PRIMARY KEY, claim_id TEXT NOT NULL REFERENCES claims(id),
          assertion_id TEXT NOT NULL REFERENCES assertions(id), query TEXT NOT NULL, provider TEXT NOT NULL,
          retrieved_at TEXT NOT NULL, state TEXT NOT NULL, error TEXT);
        CREATE TABLE IF NOT EXISTS evidence_details (
          evidence_id TEXT PRIMARY KEY REFERENCES evidence_items(id), canonical_url TEXT NOT NULL,
          publication_date TEXT, retrieval_method TEXT NOT NULL, passage_kind TEXT NOT NULL,
          relevance REAL NOT NULL, predicted_stance TEXT NOT NULL, classification_method TEXT NOT NULL,
          explanation TEXT NOT NULL, fixture INTEGER NOT NULL, ranker TEXT NOT NULL,
          features TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS feedback (
          id TEXT PRIMARY KEY, evidence_id TEXT NOT NULL REFERENCES evidence_items(id),
          reviewer TEXT NOT NULL, dimension TEXT NOT NULL, label TEXT NOT NULL,
          created_at TEXT NOT NULL, approval TEXT NOT NULL DEFAULT 'pending',
          UNIQUE(evidence_id, reviewer, dimension, label));
        CREATE TABLE IF NOT EXISTS feedback_reviews (
          id TEXT PRIMARY KEY, feedback_id TEXT NOT NULL REFERENCES feedback(id), administrator TEXT NOT NULL,
          decision TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS model_decisions (
          id TEXT PRIMARY KEY, model_id TEXT NOT NULL, action TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS model_evaluations (
          id TEXT PRIMARY KEY, model_id TEXT NOT NULL, report_json TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS active_ranker (singleton INTEGER PRIMARY KEY CHECK(singleton=1), model_id TEXT NOT NULL);
        INSERT OR IGNORE INTO active_ranker VALUES (1, 'baseline-v1');
        ''')
        db.execute('INSERT OR IGNORE INTO investigation_migrations VALUES (1, ?)', (now(),))


def audit(db, claim_id, stage, output):
    db.execute('INSERT INTO audit_log_entries VALUES (?,?,?,?,?,?,?)',
               (uid(), claim_id, stage, '', output, 0, now()))


def rows(db, sql, args=()):
    return [dict(r) for r in db.execute(sql, args)]


if __name__ == '__main__':
    migrate()
    print('Additive investigation migration 1 applied; existing records preserved.')
