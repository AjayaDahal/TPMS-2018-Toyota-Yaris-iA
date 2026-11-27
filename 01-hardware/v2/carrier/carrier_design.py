"""TPMS v2 carrier PCB, rev A: circuit, parts and JLCPCB part numbers.

100 x 100 mm, 2 layers. JLCPCB Economic PCBA places every SMD part; you hand-solder the sockets, the screw
terminals and the fan header (`hand=True`). Every pin is listed explicitly: a net name, or None for an
intentional no-connect. Reference designators are numbered by block:

    1xx  12 V input, protection, 12 V current monitor     5xx  inputs: blinkers, AUX, button, ACC sense
    2xx  5V_PI buck (Pi + display), Pi power control       6xx  outputs: door LEDs, buzzer, fan
    3xx  5V_ESP buck, 3.3 V LDO                            7xx  CC1101 radio
    4xx  ESP32 DevKit and its SPI / I2C series resistors   8xx  I2C peripherals (temperature, I/O expander)
    9xx  Pi link and GPS connectors

The ESP32 pin map must match 02-firmware/v2/include/pins_v2.h (01-hardware/v2/check_pinmap.py checks it).
Edit this file (circuit) or carrier_layout.py (placement) and re-run build_carrier.py with KiCad's Python.
"""

PROJECT = "tpms_v2_carrier"
TITLE = "TPMS v2 carrier (ESP32 + CC1101 + Pi power)"
REV = "A"
POWER_NETS = ("GND",)          # drawn with power symbols; every other net gets global labels

# ------------------------------------------------------------------ footprints
R0603 = "Resistor_SMD:R_0603_1608Metric"
R0805 = "Resistor_SMD:R_0805_2012Metric"
R1206 = "Resistor_SMD:R_1206_3216Metric"
R2512 = "Resistor_SMD:R_2512_6332Metric"
C0603 = "Capacitor_SMD:C_0603_1608Metric"
C0805 = "Capacitor_SMD:C_0805_2012Metric"
C1206 = "Capacitor_SMD:C_1206_3216Metric"
CPE63 = "Capacitor_SMD:CP_Elec_6.3x7.7"
LED0603 = "LED_SMD:LED_0603_1608Metric"
LED0805 = "LED_SMD:LED_0805_2012Metric"
SOD123 = "Diode_SMD:D_SOD-123"
SMA = "Diode_SMD:D_SMA"
SMB = "Diode_SMD:D_SMB"
SMC = "Diode_SMD:D_SMC"
SOT23 = "Package_TO_SOT_SMD:SOT-23"
TO252 = "Package_TO_SOT_SMD:TO-252-2"
PPAD8 = "Package_SO:TI_SO-PowerPAD-8"
MSOP10 = "Package_SO:TSSOP-10_3x3mm_P0.5mm"      # INA226 DGS (VSSOP-10): TI land pattern 0.30 mm pads, 0.2 mm gaps
SOIC8 = "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm"
TSSOP16 = "Package_SO:TSSOP-16_4.4x5mm_P0.65mm"
MWSA = "Inductor_SMD:L_Sunlord_MWSA1004S"
FB0603 = "Inductor_SMD:L_0603_1608Metric"
NANO2 = "Fuse:Fuse_Littelfuse-NANO2-451_453"
F1812 = "Fuse:Fuse_1812_4532Metric"
GH4 = "Connector_JST:JST_GH_SM04B-GHS-TB_1x04-1MP_P1.25mm_Horizontal"
GH6 = "Connector_JST:JST_GH_SM06B-GHS-TB_1x06-1MP_P1.25mm_Horizontal"
MKDS4 = "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-4-5.08_1x04_P5.08mm_Horizontal"
MKDS6 = "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-6-5.08_1x06_P5.08mm_Horizontal"
HDR1x2RA = "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Horizontal"
HDR1x4 = "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical"
HDR1x6 = "Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical"
HDR2x2 = "Connector_PinHeader_2.54mm:PinHeader_2x02_P2.54mm_Vertical"
HDR2x5 = "Connector_PinHeader_2.54mm:PinHeader_2x05_P2.54mm_Vertical"
HDR1x8 = "Connector_PinHeader_2.54mm:PinHeader_1x08_P2.54mm_Vertical"
TP_RAIL = "TestPoint:TestPoint_Pad_D1.5mm"
TP_SIG = "TestPoint:TestPoint_Pad_D1.0mm"
TP_GND = "TestPoint:TestPoint_THTPad_D2.0mm_Drill1.0mm"
MHOLE = "MountingHole:MountingHole_3.2mm_M3_Pad_Via"
FP_DEVKIT = "TPMS2:ESP32_DevKit_30pin_Sockets"
FP_CC1101 = "TPMS2:CC1101_2x4_Socket"
FP_LTV357 = "TPMS2:SOP-4_LTV-357T_P2.54mm_Rows6.5mm"

