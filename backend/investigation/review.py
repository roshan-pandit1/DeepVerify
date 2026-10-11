from .assessment import assess
from .store import now, uid, rows, audit


def effective_stance(db, evidence_id, prediction):
    row = db.execute("SELECT label FROM feedback WHERE evidence_id=? AND dimension='stance' AND approval='approved'", (evidence_id,)).fetchone()
    irrelevant = db.execute("SELECT 1 FROM feedback WHERE evidence_id=? AND dimension='relevance' AND approval='approved' AND label='irrelevant'", (evidence_id,)).fetchone()
    return 'unrelated' if irrelevant else row['label'] if row else prediction


def update_assessments(db, claim_id):
    for assertion in rows(db, 'SELECT id FROM assertions WHERE claim_id=?', (claim_id,)):
        evidence = rows(db, '''SELECT e.id, d.predicted_stance FROM evidence_items e
                            JOIN evidence_details d ON d.evidence_id=e.id WHERE assertion_id=?''', (assertion['id'],))
        result, explanation = assess([effective_stance(db, e['id'], e['predicted_stance']) for e in evidence])
        db.execute('UPDATE assertion_details SET assessment=?, explanation=? WHERE assertion_id=?', (result, explanation, assertion['id']))


def review(db, feedback_id, decision, reason, administrator):
    item = db.execute('SELECT * FROM feedback WHERE id=?', (feedback_id,)).fetchone()
    if not item:
        raise ValueError('Feedback not found')
    if decision == 'approved':
        previous = rows(db, "SELECT id FROM feedback WHERE evidence_id=? AND dimension=? AND approval='approved' AND id != ?",
                        (item['evidence_id'], item['dimension'], feedback_id))
        for old in previous:
            db.execute("UPDATE feedback SET approval='superseded' WHERE id=?", (old['id'],))
            db.execute('INSERT INTO feedback_reviews VALUES (?,?,?,?,?,?)', (uid(), old['id'], administrator, 'superseded', f'Replaced by {feedback_id}', now()))
    db.execute('UPDATE feedback SET approval=? WHERE id=?', (decision, feedback_id))
    db.execute('INSERT INTO feedback_reviews VALUES (?,?,?,?,?,?)', (uid(), feedback_id, administrator, decision, reason, now()))
    claim = db.execute('SELECT a.claim_id FROM assertions a JOIN evidence_items e ON a.id=e.assertion_id WHERE e.id=?', (item['evidence_id'],)).fetchone()['claim_id']
    update_assessments(db, claim)
    audit(db, claim, 'feedback review', f'{feedback_id}: {decision}; {reason}')
