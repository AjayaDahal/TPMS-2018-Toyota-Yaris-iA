#!/usr/bin/env python3
"""Generate, check, autoroute and export the TPMS v2 carrier PCB (KiCad 10 + Freerouting).

Run with the Python bundled with KiCad (it provides pcbnew):

    "%LOCALAPPDATA%\\Programs\\KiCad10\\bin\\python.exe" build_carrier.py [--no-route] [--no-render] [--passes N]
        [--attempts N] [--reroute] [--route-from FILE.ses]

Inputs: carrier_design.py (circuit, parts, JLCPCB numbers), carrier_layout.py (placement, keep-outs) and
signature_art.json (the back's silkscreen art, from make_signature_art.py).
Steps: libraries -> schematic -> ERC -> netlist -> board + placement (soft parts resolved) -> placement checks ->
GND plane (L2), high-current straps and GND fan-out vias -> Freerouting, then a repair pass on the routed board for
any connection it left behind (cached: a rebuild with the same placement and nets reuses the route) -> power / GND
pours, stitching -> DRC with schematic parity -> Gerbers, drill, JLCPCB BOM + CPL (rotations fitted to JLCPCB's
own footprints), hand-solder list, PDFs, renders.
Requires KiCad 10, Java 21+ and Freerouting 2.x (FREEROUTING_JAR, default
%LOCALAPPDATA%\\Programs\\freerouting\\freerouting-2.5.0.jar). The first run needs internet access to fetch
JLCPCB's footprint data for the CPL fit (cached in jlc_footprints.json afterwards).
"""
import argparse
import copy
import csv
import datetime
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import urllib.request
import uuid
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HW, "scripts"))

import carrier_design as D  # noqa: E402
import carrier_layout as LAY  # noqa: E402
from sexpr import QStr, Sym, dumps, find, find_all, parse, walk  # noqa: E402

import pcbnew  # noqa: E402

NAME = D.PROJECT
PRO = os.path.join(HERE, NAME + ".kicad_pro")
SCH = os.path.join(HERE, NAME + ".kicad_sch")
PCB = os.path.join(HERE, NAME + ".kicad_pcb")
LIBDIR = os.path.join(HERE, "lib")
FPLIB = os.path.join(LIBDIR, "TPMS2.pretty")
SYMLIB = os.path.join(LIBDIR, "TPMS2.kicad_sym")
MODELDIR = os.path.join(LIBDIR, "3d")
BUILD = os.path.join(HERE, "build")
DOCS = os.path.join(HERE, "docs")
PROD = os.path.normpath(os.path.join(HW, "..", "03-manufacturing", "v2_carrier"))
JLC_CACHE = os.path.join(HERE, "jlc_footprints.json")
SIGNATURE_ART = os.path.join(HERE, "signature_art.json")

KICAD_BIN = os.path.dirname(sys.executable)
KICAD_SHARE = os.path.normpath(os.path.join(KICAD_BIN, "..", "share", "kicad"))
KICAD_CLI = os.environ.get("KICAD_CLI") or shutil.which("kicad-cli") or os.path.join(
    KICAD_BIN, "kicad-cli.exe" if os.name == "nt" else "kicad-cli")
_FLATPAK_LIB = "/app/extensions/Library"
SYM_DIR = os.environ.get("KICAD_SYMBOL_DIR") or (
    os.path.join(_FLATPAK_LIB, "symbols") if os.path.isdir(os.path.join(_FLATPAK_LIB, "symbols"))
    else os.path.join(KICAD_SHARE, "symbols"))
FP_DIR = os.environ.get("KICAD_FOOTPRINT_DIR") or (
    os.path.join(_FLATPAK_LIB, "footprints") if os.path.isdir(os.path.join(_FLATPAK_LIB, "footprints"))
    else os.path.join(KICAD_SHARE, "footprints"))
_TOOLS_CACHE = os.path.expanduser("~/.cache/tpms-tools")
_DEFAULT_FR = (os.path.join(_TOOLS_CACHE, "freerouting-2.5.0.jar")
               if os.path.exists(os.path.join(_TOOLS_CACHE, "freerouting-2.5.0.jar"))
               else os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "freerouting", "freerouting-2.5.0.jar"))
FREEROUTING_JAR = os.environ.get("FREEROUTING_JAR", _DEFAULT_FR)
_DEFAULT_JAVA = (os.path.join(_TOOLS_CACHE, "jre25", "bin", "java")
                 if os.path.exists(os.path.join(_TOOLS_CACHE, "jre25", "bin", "java"))
                 else "java")
JAVA = os.environ.get("JAVA", _DEFAULT_JAVA)

TODAY = datetime.date.today().isoformat()
NS = uuid.UUID("2b8f6f0e-5c1d-4d7e-9b3a-7e0c4a51c2d9")
SCH_ROOT_UUID = str(uuid.uuid5(NS, "root-sheet"))
X0, Y0 = 50.0, 50.0                     # board top-left on the KiCad page (mm)
MM = pcbnew.FromMM
LAYERS2 = ("F.Cu", "B.Cu")
SIGNAL_LAYERS = ("F.Cu", "B.Cu")

# net classes: (name, track, clearance, via dia, via drill, nets, routing layers or None = all signal layers).
# The high-current paths are laid as wide straps before routing (carrier_layout.STRAPS); the autorouter only
# adds the branches that carry little current, so every class fits between 0.5 mm-pitch pins without neckdown.
# All vias >= 0.60 / 0.30 mm to stay in JLCPCB's zero-fee 2-layer drill tier.
PWR_HI = ("VIN_RAW", "VIN_FUSED", "12V_RP", "12V_PROT", "12V_BUS", "12V_PIB", "SW_PI", "SW_ESP", "5V_PI_RAW", "5V_PI")
PWR = ("12V_ESPB", "5V_ESP_RAW", "5V_ESP", "DEVKIT_VIN", "POD_BUZP", "POD_BUZN", "LEDL_A", "LEDR_A", "LEDL_K",
       "LEDR_K", "FAN_N", "GPS_5V", "BLKL_IN", "BLKR_IN", "AUX_IN")
NETCLASSES = [("PWR_HI", 0.3, 0.15, 0.6, 0.3, PWR_HI, None),
              ("PWR", 0.25, 0.15, 0.6, 0.3, PWR, None),
              ("GND", 0.3, 0.15, 0.6, 0.3, ("GND",), None)]


def uid(*parts):
    return str(uuid.uuid5(NS, "/".join(str(p) for p in parts)))


def log(msg):
    print(msg, flush=True)


def run(cmd, timeout=900, check=True, cwd=None):
    log("  $ " + " ".join(f'"{c}"' if " " in str(c) else str(c) for c in cmd))
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)
    if check and res.returncode != 0:
        log(res.stdout[-3000:])
        log(res.stderr[-3000:])
        raise RuntimeError(f"command failed ({res.returncode}): {cmd[0]} {cmd[1:3]}")
    return res


def g(v):
    return round(v, 4)


def P(x, y):
    """Board (template) mm -> KiCad VECTOR2I."""
    return pcbnew.VECTOR2I(MM(X0 + x), MM(Y0 + y))


def T(v):
    """KiCad VECTOR2I -> board (template) mm."""
    return pcbnew.ToMM(v.x) - X0, pcbnew.ToMM(v.y) - Y0


# ====================================================================== 3D models (VRML, renders only)
class Wrl:
    def __init__(self):
        self.shapes = []

    def box(self, x0, x1, y0, y1, z0, z1, color):
        X0_, X1_ = min(x0, x1), max(x0, x1)
        Y0_, Y1_ = -max(y0, y1), -min(y0, y1)
        Z0_, Z1_ = min(z0, z1), max(z0, z1)
        v = [(X0_, Y0_, Z0_), (X1_, Y0_, Z0_), (X1_, Y1_, Z0_), (X0_, Y1_, Z0_),
             (X0_, Y0_, Z1_), (X1_, Y0_, Z1_), (X1_, Y1_, Z1_), (X0_, Y1_, Z1_)]
        f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (2, 3, 7, 6), (3, 0, 4, 7), (1, 2, 6, 5)]
        self.shapes.append((v, f, color))

    def save(self, path):
        out = ["#VRML V2.0 utf8"]
        for verts, faces, col in self.shapes:
            pts = ", ".join(f"{x / 2.54:.5f} {y / 2.54:.5f} {z / 2.54:.5f}" for x, y, z in verts)
            idx = ", ".join(" ".join(str(i) for i in fc) + " -1" for fc in faces)
            out.append("Shape {\n  appearance Appearance { material Material { "
                       f"diffuseColor {col[0]:.3f} {col[1]:.3f} {col[2]:.3f} specularColor 0.2 0.2 0.2 "
                       "ambientIntensity 0.3 shininess 0.3 } }\n"
                       f"  geometry IndexedFaceSet {{ coord Coordinate {{ point [ {pts} ] }} coordIndex [ {idx} ] }}\n}}")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(out) + "\n")


BLACK, DARK, SILVER, GOLD = (0.04, 0.04, 0.04), (0.16, 0.16, 0.17), (0.72, 0.72, 0.74), (0.83, 0.68, 0.22)
GREEN, BLUE = (0.05, 0.38, 0.12), (0.07, 0.12, 0.42)


def build_models():
    os.makedirs(MODELDIR, exist_ok=True)
    s = LAY.DEVKIT_ROWS[1]
    w = Wrl()
    for x in (0.0, s):
        w.box(x - 1.27, x + 1.27, -1.27, 36.83, 0, 8.5, BLACK)
        w.box(x - 1.27, x + 1.27, -1.27, 36.83, 8.5, 11.0, BLACK)
    w.box(-1.45, s + 1.45, -7.62, 43.18, 11.0, 12.6, BLUE)
    cx = s / 2
    w.box(cx - 9, cx + 9, -7.62, 17.88, 12.6, 13.4, BLACK)
    w.box(cx - 8.5, cx + 8.5, -1.2, 17.3, 13.4, 15.8, SILVER)
    w.box(cx - 4.0, cx + 4.0, 39.4, 44.2, 12.6, 15.2, SILVER)
    w.save(os.path.join(MODELDIR, "ESP32_DevKit_30pin.wrl"))
    w = Wrl()
    w.box(-1.27, 8.89, -3.81, 1.27, 0, 8.5, BLACK)
    w.box(-1.27, 8.89, -3.81, 1.27, 8.5, 11.0, BLACK)
    w.box(-3.7, 11.3, -28.4, 1.6, 11.0, 12.0, GREEN)
    w.box(1.8, 5.8, -16.0, -12.0, 12.0, 12.9, BLACK)
    w.box(0.6, 7.0, -33.4, -28.4, 7.8, 14.2, GOLD)
    w.box(1.6, 6.0, -39.4, -33.4, 8.8, 13.2, GOLD)
    w.save(os.path.join(MODELDIR, "CC1101_Module.wrl"))


# ====================================================================== symbols
_LIB_CACHE = {}


def load_lib(lib):
    if lib not in _LIB_CACHE:
        with open(os.path.join(SYM_DIR, lib + ".kicad_sym"), encoding="utf-8") as fh:
            tree = parse(fh.read())[0]
        _LIB_CACHE[lib] = {s[1]: s for s in find_all(tree, "symbol")}
    return _LIB_CACHE[lib]


def flatten_symbol(lib, name):
    syms = load_lib(lib)
    child = copy.deepcopy(syms[name])
    ext = find(child, "extends")
    if not ext:
        return child
    parent = flatten_symbol(lib, ext[1])
    child_props = {p[1]: p for p in find_all(child, "property")}
    out = [Sym("symbol"), QStr(name)]
    for item in parent[2:]:
        if isinstance(item, list) and item and item[0] == "property":
            out.append(child_props.pop(item[1], item))
        elif isinstance(item, list) and item and item[0] == "symbol":
            sub = copy.deepcopy(item)
            sub[1] = QStr(name + sub[1][len(parent[1]):])
            out.append(sub)
        else:
            out.append(item)
    for p in child_props.values():
        out.insert(2, p)
    return out


def _font(size=1.27):
    return [Sym("effects"), [Sym("font"), [Sym("size"), size, size]]]


def sym_prop(name, value, x, y, hide=False, justify=None, angle=0):
    node = [Sym("property"), QStr(name), QStr(value), [Sym("at"), g(x), g(y), angle]]
    if hide:
        node.append([Sym("hide"), Sym("yes")])
    eff = _font()
    if justify:
        eff.append([Sym("justify"), Sym(justify)])
    node.append(eff)
    return node


def custom_symbol(name, spec):
    left, right = spec["left"], spec["right"]
    rows = max(len(left), len(right))
    top = g((rows - 1) * 1.27)
    hw = spec["half_width"]
    pins = []
    for side, plist in ((-1, left), (1, right)):
        for i, p in enumerate(plist):
            if p is None:
                continue
            num, pname, etype = p
            pins.append([Sym("pin"), Sym(etype), Sym("line"),
                         [Sym("at"), g(side * (hw + 2.54)), g(top - 2.54 * i), 0 if side < 0 else 180],
                         [Sym("length"), 2.54], [Sym("name"), QStr(pname), _font()],
                         [Sym("number"), QStr(num), _font()]])
    ytop, ybot = top + 2.54, -top - 2.54
    return [Sym("symbol"), QStr(name), [Sym("pin_names"), [Sym("offset"), 1.016]],
            [Sym("exclude_from_sim"), Sym("no")], [Sym("in_bom"), Sym("yes")], [Sym("on_board"), Sym("yes")],
            sym_prop("Reference", spec["ref"], -hw, ytop + 1.27, justify="left"),
            sym_prop("Value", spec["value"], -hw, ybot - 1.27, justify="left"),
            sym_prop("Footprint", spec["footprint"], 0, ybot - 3.81, hide=True),
            sym_prop("Datasheet", "", 0, 0, hide=True),
            sym_prop("Description", spec["description"], 0, 0, hide=True),
            [Sym("symbol"), QStr(name + "_0_1"),
             [Sym("rectangle"), [Sym("start"), -hw, g(ytop)], [Sym("end"), hw, g(ybot)],
              [Sym("stroke"), [Sym("width"), 0.254], [Sym("type"), Sym("default")]],
              [Sym("fill"), [Sym("type"), Sym("background")]]]],
            [Sym("symbol"), QStr(name + "_1_1")] + pins,
            [Sym("embedded_fonts"), Sym("no")]]


def custom_symbols():
    return {name: custom_symbol(name, spec) for name, spec in D.CUSTOM_SYMBOLS.items()}


def write_symbol_library(customs):
    root = [Sym("kicad_symbol_lib"), [Sym("version"), 20251024], [Sym("generator"), QStr("tpms_build")],
            [Sym("generator_version"), QStr("10.0")]] + list(customs.values())
    with open(SYMLIB, "w", encoding="utf-8") as fh:
        fh.write(dumps(root) + "\n")


def symbol_def(lib_id, customs):
    lib, name = lib_id.split(":")
    s = copy.deepcopy(customs[name]) if lib == "TPMS2" else flatten_symbol(lib, name)
    s[1] = QStr(lib_id)
    return s


def symbol_pins(sdef):
    """number -> (x, y, angle, electrical type), library coordinates (y up)."""
    pins = {}
    for p in walk(sdef, "pin"):
        if len(p) > 2 and isinstance(p[1], str) and find(p, "at") is not None:
            at = find(p, "at")
            pins[str(find(p, "number")[1])] = (float(at[1]), float(at[2]), float(at[3]) if len(at) > 3 else 0.0,
                                               str(p[1]))
    return pins


