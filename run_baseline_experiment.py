"""
Baseline experiment: single 4-arm intersection (2 lanes per direction),
fixed-time traffic light, speed limit 40 mph (17.88 m/s).

Runs the simulation N times with different random traffic (different seeds),
each time using SUMO's tripinfo output to compute per-vehicle waiting time
and average speed, then reports the overall averages across all runs.

Usage:
    python run_baseline_experiment.py --runs 100
"""
import argparse
import os
import subprocess
import sys
import xml.etree.ElementTree as ET

import sumolib

BASE_DIR = os.path.join(os.path.dirname(__file__), "net_single")
NET_FILE = os.path.join(BASE_DIR, "cross.net.xml")
TOOLS_DIR = os.path.join(os.path.dirname(sumolib.__file__), "..", "sumo", "tools")
RANDOM_TRIPS = os.path.join(TOOLS_DIR, "randomTrips.py")


def run_one(seed: int, run_dir: str, period: float):
    routes_file = os.path.join(run_dir, "routes.rou.xml")
    trips_file = os.path.join(run_dir, "trips.trips.xml")
    tripinfo_file = os.path.join(run_dir, "tripinfo.xml")

    # Generate random traffic demand for this seed
    subprocess.run(
        [
            sys.executable, RANDOM_TRIPS,
            "-n", NET_FILE,
            "-r", routes_file,
            "-o", trips_file,
            "-e", "600",
            "-p", "3.0",          # ~ one trip every 3s -> "few cars"
            "--seed", str(seed),
            "--validate",
        ],
        check=True, capture_output=True,
    )

    # Run SUMO headless with fixed-time TLS (default) and tripinfo output
    sumo_binary = sumolib.checkBinary("sumo")
    subprocess.run(
        [
            sumo_binary,
            "-n", NET_FILE,
            "-r", routes_file,
            "-b", "0", "-e", "600",
            "--tripinfo-output", tripinfo_file,
            "--no-step-log", "true",
            "--no-warnings", "true",
        ],
        check=True, capture_output=True,
    )

    # Parse tripinfo for waiting time and average speed per vehicle
    waiting_times = []
    speeds = []
    tree = ET.parse(tripinfo_file)
    for trip in tree.getroot().findall("tripinfo"):
        wt = float(trip.get("waitingTime"))
        duration = float(trip.get("duration"))
        route_length = float(trip.get("routeLength"))
        waiting_times.append(wt)
        if duration > 0:
            speeds.append(route_length / duration)

    return waiting_times, speeds


def main(runs: int):
    work_dir = os.path.join(BASE_DIR, "_runs")
    os.makedirs(work_dir, exist_ok=True)

    all_waiting = []
    all_speeds = []

    for seed in range(runs):
        run_dir = os.path.join(work_dir, f"run_{seed}")
        os.makedirs(run_dir, exist_ok=True)
        wt, sp = run_one(seed, run_dir, period=3.0)
        all_waiting.extend(wt)
        all_speeds.extend(sp)
        print(f"run {seed+1}/{runs}: vehicles={len(wt)}", end="\r")

    print()
    n = len(all_waiting)
    avg_wait = sum(all_waiting) / n
    avg_speed_ms = sum(all_speeds) / len(all_speeds)
    avg_speed_mph = avg_speed_ms * 2.23694

    print(f"Total runs: {runs}")
    print(f"Total vehicles across all runs: {n}")
    print(f"Average waiting time per car: {avg_wait:.2f} s")
    print(f"Average speed per car: {avg_speed_ms:.2f} m/s ({avg_speed_mph:.2f} mph)")
    print("(Speed limit on all approaches: 17.88 m/s = 40 mph)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=100)
    args = parser.parse_args()
    main(args.runs)
