# First-flight study: TSP E20 (`sim/first_flight_mc.py`)

Real flight code in the loop; the main Monte Carlo's dispersions (motor impulse, mass, drag, CG, sensors, servos, rod
tilt, gusts...), no payload. *Full open* = the canopy has reached its full size (latch delay + fill time).

| | Flight 1 | Flight 2 | Beyond the first-flight wind limit |
|---|---|---|---|
| flights | 300 | 300 | 100 |
| success (criteria as the main Monte Carlo) | 100.0 % | 100.0 % | 100.0 % |
| apogee, median m | 47.1 | 46.9 | 45.4 |
| apogee, 5th percentile m | 35.9 | 36.9 | 37.5 |
| latch opens at, median m | 47.1 | 46.9 | 45.3 |
| canopy fully open at, median m | 39.6 | 39.8 | 38.0 |
| canopy fully open at, 5th percentile m | 27.8 | 28.7 | 28.9 |
| canopy fully open at, lowest m | 18.2 | 22.9 | 27.6 |
| time under the open canopy, median s | 7.5 | 7.6 | 7.2 |
| time under the open canopy, shortest s | 3.4 | 4.2 | 4.7 |
| speed when the latch opens, 95th pct m/s | 2.6 | 2.6 | 5.5 |
| landing speed, 95th percentile m/s | 5.7 | 5.7 | 5.6 |
| landing distance, 95th percentile m | 38 | 36 | 78 |
| max tilt in boost, 95th percentile deg | 3.3 | 2.7 | 3.3 |
| rod exit speed, median m/s | 6.3 | 6.3 | 6.2 |
| roll rate in boost, 95th percentile deg/s | 142 | 4 | 3 |

700 flights in 478 s.
