"""
AI controller — DQN (Deep Q-Network).

Loads pre-trained weights from sim/models/dqn_weights.pt and uses them
to decide green phase durations. Same interface as ScriptController so
run_experiment.py can use it with --mode ai without any other changes.

Train first:
    python sim/train_dqn.py --scenario heavy_west --episodes 3000

Then evaluate:
    python sim/run_experiment.py --mode ai --scenario heavy_west
"""

import os
import numpy as np
import torch
import torch.nn as nn
import traci

from modules import config, state_builder

# Discrete action space: 5 green durations the agent can choose from (seconds).
# v2: minimum raised from 10s to 20s to prevent rapid phase cycling.
ACTIONS    = [20, 30, 40, 50, 60]
STATE_DIM  = 17        # length of the state vector (see state_to_vector)
ACTION_DIM = len(ACTIONS)

GREEN_PHASES = {0, 3}


def state_to_vector(state):
    """
    Flatten the dict from state_builder.build_state() into a normalized
    numpy float32 vector of length STATE_DIM.

    Normalization keeps all values roughly in [0, 1] so the network trains
    stably. Values above the normalization ceiling are clipped at 2.0.
    """
    a = state["approaches"]
    d = state["downstream_status"]
    p = state["pedestrians"]

    cong = {"free": 0.0, "moderate": 0.5, "congested": 1.0}

    vec = np.array([
        # Queue length per direction (typical max ~30 vehicles)
        a["north"]["queue_length"]           / 20,
        a["south"]["queue_length"]           / 20,
        a["east"]["queue_length"]            / 20,
        a["west"]["queue_length"]            / 20,
        # Average waiting time per direction (seconds, typical max ~200s)
        a["north"]["average_waiting_time"]   / 100,
        a["south"]["average_waiting_time"]   / 100,
        a["east"]["average_waiting_time"]    / 100,
        a["west"]["average_waiting_time"]    / 100,
        # Vehicles arriving in next 30 s per direction
        a["north"]["incoming_vehicles_30s"]  / 10,
        a["south"]["incoming_vehicles_30s"]  / 10,
        a["east"]["incoming_vehicles_30s"]   / 10,
        a["west"]["incoming_vehicles_30s"]   / 10,
        # Phase: 0 = NS green, 1 = EW green
        1.0 if state["current_phase"] == 3 else 0.0,
        # How long the current phase has been running (normalized)
        state["phase_elapsed_time"]          / config.MAX_GREEN_TIME,
        # Congestion on the J1-J2 link
        cong.get(d["road_to_other"], 0.0),
        # Pedestrian demand
        p["waiting_count"]                   / 10,
        p["average_waiting_time"]            / 60,
    ], dtype=np.float32)

    return np.clip(vec, 0.0, 2.0)


class QNetwork(nn.Module):
    """
    Two-hidden-layer MLP.
    Input:  state vector (STATE_DIM = 17)
    Output: one Q-value per action (ACTION_DIM = 5)

    The Q-value for an action estimates the total future reward the agent
    expects if it takes that action from the current state.
    """
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(STATE_DIM, 64),
            nn.ReLU(),
            nn.Linear(64, 64),
            nn.ReLU(),
            nn.Linear(64, ACTION_DIM),
        )

    def forward(self, x):
        return self.net(x)


def _apply_safety(duration, state, sim_time, last_green_time, phase):
    """
    Hard safety layer identical to SCRIPT's constraints.
    The DQN recommends a duration; this enforces the engineering limits.
    The agent cannot violate min/max green, starvation rules, or pedestrian thresholds.
    """
    other_phase = 3 if phase == 0 else 0
    time_since_other = sim_time - last_green_time.get(other_phase, 0.0)

    # Starvation: other direction hasn't had green in too long
    if time_since_other > config.STARVATION_THRESHOLD:
        duration = max(config.SAFE_MIN_GREEN, min(duration, config.STARVATION_CAP))

    # Pedestrian priority
    p = state["pedestrians"]
    if p["waiting"] and p["max_waiting_time"] > config.PEDESTRIAN_FORCE_THRESHOLD:
        duration = config.SAFE_MIN_GREEN
    elif p["waiting"] and p["average_waiting_time"] > config.PEDESTRIAN_WAIT_THRESHOLD:
        duration = min(duration, config.DEFAULT_GREEN)

    return max(config.MIN_GREEN_TIME, min(config.MAX_GREEN_TIME, duration))


class AiController:
    """
    Inference-only DQN controller for use in run_experiment.py.
    Loads trained weights and picks the highest-Q action each green phase.
    Pass scenario= to load scenario-specific weights (dqn_{scenario}_weights.pt);
    falls back to dqn_weights.pt.
    """

    def __init__(self, junction_ids, scenario=None, weights_path=None):
        self.junction_ids = junction_ids
        self._last_seen_phase = {jid: None for jid in junction_ids}
        self._last_green_time = {jid: {0: 0.0, 3: 0.0} for jid in junction_ids}

        models_dir = os.path.join(config.SIM_DIR, "models")
        if weights_path:
            model_path = weights_path
        else:
            scenario_path = os.path.join(models_dir, f"dqn_{scenario}_weights.pt") if scenario else None
            default_path  = os.path.join(models_dir, "dqn_weights.pt")
            model_path = scenario_path if (scenario_path and os.path.exists(scenario_path)) else default_path

        self.q_net = QNetwork()
        if os.path.exists(model_path):
            self.q_net.load_state_dict(torch.load(model_path, map_location="cpu", weights_only=True))
            self.q_net.eval()
            print(f"[AI] Loaded DQN weights from {model_path}")
        else:
            print(f"[AI] WARNING: no weights at {model_path} — run train_dqn.py first.")

    def step(self, sim_time):
        for jid in self.junction_ids:
            phase = traci.trafficlight.getPhase(jid)
            if phase in GREEN_PHASES:
                self._last_green_time[jid][phase] = sim_time

            new_phase = phase != self._last_seen_phase[jid]
            self._last_seen_phase[jid] = phase

            if phase not in GREEN_PHASES or not new_phase:
                continue

            state = state_builder.build_state(jid)
            vec = state_to_vector(state)

            with torch.no_grad():
                q_vals = self.q_net(torch.tensor(vec).unsqueeze(0))
            action_idx = q_vals.argmax().item()
            duration = ACTIONS[action_idx]

            duration = _apply_safety(duration, state, sim_time,
                                     self._last_green_time[jid], phase)
            traci.trafficlight.setPhaseDuration(jid, duration)
