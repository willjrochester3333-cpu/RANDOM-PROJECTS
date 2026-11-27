"""KESTREL FC v3.0 - single source of truth for the flight-computer circuit (7 servo outputs: 2 TVC, release, 4 fin tabs;
v3: a 6-pin JST-GH telemetry-radio socket (Pixhawk TELEM pinout) replaces the v2 Qwiic port).

Used by gen_schematic.py (KiCad schematic), gen_pcb.py (KiCad PCB, routing, DRC, fab files) and jlc_bom.py.
Board: 40 x 82 mm, 4 layers (F.Cu signals | In1 GND plane | In2 +3V3 plane | B.Cu signals + GND fill).
All parts are SMD on the top side except the pin headers/sockets/JST-XH/buzzer (JLCPCB hand-soldered THT),
so the user never solders anything.

Coordinates: mm, board origin = top-left corner, x right, y down; the top edge points at the nose.
"""

BOARD_W, BOARD_H = 40.0, 82.0
MOUNT_HOLES = [(3.5, 3.5), (36.5, 3.5), (36.5, 78.5)]   # M2.5, match the CAD sled standoffs (v3: the bottom-left
#                                                      corner holds the radio socket; the sled has a rest post there)

# Pico 2 W socket rows (female headers 1x20, 17.78 mm apart)
PICO_X1, PICO_X2, PICO_Y1 = 6.0, 23.78, 16.0
PICO_PIN_Y = {p: PICO_Y1 + 2.54 * (p - 1) for p in range(1, 21)}
PICO_PIN_Y.update({p: PICO_Y1 + 48.26 - 2.54 * (p - 21) for p in range(21, 41)})


def pico_nets():
    m = {1: "GPS_RXD", 2: "GPS_TXD", 3: "GND", 4: "SERVO5_PWM", 5: "SERVO_PWR_OFF", 6: "RADIO_TX", 7: "RADIO_RX", 8: "GND",
         9: "SERVO1_PWM", 10: "SERVO2_PWM", 11: "SERVO3_PWM", 12: "SERVO4_PWM", 13: "GND", 14: "BUZZER", 15: "LED_GREEN",
         16: "LED_RED", 17: "SERVO6_PWM", 18: "GND", 19: "BUTTON", 20: "SERVO7_PWM", 21: "SPI_MISO", 22: "CS_IMU", 23: "GND",
         24: "SPI_SCK", 25: "SPI_MOSI", 26: "CS_BARO", 27: "CS_FLASH", 28: "GND", 29: "BARO_INT", 30: "RUN",
         31: "VBAT_SENSE", 32: "CELL1_SENSE", 33: "GND", 34: "SERVO_V_SENSE", 35: None, 36: "+3V3", 37: None, 38: "GND",
         39: "VSYS", 40: None}
    return m


PICO_FUNCS = {1: "GP0", 2: "GP1", 3: "GND", 4: "GP2", 5: "GP3", 6: "GP4", 7: "GP5", 8: "GND", 9: "GP6", 10: "GP7", 11: "GP8",
              12: "GP9", 13: "GND", 14: "GP10", 15: "GP11", 16: "GP12", 17: "GP13", 18: "GND", 19: "GP14", 20: "GP15",
              21: "GP16", 22: "GP17", 23: "GND", 24: "GP18", 25: "GP19", 26: "GP20", 27: "GP21", 28: "GND", 29: "GP22",
              30: "RUN", 31: "GP26_A0", 32: "GP27_A1", 33: "AGND", 34: "GP28_A2", 35: "ADC_VREF", 36: "3V3_OUT",
              37: "3V3_EN", 38: "GND", 39: "VSYS", 40: "VBUS"}

# Footprint shortcuts
R0402 = "Resistor_SMD:R_0402_1005Metric"
C0402 = "Capacitor_SMD:C_0402_1005Metric"
C0805 = "Capacitor_SMD:C_0805_2012Metric"
C1206 = "Capacitor_SMD:C_1206_3216Metric"
SOT23 = "Package_TO_SOT_SMD:SOT-23"
LCSC_R = {"10k": "C25744", "100k": "C25741", "47k": "C25792", "33k": "C25779", "22k": "C25768", "1M": "C26083",
          "4.7k": "C25900", "220": "C25091", "120": "C25079", "330": "C25104", "100": "C25076", "22": "C25092", "0": "C17168"}
