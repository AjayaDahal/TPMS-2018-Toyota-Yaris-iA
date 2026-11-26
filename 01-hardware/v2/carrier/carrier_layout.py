"""TPMS v2 carrier PCB, rev A: placement and mechanical constraints.

Coordinates are the fit-template frame used by 01-hardware/enclosure/make_enclosure.py: mm from the board's
top-left corner, parts side up, y down. Rotations are KiCad's (counter-clockwise, degrees). Every part is on the
top side. A placement is the footprint's origin (pad 1 for connectors and the custom socket footprints).

FIXED parts sit exactly where listed. SOFT parts (small passives, test pads) are listed at the spot they should be
near; build_carrier.py moves each to the nearest free spot (courtyards, keep-outs, board edge) and reports any
move over 3 mm. Test pads are listed by net (TP_AT); the builder maps them to their TP reference.

Enclosure constraints (enclosure_report.json, pcb_constraints):
  - parts <= 16 mm tall; fan zone (32 x 32 mm round the lid fan): parts <= 6 mm;
  - SMA strip on the right edge: no parts (the antenna bulkhead's body and nut);
  - 10 x 10 mm round each M3 hole: no through-hole pins (the posts' ribs are underneath);
  - through-hole pins trimmed to <= 2.5 mm under the board.
"""

BOARD_W = BOARD_H = 100.0
CORNER_R = 1.0
HOLES = [(4.0, 4.0), (96.0, 4.0), (4.0, 96.0), (96.0, 96.0)]
FAN_ZONE = (29.0, 30.0, 61.0, 62.0)               # x0, y0, x1, y1: parts <= 6 mm
SMA_STRIP = (86.0, 28.5, 100.0, 40.5)             # no parts
CORNER_KEEP = 10.0                                 # no THT pins within this square at each corner
MAX_H, FAN_MAX_H, COAX_MAX_H = 16.0, 6.0, 5.0
COAX_ZONE = (72.0, 14.0, 95.0, 41.0)              # the antenna pigtail loops here (to the bulkhead at y 34.5)
J5_BEND_STRIP = (54.0, 0.0, 88.0, 2.4)            # in front of J5's wire entries: no parts
LID_CABLE_EXIT = (19.0, 41.0)                     # x range of the lid's cable slot, below the bottom edge

# DevKit: pin 1 (EN) at DEVKIT_XY, left row down +y, right rows at +0.9 in and +1.0 in
DEVKIT_XY = (1.6, 22.0)
DEVKIT_ROWS = (22.86, 25.4)
DEVKIT_BOARD = (0.15, 14.38, 28.45, 65.18)        # outline of a 1.0 in DevKit, 11 mm above the board
# the WROOM's PCB antenna sits over this strip: no copper on any layer, no parts
ANTENNA_KEEPOUT = (0.2, 14.4, 28.4, 20.3)
CC1101_XY = (74.5, 82.0)                          # socket pin 1; the module rises toward -y, SMA on top
CC1101_BOARD = (70.8, 53.6, 85.8, 83.6)           # module outline, 11 mm above the board
CC1101_SMA = (75.1, 42.6, 81.5, 53.6)             # its SMA jack (7.8-14.7 mm above the board)

# approximate heights above the board (mm) of the tall parts, for the fan-zone and coax checks
HEIGHTS = {"J1": 10.0, "J5": 10.0, "A1": 15.8, "A2": 15.5, "C104": 7.7, "J8": 5.0, "J9": 8.5, "J10": 8.5,
           "J11": 8.5, "J12": 8.5}


def _rot(lx, ly, r):
    """Offset (lx, ly) in a frame rotated by r degrees CCW (KiCad, y down) -> board offset."""
    return {0: (lx, ly), 90: (ly, -lx), 180: (-lx, -ly), 270: (-ly, lx)}[r % 360]


def macro(origin, rot, items):
    ox, oy = origin
    out = {}
    for ref, (lx, ly, lr) in items.items():
        dx, dy = _rot(lx, ly, rot)
        out[ref] = (round(ox + dx, 3), round(oy + dy, 3), (lr + rot) % 360)
    return out


