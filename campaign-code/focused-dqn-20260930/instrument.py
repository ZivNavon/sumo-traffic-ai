"""Apply documented infrastructure additions to isolated copies only, before runs."""
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def edit(name,old,new):
    p=ROOT/name;s=p.read_text(encoding='utf-8');assert s.count(old)==1,(name,old,s.count(old));p.write_text(s.replace(old,new),encoding='utf-8')
def main():
    edit('variants.py',"v=task['variant']","v=task['variant']\n    assert td.LR == .001 and td.EPS_DECAY == .997\n    if v == 'lr0003': td.LR = .0003\n    elif v == 'eps998': td.EPS_DECAY = .998")
    edit('worker.py',"from variants import install\n    install", "from guard import stopping\n    from variants import install\n    install")
    edit('worker.py',"for episode in range(start_ep, protocol['episodes']+1):", "for episode in range(start_ep, protocol['episodes']+1):\n        if stopping('train'): raise SystemExit(75)")
    edit('worker.py',"if episode % 10 == 0 or episode in protocol['checkpoints'] or episode == 1:","if True:  # Save every completed episode; no RNG or optimizer change.")
    edit('worker.py',"if (Path(__file__).parent/'STOP').exists() and episode % 10 == 0:","if stopping('train') and episode < protocol['episodes']:")
    edit('worker.py',"row = dict(scenario=scenario_base,learning_seed=learning_seed,", "row = dict(sumo_seed=protocol['sumo_seed'],epsilon_decay=td.EPS_DECAY,scenario=scenario_base,learning_seed=learning_seed,")
    edit('worker.py',"initialize(run)\n        (train", "from guard import check\n        check(run,task)\n        initialize(run)\n        (train")
    # Per-step samples permit independent reconstruction of queue and pedestrian proxy.
    edit('evaluator.py',"controller.step(t); collector.step()", "controller.step(t); collector.step()\n            samples.write(json.dumps(dict(time=t,queue=collector.queue_samples[-1],pedestrian=collector.pedestrian_wait_samples[-1]))+'\\n')")
    edit('evaluator.py',"start = time.perf_counter();", "samples=(folder/'metric-samples.jsonl').open('w',encoding='utf-8')\n    start = time.perf_counter();")
    edit('evaluator.py',"traci.close(); trace.close();series.close();phases.close()", "write_json(folder/'completion-observation.json',dict(departed=len(departed),arrived=len(arrived),departed_not_arrived=sorted(departed-arrived),teleports=teleports,colliding_vehicles=collisions,simulation_steps=steps))\n        traci.close(); trace.close();series.close();phases.close();samples.close()")
    edit('evaluator.py',"worker.initialize(run)","from guard import check\n        check(run,task)\n        worker.initialize(run)")
    # Explicit deadline in evaluations, always through traci.close finally.
    edit('evaluator.py',"traci.simulationStep(); steps+=1; t=traci.simulation.getTime()", "from guard import stopping\n            if steps % 100 == 0 and stopping('eval'): raise RuntimeError('Evaluation stopped at campaign deadline/STOP; incomplete')\n            traci.simulationStep(); steps+=1; t=traci.simulation.getTime()")
if __name__=='__main__':main()
