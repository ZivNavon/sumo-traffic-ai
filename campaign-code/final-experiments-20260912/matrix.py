"""Predeclared validation, expansion, and evaluation matrix; no test-driven choices."""
import statistics,collections,json
from pathlib import Path
from worker import read_json,write_json,sha
ROOT=Path(__file__).resolve().parent;RUN=ROOT/'campaign'
def mean(xs):return statistics.mean(xs)
def key(a,s,ep,seed):return f'val-{a["id"]}-{s}-{ep}-{seed}'
def evaluation(identifier,scenario,seed,split,**kwargs):
    load=kwargs.pop('load','base')
    return dict(id=identifier,kind='eval',scenario=scenario,seed=seed,split=split,load=load,
      demand_name=f'{scenario}_s{seed}_{load}',variant='current',**kwargs)
def validation(arms,p):
    out=[]
    for a in arms:
        for s in p['scenarios'] if a['scenario']=='mixed' else [a['scenario']]:
            for ep in a['checkpoints']:
                for seed in p['validation_seeds']:
                    t=evaluation(key(a,s,ep,seed),s,seed,'validation',algorithm=a['algorithm'],weights=f'training/{a["id"]}/checkpoint-{ep}.pt',model_key=a['id'],episode=ep)
                    t['variant']=a['variant'];t['depends_on_train']=None if a['import_pending'] else a['id'];out.append(t)
    return out
def baseline_validation(p):
    return [evaluation(f'val-baseline-{s}-{alg}-{duration}-{seed}',s,seed,'validation',algorithm=alg,duration=duration)
      for s in p['scenarios'] for alg,duration in [('timer',30)]+[('fixed',d) for d in [20,30,40,50,60]] for seed in p['validation_seeds']]
def result(identifier):
    row=read_json(RUN/'completed'/f'{identifier}.json');assert row['status']=='passed';return row['summary']
def baseline_mean(s,metric,p,alg='timer',duration=30):
    return mean([result(f'val-baseline-{s}-{alg}-{duration}-{seed}')[metric] for seed in p['validation_seeds']])
def score(a,ep,metric,p,s=None):
    s=s or a['scenario'];return mean([result(key(a,s,ep,seed))[metric] for seed in p['validation_seeds']])
def select(arms,p):
    selected={}
    for a in arms:
        choices=[]
        for ep in a['checkpoints']:
            if a['scenario']=='mixed':
                denominators=[baseline_mean(s,'avg_waiting_time',p) for s in p['scenarios']]
                assert all(x>0 for x in denominators),'Zero TIMER denominator blocks mixed selection'
                value=mean([score(a,ep,'avg_waiting_time',p,s)/d for s,d in zip(p['scenarios'],denominators)])
            else:value=score(a,ep,'avg_waiting_time',p)
            choices.append((value,ep))
        value,ep=min(choices)
        weights=f'training/{a["id"]}/checkpoint-{ep}.pt'
        choice=dict(episode=ep,validation_score=value,weights=weights,expected_weight_sha256=sha(RUN/weights),all_scores=choices)
        if a['family'] in ['A','E']:
            tv=baseline_mean(a['scenario'],'avg_waiting_time',p);tp=baseline_mean(a['scenario'],'avg_pedestrian_waiting_time',p)
            if tv>0 and tp>0:
                joint=sorted((.5*score(a,e,'avg_waiting_time',p)/tv+.5*score(a,e,'avg_pedestrian_waiting_time',p)/tp,e) for e in a['checkpoints'])
                je=joint[0][1];jw=f'training/{a["id"]}/checkpoint-{je}.pt'
                choice['joint']=dict(episode=je,weights=jw,expected_weight_sha256=sha(RUN/jw),all_scores=joint)
            else:choice['joint']=dict(blocked='Zero TIMER denominator')
        selected[a['id']]=choice
    return selected
