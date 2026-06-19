# Smart Urban Intersection System — Requirements Checklist

_Last updated: 2026-06-13 20:06_

This file is the master checklist derived from the full project spec you
gave (the "big prompt"). Every requirement is listed with its status so
progress is easy to track at a glance.

Status legend: ✅ Done | 🟡 Partial / needs tuning | ❌ Not started

---

## 1. Core project goal

- ✅ SUMO-based simulation of smart traffic-light control
- ✅ Small urban grid network (3x2 block layout, 4x3 node grid)
- ✅ Two adjacent signalized 4-way intersections, J1 and J2, directly connected
- ✅ Python communicates with SUMO via TraCI
- ❌ Not using real cameras — confirmed (no CV/camera code anywhere, as required)
- 🟡 Pedestrians included via SUMO (simplified) — basic version working,
  but controller doesn't yet use pedestrian data for *coordination* between
  J1/J2, only per-junction priority

---

## 2. Network layout

- ✅ 3x2 block-style grid (4x3 node grid: A0-D2)
- ✅ J1 = B1, J2 = C1, both full 4-way intersections with traffic lights
- ✅ J1 ↔ J2 directly connected via `B1C1` / `C1B1` edges
- ✅ Surrounding nodes (A0,A1,A2,B0,B2,C0,C2,D0,D1,D2) act as entry/exit/
  background junctions with default SUMO behavior
- ✅ Only J1 and J2 are controlled in this first version (per constraint:
  "do not control every junction")
- ✅ Each controlled intersection has North/South/East/West approaches
- ✅ Lanes support configurable speed limits (default 13.89 m/s / 50 km/h
  set network-wide; per-lane overrides not yet customized but supported)
- 🟡 "Follow Israeli traffic laws as much as possible" — using SUMO defaults
  (right-hand traffic, standard phase structure); no explicit Israeli-law
  rule review/documentation done yet

---

## 3. Traffic scenarios (spec lists 7)

- ✅ 1. Balanced traffic from all directions → `sim/scenarios/balanced.rou.xml`
- ✅ 2. Heavy traffic from one main direction → `sim/scenarios/heavy_west.rou.xml`
- ❌ 3. Morning-like traffic flow toward one side
- ❌ 4. Evening-like traffic flow in the opposite direction
- ❌ 5. Congestion near the downstream intersection
- 🟡 6. Pedestrian demand at crossing points — pedestrians exist in both
  built scenarios (`.ped.xml`), but no scenario specifically *stress-tests*
  pedestrian demand
- ✅ 7. Traffic moving through the surrounding grid while J1/J2 are focus
  (background traffic via randomTrips covers the whole grid in both
  scenarios)

---

## 4. Experiment modes

### 4a. TIMER mode (baseline)
- ✅ Fixed-time cycles for J1 and J2 (SUMO default `tls.guess` program:
  37s NS green / 5s / 3s yellow / 37s EW green / 5s / 3s yellow)
- ✅ Pedestrian phases at fixed intervals (built into the TLS program)
- ✅ Controller does not react to real-time conditions (`timer_controller.py`)
- ✅ Full simulation run + metrics collected + summary generated
- ✅ Run on `balanced` and `heavy_west` scenarios

### 4b. SCRIPT mode (adaptive rule-based)

**Versioning:**
- `script_controller_v0.py` (`ScriptControllerV0`, mode `script_v0`) — the
  original simple proportional controller. Kept for reference/comparison
  only. Underperformed TIMER on both scenarios.
- `script_controller.py` (`ScriptController`, mode `script`) — **SCRIPT v1,
  network-aware adaptive controller**, the production version. Includes all
  checkmarked items below.
- ✅ Python reads traffic state via TraCI (`state_builder.py`)
- ✅ Controls J1 and J2 traffic lights (`script_controller.py`)
- ✅ Considers: queue length, avg waiting time, max waiting time,
  incoming vehicles (30s window), vehicle speed
- ❌ "Estimated arrival time to next intersection" — partially covered by
  incoming_vehicles_within (ETA-based), but not used explicitly as its own
  decision input
- 🟡 Downstream congestion — `edge_congestion_level()` exists and is
  collected in state, but **not yet used in the load/decision formula**
