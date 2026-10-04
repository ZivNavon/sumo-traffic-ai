"""Infrastructure gates; no learning or traffic control decisions."""
import time
from pathlib import Path
from worker import read_json,sha
ROOT=Path(__file__).resolve().parent
def deadline(kind):
    p=ROOT/'clock.json'
    if not p.exists():raise RuntimeError('Campaign clock missing')
    c=read_json(p)
    return c['training_deadline'] if kind=='train' else c['simulation_deadline']
def stopping(kind):return (ROOT/'STOP').exists() or time.time()>=deadline(kind)-180
def check(run,task):
    assert time.time()<deadline(task['kind'])-180,'Deadline prevents launch'
    if task.get('split')=='test':
        g=read_json(run/'test-gate.json')
        for name,digest in g['hashes'].items():assert sha(run/name)==digest,f'Frozen test gate changed: {name}'
        tasks=read_json(run/'test-manifest.json')
        assert task in tasks,'Test task not in frozen manifest'
    if task['kind']=='eval' and task.get('split')!='smoke':
        records=read_json(run/'demand-manifest.json')
        record=next(x for x in records if x['seed']==task['seed'] and x['load']==task['load'] and x['scenario']=='day_cycle')
        for f in record['files']:assert sha(run/f['path'])==f['sha256'],'Frozen demand file changed'
    for name,digest in read_json(ROOT/'preflight.json')['hashes'].items():assert sha(ROOT/name)==digest,f'Preflight changed: {name}'
