from datetime import timedelta
from sqlalchemy import select
from app.db import SessionLocal, Response, Case, Reason, now
from app.school_db import DatasetRecord, Institution, ModelRecord
from test_journeys import setup, enroll, authorize, post, A


def test_correction_preserves_original_safety_and_invalidates_source_model(client):
    c = client
    inv, cfg = setup(c, False)
    phone = enroll(c, inv)
    c.headers['authorization'] = 'Bearer ' + phone['token']
    authorize(c, inv, cfg)
    form = c.get(A + '/me/questionnaires').json()[0]
    at = now()
    body = dict(instrument_code=form['instrument_id'], instrument_version=form['version'],
                answers={f'q{i}': int(i == 9) for i in range(1, 10)}, functioning=0,
                applied_at=at.isoformat(), recall_end=at.isoformat(), recall_start=(at-timedelta(days=14)).isoformat())
    original = post(c, '/me/questionnaires', body)
    rows = c.get(A + '/me/questionnaires/history').json()
    rid = rows[0]['id']
    assert 'total' not in rows[0] and 'review_threshold' not in rows[0]['definition']
    with SessionLocal.begin() as db:
        institution = db.scalar(select(Institution))
        ds = DatasetRecord(institution_id=institution.id, owner_id=cfg['primary_id'], name='Ficticio',
                           manifest={'label_provenance': {rid: {}}}, path='/fixture', sha256='0'*64)
        db.add(ds); db.flush()
        model = ModelRecord(institution_id=institution.id, dataset_id=ds.id, manifest={}, metrics={}, artifact='/fixture', state='active')
        db.add(model); db.flush(); mid = model.id
    corrected = dict(answers={f'q{i}': 0 for i in range(1, 10)}, functioning=0, reason='Corrección ficticia de respuesta')
    route = f'/me/questionnaires/{rid}/corrections'
    result = post(c, route, corrected, key='correction-test')
    assert result['revision'] == 2
    assert post(c, route, corrected, key='correction-test') == result
    post(c, route, corrected, code=409)
    with SessionLocal() as db:
        assert db.get(Response, rid).detail['answers']['q9'] == 1
        assert len(list(db.scalars(select(Response)))) == 2
        assert db.get(ModelRecord, mid).state == 'retired'
        assert db.scalar(select(Reason).where(Reason.kind == 'safety_review')) is not None
    rows = c.get(A + '/me/questionnaires/history').json()
    assert sum(r['current'] for r in rows) == 1
    assert c.get(A + '/me/questionnaires').json() == []
