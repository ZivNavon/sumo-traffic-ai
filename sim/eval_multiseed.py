"""
Multi-seed evaluation script.

Runs all 4 controllers on test seeds 201–205 for all 6 scenarios.
For ai/a2c modes, loads _ms weights (trained on seeds 1–20).
Computes mean ± std across seeds for each metric and saves:
  - sim/results/multiseed_summary.json
  - sim/results/RESULTS_MULTISEED.md

Usage:
    cd "D:/Ziv - OS/Projects/Trafic AI"
    py sim/eval_multiseed.py
"""

import json
import os
import sys
import statistics

sys.path.insert(0, os.path.dirname(__file__))
from run_experiment import run as _run

TEST_SEEDS = list(range(201, 206))

SCENARIOS = [
    ("balanced",         1200),
    ("heavy_west",       1200),
    ("pedestrian_heavy", 1200),
    ("morning_flow",     1200),
    ("evening_flow",     1200),
    ("day_cycle",        3600),
]

MODES = ["timer", "script", "ai", "a2c"]

METRICS = [
    "avg_waiting_time",
    "max_waiting_time",
    "avg_queue_length",
    "avg_travel_time",
    "avg_stops_per_vehicle",
    "avg_pedestrian_waiting_time",
    "max_pedestrian_waiting_time",
    "throughput",
]

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")


def run_all():
    # results[scenario][mode][seed] = {metric: value}
    results = {}

    total = len(SCENARIOS) * len(MODES) * len(TEST_SEEDS)
    done  = 0

    for scenario, end_time in SCENARIOS:
        results[scenario] = {}
        for mode in MODES:
            results[scenario][mode] = {}
            weights = f"{scenario}_ms" if mode in ("ai", "a2c") else None

            for seed in TEST_SEEDS:
                sc_name = f"{scenario}_s{seed}"
                print(f"[{done+1}/{total}] {mode} {sc_name} ...", flush=True)

                try:
                    summary = _run(mode, sc_name, end_time=end_time, weights=weights)
                    results[scenario][mode][seed] = {m: summary.get(m, None) for m in METRICS}
                except Exception as e:
                    print(f"  ERROR: {e}")
                    results[scenario][mode][seed] = {m: None for m in METRICS}

                done += 1

    return results


def aggregate(results):
    """Compute mean ± std across seeds for each (scenario, mode, metric)."""
    agg = {}
    for scenario, modes in results.items():
        agg[scenario] = {}
        for mode, seeds in modes.items():
            agg[scenario][mode] = {}
            for metric in METRICS:
                vals = [seeds[s][metric] for s in TEST_SEEDS if seeds[s][metric] is not None]
                if vals:
                    agg[scenario][mode][metric] = {
                        "mean": round(statistics.mean(vals), 3),
                        "std":  round(statistics.stdev(vals) if len(vals) > 1 else 0.0, 3),
                    }
                else:
                    agg[scenario][mode][metric] = {"mean": None, "std": None}
    return agg


def write_markdown(agg):
    lines = [
        "---",
        "type: results",
        f"date: 2026-08-25",
        "project: Trafic AI",
        "status: complete",
        "tags: [sumo, results, multi-seed, generalization]",
        "---",
        "",
        "# Multi-Seed Evaluation Results",
        "",
        "Test seeds: **201–205** (never seen during training).",
        "Training seeds: **1–20** (multi-seed DQN and A2C).",
        "Values shown as **mean ± std** across 5 test seeds.",
        "",
    ]

    for scenario, end_time in SCENARIOS:
        lines += [f"## {scenario.replace('_', ' ').title()}", ""]
        header = "| Metric | TIMER | SCRIPT | DQN (ms) | A2C (ms) |"
        sep    = "|--------|-------|--------|----------|----------|"
        lines += [header, sep]

        for metric in METRICS:
            row = f"| {metric} |"
            for mode in MODES:
                d = agg[scenario][mode][metric]
                if d["mean"] is None:
                    row += " — |"
                else:
                    row += f" {d['mean']} ± {d['std']} |"
            lines.append(row)
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    print("Running multi-seed evaluation (120 runs total)...\n")
    raw = run_all()

    # Save raw
    raw_path = os.path.join(RESULTS_DIR, "multiseed_raw.json")
    with open(raw_path, "w") as f:
        json.dump(raw, f, indent=2)
    print(f"\nRaw results → {raw_path}")

    # Aggregate
    agg = aggregate(raw)
    agg_path = os.path.join(RESULTS_DIR, "multiseed_summary.json")
    with open(agg_path, "w") as f:
        json.dump(agg, f, indent=2)
    print(f"Summary     → {agg_path}")

    # Markdown
    md = write_markdown(agg)
    md_path = os.path.join(RESULTS_DIR, "RESULTS_MULTISEED.md")
    with open(md_path, "w") as f:
        f.write(md)
    print(f"Markdown    → {md_path}")

    # Quick console summary
    print("\n── Quick summary (avg_waiting_time mean across test seeds) ──")
    for scenario, _ in SCENARIOS:
        vals = {m: agg[scenario][m]["avg_waiting_time"]["mean"] for m in MODES}
        best = min(vals, key=lambda m: vals[m] or 9999)
        print(f"  {scenario:20s}: timer={vals['timer']}  script={vals['script']}  "
              f"dqn_ms={vals['ai']}  a2c_ms={vals['a2c']}  → best: {best}")
