#!/usr/bin/env python3
"""3-D printed enclosure for the v2 build: the SunFounder TS-7 7" HDMI touch display, the Raspberry Pi 4 behind it
and the 100 x 100 mm carrier PCB in one unit. The 12 V piezo sits inside it (behind the bezel's right intake slots,
firing at the driver; the beeps mute themselves, so there is no button), and a printed wing on the bezel's right
side holds the panel-mount USB passthrough from the v1 panel (the same 25.8 mm cut), which gives back the car's own
USB port that the unit covers.

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
    PI_TOP_H=17.0,          # tallest part above the Pi's board: USB/Ethernet ~16; the 40-pin ribbon's IDC ~12.5
    JACK_OVER=2.5,          # USB/Ethernet jacks stick out past the board edge
    # carrier PCB (components face the lid)
    PCB_W=100.0, PCB_T=1.6, PCB_HOLE_IN=4.0,
    PCB_PIN_H=2.5,          # through-hole pins under the board
    PCB_COMP_H=16.0,        # tallest part on the board (the DevKit and the CC1101 on their sockets, 15.5-15.8)
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
    CSLOT=(0.8, 12.2, 39.0, 24.0),  # display leads + both USB passthrough cables through the plate: gap from the
                                    # board edge, width, bottom Y, height (24 long: plug #2 passes cable #1)
    CSLOT_R=2.5,                    # its corner radius (the fit template draws it as a plain rectangle)
    SIDE_SLOT=(16.0, 24.0),         # display cables into the box: height (Y) and depth (Z), above the USB window
    SLOT_W=2.5,             # every vent slot: the boards must stay out of reach of fingers
    PILOT_D=2.6,            # M3 machine screw driven into plastic (ASA)
    PI_PILOT_D=2.2,         # M2.5 into plastic
    CLEAR_D=3.4,
    FAN=30.0, FAN_T=10.0, FAN_HOLE=24.0,
    SMA_D=6.6,              # SMA bulkhead jack for the RG316 antenna lead
    CABLE_SLOT=(22.0, 8.0),
    AMPS=(38.0, 30.0), AMPS_D=4.4, M4_NUT_AF=7.0, M4_NUT_T=3.4,
    # 12 V active piezo (3-24 V type), inside the unit: on the plate's front in the bezel's right cavity, below the
    # display's plugs, behind the intake slots there
    BUZ_D=23.2, BUZ_H=12.0,           # MEASURE: the piezo you buy (diameter, height without its leads)
    BUZ_RING=(1.2, 4.0),              # the 3 fingers on the bezel's skin that hold it: wall, how much of it they grip
    BUZ_GAP=2.0,                      # its face to the skin: air still flows to the slots, the sound goes out
    # Two panel-mount USB passthroughs from the v1 panel (ALTW USB 3.0 female socket, M25-class double-D thread,
    # cable to a male plug): both stacked vertically in one printed wing on the bezel's right side, sockets facing
    # right. The v1 Ø25.8 mm cut with 23.8 mm double-D flats (from your caliper photos: 25.16 mm thread, 23.28 mm
    # across the flats; set PASS_FLAT_W=0 for plain round). Both cables enter the bezel above the display's plugs and
    # drop through the plate's cable slot into the pocket (car USB port + second USB / flush 12 V charger).
    PASS_HOLE_D=CFG.USB_HOLE_DIAMETER,      # the v1 cut, for the measured 25.16 mm thread
    PASS_THREAD_D=CFG.USB_THREAD_DIAMETER,
    PASS_FLAT_D=23.28,                # measured (caliper photo): across the two double-D flats on the thread
    PASS_FLAT_W=23.8,                 # double-D cut across flats (23.28 + 0.52); 0 = plain round v1 cut
    PASS_COLLAR=(28.2, 3.0),          # MEASURE: collar / flange, diameter and thickness (the v1 model's)
    PASS_FRONT=(24.2, 8.0),           # MEASURE: the socket's body in front, diameter; how far it stands out in all
    PASS_REAR_L=22.4,                 # MEASURE: thread + body behind the panel, up to where the cable leaves
    PASS_NUT=(CFG.USB_NUT_DIAMETER, 5.0),   # MEASURE: nut across corners, thickness
    PASS_CABLE_D=5.5,                 # MEASURE: the cable
    PASS_PLUG=(16.5, 8.5),            # MEASURE: the male plug's moulding (every opening on the way passes both)
    PASS_YS=(43.0, 4.0),              # upper and lower socket centres above the bezel's centre line (39 mm pitch)
    WING_WALL=2.5,
    WING_SCREW=2.2,                   # wing screws: from the wall's inner face toward the axis
    TRIM_RIGHT=(36.0, 86.0),          # MEASURE: flat trim right of the bezel's edge, where the wing lands: wide, tall
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


def hex_x(cy, cz, x0, x1, af):
    """Hex prism along X, flats level (Z extent = af, Y extent = across corners)."""
    r = af / math.sqrt(3)
    pts = [(r * math.cos(math.radians(30 + 60 * i)), r * math.sin(math.radians(30 + 60 * i))) for i in range(6)]
    xa, xb = min(x0, x1), max(x0, x1)
    return CrossSection([pts]).extrude(xb - xa).rotate((0, 90, 0)).translate((xa, cy, cz))


def teardrop_x(cy, cz, x0, x1, d, n=64):
    """Round hole along X for a wall printed upright: 45° flanks toward -Z (up on the bed) meeting a short flat
    at the circle's own radius, so it bridges cleanly and stays inside the outline a collar or nut covers."""
    r = d / 2
    k, t = r / math.sqrt(2), (math.sqrt(2) - 1) * r
    shape = CrossSection.circle(r, n) + CrossSection([[(0, -k), (k, -k), (r, -t), (r, t), (k, k), (0, k)]])
    xa, xb = min(x0, x1), max(x0, x1)
    return shape.extrude(xb - xa).rotate((0, 90, 0)).translate((xa, cy, cz))


