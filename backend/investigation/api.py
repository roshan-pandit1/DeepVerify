import hmac
import json
import os
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, Depends, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from .extraction import extract, metadata
from .ingestion import fetch_article
from .memory import related, LexicalMemory
from .review import effective_stance, review
from .store import connect, migrate, now, uid, rows, audit


@asynccontextmanager
async def lifespan(app):
    migrate()
    yield


app = FastAPI(title='DeepVerify Investigation API', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[os.getenv('FRONTEND_URL', 'http://localhost:3000')],
                   allow_methods=['GET', 'POST', 'PUT'], allow_headers=['Content-Type', 'Authorization'])


def admin(authorization: str = Header(default='')):
    expected = os.getenv('INVESTIGATION_ADMIN_TOKEN', '')
    if len(expected) < 24 or not hmac.compare_digest(authorization, 'Bearer ' + expected):
        raise HTTPException(403, 'Administrator token required (configured token must be at least 24 characters).')
    return 'token-administrator'


class Submission(BaseModel):
    text: str = Field(min_length=5, max_length=12000)
    input_type: Literal['text', 'url'] = 'text'
    provider: Literal['serpapi', 'offline'] = 'serpapi'

    @field_validator('text')
    @classmethod
    def meaningful(cls, value):
        if len(value.strip()) < 5:
            raise ValueError('Enter a claim or public article URL.')
        return value.strip()


class Edits(BaseModel):
    assertions: list[str] = Field(min_length=1, max_length=20)

    @field_validator('assertions')
    @classmethod
    def valid(cls, values):
        values = list(dict.fromkeys(x.strip() for x in values))
        if any(len(x) < 5 or len(x) > 1500 for x in values):
            raise ValueError('Each assertion must contain 5–1,500 characters.')
        return values


class Feedback(BaseModel):
    reviewer: str = Field(min_length=8, max_length=100)
    dimension: Literal['relevance', 'stance']
    label: str


class Review(BaseModel):
    decision: Literal['approved', 'rejected']
    reason: str = Field(min_length=5, max_length=1000)


def require(db, claim_id):
    item = db.execute('SELECT * FROM investigations WHERE claim_id=?', (claim_id,)).fetchone()
    if not item:
        raise HTTPException(404, 'Investigation not found')
    return item


def add_assertions(db, claim_id, texts):
    for text in texts:
        assertion_id, m = uid(), metadata(text)
        db.execute('INSERT INTO assertions VALUES (?,?,?,?,?,?)', (assertion_id, claim_id, text, json.dumps(m['entities']), 1.0, now()))
        db.execute('INSERT INTO assertion_details(assertion_id, dates, locations) VALUES (?,?,?)', (assertion_id, json.dumps(m['dates']), json.dumps(m['locations'])))


@app.post('/api/investigations', status_code=201)
def create(body: Submission):
    try:
        text = fetch_article(body.text) if body.input_type == 'url' else body.text
        assertions = extract(text)
    except (ValueError, OSError) as exc:
        raise HTTPException(422, str(exc)) from exc
    claim_id = uid()
    with connect() as db:
        db.execute('INSERT INTO claims VALUES (?,?,?,?,?,?,?)', (claim_id, body.text, body.input_type.upper(), text, 'EXTRACTED', now(), now()))
        db.execute('INSERT INTO investigations VALUES (?,?,?,?,?,?,?)', (claim_id, 'draft', body.provider, None, LexicalMemory.version, text, now()))
        add_assertions(db, claim_id, assertions)
        audit(db, claim_id, 'extraction', 'Rule-based assertion candidates. Entities/dates/locations are heuristic; edit and split compound claims before retrieval.')
    return detail(claim_id)


@app.get('/api/investigations')
def history():
    with connect() as db:
        return rows(db, 'SELECT i.*, c.raw_input FROM investigations i JOIN claims c ON c.id=i.claim_id ORDER BY i.created_at DESC LIMIT 100')


@app.get('/api/investigations/{claim_id}')
def detail(claim_id: str):
    with connect() as db:
        item = dict(require(db, claim_id))
        item['assertions'] = rows(db, 'SELECT a.*, d.* FROM assertions a JOIN assertion_details d ON a.id=d.assertion_id WHERE claim_id=? ORDER BY a.rowid', (claim_id,))
        for assertion in item['assertions']:
            assertion['evidence'] = rows(db, 'SELECT e.*, d.* FROM evidence_items e JOIN evidence_details d ON e.id=d.evidence_id WHERE assertion_id=? ORDER BY d.relevance DESC, e.id', (assertion['id'],))
            for evidence in assertion['evidence']:
                evidence['effective_stance'] = effective_stance(db, evidence['id'], evidence['predicted_stance'])
                evidence['feedback'] = rows(db, 'SELECT id, dimension, label, approval, created_at FROM feedback WHERE evidence_id=?', (evidence['id'],))
        item['searches'] = rows(db, 'SELECT * FROM searches WHERE claim_id=? ORDER BY rowid', (claim_id,))
        item['audit'] = rows(db, 'SELECT * FROM audit_log_entries WHERE claim_id=? ORDER BY rowid', (claim_id,))
        item['related'] = related(db, claim_id)
        item['job'] = dict(r) if (r := db.execute('SELECT state, lease_until, attempts FROM investigation_jobs WHERE claim_id=?', (claim_id,)).fetchone()) else None
        return item


