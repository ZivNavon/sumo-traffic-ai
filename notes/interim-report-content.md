---
type: notes
project: Trafic AI
date: 2026-08-15
status: reference
tags: [interim-report, final-report-prep]
---

# Interim Report — Content Summary

Use this when writing the final report to know what was already written and what needs updating.

---

## Abstract (as submitted)

**Hebrew summary:** Project develops a smart traffic-light control system for urban intersections adapting signal timing to real-time conditions. Evaluated in SUMO simulator collecting queue length, waiting times, network congestion, and pedestrian data. Three controllers compared: TIMER (fixed), SCRIPT (rule-based dynamic), AI (recommendation with validation). Preliminary results: dynamic logic reduced avg wait by 24% and avg queue by 28% under asymmetric conditions. Future work: algorithm calibration, more scenarios, AI model integration.

**For the final report:** Update to reflect DQN (not LLM), include final results across all scenarios and all three modes.

---

## Chapter 1 — Introduction (completed)

- 1.1 General background: urban congestion problem, fixed cycles inadequacy
- 1.2 Problem definition: adapt timing to real conditions in real time; SUMO as test environment
- 1.3 Current simulation scope: J1+J2 two-junction system, 600s runs
- 1.4 Report structure

**Final report changes:** Update scope to include DQN training runs (longer: 5,000 episodes). Update 1.3 to reflect all completed scenarios.

---

## Chapter 2 — Literature Review (completed)

- 2.1 Existing systems: SCATS, SCOOT
- 2.2 Traffic measurement methods: radar, cameras, loops
- 2.3 Current algorithms: fixed timing, adaptive
- 2.4 Adaptation between traffic conditions: microcontrollers [3][6]
- 2.5 Pedestrian considerations
- 2.6 Key papers reviewed
- 2.7 Limitations of current solutions: no true simulation environment, not learning-based
- 2.8 Impact of literature on system design

**Final report changes:** Add DRL-specific literature. Key paper: [4] Liang et al. "Deep Reinforcement Learning for Traffic Light Control" (arXiv:1803.11115). Add DQN foundational paper: Mnih et al. 2015 (Nature, DQN on Atari).

---

## Chapter 3 — System Architecture (completed, needs update)

### 3.1 Architecture
Current: SUMO → TraCI → Data Collection → State Builder → Load Calculator → Decision (Timer/Script) → TLS

Future extensions shown in diagram: Computer Vision PoC, GUI/Dashboard, AI/LLM Extension.

**Final report update:** Replace "AI/LLM Extension" with "AI/DQN Controller." Update architecture diagram to show DQN agent with training loop and replay buffer.

### 3.2 Simulation environment
- SUMO 1.27.0, Python 3, TraCI
- 600s per evaluation run
- J1=B1, J2=C1, link: B1C1 / C1B1
- Speed: 13.89 m/s (50 km/h)
- Scenarios: balanced, heavy_west

### 3.3 Decision layer (three controllers)
1. TIMER: fixed 37s NS + 37s EW, no logic
2. SCRIPT: Load = 0.35*queue + 0.30*avg_wait + 0.20*incoming_30s + 0.15*max_wait
3. AI: (interim: LLM + Python validation) → **final: DQN agent**

### 3.4 Initial results
See RESULTS.md for full tables. Summary:
- balanced: SCRIPT v1 trails TIMER (adaptive logic hurts in symmetric conditions)
- heavy_west: SCRIPT v1 beats TIMER: avg wait -24%, avg queue -28%

---

## Chapter 4 — Work Plan and Risks (needs full update for final report)

### 4.1 What was done vs planned (from interim)

| Task | Status at interim |
|---|---|
| Literature review | Done |
| System requirements | Done |
| Architecture design | Done |
| Initial logic design | Done |
| Progress report | Done |
| Software implementation | In progress |
| System integration | In progress |
| Testing/calibration | In progress |
| Final report + presentation | Future |

### 4.2 Updated schedule (months from project start)

| Month | Task |
|---|---|
| 1-2 | Literature review, requirements |
| 2-3 | Architecture, initial logic |
| 3 | Progress report (submitted) |
| 3-5 | Software implementation |
| 4-5 | AI integration + ML validation |
| 4-5 | CV and GUI (future extensions) |
| 5 | Full system integration + testing |
| 5-6 | Final report + presentation + poster |

### 4.3 Risk table (8 risks identified)

| # | Risk | Mitigation |
|---|---|---|
| 1 | Time constraints | Clear task split, different training seeds |
| 2 | Variance between simulations | Multiple seeds, not single-run conclusions |
| 3 | Traffic light timing irregularities | Grid logic prevents bad states |
| 4 | Adaptive algorithm performance | Check metrics between runs, compare to fixed baseline |
| 5 | AI tool use | Python Validation layer enforces hard limits |
| 6 | Pedestrian vs vehicle balance | Per-pedestrian metrics tracked separately |
| 7 | Real-time CV/GUI | Pre-develop to close simulation gap |
| 8 | Version control | GitHub only for code and documentation |

### 4.4 AI declaration (submitted)
AI tools used for: scenario formulation, code improvement, testing, understanding results, analysis. All results and conclusions student-verified. Graphs and data not AI-generated.

---

## Bibliography (as submitted — IEEE format)