def double_d_x(cy, cz, x0, x1, d, flat_w, n=64):
    """Double-D hole or shaft along X (circle Ød clipped to flat_w across Z). Prints front-face-down with the -Z
    flat on top (clean bridge) and keeps the USB-A slot horizontal. flat_w <= 0 falls back to teardrop_x."""
    if flat_w <= 0 or flat_w >= d:
        return teardrop_x(cy, cz, x0, x1, d, n)
    r, hw = d / 2, flat_w / 2
    clip = CrossSection([[(-hw, -r - 1), (hw, -r - 1), (hw, r + 1), (-hw, r + 1)]])
    shape = CrossSection.circle(r, n) ^ clip
    xa, xb = min(x0, x1), max(x0, x1)
    return shape.extrude(xb - xa).rotate((0, 90, 0)).translate((xa, cy, cz))


def rbox_z(x0, x1, y0, y1, z0, z1, r):
    """Box through Z with rounded vertical corners."""
    cs = CrossSection.batch_hull([CrossSection.circle(r, P["SEG"]).translate((x, y))
                                  for x in (x0 + r, x1 - r) for y in (y0 + r, y1 - r)])
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
                  ((cav[0] + mx0 - c) / 2, -25.0), (cav[1] - P["BOSS_D"] / 2 - 0.2, -50.5)]

    # 12 V piezo: in the bezel's right cavity below the display's plugs and the wing's bottom screw, firing at the
    # driver through the intake slots there. Three fingers on the bezel's skin hold it with its face 2 mm off the
    # skin, so the cabin air still reaches those slots. Its two wires go up the cavity with the display leads.
    bz_x = (mx1 + c + cav[1]) / 2
    bz_y = -32.0
    bz_z1 = z_lip0 - P["BUZ_GAP"]                          # its face
    bz_z0 = bz_z1 - P["BUZ_H"]

    # Twin USB passthrough wing on the bezel's right side (two sockets stacked along Y, like v1's H5 + H6). Both
    # axes run along X, so the long bodies lie along the trim instead of needing depth behind it. Double-D cuts
    # (Ø25.8 × 23.8 mm, from your caliper photos: 25.16 mm thread, 23.28 mm flats) stop either socket twisting when
    # a cable is plugged in, and the wing has room for a 36 mm nut to spin on the bench from the open back (or from
    # outside if rear-mounted). It prints front face down (open back on top, the -Z flat bridges clean). 3 × M3 × 10
    # from inside the bezel's right cavity hold it: top and bottom gusseted tabs plus a centre post straight off the
    # front wall, leaving an 8 mm cable channel behind both bodies so the lower cable climbs behind the centre post
    # and both cables enter the bezel through one side opening, then drop through the plate's slot into the pocket.
    nut_ac, nut_t = P["PASS_NUT"]
    nut_af = nut_ac * math.cos(math.pi / 6)
    col_d, col_t = P["PASS_COLLAR"]
    ww = P["WING_WALL"]
    cd = P["PASS_CABLE_D"]
    plug_w, plug_t = P["PASS_PLUG"]
    z_trim = z_pb - 2.0                                    # the console trim, behind the plate's 2 mm bumps
    pz = z_trim + 0.3 + nut_af / 2                         # socket axes: nuts (flats level) 0.3 mm off the trim
    pys = tuple(sorted(P["PASS_YS"], reverse=True))        # (upper, lower)
    py_hi, py_lo = pys[0], pys[1]
    in_h = nut_ac / 2 + 0.6                                # room for a 36 mm nut to spin on the bench
    in_t = max(nut_ac / 2 + 0.5, col_d / 2 + 0.4, P["PASS_THREAD_D"] / 2 + 0.4)
    chan_w = cd + 2.5                                      # behind both bodies: the lower cable climbs here
    xw0, xw1 = bx, bx + chan_w + P["PASS_REAR_L"] + ww     # bezel side, end face
    wy0, wy1 = py_lo - in_h - ww, py_hi + in_h + ww
    wz0, wz1 = z_trim, pz + in_t + ww
    x_rear = xw1 - ww - P["PASS_REAR_L"]                   # where each cable leaves its body
    x_chan = xw0 + chan_w / 2                              # the lower cable's climb inside the wing
    z_climb = -12.5                                        # behind the centre screw post, clear of the trim
    z_open = z_lip0 - 0.5 - (plug_t + 1.0) / 2             # cable opening in the bezel's side wall, under its skin
    so_y0, so_y1 = 30.5, 55.5                              # 25 mm tall: passes plug #2 alongside cable #1
    tab_z = z_lip0 - 0.6 - 5.5 / 2                         # wing screws: heads under the skin, above the HDMI adapter
    tab_y = [py_lo - in_h + P["WING_SCREW"], (py_hi + py_lo) / 2, py_hi + in_h - P["WING_SCREW"]]
    tab_l = 7.5                                            # tabs/post along X (M3 × 10: 7 mm bite, 0.5 clear of x_rear)
    tab_in = in_h - (P["PASS_THREAD_D"] / 2 + 0.4)         # top/bottom tab depth, clear of the socket bodies
    x_drop = cs_x1 - 0.5 - cd / 2                          # both cables go down through the plate's slot here
    y_drops = (55.5, 45.5)                                 # 4.5 mm clear between cables, both well inside the slot
    y_cross = (52.5, 45.5)                                 # where upper and lower cables cross the bezel's side wall

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
        box(cs_x0 + 0.6, cs_x0 + 5.6, plugs_y1, cs_y1 - 1.0, z_pf + 0.3, z_pf + 5.0),                # to the slot
        box(uface, uface + ul, P["USB_Y"] - upw / 2, P["USB_Y"] + upw / 2, zu - upt / 2, zu + upt / 2),  # 90° micro-USB
        box(uface + 2.0, uface + 6.5, P["USB_Y"] + upw / 2, cs_y0 + 3.0, top_h + 0.3, -1.0),         # its lead, in front
        box(uface + 2.0, uface + 6.5, cs_y0, cs_y0 + 3.0, z_pf + 0.3, -1.0),                         # of the HDMI adapter
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
        box(*prect(4.5, 60.5, 49.5, 56.0), z_pi_top - 12.5, z_pi_top),                    # 40-pin ribbon's IDC plug
        box(*prect(5.0, 60.0, 49.5, 70.0), z_pi_top - 13.7, z_pi_top - 12.5),              # its ribbon, toward the box bottom
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
    g["buzzer"] = cyl_z(bz_x, bz_y, bz_z0, bz_z1, P["BUZ_D"])
    fr_d, fr_l = P["PASS_FRONT"]

    def pass_body(py_):
        return [
            cyl_x(py_, pz, xw1, xw1 + col_t, col_d),                                    # collar / flange
            cyl_x(py_, pz, xw1 + col_t, xw1 + fr_l, fr_d),                              # the socket
            double_d_x(py_, pz, x_rear, xw1, P["PASS_THREAD_D"], P["PASS_FLAT_D"]),     # double-D thread + body
            hex_x(py_, pz, xw1 - ww - nut_t, xw1 - ww, nut_af),                         # nut, flats level
        ]

    g["usb_pass_1"] = union(pass_body(py_hi) + [
        Manifold.batch_hull([cyl_x(py_hi, pz, x_rear - 0.5, x_rear, cd),                # upper cable -> side opening
                             cyl_x(y_cross[0], z_open, xw0, xw0 + 0.5, cd)]),
        cyl_x(y_cross[0], z_open, x_drop, xw0 + 0.5, cd),                               # across the cavity,
        cyl_y(x_drop, z_open, y_cross[0], y_drops[0], cd),
        cyl_z(x_drop, y_drops[0], z_pb - 12.0, z_open, cd),                             # down into the pocket
    ])
    g["usb_pass_2"] = union(pass_body(py_lo) + [
        Manifold.batch_hull([cyl_x(py_lo, pz, x_rear - 0.5, x_rear, cd),                # lower cable -> channel behind
                             cyl_y(x_chan, z_climb, py_lo + 6.0, py_lo + 6.5, cd)]),    # the centre screw post,
        cyl_y(x_chan, z_climb, py_lo + 6.0, 38.0, cd),
        Manifold.batch_hull([cyl_y(x_chan, z_climb, 37.5, 38.0, cd),                    # up into the side opening,
                             cyl_x(y_cross[1], z_open, xw0, xw0 + 0.5, cd)]),
        cyl_x(y_cross[1], z_open, x_drop, xw0 + 0.5, cd),                               # across the cavity,
        cyl_z(x_drop, y_drops[1], z_pb - 12.0, z_open, cd),                             # down into the pocket
    ])
    g["usb_pass"] = g["usb_pass_1"] + g["usb_pass_2"]
    g["wing_screws"] = union([cyl_x(Y, tab_z, cav[1] - 3.0, cav[1], 5.5) + cyl_x(Y, tab_z, cav[1], cav[1] + 10.0, 3.0)
                              for Y in tab_y])                                          # 3× M3 × 10 socket cap

    # ================================================================ bezel
    bez = box(-bx, bx, by0, by1, z_pf, z_lip1)
    bez = bez - box(cav[0], cav[1], cav[2], cav[3], z_pf - 1, z_lip0)                     # one cavity behind the skin
    bez = bez - box(win[0], win[1], win[2], win[3], z_lip0 - 1, z_lip1 + 1)               # window
    slots, rslots = [], []                                                                # cabin-air intake
    lx0, lx1 = cav[0] + 1.2, mx0 - c - 1.2
    rx0, rx1 = mx1 + c + 1.5, bez_screws[5][0] - P["BOSS_D"] / 2 - 1.0
    y = cav[2] + 3.0
    while y + P["SLOT_W"] <= cav[3] - 3.0:
        if abs(y + P["SLOT_W"] / 2 - bez_screws[4][1]) > P["BOSS_D"] / 2 + 1.5:            # clear of the left boss
            slots.append(box(lx0, lx1, y, y + P["SLOT_W"], z_lip0 - 1, z_lip1 + 1))
        if y + P["SLOT_W"] <= P["USB_Y"] - upw / 2 - 3.0:                                 # below the plugs
            rslots.append(box(rx0, rx1, y, y + P["SLOT_W"], z_lip0 - 1, z_lip1 + 1))
        y += 5.0
    slots += rslots
    bez = bez - union(slots)
    intake_mm2 = sum((bb[3] - bb[0]) * (bb[4] - bb[1]) for bb in (sl.bounding_box() for sl in slots))
    face = cyl_z(bz_x, bz_y, z_lip0 - 1, z_lip1 + 1, P["BUZ_D"])                         # the piezo's face, projected
    buz_slots = sum(1 for sl in rslots if (sl ^ face).volume() > 1.0)
    buz_open = (union(rslots) ^ face).volume() / (z_lip1 - z_lip0 + 2)
    for X, Y in holes_d:                  # the display hangs on these: M3 x 6 from behind, through its ears
        bez = bez + (cyl_z(X, Y, z_bf, z_lip0 + 0.01, P["BOSS_D"]) - cyl_z(X, Y, z_bf - 1, z_bf + 6.0, P["PILOT_D"]))
    for X, Y in bez_screws:               # the plate screws on from behind
        bez = bez + (cyl_z(X, Y, z_pf, z_lip0 + 0.01, P["BOSS_D"]) - cyl_z(X, Y, z_pf - 1, z_pf + 10.0, P["PILOT_D"]))
    for Y in tab_y:                       # the USB wing: M3 from inside the cavity, heads on the wall's inner face
        bez = bez - cyl_x(Y, tab_z, cav[1] - 1.0, bx + 1.0, P["CLEAR_D"])
    # the piezo's 3 fingers: a 2 mm ledge on the skin under its face's edge, then 4 mm of grip round its side
    rw, rg = P["BUZ_RING"]
    bd = P["BUZ_D"] + 0.4
    grip = (cyl_z(bz_x, bz_y, bz_z1 - rg, z_lip0 + 0.01, bd + 2 * rw) - cyl_z(bz_x, bz_y, bz_z1 - rg - 1, z_lip0 + 1, bd))
    ledge = (cyl_z(bz_x, bz_y, bz_z1, z_lip0 + 0.01, bd + 2 * rw)
             - cyl_z(bz_x, bz_y, bz_z1 - 1, z_lip0 + 1, P["BUZ_D"] - 3.0))
    sectors = []
    for a0 in (0.0, 120.0, 240.0):
        pts = [(0.0, 0.0)] + [(30 * math.cos(math.radians(a0 + d)), 30 * math.sin(math.radians(a0 + d)))
                              for d in (-20, -10, 0, 10, 20)]
        sectors.append(CrossSection([pts]).extrude(30.0).translate((bz_x, bz_y, z_lip0 - 20.0)))
    fingers = (grip + ledge) ^ union(sectors)
    fingers = fingers ^ box(mx1 + c + 0.3, bx, cav[2], cav[3], z_pf, z_lip0 + 0.01)
    bez = bez + fingers
    # both USB passthrough cables (and their plugs, one after the other) through the right side wall, under the skin
    bez = bez - box(cav[1] - 1.0, bx + 1.0, so_y0, so_y1,
                    z_open - (plug_t + 1.0) / 2, z_open + (plug_t + 1.0) / 2)
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
    housing = housing - rbox_z(cs_x0, cs_x1, cs_y0, cs_y1, z_pb - 1, z_pf + 1, P["CSLOT_R"])
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

    # ================================================================ twin USB passthrough wing (bezel's right side)
    # Prints front face down: the open back is on top, every wall upright, the two double-D flats bridge clean.
    # Top and bottom tabs sit on 45° gussets; the centre screw post stands straight off the front wall, leaving the
    # rear open for the lower cable to climb behind it.
    wing = box(xw0, xw1, wy0, wy1, wz0, wz1) - box(xw0 - 1.0, xw1 - ww, wy0 + ww, wy1 - ww, wz0 - 1.0, wz1 - ww)
    wing = wing + box(xw0, xw0 + ww, wy0, wy1, z_lip1, wz1)          # closes its inner end in front of the bezel
    for py_ in pys:
        wing = wing - double_d_x(py_, pz, xw1 - ww - 1.0, xw1 + 1.0, P["PASS_HOLE_D"], P["PASS_FLAT_W"])
    for sg, py_, Y in ((-1, py_lo, tab_y[0]), (1, py_hi, tab_y[2])):
        yw = py_ + sg * (in_h + 0.05)                # into the top / bottom wall
        ye = py_ + sg * (in_h - tab_in)              # clear of the socket body
        za, zb = tab_z - 3.5, tab_z + 3.5
        tab = box(xw0, xw0 + tab_l, min(yw, ye), max(yw, ye), za, zb)
        foot = box(xw0, xw0 + tab_l, min(yw, yw - sg * 0.05), max(yw, yw - sg * 0.05), zb, zb + tab_in)
        wing = wing + Manifold.batch_hull([tab, foot])
    # centre screw post straight off the front wall (zero overhang; cable 2 passes behind it at z_climb)
    wing = wing + box(xw0, xw0 + tab_l, tab_y[1] - 3.5, tab_y[1] + 3.5, tab_z - 3.5, wz1 - ww + 0.05)
    for Y in tab_y:
        wing = wing - cyl_x(Y, tab_z, xw0 - 1.0, xw0 + tab_l + 1.0, P["PILOT_D"])
    g["usb_wing"] = wing

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
                   bezel_screws=[list(p) for p in bez_screws], opening_bottom_y=oy0 - 1.0,
                   buzzer=[bz_x, bz_y, P["BUZ_D"]],
                   usb_wing=[xw0, xw1, wy0, wy1], usb_holes=[[xw1, py_, P["PASS_HOLE_D"]] for py_ in pys]),
               buzzer=dict(center=(bz_x, bz_y), d=P["BUZ_D"], h=P["BUZ_H"], face_z=bz_z1, back_z=bz_z0,
                           ring=P["BUZ_RING"], slots=buz_slots, open_mm2=buz_open, skin_z=z_lip0),
               usb=dict(axis_ys=pys, axis_z=pz, hole_d=P["PASS_HOLE_D"], thread_d=P["PASS_THREAD_D"],
                        flat_d=P["PASS_FLAT_D"], flat_w=P["PASS_FLAT_W"],
                        collar=(col_d, col_t), front=P["PASS_FRONT"], rear_l=P["PASS_REAR_L"],
                        nut=(nut_ac, nut_t), nut_af=nut_af, cable_d=cd, plug=(plug_w, plug_t),
                        wing=(xw0, xw1, wy0, wy1, wz0, wz1), wall=ww, inner=(in_h, in_t), x_rear=x_rear,
                        z_open=z_open, z_trim=z_trim, side_open=((so_y0 + so_y1) / 2, z_open, so_y1 - so_y0, plug_t + 1.0),
                        tabs=[(Y, tab_z) for Y in tab_y], tab_l=tab_l, tab_in=tab_in,
                        drops=[(x_drop, yd) for yd in y_drops], bezel_wall=bx - cav[1], front_z=z_lip1))
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
    if name == "usb_wing":            # front face down, the open back on top
        return m.rotate((180, 0, 0)).translate((0, 0, geo["usb"]["wing"][5]))
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

    for name in ("bezel", "housing", "lid", "usb_wing"):
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
             ("bezel", "housing"),
             ("buzzer", "bezel"), ("buzzer", "housing"), ("buzzer", "display"), ("buzzer", "cables"),
             ("usb_pass", "usb_wing"), ("usb_pass", "bezel"), ("usb_pass", "housing"), ("usb_pass", "display"),
             ("usb_pass", "cables"), ("usb_pass", "buzzer"), ("usb_pass", "screws"),
             ("usb_pass_1", "usb_pass_2"),
             ("usb_wing", "bezel"), ("usb_wing", "housing"), ("usb_wing", "display"),
             ("wing_screws", "bezel"), ("wing_screws", "cables"), ("wing_screws", "usb_pass"),
             ("wing_screws", "display"), ("wing_screws", "buzzer")]
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
    u = geo["usb"]
    for dx, dy in u["drops"]:
        pts += [(dx + sx * u["cable_d"] / 2, dy + sy * u["cable_d"] / 2) for sx in (-1, 1) for sy in (-1, 1)]
    worst = min(margin(x, y) for x, y in pts)
    check("box, ears, 90° USB plugs, display leads, SMA lead and both USB passthrough cables fit the console opening",
          worst >= 0, f"tightest margin {worst:.1f} mm (opening {top:g} top / {bot:g} bottom × {hgt:g})")
    cx0, cx1, cy0, cy1 = geo["cable_slot"]
    cm = min(margin(x, y) for x in (cx0, cx1) for y in (cy0, cy1))
    check("display-cable slot in the plate opens into the pocket", cm >= 1.0,
          f"slot {cx1 - cx0:.0f} × {cy1 - cy0:.0f} mm at x {cx0:.1f}-{cx1:.1f}; ≥ {cm:.1f} mm inside the opening's edge")
    bez_h = geo["by1"] - geo["by0"]
    over = geo["by1"] - (y_floor + hgt)
    check("bezel stays below the HVAC panel", bez_h <= hgt + 0.5 and over <= 0.5,
          f"bezel {2 * geo['bx']:.1f} × {bez_h:.1f} mm; its top {over:+.1f} mm from the opening's top edge (HVAC above)")

    bz = geo["buzzer"]
    gap = bz["skin_z"] - bz["face_z"]
    back = bz["back_z"] - geo["z"]["plate_front"]
    check("piezo inside the dash unit, behind the right intake slots", bz["slots"] >= 3 and gap >= 1.0
          and bz["open_mm2"] >= 60.0 and back >= 0.5,
          f"Ø{bz['d']:g} piezo on 3 fingers from the bezel's skin, its face {gap:.1f} mm behind it (air still flows); "
          f"{bz['slots']} slots ({bz['open_mm2']:.0f} mm²) in front of it; {back:.1f} mm clear of the plate")

    hole, thr, fw, fd = u["hole_d"], u["thread_d"], u["flat_w"], u["flat_d"]
    col_d, _ = u["collar"]
    flat_ok = fw <= 0 or (fw - fd >= 0.3 and fw < hole)
    check("both USB passthroughs use the v1 cut (with measured double-D flats)",
          abs(hole - CFG.USB_HOLE_DIAMETER) < 1e-9 and hole - thr >= 0.3 and flat_ok
          and min(col_d, u["nut_af"]) >= hole + 1.5,
          f"2× Ø{hole:g} × {fw:g} mm double-D (v1 Ø{hole:g} for Ø{thr:g} thread + {fd:g} flats, "
          f"{hole - thr:.2f} / {fw - fd:.2f} mm clearance); collar Ø{col_d:g} and nut {u['nut_af']:.1f} mm A/F cover it")
    ac = u["nut"][0]
    pitch = abs(u["axis_ys"][0] - u["axis_ys"][1])
    spin_front = u["inner"][1] - ac / 2
    spin_side = u["inner"][0] - ac / 2
    spin_mid = pitch - ac
    trim_gap = u["axis_z"] - u["nut_af"] / 2 - u["z_trim"]
    check("both 36 mm nuts spin on the bench and clear the trim when tightened",
          min(spin_front, spin_side) >= 0.4 and spin_mid >= 1.5 and trim_gap >= 0.29,
          f"pitch {pitch:g} mm ({spin_mid:.1f} mm between spinning {ac:g} mm nuts), ≥ {min(spin_front, spin_side):.1f} mm "
          f"to the walls; flats level = {trim_gap:.1f} mm off the trim (or nut outside if rear-mounted)")

    pw, pt = u["plug"]
    cd = u["cable_d"]
    _, _, so_w, so_t = u["side_open"]
    cx0, cx1, cy0, cy1 = geo["cable_slot"]
    W, L, rr = min(cx1 - cx0, cy1 - cy0), max(cx1 - cx0, cy1 - cy0), P["CSLOT_R"]
    L_rem = L - cd                                                    # cable #1 already in the slot when plug #2 passes
    ex, ey = pt / 2 - (W / 2 - rr), pw / 2 - (L_rem / 2 - rr)
    spare = min(W / 2 - pt / 2, L_rem / 2 - pw / 2, rr - math.hypot(ex, ey) if ex > 0 and ey > 0 else rr)
    hole_ok = (pw <= hole - 1.0 and pt <= (fw if fw > 0 else hole) - 1.0
               and math.hypot(pw, pt) <= hole - 1.0)
    check("both USB plugs pass every opening (plug #2 alongside cable #1)",
          hole_ok and so_w - cd >= pw + 1.0 and so_t >= pt + 1.0 and spare >= 0.5,
          f"{pw:g} × {pt:g} mm plugs: Ø{hole:g}×{fw:g} end holes, {so_w:g} × {so_t:g} side opening ({so_w - cd:.1f} mm "
          f"free beside cable #1), {W:.1f} × {L:.1f} plate slot ({spare:.1f} mm spare for plug #2 before display leads)")

    xw0, xw1, wy0, wy1, wz0, wz1 = u["wing"]
    tw, th = P["TRIM_RIGHT"]
    reach = xw1 + u["front"][1] - geo["bx"]
    proud = wz1 - u["front_z"]
    check("twin USB wing fits the trim beside the bezel (MEASURE the trim)",
          xw1 - xw0 <= tw and wy1 - wy0 <= th and wy1 <= geo["by1"] and wy0 >= geo["by0"],
          f"wing {xw1 - xw0:.1f} × {wy1 - wy0:.1f} mm on the trim (assumed {tw:g} × {th:g} free); sockets end "
          f"{reach:.1f} mm right of the bezel; wing front {proud:.1f} mm proud of bezel")
    bite = 10.0 - u["bezel_wall"]
    check("wing screws: 3× M3 × 10 from inside the bezel", 5.0 <= bite <= u["tab_l"] - 0.5,
          f"through the {u['bezel_wall']:g} mm wall, {bite:.0f} mm into {u['tab_l']:g} mm tabs/post (top, centre, "
          f"bottom); heads under the skin, clear of the HDMI adapter and piezo")
    return res


