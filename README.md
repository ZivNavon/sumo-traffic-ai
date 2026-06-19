# Smart Urban Intersection System — SUMO Workspace

This folder is the SUMO-based simulation workspace for the project (network of
intersections, baseline fixed-time control, with room to add the AI-based
adaptive controller).

## Setup (already done in this folder)

SUMO 1.27.0 (binaries + Python bindings) is installed via pip into the
project's Python environment:

```
pip install eclipse-sumo traci sumolib
```

This installs `sumo`, `sumo-gui`, `netgenerate`, `randomTrips.py`, etc.,
and gives Python access to `traci` (live simulation control) and `sumolib`
(network/route file utilities).

`SUMO_HOME` should point to:
```
C:\Users\zivna\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages\sumo
```
(set as an environment variable so `sumolib.checkBinary` and the tools in
`SUMO_HOME/tools` work correctly).

## Folder layout

```
net/
  cross.net.xml     - a 2x2 grid network (4 intersections, traffic-light controlled)
  routes.rou.xml    - randomly generated vehicle trips
  sim.sumocfg       - SUMO configuration tying network + routes together
run_baseline.py     - TraCI script: runs the simulation with default fixed-time
                       signal programs and reports total vehicle waiting time
```

## Running the simulation

Headless (no window, fast):
```
python run_baseline.py
```

With the SUMO GUI (visualize the intersections and traffic):
```
python run_baseline.py --gui
```

## Regenerating the network / traffic

Regenerate the grid network:
```
netgenerate --grid --grid.number=2 --grid.length=200 --default.lanenumber=1 --tls.guess --output-file=net/cross.net.xml
```

Regenerate random traffic demand:
```
python "<SUMO_HOME>/tools/randomTrips.py" -n net/cross.net.xml -r net/routes.rou.xml -e 1000 -p 1.0 --validate
```

## Next steps

- `run_baseline.py` is the fixed-time baseline used for comparison.
- The adaptive controller (detection-based or LLM-based) will be added as a
  separate script that connects via TraCI, reads traffic state each step,
  and overrides traffic light phases via `traci.trafficlight.setPhase` /
  `setPhaseDuration`.