def symbol_props(sdef):
    return {p[1]: p for p in find_all(sdef, "property")}


# ====================================================================== custom footprints
def _stroke(w):
    return [Sym("stroke"), [Sym("width"), w], [Sym("type"), Sym("solid")]]


class Fp:
    def __init__(self, name, descr, attr="through_hole"):
        self.name = name
        self.items = []
        self.head = [Sym("footprint"), QStr(name), [Sym("version"), 20260206], [Sym("generator"), QStr("tpms_build")],
                     [Sym("layer"), QStr("F.Cu")], [Sym("descr"), QStr(descr)], [Sym("tags"), QStr("TPMS2")]]
        self.attr = attr
        self.props = []
        self.n = 0

    def _u(self):
        self.n += 1
        return [Sym("uuid"), QStr(uid("fp", self.name, self.n))]

    def prop(self, name, value, x, y, layer, hide=False, size=1.0):
        node = [Sym("property"), QStr(name), QStr(value), [Sym("at"), g(x), g(y), 0], [Sym("layer"), QStr(layer)]]
        if hide:
            node.append([Sym("hide"), Sym("yes")])
        node += [self._u(), [Sym("effects"), [Sym("font"), [Sym("size"), size, size], [Sym("thickness"), 0.15]]]]
        self.props.append(node)

    def line(self, x1, y1, x2, y2, layer, w=0.12):
        self.items.append([Sym("fp_line"), [Sym("start"), g(x1), g(y1)], [Sym("end"), g(x2), g(y2)], _stroke(w),
                           [Sym("layer"), QStr(layer)], self._u()])

    def rect(self, x1, y1, x2, y2, layer, w=0.12):
        self.items.append([Sym("fp_rect"), [Sym("start"), g(x1), g(y1)], [Sym("end"), g(x2), g(y2)], _stroke(w),
                           [Sym("fill"), Sym("no")], [Sym("layer"), QStr(layer)], self._u()])

    def text(self, s, x, y, layer, size=1.0, rot=0, thick=0.15, justify=None):
        eff = [Sym("effects"), [Sym("font"), [Sym("size"), size, size], [Sym("thickness"), thick]]]
        if justify:
            eff.append([Sym("justify"), Sym(justify)])
        self.items.append([Sym("fp_text"), Sym("user"), QStr(s), [Sym("at"), g(x), g(y), rot],
                           [Sym("layer"), QStr(layer)], self._u(), eff])

    def pad(self, num, x, y, shape="circle", size=1.7, drill=1.0):
        self.items.append([Sym("pad"), QStr(num), Sym("thru_hole"), Sym(shape), [Sym("at"), g(x), g(y)],
                           [Sym("size"), size, size], [Sym("drill"), drill],
                           [Sym("layers"), QStr("*.Cu"), QStr("*.Mask")],
                           [Sym("remove_unused_layers"), Sym("no")], self._u()])

    def smd(self, num, x, y, w, h, shape="roundrect"):
        node = [Sym("pad"), QStr(num), Sym("smd"), Sym(shape), [Sym("at"), g(x), g(y)], [Sym("size"), g(w), g(h)],
                [Sym("layers"), QStr("F.Cu"), QStr("F.Paste"), QStr("F.Mask")]]
        if shape == "roundrect":
            node.append([Sym("roundrect_rratio"), 0.25])
        node.append(self._u())
        self.items.append(node)

    def model(self, path):
        self.items.append([Sym("model"), QStr(path), [Sym("offset"), [Sym("xyz"), 0, 0, 0]],
                           [Sym("scale"), [Sym("xyz"), 1, 1, 1]], [Sym("rotate"), [Sym("xyz"), 0, 0, 0]]])

    def save(self):
        attr = [Sym("attr")] + [Sym(a) for a in self.attr.split()]
        node = self.head + self.props + [attr, [Sym("duplicate_pad_numbers_are_jumpers"), Sym("no")]] + self.items \
            + [[Sym("embedded_fonts"), Sym("no")]]
        with open(os.path.join(FPLIB, self.name + ".kicad_mod"), "w", encoding="utf-8") as fh:
            fh.write(dumps(node) + "\n")


def build_footprints():
    os.makedirs(FPLIB, exist_ok=True)
    esp = D.CUSTOM_SYMBOLS["ESP32_DevKit_30pin"]
    s1, s2 = LAY.DEVKIT_ROWS
    # ---- ESP32 DevKit on two 1x15 sockets. The courtyard covers only the sockets: low parts go underneath.
    f = Fp("ESP32_DevKit_30pin_Sockets",
           "ESP32 DevKit (DOIT V1 style, 30 pins) on 2x 1x15 2.54 mm sockets. The IO23..3V3 row is provided at "
           "0.9 in and 1.0 in; fit the socket on the one matching your board. Parts up to 9 mm may sit under it.")
    f.prop("Reference", "REF**", s2 / 2, -9.6, "F.SilkS")
    f.prop("Value", "ESP32_DevKit_30pin", s2 / 2, 45.2, "F.Fab")
    f.prop("Footprint", "", 0, 0, "F.Fab", hide=True)
    for i in range(15):
        y = 2.54 * i
        f.pad(str(i + 1), 0, y, "rect" if i == 0 else "circle")
        f.pad(str(i + 16), s1, y)
        f.pad(str(i + 16), s2, y)
    for x0_, x1_ in ((-1.27, 1.27), (s1 - 1.27, s2 + 1.27)):
        f.rect(x0_, -1.27, x1_, 36.83, "F.SilkS")
        f.rect(x0_ - 0.25, -1.52, x1_ + 0.25, 37.08, "F.CrtYd", 0.05)
    for bx in (s1, s2):
        f.rect(-1.45, -7.62, bx + 1.45, 43.18, "F.Fab", 0.1)
    f.text("1", 0, -2.4, "F.SilkS", size=1.0)          # above pin 1: left of it is off the board
    f.text("ANTENNA: no copper", s2 / 2, -4.6, "F.Fab", size=1.0)
    f.text("USB", s2 / 2, 41.0, "F.Fab", size=1.0)
    f.text("0.9", s1, 37.6, "F.SilkS", size=1.0)        # staggered so they don't read as one number
    f.text("1.0", s2, 38.6, "F.SilkS", size=1.0)
    f.model("${KIPRJMOD}/lib/3d/ESP32_DevKit_30pin.wrl")
    f.save()
    # ---- CC1101 module socket, E07-M1101D / V2.0 2x4 pinout. Odd pins on the bottom row, the module rises to -y.
    f = Fp("CC1101_2x4_Socket",
           "CC1101 module (E07-M1101D / V2.0, 15 x 30 mm) on a 2x4 2.54 mm socket: 1 GND, 2 VCC, 3 GDO0, 4 CSN, "
           "5 SCK, 6 MOSI, 7 MISO, 8 GDO2. The module and its SMA extend toward -y; low parts may sit under it.")
    f.prop("Reference", "REF**", 3.8, 3.2, "F.SilkS")
    f.prop("Value", "CC1101_315MHz", 3.8, -20.0, "F.Fab")
    f.prop("Footprint", "", 0, 0, "F.Fab", hide=True)
    names = {1: "GND", 2: "VCC", 3: "GDO0", 4: "CSN", 5: "SCK", 6: "MOSI", 7: "MISO", 8: "GDO2"}
    for k in range(4):
        f.pad(str(2 * k + 1), 2.54 * k, 0, "rect" if k == 0 else "circle")
        f.pad(str(2 * k + 2), 2.54 * k, -2.54)
    f.rect(-1.27, -3.81, 8.89, 1.27, "F.SilkS")
    f.rect(-1.52, -4.06, 9.14, 1.52, "F.CrtYd", 0.05)
    f.rect(-3.7, -28.4, 11.3, 1.6, "F.Fab", 0.1)
    f.rect(0.6, -39.4, 7.0, -28.4, "F.Fab", 0.1)
    f.text("SMA", 3.8, -34.0, "F.Fab", size=1.0)
    f.text("1", -2.1, 0.0, "F.SilkS", size=1.0, justify="right")
    f.model("${KIPRJMOD}/lib/3d/CC1101_Module.wrl")
    f.save()
    # ---- LTV-357T: Lite-On land pattern (0.8 mm pads, rows 6.5 mm apart, 2.54 mm pitch), KiCad SOP-4 pin order
    f = Fp("SOP-4_LTV-357T_P2.54mm_Rows6.5mm",
           "Lite-On LTV-357T SOP-4 (body 4.4 x 3.9 mm, 7.0 mm lead span), datasheet land pattern: rows 6.5 mm apart",
           attr="smd")
    f.prop("Reference", "REF**", 0, -3.4, "F.SilkS")
    f.prop("Value", "LTV-357T", 0, 3.4, "F.Fab")
    f.prop("Footprint", "", 0, 0, "F.Fab", hide=True)
    for num, (x, y) in {"1": (-3.25, -1.27), "2": (-3.25, 1.27), "3": (3.25, 1.27), "4": (3.25, -1.27)}.items():
        f.smd(num, x, y, 1.5, 0.8)
    f.rect(-1.95, -2.2, 1.95, 2.2, "F.Fab", 0.1)
    f.line(-1.95, -1.6, -1.35, -2.2, "F.Fab", 0.1)
    f.line(-1.6, -2.32, 1.6, -2.32, "F.SilkS")
    f.line(-1.6, 2.32, 1.6, 2.32, "F.SilkS")
    f.line(-4.2, -2.0, -2.6, -2.0, "F.SilkS")
    f.rect(-4.25, -2.45, 4.25, 2.45, "F.CrtYd", 0.05)
    f.save()


def write_lib_tables():
    with open(os.path.join(HERE, "fp-lib-table"), "w", encoding="utf-8") as fh:
        fh.write('(fp_lib_table\n\t(version 7)\n\t(lib (name "TPMS2")(type "KiCad")(uri "${KIPRJMOD}/lib/TPMS2.pretty")'
                 '(options "")(descr "TPMS v2 carrier footprints"))\n)\n')
    with open(os.path.join(HERE, "sym-lib-table"), "w", encoding="utf-8") as fh:
        fh.write('(sym_lib_table\n\t(version 7)\n\t(lib (name "TPMS2")(type "KiCad")(uri "${KIPRJMOD}/lib/TPMS2.kicad_sym")'
                 '(options "")(descr "TPMS v2 carrier symbols"))\n)\n')


# ====================================================================== project file (JLCPCB 2-layer rules)
def write_project():
    def nc(name, track, clr, vd, vdr, prio):
        return {"name": name, "clearance": clr, "track_width": track, "via_diameter": vd, "via_drill": vdr,
                "microvia_diameter": 0.3, "microvia_drill": 0.1, "diff_pair_gap": 0.25, "diff_pair_via_gap": 0.25,
                "diff_pair_width": 0.2, "bus_width": 12, "wire_width": 6, "line_style": 0,
                "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)", "priority": prio}
    classes = [nc("Default", 0.2, 0.15, 0.6, 0.3, 2147483647)]
    patterns = []
    for i, (name, track, clr, vd, vdr, nets, _layers) in enumerate(NETCLASSES):
        classes.append(nc(name, track, clr, vd, vdr, i))
        patterns += [{"netclass": name, "pattern": n} for n in nets]
    pro = {
        "board": {
            "design_settings": {
                "defaults": {"board_outline_line_width": 0.1, "copper_line_width": 0.2, "copper_text_size_h": 1.5,
                             "copper_text_size_v": 1.5, "copper_text_thickness": 0.3, "courtyard_line_width": 0.05,
                             "fab_line_width": 0.1, "fab_text_size_h": 1.0, "fab_text_size_v": 1.0,
                             "fab_text_thickness": 0.15, "other_line_width": 0.1, "silk_line_width": 0.12,
                             "silk_text_size_h": 1.0, "silk_text_size_v": 1.0, "silk_text_thickness": 0.15,
                             "pads": {"drill": 1.0, "height": 1.7, "width": 1.7}, "zones": {"min_clearance": 0.25}},
                "meta": {"version": 2},
                "rule_severities": {
                    "lib_footprint_issues": "ignore", "lib_footprint_mismatch": "ignore",
                    "footprint_type_mismatch": "ignore", "pth_inside_courtyard": "ignore",
                    "silk_overlap": "warning", "silk_over_copper": "warning", "silk_edge_clearance": "warning",
                    "text_height": "error", "text_thickness": "error", "courtyards_overlap": "error",
                    "missing_courtyard": "ignore", "copper_edge_clearance": "error", "unconnected_items": "error",
                    "footprint_symbol_mismatch": "warning", "isolated_copper": "warning", "starved_thermal": "warning",
                    "via_dangling": "warning", "track_dangling": "warning", "padstack": "ignore",
                    "solder_mask_bridge": "warning"},
                # JLCPCB 2-layer: >= 0.3 mm via drill / >= 0.55 mm pad keeps zero small-hole fee (0.6/0.3 mm used
                # everywhere). Track/space floor 0.15 mm (JLCPCB 2L min 0.127 mm). Hole to hole >= 0.25 mm between
                # vias and >= 0.45 mm wherever a pad hole is involved (.kicad_dru).
                "rules": {"max_error": 0.005, "min_clearance": 0.15, "min_connection": 0.0,
                          "min_copper_edge_clearance": 0.35, "min_hole_clearance": 0.25, "min_hole_to_hole": 0.25,
                          "min_microvia_diameter": 0.2, "min_microvia_drill": 0.1, "min_resolved_spokes": 1,
                          "min_silk_clearance": 0.0, "min_text_height": 1.0, "min_text_thickness": 0.15,
                          "min_through_hole_diameter": 0.3, "min_track_width": 0.15, "min_via_annular_width": 0.13,
                          "min_via_diameter": 0.55, "solder_mask_to_copper_clearance": 0.0,
                          "use_height_for_length_calcs": True},
                "track_widths": [0.0, 0.18, 0.2, 0.25, 0.3, 0.5, 0.8, 1.0, 1.5, 2.0],
                "via_dimensions": [{"diameter": 0.0, "drill": 0.0}, {"diameter": 0.6, "drill": 0.3},
                                   {"diameter": 0.8, "drill": 0.4}],
                "drc_exclusions": [],
                "zones_allow_external_fillets": False,
            },
            "layer_presets": [], "viewports": [], "3dviewports": [],
        },
        "boards": [],
        "erc": {"erc_exclusions": [], "meta": {"version": 0},
                "rule_severities": {"lib_symbol_issues": "ignore", "lib_symbol_mismatch": "ignore",
                                    "footprint_link_issues": "ignore", "endpoint_off_grid": "ignore",
                                    "similar_labels": "warning", "single_global_label": "warning"}},
        "libraries": {"pinned_footprint_libs": [], "pinned_symbol_libs": []},
        "meta": {"filename": NAME + ".kicad_pro", "version": 3},
        "net_settings": {"classes": classes, "meta": {"version": 4}, "net_colors": None,
                         "netclass_assignments": None, "netclass_patterns": patterns},
        "pcbnew": {"last_paths": {}, "page_layout_descr_file": ""},
        "schematic": {"drawing": {"default_line_thickness": 6.0, "default_text_size": 50.0},
                      "legacy_lib_dir": "", "legacy_lib_list": []},
        "sheets": [[SCH_ROOT_UUID, "Root"]],
        "text_variables": {},
    }
    with open(PRO, "w", encoding="utf-8") as fh:
        json.dump(pro, fh, indent=2)
    with open(os.path.splitext(PRO)[0] + ".kicad_dru", "w", encoding="utf-8") as fh:
        fh.write('(version 1)\n'
                 '# JLCPCB: pad holes at least 0.45 mm apart (via holes 0.2 mm; the board floor is 0.25 mm)\n'
                 '(rule "pad hole to hole"\n'
                 '  (constraint hole_to_hole (min 0.45mm))\n'
                 '  (condition "A.Type == \'Pad\' || B.Type == \'Pad\'"))\n')


