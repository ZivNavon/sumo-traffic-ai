# Smart Urban Intersection System — SUMO Progress Log

_Session work completed: 2026-06-13, finished ~20:06_
_Session 2 update: 2026-06-13, ~21:15_

## Session 2 summary (2026-06-13, ~21:15)

- Versioned the SCRIPT controller: `script_controller_v0.py` (`ScriptControllerV0`,
  mode `script_v0`) preserved as the original simple proportional controller
  for reference; `script_controller.py` (`ScriptController`, mode `script`)
  is **SCRIPT v1 — network-aware adaptive controller**, the production
  version (load calc, pedestrian priority, starvation prevention, min/max
  green, deadband, downstream-congestion penalty, J1<->J2 coordination,
  metrics). `run_experiment.py` and `REQUIREMENTS_CHECKLIST.md` updated
  accordingly.
- Reviewed current results (600s runs):
  - `heavy_west`: SCRIPT v1 beats TIMER on every metric (avg wait -24%,
    avg queue -28%, avg travel time -10%; stops and ped wait slightly worse).
  - `balanced`: SCRIPT v1 still trailing TIMER (avg wait 31.78s vs 27.94s;
    avg queue 5.00 vs 3.88) and **max_waiting_time got notably worse**
    (161s vs TIMER's 105s) — likely the deadband + bucketed durations
    letting one direction's queue build longer before kicking in. **Not
    yet investigated.**
- Next session: either dig into the `balanced` max-wait regression, or
  move on to AI mode (top open item per REQUIREMENTS_CHECKLIST.md §9).

This file tracks everything done in the SUMO/TraCI workspace at
`D:\Ziv - OS\Projects\Trafic AI`, prompt by prompt, so future sessions can
pick up context quickly.

---

## 1. SUMO installation

Installed SUMO 1.27.0 via pip (no separate installer needed):

```
pip install eclipse-sumo traci sumolib
```

This installs `sumo`, `sumo-gui`, `netgenerate`, `netconvert`, `randomTrips.py`,
and the Python packages `traci` (live simulation control) and `sumolib`
(network/route utilities).

- Binaries location: `C:\Users\zivna\AppData\Local\Python\pythoncore-3.14-64\Scripts\`
  (`sumo.exe`, `sumo-gui.exe`)
- Tools location (randomTrips.py etc.): `C:\Users\zivna\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\sumo\tools\`
- To run `sumo-gui` by name, add the Scripts folder to PATH, or call the full path.

---

## 2. First experiment: single intersection, fixed-time baseline

**Goal:** simple 4-arm intersection (2 lanes/direction, 40 mph = 17.88 m/s
speed limit), fixed-time traffic light, 100 runs with random traffic,
report average waiting time and average speed per car.

Files created:
- `net_single/cross.net.xml` — generated via:
  ```
  netgenerate --grid --grid.number=3 --grid.length=200 --default.lanenumber=2 --default.speed=17.88 --tls.guess --output-file=net_single/cross.net.xml
  ```
  (a 3x3 grid produces exactly 1 interior 4-way intersection)
- `net_single/sim.sumocfg` — config (also has `net_single/routes.rou.xml` for manual GUI runs, seed=42)
- `run_baseline_experiment.py` — runs 100 seeds, generates traffic via
  `randomTrips.py` (period=3.0s, "few cars"), parses `tripinfo.xml` for
  per-vehicle waiting time and `routeLength/duration` as average speed.

**Result (100 runs, 17,129 vehicles total):**
- Average waiting time per car: **18.87 s**
- Average speed per car: **10.42 m/s (23.32 mph)**, vs. 40 mph limit
  (lower than the limit because it includes time stopped at red lights)

This is a separate, simpler experiment from the J1/J2 project below — kept
as a standalone baseline reference.

**Run it yourself with GUI:**
```
cd "D:\Ziv - OS\Projects\Trafic AI"
"C:\Users\zivna\AppData\Local\Python\pythoncore-3.14-64\Scripts\sumo-gui.exe" -c net_single\sim.sumocfg
```
Opens paused — drag the "Delay (ms)" slider up to ~50-100ms so you can see
cars move, then click Play.

(There's also an earlier `net/` folder from an initial 2x2-grid test —
superseded by `net_single/` and then by `sim/` below.)

---

## 3. Main project: J1/J2 multi-intersection system (`sim/` folder)

This is the real final-project deliverable: a 3x2-block urban grid with two
adjacent controlled intersections (J1, J2), comparing **TIMER vs SCRIPT vs AI**
control strategies, per the full project spec (network layout, state
representation, load scores, metrics, etc. — see the big design prompt in
session history for full spec).

### 3.1 Network

Generated via:
```
netgenerate --grid --grid.x-number=4 --grid.y-number=3 --grid.length=150 \
  --default.lanenumber=2 --default.speed=13.89 --tls.guess \
  --sidewalks.guess --crossings.guess \
  --output-file=sim/network/grid.net.xml
```

This is a 4x3 node grid = 3x2 city blocks. Node layout:

```
A2 --- B2 --- C2 --- D2
|      |      |      |
A1 --- B1 === C1 --- D1
|      |      |      |
A0 --- B0 --- C0 --- D0
```

- **J1 = B1**, **J2 = C1** — the only two full 4-way intersections
  (in:4/out:4), directly connected via edges `B1C1` / `C1B1`.
- All other nodes (A0,A1,A2,B0,B2,C0,C2,D0,D1,D2) are background
  junctions with default SUMO behavior (3-way or edge nodes).
- Speed limit 13.89 m/s (50 km/h) on all lanes by default.
- Sidewalks + pedestrian crossings generated automatically.

TLS program for B1 and C1 (identical structure, 24-character state string,
6 phases):
- Phase 0 (37s green): **North+South** approaches green, East+West red
  (pedestrian crossing on the perpendicular axis also gets green here)
- Phase 1 (5s): same, pedestrian-green tail ending
- Phase 2 (3s yellow): NS → EW transition
- Phase 3 (37s green): **East+West** approaches green, North+South red
- Phase 4 (5s): same, pedestrian-green tail ending
- Phase 5 (3s yellow): EW → NS transition

### 3.2 Config (`sim/modules/config.py`)

Central constants:
- `J1_ID = "B1"`, `J2_ID = "C1"`
- `J1_TO_J2_EDGE = "B1C1"`, `J2_TO_J1_EDGE = "C1B1"`
- Approach-edge mapping per junction, by compass direction:
  - `J1_APPROACHES`: west=A1B1, south=B0B1, north=B2B1, east=C1B1 (from J2)
  - `J2_APPROACHES`: west=B1C1 (from J1), south=C0C1, north=C2C1, east=D1C1
- Tunables: `MIN_GREEN_TIME=10`, `MAX_GREEN_TIME=60`,
  `PEDESTRIAN_WAIT_THRESHOLD=40`, `STARVATION_THRESHOLD=90`,
  `INCOMING_WINDOW=30`, `SIM_END_TIME=1200`

### 3.3 Scenarios (`sim/scenarios/`)

- `balanced.rou.xml` / `balanced.ped.xml` — random trips, p=2.0 (vehicles)
  and p=6.0 (pedestrians), seed=1, 1200s, ~1200 vehicle trips / ~400 pedestrians.
- `heavy_west.rou.xml` / `heavy_west.ped.xml` — sparse background traffic
  (p=6.0, seed=3) **plus** a high-rate `<flow>` (`probability=0.5`) on route
  `A1B1 B1C1 C1D1` (west → through J1 → through J2 → east), simulating heavy
  one-directional traffic for scenario type #2 ("heavy traffic from one
  main direction").

Other scenario types from the spec (morning/evening flow, downstream
congestion, pedestrian-demand-focused, etc.) are **not yet built**.

### 3.4 Modules (`sim/modules/`)

- **`data_collection.py`** — TraCI wrappers: `queue_length`, `waiting_times`,
  `average_speed`, `incoming_vehicles_within` (ETA-based, 30s horizon),
  `edge_congestion_level` (free/moderate/congested via lane occupancy),
  `pedestrian_waiting_at_junction`, `current_phase_info`.

  **Important fix:** initial run used `--pedestrian.model nonInteracting`,
  which made pedestrians ignore traffic lights entirely (never wait →
  all pedestrian metrics were 0). **Fixed by removing that flag** — SUMO's
  default `striping` pedestrian model makes pedestrians actually stop at
  red crossings (confirmed: max wait 44s in a 300s test run).

- **`state_builder.py`** — `build_state(junction_id)` returns the full
  structured state dict from the spec (intersection_id, current_phase,
  phase_elapsed_time, per-approach queue/wait/incoming/speed,
  downstream_status, pedestrians).

- **`metrics.py`** — `MetricsCollector` (per-step sampling of queue lengths,
  pedestrian waits, J1↔J2 edge congestion) + `finalize()` (parses SUMO
  `tripinfo.xml` for waiting time, travel time, stops, throughput) +
  `compare_to_baseline()` (% improvement vs TIMER) + `save_summary()`
  (writes JSON to `sim/results/`).

### 3.5 Controllers (`sim/controllers/`)

- **`timer_controller.py`** (TIMER mode, baseline) — no-op; SUMO's default
  fixed-time TLS program runs unmodified.

- **`script_controller.py`** (SCRIPT mode) — deterministic rule-based
  adaptive controller. Only acts at the **start of green phases 0/3**
  (leaves yellow/pedestrian-tail phases untouched, so all transitions stay
  legal):
  1. Build state via `state_builder`.
  2. Load score per direction-group (NS vs EW):
     `0.35*queue + 0.30*avg_wait + 0.20*incoming_30s + 0.15*max_wait`
     (summed over the 2 approaches in the group).
  3. `ratio = load_current_group / (load_current + load_other)`
  4. `duration = MIN_GREEN + ratio * (MAX_GREEN - MIN_GREEN)`
  5. Pedestrian override → `duration = MIN_GREEN` if avg ped wait > 40s.
  6. Starvation override → `duration = MIN_GREEN` if other group's last
     green was > 90s ago.
  7. `traci.trafficlight.setPhaseDuration(jid, duration)`.
  - Mid-phase safeguard (`_check_starvation`): force-end a green phase early
    if it's past MAX_GREEN and the other group is starving.

- **AI mode (`ai_controller.py`)** — **not yet implemented.**

### 3.6 Runner (`sim/run_experiment.py`)

```
python sim/run_experiment.py --mode {timer|script|ai} --scenario {balanced|heavy_west} [--gui] [--end SECONDS]
```

Starts TraCI with the network + scenario routes/pedestrians, steps the
simulation, calls the controller's `step()` each tick, collects metrics,
writes `sim/results/{mode}_{scenario}.json` and
`sim/results/{mode}_{scenario}_tripinfo.xml`.

### 3.7 Results so far

**`balanced` scenario, 600s:**

| Metric | TIMER | SCRIPT |
|---|---|---|
| Avg waiting time | 27.94 s | 34.45 s |
| Max waiting time | 105 s | 198 s |
| Avg queue length | 3.88 | 5.80 |
| Max queue length | 9 | 11 |
| Throughput | 600 | 600 |
| Avg travel time | 86.4 s | 94.5 s |
| Avg stops/vehicle | 1.53 | 1.75 |
| Avg pedestrian wait | 15.6 s | 20.3 s |
| Max pedestrian wait | 50 s | 70 s |
| J1↔J2 congestion % | 0% | 0% |

**`heavy_west` scenario, 600s:**

| Metric | TIMER | SCRIPT |
|---|---|---|
| Avg waiting time | 43.43 s | 47.11 s |
| Max waiting time | 215 s | 171 s (better) |
| Avg queue length | 17.54 | 18.69 |
| Max queue length | 35 | 34 |
| Throughput | 787 | 787 |
| Avg travel time | 95.93 s | 102.15 s |
| Avg stops/vehicle | 1.35 | 1.70 |
| Avg pedestrian wait | 16.15 s | 22.08 s |
| Max pedestrian wait | 55 s | 94 s |

### 3.8 Known issues / open work

1. **SCRIPT mode currently underperforms TIMER on both scenarios** (except
   max-wait on heavy_west). Pipeline/plumbing is correct — this is a
   **tuning problem**:
   - The spec's load-score weights (0.35/0.30/0.20/0.15) aren't calibrated
     to this network's actual queue/wait magnitudes.
   - Pedestrian-priority and starvation overrides may fire too often,
     causing extra short cycles (avg stops increased in both scenarios).
   - Downstream-congestion and J1↔J2 coordination terms from the spec are
     **not yet implemented** in the load formula.
2. **AI mode** (LLM advisor + Python validation layer) — not started.
3. **Scenarios 3-7** from the spec (morning/evening flow, downstream
   congestion focus, pedestrian-demand focus, surrounding-grid traffic) —
   not yet built.
4. `j1_j2_congestion_pct_time` has been 0% in both tests so far — may need
   a lower occupancy threshold in `edge_congestion_level()`, or the link
   road just isn't getting congested at these traffic levels yet.
5. Figures/tables for the report (graphs of TIMER vs SCRIPT vs AI) — not
   yet generated.

---

## 4. Folder map (current state)

```
D:\Ziv - OS\Projects\Trafic AI\
├── PROGRESS.md              <- this file
├── README.md                <- SUMO setup notes (single-intersection experiment)
├── run_baseline.py           <- early 2x2-grid TraCI test (superseded)
├── run_baseline_experiment.py <- single-intersection 100-run experiment (Section 2)
├── net/                       <- early 2x2 grid test (superseded)
├── net_single/                <- single-intersection baseline (Section 2)
│   ├── cross.net.xml
│   ├── routes.rou.xml
│   ├── sim.sumocfg
│   └── _runs/                 <- per-seed run artifacts from the 100-run experiment
└── sim/                        <- MAIN PROJECT (Section 3)
    ├── network/grid.net.xml
    ├── scenarios/
    │   ├── balanced.rou.xml / .ped.xml
    │   ├── heavy_west.rou.xml / .ped.xml
    │   └── _bg.rou.xml         <- intermediate file used to build heavy_west
    ├── modules/
    │   ├── config.py
    │   ├── data_collection.py
    │   ├── state_builder.py
    │   └── metrics.py
    ├── controllers/
    │   ├── timer_controller.py
    │   └── script_controller.py
    ├── results/
    │   ├── timer_balanced.json (+tripinfo.xml)
    │   ├── script_balanced.json (+tripinfo.xml)
    │   ├── timer_heavy_west.json (+tripinfo.xml)
    │   └── script_heavy_west.json (+tripinfo.xml)
    └── run_experiment.py
```

---

## 5. Suggested next steps (in order)

1. Tune SCRIPT mode's load-score weights / thresholds so it measurably beats
   TIMER (run small parameter sweeps, especially on `heavy_west`).
2. Add downstream-congestion penalty and J1↔J2 coordination term to the load
   formula.
3. Implement AI mode (`sim/controllers/ai_controller.py`): Python builds
   state → sends to LLM → LLM recommends phase/duration/reasoning → Python
   validates against the same safety constraints (min/max green, no
   conflicting phases, pedestrian threshold, starvation, downstream
   congestion) → applies via TraCI.
4. Build remaining traffic scenarios (morning/evening directional flow,
   downstream-congestion scenario, pedestrian-focused scenario).
5. Run all three modes across all scenarios, generate comparison
   tables/graphs for the report (this maps to Chapter 3.3 "תוצאות ראשוניות"
   and Chapter 4 in `Interim_Report_Ziv_Ofek.docx`).
6. Feed real results back into the interim report's TODO placeholders.
