"""Create an isolated campaign without modifying any historical inputs."""
import json, shutil, hashlib, random
from pathlib import Path
ROOT=Path(__file__).resolve().parent
PROJECT=ROOT.parents[1]
def dump(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,indent=2,ensure_ascii=False),encoding='utf-8')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    run=ROOT/'campaign'
    if (run/'protocol.json').exists(): raise RuntimeError('Already initialized; do not overwrite')
    source=PROJECT/'working/repeatability-sumo/campaign-20260910/snapshot/sim'
    shutil.copytree(source,run/'snapshot/sim',ignore=shutil.ignore_patterns('__pycache__','results','models','*.pyc'))
    scenarios=['balanced','heavy_west','pedestrian_heavy','morning_flow','evening_flow','day_cycle']
    original=PROJECT/'source-material/code/Trafic AI/sim/scenarios'
    for s in scenarios:
        for seed in range(1,21):
            for ext in ['rou','ped']:
                name=f'{s}_s{seed}.{ext}.xml'
                dst=run/'snapshot/sim/scenarios'/name
                if dst.exists(): assert sha(dst)==sha(original/name),name
                else: shutil.copy2(original/name,dst)
    plan=PROJECT/'deliverables/full-experiment-plan-20260912.md'
    shutil.copy2(plan,run/'frozen-plan.md')
    p=json.loads((PROJECT/'working/repeatability-sumo/campaign-20260910/protocol.json').read_text())
    p={k:p[k] for k in ['episodes','checkpoints','train_seeds','demand_schedule_seed','stop_weight','pedestrian_weight','max_simulation_steps']}
    p.update(schema_version=3,scenarios=scenarios,validation_seeds=list(range(601,611)),test_seeds=list(range(701,721)),
      seed_audit='Pending; no validation or test launched until audited',sumo_seed=23423,
      sumo_seed_note='Explicit SUMO default 23423, matching prior runs without seed override',
      plan_sha256=sha(plan),test_gate='All validation selections and conditional J decisions frozen before any test',
      selection='minimum mean validation vehicle waiting, ties earlier checkpoint',
      joint_selection='0.5 vehicle/TIMER + 0.5 pedestrian proxy/TIMER; zero denominator blocks selection',
      reserve_memory_fraction=.20,min_free_disk_gib=20,max_workers=8,
      actor_advantage_normalization='Within each junction trajectory, (adv-mean)/(population std+1e-8); constant advantages become zero; critic unchanged',
      loads=['base','vehicle075','vehicle125','pedestrian075','pedestrian125'],
      evaluation_gate='BLOCKED until evaluation implementation and seed/demand audit pass',
      import_gate='Six day_cycle current runs reserved for provenance audit and three-checkpoint import')
    arms=[]
    seeds={'dqn':[73021,83021,93021],'a2c':[73021,103021,113021]}
    def add(family,scenario,alg,variant,repetition,conditional=False):
        key=f'{family}-{scenario}-{alg}-{variant}-r{repetition+1}'
        arms.append(dict(id=key,kind='train',family=family,scenario=scenario,algorithm=alg,variant=variant,
          repetition=repetition+1,learning_seed=seeds[alg][repetition],episodes=6000 if family=='G' else 1000,
          checkpoints=[3000,4500,6000] if family=='G' else [500,750,1000],
          conditional=conditional,import_pending=family=='A' and scenario=='day_cycle'))
    for s in scenarios:
        for r in range(3):
            for alg in seeds: add('A',s,alg,'current',r)
    variants={'E':(['vehicle_seconds','vehicle_seconds_no_stops','pedestrians'],['day_cycle','pedestrian_heavy'],list(seeds)),
      'F':(['mask_pedestrians','mask_link'],['day_cycle','pedestrian_heavy'],list(seeds)),
      'H':(['entropy005','normalized_advantage'],['day_cycle','morning_flow'],['a2c']),
      'I':(['huber'],['day_cycle','morning_flow'],['dqn'])}
    for fam,(vv,ss,aa) in variants.items():
        for s in scenarios:
            for v in vv:
                for r in range(3):
                    for a in aa: add(fam,s,a,v,r,conditional=s not in ss)
    for r in range(3):
        for a in seeds: add('G','mixed',a,'current',r)
    for arm in arms: dump(run/'tasks'/f"{arm['id']}.json",arm)
    manifest=dict(training=arms,evaluation_expansion=dict(validation='Every arm: 3 checkpoints x 10 seeds; mixed: all six scenarios',
      A_B='Every A selected model and baselines: six scenarios x five loads x twenty test seeds',
      C='Validation modal proposed action per junction/phase; same A/B test matrix',
      D='Joint checkpoint selection for A/E; same base test seeds',
      E_F_H_I='Every initial arm tested regardless of J eligibility',
      G='Six mixed models x six scenarios x five loads x twenty seeds',
      J='Potential arms predeclared above; validation-only eligibility and union symmetry as frozen plan'),
      status='Training manifest explicit; evaluation jobs blocked pending implementation and audits')
    dump(run/'manifest.json',manifest);dump(run/'protocol.json',p)
    dump(run/'source-hashes.json',{str(x.relative_to(run)):sha(x) for x in (run/'snapshot').rglob('*') if x.is_file()})
    worker=(PROJECT/'working/repeatability-sumo/worker.py').read_text(encoding='utf-8')
    worker=worker.replace("algorithm, variant = task['algorithm'], task['variant']", "algorithm, variant = task['algorithm'], task['variant']\n    protocol = dict(protocol, episodes=task.get('episodes', protocol['episodes']), checkpoints=task.get('checkpoints', protocol['checkpoints']))\n    from variants import install\n    install(task, td, ta, ai, ac, torch, np)\n    reward_variant = variant if variant in ('vehicle_seconds', 'vehicle_seconds_no_stops', 'pedestrians') else 'current'")
    worker=worker.replace("if variant == 'current':","if reward_variant == 'current':").replace("if variant == 'pedestrians' else 0","if reward_variant == 'pedestrians' else 0")
    worker=worker.replace("mod.STOP_PENALTY = protocol['stop_weight']","mod.STOP_PENALTY = 0.0 if variant == 'vehicle_seconds_no_stops' else protocol['stop_weight']")
    worker=worker.replace('scenario = f"day_cycle_s{schedule[episode-1]}"', 'scenario_base = task["scenario"]\n        if scenario_base == "mixed": scenario_base = protocol["scenarios"][(episode-1) % 6]\n        scenario = f"{scenario_base}_s{schedule[(episode-1)//6 if task[\"scenario\"] == \"mixed\" else episode-1]}"\n        demand_end = 3600 if scenario_base == "day_cycle" else 1200')
    worker=worker.replace('scenario, 3600)', 'scenario, demand_end)')
    worker=worker.replace('row = dict(episode=episode,','row = dict(scenario=scenario_base,learning_seed=learning_seed,episode=episode,')
    worker=worker.replace("if task.get('expected_weight_sha256'):","if task.get('expected_weight_sha256'):")
    # Restrict this runner to training until evaluation audits are implemented.
    worker=worker.replace('initialize(run)\n        (train', "assert task['kind'] == 'train', 'Evaluation gate: use audited evaluator only'\n        initialize(run)\n        (train")
    compile(worker,'worker.py','exec')
    (ROOT/'worker.py').write_text(worker,encoding='utf-8')
    print(json.dumps({'new_training':sum(not a['conditional'] and not a['import_pending'] for a in arms),'conditional_training':sum(a['conditional'] for a in arms),'root':str(run)}))
if __name__=='__main__':main()