# ====================================================================== schematic (auto-placed, label-connected)
ROT = {0: lambda x, y: (x, y), 90: lambda x, y: (y, -x), 180: lambda x, y: (-x, -y), 270: lambda x, y: (-y, x)}
BLOCK_TITLES = {
    "1": "12 V INPUT, PROTECTION, 12 V MONITOR", "2": "5V_PI BUCK (Pi + display) AND PI POWER CONTROL",
    "3": "5V_ESP BUCK AND 3.3 V", "4": "ESP32 DEVKIT", "5": "INPUTS: BLINKERS, AUX, BUTTON, ACC SENSE",
    "6": "OUTPUTS: DOOR LEDS, PIEZO, FAN", "7": "CC1101 315 MHz RADIO", "8": "I2C: TEMPERATURE, I/O EXPANDER",
    "9": "PI LINK, GPS", "T": "TEST PADS, MOUNTING HOLES"}


def block_of(ref):
    if ref.startswith(("TP", "H")):
        return "T"
    if ref in ("A1",):
        return "4"
    if ref in ("A2",):
        return "7"
    if ref == "J1":
        return "1"
    if ref in ("J5", "J11"):
        return "2"
    if ref in ("J12", "J13"):
        return "3"
    if ref in ("J2", "J3", "J4", "J8"):
        return "6"
    if ref == "J10":
        return "7"
    if ref == "J9":
        return "8"
    if ref in ("J6", "J7", "J14"):
        return "9"
    m = re.search(r"(\d)\d\d$", ref)
    return m.group(1) if m else "T"


class Schematic:
    def __init__(self, customs):
        self.customs = customs
        self.lib_symbols = {}
        self.items = []
        self.pwr_n = 0
        self.flg_n = 0

    def use(self, lib_id):
        if lib_id not in self.lib_symbols:
            self.lib_symbols[lib_id] = symbol_def(lib_id, self.customs)
        return self.lib_symbols[lib_id]

    def wire(self, x1, y1, x2, y2):
        self.items.append([Sym("wire"), [Sym("pts"), [Sym("xy"), g(x1), g(y1)], [Sym("xy"), g(x2), g(y2)]],
                           [Sym("stroke"), [Sym("width"), 0], [Sym("type"), Sym("default")]],
                           [Sym("uuid"), QStr(uid("w", x1, y1, x2, y2))]])

    def no_connect(self, x, y):
        self.items.append([Sym("no_connect"), [Sym("at"), g(x), g(y)], [Sym("uuid"), QStr(uid("nc", x, y))]])

    def glabel(self, name, x, y, d):
        ang = {(-1, 0): 180, (1, 0): 0, (0, -1): 90, (0, 1): 270}[d]
        just = "left" if ang in (0, 90) else "right"
        eff = [Sym("effects"), [Sym("font"), [Sym("size"), 1.27, 1.27]], [Sym("justify"), Sym(just)]]
        self.items.append([Sym("global_label"), QStr(name), [Sym("shape"), Sym("passive")],
                           [Sym("at"), g(x), g(y), ang], [Sym("fields_autoplaced"), Sym("yes")], eff,
                           [Sym("uuid"), QStr(uid("gl", name, x, y))],
                           [Sym("property"), QStr("Intersheetrefs"), QStr("${INTERSHEET_REFS}"),
                            [Sym("at"), g(x), g(y), ang], [Sym("hide"), Sym("yes")], copy.deepcopy(eff)]])

    def text(self, s, x, y, size=1.27, bold=False):
        font = [Sym("font"), [Sym("size"), size, size]]
        if bold:
            font.append([Sym("bold"), Sym("yes")])
        self.items.append([Sym("text"), QStr(s), [Sym("exclude_from_sim"), Sym("no")], [Sym("at"), g(x), g(y), 0],
                           [Sym("effects"), font, [Sym("justify"), Sym("left"), Sym("top")]],
                           [Sym("uuid"), QStr(uid("txt", s, x, y))]])

    def symbol(self, lib_id, ref, value, footprint, x, y, rot=0, fields=None, dnp=False, power=False, in_bom=True):
        sdef = self.use(lib_id)
        props = symbol_props(sdef)
        su = uid("sym", ref)
        node = [Sym("symbol"), [Sym("lib_id"), QStr(lib_id)], [Sym("at"), g(x), g(y), rot], [Sym("unit"), 1],
                [Sym("exclude_from_sim"), Sym("no")], [Sym("in_bom"), Sym("yes" if in_bom and not power else "no")],
                [Sym("on_board"), Sym("no" if power else "yes")], [Sym("dnp"), Sym("yes" if dnp else "no")],
                [Sym("uuid"), QStr(su)]]

        def prop(name, val, hide):
            p = props.get(name)
            px, py = (float(p[3][1]), float(p[3][2])) if p is not None else (0.0, 0.0)
            ox, oy = ROT[rot](px, -py)
            node_p = [Sym("property"), QStr(name), QStr(val), [Sym("at"), g(x + ox), g(y + oy), 0]]
            if hide:
                node_p.append([Sym("hide"), Sym("yes")])
            eff = copy.deepcopy(find(p, "effects")) if p is not None and find(p, "effects") else _font()
            eff = [e for e in eff if not (isinstance(e, list) and e and e[0] in ("hide", "justify"))]
            node_p.append(eff)
            node.append(node_p)

        prop("Reference", ref, power)
        prop("Value", value, False)
        prop("Footprint", footprint, True)
        prop("Datasheet", "", True)
        desc = props.get("Description")
        prop("Description", str(desc[2]) if desc is not None else "", True)
        for k, v in (fields or {}).items():
            node.append(sym_prop(k, v, x, y, hide=True))
        for num in symbol_pins(sdef):
            node.append([Sym("pin"), QStr(num), [Sym("uuid"), QStr(uid("pin", ref, num))]])
        node.append([Sym("instances"), [Sym("project"), QStr(NAME),
                                        [Sym("path"), QStr("/" + SCH_ROOT_UUID), [Sym("reference"), QStr(ref)],
                                         [Sym("unit"), 1]]]])
        self.items.append(node)
        return sdef

    def power(self, net, x, y, d):
        self.pwr_n += 1
        rot = {(0, 1): 0, (1, 0): 90, (0, -1): 180, (-1, 0): 270}[d]      # power:GND points down at rot 0
        self.symbol("power:" + net, f"#PWR{self.pwr_n:03d}", net, "", x, y, rot, power=True)

    def pwr_flag(self, net, x, y):
        self.flg_n += 1
        self.symbol("power:PWR_FLAG", f"#FLG{self.flg_n:02d}", "PWR_FLAG", "", x, y, 0, power=True)
        self.wire(x, y, x, y + 2.54)
        if net in D.POWER_NETS:
            self.power(net, x, y + 2.54, (0, 1))
        else:
            self.glabel(net, x, y + 2.54, (0, 1))

    def save(self, path, paper):
        title = [Sym("title_block"), [Sym("title"), QStr(D.TITLE)], [Sym("date"), QStr(TODAY)],
                 [Sym("rev"), QStr(D.REV)], [Sym("company"), QStr("Ajaya Dahal")],
                 [Sym("comment"), 1, QStr("100 x 100 mm, 6 layers, JLCPCB Economic PCBA + hand-soldered sockets")],
                 [Sym("comment"), 2, QStr("Generated by 01-hardware/v2/carrier/build_carrier.py from carrier_design.py")]]
        root = [Sym("kicad_sch"), [Sym("version"), 20250610], [Sym("generator"), QStr("eeschema")],
                [Sym("generator_version"), QStr("10.0")], [Sym("uuid"), QStr(SCH_ROOT_UUID)],
                [Sym("paper"), QStr(paper)], title,
                [Sym("lib_symbols")] + [self.lib_symbols[k] for k in sorted(self.lib_symbols)]] + self.items + [
            [Sym("sheet_instances"), [Sym("path"), QStr("/"), [Sym("page"), QStr("1")]]],
            [Sym("embedded_fonts"), Sym("no")]]
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(dumps(root) + "\n")


def _label_len(net):
    return 0.0 if net is None or net in D.POWER_NETS else 2.0 + 0.95 * len(net)


def build_schematic(customs):
    """Parts in block panels, every pin on a short stub with a global label (GND: power symbol)."""
    sch = Schematic(customs)
    grid = 1.27
    colw, sheet_h, top, left = 165.0, 560.0, 28.0, 18.0
    by_block = {}
    for p in D.PARTS:
        by_block.setdefault(block_of(p["ref"]), []).append(p)
    col, cy = 0, top
    power_pins = {}                    # net -> list of electrical types, for the PWR_FLAG pass
    for blk in ("1", "2", "3", "4", "5", "6", "7", "8", "9", "T"):
        parts = by_block.get(blk, [])
        if not parts:
            continue
        # measure each part: rotation (2-pin parts horizontal), extents incl. labels
        items = []
        for p in parts:
            sdef = sch.use(p["sym"])
            pins = symbol_pins(sdef)
            if set(pins) != set(p["pins"]):
                raise ValueError(f"{p['ref']}: pin map {sorted(p['pins'])} != symbol pins {sorted(pins)}")
            rot = 0
            if len(pins) == 2 and all(abs(v[0]) < 1e-6 for v in pins.values()):
                rot = 90
            ext = []
            for num, (px, py, ang, et) in pins.items():
                sx, sy = ROT[rot](px, -py)
                a = math.radians(ang)
                dx, dy = ROT[rot](int(round(-math.cos(a))), int(round(math.sin(a))))
                L = 2.54 + _label_len(p["pins"][num]) + (3.0 if p["pins"][num] in D.POWER_NETS else 0.0)
                ext.append((sx + dx * L, sy + dy * L))
                ext.append((sx, sy))
            xs = [e[0] for e in ext]
            ys = [e[1] for e in ext]
            bx0, bx1 = min(min(xs), -4.0), max(max(xs), 4.0)
            by0, by1 = min(min(ys), -2.0), max(max(ys), 2.0)
            items.append((p, rot, pins, bx0, bx1, by0, by1))
        # shelf-pack inside the column
        need = 12.0
        rows, row, rw, rh = [], [], 0.0, 0.0
        for it in items:
            w, h = it[4] - it[3] + 4.0, it[6] - it[5] + 3.0
            if row and rw + w > colw - 8.0:
                rows.append((row, rh))
                row, rw, rh = [], 0.0, 0.0
            row.append(it)
            rw += w
            rh = max(rh, h)
        if row:
            rows.append((row, rh))
        need += sum(r[1] for r in rows)
        if cy + need > sheet_h and cy > top:
            col += 1
            cy = top
        x_col = left + col * colw
        sch.text(f"{blk if blk != 'T' else ''}{'xx  ' if blk != 'T' else ''}{BLOCK_TITLES[blk]}", x_col, cy, 2.0, True)
        y = cy + 8.0
        for row, rh in rows:
            x = x_col
            for p, rot, pins, bx0, bx1, by0, by1 in row:
                sx = round((x - bx0) / grid) * grid
                sy = round((y - by0) / grid) * grid
                fields = {}
                if p["lcsc"]:
                    fields["LCSC"] = p["lcsc"]
                if p["mpn"]:
                    fields["MPN"] = p["mpn"]
                if p["desc"]:
                    fields["Notes"] = p["desc"]
                in_bom = not p["ref"].startswith(("TP", "H"))
                sch.symbol(p["sym"], p["ref"], p["value"], p["footprint"], sx, sy, rot, fields, dnp=p["dnp"],
                           in_bom=in_bom)
                for num, (px, py, ang, et) in pins.items():
                    ox, oy = ROT[rot](px, -py)
                    a = math.radians(ang)
                    d = ROT[rot](int(round(-math.cos(a))), int(round(math.sin(a))))
                    pxs, pys = sx + ox, sy + oy
                    net = p["pins"][num]
                    if net is None:
                        sch.no_connect(pxs, pys)
                        continue
                    power_pins.setdefault(net, []).append(et)
                    ex, ey = pxs + d[0] * 2.54, pys + d[1] * 2.54
                    sch.wire(pxs, pys, ex, ey)
                    if net in D.POWER_NETS:
                        sch.power(net, ex, ey, d)
                    else:
                        sch.glabel(net, ex, ey, d)
                x += bx1 - bx0 + 4.0
            y += rh
        cy = y + 6.0
    # PWR_FLAG on every net that has power inputs but no power output
    flags = sorted(n for n, types in power_pins.items() if "power_in" in types and "power_out" not in types)
    fx, fy = left + (col + 1) * colw, top
    if fx + 40 > left + 4 * colw:
        fx, fy = left + col * colw + 60, cy
    sch.text("POWER FLAGS (rails driven through passives)", fx, fy, 2.0, True)
    for i, net in enumerate(flags):
        sch.pwr_flag(net, fx + 6 + (i % 4) * 35.56, fy + 10 + (i // 4) * 15.24)
    width = left + (col + 2) * colw
    paper = "A1" if width > 594 else "A2"
    sch.save(SCH, paper)
    return flags


def parse_netlist(path):
    with open(path, encoding="utf-8") as fh:
        tree = parse(fh.read())[0]
    comps = {}
    for c in walk(find(tree, "components"), "comp"):
        ref = str(find(c, "ref")[1])
        fp = find(c, "footprint")
        ts = find(c, "tstamps")
        fields = {}
        fl = find(c, "fields")
        for f in (find_all(fl, "field") if fl else []):
            nm = find(f, "name")
            vals = [x for x in f[1:] if not isinstance(x, list)]
            if nm:
                fields[str(nm[1])] = str(vals[0]) if vals else ""
        comps[ref] = dict(value=str(find(c, "value")[1]), footprint=str(fp[1]) if fp else "",
                          tstamp=str(ts[1]) if ts else "", nets={}, fields=fields)
    for n in walk(find(tree, "nets"), "net"):
        name = str(find(n, "name")[1])
        for node in find_all(n, "node"):
            ref, pin = str(find(node, "ref")[1]), str(find(node, "pin")[1])
            if ref in comps:
                comps[ref]["nets"][pin] = name
    return comps


# ====================================================================== board
def load_footprint(fpid):
    lib, name = fpid.split(":")
    path = FPLIB if lib == "TPMS2" else os.path.join(FP_DIR, lib + ".pretty")
    fp = pcbnew.FootprintLoad(path, name)
    if fp is None:
        raise RuntimeError(f"footprint not found: {fpid}")
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    return fp


def add_seg(board, a, b, layer, w=0.1):
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(P(*a))
    s.SetEnd(P(*b))
    s.SetLayer(layer)
    s.SetWidth(MM(w))
    board.Add(s)


def add_arc(board, start, mid, end, layer, w=0.1):
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(pcbnew.SHAPE_T_ARC)
    s.SetArcGeometry(P(*start), P(*mid), P(*end))
    s.SetLayer(layer)
    s.SetWidth(MM(w))
    board.Add(s)


def outline_points(r=LAY.CORNER_R, n=6, inset=0.0):
    """Board outline polygon, optionally pulled back by `inset` (zones keep off the routed edge)."""
    W, H = LAY.BOARD_W, LAY.BOARD_H
    rr = max(r - inset, 0.2)
    pts = []
    for cx, cy, a0 in ((W - r, r, -90), (W - r, H - r, 0), (r, H - r, 90), (r, r, 180)):
        for i in range(n + 1):
            a = math.radians(a0 + 90 * i / n)
            pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    return pts


EDGE_W = 0.1


def add_outline(board):
    """The board edge, its centre line inset by half the line width: the outer edge of the line, which a fab's
    size detection and KiCad's Gerber job file measure, is then exactly BOARD_W x BOARD_H (100.0, not 100.1, so
    the order stays inside the 100 x 100 mm price tier)."""
    W, H, r = LAY.BOARD_W, LAY.BOARD_H, LAY.CORNER_R
    e = EDGE_W / 2
    q = (r - e) * math.sqrt(0.5)                  # arcs keep their centres, radius r - e: outer corner radius r
    E = pcbnew.Edge_Cuts
    add_seg(board, (r, e), (W - r, e), E, EDGE_W)
    add_seg(board, (W - e, r), (W - e, H - r), E, EDGE_W)
    add_seg(board, (W - r, H - e), (r, H - e), E, EDGE_W)
    add_seg(board, (e, H - r), (e, r), E, EDGE_W)
    add_arc(board, (W - r, e), (W - r + q, r - q), (W - e, r), E, EDGE_W)
    add_arc(board, (W - e, H - r), (W - r + q, H - r + q), (W - r, H - e), E, EDGE_W)
    add_arc(board, (r, H - e), (r - q, H - r + q), (e, H - r), E, EDGE_W)
    add_arc(board, (e, r), (r - q, r - q), (r, e), E, EDGE_W)


def add_text(board, s, x, y, layer=pcbnew.F_SilkS, size=1.0, thick=0.15, justify="center", rot=0):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(s)
    t.SetLayer(layer)
    t.SetTextSize(pcbnew.VECTOR2I(MM(size), MM(size)))
    t.SetTextThickness(MM(thick))
    t.SetPosition(P(x, y))
    if rot:
        t.SetTextAngleDegrees(rot)
    t.SetHorizJustify({"left": pcbnew.GR_TEXT_H_ALIGN_LEFT, "right": pcbnew.GR_TEXT_H_ALIGN_RIGHT,
                       "center": pcbnew.GR_TEXT_H_ALIGN_CENTER}[justify])
    board.Add(t)
    return t


def lset(*layers):
    ls = pcbnew.LSET()
    for layer in layers:
        ls.AddLayer(layer)
    return ls


def copper_layers():
    return (pcbnew.F_Cu, pcbnew.B_Cu)


def add_rule_area(board, rect, layers, name, tracks=True, vias=True, fills=True, footprints=False):
    x0, y0, x1, y1 = rect
    z = pcbnew.ZONE(board)
    z.SetIsRuleArea(True)
    z.SetLayerSet(lset(*layers))
    z.SetZoneName(name)
    z.SetDoNotAllowTracks(tracks)
    z.SetDoNotAllowVias(vias)
    z.SetDoNotAllowZoneFills(fills)
    z.SetDoNotAllowPads(False)
    z.SetDoNotAllowFootprints(footprints)
    ol = z.Outline()
    ol.NewOutline()
    for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        v = P(x, y)
        ol.Append(v.x, v.y)
    board.Add(z)
    return z


def fp_courtyard_boxes(fp):
    """One bounding box (board mm) per courtyard outline of a placed footprint (the DevKit has two)."""
    fp.BuildCourtyardCaches()
    cy = fp.GetCourtyard(pcbnew.F_CrtYd)
    out = []
    for i in range(cy.OutlineCount()):
        bb = cy.Outline(i).BBox()
        (x0, y0), (x1, y1) = T(pcbnew.VECTOR2I(bb.GetLeft(), bb.GetTop())), T(
            pcbnew.VECTOR2I(bb.GetRight(), bb.GetBottom()))
        out.append((x0, y0, x1, y1))
    if not out:
        bb = fp.GetBoundingBox(False)
        (x0, y0), (x1, y1) = T(pcbnew.VECTOR2I(bb.GetLeft(), bb.GetTop())), T(
            pcbnew.VECTOR2I(bb.GetRight(), bb.GetBottom()))
        out.append((x0, y0, x1, y1))
    return out


def fp_courtyard_bbox(fp):
    boxes = fp_courtyard_boxes(fp)
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))


