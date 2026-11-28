# Drag build-up and what-if flights (`sim/whatif.py`)

Drag build-up at 40 m/s, coasting (`Cd0` = 0.85, every term includes the 8 % allowance):

| Term | Cd |
|---|---|
| body skin friction | 0.282 |
| base | 0.132 |
| fin + leg skin friction | 0.080 |
| fin trailing edges | 0.071 |
| fin band fairing | 0.063 |
| fin leading edges | 0.042 |
| launch lugs (2) | 0.040 |
| leg sleeve boat-tails | 0.029 |
| nose | 0.022 |
| leg bolt heads / nuts | 0.021 |
| tab hinges / linkages | 0.017 |
| camera brow | 0.017 |
| feet | 0.012 |
| gimbal gap | 0.011 |
| battery-hatch door | 0.005 |
| camera door | 0.005 |

Dry mass with 25 g payload, no motor: 860 g

| Change (passive, calm, 1 m rod) | F35 apogee | rod-exit speed |
|---|---|---|
| **as designed** (rated 65 Ns, 25 g payload) | 156.7 m | 9.3 m/s |
| empty payload bay | 164.5 m | 9.5 m/s |
| maximum 50 g payload | 149.3 m | 9.1 m/s |
| F35 delivering its published curve (67 Ns) | 162.4 m | 9.0 m/s |
| 51 g lighter (= no nose ballast; margin would fall to +0.18 cal) | 173.0 m | 9.7 m/s |
| 50 g lighter | 172.7 m | 9.7 m/s |
| 100 g lighter | 190.2 m | 10.1 m/s |
| drag 20 % lower | 161.5 m | 9.3 m/s |
| TSP E20 in the 24 mm adapter (the first two flights) | 40.5 m | 5.9 m/s |
| TSP D20 in the 24 mm adapter (optional, not in the flight programme) | 14.4 m | 6.2 m/s |

(31 s)
