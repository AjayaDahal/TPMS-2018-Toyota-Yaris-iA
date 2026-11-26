#!/usr/bin/env python3
"""3-D printed enclosure for the v2 build: the SunFounder TS-7 7" HDMI touch display, the Raspberry Pi 4 behind it
and the 100 x 100 mm carrier PCB in one unit, plus a small wired "alert pod" for the mute button and the buzzer.

    python 01-hardware/enclosure/make_enclosure.py                       # STLs + report, runs every check
    python 01-hardware/enclosure/make_enclosure.py --set MOD_H=124.6 HDMI_Y=23.5 HDMI_PLUG=22,21,7.5

Writes stl/print_*.stl (print orientation, for the slicer), stl/asm_*.stl (assembly, used by the viewer) and
enclosure_report.json next to this file. Exits with status 1 if a check fails.

Frame: X to the driver's right, Y up, Z toward the driver. Z = 0 is the front of the display glass, so
everything behind the glass has Z < 0. Millimetres. Requires: pip install manifold3d numpy

Display: SunFounder TS-7 (SKU CN0199). SunFounder's table: module 165.30 x 121.00 x 7.75 mm, active area
154.21 x 85.92 mm, 1024 x 600 IPS, HDMI video, micro-USB for touch and power (5 V, 480 mA typ.). SunFounder
publishes no drawing, and four of its product photos give a width/height ratio of 1.33: a board about 124.4 mm tall
over its mounting ears (like the common 7" HDMI board, 164.9 x 124.27 mm), not 121. The defaults follow the
photos; every value marked MEASURE must be checked with calipers before printing (README, "Measure first").
The display hangs by its four M3 ears on bosses in the bezel. Its HDMI and micro-USB sockets sit on the back of
its board at the right edge (seen from the front); the LCD flex wraps round the bottom edge.
"""
import argparse
import json
import math
import pathlib
import sys

import numpy as np
from manifold3d import CrossSection, Manifold, OpType

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import panel_config as CFG  # noqa: E402  console opening from the v1 paper fit

# ------------------------------------------------------------------------------------------------- parameters
# MEASURE = check on your own parts (README "Measure first") and pass the value with --set before the final print.
P = dict(
    # SunFounder TS-7, front view, measured from the centre of its board
    MOD_W=165.3,            # board width (SunFounder)
    MOD_H=124.4,            # MEASURE: board height over the ears (SunFounder lists 121.0; its photos give 124.1-124.8)
    MAIN_H=106.4,           # MEASURE: board height between the ears
    EAR_W=7.6,              # MEASURE: width of each corner ear
    HOLE_IN_X=4.0,          # MEASURE: ear-hole centre from the board's left / right edge
    HOLE_IN_Y=5.0,          # MEASURE: ear-hole centre from the board's top / bottom edge
    HOLE_D=3.2,
    GW=164.9, GH=100.0,     # cover glass
    GLASS_DY=-0.5,          # MEASURE: glass centre above (+) or below (-) the board centre
    ACTIVE_W=154.21, ACTIVE_H=85.92,
    ACTIVE_DX=-1.2, ACTIVE_DY=3.2,   # active-area centre from the glass centre (estimated from photos)
    MODULE_T=7.75,          # glass front -> back of the board (SunFounder)
    BOARD_T=1.6,
    BACK_H=6.3,             # MEASURE: tallest part on the back of the board (the HDMI socket)
    BACK_CLR=0.4,
    HDMI_Y=25.0,            # MEASURE: HDMI socket centre above the board centre (right edge)
    USB_Y=4.0,              # MEASURE: micro-USB socket centre above the board centre (right edge)
    HDMI_SOCK=(13.0, 15.0, 6.3, 1.4),     # depth into the board, width, height, overhang past the board edge
    USB_SOCK=(5.5, 7.5, 2.8, 1.2),
    HDMI_PLUG=(20.0, 22.0, 6.0),          # MEASURE your straight HDMI-A FPC adapter: length past the socket, width, thickness
    USB_PLUG=(11.0, 12.0, 7.0),           # MEASURE your 90° micro-USB plug (cable leaving upward): same three
    LCD_FPC_X=(-16.5, 13.5),              # MEASURE: LCD flex at the bottom edge, from the board centre
    SCREEN_DX=-8.0,         # the display sits this far toward the driver, so the plugs fit on its right
    # Pi 4 on four posts behind the plate
    PI_POST_H=5.0,          # plate back -> underside of the Pi
    PI_BOARD_T=1.4,
    PI_TOP_H=17.0,          # tallest part above the Pi's board: USB/Ethernet ~16; GPIO plugs must be 90° / low profile
    JACK_OVER=2.5,          # USB/Ethernet jacks stick out past the board edge
    # carrier PCB (components face the lid)
    PCB_W=100.0, PCB_T=1.6, PCB_HOLE_IN=4.0,
    PCB_PIN_H=2.5,          # through-hole pins under the board
    PCB_COMP_H=16.0,        # tallest part on the board (DevKit and Pololu on sockets ~14-15)
    PCB_EDGE=3.5,           # air gap between the board edge and the walls
    AIR_GAP=3.0,            # between the Pi's tallest part and the PCB's pins
    FAN_PCB_XY=(45.0, 46.0),  # fan centre over the PCB in fit-template coords (from the top-left, component side)
    FAN_ZONE_H=6.0,         # PCB parts under the fan must stay below this
    SMA_FROM_TOP=38.0,      # SMA bulkhead, measured down from the inside of the box's top wall
    SMA_PCB_KEEP=(14.0, 12.0),  # board-edge strip kept free for the bulkhead (into the board x along the edge)
    # walls and fasteners
    BEZEL_W=205.6,          # overall width, centred on the console opening
    BEZEL_SIDE=3.0,         # side walls
    BEZEL_TB=2.0,           # top / bottom walls: thin, so the bezel is no taller than the console opening
    MOD_CLR=0.3,            # board outline -> bezel cavity
    LIP_T=2.0, LIP_GAP=0.3,
    LIP_COVER=2.0,          # the lip covers the outer 2 mm of the glass; the glass's own black border does the rest
    BOSS_D=7.0,
    WALL=2.5, PLATE_T=3.0, LID_T=2.5, LID_GAP=1.5,
    BOX_TOP_GAP=4.0,        # box top below the bezel top (the console opening's top edge is just above it)
    CSLOT=(1.5, 9.0, 38.0, 20.0),   # display cables through the plate: gap from the board edge, width, bottom Y, height
    SIDE_SLOT=(16.0, 24.0),         # display cables into the box: height (Y) and depth (Z), above the USB window
    SLOT_W=2.5,             # every vent slot: the boards must stay out of reach of fingers
    PILOT_D=2.6,            # M3 machine screw driven into plastic (ASA)
    PI_PILOT_D=2.2,         # M2.5 into plastic
    CLEAR_D=3.4,
    FAN=30.0, FAN_T=10.0, FAN_HOLE=24.0,
    SMA_D=6.6,              # SMA bulkhead jack for the RG316 antenna lead
    CABLE_SLOT=(22.0, 8.0),
    AMPS=(38.0, 30.0), AMPS_D=4.4, M4_NUT_AF=7.0, M4_NUT_T=3.4,
    # alert pod (mute button + buzzer, wired, near the shifter)
    BUTTON_D=12.2,          # MEASURE: thread of the inventory panel-mount pushbutton
    POD_BUZ_D=23.2, POD_BUZ_H=12.0,   # MEASURE: 12 V active piezo (3-24 V type)
    POD=(60.0, 30.0, 28.0),
    BED=(220.0, 220.0, 250.0),
    SEG=40,
)