# ------------------------------------------------------------------ JLCPCB / LCSC part numbers
# Basic and Preferred Extended parts cost no loading fee on Economic PCBA; Extended parts cost ~$3 per part number
# (feeder loading), once per order whatever the quantity.
LCSC = {
    (R0603, "0"): "C21189", (R0603, "10"): "C22859", (R0603, "33"): "C23140", (R0603, "100"): "C22775",
    (R0603, "330"): "C23138", (R0603, "1k"): "C21190", (R0603, "4.7k"): "C23162", (R0603, "10k"): "C25804",
    (R0603, "15k"): "C22809", (R0603, "18k"): "C25810", (R0603, "22k"): "C31850", (R0603, "33k"): "C4216",
    (R0603, "47k"): "C25819", (R0603, "82k"): "C23254", (R0603, "100k"): "C25803", (R0603, "150k"): "C22807",
    (R0603, "200k"): "C25811", (R0603, "220k"): "C22961", (R0603, "1M"): "C22935",
    (R0805, "470"): "C17710", (R0805, "1.2k"): "C17379", (R0805, "10k"): "C17414",
    (R1206, "0"): "C17888", (R2512, "10m"): "C192580",
    (C0603, "100n"): "C14663", (C0603, "1u"): "C15849", (C0603, "10n"): "C57112", (C0603, "4.7n"): "C53987",
    (C0603, "47p"): "C1671", (C0603, "1n"): "C1588", (C0603, "10u"): "C96446",
    (C0805, "10u"): "C15850", (C1206, "10u/50V"): "C13585", (C1206, "47u/10V"): "C96123",
    (CPE63, "47u/50V"): "C970679",
    (LED0805, "green"): "C2297", (LED0805, "yellow"): "C2296", (LED0603, "red"): "C2286",
    (SOD123, "1N4148W"): "C81598", (SMA, "SS14"): "C2480", (SMC, "SS56C"): "C18199187", (SMC, "SMCJ24CA"): "C41411747",
    (SMB, "SMBJ6.0CA"): "C2925451",
    (SOT23, "AO3400A"): "C20917", (SOT23, "2N7002"): "C8545", (TO252, "SUD50P06-15"): "C7503186",
    (PPAD8, "TPS54560B"): "C1850354", (MSOP10, "INA226"): "C49851", (SOIC8, "TMP75"): "C30389",
    (TSSOP16, "TCA9534"): "C783615", (SOT23, "XC6206P332MR"): "C5446", (FP_LTV357, "ICPL-356-50C"): "C42432283",
    (MWSA, "6.8uH"): "C408485", (FB0603, "600R@100MHz"): "C1002",
    (NANO2, "4A"): "C27515", (F1812, "0.5A/60V"): "C70113",
    (GH4, "GH-4"): "C189895", (GH6, "GH-6"): "C133065",
}
PREFERRED = {"C41411747", "C18199187", "C2925451", "C42432283"}          # $0 feeder fee on Economic PCBA
EXTENDED = {"C1850354", "C49851", "C30389", "C783615", "C189895", "C133065"}  # only the 6 fine-pitch / PowerPAD / GH lines
MPN = {
    "C1850354": "TI TPS54560BDDAR", "C49851": "TI INA226AIDGSR", "C30389": "TI TMP75AIDR",
    "C783615": "TI TCA9534PWR", "C5446": "Torex XC6206P332MR-G", "C42432283": "ICPL-356-50CEAXW",
    "C408485": "Sunlord MWSA1004S-6R8MT", "C18199187": "SS56C", "C41411747": "SMCJ24CA",
    "C2925451": "SMBJ6.0CA", "C7503186": "UMW SUD50P06-15", "C27515": "Littelfuse 0451004.MRL",
    "C70113": "Littelfuse mSMD050-60V", "C970679": "Lelon RVT1H470M0607", "C192580": "Viking RLM25FEER010",
    "C189895": "JST SM04B-GHS-TB(LF)(SN)", "C133065": "JST SM06B-GHS-TB(LF)(SN)", "C20917": "AOS AO3400A",
    "C8545": "2N7002", "C2480": "SS14", "C81598": "1N4148W", "C1002": "Sunlord GZ1608D601TF",
}
# Hand-soldered parts: 5 THT connectors + 10 large 2/3-pad SMD power parts (6 extended lines). Keeping these 6 lines
# off JLCPCB Economic PCBA trims ~$24 off the merchandise total (~$76 -> ~$52), staying under JLCPCB's $59.00
# Global Standard Direct Line cutoff (avoiding ~$91 in forced UPS Express DDP shipping + duties).
HAND = {
    "J1": "4-pos 5.08 mm screw terminal, horizontal entry (Phoenix MKDS 1,5/4-5,08, KF301-4P, or 2x KF301-2P "
          "side by side: 5.0 or 5.08 mm pitch both fit)",
    "J5": "6-pos 5.08 mm screw terminal, horizontal entry (Phoenix MKDS 1,5/6-5,08, 2x KF301-3P or 3x KF301-2P)",
    "A1": "2x 1x15 2.54 mm female header, 8.5 mm (solder the row that matches your DevKit: 0.9 or 1.0 in)",
    "A2": "2x4 2.54 mm female header, 8.5 mm (CC1101 module socket)",
    "J8": "1x2 2.54 mm right-angle male header (fan lead)",
    "C104": "47u/50V electrolytic, 6.3x7.7 SMD (LCSC C970679, Lelon RVT1H470M0607) or leaded 47u/50V from lab bin",
    "F101": "4A 2410 NANO2 fast SMD fuse (LCSC C27515, Littelfuse 0451004.MRL)",
    "F601": "0.5A/60V 1812 PTC polyfuse (LCSC C70113, Littelfuse mSMD050-60V)",
    "F901": "0.5A/60V 1812 PTC polyfuse (LCSC C70113, Littelfuse mSMD050-60V)",
    "L101": "6.8uH 11x10 mm shielded inductor, >= 8.5A (LCSC C408485, Sunlord MWSA1004S-6R8MT / Bourns SRP1038A-6R8M)",
    "L201": "6.8uH 11x10 mm shielded inductor, >= 8.5A (LCSC C408485, Sunlord MWSA1004S-6R8MT / Bourns SRP1038A-6R8M)",
    "L301": "6.8uH 11x10 mm shielded inductor, >= 8.5A (LCSC C408485, Sunlord MWSA1004S-6R8MT / Bourns SRP1038A-6R8M)",
    "Q101": "-60V P-MOSFET TO-252 DPAK, <=25 mOhm (LCSC C7503186, UMW SUD50P06-15 / Vishay SUD50P06-15-GE3 or SQD50P06-15L_GE3)",
    "R104": "10 mOhm 1% 2W 2512 current shunt (LCSC C192580, Viking RLM25FEER010 / Stackpole CSR2512FK10L0)",
    "R211": "10 mOhm 1% 2W 2512 current shunt (LCSC C192580, Viking RLM25FEER010 / Stackpole CSR2512FK10L0)",
}

PARTS = []


def part(ref, sym, value, fp, pins, dnp=False, hand=False, desc="", block="", mpn=""):
    lcsc = "" if hand else LCSC.get((fp, value), "")
    if not lcsc and not hand and not ref.startswith(("TP", "H")) and not dnp:
        raise ValueError(f"{ref}: no LCSC part for {fp} / {value}")
    PARTS.append(dict(ref=ref, sym=sym, value=value, footprint=fp, pins=pins, dnp=dnp, hand=hand, desc=desc,
                      block=block, lcsc=lcsc, mpn=mpn or MPN.get(lcsc, HAND.get(ref, ""))))


