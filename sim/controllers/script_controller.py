"""
SCRIPT v1 -- network-aware adaptive controller (production version).

The original simple proportional controller (SCRIPT v0, no deadband, no
downstream penalty, no J1<->J2 coordination) is kept for reference in
script_controller_v0.py / ScriptControllerV0. v1 adds all of the following
on top of it:
  load calculation, pedestrian priority, starvation prevention, min/max
  green, deadband, downstream-congestion penalty, J1<->J2 coordination,
  and feeds into the same result-metrics pipeline (sim/modules/metrics.py).

TLS program structure (from sim/network/grid.net.xml, identical for B1/C1):
  phase 0 (green): NORTH + SOUTH approaches green, EAST+WEST red
                   (perpendicular pedestrian crossing -- the one used by
                   the EW phase -- is RED during this phase)
  phase 1 (green tail), phase 2 (yellow): NS -> EW transition
  phase 3 (green): EAST + WEST approaches green, NORTH+SOUTH red
                   (perpendicular pedestrian crossing -- the one used by
                   the NS phase -- is RED during this phase)
  phase 4 (green tail), phase 5 (yellow): EW -> NS transition

SCRIPT mode only decides the *duration* of the current green phase (0 or 3)
at the moment it starts (plus one mid-phase safeguard). Yellow / green-tail
phases are left untouched so all transitions stay legal.

Decision pipeline per green-phase start:
  1. Raw load score per direction-group (NS vs EW).
  2. Downstream-congestion penalty on each group's load (Problem 4).
  3. J1->J2 coordination boost for J2's matching group (Problem 5).
  4. Deadband / hysteresis: if the (penalized/boosted) load ratio is close
     to 0.5, just use DEFAULT_GREEN (Problem 3).
  5. Otherwise pick a duration from fixed buckets based on the ratio
     (Problem 6) instead of a fully proportional formula.
  6. Starvation cap: if the other group hasn't had green in too long, clamp
     duration into [SAFE_MIN_GREEN, STARVATION_CAP] rather than forcing the
     absolute minimum (Problem 2).
  7. Pedestrian priority (Problem 1):
       - max wait > PEDESTRIAN_FORCE_THRESHOLD -> force duration = SAFE_MIN_GREEN
         (this phase's perpendicular pedestrian crossing is the one that's
         currently red, so ending this phase sooner serves it next)
       - avg wait > PEDESTRIAN_WAIT_THRESHOLD and count > 0 -> cap duration
         at DEFAULT_GREEN (don't let it run long while peds are waiting)
  8. Clamp to [MIN_GREEN_TIME, MAX_GREEN_TIME] as a hard safety bound.
"""

import traci

from modules import config, state_builder, data_collection as dc


GROUP_NS = ("north", "south")
GROUP_EW = ("east", "west")
GREEN_PHASES = {0: GROUP_NS, 3: GROUP_EW}

# Which approach edge each junction would push extra traffic into, per group
# (used for the downstream-congestion penalty). Both networks funnel most
# through/right movements onto the J1<->J2 link, so we attribute the link's
# congestion to the EW group (the group containing the "west"/"east"
# approach that directly faces the other controlled junction).
DOWNSTREAM_LINK_EDGE = {
    config.J1_ID: config.J1_TO_J2_EDGE,  # B1C1
    config.J2_ID: config.J2_TO_J1_EDGE,  # C1B1
}
DOWNSTREAM_PENALIZED_GROUP = "east_west"  # GROUP_EW for both J1 and J2


def load_score(approach_state):
    return (
        0.35 * approach_state["queue_length"]
        + 0.30 * approach_state["average_waiting_time"]
        + 0.20 * approach_state["incoming_vehicles_30s"]
        + 0.15 * approach_state["max_waiting_time"]
    )


def bucket_duration(ratio):
    for threshold, duration in config.DURATION_BUCKETS:
        if ratio > threshold:
            return duration
    return config.DURATION_BUCKET_FLOOR


