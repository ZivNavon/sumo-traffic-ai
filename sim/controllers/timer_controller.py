"""
TIMER mode controller (baseline).

Fixed-time traffic-light cycles for J1 and J2. SUMO's auto-generated TLS
program (from --tls.guess) already provides a fixed-cycle program with
green/yellow/red phases including the pedestrian crossings, so TIMER mode
simply lets that default program run unmodified -- it does not read any
traffic state and does not call setPhase/setPhaseDuration.

This is the reference baseline that SCRIPT and AI modes are compared against.
"""


class TimerController:
    """No-op controller: does not alter traffic lights, just lets the
    default fixed-time SUMO program run."""

    def __init__(self, junction_ids):
        self.junction_ids = junction_ids

    def step(self, sim_time):
        # Fixed-time mode: nothing to do, SUMO's default TLS program handles it.
        pass