def two(a, b):
    return {"1": a, "2": b}


def R(ref, value, a, b, fp=R0603, dnp=False, hand=False, desc=""):
    part(ref, "Device:R", value, fp, two(a, b), dnp=dnp, hand=hand, desc=desc)


def C(ref, value, a, b, fp=C0603, dnp=False, desc=""):
    part(ref, "Device:C", value, fp, two(a, b), dnp=dnp, desc=desc)


def D(ref, value, k, a, fp=SOD123, sym="Device:D", desc=""):
    part(ref, sym, value, fp, {"1": k, "2": a}, desc=desc)


def LED(ref, colour, k, a, fp=LED0805, desc=""):
    part(ref, "Device:LED", colour, fp, {"1": k, "2": a}, desc=desc)


def NFET(ref, value, g, s, d, desc=""):
    part(ref, "Transistor_FET:Q_NMOS_GSD", value, SOT23, {"1": g, "2": s, "3": d}, desc=desc)


def TP(ref, net, fp=TP_SIG):
    part(ref, "Connector:TestPoint", net, fp, {"1": net}, desc="test pad")


# ================================================================== 1xx: 12 V input, protection, monitor
part("J1", "Connector_Generic:Conn_01x04", "12V_IN", MKDS4,
     {"1": "VIN_RAW", "2": "GND", "3": "AUX_IN", "4": "AUX_RET"}, hand=True,
     desc="12 V ACC in (1), GND (2), spare 12 V sense input (3) and its return (4)")
part("F101", "Device:Fuse", "4A", NANO2, two("VIN_RAW", "VIN_FUSED"), hand=True, desc="NANO2 4 A fast fuse")
part("D101", "Device:D_TVS", "SMCJ24CA", SMC, two("VIN_FUSED", "GND"),
     desc="Bidirectional TVS: 26.7 V min breakdown (24 V jump start), 38.9 V clamp, reverse battery safe")
part("Q101", "Transistor_FET:Q_PMOS_GDS", "SUD50P06-15", TO252, {"1": "Q101_G", "2": "VIN_FUSED", "3": "12V_RP"},
     hand=True, desc="Reverse-battery P-MOSFET, -60 V, 12 mOhm")
R("R101", "33k", "12V_RP", "Q101_G", desc="Q101 gate: Vgs = -5 V at 12 V, -16 V at 39 V")
R("R102", "47k", "Q101_G", "GND")
C("C101", "10u/50V", "12V_RP", "GND", fp=C1206)
part("L101", "Device:L", "6.8uH", MWSA, two("12V_RP", "12V_PROT"), hand=True, desc="Input pi filter")
C("C102", "10u/50V", "12V_PROT", "GND", fp=C1206)
C("C103", "10u/50V", "12V_PROT", "GND", fp=C1206)
part("C104", "Device:C_Polarized", "47u/50V", CPE63, two("12V_PROT", "GND"), hand=True,
     desc="Electrolytic: damps the pi filter and the input cable")
C("C105", "100n", "12V_PROT", "GND")
R("R104", "10m", "12V_PROT", "12V_BUS", fp=R2512, hand=True, desc="12 V current shunt; remove to isolate both bucks")
R("R105", "10", "12V_PROT", "INA1_P")
R("R106", "10", "12V_BUS", "INA1_N")
C("C106", "100n", "INA1_P", "INA1_N")
part("U101", "TPMS2:INA226", "INA226", MSOP10,
     {"1": "GND", "2": "GND", "3": None, "4": "I2C_SDA", "5": "I2C_SCL", "6": "3V3", "7": "GND", "8": "12V_PROT",
      "9": "INA1_N", "10": "INA1_P"}, desc="12 V input current / voltage, I2C 0x40 (VBUS on the shunt's input side)")
C("C107", "100n", "3V3", "GND")
R("R107", "10k", "12V_PROT", "LED12_A", fp=R0805)
LED("D102", "green", "GND", "LED12_A", desc="12V_PROT present")

# ================================================================== 2xx: 5V_PI buck and Pi power control
R("R201", "0", "12V_BUS", "12V_PIB", fp=R1206, desc="Pi buck input link (2 in parallel); remove both to isolate")
R("R202", "0", "12V_BUS", "12V_PIB", fp=R1206)
C("C201", "10u/50V", "12V_PIB", "GND", fp=C1206)
C("C202", "10u/50V", "12V_PIB", "GND", fp=C1206)
C("C203", "100n", "GND", "12V_PIB")
C("C204", "10u/50V", "12V_PIB", "GND", fp=C1206, dnp=True, desc="DNP: spare input capacitor")
part("U201", "TPMS2:TPS54560B", "TPS54560B", PPAD8,
     {"1": "BOOT_PI", "2": "12V_PIB", "3": "EN_PI", "4": "RT_PI", "5": "FB_PI", "6": "COMP_PI", "7": "GND",
      "8": "SW_PI", "9": "GND"}, desc="60 V 5 A buck, 441 kHz, 5.17 V out")
C("C205", "100n", "BOOT_PI", "SW_PI")
D("D201", "SS56C", "SW_PI", "GND", fp=SMC, sym="Device:D_Schottky", desc="Catch diode 60 V 5 A (Preferred)")
part("L201", "Device:L", "6.8uH", MWSA, two("SW_PI", "5V_PI_RAW"), hand=True)
for i in range(4):
    C(f"C{206 + i}", "47u/10V", "5V_PI_RAW", "GND", fp=C1206)