def parse_args():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--set", nargs="*", default=[], metavar="NAME=VALUE",
                    help="override a parameter; tuples as comma lists, e.g. HDMI_PLUG=22,21,7.5")
    ap.add_argument("--out", default=str(HERE))
    a = ap.parse_args()
    for kv in a.set:
        k, v = kv.split("=", 1)
        if k not in P or not isinstance(P[k], (int, float, tuple)):
            sys.exit(f"unknown or non-numeric parameter {k}")
        if isinstance(P[k], tuple):
            vals = tuple(float(x) for x in v.split(","))
            if len(vals) != len(P[k]):
                sys.exit(f"{k} needs {len(P[k])} comma-separated values")
            P[k] = vals
        else:
            P[k] = float(v)
    return pathlib.Path(a.out)


# ------------------------------------------------------------------------------------------------- CSG helpers
def box(x0, x1, y0, y1, z0, z1):
    xa, xb, ya, yb, za, zb = min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1), min(z0, z1), max(z0, z1)
    return Manifold.cube((xb - xa, yb - ya, zb - za)).translate((xa, ya, za))


def cyl_z(cx, cy, z0, z1, d, seg=None):
    za, zb = min(z0, z1), max(z0, z1)
    return Manifold.cylinder(zb - za, d / 2, d / 2, seg or P["SEG"]).translate((cx, cy, za))


def cyl_y(cx, cz, y0, y1, d, seg=None):
    ya, yb = min(y0, y1), max(y0, y1)
    return Manifold.cylinder(yb - ya, d / 2, d / 2, seg or P["SEG"]).rotate((-90, 0, 0)).translate((cx, ya, cz))


def cyl_x(cy, cz, x0, x1, d, seg=None):
    xa, xb = min(x0, x1), max(x0, x1)
    return Manifold.cylinder(xb - xa, d / 2, d / 2, seg or P["SEG"]).rotate((0, 90, 0)).translate((xa, cy, cz))


def hex_y(cx, cz, y0, y1, af):
    r = af / math.sqrt(3)
    pts = [(r * math.cos(math.radians(30 + 60 * i)), r * math.sin(math.radians(30 + 60 * i))) for i in range(6)]
    ya, yb = min(y0, y1), max(y0, y1)
    return CrossSection([pts]).extrude(yb - ya).rotate((-90, 0, 0)).translate((cx, ya, cz))


def stadium_z(x0, x1, y0, y1, z0, z1):
    """Rounded slot (stadium) through Z, its long axis along the longer side."""
    w, h = x1 - x0, y1 - y0
    r = min(w, h) / 2
    if w >= h:
        a, b = (x0 + r, (y0 + y1) / 2), (x1 - r, (y0 + y1) / 2)
    else:
        a, b = ((x0 + x1) / 2, y0 + r), ((x0 + x1) / 2, y1 - r)
    cs = CrossSection.batch_hull([CrossSection.circle(r, P["SEG"]).translate(a),
                                  CrossSection.circle(r, P["SEG"]).translate(b)])
    za, zb = min(z0, z1), max(z0, z1)
    return cs.extrude(zb - za).translate((0, 0, za))


def union(parts):
    parts = [p for p in parts if p is not None]
    return Manifold.batch_boolean(parts, OpType.Add) if len(parts) > 1 else parts[0]


def bbox(m):
    return [round(v, 3) for v in m.bounding_box()]


def overlap(a, b):
    return (a ^ b).volume()


