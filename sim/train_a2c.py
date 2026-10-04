"""
A2C Training Script — Smart Urban Intersection System.

A2C (Advantage Actor-Critic) is a policy-gradient method — fundamentally
different from DQN:

  DQN (value-based):
    - Learns Q(s,a) = expected future return for each action
    - Off-policy: learns from a replay buffer of past experiences
    - Picks action = argmax Q(s,a) (deterministic policy)

  A2C (policy-gradient):
    - Learns π(a|s) = probability distribution over actions (Actor)
    - Also learns V(s) = state value used to compute advantages (Critic)
    - On-policy: learns from fresh experience each episode (no replay buffer)
    - Picks action by sampling from π (stochastic during training, greedy at eval)
    - Advantage A(s,a) = R_t - V(s_t): how much better was the action vs average?

Usage:
    python sim/train_a2c.py --scenario heavy_west --episodes 1000
    python sim/train_a2c.py --scenario balanced   --episodes 1000

Evaluate:
    python sim/run_experiment.py --mode a2c --scenario heavy_west
"""

import argparse
import collections
import csv
import os
import random
import sys

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.distributions import Categorical
import sumolib
import traci

sys.path.insert(0, os.path.dirname(__file__))
from modules import config, state_builder
from controllers.ai_controller import ACTIONS, state_to_vector, _apply_safety
from controllers.a2c_controller import ActorCritic

# ── Hyperparameters ──────────────────────────────────────────────────────────
GAMMA        = 0.95    # discount factor (same as DQN for fair comparison)
LR           = 1e-3    # Adam learning rate
ENTROPY_COEF = 0.01    # entropy bonus weight: encourages exploration
VALUE_COEF   = 0.5     # critic loss weight relative to actor loss
STOP_PENALTY = 20      # same stop penalty as DQN v2

GREEN_PHASES = {0, 3}

# One experience along a junction's on-policy trajectory
Step = collections.namedtuple("Step", ["state", "action", "reward"])


# ── Helpers ──────────────────────────────────────────────────────────────────
def _total_waiting_time():
    return sum(traci.vehicle.getWaitingTime(v) for v in traci.vehicle.getIDList())


def _count_new_stops(prev_stopped):
    current = {v for v in traci.vehicle.getIDList()
               if traci.vehicle.getSpeed(v) < 0.1}
    return len(current - prev_stopped), current


def _start_sumo(scenario, end_time, gui=False):
    route_file = os.path.join(config.SCENARIOS_DIR, f"{scenario}.rou.xml")
    ped_file   = os.path.join(config.SCENARIOS_DIR, f"{scenario}.ped.xml")
    routes     = f"{route_file},{ped_file}" if os.path.exists(ped_file) else route_file
    binary     = sumolib.checkBinary("sumo-gui" if gui else "sumo")
    traci.start([
        binary, "-n", config.NET_FILE, "-r", routes,
        "-b", "0", "-e", str(end_time),
        "--no-step-log", "true", "--no-warnings", "true",
    ])


def compute_returns(rewards, gamma):
    """Compute discounted returns backwards from episode end."""
    returns = []
    R = 0.0
    for r in reversed(rewards):
        R = r + gamma * R
        returns.insert(0, R)
    return returns


# ── Episode runner ────────────────────────────────────────────────────────────
def run_episode(net, scenario, end_time, gui=False):
    """
    Collect one full on-policy episode.

    For each junction, records (state, action) at every green phase onset
    and accumulates reward until the next decision. Returns per-junction
    trajectories for the A2C update.
    """
    _start_sumo(scenario, end_time, gui)

    trajectories = {jid: [] for jid in config.CONTROLLED_JUNCTIONS}
    last_seen    = {jid: None  for jid in config.CONTROLLED_JUNCTIONS}
    last_green   = {jid: {0: 0.0, 3: 0.0} for jid in config.CONTROLLED_JUNCTIONS}
    pending      = {jid: None  for jid in config.CONTROLLED_JUNCTIONS}  # (vec, action_idx)
    accum_r      = {jid: 0.0   for jid in config.CONTROLLED_JUNCTIONS}
    prev_stopped = set()
    total_reward = 0.0

    try:
        while traci.simulation.getMinExpectedNumber() > 0:
            traci.simulationStep()
            sim_time = traci.simulation.getTime()

            new_stops, prev_stopped = _count_new_stops(prev_stopped)
            step_r   = -_total_waiting_time() - STOP_PENALTY * new_stops
            total_reward += step_r

            for jid in config.CONTROLLED_JUNCTIONS:
                if pending[jid] is not None:
                    accum_r[jid] += step_r

                phase = traci.trafficlight.getPhase(jid)
                if phase in GREEN_PHASES:
                    last_green[jid][phase] = sim_time

                new_phase = phase != last_seen[jid]
                last_seen[jid] = phase

                if phase not in GREEN_PHASES or not new_phase:
                    continue

                state   = state_builder.build_state(jid)
                cur_vec = state_to_vector(state)

                if pending[jid] is not None:
                    prev_vec, act = pending[jid]
                    trajectories[jid].append(Step(prev_vec, act, accum_r[jid]))

                with torch.no_grad():
                    logits, _ = net(torch.tensor(cur_vec).unsqueeze(0))
                    dist = Categorical(logits=logits.squeeze(0))
                    action_idx = dist.sample().item()

                duration = ACTIONS[action_idx]
                duration = _apply_safety(duration, state, sim_time, last_green[jid], phase)
                traci.trafficlight.setPhaseDuration(jid, duration)

                pending[jid] = (cur_vec, action_idx)
                accum_r[jid] = 0.0

    finally:
        traci.close()

    return trajectories, total_reward