C("C210", "47u/10V", "5V_PI_RAW", "GND", fp=C1206, dnp=True, desc="DNP: spare output capacitor")
R("R203", "82k", "5V_PI_RAW", "FB_PI", desc="Vout = 0.8 V x (1 + 82k/15k) = 5.17 V")
R("R204", "15k", "FB_PI", "GND")
R("R205", "18k", "COMP_PI", "COMPR_PI", desc="Compensation: crossover ~33 kHz")
C("C211", "4.7n", "COMPR_PI", "GND")
C("C212", "47p", "COMP_PI", "GND")
R("R206", "220k", "RT_PI", "GND", desc="RT: 441 kHz")
R("R207", "1M", "12V_PIB", "EN_PI", desc="UVLO: start 8.0 V, stop 4.6 V")
R("R208", "150k", "EN_PI", "GND")
C("C213", "10u", "EN_PI", "GND", fp=C0805, desc="Start delay 1.2-1.4 s after ACC: the ESP32 boots first")
D("D202", "1N4148W", "12V_PIB", "EN_PI", desc="Empties C213 when 12 V drops")
NFET("Q201", "2N7002", "INH_G", "GND", "EN_PI", desc="PI_INHIBIT: high holds the Pi buck off")
R("R209", "100", "ESP_IO26", "INH_G")
R("R210", "100k", "INH_G", "GND", desc="Pi rail on while the ESP32 is in reset")
R("R211", "10m", "5V_PI_RAW", "5V_PI", fp=R2512, hand=True, desc="5V_PI current shunt; remove to isolate the Pi rail")
R("R212", "10", "5V_PI_RAW", "INA2_P")
R("R213", "10", "5V_PI", "INA2_N")
C("C214", "100n", "INA2_P", "INA2_N")
part("U202", "TPMS2:INA226", "INA226", MSOP10,
     {"1": "GND", "2": "3V3", "3": None, "4": "I2C_SDA", "5": "I2C_SCL", "6": "3V3", "7": "GND", "8": "5V_PI",
      "9": "INA2_N", "10": "INA2_P"}, desc="5V_PI current / voltage, I2C 0x41")
C("C215", "100n", "3V3", "GND")
D("D203", "SMBJ6.0CA", "5V_PI", "GND", fp=SMB, sym="Device:D_TVS",
  desc="Overvoltage clamp (Preferred): a shorted buck blows F101 instead of the Pi")
R("R214", "22k", "5V_PI", "PI_PGOOD", desc="Rail-up sense to GPIO15: 3.1 V when 5V_PI is up")
R("R215", "33k", "PI_PGOOD", "GND")
R("R216", "1k", "5V_PI", "LEDPI_A")
LED("D204", "green", "GND", "LEDPI_A", desc="5V_PI present")
part("J5", "Connector_Generic:Conn_01x06", "5V_OUT", MKDS6,
     {"1": "5V_PI", "2": "GND", "3": "5V_PI", "4": "GND", "5": "5V_PI", "6": "GND"}, hand=True,
     desc="5V_PI out: 1-2 Pi USB-C pigtail, 3-4 display split lead, 5-6 spare")
part("J11", "Connector_Generic:Conn_02x02_Odd_Even", "EXT_12V", HDR2x2,
     {"1": "12V_BUS", "2": "12V_BUS", "3": "GND", "4": "GND"}, dnp=True,
     desc="DNP: 12 V (protected, after the shunt) for an external 5 V module. Pi rail fallback: module out to J5 "
          "5-6, remove R201/R202")

# ================================================================== 3xx: 5V_ESP buck, 3.3 V
R("R301", "0", "12V_BUS", "12V_ESPB", fp=R1206, desc="ESP buck input link; remove to isolate")
C("C301", "10u/50V", "12V_ESPB", "GND", fp=C1206)
C("C302", "10u/50V", "12V_ESPB", "GND", fp=C1206)
C("C303", "100n", "GND", "12V_ESPB")
C("C304", "10u/50V", "12V_ESPB", "GND", fp=C1206, dnp=True, desc="DNP: spare input capacitor")
part("U301", "TPMS2:TPS54560B", "TPS54560B", PPAD8,
     {"1": "BOOT_ESP", "2": "12V_ESPB", "3": "EN_ESP", "4": "RT_ESP", "5": "FB_ESP", "6": "COMP_ESP", "7": "GND",
      "8": "SW_ESP", "9": "GND"}, desc="60 V 5 A buck, 485 kHz, 5.17 V out")
C("C305", "100n", "BOOT_ESP", "SW_ESP")
D("D301", "SS56C", "SW_ESP", "GND", fp=SMC, sym="Device:D_Schottky")
part("L301", "Device:L", "6.8uH", MWSA, two("SW_ESP", "5V_ESP_RAW"), hand=True)
for i in range(4):
    C(f"C{306 + i}", "47u/10V", "5V_ESP_RAW", "GND", fp=C1206)
C("C310", "47u/10V", "5V_ESP_RAW", "GND", fp=C1206, dnp=True, desc="DNP: spare output capacitor")
R("R303", "82k", "5V_ESP_RAW", "FB_ESP")
R("R304", "15k", "FB_ESP", "GND")
R("R305", "18k", "COMP_ESP", "COMPR_ESP")
C("C311", "4.7n", "COMPR_ESP", "GND")
C("C312", "47p", "COMP_ESP", "GND")
R("R306", "200k", "RT_ESP", "GND", desc="RT: 485 kHz (beats with the Pi buck above the audio band)")
R("R307", "1M", "12V_ESPB", "EN_ESP")
R("R308", "150k", "EN_ESP", "GND")
C("C313", "1n", "EN_ESP", "GND")
R("R309", "0", "5V_ESP_RAW", "5V_ESP", fp=R1206, desc="5V_ESP link; remove to isolate")
D("D302", "SMBJ6.0CA", "5V_ESP", "GND", fp=SMB, sym="Device:D_TVS")
R("R310", "1k", "5V_ESP", "LEDESP_A")
LED("D303", "yellow", "GND", "LEDESP_A", desc="5V_ESP present")
D("D304", "SS14", "DEVKIT_VIN", "5V_ESP", fp=SMA, sym="Device:D_Schottky",
  desc="No back-feed between the DevKit's USB and 5V_ESP")
C("C314", "10u", "DEVKIT_VIN", "GND", fp=C0805)
part("U302", "TPMS2:XC6206", "XC6206P332MR", SOT23, {"1": "GND", "2": "3V3_LDO", "3": "5V_ESP"},
     desc="3.3 V 200 mA LDO: CC1101, I2C parts, pull-ups")
