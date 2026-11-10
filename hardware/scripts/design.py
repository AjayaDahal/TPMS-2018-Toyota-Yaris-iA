"""Circuit definition for the TPMS monitor panel: symbols, parts, nets and schematic layout.

Every pin is listed explicitly: a net name, or None for an intentional no-connect.
Nets named GND, +3V3, +5V and +12V are drawn with power symbols; all others with global labels.
"""
import panel_config as CFG

ENCODER = CFG.INPUT_STYLE == "encoder"
POWER_NETS = ("GND", "+3V3", "+5V", "+12V")

# ------------------------------------------------------------------ custom symbols (TPMS library)
# Each pin: (number, name, electrical type). None leaves an empty row.
CUSTOM_SYMBOLS = {
    "ESP32_DevKit_V1_30pin": dict(
        ref="A", value="ESP32_DevKit_V1", footprint="TPMS:ESP32_DOIT_DevKit_V1_30pin",
        description="DOIT ESP32 DEVKIT V1 (30-pin) development board, plugs into 2x 1x15 sockets",
        half_width=10.16,
        left=[("1", "EN", "input"), ("2", "IO36/VP", "input"), ("3", "IO39/VN", "input"),
              ("4", "IO34", "input"), ("5", "IO35", "input"), ("6", "IO32", "bidirectional"),
              ("7", "IO33", "bidirectional"), ("8", "IO25", "bidirectional"), ("9", "IO26", "bidirectional"),
              ("10", "IO27", "bidirectional"), ("11", "IO14", "bidirectional"), ("12", "IO12", "bidirectional"),
              ("13", "IO13", "bidirectional"), ("14", "GND", "power_in"), ("15", "VIN", "power_in")],
        right=[("16", "IO23", "bidirectional"), ("17", "IO22", "bidirectional"), ("18", "TX0/IO1", "bidirectional"),
               ("19", "RX0/IO3", "bidirectional"), ("20", "IO21", "bidirectional"), ("21", "IO19", "bidirectional"),
               ("22", "IO18", "bidirectional"), ("23", "IO5", "bidirectional"), ("24", "IO17", "bidirectional"),
               ("25", "IO16", "bidirectional"), ("26", "IO4", "bidirectional"), ("27", "IO2", "bidirectional"),
               ("28", "IO15", "bidirectional"), ("29", "GND", "power_in"), ("30", "3V3", "power_out")],
    ),
    "CC1101_Module": dict(
        ref="U", value="CC1101_315MHz", footprint="TPMS:CC1101_E07-M1101D_Socket",
        description="TI CC1101 sub-GHz transceiver module, E07-M1101D 2x4 pinout, 3.3 V only",
        half_width=7.62,
        left=[("2", "VCC", "power_in"), None, None, None, None, ("1", "GND", "power_in")],
        right=[("4", "CSN", "input"), ("5", "SCK", "input"), ("6", "MOSI", "input"),
               ("7", "MISO/GDO1", "output"), ("3", "GDO0", "output"), ("8", "GDO2", "output")],
    ),
    "NHD-2.7-12864WDW3": dict(
        ref="U", value="NHD-2.7-12864WDW3", footprint="TPMS:NHD-2.7-12864WDW3",
        description="Newhaven 2.7in 128x64 OLED module, SSD1322, 1x20 2.54 mm header, 3.3 V",
        half_width=8.89,
        left=[("1", "VSS", "power_in"), ("2", "VDD", "power_in"), ("3", "BC_VDD", "passive"),
              ("4", "D/~{C}", "input"), ("5", "R/~{W}", "input"), ("6", "E", "input"),
              ("7", "DB0/SCLK", "input"), ("8", "DB1/SDIN", "input"), ("9", "DB2", "input"),
              ("10", "DB3", "input"), ("11", "DB4", "input"), ("12", "DB5", "input"),
              ("13", "DB6", "input"), ("14", "DB7", "input"), ("15", "VCC", "passive"),
              ("16", "~{RES}", "input"), ("17", "~{CS}", "input"), ("18", "~{SHDN}", "input"),
              ("19", "BS1", "input"), ("20", "BS0", "input")],
        right=[],
    ),
    "MX-05V_Receiver": dict(
        ref="J", value="MX-05V", footprint="Connector_PinSocket_2.54mm:PinSocket_1x04_P2.54mm_Vertical",
        description="MX-05V / XY-MK-5V superregenerative OOK receiver module (optional)",
        half_width=5.08,
        left=[("1", "VCC", "power_in"), ("2", "DATA", "passive"), ("3", "DATA", "passive"), ("4", "GND", "power_in")],
        right=[],
    ),
}

