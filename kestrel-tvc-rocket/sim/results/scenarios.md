# Scenario & fault-injection results (real flight code in the loop)

| case | description | apogee m | max tilt in boost ° | max gimbal ° | deploy − apogee s | speed at deploy m/s | descent rate at landing m/s | drift m | verdict |
|---|---|---|---|---|---|---|---|---|---|
| nominal_calm | E20, no wind | 197 | 0.8 | 0.4 | +0.03 | 0.3 | 5.5 | 1 | **PASS**  |
| nominal_wind3 | E20, 3 m/s wind + gusts (baseline) | 196 | 2.1 | 4.3 | +0.02 | 2.5 | 5.5 | 154 | **PASS**  |
| wind6_gusty | E20, 6 m/s wind, 1.5 m/s gusts | 196 | 3.3 | 5.8 | +0.02 | 5.9 | 5.5 | 317 | **PASS**  |
| wind9_limit | E20, 9 m/s wind (UKRA/NAR wind limit) | 196 | 4.0 | 5.8 | +0.04 | 9.5 | 5.4 | 469 | **PASS**  |
| rod_tilt5 | rod tilted 5 deg downwind (rocket holds the rod direction) | 195 | 5.0 | 2.4 | +0.03 | 6.5 | 5.5 | 186 | **PASS**  |
| misalign_1p5 | 1.5 deg thrust misalignment (badly seated motor) | 196 | 3.0 | 4.8 | +0.03 | 2.7 | 5.5 | 154 | **PASS**  |
| roll_spin | 2 deg fin cant -> fast roll (tests roll-lead compensation) | 196 | 2.9 | 5.4 | +0.03 | 2.3 | 5.5 | 152 | **PASS**  |
| cg_aft_20mm | CG 20 mm further aft than predicted | 196 | 1.8 | 3.5 | +0.02 | 2.8 | 5.5 | 156 | **PASS**  |
| heavy_15pct | airframe 15% heavier than predicted | 161 | 2.1 | 3.6 | +0.03 | 2.2 | 5.9 | 114 | **PASS**  |
| cd_plus20 | drag 20% higher than predicted | 188 | 2.1 | 4.3 | +0.03 | 2.6 | 5.5 | 147 | **PASS**  |
| gains_x0.5 | controller gains halved | 196 | 3.2 | 3.1 | +0.02 | 1.9 | 5.5 | 148 | **PASS**  |
| gains_x2 | controller gains doubled | 196 | 1.4 | 5.7 | +0.03 | 2.9 | 5.5 | 157 | **PASS**  |
| slow_servos | servos half as fast, 25 ms lag, 0.5 deg backlash | 196 | 2.3 | 4.2 | +0.02 | 2.4 | 5.5 | 152 | **PASS**  |
| imu_misalign2 | IMU mounted 2 deg crooked | 196 | 4.3 | 3.3 | +0.02 | 2.4 | 5.5 | 150 | **PASS**  |
| gyro_drift | gyro bias drifting 10x faster than spec | 196 | 2.0 | 4.3 | +0.02 | 2.5 | 5.5 | 154 | **PASS**  |
| motor_E12 | TSP E12-0 (3.5 s long-burn TVC demo) | 161 | 1.5 | 2.3 | +0.04 | 3.0 | 5.5 | 135 | **PASS**  |
| motor_D20 | TSP D20-0 (first test hop) | 82 | 1.4 | 3.2 | +0.03 | 1.5 | 5.5 | 54 | **PASS**  |
| motor_EstesE12 | Estes E12-0 (if available abroad) | 92 | 1.2 | 0.9 | +0.04 | 2.6 | 5.4 | 65 | **PASS**  |
| unarmed_launch | FAULT: launched before calibration finished (1 s on the pad) | 190 | 14.9 | 0.0 | +0.02 | 6.2 | 5.5 | 89 | **PASS**  |
| tvc_off_calm | FAULT: TVC servos dead, calm | 194 | 8.6 | 0.0 | +0.01 | 4.4 | 5.5 | 38 | **PASS**  |
| tvc_off_wind3 | FAULT: TVC servos dead, 3 m/s wind | 190 | 15.3 | 0.0 | +0.01 | 6.5 | 5.5 | 95 | **PASS**  |
| servo_hardover | FAULT: pitch servo jams at full deflection at T+0.5 s | 21 | 160.6 | 6.5 | -0.66 | 26.1 | 5.5 | 15 | **PASS** contained near pad |
| baro_dead | FAULT: barometer dies at T+1 s | 196 | 1.9 | 4.3 | +1.40 | 12.7 | 5.5 | 128 | **PASS**  |
| no_chute | FAULT: parachute fails to deploy (shows why ground tests matter) | 196 | 2.1 | 4.3 | +0.02 | 2.5 | 51.6 | 31 | **INFO** informational |