C("C315", "1u", "5V_ESP", "GND")
C("C316", "1u", "3V3_LDO", "GND")
R("R311", "0", "3V3_LDO", "3V3", desc="3V3 link; swap to R312 to run 3V3 from the DevKit")
C("C317", "10u", "3V3", "GND")
R("R312", "0", "DEVKIT_3V3", "3V3", dnp=True, desc="DNP: 3V3 from the DevKit's own regulator")
R("R313", "1k", "3V3", "LED3V3_A")
LED("D305", "red", "GND", "LED3V3_A", fp=LED0603, desc="3V3 present")
part("J12", "Connector_Generic:Conn_02x02_Odd_Even", "EXT_5V_ESP", HDR2x2,
     {"1": "5V_ESP_RAW", "2": "5V_ESP_RAW", "3": "GND", "4": "GND"}, dnp=True,
     desc="DNP: ESP rail fallback, an external 5 V module's output (its input from J11); remove R301")

# ================================================================== 4xx: ESP32 DevKit
part("A1", "TPMS2:ESP32_DevKit_30pin", "ESP32_DevKit_30pin", FP_DEVKIT,
     {"1": None, "2": "ESP_IO36", "3": "ESP_IO39", "4": "ESP_IO34", "5": "ESP_IO35", "6": "ESP_IO32",
      "7": "ESP_IO33", "8": "ESP_IO25", "9": "ESP_IO26", "10": "ESP_IO27", "11": "ESP_IO14", "12": None,
      "13": "ESP_IO13", "14": "GND", "15": "DEVKIT_VIN", "16": "ESP_IO23", "17": "ESP_IO22", "18": None,
      "19": None, "20": "ESP_IO21", "21": "ESP_IO19", "22": "ESP_IO18", "23": "ESP_IO5", "24": "ESP_IO17",
      "25": "ESP_IO16", "26": "ESP_IO4", "27": None, "28": "PI_PGOOD", "29": "GND", "30": "DEVKIT_3V3"},
     hand=True, desc="ESP32 DevKit (30-pin) on two 1x15 sockets. Open: EN, TX0/RX0 (USB), IO2 (its LED), "
                     "IO12 (strapping pin)")
# SPI outputs get 1 k: at 4 MHz the edges stay < 20 ns, and a DevKit on USB with the carrier unpowered can't
# push more than ~3 mA per line into the CC1101's clamp diodes. I2C is open drain: 33 R is enough.
R("R401", "1k", "ESP_IO23", "SPI_MOSI")
R("R402", "1k", "ESP_IO18", "SPI_SCK")
R("R403", "1k", "ESP_IO5", "CC_CSN")
R("R404", "33", "ESP_IO22", "I2C_SCL")
R("R405", "33", "ESP_IO21", "I2C_SDA")

# ================================================================== 5xx: inputs
# Turn-signal and AUX inputs: 12 V through 2.4 k, an indicator LED and the opto's LED (~4 mA at 12.6 V,
# ~15 mA at a 40 V load dump); 1N4148W across both LEDs against reverse voltage. The return pin is separate
# (twisted pair to a ground near the lamp); a DNP 0 R ties it to board GND.
for side, n, gpio, base in (("L", 0, "ESP_IO36", 501), ("R", 1, "ESP_IO39", 506)):
    p = f"BLK{side}_"
    R(f"R{base}", "1.2k", p + "IN", p + "1", fp=R0805)
    R(f"R{base + 1}", "1.2k", p + "1", p + "2", fp=R0805)
    LED(f"D{501 + 2 * n}", "yellow", p + "3", p + "2", desc=f"{side} blinker lamp lit")
    part(f"U{501 + n}", "TPMS2:LTV-357T", "ICPL-356-50C", FP_LTV357,
         {"1": p + "3", "2": p + "RET", "3": "GND", "4": f"BLINK_{side}_OC"}, desc="Optocoupler, CTR 200-400 % (Preferred)")
    D(f"D{502 + 2 * n}", "1N4148W", p + "2", p + "RET")
    R(f"R{base + 2}", "10k", "3V3", f"BLINK_{side}_OC")
    C(f"C{501 + n}", "10n", f"BLINK_{side}_OC", "GND")
    R(f"R{base + 3}", "1k", f"BLINK_{side}_OC", gpio)
    R(f"R{base + 4}", "0", p + "RET", "GND", dnp=True, desc="DNP: tie the lamp return to board GND")
R("R511", "1.2k", "AUX_IN", "AUX_1", fp=R0805)
R("R512", "1.2k", "AUX_1", "AUX_2", fp=R0805)
LED("D505", "green", "AUX_3", "AUX_2", desc="AUX input lit")
part("U503", "TPMS2:LTV-357T", "ICPL-356-50C", FP_LTV357,
     {"1": "AUX_3", "2": "AUX_RET", "3": "GND", "4": "AUX_OPTO"})
D("D506", "1N4148W", "AUX_2", "AUX_RET")
R("R513", "10k", "3V3", "AUX_OPTO")
C("C503", "10n", "AUX_OPTO", "GND")
R("R514", "1k", "AUX_OPTO", "EXP_P0")
R("R515", "0", "AUX_RET", "GND", desc="AUX return tied to GND at J1; remove for an isolated input")
R("R516", "10k", "3V3", "POD_BTN", desc="J4 spare button input (IO4): v1 RC filter")
C("C504", "100n", "POD_BTN", "GND")
R("R517", "1k", "POD_BTN", "ESP_IO4")
R("R518", "100k", "12V_PROT", "ACC_DIV", desc="ACC sense: 12V_PROT / 11 to ADC1")
R("R519", "10k", "ACC_DIV", "GND")
C("C505", "100n", "ACC_DIV", "GND")
D("D507", "1N4148W", "3V3", "ACC_DIV", desc="Clamp to 3V3")
R("R520", "1k", "ACC_DIV", "ESP_IO32")

# ================================================================== 6xx: outputs
part("J2", "Connector_Generic_MountingPin:Conn_01x04_MountingPin", "GH-4", GH4,
     {"1": "BLKL_IN", "2": "BLKL_RET", "3": "LEDL_A", "4": "LEDL_K", "MP": "GND"},
     desc="DOOR_L: blinker sense pair (1-2), amber LED (3 +, 4 -)")
