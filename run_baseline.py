"""
Baseline run: connects to SUMO via TraCI, runs the simulation with default
(fixed-time) traffic light programs, and reports total waiting time.

Usage:
    python run_baseline.py            # headless
    python run_baseline.py --gui      # with sumo-gui
"""
import argparse
import os
import sys

import traci
import sumolib

NET_DIR = os.path.join(os.path.dirname(__file__), "net")
SUMOCFG = os.path.join(NET_DIR, "sim.sumocfg")


def find_sumo_binary(gui: bool) -> str:
    name = "sumo-gui" if gui else "sumo"
    path = sumolib.checkBinary(name)
    return path


def run(gui: bool):
    sumo_binary = find_sumo_binary(gui)
    traci.start([sumo_binary, "-c", SUMOCFG, "--no-step-log", "true"])

    total_waiting_time = 0.0
    step = 0
    while traci.simulation.getMinExpectedNumber() > 0:
        traci.simulationStep()
        for veh_id in traci.vehicle.getIDList():
            total_waiting_time += traci.vehicle.getWaitingTime(veh_id)
        step += 1

    traci.close()
    print(f"Simulation finished after {step} steps.")
    print(f"Cumulative waiting time across all vehicles: {total_waiting_time:.1f} s")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--gui", action="store_true", help="Run with sumo-gui")
    args = parser.parse_args()
    run(args.gui)