# Buck power stage in the IC's frame (TPS54560B at the origin, rot 0: BOOT/PH on top, VIN left, FB/COMP right).
# Hot loop: input caps left of VIN, catch diode right of PH, their grounds joined by copper above the IC.
BUCK = {
    "U": (0, 0, 0), "CB": (0, -3.65, 0),
    "CI1": (-6.15, -1.6, 90), "CI2": (-8.65, -1.6, 90), "CI3": (-11.15, -1.6, 90), "CIH": (-6.15, 2.4, 90),
    "D": (7.6, -4.4, 90), "L": (16.6, -5.75, 90),
    "CO1": (24.4, -13.0, 0), "CO2": (24.4, -10.5, 0), "CO3": (24.4, -8.0, 0), "CO4": (24.4, -5.5, 0),
    "CO5": (24.4, -3.0, 0),
    "RT": (-1.8, 4.7, 0), "RENT": (-5.1, 4.7, 0), "RENB": (-5.1, 6.5, 0), "CEN": (-8.6, 5.5, 90),
    "FBB": (1.8, 4.7, 180), "FBT": (1.8, 6.5, 180), "RC": (5.1, 4.7, 0), "CC": (5.1, 6.5, 180),
    "CP": (5.1, 8.3, 0),
    "DEN": (-5.1, 8.7, 0), "QINH": (-5.1, 11.9, 0), "RINHPD": (-8.6, 11.6, 270),
}
PI_ROLES = dict(U="U201", CB="C205", CI1="C201", CI2="C202", CI3="C204", CIH="C203", D="D201", L="L201",
                CO1="C206", CO2="C207", CO3="C208", CO4="C209", CO5="C210", RT="R206", RENT="R207", RENB="R208",
                CEN="C213", FBB="R204", FBT="R203", RC="R205", CC="C211", CP="C212", DEN="D202", QINH="Q201",
                RINHPD="R210")
ESP_ROLES = dict(U="U301", CB="C305", CI1="C301", CI2="C302", CI3="C304", CIH="C303", D="D301", L="L301",
                 CO1="C306", CO2="C307", CO3="C308", CO4="C309", CO5="C310", RT="R306", RENT="R307", RENB="R308",
                 CEN="C313", FBB="R304", FBT="R303", RC="R305", CC="C311", CP="C312")
PI_BUCK_AT = ((67.05, 44.5), 90)      # output (inductor, caps) up toward J5, input down toward the 12 V bus
ESP_BUCK_AT = ((38.23, 30.1), 270)    # output down toward the DevKit, LDO and connectors


def _buck(roles, at):
    return macro(at[0], at[1], {ref: BUCK[role] for role, ref in roles.items()})


