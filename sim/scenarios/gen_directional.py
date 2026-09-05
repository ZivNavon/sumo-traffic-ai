"""
Generate morning_flow and evening_flow scenario XML files.

morning_flow: heavy south→north commute (people going to work)
  - High-rate vehicles: bottom row (A0,B0,C0,D0) → top row (A2,B2,C2,D2)
  - Background random traffic at low rate

evening_flow: heavy north→south commute (people coming home)
  - High-rate vehicles: top row (A2,B2,C2,D2) → bottom row (A0,B0,C0,D0)
  - Background random traffic at low rate

Network layout reminder:
    A2 --- B2 --- C2 --- D2
    |      |      |      |
    A1 --- B1 === C1 --- D1   (J1=B1, J2=C1 — controlled)
    |      |      |      |
    A0 --- B0 --- C0 --- D0

South→North routes through J1 (B1):
  A0→A1→B1→B2, B0→B1→B2, B0→B1→C1→C2, A0→A1→B1→C1→D1→D2

South→North routes through J2 (C1):
  C0→C1→C2, C0→C1→D1→D2, B0→B1→C1→C2

North→South: reverse of above.
"""

import random
import os

# Common routes: (edges list, is_south_to_north)
S_TO_N_ROUTES = [
    # Through J1 only
    "A0A1 A1B1 B1B2",
    "B0B1 B1B2",
    "B0B1 B1B2 B2A2",
    # Through J1 then J2
    "A0A1 A1B1 B1C1 C1C2",
    "B0B1 B1C1 C1C2",
    "B0B1 B1C1 C1C2 C2D2",
    # Through J2 only
    "C0C1 C1C2",
    "C0C1 C1D1 D1D2",
    "C0C1 C1C2 C2D2",
    # Far east — background / no intersection
    "D0D1 D1D2",
    "A0A1 A1A2",
]

N_TO_S_ROUTES = [
    # Through J1 only
    "A2A1 A1B1 B1B0",
    "B2B1 B1B0",
    "A2B2 B2B1 B1B0",
    # Through J2 then J1
    "C2C1 C1B1 B1B0",
    "C2C1 C1B1 B1A1 A1A0",
    "D2C2 C2C1 C1B1 B1B0",
    # Through J2 only
    "C2C1 C1C0",
    "D1C1 C1C0",
    "C2C1 C1C0 C0B0",
    # Far east — background / no intersection
    "D2D1 D1D0",
    "A2A1 A1A0",
]

# Sparse background routes (east-west, local)
BG_ROUTES = [
    "A1B1 B1C1 C1D1",
    "D1C1 C1B1 B1A1",
    "B1C1 C1D1",
    "D1C1 C1B1",
    "A0B0 B0C0 C0D0",
    "D0C0 C0B0 B0A0",
    "B0C0 C0D0",
    "D0C0 C0B0",
]

PED_ROUTES = [
    "A1B1 B1C1 C1D1 D0D1",
    "D1C1 C1B1 B1A1 A0A1",
    "B1C1 C1D1",
    "C1B1 B1A1",
    "A0A1 A1B1 B0B1",
    "C2C1 B1C1 B0B1",
]

HEADER = '''<?xml version="1.0" encoding="UTF-8"?>
<routes xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/routes_file.xsd">
'''
FOOTER = '</routes>\n'


def gen_vehicles(peak_routes, bg_routes, seed, end_time,
                 peak_period, bg_period):
    """
    Interleave peak directional vehicles with background traffic.
    peak_period: seconds between peak vehicles (smaller = more vehicles)
    bg_period:   seconds between background vehicles
    """
    rng = random.Random(seed)
    events = []

    t = 0.0
    while t < end_time:
        events.append((t, rng.choice(peak_routes)))
        t += peak_period

    t = bg_period / 2  # offset background so it doesn't cluster with peak
    while t < end_time:
        events.append((t, rng.choice(bg_routes)))
        t += bg_period

    events.sort(key=lambda e: e[0])
    lines = []
    for i, (depart, edges) in enumerate(events):
        lines.append(f'    <vehicle id="{i}" depart="{depart:.2f}">')
        lines.append(f'        <route edges="{edges}"/>')
        lines.append(f'    </vehicle>')
    return lines


def gen_pedestrians(ped_routes, seed, end_time, period):
    rng = random.Random(seed + 1000)
    lines = []
    t = 0.0
    i = 0
    while t < end_time:
        edges = rng.choice(ped_routes)
        lines.append(f'    <person id="{i}" depart="{t:.2f}">')
        lines.append(f'        <walk edges="{edges}"/>')
        lines.append(f'    </person>')
        t += period
        i += 1
    return lines


def write_scenario(name, peak_routes, seed, end_time=1200,
                   peak_period=2.0, bg_period=8.0, ped_period=6.0):
    out_dir = os.path.dirname(__file__)

    # Vehicles
    vehicle_lines = gen_vehicles(peak_routes, BG_ROUTES, seed, end_time,
                                 peak_period, bg_period)
    rou_path = os.path.join(out_dir, f"{name}.rou.xml")
    with open(rou_path, "w") as f:
        f.write(HEADER)
        f.write("\n".join(vehicle_lines))
        f.write("\n" + FOOTER)

    # Pedestrians
    ped_lines = gen_pedestrians(PED_ROUTES, seed, end_time, ped_period)
    ped_path = os.path.join(out_dir, f"{name}.ped.xml")
    with open(ped_path, "w") as f:
        f.write(HEADER)
        f.write("\n".join(ped_lines))
        f.write("\n" + FOOTER)

    v_count = sum(1 for l in vehicle_lines if "<vehicle" in l)
    p_count = sum(1 for l in ped_lines if "<person" in l)
    print(f"{name}: {v_count} vehicles, {p_count} pedestrians → {rou_path}")


if __name__ == "__main__":
    write_scenario("morning_flow", S_TO_N_ROUTES, seed=7)
    write_scenario("evening_flow", N_TO_S_ROUTES, seed=9)
    print("Done.")
