# Drag build-up and what-if flights (`sim/whatif.py`)

Drag build-up at 40 m/s, coasting (`Cd0` = 0.94, every term includes the 8 % allowance):

| Term | Cd |
|---|---|
| body skin friction | 0.282 |
| fin leading edges | 0.156 |
| base | 0.132 |
| fin + leg skin friction | 0.088 |
| fin trailing edges | 0.078 |
| camera pod | 0.076 |
| launch lugs (2) | 0.040 |
| feet | 0.038 |
| nose | 0.022 |
| tab hinges / linkages | 0.017 |
| gimbal gap | 0.011 |

Dry mass with 25 g payload, no motor: 771 g

| Change (passive, calm, 1 m rod) | E20 apogee | rod-exit speed |
|---|---|---|
| **as designed** (rated 36 Ns, 25 g payload) | 55.5 m | 6.7 m/s |
| empty payload bay | 59.7 m | 6.9 m/s |
| maximum 50 g payload | 51.6 m | 6.5 m/s |
| E20 delivering its published curve (40 Ns) | 68.2 m | 7.0 m/s |
| 33 g lighter (= no nose ballast; margin would fall to +0.46 cal) | 61.1 m | 7.0 m/s |
| 50 g lighter | 64.2 m | 7.1 m/s |
| 100 g lighter | 74.5 m | 7.5 m/s |
| drag 20 % lower | 56.2 m | 6.7 m/s |
| TSP F35 (29 mm, 65 Ns), which would need a 29 mm TVC module | 182 m | 9.9 m/s |

(24 s)