part("J3", "Connector_Generic_MountingPin:Conn_01x04_MountingPin", "GH-4", GH4,
     {"1": "BLKR_IN", "2": "BLKR_RET", "3": "LEDR_A", "4": "LEDR_K", "MP": "GND"},
     desc="DOOR_R: blinker sense pair (1-2), amber LED (3 +, 4 -)")
part("J4", "Connector_Generic_MountingPin:Conn_01x04_MountingPin", "GH-4", GH4,
     {"1": "POD_BTN", "2": "GND", "3": "POD_BUZP", "4": "POD_BUZN", "MP": "GND"},
     desc="BUZ: 12 V piezo (3 +, 4 -); 1-2 spare button input (IO4)")
for side, n, gpio in (("L", 0, "ESP_IO25"), ("R", 1, "ESP_IO14")):
    b = 601 + 4 * n
    NFET(f"Q{601 + n}", "AO3400A", f"LED{side}_G", "GND", f"LED{side}_K", desc=f"{side} door LED, low side, PWM")
    R(f"R{b}", "100", gpio, f"LED{side}_G")
    R(f"R{b + 1}", "100k", f"LED{side}_G", "GND")
    R(f"R{b + 2}", "470", "5V_ESP", f"LED{side}_A", fp=R0805, desc="2 x 470 R in parallel: 13 mA, short-proof")
    R(f"R{b + 3}", "470", "5V_ESP", f"LED{side}_A", fp=R0805)
NFET("Q603", "2N7002", "BUZ_G", "GND", "POD_BUZN", desc="Piezo, low side (60 V for load dump)")
R("R609", "100", "ESP_IO13", "BUZ_G")
R("R610", "100k", "BUZ_G", "GND")
part("F601", "Device:Polyfuse", "0.5A/60V", F1812, two("12V_BUS", "POD_BUZP"), hand=True,
     desc="Piezo feed PTC, after the 12 V shunt: the INA226 at 0x40 sees a shorted piezo lead")
D("D601", "1N4148W", "POD_BUZP", "POD_BUZN")
NFET("Q604", "AO3400A", "FAN_G", "GND", "FAN_N", desc="Lid fan, on by default")
R("R611", "10k", "3V3", "FAN_G", desc="Fan on while the expander pin is an input (power-up default)")
R("R612", "1k", "EXP_P1", "FAN_G")
D("D602", "1N4148W", "5V_ESP", "FAN_N")
part("J8", "Connector_Generic:Conn_01x02", "FAN", HDR1x2RA, two("5V_ESP", "FAN_N"), hand=True,
     desc="30 mm lid fan (1 = +5 V, 2 = switched -)")

# ================================================================== 7xx: CC1101 radio
part("A2", "TPMS2:CC1101_Module", "CC1101_315MHz", FP_CC1101,
     {"1": "GND", "2": "3V3_RF", "3": "CC_GDO0", "4": "CC_CSN", "5": "SPI_SCK", "6": "SPI_MOSI", "7": "CC_MISO",
      "8": "CC_GDO2"}, hand=True, desc="CC1101 module (2x4 E07 / V2.0 pinout) on a socket")
part("FB701", "Device:FerriteBead", "600R@100MHz", FB0603, two("3V3", "3V3_RF"))
C("C701", "10u", "3V3_RF", "GND")
C("C702", "100n", "3V3_RF", "GND")
R("R701", "33", "CC_MISO", "ESP_IO19")
R("R702", "33", "CC_GDO0", "ESP_IO34")
R("R703", "33", "CC_GDO2", "ESP_IO35")
part("J10", "Connector_Generic:Conn_01x08", "CC1101_ALT", HDR1x8,
     {"1": "GND", "2": "3V3_RF", "3": "CC_GDO0", "4": "CC_CSN", "5": "SPI_SCK", "6": "SPI_MOSI", "7": "CC_MISO",
      "8": "CC_GDO2"}, dnp=True, desc="DNP: breakout for a module with another pinout (wire it here)")

# ================================================================== 8xx: I2C peripherals
R("R801", "4.7k", "3V3", "I2C_SDA")
R("R802", "4.7k", "3V3", "I2C_SCL")
part("U801", "TPMS2:TMP75", "TMP75", SOIC8,
     {"1": "I2C_SDA", "2": "I2C_SCL", "3": None, "4": "GND", "5": "GND", "6": "GND", "7": "GND", "8": "3V3"},
     desc="Board temperature, LM75 compatible, I2C 0x48")
C("C801", "100n", "3V3", "GND")
part("U802", "TPMS2:TCA9534", "TCA9534", TSSOP16,
     {"1": "GND", "2": "GND", "3": "GND", "4": "EXP_P0", "5": "EXP_P1", "6": "EXP_P2", "7": "EXP_P3", "8": "GND",
      "9": "EXP_P4", "10": "EXP_P5", "11": "EXP_P6", "12": "EXP_P7", "13": "EXP_INT", "14": "I2C_SCL",
      "15": "I2C_SDA", "16": "3V3"}, desc="I/O expander 0x20: P0 AUX in, P1 fan, P2 Pi I2C enable (input), "
                                           "P3-P7 spare")
C("C802", "100n", "3V3", "GND")
R("R803", "10k", "3V3", "EXP_INT")
part("J9", "Connector_Generic:Conn_02x05_Odd_Even", "EXPANSION", HDR2x5,
     {"1": "3V3", "2": "GND", "3": "EXP_P3", "4": "EXP_P4", "5": "EXP_P5", "6": "EXP_P6", "7": "EXP_P7",
      "8": "EXP_INT", "9": "I2C_SDA", "10": "I2C_SCL"}, dnp=True, desc="DNP: spare I/O and I2C")

