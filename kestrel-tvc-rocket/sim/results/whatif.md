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

Dry mass with 25 g payload, no motor: 761 g

| Change (passive, calm, 1 m rod) | E20 apogee | rod-exit speed |
|---|---|---|
| **as designed** (rated 36 Ns, 25 g payload) | 57.5 m | 6.8 m/s |
| empty payload bay | 61.9 m | 7.0 m/s |
| maximum 50 g payload | 53.4 m | 6.6 m/s |
| E20 delivering its published curve (40 Ns) | 70.7 m | 7.1 m/s |
| 33 g lighter (= no nose ballast; margin would fall to +0.47 cal) | 63.4 m | 7.1 m/s |
| 50 g lighter | 66.7 m | 7.2 m/s |
| 100 g lighter | 77.5 m | 7.7 m/s |
| drag 20 % lower | 58.2 m | 6.8 m/s |
| TSP F35 (29 mm, 65 Ns), which would need a 29 mm TVC module | 190 m | 10.0 m/s |

(16 s)
