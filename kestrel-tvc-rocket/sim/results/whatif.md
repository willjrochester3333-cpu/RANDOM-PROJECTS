# Drag build-up and what-if flights (`sim/whatif.py`)

Drag build-up at 40 m/s, coasting (`Cd0` = 0.85, every term includes the 8 % allowance):

| Term | Cd |
|---|---|
| body skin friction | 0.282 |
| base | 0.132 |
| fin + leg skin friction | 0.080 |
| camera pod | 0.076 |
| fin trailing edges | 0.075 |
| fin band fairing | 0.057 |
| fin leading edges | 0.042 |
| launch lugs (2) | 0.040 |
| nose | 0.022 |
| feet | 0.017 |
| tab hinges / linkages | 0.017 |
| gimbal gap | 0.011 |

Dry mass with 25 g payload, no motor: 764 g

| Change (passive, calm, 1 m rod) | F35 apogee | rod-exit speed |
|---|---|---|
| **as designed** (rated 65 Ns, 25 g payload) | 188.3 m | 10.0 m/s |
| empty payload bay | 197.6 m | 10.2 m/s |
| maximum 50 g payload | 179.4 m | 9.8 m/s |
| F35 delivering its published curve (67 Ns) | 195.5 m | 9.7 m/s |
| 33 g lighter (= no nose ballast; margin would fall to +0.33 cal) | 200.6 m | 10.3 m/s |
| 50 g lighter | 207.2 m | 10.4 m/s |
| 100 g lighter | 227.7 m | 10.8 m/s |
| drag 20 % lower | 196.0 m | 10.0 m/s |
| TSP E20 in the 24 mm adapter (second test flights) | 53.3 m | 6.6 m/s |
| TSP D20 in the 24 mm adapter (first test hops) | 18.9 m | 6.9 m/s |

(24 s)
