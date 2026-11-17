"""Cambios acordados para el piloto: corte PHQ-9 ≥ 11, PHQ-2, cuestionarios breves,
proxy de descanso, asistencia por GPS y cuestionario anterior como variable del modelo."""
from datetime import datetime, timezone, timedelta
import numpy as np
from conftest import login
from test_journeys import A, post, setup, enroll, authorize


def phq(answers, at=None):
    at = at or datetime.now(timezone.utc)
    return {'instrument_code': 'PHQ9_ES_AETC_2016', 'instrument_version': 'AETC-2016-es-2', 'answers': answers,
            'functioning': 1 if any(answers.values()) else None, 'applied_at': at.isoformat(),
            'recall_end': at.isoformat(), 'recall_start': (at - timedelta(days=14)).isoformat()}


def test_threshold_is_eleven_and_phq2_is_stored(client):
    from app.phq9 import PHQ9, phq2
    assert PHQ9['review_threshold'] == 11 and PHQ9['version'] == 'AETC-2016-es-2'
    assert phq2({f'q{i}': 2 for i in range(1, 10)}) == 4
    c = client
    inv, cfg = setup(c)
    phone = enroll(c, inv)
    c.headers['authorization'] = 'Bearer ' + phone['token']
    authorize(c, inv, cfg)
    # Total 10: con el corte de adultos abría caso; con el de adolescentes ya no.
    answers = {'q1': 2, 'q2': 2, 'q3': 2, 'q4': 2, 'q5': 1, 'q6': 1, 'q7': 0, 'q8': 0, 'q9': 0}
    post(c, '/me/questionnaires', phq(answers))
    login(c, 'psicologo')
    assert c.get(A + '/cases').json() == []
    from app.db import SessionLocal, Response
    from sqlalchemy import select
    with SessionLocal() as db:
        row = db.scalar(select(Response))
        assert row.detail['total'] == 10 and row.detail['phq2'] == 4 and row.detail['review_threshold'] == 11


def test_eleven_opens_review(client):
    c = client
    inv, cfg = setup(c)
    phone = enroll(c, inv)
    c.headers['authorization'] = 'Bearer ' + phone['token']
    authorize(c, inv, cfg)
    post(c, '/me/questionnaires', phq({'q1': 2, 'q2': 2, 'q3': 2, 'q4': 2, 'q5': 2, 'q6': 1, 'q7': 0, 'q8': 0, 'q9': 0}))
    login(c, 'psicologo')
    rows = c.get(A + '/cases').json()
    assert any(r['kind'] == 'questionnaire_review' for r in rows[0]['reasons'])


def test_checkins_are_optional_due_and_never_open_cases(client):
    c = client
    inv, cfg = setup(c)
    phone = enroll(c, inv)
    token = 'Bearer ' + phone['token']
    c.headers['authorization'] = token
    authorize(c, inv, cfg)
    forms = c.get(A + '/me/questionnaires').json()
    assert [f['instrument_id'] for f in forms] == ['PHQ9_ES_AETC_2016']
    assert forms[0]['submit_path'] == '/me/questionnaires'
    login(c)
    full = c.get(A + '/settings').json()
    keep = set(cfg) | {'phq2_weekly_enabled', 'daily_social_enabled', 'context_questions_enabled', 'school_zone', 'school_days', 'school_start', 'school_end', 'behavior_change_alerts'}
    body = {k: v for k, v in full.items() if k in keep}
    body.update(phq2_weekly_enabled=True, daily_social_enabled=True, context_questions_enabled=True,
                school_zone={'latitude': -12.1, 'longitude': -77.0, 'radius_m': 150})
    r = c.put(A + '/settings', json=body)
    assert r.status_code == 200, r.text
    c.headers['authorization'] = token
    me = c.get(A + '/me').json()
    assert me['school_zone']['radius_m'] == 150 and me['school_zone']['days'] == [0, 1, 2, 3, 4]
    forms = c.get(A + '/me/questionnaires').json()
    codes = [f['instrument_id'] for f in forms]
    assert codes == ['PHQ9_ES_AETC_2016', 'PHQ2_SEMANAL', 'CONTACTO_DIARIO', 'CONTEXTO_MENSUAL']
    daily = forms[2]
    now = datetime.now(timezone.utc).isoformat()
    bad = {'instrument_code': 'CONTACTO_DIARIO', 'instrument_version': daily['version'], 'answers': {'social': 9}, 'applied_at': now}
    post(c, '/me/check-ins', bad, code=422)
    ok = {**bad, 'answers': {'social': 1}}
    post(c, '/me/check-ins', ok)
    post(c, '/me/check-ins', ok, code=409)
    ctx = forms[3]
    answers = {q['id']: q['options'][-1]['value'] for q in ctx['questions']}
    post(c, '/me/check-ins', {'instrument_code': 'CONTEXTO_MENSUAL', 'instrument_version': ctx['version'], 'answers': answers, 'applied_at': now})
    post(c, '/me/check-ins', {'instrument_code': 'PHQ2_SEMANAL', 'instrument_version': forms[1]['version'], 'answers': {'q1': 3, 'q2': 3}, 'applied_at': now})
    codes = [f['instrument_id'] for f in c.get(A + '/me/questionnaires').json()]
    assert codes == ['PHQ9_ES_AETC_2016']
    login(c, 'psicologo')
    assert c.get(A + '/cases').json() == []
    pid = inv['student']['participant_id']
    profile = c.get(A + f'/students/{pid}/profile').json()
    assert {x['code'] for x in profile['checkins']} == {'CONTACTO_DIARIO', 'CONTEXTO_MENSUAL', 'PHQ2_SEMANAL'}


