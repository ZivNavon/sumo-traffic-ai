"""Real-agent checks without starting SUMO; freeze reviewed files for runtime gates."""
import sys,json,subprocess,ast,hashlib,random
from pathlib import Path
from worker import read_json as read,write_json as write,sha
ROOT=Path(__file__).resolve().parent;RUN=ROOT/'campaign'
def probe(variant):
    import worker,variants
    worker.initialize(RUN)
    td=worker.td;torch=worker.torch;np=worker.np
    random.seed(73021);np.random.seed(73021);torch.manual_seed(73021)
    variants.install(dict(algorithm='dqn',variant=variant),td,worker.ta,worker.ai,worker.ac,torch,np)
    agent=td.DQNAgent();params=hashlib.sha256(b''.join(p.detach().numpy().tobytes() for p in agent.online.parameters())).hexdigest()
    settings=dict(LR=agent.optimizer.param_groups[0]['lr'],EPS_DECAY=td.EPS_DECAY,EPS_START=td.EPS_START,EPS_END=td.EPS_END,GAMMA=td.GAMMA,BUFFER_SIZE=td.BUFFER_SIZE,BATCH_SIZE=td.BATCH_SIZE,TARGET_UPDATE=td.TARGET_UPDATE,TRAIN_START=td.TRAIN_START,STOP_PENALTY=td.STOP_PENALTY,actions=td.ACTIONS,parameters=params)
    print(json.dumps(settings))
def main():
    assert not (ROOT/'clock.json').exists(),'Preflight cannot silently change a running campaign'
    for f in ROOT.glob('*.py'):ast.parse(f.read_text(encoding='utf-8'),filename=str(f))
    p=read(RUN/'protocol.json');checks={}
    for variant in ['current','lr0003','eps998']:
        result=subprocess.run([sys.executable,str(__file__),'--probe',variant],capture_output=True,text=True,check=True)
        checks[variant]=json.loads(result.stdout.strip().splitlines()[-1])
    baseline=checks['current']
    for variant,key,value in [('lr0003','LR',.0003),('eps998','EPS_DECAY',.998)]:
        changed={k for k in baseline if baseline[k]!=checks[variant][k]}
        assert changed=={key},(variant,changed)
        assert checks[variant][key]==value
    assert baseline['LR']==.001 and baseline['EPS_DECAY']==.997 and baseline['EPS_START']==1 and baseline['EPS_END']==.05
    assert baseline['actions']==[20,30,40,50,60]
    assert set(p['train_seeds']).isdisjoint(p['validation_seeds']) and set(p['validation_seeds']).isdisjoint(p['test_seeds'])
    assert len(p['test_seeds'])==20 and len(p['validation_seeds'])==10
    from runner import choose,resources
    assert choose([dict(episode=1000,mean_wait=2),dict(episode=500,mean_wait=2)],'episode')['episode']==500
    assert choose([dict(duration=60,mean_wait=2),dict(duration=20,mean_wait=2)],'duration')['duration']==20
    for name,digest in read(ROOT/'copied-source-hashes.json').items():assert sha(ROOT/name)==digest
    assert len(read(RUN/'import-audit.json'))==3
    r=resources();assert r['free_fraction']>.2 and r['disk_free']>20*1024**3,r
    from unittest.mock import patch
    import guard
    with patch.object(guard,'deadline',return_value=0):assert guard.stopping('train')
    # A test task must not pass a closed test gate.
    with patch.object(guard,'deadline',return_value=10**20):
        try:guard.check(RUN,dict(kind='eval',split='test'))
        except FileNotFoundError:pass
        else:raise AssertionError('Closed test gate accepted')
    paths=list(ROOT.glob('*.py'))+[RUN/'protocol.json',RUN/'training-manifest.json',RUN/'import-audit.json',ROOT/'copied-source-hashes.json',ROOT/'historical-seed-audit.json']
    write(ROOT/'preflight.json',dict(status='passed',checks=checks,resources=r,hashes={str(f.relative_to(ROOT)):sha(f) for f in paths},tests=['single-factor real Adam/epsilon isolation','same initial network for matched learning seed','source identity','3 complete historical imports','fresh seed splits','tie order','deadline stop','closed test gate']))
    print(json.dumps(dict(status='passed',resources=r,probes=checks)))
if __name__=='__main__':
    if len(sys.argv)>1:probe(sys.argv[2])
    else:main()