# ------------------------------------------------------------------ parts
R1206 = "Resistor_SMD:R_1206_3216Metric"
C1206 = "Capacitor_SMD:C_1206_3216Metric"


def part(ref, lib_id, value, footprint, at, pins, mpn="", desc="", dnp=False):
    return dict(ref=ref, lib_id=lib_id, value=value, footprint=footprint, at=at, pins=pins,
                mpn=mpn, desc=desc, dnp=dnp)


def two(n1, n2):
    return {"1": n1, "2": n2}


LED_NETS = (("D1", "R1", "LED_FL", "FL"), ("D2", "R2", "LED_FR", "FR"),
            ("D3", "R3", "LED_RL", "RL"), ("D4", "R4", "LED_RR", "RR"))
BTN_NETS = (("SW1", "R5", "BTN_UP", "UP"), ("SW2", "R6", "BTN_OK", "OK"),
            ("SW3", "R7", "BTN_DOWN", "DOWN"), ("SW4", "R8", "BTN_BACK", "BACK"))
UI_X = (33.02, 63.5, 93.98, 124.46)

PARTS = [
    # ---------------------------------------------------------- power 12 V -> 5 V -> 3.3 V
    part("J1", "Connector_Generic:Conn_01x02", "12V_IN",
         "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal",
         (30.48, 50.8), two("VIN_RAW", "GND"), "Phoenix MKDS 1,5/2-5,08 (1715721)", "Screw terminal, 12 V ACC input"),
    part("F1", "Device:Polyfuse", "0.75A", "Fuse:Fuse_1812_4532Metric", (50.8, 50.8),
         two("VIN_RAW", "VIN_FUSED"), "Bourns MF-MSMF075/24X-2", "PTC fuse 1812, 0.75 A hold (0.49 A at 70 C), 24 V"),
    part("D6", "Device:D_TVS", "SMAJ22CA", "Diode_SMD:D_SMA", (76.2, 50.8),
         two("VIN_FUSED", "GND"), "Littelfuse SMAJ22CA",
         "Bidirectional TVS 22 V, SMA: 24.4 V min breakdown (24 V jump start), 35.5 V clamp (< 36 V of U3)"),
    part("D5", "Device:D_Schottky", "SS34", "Diode_SMD:D_SMA", (101.6, 50.8),
         two("+12V", "VIN_FUSED"), "SS34", "Schottky 40 V 3 A, reverse-polarity protection"),
    part("C1", "Device:C_Polarized", "47u/50V", "Capacitor_SMD:CP_Elec_6.3x7.7", (127.0, 50.8),
         two("+12V", "GND"), "Panasonic EEE-FK1H470XP",
         "Aluminium electrolytic 47 uF 50 V, 6.3 mm (U3 needs 22 uF / 50 V at its input above 30-32 V)"),
    part("C2", "Device:C", "1u/50V", C1206, (139.7, 50.8), two("+12V", "GND"), "", "MLCC X7R 1206"),
    part("U3", "Converter_DCDC:TSR_1-2450", "TSR_1-2450", "Converter_DCDC:Converter_DCDC_TRACO_TSR-1_THT",
         (165.1, 50.8), {"1": "+12V", "2": "GND", "3": "+5V"},
         "TRACO TSR 1-2450 (6.5-36 V in; alt. Mornsun K7805-1000R3, 8-36 V)",
         "5 V 1 A switching regulator, 7805 pinout, needs >= 36 V input rating"),
    part("C3", "Device:C", "22u/10V", C1206, (187.96, 50.8), two("+5V", "GND"), "", "MLCC X5R 1206"),
    part("U4", "Regulator_Linear:AMS1117-3.3", "AMS1117-3.3", "Package_TO_SOT_SMD:SOT-223-3_TabPin2",
         (165.1, 81.28), {"1": "GND", "2": "+3V3", "3": "+5V"}, "AMS1117-3.3", "3.3 V 1 A LDO (display + radio)"),
    part("C4", "Device:C", "10u/25V", C1206, (139.7, 81.28), two("+5V", "GND"), "", "MLCC X5R 1206"),
    part("C5", "Device:C_Polarized", "22u/10V Ta", "Capacitor_Tantalum_SMD:CP_EIA-3216-18_Kemet-A_HandSolder",
         (187.96, 81.28), two("+3V3", "GND"), "KEMET T491A226K010AT",
         "Tantalum 22 uF 10 V case A: AMS1117 output, as its datasheet specifies for stability"),
    # ---------------------------------------------------------- MCU
    part("A1", "TPMS:ESP32_DevKit_V1_30pin", "ESP32_DevKit_V1", "TPMS:ESP32_DOIT_DevKit_V1_30pin",
         (226.06, 76.2),
         {"1": None, "2": "MX05_DATA", "3": "IO39_EXP" if ENCODER else "BTN_BACK", "4": "CC_GDO0",
          "5": "CC_GDO2", "6": "LED_RL", "7": "LED_FR", "8": "LED_FL", "9": "OLED_RES", "10": "OLED_DC",
          "11": "LED_RR", "12": None, "13": "BUZZER", "14": "GND", "15": "+5V", "16": "SPI_MOSI",
          "17": "I2C_SCL", "18": None, "19": None, "20": "I2C_SDA", "21": "SPI_MISO", "22": "SPI_SCK",
          "23": "CC_CS", "24": "ENC_B" if ENCODER else "BTN_DOWN", "25": "ENC_A" if ENCODER else "BTN_OK",
          "26": "ENC_SW" if ENCODER else "BTN_UP", "27": "IO2_EXP", "28": "OLED_CS", "29": "GND", "30": None},
         "DOIT ESP32 DEVKIT V1 30-pin + 2x 1x15 2.54 mm female header",
         "ESP32 dev board (0.9 in or 1.0 in row spacing)"),
    # ---------------------------------------------------------- 315 MHz radio
    part("U1", "TPMS:CC1101_Module", "CC1101_315MHz", "TPMS:CC1101_E07-M1101D_Socket", (299.72, 55.88),
         {"1": "GND", "2": "+3V3", "3": "CC_GDO0", "4": "CC_CS", "5": "SPI_SCK", "6": "SPI_MOSI",
          "7": "SPI_MISO", "8": "CC_GDO2"},
         "EBYTE E07-M1101D-SMA (CC1101; 433 MHz-tuned build works at 315 MHz with some loss) + 2x4 2.54 mm "
         "female header + 315 MHz antenna",
         "Sub-GHz transceiver used as OOK receiver"),
    part("J2", "Connector_Generic:Conn_01x08", "CC1101_ALT",
         "Connector_PinHeader_2.54mm:PinHeader_1x08_P2.54mm_Vertical", (360.68, 55.88),
         {"1": "GND", "2": "+3V3", "3": "CC_GDO0", "4": "CC_CS", "5": "SPI_SCK", "6": "SPI_MOSI",
          "7": "SPI_MISO", "8": "CC_GDO2"},
         "1x8 2.54 mm pin header", "Breakout for CC1101 modules with other pinouts", dnp=True),
    part("C6", "Device:C", "10u/25V", C1206, (381.0, 50.8), two("+3V3", "GND"), "", "MLCC X5R 1206"),
    part("C7", "Device:C", "100n", C1206, (391.16, 50.8), two("+3V3", "GND"), "", "MLCC X7R 1206"),
    part("J3", "TPMS:MX-05V_Receiver", "MX-05V(opt)",
         "Connector_PinSocket_2.54mm:PinSocket_1x04_P2.54mm_Vertical", (299.72, 96.52),
         {"1": "+5V", "2": "MX05_RAW", "3": "MX05_RAW", "4": "GND"},
         "1x4 2.54 mm female header", "Optional MX-05V / XY-MK-5V 315 MHz receiver", dnp=True),
    part("R9", "Device:R", "1k", R1206, (325.12, 93.98), two("MX05_RAW", "MX05_DATA"), "", "1206 1%", dnp=True),
    part("R10", "Device:R", "10k", R1206, (335.28, 101.6), two("MX05_DATA", "GND"), "", "1206 1%", dnp=True),
    # ---------------------------------------------------------- display
    part("U2", "TPMS:NHD-2.7-12864WDW3", "NHD-2.7-12864WDW3", "TPMS:NHD-2.7-12864WDW3", (309.88, 165.1),
         {"1": "GND", "2": "+3V3", "3": "OLED_BCVDD", "4": "OLED_DC", "5": "GND", "6": "GND",
          "7": "SPI_SCK", "8": "SPI_MOSI", "9": None, "10": "GND", "11": "GND", "12": "GND", "13": "GND",
          "14": "GND", "15": None, "16": "OLED_RES", "17": "OLED_CS", "18": None, "19": "GND", "20": "GND"},
         "Newhaven NHD-2.7-12864WDW3 + 1x20 2.54 mm header + 4x M2 screws/nuts + 4x M2 x 3 mm spacers",
         "2.7 in 128x64 OLED, 4-wire SPI"),
    part("JP1", "Jumper:SolderJumper_2_Open", "BC_VDD_5V", "Jumper:SolderJumper-2_P1.3mm_Open_RoundedPad1.0x1.5mm",
         (350.52, 134.62), two("OLED_BCVDD", "+5V"), "", "Close for display jumper option #1"),
    part("C8", "Device:C", "10u/25V", C1206, (365.76, 134.62), two("+3V3", "GND"), "", "MLCC X5R 1206"),
    part("C9", "Device:C", "100n", C1206, (375.92, 134.62), two("+3V3", "GND"), "", "MLCC X7R 1206"),
    # ---------------------------------------------------------- buzzer
    part("BZ1", "Device:Buzzer", "Buzzer_5V", "Buzzer_Beeper:Buzzer_12x9.5RM7.6", (170.18, 124.46),
         two("+5V", "BUZ_C"), "12 mm 5 V active magnetic buzzer, 7.6 mm pitch", "Low-pressure alarm"),
    part("D7", "Device:D", "1N4148W", "Diode_SMD:D_SOD-123", (170.18, 139.7), two("+5V", "BUZ_C"),
         "1N4148W", "Flyback diode"),
    part("Q1", "Transistor_BJT:MMBT3904", "MMBT3904", "Package_TO_SOT_SMD:SOT-23", (170.18, 157.48),
         {"1": "BUZ_B", "2": "GND", "3": "BUZ_C"}, "MMBT3904", "Buzzer driver"),
    part("R11", "Device:R", "1k", R1206, (152.4, 175.26), two("BUZZER", "BUZ_B"), "", "1206 1%"),
    part("R12", "Device:R", "10k", R1206, (165.1, 175.26), two("BUZ_B", "GND"), "", "1206 1%"),
    # ---------------------------------------------------------- expansion
    part("J4", f"Connector_Generic:Conn_01x0{7 if ENCODER else 6}", "EXPANSION",
         f"Connector_PinHeader_2.54mm:PinHeader_1x0{7 if ENCODER else 6}_P2.54mm_Vertical", (226.06, 124.46),
         {"1": "+5V", "2": "+3V3", "3": "GND", "4": "I2C_SDA", "5": "I2C_SCL", "6": "IO2_EXP",
          **({"7": "IO39_EXP"} if ENCODER else {})},
         f"1x{7 if ENCODER else 6} 2.54 mm pin header", "Future expansion: I2C + spare GPIO", dnp=True),
    part("R13", "Device:R", "4k7", R1206, (241.3, 116.84), two("+3V3", "I2C_SDA"), "", "1206 1%"),
    part("R14", "Device:R", "4k7", R1206, (254.0, 116.84), two("+3V3", "I2C_SCL"), "", "1206 1%"),
]

