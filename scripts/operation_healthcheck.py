"""Reproducible health / monitoring probe for the REAL school product (A10).

Distinguishes three components without exposing personal data or secrets:

* ``database`` - reachability, ``SELECT 1`` latency, replica/recovery flag,
  open-connection count (a number, never row contents).
* ``api``     - HTTP ``GET {API}/health`` returns 200 with ``status=ok``; reports
  only ``mode`` and ``version``.
* ``worker``  - liveness *by effect* from the jobs table: ``ok`` only with a
  ``running`` job whose lease is still in the future (proof the worker renewed it);
  ``degraded`` with an expired lease (crashed mid-job) or a queue older than
  ``--worker-stale-minutes`` (not consuming); ``unknown`` when there is no work at
  all — absence of jobs is not health. Counts by state only, no payloads.
  In ``--target compose`` the container check only proves a process is present,
  not that it consumes the queue; that limit is stated in the output.

Targets:
  --target direct  (default)  uses env: MONITOR_API_URL, MONITOR_DATABASE_URL
                              (falls back to DATABASE_URL). Good for local product
                              and for tests.
  --target compose --compose-file FILE   parses ``docker compose ps`` into a
                              per-service verdict (running + health). Combine with
                              a ``--target direct`` run for deep DB/worker checks.

Output: single JSON object on stdout. Exit 0 ok / 1 degraded-or-unknown /
2 down-or-error. Never prints DSNs, passwords or tokens; error text is redacted.
"""
from __future__ import annotations
import argparse,json,os,re,subprocess,sys,time,urllib.request
from datetime import datetime,timezone

_SECRET=re.compile(
    r'(postgres(?:ql)?://[^\s"\']+'
    r'|password=[^\s"\';]+'
    r'|(?:authorization|cookie)[=:].*'
    r'|(?:secret|token|api[_-]?key)[=:]\s*\S+'
    r'|bearer\s+\S+)',
    re.I,
)


def redact(text:str)->str:
    return _SECRET.sub('[redacted]',str(text))


def _now(clock=None)->datetime:
    return clock() if clock else datetime.now(timezone.utc)


# ---- pure evaluators (unit-tested without IO) ---------------------------------

def evaluate_api(status_code:int|None,body:dict|None,error:str|None=None)->dict:
    if error or status_code is None:
        return {'status':'down','detail':redact(error or 'sin respuesta')}
    if status_code!=200:
        return {'status':'down','detail':f'HTTP {status_code}'}
    if not body or body.get('status')!='ok':
        return {'status':'degraded','detail':'respuesta sin status=ok'}
    return {'status':'ok','mode':body.get('mode'),'version':body.get('version')}


def evaluate_database(ok:bool,latency_ms:float|None,in_recovery:bool|None,connections:int|None,error:str|None=None)->dict:
    if not ok:
        return {'status':'down','detail':redact(error or 'sin conexión')}
    out={'status':'ok','latency_ms':latency_ms,'in_recovery':bool(in_recovery),'connections':connections}
    if latency_ms is not None and latency_ms>1000:
        out['status']='degraded';out['detail']='latencia > 1000 ms'
    return out


def evaluate_worker(jobs:list[dict],now:datetime,stale_minutes:int)->dict:
    """Liveness *by effect* from the ``jobs`` table.

    ``jobs`` items: {state, lease_until(datetime|None), created_at(datetime)}.

    Positive proof of life = a ``running`` job holding a lease that is still in the
    future (the worker renewed it within the last lease window). Absence of work
    is NOT health: with no running/queued job we cannot tell the worker apart from
    a dead one, so the verdict is ``unknown`` (never ``ok``).
    """
    by_state:dict[str,int]={}
    crashed=0;stalled=0;alive=0
    for j in jobs:
        st=j.get('state','?');by_state[st]=by_state.get(st,0)+1
        lease=j.get('lease_until');created=j.get('created_at')
        if st=='running' and lease is not None:
            crashed+=1 if lease<now else 0
            alive+=1 if lease>=now else 0
        if st=='queued' and created is not None and (now-created).total_seconds()>stale_minutes*60:
            stalled+=1
    out={'jobs_by_state':by_state,'expired_leases':crashed,'stale_queued':stalled}
    if crashed:
        out['status']='degraded';out['detail']=f'{crashed} job(s) running con lease vencido: el worker pudo caer a mitad'
    elif stalled:
        out['status']='degraded';out['detail']=f'{stalled} job(s) en cola > {stale_minutes} min sin tomar: el worker no consume'
    elif alive:
        out['status']='ok';out['detail']=f'{alive} job(s) en curso con lease vigente: worker activo'
    else:
        out['status']='unknown';out['detail']=('sin trabajo en curso ni en cola: no se puede confirmar el worker por efecto; '
                                               'combine con el healthcheck del contenedor o encole un job de prueba')
    return out


def overall(components:dict)->str:
    values={c['status'] for c in components.values()}
    for level in ('down','degraded','unknown'):
        if level in values:return level
    return 'ok'


# ---- IO probes --------------------------------------------------------------

