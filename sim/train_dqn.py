"""
DQN Training Script — Smart Urban Intersection System.

Trains the DQN agent by running many SUMO episodes. Each episode is a full
600-second simulation. At every green-phase start the agent picks a duration,
the simulation runs, and the agent learns from the reward (negative waiting time).

After training, weights are saved to sim/models/dqn_weights.pt.
A CSV training log is saved to sim/results/dqn_training_<scenario>.csv.

Usage:
    cd "D:/Ziv - OS/Projects/Trafic AI"
    python sim/train_dqn.py --scenario heavy_west --episodes 3000
    python sim/train_dqn.py --scenario balanced   --episodes 3000

Evaluate after training:
    python sim/run_experiment.py --mode ai --scenario heavy_west
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
import torch.optim as optim
import sumolib
import traci

sys.path.insert(0, os.path.dirname(__file__))
from modules import config, state_builder
from controllers.ai_controller import (
    QNetwork, ACTIONS, state_to_vector, _apply_safety
)

# ── Hyperparameters ──────────────────────────────────────────────────────────
GAMMA         = 0.95    # discount: how much future rewards matter vs. immediate
LR            = 1e-3    # learning rate for Adam optimizer
BUFFER_SIZE   = 10_000  # max experiences stored in replay buffer
BATCH_SIZE    = 64      # experiences sampled per training update
EPS_START     = 1.0     # epsilon start: 100% random exploration
EPS_END       = 0.05    # epsilon floor: 5% random after full decay
EPS_DECAY     = 0.997   # epsilon *= EPS_DECAY after each episode
TARGET_UPDATE = 50      # copy online → target network every N episodes
TRAIN_START   = 300     # don't train until buffer has this many experiences

# v2 reward shaping: penalize each new vehicle stop to discourage rapid cycling.
# Each new stop costs this many "waiting-seconds" equivalents in the reward.
STOP_PENALTY  = 20

GREEN_PHASES = {0, 3}


# ── Replay Buffer ─────────────────────────────────────────────────────────────
Experience = collections.namedtuple(
    "Experience", ["state", "action", "reward", "next_state", "done"]
)


class ReplayBuffer:
    """
    Stores past (state, action, reward, next_state) tuples.
    Randomly samples batches so the network doesn't overfit to recent events.
    Acts like a deque — oldest entries drop off when full.
    """
    def __init__(self, capacity):
        self.buf = collections.deque(maxlen=capacity)

    def push(self, state, action, reward, next_state, done):
        self.buf.append(Experience(state, action, reward, next_state, done))

    def sample(self, n):
        batch = random.sample(self.buf, n)
        s, a, r, s2, d = zip(*batch)
        return (
            torch.tensor(np.array(s),  dtype=torch.float32),
            torch.tensor(a,            dtype=torch.long),
            torch.tensor(r,            dtype=torch.float32),
            torch.tensor(np.array(s2), dtype=torch.float32),
            torch.tensor(d,            dtype=torch.float32),
        )

    def __len__(self):
        return len(self.buf)


# ── DQN Agent ─────────────────────────────────────────────────────────────────
class DQNAgent:
    """
    Two networks:
      online  — picks actions + gets updated every training step
      target  — provides stable Q-value targets (updated every TARGET_UPDATE episodes)

    Using two networks is the key DQN trick: without it the targets move every
    step and training oscillates/diverges.
    """
    def __init__(self):
        self.online  = QNetwork()
        self.target  = QNetwork()
        self.target.load_state_dict(self.online.state_dict())
        self.target.eval()

        self.optimizer = optim.Adam(self.online.parameters(), lr=LR)
        self.buffer    = ReplayBuffer(BUFFER_SIZE)
        self.epsilon   = EPS_START

    def choose_action(self, state_vec):
        """
        ε-greedy policy:
        - With probability ε: pick a random action (explore)
        - Otherwise: pick the action with the highest Q-value (exploit)
        ε starts high and decays over training so the agent explores early
        and exploits what it has learned later.
        """
        if random.random() < self.epsilon:
            return random.randrange(len(ACTIONS))
        with torch.no_grad():
            q = self.online(torch.tensor(state_vec).unsqueeze(0))
        return q.argmax().item()

    def train_step(self):
        """One gradient update using a random batch from the replay buffer."""
        if len(self.buffer) < TRAIN_START:
            return None

        s, a, r, s2, done = self.buffer.sample(BATCH_SIZE)

        # Q-values the online network predicted for the actions that were taken
        q_current = self.online(s).gather(1, a.unsqueeze(1)).squeeze(1)

        # Double DQN target: use ONLINE network to SELECT the best action,
        # use TARGET network to EVALUATE it. Prevents Q-value overestimation
        # that causes the agent to be overconfident about suboptimal actions.
        with torch.no_grad():
            best_actions = self.online(s2).argmax(1, keepdim=True)
            q_next       = self.target(s2).gather(1, best_actions).squeeze(1)
            q_target     = r + GAMMA * q_next * (1 - done)

        loss = nn.functional.mse_loss(q_current, q_target)
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()
        return loss.item()

    def update_target(self):
        """Copy online network weights into the target network."""
        self.target.load_state_dict(self.online.state_dict())

    def decay_epsilon(self):
        self.epsilon = max(EPS_END, self.epsilon * EPS_DECAY)

    def save(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        torch.save(self.online.state_dict(), path)


# ── Simulation helpers ────────────────────────────────────────────────────────
def _total_waiting_time():
    """Total accumulated waiting time across all vehicles right now."""
    return sum(traci.vehicle.getWaitingTime(v) for v in traci.vehicle.getIDList())


def _count_new_stops(prev_stopped: set):
    """
    Returns (new_stop_count, current_stopped_set).
    A 'new stop' is a vehicle that just dropped below 0.1 m/s this step.
    Used by the stop-penalty term in the reward function.
    """
    current = {v for v in traci.vehicle.getIDList()
               if traci.vehicle.getSpeed(v) < 0.1}
    return len(current - prev_stopped), current


def _start_sumo(scenario, end_time, gui=False):
    route_file = os.path.join(config.SCENARIOS_DIR, f"{scenario}.rou.xml")
    ped_file   = os.path.join(config.SCENARIOS_DIR, f"{scenario}.ped.xml")
    routes     = f"{route_file},{ped_file}" if os.path.exists(ped_file) else route_file

    binary = sumolib.checkBinary("sumo-gui" if gui else "sumo")
    traci.start([
        binary,
        "-n", config.NET_FILE,
        "-r", routes,
        "-b", "0", "-e", str(end_time),
        "--no-step-log",  "true",
        "--no-warnings",  "true",
    ])


# ── Episode runner ─────────────────────────────────────────────────────────────
def run_episode(agent, scenario, end_time, gui=False):
    """
    Run one full SUMO episode.

    For each junction, every time a green phase starts:
      1. Store the experience from the PREVIOUS decision (state, action, reward accumulated)
      2. Train the network on a random batch
      3. Make a new decision for this phase

    The reward for a decision = sum of (-waiting_time) at every simulation step
    from when the decision was made until the next decision for that junction.
    This way the agent learns that good decisions lead to lower wait times
    over the duration of the green phase it set.

    Returns (total_episode_reward, number_of_decisions_made).
    """
    _start_sumo(scenario, end_time, gui)

    last_seen_phase  = {jid: None  for jid in config.CONTROLLED_JUNCTIONS}
    last_green_time  = {jid: {0: 0.0, 3: 0.0} for jid in config.CONTROLLED_JUNCTIONS}
    pending          = {jid: None  for jid in config.CONTROLLED_JUNCTIONS}  # (vec, action_idx)
    accum_reward     = {jid: 0.0   for jid in config.CONTROLLED_JUNCTIONS}
    prev_stopped     = set()   # vehicles that were already stopped last step

    total_reward = 0.0
    n_decisions  = 0

    try:
        while traci.simulation.getMinExpectedNumber() > 0:
            traci.simulationStep()
            sim_time = traci.simulation.getTime()

            new_stops, prev_stopped = _count_new_stops(prev_stopped)
            # Reward = negative waiting time - penalty for each new vehicle stop.
            # The stop penalty discourages rapid phase cycling (v2 improvement).
            step_reward   = -_total_waiting_time() - STOP_PENALTY * new_stops
            total_reward += step_reward

            for jid in config.CONTROLLED_JUNCTIONS:
                # Accumulate reward towards the current pending experience
                if pending[jid] is not None:
                    accum_reward[jid] += step_reward

                phase = traci.trafficlight.getPhase(jid)
                if phase in GREEN_PHASES:
                    last_green_time[jid][phase] = sim_time

                new_phase = phase != last_seen_phase[jid]
                last_seen_phase[jid] = phase

                if phase not in GREEN_PHASES or not new_phase:
                    continue

                # New green phase — build current state
                state   = state_builder.build_state(jid)
                cur_vec = state_to_vector(state)

                # Store previous experience now that we have the next state
                if pending[jid] is not None:
                    prev_vec, prev_action = pending[jid]
                    agent.buffer.push(prev_vec, prev_action, accum_reward[jid], cur_vec, 0.0)
                    agent.train_step()

                # Make new decision for this green phase
                action_idx = agent.choose_action(cur_vec)
                duration   = ACTIONS[action_idx]
                duration   = _apply_safety(duration, state, sim_time,
                                           last_green_time[jid], phase)
                traci.trafficlight.setPhaseDuration(jid, duration)

                pending[jid]      = (cur_vec, action_idx)
                accum_reward[jid] = 0.0
                n_decisions      += 1

    finally:
        traci.close()

    return total_reward, n_decisions


# ── Main training loop ────────────────────────────────────────────────────────
def train(scenario, num_episodes, end_time, gui_episode=None, multi_seed=False, n_train_seeds=20):
    suffix     = "_ms" if multi_seed else ""
    model_path = os.path.join(config.SIM_DIR, "models", f"dqn_{scenario}{suffix}_weights.pt")
    log_path   = os.path.join(config.RESULTS_DIR, f"dqn_training_{scenario}{suffix}.csv")

    agent        = DQNAgent()
    best_reward  = float("-inf")

    print(f"Training DQN on '{scenario}' for {num_episodes} episodes"
          + (f" [multi-seed 1–{n_train_seeds}]" if multi_seed else "") + ".")
    print(f"Model will be saved to: {model_path}")
    print(f"Training log:           {log_path}\n")

    with open(log_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["episode", "total_reward", "avg_reward_per_decision", "epsilon"])

        for ep in range(1, num_episodes + 1):
            gui      = (gui_episode is not None and ep == gui_episode)
            ep_scenario = f"{scenario}_s{random.randint(1, n_train_seeds)}" if multi_seed else scenario
            total_r, n_dec = run_episode(agent, ep_scenario, end_time, gui=gui)
            avg_r    = total_r / max(n_dec, 1)

            agent.decay_epsilon()

            if ep % TARGET_UPDATE == 0:
                agent.update_target()

            # Save weights whenever this is the best episode so far
            if total_r > best_reward:
                best_reward = total_r
                agent.save(model_path)

            writer.writerow([ep, round(total_r, 2), round(avg_r, 4), round(agent.epsilon, 4)])
            f.flush()

            if ep % 10 == 0 or ep == 1:
                print(f"Ep {ep:4d}/{num_episodes}  "
                      f"reward: {total_r:10.0f}  "
                      f"avg/decision: {avg_r:7.1f}  "
                      f"ε: {agent.epsilon:.3f}  "
                      f"buffer: {len(agent.buffer)}")

    print(f"\nDone. Best reward: {best_reward:.0f}")
    print(f"Weights → {model_path}")
    print(f"Log     → {log_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario",     default="heavy_west",
                        choices=["balanced", "heavy_west", "pedestrian_heavy",
                                 "morning_flow", "evening_flow", "day_cycle"])
    parser.add_argument("--episodes",     type=int, default=3000)
    parser.add_argument("--end",          type=int, default=config.SIM_END_TIME)
    parser.add_argument("--gui-ep",       type=int, default=None)
    parser.add_argument("--multi-seed",   action="store_true",
                        help="Pick a random seed (1–n) each episode from pre-generated {scenario}_s*.rou.xml files")
    parser.add_argument("--n-train-seeds", type=int, default=20,
                        help="Number of training seeds available (default 20)")
    args = parser.parse_args()
    train(args.scenario, args.episodes, args.end, args.gui_ep,
          multi_seed=args.multi_seed, n_train_seeds=args.n_train_seeds)
