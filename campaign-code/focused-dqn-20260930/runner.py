"""Single-owner, bounded 24-hour experiment. No automatic retries or scientific repairs."""
import os,sys,time,subprocess,ctypes,shutil,statistics,msvcrt,traceback
from pathlib import Path
from worker import read_json as read,write_json as write,sha
ROOT=Path(__file__).resolve().parent;RUN=ROOT/'campaign'
os.environ.update(PYTHONIOENCODING='utf-8',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
class MEMORY(ctypes.Structure):
    _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(k,ctypes.c_ulonglong) for k in ['total','free','page_total','page_free','virtual_total','virtual_free','extended']]
def resources():
    m=MEMORY();m.length=ctypes.sizeof(m);assert ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return dict(total=m.total,free=m.free,free_fraction=m.free/m.total,disk_free=shutil.disk_usage(ROOT).free,logical_cpus=os.cpu_count())
def queue(tasks,cap,label,deadline):
    active={};done=set();started=time.time();minfree=1.;peak=0;failure=None
    for t in tasks:
        p=RUN/'tasks'/f'{t["id"]}.json'
        if p.exists():assert read(p)==t
        else:write(p,t)
        if (RUN/'completed'/p.name).exists():done.add(t['id'])
        assert not (RUN/'failed'/p.name).exists(),f'Prior failure requires review: {t["id"]}'
    try:
        while len(done)<len(tasks):
            for key,(proc,log,t,launch) in list(active.items()):
                if proc.poll() is not None:
                    log.close();del active[key]
                    if proc.returncode==0 and (RUN/'completed'/f'{key}.json').exists():done.add(key)
                    else:failure=f'{key}: exit {proc.returncode}';(ROOT/'STOP').touch()
                else:
                    p=RUN/('training' if t['kind']=='train' else 'evaluations')/key/'progress.json'
                    updated=read(p).get('updated_at',launch) if p.exists() else launch
                    if time.time()-max(launch,updated)>900:failure=f'{key}: no progress for 15 minutes';(ROOT/'STOP').touch()
            r=resources();minfree=min(minfree,r['free_fraction']);peak=max(peak,len(active))
            stopping=(ROOT/'STOP').exists() or time.time()>deadline-180
            pending=[t for t in tasks if t['id'] not in done and t['id'] not in active]
            if pending and len(active)<cap and not stopping and r['free']-.2*r['total']>.75*1024**3 and r['disk_free']>20*1024**3:
                t=pending[0];(RUN/'logs').mkdir(exist_ok=True);log=(RUN/'logs'/f'{t["id"]}.log').open('ab')
                script='worker.py' if t['kind']=='train' else 'evaluator.py'
                proc=subprocess.Popen([sys.executable,str(ROOT/script),str(RUN),t['id']],stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
                active[t['id']]=(proc,log,t,time.time())
            write(ROOT/'status.json',dict(stage=label,updated_at=time.time(),scheduler_pid=os.getpid(),active=[dict(id=k,pid=v[0].pid) for k,v in active.items()],completed=len(done),total=len(tasks),capacity=cap,resources=r,deadline=deadline,stopping=stopping,failure=failure))
            if stopping and not active:raise RuntimeError(failure or 'Campaign stopped/deadline reached; stage incomplete')
            if time.time()>deadline-15:raise RuntimeError('Absolute phase deadline reached')
            if not active and pending and time.time()-started>600:raise RuntimeError('Insufficient resources to launch within admission window')
            time.sleep(2)
    finally:
        for proc,log,_,_ in active.values():
            subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],capture_output=True);log.close()
    result=dict(stage=label,elapsed=time.time()-started,min_free_fraction=minfree,peak=peak,completed=len(done))
    write(ROOT/f'{label}-timing.json',result);return result
def evaltask(model,split,seed,load='base',ep=None):
    t=dict(kind='eval',algorithm=model['algorithm'],variant='current',scenario='day_cycle',seed=seed,split=split,load=load,model=model['id'],repetition=model.get('repetition'),family=model.get('family',model['id']),demand_name=f'day_cycle_s{seed}_{load}')
    if ep is not None:t['checkpoint']=ep
    for k in ['weights','duration','expected_weight_sha256']:
        if k in model:t[k]=model[k]
    t['id']=f'{split}-{model["id"]}'+(f'-cp{ep}' if ep else '')+f'-s{seed}-{load}'
    return t
