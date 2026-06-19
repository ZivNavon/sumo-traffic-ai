"""
SCRIPT v0 -- simple adaptive proportional controller (initial version).

Kept for reference / comparison only. This is the FIRST working SCRIPT
implementation, before the v1 network-aware tuning pass. It uses a single
proportional formula with no deadband, no downstream-congestion penalty,
and no J1<->J2 coordination -- and it underperformed TIMER on both test
scenarios (see PROGRESS.md / REQUIREMENTS_CHECKLIST.md for results).

The current production controller is script_controller.py ("SCRIPT v1 --
network-aware adaptive controller"), which adds:
  - downstream congestion penalty
  - J1->J2 coordination boost
  - load deadband / hysteresis
  - bucketed (non-proportional) green durations
  - starvation cap instead of forced absolute minimum
  - pedestrian max-wait force vs avg-wait cap

TLS program structure (from sim/network/grid.net.xml, identical for B1/C1):
  phase 0 (37s green): NORTH + SOUTH approaches green, EAST+WEST red
  phase 1 (5s):  same, pedestrian-green tail ending
  phase 2 (3s yellow): NS -> EW transition
  phase 3 (37s green): EAST + WEST approaches green, NS red
  phase 4 (5s):  same, pedestrian-green tail ending
  phase 5 (3s yellow): EW -> NS transition
"""

import traci

from modules import config, state_builder


GROUP_NS = ("north", "south")
GROUP_EW = ("east", "west")
GREEN_PHASES = {0: GROUP_NS, 3: GROUP_EW}


def load_score(approach_state):
    return (
        0.35 * approach_state["queue_length"]
        + 0.30 * approach_state["average_waiting_time"]
        + 0.20 * approach_state["incoming_vehicles_30s"]
        + 0.15 * approach_state["max_waiting_time"]
    )


class ScriptControllerV0:
    def __init__(self, junction_ids):
        self.junction_ids = junction_ids
        self._last_seen_phase = {jid: None for jid in junction_ids}
        self._last_green_time = {jid: {0: 0.0, 3: 0.0} for jid in junction_ids}

    def step(self, sim_time):
        for jid in self.junction_ids:
            phase, elapsed = self._phase_info(jid)

            if phase in GREEN_PHASES:
                self._last_green_time[jid][phase] = sim_time

            new_phase = phase != self._last_seen_phase[jid]
            self._last_seen_phase[jid] = phase

            if phase not in GREEN_PHASES:
                continue

            if new_phase:
                self._decide_duration(jid, phase, sim_time)
            else:
                self._check_starvation(jid, phase, elapsed, sim_time)

    def _phase_info(self, tls_id):
        phase = traci.trafficlight.getPhase(tls_id)
        next_switch = traci.trafficlight.getNextSwitch(tls_id)
        elapsed = traci.trafficlight.getPhaseDuration(tls_id) - (next_switch - traci.simulation.getTime())
        return phase, max(elapsed, 0.0)

    def _decide_duration(self, jid, phase, sim_time):
        state = state_builder.build_state(jid)
        current_dirs = GREEN_PHASES[phase]
        other_phase = 3 if phase == 0 else 0
        other_dirs = GREEN_PHASES[other_phase]

        load_current = sum(load_score(state["approaches"][d]) for d in current_dirs)
        load_other = sum(load_score(state["approaches"][d]) for d in other_dirs)

        total = load_current + load_other
        ratio = load_current / total if total > 0 else 0.5

        duration = config.MIN_GREEN_TIME + ratio * (config.MAX_GREEN_TIME - config.MIN_GREEN_TIME)

        if state["pedestrians"]["waiting"] and state["pedestrians"]["average_waiting_time"] > config.PEDESTRIAN_WAIT_THRESHOLD:
            duration = config.MIN_GREEN_TIME

        time_since_other_green = sim_time - self._last_green_time[jid][other_phase]
        if time_since_other_green > config.STARVATION_THRESHOLD:
            duration = config.MIN_GREEN_TIME

        duration = max(config.MIN_GREEN_TIME, min(config.MAX_GREEN_TIME, duration))
        traci.trafficlight.setPhaseDuration(jid, duration)

    def _check_starvation(self, jid, phase, elapsed, sim_time):
        other_phase = 3 if phase == 0 else 0
        time_since_other_green = sim_time - self._last_green_time[jid][other_phase]
        if elapsed >= config.MAX_GREEN_TIME and time_since_other_green > config.STARVATION_THRESHOLD:
            traci.trafficlight.setPhaseDuration(jid, elapsed)
