# SUMO Traffic-Light Control — AI vs. Rule-Based Comparison

Final project for the Industrial Engineering & Management degree at HIT.
Compares four traffic-light controllers on a 4×3 SUMO grid network across six traffic scenarios.

## Controllers

| Controller | Type | Description |
|---|---|---|
| **TIMER** | Fixed-time | Fixed 30s green cycles, no sensing |
| **SCRIPT** | Rule-based | Extends green when queue > threshold |
| **DQN** | Deep RL (off-policy) | Double DQN, experience replay, stop-penalty reward |
| **A2C** | Deep RL (on-policy) | Actor-Critic with entropy bonus, no replay buffer |

## Scenarios

`balanced` · `heavy_west` · `morning_flow` · `evening_flow` · `pedestrian_heavy` · `day_cycle`

## Experiment Protocol

- **20 training seeds** (1–20) per controller × scenario
- **5 evaluation seeds** (201–205) per model
- **120 total runs** (6 scenarios × 4 controllers × 5 test seeds)
- State vector: 17 features (queue length, wait time, arrivals × 4 directions + 3 signal + 2 pedestrian)

## Folder Layout

```
sim/
  controllers/
    timer_controller.py       # fixed-time baseline
    script_controller.py      # rule-based
    ai_controller.py          # DQN (Double DQN, off-policy)
    a2c_controller.py         # A2C (Actor-Critic, on-policy)
  scenarios/                  # per-seed .rou.xml and .ped.xml files
  models/                     # trained .pt weight files for all 12 ML models
  results/                    # JSON results + RESULTS.md summary
  run_experiment.py           # single-seed run
  eval_multiseed.py           # multi-seed evaluation harness
sim/scenarios/net/            # SUMO 4×3 network files
run_multiseed_eval.bat        # convenience launcher for full eval sweep
PROGRESS.md                   # full engineering history: failures, iterations, re-runs
```

## Setup

```bash
pip install eclipse-sumo traci sumolib torch numpy
```

Set `SUMO_HOME` to your SUMO Python package path (e.g. the `sumo` folder inside `site-packages`).

## Running

Single scenario (one seed):
```bash
python sim/run_experiment.py --mode dqn --scenario balanced --seed 1
```

Full multi-seed evaluation:
```bash
run_multiseed_eval.bat
```

Or directly:
```bash
python sim/eval_multiseed.py --modes timer script dqn a2c --scenarios balanced heavy_west morning_flow evening_flow pedestrian_heavy day_cycle
```

## Results

See `sim/results/RESULTS.md` and `sim/results/RESULTS_MULTISEED.md` for full tables.
DQN and A2C consistently outperform TIMER and SCRIPT on average wait time across all scenarios.

## Engineering Notes

The project went through three complete re-runs of the experiment suite due to:
- A pedestrian model bug (`--pedestrian.model nonInteracting` zeroed all pedestrian metrics)
- DQN v1 "rapid cycling" failure fixed by adding a stop penalty and revised action space
- Upgrade from single-seed to multi-seed protocol (24 → 120 runs)

See `PROGRESS.md` for the full story.
