"""Read-only historical audit and isolated campaign preparation. No SUMO runs."""
import os,re,json,hashlib,shutil,random
from pathlib import Path
ROOT=Path(__file__).resolve().parent
PROJECT=ROOT.parents[1]
OLD=PROJECT/'working/final-experiments-20260912'
RUN=ROOT/'campaign'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,x):
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2,ensure_ascii=False),encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    assert not (ROOT/'clock.json').exists(),'Preparation cannot change a started campaign'
    used=set();evidence=[];variants=[];matches=[];errors=[]
    skip={'sumo-env','analysis-deps','__pycache__','.git','node_modules','drive-results-20260930',ROOT.name,
          'episodes','diagnostics','evaluations','logs','completed','failed','3d-modeling-sync','agent-kit-sync','goatgun-peq15','logo-keychain','paw-qr-audit'}
    def walk_json(x,key=''):
        if isinstance(x,dict):
            for k,v in x.items():walk_json(v,k)
        elif isinstance(x,list):
            for v in x:walk_json(v,key)
        elif 'seed' in key.lower() and isinstance(x,int):used.add(x)
    for base in [PROJECT/'source-material/code',PROJECT/'working',PROJECT/'deliverables']:
        for folder,dirs,files in os.walk(base,onerror=lambda e:errors.append(str(e))):
            dirs[:]=[d for d in dirs if d not in skip and not d.endswith('render') and not d.startswith('render-')]
            p=Path(folder)
            for name in files:
                f=p/name
                for m in re.finditer(r'(?:_s|seed[-_]?)(\d+)',name):used.add(int(m[1]))
                # All actual job definitions, protocols and result seeds, plus all seed-bearing source lines.
                if f.suffix=='.json' and name in ('protocol.json','manifest.json','selection.json','multiseed_raw.json','test-manifest.json','validation-manifest.json','training-manifest.json'):
                    try:
                        obj=read(f);walk_json(obj);evidence.append(str(f.relative_to(PROJECT)))
                        if name in ('manifest.json','training-manifest.json'):
                            records=obj.get('training',[]) if isinstance(obj,dict) else obj
                            for t in records:
                                if isinstance(t,dict) and t.get('kind','train')=='train':variants.append((str(f.relative_to(PROJECT)),t.get('variant')))
                    except Exception as e:errors.append(f'{f}: {e}')
                if f.suffix=='.py' and 'snapshot' not in f.parts:
                    text=f.read_text(encoding='utf-8-sig',errors='replace')
                    for n,line in enumerate(text.splitlines(),1):
                        if 'seed' in line.lower():
                            for m in re.findall(r'\b\d+\b',line):used.add(int(m))
                        if re.search(r'(?<!\d)(?:0?\.0003|3e-0?4|0?\.998)(?!\d)',line,re.I):matches.append(dict(path=str(f.relative_to(PROJECT)),line=n,text=line.strip()))
    assert not errors,errors[:20]
    val=list(range(2001,2011));test=list(range(2101,2121))
    assert not set(val+test)&used,sorted(set(val+test)&used)
    write(ROOT/'historical-seed-audit.json',dict(used_seed_and_conservative_source_number_union=sorted(used),files=evidence,training_variants=sorted(set(v for _,v in variants if v)),parameter_mentions=matches,excluded_runtime_dependencies=sorted(skip),errors=errors,new_validation=val,new_test=test))
    # Parameter mentions are reviewed manually before launch; no unsupported universal absence claim.
    for name in ['worker.py','evaluator.py','variants.py','demand.py']:
        shutil.copy2(OLD/name,ROOT/name)
    src=OLD/'campaign/snapshot/sim';dst=RUN/'snapshot/sim'
    for f in src.rglob('*'):
        if f.is_file() and (f.suffix=='.py' or f.name=='grid.net.xml' or re.fullmatch(r'day_cycle_s(?:[1-9]|1\d|20)\.(rou|ped)\.xml',f.name)):
            target=dst/f.relative_to(src);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,target)
    p=read(OLD/'campaign/protocol.json')
    p.update(scenarios=['day_cycle'],loads=['base','vehicle125'],validation_seeds=val,test_seeds=test,
        learning_seeds=[73021,83021,93021],runtime_status='prepared',schema_version=4,
        arms={'lr0003':{'LR':.0003,'EPS_DECAY':.997},'eps998':{'LR':.001,'EPS_DECAY':.998}},
        seed_audit='historical-seed-audit.json; project protocols/manifests, XML demand filenames and conservative source seed numbers; completed/evaluation/episode payloads excluded because covered by manifests',
        deadline_hours=24,training_deadline_hours=18,fixed_durations=[20,30,40,50,60],
        selection='mean vehicle waiting over all 10 validation seeds at base load; exact ties earlier checkpoint / shorter duration',
        scope_priority=['lr0003','eps998'],inference='greedy argmax, no exploration; unchanged safety',
        uncertainty='Sample SD between 3 training means separately from SD across 20 demands within each training. Matched demand differences; matched learning-seed baseline differences. No 60-independent-trainings claim.',
        retained_limitations='Original terminal pending interval handling retained, as explicitly documented in prior protocol. Pedestrian metric remains positive-time/junction average proxy, not person-weighted wait.',
        analysis_predeclared='All test rows including teleports primary; additionally common-seed exclusion sensitivity if any teleport/collision. Action bins by junction/phase and total normalized queue: 0, (0,.5], (.5,1], >1; observational association, not causality.',
        pause_behavior='Every complete episode saves full resume; STOP or absolute phase deadline prevents next episode. Hard watchdog ends only owned worker processes before 24h.')
    write(RUN/'protocol.json',p)
    imports=[]
    for rep,seed in enumerate(p['learning_seeds'],1):
        origin=PROJECT/'working'/('overnight-sumo/campaign-20260908' if rep==1 else 'repeatability-sumo/campaign-20260910')
        folder=origin/'training'/('dqn-current' if rep==1 else f'dqn-r{rep-1}')
        q=read(origin/'protocol.json')
        for key in ['episodes','checkpoints','train_seeds','demand_schedule_seed','stop_weight']:assert q[key]==p[key],key
        for f in dst.rglob('*.py'):assert sha(f)==sha(origin/'snapshot/sim'/f.relative_to(dst)),str(f)
        for f in (dst/'scenarios').glob('day_cycle_s*.xml'):assert sha(f)==sha(origin/'snapshot/sim/scenarios'/f.name)
        rng=random.Random(p['demand_schedule_seed']);rows=[]
        for ep in range(1,1001):
            row=read(folder/'episodes'/f'{ep:04d}.json');assert row['demand_seed']==rng.choice(p['train_seeds'])
            if 'learning_rate' in row:assert abs(row['learning_rate']-.001)<1e-12
            assert abs(row['epsilon']-max(.05,.997**ep))<1e-10
            rows.append(row)
        actualseed=read(folder/'initial.json')['learning_seed'] if (folder/'initial.json').exists() else q['learning_seed']
        assert actualseed==seed
        checkpoints=[]
        for ep in p['checkpoints']:
            f=folder/f'checkpoint-{ep}.pt';assert sha(f)==read(f.with_suffix('.json'))['sha256']
            recent=OLD/f'campaign/training/A-day_cycle-dqn-current-r{rep}'/f.name;assert sha(f)==sha(recent)
            target=RUN/f'training/current-r{rep}'/f.name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,target)
            checkpoints.append(dict(episode=ep,path=str(target.relative_to(RUN)),sha256=sha(target)))
        imports.append(dict(id=f'current-r{rep}',learning_seed=seed,origin=str(folder),checkpoints=checkpoints,episodes_verified=len(rows),learning_rate_evidence='Identical full train_dqn.py uses Adam(LR), LR=.001; historical wrapper has no override. Historical episode logs omit learning_rate. Epsilon schedule checked in all 1000 rows.'))
    write(RUN/'import-audit.json',imports)
    tasks=[]
    for arm in p['arms']:
        for rep,seed in enumerate(p['learning_seeds'],1):
            task=dict(id=f'{arm}-r{rep}',kind='train',algorithm='dqn',variant=arm,scenario='day_cycle',learning_seed=seed,repetition=rep)
            tasks.append(task);write(RUN/'tasks'/f'{task["id"]}.json',task)
    write(RUN/'training-manifest.json',tasks)
    write(ROOT/'copied-source-hashes.json',{str(f.relative_to(ROOT)):sha(f) for f in dst.rglob('*') if f.is_file()})
    print(json.dumps(dict(imports=len(imports),trainings=len(tasks),parameter_mentions=matches,known_seeds=len(used)),ensure_ascii=False))
if __name__=='__main__':main()