def set_pose(fp, x, y, rot):
    fp.SetOrientationDegrees(0)
    fp.SetPosition(P(x, y))
    if rot:
        fp.SetOrientationDegrees(rot)


def _overlap(a, b, m=0.0):
    return a[0] < b[2] + m and b[0] < a[2] + m and a[1] < b[3] + m and b[1] < a[3] + m


def placement_plan(comps):
    """Fixed + soft + test-pad placements, refs -> (x, y, rot, soft)."""
    plan = {ref: (x, y, r, False) for ref, (x, y, r) in LAY.fixed().items()}
    for ref, (x, y, r) in LAY.soft().items():
        if ref in plan:
            raise ValueError(f"{ref} is both fixed and soft")
        plan[ref] = (x, y, r, True)
    tp_by_net = {}
    for ref, c in comps.items():
        if ref.startswith("TP"):
            tp_by_net.setdefault(c["nets"].get("1"), []).append(ref)
    for net, (x, y) in LAY.TP_AT.items():
        refs = tp_by_net.get(net)
        if not refs:
            raise ValueError(f"no test pad for net {net}")
        plan[refs.pop(0)] = (x, y, 0, True)
    for (x, y), ref in zip(LAY.TP_GND_AT, sorted(tp_by_net.get("GND", []))):
        plan[ref] = (x, y, 0, True)
    missing = sorted(set(comps) - set(plan))
    if missing:
        raise ValueError(f"no placement for: {missing}")
    return plan


def build_board(comps):
    if os.path.exists(PCB):
        os.remove(PCB)
    board = pcbnew.NewBoard(PCB)
    board.SetCopperLayerCount(2)
    ds = board.GetDesignSettings()
    ds.SetBoardThickness(MM(1.6))
    add_outline(board)
    nets = {}
    for c in comps.values():
        for net in c["nets"].values():
            if net not in nets:
                ni = pcbnew.NETINFO_ITEM(board, net)
                board.Add(ni)
                nets[net] = ni
    parts = {p["ref"]: p for p in D.PARTS}
    plan = placement_plan(comps)
    fps = {}
    for ref in sorted(comps):
        c = comps[ref]
        fp = load_footprint(c["footprint"])
        fp.SetReference(ref)
        fp.SetValue(c["value"])
        fp.SetPath(pcbnew.KIID_PATH("/" + c["tstamp"]))
        fp.SetSheetname("/")
        fp.SetSheetfile(NAME + ".kicad_sch")
        p = parts[ref]
        fields = {k: v for k, v in c.get("fields", {}).items() if k not in ("Footprint", "Datasheet") and v}
        fields.update({k: v for k, v in (("LCSC", p["lcsc"]), ("MPN", p["mpn"])) if v})
        for k, v in fields.items():            # the schematic's fields, so the parity check matches
            fp.SetField(k, v)
            f = fp.GetField(k)
            f.SetVisible(False)
            f.SetLayer(pcbnew.F_Fab)
        if p["dnp"]:
            fp.SetDNP(True)
        if fp.GetLocalClearance():
            fp.SetLocalClearance(None)     # TI's PowerPAD footprint asks 0.2 mm; one board-wide rule set instead
        if ref.startswith(("TP", "H")):
            fp.SetExcludedFromBOM(True)
            fp.SetExcludedFromPosFiles(True)
        board.Add(fp)
        for pad in fp.Pads():
            net = c["nets"].get(pad.GetNumber())
            if net:
                pad.SetNet(nets[net])
        fps[ref] = fp
    moves = resolve_placement(board, fps, plan)
    for ref, fp in fps.items():
        fp.Value().SetLayer(pcbnew.F_Fab)
        r = fp.Reference()
        r.SetTextSize(pcbnew.VECTOR2I(MM(1.0), MM(1.0)))
        r.SetTextThickness(MM(0.15))
        r.SetLayer(pcbnew.F_Fab)            # refdes on the fab layer; silkscreen carries block labels
    board.SynchronizeNetsAndNetClasses(True)
    return board, fps, moves


def static_keepouts():
    """Rectangles (board mm) where no part may sit."""
    return [("SMA strip", LAY.SMA_STRIP), ("ESP32 antenna", LAY.ANTENNA_KEEPOUT), ("J5 wire bend", LAY.J5_BEND_STRIP)]


def resolve_placement(board, fps, plan):
    """Fixed parts exactly; soft parts at the nearest free spot (spiral search, 0.2 mm steps, up to 12 mm)."""
    edge = 0.3
    boxes = []
    for ref, (x, y, r, soft) in plan.items():
        if not soft:
            set_pose(fps[ref], x, y, r)
            boxes += [(ref, b) for b in fp_courtyard_boxes(fps[ref])]
    keep = [k[1] for k in static_keepouts()]
    moves = {}
    step, rmax = 0.2, 12.0
    offsets = sorted({(round(i * step, 3), round(j * step, 3)) for i in range(-int(rmax / step), int(rmax / step) + 1)
                      for j in range(-int(rmax / step), int(rmax / step) + 1)
                      if (i * step) ** 2 + (j * step) ** 2 <= rmax ** 2}, key=lambda o: (o[0] ** 2 + o[1] ** 2, o))
    for ref, (x, y, r, soft) in plan.items():
        if not soft:
            continue
        fp = fps[ref]
        found = None
        for rr in (r, (r + 180) % 360, (r + 90) % 360, (r + 270) % 360):
            set_pose(fp, x, y, rr)
            bb = fp_courtyard_bbox(fp)
            near = [b for _, b in boxes if _overlap(b, (bb[0] - rmax, bb[1] - rmax, bb[2] + rmax, bb[3] + rmax))]
            for dx, dy in offsets:
                if found is not None and math.hypot(dx, dy) >= found[0] - 1e-9:
                    break
                c = (bb[0] + dx, bb[1] + dy, bb[2] + dx, bb[3] + dy)
                if c[0] < edge or c[1] < edge or c[2] > LAY.BOARD_W - edge or c[3] > LAY.BOARD_H - edge:
                    continue
                if any(_overlap(c, k) for k in keep):
                    continue
                if any(_overlap(c, b, 0.05) for b in near):
                    continue
                found = (math.hypot(dx, dy), x + dx, y + dy, rr)
                break
            if found is not None and found[0] < 0.01:
                break
        if found is None:
            raise RuntimeError(f"no free spot for {ref} near ({x}, {y})")
        _, fx, fy, fr = found
        set_pose(fp, fx, fy, fr)
        boxes += [(ref, b) for b in fp_courtyard_boxes(fp)]
        if found[0] > 0.05:
            moves[ref] = (round(found[0], 2), round(fx, 2), round(fy, 2), fr)
    return moves


def check_placement(board, fps):
    """Mechanical checks against the enclosure; returns a list of problems."""
    probs = []
    boxes = [(ref, b) for ref, fp in fps.items() for b in fp_courtyard_boxes(fp)]
    for i, (a, ba) in enumerate(boxes):
        for b, bb in boxes[i + 1:]:
            if a != b and _overlap(ba, bb, -0.001):
                probs.append(f"courtyards overlap: {a} / {b}")
    for name, rect in static_keepouts():
        for ref, bb in boxes:
            if _overlap(bb, rect, -0.001):
                probs.append(f"{ref} in the {name} keep-out")
    boxes = {ref: fp_courtyard_bbox(fp) for ref, fp in fps.items()}
    k = LAY.CORNER_KEEP
    corners = [(0, 0, k, k), (LAY.BOARD_W - k, 0, LAY.BOARD_W, k), (0, LAY.BOARD_H - k, k, LAY.BOARD_H),
               (LAY.BOARD_W - k, LAY.BOARD_H - k, LAY.BOARD_W, LAY.BOARD_H)]
    for ref, fp in fps.items():
        if ref.startswith("H"):
            continue
        for pad in fp.Pads():
            if pad.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH) and pad.GetDrillSizeX() > MM(0.5):
                x, y = T(pad.GetPosition())
                if any(c[0] <= x <= c[2] and c[1] <= y <= c[3] for c in corners):
                    probs.append(f"{ref} pad {pad.GetNumber()} (THT) in a corner keep-out at ({x:.1f}, {y:.1f})")
    for ref, h in LAY.HEIGHTS.items():
        bb = {"A1": LAY.DEVKIT_BOARD, "A2": LAY.CC1101_BOARD}.get(ref, boxes.get(ref))
        if bb is None:
            continue
        if h > LAY.FAN_MAX_H and _overlap(bb, LAY.FAN_ZONE, -0.001):
            probs.append(f"{ref} ({h} mm) in the fan zone (max {LAY.FAN_MAX_H} mm)")
        if h > LAY.COAX_MAX_H and _overlap(bb, LAY.COAX_ZONE, -0.001):
            probs.append(f"{ref} ({h} mm) in the antenna-pigtail zone (max {LAY.COAX_MAX_H} mm)")
        if h > LAY.MAX_H:
            probs.append(f"{ref} taller than {LAY.MAX_H} mm")
    return probs


def add_keepouts(board):
    add_rule_area(board, LAY.ANTENNA_KEEPOUT, copper_layers(), "ESP32_ANTENNA_NO_COPPER")
    add_rule_area(board, LAY.SMA_STRIP, (pcbnew.F_Cu,), "SMA_BULKHEAD_NO_PARTS", tracks=False, vias=False,
                  fills=False, footprints=True)


def _silk_obstacles(board, fps):
    """Boxes a silkscreen label must avoid: every pad (+0.15 mm, JLCPCB's pad-to-silk rule) and every
    footprint silkscreen item."""
    boxes = []
    for fp in fps.values():
        for pad in fp.Pads():
            bb = pad.GetBoundingBox()
            (x0, y0), (x1, y1) = T(pcbnew.VECTOR2I(bb.GetLeft(), bb.GetTop())), T(
                pcbnew.VECTOR2I(bb.GetRight(), bb.GetBottom()))
            boxes.append((x0 - 0.15, y0 - 0.15, x1 + 0.15, y1 + 0.15))
        for item in fp.GraphicalItems():
            if item.GetLayer() == pcbnew.F_SilkS:
                bb = item.GetBoundingBox()
                (x0, y0), (x1, y1) = T(pcbnew.VECTOR2I(bb.GetLeft(), bb.GetTop())), T(
                    pcbnew.VECTOR2I(bb.GetRight(), bb.GetBottom()))
                boxes.append((x0, y0, x1, y1))
    return boxes


def add_label(board, s, spots, obstacles, size=1.0):
    """Centred silkscreen text at the first spot whose box clears the obstacles (else the first spot)."""
    w, h = 0.72 * size * len(s) + 0.2, size + 0.2
    for x, y in spots:
        box = (x - w / 2, y - h / 2, x + w / 2, y + h / 2)
        if (box[0] > 0.4 and box[2] < LAY.BOARD_W - 0.4 and box[1] > 0.4 and box[3] < LAY.BOARD_H - 0.4
                and not any(_overlap(box, b) for b in obstacles)):
            break
    else:
        x, y = spots[0]
        box = (x - w / 2, y - h / 2, x + w / 2, y + h / 2)
    obstacles.append(box)
    return add_text(board, s, x, y, size=size)