LCSC_C = {("100nF", C0402): "C1525", ("1uF", C0402): "C52923", ("10uF", C0805): "C15850", ("22uF", C1206): "C12891",
          ("47pF", C0402): "C1567", ("10nF", C0402): "C15195"}

PARTS = []


def part(ref, lib, value, fp, pins, pos, lcsc=None, mpn=None, block="misc", dnp=False, note=""):
    PARTS.append(dict(ref=ref, lib=lib, value=value, fp=fp, pins=pins, pos=pos, lcsc=lcsc, mpn=mpn or value,
                      block=block, dnp=dnp, note=note))


def R(ref, val, a, b, pos, block, note="", dnp=False):
    part(ref, "Device:R", val, R0402, {"1": a, "2": b}, pos, LCSC_R[val], f"0402 {val} 1%", block, dnp=dnp, note=note)


def C(ref, val, a, b, pos, block, fp=C0402):
    part(ref, "Device:C", val, fp, {"1": a, "2": b}, pos, LCSC_C[(val, fp)], f"{fp.split('_')[1]} {val}", block)


# ------------------------------------------------------------------------------------------------
# Raspberry Pi Pico 2 W (plug-in module on two 1x20 female headers)
pn = pico_nets()
part("J10", "Connector_Generic:Conn_01x20", "Pico2W pins 1-20", "Connector_PinSocket_2.54mm:PinSocket_1x20_P2.54mm_Vertical",
     {str(p): pn[p] for p in range(1, 21)}, (PICO_X1, PICO_Y1, 0), "C7499336", "Female header 1x20 2.54 mm H8.5", "mcu")
part("J11", "Connector_Generic:Conn_01x20", "Pico2W pins 21-40", "Connector_PinSocket_2.54mm:PinSocket_1x20_P2.54mm_Vertical",
     {str(p - 20): pn[p] for p in range(21, 41)}, (PICO_X2, PICO_Y1 + 48.26, 180), "C7499336", "Female header 1x20 2.54 mm H8.5", "mcu")

# ------------------------------------------------------------------------------------------------
# Power input: 2S LiPo balance lead (JST-XH 3P) -> reverse-polarity P-FET -> soft switch P-FET
part("J1", "Connector_Generic:Conn_01x03", "BATT 2S (balance plug)", "Connector_JST:JST_XH_B3B-XH-A_1x03_P2.50mm_Vertical",
     {"1": "GND", "2": "CELL1", "3": "VBAT_IN"}, (25.5, 76.5, 0), "C144394", "JST B3B-XH-A", "power")
part("Q1", "Transistor_FET:AO3401A", "AO3401A", SOT23, {"1": "Q1_G", "2": "VBAT_RP", "3": "VBAT_IN"}, (33.0, 70.0, 0), "C15127", block="power",
     note="reverse-polarity protection")
R("R1", "100k", "Q1_G", "VBAT_RP", (30.0, 67.5, 90), "power")
R("R2", "47k", "Q1_G", "GND", (30.0, 71.5, 90), "power")
part("D1", "Device:D_Zener", "SMF13A", "Diode_SMD:D_SOD-123F", {"1": "VBAT_RP", "2": "GND"}, (36.5, 65.0, 90), "C41376087",
     "SMF13A TVS 13V", "power")
part("Q2", "Transistor_FET:AO3401A", "AO3401A", SOT23, {"1": "Q2_G", "2": "VBAT_RP", "3": "VBAT_SW"}, (33.0, 50.0, 0), "C15127", block="power",
     note="soft power switch")
R("R3", "100k", "Q2_G", "VBAT_RP", (30.0, 52.5, 90), "power")
R("R4", "47k", "Q2_G", "SW_COM", (30.0, 48.0, 90), "power")
part("SW1", "Switch:SW_SPDT", "POWER", "Button_Switch_SMD:SW_SPDT_PCM12", {"1": "GND", "2": "SW_COM", "3": None},
     (37.6, 40.0, 90), "C221841", "C&K PCM12SMTR", "power")