def test_sleep_proxy_longest_rest_between_two_uses():
    from app.sleep import sleep_features, clock
    z = timezone.utc
    t = lambda h, m=0, d=2: datetime(2026, 3, d, h, m, tzinfo=z)
    windows = [(t(0, 0, 1), t(23, 59, 2))]
    spans = [(t(21, 0, 1), t(22, 30, 1)), (t(23, 0, 1), t(23, 40, 1)),
             (t(3, 0), t(3, 1)),  # mirar la hora: menos de 2 minutos, no corta
             (t(7, 0), t(7, 20)), (t(9, 0), t(9, 30))]
    f = sleep_features(spans, windows, '2026-03-02', 'UTC', t(13))
    assert f['sleep_duration_min']['value'] == 440 and f['sleep_duration_min']['eligible']
    assert clock(f['sleep_onset_min']['value']) == '23:40' and clock(f['wake_min']['value']) == '07:00'
    # Sin uso por la mañana no se sabe cuándo despertó: no se inventa.
    f = sleep_features(spans[:2], windows, '2026-03-02', 'UTC', t(13))
    assert f['sleep_duration_min']['value'] == 30 and not f['sleep_duration_min']['eligible']
    # Si no hubo consulta (permiso o teléfono apagado) en la pausa, queda parcial.
    f = sleep_features(spans, [(t(0, 0, 1), t(0, 30))], '2026-03-02', 'UTC', t(13))
    assert f['sleep_duration_min']['state'] == 'partial'
    # Día no cerrado todavía.
    assert sleep_features(spans, windows, '2026-03-02', 'UTC', t(10))['wake_min']['state'] == 'missing'


def test_screen_day_includes_sleep_features():
    from app.features import build_day
    ev = []
    for i, (on, off) in enumerate([('2026-03-01T22:00:00Z', '2026-03-01T23:30:00Z'), ('2026-03-02T06:30:00Z', '2026-03-02T07:00:00Z')]):
        ev += [{'id': f'a{i}', 'occurred_at': on, 'event_type': 'SCREEN_INTERACTIVE'}, {'id': f'b{i}', 'occurred_at': off, 'event_type': 'SCREEN_NON_INTERACTIVE'}]
    cap = [{'id': 'c', 'start_at': '2026-03-01T00:00:00Z', 'end_at': '2026-03-03T00:00:00Z', 'detail': {'success': True, 'permission_before': True, 'permission_after': True}}]
    day = build_day(ev, cap, '2026-03-02', 'UTC', cutoff='2026-03-03T01:00:00Z')
    assert day['features']['sleep_duration_min']['value'] == 420
    assert day['features']['sleep_duration_min']['state'] == 'observed'


def test_history_features_and_person_level_validation():
    from ml.school_pipeline import history_values, cross_validate, screening, HISTORY
    assert HISTORY == ['previous_phq9_total', 'days_since_previous']
    assert history_values(None, None, '2026-03-01T00:00:00Z') == [None, None]
    assert history_values(12, '2026-02-15T00:00:00Z', '2026-03-01T00:00:00Z') == [12, 14.0]
    rng = np.random.default_rng(1)
    rows = []
    for person in range(8):
        level = rng.integers(0, 20)
        prev = None
        for k in range(4):
            y = int(np.clip(level + rng.integers(-2, 3), 0, 27))
            rows.append({'x': [float(level), None, None, None, 1] + history_values(prev, '2026-01-01T00:00:00Z', '2026-01-15T00:00:00Z'),
                         'y': y, 'participant_id': f'p{person}', 'previous': prev})
            prev = y
    out = cross_validate(rows, 3)
    assert out['status'] == 'completed' and out['method'] == 'LeaveOneGroupOut' and out['participants'] == 8
    assert set(out['metrics']) == {'xgboost', 'last_questionnaire', 'constant'}
    s = screening([5, 12, 15, 2], [4, 13, 9, 1])
    assert s['positives'] == 2 and s['sensitivity'] == .5 and s['specificity'] == 1.0


def test_behavior_change_is_information_unless_enabled(client):
    from app.features import behavior_alerts
    from app.config import MODE
    c = client
    inv, cfg = setup(c)
    from app.db import SessionLocal
    with SessionLocal() as db:
        expected = MODE != 'REAL'
        assert behavior_alerts(db, inv['student']['participant_id']) is expected