def add_silkscreen(board, fps):
    obstacles = _silk_obstacles(board, fps)
    add_text(board, f"TPMS v2 carrier {D.REV}", 2.6, 12.6, size=1.0, justify="left")
    add_text(board, "JLCJLCJLCJLC", 2.6, 10.8, size=1.0, justify="left")
    labels = {"J1": ("+12V", "GND", "AUX", "RET"), "J5": ("5V", "GND", "5V", "GND", "5V", "GND")}
    for ref, names in labels.items():
        fp = fps[ref]
        for pad in fp.Pads():
            n = int(pad.GetNumber())
            x, y = T(pad.GetPosition())
            dy = -4.4 if ref == "J1" else 4.6
            add_text(board, names[n - 1], x, y + dy, size=1.0)
    # door ports are "L" / "R": a row of 0603 parts sits right above the connectors (see the README's table)
    for ref, name in (("J2", "L"), ("J3", "R"), ("J4", "BUZ"), ("J6", "PI"), ("J7", "GPS"),
                      ("J8", "FAN"), ("J9", "EXP"), ("J10", "ALT"), ("J11", "EXT 12V"), ("J12", "EXT 5V"),
                      ("J13", "SAFE PWR"), ("J14", "SAFE PI")):
        x0, y0, x1, y1 = fp_courtyard_bbox(fps[ref])
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        w = 0.72 * len(name) + 0.2
        spots = [(cx, y0 - 0.7), (cx, y0 - 1.9), (cx, y1 + 0.7), (x1 + w / 2 + 0.3, cy), (x0 - w / 2 - 0.3, cy),
                 (cx, y0 - 3.1)]
        spots += [(cx + dx, y0 - dy) for dy in (0.7, 1.9, 3.1) for dx in (-2.5, 2.5, -5.0, 5.0)]
        add_label(board, name, spots, obstacles)
    # which way the modules face: a DevKit or a CC1101 plugged in turned round swaps power pins
    ax0, ay0, ax1, ay1 = LAY.ANTENNA_KEEPOUT
    cx0, cy0, cx1, cy1 = LAY.CC1101_BOARD
    add_label(board, "ESP32 ANTENNA END", [((ax0 + ax1) / 2, (ay0 + ay1) / 2 + d) for d in (0, -1.2, 1.2)],
              obstacles)
    add_label(board, "CC1101: SMA END", [((cx0 + cx1) / 2 + dx, cy0 + 1.0 + dy) for dy in (0, 1.2, 2.4, 3.6)
                                         for dx in (0, -2, 2)], obstacles)


def add_signature(board, fps):
    """The back's signature (make_signature_art.py: the AjayaDesign logo over the dedication), mirrored onto B.SilkS
    round LAY.SIGNATURE so it reads the right way round from the back. Board graphics, not a footprint: no BOM or CPL
    line, and the route's fingerprint ignores them, so the copper stays the route of record. Returns the placement
    problems: the art must pass its print check and keep 1 mm from the edge and from every pad open on the back."""
    with open(SIGNATURE_ART, encoding="utf-8") as fh:
        art = json.load(fh)
    w, h = art["size_mm"]
    cx, cy = LAY.SIGNATURE
    x0, y0, x1, y1 = cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2
    probs = [f"signature art: {p} (fix make_signature_art.py and rerun it)" for p in art["checks"]["problems"]]
    if x0 < 1.0 or y0 < 1.0 or x1 > LAY.BOARD_W - 1.0 or y1 > LAY.BOARD_H - 1.0:
        probs.append("signature closer than 1 mm to the board edge")
    for fp in fps.values():
        for pad in fp.Pads():
            if pad.IsOnLayer(pcbnew.B_Mask):
                bb = pad.GetBoundingBox()
                (px0, py0), (px1, py1) = T(pcbnew.VECTOR2I(bb.GetLeft(), bb.GetTop())), T(
                    pcbnew.VECTOR2I(bb.GetRight(), bb.GetBottom()))
                if _overlap((x0, y0, x1, y1), (px0, py0, px1, py1), 1.0):
                    probs.append(f"signature within 1 mm of {fp.GetReference()} pad {pad.GetNumber()}")
    n = 0
    for poly in art["polygons"]:
        sps = pcbnew.SHAPE_POLY_SET()
        sps.NewOutline()
        for x, y in poly["outline"]:
            sps.Append(MM(X0 + x1 - x), MM(Y0 + y0 + y))           # mirrored: read from the back
        for ring in poly["holes"]:
            hole = sps.NewHole()
            for x, y in ring:
                sps.Append(MM(X0 + x1 - x), MM(Y0 + y0 + y), -1, hole)
        sps.Fracture()      # a board polygon keeps one outline: each counter becomes a zero-width slit
        for i in range(sps.OutlineCount()):
            shape = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_POLY)
            shape.SetLayer(pcbnew.B_SilkS)
            shape.SetFilled(True)
            shape.SetWidth(0)
            shape.SetPolyShape(pcbnew.SHAPE_POLY_SET(sps.Outline(i)))
            board.Add(shape)
            n += 1
    log(f"  signature on the back: {w:.1f} x {h:.1f} mm round ({cx}, {cy}), {n} filled polygons")
    return probs


# ====================================================================== routing
def _child_spans(txt, start):
    depth, spans, child, quoted = 0, [], None, False
    for i in range(start, len(txt)):
        c = txt[i]
        if quoted:
            quoted = c != '"'
        elif c == '"':
            quoted = True
        elif c == "(":
            depth += 1
            if depth == 2:
                child = i
        elif c == ")":
            if depth == 2:
                spans.append((child, i + 1))
            depth -= 1
            if depth == 0:
                return spans
    raise RuntimeError("unbalanced DSN section")


def _shuffle_dsn(txt, seed):
    import random
    rng = random.Random(seed)
    for section, movable in (("placement", "(component"), ("network", "(net ")):
        m = re.search(r"\(" + section + r"\b", txt)
        spans = _child_spans(txt, m.start())
        items = [txt[a:b] for a, b in spans]
        moved = [s for s in items if s.startswith(movable)]
        fixed = [s for s in items if not s.startswith(movable)]
        rng.shuffle(moved)
        txt = txt[:spans[0][0]] + "\n    ".join(moved + fixed) + txt[spans[-1][1]:]
    return txt


def _restrict_class_layers(txt):
    """Every class routes on the signal layers only: In1 is the solid GND plane (a class may name its
    own list in NETCLASSES instead)."""
    special = {name: layers for name, *_rest, layers in NETCLASSES if layers}
    starts = list(re.finditer(r"\(class\s+\"?([^\s\"()]+)\"?", txt))
    inserts = []
    for i, m in enumerate(starts):
        end = starts[i + 1].start() if i + 1 < len(starts) else len(txt)
        cm = re.search(r"\(circuit\b", txt[m.end():end])
        if cm:
            layers = special.get(m.group(1), SIGNAL_LAYERS)
            inserts.append((m.end() + cm.end(), "\n        (use_layer " + " ".join(layers) + ")"))
    for pos, s in reversed(inserts):
        txt = txt[:pos] + s + txt[pos:]
    return txt


def _freeroute(dsn, ses, passes):
    if os.path.exists(ses):
        os.remove(ses)
    res = run([JAVA, "-jar", FREEROUTING_JAR, "-de", dsn, "-do", ses, f"--router.autorouter.max_passes={passes}",
               "--router.max_threads=8", "--router.automatic_neckdown=false", "--router.fanout.enabled=false",
               "--gui.enabled=false"],
              timeout=5400, check=False)
    text = res.stdout + res.stderr
    with open(os.path.join(BUILD, "freerouting.log"), "a", encoding="utf-8") as fh:
        fh.write(text)
    m = re.findall(r"Auto-routing stage completed.*?\((\d+) unrouted and (\d+) violations?\)", text)
    if not m or not os.path.exists(ses):
        return None
    pre = re.search(r"Board has (\d+) pre-existing clearance violation", text)
    # pre-existing = a fan-out via beside its own GND pad, which Freerouting counts even on the same net
    return int(m[-1][0]), max(0, int(m[-1][1]) - (int(pre.group(1)) if pre else 0))


def _route_fingerprint(board):
    """What a route depends on, in a stable order and rounded to 10 um: every part, pad (with its net), locked
    track and via, zone and keep-out, the outline and the design rules. KiCad's DSN text can't be the key: its
    exporter orders the pins of a net and the parts of a footprint group differently from run to run."""
    r2 = lambda v: f"{pcbnew.ToMM(v):.2f}"
    rows = []
    for fp in board.GetFootprints():
        x, y = fp.GetPosition()
        rows.append(f"F {fp.GetReference()} {fp.GetFPIDAsString()} {r2(x)} {r2(y)} "
                    f"{fp.GetOrientationDegrees():.1f} {fp.GetLayer()}")
        for pad in fp.Pads():
            bb = pad.GetBoundingBox()
            rows.append(f"P {fp.GetReference()}.{pad.GetNumber()} {pad.GetNetname()} {pad.GetAttribute()} "
                        f"{r2(bb.GetLeft())} {r2(bb.GetTop())} {r2(bb.GetRight())} {r2(bb.GetBottom())} "
                        f"{r2(pad.GetDrillSizeX())}")
    for t in board.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T:
            x, y = t.GetPosition()
            rows.append(f"V {t.GetNetname()} {r2(x)} {r2(y)} {r2(t.GetWidth(pcbnew.F_Cu))} {r2(t.GetDrillValue())} "
                        f"{t.IsLocked()}")
        else:
            (ax, ay), (bx, by) = t.GetStart(), t.GetEnd()
            ends = sorted([(r2(ax), r2(ay)), (r2(bx), r2(by))])
            rows.append(f"T {t.GetNetname()} {t.GetLayer()} {ends} {r2(t.GetWidth())} {t.IsLocked()}")
    for z in board.Zones():
        ol = z.Outline()
        pts = " ".join(f"{r2(ol.CVertex(i).x)},{r2(ol.CVertex(i).y)}" for i in range(ol.TotalVertices()))
        rows.append(f"Z {z.GetNetname()} {list(z.GetLayerSet().Seq())} {z.GetIsRuleArea()} {z.GetDoNotAllowTracks()} "
                    f"{z.GetDoNotAllowVias()} {z.GetAssignedPriority()} {pts}")
    for d in board.GetDrawings():
        if d.GetLayer() == pcbnew.Edge_Cuts:
            bb = d.GetBoundingBox()
            rows.append(f"E {d.GetClass()} {r2(bb.GetLeft())} {r2(bb.GetTop())} {r2(bb.GetRight())} {r2(bb.GetBottom())}")
    with open(PRO, encoding="utf-8") as fh:
        pro = json.load(fh)
    rows.append("R " + json.dumps([pro["board"]["design_settings"]["rules"], pro["net_settings"]["classes"],
                                   pro["net_settings"]["netclass_patterns"]], sort_keys=True))
    dru = os.path.splitext(PRO)[0] + ".kicad_dru"
    if os.path.exists(dru):
        with open(dru, encoding="utf-8") as fh:
            rows.append("D " + fh.read())
    rows.append(f"L {SIGNAL_LAYERS} {NETCLASSES}")
    return hashlib.sha256("\n".join(sorted(rows)).encode("utf-8")).hexdigest()


def autoroute(board, passes, attempts=4, route_from=None, reroute=False):
    """Freerouting with shuffled retries. The best session is cached against a fingerprint of the board
    (placement, footprints, nets, straps, rules): a rebuild that only changes values, text or docs reuses it."""
    os.makedirs(BUILD, exist_ok=True)
    dsn = os.path.join(BUILD, NAME + ".dsn")
    ses = os.path.join(BUILD, NAME + ".ses")
    cache_ses = os.path.join(HERE, NAME + "_route.ses")             # the route of record, committed with the design
    cache_meta = os.path.join(HERE, NAME + "_route.json")
    if os.path.exists(dsn):
        os.remove(dsn)
    if not pcbnew.ExportSpecctraDSN(board, dsn):
        raise RuntimeError("DSN export failed")
    with open(dsn, encoding="utf-8") as fh:
        base = _restrict_class_layers(fh.read())
    digest = _route_fingerprint(board)
    meta = {}
    if os.path.exists(cache_meta):
        with open(cache_meta, encoding="utf-8") as fh:
            meta = json.load(fh)
    if route_from:
        shutil.copyfile(route_from, cache_ses)
        meta = dict(route_key=digest, result=None, source=os.path.basename(route_from))
        with open(cache_meta, "w", encoding="utf-8") as fh:
            json.dump(meta, fh, indent=1)
        log(f"    seeded the route cache from {route_from}")
    if not reroute and meta.get("route_key") == digest and os.path.exists(cache_ses):
        log(f"    reusing the cached route (board unchanged, {digest[:12]})")
        shutil.copyfile(cache_ses, ses)
        if not pcbnew.ImportSpecctraSES(board, ses):
            raise RuntimeError("SES import failed")
        return tuple(meta["result"]) if meta.get("result") else None
    if not os.path.exists(FREEROUTING_JAR):
        raise RuntimeError(f"Freerouting not found: {FREEROUTING_JAR} (set FREEROUTING_JAR)")
    open(os.path.join(BUILD, "freerouting.log"), "w").close()
    tries = [os.path.join(BUILD, f"{NAME}_try{i}.ses") for i in range(1, attempts + 1)]
    finals = [os.path.join(BUILD, f"{NAME}_try{i}_final.ses") for i in range(1, attempts + 1)]
    best = None             # (unconnected by KiCad's count after repair, Freerouting's result, session file)
    for attempt, out in enumerate(tries, 1):
        with open(dsn, "w", encoding="utf-8") as fh:
            fh.write(base if attempt == 1 else _shuffle_dsn(base, attempt))
        result = _freeroute(dsn, out, passes)
        log(f"    attempt {attempt}: " + ("no result" if result is None else
                                          f"{result[0]} unrouted, {result[1]} violations (Freerouting's count)"))
        if result is None or not pcbnew.ImportSpecctraSES(board, out):
            continue
        raw_left = _unconnected(board)
        if best is not None and raw_left > max(25, best[0] + 20):
            log(f"    attempt {attempt}: {raw_left} unconnected (skipping repair, best so far is {best[0]})")
            continue
        kept, left = _repair_route(board, out, passes, rounds=3)
        shutil.copyfile(kept, finals[attempt - 1])
        log(f"    attempt {attempt}: {left} unconnected by KiCad's count")
        if best is None or left < best[0]:
            best = (left, result, finals[attempt - 1])
        if left == 0:
            break
    if best is None:
        raise RuntimeError("Freerouting did not produce a session file")
    shutil.copyfile(best[2], ses)
    if not pcbnew.ImportSpecctraSES(board, ses):
        raise RuntimeError("SES import failed")
    shutil.copyfile(ses, cache_ses)
    with open(cache_meta, "w", encoding="utf-8") as fh:
        json.dump(dict(route_key=digest, result=list(best[1]), kicad_unconnected=best[0], source="freerouting"), fh,
                  indent=1)
    for f in tries + finals + [os.path.join(BUILD, f"{NAME}_repair{i}.ses") for i in (1, 2)]:
        if os.path.exists(f):
            os.remove(f)
    return best[1]


def _unconnected(board):
    board.BuildConnectivity()
    return board.GetConnectivity().GetUnconnectedCount(False)


