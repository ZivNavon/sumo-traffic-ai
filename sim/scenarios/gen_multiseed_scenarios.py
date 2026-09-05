"""
Generate multi-seed scenario files.

Training seeds  : 1–20    → {scenario}_s1.rou.xml … {scenario}_s20.rou.xml
Test seeds      : 201–205 → {scenario}_s201.rou.xml … {scenario}_s205.rou.xml

Do NOT train on seeds 201–205. They are the final unseen test set.

Usage:
    cd "D:/Ziv - OS/Projects/Trafic AI"
    py sim/scenarios/gen_multiseed_scenarios.py
"""

import os
import random
import subprocess
import sys

SCENARIOS_DIR = os.path.dirname(__file__)
SIM_DIR       = os.path.join(SCENARIOS_DIR, "..")
NET_FILE      = os.path.abspath(os.path.join(SIM_DIR, "network", "grid.net.xml"))

TRAIN_SEEDS = list(range(1, 21))       # 1–20
TEST_SEEDS  = list(range(201, 206))    # 201–205
ALL_SEEDS   = TRAIN_SEEDS + TEST_SEEDS


# ── Find randomTrips.py ───────────────────────────────────────────────────────
def _find_random_trips():
    candidates = [
        os.path.join(os.environ.get("SUMO_HOME", ""), "tools", "randomTrips.py"),
        r"C:\Users\zivna\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\sumo\tools\randomTrips.py",
        r"C:\Program Files (x86)\Eclipse\Sumo\tools\randomTrips.py",
        r"C:\Program Files\Eclipse\Sumo\tools\randomTrips.py",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    sys.exit("ERROR: randomTrips.py not found.")

RT = _find_random_trips()


def _rt(out, seed, period, end=1200, persons=False, fringe=5):
    cmd = [sys.executable, RT, "-n", NET_FILE, "-r", os.path.abspath(out),
           "--seed", str(seed), "--period", str(period), "--end", str(end),
           "--fringe-factor", str(fringe)]
    if persons:
        cmd += ["--pedestrians"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"    WARN: {r.stderr[:120]}")


# ── Import Python generators ──────────────────────────────────────────────────
sys.path.insert(0, SIM_DIR)
from scenarios.gen_directional import write_scenario as _write_dir, S_TO_N_ROUTES, N_TO_S_ROUTES
from scenarios.gen_day_cycle   import PHASES, BG, PED_ROUTES, HEADER, FOOTER

HEAVY_WEST_FLOW = (
    '    <flow id="heavy_west" type="DEFAULT_VEHTYPE" begin="0" end="1200" '
    'probability="0.5"><route edges="A1B1 B1C1 C1D1" /></flow>\n'
)


def _inject_flow(path):
    """Prepend the heavy_west flow into an existing randomTrips rou.xml."""
    with open(path) as f:
        txt = f.read()
    idx = txt.find("<routes")
    end = txt.find(">", idx) + 1
    with open(path, "w") as f:
        f.write(txt[:end] + "\n" + HEAVY_WEST_FLOW + txt[end:])


def _gen_day_cycle(name, seed, end=3600, ped_period=6.0):
    rng = random.Random(seed)
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
    for i, (dep, edges) in enumerate(events):
        v_lines += [f'    <vehicle id="{i}" depart="{dep:.2f}">',
                    f'        <route edges="{edges}"/>',
                    f'    </vehicle>']

    rou = os.path.join(SCENARIOS_DIR, f"{name}.rou.xml")
    with open(rou, "w") as f:
        f.write(HEADER + "\n".join(v_lines) + "\n" + FOOTER)

    rng2 = random.Random(seed + 1000)
    p_lines, t, i = [], 0.0, 0
    while t < end:
        e = rng2.choice(PED_ROUTES)
        p_lines += [f'    <person id="{i}" depart="{t:.2f}">',
                    f'        <walk edges="{e}"/>',
                    f'    </person>']
        t += ped_period
        i += 1

    ped = os.path.join(SCENARIOS_DIR, f"{name}.ped.xml")
    with open(ped, "w") as f:
        f.write(HEADER + "\n".join(p_lines) + "\n" + FOOTER)


# ── Main generation ───────────────────────────────────────────────────────────
def generate_all():
    total = len(ALL_SEEDS) * 6
    done  = 0

    for seed in ALL_SEEDS:
        tag = f"s{seed}"
        print(f"\n── seed {seed} ──────────────────────────────────────────")

        # balanced
        name = f"balanced_{tag}"
        if not os.path.exists(os.path.join(SCENARIOS_DIR, f"{name}.rou.xml")):
            _rt(os.path.join(SCENARIOS_DIR, f"{name}.rou.xml"), seed, period=2)
            _rt(os.path.join(SCENARIOS_DIR, f"{name}.ped.xml"), seed, period=6, persons=True)
        print(f"  balanced_{tag} ok")

        # heavy_west
        name = f"heavy_west_{tag}"
        if not os.path.exists(os.path.join(SCENARIOS_DIR, f"{name}.rou.xml")):
            bg = os.path.join(SCENARIOS_DIR, f"{name}.rou.xml")
            _rt(bg, seed, period=6)
            _inject_flow(bg)
            _rt(os.path.join(SCENARIOS_DIR, f"{name}.ped.xml"), seed, period=6, persons=True)
        print(f"  heavy_west_{tag} ok")

        # pedestrian_heavy
        name = f"pedestrian_heavy_{tag}"
        if not os.path.exists(os.path.join(SCENARIOS_DIR, f"{name}.rou.xml")):
            _rt(os.path.join(SCENARIOS_DIR, f"{name}.rou.xml"), seed, period=6, fringe=5)
            _rt(os.path.join(SCENARIOS_DIR, f"{name}.ped.xml"), seed, period=2, persons=True, fringe=5)
        print(f"  pedestrian_heavy_{tag} ok")

        # morning_flow
        name = f"morning_flow_{tag}"
        if not os.path.exists(os.path.join(SCENARIOS_DIR, f"{name}.rou.xml")):
            _write_dir(name, S_TO_N_ROUTES, seed=seed)
        print(f"  morning_flow_{tag} ok")

        # evening_flow
        name = f"evening_flow_{tag}"
        if not os.path.exists(os.path.join(SCENARIOS_DIR, f"{name}.rou.xml")):
            _write_dir(name, N_TO_S_ROUTES, seed=seed)
        print(f"  evening_flow_{tag} ok")

        # day_cycle
        name = f"day_cycle_{tag}"
        if not os.path.exists(os.path.join(SCENARIOS_DIR, f"{name}.rou.xml")):
            _gen_day_cycle(name, seed)
        print(f"  day_cycle_{tag} ok")

        done += 6
        print(f"  [{done}/{total} files]")

    print(f"\nDone. {total} scenario pairs generated.")


if __name__ == "__main__":
    generate_all()