C("C1", "10uF", "VBAT_SW", "GND", (36.0, 55.0, 90), "power", C0805)
C("C2", "100nF", "VBAT_SW", "GND", (33.5, 55.0, 90), "power")
R("R5", "100k", "VBAT_SW", "VBAT_SENSE", (27.5, 44.5, 90), "power")
R("R6", "33k", "VBAT_SENSE", "GND", (27.5, 40.5, 90), "power")
C("C3", "100nF", "VBAT_SENSE", "GND", (27.5, 37.0, 90), "power")
R("R7", "1M", "CELL1", "CELL1_SENSE", (27.5, 33.5, 90), "power", note="cell-1 tap, 2 uA load")
R("R8", "1M", "CELL1_SENSE", "GND", (27.5, 30.0, 90), "power")
C("C4", "100nF", "CELL1_SENSE", "GND", (27.5, 26.5, 90), "power")

# ------------------------------------------------------------------------------------------------
# Servo rail buck: TPS563201 -> 5.0 V / 3 A
BUCK = "Regulator_Switching:TPS563200"
part("U2", BUCK, "TPS563201", "Package_TO_SOT_SMD:TSOT-23-6",
     {"1": "GND", "2": "SW_S", "3": "VBAT_SW", "4": "FB_S", "5": "EN_S", "6": "BST_S"}, (31.0, 60.0, 0), "C116592",
     "TI TPS563201DDCR", "servo_buck")
C("C5", "100nF", "BST_S", "SW_S", (31.0, 57.2, 0), "servo_buck")
part("L1", "Device:L", "3.3uH", "Inductor_SMD:L_Sunlord_MWSA0503S", {"1": "SW_S", "2": "5V_SERVO"}, (34.8, 60.5, 90), "C408409",
     "Sunlord MWSA0503S-3R3MT 5.5A", "servo_buck")
C("C6", "10uF", "VBAT_SW", "GND", (28.0, 60.0, 90), "servo_buck", C0805)
R("R9", "33k", "5V_SERVO", "FB_S_M", (31.5, 63.3, 0), "servo_buck", note="33k+22k = 55k top")
R("R10", "22k", "FB_S_M", "FB_S", (29.0, 63.3, 0), "servo_buck")
R("R11", "10k", "FB_S", "GND", (29.0, 65.0, 0), "servo_buck")
R("R12", "100k", "VBAT_SW", "EN_S", (33.5, 63.3, 0), "servo_buck")
part("Q3", "Transistor_FET:2N7002", "2N7002", SOT23, {"1": "SERVO_PWR_OFF", "2": "GND", "3": "EN_S"}, (26.8, 64.0, 0), "C8545",
     block="servo_buck", note="MCU can switch the servo rail off")
R("R13", "100k", "SERVO_PWR_OFF", "GND", (26.0, 61.0, 90), "servo_buck")
C("C7", "22uF", "5V_SERVO", "GND", (38.0, 59.5, 90), "servo_buck", C1206)
C("C8", "22uF", "5V_SERVO", "GND", (38.0, 55.0, 90), "servo_buck", C1206)
C("C9", "22uF", "5V_SERVO", "GND", (26.5, 69.0, 0), "servo_buck", C1206)
R("R14", "100k", "5V_SERVO", "SERVO_V_SENSE", (36.0, 46.0, 90), "servo_buck")
R("R15", "100k", "SERVO_V_SENSE", "GND", (36.0, 49.5, 90), "servo_buck")

# ------------------------------------------------------------------------------------------------
# Logic buck: TPS563201 -> 5.0 V -> Schottky -> Pico VSYS (Pico makes its own 3V3)
part("U3", BUCK, "TPS563201", "Package_TO_SOT_SMD:TSOT-23-6",
     {"1": "GND", "2": "SW_L", "3": "VBAT_SW", "4": "FB_L", "5": "EN_L", "6": "BST_L"}, (31.0, 21.0, 0), "C116592",
     "TI TPS563201DDCR", "logic_buck")
