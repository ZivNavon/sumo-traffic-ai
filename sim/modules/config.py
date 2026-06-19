"""
Shared configuration/constants for the J1/J2 smart-intersection project.

Network layout (4x3 node grid = 3x2 city blocks):

    A2 --- B2 --- C2 --- D2
    |      |      |      |
    A1 --- B1 === C1 --- D1
    |      |      |      |
    A0 --- B0 --- C0 --- D0

B1 and C1 are the two controlled four-way intersections (J1, J2),
directly connected by the B1C1 / C1B1 edges. All other nodes are
background/entry-exit junctions running SUMO's default behavior.
"""

import os

# ---- Paths -----------------------------------------------------------
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SIM_DIR = os.path.join(PROJECT_ROOT, "sim")
NETWORK_DIR = os.path.join(SIM_DIR, "network")
SCENARIOS_DIR = os.path.join(SIM_DIR, "scenarios")
RESULTS_DIR = os.path.join(SIM_DIR, "results")

NET_FILE = os.path.join(NETWORK_DIR, "grid.net.xml")

# ---- Controlled intersections ----------------------------------------
J1_ID = "B1"
J2_ID = "C1"
CONTROLLED_JUNCTIONS = [J1_ID, J2_ID]

# Edges connecting J1 <-> J2 (the "between J1 and J2" road segment)
J1_TO_J2_EDGE = "B1C1"
J2_TO_J1_EDGE = "C1B1"

# Approach edges (incoming) for each controlled junction, by compass direction.
# Determined from network coordinates: A1B1 (west->east, "west" approach of J1),
# B0B1 (south->north, "south" approach), B2B1 (north->south, "north" approach),
# C1B1 (east->west, "east" approach of J1 -- this is the J1<->J2 link).
J1_APPROACHES = {
    "west": "A1B1",
    "south": "B0B1",
    "north": "B2B1",
    "east": "C1B1",   # arrives from J2
}

J2_APPROACHES = {
    "west": "B1C1",   # arrives from J1
    "south": "C0C1",
    "north": "C2C1",
    "east": "D1C1",
}

# ---- Simulation defaults ----------------------------------------------
SIM_END_TIME = 1200  # seconds

# ---- Control / decision defaults --------------------------------------
MIN_GREEN_TIME = 10   # seconds (absolute floor, used only as a hard clamp)
MAX_GREEN_TIME = 60   # seconds
SAFE_MIN_GREEN = 15   # seconds (starvation cap floor -- not the absolute min)
DEFAULT_GREEN = 37    # seconds, same as TIMER mode's fixed green
INCOMING_WINDOW = 30  # seconds, for "incoming vehicles in next N seconds"

# Pedestrians
PEDESTRIAN_WAIT_THRESHOLD = 40   # avg wait (s) -> soft priority (cap at DEFAULT_GREEN)
PEDESTRIAN_FORCE_THRESHOLD = 60  # max wait (s) -> force phase to end at SAFE_MIN_GREEN

# Starvation
STARVATION_THRESHOLD = 90  # seconds -> cap current phase into [SAFE_MIN_GREEN, 25]
STARVATION_CAP = 25

# Deadband / hysteresis: if the load ratio is within this distance of 0.5,
# ignore the imbalance and use DEFAULT_GREEN.
LOAD_DEADBAND = 0.075  # i.e. |load_diff| / total_load < 0.15

# Green-duration buckets, keyed by load ratio of the current group
# (ratio > threshold -> duration). Falls through to the last value.
DURATION_BUCKETS = [
    (0.70, 50),
    (0.55, 40),
    (0.45, 30),
    (0.30, 20),
]
DURATION_BUCKET_FLOOR = 15

# Downstream-congestion penalty applied to a group's load when the road it
# would feed into is congested (reduces its priority -> shorter green).
DOWNSTREAM_FACTOR = {
    "free": 1.0,
    "moderate": 0.7,
    "congested": 0.4,
}

# J1 -> J2 coordination: if this many vehicles on B1C1 are expected to reach
# J2 within INCOMING_WINDOW seconds, boost J2's matching (west/EW) approach.
COORDINATION_INCOMING_THRESHOLD = 3
COORDINATION_BOOST = 1.5
