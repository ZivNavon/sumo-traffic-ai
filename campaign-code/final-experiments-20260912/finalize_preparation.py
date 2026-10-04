"""Save preparation metadata only; never starts experiment processes."""
from pathlib import Path
from worker import read_json,write_json
ROOT=Path(__file__).resolve().parent;RUN=ROOT/'campaign'
p=read_json(RUN/'protocol.json')
p.update(seed_audit='Passed: input-audit.json; 560 historical XML demand names plus protocol splits inspected; no proposed seed overlap',
  import_gate='Passed: six current day_cycle runs, all 18 checkpoints copied and hash checked; code and all demand schedule entries matched',
  evaluation_gate='Implemented; runtime smoke tests required after explicit user start',
  benchmark_capacities=[4,6,8,10,12,16],benchmark_jobs_per_capacity=16,benchmark_episodes_per_job=3,
  benchmark_increase_rule='Above 8 only if throughput improved >3% and previous minimum free memory >=25%; select highest throughput improvement >3% with >=20% free memory',
  max_workers='Selected by benchmark; admission checks free RAM and disk; below-normal process priority',
  runtime_status='NOT STARTED: user explicitly requested preparation only',
  demand_generation=dict(heavy_west='Training XML unchanged. Fresh evaluation flow materialized before simulation using Python Random(demand_seed+1000000), Bernoulli p=0.5 at each integer second 0..1199. This is a new frozen demand realization, not an exact replay of historical SUMO RNG.',
    scaling='Within each route and day phase, deterministically hash-rank individuals by seed:id, retain or duplicate to floor(N*factor+0.5). Duplicates retain departure time/route. Unchanged population is byte-identical. Record actual counts and hashes. Training demand not scaled.',
    test_seeds=20,validation_seeds=10),
  pause_behavior='STOP prevents new tasks; active training saves full resume and exits at next 10-episode checkpoint; active evaluations finish',
  resource_watch='Each scheduler loop samples free RAM and disk; no new launch under 20% RAM reserve plus 0.75 GiB launch allowance or 20 GiB disk reserve',
  execution_priority='Below normal; Torch, MKL, OpenBLAS and OMP each one thread per worker')
write_json(RUN/'protocol.json',p)
m=read_json(RUN/'manifest.json');m['status']='Prepared: all initial and possible conditional training arms explicit; validation manifest explicit; test matrix deterministic in matrix.py and frozen plan. Runtime gates deferred until user starts.'
write_json(RUN/'manifest.json',m)
print('Preparation metadata saved; no runtime started.')
