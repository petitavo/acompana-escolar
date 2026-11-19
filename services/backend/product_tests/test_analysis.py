from datetime import datetime,timezone,timedelta
from types import SimpleNamespace
import json, hashlib
import pytest
from app.mobility import day_summary,haversine
from app.phq9 import PHQ9,SOURCE_SHA256
from app.forms import score
from app.db import SessionLocal
from app.school_db import DatasetRecord,ModelRecord
from ml.school_pipeline import validate_dataset,windows,train_real,predict,CONTRACT
from conftest import login
from test_journeys import setup,post,A

def fixture_dataset():
    start=datetime(2025,1,1,tzinfo=timezone.utc)
    data={'manifest':{'name':'Fixture de contrato, nunca datos reales','provenance':'test_fixture','authorization_reference':'Únicamente pruebas automatizadas','instrument':PHQ9['instrument_id'],'instrument_version':PHQ9['version'],'recall_days':14,'task':'prospective','contract':CONTRACT,'units':{'observed_steps':'pasos'}},'days':[],'labels':[]}
    for p in range(6):
        for d in range(120):
            day=start+timedelta(days=d);end=day+timedelta(days=1)
            data['days'].append({'participant_id':f'fixture-{p}','day':day.date().isoformat(),'available_at':end.isoformat(),'window_end':end.isoformat(),'features':{'observed_steps':{'value':1000+p*100+d*3,'eligible':True}}})
        for d in (49,63,77,91,105,119):
            end=start+timedelta(days=d)
            data['labels'].append({'id':f'label-{p}-{d}','participant_id':f'fixture-{p}','score':(p+d)%20,'applied_at':end.isoformat(),'recall_end':end.isoformat(),'recall_start':(end-timedelta(days=14)).isoformat()})
    return data

def test_exact_instrument_scoring_and_source():
    from pathlib import Path
    assert hashlib.sha256(Path('docs/instrumentos/PHQ-9_Spanish_AETC.pdf').read_bytes()).hexdigest()==SOURCE_SHA256
    assert score(PHQ9,{f'q{i}':3 for i in range(1,10)})[0]==27
    total,review,rules=score(PHQ9,{f'q{i}':int(i==9) for i in range(1,10)})
    assert total==1 and 'safety_review' in rules

def test_mobility_observed_quality_midnight_and_counter():
    base=datetime(2025,1,2,tzinfo=timezone.utc)
    def point(i,lat=0,lon=0,**kw):
        return {'id':str(i),'kind':'location','occurred_at':(base+timedelta(minutes=i)).isoformat(),'latitude':lat,'longitude':lon,'accuracy_m':10,'permission':'precise',**kw}
    rows=[point(-15),point(15),point(30,lon=.001),point(100,lon=.002),point(115,accuracy_m=101),point(130,permission='approximate')]
    result=day_summary(rows,'2025-01-02','UTC',{'latitude':0,'longitude':0})
    f=result['features'];q=result['quality']
    assert f['observed_distance_m']['value']==pytest.approx(haversine((0,0),(0,.001)),abs=.0001)
    assert q['observed_minutes']==30 and q['gap_count']==1 and q['excluded_count']==2
    assert q['inside_minutes']+q['outside_minutes']+q['uncertain_minutes']==1440
    assert not f['home_minutes']['eligible']
    assert day_summary([],'2025-01-02','UTC')['features']['observed_steps']['value'] is None
    rows=[{'id':str(i),'kind':'steps','occurred_at':(base+timedelta(minutes=i*15)).isoformat(),'counter':v,'boot_id':b} for i,(v,b) in enumerate([(100,'a'),(150,'a'),(3,'b'),(10,'b')])]
    result=day_summary(rows,'2025-01-02','UTC')
    assert result['features']['observed_steps']['value']==57
    assert result['quality']['step_resets']==1
    assert haversine((0,179.999),(0,-179.999))<225

def test_prospective_window_never_reads_recall_or_future():
    d=fixture_dataset();rows,names=windows(d);before=rows[0]['x']
    cutoff=rows[0]['cutoff']
    for day in d['days']:
        if day['window_end']>cutoff:day['features']['observed_steps']['value']=999999
    assert windows(d)[0][0]['x']==before
    d['days'][0]['features']['gps']={'value':1,'eligible':True}
    with pytest.raises(ValueError):validate_dataset(d)

def test_train_comparators_reproducible_shap_and_fixture_not_active(client):
    c=client;setup(c);data=fixture_dataset()
    imported=post(c,'/models/datasets',data)
    queued=post(c,f'/models/datasets/{imported["id"]}/train')
    with SessionLocal.begin() as db:
        result=train_real(db,SimpleNamespace(payload=queued['payload']))
    with SessionLocal.begin() as db:
        model=db.get(ModelRecord,result['model_id'])
        values=windows(data)[0][0]['x']
        first=predict(model,values);assert first==predict(model,values)
        assert abs(first['shap']['base']+sum(first['shap']['contributions'].values())-first['raw_estimate'])<.001
        assert {'constant','last_questionnaire','ridge','xgboost','levels_only'}<=set(model.metrics)
        # A06: the recorded evaluation is bound to the exact artifact hash.
        assert model.metrics['artifact_sha256']==model.manifest['artifact_sha256']
        t=model.manifest['temporal']
        assert t['status'] in ('completed','insufficient_time_periods')
        if t['status']=='completed':
            assert t['artifact_sha256'] not in (None, model.manifest['artifact_sha256'])
        partitions=model.manifest['partitions']
        assert not set(partitions['train'])&set(partitions['test'])
    post(c,f'/models/{result["model_id"]}/decision',{'state':'shadow','rationale':'Prueba de ejecución sin activación'})
    login(c,'psicologo')
    post(c,f'/models/{result["model_id"]}/decision',{'state':'active','rationale':'Prueba negativa: un fixture no se activa'},code=409)

def test_shared_android_contract_fixtures():
    from pathlib import Path
    for c in json.loads(Path('packages/contracts/fixtures/mobility-v1.json').read_text()):
        actual=day_summary(c['samples'],c['day'],c['zone'],c.get('home'),school=c.get('school'))
        assert actual['features']==c['expected']['features'],c['name']
        assert actual['quality']==c['expected']['quality'],c['name']

def test_pause_segment_never_bridges_location_or_step_counter():
    samples=[]
    for i,segment in enumerate(('before','after')):
        samples.append({'id':str(i),'kind':'location','occurred_at':f'2025-01-02T00:{i*15:02}:00Z','segment_id':segment,'latitude':0,'longitude':i*.001,'accuracy_m':10,'permission':'precise'})
        samples.append({'id':'step'+str(i),'kind':'steps','occurred_at':f'2025-01-02T00:{i*15:02}:00Z','segment_id':segment,'counter':100+i*400,'boot_id':'same-boot'})
    result=day_summary(samples,'2025-01-02','UTC')
    assert result['features']['observed_steps']['value'] is None
    assert result['features']['observed_distance_m']['value'] is None
