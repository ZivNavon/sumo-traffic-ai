"""
AI controller — A2C (Advantage Actor-Critic).

Loads pre-trained weights from sim/models/a2c_{scenario}_weights.pt and uses
the actor head to pick green phase durations. Same interface as AiController.

Train first:
    python sim/train_a2c.py --scenario heavy_west --episodes 1000

Then evaluate:
    python sim/run_experiment.py --mode a2c --scenario heavy_west
"""

import os
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import traci

from modules import config, state_builder
from controllers.ai_controller import ACTIONS, STATE_DIM, ACTION_DIM, state_to_vector, _apply_safety

GREEN_PHASES = {0, 3}


class ActorCritic(nn.Module):
    """
    Shared-trunk Actor-Critic network.

    Shared trunk (2 hidden layers) extracts features from the state.
    Actor head outputs logits over actions — during training, sample from
    softmax(logits) for stochastic exploration. During eval, take argmax.
    Critic head outputs a scalar value estimate V(s) used to compute advantages.

    Key difference from DQN's QNetwork:
      DQN outputs Q(s,a) for all a — pick max.
      A2C outputs π(a|s) (actor) and V(s) (critic) separately.
    """
    def __init__(self):
        super().__init__()
        self.trunk = nn.Sequential(
            nn.Linear(STATE_DIM, 64), nn.ReLU(),
            nn.Linear(64, 64),        nn.ReLU(),
        )
        self.actor  = nn.Linear(64, ACTION_DIM)
        self.critic = nn.Linear(64, 1)

    def forward(self, x):
        h = self.trunk(x)
        return self.actor(h), self.critic(h).squeeze(-1)


class A2CController:
    """
    Inference-only A2C controller. Loads actor weights and picks the
    highest-probability action (greedy) at each green phase.
    """

    def __init__(self, junction_ids, scenario=None, weights_path=None):
        self.junction_ids = junction_ids
        self._last_seen_phase = {jid: None for jid in junction_ids}
        self._last_green_time = {jid: {0: 0.0, 3: 0.0} for jid in junction_ids}

        models_dir = os.path.join(config.SIM_DIR, "models")
        if weights_path:
            path = weights_path
        else:
            path = (os.path.join(models_dir, f"a2c_{scenario}_weights.pt")
                    if scenario else os.path.join(models_dir, "a2c_weights.pt"))

        self.net = ActorCritic()
        if os.path.exists(path):
            self.net.load_state_dict(torch.load(path, map_location="cpu", weights_only=True))
            self.net.eval()
            print(f"[A2C] Loaded weights from {path}")
        else:
            print(f"[A2C] WARNING: no weights at {path} — run train_a2c.py first.")

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
            vec   = state_to_vector(state)

            with torch.no_grad():
                logits, _ = self.net(torch.tensor(vec).unsqueeze(0))
                action_idx = F.softmax(logits, dim=-1).argmax().item()

            duration = ACTIONS[action_idx]
            duration = _apply_safety(duration, state, sim_time,
                                     self._last_green_time[jid], phase)
            traci.trafficlight.setPhaseDuration(jid, duration)