# ================================================================== 9xx: Pi link, GPS
# J6 is the whole Pi <-> ESP32 link: UART (Pi UART0 <-> ESP32 UART2), and the Pi's I2C6 (GPIO22/23) switched onto
# the carrier's I2C bus by the Pi's own GPIO18 (PI_AUX_C, also read by the ESP32 on expander P2). Q901 / Q902 are
# the classic bidirectional level-shift switches: gate on GPIO18, source on the Pi side, and R911 / R912 are the
# Pi-side pull-ups, powered by GPIO18 too. With GPIO18 low, or the Pi off, halted or booting, the gates are at 0 V
# and the body diodes face the carrier bus: nothing on the Pi side can pull the ESP32's bus low. I2C6 rather than
# I2C1 keeps the Pi's fixed 1.8 k pull-ups off the bus and leaves GPIO3 (the Pi 4's wake-from-halt pin) alone, so
# the ESP32's polling can't wake a halted Pi. Remove Q901 / Q902 to take the Pi off the bus for good.
part("J6", "Connector_Generic_MountingPin:Conn_01x06_MountingPin", "GH-6", GH6,
     {"1": "GND", "2": "PI_TXD", "3": "PI_RXD", "4": "PI_AUX_C", "5": "PI_SDA", "6": "PI_SCL", "MP": "GND"},
     desc="PI: to the Pi's GPIO pins 6 (GND), 8 (TXD), 10 (RXD), 12 (GPIO18, I2C enable), 15 (GPIO22, SDA6), "
          "16 (GPIO23, SCL6)")
R("R901", "1k", "PI_TXD", "ESP_IO16")
R("R902", "4.7k", "ESP_IO17", "PI_RXD", desc="Limits back-powering the Pi's GPIO while it is off")
R("R903", "1k", "PI_AUX_C", "EXP_P2")
R("R904", "100k", "EXP_P2", "GND", desc="Holds the I2C-enable line (and Q901 / Q902) off while the Pi is off")
NFET("Q901", "2N7002", "PI_AUX_C", "PI_SDA", "I2C_SDA", desc="Pi SDA6 onto the I2C bus while the Pi drives GPIO18 high")
NFET("Q902", "2N7002", "PI_AUX_C", "PI_SCL", "I2C_SCL", desc="Pi SCL6 onto the I2C bus while the Pi drives GPIO18 high")
R("R911", "4.7k", "PI_AUX_C", "PI_SDA", desc="Pi-side SDA pull-up, powered only while GPIO18 is high")
R("R912", "4.7k", "PI_AUX_C", "PI_SCL", desc="Pi-side SCL pull-up, powered only while GPIO18 is high")
part("J7", "Connector_Generic_MountingPin:Conn_01x06_MountingPin", "GH-6", GH6,
     {"1": "GPS_5V", "2": "GPS_RXD_C", "3": "GPS_TXD_C", "4": "GPS_SCL", "5": "GPS_SDA", "6": "GND", "MP": "GND"},
     desc="GPS (Pixhawk port): 5V, TX (to GPS RX), RX (from GPS TX), SCL, SDA, GND")
part("F901", "Device:Polyfuse", "0.5A/60V", F1812, two("5V_ESP", "GPS_5V"), hand=True)
C("C901", "10u", "GPS_5V", "GND", fp=C0805)
R("R905", "1k", "ESP_IO27", "GPS_RXD_C", desc="GPS TX/RX normal (move R905/R906 to R907/R908 to swap); "
                                              "1 k also limits back-feed into an unpowered GPS")
R("R906", "1k", "GPS_TXD_C", "ESP_IO33")
R("R907", "1k", "ESP_IO27", "GPS_TXD_C", dnp=True, desc="DNP: swapped GPS TX/RX")
R("R908", "1k", "GPS_RXD_C", "ESP_IO33", dnp=True)
R("R909", "0", "I2C_SCL", "GPS_SCL", dnp=True, desc="DNP: GPS compass on the I2C bus")
R("R910", "0", "I2C_SDA", "GPS_SDA", dnp=True)

# Safety / modification headers (DNP 2.54 mm, $0 extra on JLCPCB): bench probing, rail bypass, or future mods
part("J13", "Connector_Generic:Conn_01x06", "SAFETY_PWR", HDR1x6,
     {"1": "GND", "2": "5V_ESP", "3": "5V_PI", "4": "3V3", "5": "EN_PI", "6": "EN_ESP"}, dnp=True,
     desc="DNP safety header: GND, 5V_ESP, 5V_PI (jumper 2-3 to feed ESP from Pi buck if U301 fails), 3V3, EN_PI, EN_ESP")
part("J14", "Connector_Generic:Conn_01x04", "SAFETY_PI", HDR1x4,
     {"1": "GND", "2": "PI_TXD", "3": "PI_RXD", "4": "PI_AUX_C"}, dnp=True,
     desc="DNP safety header: 2.54 mm Pi UART + I2C-enable bypass/debug tap (bypasses 1.25 mm J6)")

# ================================================================== test pads, mounting holes
TEST_PADS = (("12V_PROT", TP_RAIL), ("12V_BUS", TP_RAIL), ("5V_PI_RAW", TP_RAIL), ("5V_PI", TP_RAIL),
             ("5V_ESP", TP_RAIL), ("3V3", TP_RAIL), ("3V3_RF", TP_SIG), ("DEVKIT_VIN", TP_SIG), ("EN_PI", TP_SIG),
             ("EN_ESP", TP_SIG), ("ACC_DIV", TP_SIG), ("BLINK_L_OC", TP_SIG), ("BLINK_R_OC", TP_SIG),
             ("AUX_OPTO", TP_SIG), ("PI_TXD", TP_SIG), ("PI_RXD", TP_SIG), ("GPS_RXD_C", TP_SIG),
             ("GPS_TXD_C", TP_SIG), ("I2C_SDA", TP_SIG), ("I2C_SCL", TP_SIG), ("CC_GDO0", TP_SIG),
             ("CC_GDO2", TP_SIG), ("POD_BTN", TP_SIG))
for i, (net, fp) in enumerate(TEST_PADS, 1):
    TP(f"TP{i}", net, fp)
TP("TP24", "GND", TP_GND)
TP("TP25", "GND", TP_GND)
for i in range(1, 5):
    part(f"H{i}", "Mechanical:MountingHole_Pad", "M3", MHOLE, {"1": "GND"}, desc="M3 into the enclosure post")

