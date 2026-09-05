"""
Generate _v2 variants of all 6 scenarios with shifted seeds.

Trained weights stay unchanged. This tests whether the trained policies
generalize to unseen traffic of the same character.

Seed mapping (v1 → v2):
  balanced         1  → 101
  heavy_west       3  → 103
  pedestrian_heavy 5  → 105
  morning_flow     7  → 107
  evening_flow     9  → 109
  day_cycle       42  → 142

Usage:
    cd "D:/Ziv - OS/Projects/Trafic AI"
    py sim/scenarios/gen_v2_scenarios.py
"""

import os
import subprocess
import sys

# ── Paths ─────────────────────────────────────────────────────────────────────
SCENARIOS_DIR = os.path.dirname(__file__)
SIM_DIR       = os.path.join(SCENARIOS_DIR, "..")
NET_FILE      = os.path.join(SIM_DIR, "network", "grid.net.xml")

# Find randomTrips.py
def _find_random_trips():
    sumo_home = os.environ.get("SUMO_HOME", "")
    candidates = [
        os.path.join(sumo_home, "tools", "randomTrips.py"),
        r"C:\Users\zivna\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\sumo\tools\randomTrips.py",
        r"C:\Program Files (x86)\Eclipse\Sumo\tools\randomTrips.py",
        r"C:\Program Files\Eclipse\Sumo\tools\randomTrips.py",
        r"C:\SUMO\tools\randomTrips.py",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    sys.exit("ERROR: randomTrips.py not found. Set SUMO_HOME environment variable.")

RANDOM_TRIPS = _find_random_trips()


# ── randomTrips wrapper ────────────────────────────────────────────────────────
def run_random_trips(out_rou, seed, period, end=1200, persons=False, fringe=5):
    net = os.path.abspath(NET_FILE)
    out = os.path.abspath(out_rou)
    cmd = [
        sys.executable, RANDOM_TRIPS,
        "-n", net,
        "-r", out,
        "--seed", str(seed),
        "--period", str(period),
        "--end", str(end),
        "--fringe-factor", str(fringe),
    ]
    if persons:
        cmd += ["--pedestrians"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  WARN: {result.stderr[:200]}")
    return result.returncode == 0


# ── Scenario: balanced_v2 ──────────────────────────────────────────────────────
def gen_balanced_v2():
    print("balanced_v2 ...")
    run_random_trips(os.path.join(SCENARIOS_DIR, "balanced_v2.rou.xml"),
                     seed=101, period=2, end=1200)
    run_random_trips(os.path.join(SCENARIOS_DIR, "balanced_v2.ped.xml"),
                     seed=101, period=6, end=1200, persons=True)
    print("  done")


# ── Scenario: heavy_west_v2 ────────────────────────────────────────────────────
HEAVY_WEST_FLOW = (
    '    <flow id="heavy_west" type="DEFAULT_VEHTYPE" begin="0" end="1200" '
    'probability="0.5"><route edges="A1B1 B1C1 C1D1" /></flow>\n'
)

def gen_heavy_west_v2():
    print("heavy_west_v2 ...")
    bg_path = os.path.join(SCENARIOS_DIR, "_heavy_west_v2_bg.rou.xml")
    run_random_trips(bg_path, seed=103, period=6, end=1200, fringe=5)

    # Read background vehicles and prepend the heavy flow
    with open(bg_path) as f:
        bg = f.read()

    # Strip the XML declaration and insert after it, then inject the flow
    out_path = os.path.join(SCENARIOS_DIR, "heavy_west_v2.rou.xml")
    # Find the <routes> open tag and inject the flow right after it
    idx = bg.find("<routes")
    end_tag = bg.find(">", idx) + 1
    out = bg[:end_tag] + "\n" + HEAVY_WEST_FLOW + bg[end_tag:]
    with open(out_path, "w") as f:
        f.write(out)
    os.remove(bg_path)

    # Ped file same parameters as balanced_v2
    run_random_trips(os.path.join(SCENARIOS_DIR, "heavy_west_v2.ped.xml"),
                     seed=103, period=6, end=1200, persons=True)
    print("  done")


# ── Scenario: pedestrian_heavy_v2 ─────────────────────────────────────────────
def gen_pedestrian_heavy_v2():
    print("pedestrian_heavy_v2 ...")
    run_random_trips(os.path.join(SCENARIOS_DIR, "pedestrian_heavy_v2.rou.xml"),
                     seed=105, period=6, end=1200, fringe=5)
    run_random_trips(os.path.join(SCENARIOS_DIR, "pedestrian_heavy_v2.ped.xml"),
                     seed=105, period=2, end=1200, persons=True, fringe=5)
    print("  done")


# ── Scenarios: morning_flow_v2 / evening_flow_v2 ──────────────────────────────
# Reuse gen_directional logic directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from scenarios.gen_directional import write_scenario, S_TO_N_ROUTES, N_TO_S_ROUTES

def gen_directional_v2():
    print("morning_flow_v2 ...")
    write_scenario("morning_flow_v2", S_TO_N_ROUTES, seed=107)
    print("  done")
    print("evening_flow_v2 ...")
    write_scenario("evening_flow_v2", N_TO_S_ROUTES, seed=109)
    print("  done")


# ── Scenario: day_cycle_v2 ────────────────────────────────────────────────────
# Inline day_cycle generation with seed=142
from scenarios.gen_day_cycle import PHASES, BG, PED_ROUTES, HEADER, FOOTER

def gen_day_cycle_v2():
    import random
    print("day_cycle_v2 ...")
    SEED = 142

    # Vehicles
    rng = random.Random(SEED)
    events = []
    for (t_start, t_end, pool, peak_period, bg_period) in PHASES:
        t = float(t_start)
        while t < t_end:
            events.append((t, rng.choice(pool)))
            t += peak_period
        if bg_period > 0:
            t = t_start + bg_period / 2
            while t < t_end:
                events.append((t, rng.choice(BG)))
                t += bg_period
    events.sort(key=lambda e: e[0])

    v_lines = []
    for i, (depart, edges) in enumerate(events):
        v_lines.append(f'    <vehicle id="{i}" depart="{depart:.2f}">')
        v_lines.append(f'        <route edges="{edges}"/>')
        v_lines.append(f'    </vehicle>')

    rou_path = os.path.join(SCENARIOS_DIR, "day_cycle_v2.rou.xml")
    with open(rou_path, "w") as f:
        f.write(HEADER + "\n".join(v_lines) + "\n" + FOOTER)

    # Pedestrians
    rng2 = random.Random(SEED + 1000)
    p_lines = []
    t, i = 0.0, 0
    while t < 3600:
        edges = rng2.choice(PED_ROUTES)
        p_lines.append(f'    <person id="{i}" depart="{t:.2f}">')
        p_lines.append(f'        <walk edges="{edges}"/>')
        p_lines.append(f'    </person>')
        t += 6.0
        i += 1

    ped_path = os.path.join(SCENARIOS_DIR, "day_cycle_v2.ped.xml")
    with open(ped_path, "w") as f:
        f.write(HEADER + "\n".join(p_lines) + "\n" + FOOTER)

    print(f"  {len([l for l in v_lines if '<vehicle' in l])} vehicles, {i} pedestrians — done")


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"Using randomTrips: {RANDOM_TRIPS}\n")
    gen_balanced_v2()
    gen_heavy_west_v2()
    gen_pedestrian_heavy_v2()
    gen_directional_v2()
    gen_day_cycle_v2()
    print("\nAll v2 scenarios generated.")
    print("Evaluate with:")
    for sc in ["balanced", "heavy_west", "pedestrian_heavy",
               "morning_flow", "evening_flow"]:
        for mode in ["timer", "script", "ai", "a2c"]:
            print(f"  py sim/run_experiment.py --mode {mode} --scenario {sc}_v2")
    for mode in ["timer", "script", "ai", "a2c"]:
        print(f"  py sim/run_experiment.py --mode {mode} --scenario day_cycle_v2 --end 3600")