def probe_api(url:str,ca_cert:str|None,timeout:float)->dict:
    ctx=None
    if url.startswith('https'):
        import ssl
        ctx=ssl.create_default_context(cafile=ca_cert) if ca_cert else ssl.create_default_context()
    try:
        with urllib.request.urlopen(url,timeout=timeout,context=ctx) as r:
            return evaluate_api(r.status,json.loads(r.read().decode() or '{}'))
    except Exception as exc:  # noqa: BLE001 - report, never leak
        return evaluate_api(None,None,error=f'{type(exc).__name__}: {exc}')


def _connect(dsn:str,timeout:float):
    import psycopg
    return psycopg.connect(dsn,connect_timeout=int(max(1,timeout)))


def probe_database(dsn:str,timeout:float)->dict:
    try:
        t=time.monotonic()
        with _connect(dsn,timeout) as conn,conn.cursor() as cur:
            cur.execute('SELECT 1');cur.fetchone()
            latency=round((time.monotonic()-t)*1000,1)
            cur.execute('SELECT pg_is_in_recovery()');rec=cur.fetchone()[0]
            cur.execute('SELECT count(*) FROM pg_stat_activity');conns=int(cur.fetchone()[0])
        return evaluate_database(True,latency,rec,conns)
    except Exception as exc:  # noqa: BLE001
        return evaluate_database(False,None,None,None,error=f'{type(exc).__name__}: {exc}')


def probe_worker(dsn:str,timeout:float,stale_minutes:int,clock=None)->dict:
    try:
        with _connect(dsn,timeout) as conn,conn.cursor() as cur:
            cur.execute('SELECT state, lease_until, created_at FROM jobs')
            jobs=[{'state':s,'lease_until':l,'created_at':c} for s,l,c in cur.fetchall()]
        return evaluate_worker(jobs,_now(clock),stale_minutes)
    except Exception as exc:  # noqa: BLE001
        return {'status':'down','detail':redact(f'{type(exc).__name__}: {exc}')}


# ---- compose target --------------------------------------------------------

def compose_ps(compose_file:str,env_file:str|None)->list[dict]:
    cmd=['docker','compose','-f',compose_file]
    if env_file:cmd+=['--env-file',env_file]
    cmd+=['ps','--format','json']
    res=subprocess.run(cmd,capture_output=True,text=True,check=True)
    rows=[]
    out=res.stdout.strip()
    if out.startswith('['):
        rows=json.loads(out)
    else:
        rows=[json.loads(line) for line in out.splitlines() if line.strip()]
    return rows


def evaluate_compose(rows:list[dict])->dict:
    want={'db':'database','api':'api','worker':'worker','web':'web','proxy':'proxy'}
    seen={r.get('Service'):r for r in rows}
    comps={}
    for svc,label in want.items():
        r=seen.get(svc)
        if not r:
            comps[label]={'status':'down','detail':'contenedor ausente'};continue
        state=(r.get('State') or '').lower()
        health=(r.get('Health') or '').lower()
        if state!='running':
            comps[label]={'status':'down','detail':f'estado {state or "?"}'}
        elif health in ('unhealthy','starting'):
            comps[label]={'status':'degraded','detail':f'health {health}'}
        else:
            comps[label]={'status':'ok','detail':f'running{"/"+health if health else ""}'}
    # A container being up proves a process, not that the worker consumes the
    # queue. Keep the verdict but state the limit; use --target direct to prove
    # consumption by effect (evaluate_worker).
    if comps.get('worker',{}).get('status')=='ok':
        comps['worker']['detail']+=' · sólo presencia de proceso, no prueba consumo de la cola'
    return comps


# ---- CLI ------------------------------------------------------------------

def build_parser()->argparse.ArgumentParser:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--target',choices=['direct','compose'],default='direct')
    p.add_argument('--compose-file')
    p.add_argument('--env-file')
    p.add_argument('--api-url',default=os.getenv('MONITOR_API_URL'))
    p.add_argument('--database-url',default=os.getenv('MONITOR_DATABASE_URL') or os.getenv('DATABASE_URL'))
    p.add_argument('--ca-cert',default=os.getenv('MONITOR_CA_CERT'))
    p.add_argument('--timeout',type=float,default=5.0)
    p.add_argument('--worker-stale-minutes',type=int,default=15)
    return p


def run(argv:list[str]|None=None)->int:
    a=build_parser().parse_args(argv)
    components:dict={}
    if a.target=='compose':
        if not a.compose_file:raise SystemExit('--target compose requiere --compose-file')
        try:
            components=evaluate_compose(compose_ps(a.compose_file,a.env_file))
        except (subprocess.CalledProcessError,FileNotFoundError) as exc:
            print(json.dumps({'generated_at':_now().isoformat(),'target':'compose','overall':'down','error':redact(f'{type(exc).__name__}: {exc}')}))
            return 2
    else:
        if not a.api_url or not a.database_url:
            raise SystemExit('--target direct requiere --api-url y --database-url (o env MONITOR_*)')
        components['database']=probe_database(a.database_url,a.timeout)
        components['worker']=probe_worker(a.database_url,a.timeout,a.worker_stale_minutes)
        components['api']=probe_api(a.api_url,a.ca_cert,a.timeout)
    result={'generated_at':_now().isoformat(),'target':a.target,'overall':overall(components),'components':components}
    print(json.dumps(result,indent=2,default=str))
    return {'ok':0,'unknown':1,'degraded':1,'down':2}[result['overall']]


if __name__=='__main__':
    sys.exit(run())