# tyre LEDs (front) + series resistors (back)
for i, (d, r, net, lab) in enumerate(LED_NETS):
    PARTS.append(part(r, "Device:R", "220", R1206, (UI_X[i], 124.46), two(net, net + "_A"), "", "1206 1%"))
    PARTS.append(part(d, "Device:LED", "LED_" + lab, "LED_THT:LED_D5.0mm", (UI_X[i], 144.78),
                      {"1": "GND", "2": net + "_A"}, "5 mm LED", f"Tyre status LED {lab}"))
# user input (front) + conditioning (back)
if ENCODER:
    ENC_Y = 172.72
    PARTS += [
        part("SW1", "Device:RotaryEncoder_Switch_MP", "EC11_Encoder_SW",
             "Rotary_Encoder:RotaryEncoder_Alps_EC11E-Switch_Vertical_H20mm", (48.26, 177.8),
             {"A": "ENC_A_RAW", "B": "ENC_B_RAW", "C": "GND", "S1": "ENC_SW", "S2": "GND", "MP": "GND"},
             "EC11 rotary encoder with push switch (ALPS EC11E-switch type), 20 mm D-shaft + 20-25 mm knob",
             "Menu knob: rotate = up/down, push = OK"),
        part("R5", "Device:R", "10k", R1206, (76.2, ENC_Y), two("+3V3", "ENC_A_RAW"), "", "1206 1%"),
        part("R15", "Device:R", "10k", R1206, (86.36, ENC_Y), two("ENC_A_RAW", "ENC_A"), "", "1206 1%"),
        part("C10", "Device:C", "10n", C1206, (96.52, ENC_Y), two("ENC_A", "GND"), "", "MLCC X7R 1206"),
        part("R6", "Device:R", "10k", R1206, (106.68, ENC_Y), two("+3V3", "ENC_B_RAW"), "", "1206 1%"),
        part("R16", "Device:R", "10k", R1206, (116.84, ENC_Y), two("ENC_B_RAW", "ENC_B"), "", "1206 1%"),
        part("C11", "Device:C", "10n", C1206, (127.0, ENC_Y), two("ENC_B", "GND"), "", "MLCC X7R 1206"),
        part("R7", "Device:R", "10k", R1206, (137.16, ENC_Y), two("+3V3", "ENC_SW"), "", "1206 1%"),
        part("C12", "Device:C", "100n", C1206, (144.78, ENC_Y), two("ENC_SW", "GND"), "", "MLCC X7R 1206"),
    ]