# ------------------------------------------------------------------------------------------------- geometry
def build():
    g = {}
    W, H, dx = P["MOD_W"], P["MOD_H"], P["SCREEN_DX"]
    mx0, mx1, my0, my1 = dx - W / 2, dx + W / 2, -H / 2, H / 2          # display board over the ears
    mh, ew = P["MAIN_H"] / 2, P["EAR_W"]
    holes_d = [(x, y) for x in (mx0 + P["HOLE_IN_X"], mx1 - P["HOLE_IN_X"])
               for y in (my0 + P["HOLE_IN_Y"], my1 - P["HOLE_IN_Y"])]
    gx0, gx1 = dx - P["GW"] / 2, dx + P["GW"] / 2
    gy0, gy1 = P["GLASS_DY"] - P["GH"] / 2, P["GLASS_DY"] + P["GH"] / 2
    acx, acy = dx + P["ACTIVE_DX"], P["GLASS_DY"] + P["ACTIVE_DY"]
    act = (acx - P["ACTIVE_W"] / 2, acx + P["ACTIVE_W"] / 2, acy - P["ACTIVE_H"] / 2, acy + P["ACTIVE_H"] / 2)
    lc = P["LIP_COVER"]
    win = (gx0 + lc, gx1 - lc, gy0 + lc, gy1 - lc)

    # ---- Z levels (negative = behind the glass)
    z_bb = -P["MODULE_T"]                        # back of the display's board
    z_bf = z_bb + P["BOARD_T"]                   # front of the board = front face of the ears
    z_pf = z_bb - P["BACK_H"] - P["BACK_CLR"]    # plate front
    z_pb = z_pf - P["PLATE_T"]                   # plate back
    z_pi_bot = z_pb - P["PI_POST_H"]
    z_pi_top = z_pi_bot - P["PI_BOARD_T"]
    z_pi_tall = z_pi_top - P["PI_TOP_H"]
    z_pcb_bot = z_pi_tall - P["AIR_GAP"] - P["PCB_PIN_H"]
    z_pcb_top = z_pcb_bot - P["PCB_T"]
    z_comp = z_pcb_top - P["PCB_COMP_H"]
    z_lid_in = z_comp - P["LID_GAP"]
    z_lid_out = z_lid_in - P["LID_T"]
    z_lip0, z_lip1 = P["LIP_GAP"], P["LIP_GAP"] + P["LIP_T"]

    # ---- bezel outline, centred on the console opening
    bx = P["BEZEL_W"] / 2
    c = P["MOD_CLR"]
    cav = (-bx + P["BEZEL_SIDE"], bx - P["BEZEL_SIDE"], my0 - c, my1 + c)
    by0, by1 = cav[2] - P["BEZEL_TB"], cav[3] + P["BEZEL_TB"]

    # ---- rear box: as wide as the PCB needs, centred; it stands on the pocket floor, 1 mm above the opening's bottom
    # edge, so the bezel (as tall as the opening) lines up with the opening's top and bottom edges
    s = 1.0                                       # the Pi's USB/Ethernet end faces the driver's right (+X)
    ix1 = P["PCB_W"] / 2 + P["PCB_EDGE"]
    ix0 = -ix1
    ox0, ox1 = ix0 - P["WALL"], ix1 + P["WALL"]
    oy0 = by0 + 1.0
    iy0 = oy0 + P["WALL"]
    oy1 = by1 - P["BOX_TOP_GAP"]
    iy1 = oy1 - P["WALL"]
    pcb_x0 = ix0 + P["PCB_EDGE"]
    pcb_x1 = pcb_x0 + P["PCB_W"]
    pcb_y1 = iy1 - P["PCB_EDGE"]
    pcb_y0 = pcb_y1 - P["PCB_W"]
    xpc, ypc = (pcb_x0 + pcb_x1) / 2, (pcb_y0 + pcb_y1) / 2

    def tpl(x, y):                        # fit-template PCB coords (component side, from the top-left) -> X, Y
        return xpc - (x - 50.0), ypc + (50.0 - y)

    holes = [tpl(hx, hy) for hx in (P["PCB_HOLE_IN"], P["PCB_W"] - P["PCB_HOLE_IN"])
             for hy in (P["PCB_HOLE_IN"], P["PCB_W"] - P["PCB_HOLE_IN"])]

    # ---- Pi 4: parts toward the lid, USB/Ethernet end toward the driver's right. That is the Pi's usual
    # orientation turned 180° about X (not mirrored), so its HDMI / USB-C edge is on top and the GPIO header at the
    # bottom. It sits between the PCB's posts, its jacks 0.5 mm inside the port-side wall.
    pi_x1 = ix1 - 0.5 - P["JACK_OVER"]
    pi_x0 = pi_x1 - 85.0
    post_lo, post_hi = min(y for _, y in holes), max(y for _, y in holes)
    pi_y0 = post_lo + 3.5 + 2.0
    pi_y1 = pi_y0 + 56.0

    def pxy(xl, yl):                      # Pi local (x toward the USB/Ethernet end, y toward the GPIO header) -> X, Y
        return pi_x0 + xl, pi_y1 - yl

    def prect(x0, x1, y0, y1):
        (xa, ya), (xb, yb) = pxy(x0, y0), pxy(x1, y1)
        return min(xa, xb), max(xa, xb), min(ya, yb), max(ya, yb)

    pi_posts = [pxy(x, y) for x in (3.5, 61.5) for y in (3.5, 52.5)]
    wx0, wx1, wy0, wy1 = prect(64, 85 + P["JACK_OVER"], 1.5, 54.5)
    usb_y = prect(64, 85, 1.5, 36.0)[2:]          # the four USB-A ports (the Ethernet jack below them stays empty)
    win_y = (wy0 - 2.5, wy1 + 2.5)                # USB/Ethernet window in the port-side wall
    ss_y0 = win_y[1] + 3.0                        # display-cable slot above it
    ss_y1 = ss_y0 + P["SIDE_SLOT"][0]
    ss_z1 = z_pb - 1.5
    ss_z0 = ss_z1 - P["SIDE_SLOT"][1]
    port_x, other_x = ox1 + 3.0, ox0 - 3.0
    ears = [(port_x, oy0 + 16.0), (port_x, ss_y1 + 6.5),
            (other_x, (oy0 + oy1) / 2 - 5.0), (other_x, oy1 - 15.5)]
    sma_y = iy1 - P["SMA_FROM_TOP"]
    sma_z = (z_pcb_top + z_lid_in) / 2

    # display cables: HDMI and micro-USB plugs at the board's right edge, rising inside the bezel to a slot in the
    # plate that lies inside the console opening, then behind the plate beside the box
    hd, hw, hh, ho = P["HDMI_SOCK"]
    ud, uw, uh, uo = P["USB_SOCK"]
    hl, hpw, hpt = P["HDMI_PLUG"]
    ul, upw, upt = P["USB_PLUG"]
    hface, uface = mx1 + ho, mx1 + uo
    zh, zu = z_bb - hh / 2, z_bb - uh / 2
    plugs_y1 = max(P["HDMI_Y"] + hpw / 2, P["USB_Y"] + upw / 2)
    cs_x0 = mx1 + P["CSLOT"][0]
    cs_x1 = cs_x0 + P["CSLOT"][1]
    cs_y0 = P["CSLOT"][2]
    cs_y1 = cs_y0 + P["CSLOT"][3]

    # bezel screws: from the back of the plate into bosses in the bezel; outside the box, clear of the ears
    strip_x = ox1 + 5.5
    strip_y = cav[3] - P["BOSS_D"] / 2 + 0.5
    bez_screws = [(-strip_x, strip_y), (strip_x, strip_y), (-strip_x, -strip_y), (strip_x, -strip_y),
                  ((cav[0] + mx0 - c) / 2, -25.0), (cav[1] - P["BOSS_D"] / 2 - 0.2, -45.0)]

    # ================================================================ dummies (what goes inside)
    board = box(mx0, mx1, -mh, mh, z_bb, z_bf)
    for xa, xb in ((mx0, mx0 + ew), (mx1 - ew, mx1)):
        board = board + box(xa, xb, my0, -mh + 0.01, z_bb, z_bf) + box(xa, xb, mh - 0.01, my1, z_bb, z_bf)
    for X, Y in holes_d:
        board = board - cyl_z(X, Y, z_bb - 1, z_bf + 1, P["HOLE_D"])
    fx0, fx1 = dx + P["LCD_FPC_X"][0], dx + P["LCD_FPC_X"][1]
    g["display"] = union([
        board,
        box(gx0, gx1, gy0, gy1, z_bf, 0.0),                                                 # glass + LCD
        box(mx0 + 1.5, mx1 - 1.5, -mh + 1.5, mh - 1.5, z_bb - P["BACK_H"], z_bb),            # parts on the back
        box(hface - hd, hface, P["HDMI_Y"] - hw / 2, P["HDMI_Y"] + hw / 2, z_bb - hh, z_bb),   # HDMI socket
        box(uface - ud, uface, P["USB_Y"] - uw / 2, P["USB_Y"] + uw / 2, z_bb - uh, z_bb),     # micro-USB socket
        box(fx0, fx1, -mh - 1.7, gy0 + 1.0, z_bb - 0.6, z_bf - 0.2),                        # LCD flex round the edge
    ])
    top_h = zh + hpt / 2                                     # front face of the HDMI adapter
    g["cables"] = union([
        box(hface, hface + hl, P["HDMI_Y"] - hpw / 2, P["HDMI_Y"] + hpw / 2, zh - hpt / 2, top_h),     # HDMI FPC adapter
        box(hface + hl, hface + hl + 1.5, P["HDMI_Y"] - hpw / 2, plugs_y1 + 3.0, z_pf + 0.3, top_h),   # flat cable folds up
        box(cs_x0 + 1.0, hface + hl + 1.5, plugs_y1, plugs_y1 + 3.0, z_pf + 0.3, z_pf + 2.0),        # and runs over it
        box(cs_x0 + 1.0, cs_x1 - 1.0, plugs_y1, cs_y1 - 1.0, z_pf + 0.3, z_pf + 5.0),                # to the slot
        box(uface, uface + ul, P["USB_Y"] - upw / 2, P["USB_Y"] + upw / 2, zu - upt / 2, zu + upt / 2),  # 90° micro-USB
        box(uface + 2.0, uface + 6.5, P["USB_Y"] + upw / 2, cs_y0 + 4.0, top_h + 0.3, -1.0),         # its lead, in front
        box(uface + 2.0, uface + 6.5, cs_y0, cs_y0 + 4.0, z_pf + 0.3, -1.0),                         # of the HDMI adapter
    ])

    under = box(*prect(0, 85, 0, 56), z_pi_bot, z_pi_bot + 2.0)                               # solder joints, SD socket
    for X, Y in pi_posts:
        under = under - cyl_z(X, Y, z_pi_bot - 1, z_pi_bot + 3, 6.4)                          # keep-out round the holes
    g["pi"] = union([
        box(*prect(0, 85, 0, 56), z_pi_top, z_pi_bot),                                     # board
        box(*prect(0, 85, 0, 56), z_pi_tall, z_pi_top),                                    # everything on top
        box(*prect(64, 85 + P["JACK_OVER"], 1.5, 54.5), z_pi_top - 16.0, z_pi_top),        # USB / Ethernet
        box(*prect(5.2, 17.2, -13.0, 0.0), z_pi_top - 9.0, z_pi_top + 1.0),                # 90° USB-C plug
        box(*prect(20.0, 32.0, -18.0, 0.0), z_pi_top - 8.0, z_pi_top + 0.5),               # micro-HDMI FPC adapter
        box(*prect(11.0, 21.0, 50.0, 71.0), z_pi_top - 12.0, z_pi_top),                    # 90° UART plug on the GPIO
        box(*prect(-2.5, 15.0, 22.0, 34.0), z_pi_bot, z_pi_bot + 1.5),                     # micro-SD card
        under,
    ])

    pcb = box(pcb_x0, pcb_x1, pcb_y0, pcb_y1, z_pcb_top, z_pcb_bot)
    for X, Y in holes:
        pcb = pcb - cyl_z(X, Y, z_pcb_top - 1, z_pcb_bot + 1, 3.2)
    g["pcb"] = pcb
    fan_x, fan_y = tpl(*P["FAN_PCB_XY"])
    fz = P["FAN"] / 2 + 1
    env = box(pcb_x0, pcb_x1, pcb_y0, pcb_y1, z_comp, z_pcb_top)
    pins = box(pcb_x0, pcb_x1, pcb_y0, pcb_y1, z_pcb_bot, z_pcb_bot + P["PCB_PIN_H"])
    for X, Y in holes:                                        # no pins round the mounting holes / post ribs
        pins = pins - box(X - 5.0, X + 5.0, Y - 5.0, Y + 5.0, z_pcb_bot - 1, z_pcb_bot + P["PCB_PIN_H"] + 1)
        pins = pins - box(X, (pcb_x0 if X < xpc else pcb_x1), Y - 1.6, Y + 1.6, z_pcb_bot - 1, z_pcb_bot + 4)
        pins = pins - box(X - 1.6, X + 1.6, Y, (pcb_y0 if Y < ypc else pcb_y1), z_pcb_bot - 1, z_pcb_bot + 4)
    env = env - box(fan_x - fz, fan_x + fz, fan_y - fz, fan_y + fz, z_comp - 1, z_pcb_top - P["FAN_ZONE_H"])
    kx, ky = P["SMA_PCB_KEEP"]
    edge_x = pcb_x0 if s > 0 else pcb_x1
    env = env - box(edge_x, edge_x + s * kx, sma_y - ky / 2, sma_y + ky / 2, z_comp - 1, z_pcb_top)
    g["pcb_parts"] = env + pins
    g["fan"] = box(fan_x - P["FAN"] / 2, fan_x + P["FAN"] / 2, fan_y - P["FAN"] / 2, fan_y + P["FAN"] / 2,
                   z_lid_in, z_lid_in + P["FAN_T"])
    sma_wall_x = ix0 if s > 0 else ix1
    g["sma"] = cyl_x(sma_y, sma_z, sma_wall_x, sma_wall_x + s * 9.0, 9.0)                 # bulkhead body + nut
    g["screws"] = union([cyl_z(X, Y, z_pb - 2.0, z_pb, 6.0) for X, Y in bez_screws])      # bezel screw heads

    # ================================================================ bezel
    bez = box(-bx, bx, by0, by1, z_pf, z_lip1)
    bez = bez - box(cav[0], cav[1], cav[2], cav[3], z_pf - 1, z_lip0)                     # one cavity behind the skin
    bez = bez - box(win[0], win[1], win[2], win[3], z_lip0 - 1, z_lip1 + 1)               # window
    slots = []                                                                            # cabin-air intake
    lx0, lx1 = cav[0] + 1.2, mx0 - c - 1.2
    rx0, rx1 = mx1 + c + 1.5, bez_screws[5][0] - P["BOSS_D"] / 2 - 1.0
    y = cav[2] + 3.0
    while y + P["SLOT_W"] <= cav[3] - 3.0:
        if abs(y + P["SLOT_W"] / 2 - bez_screws[4][1]) > P["BOSS_D"] / 2 + 1.5:            # clear of the left boss
            slots.append(box(lx0, lx1, y, y + P["SLOT_W"], z_lip0 - 1, z_lip1 + 1))
        if y + P["SLOT_W"] <= P["USB_Y"] - upw / 2 - 3.0:                                 # below the plugs
            slots.append(box(rx0, rx1, y, y + P["SLOT_W"], z_lip0 - 1, z_lip1 + 1))
        y += 5.0
    bez = bez - union(slots)
    intake_mm2 = sum((bb[3] - bb[0]) * (bb[4] - bb[1]) for bb in (sl.bounding_box() for sl in slots))
    for X, Y in holes_d:                  # the display hangs on these: M3 x 6 from behind, through its ears
        bez = bez + (cyl_z(X, Y, z_bf, z_lip0 + 0.01, P["BOSS_D"]) - cyl_z(X, Y, z_bf - 1, z_bf + 6.0, P["PILOT_D"]))
    for X, Y in bez_screws:               # the plate screws on from behind
        bez = bez + (cyl_z(X, Y, z_pf, z_lip0 + 0.01, P["BOSS_D"]) - cyl_z(X, Y, z_pf - 1, z_pf + 10.0, P["PILOT_D"]))
    g["bezel"] = bez

    # ================================================================ housing: plate + box
    plate = box(-bx, bx, by0, by1, z_pb, z_pf)
    walls = box(ox0, ox1, oy0, oy1, z_lid_in, z_pb + 0.01)
    ear_solids = []
    for X, Y in ears:
        ear_solids.append(cyl_z(X, Y, z_lid_in, z_pb, 8.0))
        ear_solids.append(box(X, ox0 + 1 if X < ox0 else ox1 - 1, Y - 4.0, Y + 4.0, z_lid_in, z_pb))
    housing = union([plate, walls] + ear_solids)
    housing = housing - box(ix0, ix1, iy0, iy1, z_lid_in - 1, z_pb)                       # inside of the box
    posts = []
    for X, Y in holes:                    # PCB posts, each tied to its two nearest walls
        z0, z1 = z_pcb_bot, z_pb + 0.6
        posts.append(cyl_z(X, Y, z0, z1, 7.0))
        posts.append(box(X, ix0 if X < xpc else ix1, Y - 1.0, Y + 1.0, z0, z1))
        posts.append(box(X - 1.0, X + 1.0, Y, iy0 if Y < ypc else iy1, z0, z1))
    for X, Y in pi_posts:                 # Pi posts (M2.5)
        posts.append(cyl_z(X, Y, z_pi_bot, z_pb + 0.6, 6.0))
    housing = housing + union(posts)
    for X, Y in holes:
        housing = housing - cyl_z(X, Y, z_pcb_bot - 1, z_pcb_bot + 10.0, P["PILOT_D"])
    for X, Y in pi_posts:
        housing = housing - cyl_z(X, Y, z_pi_bot - 1, z_pi_bot + 6.0, P["PI_PILOT_D"])
    # air intake windows behind the display: bezel slots -> behind the display -> these -> past the Pi -> lid fan
    ppx = sorted({round(p[0], 3) for p in pi_posts})
    ppy = sorted({round(p[1], 3) for p in pi_posts})
    intake = [(ix0 + 3.0, ppx[0] - 5.0, post_lo + 5.0, post_hi - 5.0),
              (ppx[1] + 5.0, ix1 - 3.0, ppy[0] + 4.0, ppy[1] - 4.0),
              (ppx[0], ppx[1], pi_y1 + 3.0, post_hi - 5.0)]
    for x0, x1, y0, y1 in intake:
        housing = housing - box(x0, x1, y0, y1, z_pb - 0.5, z_pf + 0.5)
    # display cables through the plate (outside the box, inside the console opening) and into the box
    housing = housing - stadium_z(cs_x0, cs_x1, cs_y0, cs_y1, z_pb - 1, z_pf + 1)
    housing = housing - box(ix1 - 1, ox1 + 1, ss_y0, ss_y1, ss_z0, ss_z1)
    for X, Y in bez_screws:
        housing = housing - cyl_z(X, Y, z_pb - 1, z_pf + 1, P["CLEAR_D"])
    for X, Y in ears:
        housing = housing - cyl_z(X, Y, z_lid_in - 1, z_lid_in + 10.0, P["PILOT_D"])
    # USB/Ethernet window in the port-side wall, big enough for the plugs' moulded bodies
    housing = housing - box(ix1 - 1, ox1 + 1, win_y[0], win_y[1], z_pi_top - 18.5, z_pi_top + 1.5)
    # SMA bulkhead for the RG316 antenna lead, in the wall away from the ports, level with the PCB bay
    housing = housing - cyl_x(sma_y, sma_z, ox0 - 1, ix0 + 1, P["SMA_D"])
    # AMPS 30 x 38 pattern in the bottom wall, M4 nuts captured in bosses inside (RAM base or a car bracket)
    amps_x0 = (ix0 + ix1) / 2
    amps_z0 = (z_pb + z_lid_in) / 2
    amps = [(amps_x0 + ddx, amps_z0 + ddz) for ddx in (-P["AMPS"][0] / 2, P["AMPS"][0] / 2)
            for ddz in (-P["AMPS"][1] / 2, P["AMPS"][1] / 2)]
    housing = housing + union([cyl_y(X, Z, iy0 - 0.5, iy0 + 5.0, 11.0) for X, Z in amps])
    for X, Z in amps:
        housing = housing - cyl_y(X, Z, oy0 - 1, iy0 + 6.0, P["AMPS_D"])
        housing = housing - hex_y(X, Z, iy0 + 5.0 - P["M4_NUT_T"], iy0 + 6.0, P["M4_NUT_AF"] + 0.3)
    # bumps on the back of the plate: a 2 mm gap to the trim lets the fan's air out round the edge (Option A)
    bumps = [(X, Y) for X in (-(bx - 6), bx - 6) for Y in (by0 + 6, 0.0, by1 - 6)]
    housing = housing + union([cyl_z(X, Y, z_pb - 2.0, z_pb + 0.01, 6.0) for X, Y in bumps])
    g["housing"] = housing

    # ================================================================ lid with the fan
    lid = box(ox0, ox1, oy0, oy1, z_lid_out, z_lid_in)
    for X, Y in ears:
        lid = lid + cyl_z(X, Y, z_lid_out, z_lid_in, 8.0)
        lid = lid + box(X, ox0 + 1 if X < ox0 else ox1 - 1, Y - 4.0, Y + 4.0, z_lid_out, z_lid_in)
    rim = box(ix0 + 0.3, ix1 - 0.3, iy0 + 0.3, iy1 - 0.3, z_lid_in, z_lid_in + 2.0)
    rim = rim - box(ix0 + 1.9, ix1 - 1.9, iy0 + 1.9, iy1 - 1.9, z_lid_in - 1, z_lid_in + 3.0)
    lid = lid + rim
    for X, Y in ears:
        lid = lid - cyl_z(X, Y, z_lid_out - 1, z_lid_in + 1, P["CLEAR_D"])
    grille = cyl_z(fan_x, fan_y, z_lid_out - 1, z_lid_in + 1, P["FAN"] - 2.0)
    bars = union([box(fan_x - P["FAN"], fan_x + P["FAN"], fan_y + k - 1.0, fan_y + k + 1.0, z_lid_out - 2,
                      z_lid_in + 2) for k in np.arange(-13.5, 14.0, 4.5)])
    lid = lid - (grille - bars)
    h = P["FAN_HOLE"] / 2
    for ddx in (-h, h):
        for ddy in (-h, h):
            lid = lid - cyl_z(fan_x + ddx, fan_y + ddy, z_lid_out - 1, z_lid_in + 1, P["CLEAR_D"])
    cw, ch = P["CABLE_SLOT"]
    cx_, cy_ = xpc + s * 20.0, iy0 + 10.0
    slot2d = CrossSection.batch_hull([CrossSection.circle(ch / 2, P["SEG"]).translate((cx_ - cw / 2 + ch / 2, cy_)),
                                      CrossSection.circle(ch / 2, P["SEG"]).translate((cx_ + cw / 2 - ch / 2, cy_))])
    lid = lid - slot2d.extrude(P["LID_T"] + 2).translate((0, 0, z_lid_out - 1))
    g["lid"] = lid

    # ================================================================ alert pod (separate, wired)
    pw, pd, ph = P["POD"]
    shell = box(-pw / 2, pw / 2, -pd / 2, pd / 2, 0.0, ph) - box(-pw / 2 + 2, pw / 2 - 2, -pd / 2 + 2, pd / 2 - 2,
                                                                 -1.0, ph - 2.0)
    bxp, buzx = -16.0, 14.0
    shell = shell - cyl_z(bxp, 0, ph - 3, ph + 1, P["BUTTON_D"])
    cup_d = P["POD_BUZ_D"] + 0.4
    shell = shell + (cyl_z(buzx, 0, ph - 2 - P["POD_BUZ_H"], ph - 1, cup_d + 2.4)
                     - cyl_z(buzx, 0, ph - 3 - P["POD_BUZ_H"], ph - 2, cup_d))
    for k in range(7):
        a = 2 * math.pi * k / 6
        X, Y = (buzx, 0.0) if k == 6 else (buzx + 4.5 * math.cos(a), 4.5 * math.sin(a))
        shell = shell - cyl_z(X, Y, ph - 3, ph + 1, 1.8, 16)
    shell = shell - cyl_y(0.0, 6.0, pd / 2 - 3, pd / 2 + 1, 5.0)                        # cable exit
    for Y in (-(pd / 2 - 3.0), pd / 2 - 3.0):
        shell = shell + cyl_z(-3.0, Y, 0.0, ph - 2.0, 6.0) - cyl_z(-3.0, Y, -1.0, 10.0, P["PILOT_D"])
    g["pod_shell"] = shell
    base = box(-pw / 2, pw / 2, -pd / 2, pd / 2, -2.5, 0.0)
    for Y in (-(pd / 2 - 3.0), pd / 2 - 3.0):
        base = base - cyl_z(-3.0, Y, -3.0, 1.0, P["CLEAR_D"])
    g["pod_base"] = base
    g["pod_button"] = cyl_z(bxp, 0, ph - 2 - 22.0, ph - 2.0, P["BUTTON_D"] + 5.0)          # nut + body + tags
    g["pod_buzzer"] = cyl_z(buzx, 0, ph - 2 - P["POD_BUZ_H"], ph - 2.0, P["POD_BUZ_D"])

    geo = dict(s=s, bx=bx, by0=by0, by1=by1, cav=cav, module=(mx0, mx1, my0, my1), main_h=mh,
               glass=(gx0, gx1, gy0, gy1), active=act, window=win, holes_d=holes_d,
               box_outer=(ox0, ox1, oy0, oy1), box_inner=(ix0, ix1, iy0, iy1),
               pcb=(pcb_x0, pcb_x1, pcb_y0, pcb_y1), pcb_center=(xpc, ypc), pi=(pi_x0, pi_x1, pi_y0, pi_y1),
               z=dict(lip_front=z_lip1, glass=0.0, display_board_back=z_bb, plate_front=z_pf, plate_back=z_pb,
                      pi_bottom=z_pi_bot, pi_top=z_pi_top, pi_tall=z_pi_tall, pcb_bottom=z_pcb_bot,
                      pcb_top=z_pcb_top, parts_top=z_comp, lid_inner=z_lid_in, lid_outer=z_lid_out),
               bez_screws=bez_screws, ears=ears, amps=amps, fan=(fan_x, fan_y), sma=(sma_y, sma_z),
               port_window=win_y, usb_ports=usb_y, side_slot=(ss_y0, ss_y1), cable_slot=(cs_x0, cs_x1, cs_y0, cs_y1),
               pcb_holes=holes, pi_posts=pi_posts, slots=len(slots), intake_mm2=intake_mm2,
               plug_end_x=max(hface + hl + 1.5, uface + ul),
               front=dict(          # front-view outlines for the 1:1 fit template (X right, Y up, mm)
                   bezel=[-bx, bx, by0, by1], board=[mx0, mx1, my0, my1], main_h=2 * mh, ear_w=ew,
                   ear_holes=[list(p) for p in holes_d], glass=[gx0, gx1, gy0, gy1], window=list(win),
                   active=list(act), lcd_flex=[fx0, fx1, -mh - 1.7, -mh + 4.0],
                   hdmi_socket=[hface - hd, hface, P["HDMI_Y"] - hw / 2, P["HDMI_Y"] + hw / 2],
                   usb_socket=[uface - ud, uface, P["USB_Y"] - uw / 2, P["USB_Y"] + uw / 2],
                   hdmi_plug=[hface, hface + hl, P["HDMI_Y"] - hpw / 2, P["HDMI_Y"] + hpw / 2],
                   usb_plug=[uface, uface + ul, P["USB_Y"] - upw / 2, P["USB_Y"] + upw / 2],
                   cable_slot=[cs_x0, cs_x1, cs_y0, cs_y1], box=[ox0, ox1, oy0, oy1],
                   bezel_screws=[list(p) for p in bez_screws], opening_bottom_y=oy0 - 1.0))
    return g, geo


