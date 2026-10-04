"""Mechanical adaptation of the audited earlier evaluator; does not run it."""
from pathlib import Path
ROOT=Path(__file__).resolve().parent
old=(ROOT.parent/'repeatability-sumo/worker.py').read_text(encoding='utf-8')
code=old[old.index('def evaluate('):old.index("if __name__=='__main__':")]
code=code.replace("    from controllers.timer_controller", "    raw_vector = ai.state_to_vector\n    from variants import install\n    install(task,td,ta,ai,ac,torch,np)\n    from controllers.timer_controller",1)
code=code.replace("task['duration']","task.get('duration',30)")
code=code.replace('        applied = original_safety(duration,state,sim_time,last_green,phase)',"        if task.get('table'): duration = task['table'].get(state['intersection_id'],{}).get(str(phase),task['duration'])\n        applied = original_safety(duration,state,sim_time,last_green,phase)")
code=code.replace('vector=vec.tolist(),proposed=',"raw_vector=raw_vector(state).tolist(),vector=vec.tolist(),entropy=float(-sum(x*np.log(max(x,1e-300)) for x in scores)) if mode=='a2c' else None,proposed=")
code=code.replace('    name = task.get(\'scenario\',f"day_cycle_s{task[\'seed\']}")', "    name = task['demand_name']")
code=code.replace('Path(config.SCENARIOS_DIR)',"run/task.get('demand_folder','demand')")
code=code.replace("demand_end = 1200 if name.startswith('balanced') else 3600","demand_end = 3600 if name.startswith('day_cycle') else 1200")
code=code.replace("start = time.perf_counter(); observed={}; steps=0","start = time.perf_counter(); observed={}; steps=0; t=0; departed=set(); arrived=set(); teleports=0; collisions=0")
code=code.replace("'--no-step-log','true','--no-warnings','true'])","'--seed',str(protocol['sumo_seed']),'--no-step-log','true','--no-warnings','true'])")
code=code.replace('            for j in config.CONTROLLED_JUNCTIONS:', '            departed.update(traci.simulation.getDepartedIDList()); arrived.update(traci.simulation.getArrivedIDList())\n            teleports += traci.simulation.getStartingTeleportNumber(); collisions += traci.simulation.getCollidingVehiclesNumber()\n            for j in config.CONTROLLED_JUNCTIONS:')
code=code.replace('active_persons=len(traci.person.getIDList())',"stage='drain' if t>=demand_end else ('day-'+str(sum(t>=b for b in [600,1200,1800,2700])) if demand_end==3600 else 'demand'),active_persons=len(traci.person.getIDList())")
code=code.replace("    waits=[float(v.get('waitingTime')) for v in trips]","    assert departed==expected_ids and arrived==expected_ids,'Departed/arrived demand mismatch'\n    waits=[float(v.get('waitingTime')) for v in trips]\n    for metric,field in [('avg_travel_time','duration'),('avg_stops_per_vehicle','waitingCount')]:\n        assert abs(sum(float(v.get(field,0)) for v in trips)/len(trips)-summary[metric])<1e-10")
code=code.replace("result=dict(status='passed',summary=summary", "result=dict(status='passed',task=task,created_vehicles=len(expected_ids),departed_vehicles=len(departed),arrived_vehicles=len(arrived),unfinished_vehicles=len(expected_ids-arrived),teleports=teleports,colliding_vehicles=collisions,summary=summary")
head="""# Generated from prior evaluator by build_evaluator.py; isolated imports initialized per task.
import sys,time,json,os,traceback
from pathlib import Path
from worker import read_json,write_json,sha
"""
tail="""
if __name__=='__main__':
    import worker
    run=Path(sys.argv[1]);task=read_json(run/'tasks'/f'{sys.argv[2]}.json');protocol=read_json(run/'protocol.json')
    try:
        if task.get('split')=='test':assert (run/'test-gate.json').exists(),'Test gate closed'
        worker.initialize(run)
        for key in ['torch','np','traci','config','state_builder','dc','ai','ac','td','ta','metrics']:globals()[key]=getattr(worker,key)
        evaluate(run,task,protocol)
    except Exception:
        write_json(run/'failed'/f'{task["id"]}.json',dict(status='failed',error=traceback.format_exc(),time=time.time()))
        traceback.print_exc();sys.exit(1)
"""
compile(head+code+tail,'evaluator.py','exec')
(ROOT/'evaluator.py').write_text(head+code+tail,encoding='utf-8')
