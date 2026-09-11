import uuid
from datetime import datetime, timezone, timedelta
from conftest import login
A='/api/v1/school'
def post(c,path,body=None,key=None,code=200):
    r=c.post(A+path,json=body,headers={'Idempotency-Key':key or str(uuid.uuid4())})
    assert r.status_code==code,r.text
    return r.json()
def setup(c,minor=True):
    login(c)
    post(c,'/setup',{'name':'Institución de prueba'})
    people={name:post(c,'/accounts',{'username':name,'password':'test-password-123','role':role})['id'] for name,role in [('psicologo','psychologist'),('suplente','psychologist'),('direccion','director')]}
    classroom=post(c,'/classrooms',{'name':'A','grade':'Quinto','period':'2026'})
    cfg=c.get(A+'/settings').json()
    allowed={'document_version','participation_document','purpose','primary_id','backup_id','coverage','days','opens','closes','acknowledgement_minutes','safety_minutes','escalation_minutes','resources','instrument_enabled','professional_decision','cadence_days','minimum_group','external_notifications_authorized','raw_location_retention_days','location_interval_minutes','location_distance_meters'}
    cfg={k:v for k,v in cfg.items() if k in allowed}
    cfg.update(coverage='Prueba: lunes a viernes de 08:00 a 17:00; sin atención real.',purpose='Prueba funcional con identidades ficticias, sin decisión clínica.',participation_document='Documento ficticio exclusivo para pruebas automatizadas de incorporación y autorización.',primary_id=people['psicologo'],backup_id=people['suplente'],instrument_enabled=True,professional_decision='Configuración ficticia para pruebas automatizadas.',resources=[{'title':'Recurso ficticio','contact':'No usar fuera de pruebas','verified_by':'Prueba automatizada','verified_at':datetime.now(timezone.utc).isoformat()}])
    r=c.put(A+'/settings',json=cfg);assert r.status_code==200,r.text
    invitation=post(c,'/students',{'display_name':'Estudiante ficticio','classroom_id':classroom['id'],'psychologist_id':people['psicologo'],'minor':minor,'is_test':True,'guardian_channel':'Canal ficticio'})
    return invitation,cfg

def enroll(c,inv):
    return post(c,'/enroll',{'invitation':inv['invitation']['token'],'verification_code':inv['invitation']['verification_code'],'device':{'android_api':35,'manufacturer':'Fixture','model':'Test','app_version':'test','timezone':'America/Lima'}})

def authorize(c,inv,cfg):
    if inv['guardian']:
        g=inv['guardian'];post(c,'/guardian/approve',{'token':g['token'],'verification_code':g['verification_code'],'full_name':'Responsable ficticio','relationship':'Responsable','identity_reference':'Referencia ficticia','document_version':cfg['document_version'],'accepted':True})
    post(c,'/me/participation',{'action':'assent' if inv['guardian'] else 'consent','document_version':cfg['document_version'],'occurred_at':datetime.now(timezone.utc).isoformat()})

def test_complete_minor_safety_contact_followup_and_roles(client):
    c=client;inv,cfg=setup(c);phone=enroll(c,inv)
    c.headers['authorization']='Bearer '+phone['token']
    assert c.get(A+'/me/questionnaires').json()==[]
    support=post(c,'/me/support',key='support')
    assert post(c,'/me/support',key='support')==support
    authorize(c,inv,cfg)
    forms=c.get(A+'/me/questionnaires').json();assert len(forms)==1
    at=datetime.now(timezone.utc)
    body={'instrument_code':forms[0]['instrument_id'],'instrument_version':forms[0]['version'],'answers':{f'q{i}':int(i==9) for i in range(1,10)},'functioning':0,'applied_at':at.isoformat(),'recall_end':at.isoformat(),'recall_start':(at-timedelta(days=14)).isoformat()}
    response=post(c,'/me/questionnaires',body,key='phq')
    assert 'total' not in response
    assert post(c,'/me/questionnaires',body,key='phq')==response
    post(c,'/me/questionnaires',body,code=409)
    assert c.get(A+'/me/questionnaires').json()==[]
    login(c,'psicologo')
    cases=c.get(A+'/cases');assert cases.status_code==200,cases.text
    rows=cases.json();assert len(rows)==1
    assert any(r['kind']=='safety_review' for r in rows[0]['reasons'])
    appointment=post(c,'/followups',{'case_id':rows[0]['id'],'kind':'appointment','title':'Entrevista privada de prueba','due_at':(at+timedelta(days=1)).isoformat(),'location':'Orientación'})
    assert c.get(A+'/notifications').json()
    profile_id=inv['student']['participant_id']
    assert c.get(A+f'/students/{profile_id}/profile').status_code==200
    login(c,'direccion')
    assert c.get(A+f'/students/{profile_id}/profile').status_code in (403,404)
    assert c.get(A+'/cases').status_code==403
    c.headers['authorization']='Bearer '+phone['token']
    requests=c.get(A+'/me/requests');assert requests.status_code==200,requests.text
    assert 'Entrevista privada' not in requests.text
    post(c,f'/me/appointments/{appointment["id"]}/confirm')

def test_verification_single_use_and_guardian_required(client):
    c=client;inv,cfg=setup(c);phone=enroll(c,inv)
    c.headers['authorization']='Bearer '+phone['token']
    post(c,'/me/participation',{'action':'assent','document_version':cfg['document_version'],'occurred_at':datetime.now(timezone.utc).isoformat()},code=409)
    r=c.post(A+'/enroll',json={'invitation':inv['invitation']['token'],'verification_code':inv['invitation']['verification_code'],'device':{'android_api':35,'manufacturer':'Fixture','model':'Test','app_version':'test','timezone':'America/Lima'}})
    assert r.status_code==401

def test_withdraw_stops_session_and_queues_deletion(client):
    c=client;inv,cfg=setup(c,False);phone=enroll(c,inv);c.headers['authorization']='Bearer '+phone['token'];authorize(c,inv,cfg)
    post(c,'/me/participation',{'action':'withdraw','document_version':cfg['document_version'],'occurred_at':datetime.now(timezone.utc).isoformat()})
    assert c.get(A+'/me').status_code==401


def test_changing_preferences_does_not_resume_paused_participation(client):
    c=client
    inv,cfg=setup(c,False)
    phone=enroll(c,inv)
    c.headers['authorization']='Bearer '+phone['token']
    authorize(c,inv,cfg)
    body={'action':'pause','document_version':cfg['document_version'],'occurred_at':datetime.now(timezone.utc).isoformat()}
    assert post(c,'/me/participation',body)['capture_active'] is False
    body.update(action='preferences',usage=True,location=True)
    saved=post(c,'/me/participation',body)
    assert saved['capture_active'] is False
    assert c.get(A+'/me').json()['capture_active'] is False
    body['action']='resume'
    assert post(c,'/me/participation',body)['capture_active'] is True