# ------------------------------------------------------------------------------------------------- export
def write_stl(man, path):
    mesh = man.to_mesh()
    v = np.asarray(mesh.vert_properties, dtype=np.float64)[:, :3]
    t = np.asarray(mesh.tri_verts, dtype=np.int64)
    tri = v[t]
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    n = n / np.where(ln == 0, 1, ln)
    rec = np.zeros(len(t), dtype=[("n", "<f4", (3,)), ("v", "<f4", (3, 3)), ("a", "<u2")])
    rec["n"], rec["v"] = n, tri
    with open(path, "wb") as fh:
        fh.write(b"Yaris iA v2 enclosure (make_enclosure.py), mm".ljust(80, b" "))
        fh.write(np.uint32(len(t)).tobytes())
        fh.write(rec.tobytes())
    return len(t)


def to_print(name, m, geo):
    z = geo["z"]
    if name == "bezel":               # face down
        return m.rotate((180, 0, 0)).translate((0, 0, z["lip_front"]))
    if name == "housing":             # front of the plate down, box upward
        return m.rotate((180, 0, 0)).translate((0, 0, z["plate_front"]))
    if name == "lid":                 # outside face down
        return m.translate((0, 0, -z["lid_outer"]))
    if name == "pod_shell":           # top face down
        return m.rotate((180, 0, 0)).translate((0, 0, P["POD"][2]))
    if name == "pod_base":
        return m.translate((0, 0, 2.5))
    return m