class ScriptController:
    def __init__(self, junction_ids):
        self.junction_ids = junction_ids
        self._last_seen_phase = {jid: None for jid in junction_ids}
        self._last_green_time = {jid: {0: 0.0, 3: 0.0} for jid in junction_ids}

    def step(self, sim_time):
        # J1 -> J2 coordination signal: how many vehicles on the J1->J2 link
        # are expected to reach J2 within the incoming window.
        incoming_j1_to_j2 = dc.incoming_vehicles_within(config.J1_TO_J2_EDGE)

        for jid in self.junction_ids:
            phase, elapsed = self._phase_info(jid)

            if phase in GREEN_PHASES:
                self._last_green_time[jid][phase] = sim_time

            new_phase = phase != self._last_seen_phase[jid]
            self._last_seen_phase[jid] = phase

            if phase not in GREEN_PHASES:
                continue  # leave yellow / green-tail phases untouched

            if new_phase:
                self._decide_duration(jid, phase, sim_time, incoming_j1_to_j2)
            else:
                self._check_starvation(jid, phase, elapsed, sim_time)

    def _phase_info(self, tls_id):
        phase = traci.trafficlight.getPhase(tls_id)
        next_switch = traci.trafficlight.getNextSwitch(tls_id)
        elapsed = traci.trafficlight.getPhaseDuration(tls_id) - (next_switch - traci.simulation.getTime())
        return phase, max(elapsed, 0.0)

    def _decide_duration(self, jid, phase, sim_time, incoming_j1_to_j2):
        state = state_builder.build_state(jid)
        current_dirs = GREEN_PHASES[phase]
        other_phase = 3 if phase == 0 else 0
        other_dirs = GREEN_PHASES[other_phase]

        load_current = sum(load_score(state["approaches"][d]) for d in current_dirs)
        load_other = sum(load_score(state["approaches"][d]) for d in other_dirs)

        # --- Problem 4: downstream-congestion penalty -----------------
        link_edge = DOWNSTREAM_LINK_EDGE[jid]
        congestion = dc.edge_congestion_level(link_edge)
        factor = config.DOWNSTREAM_FACTOR.get(congestion, 1.0)
        if phase == 3:  # current group is EW -> the penalized group
            load_current *= factor
        else:
            load_other *= factor

        # --- Problem 5: J1 -> J2 coordination boost --------------------
        # J2's EW group (its "west" approach == B1C1, fed directly by J1) is
        # boosted if J1 is about to send a wave of vehicles its way and J2's
        # outgoing link toward J1 isn't already congested.
        if jid == config.J2_ID and incoming_j1_to_j2 > config.COORDINATION_INCOMING_THRESHOLD:
            j2_outflow_congestion = dc.edge_congestion_level(config.J2_TO_J1_EDGE)
            if j2_outflow_congestion != "congested":
                if phase == 3:
                    load_current *= config.COORDINATION_BOOST
                else:
                    load_other *= config.COORDINATION_BOOST

        total = load_current + load_other

        # --- Problem 3: deadband / hysteresis ---------------------------
        if total <= 0 or abs(load_current - load_other) / total < config.LOAD_DEADBAND:
            duration = config.DEFAULT_GREEN
        else:
            # --- Problem 6: bucketed (not fully proportional) duration --
            ratio = load_current / total
            duration = bucket_duration(ratio)

        # --- Problem 2: starvation cap, not forced absolute minimum -----
        time_since_other_green = sim_time - self._last_green_time[jid][other_phase]
        if time_since_other_green > config.STARVATION_THRESHOLD:
            duration = max(config.SAFE_MIN_GREEN, min(duration, config.STARVATION_CAP))

        # --- Problem 1: pedestrian priority ------------------------------
        peds = state["pedestrians"]
        if peds["waiting"] and peds["max_waiting_time"] > config.PEDESTRIAN_FORCE_THRESHOLD:
            duration = config.SAFE_MIN_GREEN
        elif peds["waiting"] and peds["average_waiting_time"] > config.PEDESTRIAN_WAIT_THRESHOLD:
            duration = min(duration, config.DEFAULT_GREEN)

        duration = max(config.MIN_GREEN_TIME, min(config.MAX_GREEN_TIME, duration))
        traci.trafficlight.setPhaseDuration(jid, duration)

    def _check_starvation(self, jid, phase, elapsed, sim_time):
        """Mid-phase safeguard: if this phase has already run MAX_GREEN_TIME
        and the other group is starving, end it now."""
        other_phase = 3 if phase == 0 else 0
        time_since_other_green = sim_time - self._last_green_time[jid][other_phase]
        if elapsed >= config.MAX_GREEN_TIME and time_since_other_green > config.STARVATION_THRESHOLD:
            traci.trafficlight.setPhaseDuration(jid, elapsed)
