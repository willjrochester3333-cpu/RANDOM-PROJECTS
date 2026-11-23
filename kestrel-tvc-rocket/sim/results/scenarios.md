# Scenario & fault-injection results (real flight code in the loop)

| case | description | apogee m | max tilt boost ° | max tilt coast ° | max gimbal ° | roll rate boost / coast °/s | max tab ° | deploy − apogee s | speed at deploy m/s | landing m/s | drift m | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| nominal_calm | E20, no wind | 55 | 0.3 | 0.1 | 0.5 | 1 / 2 | 2.1 | +0.04 | 0.4 | 4.9 | 0 | **PASS**  |
| nominal_wind3 | E20, 3 m/s wind + gusts (baseline) | 55 | 0.3 | 2.0 | 1.2 | 2 / 3 | 8.5 | +0.04 | 2.6 | 4.9 | 43 | **PASS**  |
| wind6_gusty | E20, 6 m/s wind, 1.5 m/s gusts | 55 | 0.3 | 5.2 | 0.5 | 2 / 3 | 14.4 | +0.05 | 6.2 | 4.9 | 91 | **PASS**  |
| wind9_limit | E20, 9 m/s wind (UKRA/NAR wind limit) | 55 | 0.8 | 20.7 | 2.0 | 1 / 18 | 14.4 | +0.04 | 9.9 | 4.9 | 143 | **PASS**  |
| rod_tilt5 | rod tilted 5 deg downwind (rocket holds the rod direction) | 54 | 5.0 | 5.0 | 1.1 | 2 / 3 | 4.0 | +0.04 | 4.6 | 4.9 | 58 | **PASS**  |
| rod_1.5m_wind6 | 1.5 m launch rod, 6 m/s wind + 1.5 m/s gusts | 55 | 0.3 | 5.2 | 0.5 | 2 / 3 | 14.4 | +0.05 | 6.1 | 4.9 | 91 | **PASS**  |
| wind6_payload50 | 6 m/s wind + gusts with the maximum 50 g payload | 51 | 0.4 | 4.9 | 0.4 | 2 / 3 | 14.4 | +0.04 | 5.8 | 4.8 | 77 | **PASS**  |
| misalign_1p5 | 1.5 deg thrust misalignment (badly seated motor) | 55 | 1.0 | 2.2 | 2.2 | 3 / 1 | 10.9 | +0.04 | 2.5 | 4.9 | 42 | **PASS**  |
| fin_cant2 | 2 deg fin cant: strong roll torque the tabs must cancel | 55 | 0.3 | 1.9 | 1.1 | 10 / 10 | 11.8 | +0.04 | 2.6 | 4.9 | 43 | **PASS**  |
| fin_misalign | fins glued crooked: +1.0 / -0.5 / +0.8 / -0.2 deg | 55 | 0.4 | 2.0 | 1.2 | 3 / 3 | 8.9 | +0.04 | 2.6 | 4.9 | 43 | **PASS**  |
| cg_aft_20mm | CG 20 mm further aft than predicted | 55 | 0.3 | 2.5 | 0.4 | 2 / 2 | 13.4 | +0.04 | 2.7 | 4.9 | 44 | **PASS**  |
| heavy_15pct | airframe 15% heavier than predicted | 40 | 0.3 | 2.3 | 0.9 | 2 / 2 | 14.0 | +0.05 | 2.0 | 5.2 | 28 | **PASS**  |
| cd_plus20 | drag 20% higher than predicted | 55 | 0.3 | 2.0 | 1.2 | 2 / 2 | 8.7 | +0.05 | 2.6 | 4.9 | 46 | **PASS**  |
| payload_0g | empty payload bay | 60 | 0.3 | 1.9 | 1.0 | 3 / 2 | 9.7 | +0.05 | 2.8 | 4.8 | 46 | **PASS**  |
| payload_50g | maximum payload 50 g | 51 | 0.4 | 2.0 | 1.3 | 2 / 2 | 6.1 | +0.05 | 2.4 | 5.0 | 35 | **PASS**  |
| tvc_gains_x0.5 | TVC gains halved | 55 | 0.9 | 2.1 | 1.5 | 2 / 2 | 9.0 | +0.04 | 2.6 | 4.9 | 43 | **PASS**  |
| tvc_gains_x2 | TVC gains doubled | 55 | 0.2 | 1.9 | 1.3 | 2 / 1 | 7.7 | +0.04 | 2.6 | 4.9 | 43 | **PASS**  |
| tab_gains_x0.5 | tab (roll + coast) gains halved | 55 | 0.3 | 2.2 | 1.1 | 6 / 7 | 6.2 | +0.04 | 2.6 | 4.9 | 43 | **PASS**  |
| tab_gains_x2 | tab (roll + coast) gains doubled | 55 | 0.4 | 1.7 | 1.1 | 2 / 1 | 10.7 | +0.04 | 2.6 | 4.9 | 43 | **PASS**  |
| tab_eff_minus40 | tabs 40% less effective than predicted | 55 | 0.4 | 2.1 | 1.4 | 4 / 2 | 10.1 | +0.04 | 2.6 | 4.9 | 43 | **PASS**  |
| tab_eff_plus40 | tabs 40% more effective than predicted | 55 | 0.3 | 1.8 | 0.9 | 5 / 5 | 6.8 | +0.04 | 2.6 | 4.9 | 43 | **PASS**  |
| slow_servos | all servos half speed, 25 ms lag, extra backlash | 55 | 0.5 | 2.0 | 0.7 | 3 / 2 | 8.6 | +0.04 | 2.6 | 4.9 | 43 | **PASS**  |
| imu_misalign2 | IMU mounted 2 deg crooked | 55 | 0.3 | 2.0 | 1.2 | 2 / 1 | 8.2 | +0.04 | 2.6 | 4.9 | 43 | **PASS**  |
| gyro_drift | gyro bias drifting 10x faster than spec | 55 | 0.3 | 2.0 | 1.2 | 2 / 2 | 8.3 | +0.04 | 2.6 | 4.9 | 43 | **PASS**  |
| roll_program | camera panorama: 90 deg/s roll programme in the coast | 55 | 0.3 | 1.5 | 1.2 | 2 / 93 | 11.3 | +0.04 | 2.6 | 4.9 | 43 | **PASS**  |
| coast_rate_only | tabs only damp pitch/yaw in the coast (no attitude hold) | 55 | 0.3 | 1.8 | 1.2 | 2 / 2 | 4.4 | +0.04 | 2.5 | 4.9 | 43 | **PASS**  |
| tabs_disabled | tabs switched off in the settings (TVC only, like KESTREL-1) | 55 | 0.3 | 22.4 | 1.8 | 72 / 94 | 0.0 | +0.05 | 2.1 | 4.9 | 46 | **PASS**  |
| motor_D20 | TSP D20-0 (first test hop) | 20 | 0.4 | 4.0 | 0.9 | 1 / 2 | 10.7 | +0.05 | 1.2 | 4.9 | 10 | **PASS**  |
| motor_curve | E20 performing like its published test curve (40 Ns, not the rated 36 Ns) | 68 | 0.4 | 2.0 | 0.8 | 3 / 2 | 8.4 | +0.05 | 3.0 | 4.9 | 56 | **PASS**  |
| unarmed_launch | FAULT: launched before calibration finished (1 s on the pad) | 54 | 20.7 | 28.6 | 0.0 | 73 / 95 | 0.0 | +0.04 | 3.5 | 4.9 | 33 | **PASS**  |
| tvc_off_calm | FAULT: TVC servos dead, calm | 55 | 3.6 | 0.3 | 0.0 | 2 / 1 | 14.4 | +0.04 | 0.7 | 4.9 | 3 | **PASS**  |
| tvc_off_wind3 | FAULT: TVC servos dead, 3 m/s wind (tabs still steer) | 55 | 4.2 | 3.2 | 0.0 | 4 / 2 | 14.4 | +0.04 | 2.3 | 4.9 | 40 | **PASS**  |
| servo_hardover | FAULT: TVC pitch servo jams at full deflection at T+0.5 s | 16 | 119.9 | 0.0 | 6.5 | 17 / 0 | 14.4 | -0.96 | 14.3 | 4.9 | 19 | **PASS** contained near pad |
| tab_hardover | FAULT: tab 1 jams at full deflection at T+1 s | 55 | 0.6 | 37.6 | 2.7 | 24 / 158 | 16.0 | +0.04 | 3.2 | 4.9 | 49 | **PASS**  |
| tab_stuck | FAULT: tab 2 freezes at T+0.5 s | 55 | 0.4 | 2.5 | 1.2 | 2 / 9 | 14.4 | +0.04 | 2.6 | 4.9 | 43 | **PASS**  |
| tabs_dead | FAULT: all four tab servos dead from launch | 55 | 0.4 | 22.9 | 1.5 | 72 / 94 | 0.0 | +0.05 | 2.1 | 4.9 | 46 | **PASS**  |
| passive_calm | FAULT: all 6 steering servos dead (TVC + tabs), calm | 54 | 17.2 | 19.9 | 0.0 | 71 / 92 | 0.0 | +0.05 | 4.2 | 4.9 | 18 | **PASS**  |
| passive_wind3 | FAULT: all 6 steering servos dead, 3 m/s wind | 54 | 22.8 | 35.2 | 0.0 | 73 / 97 | 0.0 | +0.05 | 3.4 | 4.9 | 29 | **PASS**  |
| passive_empty_bay | FAULT: all steering dead + empty payload bay (least stable), 3 m/s | 58 | 22.0 | 33.7 | 0.0 | 80 / 105 | 0.0 | +0.04 | 3.4 | 4.8 | 26 | **PASS**  |
| baro_dead | FAULT: barometer dies at T+1 s | 55 | 0.3 | 0.4 | 1.1 | 3 / 4 | 4.0 | +1.26 | 12.3 | 4.9 | 28 | **PASS**  |
| passive_wind6 | FAULT: all steering dead in 6 m/s wind (why first flights need <= 3 m/s) | 46 | 27.3 | 170.4 | 0.0 | 72 / 86 | 0.0 | +0.03 | 8.4 | 4.9 | 82 | **INFO** informational |
| no_chute | FAULT: parachute fails to deploy (shows why ground tests matter) | 55 | 0.3 | 2.0 | 1.2 | 2 / 3 | 8.5 | +0.04 | 2.6 | 31.3 | 14 | **INFO** informational |
| motor_E12 | TSP E12-0: NOT for KESTREL-2 (too little thrust for its mass) | 46 | 0.2 | 3.3 | 1.0 | 2 / 2 | 9.6 | +0.06 | 2.7 | 4.9 | 34 | **INFO** informational |
