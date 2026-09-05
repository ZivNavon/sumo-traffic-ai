# Trafic AI — Project Instructions

SUMO/TraCI simulation comparing TIMER vs SCRIPT vs AI traffic-light control.
Network: 4×3 node grid, J1=B1, J2=C1. See `PROGRESS.md` for full context.

## After every simulation run

When a new simulation completes (any mode or scenario), immediately update `sim/results/RESULTS.md`:

1. Add the new result to the correct scenario section (or create a new section if it's a new scenario).
2. Update the cross-scenario summary table.
3. Note any regressions or surprises under "Open issues".
4. Mark the scenario as done in the "Pending scenarios" table if applicable.

Result data comes from `sim/results/{mode}_{scenario}.json`. Run the simulation with:

```
python sim/run_experiment.py --mode {timer|script|script_v0|ai} --scenario {balanced|heavy_west|...}
```

## Commit after results update

After updating `RESULTS.md`, commit both the new JSON and the updated markdown:

```
git add sim/results/
git commit -m "results: {mode} {scenario} — <one-line summary>"
git push
```

Remote: https://github.com/ZivNavon/sumo-traffic-ai
