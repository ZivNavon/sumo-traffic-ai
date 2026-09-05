"""
Generate day_cycle scenario: a compressed 24-hour traffic simulation.

Five phases in 3600 seconds:

  Phase        | Sim time    | Real-world analogy | Traffic pattern
  -------------|-------------|--------------------|-----------------
  Pre-dawn     |    0– 600 s | 00:00–06:00        | Very sparse
  Morning rush |  600–1200 s | 06:00–12:00        | Heavy S→N commute
  Midday       | 1200–1800 s | 12:00–16:00        | Balanced moderate
  Evening rush | 1800–2700 s | 16:00–20:00        | Heavy N→S commute
  Night        | 2700–3600 s | 20:00–24:00        | Sparse

The ML controllers receive only real-time queue/wait state — they never see
the clock. They must infer the dominant flow direction from the state alone.
TIMER gets 37s fixed green the whole day, every phase.

Network reminder:
    A2 --- B2 --- C2 --- D2
    |      |      |      |
    A1 --- B1 === C1 --- D1   (J1=B1, J2=C1 — controlled)
    |      |      |      |
    A0 --- B0 --- C0 --- D0
"""

import os

# ── Route pools (reused from gen_directional.py) ──────────────────────────────

S_TO_N = [
    "A0A1 A1B1 B1B2",
    "B0B1 B1B2",
    "A0A1 A1B1 B1C1 C1C2",
    "B0B1 B1C1 C1C2",
    "C0C1 C1C2",
    "C0C1 C1D1 D1D2",
    "D0D1 D1D2",
    "A0A1 A1A2",
]

N_TO_S = [
    "A2A1 A1B1 B1B0",
    "B2B1 B1B0",
    "C2C1 C1B1 B1B0",
    "D2C2 C2C1 C1B1 B1B0",
    "C2C1 C1C0",
    "D1C1 C1C0",
    "D2D1 D1D0",
    "A2A1 A1A0",
]

BALANCED = S_TO_N + N_TO_S  # equal mix

BG = [
    "A1B1 B1C1 C1D1",
    "D1C1 C1B1 B1A1",
    "B1C1 C1D1",
    "D1C1 C1B1",
    "A0B0 B0C0 C0D0",
    "D0C0 C0B0 B0A0",
]

PED_ROUTES = [
    "A1B1 B1C1 C1D1 D0D1",
    "D1C1 C1B1 B1A1 A0A1",
    "B1C1 C1D1",
    "C1B1 B1A1",
    "A0A1 A1B1 B0B1",
    "C2C1 B1C1 B0B1",
]

HEADER = ('<?xml version="1.0" encoding="UTF-8"?>\n'
          '<routes xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
          'xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/routes_file.xsd">\n')
FOOTER = '</routes>\n'

# ── Phase definitions ────────────────────────────────────────────────────────
# (start, end, routes_pool, peak_period, bg_period)
PHASES = [
    (0,    600,  BG,       20.0, 0),      # pre-dawn: only background, no peak
    (600,  1200, S_TO_N,    2.0, 10.0),   # morning rush: heavy S→N
    (1200, 1800, BALANCED,  4.0, 0),      # midday: balanced (no separate BG)
    (1800, 2700, N_TO_S,    2.0, 10.0),   # evening rush: heavy N→S
    (2700, 3600, BG,       20.0, 0),      # night: sparse
]

SEED = 42


def _rng(seed):
    import random
    return random.Random(seed)


def gen_vehicles():
    import random
    rng = random.Random(SEED)
    events = []

    for phase_idx, (t_start, t_end, pool, peak_period, bg_period) in enumerate(PHASES):
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
    lines = []
    for i, (depart, edges) in enumerate(events):
        lines.append(f'    <vehicle id="{i}" depart="{depart:.2f}">')
        lines.append(f'        <route edges="{edges}"/>')
        lines.append(f'    </vehicle>')
    return lines, len([l for l in lines if "<vehicle" in l])


def gen_pedestrians(end_time=3600, period=6.0):
    import random
    rng = random.Random(SEED + 1000)
    lines = []
    t = 0.0
    i = 0
    while t < end_time:
        edges = rng.choice(PED_ROUTES)
        lines.append(f'    <person id="{i}" depart="{t:.2f}">')
        lines.append(f'        <walk edges="{edges}"/>')
        lines.append(f'    </person>')
        t += period
        i += 1
    return lines, i


def write():
    out_dir = os.path.dirname(__file__)

    v_lines, v_count = gen_vehicles()
    rou_path = os.path.join(out_dir, "day_cycle.rou.xml")
    with open(rou_path, "w") as f:
        f.write(HEADER)
        f.write("\n".join(v_lines))
        f.write("\n" + FOOTER)

    p_lines, p_count = gen_pedestrians()
    ped_path = os.path.join(out_dir, "day_cycle.ped.xml")
    with open(ped_path, "w") as f:
        f.write(HEADER)
        f.write("\n".join(p_lines))
        f.write("\n" + FOOTER)

    print(f"day_cycle: {v_count} vehicles, {p_count} pedestrians")
    print(f"  → {rou_path}")
    print(f"  → {ped_path}")
    print("\nPhase breakdown:")
    phase_names = ["Pre-dawn", "Morning rush", "Midday", "Evening rush", "Night"]
    for name, (ts, te, pool, pp, bp) in zip(phase_names, PHASES):
        v_in_phase = (te - ts) / pp + ((te - ts) / bp if bp else 0)
        print(f"  {name:15s} ({ts:4d}–{te:4d}s): ~{int(v_in_phase)} vehicles")


if __name__ == "__main__":
    write()