else:
    for i, (sw, r, net, lab) in enumerate(BTN_NETS):
        PARTS.append(part(sw, "Switch:SW_Push", "BTN_" + lab, "Button_Switch_THT:SW_PUSH_6mm", (UI_X[i], 170.18),
                          two(net, "GND"), "6x6 mm THT tactile switch", f"Button {lab}"))
        PARTS.append(part(r, "Device:R", "10k", R1206, (UI_X[i], 193.04), two("+3V3", net), "", "1206 1%"))
# mechanical
for i, (ref, val, fp) in enumerate((
        ("H1", "M3", "MountingHole:MountingHole_3.2mm_M3"), ("H2", "M3", "MountingHole:MountingHole_3.2mm_M3"),
        ("H3", "M3", "MountingHole:MountingHole_3.2mm_M3"), ("H4", "M3", "MountingHole:MountingHole_3.2mm_M3"),
        ("H5", "USB_CUTOUT", "TPMS:USB_PanelMount_Cutout"),
        ("H6", "USB_CUTOUT", "TPMS:USB_PanelMount_Cutout"))):
    PARTS.append(part(ref, "Mechanical:MountingHole", val, fp, (205.74 + 15.24 * i, 236.22), {},
                      "USB 3.0 panel-mount passthrough cable, female socket to male plug, M25-class thread "
                      "(measured 25.2 mm), ~30 cm (buy 2)"
                      if "USB" in val else "",
                      "Cut-out for a panel-mount USB passthrough: front socket, male plug behind goes to the car's "
                      "USB port / a 12 V USB charger" if "USB" in val else "M3 mounting hole"))