def _repair_route(board, ses, passes, rounds=2):
    """Freerouting leaves a few connections behind in the crowded spots, and which ones changes from run to run.
    Export the routed board, wiring included, and let Freerouting finish just those (it may rip up and redo its
    own routes; the locked straps and fan-out stay). Keeps whichever session has the fewest unconnected items,
    by KiCad's count. Returns (session file, unconnected)."""
    best_n, best_ses = _unconnected(board), ses
    dsn = os.path.join(BUILD, NAME + "_repair.dsn")
    for rnd in range(1, rounds + 1):
        if best_n == 0:
            break
        log(f"    repair {rnd}: {best_n} connection(s) left; routing them on the routed board")
        if os.path.exists(dsn):
            os.remove(dsn)
        if not pcbnew.ExportSpecctraDSN(board, dsn):
            raise RuntimeError("DSN export failed")
        with open(dsn, encoding="utf-8") as fh:
            txt = _restrict_class_layers(fh.read())
        with open(dsn, "w", encoding="utf-8") as fh:
            fh.write(txt)
        out = os.path.join(BUILD, f"{NAME}_repair{rnd}.ses")
        if _freeroute(dsn, out, passes) is None or not pcbnew.ImportSpecctraSES(board, out):
            log("    repair: no session; keeping the previous route")
            pcbnew.ImportSpecctraSES(board, best_ses)
            break
        n = _unconnected(board)
        log(f"    repair {rnd}: {n} left")
        if n < best_n:
            best_n, best_ses = n, out
        else:
            pcbnew.ImportSpecctraSES(board, best_ses)
            break
    return best_ses, best_n


def normalize_vias(board, min_ring=0.13):
    fixed = 0
    for t in board.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T:
            dia = pcbnew.ToMM(t.GetWidth(pcbnew.F_Cu))
            if dia < 0.6:
                t.SetWidth(MM(0.6))
                dia = 0.6
                fixed += 1
            if pcbnew.ToMM(t.GetDrillValue()) < 0.3:
                t.SetDrill(MM(0.3))
                fixed += 1
            if (dia - pcbnew.ToMM(t.GetDrillValue())) / 2 < min_ring - 1e-6:
                t.SetDrill(MM(round(dia - 2 * min_ring, 2)))
                fixed += 1
    return fixed


# ====================================================================== zones, pours, stitching
def new_zone(board, layer, net, pts, name, prio=0, conn=None, clearance=0.25, min_w=0.2):
    z = pcbnew.ZONE(board)
    z.SetLayer(layer)
    z.SetNet(board.FindNet(net))
    z.SetZoneName(name)
    z.SetLocalClearance(MM(clearance))
    z.SetMinThickness(MM(min_w))
    z.SetThermalReliefGap(MM(0.4))
    z.SetThermalReliefSpokeWidth(MM(0.6))
    z.SetPadConnection(conn if conn is not None else pcbnew.ZONE_CONNECTION_THT_THERMAL)
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    z.SetAssignedPriority(prio)
    ol = z.Outline()
    ol.NewOutline()
    for x, y in pts:
        v = P(x, y)
        ol.Append(v.x, v.y)
    board.Add(z)
    return z


def rect_pts(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def add_gnd_planes(board):
    """2-layer board has no internal GND plane; Freerouting routes GND and outer GND pours fill after routing."""
    return []


# Power pours (outer layers, after routing). Polygons are generous: the fill keeps clear of other nets.
POWER_POURS = [
    ("VIN_RAW", (10.0, 86.0, 18.0, 93.0)),
    ("VIN_FUSED", (2.0, 80.0, 24.5, 86.5)),
    ("12V_RP", (11.0, 72.5, 32.5, 80.0)),
    ("12V_PROT", (0.6, 59.6, 21.5, 66.5)),
    ("12V_BUS", (25.0, 57.0, 66.0, 63.0)),
    ("12V_PIB", (60.5, 47.0, 68.5, 62.5)),
    ("5V_PI_RAW", (51.5, 17.6, 66.0, 31.5)),
    ("5V_PI", (54.5, 2.6, 87.5, 17.4)),
    ("5V_ESP_RAW", (37.5, 50.5, 53.0, 60.0)),
]


def add_power_pours(board):
    """Power pours on F.Cu only. On 2 layers B.Cu is the ground return: a power pour there (as on the 6-layer
    board's L6) cut the Pi buck's input-cap ground and J5's 5 A return off from the bottom ground."""
    return [new_zone(board, pcbnew.F_Cu, net, rect_pts(*rect), f"PWR_{net}_F", prio=10 + i,
                     conn=pcbnew.ZONE_CONNECTION_THT_THERMAL, clearance=0.3, min_w=0.3)
            for i, (net, rect) in enumerate(POWER_POURS)]


# Ground pads of the power stage: each gets its own via(s) straight into the bottom ground, so the bucks' hot loops
# (input caps -> IC -> catch diode) and the 5 A return close through B.Cu even where F.Cu ground is cut by straps.
# (ref, vias per GND pad)
POWER_GND_VIAS = [("C101", 1), ("C102", 1), ("C103", 1), ("C105", 1), ("D101", 2),
                  ("C201", 2), ("C202", 2), ("C203", 2), ("C204", 1), ("D201", 3), ("D203", 1),
                  ("C206", 1), ("C207", 1), ("C208", 1), ("C209", 1), ("C210", 1),
                  ("C301", 2), ("C302", 2), ("C303", 2), ("C304", 1), ("D301", 3), ("D302", 1),
                  ("C306", 1), ("C307", 1), ("C308", 1), ("C309", 1), ("C310", 1)]


def add_power_gnd_vias(board):
    pads, tracks = _copper_items(board)
    obs = Obstacles(board)
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
    ak = LAY.ANTENNA_KEEPOUT
    added, short = 0, []
    for ref, want in POWER_GND_VIAS:
        for pad in fps[ref].Pads():
            if pad.GetNetname() != "GND" or pad.GetDrillSizeX() > 0:
                continue
            bb = pad.GetBoundingBox()
            (x0, y0), (x1, y1) = T(pcbnew.VECTOR2I(bb.GetLeft(), bb.GetTop())), T(
                pcbnew.VECTOR2I(bb.GetRight(), bb.GetBottom()))
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            cands = []
            for d in (0.75, 0.95, 1.2, 1.5, 1.9, 2.4):
                ex0, ey0, ex1, ey1 = x0 - d, y0 - d, x1 + d, y1 + d
                per = 2 * ((ex1 - ex0) + (ey1 - ey0))
                for i in range(int(per / 0.25)):
                    s = i * 0.25
                    for seg, length in ((0, ex1 - ex0), (1, ey1 - ey0), (2, ex1 - ex0), (3, ey1 - ey0)):
                        if s <= length:
                            x, y = [(ex0 + s, ey0), (ex1, ey0 + s), (ex1 - s, ey1), (ex0, ey1 - s)][seg]
                            cands.append((d, math.hypot(x - cx, y - cy), round(x, 3), round(y, 3)))
                            break
                        s -= length
            got = 0
            for _d, _r, x, y in sorted(cands):
                if got >= want:
                    break
                if not (1.2 <= x <= LAY.BOARD_W - 1.2 and 1.2 <= y <= LAY.BOARD_H - 1.2):
                    continue
                if ak[0] - 0.8 < x < ak[2] + 0.8 and ak[1] - 0.8 < y < ak[3] + 0.8:
                    continue
                if not obs.clear(x, y, 0.3, "GND", clr=0.2, drill_r=0.15):
                    continue
                px_, py_ = min(max(x, x0), x1), min(max(y, y0), y1)
                if not _path_clear([(px_, py_), (x, y)], 0.25, "GND", pads, tracks, 0.2):
                    continue
                add_via(board, x, y, "GND", 0.6, 0.3)
                t = pcbnew.PCB_TRACK(board)
                t.SetStart(P(px_, py_)); t.SetEnd(P(x, y)); t.SetWidth(MM(0.5)); t.SetLayer(pcbnew.F_Cu)
                t.SetNet(board.FindNet("GND")); board.Add(t)
                obs.add_via(x, y, 0.3, "GND", 0.15)
                obs.items.append((px_, py_, x, y, 0.25, "GND"))
                tracks.append((px_, py_, x, y, 0.25, "GND", pcbnew.F_Cu))
                got += 1
                added += 1
            if got < want:
                short.append(f"{ref}.{pad.GetNumber()} {got}/{want}")
    return added, short


def add_gnd_pours(board):
    return [new_zone(board, layer, "GND", outline_points(inset=0.5), f"GND_{name}", prio=1, clearance=0.3,
                     min_w=0.25)
            for layer, name in ((pcbnew.F_Cu, "L1"), (pcbnew.B_Cu, "L2"))]


def relieve_hand_soldered_gnd(board):
    """SMD pads join their pours solid (zones: THT_THERMAL). A hand-soldered SMD pad on GND would then sit solid in
    the top GND pour, stitched to four inner GND planes, and an iron couldn't heat it: give those pads spokes. Their
    fan-out via still joins them to the planes. Power-pour pads stay solid for current; those pours are small."""
    hand = {p["ref"] for p in D.PARTS if p["hand"]}
    done = []
    for fp in board.GetFootprints():
        if fp.GetReference() not in hand:
            continue
        for pad in fp.Pads():
            if pad.GetAttribute() == pcbnew.PAD_ATTRIB_SMD and pad.GetNetname() == "GND":
                pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_THERMAL)
                done.append(f"{fp.GetReference()}.{pad.GetNumber()}")
    return sorted(done)


def fill_zones(board):
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())


def _seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


class Obstacles:
    """Fast 'is this via spot clear of other copper' test (tracks, vias, pads) plus drill-to-drill spacing."""

    HOLE_GAP = 0.5                  # drill edge to drill edge, any net (board rule 0.45)

    def __init__(self, board):
        self.items, self.holes = [], []
        for t in board.GetTracks():
            w = t.GetWidth(pcbnew.F_Cu) if t.Type() == pcbnew.PCB_VIA_T else t.GetWidth()
            (ax, ay), (bx, by) = T(t.GetStart()), T(t.GetEnd())
            self.items.append((ax, ay, bx, by, pcbnew.ToMM(w) / 2, t.GetNetname()))
            if t.Type() == pcbnew.PCB_VIA_T:
                self.holes.append((ax, ay, pcbnew.ToMM(t.GetDrillValue()) / 2))
        self.pads = []
        for fp in board.GetFootprints():
            for pad in fp.Pads():
                bb = pad.GetBoundingBox()
                (x0, y0), (x1, y1) = T(pcbnew.VECTOR2I(bb.GetLeft(), bb.GetTop())), T(
                    pcbnew.VECTOR2I(bb.GetRight(), bb.GetBottom()))
                self.pads.append((x0, y0, x1, y1, pad.GetNetname(), pad.GetDrillSizeX() > 0))
                if pad.GetDrillSizeX() > 0:
                    x, y = T(pad.GetPosition())
                    self.holes.append((x, y, pcbnew.ToMM(max(pad.GetDrillSizeX(), pad.GetDrillSizeY())) / 2))

    def clear(self, x, y, r, net, clr=0.3, same_net_ok=True, drill_r=0.2):
        if any(math.hypot(x - hx, y - hy) < hr + drill_r + self.HOLE_GAP for hx, hy, hr in self.holes):
            return False
        for ax, ay, bx, by, hw, n in self.items:
            if same_net_ok and n == net:
                if _seg_dist(x, y, ax, ay, bx, by) < hw + r + 0.05 and (ax, ay) == (bx, by):
                    return False
                continue
            if _seg_dist(x, y, ax, ay, bx, by) < hw + r + clr:
                return False
        for x0, y0, x1, y1, n, tht in self.pads:
            m = r + (clr if n != net or tht else 0.15)
            if x0 - m < x < x1 + m and y0 - m < y < y1 + m:
                return False
        return True

    def add_via(self, x, y, r, net, drill_r=0.2):
        self.items.append((x, y, x, y, r, net))
        self.holes.append((x, y, drill_r))


def add_via(board, x, y, net, d=0.6, drill=0.3):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(P(x, y))
    try:
        v.SetWidth(MM(d))
    except TypeError:
        v.SetWidth(pcbnew.F_Cu, MM(d))
    v.SetDrill(MM(drill))
    v.SetNet(board.FindNet(net))
    board.Add(v)
    return v


def add_exposed_pad_vias(board, fps):
    """Thermal vias in the TPS54560B PowerPADs (4 x 0.60/0.30 mm tented vias, zero small-hole/POFV fee)."""
    n = 0
    for ref in ("U201", "U301"):
        fp = fps[ref]
        rot = fp.GetOrientationDegrees() % 180
        cx, cy = T(fp.GetPosition())
        offs = [(dx, dy) for dx in (-0.55, 0.55) for dy in (-0.85, 0.85)]
        for dx, dy in offs:
            if rot:
                dx, dy = dy, dx
            add_via(board, cx + dx, cy + dy, "GND", 0.6, 0.3).SetLocked(True)
            n += 1
    return n


# ---------------------------------------------------------------------- power straps (before routing)
def _pad_of(fps, spec):
    ref, num = spec.split(".", 1)
    pads = [p for p in fps[ref].Pads() if p.GetNumber() == num]
    if not pads:
        raise ValueError(f"strap end {spec}: no such pad")
    return pads[0]


def _strap_paths(a, b, span=4.0, step=0.25):
    """Candidate polylines from a to b: straight, both L's, and Z's with the middle leg swept across a band."""
    (ax, ay), (bx, by) = a, b
    cands = [[a, b]] if abs(ax - bx) < 1e-6 or abs(ay - by) < 1e-6 else []
    cands += [[a, (bx, ay), b], [a, (ax, by), b]]
    lo = min(ay, by) - span
    for i in range(int(round((abs(ay - by) + 2 * span) / step)) + 1):
        m = lo + i * step
        cands.append([a, (ax, m), (bx, m), b])
    lo = min(ax, bx) - span
    for i in range(int(round((abs(ax - bx) + 2 * span) / step)) + 1):
        m = lo + i * step
        cands.append([a, (m, ay), (m, by), b])

    def clean(path):
        out = [path[0]]
        for p in path[1:]:
            if math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) > 1e-6:
                out.append(p)
        return out

    def length(c):
        return sum(math.hypot(q[0] - p[0], q[1] - p[1]) for p, q in zip(c, c[1:]))

    return sorted((clean(c) for c in cands), key=lambda c: (round(length(c), 3), len(c)))


def _copper_items(board):
    pads = []
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            bb = pad.GetBoundingBox()
            (x0, y0), (x1, y1) = T(pcbnew.VECTOR2I(bb.GetLeft(), bb.GetTop())), T(
                pcbnew.VECTOR2I(bb.GetRight(), bb.GetBottom()))
            tht = pad.GetDrillSizeX() > 0
            pads.append(dict(ref=fp.GetReference(), num=pad.GetNumber(), net=pad.GetNetname(),
                             box=(x0, y0, x1, y1), tht=tht, front=tht or pad.IsOnLayer(pcbnew.F_Cu), pad=pad))
    tracks = []
    for t in board.GetTracks():
        if t.Type() != pcbnew.PCB_VIA_T:
            (ax, ay), (bx, by) = T(t.GetStart()), T(t.GetEnd())
            tracks.append((ax, ay, bx, by, pcbnew.ToMM(t.GetWidth()) / 2, t.GetNetname(), t.GetLayer()))
    return pads, tracks


