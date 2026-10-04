"""Isolated SUMO worker. Scientific behavior is inherited from the source snapshot."""
import os, sys, json, time, random, hashlib, argparse, traceback
from pathlib import Path
sys.dont_write_bytecode = True
os.environ.update(OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1')

def replace_with_retry(source, target):
    # Windows readers/scanners can briefly prevent replacement of an open file.
    # Keep the previous complete file visible; fail explicitly after ~12 seconds.
    for attempt in range(16):
        try:
            os.replace(source, target)
            return
        except PermissionError:
            if attempt == 15:
                raise
            time.sleep(min(0.05 * 2 ** attempt, 1.0))

def write_json(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, indent=2, allow_nan=False), encoding='utf-8')
    replace_with_retry(temp, path)

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def read_json(path):
    for attempt in range(16):
        try:
            return json.loads(Path(path).read_text(encoding='utf-8'))
        except PermissionError:
            if attempt == 15: raise
            time.sleep(min(.05 * 2 ** attempt, 1.0))

def initialize(run):
    global torch, np, traci, config, state_builder, dc, ai, ac, td, ta, metrics
    import sumo
    os.environ['SUMO_HOME'] = str(Path(sumo.__file__).parent)
    sys.path.insert(0, str(run/'snapshot/sim'))
    import torch, numpy as np, traci
    from modules import config, state_builder, data_collection as dc, metrics
    from controllers import ai_controller as ai, a2c_controller as ac
    import train_dqn as td, train_a2c as ta
    torch.set_num_threads(1); torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    original_start=traci.start
    def seeded_start(command,*args,**kwargs):
        command=list(command)
        if '--seed' not in command:command+=['--seed',str(read_json(run/'protocol.json')['sumo_seed'])]
        return original_start(command,*args,**kwargs)
    traci.start=seeded_start

def save_torch(path, value):
    tmp = path.with_suffix('.tmp'); torch.save(value, tmp); replace_with_retry(tmp, path)

def pedestrian_count():
    # Same local stopped-person proxy as the original constraints, counted once.
    return sum(traci.person.getSpeed(p) < .1 and any(j in traci.person.getRoadID(p)
        for j in config.CONTROLLED_JUNCTIONS) for p in traci.person.getIDList())

