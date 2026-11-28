#!/bin/sh
# Every simulation suite in order (about 45 min on 4 cores). Console logs go to sim/results/*_console.txt.
set -e
cd "$(dirname "$0")"
python3 scenarios.py            > results/scenarios_console.txt 2>&1
python3 montecarlo.py 1000 400 100 > results/montecarlo_console.txt 2>&1
python3 plot_montecarlo.py      > results/plot_montecarlo_console.txt 2>&1
python3 first_flight_mc.py 300 300 100 > results/first_flight_mc_console.txt 2>&1
python3 stress_montecarlo.py 1000 > results/stress_montecarlo_console.txt 2>&1
python3 mc_tab_effectiveness.py > results/mc_tab_effectiveness_console.txt 2>&1
python3 validate_rocketpy.py    > results/rocketpy_console.txt 2>&1
python3 whatif.py               > results/whatif_console.txt 2>&1
echo ALL DONE