C("C10", "100nF", "BST_L", "SW_L", (31.0, 18.2, 0), "logic_buck")
part("L2", "Device:L", "3.3uH", "Inductor_SMD:L_Sunlord_MWSA0503S", {"1": "SW_L", "2": "5V_LOG"}, (34.8, 21.5, 90), "C408409",
     "Sunlord MWSA0503S-3R3MT 5.5A", "logic_buck")
C("C11", "10uF", "VBAT_SW", "GND", (28.0, 21.0, 90), "logic_buck", C0805)
R("R16", "33k", "5V_LOG", "FB_L_M", (31.5, 24.3, 0), "logic_buck")
R("R17", "22k", "FB_L_M", "FB_L", (29.0, 24.3, 0), "logic_buck")
R("R18", "10k", "FB_L", "GND", (29.0, 26.0, 0), "logic_buck")
R("R19", "100k", "VBAT_SW", "EN_L", (33.5, 24.3, 0), "logic_buck")
C("C12", "22uF", "5V_LOG", "GND", (38.0, 21.0, 90), "logic_buck", C1206)
C("C13", "22uF", "5V_LOG", "GND", (38.0, 25.5, 90), "logic_buck", C1206)
part("D2", "Device:D_Schottky", "B5819W", "Diode_SMD:D_SOD-123", {"1": "VSYS", "2": "5V_LOG"}, (33.5, 28.5, 180), "C8598",
     "B5819W SL", "logic_buck", note="OR-ing with the Pico's own USB VBUS diode")
C("C14", "10uF", "VSYS", "GND", (26.5, 17.0, 90), "logic_buck", C0805)
C("C15", "10uF", "+3V3", "GND", (26.5, 31.5, 90), "logic_buck", C0805)

# ------------------------------------------------------------------------------------------------
# Sensors on SPI0 (all under the Pico)
part("U4", "Sensor_Motion:LSM6DSM", "LSM6DSO", "Package_LGA:LGA-14_3x2.5mm_P0.5mm_LayoutBorder3x4y",
     {"1": "SPI_MISO", "2": "GND", "3": "GND", "4": None, "5": "+3V3", "6": "GND", "7": "GND", "8": "+3V3", "9": None,
      "10": None, "11": None, "12": "CS_IMU", "13": "SPI_SCK", "14": "SPI_MOSI"}, (15.0, 39.0, 0), "C2655100",
     "ST LSM6DSOTR (alt: LSM6DS3TR-C C967633)", "sensors", note="pin-compatible with LSM6DSM symbol; SDx/SCx tied low (mode 1)")
C("C16", "100nF", "+3V3", "GND", (12.0, 39.5, 90), "sensors")
C("C17", "100nF", "+3V3", "GND", (18.0, 39.5, 90), "sensors")
R("R20", "10k", "CS_IMU", "+3V3", (18.5, 36.0, 0), "sensors")
part("U5", "kestrel:BMP580", "BMP580", "kestrel:Bosch_LGA-10_2x2mm_P0.5mm_BMP58x",
     {"1": "+3V3", "2": "SPI_SCK", "3": "GND", "4": "SPI_MOSI", "5": "SPI_MISO", "6": "CS_BARO", "7": "BARO_INT", "8": "GND",
      "9": "GND", "10": "+3V3"}, (15.0, 47.0, 0), "C22391138", "Bosch BMP580", "sensors",
     note="land pattern from SparkFun BMP581 Qwiic board (verified product)")
C("C18", "100nF", "+3V3", "GND", (12.0, 47.0, 90), "sensors")
C("C19", "100nF", "+3V3", "GND", (18.0, 47.0, 90), "sensors")
R("R21", "10k", "CS_BARO", "+3V3", (18.5, 44.0, 0), "sensors")
part("U6", "Memory_Flash:W25Q128JVS", "W25Q128JVSIQ", "Package_SO:SOIC-8_5.23x5.23mm_P1.27mm",
     {"1": "CS_FLASH", "2": "SPI_MISO", "3": "+3V3", "4": "GND", "5": "SPI_MOSI", "6": "SPI_SCK", "7": "+3V3", "8": "+3V3"},
     (15.0, 56.5, 0), "C97521", "Winbond W25Q128JVSIQ 16 MB", "sensors")