def _path_clear(path, hw, net, pads, tracks, clr):
    W, H = LAY.BOARD_W, LAY.BOARD_H
    ak = LAY.ANTENNA_KEEPOUT
    m = hw + clr
    for (ax, ay), (bx, by) in zip(path, path[1:]):
        lo_x, hi_x, lo_y, hi_y = min(ax, bx) - m - 0.2, max(ax, bx) + m + 0.2, min(ay, by) - m - 0.2, max(ay, by) + m + 0.2
        near_p = [p["box"] for p in pads if p["front"] and p["net"] != net and p["box"][0] < hi_x
                  and p["box"][2] > lo_x and p["box"][1] < hi_y and p["box"][3] > lo_y]
        near_t = [t for t in tracks if t[5] != net and t[6] == pcbnew.F_Cu and min(t[0], t[2]) - t[4] < hi_x
                  and max(t[0], t[2]) + t[4] > lo_x and min(t[1], t[3]) - t[4] < hi_y and max(t[1], t[3]) + t[4] > lo_y]
        n = max(1, int(math.hypot(bx - ax, by - ay) / 0.05))
        for i in range(n + 1):
            x, y = ax + (bx - ax) * i / n, ay + (by - ay) * i / n
            if not (hw + 0.5 <= x <= W - hw - 0.5 and hw + 0.5 <= y <= H - hw - 0.5):
                return False
            if ak[0] - m < x < ak[2] + m and ak[1] - m < y < ak[3] + m:
                return False
            if any(_rect_dist(b, x, y) < m - 1e-6 for b in near_p):
                return False
            if any(_seg_dist(x, y, t[0], t[1], t[2], t[3]) < m + t[4] - 1e-6 for t in near_t):
                return False
    return True


def lay_straps(board, fps):
    """Lay LAY.STRAPS as locked F.Cu tracks (see carrier_layout.py). Returns (segments, failures).
    A strap with a waypoint list takes exactly that path (a None coordinate repeats the previous point's, or for
    the last waypoint the end pad's); otherwise the shortest clear straight / L / Z path is searched."""
    pads, tracks = _copper_items(board)
    segs, failed = 0, []
    for strap in LAY.STRAPS:
        net, a, b, w = strap[:4]
        pa, pb = _pad_of(fps, a), _pad_of(fps, b)
        for p, spec in ((pa, a), (pb, b)):
            if p.GetNetname() != net:
                raise ValueError(f"strap {net}: {spec} is on {p.GetNetname()}")
        A, B = T(pa.GetPosition()), T(pb.GetPosition())
        if len(strap) > 4:
            pts, prev = [A], A
            for i, (wx, wy) in enumerate(strap[4]):
                ref = B if i == len(strap[4]) - 1 else prev
                prev = (ref[0] if wx is None else wx, ref[1] if wy is None else wy)
                pts.append(prev)
            cands = [pts + [B]]
        else:
            cands = _strap_paths(A, B)
        path = next((c for c in cands if _path_clear(c, w / 2, net, pads, tracks, LAY.STRAP_CLR)), None)
        if path is None:
            failed.append(f"{net} {a} -> {b} ({w} mm)")
            continue
        for (ax, ay), (bx, by) in zip(path, path[1:]):
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(P(ax, ay))
            t.SetEnd(P(bx, by))
            t.SetWidth(MM(w))
            t.SetLayer(pcbnew.F_Cu)
            t.SetNet(board.FindNet(net))
            t.SetLocked(True)
            board.Add(t)
            tracks.append((ax, ay, bx, by, w / 2, net, pcbnew.F_Cu))
            segs += 1
    return segs, failed


# ---------------------------------------------------------------------- GND fan-out (before routing)
FAN_CLR = 0.2           # copper clearance to other nets (a little over the 0.15 class rule)
FAN_HOLE_GAP = 0.5      # drill edge to drill edge
FAN_VIA, FAN_DRILL = 0.6, 0.3
EP_PADS = {("U201", "9"), ("U301", "9")}


def _rect_dist(box, x, y):
    x0, y0, x1, y1 = box
    return math.hypot(max(x0 - x, 0.0, x - x1), max(y0 - y, 0.0, y - y1))


def fanout_gnd(board):
    """On 2 layers, skip pre-locked GND fan-out vias so Freerouting can route F.Cu/B.Cu channels freely."""
    return 0, []
    """Give every SMD GND pad its own short stub + via into the In1 plane (locked, kept by the SES import).

    Freerouting then sees GND as complete and only routes signals and power; each return current gets a
    via next to its pad instead of a long detour. Pads of 1.5 mm^2 or more get two vias, 4 mm^2 three."""
    pads, tracks = _copper_items(board)
    tracks = [t for t in tracks if t[5] != "GND"]
    holes = []
    for p in pads:
        if p["tht"]:
            cx, cy = T(p["pad"].GetPosition())
            holes.append((cx, cy, pcbnew.ToMM(max(p["pad"].GetDrillSizeX(), p["pad"].GetDrillSizeY())) / 2))
    for t in board.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T:
            x, y = T(t.GetPosition())
            holes.append((x, y, pcbnew.ToMM(t.GetDrillValue()) / 2))
    centers = {}
    for p in pads:
        b = p["box"]
        centers.setdefault(p["ref"], []).append(((b[0] + b[2]) / 2, (b[1] + b[3]) / 2))
    r, dr = FAN_VIA / 2, FAN_DRILL / 2
    W, H = LAY.BOARD_W, LAY.BOARD_H
    ak = LAY.ANTENNA_KEEPOUT

    def via_ok(x, y, near, near_t):
        if not (0.8 <= x <= W - 0.8 and 0.8 <= y <= H - 0.8):
            return False
        if ak[0] - r - 0.3 < x < ak[2] + r + 0.3 and ak[1] - r - 0.3 < y < ak[3] + r + 0.3:
            return False
        for q in near:
            d = _rect_dist(q["box"], x, y)
            if q["net"] != "GND":
                if d < r + FAN_CLR - 1e-6:
                    return False
            elif not q["tht"] and d < r + 0.1:
                return False                                   # no via-in-pad on SMD pads
        if any(_seg_dist(x, y, t[0], t[1], t[2], t[3]) < r + t[4] + FAN_CLR - 1e-6 for t in near_t):
            return False
        return all(math.hypot(x - hx, y - hy) >= hr + dr + FAN_HOLE_GAP - 1e-6 for hx, hy, hr in holes)

    def stub_ok(ax, ay, bx, by, hw, own, near, near_t):
        n = max(2, int(math.hypot(bx - ax, by - ay) / 0.04))
        for i in range(n + 1):
            x, y = ax + (bx - ax) * i / n, ay + (by - ay) * i / n
            if any(_seg_dist(x, y, t[0], t[1], t[2], t[3]) < hw + t[4] + FAN_CLR - 1e-6
                   for t in near_t if t[6] == pcbnew.F_Cu):
                return False
            if _rect_dist(own["box"], x, y) <= 1e-9:
                continue                                       # still on its own pad
            for q in near:
                if q["front"] and q["net"] != "GND" and _rect_dist(q["box"], x, y) < hw + FAN_CLR - 1e-6:
                    return False
        return True

    added, failed = 0, []
    for p in pads:
        if p["net"] != "GND" or p["tht"] or not p["front"] or (p["ref"], p["num"]) in EP_PADS:
            continue
        x0, y0, x1, y1 = p["box"]
        px, py = (x0 + x1) / 2, (y0 + y1) / 2
        hx, hy = (x1 - x0) / 2, (y1 - y0) / 2
        area = 4 * hx * hy
        want = 3 if area >= 4.0 else 2 if area >= 1.5 else 1
        tw = max(0.2, min(0.5, 2 * min(hx, hy) - 0.05))
        cs = centers[p["ref"]]
        fx, fy = sum(c[0] for c in cs) / len(cs), sum(c[1] for c in cs) / len(cs)
        vx, vy = px - fx, py - fy
        if abs(vx) < 1e-6 and abs(vy) < 1e-6:
            dirs = [(0, -1), (1, 0), (0, 1), (-1, 0)]
        elif abs(vx) >= abs(vy):
            s = 1 if vx > 0 else -1
            dirs = [(s, 0), (0, -1), (0, 1), (-s, 0)]
        else:
            s = 1 if vy > 0 else -1
            dirs = [(0, s), (-1, 0), (1, 0), (0, -s)]
        near = [q for q in pads if q is not p and _rect_dist(q["box"], px, py) < 5.0]
        near_t = [t for t in tracks if _seg_dist(px, py, t[0], t[1], t[2], t[3]) < 6.0 + t[4]]
        got = 0
        for _ in range(want):
            done = False
            for ux, uy in dirs:
                ext, lat_ext = (hx, hy) if ux else (hy, hx)
                for k in range(9):
                    dist = ext + 0.12 + r + 0.2 * k
                    for lat in (0.0, 0.3, -0.3, 0.6, -0.6, 0.9, -0.9, 1.2, -1.2):
                        if abs(lat) > lat_ext + 0.9:
                            continue
                        x, y = px + ux * dist - uy * lat, py + uy * dist + ux * lat
                        if via_ok(x, y, near, near_t) and stub_ok(px, py, x, y, tw / 2, p, near, near_t):
                            v = add_via(board, x, y, "GND", FAN_VIA, FAN_DRILL)
                            v.SetLocked(True)
                            t = pcbnew.PCB_TRACK(board)
                            t.SetStart(P(px, py))
                            t.SetEnd(P(x, y))
                            t.SetWidth(MM(tw))
                            t.SetLayer(pcbnew.F_Cu)
                            t.SetNet(board.FindNet("GND"))
                            t.SetLocked(True)
                            board.Add(t)
                            holes.append((x, y, dr))
                            pads.append(dict(ref="#via", num="", net="GND", box=(x - r, y - r, x + r, y + r),
                                             tht=True, front=True, pad=None))
                            got += 1
                            added += 1
                            done = True
                            break
                    if done:
                        break
                if done:
                    break
            if not done:
                break
        if got == 0:
            failed.append(f"{p['ref']}.{p['num']}")
    return added, failed


def zone_contains(z, layer, x, y):
    return z.HitTestFilledArea(layer, P(x, y), 0)


def stitch(board, zones_by_layer, net, pitch, region=None, d=0.6, drill=0.3, avoid=()):
    """Vias wherever every listed layer's fill of `net` covers the spot and nothing else is near."""
    obs = Obstacles(board)
    m = d / 2 + 0.5                                   # via ring >= 0.35 mm (rule) + margin from the edge
    x0, y0, x1, y1 = region or (1.5, 1.5, LAY.BOARD_W - 1.5, LAY.BOARD_H - 1.5)
    x0, y0, x1, y1 = max(x0, m), max(y0, m), min(x1, LAY.BOARD_W - m), min(y1, LAY.BOARD_H - m)
    keep = [LAY.ANTENNA_KEEPOUT] + list(avoid)
    added = 0
    y = y0
    while y <= y1:
        x = x0
        while x <= x1:
            if not any(k[0] - 0.6 <= x <= k[2] + 0.6 and k[1] - 0.6 <= y <= k[3] + 0.6 for k in keep):
                if all(any(zone_contains(z, layer, x, y) for z in zs) for layer, zs in zones_by_layer.items()):
                    if obs.clear(x, y, d / 2, net, drill_r=drill / 2):
                        add_via(board, x, y, net, d, drill)
                        obs.add_via(x, y, d / 2, net, drill / 2)
                        added += 1
            x += pitch
        y += pitch
    return added


# ====================================================================== checks & outputs
def kicad_cli(*args, timeout=1200, check=True):
    return run([KICAD_CLI] + list(args), timeout=timeout, check=check)


def run_erc():
    out = os.path.join(BUILD, "erc.json")
    kicad_cli("sch", "erc", "--format", "json", "--severity-all", "-o", out, SCH, check=False)
    with open(out, encoding="utf-8") as fh:
        rep = json.load(fh)
    viol = [v for s in rep.get("sheets", []) for v in s.get("violations", [])]
    errors = [v for v in viol if v.get("severity") == "error"]
    warns = [v for v in viol if v.get("severity") == "warning"]
    log(f"  ERC: {len(errors)} errors, {len(warns)} warnings")
    for v in (errors + warns)[:30]:
        items = "; ".join(i.get("description", "") for i in v.get("items", []))
        log(f"    [{v.get('severity')}] {v.get('type')}: {v.get('description')} -- {items[:160]}")
    return errors, warns


def run_drc():
    out = os.path.join(BUILD, "drc.json")
    kicad_cli("pcb", "drc", "--format", "json", "--severity-all", "--schematic-parity", "-o", out, PCB, check=False)
    with open(out, encoding="utf-8") as fh:
        rep = json.load(fh)
    groups = {"violations": rep.get("violations", []), "unconnected": rep.get("unconnected_items", []),
              "parity": rep.get("schematic_parity", [])}
    summary = {}
    for k, lst in groups.items():
        errs = [v for v in lst if v.get("severity") == "error"]
        warns = [v for v in lst if v.get("severity") == "warning"]
        summary[k] = (len(errs), len(warns))
        log(f"  DRC {k}: {len(errs)} errors, {len(warns)} warnings")
        for v in (errs + warns)[:40]:
            items = "; ".join(i.get("description", "") for i in v.get("items", []))
            log(f"    [{v.get('severity')}] {v.get('type')}: {v.get('description')} -- {items[:170]}")
    return summary


def set_stackup(path):
    """JLCPCB 2-layer 1.6 mm FR-4, 1 oz copper, lead-free HASL, green mask, white silk."""
    with open(path, encoding="utf-8") as fh:
        txt = fh.read()
    if "(stackup" in txt:
        return
    lay = [('"F.SilkS"', '(type "Top Silk Screen") (color "White")'), ('"F.Paste"', '(type "Top Solder Paste")'),
           ('"F.Mask"', '(type "Top Solder Mask") (color "Green") (thickness 0.01)'),
           ('"F.Cu"', '(type "copper") (thickness 0.035)'),
           ('"dielectric 1"', '(type "core") (thickness 1.51) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02)'),
           ('"B.Cu"', '(type "copper") (thickness 0.035)'),
           ('"B.Mask"', '(type "Bottom Solder Mask") (color "Green") (thickness 0.01)'),
           ('"B.Paste"', '(type "Bottom Solder Paste")'), ('"B.SilkS"', '(type "Bottom Silk Screen") (color "White")')]
    stack = "\t\t(stackup\n" + "".join(f"\t\t\t(layer {n} {body})\n" for n, body in lay) + \
        '\t\t\t(copper_finish "HAL lead-free")\n\t\t\t(dielectric_constraints no)\n\t\t)\n'
    txt = re.sub(r"(\(setup\s*\n)", lambda m: m.group(1) + stack, txt, count=1)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(txt)


def export_glb():
    """The assembled board as binary glTF for the viewer (04-viewer, Printed Parts mode): the fitted and hand-soldered
    parts (not DNP), solder mask and silkscreen; origin at the board's centre, glTF Y up. KiCad's glTF export takes
    STEP models only, so the DevKit and the CC1101 (our VRML models in lib/3d) come out as empty nodes named A1 and A2:
    the viewer reads those two .wrl files and fills them in."""
    out = os.path.join(DOCS, NAME + ".glb")
    kicad_cli("pcb", "export", "glb", "--no-dnp", "--subst-models", "--include-soldermask", "--include-silkscreen",
              "--user-origin", f"{X0 + LAY.BOARD_W / 2:g}x{Y0 + LAY.BOARD_H / 2:g}mm", "-f", "-o", out, PCB,
              check=False)
    return out