def choose(rows,key):return min(rows,key=lambda x:(x['mean_wait'],x[key]))
def main():
    lock=(ROOT/'runner.lock').open('a+b');lock.write(b'0');lock.flush();lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    assert not (ROOT/'STOP').exists(),'STOP present'
    for name,digest in read(ROOT/'preflight.json')['hashes'].items():assert sha(ROOT/name)==digest,name
    if not (ROOT/'clock.json').exists():
        start=time.time();write(ROOT/'clock.json',dict(started_at=start,training_deadline=start+18*3600,simulation_deadline=start+23*3600,final_deadline=start+24*3600,note='Includes smoke and timing; 1h final audit/analysis reserve'))
    clock=read(ROOT/'clock.json');assert time.time()<clock['training_deadline']-600
    ctypes.windll.kernel32.SetThreadExecutionState(0x80000001) # Prevent idle sleep, leave display sleep available.
    p=read(RUN/'protocol.json');train=read(RUN/'training-manifest.json')
    try:
        # Smoke is full day_cycle on known training demands, not fresh validation/test.
        smoke=[dict(t,id='smoke-'+t['id'],episodes=5,checkpoints=[5]) for t in train]
        if not (ROOT/'scope.json').exists():
            smoke_timing=queue(smoke,6,'smoke-training',clock['training_deadline'])
            samples=[]
            for t in smoke:
                rows=[read(f) for f in sorted((RUN/'training'/t['id']/'episodes').glob('*.json'))]
                assert len(rows)==5
                for row in rows:
                    arm=p['arms'][t['variant']]
                    assert row['learning_rate']==arm['LR'] and abs(row['epsilon']-max(.05,arm['EPS_DECAY']**row['episode']))<1e-10
                samples.extend(x['wall_seconds'] for x in rows[2:])
            # Verify current wrapper against historical first episode, beyond source equality.
            compat=dict(train[0],id='smoke-current-compat',variant='current',episodes=2,checkpoints=[2])
            queue([compat],1,'compatibility',clock['training_deadline'])
            origin=Path(read(RUN/'import-audit.json')[0]['origin'])
            for ep in [1,2]:
                a=read(RUN/'training'/compat['id']/'episodes'/f'{ep:04d}.json');b=read(origin/'episodes'/f'{ep:04d}.json')
                for k in ['demand_seed','total_reward','decisions','simulation_steps','learning_updates','epsilon']:assert a[k]==b[k],f'Baseline replay mismatch: {k} episode {ep}'
            from demand import generate
            generate()
            # Smoke evaluation uses a familiar demand file, with complete audit output.
            for ext in ['rou','ped']:shutil.copy2(RUN/f'snapshot/sim/scenarios/day_cycle_s1.{ext}.xml',RUN/f'demand/day_cycle_s1_base.{ext}.xml')
            evalsmoke=[evaltask(dict(id='smoke-current',algorithm='dqn',weights='training/current-r1/checkpoint-500.pt'),'smoke',1),evaltask(dict(id='smoke-timer',algorithm='timer'),'smoke',1),evaltask(dict(id='smoke-fixed',algorithm='fixed',duration=30),'smoke',1)]
            et=queue(evalsmoke,3,'smoke-evaluation',clock['training_deadline'])
            # 50% timing margin on the slowest observed training episode, after replay warm-up.
            estimate=max(max(samples)*1000*max(1,6/smoke_timing['peak']),smoke_timing['elapsed']/5*1000)*1.5
            remaining=clock['training_deadline']-time.time()
            arms=list(p['arms']) if estimate<remaining else []
            capacity=6
            if not arms:
                three=[dict(t,id='benchmark3-'+t['id'],episodes=5,checkpoints=[5]) for t in train if t['variant']=='lr0003']
                three_timing=queue(three,3,'benchmark-three',clock['training_deadline'])
                samples=[read(f)['wall_seconds'] for t in three for f in (RUN/'training'/t['id']/'episodes').glob('*.json') if int(f.stem)>=3]
                estimate=max(max(samples)*1000*max(1,3/three_timing['peak']),three_timing['elapsed']/5*1000)*1.5;remaining=clock['training_deadline']-time.time()
                if estimate>=remaining:raise RuntimeError(f'One complete 3-run arm not supported by timing: {estimate/3600:.2f}h vs {remaining/3600:.2f}h')
                arms=['lr0003'];capacity=3
            eval_est=et['elapsed']/3*770/6*2
            assert eval_est<5*3600,'Evaluation budget projection exceeds reserve'
            write(ROOT/'scope.json',dict(arms=arms,excluded_arms=[a for a in p['arms'] if a not in arms],exclusion_reason='Pre-validation timing budget only',train_capacity=capacity,eval_capacity=6,training_estimate_seconds=estimate,evaluation_estimate_seconds=eval_est,timing_samples=samples,resources=resources(),decision_before_validation=True))
        scope=read(ROOT/'scope.json');train=[t for t in train if t['variant'] in scope['arms']]
        queue(train,scope['train_capacity'],'training',clock['training_deadline'])
        models=[dict(id=f'current-r{r}',algorithm='dqn',family='current',repetition=r) for r in range(1,4)]+[dict(id=t['id'],algorithm='dqn',family=t['variant'],repetition=t['repetition']) for t in train]
        validation=[]
        for m in models:
            for ep in p['checkpoints']:
                path=f'training/{m["id"]}/checkpoint-{ep}.pt'
                validation.extend(evaltask(dict(m,weights=path,expected_weight_sha256=sha(RUN/path)),'validation',seed,ep=ep) for seed in p['validation_seeds'])
        for duration in p['fixed_durations']:
            validation.extend(evaltask(dict(id=f'fixed{duration}',algorithm='fixed',duration=duration),'validation',s) for s in p['validation_seeds'])
        validation.extend(evaltask(dict(id='TIMER',algorithm='timer'),'validation',s) for s in p['validation_seeds'])
        write(RUN/'validation-manifest.json',validation)
        queue(validation,scope['eval_capacity'],'validation',clock['simulation_deadline'])
        selected=[];scores=[]
        for m in models:
            candidates=[]
            for ep in p['checkpoints']:
                ts=[t for t in validation if t['model']==m['id'] and t.get('checkpoint')==ep]
                assert len(ts)==10
                candidates.append(dict(episode=ep,mean_wait=statistics.mean(read(RUN/'completed'/f'{t["id"]}.json')['summary']['avg_waiting_time'] for t in ts)))
            best=choose(candidates,'episode');path=f'training/{m["id"]}/checkpoint-{best["episode"]}.pt'
            selected.append(dict(m,weights=path,expected_weight_sha256=sha(RUN/path),selected_checkpoint=best['episode']))
            scores.append(dict(model=m['id'],candidates=candidates,selected=best))
        fixed=[]
        for duration in p['fixed_durations']:
            ts=[t for t in validation if t['model']==f'fixed{duration}']
            fixed.append(dict(duration=duration,mean_wait=statistics.mean(read(RUN/'completed'/f'{t["id"]}.json')['summary']['avg_waiting_time'] for t in ts)))
        best=choose(fixed,'duration');selected.extend([dict(id='TIMER',algorithm='timer'),dict(id='calibrated',algorithm='fixed',duration=best['duration'])])
        selection=dict(models=selected,scores=scores,fixed_candidates=fixed,fixed_selected=best,frozen_at=time.time())
        tests=[evaltask(m,'test',s,load) for m in selected for load in p['loads'] for s in p['test_seeds']]
        assert len(tests)==(len(models)+2)*40
        if (RUN/'test-gate.json').exists():
            assert read(RUN/'selection.json')['models']==selected
            assert read(RUN/'test-manifest.json')==tests
        else:
            write(RUN/'selection.json',selection);write(RUN/'test-manifest.json',tests)
            write(RUN/'test-gate.json',dict(frozen_at=time.time(),hashes={n:sha(RUN/n) for n in ['protocol.json','selection.json','test-manifest.json','validation-manifest.json','demand-manifest.json']}))
        # Measured validation speed, plus 1h analysis margin, gates the whole final set.
        validation_wall=[read(RUN/'completed'/f'{t["id"]}.json')['wall_elapsed_s'] for t in validation]
        seconds=statistics.mean(validation_wall)*len(tests)/scope['eval_capacity']*1.5+len(tests)*2
        assert time.time()+seconds<clock['simulation_deadline']-180,'Insufficient remaining budget for complete test set'
        queue(tests,scope['eval_capacity'],'test',clock['simulation_deadline'])
        subprocess.run([sys.executable,str(ROOT/'analyze.py')],check=True,timeout=max(1,clock['final_deadline']-time.time()-30))
        write(ROOT/'status.json',dict(stage='complete',updated_at=time.time(),elapsed_hours=(time.time()-clock['started_at'])/3600,report=str(ROOT/'report-he.md')))
    finally:ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
