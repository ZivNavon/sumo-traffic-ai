"""Owned-process scheduler with memory reserve, explicit gates and a stop file."""
import os,sys,time,json,subprocess,ctypes,msvcrt,shutil,argparse,statistics
from pathlib import Path
from worker import read_json,write_json,sha
ROOT=Path(__file__).resolve().parent
for stream in (sys.stdout,sys.stderr):
    if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf-8',errors='backslashreplace')
os.environ['PYTHONIOENCODING']='utf-8'
class MEMORY(ctypes.Structure):
    _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(k,ctypes.c_ulonglong) for k in ['total','free','page_total','page_free','virtual_total','virtual_free','extended']]
def memory():
    m=MEMORY();m.length=ctypes.sizeof(m)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):raise ctypes.WinError()
    return dict(total=m.total,free=m.free,free_fraction=m.free/m.total)
def heartbeat_expired(started, updated, now):
    return now-max(started,updated)>3600
def run_queue(run,tasks,cap,label):
    active={};done=set();failed=set();start=time.time();minimum=1.;peak=0
    for task in tasks:
        path=run/'tasks'/f"{task['id']}.json"
        if not path.exists():write_json(path,task)
        if (run/'completed'/f"{task['id']}.json").exists():done.add(task['id'])
        if (run/'failed'/f"{task['id']}.json").exists():failed.add(task['id'])
    while len(done|failed)<len(tasks):
        try:
            for key,(proc,log,task) in list(active.items()):
                code=proc.poll()
                if code is None:
                    progress=run/('training' if task['kind']=='train' else 'evaluations')/key/'progress.json'
                    if progress.exists() and heartbeat_expired(proc._campaign_started,read_json(progress).get('updated_at',time.time()),time.time()):
                        subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],capture_output=True)
                        write_json(run/'failed'/f'{key}.json',dict(status='failed',reason='Owned worker heartbeat exceeded one hour'))
                    continue
                log.close();del active[key]
                if code==75 and (ROOT/'STOP').exists():continue
                if code==0 and (run/'completed'/f'{key}.json').exists():done.add(key)
                else:
                    failed.add(key)
                    if not (run/'failed'/f'{key}.json').exists():write_json(run/'failed'/f'{key}.json',dict(exit_code=code,status='failed'))
            mem=memory();minimum=min(minimum,mem['free_fraction']);peak=max(peak,len(active))
            stop=(ROOT/'STOP').exists()
            free_disk=shutil.disk_usage(ROOT).free
            # Reserve 0.75 GiB for each newly launched Python+SUMO process pair.
            allowed=mem['free']-mem['total']*.20 > .75*1024**3 and free_disk>20*1024**3
            pending=[t for t in tasks if t['id'] not in done|failed and t['id'] not in active]
            for task in pending:
                if task.get('depends_on_train') in failed:
                    failed.add(task['id']);write_json(run/'failed'/f"{task['id']}.json",dict(status='blocked',dependency=task['depends_on_train']))
            pending=[t for t in pending if t['id'] not in failed and (not t.get('weights') or ((run/t['weights']).is_file() and (run/t['weights']).with_suffix('.json').is_file()))]
            if pending and len(active)<cap and allowed and not stop:
                task=pending[0];key=task['id'];(run/'logs').mkdir(exist_ok=True)
                log=(run/'logs'/f'{key}.log').open('ab')
                worker='worker.py' if task['kind']=='train' else 'evaluator.py'
                proc=subprocess.Popen([sys.executable,str(ROOT/worker),str(run),key],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
                proc._campaign_started=time.time()
                active[key]=(proc,log,task)
                # Stagger starts to measure actual memory before admitting another.
            state=dict(stage=label,pid=os.getpid(),updated_at=time.time(),capacity=cap,active=[dict(id=k,pid=v[0].pid) for k,v in active.items()],passed=len(done),failed=len(failed),pending=len(tasks)-len(done|failed)-len(active),memory=mem,free_disk=free_disk,stop_requested=stop)
            write_json(run/'status.json',state)
            if stop and not active:break
            time.sleep(2)
        except (PermissionError,FileNotFoundError):time.sleep(2)
    elapsed=time.time()-start
    steps=0;episodes=[]
    for task in tasks:
        for f in (run/'training'/task['id']/'episodes').glob('*.json'):
            row=read_json(f);steps+=row['simulation_steps'];episodes.append(row['wall_seconds'])
    result=dict(stage=label,elapsed_seconds=elapsed,simulation_steps=steps,steps_per_second=steps/elapsed,passed=len(done),failed=sorted(failed),min_free_memory_fraction=minimum,peak_workers=peak,mean_episode_seconds=statistics.mean(episodes) if episodes else None)
    write_json(run/'queue-result.json',result);return result
def prepare_child(name,tasks):
    run=ROOT/name;run.mkdir(exist_ok=True)
    p=read_json(ROOT/'campaign/protocol.json');write_json(run/'protocol.json',p)
    # Junction uses only new campaign snapshot; no historical folder is changed.
    snap=run/'snapshot'
    if not snap.exists():
        subprocess.run(['cmd','/c','mklink','/J',str(snap),str(ROOT/'campaign/snapshot')],check=True,capture_output=True)
    return run
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--start-authorized',action='store_true')
    args=parser.parse_args()
    if not args.start_authorized:
        print('Prepared only. No simulation or training started. Explicit start authorization is required.')
        return
    if (ROOT/'STOP').exists():raise RuntimeError('STOP file present. Remove it only when explicitly authorizing resume.')
    prepared=read_json(ROOT/'preflight.json')
    assert prepared['status']=='static_checks_passed'
    for name,digest in prepared['code_hashes'].items():assert sha(ROOT/name)==digest,f'Code changed after preparation: {name}'
    assert sha(ROOT/'campaign/protocol.json')==prepared['protocol_sha256']
    assert sha(ROOT/'campaign/manifest.json')==prepared['manifest_sha256']
    for name,digest in read_json(ROOT/'campaign/source-hashes.json').items():assert sha(ROOT/'campaign'/name)==digest,f'Snapshot changed: {name}'
    lock=(ROOT/'runner.lock').open('a+b');lock.seek(0);lock.write(b'0');lock.flush();lock.seek(0)
    msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    for status in ROOT.glob('*/status.json'):
        for item in read_json(status).get('active',[]):
            kernel=ctypes.windll.kernel32;kernel.OpenProcess.restype=ctypes.c_void_p
            handle=kernel.OpenProcess(0x1000,False,item['pid'])
            if handle:
                exitcode=ctypes.c_ulong();kernel.GetExitCodeProcess(ctypes.c_void_p(handle),ctypes.byref(exitcode));kernel.CloseHandle(ctypes.c_void_p(handle))
                if exitcode.value==259:raise RuntimeError(f'Prior worker may still be alive: {item}. Refusing duplicate launch.')
    ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
    manifest=read_json(ROOT/'campaign/manifest.json')
    from matrix import validation,baseline_validation,select,expansion,tests,evaluation
    p=read_json(ROOT/'campaign/protocol.json')
    tasks=[t for t in manifest['training'] if not t['conditional'] and not t['import_pending']]
    # Exercise every algorithm/scenario/variant before long training; repetition zero suffices for code paths.
    smoke=[]
    for t in tasks:
        if t['repetition']!=1:continue
        smoke.append(dict(t,id='smoke-'+t['id'],episodes=2,checkpoints=[1,2]))
    for alg in ['dqn','a2c']:
        smoke.append(dict(id='smoke-current-day_cycle-'+alg,kind='train',scenario='day_cycle',algorithm=alg,variant='current',learning_seed=373021,episodes=2,checkpoints=[1,2]))
    sr=prepare_child('smoke',smoke)
    result=run_queue(sr,smoke,4,'smoke')
    if result['failed'] or (ROOT/'STOP').exists():return
    smoke_eval=[]
    for t in smoke:
        scenario='balanced' if t['scenario']=='mixed' else t['scenario']
        e=evaluation('eval-'+t['id'],scenario,19,'smoke',algorithm=t['algorithm'],weights=f'training/{t["id"]}/checkpoint-2.pt',demand_folder='snapshot/sim/scenarios')
        e.update(variant=t['variant'],demand_name=f'{scenario}_s19');smoke_eval.append(e)
    for alg in ['timer','script','fixed']:
        e=evaluation('smoke-baseline-'+alg,'balanced',19,'smoke',algorithm=alg,duration=30,demand_folder='snapshot/sim/scenarios')
        e['demand_name']='balanced_s19';smoke_eval.append(e)
    e=evaluation('smoke-table','balanced',19,'smoke',algorithm='fixed',duration=30,table={'B1':{'0':20,'3':60},'C1':{'0':40,'3':50}},demand_folder='snapshot/sim/scenarios')
    e['demand_name']='balanced_s19';smoke_eval.append(e)
    result=run_queue(sr,smoke_eval,4,'evaluation-smoke')
    if result['failed'] or (ROOT/'STOP').exists():return
    # Reuse completed measurements on infrastructure recovery; never divide old
    # completed work by the near-zero time of a resumed empty queue.
    results=read_json(ROOT/'benchmark-results.json') if (ROOT/'launch-gate.json').exists() else []
    for cap in ([] if results else [4,6,8,10,12,16]):
        if cap>8 and (results[-1]['steps_per_second']<=results[-2]['steps_per_second']*1.03 or results[-1]['min_free_memory_fraction']<.25):break
        bench=[dict(id=f'bench-{i}',kind='train',scenario='day_cycle',algorithm='dqn' if i%2==0 else 'a2c',variant='current',learning_seed=273021+i,episodes=3,checkpoints=[3]) for i in range(16)]
        br=prepare_child(f'benchmark-{cap}',bench)
        result=run_queue(br,bench,cap,f'benchmark-{cap}');results.append(dict(cap=cap,**result))
        write_json(ROOT/'benchmark-results.json',results)
        if result['failed'] or result['min_free_memory_fraction']<.20 or (ROOT/'STOP').exists():break
    valid=[r for r in results if not r['failed'] and r['min_free_memory_fraction']>=.20]
    if not valid:raise RuntimeError('No benchmark passed memory and error gates')
    best=valid[0]
    for r in valid[1:]:
        if r['steps_per_second']>best['steps_per_second']*1.03:best=r
    write_json(ROOT/'launch-gate.json',dict(benchmark=best,code_hashes={f.name:sha(f) for f in ROOT.glob('*.py')},scope='Initial training and validation; test waits for all selections and J decisions',time=time.time()))
    from demand import generate
    generate()
    # Round-robin scenarios and algorithms inside each repeat; A before variants, G last.
    order={'A':0,'E':1,'F':1,'H':1,'I':1,'G':2}
    tasks.sort(key=lambda t:(order[t['family']],t['repetition'],t['scenario'],t['variant'],t['algorithm']))
    initial=[t for t in manifest['training'] if not t['conditional']]
    combined=baseline_validation(p)+validation(initial,p)+tasks
    result=run_queue(ROOT/'campaign',combined,best['cap'],'initial-training-and-validation')
    if result['failed'] or (ROOT/'STOP').exists():return
    chosen=select(initial,p);decisions=expansion(initial,chosen,p)
    write_json(ROOT/'campaign/expansion-decisions.json',decisions)
    extra=[t for t in manifest['training'] if t['conditional'] and t['variant'] in decisions[t['family']+'-'+t['algorithm']]['expand_variants']]
    if extra:
        result=run_queue(ROOT/'campaign',validation(extra,p)+extra,best['cap'],'conditional-training-and-validation')
        if result['failed'] or (ROOT/'STOP').exists():return
        chosen.update(select(extra,p))
    final_tasks=tests(initial+extra,chosen,p)
    write_json(ROOT/'campaign/selections.json',chosen)
    write_json(ROOT/'campaign/test-manifest.json',final_tasks)
    write_json(ROOT/'campaign/test-gate.json',dict(time=time.time(),selections_sha256=sha(ROOT/'campaign/selections.json'),expansion_sha256=sha(ROOT/'campaign/expansion-decisions.json')))
    result=run_queue(ROOT/'campaign',final_tasks,best['cap'],'test')
    from analyze import analyze
    analyze()
    ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
if __name__=='__main__':main()