# ── A2C update ────────────────────────────────────────────────────────────────
def update(net, optimizer, trajectories):
    """
    One gradient update from all junction trajectories collected this episode.

    For each step in each trajectory:
      - Compute discounted return R_t
      - Advantage A_t = R_t - V(s_t)  (how much better than expected)
      - Actor loss:  -log π(a_t|s_t) * A_t.detach()  (REINFORCE with baseline)
      - Critic loss: (R_t - V(s_t))²  (fit the value function)
      - Entropy:     -Σ π(a|s) log π(a|s)  (exploration bonus)

    Total loss = actor_loss + VALUE_COEF * critic_loss - ENTROPY_COEF * entropy
    """
    actor_losses  = []
    critic_losses = []
    entropies     = []

    for jid, traj in trajectories.items():
        if not traj:
            continue

        states  = torch.tensor(np.array([s.state  for s in traj]), dtype=torch.float32)
        actions = torch.tensor([s.action for s in traj],            dtype=torch.long)
        returns = torch.tensor(compute_returns([s.reward for s in traj], GAMMA),
                               dtype=torch.float32)

        logits, values = net(states)
        dist     = Categorical(logits=logits)
        log_probs = dist.log_prob(actions)
        entropy   = dist.entropy().mean()

        advantages = (returns - values.detach())

        actor_losses.append(-(log_probs * advantages).mean())
        critic_losses.append(F.mse_loss(values, returns))
        entropies.append(entropy)

    if not actor_losses:
        return None

    loss = (sum(actor_losses) / len(actor_losses)
            + VALUE_COEF  * sum(critic_losses) / len(critic_losses)
            - ENTROPY_COEF * sum(entropies)    / len(entropies))

    optimizer.zero_grad()
    loss.backward()
    torch.nn.utils.clip_grad_norm_(net.parameters(), max_norm=0.5)
    optimizer.step()
    return loss.item()


# ── Main training loop ────────────────────────────────────────────────────────
def train(scenario, num_episodes, end_time, gui_episode=None, multi_seed=False, n_train_seeds=20):
    suffix     = "_ms" if multi_seed else ""
    model_path = os.path.join(config.SIM_DIR, "models", f"a2c_{scenario}{suffix}_weights.pt")
    log_path   = os.path.join(config.RESULTS_DIR, f"a2c_training_{scenario}{suffix}.csv")

    net       = ActorCritic()
    optimizer = optim.Adam(net.parameters(), lr=LR)
    best_reward = float("-inf")

    print(f"Training A2C on '{scenario}' for {num_episodes} episodes"
          + (f" [multi-seed 1–{n_train_seeds}]" if multi_seed else "") + ".")
    print(f"Model → {model_path}\n")

    with open(log_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["episode", "total_reward", "loss"])

        for ep in range(1, num_episodes + 1):
            gui = (gui_episode is not None and ep == gui_episode)
            ep_scenario = f"{scenario}_s{random.randint(1, n_train_seeds)}" if multi_seed else scenario
            trajectories, total_r = run_episode(net, ep_scenario, end_time, gui=gui)
            loss = update(net, optimizer, trajectories)

            if total_r > best_reward:
                best_reward = total_r
                os.makedirs(os.path.dirname(model_path), exist_ok=True)
                torch.save(net.state_dict(), model_path)

            writer.writerow([ep, round(total_r, 2), round(loss, 4) if loss else ""])
            f.flush()

            if ep % 10 == 0 or ep == 1:
                print(f"Ep {ep:4d}/{num_episodes}  "
                      f"reward: {total_r:10.0f}  "
                      f"loss: {loss:8.4f}" if loss else
                      f"Ep {ep:4d}/{num_episodes}  reward: {total_r:10.0f}")

    print(f"\nDone. Best reward: {best_reward:.0f}")
    print(f"Weights → {model_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario",     default="heavy_west",
                        choices=["balanced", "heavy_west", "pedestrian_heavy",
                                 "morning_flow", "evening_flow", "day_cycle"])
    parser.add_argument("--episodes",     type=int, default=1000)
    parser.add_argument("--end",          type=int, default=config.SIM_END_TIME)
    parser.add_argument("--gui-ep",       type=int, default=None)
    parser.add_argument("--multi-seed",   action="store_true",
                        help="Pick a random seed (1–n) each episode from pre-generated {scenario}_s*.rou.xml files")
    parser.add_argument("--n-train-seeds", type=int, default=20)
    args = parser.parse_args()
    train(args.scenario, args.episodes, args.end, args.gui_ep,
          multi_seed=args.multi_seed, n_train_seeds=args.n_train_seeds)