# PWR_FLAGs: (net, x, y)
PWR_FLAGS = (("+12V", 40.64, 73.66), ("GND", 53.34, 73.66))

SHEET_TEXT = [
    (25.4, 30.48, 2.0, "POWER: 12 V (ACC) -> 5 V -> 3.3 V"),
    (198.12, 30.48, 2.0, "MCU: ESP32 DevKit V1 (DOIT, 30-pin)"),
    (279.4, 30.48, 2.0, "315 MHz RADIO: CC1101 module (+ optional MX-05V)"),
    (279.4, 119.38, 2.0, "DISPLAY: NHD-2.7-12864WDW3 (SSD1322, 4-wire SPI)"),
    (25.4, 104.14, 2.0, "FRONT PANEL: tyre LEDs, " + ("menu encoder" if ENCODER else "buttons") + ", buzzer"),
    (198.12, 106.68, 2.0, "EXPANSION"),
    (198.12, 226.06, 2.0, "MECHANICAL"),
    (186.69, 165.1, 1.27,
     "ESP32 GPIO MAP\n"
     "IO18 SPI_SCK  -> CC1101 SCK + OLED SCLK\n"
     "IO23 SPI_MOSI -> CC1101 MOSI + OLED SDIN\n"
     "IO19 SPI_MISO <- CC1101 MISO\n"
     "IO5  CC_CS    -> CC1101 CSn\n"
     "IO34 CC_GDO0  <- CC1101 GDO0 (OOK data)\n"
     "IO35 CC_GDO2  <- CC1101 GDO2 (carrier sense)\n"
     "IO15 / IO27 / IO26 -> OLED CS / DC / RES\n"
     "IO25 / IO33 / IO32 / IO14 -> LED FL/FR/RL/RR\n"
     + ("IO16 / IO17 <- encoder A / B (PCNT)   IO4 <- push\n" if ENCODER else
        "IO4 / IO16 / IO17 / IO39 <- UP/OK/DOWN/BACK\n") +
     "IO13 -> buzzer   IO36 <- MX-05V data\n"
     "IO21 / IO22 I2C SDA / SCL   IO2" + (" + IO39 (input/ADC)" if ENCODER else "") + " spare\n"
     "Use a WROOM-32 DevKit (on WROVER, IO16/IO17 are taken by PSRAM)"),
    (25.4, 213.36, 1.27,
     "NOTES\n"
     "1. CC1101 and OLED are 3.3 V parts: never drive them with 5 V logic.\n"
     "2. Target sensor: GM / Schrader EG53MA4 (FCC MRXEG53MA4): 315 MHz OOK,\n"
     "   Manchester, ~123 us chips. Run the CC1101 in async serial mode, data on GDO0.\n"
     "3. U3: 7805-pinout switcher rated >= 36 V in (TSR 1-2450, K7805-1000R3). Not R-78E (28 V max).\n"
     "4. JP1 open by default. Close only after re-jumpering the NHD module to\n"
     "   option #1 (R4 open, R5 closed) so its OLED boost runs from 5 V.\n"
     "5. J3, R9, R10 (MX-05V superregen receiver) optional: DNP with the CC1101.\n"
     "6. J2 = 1x8 breakout of the CC1101 bus for modules with another pinout."),
]