if __name__=='__main__':
    try:main()
    except Exception:
        write(ROOT/'failure.json',dict(time=time.time(),error=traceback.format_exc()))
        completed=[f.stem for f in (RUN/'completed').glob('*.json')]
        failures=[dict(task=f.stem,**read(f)) for f in (RUN/'failed').glob('*.json')]
        observations=[dict(task=f.parent.name,**read(f)) for f in (RUN/'evaluations').glob('*/completion-observation.json')]
        write(ROOT/'incomplete-summary.json',dict(completed=completed,failures=failures,completion_observations=observations,scope=read(ROOT/'scope.json') if (ROOT/'scope.json').exists() else None))
        write(ROOT/'status.json',dict(stage='stopped-incomplete',updated_at=time.time(),completed=len(completed),failure_file=str(ROOT/'failure.json')))
        (ROOT/'incomplete-he.md').write_text(f'הסבב נעצר ואינו השוואה מלאה. הושלמו {len(completed)} משימות, כולל בדיקות התקינות. נשמרו {len(failures)} רישומי כישלון. יש לבדוק failure.json ו־incomplete-summary.json, המכיל גם מוני השלמה ו־teleports לכל סימולציה שנצפתה. אין להסיק שיפור מהרצה חלקית.\n',encoding='utf-8')
        traceback.print_exc();sys.exit(1)
