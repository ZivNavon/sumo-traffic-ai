<p align="center"><img src="docs/assets/hit-logo.png" alt="HIT — Holon Institute of Technology" width="420"></p>

# Traffic signal control with reinforcement learning

This final project was created by **Ofek and Ziv** for **HIT — Holon Institute of Technology**. It studies traffic signal control at two connected intersections in the SUMO simulator, with the aim of reducing vehicle and pedestrian waiting and unnecessary stops.

The project compares reinforcement learning controllers (DQN and A2C) with a fixed-time TIMER and a rule-based SCRIPT controller. Python code communicates with SUMO through TraCI to read traffic conditions, select green durations, and record performance across six traffic scenarios. The repository contains the simulation, controller implementations, training scripts, and experiment code.

The existing repository history and historical assets are preserved. The previous README is available at `docs/README-before-code-publication.md`; use the instructions below for the published source snapshot.

## Contents

| Path | Contents |
| --- | --- |
| `sim/controllers/` | DQN, A2C, SCRIPT, historical SCRIPTv0, and TIMER implementations. |
| `sim/modules/config.py` | Network paths, controlled intersections, timing thresholds and controller settings. |
| `sim/modules/` | State construction, traffic data collection and evaluation metrics. |
| `sim/network/grid.net.xml` | SUMO network and its default traffic-light program. |
| `sim/scenarios/` | Demand-generation scripts and original unseeded demand files for the six scenarios. |
| `sim/run_experiment.py` | Simulation loop that invokes controller decisions. |
| `sim/train_dqn.py`, `sim/train_a2c.py` | Original full training implementations. |
| `sim/eval_multiseed.py` | Original multi-seed evaluation entry point. |
| `campaign-code/final-experiments-20260912/` | Later campaign training, evaluation, demand generation, scheduling and analysis scripts. The fixed-duration controller is implemented in `evaluator.py`. |
| `campaign-code/focused-dqn-20260930/` | Separate focused DQN campaign: learning-rate and epsilon-decay alternatives, evaluation, integrity checks and analysis. |
| `campaign-metadata/` | Preserved protocol, source hashes and selection metadata; focused campaign scope and seed audit are in its named subdirectory. |
| `inventory.json`, `repository-file-hashes.json` | File provenance and SHA256 inventories. |
| `README-he.txt` | Hebrew source-package notes and provenance limitations. |

## Controller execution and timing limits

The DQN and A2C controllers propose green durations from their discrete action set. `sim/controllers/ai_controller.py` contains the shared `_apply_safety` function, which can constrain the applied duration; A2C imports this function. SCRIPT implements its own timing and starvation handling. TIMER's Python controller is a no-op: its signal program is defined in the network XML. A fixed-duration campaign controller also goes through the learned-controller safety path; it does not keep conflicting directions permanently green.

The source includes six demand scenarios: balanced, heavy west, pedestrian heavy, morning flow, evening flow and day cycle. See the preserved protocol files for campaign-specific training, checkpoint selection and evaluation settings.

## Setup and basic simulation

Install Python, PyTorch, NumPy, and SUMO. The SUMO `sumo` executable must be available on PATH. Set `SUMO_HOME` to your SUMO installation so that its Python tools and demand-generation utilities can be located. The Python syntax was checked with Python 3.12; this is not a claim that arbitrary dependency versions reproduce the historical environment.

```bash
python -m pip install -r requirements.txt
python sim/run_experiment.py --mode timer --scenario day_cycle
python sim/run_experiment.py --mode script --scenario day_cycle
```

These commands use the included unseeded demand inputs and write generated outputs under `sim/results/`. Learned-controller evaluation additionally requires the corresponding weight files in the location expected by the source. This repository already contains historical models and results from its previous commits. Those files are preserved, but their presence alone does not establish correspondence with every reported run. Additional campaign checkpoints and full raw outputs were archived separately.

The original training interfaces can be inspected without starting training:

```bash
python sim/train_dqn.py --help
python sim/train_a2c.py --help
```

Seeded training requires generating the appropriate demand files first. Inspect `sim/scenarios/gen_multiseed_scenarios.py` and the relevant campaign protocol before running a campaign. Do not treat the two commands above as reproductions of the held-out multi-seed experiments.

## Campaign code and reproducibility boundaries

`sim/` is copied unchanged from the preserved September 12 campaign snapshot and checked against the received original source. Campaign scripts are preserved separately; their experimental branches are not all baseline settings. The September 30 focused campaign tested LR=0.0003 and EPS_DECAY=0.998 separately, with three fresh training initializations per alternative. It did not establish a consistent improvement over the original DQN.

The campaign wrappers expect their original campaign directory layout, manifests, demands, checkpoints and result files. They are included for inspection and reconstruction, not as a ready-to-launch portable campaign installation. Original comments can be outdated; executable code and raw outputs are the evidence for behavior. No scientific implementation was changed for publication.

This snapshot verifies the preserved source for campaigns executed in this workspace. It does not establish a signed code revision for every historical run from the previous computer or resolve the historical weight-provenance limitation. A new Git commit records publication, not the original experiment date.

Results, checkpoints and raw evidence were archived separately in the [project results folder](https://drive.google.com/drive/folders/1TVKGlnPP1sBKft9mtiTXRHDFUrbsgvRD). This GitHub repository is the code-sharing location; the project report has not been edited by this upload.

## Verification

Before publication, copied source hashes were checked, the source archive passed CRC and content-hash checks, and every published Python file was parsed for syntax. No new training or simulation was launched as part of publication. The inventory files allow readers to check the exact source files; they do not certify model quality or resolve documented experimental limitations.


## Patch notes

- 2026-10-04: Added HIT final-project attribution to Ofek and Ziv and a concise overview of the system, objectives, and controllers.
- 2026-10-04: Added the HIT logo from the project book cover to the README.
