# Scenario & fault-injection results (real flight code in the loop)

| case | description | apogee m | max tilt boost ° | max tilt coast ° | max gimbal ° | roll rate boost / coast °/s | max tab ° | deploy − apogee s | speed at deploy m/s | landing m/s | drift m | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| nominal_calm | F35, no wind | 188 | 0.5 | 0.2 | 0.3 | 7 / 11 | 2.0 | +0.03 | 0.3 | 4.9 | 1 | **PASS**  |
| nominal_wind3 | F35, 3 m/s wind + gusts (baseline) | 188 | 0.8 | 1.1 | 1.1 | 8 / 8 | 4.3 | +0.03 | 4.4 | 4.9 | 168 | **PASS**  |
| wind6_gusty | F35, 6 m/s wind, 1.5 m/s gusts | 188 | 1.0 | 1.7 | 1.2 | 8 / 6 | 5.4 | +0.03 | 9.6 | 4.9 | 342 | **PASS**  |
| wind9_limit | F35, 9 m/s wind (UKRA/NAR wind limit) | 188 | 1.2 | 1.9 | 1.2 | 7 / 4 | 14.4 | +0.04 | 14.6 | 4.8 | 521 | **PASS**  |
| rod_tilt5 | rod tilted 5 deg downwind (rocket holds the rod direction) | 186 | 5.0 | 5.3 | 0.8 | 10 / 8 | 14.4 | +0.02 | 7.0 | 4.9 | 197 | **PASS**  |
| rod_1.5m_wind6 | 1.5 m launch rod, 6 m/s wind + 1.5 m/s gusts | 188 | 1.1 | 1.6 | 1.2 | 12 / 9 | 5.3 | +0.03 | 9.6 | 4.9 | 342 | **PASS**  |
| wind6_payload50 | 6 m/s wind + gusts with the maximum 50 g payload | 179 | 1.1 | 1.8 | 1.4 | 8 / 4 | 4.0 | +0.03 | 9.4 | 5.0 | 322 | **PASS**  |
| misalign_1p5 | 1.5 deg thrust misalignment (badly seated motor) | 188 | 1.8 | 1.2 | 1.6 | 15 / 5 | 6.1 | +0.04 | 4.4 | 4.9 | 165 | **PASS**  |
| fin_cant2 | 2 deg fin cant: strong roll torque the tabs must cancel | 188 | 0.7 | 1.0 | 0.7 | 34 / 24 | 8.0 | +0.03 | 4.5 | 4.9 | 168 | **PASS**  |
| fin_misalign | fins glued crooked: +1.0 / -0.5 / +0.8 / -0.2 deg | 188 | 0.8 | 1.0 | 1.0 | 12 / 9 | 4.9 | +0.03 | 4.5 | 4.9 | 168 | **PASS**  |
| cg_aft_20mm | CG 20 mm further aft than predicted | 188 | 0.7 | 0.6 | 0.4 | 8 / 10 | 2.6 | +0.03 | 4.6 | 4.9 | 169 | **PASS**  |
| heavy_15pct | airframe 15% heavier than predicted | 151 | 0.8 | 1.0 | 1.1 | 7 / 6 | 3.4 | +0.03 | 4.0 | 5.3 | 131 | **PASS**  |
| cd_plus20 | drag 20% higher than predicted | 181 | 0.8 | 1.0 | 1.1 | 8 / 7 | 4.1 | +0.02 | 4.4 | 4.9 | 165 | **PASS**  |
| payload_0g | empty payload bay | 197 | 0.8 | 0.9 | 0.9 | 12 / 8 | 4.0 | +0.03 | 4.6 | 4.9 | 180 | **PASS**  |
| payload_50g | maximum payload 50 g | 179 | 0.8 | 1.1 | 1.3 | 9 / 9 | 4.6 | +0.03 | 4.3 | 5.0 | 157 | **PASS**  |
| tvc_gains_x0.5 | TVC gains halved | 188 | 1.7 | 1.5 | 0.9 | 11 / 10 | 4.1 | +0.03 | 4.3 | 4.9 | 166 | **PASS**  |
| tvc_gains_x2 | TVC gains doubled | 188 | 0.4 | 1.0 | 1.2 | 8 / 9 | 4.2 | +0.03 | 4.5 | 4.9 | 168 | **PASS**  |
| tab_gains_x0.5 | tab (roll + coast) gains halved | 188 | 0.8 | 1.4 | 1.0 | 12 / 20 | 4.1 | +0.03 | 4.3 | 4.9 | 167 | **PASS**  |
| tab_gains_x2 | tab (roll + coast) gains doubled | 188 | 0.8 | 0.7 | 1.1 | 6 / 3 | 5.1 | +0.03 | 4.5 | 4.9 | 168 | **PASS**  |
| tab_eff_minus40 | tabs 40% less effective than predicted | 188 | 0.9 | 1.6 | 1.2 | 9 / 8 | 6.4 | +0.03 | 4.3 | 4.9 | 167 | **PASS**  |
| tab_eff_plus40 | tabs 40% more effective than predicted | 188 | 0.7 | 0.8 | 0.9 | 9 / 6 | 3.3 | +0.03 | 4.5 | 4.9 | 168 | **PASS**  |
| slow_servos | all servos half speed, 25 ms lag, extra backlash | 188 | 1.0 | 1.2 | 0.8 | 7 / 4 | 4.5 | +0.03 | 4.4 | 4.9 | 168 | **PASS**  |
| imu_misalign2 | IMU mounted 2 deg crooked | 188 | 0.7 | 1.0 | 1.2 | 10 / 10 | 4.4 | +0.03 | 4.5 | 4.9 | 168 | **PASS**  |
| gyro_drift | gyro bias drifting 10x faster than spec | 188 | 0.8 | 1.0 | 1.1 | 8 / 8 | 4.3 | +0.03 | 4.5 | 4.9 | 168 | **PASS**  |
| roll_program | camera panorama: 90 deg/s roll programme in the coast | 188 | 0.8 | 1.1 | 1.1 | 8 / 110 | 6.3 | +0.03 | 4.3 | 4.9 | 167 | **PASS**  |
| coast_rate_only | tabs only damp pitch/yaw in the coast (no attitude hold) | 188 | 0.8 | 5.5 | 1.1 | 8 / 8 | 4.1 | +0.03 | 3.5 | 4.9 | 163 | **PASS**  |
| tabs_disabled | tabs switched off in the settings (TVC only, like KESTREL-1) | 188 | 1.1 | 18.8 | 4.5 | 258 / 304 | 0.0 | +0.03 | 2.6 | 4.9 | 158 | **PASS**  |
| motor_D20 | TSP D20-0 in the 24 mm adapter (first test hops) | 19 | 0.3 | 4.4 | 0.7 | 1 / 2 | 14.4 | +0.05 | 1.2 | 5.0 | 8 | **PASS**  |
| motor_E20 | TSP E20-0 in the 24 mm adapter (second test flights) | 53 | 0.3 | 2.2 | 0.9 | 1 / 2 | 10.1 | +0.04 | 2.6 | 5.0 | 41 | **PASS**  |
| motor_curve | F35 performing like its published test curve instead of its rating | 195 | 0.8 | 1.0 | 0.7 | 12 / 7 | 4.3 | +0.03 | 4.5 | 4.9 | 171 | **PASS**  |
| unarmed_launch | FAULT: launched before calibration finished (1 s on the pad) | 179 | 18.7 | 55.7 | 0.0 | 259 / 305 | 0.0 | +0.02 | 7.6 | 4.9 | 113 | **PASS**  |
| tvc_off_calm | FAULT: TVC servos dead, calm | 188 | 3.6 | 0.8 | 0.0 | 8 / 7 | 9.1 | +0.04 | 0.5 | 4.9 | 5 | **PASS**  |
| tvc_off_wind3 | FAULT: TVC servos dead, 3 m/s wind (tabs still steer) | 188 | 4.5 | 1.5 | 0.0 | 5 / 4 | 10.5 | +0.03 | 4.3 | 4.9 | 163 | **PASS**  |
| servo_hardover | FAULT: TVC pitch servo jams at full deflection at T+0.5 s | 25 | 168.7 | 0.0 | 6.5 | 50 / 0 | 14.4 | -0.74 | 28.1 | 4.9 | 25 | **PASS** contained near pad |
| tab_hardover | FAULT: tab 1 jams at full deflection at T+1 s | 133 | 3.6 | 174.8 | 4.3 | 148 / 738 | 16.0 | -0.06 | 8.2 | 4.9 | 128 | **PASS**  |
| tab_stuck | FAULT: tab 2 freezes at T+0.5 s | 188 | 0.8 | 1.1 | 1.0 | 18 / 23 | 5.8 | +0.03 | 4.4 | 4.9 | 167 | **PASS**  |
| tabs_dead | FAULT: all four tab servos dead from launch | 188 | 1.4 | 19.9 | 1.4 | 258 / 304 | 0.0 | +0.03 | 2.4 | 4.9 | 157 | **PASS**  |
| passive_calm | FAULT: all 6 steering servos dead (TVC + tabs), calm | 181 | 15.7 | 41.3 | 0.0 | 256 / 301 | 0.0 | +0.03 | 8.0 | 4.9 | 64 | **PASS**  |
| passive_wind3 | FAULT: all 6 steering servos dead, 3 m/s wind | 180 | 18.3 | 58.2 | 0.0 | 259 / 306 | 0.0 | +0.01 | 7.6 | 4.9 | 110 | **PASS**  |
| passive_empty_bay | FAULT: all steering dead + empty payload bay (least stable), 3 m/s | 188 | 18.6 | 55.3 | 0.0 | 274 / 319 | 0.0 | +0.02 | 7.7 | 4.8 | 119 | **PASS**  |
| baro_dead | FAULT: barometer dies at T+1 s | 188 | 0.8 | 1.0 | 1.1 | 8 / 7 | 4.7 | +1.29 | 12.9 | 4.9 | 158 | **PASS**  |
| passive_wind6 | FAULT: all steering dead in 6 m/s wind (why first flights need <= 3 m/s) | 181 | 17.8 | 60.4 | 0.0 | 262 / 309 | 0.0 | +0.01 | 5.1 | 4.9 | 290 | **INFO** informational |
| no_chute | FAULT: parachute fails to deploy (shows why ground tests matter) | 188 | 0.8 | 1.1 | 1.1 | 8 / 8 | 4.3 | +0.03 | 4.4 | 52.8 | 48 | **INFO** informational |
| motor_E12 | TSP E12-0: NOT for KESTREL-2 (too little thrust for its mass) | 43 | 0.2 | 3.4 | 0.6 | 2 / 2 | 12.9 | +0.05 | 2.6 | 5.0 | 28 | **INFO** informational |
