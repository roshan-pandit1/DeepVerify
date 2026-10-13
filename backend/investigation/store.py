import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

from .runtime import storage_path


def now():
    return datetime.now(timezone.utc).isoformat()


def uid():
    return str(uuid.uuid4())


@contextmanager
def connect():
    db = sqlite3.connect(storage_path('INVESTIGATION_DB', 'deepfake.db'), timeout=30)
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
        CREATE TABLE IF NOT EXISTS source_documents (
          id TEXT PRIMARY KEY, source_url TEXT NOT NULL, final_url TEXT NOT NULL, retrieved_at TEXT NOT NULL,
          method TEXT NOT NULL, status TEXT NOT NULL, title TEXT NOT NULL, main_text TEXT NOT NULL,
          publication_date TEXT, date_method TEXT, content_hash TEXT, body_hash TEXT, error TEXT, synthetic INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS source_passages (
          evidence_id TEXT PRIMARY KEY REFERENCES evidence_items(id), source_id TEXT NOT NULL REFERENCES source_documents(id),
          assertion_id TEXT NOT NULL REFERENCES assertions(id), start_offset INTEGER, end_offset INTEGER,
          context TEXT NOT NULL, context_start INTEGER, context_end INTEGER, search_snippet TEXT NOT NULL, selection_method TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS evaluation_datasets (
          id TEXT PRIMARY KEY, name TEXT NOT NULL, version TEXT NOT NULL, format_version TEXT NOT NULL,
          seed INTEGER NOT NULL, synthetic INTEGER NOT NULL, state TEXT NOT NULL, created_at TEXT NOT NULL,
          frozen_hash TEXT, UNIQUE(name, version));
        CREATE TABLE IF NOT EXISTS evaluation_cases (
          id TEXT PRIMARY KEY, dataset_id TEXT NOT NULL REFERENCES evaluation_datasets(id),
          assertion_id TEXT NOT NULL REFERENCES assertions(id), related_group TEXT NOT NULL,
          temporal_context TEXT NOT NULL, categories TEXT NOT NULL, snapshot_json TEXT NOT NULL,
          split TEXT, component TEXT, UNIQUE(dataset_id, assertion_id));
        CREATE TABLE IF NOT EXISTS evaluation_labels (
          id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES evaluation_cases(id), target TEXT NOT NULL,
          dimension TEXT NOT NULL, label TEXT NOT NULL, reviewer TEXT NOT NULL, status TEXT NOT NULL,
          reason TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS evaluation_reports (
          id TEXT PRIMARY KEY, dataset_id TEXT NOT NULL REFERENCES evaluation_datasets(id), partition TEXT NOT NULL,
          model_id TEXT NOT NULL, report_json TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS evaluation_holdout_locks (
          dataset_id TEXT PRIMARY KEY REFERENCES evaluation_datasets(id), model_hash TEXT NOT NULL,
          report_id TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS pilot_runs (
          id TEXT PRIMARY KEY, kind TEXT NOT NULL, created_at TEXT NOT NULL, specification TEXT NOT NULL,
          max_searches INTEGER NOT NULL, max_sources INTEGER NOT NULL, unit_cost REAL NOT NULL, max_cost REAL NOT NULL,
          status TEXT NOT NULL, dataset_id TEXT REFERENCES evaluation_datasets(id));
        CREATE TABLE IF NOT EXISTS pilot_jobs (
          claim_id TEXT PRIMARY KEY REFERENCES claims(id), run_id TEXT NOT NULL REFERENCES pilot_runs(id),
          plan_json TEXT NOT NULL, max_sources INTEGER NOT NULL, case_id TEXT REFERENCES evaluation_cases(id));
        CREATE TABLE IF NOT EXISTS pilot_requests (
          id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES pilot_runs(id), kind TEXT NOT NULL,
          reference TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS workspace_policy (singleton INTEGER PRIMARY KEY CHECK(singleton=1), policy_json TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS workspace_events (id TEXT PRIMARY KEY, kind TEXT NOT NULL, occurred REAL NOT NULL, cost_microusd INTEGER NOT NULL, reference TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS workspace_event_window ON workspace_events(kind, occurred);
        CREATE TABLE IF NOT EXISTS workspace_request_leases (id TEXT PRIMARY KEY, expires REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS search_result_failures (
          id TEXT PRIMARY KEY, search_id TEXT NOT NULL REFERENCES searches(id),
          result_index INTEGER NOT NULL, category TEXT NOT NULL, incident TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS search_observations (
          search_id TEXT PRIMARY KEY REFERENCES searches(id), latency_ms INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS source_observations (
          source_id TEXT PRIMARY KEY REFERENCES source_documents(id), latency_ms INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS worker_observations (
          worker_id TEXT PRIMARY KEY, observed_at TEXT NOT NULL, mode TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS pilot_dataset_policies (
          dataset_id TEXT PRIMARY KEY REFERENCES evaluation_datasets(id), protocol TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS pilot_case_policies (
          case_id TEXT PRIMARY KEY REFERENCES evaluation_cases(id), required_reviewers INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS independent_reviews (
          id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES evaluation_cases(id), target TEXT NOT NULL,
          dimension TEXT NOT NULL, label TEXT NOT NULL, reviewer TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS review_adjudications (
          id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES evaluation_cases(id), target TEXT NOT NULL,
          dimension TEXT NOT NULL, label TEXT NOT NULL, adjudicator TEXT NOT NULL, reason TEXT NOT NULL,
          reviews_hash TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS failure_observations (
          id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES evaluation_cases(id), target TEXT NOT NULL,
          kind TEXT NOT NULL, detail TEXT NOT NULL, reviewer TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS failure_observation_reviews (
          id TEXT PRIMARY KEY, observation_id TEXT NOT NULL REFERENCES failure_observations(id), decision TEXT NOT NULL,
          reviewer TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL);
        ''')
        db.execute('INSERT OR IGNORE INTO investigation_migrations VALUES (1, ?)', (now(),))
        db.execute('INSERT OR IGNORE INTO investigation_migrations VALUES (2, ?)', (now(),))
        db.execute('INSERT OR IGNORE INTO investigation_migrations VALUES (3, ?)', (now(),))
        db.execute('INSERT OR IGNORE INTO investigation_migrations VALUES (4, ?)', (now(),))
        db.execute('INSERT OR IGNORE INTO investigation_migrations VALUES (5, ?)', (now(),))
        from .controls import environment_policy
        db.execute('INSERT OR IGNORE INTO workspace_policy VALUES (1,?)', (json.dumps(environment_policy(), sort_keys=True),))


def audit(db, claim_id, stage, output):
    db.execute('INSERT INTO audit_log_entries VALUES (?,?,?,?,?,?,?)',
               (uid(), claim_id, stage, '', output, 0, now()))


def rows(db, sql, args=()):
    return [dict(r) for r in db.execute(sql, args)]


if __name__ == '__main__':
    migrate()
    print('Additive investigation migrations through 5 applied; existing records preserved.')