def export_fab(render=True):
    os.makedirs(PROD, exist_ok=True)
    gdir = os.path.join(PROD, "gerbers")
    os.makedirs(gdir, exist_ok=True)
    for fn in os.listdir(gdir):
        os.remove(os.path.join(gdir, fn))
    kicad_cli("pcb", "export", "gerbers", "-o", gdir + os.sep, "--layers",
              ",".join(LAYERS2) + ",F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts",
              "--subtract-soldermask", "--check-zones", PCB)
    kicad_cli("pcb", "export", "drill", "-o", gdir + os.sep, "--format", "excellon", "--excellon-units", "mm",
              "--excellon-zeros-format", "decimal", "--excellon-oval-format", "alternate", "--excellon-separate-th",
              "--generate-map", "--map-format", "gerberx2", PCB)
    zpath = os.path.join(PROD, NAME + "_gerbers_jlcpcb.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for fn in sorted(os.listdir(gdir)):
            z.write(os.path.join(gdir, fn), fn)
    log(f"  gerber zip: {zpath} ({len(os.listdir(gdir))} files)")
    os.makedirs(DOCS, exist_ok=True)
    kicad_cli("sch", "export", "pdf", "-o", os.path.join(DOCS, NAME + "_schematic.pdf"), SCH)
    kicad_cli("pcb", "export", "pdf", "-o", os.path.join(DOCS, NAME + "_assembly_1to1.pdf"), "--layers",
              "F.Fab,F.SilkS,F.CrtYd,Edge.Cuts", "--mode-single", "--include-border-title", "--sketch-pads-on-fab-layers",
              "--crossout-DNP-footprints-on-fab-layers", "--scale", "1", PCB, check=False)
    kicad_cli("pcb", "export", "pdf", "-o", os.path.join(DOCS, NAME + "_copper_layers.pdf"), "--layers",
              ",".join(LAYERS2), "--common-layers", "Edge.Cuts", "--mode-multipage", "--scale", "0", PCB,
              check=False)
    export_glb()
    if render:
        common = ["--width", "2000", "--height", "1600", "--quality", "high", "--background", "opaque",
                  "--use-board-stackup-colors"]
        kicad_cli("pcb", "render", "-o", os.path.join(DOCS, "render_top.png"), "--side", "top", *common, PCB,
                  timeout=1800)
        kicad_cli("pcb", "render", "-o", os.path.join(DOCS, "render_bottom.png"), "--side", "bottom", *common, PCB,
                  timeout=1800)
        kicad_cli("pcb", "render", "-o", os.path.join(DOCS, "render_iso.png"), "--rotate", "-40,0,25",
                  "--perspective", "--zoom", "0.85", *common, PCB, timeout=1800)


# ---------------------------------------------------------------------- JLCPCB BOM + CPL
_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                     "Chrome/120 Safari/537.36"}


def _fetch_easyeda(code):
    url = f"https://easyeda.com/api/products/{code}/components?version=6.5.39"
    with urllib.request.urlopen(urllib.request.Request(url, headers=_UA), timeout=40) as r:
        res = json.load(r)["result"]
    ds = res["packageDetail"]["dataStr"]
    hx, hy = float(ds["head"]["x"]), float(ds["head"]["y"])
    pads = []
    for s in ds["shape"]:
        if s.startswith("PAD"):
            f = s.split("~")
            pads.append([f[8], round((float(f[2]) - hx) * 0.254, 4), round((float(f[3]) - hy) * 0.254, 4)])
    names = {}
    for s in (res.get("dataStr") or {}).get("shape", []):
        if s.startswith("P~"):
            segs = s.split("^^")
            num = segs[0].split("~")[3]
            try:
                names[num] = segs[3].split("~")[4]
            except IndexError:
                names[num] = ""
    return {"title": res.get("title"), "package": res["packageDetail"].get("title"), "pads": pads, "names": names}


def jlc_footprints(codes):
    cache = {}
    if os.path.exists(JLC_CACHE):
        with open(JLC_CACHE, encoding="utf-8") as fh:
            cache = json.load(fh)
    changed = False
    for code in sorted(codes):
        if code not in cache:
            log(f"  fetching JLCPCB footprint data for {code}")
            cache[code] = _fetch_easyeda(code)
            changed = True
    if changed:
        with open(JLC_CACHE, "w", encoding="utf-8") as fh:
            json.dump(cache, fh, indent=1, sort_keys=True)
    return cache


POLARITY = {"Device:LED": ("K", "A"), "Device:D": ("K", "A"), "Device:D_Schottky": ("K", "A"),
            "Device:D_Zener": ("K", "A")}


def _pad_centres(pads):
    acc = {}
    for num, x, y in pads:
        acc.setdefault(num, []).append((x, y))
    return {n: (sum(p[0] for p in v) / len(v), sum(p[1] for p in v) / len(v)) for n, v in acc.items()}


def fit_rotation(kicad_pads, jlc, sym):
    """Rotation phi (deg CCW) and offset t (y-up mm) with Rot(phi) * jlc + t ~ kicad, matched by pad function."""
    kp = _pad_centres(kicad_pads)
    jp = _pad_centres([[n, x, y] for n, x, y in jlc["pads"]])
    pairs = []
    if sym in POLARITY:
        alias = {"+": "A", "ANODE": "A", "-": "K", "−": "K", "CATHODE": "K", "C": "K"}
        names = {}
        for k, v in jlc["names"].items():
            v = v.strip().upper()
            names[alias.get(v, v)] = k
        k_num, a_num = names.get("K"), names.get("A")
        if k_num is None or a_num is None:
            if set(jlc["names"].values()) != {"1", "2"}:  # unknown names on a polarised part: don't guess
                raise SystemExit(f"polarity: can't tell anode from cathode in JLC footprint names {jlc['names']}")
            k_num, a_num = "1", "2"                    # bidirectional TVS (pads named 1/2): either way
        pairs = [[("1", k_num), ("2", a_num)]]
    else:
        common = sorted(set(kp) & set(jp))
        pairs = [[(n, n) for n in common]]
        if sym != "Device:C_Polarized" and len(kp) == 2 and len(jp) == 2 and set(kp) == {"1", "2"} and set(jp) == {"1", "2"}:
            pairs.append([("1", "2"), ("2", "1")])     # unpolarised: either way round
    best = None
    for pr in pairs:
        if len(pr) < 2:
            continue
        K = [(kp[a][0], -kp[a][1]) for a, _ in pr]
        J = [(jp[b][0], -jp[b][1]) for _, b in pr]
        for phi in (0, 90, 180, 270):
            c, s = round(math.cos(math.radians(phi))), round(math.sin(math.radians(phi)))
            RJ = [(c * x - s * y, s * x + c * y) for x, y in J]
            tx = sum(k[0] - r[0] for k, r in zip(K, RJ)) / len(K)
            ty = sum(k[1] - r[1] for k, r in zip(K, RJ)) / len(K)
            err = math.sqrt(sum((r[0] + tx - k[0]) ** 2 + (r[1] + ty - k[1]) ** 2 for k, r in zip(K, RJ)) / len(K))
            if best is None or err < best[0] - 1e-6:
                best = (err, phi, (tx, ty))
    return best


def write_jlc_files(board):
    os.makedirs(PROD, exist_ok=True)
    parts = {p["ref"]: p for p in D.PARTS}
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
    assembled = [r for r, p in parts.items() if p["lcsc"] and not p["dnp"] and not p["hand"]]
    lib = jlc_footprints({parts[r]["lcsc"] for r in assembled})
    rows, issues = [], []
    for ref in sorted(assembled, key=lambda r: (re.match(r"[A-Z]+", r).group(0), int(re.search(r"\d+", r).group(0)))):
        p = parts[ref]
        fp = fps[ref]
        fresh = load_footprint(p["footprint"])
        kpads = [[pd.GetNumber(), pcbnew.ToMM(pd.GetPosition().x), pcbnew.ToMM(pd.GetPosition().y)]
                 for pd in fresh.Pads() if pd.GetNumber()]
        err, phi, (tx, ty) = fit_rotation(kpads, lib[p["lcsc"]], p["sym"])
        if err > 0.35:
            issues.append(f"{ref} ({p['lcsc']}, {lib[p['lcsc']]['package']}): pad fit error {err:.2f} mm")
        a = fp.GetOrientationDegrees()
        x, y = T(fp.GetPosition())
        X, Y = X0 + x, -(Y0 + y)                       # Gerber frame (y up)
        ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
        wx, wy = X + ca * tx - sa * ty, Y + sa * tx + ca * ty
        rows.append(dict(ref=ref, x=wx, y=wy, rot=(a + phi) % 360, fit=err, lcsc=p["lcsc"], value=p["value"],
                         fp=p["footprint"].split(":")[1]))
    with open(os.path.join(PROD, NAME + "_cpl_jlcpcb.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for r in rows:
            w.writerow([r["ref"], f"{r['x']:.3f}mm", f"{r['y']:.3f}mm", "Top", f"{r['rot']:.0f}"])
    groups = {}
    for r in rows:
        groups.setdefault((r["lcsc"], r["value"], r["fp"]), []).append(r["ref"])
    with open(os.path.join(PROD, NAME + "_bom_jlcpcb.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #", "Qty", "Library"])
        for (code, value, fpn), refs in sorted(groups.items(), key=lambda kv: kv[1][0]):
            mpn = D.MPN.get(code, "")
            w.writerow([f"{value} {mpn}".strip(), ",".join(refs), fpn, code, len(refs),
                        "extended" if code in D.EXTENDED else ("preferred" if code in D.PREFERRED else "basic")])
    with open(os.path.join(PROD, NAME + "_hand_solder_and_dnp.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Designator", "What", "Buy / fit", "Notes"])
        for ref, p in sorted(parts.items()):
            if p["hand"]:
                w.writerow([ref, p["value"], p["mpn"], p["desc"]])
        for ref, p in sorted(parts.items()):
            if p["dnp"]:
                w.writerow([ref, f"DNP {p['value']}", "not fitted (rework option)", p["desc"]])
    log(f"  JLCPCB BOM: {len(groups)} lines, {len(rows)} placements; CPL fit worst "
        f"{max(r['fit'] for r in rows):.2f} mm")
    for s in issues:
        log("  !! " + s)
    return rows, issues


# ====================================================================== main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-route", action="store_true", help="place and check only")
    ap.add_argument("--no-render", action="store_true", help="skip 3D renders")
    ap.add_argument("--passes", type=int, default=120, help="Freerouting max passes")
    ap.add_argument("--attempts", type=int, default=4,
                    help="Freerouting runs (shuffled order) until one leaves nothing unconnected after the repair pass")
    ap.add_argument("--reroute", action="store_true", help="ignore the cached route and run Freerouting")
    ap.add_argument("--route-from", metavar="SES", help="import this Specctra session instead of routing "
                                                        "(and cache it for this placement)")
    args = ap.parse_args()
    import faulthandler
    faulthandler.dump_traceback_later(7200, exit=True)
    for d in (LIBDIR, FPLIB, MODELDIR, BUILD, DOCS, PROD):
        os.makedirs(d, exist_ok=True)

    log("[1/9] libraries")
    customs = custom_symbols()
    write_symbol_library(customs)
    build_footprints()
    build_models()
    write_lib_tables()

    log("[2/9] project + schematic + ERC")
    write_project()
    flags = build_schematic(customs)
    log(f"  power flags: {', '.join(flags)}")
    errors, _ = run_erc()
    if errors:
        raise SystemExit("ERC errors - fix carrier_design.py first")
    netfile = os.path.join(BUILD, NAME + ".net")
    kicad_cli("sch", "export", "netlist", "--format", "kicadsexpr", "-o", netfile, SCH)
    comps = parse_netlist(netfile)
    log(f"  netlist: {len(comps)} components, {len({n for c in comps.values() for n in c['nets'].values()})} nets")

    log("[3/9] board + placement")
    board, fps, moves = build_board(comps)
    for ref, (d, x, y, r) in sorted(moves.items(), key=lambda kv: -kv[1][0]):
        if d > 3.0:
            log(f"  soft part moved {d:.1f} mm: {ref} -> ({x}, {y}) rot {r}")
    log(f"  soft parts moved: {len(moves)} (>3 mm: {sum(1 for m in moves.values() if m[0] > 3.0)})")
    probs = check_placement(board, fps)
    for s in probs:
        log("  !! " + s)
    add_keepouts(board)
    add_silkscreen(board, fps)
    sig_probs = add_signature(board, fps)
    for s in sig_probs:
        log("  !! " + s)
    probs += sig_probs
    add_gnd_planes(board)
    n_strap, strap_failed = lay_straps(board, fps)
    log(f"  power straps: {len(LAY.STRAPS) - len(strap_failed)}/{len(LAY.STRAPS)} laid ({n_strap} segments)")
    for s in strap_failed:
        log(f"  !! no clear path for strap {s}")
    probs += [f"no clear path for strap {s}" for s in strap_failed]
    n_ep = add_exposed_pad_vias(board, fps)
    n_fan, fan_failed = fanout_gnd(board)
    log(f"  GND fan-out: {n_fan} vias (+{n_ep} in the PowerPADs); pads left to the router: "
        f"{', '.join(fan_failed) or 'none'}")
    fill_zones(board)
    pcbnew.SaveBoard(PCB, board)
    if probs:
        raise SystemExit(f"{len(probs)} placement problem(s)")
    if args.no_route:
        set_stackup(PCB)
        return

    log("[4/9] autorouting (Freerouting)")
    board = pcbnew.LoadBoard(PCB)
    result = autoroute(board, args.passes, args.attempts, route_from=args.route_from, reroute=args.reroute)
    n = normalize_vias(board)
    left = _unconnected(board)
    log("  routed: " + ("imported session" if result is None else
                        f"Freerouting's count {result[0]} unrouted, {result[1]} violations")
        + f"; KiCad's count {left} unconnected; vias re-drilled: {n}")
    pcbnew.SaveBoard(PCB, board)

    log("[5/9] pours, thermal vias, stitching")
    board = pcbnew.LoadBoard(PCB)
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
    relieved = relieve_hand_soldered_gnd(board)
    log(f"  thermal reliefs on hand-soldered SMD GND pads: {', '.join(relieved) or 'none'}")
    n_pgv, pgv_short = add_power_gnd_vias(board)
    log(f"  power-stage GND vias: {n_pgv}" + (f" (short: {', '.join(pgv_short)})" if pgv_short else ""))
    add_power_pours(board)
    gnd = add_gnd_pours(board)
    fill_zones(board)
    layers = {pcbnew.F_Cu: [z for z in gnd if z.GetLayer() == pcbnew.F_Cu],
              pcbnew.B_Cu: [z for z in gnd if z.GetLayer() == pcbnew.B_Cu]}
    n_gnd = stitch(board, layers, "GND", 3.0)
    fill_zones(board)
    log(f"  vias: {n_ep} in exposed pads, {n_pgv} power-stage GND, {n_gnd} GND stitching")
    pcbnew.SaveBoard(PCB, board)
    set_stackup(PCB)

    log("[6/9] DRC")
    summary = run_drc()

    log("[7/9] fabrication outputs")
    export_fab(render=not args.no_render)
    board = pcbnew.LoadBoard(PCB)
    rows, issues = write_jlc_files(board)

    log("[8/9] report")
    report = dict(generated=TODAY, drc=summary, route=result, cpl_issues=issues, placement_moves=moves,
                  parts=len(D.PARTS), assembled=len(rows))
    with open(os.path.join(BUILD, "build_report.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1)
    log("[9/9] done: " + json.dumps(summary))
    errors = sum(e for e, _ in summary.values())
    if errors or issues:
        log(f"!! {errors} DRC error(s), {len(issues)} CPL issue(s): do NOT order yet")
        sys.exit(2)


if __name__ == "__main__":
    main()