C("C20", "100nF", "+3V3", "GND", (19.5, 61.0, 0), "sensors")
R("R22", "10k", "CS_FLASH", "+3V3", (10.5, 61.0, 0), "sensors")

# ------------------------------------------------------------------------------------------------
# GPS (u-blox MAX footprint: ATGM336H-5N31 default, MAX-M10S drop-in) + active antenna bias tee
part("U7", "RF_GPS:MAX-M10S", "ATGM336H-5N31", "RF_GPS:ublox_MAX",
     {"1": "GND", "2": "GPS_TXD", "3": "GPS_RXD", "4": None, "5": None, "6": "+3V3_GPS", "7": "VIO_GPS", "8": "+3V3_GPS",
      "9": None, "10": "GND", "11": "RF_IN", "12": "GND", "13": None, "14": None, "15": None, "16": None, "17": None, "18": None},
     (15.0, 22.0, 270), "C90770", "ZHONGKEWEI ATGM336H-5N31 (alt: u-blox MAX-M10S C24834155)", "gps",
     note="only pins common to MAX-compatible modules are used")
R("R23", "0", "+3V3_GPS", "VIO_GPS", (9.6, 28.6, 0), "gps", note="fit for MAX-M10S/ATGM336H (VIO / NC)")
part("FB1", "Device:FerriteBead_Small", "600R@100MHz", "Inductor_SMD:L_0805_2012Metric", {"1": "+3V3", "2": "+3V3_GPS"},
     (12.0, 29.5, 0), "C1017", "0805 ferrite 600R 500mA", "gps")
C("C21", "10uF", "+3V3_GPS", "GND", (19.5, 29.0, 0), "gps", C0805)
C("C22", "100nF", "+3V3_GPS", "GND", (16.2, 29.5, 0), "gps")
part("J8", "Connector:Conn_Coaxial", "GPS ANT (U.FL)", "Connector_Coaxial:U.FL_Hirose_U.FL-R-SMT-1_Vertical",
     {"1": "RF_ANT", "2": "GND"}, (14.5, 11.6, 90), "C88374", "Hirose U.FL-R-SMT-1(80)", "gps")
C("C23", "47pF", "RF_ANT", "RF_IN", (16.5, 14.3, 90), "gps")
part("L3", "Device:L", "15nH", "Inductor_SMD:L_0402_1005Metric", {"1": "BIAS_N", "2": "RF_ANT"}, (12.3, 13.9, 0), "C27143",
     "0402 15nH (antenna DC feed)", "gps")
R("R24", "22", "+3V3_GPS", "BIAS_N", (9.9, 13.9, 0), "gps", dnp=True,
  note="NOT FITTED: passive antenna, no DC bias on the U.FL (fit 22R only for an active antenna)")
C("C24", "100nF", "BIAS_N", "GND", (11.2, 15.6, 0), "gps")

# ------------------------------------------------------------------------------------------------
# Servo outputs (S + -). 220R series resistors protect the GPIOs. 7 ports at 3.75 mm pitch along the bottom edge:
#   1 TVC ring (GP6)  2 TVC motor holder (GP7)  3 parachute release (GP8)  4-7 fin tabs 1-4 (GP9, GP2, GP13, GP15)
SERVO_X = [8.8 + 3.75 * i for i in range(7)]
SERVO_LABEL = ["TVC RING", "TVC MOTOR", "RELEASE", "TAB1", "TAB2", "TAB3", "TAB4"]
for i, x in enumerate(SERVO_X):
    n = i + 1
    ref = f"J{n + 1}" if n <= 4 else f"J{n + 7}"          # J2-J5 as before, J12-J14 new
    part(ref, "Connector_Generic:Conn_01x03", f"SERVO{n} {SERVO_LABEL[i]}", "Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical",
         {"1": f"S{n}", "2": "5V_SERVO", "3": "GND"}, (x, 74.85, 0), "C49257", "Male header 1x3 2.54 mm", "servos")
    R(f"R{24 + n}" if n <= 4 else f"R{36 + n - 4}", "220", f"SERVO{n}_PWM", f"S{n}", (x, 71.1, 90), "servos")

