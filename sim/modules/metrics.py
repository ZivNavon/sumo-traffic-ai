"""
Metrics and Evaluation Module.

Collects per-step data during a run and produces a summary dict matching
the project spec's required performance metrics. Also computes the
percentage-improvement comparison against a TIMER baseline.
"""

import json
import os
import xml.etree.ElementTree as ET

import traci

from . import config, data_collection as dc


class MetricsCollector:
    def __init__(self, mode_name, scenario_name):
        self.mode_name = mode_name
        self.scenario_name = scenario_name
        self.queue_samples = []          # per-step total queue length (J1+J2 approaches)
        self.pedestrian_wait_samples = []  # per-step (count, avg, max) across J1+J2
        self.j1j2_congestion_samples = []  # per-step congestion level string

    def step(self):
        total_queue = 0
        max_queue = 0
        ped_count_total = 0
        ped_avg_list = []
        ped_max = 0
        for jid, approaches in (
            (config.J1_ID, config.J1_APPROACHES),
            (config.J2_ID, config.J2_APPROACHES),
        ):
            for edge in approaches.values():
                q = dc.queue_length(edge)
                total_queue += q
                max_queue = max(max_queue, q)
            persons = traci.person.getIDList()
            c, avg, mx = dc.pedestrian_waiting_at_junction(jid, persons)
            ped_count_total += c
            if avg:
                ped_avg_list.append(avg)
            ped_max = max(ped_max, mx)

        self.queue_samples.append((total_queue, max_queue))
        self.pedestrian_wait_samples.append(
            (ped_count_total, (sum(ped_avg_list) / len(ped_avg_list)) if ped_avg_list else 0.0, ped_max)
        )
        self.j1j2_congestion_samples.append(dc.edge_congestion_level(config.J1_TO_J2_EDGE))

    def finalize(self, tripinfo_file, sim_time):
        """Parse SUMO tripinfo output and combine with per-step samples."""
        waiting_times, travel_times, stops, throughput = [], [], [], 0
        if os.path.exists(tripinfo_file):
            tree = ET.parse(tripinfo_file)
            for trip in tree.getroot().findall("tripinfo"):
                waiting_times.append(float(trip.get("waitingTime")))
                travel_times.append(float(trip.get("duration")))
                stops.append(int(trip.get("waitingCount", 0)))
                throughput += 1

        avg_queue = (
            sum(q for q, _ in self.queue_samples) / len(self.queue_samples)
            if self.queue_samples else 0.0
        )
        max_queue = max((mx for _, mx in self.queue_samples), default=0)

        ped_avgs = [a for _, a, _ in self.pedestrian_wait_samples if a > 0]
        ped_maxs = [m for _, _, m in self.pedestrian_wait_samples]
        ped_counts = [c for c, _, _ in self.pedestrian_wait_samples]

        congested_steps = sum(1 for c in self.j1j2_congestion_samples if c == "congested")
        congestion_pct = (
            100.0 * congested_steps / len(self.j1j2_congestion_samples)
            if self.j1j2_congestion_samples else 0.0
        )

        summary = {
            "experiment": self.mode_name,
            "scenario": self.scenario_name,
            "sim_time": sim_time,
            "avg_waiting_time": _avg(waiting_times),
            "max_waiting_time": max(waiting_times, default=0.0),
            "avg_queue_length": avg_queue,
            "max_queue_length": max_queue,
            "throughput": throughput,
            "avg_travel_time": _avg(travel_times),
            "avg_stops_per_vehicle": _avg(stops),
            "avg_pedestrian_waiting_time": _avg(ped_avgs),
            "max_pedestrian_waiting_time": max(ped_maxs, default=0.0),
            "avg_waiting_pedestrians": _avg(ped_counts),
            "j1_j2_congestion_pct_time": congestion_pct,
        }
        return summary


def _avg(values):
    return (sum(values) / len(values)) if values else 0.0


def compare_to_baseline(baseline_summary, other_summary):
    """Compute percentage improvement of `other_summary` vs `baseline_summary`
    for the 'lower is better' metrics."""
    lower_is_better = [
        "avg_waiting_time", "max_waiting_time", "avg_queue_length", "max_queue_length",
        "avg_travel_time", "avg_stops_per_vehicle", "avg_pedestrian_waiting_time",
        "max_pedestrian_waiting_time", "avg_waiting_pedestrians", "j1_j2_congestion_pct_time",
    ]
    improvements = {}
    for key in lower_is_better:
        base = baseline_summary.get(key, 0)
        other = other_summary.get(key, 0)
        if base == 0:
            improvements[key] = 0.0
        else:
            improvements[key] = ((base - other) / base) * 100.0
    # throughput: higher is better
    base_t = baseline_summary.get("throughput", 0)
    other_t = other_summary.get("throughput", 0)
    improvements["throughput"] = ((other_t - base_t) / base_t * 100.0) if base_t else 0.0
    return improvements


def save_summary(summary, results_dir=config.RESULTS_DIR):
    os.makedirs(results_dir, exist_ok=True)
    path = os.path.join(results_dir, f"{summary['experiment']}_{summary['scenario']}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    return path