[1] Reza et al., "Urban Safety: Image-Processing and Deep-Learning-Based Intelligent Traffic Management," Sensors, 2021.
[2] Alshraiedeh et al., "Deep Learning and IoT for Predictive Traffic Management in Smart Cities," IEEE Access, 2024.
[3] Vieira et al., "Visible Light Communication and Learning-Based Control for Traffic Signal Optimization," Symmetry, 2024.
[4] Liang et al., "Deep Reinforcement Learning for Traffic Light Control in Vehicular Networks," arXiv:1803.11115, 2018.
[5] Han et al., "Deep Reinforcement Learning for Intersection Signal Control Considering Pedestrian Behavior," 2021.
[6] Elliott et al., "Recent Advances in Connected and Automated Vehicles," 2019.
[7] Zou et al., "Traffic Flow Video Image Recognition Based on Multi-Target Tracking and Deep Learning," 2020.
[8] Umair et al., "Efficient Video-Based Vehicle Queue Length Estimation Using Computer Vision," Processes, 2021.
[9] Mohammed et al., "Autonomous Short-Term Traffic Flow Prediction Using Pelican Optimization," Applied Sciences, 2022.
[10] Huang et al., "Optimized YOLOv3 Algorithm for Traffic Flow Detection," 2020.

**To add in final report:**
- Mnih et al. 2015, "Human-level control through deep reinforcement learning," Nature (foundational DQN paper)
- SUMO documentation reference

---

---

## Revision of AI Approach: LLM → DQN (for final report Chapter 3)

The interim report described AI mode as LLM-based. The final report must justify the change.
Add this as a subsection in Chapter 3 (after 3.3, before 3.4), or as a discussion paragraph in Chapter 4.

### Comparison table (include in report)

| Criterion | LLM (GPT/Claude API) | DQN (Deep Q-Network) |
|---|---|---|
| Learns from experience | No — same reasoning every call | Yes — policy improves with training |
| External dependency | Yes — internet + API key required | No — runs fully offline in SUMO |
| Reproducibility | No — non-deterministic output | Yes — fixed random seed |
| Latency per decision | ~100-500 ms (API round-trip) | ~0.1 ms (forward pass) |
| Established in traffic research | No | Yes — [4][5] use DRL for traffic signal control |
| Can prove learning occurred | No | Yes — reward curve over episodes |
| Student can fully explain internals | Partial | Full (weights, Q-values, policy) |

### Draft paragraph for the report

> "During implementation, two candidate approaches were evaluated for the AI controller: a Large Language Model (LLM) queried via API, and a Deep Q-Network (DQN) trained directly within the SUMO simulation environment.
>
> The LLM approach was rejected for several engineering reasons. First, it introduces an external API dependency, making the system unable to operate offline or in real-time without network access. Second, LLM outputs are non-deterministic, making results unreproducible across runs. Third, and most critically, an LLM does not learn: it applies the same reasoning regardless of past outcomes, making it fundamentally a rule-based system expressed in natural language rather than a true learning agent.
>
> DQN addresses all of these limitations. It is a learning algorithm that optimizes a reward function through accumulated simulation experience, runs fully locally, produces reproducible results under a fixed seed, and is already the established method in traffic signal control research [4][5]. For these reasons, the AI mode was implemented as a DQN controller."

### What this enables in the defense

- Show the **training reward curve** (reward per episode over 5,000 runs — goes from bad to good, proves learning)
- Show **Q-values** the network assigns to each action at a given state
- Argue the agent discovered a directional-priority policy similar to SCRIPT — but without being told the rules
- Answer the examiner question "what did the AI actually learn?" with a concrete graph

---

## Key gaps: interim → final report

1. Chapter 3: Replace AI/LLM with DQN. Add DQN architecture description (state space, action space, reward, network layers, training loop).
2. Chapter 3.4: Add DQN results alongside TIMER and SCRIPT v1.
3. Chapter 4: Update work plan to reflect actual completion timeline.
4. New: training reward curve graph showing DQN learning over episodes.
5. Final abstract: update with DQN framing and final numbers.

---

## Methodology note: fixed seed and overfitting (include in Chapter 3 or 4)

Each scenario uses a single fixed random seed baked into the route XML. Every controller (TIMER, SCRIPT, DQN, A2C) is evaluated on the exact same traffic sequence, making the comparison controlled and fair.

The ML models are also trained on this same fixed route file, replayed every episode. Technically this means the model memorizes the specific traffic sequence rather than learning a fully general policy. However, this is not a meaningful limitation here for two reasons:

1. **The state space prevents direct memorization.** The model never receives vehicle IDs, timestamps, or episode numbers. It only sees queue lengths, waiting times, and pedestrian counts at the current moment. Any policy it learns is therefore expressed in terms of traffic state, not episode position.

2. **The evaluation matches the training distribution.** The goal is not to claim generalization to unseen traffic — it is to answer: "given this exact traffic, can an ML controller outperform a fixed timer?" The answer is yes, and the comparison is valid.

### Draft paragraph for the report (add to Chapter 3.2 or as a limitation in Chapter 5)

> "All simulation runs use a fixed random seed per scenario. The route files are generated once and reused for both training and evaluation. This ensures a controlled comparison: all controllers face an identical vehicle sequence, so differences in outcome are attributable solely to the control policy and not to traffic variation.
>
> As a consequence, the trained models are optimized for a specific traffic realization rather than a distribution of random scenarios. The model's state inputs (queue lengths, waiting times) do not include the simulation clock or vehicle identities, so the learned policy is implicitly state-based and not sequence-based. Generalization to arbitrary real-world traffic patterns was not evaluated and would require training across randomized seeds — a direction for future work."