def fixed():
    P = {}
    for i, (x, y) in enumerate(HOLES, 1):
        P[f"H{i}"] = (x, y, 0)
    P["A1"] = (DEVKIT_XY[0], DEVKIT_XY[1], 0)
    P["A2"] = (CC1101_XY[0], CC1101_XY[1], 0)
    P["J5"] = (83.4, 7.6, 180)          # 5 V out, wire entries toward the top edge
    P["J1"] = (14.0, 94.0, 0)           # 12 V in, wire entries toward the bottom edge (lid cable exit below)
    for ref, x in (("J4", 38.3), ("J2", 48.5), ("J3", 58.7), ("J6", 68.9)):
        P[ref] = (x, 96.6, 0)           # GH-4, mouths on the bottom edge
    P["J7"] = (81.4, 96.6, 0)           # GH-6 GPS
    P["J8"] = (30.5, 12.6, 0)           # fan header (top of the fan zone), right-angle pins point +x
    P["J10"] = (89.4, 62.0, 0)          # DNP CC1101 breakout, 1x8 down +y
    P["J9"] = (93.4, 62.0, 0)           # DNP expansion 2x5
    P["J11"] = (51.6, 64.8, 0)          # DNP 12 V for an external 5 V module (below the 12 V bus)
    P["J12"] = (44.6, 64.8, 0)          # DNP external 5 V module output into 5V_ESP_RAW
    P.update(_buck(PI_ROLES, PI_BUCK_AT))
    P.update(_buck(ESP_ROLES, ESP_BUCK_AT))
    # 12 V input chain, left of J1
    P["F101"] = (14.0, 84.5, 90)
    P["D101"] = (6.6, 84.2, 180)        # TVS: its VIN_FUSED pad next to the fuse, GND pad toward the edge
    P["Q101"] = (21.0, 81.5, 180)
    P["L101"] = (14.5, 70.0, 90)
    P["C104"] = (4.6, 70.0, 270)
    P["R104"] = (23.7, 63.5, 0)
    P["U101"] = (23.7, 68.5, 0)
    P["R211"] = (67.4, 18.5, 90)        # 5V_PI shunt: 5V_PI_RAW at the bottom pad, 5V_PI at the top
    P["U202"] = (71.8, 18.5, 90)
    P["D203"] = (90.0, 17.0, 0)
    P["D302"] = (40.0, 59.4, 0)
    P["D304"] = (9.5, 56.6, 0)
    P["U302"] = (77.6, 70.0, 0)         # 3.3 V LDO under the CC1101 module (11 mm above), near its VCC pin
    P["U801"] = (81.5, 34.0, 90)        # TMP75 beside the Pi buck and the INA226 (U202), on the I2C bus
    P["U802"] = (94.0, 50.0, 90)
    P["U501"] = (50.0, 78.6, 0)
    P["U502"] = (60.4, 78.6, 0)
    P["U503"] = (38.6, 75.0, 0)
    P["Q601"] = (52.4, 88.4, 0)
    P["Q602"] = (62.6, 88.4, 0)
    P["Q603"] = (42.0, 85.2, 0)
    P["Q604"] = (44.2, 12.8, 0)         # fan switch beside J8
    P["F601"] = (36.6, 86.8, 0)
    P["F901"] = (78.4, 88.6, 0)
    return P