# ------------------------------------------------------------------------------------------------
# User interface: buzzer, LEDs, buttons, telemetry-radio socket
part("BZ1", "Device:Buzzer", "TMB12A03", "Buzzer_Beeper:Buzzer_12x9.5RM7.6", {"1": "+3V3", "2": "BUZ_N"}, (9.2, 7.0, 0), "C96222",
     "12 mm active buzzer 3V 85 dB", "ui")
part("Q4", "Transistor_FET:AO3400A", "AO3400A", SOT23, {"1": "BUZ_G", "2": "GND", "3": "BUZ_N"}, (21.0, 7.5, 0), "C20917", block="ui")
R("R31", "100", "BUZZER", "BUZ_G", (21.0, 10.5, 0), "ui")
R("R32", "100k", "BUZ_G", "GND", (21.0, 12.1, 0), "ui")
part("D3", "Device:D_Schottky", "1N5819WS", "Diode_SMD:D_SOD-323", {"1": "+3V3", "2": "BUZ_N"}, (21.0, 4.0, 180), "C191023",
     "flyback", "ui")
part("D4", "Device:LED", "GREEN", "LED_SMD:LED_0805_2012Metric", {"1": "GND", "2": "LEDG_A"}, (38.4, 34.6, 90), "C2297", "0805 green", "ui")
R("R33", "120", "LED_GREEN", "LEDG_A", (35.6, 34.6, 90), "ui")
part("D5", "Device:LED", "RED", "LED_SMD:LED_0805_2012Metric", {"1": "GND", "2": "LEDR_A"}, (38.4, 45.4, 90), "C84256", "0805 red", "ui")
R("R34", "330", "LED_RED", "LEDR_A", (33.4, 44.0, 90), "ui")
part("SW2", "Switch:SW_Push", "USER", "Button_Switch_SMD:SW_Push_1P1T_XKB_TS-1187A", {"1": "BUTTON", "2": "GND"}, (31.0, 8.5, 0),
     "C318884", "XKB TS-1187A 5.1 mm", "ui")
part("SW3", "Switch:SW_Push", "RESET", "Button_Switch_SMD:SW_Push_1P1T_XKB_TS-1187A", {"1": "RUN", "2": "GND"}, (31.0, 14.5, 0),
     "C318884", "XKB TS-1187A 5.1 mm", "ui")
part("J7", "Connector_Generic:Conn_01x06", "RADIO (SiK, Pixhawk TELEM)", "Connector_JST:JST_GH_BM06B-GHS-TBT_1x06-1MP_P1.25mm_Vertical",
     {"1": "VSYS", "2": "RADIO_TX", "3": "RADIO_RX", "4": None, "5": None, "6": "GND", "MP": "GND"}, (3.5, 74.5, 270), "C189892",
     "JST BM06B-GHS-TBT(LF)(SN)", "ui",
     note="telemetry radio, Pixhawk TELEM pinout: 1 +5V (VSYS), 2 TX out (GP4, UART1), 3 RX in (GP5), 4 CTS / 5 RTS not used, 6 GND")
C("C25", "10uF", "VSYS", "GND", (4.6, 67.3, 0), "ui", C0805)

# Mounting holes (not in BOM)
MH = [dict(ref=f"H{i+1}", pos=p) for i, p in enumerate(MOUNT_HOLES)]


def nets():
    s = set()
    for p in PARTS:
        for n in p["pins"].values():
            if n:
                s.add(n)
    return sorted(s)


POWER_NETS = {"GND": 0.6, "+3V3": 0.4, "+3V3_GPS": 0.4, "VBAT_IN": 0.8, "VBAT_RP": 0.8, "VBAT_SW": 0.8, "5V_SERVO": 1.0,
              "5V_LOG": 0.6, "VSYS": 0.6, "AUX_5V": 0.6, "SW_S": 0.8, "SW_L": 0.6, "CELL1": 0.3}

