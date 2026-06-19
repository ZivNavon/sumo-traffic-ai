"""
Data Collection Module.

Thin wrappers around TraCI that pull the raw simulation data needed by the
State Builder: per-lane queues/waiting times, incoming vehicles within a
time window, pedestrian waiting at crossings, and congestion on a given edge.

All functions assume an active TraCI connection (traci.start already called).
"""

import traci

from . import config


def get_lane_ids_for_edge(edge_id):
    n_lanes = traci.edge.getLaneNumber(edge_id)
    return [f"{edge_id}_{i}" for i in range(n_lanes)]


def queue_length(edge_id, speed_threshold=0.1):
    """Number of vehicles on the edge moving slower than speed_threshold (m/s)."""
    count = 0
    for veh_id in traci.edge.getLastStepVehicleIDs(edge_id):
        if traci.vehicle.getSpeed(veh_id) < speed_threshold:
            count += 1
    return count


def waiting_times(edge_id):
    """List of accumulated waiting times (s) for vehicles currently on edge_id."""
    return [traci.vehicle.getWaitingTime(v) for v in traci.edge.getLastStepVehicleIDs(edge_id)]


def average_speed(edge_id):
    vehs = traci.edge.getLastStepVehicleIDs(edge_id)
    if not vehs:
        return 0.0
    speeds = [traci.vehicle.getSpeed(v) for v in vehs]
    return sum(speeds) / len(speeds)


def incoming_vehicles_within(edge_id, horizon_s=config.INCOMING_WINDOW):
    """
    Estimate how many vehicles currently on edge_id will reach its end
    within `horizon_s` seconds, based on current speed and remaining distance.
    """
    edge_len = traci.lane.getLength(f"{edge_id}_0")
    count = 0
    for veh_id in traci.edge.getLastStepVehicleIDs(edge_id):
        speed = traci.vehicle.getSpeed(veh_id)
        if speed <= 0.1:
            continue
        pos = traci.vehicle.getLanePosition(veh_id)
        remaining = max(edge_len - pos, 0)
        eta = remaining / speed
        if eta <= horizon_s:
            count += 1
    return count


def edge_congestion_level(edge_id, jam_occupancy=0.5, moderate_occupancy=0.2):
    """
    Classify an edge as 'free', 'moderate' or 'congested' based on lane
    occupancy (fraction of the lane length covered by vehicles).
    """
    occ = traci.edge.getLastStepOccupancy(edge_id) / 100.0
    if occ >= jam_occupancy:
        return "congested"
    if occ >= moderate_occupancy:
        return "moderate"
    return "free"


def pedestrian_waiting_at_junction(junction_id, persons_cache=None):
    """
    Returns (waiting_count, avg_waiting_time, max_waiting_time) for
    pedestrians currently waiting (speed ~ 0) near the given junction.
    `persons_cache` may be a pre-fetched list of person IDs (traci.person.getIDList()).
    """
    persons = persons_cache if persons_cache is not None else traci.person.getIDList()
    waits = []
    for p in persons:
        try:
            edge = traci.person.getRoadID(p)
            speed = traci.person.getSpeed(p)
        except traci.TraCIException:
            continue
        # crude proxy: pedestrian on an edge adjacent to the junction and not moving
        if speed < 0.1 and (edge.endswith(junction_id) or junction_id in edge):
            waits.append(traci.person.getWaitingTime(p))
    if not waits:
        return 0, 0.0, 0.0
    return len(waits), sum(waits) / len(waits), max(waits)


def current_phase_info(tls_id):
    """Returns (phase_index, phase_state_string, time_since_last_switch)."""
    phase = traci.trafficlight.getPhase(tls_id)
    state = traci.trafficlight.getRedYellowGreenState(tls_id)
    next_switch = traci.trafficlight.getNextSwitch(tls_id)
    program_duration = traci.trafficlight.getPhaseDuration(tls_id)
    elapsed = program_duration - (next_switch - traci.simulation.getTime())
    return phase, state, max(elapsed, 0)
