# Generated from prior evaluator by build_evaluator.py; isolated imports initialized per task.
import sys,time,json,os,traceback
from pathlib import Path
from worker import read_json,write_json,sha
def evaluate(run, task, protocol):
    raw_vector = ai.state_to_vector
    from variants import install
    install(task,td,ta,ai,ac,torch,np)
    from controllers.timer_controller import TimerController
    from controllers.script_controller import ScriptController
    import sumolib
    folder = run/'evaluations'/task['id']; folder.mkdir(parents=True,exist_ok=True)
    mode = task['algorithm']; model = run/task['weights'] if task.get('weights') else None
    model_hash = None
    if model:
        if not model.is_file(): raise FileNotFoundError(model)
        model_hash = sha(model)
        if task.get('expected_weight_sha256'):
            assert model_hash == task['expected_weight_sha256'], 'Selected model identity mismatch'
    if mode == 'dqn': controller = ai.AiController(config.CONTROLLED_JUNCTIONS,weights_path=str(model))
    elif mode == 'a2c': controller = ac.A2CController(config.CONTROLLED_JUNCTIONS,weights_path=str(model))
    elif mode == 'timer': controller = TimerController(config.CONTROLLED_JUNCTIONS)
    elif mode == 'script': controller = ScriptController(config.CONTROLLED_JUNCTIONS)
    else:
        class Fixed(torch.nn.Module):
            def forward(self,x):
                v = torch.zeros((len(x),5)); v[:,ai.ACTIONS.index(task.get('duration',30))]=1
                return v
        controller = ai.AiController.__new__(ai.AiController)
        controller.junction_ids = config.CONTROLLED_JUNCTIONS
        controller._last_seen_phase = {j:None for j in config.CONTROLLED_JUNCTIONS}
        controller._last_green_time = {j:{0:0.,3:0.} for j in config.CONTROLLED_JUNCTIONS}
        controller.q_net = Fixed()
    trace = (folder/'decisions.jsonl').open('w',encoding='utf-8')
    series = (folder/'series.jsonl').open('w',encoding='utf-8')
    phases = (folder/'phases.jsonl').open('w',encoding='utf-8')
    original_safety = ai._apply_safety
    def safety(duration,state,sim_time,last_green,phase):
        if task.get('table'): duration = task['table'].get(state['intersection_id'],{}).get(str(phase),task['duration'])
        applied = original_safety(duration,state,sim_time,last_green,phase)
        vec = ai.state_to_vector(state)
        with torch.no_grad():
            if mode == 'a2c': scores = torch.softmax(controller.net(torch.tensor(vec).unsqueeze(0))[0],-1)[0].tolist()
            elif mode == 'dqn': scores = controller.q_net(torch.tensor(vec).unsqueeze(0))[0].tolist()
            else: scores = None
        p = state['pedestrians']; reasons=[]
        if sim_time-last_green.get(3 if phase==0 else 0,0)>config.STARVATION_THRESHOLD: reasons.append('starvation_threshold')
        if p['waiting'] and p['max_waiting_time']>config.PEDESTRIAN_FORCE_THRESHOLD: reasons.append('pedestrian_max')
        elif p['waiting'] and p['average_waiting_time']>config.PEDESTRIAN_WAIT_THRESHOLD: reasons.append('pedestrian_average')
        if task.get('logging',True):
            trace.write(json.dumps(dict(time=sim_time,junction=state['intersection_id'],phase=phase,
                raw_vector=raw_vector(state).tolist(),vector=vec.tolist(),entropy=float(-sum(x*np.log(max(x,1e-300)) for x in scores)) if mode=='a2c' else None,proposed=duration,applied=applied,changed=duration!=applied,
                triggered_rules=reasons,scores=scores))+'\n')
        return applied
    ai._apply_safety = safety; ac._apply_safety = safety
    # Observe SCRIPT locals at function return, without editing its decision code.
    # TIMER has no agent decisions; its automatic cycle is recorded in phases.jsonl.
    def script_profile(frame,event,arg):
        if event != 'return' or frame.f_code.co_filename != sys.modules[ScriptController.__module__].__file__: return
        v=frame.f_locals; name=frame.f_code.co_name
        if name == '_decide_duration':
            module=sys.modules[ScriptController.__module__]
            raw=config.DEFAULT_GREEN if v['total']<=0 or abs(v['load_current']-v['load_other'])/v['total']<config.LOAD_DEADBAND else module.bucket_duration(v['load_current']/v['total'])
            state=v['state'];ped=state['pedestrians'];reasons=[]
            if v['time_since_other_green']>config.STARVATION_THRESHOLD:reasons.append('starvation_threshold')
            if ped['waiting'] and ped['max_waiting_time']>config.PEDESTRIAN_FORCE_THRESHOLD:reasons.append('pedestrian_max')
            elif ped['waiting'] and ped['average_waiting_time']>config.PEDESTRIAN_WAIT_THRESHOLD:reasons.append('pedestrian_average')
            trace.write(json.dumps(dict(time=v['sim_time'],junction=v['jid'],phase=v['phase'],vector=ai.state_to_vector(state).tolist(),
                proposed=raw,applied=v['duration'],changed=raw!=v['duration'],triggered_rules=reasons,scores=None,
                proposal_definition='after load/downstream/coordination/deadband, before safety clamps'))+'\n')
        elif name == '_check_starvation' and v['elapsed']>=config.MAX_GREEN_TIME and v['time_since_other_green']>config.STARVATION_THRESHOLD:
            trace.write(json.dumps(dict(time=v['sim_time'],junction=v['jid'],phase=v['phase'],proposed=None,applied=v['elapsed'],changed=None,
                triggered_rules=['mid_phase_starvation'],scores=None,event='mid_phase_safeguard'))+'\n')
    if mode == 'script' and task.get('logging',True):sys.setprofile(script_profile)
    name = task['demand_name']
    route = run/task.get('demand_folder','demand')/f'{name}.rou.xml'; ped = run/task.get('demand_folder','demand')/f'{name}.ped.xml'
    demand_end = 3600 if name.startswith('day_cycle') else 1200
    collector = metrics.MetricsCollector(mode_name='ai' if mode=='dqn' else mode,scenario_name=name)
    samples=(folder/'metric-samples.jsonl').open('w',encoding='utf-8')
    start = time.perf_counter(); observed={}; steps=0; t=0; departed=set(); arrived=set(); teleports=0; collisions=0
    traci.start([sumolib.checkBinary('sumo'),'-n',config.NET_FILE,'-r',f'{route},{ped}',
        '-b','0','-e',str(demand_end),'--tripinfo-output',str(folder/'tripinfo.xml'),
        '--seed',str(protocol['sumo_seed']),'--no-step-log','true','--no-warnings','true'])
    try:
        while traci.simulation.getMinExpectedNumber()>0:
            from guard import stopping
            if steps % 100 == 0 and stopping('eval'): raise RuntimeError('Evaluation stopped at campaign deadline/STOP; incomplete')
            traci.simulationStep(); steps+=1; t=traci.simulation.getTime()
            if steps>protocol['max_simulation_steps']: raise RuntimeError('Evaluation simulation did not drain within limit')
            departed.update(traci.simulation.getDepartedIDList()); arrived.update(traci.simulation.getArrivedIDList())
            teleports += traci.simulation.getStartingTeleportNumber(); collisions += traci.simulation.getCollidingVehiclesNumber()
            for j in config.CONTROLLED_JUNCTIONS:
                phase=traci.trafficlight.getPhase(j)
                if observed.get(j,(None,0))[0]!=phase:
                    prev,at=observed.get(j,(None,t))
                    phases.write(json.dumps(dict(time=t,junction=j,phase=phase,previous_phase=prev,
                        completed_duration=t-at if prev is not None else None))+'\n')
                    observed[j]=(phase,t)
            controller.step(t); collector.step()
            samples.write(json.dumps(dict(time=t,queue=collector.queue_samples[-1],pedestrian=collector.pedestrian_wait_samples[-1]))+'\n')
            if steps%300==0:
                write_json(folder/'progress.json',dict(state='running',updated_at=time.time(),simulation_steps=steps))
            if steps%60==0 and task.get('logging',True):
                local={j:{d:dc.queue_length(e) for d,e in approaches.items()} for j,approaches in
                    [(config.J1_ID,config.J1_APPROACHES),(config.J2_ID,config.J2_APPROACHES)]}
                series.write(json.dumps(dict(time=t,queues=local,active_vehicles=len(traci.vehicle.getIDList()),
                    stage='drain' if t>=demand_end else ('day-'+str(sum(t>=b for b in [600,1200,1800,2700])) if demand_end==3600 else 'demand'),active_persons=len(traci.person.getIDList())))+'\n')
        simulation_end=t
    finally:
        sys.setprofile(None)
        try:
            import xml.etree.ElementTree as ET
            expected_count=len(ET.parse(route).getroot().findall('vehicle'))
            write_json(folder/'completion-observation.json',dict(created=expected_count,departed=len(departed),arrived=len(arrived),unfinished=expected_count-len(arrived),departed_not_arrived=sorted(departed-arrived),teleports=teleports,colliding_vehicles=collisions,simulation_steps=steps))
        finally:
            traci.close(); trace.close();series.close();phases.close();samples.close()
    summary=collector.finalize(str(folder/'tripinfo.xml'),sim_time=demand_end)
    import xml.etree.ElementTree as ET
    root=ET.parse(folder/'tripinfo.xml').getroot(); trips=root.findall('tripinfo'); persons=root.findall('personinfo')
    expected_ids={v.get('id') for v in ET.parse(route).getroot().findall('vehicle')}
    flows=ET.parse(route).getroot().findall('flow')
    if flows:
        assert task['split']=='smoke','Production evaluation demand must have explicit vehicles'
        flow_prefixes=tuple(f.get('id')+'.' for f in flows)
        expected_ids.update(v for v in departed if v.startswith(flow_prefixes))
    expected_peds={v.get('id') for v in ET.parse(ped).getroot().findall('person')}
    assert {v.get('id') for v in trips}==expected_ids and len(trips)==len(expected_ids),'Incomplete vehicle arrivals'
    assert {v.get('id') for v in persons}==expected_peds and len(persons)==len(expected_peds),'Incomplete pedestrian arrivals'
    assert all(v.get('vaporized','') in ('','false','0') for v in trips),'Removed vehicles'
    assert departed==expected_ids and arrived==expected_ids,'Departed/arrived demand mismatch'
    waits=[float(v.get('waitingTime')) for v in trips]
    for metric,field in [('avg_travel_time','duration'),('avg_stops_per_vehicle','waitingCount')]:
        assert abs(sum(float(v.get(field,0)) for v in trips)/len(trips)-summary[metric])<1e-10
    assert abs(sum(waits)/len(waits)-summary['avg_waiting_time'])<1e-10
    if model: assert model_hash==sha(model),'Evaluation changed weights'
    result=dict(status='passed',task=task,created_vehicles=len(expected_ids),departed_vehicles=len(departed),arrived_vehicles=len(arrived),unfinished_vehicles=len(expected_ids-arrived),teleports=teleports,colliding_vehicles=collisions,summary=summary,weight_sha256=model_hash,
        demand_end_s=demand_end,simulation_end_s=simulation_end,wall_elapsed_s=time.perf_counter()-start,
        simulation_steps=steps,vehicle_count=len(trips),person_count=len(persons),
        p95_vehicle_wait=float(np.percentile(waits,95)),
        input_hashes={str(p):sha(p) for p in [route,ped,Path(config.NET_FILE)]})
    write_json(folder/'result.json',result); write_json(run/'completed'/f"{task['id']}.json",result)
    write_json(folder/'progress.json',dict(state='complete',updated_at=time.time(),simulation_steps=steps))


if __name__=='__main__':
    import worker
    run=Path(sys.argv[1]);task=read_json(run/'tasks'/f'{sys.argv[2]}.json');protocol=read_json(run/'protocol.json')
    try:
        if task.get('split')=='test':assert (run/'test-gate.json').exists(),'Test gate closed'
        from guard import check
        check(run,task)
        worker.initialize(run)
        for key in ['torch','np','traci','config','state_builder','dc','ai','ac','td','ta','metrics']:globals()[key]=getattr(worker,key)
        evaluate(run,task,protocol)
    except Exception:
        write_json(run/'failed'/f'{task["id"]}.json',dict(status='failed',error=traceback.format_exc(),time=time.time()))
        traceback.print_exc();sys.exit(1)