# ------------------------------------------------------------------------------------------------- main
COLORS = dict(bezel="#1f2937", housing="#334155", lid="#475569", display="#0b1220", pi="#15803d",
              pcb="#065f46", pcb_parts="#f59e0b", fan="#111827", cables="#f97316", buzzer="#e11d48",
              usb_wing="#1f2937", usb_pass="#94a3b8", wing_screws="#cbd5e1")
LABELS = dict(
    bezel="Bezel: front frame, the display hangs on its 4 bosses; intake slots beside the screen; 3 fingers hold the "
          "piezo behind the right slots (print face down)",
    housing="Housing: plate + rear box for the Pi and the PCB (print plate down)",
    lid="Lid: 30 mm exhaust fan + cable exit (print outside face down)",
    display="SunFounder TS-7 7\" HDMI touch display (dummy)",
    pi="Raspberry Pi 4 with its plugs: micro-HDMI adapter, 90° USB-C, 40-pin ribbon IDC (dummy)",
    pcb="100 × 100 mm carrier PCB (dummy)", pcb_parts="PCB part-height budget (dummy)", fan="30 mm fan (dummy)",
    cables="HDMI flat-cable adapter and 90° micro-USB plug, rising to the plate's cable slot (dummy)",
    buzzer="12 V active piezo, behind the right intake slots (dummy)",
    usb_wing="Twin USB wing: holds both car USB passthroughs beside the bezel, v1's Ø25.8 × 23.8 double-D cuts (print front face down)",
    usb_pass="Both v1 USB passthroughs (ALTW 25.16 / 23.28 double-D): sockets facing right, both cables into the pocket (dummy)",
    wing_screws="3× M3 × 10 from inside the bezel into the wing's top, centre and bottom bosses (dummy)")