@app.put('/api/investigations/{claim_id}/assertions')
def edit(claim_id: str, body: Edits):
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        if require(db, claim_id)['stage'] != 'draft':
            raise HTTPException(409, 'Assertions are locked after retrieval starts. Create a new investigation to revise them.')
        db.execute('DELETE FROM assertion_details WHERE assertion_id IN (SELECT id FROM assertions WHERE claim_id=?)', (claim_id,))
        db.execute('DELETE FROM assertions WHERE claim_id=?', (claim_id,))
        add_assertions(db, claim_id, body.assertions)
        db.execute('UPDATE investigations SET memory_text=? WHERE claim_id=?', (' '.join(body.assertions), claim_id))
        audit(db, claim_id, 'assertions edited', f'{len(body.assertions)} editable assertion candidates saved.')
    return detail(claim_id)


@app.post('/api/investigations/{claim_id}/run')
def run(claim_id: str):
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        if require(db, claim_id)['stage'] not in ('draft', 'partial'):
            raise HTTPException(409, 'Already queued or completed. Create a new investigation to refresh completed research.')
        db.execute("INSERT INTO investigation_jobs(claim_id,state) VALUES (?,'queued') ON CONFLICT(claim_id) DO UPDATE SET state='queued', owner=NULL, lease_until=0", (claim_id,))
        db.execute("UPDATE investigations SET stage='queued', error=NULL WHERE claim_id=?", (claim_id,))
        audit(db, claim_id, 'queued', 'Waiting for the separate investigation worker.')
    return detail(claim_id)


@app.post('/api/evidence/{evidence_id}/feedback')
def feedback(evidence_id: str, body: Feedback):
    labels = {'relevance': ['relevant', 'irrelevant'], 'stance': ['supporting', 'contradicting', 'unrelated', 'needing review']}
    if body.label not in labels[body.dimension]:
        raise HTTPException(422, 'Invalid label for this feedback dimension')
    with connect() as db:
        if not db.execute('SELECT 1 FROM evidence_details WHERE evidence_id=?', (evidence_id,)).fetchone():
            raise HTTPException(404, 'Evidence not found')
        db.execute('INSERT OR IGNORE INTO feedback VALUES (?,?,?,?,?,?,?)', (uid(), evidence_id, body.reviewer, body.dimension, body.label, now(), 'pending'))
        return dict(db.execute('SELECT * FROM feedback WHERE evidence_id=? AND reviewer=? AND dimension=? AND label=?', (evidence_id, body.reviewer, body.dimension, body.label)).fetchone())


@app.get('/api/admin/feedback', dependencies=[Depends(admin)])
def pending():
    with connect() as db:
        return {'feedback': rows(db, '''SELECT f.*, a.assertion_text, e.content_snippet, e.source_url, d.predicted_stance, d.fixture
                     FROM feedback f JOIN evidence_items e ON e.id=f.evidence_id JOIN assertions a ON a.id=e.assertion_id
                     JOIN evidence_details d ON d.evidence_id=e.id ORDER BY f.created_at DESC'''),
                'review_history': rows(db, 'SELECT * FROM feedback_reviews ORDER BY created_at DESC')}


@app.post('/api/admin/feedback/{feedback_id}/review')
def approve(feedback_id: str, body: Review, administrator=Depends(admin)):
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        try:
            review(db, feedback_id, body.decision, body.reason, administrator)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc
    return {'status': body.decision}


@app.get('/api/learning')
def learning():
    from .training import eligible_data
    from .ranking import score
    with connect() as db:
        active = db.execute('SELECT model_id FROM active_ranker WHERE singleton=1').fetchone()['model_id']
        effective = score([0, 0, 0, 1, 1], active)[1]
        count = len(eligible_data(db))
        return {'active_ranker': active, 'effective_ranker': effective, 'approved_live_examples': count,
                'status': 'collecting reviewed feedback' if active == 'baseline-v1' else 'reviewed candidate active',
                'memory': LexicalMemory.version, 'training': 'Batch only; searches update memory, not model weights.'}
