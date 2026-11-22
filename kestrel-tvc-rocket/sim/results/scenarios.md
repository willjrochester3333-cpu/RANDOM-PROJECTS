# Scenario & fault-injection results (real flight code in the loop)

| case | description | apogee m | max tilt boost ° | max tilt coast ° | max gimbal ° | roll rate boost / coast °/s | max tab ° | deploy − apogee s | speed at deploy m/s | landing m/s | drift m | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| nominal_calm | E20, no wind | 95 | 0.4 | 0.2 | 0.4 | 3 / 3 | 2.1 | +0.04 | 0.3 | 5.4 | 0 | **PASS**  |
| nominal_wind3 | E20, 3 m/s wind + gusts (baseline) | 95 | 0.5 | 2.0 | 0.8 | 3 / 3 | 14.7 | +0.04 | 3.7 | 5.4 | 70 | **PASS**  |
| wind6_gusty | E20, 6 m/s wind, 1.5 m/s gusts | 94 | 0.6 | 15.4 | 0.7 | 3 / 2 | 14.7 | +0.05 | 8.4 | 5.4 | 144 | **PASS**  |
| wind9_limit | E20, 9 m/s wind (UKRA/NAR wind limit) | 94 | 1.0 | 29.8 | 1.4 | 3 / 2 | 14.7 | +0.05 | 12.8 | 5.3 | 231 | **PASS**  |
| rod_tilt5 | rod tilted 5 deg downwind (rocket holds the rod direction) | 93 | 5.0 | 5.1 | 0.8 | 3 / 2 | 2.8 | +0.05 | 5.8 | 5.4 | 89 | **PASS**  |
| misalign_1p5 | 1.5 deg thrust misalignment (badly seated motor) | 94 | 1.4 | 2.4 | 1.6 | 3 / 2 | 14.7 | +0.04 | 3.6 | 5.4 | 69 | **PASS**  |
| fin_cant2 | 2 deg fin cant: strong roll torque the tabs must cancel | 95 | 0.5 | 2.0 | 0.8 | 17 / 18 | 14.7 | +0.04 | 3.7 | 5.4 | 70 | **PASS**  |
| fin_misalign | fins glued crooked: +1.0 / -0.5 / +0.8 / -0.2 deg | 95 | 0.5 | 2.0 | 0.9 | 6 / 5 | 14.7 | +0.04 | 3.7 | 5.4 | 70 | **PASS**  |
| cg_aft_20mm | CG 20 mm further aft than predicted | 95 | 0.4 | 2.6 | 0.3 | 3 / 3 | 14.7 | +0.04 | 3.9 | 5.4 | 71 | **PASS**  |
| heavy_15pct | airframe 15% heavier than predicted | 71 | 0.5 | 3.0 | 0.6 | 2 / 2 | 7.8 | +0.05 | 3.1 | 5.8 | 52 | **PASS**  |
| cd_plus20 | drag 20% higher than predicted | 93 | 0.5 | 2.3 | 0.8 | 3 / 2 | 14.7 | +0.05 | 3.7 | 5.4 | 77 | **PASS**  |
| payload_0g | empty payload bay | 102 | 0.5 | 1.3 | 0.7 | 3 / 3 | 9.2 | +0.04 | 3.9 | 5.3 | 78 | **PASS**  |
| payload_50g | maximum payload 50 g | 88 | 0.5 | 2.7 | 1.0 | 3 / 3 | 14.7 | +0.03 | 3.5 | 5.5 | 62 | **PASS**  |
| tvc_gains_x0.5 | TVC gains halved | 95 | 1.2 | 2.2 | 0.8 | 3 / 3 | 14.7 | +0.04 | 3.6 | 5.4 | 70 | **PASS**  |
| tvc_gains_x2 | TVC gains doubled | 95 | 0.3 | 1.9 | 0.8 | 3 / 2 | 14.7 | +0.04 | 3.7 | 5.4 | 71 | **PASS**  |
| tab_gains_x0.5 | tab (roll + coast) gains halved | 95 | 0.5 | 3.4 | 0.8 | 6 / 6 | 14.2 | +0.04 | 3.6 | 5.4 | 70 | **PASS**  |
| tab_gains_x2 | tab (roll + coast) gains doubled | 95 | 0.5 | 1.2 | 0.9 | 1 / 1 | 14.7 | +0.04 | 3.7 | 5.4 | 70 | **PASS**  |
| tab_eff_minus40 | tabs 40% less effective than predicted | 95 | 0.6 | 3.3 | 1.2 | 5 / 4 | 14.7 | +0.04 | 3.6 | 5.4 | 70 | **PASS**  |
| tab_eff_plus40 | tabs 40% more effective than predicted | 95 | 0.5 | 1.5 | 0.6 | 2 / 2 | 10.7 | +0.04 | 3.7 | 5.4 | 70 | **PASS**  |
| slow_servos | all servos half speed, 25 ms lag, extra backlash | 95 | 0.7 | 1.9 | 0.7 | 3 / 2 | 14.4 | +0.04 | 3.7 | 5.4 | 70 | **PASS**  |
| imu_misalign2 | IMU mounted 2 deg crooked | 95 | 0.5 | 1.9 | 0.8 | 3 / 3 | 14.7 | +0.04 | 3.7 | 5.4 | 70 | **PASS**  |
| gyro_drift | gyro bias drifting 10x faster than spec | 95 | 0.5 | 2.0 | 0.8 | 2 / 2 | 14.7 | +0.04 | 3.7 | 5.4 | 70 | **PASS**  |
| roll_program | camera panorama: 90 deg/s roll programme in the coast | 95 | 0.5 | 1.3 | 0.8 | 3 / 96 | 14.7 | +0.04 | 3.7 | 5.4 | 70 | **PASS**  |
| coast_rate_only | tabs only damp pitch/yaw in the coast (no attitude hold) | 95 | 0.5 | 4.0 | 0.8 | 3 / 3 | 8.3 | +0.03 | 3.3 | 5.4 | 69 | **PASS**  |
| tabs_disabled | tabs switched off in the settings (TVC only, like KESTREL-1) | 95 | 0.8 | 9.0 | 2.1 | 161 / 180 | 0.0 | +0.04 | 2.6 | 5.4 | 66 | **PASS**  |
| motor_D20 | TSP D20-0 (first test hop) | 36 | 0.4 | 4.6 | 0.7 | 2 / 2 | 10.7 | +0.05 | 2.1 | 5.4 | 22 | **PASS**  |
| unarmed_launch | FAULT: launched before calibration finished (1 s on the pad) | 88 | 27.5 | 82.3 | 0.0 | 162 / 182 | 0.0 | +0.04 | 5.4 | 5.4 | 51 | **PASS**  |
| tvc_off_calm | FAULT: TVC servos dead, calm | 95 | 3.2 | 0.4 | 0.0 | 3 / 2 | 10.0 | +0.04 | 0.5 | 5.4 | 3 | **PASS**  |
| tvc_off_wind3 | FAULT: TVC servos dead, 3 m/s wind (tabs still steer) | 95 | 3.5 | 2.6 | 0.0 | 2 / 2 | 14.7 | +0.04 | 3.6 | 5.4 | 68 | **PASS**  |
| servo_hardover | FAULT: TVC pitch servo jams at full deflection at T+0.5 s | 17 | 150.9 | 0.0 | 6.5 | 8 / 0 | 14.7 | -0.79 | 17.6 | 5.4 | 22 | **PASS** contained near pad |
| tab_hardover | FAULT: tab 1 jams at full deflection at T+1 s | 81 | 2.4 | 179.5 | 3.8 | 73 / 319 | 16.0 | +0.02 | 5.9 | 5.4 | 68 | **PASS**  |
| tab_stuck | FAULT: tab 2 freezes at T+0.5 s | 95 | 0.6 | 3.4 | 0.8 | 6 / 11 | 10.9 | +0.04 | 3.7 | 5.4 | 70 | **PASS**  |
| tabs_dead | FAULT: all four tab servos dead from launch | 95 | 1.0 | 9.3 | 1.1 | 161 / 181 | 0.0 | +0.03 | 2.6 | 5.4 | 66 | **PASS**  |
| baro_dead | FAULT: barometer dies at T+1 s | 95 | 0.5 | 0.7 | 0.9 | 3 / 3 | 3.7 | +1.27 | 12.6 | 5.4 | 61 | **PASS**  |
| no_chute | FAULT: parachute fails to deploy (shows why ground tests matter) | 95 | 0.5 | 2.0 | 0.8 | 3 / 3 | 14.7 | +0.04 | 3.7 | 39.3 | 28 | **INFO** informational |
| motor_E12 | TSP E12-0: NOT for KESTREL-2 (too little thrust for its mass) | 64 | 0.3 | 1.6 | 0.6 | 2 / 2 | 7.0 | +0.05 | 3.4 | 5.4 | 52 | **INFO** informational |