def expansion(arms,selected,p):
    decisions={};baseline={(a['algorithm'],a['scenario'],a['repetition']):a for a in arms if a['family']=='A'}
    for family in ['E','F','H','I']:
        algorithms=['dqn','a2c'] if family in ['E','F'] else ['a2c'] if family=='H' else ['dqn']
        winners={}
        for alg in algorithms:
            candidates=[]
            for variant in sorted({a['variant'] for a in arms if a['family']==family and a['algorithm']==alg}):
                aa=[a for a in arms if a['family']==family and a['algorithm']==alg and a['variant']==variant];checks=[];ratios=[]
                for scenario in sorted({a['scenario'] for a in aa}):
                    entries=[a for a in aa if a['scenario']==scenario];av=[];bv=[];ap=[];bp=[]
                    for a in entries:
                        b=baseline[alg,scenario,a['repetition']]
                        for dest,arm,metric in [(av,a,'avg_waiting_time'),(bv,b,'avg_waiting_time'),(ap,a,'avg_pedestrian_waiting_time'),(bp,b,'avg_pedestrian_waiting_time')]:
                            dest.append(score(arm,selected[arm['id']]['episode'],metric,p))
                    ok=len(av)==3 and mean(av)<mean(bv) and sum(x<y for x,y in zip(av,bv))>=2 and mean(ap)<=1.05*mean(bp)
                    checks.append(dict(scenario=scenario,eligible=ok,vehicle=av,baseline_vehicle=bv,pedestrian=ap,baseline_pedestrian=bp))
                    ratios.append(mean(av)/mean(bv) if mean(bv)>0 else float('inf'))
                eligible=len(checks)==2 and all(c['eligible'] for c in checks)
                candidates.append(dict(variant=variant,eligible=eligible,score=mean(ratios) if all(x!=float('inf') for x in ratios) else None,checks=checks))
            eligible=[c for c in candidates if c['eligible']]
            winners[alg]=min(eligible,key=lambda c:(c['score'],c['variant']))['variant'] if eligible else None
            decisions[family+'-'+alg]=dict(candidates=candidates,winner=winners[alg])
        if family in ['E','F']:
            union=sorted({v for v in winners.values() if v})
            for alg in algorithms:decisions[family+'-'+alg]['expand_variants']=union
        else:
            for alg in algorithms:decisions[family+'-'+alg]['expand_variants']=[winners[alg]] if winners[alg] else []
    return decisions
def tests(arms,selected,p):
    out=[];fixed={}
    for s in p['scenarios']:
        fixed[s]=min((baseline_mean(s,'avg_waiting_time',p,'fixed',d),d) for d in [20,30,40,50,60])[1]
        for load in p['loads']:
            for seed in p['test_seeds']:
                for alg,d in [('timer',30),('script',30)]+[('fixed',d) for d in sorted({30,fixed[s]})]:
                    out.append(evaluation(f'test-baseline-{s}-{load}-{alg}-{d}-{seed}',s,seed,'test',algorithm=alg,duration=d,load=load))
    for a in arms:
        choice=selected[a['id']]
        for s in p['scenarios'] if a['scenario']=='mixed' else [a['scenario']]:
            table=None
            if a['family']=='A':
                counts=collections.defaultdict(collections.Counter)
                for seed in p['validation_seeds']:
                    with (RUN/'evaluations'/key(a,s,choice['episode'],seed)/'decisions.jsonl').open() as f:
                        for line in f:
                            row=json.loads(line);counts[row['junction'],str(row['phase'])][row['proposed']]+=1
                table={}
                for (junction,phase),counter in counts.items():table.setdefault(junction,{})[phase]=min(counter,key=lambda v:(-counter[v],v))
                choice['table']=dict(values=table,fallback=fixed[s])
            for load in p['loads'] if a['family'] in ['A','G'] else ['base']:
                for seed in p['test_seeds']:
                    t=evaluation(f'test-{a["id"]}-{s}-{load}-{seed}',s,seed,'test',algorithm=a['algorithm'],model_key=a['id'],load=load,**{k:choice[k] for k in ['weights','expected_weight_sha256','episode']})
                    t['variant']=a['variant'];out.append(t)
                    if table is not None:out.append(evaluation(f'test-table-{a["id"]}-{s}-{load}-{seed}',s,seed,'test',algorithm='fixed',model_key=a['id'],load=load,table=table,duration=fixed[s],comparison='frozen_phase_table'))
            joint=choice.get('joint',{})
            if joint.get('episode') and joint['episode']!=choice['episode']:
                for seed in p['test_seeds']:
                    t=evaluation(f'test-joint-{a["id"]}-{s}-{seed}',s,seed,'test',algorithm=a['algorithm'],model_key=a['id'],comparison='joint_selection',**{k:joint[k] for k in ['weights','expected_weight_sha256','episode']})
                    t['variant']=a['variant'];out.append(t)
    write_json(RUN/'fixed-selections.json',fixed)
    return out