def soft():
    """Approximate spots for the small parts (see the module docstring)."""
    S = {}
    x0, y0 = DEVKIT_XY
    pin_y = {n: y0 + 2.54 * (n - 1) for n in range(1, 16)}
    # cut-point resistors beside the DevKit's pins (left row: x0 + 3.9, right row: x0 + 18.9), turned so the
    # pad on the ESP32 net faces its pin
    left = {2: "R504", 3: "R509", 4: "R702", 5: "R703", 6: "R520", 7: "R906", 8: "R601", 9: "R209", 10: "R905",
            11: "R605", 13: "R609"}
    right = {1: "R401", 2: "R404", 5: "R405", 6: "R701", 7: "R402", 8: "R403", 9: "R902", 10: "R901", 11: "R517"}
    esp_pad1 = {"R601", "R209", "R905", "R605", "R609", "R401", "R404", "R405", "R402", "R403", "R902"}
    for n, ref in left.items():                     # pad 1 sits on the left at rotation 0
        S[ref] = (x0 + 3.9, pin_y[n], 0 if ref in esp_pad1 else 180)
    for n, ref in right.items():
        S[ref] = (x0 + 18.9, pin_y[n], 180 if ref in esp_pad1 else 0)
    S["R907"] = (x0 + 7.4, pin_y[10], 0)            # DNP GPS swap pair beside R905 / R906
    S["R908"] = (x0 + 7.4, pin_y[7], 180)
    S["R214"] = (79.4, 21.6, 0)                     # 5V_PI rail-up divider: top resistor at the rail ...
    S["R215"] = (x0 + 18.9, pin_y[13], 0)           # ... pull-down at IO15 (PGOOD reads low if the trace is cut)
    S["C314"] = (5.0, 56.2, 90)
    S["R518"] = (19.6, 59.4, 90)                    # ACC sense: 100 k at the 12 V source ...
    S["R519"] = (x0 + 10.8, pin_y[6] + 0.9, 0)      # ... 10 k, filter and clamp beside IO32
    S["C505"] = (x0 + 10.8, pin_y[6] + 2.7, 0)
    S["D507"] = (x0 + 11.0, pin_y[4] - 0.3, 0)
    S["R801"] = (x0 + 15.3, pin_y[5], 0)            # I2C pull-ups
    S["R802"] = (x0 + 15.3, pin_y[2], 0)
    S["R612"] = (48.0, 12.0, 0)                     # fan gate: series from the expander, pull-up to 3V3
    S["R611"] = (48.0, 13.8, 0)
    S["C801"] = (79.6, 28.6, 90)                    # above the TMP75's V+ pin
    # 12 V input chain
    S["R101"] = (29.8, 81.5, 270)
    S["R102"] = (29.8, 85.0, 270)
    S["C101"] = (30.5, 76.5, 90)
    S["C102"] = (6.5, 61.5, 90)                     # pi-filter output caps upright: 12V_PROT pads at the bottom
    S["C103"] = (11.6, 61.5, 90)                    # so one strap joins them, the inductor and the shunt
    S["C105"] = (16.6, 61.5, 0)
    S["R106"] = (29.3, 64.2, 0)                     # INA1 sense filters: 12V_BUS tap beside the shunt's
    S["R105"] = (29.3, 66.6, 0)                     # right pad, 12V_PROT tap below it (the sense straps
    S["C106"] = (29.3, 68.6, 0)                     # from the two shunt pads don't cross)
    S["C107"] = (23.7, 71.6, 0)
    S["R107"] = (9.5, 78.6, 0)
    S["D102"] = (5.0, 78.6, 180)
    # bucks' links and outputs
    S["R201"] = (63.0, 58.6, 0)
    S["R202"] = (63.0, 61.0, 0)
    S["R301"] = (57.0, 60.0, 0)
    S["R309"] = (46.6, 58.8, 0)
    S["R310"] = (50.8, 58.0, 0)
    S["D303"] = (50.8, 59.8, 180)
    # 5V_PI monitor and indicators
    S["R212"] = (75.2, 20.6, 90)
    S["R213"] = (75.2, 16.4, 90)
    S["C214"] = (77.0, 18.5, 90)
    S["C215"] = (73.6, 22.9, 0)
    S["R216"] = (88.6, 21.4, 0)
    S["D204"] = (92.2, 21.4, 180)
    # 3.3 V and radio supply, under the CC1101 module
    S["C315"] = (74.6, 70.0, 90)
    S["C316"] = (80.6, 70.0, 90)
    S["R311"] = (77.6, 73.2, 0)
    S["C317"] = (80.8, 73.4, 90)
    S["R312"] = (83.4, 70.0, 90)
    S["R313"] = (77.6, 66.6, 0)
    S["D305"] = (81.0, 66.6, 0)
    S["FB701"] = (75.2, 75.8, 0)
    S["C701"] = (72.0, 76.4, 90)
    S["C702"] = (72.0, 80.0, 90)
    # fan driver
    S["D602"] = (44.2, 15.4, 0)                     # above the ESP32 buck's 12 V feed strap
    # opto inputs: left door, right door (same pattern +10.2 mm), AUX
    for dx, (r1, r2, led, dpro, rpu, cf, rtie) in ((0.0, ("R501", "R502", "D501", "D502", "R503", "C501", "R505")),
                                                  (10.2, ("R506", "R507", "D503", "D504", "R508", "C502", "R510"))):
        S[r1] = (46.4 + dx, 90.6, 90)
        S[r2] = (46.4 + dx, 87.0, 90)
        S[led] = (46.4 + dx, 83.5, 90)
        S[dpro] = (48.6 + dx, 88.0, 90)
        S[rpu] = (53.6 + dx, 74.6, 90)
        S[cf] = (55.4 + dx, 74.6, 90)
        S[rtie] = (48.6 + dx, 92.4, 0)
    S["R511"] = (34.0, 80.6, 90)
    S["R512"] = (36.2, 80.6, 90)
    S["D505"] = (38.4, 80.6, 90)
    S["D506"] = (42.0, 80.6, 0)
    S["R513"] = (44.0, 73.2, 90)
    S["C503"] = (44.0, 76.6, 90)
    S["R514"] = (45.8, 76.6, 90)
    S["R515"] = (27.0, 87.4, 0)
    # door LED, piezo and button drivers
    S["R602"] = (52.4, 91.6, 0)
    S["R603"] = (50.6, 84.6, 90)
    S["R604"] = (52.6, 84.6, 90)
    S["R606"] = (62.6, 91.6, 0)
    S["R607"] = (60.8, 84.6, 90)
    S["R608"] = (62.8, 84.6, 90)
    S["R610"] = (42.0, 88.6, 0)
    S["D601"] = (40.0, 90.5, 0)                     # leaves room for the POD label above J4
    S["R516"] = (34.0, 91.2, 90)
    S["C504"] = (35.8, 91.2, 90)
    # Pi link, GPS
    S["R903"] = (90.6, 55.2, 90)
    S["R904"] = (92.4, 55.2, 90)
    S["C901"] = (83.6, 88.6, 90)
    S["R909"] = (85.6, 91.0, 90)
    S["R910"] = (87.4, 91.0, 90)
    # I/O expander
    S["C802"] = (90.2, 47.0, 90)
    S["R803"] = (90.2, 50.6, 90)
    return S


