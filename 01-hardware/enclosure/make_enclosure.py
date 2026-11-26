#!/usr/bin/env python3
"""3-D printed enclosure for the v2 build: the Official Raspberry Pi 7" Touch Display, the Raspberry Pi 4 on its
back and the 100 x 100 mm carrier PCB in one unit, plus a small wired "alert pod" for the mute button and the
buzzer.

    python 01-hardware/enclosure/make_enclosure.py                    # STLs + report, runs every check
    python 01-hardware/enclosure/make_enclosure.py --mount normal     # cable edge down
    python 01-hardware/enclosure/make_enclosure.py --set PI_SEAT=21.5 BUTTON_D=16.2

Writes stl/print_*.stl (print orientation, for the slicer), stl/asm_*.stl (assembly, used by the viewer) and
enclosure_report.json next to this file. Exits with status 1 if a check fails.

Frame: X to the driver's right, Y up, Z toward the driver. Z = 0 is the front of the display glass, so
everything behind the glass has Z < 0. Millimetres. Requires: pip install manifold3d numpy

Display data: Raspberry Pi 7" display mechanical drawing LMD-D/5624/KIT-LC-V3 rev 003 (front view: origin at the
glass's top-left corner, v down, flat cable leaving the bottom edge). The M3 holes are dimensioned from the outer
frame flange (20.0 from each side), the M2.5 standoffs from the frame body. Pi 4: Raspberry Pi mechanical drawing.
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
    MOUNT="inverted",       # "inverted" = cable edge up (best contrast when you look down at it, see README)
    # display, from the drawing
    GW=192.96, GH=110.76, MODULE_T=5.96,
    M3_U=(34.87, 161.07), M3_V=(21.58, 87.23),
    M25_U=(73.97, 131.97), M25_V=(27.43, 76.43),
    ACTIVE_U=(19.44, 173.52), ACTIVE_V=(11.41, 97.33),
    FPC_U=(83.72, 109.22),
    # Pi 4 stack behind the display
    PI_SEAT=24.0,           # MEASURE: glass front -> top of the display's standoffs (where the Pi's board sits)
    PI_ROT180=0,            # MEASURE: 1 if your Pi sits the other way round (ports to the left, seen from behind)
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
    WALL=2.5, PLATE_T=3.0, LID_T=2.5, LID_GAP=1.5,
    BEZEL_WALL=6.0,         # side walls (screws)
    BEZEL_TOP=4.0,          # top wall: thin, so the bezel is no taller than the console opening
    LIP_T=2.0, LIP_GAP=0.3, GLASS_CLR=0.3, FPC_CLR=2.8, LIP_MARGIN=1.0,
    CHIN_H=10.0, CHIN_SKIN=2.0,
    SLOT_W=2.5,             # every vent slot: the display docs require the boards to be unreachable
    PILOT_D=2.6,            # M3 machine screw driven into plastic (ASA/PETG)
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
    ap.add_argument("--mount", choices=("inverted", "normal"))
    ap.add_argument("--set", nargs="*", default=[], metavar="NAME=VALUE")
    ap.add_argument("--out", default=str(HERE))
    a = ap.parse_args()
    if a.mount:
        P["MOUNT"] = a.mount
    for kv in a.set:
        k, v = kv.split("=", 1)
        if k not in P or not isinstance(P[k], (int, float)):
            sys.exit(f"unknown or non-numeric parameter {k}")
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
    inv = P["MOUNT"] == "inverted"
    f = -1.0 if inv else 1.0
    GW, GH = P["GW"], P["GH"]

    def dxy(u, v):                       # drawing -> physical X, Y
        return f * (u - GW / 2), f * (GH / 2 - v)

    def drect(u0, u1, v0, v1):
        (xa, ya), (xb, yb) = dxy(u0, v0), dxy(u1, v1)
        return min(xa, xb), max(xa, xb), min(ya, yb), max(ya, yb)

    cu, cv = sum(P["M25_U"]) / 2, sum(P["M25_V"]) / 2

    def pxy(xp, yp):
        # Pi 4 local (x toward the USB/Ethernet end, y toward the GPIO header, origin at a board corner). Seen from
        # behind the display the Pi sits the usual way round (GPIO on top, ports to the right): so in the front
        # view x runs to the left. Its hole-pattern centre (32.5, 28) is the display's M2.5 centre; the 58 x 49
        # pattern is symmetric, so the only other way to fit it is turned 180° (PI_ROT180=1).
        k = -1.0 if P["PI_ROT180"] else 1.0
        return dxy(cu - k * (xp - 32.5), cv - k * (yp - 28.0))

    def prect(x0, x1, y0, y1):
        (xa, ya), (xb, yb) = pxy(x0, y0), pxy(x1, y1)
        return min(xa, xb), max(xa, xb), min(ya, yb), max(ya, yb)

    # ---- Z levels (negative = behind the glass)
    z_mb = -P["MODULE_T"]
    z_pb = z_mb - P["PLATE_T"]
    z_pi_bot = -P["PI_SEAT"]
    z_pi_top = z_pi_bot - P["PI_BOARD_T"]
    z_pi_tall = z_pi_top - P["PI_TOP_H"]
    z_pcb_bot = z_pi_tall - P["AIR_GAP"] - P["PCB_PIN_H"]
    z_pcb_top = z_pcb_bot - P["PCB_T"]
    z_comp = z_pcb_top - P["PCB_COMP_H"]
    z_lid_in = z_comp - P["LID_GAP"]
    z_lid_out = z_lid_in - P["LID_T"]
    z_lip0, z_lip1 = P["LIP_GAP"], P["LIP_GAP"] + P["LIP_T"]

    # ---- outlines
    fpc_top = inv                         # the flat cable leaves the glass edge that is on top when inverted
    clr_top = P["FPC_CLR"] if fpc_top else P["GLASS_CLR"]
    clr_bot = P["GLASS_CLR"] if fpc_top else P["FPC_CLR"]
    gx = GW / 2 + P["GLASS_CLR"]
    gy0, gy1 = -(GH / 2 + clr_bot), GH / 2 + clr_top
    bx = gx + P["BEZEL_WALL"]
    by0, by1 = gy0 - P["CHIN_H"], gy1 + P["BEZEL_TOP"]

    # ---- the Pi's port face decides the box
    port_x = pxy(85.0 + P["JACK_OVER"], 28)[0]
    s = 1.0 if port_x > pxy(0, 28)[0] else -1.0          # +1: ports face the driver's right
    xi_port = port_x + s * 0.5
    xi_other = xi_port - s * (P["PCB_W"] + 2 * P["PCB_EDGE"])
    ix0, ix1 = min(xi_port, xi_other), max(xi_port, xi_other)
    iy1 = GH / 2 - 3.4                                    # the box stays behind the glass
    oy0 = by0                                             # box bottom = bezel bottom (the chin feeds it)
    iy0 = oy0 + P["WALL"]
    ox0, ox1, oy1 = ix0 - P["WALL"], ix1 + P["WALL"], iy1 + P["WALL"]
    pcb_x0 = ix0 + P["PCB_EDGE"]
    pcb_x1 = pcb_x0 + P["PCB_W"]
    pcb_y1 = iy1 - P["PCB_EDGE"]
    pcb_y0 = pcb_y1 - P["PCB_W"]
    xpc, ypc = (pcb_x0 + pcb_x1) / 2, (pcb_y0 + pcb_y1) / 2

    def tpl(x, y):                        # fit-template PCB coords (component side, from the top-left) -> X, Y
        return xpc - (x - 50.0), ypc + (50.0 - y)

    holes = [tpl(hx, hy) for hx in (P["PCB_HOLE_IN"], P["PCB_W"] - P["PCB_HOLE_IN"])
             for hy in (P["PCB_HOLE_IN"], P["PCB_W"] - P["PCB_HOLE_IN"])]
    port_side_x, other_side_x = (ox1 + 3.0, ox0 - 3.0) if s > 0 else (ox0 - 3.0, ox1 + 3.0)
    ears = [(port_side_x, oy0 + 10.0), (port_side_x, oy1 - 12.0),      # clear of the USB window
            (other_side_x, (oy0 + oy1) / 2 - 5.0), (other_side_x, oy1 - 4.5)]   # clear of the display's M3 screws
    sma_y = iy1 - P["SMA_FROM_TOP"]
    sma_z = (z_pcb_top + z_lid_in) / 2

    # ================================================================ dummies (what goes inside)
    disp = box(-GW / 2, GW / 2, -GH / 2, GH / 2, z_mb, 0.0)
    fx0, fx1 = sorted(dxy(u, 0)[0] for u in P["FPC_U"])
    edge_y, sgn = (GH / 2, 1.0) if fpc_top else (-GH / 2, -1.0)
    fpc = union([
        box(fx0 - 1, fx1 + 1, edge_y, edge_y + sgn * 2.0, z_mb - 0.5, -0.5),               # wrap round the edge
        box(fx0 - 1, fx1 + 1, edge_y + sgn * 2.0, edge_y - sgn * 40.0, z_mb - 0.6, z_mb),  # along the back frame
    ])
    g["display"] = disp + fpc

    g["pi"] = union([
        box(*prect(0, 85, 0, 56), z_pi_top, z_pi_bot),                                     # board
        box(*prect(0, 85, 0, 56), z_pi_tall, z_pi_top),                                    # everything on top
        box(*prect(64, 85 + P["JACK_OVER"], 1.5, 54.5), z_pi_top - 16.0, z_pi_top),        # USB / Ethernet
        box(*prect(5.2, 17.2, -13.0, 0.0), z_pi_top - 9.0, z_pi_top + 1.0),                # 90° USB-C plug
        box(*prect(-12, 85, -2, 58), z_mb, z_pi_bot),                                      # adapter, standoffs, SD
        box(*prect(-12, 6, 14, 42), z_mb, z_pi_top - 6.0),                                 # DSI ribbon loop
        box(*prect(5, 20, 50, 62), z_mb, z_pi_tall),                                       # display power jumpers
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

    # ================================================================ bezel
    bez = box(-bx, bx, by0, by1, z_mb, z_lip1)
    bez = bez - box(-gx, gx, gy0, gy1, z_mb - 1, z_lip0)                                  # glass pocket
    ax0, ax1, ay0, ay1 = drect(P["ACTIVE_U"][0], P["ACTIVE_U"][1], P["ACTIVE_V"][0], P["ACTIVE_V"][1])
    m = P["LIP_MARGIN"]
    bez = bez - box(ax0 - m, ax1 + m, ay0 - m, ay1 + m, z_lip0 - 1, z_lip1 + 1)           # window
    cy0 = by0 + P["CHIN_SKIN"]
    bez = bez - box(ix0, ix1, cy0, gy0 + 0.01, z_mb - 1, z_lip0)                          # chin cavity -> box
    slot_cy = (cy0 + gy0) / 2
    slots = []
    x = ix0 + 4.0
    while x + P["SLOT_W"] <= ix1 - 4.0:
        slots.append(box(x, x + P["SLOT_W"], slot_cy - 2.6, slot_cy + 2.6, z_lip0 - 1, z_lip1 + 1))
        x += 5.0
    bez = bez - union(slots)
    side_x = gx + P["BEZEL_WALL"] / 2
    chin_y = (by0 + gy0) / 2
    bez_screws = [(-side_x, 30.0), (-side_x, -30.0), (side_x, 30.0), (side_x, -30.0), (-90.0, chin_y), (90.0, chin_y)]
    for X, Y in bez_screws:
        bez = bez - cyl_z(X, Y, z_mb - 1, z_mb + 7.0, P["PILOT_D"])
    g["bezel"] = bez

    # ================================================================ housing: plate + box
    plate = box(-bx, bx, by0, by1, z_pb, z_mb)
    walls = box(ox0, ox1, oy0, oy1, z_lid_in, z_mb)
    ear_solids = []
    for X, Y in ears:
        ear_solids.append(cyl_z(X, Y, z_lid_in, z_pb, 8.0))
        ear_solids.append(box(X, ox0 + 1 if X < ox0 else ox1 - 1, Y - 4.0, Y + 4.0, z_lid_in, z_pb))
    housing = union([plate, walls] + ear_solids)
    housing = housing - box(ix0, ix1, iy0, iy1, z_lid_in - 1, z_mb + 1)                   # inside of the box
    posts = []
    for X, Y in holes:                    # PCB posts, each tied to its two nearest walls
        z0, z1 = z_pcb_bot, z_mb - 0.6
        posts.append(cyl_z(X, Y, z0, z1, 7.0))
        posts.append(box(X, ix0 if X < xpc else ix1, Y - 1.0, Y + 1.0, z0, z1))
        posts.append(box(X - 1.0, X + 1.0, Y, iy0 if Y < ypc else iy1, z0, z1))
    housing = housing + union(posts)
    for X, Y in holes:
        housing = housing - cyl_z(X, Y, z_pcb_bot - 1, z_pcb_bot + 10.0, P["PILOT_D"])
    # flat-cable relief through the plate where the cable wraps round the glass edge
    fy_a, fy_b = (gy1 - 8.0, gy1 + 0.5) if fpc_top else (gy0 - 0.5, gy0 + 8.0)
    housing = housing - box(fx0 - 3, fx1 + 3, fy_a, fy_b, z_pb - 0.6, z_mb + 1)
    m3 = [dxy(u, v) for u in P["M3_U"] for v in P["M3_V"]]
    for X, Y in m3 + bez_screws:          # display M3 screws (heads on the back of the plate), bezel screws
        housing = housing - cyl_z(X, Y, z_pb - 1, z_mb + 1, P["CLEAR_D"])
    for X, Y in ears:
        housing = housing - cyl_z(X, Y, z_lid_in - 1, z_lid_in + 10.0, P["PILOT_D"])
    # USB/Ethernet window in the port-side wall, big enough for the plugs' moulded bodies
    wx0, wx1, wy0, wy1 = prect(64, 85 + P["JACK_OVER"], 1.5, 54.5)
    win_y = (wy0 - 2.5, wy1 + 2.5)
    wall_a, wall_b = (ix1 - 1, ox1 + 1) if s > 0 else (ox0 - 1, ix0 + 1)
    housing = housing - box(wall_a, wall_b, win_y[0], win_y[1], z_pi_top - 18.5, z_pi_top + 1.5)
    # SMA bulkhead for the RG316 antenna lead, in the wall away from the ports, level with the PCB bay
    sw_a, sw_b = (ox0 - 1, ix0 + 1) if s > 0 else (ix1 - 1, ox1 + 1)
    housing = housing - cyl_x(sma_y, sma_z, sw_a, sw_b, P["SMA_D"])
    # AMPS 30 x 38 pattern in the bottom wall, M4 nuts captured in bosses inside (RAM base or a car bracket)
    amps_x0 = (ix0 + ix1) / 2
    amps_z0 = (z_mb + z_lid_in) / 2 - 4.0
    amps = [(amps_x0 + dx, amps_z0 + dz) for dx in (-P["AMPS"][0] / 2, P["AMPS"][0] / 2)
            for dz in (-P["AMPS"][1] / 2, P["AMPS"][1] / 2)]
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
    for dx in (-h, h):
        for dy in (-h, h):
            lid = lid - cyl_z(fan_x + dx, fan_y + dy, z_lid_out - 1, z_lid_in + 1, P["CLEAR_D"])
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

    geo = dict(inv=inv, s=s, bx=bx, by0=by0, by1=by1, gx=gx, gy0=gy0, gy1=gy1,
               box_outer=(ox0, ox1, oy0, oy1), box_inner=(ix0, ix1, iy0, iy1),
               pcb=(pcb_x0, pcb_x1, pcb_y0, pcb_y1), pcb_center=(xpc, ypc),
               z=dict(lip_front=z_lip1, glass=0.0, module_back=z_mb, plate_back=z_pb, pi_seat=z_pi_bot,
                      pi_top=z_pi_top, pi_tall=z_pi_tall, pcb_bottom=z_pcb_bot, pcb_top=z_pcb_top,
                      parts_top=z_comp, lid_inner=z_lid_in, lid_outer=z_lid_out),
               m3=m3, bez_screws=bez_screws, ears=ears, amps=amps, fan=(fan_x, fan_y), sma=(sma_y, sma_z),
               port_window=win_y, pcb_holes=holes, slots=len(slots))
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
        return m.rotate((180, 0, 0)).translate((0, 0, z["module_back"]))
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

    pairs = [("bezel", "display"), ("housing", "display"), ("housing", "pi"), ("housing", "pcb"),
             ("housing", "pcb_parts"), ("housing", "fan"), ("housing", "lid"), ("lid", "pcb_parts"),
             ("lid", "pcb"), ("fan", "pcb_parts"), ("pi", "pcb_parts"), ("pi", "pcb"), ("bezel", "pi"),
             ("sma", "pcb_parts"), ("sma", "housing"), ("bezel", "housing"), ("pod_shell", "pod_button"),
             ("pod_shell", "pod_buzzer"), ("pod_button", "pod_buzzer"), ("pod_shell", "pod_base")]
    for a, b in pairs:
        v = overlap(g[a], g[b])
        check(f"no clash: {a} / {b}", v < 0.05, f"overlap {v:.3f} mm³")

    m3 = geo["m3"]
    xs, ys = sorted({round(p[0], 3) for p in m3}), sorted({round(p[1], 3) for p in m3})
    check("display M3 pattern 126.2 × 65.65 (drawing)",
          abs(xs[1] - xs[0] - 126.2) < 0.01 and abs(ys[1] - ys[0] - 65.65) < 0.01,
          f"{xs[1] - xs[0]:.2f} × {ys[1] - ys[0]:.2f}, flange-referenced")
    ox0, ox1, oy0, oy1 = geo["box_outer"]

    def wall_dist(x, y):                  # distance from a screw axis to the outside of the box (0 if inside it)
        dx = max(ox0 - x, 0.0, x - ox1)
        dy = max(oy0 - y, 0.0, y - oy1)
        return math.hypot(dx, dy)

    d_wall = min(wall_dist(x, y) for x, y in m3)
    d_ear = min(math.hypot(x - ex, y - ey) for x, y in m3 for ex, ey in geo["ears"])
    check("display M3 screws reachable from behind", d_wall >= 3.5 and d_ear >= 10.0,
          f"axis ≥ {d_wall:.1f} mm from the box wall, ≥ {d_ear:.1f} mm from a lid ear (2 mm hex key / #1 driver)")
    ph = geo["pcb_holes"]
    hx, hy = sorted({round(p[0], 3) for p in ph}), sorted({round(p[1], 3) for p in ph})
    check("PCB posts on 92 × 92", abs(hx[1] - hx[0] - 92) < 0.01 and abs(hy[1] - hy[0] - 92) < 0.01,
          f"{hx[1] - hx[0]:.2f} × {hy[1] - hy[0]:.2f}")
    gx, gy0 = geo["gx"], geo["gy0"]
    ok = all((abs(x) > gx + 1.5 or y < gy0 - 1.5) for x, y in geo["bez_screws"])
    check("bezel screws in solid wall", ok, f"{len(geo['bez_screws'])} × M3 into {P['PILOT_D']} mm pilots")
    z = geo["z"]
    gap = z["pi_tall"] - z["pcb_bottom"] - P["PCB_PIN_H"]
    check("air gap Pi -> PCB pins", gap >= P["AIR_GAP"] - 1e-6, f"{gap:.1f} mm")
    check("vent openings finger-safe", P["SLOT_W"] <= 2.5,
          f"{geo['slots']} chin slots {P['SLOT_W']} mm wide; fan grille 2.5 mm gaps")

    # console opening (v1 paper fit): box bottom 1 mm above the opening's bottom edge, glass centred on it
    top, bot, hgt = CFG.OPENING_TOP_WIDTH, CFG.OPENING_BOTTOM_WIDTH, CFG.OPENING_HEIGHT
    y_floor = oy0 - 1.0
    pts = [(ox0, oy0), (ox1, oy0), (ox0, oy1), (ox1, oy1)]
    pts += [(x + d, y) for x, y in geo["ears"] for d in (-4.0, 4.0)]
    wy0, wy1 = geo["port_window"]
    plug_x = ox1 + 15.0 if geo["s"] > 0 else ox0 - 15.0
    sma_x = ox0 - 15.0 if geo["s"] > 0 else ox1 + 15.0
    pts += [(plug_x, wy0), (plug_x, wy1), (sma_x, geo["sma"][0])]
    worst = 1e9
    for x, y in pts:
        hb = y - y_floor
        half = (bot + (top - bot) * min(max(hb, 0), hgt) / hgt) / 2
        worst = min(worst, half - abs(x), hgt - hb)
    check("box, ears, 90° USB plugs and SMA lead fit the console opening", worst >= 0,
          f"tightest margin {worst:.1f} mm (opening {top:g} top / {bot:g} bottom × {hgt:g})")
    bez_h = geo["by1"] - geo["by0"]
    check("bezel no taller than the opening", bez_h <= hgt + 0.5,
          f"bezel {2 * geo['bx']:.1f} × {bez_h:.1f} mm; opening {hgt:g} high, its top edge is under the HVAC")
    return res


# ------------------------------------------------------------------------------------------------- main
COLORS = dict(bezel="#1f2937", housing="#334155", lid="#475569", display="#0b1220", pi="#15803d",
              pcb="#065f46", pcb_parts="#f59e0b", fan="#111827")
LABELS = dict(
    bezel="Bezel: front frame + 10 mm air-intake chin (print face down)",
    housing="Housing: plate the display screws to + rear box for the Pi and the PCB (print plate down)",
    lid="Lid: 30 mm exhaust fan + cable exit (print outside face down)",
    display="Official 7\" Touch Display (dummy)", pi="Raspberry Pi 4, display adapter and cables (dummy)",
    pcb="100 × 100 mm carrier PCB (dummy)", pcb_parts="PCB part-height budget (dummy)", fan="30 mm fan (dummy)")


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
    for name in ("bezel", "housing", "lid", "display", "pi", "pcb", "pcb_parts", "fan"):
        n = write_stl(to_viewer(g[name], geo), stl / f"asm_{name}.stl")
        files[f"asm_{name}"] = dict(file=f"stl/asm_{name}.stl", triangles=n, color=COLORS[name], label=LABELS[name])

    z = geo["z"]
    ox0, ox1, oy0, oy1 = geo["box_outer"]
    behind = z["plate_back"] - z["lid_outer"]
    report = dict(
        generator="01-hardware/enclosure/make_enclosure.py",
        mount=P["MOUNT"],
        overall_mm=dict(width=round(2 * geo["bx"], 2), height=round(geo["by1"] - geo["by0"], 2),
                        depth=round(z["lip_front"] - z["lid_outer"], 2)),
        box_mm=dict(width=round(ox1 - ox0, 2), width_with_ears=round(ox1 - ox0 + 14.0, 2),
                    height=round(oy1 - oy0, 2), behind_plate=round(behind, 2),
                    clear_pocket_depth_needed=round(behind + 2.0 + 3.0, 1)),
        z_levels_mm={k: round(v, 2) for k, v in z.items()},
        ports_face="driver's right (+X)" if geo["s"] > 0 else "driver's left (-X)",
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
            display_to_plate="4× M3 × 6 button head (check how deep the display's threads are first)",
            bezel_to_plate=f"{len(geo['bez_screws'])}× M3 × 10 into {P['PILOT_D']} mm pilots",
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
        for a, b_ in (("×", "x"), ("³", "3"), ("≥", ">="), ("≤", "<="), ("°", " deg"), ("→", "->")):
            t = t.replace(a, b_)
        return t

    w = max(len(c["check"]) for c in checks)
    for c in checks:
        print(asc(f"{'PASS' if c['ok'] else 'FAIL'}  {c['check']:<{w}}  {c['detail']}"))
    o, b = report["overall_mm"], report["box_mm"]
    print(asc(f"\noverall {o['width']} × {o['height']} × {o['depth']} mm ({P['MOUNT']}); box {b['width']} × "
              f"{b['height']} mm, {b['behind_plate']} mm behind the plate; needs ≥ {b['clear_pocket_depth_needed']} mm "
              f"clear pocket depth"))
    print(f"{sum(c['ok'] for c in checks)}/{len(checks)} checks passed -> {out / 'enclosure_report.json'}")
    return 0 if report["all_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