def to_viewer(m, geo):
    """Viewer frame: PCB centre at the origin, component side up (+Z). A rotation, so nothing is mirrored."""
    xpc, ypc = geo["pcb_center"]
    zmid = (geo["z"]["pcb_bottom"] + geo["z"]["pcb_top"]) / 2
    return m.translate((-xpc, -ypc, -zmid)).rotate((0, 180, 0))


# ------------------------------------------------------------------------------------------------- checks
def run_checks(g, geo):
    res = []

    def check(name, ok, detail):
        res.append(dict(check=name, ok=bool(ok), detail=detail))

    for name in ("bezel", "housing", "lid", "pod_shell", "pod_base"):
        m = g[name]
        st = str(m.status())
        check(f"{name}: valid solid", st.endswith("NoError") and m.volume() > 0,
              f"{st.split('.')[-1]}, {m.volume() / 1000:.1f} cm³, genus {m.genus()}")
        b = bbox(to_print(name, m, geo))
        size = (b[3] - b[0], b[4] - b[1], b[5] - b[2])
        bed = P["BED"]
        flat = (size[0] <= bed[0] - 5 and size[1] <= bed[1] - 5) or (size[1] <= bed[0] - 5 and size[0] <= bed[1] - 5)
        check(f"{name}: fits a {bed[0]:.0f} × {bed[1]:.0f} bed", flat and size[2] <= bed[2] and abs(b[2]) < 1e-6,
              f"print size {size[0]:.1f} × {size[1]:.1f} × {size[2]:.1f} mm, flat face on the bed")

    pairs = [("bezel", "display"), ("bezel", "cables"), ("display", "cables"), ("housing", "display"),
             ("housing", "cables"), ("housing", "pi"), ("housing", "pcb"), ("housing", "pcb_parts"),
             ("housing", "fan"), ("housing", "lid"), ("housing", "screws"), ("lid", "pcb_parts"), ("lid", "pcb"),
             ("fan", "pcb_parts"), ("pi", "pcb_parts"), ("pi", "pcb"), ("sma", "pcb_parts"), ("sma", "housing"),
             ("bezel", "housing"), ("pod_shell", "pod_button"), ("pod_shell", "pod_buzzer"),
             ("pod_button", "pod_buzzer"), ("pod_shell", "pod_base")]
    for a, b in pairs:
        v = overlap(g[a], g[b])
        check(f"no clash: {a} / {b}", v < 0.05, f"overlap {v:.3f} mm³")

    hd = geo["holes_d"]
    xs, ys = sorted({round(p[0], 3) for p in hd}), sorted({round(p[1], 3) for p in hd})
    mx0, mx1, my0, my1 = geo["module"]
    r = P["BOSS_D"] / 2

    def on_ear(x, y):                     # the boss sits on the ear, clear of the board's main edge
        ex0, ex1 = (mx0, mx0 + P["EAR_W"]) if x < (mx0 + mx1) / 2 else (mx1 - P["EAR_W"], mx1)
        return abs(y) - r >= geo["main_h"] + 0.2 and x - r >= ex0 - 0.01 and x + r <= ex1 + 0.01

    on_ears = all(on_ear(x, y) for x, y in hd)
    check("display hangs on 4 bezel bosses, on its ears only", on_ears,
          f"ear holes {xs[1] - xs[0]:.1f} × {ys[1] - ys[0]:.1f} mm; Ø{P['BOSS_D']:g} bosses clear of the board's "
          f"main edge; M3 × 6 from behind")
    gx0, gx1, gy0, gy1 = geo["glass"]
    w = geo["window"]
    a = geo["active"]
    cover = min(w[0] - gx0, gx1 - w[1], w[2] - gy0, gy1 - w[3])
    clear = min(a[0] - w[0], w[1] - a[1], a[2] - w[2], w[3] - a[3])
    check("lip covers the glass edge, clears the active area", cover >= 1.5 and clear >= 0.5,
          f"lip over the glass {cover:.1f} mm, {P['LIP_GAP']:g} mm in front of it; window ≥ {clear:.1f} mm beyond "
          f"the active area (estimated position)")
    check("plugs fit inside the bezel", geo["plug_end_x"] <= geo["cav"][1] - 0.5,
          f"HDMI adapter + folded cable end {geo['plug_end_x']:.1f} mm, cavity wall {geo['cav'][1]:.1f} mm")
    ph = geo["pcb_holes"]
    hx, hy = sorted({round(p[0], 3) for p in ph}), sorted({round(p[1], 3) for p in ph})
    check("PCB posts on 92 × 92", abs(hx[1] - hx[0] - 92) < 0.01 and abs(hy[1] - hy[0] - 92) < 0.01,
          f"{hx[1] - hx[0]:.2f} × {hy[1] - hy[0]:.2f}")
    pp = geo["pi_posts"]
    px, py = sorted({round(p[0], 3) for p in pp}), sorted({round(p[1], 3) for p in pp})
    check("Pi posts on 58 × 49", abs(px[1] - px[0] - 58) < 0.01 and abs(py[1] - py[0] - 49) < 0.01,
          f"{px[1] - px[0]:.2f} × {py[1] - py[0]:.2f}, M2.5 into {P['PI_PILOT_D']} mm pilots")
    z = geo["z"]
    gap = z["pi_tall"] - z["pcb_bottom"] - P["PCB_PIN_H"]
    check("air gap Pi -> PCB pins", gap >= P["AIR_GAP"] - 1e-6, f"{gap:.1f} mm")
    check("vent openings finger-safe", P["SLOT_W"] <= 2.5,
          f"{geo['slots']} intake slots {P['SLOT_W']} mm wide ({geo['intake_mm2']:.0f} mm²); fan grille 2.5 mm gaps")

    # console opening (v1 paper fit): the box stands 1 mm above the opening's bottom edge
    top, bot, hgt = CFG.OPENING_TOP_WIDTH, CFG.OPENING_BOTTOM_WIDTH, CFG.OPENING_HEIGHT
    ox0, ox1, oy0, oy1 = geo["box_outer"]
    y_floor = oy0 - 1.0

    def margin(x, y):
        hb = y - y_floor
        half = (bot + (top - bot) * min(max(hb, 0), hgt) / hgt) / 2
        return min(half - abs(x), hgt - hb)

    pts = [(ox0, oy0), (ox1, oy0), (ox0, oy1), (ox1, oy1)]
    pts += [(x + d, y) for x, y in geo["ears"] for d in (-4.0, 4.0)]
    wy0, wy1 = geo["usb_ports"]
    sy0, sy1 = geo["side_slot"]
    plug_x = ox1 + 15.0 if geo["s"] > 0 else ox0 - 15.0
    lead_x = ox1 + 12.0 if geo["s"] > 0 else ox0 - 12.0
    sma_x = ox0 - 15.0 if geo["s"] > 0 else ox1 + 15.0
    pts += [(plug_x, wy0), (plug_x, wy1), (lead_x, sy0), (lead_x, sy1), (sma_x, geo["sma"][0])]
    worst = min(margin(x, y) for x, y in pts)
    check("box, ears, 90° USB plugs, display leads and SMA lead fit the console opening", worst >= 0,
          f"tightest margin {worst:.1f} mm (opening {top:g} top / {bot:g} bottom × {hgt:g})")
    cx0, cx1, cy0, cy1 = geo["cable_slot"]
    cm = min(margin(x, y) for x in (cx0, cx1) for y in (cy0, cy1))
    check("display-cable slot in the plate opens into the pocket", cm >= 1.0,
          f"slot {cx1 - cx0:.0f} × {cy1 - cy0:.0f} mm at x {cx0:.1f}-{cx1:.1f}; ≥ {cm:.1f} mm inside the opening's edge")
    bez_h = geo["by1"] - geo["by0"]
    over = geo["by1"] - (y_floor + hgt)
    check("bezel stays below the HVAC panel", bez_h <= hgt + 0.5 and over <= 0.5,
          f"bezel {2 * geo['bx']:.1f} × {bez_h:.1f} mm; its top {over:+.1f} mm from the opening's top edge (HVAC above)")
    return res