# test pads by net: approximate spots
TP_AT = {
    "12V_PROT": (9.2, 66.0), "12V_BUS": (32.0, 60.6), "5V_PI_RAW": (63.8, 15.6), "5V_PI": (81.6, 16.4),
    "5V_ESP": (55.6, 57.6), "3V3": (80.4, 76.4), "3V3_RF": (83.0, 76.4), "DEVKIT_VIN": (14.6, 56.6),
    "EN_PI": (80.6, 46.0), "EN_ESP": (31.4, 18.0), "ACC_DIV": (16.0, 42.0), "BLINK_L_OC": (55.6, 80.0),
    "BLINK_R_OC": (66.0, 80.0), "AUX_OPTO": (46.6, 79.6), "PI_TXD": (74.8, 91.6), "PI_RXD": (77.2, 91.6),
    "GPS_RXD_C": (79.6, 91.6), "GPS_TXD_C": (82.0, 91.6), "I2C_SDA": (16.0, 46.0), "I2C_SCL": (16.0, 48.4),
    "CC_GDO0": (86.2, 86.4), "CC_GDO2": (88.6, 86.4), "POD_BTN": (33.8, 83.4),
}
TP_GND_AT = [(2.6, 88.8), (93.0, 86.0)]

# High-current copper, laid as locked F.Cu tracks before the autorouter: (net, from "REF.PAD", to "REF.PAD",
# width mm[, waypoints]). Without waypoints the builder takes the shortest straight, L or Z path that clears
# every other net by STRAP_CLR; with them it takes exactly that path (None = keep the previous coordinate, or the
# end pad's for the last waypoint). Either way it stops if the copper isn't clear. Everything not listed carries
# well under 0.5 A and is autorouted; the power pours added after routing only add copper on top of these.
STRAP_CLR = 0.25
STRAPS = [
    # 12 V in (fused 4 A): J1 -> fuse -> P-FET; TVS on the fused side; pi filter; shunt
    ("VIN_RAW", "J1.1", "F101.1", 2.0),
    ("VIN_FUSED", "F101.2", "Q101.2", 2.0),
    ("VIN_FUSED", "F101.2", "D101.1", 1.5),
    ("12V_RP", "Q101.3", "L101.1", 2.0),
    ("12V_RP", "Q101.3", "C101.1", 1.0),
    ("12V_RP", "C101.1", "R101.1", 0.4),
    ("12V_PROT", "L101.2", "R104.1", 2.0),
    ("12V_PROT", "L101.2", "C103.1", 1.0),
    ("12V_PROT", "C103.1", "C102.1", 1.0),
    ("12V_PROT", "C102.1", "C104.1", 1.0),
    # 12 V bus: shunt -> the 0 R links of both bucks (and the DNP external-module header)
    ("12V_BUS", "R104.2", "R202.1", 1.5),
    ("12V_BUS", "R202.1", "R201.1", 1.5),
    ("12V_BUS", "R301.1", "R202.1", 1.0),
    ("12V_BUS", "J11.1", "J11.2", 1.0),
    ("12V_BUS", "J11.1", "R301.1", 1.0),
    # Pi buck (5 A): input caps, switch node, output caps, shunt, J5's three 5 V pins, clamp
    ("12V_PIB", "R201.2", "R202.2", 1.5),
    ("12V_PIB", "R202.2", "C204.1", 1.5),
    ("12V_PIB", "C204.1", "C202.1", 1.5),
    ("12V_PIB", "C202.1", "C201.1", 1.5),
    ("12V_PIB", "C201.1", "U201.2", 0.8),
    ("SW_PI", "U201.8", "D201.1", 1.0),
    ("SW_PI", "D201.1", "L201.1", 2.0),
    ("5V_PI_RAW", "L201.2", "C207.1", 2.0),
    ("5V_PI_RAW", "C206.1", "C210.1", 2.0),
    ("5V_PI_RAW", "C210.1", "R211.1", 2.0),
    ("5V_PI", "R211.2", "J5.5", 2.0),
    ("5V_PI", "J5.5", "J5.3", 2.0),
    ("5V_PI", "J5.3", "J5.1", 2.0),
    ("5V_PI", "J5.1", "D203.1", 1.0),
    # ESP32 buck (1 A)
    ("12V_ESPB", "C304.1", "C302.1", 1.0),
    ("12V_ESPB", "C302.1", "C301.1", 1.0),
    ("12V_ESPB", "C301.1", "U301.2", 0.8),
    ("SW_ESP", "U301.8", "D301.1", 1.0),
    ("SW_ESP", "D301.1", "L301.1", 1.5),
    ("5V_ESP_RAW", "L301.2", "C307.1", 1.5),
    ("5V_ESP_RAW", "C306.1", "C310.1", 1.5),
    # Kelvin sense: each INA226 filter resistor taps its shunt pad directly, so no strap copper (about
    # 1 mOhm per 5 mm at 2 mm wide: 10 % of a 10 mOhm shunt) sits inside the measurement
    ("12V_PROT", "R104.1", "R105.1", 0.3),
    ("12V_BUS", "R104.2", "R106.1", 0.3),
    ("5V_PI_RAW", "R211.1", "R212.1", 0.3),
    ("5V_PI", "R211.2", "R213.1", 0.3),
    # small branches boxed in by the straps above (0.2 mm fits between 0.5 mm-pitch pins)
    ("12V_PROT", "R105.1", "U101.8", 0.2),
    ("5V_PI", "R213.1", "U202.8", 0.2),
    ("5V_PI", "D203.1", "R216.1", 0.3),
    ("5V_PI", "R216.1", "R214.1", 0.25),
    # the Pi buck regulates at the shunt's input pad (the Kelvin point): its feedback divider runs round the
    # compensation parts to the INA226 filter resistor's 5V_PI_RAW pad
    ("5V_PI_RAW", "R203.1", "R212.1", 0.25, [(77.6, None), (77.6, None)]),
    # the piezo's PTC is walled off from the router by U101 and the shunt's Kelvin lines: a strap from the 12 V bus
    # test pad straight down the free x = 32 corridor
    ("12V_BUS", "TP2.1", "F601.1", 0.3),
    # ESP32 buck feed, from its 0 R link at the 12 V bus: up beside the Pi buck's input caps, left under the
    # Pi buck's output caps, up between the two bucks (clear of L201 and the 5V_PI_RAW bus) and over the
    # top into the input capacitors
    ("12V_ESPB", "R301.2", "C304.1", 0.8, [(None, 50.0), (52.2, 50.0), (52.2, 17.2), (None, 17.2)]),
]
