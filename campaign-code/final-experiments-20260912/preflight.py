"""Preparation-only checks: no subprocess, SUMO, optimizer steps or training."""
import ast,json,collections,xml.etree.ElementTree as ET,random
from pathlib import Path
from worker import read_json,write_json,sha
from matrix import validation,baseline_validation,evaluation
ROOT=Path(__file__).resolve().parent;RUN=ROOT/'campaign'
def main():
    files=list(ROOT.glob('*.py'))
    for f in files:compile(f.read_text(encoding='utf-8'),str(f),'exec')
    p=read_json(RUN/'protocol.json');manifest=read_json(RUN/'manifest.json');arms=manifest['training']
    assert len({a['id'] for a in arms})==len(arms)
    initial=[a for a in arms if not a['conditional']]
    assert len(initial)==120 and sum(a['import_pending'] for a in initial)==6
    assert len(arms)==276 and sum(a['conditional'] for a in arms)==156
    assert set(p['train_seeds']).isdisjoint(p['validation_seeds']) and set(p['test_seeds']).isdisjoint(p['train_seeds']+p['validation_seeds'])
    for s in p['scenarios']:
        for seed in p['train_seeds']:
            for ext in ['rou','ped']:
                root=ET.parse(RUN/'snapshot/sim/scenarios'/f'{s}_s{seed}.{ext}.xml').getroot()
                assert root.tag=='routes'
    audit=read_json(RUN/'input-audit.json');assert len(audit['imports'])==6 and not audit['seed_collisions']
    for item in audit['imports']:
        for checkpoint in item['checkpoints']:
            assert sha(RUN/'training'/item['id']/f'checkpoint-{checkpoint["episode"]}.pt')==checkpoint['sha256']
    jobs=baseline_validation(p)+validation(arms,p)
    assert len({j['id'] for j in jobs})==len(jobs)
    for j in jobs:
        assert j['seed'] in p['validation_seeds']
        assert j['kind']=='eval' and j['split']=='validation'
    write_json(RUN/'validation-manifest.json',jobs)
    templates=[]
    for a in arms:
        for s in p['scenarios'] if a['scenario']=='mixed' else [a['scenario']]:
            for load in p['loads'] if a['family'] in ['A','G'] else ['base']:
                for seed in p['test_seeds']:
                    templates.append(dict(model=a['id'],scenario=s,load=load,seed=seed,selection='vehicle',conditional=a['conditional']))
                    if a['family']=='A':templates.append(dict(model=a['id'],scenario=s,load=load,seed=seed,selection='validation_phase_table',conditional=False))
            if a['family'] in ['A','E']:
                for seed in p['test_seeds']:templates.append(dict(model=a['id'],scenario=s,load='base',seed=seed,selection='joint_if_distinct_checkpoint_and_nonzero_denominators',conditional=a['conditional']))
    for s in p['scenarios']:
        for load in p['loads']:
            for seed in p['test_seeds']:
                for b in ['timer','script','fixed30','fixed_validation_selected_if_not_30']:
                    templates.append(dict(model=b,scenario=s,load=load,seed=seed,selection='baseline',conditional=False))
    write_json(RUN/'test-templates.json',templates)
    counts=collections.Counter(a['family'] for a in initial)
    report=dict(status='static_checks_passed',simulations_started=False,training_started=False,
      compiled_python_files=len(files),initial_arms=len(initial),new_training=114,imported_training=6,conditional_arms=156,
      initial_by_family=dict(counts),validation_jobs_including_all_potential_expansions=len(jobs),
      runtime_checks='Deferred until explicit start: smoke, simulation drain/metrics, benchmark, demand generation',
      code_hashes={f.name:sha(f) for f in files},protocol_sha256=sha(RUN/'protocol.json'),manifest_sha256=sha(RUN/'manifest.json'))
    write_json(ROOT/'preflight.json',report);print(json.dumps(report,indent=2))
if __name__=='__main__':main()
