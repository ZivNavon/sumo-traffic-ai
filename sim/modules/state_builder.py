"""
State Builder Module.

Converts raw TraCI data (via data_collection.py) into the structured state
dict for a controlled junction, matching the design in the project spec:

{
  "intersection_id": "J1",
  "current_phase": <int>,
  "phase_elapsed_time": <float>,
  "approaches": {
     "north": {"queue_length":.., "average_waiting_time":.., "max_waiting_time":..,
                "incoming_vehicles_30s":.., "average_speed":..},
     ...
  },
  "downstream_status": {"road_to_other": "free|moderate|congested", ...},
  "pedestrians": {"waiting": bool, "waiting_count":.., "average_waiting_time":.., "max_waiting_time":..}
}
"""

import traci

from . import config, data_collection as dc


def _approach_state(edge_id):
    waits = dc.waiting_times(edge_id)
    return {
        "queue_length": dc.queue_length(edge_id),
        "average_waiting_time": (sum(waits) / len(waits)) if waits else 0.0,
        "max_waiting_time": max(waits) if waits else 0.0,
        "incoming_vehicles_30s": dc.incoming_vehicles_within(edge_id),
        "average_speed": dc.average_speed(edge_id),
    }


def build_state(junction_id):
    if junction_id == config.J1_ID:
        approaches_def = config.J1_APPROACHES
        link_edge = config.J1_TO_J2_EDGE
    elif junction_id == config.J2_ID:
        approaches_def = config.J2_APPROACHES
        link_edge = config.J2_TO_J1_EDGE
    else:
        raise ValueError(f"Unknown controlled junction: {junction_id}")

    phase, _state_str, elapsed = dc.current_phase_info(junction_id)

    approaches = {dirn: _approach_state(edge) for dirn, edge in approaches_def.items()}

    downstream_status = {
        "road_to_other": dc.edge_congestion_level(link_edge),
    }

    persons = traci.person.getIDList()
    waiting_count, avg_wait, max_wait = dc.pedestrian_waiting_at_junction(junction_id, persons)

    return {
        "intersection_id": junction_id,
        "current_phase": phase,
        "phase_elapsed_time": elapsed,
        "approaches": approaches,
        "downstream_status": downstream_status,
        "pedestrians": {
            "waiting": waiting_count > 0,
            "waiting_count": waiting_count,
            "average_waiting_time": avg_wait,
            "max_waiting_time": max_wait,
        },
    }