# ================================================================== custom symbols (TPMS2 library)
# Each pin: (number, name, electrical type). None leaves an empty row.
CUSTOM_SYMBOLS = {
    "ESP32_DevKit_30pin": dict(
        ref="A", value="ESP32_DevKit_30pin", footprint=FP_DEVKIT, half_width=10.16,
        description="ESP32 DevKit (DOIT V1 style, 30 pins) on two 1x15 sockets",
        left=[("1", "EN", "input"), ("2", "IO36/VP", "input"), ("3", "IO39/VN", "input"), ("4", "IO34", "input"),
              ("5", "IO35", "input"), ("6", "IO32", "bidirectional"), ("7", "IO33", "bidirectional"),
              ("8", "IO25", "bidirectional"), ("9", "IO26", "bidirectional"), ("10", "IO27", "bidirectional"),
              ("11", "IO14", "bidirectional"), ("12", "IO12", "bidirectional"), ("13", "IO13", "bidirectional"),
              ("14", "GND", "power_in"), ("15", "VIN", "power_in")],
        right=[("16", "IO23", "bidirectional"), ("17", "IO22", "bidirectional"), ("18", "TX0/IO1", "bidirectional"),
               ("19", "RX0/IO3", "bidirectional"), ("20", "IO21", "bidirectional"), ("21", "IO19", "bidirectional"),
               ("22", "IO18", "bidirectional"), ("23", "IO5", "bidirectional"), ("24", "IO17", "bidirectional"),
               ("25", "IO16", "bidirectional"), ("26", "IO4", "bidirectional"), ("27", "IO2", "bidirectional"),
               ("28", "IO15", "bidirectional"), ("29", "GND", "power_in"), ("30", "3V3", "power_out")]),
    "CC1101_Module": dict(
        ref="A", value="CC1101_315MHz", footprint=FP_CC1101, half_width=7.62,
        description="CC1101 sub-GHz module, 2x4 2.54 mm header (E07-M1101D / V2.0 pinout), 3.3 V only",
        left=[("2", "VCC", "power_in"), None, None, None, None, ("1", "GND", "power_in")],
        right=[("4", "CSN", "input"), ("5", "SCK", "input"), ("6", "MOSI", "input"), ("7", "MISO/GDO1", "output"),
               ("3", "GDO0", "output"), ("8", "GDO2", "output")]),
    "TPS54560B": dict(
        ref="U", value="TPS54560B", footprint=PPAD8, half_width=7.62,
        description="TI TPS54560B 4.5-60 V 5 A step-down converter, Eco-mode, SO-8 PowerPAD",
        left=[("2", "VIN", "power_in"), ("3", "EN", "input"), ("4", "RT/CLK", "passive"), None,
              ("7", "GND", "power_in"), ("9", "EP", "power_in")],
        right=[("1", "BOOT", "passive"), ("8", "PH", "passive"), None, ("5", "FB", "input"), ("6", "COMP", "passive")]),
    "INA226": dict(
        ref="U", value="INA226", footprint=MSOP10, half_width=7.62,
        description="TI INA226 36 V bidirectional current / power monitor, I2C",
        left=[("6", "VS", "power_in"), ("10", "IN+", "input"), ("9", "IN-", "input"), ("8", "VBUS", "input"),
              ("7", "GND", "power_in")],
        right=[("4", "SDA", "bidirectional"), ("5", "SCL", "input"), ("3", "~{ALERT}", "open_collector"),
               ("2", "A0", "input"), ("1", "A1", "input")]),
    "TMP75": dict(
        ref="U", value="TMP75", footprint=SOIC8, half_width=7.62,
        description="TI TMP75 digital temperature sensor, LM75 compatible, I2C",
        left=[("8", "V+", "power_in"), ("7", "A0", "input"), ("6", "A1", "input"), ("5", "A2", "input"),
              ("4", "GND", "power_in")],
        right=[("1", "SDA", "bidirectional"), ("2", "SCL", "input"), ("3", "ALERT", "open_collector")]),
    "TCA9534": dict(
        ref="U", value="TCA9534", footprint=TSSOP16, half_width=7.62,
        description="TI TCA9534 8-bit I2C I/O expander",
        left=[("16", "VCC", "power_in"), ("15", "SDA", "bidirectional"), ("14", "SCL", "input"),
              ("13", "~{INT}", "open_collector"), ("1", "A0", "input"), ("2", "A1", "input"), ("3", "A2", "input"),
              ("8", "GND", "power_in")],
        right=[("4", "P0", "bidirectional"), ("5", "P1", "bidirectional"), ("6", "P2", "bidirectional"),
               ("7", "P3", "bidirectional"), ("9", "P4", "bidirectional"), ("10", "P5", "bidirectional"),
               ("11", "P6", "bidirectional"), ("12", "P7", "bidirectional")]),
    "XC6206": dict(
        ref="U", value="XC6206P332MR", footprint=SOT23, half_width=5.08,
        description="Torex XC6206 3.3 V 200 mA LDO, SOT-23 (1 VSS, 2 VOUT, 3 VIN)",
        left=[("3", "VIN", "power_in"), ("1", "GND", "power_in")],
        right=[("2", "VOUT", "power_out")]),
    "LTV-357T": dict(
        ref="U", value="LTV-357T", footprint=FP_LTV357, half_width=5.08,
        description="Lite-On LTV-357T phototransistor optocoupler, SOP-4 2.54 mm",
        left=[("1", "A", "passive"), ("2", "K", "passive")],
        right=[("4", "C", "passive"), ("3", "E", "passive")]),
}

# ESP32 DevKit pin -> function, checked against pins_v2.h by check_pinmap.py
DEVKIT_GPIO = {
    36: "BLINK_L", 39: "BLINK_R", 34: "CC_GDO0", 35: "CC_GDO2", 32: "ACC_SENSE", 33: "GPS_RX", 25: "LED_L",
    26: "PI_INHIBIT", 27: "GPS_TX", 14: "LED_R", 13: "BUZZER", 23: "SPI_MOSI", 22: "I2C_SCL", 21: "I2C_SDA",
    19: "SPI_MISO", 18: "SPI_SCK", 5: "CC_CS", 17: "PI_UART_TX", 16: "PI_UART_RX", 4: "BTN", 15: "PI_PGOOD",
}
