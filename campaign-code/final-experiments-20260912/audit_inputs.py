"""Read-only audit of historical inputs, then copy approved checkpoint imports."""
import json,random,shutil,re
from pathlib import Path
from worker import read_json,write_json,sha
ROOT=Path(__file__).resolve().parent;PROJECT=ROOT.parents[1];RUN=ROOT/'campaign'
def main():
    manifest=read_json(RUN/'manifest.json');p=read_json(RUN/'protocol.json')
    target=set(p['validation_seeds']+p['test_seeds']);collisions=[];checked=0
    for base in [PROJECT/'source-material/code',PROJECT/'working/overnight-sumo',PROJECT/'working/repeatability-sumo']:
        for f in base.rglob('*.xml'):
            match=re.search(r'_s(\d+)\.',f.name)
            if match:
                checked+=1
                if int(match[1]) in target:collisions.append(str(f))
        for f in base.rglob('protocol.json'):
            q=read_json(f)
            for key in ('train_seeds','validation_seeds','test_seeds'):
                overlap=target.intersection(q.get(key,[]))
                if overlap:collisions.append(dict(path=str(f),field=key,seeds=sorted(overlap)))
    assert not collisions,collisions
    imports=[]
    for arm in manifest['training']:
        if not arm['import_pending']:continue
        r=arm['repetition'];alg=arm['algorithm']
        parent=PROJECT/'working'/('overnight-sumo/campaign-20260908' if r==1 else 'repeatability-sumo/campaign-20260910')
        key=f'{alg}-current' if r==1 else f'{alg}-r{r-1}'
        folder=parent/'training'/key
        q=read_json(parent/'protocol.json')
        assert q['episodes']==1000 and q['checkpoints']==[500,750,1000]
        assert q['train_seeds']==p['train_seeds'] and q['demand_schedule_seed']==p['demand_schedule_seed']
        assert q['stop_weight']==p['stop_weight']
        initial=read_json(folder/'initial.json') if (folder/'initial.json').exists() else None
        oldseed=initial['learning_seed'] if initial else q['learning_seed']
        assert oldseed==arm['learning_seed'],(key,oldseed,arm['learning_seed'])
        for f in (RUN/'snapshot/sim').rglob('*.py'):
            old=parent/'snapshot/sim'/f.relative_to(RUN/'snapshot/sim')
            assert old.exists() and sha(old)==sha(f),str(f)
        for seed in p['train_seeds']:
            for ext in ['rou','ped']:
                name=f'day_cycle_s{seed}.{ext}.xml'
                assert sha(parent/'snapshot/sim/scenarios'/name)==sha(RUN/'snapshot/sim/scenarios'/name)
        rng=random.Random(p['demand_schedule_seed'])
        for ep in range(1,1001):
            row=read_json(folder/'episodes'/f'{ep:04d}.json')
            assert row['demand_seed']==rng.choice(p['train_seeds'])
        imported=[]
        for ep in p['checkpoints']:
            f=folder/f'checkpoint-{ep}.pt';meta=read_json(folder/f'checkpoint-{ep}.json')
            assert sha(f)==meta['sha256']
            dest=RUN/'training'/arm['id']/f.name;dest.parent.mkdir(parents=True,exist_ok=True)
            if dest.exists():assert sha(dest)==sha(f)
            else:shutil.copy2(f,dest)
            write_json(dest.with_suffix('.json'),dict(meta,imported_from=str(f)))
            imported.append(dict(episode=ep,source=str(f),sha256=sha(f)))
        imports.append(dict(id=arm['id'],learning_seed=oldseed,checkpoints=imported))
    write_json(RUN/'input-audit.json',dict(seed_collisions=collisions,route_files_inspected=checked,imports=imports,
      scope='Historical source and both campaigns: XML demand names and protocol split lists; matched source and all 1000 demand schedule entries for each import'))
    print(json.dumps({'imports':len(imports),'seed_collisions':len(collisions),'route_files_inspected':checked}))
if __name__=='__main__':main()
