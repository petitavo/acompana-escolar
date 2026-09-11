from datetime import datetime,timezone,timedelta
import uuid
from sqlalchemy import select
from app.db import SessionLocal,User,Participant,Idempotency,now
from app.school_db import Notification,Institution,StudentProfile,PushToken,Membership
from app.security import hasher
from app.notifications import maintain_notifications,dispatch
from worker.main import erase
from conftest import login
from test_journeys import setup,enroll,authorize,post,A

def test_revoke_gps_support_still_works_and_no_raw_export(client):
    c=client;inv,cfg=setup(c,False);phone=enroll(c,inv);c.headers['authorization']='Bearer '+phone['token'];authorize(c,inv,cfg)
    body={'action':'preferences','document_version':cfg['document_version'],'occurred_at':now().isoformat(),'location':True,'raw_location_upload':False}
    post(c,'/me/participation',body)
    point={'id':str(uuid.uuid4()),'kind':'location','occurred_at':now().isoformat(),'timezone':'America/Lima','utc_offset_minutes':-300,'latitude':-12,'longitude':-77,'accuracy_m':10,'provider':'fixture','permission':'precise'}
    result=post(c,'/me/sensors',{'points':[point]});assert result['rejected'][0]['reason']=='raw_location_upload_disabled'
    body.update(raw_location_upload=True,occurred_at=now().isoformat());post(c,'/me/participation',body)
    result=post(c,'/me/sensors',{'points':[point]});assert result['accepted']==[point['id']]
    assert post(c,'/me/sensors',{'points':[point]})['duplicates']==[point['id']]
    body.update(location=False,raw_location_upload=False,occurred_at=now().isoformat());post(c,'/me/participation',body)
    point['id']=str(uuid.uuid4());assert post(c,'/me/sensors',{'points':[point]})['rejected']
    assert post(c,'/me/support')['received']
    assert c.get(A+'/me/questionnaires').json()
    login(c)
    assert c.get(A+f'/diagnostics/{phone["device_id"]}?kind=location').status_code==403
    assert c.get('/api/v1/lab/events').status_code==404

def test_assignments_supervision_tenant_report_and_deletion(client):
    c=client;inv,cfg=setup(c,False);pid=inv['student']['participant_id']
    practitioner=post(c,'/accounts',{'username':'practicante','role':'practitioner','password':'test-password-123','supervisor_id':cfg['primary_id']})
    researcher=post(c,'/accounts',{'username':'investigador','role':'researcher','password':'test-password-123','scopes':['models','diagnostics']})
    login(c,'practicante');assert c.get(A+f'/students/{pid}/profile').status_code==404
    login(c);post(c,f'/students/{pid}/assign/{practitioner["id"]}')
    login(c,'practicante');assert c.get(A+f'/students/{pid}/profile').status_code==200
    login(c,'investigador');assert c.get(A+f'/students/{pid}/report?start=2026-01-01T00:00:00Z&end=2026-10-01T00:00:00Z').status_code==403
    with SessionLocal.begin() as db:
        db.add(User(username='another-admin',role='admin',password_hash=hasher.hash('test-password-123')))
    login(c,'another-admin');post(c,'/setup',{'name':'Otra institución'})
    assert c.get(A+f'/students/{pid}/authorizations').status_code==404
    login(c);post(c,f'/accounts/{cfg["primary_id"]}/disable')
    login(c,'practicante');assert c.get(A+f'/students/{pid}/profile').status_code==403
    with SessionLocal.begin() as db:erase(db,pid,'test')
    with SessionLocal.begin() as db:
        assert db.get(Participant,pid) is None
        assert not any(pid in str(r.result) for r in db.scalars(select(Idempotency)))

def test_escalation_idempotent_ack_and_delivery_not_faked(client,monkeypatch,tmp_path):
    c=client;inv,cfg=setup(c,False);phone=enroll(c,inv);c.headers['authorization']='Bearer '+phone['token'];post(c,'/me/support')
    with SessionLocal.begin() as db:
        notification=db.scalar(select(Notification).where(Notification.kind=='case'));nid=notification.id
        first=now()+timedelta(days=2)
        maintain_notifications(db,first);maintain_notifications(db,first)
        escalations=list(db.scalars(select(Notification).where(Notification.kind=='escalation')));assert len(escalations)==1
        maintain_notifications(db,first+timedelta(minutes=cfg['escalation_minutes']+1))
        assert len(list(db.scalars(select(Notification).where(Notification.kind=='escalation'))))==2
        assert notification.state=='created'
        i=db.scalar(select(Institution));i.settings={**i.settings,'external_notifications_authorized':True}
        db.add(PushToken(owner_id=notification.recipient_id,token_hash='fixture-token-hash',token='fake-token'))
    credentials=tmp_path/'credentials.json';credentials.write_text('{}')
    monkeypatch.setenv('FCM_SERVICE_ACCOUNT',str(credentials));monkeypatch.setenv('ALLOW_EXTERNAL_NOTIFICATIONS','true')
    monkeypatch.setattr('app.notifications.send_push',lambda *args:'fake-provider-acceptance')
    with SessionLocal.begin() as db:
        dispatch(db);assert db.get(Notification,nid).state=='sent'
    login(c,'suplente');post(c,f'/notifications/{nid}/delivered',code=404)
    login(c,'psicologo');post(c,f'/notifications/{nid}/delivered')
    assert next(n for n in c.get(A+'/notifications').json() if n['id']==nid)['state']=='delivered'
    post(c,f'/notifications/{nid}/ack')
    assert next(n for n in c.get(A+'/notifications').json() if n['id']==nid)['state']=='acknowledged'

def test_access_recovery_and_export_permission_are_separate(client):
    c=client;inv,cfg=setup(c,False);phone=enroll(c,inv);pid=inv['student']['participant_id']
    login(c)
    renewed=post(c,f'/students/{pid}/access-link')
    c.headers['authorization']='Bearer '+phone['token'];assert c.get(A+'/me').status_code==401
    new_phone=enroll(c,renewed);c.headers['authorization']='Bearer '+new_phone['token'];assert c.get(A+'/me').status_code==200
    login(c)
    assert c.get(A+f'/diagnostics/{new_phone["device_id"]}/export').status_code==403
    with SessionLocal.begin() as db:
        u=db.scalar(select(User).where(User.username=='admin'));u.scopes=[*u.scopes,'raw_export']
    assert c.get(A+f'/diagnostics/{new_phone["device_id"]}/export?kind=usage').status_code==200
    assert c.get(A+f'/diagnostics/{new_phone["device_id"]}/export?kind=location').status_code==422
    assert c.get(A+f'/diagnostics/{new_phone["device_id"]}?start=invalid').status_code==422
    post(c,f'/accounts/{cfg["backup_id"]}/password',{'password':'replacement-password-123'})
    r=c.post('/api/v1/auth/login',json={'username':'suplente','password':'test-password-123'});assert r.status_code==401
    r=c.post('/api/v1/auth/login',json={'username':'suplente','password':'replacement-password-123'});assert r.status_code==200
