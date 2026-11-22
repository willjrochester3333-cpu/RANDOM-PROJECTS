# Scenario & fault-injection results (real flight code in the loop)

| case | description | apogee m | max tilt in boost ° | max gimbal ° | deploy − apogee s | speed at deploy m/s | descent rate at landing m/s | drift m | verdict |
|---|---|---|---|---|---|---|---|---|---|
| nominal_calm | E20, no wind | 193 | 0.8 | 0.4 | +0.02 | 0.2 | 5.5 | 1 | **PASS**  |
| nominal_wind3 | E20, 3 m/s wind + gusts (baseline) | 193 | 2.1 | 4.4 | +0.02 | 2.5 | 5.5 | 151 | **PASS**  |
| wind6_gusty | E20, 6 m/s wind, 1.5 m/s gusts | 193 | 3.4 | 5.8 | +0.03 | 5.8 | 5.4 | 285 | **PASS**  |
| wind9_limit | E20, 9 m/s wind (UKRA/NAR wind limit) | 193 | 4.2 | 5.8 | +0.03 | 9.4 | 5.4 | 440 | **PASS**  |
| rod_tilt5 | rod tilted 5 deg downwind (rocket holds the rod direction) | 192 | 5.0 | 2.4 | +0.02 | 6.5 | 5.5 | 186 | **PASS**  |
| misalign_1p5 | 1.5 deg thrust misalignment (badly seated motor) | 193 | 3.0 | 4.8 | +0.02 | 2.7 | 5.5 | 151 | **PASS**  |
| roll_spin | 2 deg fin cant -> fast roll (tests roll-lead compensation) | 193 | 2.9 | 5.4 | +0.02 | 2.3 | 5.5 | 149 | **PASS**  |
| cg_aft_20mm | CG 20 mm further aft than predicted | 193 | 1.8 | 3.6 | +0.02 | 2.7 | 5.5 | 153 | **PASS**  |
| heavy_15pct | airframe 15% heavier than predicted | 159 | 2.1 | 3.7 | +0.03 | 2.2 | 5.9 | 115 | **PASS**  |
| cd_plus20 | drag 20% higher than predicted | 185 | 2.1 | 4.3 | +0.02 | 2.6 | 5.5 | 139 | **PASS**  |
| gains_x0.5 | controller gains halved | 193 | 3.2 | 3.2 | +0.03 | 1.9 | 5.5 | 135 | **PASS**  |
| gains_x2 | controller gains doubled | 193 | 1.4 | 5.8 | +0.02 | 2.9 | 5.5 | 154 | **PASS**  |
| slow_servos | servos half as fast, 25 ms lag, 0.5 deg backlash | 193 | 2.4 | 4.3 | +0.02 | 2.4 | 5.5 | 149 | **PASS**  |
| imu_misalign2 | IMU mounted 2 deg crooked | 193 | 4.4 | 3.3 | +0.02 | 2.4 | 5.5 | 147 | **PASS**  |
| gyro_drift | gyro bias drifting 10x faster than spec | 193 | 2.1 | 4.4 | +0.02 | 2.5 | 5.5 | 151 | **PASS**  |
| motor_E12 | TSP E12-0 (3.5 s long-burn TVC demo) | 158 | 1.5 | 2.4 | +0.04 | 3.0 | 5.5 | 128 | **PASS**  |
| motor_D20 | TSP D20-0 (first test hop) | 81 | 1.4 | 3.3 | +0.04 | 1.5 | 5.5 | 56 | **PASS**  |
| motor_EstesE12 | Estes E12-0 (if available abroad) | 91 | 1.2 | 1.0 | +0.04 | 2.6 | 5.5 | 70 | **PASS**  |
| unarmed_launch | FAULT: launched before calibration finished (1 s on the pad) | 187 | 14.9 | 0.0 | +0.01 | 6.2 | 5.5 | 90 | **PASS**  |
| tvc_off_calm | FAULT: TVC servos dead, calm | 192 | 8.5 | 0.0 | +0.03 | 4.3 | 5.5 | 37 | **PASS**  |
| tvc_off_wind3 | FAULT: TVC servos dead, 3 m/s wind | 187 | 15.3 | 0.0 | +0.00 | 6.4 | 5.5 | 99 | **PASS**  |
| servo_hardover | FAULT: pitch servo jams at full deflection at T+0.5 s | 21 | 160.0 | 6.5 | -0.67 | 26.0 | 5.5 | 16 | **PASS** contained near pad |
| baro_dead | FAULT: barometer dies at T+1 s | 193 | 2.0 | 4.3 | +1.39 | 12.8 | 5.5 | 137 | **PASS**  |
| no_chute | FAULT: parachute fails to deploy (shows why ground tests matter) | 193 | 2.1 | 4.4 | +0.02 | 2.5 | 51.0 | 31 | **INFO** informational |