if __name__ == "__main__":
    print(len(PARTS), "parts,", len(nets()), "nets")
    from collections import Counter
    c = Counter()
    for p in PARTS:
        for n in p["pins"].values():
            if n:
                c[n] += 1
    single = [n for n, k in c.items() if k < 2]
    print("nets with a single connection:", single)


# --- placement (legalised in board_build.py) ---
PLACEMENT = {'BZ1': (9.45, 7.15, 0), 'J8': (22.6, 3.0, 90), 'L3': (21.3, 7.6, 90), 'R24': (21.3, 10.3, 90), 'C24': (23.6, 9.0, 90), 'C23': (23.6, 12.2, 90), 'U7': (14.9, 20.6, 270), 'FB1': (11.5, 28.3, 0), 'C21': (17.6, 28.3, 0), 'C22': (14.6, 30.3, 0), 'R23': (10.3, 30.3, 0), 'U4': (15.0, 38.0, 0), 'C16': (11.6, 38.0, 90), 'C17': (18.4, 38.0, 90), 'R20': (15.0, 35.4, 0), 'U5': (15.0, 45.0, 0), 'C18': (11.8, 45.0, 90), 'C19': (18.2, 45.0, 90), 'R21': (15.0, 42.4, 0), 'U6': (15.0, 54.5, 0), 'C20': (18.0, 58.6, 0), 'R22': (12.0, 58.6, 0), 'SW2': (29.7, 3.9, 0), 'SW3': (29.7, 9.9, 0), 'Q4': (30.5, 15.1, 0), 'R31': (34.2, 13.8, 0), 'R32': (34.2, 15.4, 0), 'D3': (36.6, 9.6, 180), 'U3': (30.0, 21.6, 0), 'C10': (30.0, 19.0, 0), 'L2': (36.5, 22.0, 90), 'C11': (26.9, 21.8, 90), 'R16': (31.2, 24.4, 0), 'R17': (29.1, 24.4, 0), 'R18': (29.1, 25.9, 0), 'R19': (31.2, 25.9, 0), 'C12': (36.5, 26.9, 0), 'C13': (36.5, 29.4, 0), 'D2': (29.5, 28.4, 180), 'C14': (26.9, 17.6, 90), 'C15': (26.9, 31.4, 90), 'SW1': (36.6, 40.0, 90), 'D4': (38.4, 33.3, 90), 'R33': (35.8, 33.3, 90), 'D5': (38.4, 46.7, 90), 'R34': (35.8, 46.7, 90), 'Q2': (29.0, 36.6, 0), 'R3': (32.3, 35.8, 90), 'R4': (32.3, 38.9, 90), 'R5': (26.4, 41.0, 90), 'R6': (26.4, 44.0, 90), 'C3': (26.4, 47.0, 90), 'R7': (28.2, 41.0, 90), 'R8': (28.2, 44.0, 90), 'C4': (28.2, 47.0, 90), 'R14': (30.0, 42.0, 90), 'R15': (30.0, 45.0, 90), 'C2': (32.0, 42.5, 90), 'C1': (32.4, 46.0, 0), 'U2': (30.0, 51.6, 0), 'C5': (30.0, 49.0, 0), 'L1': (36.5, 52.4, 90), 'C6': (26.9, 51.8, 90), 'R9': (31.2, 54.4, 0), 'R10': (29.1, 54.4, 0), 'R11': (29.1, 55.9, 0), 'R12': (31.2, 55.9, 0), 'C7': (36.5, 57.3, 0), 'C8': (36.5, 59.8, 0), 'Q3': (28.0, 59.2, 0), 'R13': (31.6, 58.4, 0), 'J1': (36.1, 70.45, 90), 'Q1': (29.3, 64.5, 0), 'R1': (26.4, 63.9, 90), 'R2': (26.4, 66.9, 90), 'D1': (28.5, 69.0, 0), 'J7': (3.5, 74.5, 270), 'C25': (4.6, 67.3, 0), 'C9': (15.5, 67.6, 0)}
for _p in PARTS:
    if _p['ref'] in PLACEMENT:
        _p['pos'] = PLACEMENT[_p['ref']]