- ✅ Pedestrian waiting time + count considered (priority override)
- ✅ Minimum green time / maximum green time enforced
- ✅ Starvation prevention implemented
- 🟡 Israeli traffic-law constraints / legal phase transitions — respected
  implicitly (only green-phase durations are changed; yellow/ped-tail
  phases untouched, so SUMO's legal program structure is preserved), but
  not explicitly documented/verified against Israeli law specifics
- ✅ Non-conflicting vehicle/pedestrian phases — preserved (same reason)
- ✅ Full simulation run + metrics + summary + comparison vs TIMER
- ✅ **Result quality (v1, network-aware, tuned per review)**: on `heavy_west`, SCRIPT now
  beats TIMER on every metric (avg wait 43.4s→32.9s, -24%; avg queue
  17.5→12.6, -28%; avg travel time 95.9s→86.7s, -10%). On `balanced`,
  SCRIPT is close but still slightly behind TIMER (31.8s vs 27.9s avg
  wait) — expected, since the fixed 37/37 split is near-optimal for
  symmetric demand. v2 fixes applied: downstream-congestion penalty,
  J1->J2 coordination boost, load deadband/hysteresis, bucketed (not
  proportional) green durations, starvation cap instead of forced MIN, and
  pedestrian max-wait force / avg-wait cap. See `sim/controllers/script_controller.py`.

### 4c. AI mode (LLM-guided)
- ❌ Not started at all. Required pieces, all ❌:
  - Python collects state and builds structured summary (state_builder
    already produces this — reusable)
  - LLM receives state summary
  - LLM recommends: next phase, green duration, reasoning, pedestrian
    priority flag, congestion-avoidance flag, J1↔J2 coordination flag
  - Python validation layer (min/max green, no conflicting phases, ped
    threshold, starvation, downstream congestion, legal phase transitions)
  - Apply validated decision via TraCI
  - Run full simulation + metrics + summary + comparison vs TIMER and SCRIPT

---

## 5. Main questions the algorithm should answer (15 items from spec)

| # | Question | Status |
|---|---|---|
| 1 | Where is each vehicle going? | ❌ not explicitly tracked (route/next-edge lookup not implemented) |
| 2 | Status of the next intersection? | 🟡 `edge_congestion_level()` exists, collected in state, unused in decisions |
| 3 | Vehicle speed → ETA to next intersection | ✅ via `incoming_vehicles_within()` |
| 4 | How many vehicles arriving within 30s? | ✅ `incoming_vehicles_30s` per approach |
| 5 | Queue length per direction? | ✅ |
| 6 | Avg/max waiting time per direction? | ✅ |
| 7 | Are pedestrians waiting (count, duration)? | ✅ |
| 8 | Current phase + time active? | ✅ `current_phase`, `phase_elapsed_time` |
| 9 | Is queue increasing/decreasing over time? | ❌ no trend tracking yet |
| 10 | Can J1/J2 be coordinated? | ❌ not implemented |
| 11 | Will releasing vehicles congest the next intersection? | ❌ not implemented |
| 12 | Has any direction waited too long (starvation)? | ✅ implemented in SCRIPT |
| 13 | Have pedestrians waited too long? | ✅ implemented in SCRIPT |
| 14 | Is the decision safe/legal/valid? | 🟡 implicit via phase structure; no explicit validator module yet (needed for AI mode) |
| 15 | What's happening on the J1↔J2 connecting road? | 🟡 collected (`downstream_status.road_to_other`) but unused in decisions |

---

## 6. Required architecture modules

1. ✅ SUMO Simulation Module — `sim/network/grid.net.xml` + scenarios
2. ✅ Data Collection Module — `sim/modules/data_collection.py`
3. ✅ State Builder Module — `sim/modules/state_builder.py`
4. 🟡 Load Calculator Module — implemented inline in `script_controller.py`
   (`load_score()`), but missing pedestrian-priority component in the
   formula itself, downstream penalty, and J1↔J2 coordination term (spec
   describes these as part of the load formula; currently they're separate
   override checks, not part of the score)
5. 🟡 Decision Module — exists per-mode (`timer_controller.py`,
   `script_controller.py`); AI decision module ❌ not started
6. ✅ Traffic Light Control Module — via TraCI `setPhaseDuration` (script)
   and default program (timer)
7. 🟡 Metrics and Evaluation Module — `sim/modules/metrics.py` implemented
   and working; `j1_j2_congestion_pct_time` always reading 0% so far
   (needs threshold check)

---

## 7. Metrics (spec list)

All implemented in `MetricsCollector.finalize()`:
- ✅ Average vehicle waiting time
- ✅ Maximum vehicle waiting time
- ✅ Average queue length
- ✅ Maximum queue length
- ✅ Throughput
- ✅ Average pedestrian waiting time
- ✅ Maximum pedestrian waiting time
- ✅ Number of waiting pedestrians
- ✅ Number of stops per vehicle
- ✅ Average travel time
- 🟡 Congestion level on J1↔J2 road — collected but always 0% so far,
  needs threshold tuning
- ✅ Percentage improvement vs TIMER — `compare_to_baseline()`

---

## 8. "Expected output" — 21 deliverables from the spec

| # | Deliverable | Status |
|---|---|---|
| 1 | Proposed SUMO network structure (3x2 grid) | ✅ built (`grid.net.xml`) |
| 2 | Definition of J1/J2 | ✅ (`config.py`) |
| 3 | Surrounding-roads usage recommendation | ✅ (background traffic via randomTrips covers full grid) |
| 4 | Recommended folder structure | ✅ (`sim/network`, `sim/scenarios`, `sim/modules`, `sim/controllers`, `sim/results`) |
| 5 | Python code structure using TraCI | ✅ |
| 6 | Implementation plan for TIMER | ✅ implemented (not just planned) |
| 7 | Implementation plan for SCRIPT | ✅ implemented (not just planned) |
| 8 | Implementation plan for AI | ❌ not started |
| 9 | Adaptive rule-based algorithm for SCRIPT | ✅ implemented and tuned (v2, beats TIMER on heavy_west) |
| 10 | Safe LLM-guided algorithm for AI | ❌ not started |
| 11 | State representation design | ✅ |
| 12 | Load calculation method | 🟡 basic version done, missing components (see §6.4) |
| 13 | Traffic-light phase design | ✅ documented in PROGRESS.md §3.1 |
| 14 | Pedestrian phase design | ✅ (built into TLS program; pedestrian model fixed) |
| 15 | J1-J2 coordination logic | ❌ not implemented |
| 16 | Metrics collection method | ✅ |
| 17 | Experiment execution flow | ✅ (`run_experiment.py`) |
| 18 | Result comparison method | ✅ (`compare_to_baseline()`) |
| 19 | Suggestions for graphs/tables for report | ❌ not done |
| 20 | Result summary template per mode | ✅ (JSON summary in `sim/results/`) |
| 21 | Final TIMER vs SCRIPT vs AI comparison table | 🟡 TIMER vs SCRIPT done for 2 scenarios; AI missing |

---

## 9. Overall snapshot

**Solid foundation (done):** network, J1/J2 definition, TraCI data pipeline,
state builder, metrics/comparison framework, TIMER baseline, SCRIPT
controller (functional but needs tuning), pedestrian simulation (bug fixed),
2 of 7 scenarios.

**Biggest remaining gaps, roughly in priority order:**
1. ✅ ~~Tune SCRIPT mode so it actually beats TIMER~~ — done (v2), beats
   TIMER on heavy_west; balanced is close but slightly behind (expected).
   Could optionally tune further (deadband width, bucket thresholds) to
   close the balanced-scenario gap.
2. **Build AI mode** (LLM advisor + Python validator) — entire mode missing
3. **Build remaining scenarios** (#3,4,5, and a pedestrian-focused one)
4. **Add validation/safety-check module** shared by SCRIPT and AI (currently
   safety is implicit; AI mode needs an explicit validator)
5. **Trend tracking** (is queue growing/shrinking) and **vehicle-routing
   awareness** (where is each vehicle going) — needed for full spec
   compliance on questions #1, #9, #10, #11
6. **Graphs/tables** for the report
7. Document how the SUMO setup follows Israeli traffic-law conventions
   (even if just a short justification section)

---

## 10. Future task (gated — do not start yet): Compare LLM backends for AI mode

❌ Not started. **Gate: do not begin until items 1-5 below are all done:**
1. ✅ SUMO network
2. ✅ TIMER mode
3. 🟡 SCRIPT mode (working, needs tuning — see §9)
4. ✅ Metrics collection
5. ❌ Basic AI mode with one LLM backend

**Goal:** evaluate whether different LLMs produce different traffic-control
quality, reliability, latency, and decision consistency.

**Backends to compare:**
1. GPT-based model
2. Claude-based model
3. Local Ollama-based model
4. Optional additional local/open-source models

**Architecture requirement:** modular `LLMControllerBackend` adapter
interface so the AI controller can swap models without touching the rest
of the system:
- `build_prompt(state_summary)`
- `send_request(prompt)`
- `parse_response(response)`
- `validate_response_format(response)`
- `return_recommendation()`

**Required AI response schema** (same for every backend):
```json
{
  "recommended_phase": "...",
  "recommended_green_duration": 0,
  "priority_reason": "...",
  "pedestrian_priority": true,
  "downstream_congestion_action": "...",
  "coordination_between_J1_J2": "...",
  "confidence": 0
}
```
Python must validate every recommendation before applying it in SUMO
(reuses the same safety-validation layer as basic AI mode).

**Comparison must hold constant across backends:** SUMO network, traffic
scenarios, vehicle/pedestrian demand, simulation time, state representation,
safety validation layer, metrics calculation.

**Metrics for LLM comparison:**
- Avg/max vehicle waiting time, avg/max queue length, throughput
- Avg/max pedestrian waiting time, travel time, stops per vehicle
- Congestion level between J1 and J2
- % improvement vs TIMER and vs SCRIPT
- AI response latency
- Number of invalid AI responses
- Number of recommendations rejected by Python validation
- Decision consistency across repeated runs
- Cost per simulation run (paid APIs)
- Ease of running locally (Ollama)

**Expected output:**
- Comparison table: GPT vs Claude vs Ollama/local
- Graphs comparing performance metrics
- Latency comparison
- Valid/invalid recommendation rate
- Final recommendation on which backend is most suitable for this project

---

## 11. How to use this file

- When you complete an item, change ❌ → 🟡 or ✅ and add a one-line note
  with the file/commit it lives in.
- `PROGRESS.md` has the detailed narrative/history; this file is the
  flat checklist for tracking completeness against the original spec.
- Re-run `python sim/run_experiment.py --mode {timer|script|ai} --scenario {name}`
  after each change to refresh `sim/results/`.
