"""
Experiment runner.

Runs the SUMO simulation for a given scenario under a given control mode
(TIMER, SCRIPT, or AI -- only TIMER is implemented so far), collects
metrics via the Metrics module, and saves a JSON summary to sim/results/.

Usage:
    python sim/run_experiment.py --mode timer --scenario balanced
"""

import argparse
import os
import sys

import sumolib
import traci

sys.path.insert(0, os.path.dirname(__file__))
from modules import config, metrics  # noqa: E402
from controllers.timer_controller import TimerController  # noqa: E402
from controllers.script_controller import ScriptController  # noqa: E402
from controllers.script_controller_v0 import ScriptControllerV0  # noqa: E402


def build_controller(mode):
    if mode == "timer":
        return TimerController(config.CONTROLLED_JUNCTIONS)
    if mode == "script":
        return ScriptController(config.CONTROLLED_JUNCTIONS)
    if mode == "script_v0":
        return ScriptControllerV0(config.CONTROLLED_JUNCTIONS)
    raise NotImplementedError(f"Mode '{mode}' is not implemented yet (only 'timer'/'script'/'script_v0' so far).")


def run(mode, scenario, gui=False, end_time=config.SIM_END_TIME):
    route_file = os.path.join(config.SCENARIOS_DIR, f"{scenario}.rou.xml")
    ped_file = os.path.join(config.SCENARIOS_DIR, f"{scenario}.ped.xml")
    tripinfo_file = os.path.join(config.RESULTS_DIR, f"{mode}_{scenario}_tripinfo.xml")
    os.makedirs(config.RESULTS_DIR, exist_ok=True)

    route_files = route_file
    if os.path.exists(ped_file):
        route_files = f"{route_file},{ped_file}"

    sumo_binary = sumolib.checkBinary("sumo-gui" if gui else "sumo")
    traci.start([
        sumo_binary,
        "-n", config.NET_FILE,
        "-r", route_files,
        "-b", "0", "-e", str(end_time),
        "--tripinfo-output", tripinfo_file,
        "--no-step-log", "true",
        "--no-warnings", "true",
    ])

    controller = build_controller(mode)
    collector = metrics.MetricsCollector(mode_name=mode, scenario_name=scenario)

    try:
        while traci.simulation.getMinExpectedNumber() > 0:
            traci.simulationStep()
            t = traci.simulation.getTime()
            controller.step(t)
            collector.step()
    finally:
        traci.close()

    summary = collector.finalize(tripinfo_file, sim_time=end_time)
    path = metrics.save_summary(summary)
    print(f"Saved summary to {path}")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["timer", "script", "script_v0", "ai"], default="timer")
    parser.add_argument("--scenario", default="balanced")
    parser.add_argument("--gui", action="store_true")
    parser.add_argument("--end", type=int, default=config.SIM_END_TIME)
    args = parser.parse_args()
    run(args.mode, args.scenario, gui=args.gui, end_time=args.end)