def train(run, task, protocol):
    algorithm, variant = task['algorithm'], task['variant']
    protocol = dict(protocol, episodes=task.get('episodes', protocol['episodes']), checkpoints=task.get('checkpoints', protocol['checkpoints']))
    from guard import stopping
    from variants import install
    install(task, td, ta, ai, ac, torch, np)
    reward_variant = variant if variant in ('vehicle_seconds', 'vehicle_seconds_no_stops', 'pedestrians') else 'current'
    folder = run/'training'/task['id']; folder.mkdir(parents=True, exist_ok=True)
    learning_seed = task.get('learning_seed', protocol.get('learning_seed'))
    random.seed(learning_seed); np.random.seed(learning_seed)
    torch.manual_seed(learning_seed)
    mod = td if algorithm == 'dqn' else ta
    agent = td.DQNAgent() if algorithm == 'dqn' else None
    net = agent.online if agent else ac.ActorCritic()
    optimizer = agent.optimizer if agent else torch.optim.Adam(net.parameters(), lr=ta.LR)
    resume = folder/'resume.pt'; start_ep = 1
    if not resume.exists():
        initial = folder/'initial.pt'
        if not initial.exists():
            save_torch(initial,net.state_dict())
            write_json(folder/'initial.json',dict(fresh_initialization=True,learning_seed=learning_seed,
                sha256=sha(initial),time=time.time()))
    if resume.exists():
        # Trusted full checkpoint created only by this worker in this campaign.
        state = torch.load(resume, map_location='cpu', weights_only=False)
        net.load_state_dict(state['network']); optimizer.load_state_dict(state['optimizer'])
        if agent:
            agent.target.load_state_dict(state['target']); agent.epsilon = state['epsilon']
            agent.buffer.buf.extend(state['replay'])
        random.setstate(state['python_rng']); np.random.set_state(state['numpy_rng'])
        torch.set_rng_state(state['torch_rng']); start_ep = state['episode'] + 1
    # A separate deterministic demand schedule prevents algorithm/action RNG from
    # changing which demand seed each reward arm receives.
    demand_rng = random.Random(protocol['demand_schedule_seed'])
    schedule = [demand_rng.choice(protocol['train_seeds']) for _ in range(protocol['episodes'])]
    original_wait = mod._total_waiting_time
    original_stops = mod._count_new_stops
    components = {}; stopped = set()
    def stops(previous):
        nonlocal stopped
        n, stopped = original_stops(previous)
        components['new_stops'] += n
        return n, stopped
    def wait():
        if reward_variant == 'current':
            value = original_wait()
        else:
            value = len(stopped)
        ped = pedestrian_count() if reward_variant == 'pedestrians' else 0
        components['vehicle_term'] += value; components['pedestrian_term'] += ped
        return value + protocol['pedestrian_weight'] * ped
    mod._count_new_stops = stops; mod._total_waiting_time = wait
    mod.STOP_PENALTY = 0.0 if variant == 'vehicle_seconds_no_stops' else protocol['stop_weight']
    original_step = traci.simulationStep
    episode = 0; steps = 0; episode_start = 0; durations = []
    update_count = 0
    if agent:
        original_train = agent.train_step
        def counted_train():
            nonlocal update_count
            loss = original_train()
            if loss is not None: update_count += 1
            return loss
        agent.train_step = counted_train
    def step(*a, **kw):
        nonlocal steps
        result = original_step(*a, **kw); steps += 1
        if steps > protocol['max_simulation_steps']:
            raise RuntimeError('Simulation step limit exceeded; episode rejected')
        if steps % 300 == 0:
            write_json(folder/'progress.json', {'state':'running','episode':episode,
                'completed_episodes':episode-1,'steps_current_episode':steps,
                'updated_at':time.time(),'mean_episode_seconds':sum(durations[-10:])/len(durations[-10:]) if durations else None})
        return result
    traci.simulationStep = step
    for episode in range(start_ep, protocol['episodes']+1):
        if stopping('train'): raise SystemExit(75)
        steps = 0; update_count = 0; components = dict(vehicle_term=0.,new_stops=0,pedestrian_term=0)
        episode_start = time.perf_counter()
        scenario_base = task["scenario"]
        if scenario_base == "mixed": scenario_base = protocol["scenarios"][(episode-1) % 6]
        scenario = f"{scenario_base}_s{schedule[(episode-1)//6 if task["scenario"] == "mixed" else episode-1]}"
        demand_end = 3600 if scenario_base == "day_cycle" else 1200
        if agent:
            reward, decisions = td.run_episode(agent, scenario, demand_end)
            agent.decay_epsilon()
            if episode % td.TARGET_UPDATE == 0: agent.update_target()
            from variants import diagnostics
            diagnostic=diagnostics();loss=diagnostic.get('loss')
            write_json(folder/'diagnostics'/f'{episode:04d}.json',dict(diagnostic,aggregation='mean of per-minibatch statistics',gradient_clipping=False,learning_rate=optimizer.param_groups[0]['lr']))
        else:
            trajectories, reward = ta.run_episode(net, scenario, demand_end)
            decisions = sum(len(t) for t in trajectories.values())
            diagnostic = {'actor_loss':[], 'critic_loss':[], 'entropy':[], 'mean_abs_return':[], 'mean_abs_advantage':[]}
            with torch.no_grad():
                for trajectory in trajectories.values():
                    if not trajectory: continue
                    states=torch.tensor(np.array([s.state for s in trajectory]),dtype=torch.float32)
                    actions=torch.tensor([s.action for s in trajectory])
                    returns=torch.tensor(ta.compute_returns([s.reward for s in trajectory],ta.GAMMA),dtype=torch.float32)
                    logits,values=net(states);dist=torch.distributions.Categorical(logits=logits)
                    advantage=returns-values
                    if variant=='normalized_advantage':advantage=(advantage-advantage.mean())/(advantage.std(unbiased=False)+1e-8)
                    diagnostic['actor_loss'].append(float(-(dist.log_prob(actions)*advantage).mean()))
                    diagnostic['critic_loss'].append(float(((returns-values)**2).mean()))
                    diagnostic['entropy'].append(float(dist.entropy().mean()))
                    diagnostic['mean_abs_return'].append(float(returns.abs().mean()))
                    diagnostic['mean_abs_advantage'].append(float(advantage.abs().mean()))
            clip=torch.nn.utils.clip_grad_norm_
            def recorded_clip(parameters,*a,**kw):
                parameters=list(parameters);norm=clip(parameters,*a,**kw)
                diagnostic['gradient_norm_before_clip']=[float(norm)]
                diagnostic['gradient_norm_after_clip']=[float(torch.sqrt(sum((p.grad**2).sum() for p in parameters if p.grad is not None)))]
                return norm
            torch.nn.utils.clip_grad_norm_=recorded_clip
            loss = ta.update(net, optimizer, trajectories); update_count = int(loss is not None)
            torch.nn.utils.clip_grad_norm_=clip
            write_json(folder/'diagnostics'/f'{episode:04d}.json',
                {k:sum(v)/len(v) if v else None for k,v in diagnostic.items()})
        if not all(torch.isfinite(p).all().item() for p in net.parameters()):
            raise RuntimeError('Nonfinite network parameters')
        duration = time.perf_counter()-episode_start; durations.append(duration)
        row = dict(sumo_seed=protocol['sumo_seed'],epsilon_decay=td.EPS_DECAY,scenario=scenario_base,learning_seed=learning_seed,episode=episode,demand_seed=schedule[(episode-1)//6 if task['scenario']=='mixed' else episode-1],total_reward=reward,
            loss=loss,wall_seconds=duration,simulation_steps=steps,decisions=decisions,
            decision_count_definition='all decisions' if agent else 'stored decisions excluding final pending intervals',
            learning_updates=update_count,learning_rate=optimizer.param_groups[0]['lr'],epsilon=agent.epsilon if agent else None,**components)
        write_json(folder/'episodes'/f'{episode:04d}.json',row)
        if True:  # Save every completed episode; no RNG or optimizer change.
            full = dict(episode=episode,network=net.state_dict(),optimizer=optimizer.state_dict(),
                python_rng=random.getstate(),numpy_rng=np.random.get_state(),torch_rng=torch.get_rng_state())
            if agent: full.update(target=agent.target.state_dict(),epsilon=agent.epsilon,replay=list(agent.buffer.buf))
            save_torch(resume,full)
        if episode in protocol['checkpoints']:
            checkpoint = folder/f'checkpoint-{episode}.pt'
            save_torch(checkpoint,net.state_dict())
            write_json(folder/f'checkpoint-{episode}.json',dict(episode=episode,sha256=sha(checkpoint),
                selection='scheduled snapshot; not selected by training reward'))
        remaining = (protocol['episodes']-episode)*sum(durations[-10:])/len(durations[-10:])
        write_json(folder/'progress.json',dict(state='complete' if episode == protocol['episodes'] else 'running',
            completed_episodes=episode,episode=episode,updated_at=time.time(),
            mean_episode_seconds=sum(durations[-10:])/len(durations[-10:]),estimated_remaining_seconds=remaining))
        print(f"{task['id']} episode {episode}/{protocol['episodes']} {duration:.1f}s reward {reward:.1f}",flush=True)
        if stopping('train') and episode < protocol['episodes']:
            write_json(folder/'progress.json',dict(state='paused',episode=episode,completed_episodes=episode,updated_at=time.time()))
            raise SystemExit(75)
    write_json(run/'completed'/f"{task['id']}.json",dict(status='passed',episodes=protocol['episodes']))

def evaluate(run, task, protocol):
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
                v = torch.zeros((len(x),5)); v[:,ai.ACTIONS.index(task['duration'])]=1
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
                vector=vec.tolist(),proposed=duration,applied=applied,changed=duration!=applied,
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
    name = task.get('scenario',f"day_cycle_s{task['seed']}")
    route = Path(config.SCENARIOS_DIR)/f'{name}.rou.xml'; ped = Path(config.SCENARIOS_DIR)/f'{name}.ped.xml'
    demand_end = 1200 if name.startswith('balanced') else 3600
    collector = metrics.MetricsCollector(mode_name='ai' if mode=='dqn' else mode,scenario_name=name)
    start = time.perf_counter(); observed={}; steps=0
    traci.start([sumolib.checkBinary('sumo'),'-n',config.NET_FILE,'-r',f'{route},{ped}',
        '-b','0','-e',str(demand_end),'--tripinfo-output',str(folder/'tripinfo.xml'),
        '--no-step-log','true','--no-warnings','true'])
    try:
        while traci.simulation.getMinExpectedNumber()>0:
            traci.simulationStep(); steps+=1; t=traci.simulation.getTime()
            if steps>protocol['max_simulation_steps']: raise RuntimeError('Evaluation simulation did not drain within limit')
            for j in config.CONTROLLED_JUNCTIONS:
                phase=traci.trafficlight.getPhase(j)
                if observed.get(j,(None,0))[0]!=phase:
                    prev,at=observed.get(j,(None,t))
                    phases.write(json.dumps(dict(time=t,junction=j,phase=phase,previous_phase=prev,
                        completed_duration=t-at if prev is not None else None))+'\n')
                    observed[j]=(phase,t)
            controller.step(t); collector.step()
            if steps%300==0:
                write_json(folder/'progress.json',dict(state='running',updated_at=time.time(),simulation_steps=steps))
            if steps%60==0 and task.get('logging',True):
                local={j:{d:dc.queue_length(e) for d,e in approaches.items()} for j,approaches in
                    [(config.J1_ID,config.J1_APPROACHES),(config.J2_ID,config.J2_APPROACHES)]}
                series.write(json.dumps(dict(time=t,queues=local,active_vehicles=len(traci.vehicle.getIDList()),
                    active_persons=len(traci.person.getIDList())))+'\n')
        simulation_end=t
    finally:
        sys.setprofile(None)
        traci.close(); trace.close();series.close();phases.close()
    summary=collector.finalize(str(folder/'tripinfo.xml'),sim_time=demand_end)
    import xml.etree.ElementTree as ET
    root=ET.parse(folder/'tripinfo.xml').getroot(); trips=root.findall('tripinfo'); persons=root.findall('personinfo')
    expected_ids={v.get('id') for v in ET.parse(route).getroot().findall('vehicle')}
    expected_peds={v.get('id') for v in ET.parse(ped).getroot().findall('person')}
    assert {v.get('id') for v in trips}==expected_ids and len(trips)==len(expected_ids),'Incomplete vehicle arrivals'
    assert {v.get('id') for v in persons}==expected_peds and len(persons)==len(expected_peds),'Incomplete pedestrian arrivals'
    assert all(v.get('vaporized','') in ('','false','0') for v in trips),'Removed vehicles'
    waits=[float(v.get('waitingTime')) for v in trips]
    assert abs(sum(waits)/len(waits)-summary['avg_waiting_time'])<1e-10
    if model: assert model_hash==sha(model),'Evaluation changed weights'
    result=dict(status='passed',summary=summary,weight_sha256=model_hash,
        demand_end_s=demand_end,simulation_end_s=simulation_end,wall_elapsed_s=time.perf_counter()-start,
        simulation_steps=steps,vehicle_count=len(trips),person_count=len(persons),
        p95_vehicle_wait=float(np.percentile(waits,95)),
        input_hashes={str(p):sha(p) for p in [route,ped,Path(config.NET_FILE)]})
    write_json(folder/'result.json',result); write_json(run/'completed'/f"{task['id']}.json",result)
    write_json(folder/'progress.json',dict(state='complete',updated_at=time.time(),simulation_steps=steps))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('run');parser.add_argument('task')
    args=parser.parse_args();run=Path(args.run).resolve()
    task=read_json(run/'tasks'/f'{args.task}.json');protocol=read_json(run/'protocol.json')
    try:
        assert task['kind'] == 'train', 'Evaluation gate: use audited evaluator only'
        from guard import check
        check(run,task)
        initialize(run)
        (train if task['kind']=='train' else evaluate)(run,task,protocol)
    except Exception:
        write_json(run/'failed'/f"{task['id']}.json",dict(status='failed',error=traceback.format_exc(),time=time.time()))
        traceback.print_exc();sys.exit(1)