# ------------------------------------------------------------------------------------------------- main
COLORS = dict(bezel="#1f2937", housing="#334155", lid="#475569", display="#0b1220", pi="#15803d",
              pcb="#065f46", pcb_parts="#f59e0b", fan="#111827", cables="#f97316")
LABELS = dict(
    bezel="Bezel: front frame, the display hangs on its 4 bosses; intake slots beside the screen (print face down)",
    housing="Housing: plate + rear box for the Pi and the PCB (print plate down)",
    lid="Lid: 30 mm exhaust fan + cable exit (print outside face down)",
    display="SunFounder TS-7 7\" HDMI touch display (dummy)",
    pi="Raspberry Pi 4 with its plugs: micro-HDMI adapter, 90° USB-C, 90° UART (dummy)",
    pcb="100 × 100 mm carrier PCB (dummy)", pcb_parts="PCB part-height budget (dummy)", fan="30 mm fan (dummy)",
    cables="HDMI flat-cable adapter and 90° micro-USB plug, rising to the plate's cable slot (dummy)")


def _r2(v):
    return [_r2(x) for x in v] if isinstance(v, (list, tuple)) else round(float(v), 2)


def main():
    out = parse_args()
    g, geo = build()
    checks = run_checks(g, geo)
    stl = out / "stl"
    stl.mkdir(parents=True, exist_ok=True)
    files = {}
    for name in ("bezel", "housing", "lid", "pod_shell", "pod_base"):
        n = write_stl(to_print(name, g[name], geo), stl / f"print_{name}.stl")
        files[f"print_{name}"] = dict(file=f"stl/print_{name}.stl", triangles=n)
    for name in ("bezel", "housing", "lid", "display", "cables", "pi", "pcb", "pcb_parts", "fan"):
        n = write_stl(to_viewer(g[name], geo), stl / f"asm_{name}.stl")
        files[f"asm_{name}"] = dict(file=f"stl/asm_{name}.stl", triangles=n, color=COLORS[name], label=LABELS[name])

    z = geo["z"]
    ox0, ox1, oy0, oy1 = geo["box_outer"]
    behind = z["plate_back"] - z["lid_outer"]
    hd = geo["holes_d"]
    xs, ys = sorted({round(p[0], 2) for p in hd}), sorted({round(p[1], 2) for p in hd})
    cx0, cx1, cy0, cy1 = geo["cable_slot"]
    report = dict(
        generator="01-hardware/enclosure/make_enclosure.py",
        display="SunFounder TS-7 7\" HDMI touch display (1024 × 600 IPS)",
        mount="normal (IPS: no need to turn it upside down)",
        overall_mm=dict(width=round(2 * geo["bx"], 2), height=round(geo["by1"] - geo["by0"], 2),
                        depth=round(z["lip_front"] - z["lid_outer"], 2)),
        proud_of_trim_mm=round(z["lip_front"] - z["plate_back"] + 2.0, 1),
        screen_offset_mm=P["SCREEN_DX"],
        box_mm=dict(width=round(ox1 - ox0, 2), width_with_ears=round(ox1 - ox0 + 14.0, 2),
                    height=round(oy1 - oy0, 2), behind_plate=round(behind, 2),
                    clear_pocket_depth_needed=round(behind + 2.0 + 3.0, 1)),
        z_levels_mm={k: round(v, 2) for k, v in z.items()},
        ports_face="driver's right (+X)" if geo["s"] > 0 else "driver's left (-X)",
        display_mount=dict(
            ear_holes_mm=[round(xs[1] - xs[0], 2), round(ys[1] - ys[0], 2)],
            screws="4× M3 × 6 from behind, through the ears into the bezel's bosses",
            cable_slot=f"{cx1 - cx0:.0f} × {cy1 - cy0:.0f} mm in the plate, {cx0:.1f}-{cx1:.1f} mm right of centre, "
                       f"{cy0:.0f}-{cy1:.0f} mm up: the HDMI flat cable and the micro-USB lead go through it into the "
                       f"pocket, then into the box through the slot above the USB window",
            intake_slots_mm2=round(geo["intake_mm2"])),
        front_view_mm={k: _r2(v) for k, v in geo["front"].items()},
        pcb_constraints=dict(
            outline="100 × 100 mm, parts face the lid, 4× M3 on 92 × 92 into the posts",
            max_part_height_mm=P["PCB_COMP_H"],
            fan_zone=f"{P['FAN'] + 2:.0f} × {P['FAN'] + 2:.0f} mm centred at template {list(P['FAN_PCB_XY'])} "
                     f"(mm from the top-left, parts side up): parts ≤ {P['FAN_ZONE_H']:g} mm",
            sma_strip=f"{P['SMA_PCB_KEEP'][0]:g} mm into the board × {P['SMA_PCB_KEEP'][1]:g} mm along the edge, on "
                      f"the edge away from the Pi's ports, centred {P['SMA_FROM_TOP'] - P['PCB_EDGE']:g} mm below the "
                      f"board's top edge: no parts",
            corners="10 × 10 mm round each mounting hole: no through-hole pins (posts and ribs underneath)",
            pins_below_mm=P["PCB_PIN_H"]),
        hardware=dict(
            display_to_bezel="4× M3 × 6 pan or button head, from behind through the display's ears",
            bezel_to_plate=f"{len(geo['bez_screws'])}× M3 × 10 from the back of the plate into {P['PILOT_D']} mm pilots",
            pi_to_posts="4× M2.5 × 6 into 2.2 mm pilots",
            lid_to_box="4× M3 × 12 into the ears", pcb_to_posts="4× M3 × 6",
            fan="30 mm 5 V fan from the black Pi case, 4× M3 × 16 + nuts, blowing OUT through the lid",
            amps="4× M4 nuts in the bottom bosses, M4 × 10 (RAM-B-202U round base, or a car bracket)",
            pod="2× M3 × 8, VHB tape under the base"),
        parameters={k: v for k, v in P.items()},
        volumes_cm3={k: round(g[k].volume() / 1000, 1) for k in ("bezel", "housing", "lid", "pod_shell",
                                                                  "pod_base")},
        files=files,
        checks=checks,
        all_ok=all(c["ok"] for c in checks),
    )
    (out / "enclosure_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    def asc(t):                           # the Windows console may not be UTF-8
        for a, b_ in (("×", "x"), ("³", "3"), ("²", "2"), ("≥", ">="), ("≤", "<="), ("°", " deg"), ("→", "->"),
                      ("Ø", "D")):
            t = t.replace(a, b_)
        return t

    w = max(len(c["check"]) for c in checks)
    for c in checks:
        print(asc(f"{'PASS' if c['ok'] else 'FAIL'}  {c['check']:<{w}}  {c['detail']}"))
    o, b = report["overall_mm"], report["box_mm"]
    print(asc(f"\noverall {o['width']} × {o['height']} × {o['depth']} mm; stands {report['proud_of_trim_mm']} mm "
              f"proud of the trim; box {b['width']} × {b['height']} mm, {b['behind_plate']} mm behind the plate; "
              f"needs ≥ {b['clear_pocket_depth_needed']} mm clear pocket depth"))
    print(f"{sum(c['ok'] for c in checks)}/{len(checks)} checks passed -> {out / 'enclosure_report.json'}")
    return 0 if report["all_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