def _r2(v):
    return [_r2(x) for x in v] if isinstance(v, (list, tuple)) else round(float(v), 2)


def main():
    out = parse_args()
    g, geo = build()
    checks = run_checks(g, geo)
    stl = out / "stl"
    stl.mkdir(parents=True, exist_ok=True)
    files = {}
    for name in ("bezel", "housing", "lid", "usb_wing"):
        n = write_stl(to_print(name, g[name], geo), stl / f"print_{name}.stl")
        files[f"print_{name}"] = dict(file=f"stl/print_{name}.stl", triangles=n)
    for name in ("bezel", "housing", "lid", "display", "cables", "pi", "pcb", "pcb_parts", "fan", "buzzer",
                 "usb_wing", "usb_pass", "wing_screws"):
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
        viewer_frame=dict(
            pcb_center_mm=_r2(geo["pcb_center"]), z_mid_mm=round((z["pcb_bottom"] + z["pcb_top"]) / 2, 3),
            rule="every asm_*.stl: this frame moved by (-x, -y, -z_mid), then turned 180° about Y (PCB centre at the "
                 "origin, its parts up)"),
        console_opening_mm=dict(top_width=CFG.OPENING_TOP_WIDTH, bottom_width=CFG.OPENING_BOTTOM_WIDTH,
                                height=CFG.OPENING_HEIGHT, bottom_y=round(oy0 - 1.0, 2)),
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
            piezo="pressed into the 3 fingers on the bezel's skin (face on their 2 mm ledges), a dab of RTV on each; "
                  "leads up the right cavity and out through the plate's slot",
            usb_wing="3× M3 × 10 socket cap from inside the bezel's right cavity (before the display goes in), "
                     "VHB on its back to the trim",
            usb_passthrough="2× ALTW USB 3.0 passthroughs with their own hex nuts, tightened on the bench before the "
                            "wing screws onto the bezel (the double-D flats stop them turning)"),
        buzzer=dict(
            part=f"12 V active piezo Ø{geo['buzzer']['d']:g} × {geo['buzzer']['h']:g} mm (MEASURE yours)",
            where=f"in the bezel's right cavity below the display's plugs and the wing's bottom screw, centre "
                  f"{_r2(geo['buzzer']['center'])} mm (right of / above the bezel's centre), held by 3 fingers on the skin",
            fires_through=f"{geo['buzzer']['slots']} right intake slots "
                          f"({geo['buzzer']['open_mm2']:.0f} mm² open), "
                          f"{geo['buzzer']['skin_z'] - geo['buzzer']['face_z']:.1f} mm behind the bezel's skin",
            wiring="J4 (BUZ) on the carrier: pin 3 + and pin 4 - only; the button pins 1-2 stay unused",
            behaviour="blind-spot beeps auto-mute after 4 s (the side LED keeps flashing); a TPMS warning beeps "
                      "twice, then only the screen shows it"),
        usb_passthrough=dict(
            count=2,
            hole=f"2× Ø{geo['usb']['hole_d']:g} mm (v1 CFG.USB_HOLE_DIAMETER) × {geo['usb']['flat_w']:g} mm double-D "
                 f"(measured {geo['usb']['thread_d']:g} thread, {geo['usb']['flat_d']:g} flats), in the wing's end wall",
            faces="the passenger side (+X), stacked vertically at Y = "
                  f"{geo['usb']['axis_ys'][0]:g} and {geo['usb']['axis_ys'][1]:g} mm "
                  f"({abs(geo['usb']['axis_ys'][0] - geo['usb']['axis_ys'][1]):g} mm pitch)",
            wing_mm=_r2([geo["usb"]["wing"][1] - geo["usb"]["wing"][0], geo["usb"]["wing"][3] - geo["usb"]["wing"][2],
                         geo["usb"]["wing"][5] - geo["usb"]["wing"][4]]),
            socket_reach_right_of_bezel_mm=round(geo["usb"]["wing"][1] + geo["usb"]["front"][1] - geo["bx"], 1),
            wing_front_proud_of_bezel_mm=round(geo["usb"]["wing"][5] - geo["usb"]["front_z"], 1),
            cable="the lower cable climbs behind the centre screw post inside the wing; both cables enter the bezel "
                  "through one side opening (hidden by the wing), cross above the display's plugs, and drop through "
                  "the plate's cable slot into the pocket (car USB port + second USB / flush 12 V charger)",
            assembly=["fit BOTH USB passthroughs into the wing on the bench first (double-D flats lock them; tighten "
                      "the nuts with two flats level so they clear the trim, or from outside if rear-mounted)",
                      "bezel face down: feed both plugs through the bezel's side opening (one after the other) and "
                      "screw the wing on with 3× M3 × 10 from inside the right cavity",
                      "fit the piezo and the display, then thread BOTH USB plugs through the plate's cable slot "
                      "FIRST (one after the other), before the display's leads and piezo wires",
                      "fit the plate (6× M3 × 10)"],
            measure=["thread Ø 25.16 mm and double-D flats 23.28 mm (already measured from your caliper photos)",
                     "collar / front flange Ø and thickness (or confirm rear-mounted with front nut)",
                     "socket body Ø and how far it stands out",
                     "body/boot length behind the panel up to where the cable leaves",
                     "nut across corners / flats and thickness", "cable Ø and tightest bend",
                     "the male plug's moulding (w × t × length)",
                     "free flat trim right of the bezel's edge (≥ wing size) and anything in front of it"]),
        parameters={k: v for k, v in P.items()},
        volumes_cm3={k: round(g[k].volume() / 1000, 1) for k in ("bezel", "housing", "lid", "usb_wing")},
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
