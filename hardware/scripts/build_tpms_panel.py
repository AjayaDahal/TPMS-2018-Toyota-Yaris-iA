#!/usr/bin/env python3
"""Generate, autoroute and export the TPMS monitor panel PCB (KiCad 10).

Run with the Python interpreter bundled with KiCad (it provides the pcbnew module):

    "%LOCALAPPDATA%\\Programs\\KiCad10\\bin\\python.exe" build_tpms_panel.py

Edit panel_config.py (outline / positions) or design.py (circuit) and re-run.
Requires KiCad 10 (kicad-cli next to python.exe), Java 21+ and Freerouting 2.x
(FREEROUTING_JAR environment variable, default %LOCALAPPDATA%\\Programs\\freerouting\\freerouting-2.5.0.jar).
"""
import argparse
import copy
import csv
import datetime
import json
import math
import os
import re
import shutil
import subprocess
import sys
import uuid
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import design as D  # noqa: E402
import panel_config as CFG  # noqa: E402
from sexpr import QStr, Sym, dumps, find, find_all, parse, walk  # noqa: E402

import pcbnew  # noqa: E402

HW = os.path.dirname(HERE)
NAME = "tpms_panel"
PRO = os.path.join(HW, NAME + ".kicad_pro")
SCH = os.path.join(HW, NAME + ".kicad_sch")
PCB = os.path.join(HW, NAME + ".kicad_pcb")
LIBDIR = os.path.join(HW, "lib")
FPLIB = os.path.join(LIBDIR, "TPMS.pretty")
SYMLIB = os.path.join(LIBDIR, "TPMS.kicad_sym")
MODELDIR = os.path.join(LIBDIR, "3d")
PROD = os.path.join(HW, "production")
DOCS = os.path.join(HW, "docs")
BUILD = os.path.join(HW, "build")

KICAD_BIN = os.path.dirname(sys.executable)
KICAD_SHARE = os.path.normpath(os.path.join(KICAD_BIN, "..", "share", "kicad"))
KICAD_CLI = os.path.join(KICAD_BIN, "kicad-cli.exe" if os.name == "nt" else "kicad-cli")
SYM_DIR = os.environ.get("KICAD_SYMBOL_DIR", os.path.join(KICAD_SHARE, "symbols"))
FP_DIR = os.environ.get("KICAD_FOOTPRINT_DIR", os.path.join(KICAD_SHARE, "footprints"))
FREEROUTING_JAR = os.environ.get("FREEROUTING_JAR", os.path.join(
    os.environ.get("LOCALAPPDATA", ""), "Programs", "freerouting", "freerouting-2.5.0.jar"))
JAVA = os.environ.get("JAVA", "java")

TODAY = datetime.date.today().isoformat()
NS = uuid.UUID("6f1d3c2a-8b7e-4f62-9a51-1c0de7a5b315")
SCH_ROOT_UUID = str(uuid.uuid5(NS, "root-sheet"))


def uid(*parts):
    return str(uuid.uuid5(NS, "/".join(str(p) for p in parts)))


def log(msg):
    print(msg, flush=True)


def run(cmd, timeout=600, check=True, cwd=None):
    log("  $ " + " ".join(f'"{c}"' if " " in str(c) else str(c) for c in cmd))
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)
    if check and res.returncode != 0:
        log(res.stdout[-3000:])
        log(res.stderr[-3000:])
        raise RuntimeError(f"command failed ({res.returncode}): {cmd[0]} {cmd[1:3]}")
    return res


def g(v):
    """Snap to the 0.01 mm grid used in generated files."""
    return round(v, 4)


# ====================================================================== 3D models (VRML)
class Wrl:
    """Tiny VRML 2.0 writer. Input coordinates are footprint mm (x right, y down, z up)."""

    def __init__(self):
        self.shapes = []

    def _shape(self, verts, faces, color, shininess=0.3, transparency=0.0):
        self.shapes.append((verts, faces, color, shininess, transparency))

    def box(self, x0, x1, y0, y1, z0, z1, color, **kw):
        X0, X1 = min(x0, x1), max(x0, x1)
        Y0, Y1 = -max(y0, y1), -min(y0, y1)
        Z0, Z1 = min(z0, z1), max(z0, z1)
        v = [(X0, Y0, Z0), (X1, Y0, Z0), (X1, Y1, Z0), (X0, Y1, Z0),
             (X0, Y0, Z1), (X1, Y0, Z1), (X1, Y1, Z1), (X0, Y1, Z1)]
        f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (2, 3, 7, 6), (3, 0, 4, 7), (1, 2, 6, 5)]
        self._shape(v, f, color, **kw)

    def prism(self, cx, cy, r, n, z0, z1, color, a0=0.0, **kw):
        cy = -cy
        v = []
        for z in (z0, z1):
            for i in range(n):
                a = a0 + 2 * math.pi * i / n
                v.append((cx + r * math.cos(a), cy + r * math.sin(a), z))
        f = [tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))]
        for i in range(n):
            j = (i + 1) % n
            f.append((i, j, n + j, n + i))
        self._shape(v, f, color, **kw)

    def save(self, path):
        out = ["#VRML V2.0 utf8"]
        for verts, faces, col, shin, tr in self.shapes:
            pts = ", ".join(f"{x / 2.54:.5f} {y / 2.54:.5f} {z / 2.54:.5f}" for x, y, z in verts)
            idx = ", ".join(" ".join(str(i) for i in fc) + " -1" for fc in faces)
            out.append(
                "Shape {\n  appearance Appearance { material Material { "
                f"diffuseColor {col[0]:.3f} {col[1]:.3f} {col[2]:.3f} "
                "specularColor 0.25 0.25 0.25 ambientIntensity 0.3 "
                f"shininess {shin:.2f} transparency {tr:.2f} }} }}\n"
                f"  geometry IndexedFaceSet {{ coord Coordinate {{ point [ {pts} ] }} coordIndex [ {idx} ] }}\n}}")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(out) + "\n")


BLACK = (0.04, 0.04, 0.04)
DARK = (0.16, 0.16, 0.17)
SILVER = (0.72, 0.72, 0.74)
GOLD = (0.83, 0.68, 0.22)
GREEN = (0.05, 0.38, 0.12)
BLUE = (0.07, 0.12, 0.42)
USB_BLUE = (0.10, 0.25, 0.85)


def build_models():
    os.makedirs(MODELDIR, exist_ok=True)
    # ESP32 DOIT DevKit V1 (0.9 in variant) on 8.5 mm female headers
    w = Wrl()
    s = CFG.ESP32_ROW_SPACINGS[0]
    for x in (0.0, s):
        w.box(x - 1.27, x + 1.27, -1.27, 36.83, 0, 8.5, BLACK)
        w.box(x - 1.27, x + 1.27, -1.27, 36.83, 8.5, 11.0, BLACK)
    w.box(-2.54, s + 2.54, -7.62, 43.18, 11.0, 12.6, BLUE)
    cx = s / 2
    w.box(cx - 9, cx + 9, -7.62, 17.88, 12.6, 13.4, BLACK)          # WROOM module PCB
    w.box(cx - 8.5, cx + 8.5, -1.2, 17.3, 13.4, 15.8, SILVER)       # RF shield
    w.box(cx - 4.0, cx + 4.0, 39.4, 44.2, 12.6, 15.2, SILVER)       # micro USB
    for dx in (-7.5, 7.5):
        w.box(cx + dx - 1.8, cx + dx + 1.8, 36.5, 40.0, 12.6, 14.4, DARK)  # EN / BOOT buttons
    w.save(os.path.join(MODELDIR, "ESP32_DevKit_V1.wrl"))

    # CC1101 module (E07-M1101D-SMA style) on a 2x4 female header
    w = Wrl()
    w.box(-8.89, 1.27, -1.27, 3.81, 0, 8.5, BLACK)
    w.box(-8.89, 1.27, -1.27, 3.81, 8.5, 11.0, BLACK)
    w.box(-11.3, 3.7, -1.6, 28.4, 11.0, 12.0, GREEN)
    w.box(-5.8, -1.8, 12.0, 16.0, 12.0, 12.9, BLACK)                 # CC1101 QFN
    w.box(-9.6, -6.4, 17.5, 19.5, 12.0, 12.8, SILVER)                # crystal
    w.box(-6.98, -0.62, 26.0, 31.0, 11.0, 17.4, GOLD)                # SMA body
    w.prism(-3.8, 31.0, 3.0, 16, 11.0, 11.0, GOLD)
    w.box(-6.0, -1.6, 31.0, 39.4, 12.0, 16.4, GOLD)                  # SMA thread
    w.save(os.path.join(MODELDIR, "CC1101_Module.wrl"))

    # NHD-2.7-12864WDW3 on a 2.5 mm header spacer
    w = Wrl()
    w.box(-25.4, 25.4, -22.5, -20.0, 0, 2.5, BLACK)
    w.box(-41.0, 41.0, -23.75, 23.75, 2.5, 4.1, DARK)
    w.box(-37.1, 37.1, -20.0, 23.0, 4.1, 6.9, (0.22, 0.22, 0.23))
    w.box(-31.7, 31.7, -14.8, 17.9, 6.9, 6.95, (0.02, 0.02, 0.03), shininess=0.9)
    w.save(os.path.join(MODELDIR, "NHD-2.7-12864WDW3.wrl"))

    # Panel-mount USB-A socket with front hex nut (fits the cut-out footprint)
    w = Wrl()
    w.prism(0, 0, 14.4, 6, 0.0, 3.0, SILVER, a0=math.pi / 6)
    w.prism(0, 0, 10.0, 32, 3.0, 8.0, (0.3, 0.3, 0.32))
    w.box(-6.3, 6.3, -2.9, 2.9, 8.0, 8.05, BLACK)
    w.box(-5.6, 5.6, -2.3, -0.6, 8.05, 8.1, USB_BLUE)
    w.prism(0, 0, 9.6, 32, -24.0, -1.6, (0.3, 0.3, 0.32))
    w.prism(0, 0, 12.5, 6, -4.6, -1.6, SILVER, a0=math.pi / 6)
    w.save(os.path.join(MODELDIR, "USB_PanelMount.wrl"))

    # Knob for the EC11 encoder (shaft at (7.5, 2.5) in the KiCad EC11E footprint)
    w = Wrl()
    kx, ky, kr = 7.5, 2.5, CFG.KNOB_DIAMETER / 2
    w.prism(kx, ky, kr + 0.4, 48, 7.0, 8.2, (0.10, 0.10, 0.11))
    w.prism(kx, ky, kr, 48, 8.2, 20.0, (0.20, 0.20, 0.21), shininess=0.6)
    w.prism(kx, ky, kr - 0.8, 48, 20.0, 21.0, (0.30, 0.30, 0.32), shininess=0.7)
    w.box(kx - 0.5, kx + 0.5, ky - kr + 1.5, ky - 3.5, 21.0, 21.05, (0.95, 0.95, 0.95))
    w.save(os.path.join(MODELDIR, "EC11_Knob.wrl"))


# ====================================================================== symbol library helpers
_LIB_CACHE = {}


def load_lib(lib):
    if lib not in _LIB_CACHE:
        with open(os.path.join(SYM_DIR, lib + ".kicad_sym"), encoding="utf-8") as fh:
            tree = parse(fh.read())[0]
        _LIB_CACHE[lib] = {s[1]: s for s in find_all(tree, "symbol")}
    return _LIB_CACHE[lib]


def flatten_symbol(lib, name):
    """Return a self-contained copy of a library symbol (resolves `extends`)."""
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


def sym_prop(name, value, x, y, hide=False, justify=None):
    node = [Sym("property"), QStr(name), QStr(value), [Sym("at"), g(x), g(y), 0]]
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
            x = side * (hw + 2.54)
            y = g(top - 2.54 * i)
            pins.append([Sym("pin"), Sym(etype), Sym("line"), [Sym("at"), g(x), y, 0 if side < 0 else 180],
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
    s = copy.deepcopy(customs[name]) if lib == "TPMS" else flatten_symbol(lib, name)
    s[1] = QStr(lib_id)
    return s


def symbol_pins(sdef):
    pins = {}
    for p in walk(sdef, "pin"):
        if len(p) > 2 and isinstance(p[1], str) and find(p, "at") is not None:
            at = find(p, "at")
            pins[str(find(p, "number")[1])] = (float(at[1]), float(at[2]), float(at[3]))
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
                     [Sym("layer"), QStr("F.Cu")], [Sym("descr"), QStr(descr)], [Sym("tags"), QStr("TPMS")]]
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

    def circle(self, cx, cy, r, layer, w=0.12):
        self.items.append([Sym("fp_circle"), [Sym("center"), g(cx), g(cy)], [Sym("end"), g(cx + r), g(cy)],
                           _stroke(w), [Sym("fill"), Sym("no")], [Sym("layer"), QStr(layer)], self._u()])

    def text(self, s, x, y, layer, size=1.0, rot=0, thick=0.15, justify=None):
        eff = [Sym("effects"), [Sym("font"), [Sym("size"), size, size], [Sym("thickness"), thick]]]
        if justify:
            eff.append([Sym("justify"), Sym(justify)])
        self.items.append([Sym("fp_text"), Sym("user"), QStr(s), [Sym("at"), g(x), g(y), rot],
                           [Sym("layer"), QStr(layer)], self._u(), eff])

    def pad(self, num, x, y, shape="circle", size=1.7, drill=1.0):
        self.items.append([Sym("pad"), QStr(num), Sym("thru_hole"), Sym(shape), [Sym("at"), g(x), g(y)],
                           [Sym("size"), size, size], [Sym("drill"), drill], [Sym("layers"), QStr("*.Cu"), QStr("*.Mask")],
                           [Sym("remove_unused_layers"), Sym("no")], self._u()])

    def npth(self, x, y, d):
        self.items.append([Sym("pad"), QStr(""), Sym("np_thru_hole"), Sym("circle"), [Sym("at"), g(x), g(y)],
                           [Sym("size"), d, d], [Sym("drill"), d], [Sym("layers"), QStr("*.Cu"), QStr("*.Mask")],
                           self._u()])

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
    esp = D.CUSTOM_SYMBOLS["ESP32_DevKit_V1_30pin"]

    # ---- ESP32 DOIT DevKit V1, 30 pin, both row spacings
    f = Fp("ESP32_DOIT_DevKit_V1_30pin",
           "DOIT ESP32 DEVKIT V1 30-pin on 2x 1x15 2.54 mm sockets. GPIO23..3V3 row provided at "
           "22.86 mm (0.9 in) and 25.4 mm (1.0 in) from the EN..VIN row; populate the one matching your board.")
    s1, s2 = CFG.ESP32_ROW_SPACINGS
    f.prop("Reference", "REF**", s2 / 2, -9.2, "F.SilkS")
    f.prop("Value", "ESP32_DevKit_V1", s2 / 2, 45.0, "F.Fab")
    f.prop("Footprint", "", 0, 0, "F.Fab", hide=True)
    for i in range(15):
        y = 2.54 * i
        f.pad(str(i + 1), 0, y, "rect" if i == 0 else "circle")
        f.pad(str(i + 16), s1, y)
        f.pad(str(i + 16), s2, y)
        f.text(esp["left"][i][1].split("/")[0], 1.55, y, "F.SilkS", size=1.0, thick=0.15, justify="left")
        f.text(esp["right"][i][1].split("/")[0], s1 - 1.55, y, "F.SilkS", size=1.0, thick=0.15, justify="right")
    x0, x1, y0, y1 = -2.54, s2 + 2.54, -7.62, 43.18
    f.rect(x0, y0, x1, y1, "F.SilkS")
    f.rect(x0, y0, x1, y1, "F.Fab", 0.1)
    f.rect(x0 - 0.25, y0 - 0.25, x1 + 0.25, y1 + 0.25, "F.CrtYd", 0.05)
    f.line(x0, -1.0, x1, -1.0, "F.SilkS")
    f.text("ANTENNA - keep clear", s2 / 2, -4.3, "F.SilkS", size=1.0)
    f.text("USB", s2 / 2, 41.4, "F.SilkS", size=1.0)
    f.text("ESP32 DEVKIT V1 (DOIT 30-pin)", s2 / 2 - 1.6, 20.0, "F.SilkS", size=1.2, rot=90)
    f.text("0.9in", s1, 38.4, "F.SilkS", size=1.0, thick=0.15)
    f.text("1.0in", s2, 39.9, "F.SilkS", size=1.0, thick=0.15)
    f.model("${KIPRJMOD}/lib/3d/ESP32_DevKit_V1.wrl")
    f.save()

    # ---- CC1101 module, Ebyte E07-M1101D(-SMA) 2x4 header pinout
    f = Fp("CC1101_E07-M1101D_Socket",
           "CC1101 module, Ebyte E07-M1101D(-SMA) form factor (15x30 mm), 2x4 2.54 mm socket. "
           "Pin 1 GND, 2 VCC, 3 GDO0, 4 CSN, 5 SCK, 6 MOSI, 7 MISO, 8 GDO2.")
    f.prop("Reference", "REF**", -3.8, 9.5, "F.SilkS")
    f.prop("Value", "CC1101_315MHz", -3.8, 20.0, "F.Fab")
    f.prop("Footprint", "", 0, 0, "F.Fab", hide=True)
    names = {1: "GND", 2: "VCC", 3: "GDO0", 4: "CSN", 5: "SCK", 6: "MOSI", 7: "MISO", 8: "GDO2"}
    for k in range(4):
        x = -2.54 * k
        f.pad(str(2 * k + 1), x, 0, "rect" if k == 0 else "circle")
        f.pad(str(2 * k + 2), x, 2.54)
        f.text(names[2 * k + 2], x, 6.0, "F.SilkS", size=1.0, thick=0.15, rot=90)
    f.rect(-11.3, -1.6, 3.7, 28.4, "F.SilkS")
    f.rect(-11.3, -1.6, 3.7, 28.4, "F.Fab", 0.1)
    f.rect(-11.55, -1.85, 3.95, 28.65, "F.CrtYd", 0.05)
    f.rect(-7.0, 28.4, -0.6, 39.4, "F.Fab", 0.1)
    f.text("CC1101 315MHz", -3.8, 13.0, "F.SilkS", size=1.2)
    f.text("SMA", -3.8, 26.6, "F.SilkS", size=1.0)
    f.text("1", 1.9, -0.9, "F.SilkS", size=1.0, thick=0.15)
    f.model("${KIPRJMOD}/lib/3d/CC1101_Module.wrl")
    f.save()

    # ---- NHD-2.7-12864WDW3 (origin = module centre, pin 1 on the right seen from the front)
    f = Fp("NHD-2.7-12864WDW3",
           "Newhaven NHD-2.7-12864WDW3 2.7in OLED, 82x47.5 mm, 1x20 2.54 mm header (pin 1 right when viewed "
           "from the front), 4x 2.5 mm mounting holes on 77x42.5 mm")
    f.prop("Reference", "REF**", 0, -26.0, "F.Fab")
    f.prop("Value", "NHD-2.7-12864WDW3", 0, 0, "F.Fab")
    f.prop("Footprint", "", 0, 0, "F.Fab", hide=True)
    for n in range(1, 21):
        f.pad(str(n), 24.13 - 2.54 * (n - 1), -21.25, "rect" if n == 1 else "circle")
    for sx in (-1, 1):
        for sy in (-1, 1):
            f.npth(38.5 * sx, 21.25 * sy, 2.7)
    f.rect(-41.0, -23.75, 41.0, 23.75, "F.Fab", 0.1)
    f.rect(-30.705, -15.345 + 1.55, 30.705, 15.345 + 1.55, "F.Fab", 0.1)
    f.rect(-41.25, -24.0, 41.25, 24.0, "F.CrtYd", 0.05)
    f.text("1", 24.13, -19.4, "F.SilkS", size=1.0, thick=0.15)
    f.model("${KIPRJMOD}/lib/3d/NHD-2.7-12864WDW3.wrl")
    f.save()

    # ---- panel-mount USB socket cut-out
    r = CFG.USB_HOLE_DIAMETER / 2
    rn = CFG.USB_NUT_DIAMETER / 2
    f = Fp("USB_PanelMount_Cutout",
           f"Round {CFG.USB_HOLE_DIAMETER:g} mm cut-out for a panel-mount USB socket with front nut",
           attr="board_only exclude_from_pos_files exclude_from_bom")
    f.prop("Reference", "REF**", 0, -rn - 1.5, "F.Fab")
    f.prop("Value", "USB_PANEL_CUTOUT", 0, rn + 1.5, "F.Fab")
    f.prop("Footprint", "", 0, 0, "F.Fab", hide=True)
    f.circle(0, 0, r, "Edge.Cuts", 0.1)
    f.circle(0, 0, rn, "F.Fab", 0.1)
    f.circle(0, 0, rn + 0.25, "F.CrtYd", 0.05)
    f.model("${KIPRJMOD}/lib/3d/USB_PanelMount.wrl")
    f.save()


def write_lib_tables():
    with open(os.path.join(HW, "fp-lib-table"), "w", encoding="utf-8") as fh:
        fh.write('(fp_lib_table\n\t(version 7)\n\t(lib (name "TPMS")(type "KiCad")(uri "${KIPRJMOD}/lib/TPMS.pretty")'
                 '(options "")(descr "TPMS panel custom footprints"))\n)\n')
    with open(os.path.join(HW, "sym-lib-table"), "w", encoding="utf-8") as fh:
        fh.write('(sym_lib_table\n\t(version 7)\n\t(lib (name "TPMS")(type "KiCad")(uri "${KIPRJMOD}/lib/TPMS.kicad_sym")'
                 '(options "")(descr "TPMS panel custom symbols"))\n)\n')


# ====================================================================== project file
def write_project():
    pro = {
        "board": {
            "design_settings": {
                "defaults": {"board_outline_line_width": 0.1, "copper_line_width": 0.2, "copper_text_size_h": 1.5,
                             "copper_text_size_v": 1.5, "copper_text_thickness": 0.3, "courtyard_line_width": 0.05,
                             "fab_line_width": 0.1, "fab_text_size_h": 1.0, "fab_text_size_v": 1.0,
                             "fab_text_thickness": 0.15, "other_line_width": 0.1, "silk_line_width": 0.12,
                             "silk_text_size_h": 1.0, "silk_text_size_v": 1.0, "silk_text_thickness": 0.15,
                             "pads": {"drill": 1.0, "height": 1.7, "width": 1.7}, "zones": {"min_clearance": 0.3}},
                "meta": {"version": 2},
                "rule_severities": {
                    "lib_footprint_issues": "ignore", "lib_footprint_mismatch": "ignore",
                    "footprint_type_mismatch": "ignore", "pth_inside_courtyard": "ignore",
                    "silk_overlap": "warning", "silk_over_copper": "warning", "silk_edge_clearance": "warning",
                    "text_height": "error", "text_thickness": "error", "courtyards_overlap": "error",
                    "missing_courtyard": "ignore", "copper_edge_clearance": "error", "unconnected_items": "error",
                    "footprint_symbol_mismatch": "warning", "isolated_copper": "warning", "starved_thermal": "warning",
                    "via_dangling": "warning", "track_dangling": "warning"},
                # JLCPCB 2-layer limits: silkscreen text >= 1.0 mm high / 0.15 mm stroke, pad hole-to-hole 0.45 mm
                "rules": {"max_error": 0.005, "min_clearance": 0.15, "min_connection": 0.0,
                          "min_copper_edge_clearance": 0.4, "min_hole_clearance": 0.25, "min_hole_to_hole": 0.45,
                          "min_microvia_diameter": 0.2, "min_microvia_drill": 0.1, "min_resolved_spokes": 1,
                          "min_silk_clearance": 0.0, "min_text_height": 1.0, "min_text_thickness": 0.15,
                          "min_through_hole_diameter": 0.3, "min_track_width": 0.15, "min_via_annular_width": 0.15,
                          "min_via_diameter": 0.5, "solder_mask_to_copper_clearance": 0.0,
                          "use_height_for_length_calcs": True},
                "track_widths": [0.0, 0.25, 0.4, 0.6, 0.8, 1.0],
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
        "net_settings": {
            "classes": [
                {"name": "Default", "clearance": 0.2, "track_width": 0.25, "via_diameter": 0.6, "via_drill": 0.3,
                 "microvia_diameter": 0.3, "microvia_drill": 0.1, "diff_pair_gap": 0.25, "diff_pair_via_gap": 0.25,
                 "diff_pair_width": 0.2, "bus_width": 12, "wire_width": 6, "line_style": 0,
                 "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)",
                 "priority": 2147483647},
                {"name": "Power", "clearance": 0.25, "track_width": 0.6, "via_diameter": 0.8, "via_drill": 0.4,
                 "microvia_diameter": 0.3, "microvia_drill": 0.1, "diff_pair_gap": 0.25, "diff_pair_via_gap": 0.25,
                 "diff_pair_width": 0.2, "bus_width": 12, "wire_width": 6, "line_style": 0,
                 "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)", "priority": 0},
                {"name": "Ground", "clearance": 0.2, "track_width": 0.4, "via_diameter": 0.6, "via_drill": 0.3,
                 "microvia_diameter": 0.3, "microvia_drill": 0.1, "diff_pair_gap": 0.25, "diff_pair_via_gap": 0.25,
                 "diff_pair_width": 0.2, "bus_width": 12, "wire_width": 6, "line_style": 0,
                 "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)", "priority": 1},
            ],
            "meta": {"version": 4},
            "net_colors": None,
            "netclass_assignments": None,
            "netclass_patterns": [{"netclass": "Power", "pattern": p} for p in ("+12V", "VIN_*", "+5V", "+3V3")]
            + [{"netclass": "Ground", "pattern": "GND"}],
        },
        "pcbnew": {"last_paths": {}, "page_layout_descr_file": ""},
        "schematic": {"drawing": {"default_line_thickness": 6.0, "default_text_size": 50.0},
                      "legacy_lib_dir": "", "legacy_lib_list": []},
        "sheets": [[SCH_ROOT_UUID, "Root"]],
        "text_variables": {},
    }
    with open(PRO, "w", encoding="utf-8") as fh:
        json.dump(pro, fh, indent=2)


# ====================================================================== schematic
ROT_CCW = {0: lambda x, y: (x, y), 90: lambda x, y: (y, -x), 180: lambda x, y: (-x, -y), 270: lambda x, y: (-y, x)}


def _dir_rot(natural, wanted):
    for r in (0, 90, 180, 270):
        if ROT_CCW[r](*natural) == wanted:
            return r
    return 0


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

    def text(self, s, x, y, size=1.27):
        self.items.append([Sym("text"), QStr(s), [Sym("exclude_from_sim"), Sym("no")], [Sym("at"), g(x), g(y), 0],
                           [Sym("effects"), [Sym("font"), [Sym("size"), size, size]],
                            [Sym("justify"), Sym("left"), Sym("top")]],
                           [Sym("uuid"), QStr(uid("txt", x, y))]])

    def symbol(self, lib_id, ref, value, footprint, x, y, rot=0, fields=None, dnp=False, power=False, in_bom=True,
               value_horizontal=False):
        sdef = self.use(lib_id)
        props = symbol_props(sdef)
        su = uid("sym", ref)
        node = [Sym("symbol"), [Sym("lib_id"), QStr(lib_id)], [Sym("at"), g(x), g(y), rot], [Sym("unit"), 1],
                [Sym("exclude_from_sim"), Sym("no")], [Sym("in_bom"), Sym("yes" if in_bom and not power else "no")],
                [Sym("on_board"), Sym("no" if power else "yes")], [Sym("dnp"), Sym("yes" if dnp else "no")],
                [Sym("uuid"), QStr(su)]]

        def prop(name, val, hide):
            p = props.get(name)
            px, py, pa = (float(p[3][1]), float(p[3][2]), float(p[3][3]) if len(p[3]) > 3 else 0.0) \
                if p is not None else (0.0, 0.0, 0.0)
            angle = pa if rot == 0 else 0
            if value_horizontal and name == "Value" and rot in (90, 270):
                # KiCad draws a field of a 90/270-rotated symbol rotated as well: a 90 deg field reads horizontally
                angle = 90
                py = math.copysign(abs(py) + 1.27, py) if py else py
            ox, oy = ROT_CCW[rot](px, -py)
            node_p = [Sym("property"), QStr(name), QStr(val), [Sym("at"), g(x + ox), g(y + oy), angle]]
            if hide:
                node_p.append([Sym("hide"), Sym("yes")])
            eff = copy.deepcopy(find(p, "effects")) if p is not None and find(p, "effects") else _font()
            eff = [e for e in eff if not (isinstance(e, list) and e and e[0] == "hide")]
            if rot != 0:
                eff = [e for e in eff if not (isinstance(e, list) and e and e[0] == "justify")]
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
        return su, sdef

    def power(self, net, x, y, d, value_horizontal=False):
        lib_id = "power:" + net
        self.pwr_n += 1
        natural = (0, 1) if net == "GND" else (0, -1)
        self.symbol(lib_id, f"#PWR{self.pwr_n:03d}", net, "", x, y, _dir_rot(natural, d), power=True,
                    value_horizontal=value_horizontal)

    def pwr_flag(self, net, x, y):
        self.flg_n += 1
        self.symbol("power:PWR_FLAG", f"#FLG{self.flg_n:02d}", "PWR_FLAG", "", x, y, 0, power=True)
        self.wire(x, y, x, y + 2.54)
        self.power(net, x, y + 2.54, (0, 1))

    def connect_pin(self, net, px, py, d, stub=2.54):
        if net is None:
            self.no_connect(px, py)
            return
        ex, ey = px + d[0] * stub, py + d[1] * stub
        self.wire(px, py, ex, ey)
        if net in D.POWER_NETS:
            self.power(net, ex, ey, d)
        else:
            self.glabel(net, ex, ey, d)

    def save(self, path):
        title = [Sym("title_block"), [Sym("title"), QStr("TPMS Monitor Panel (315 MHz)")], [Sym("date"), QStr(TODAY)],
                 [Sym("rev"), QStr("1.0")], [Sym("company"), QStr("Ajaya Dahal")],
                 [Sym("comment"), 1, QStr("ESP32 DevKit V1 + CC1101 (E07-M1101D) + NHD-2.7-12864WDW3 OLED")],
                 [Sym("comment"), 2, QStr("Generated by hardware/scripts/build_tpms_panel.py - edit design.py and re-run")]]
        root = [Sym("kicad_sch"), [Sym("version"), 20250610], [Sym("generator"), QStr("eeschema")],
                [Sym("generator_version"), QStr("10.0")], [Sym("uuid"), QStr(SCH_ROOT_UUID)],
                [Sym("paper"), QStr("A3")], title,
                [Sym("lib_symbols")] + [self.lib_symbols[k] for k in sorted(self.lib_symbols)]] + self.items + [
            [Sym("sheet_instances"), [Sym("path"), QStr("/"), [Sym("page"), QStr("1")]]],
            [Sym("embedded_fonts"), Sym("no")]]
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(dumps(root) + "\n")


def build_schematic(customs):
    sch = Schematic(customs)
    for p in D.PARTS:
        sx, sy = p["at"]
        fields = {"MPN": p["mpn"]} if p["mpn"] else {}
        in_bom = not re.match(r"^(H|JP)\d", p["ref"])
        _, sdef = sch.symbol(p["lib_id"], p["ref"], p["value"], p["footprint"], sx, sy, 0, fields, dnp=p["dnp"],
                             in_bom=in_bom)
        pins = symbol_pins(sdef)
        if set(pins) != set(p["pins"]):
            raise ValueError(f"{p['ref']}: pin map {sorted(p['pins'])} != symbol pins {sorted(pins)}")
        ends = []
        for num, (px, py, ang) in pins.items():
            a = math.radians(ang)
            d = (int(round(-math.cos(a))), int(round(math.sin(a))))
            ends.append((p["pins"][num], sx + px, sy - py, d))
        # consecutive pins on the same side with the same power net share one power symbol
        done = set()
        for i, (net, px, py, d) in enumerate(ends):
            if i in done or net not in D.POWER_NETS or d[1] != 0:
                continue
            run_ = [i]
            while True:
                last = ends[run_[-1]]
                nxt = [j for j, e in enumerate(ends) if j not in run_ and e[0] == net and e[3] == d
                       and abs(e[1] - last[1]) < 1e-6 and abs(e[2] - last[2] - 2.54) < 1e-6]
                if not nxt:
                    break
                run_.append(nxt[0])
            if len(run_) < 2:
                continue
            ex = px + d[0] * 2.54
            for j in run_:
                sch.wire(ends[j][1], ends[j][2], ex, ends[j][2])
                done.add(j)
            sch.wire(ex, ends[run_[0]][2], ex, ends[run_[-1]][2])
            sch.power(net, ex, ends[run_[0]][2], d)
            sch.items.append([Sym("junction"), [Sym("at"), g(ex), g(ends[run_[0]][2])], [Sym("diameter"), 0],
                              [Sym("color"), 0, 0, 0, 0], [Sym("uuid"), QStr(uid("j", ex, ends[run_[0]][2]))]])
            for j in run_[1:-1]:
                sch.items.append([Sym("junction"), [Sym("at"), g(ex), g(ends[j][2])], [Sym("diameter"), 0],
                                  [Sym("color"), 0, 0, 0, 0], [Sym("uuid"), QStr(uid("j", ex, ends[j][2]))]])
        def neighbour(px, py, d, dy):
            for j, e in enumerate(ends):
                if j not in done and e[3] == d and abs(e[1] - px) < 1e-6 and abs(e[2] - (py + dy)) < 1e-6:
                    return e
            return None

        # a single sideways power pin between two labelled pins (e.g. encoder A / C=GND / B): give the power
        # symbol horizontal text and push the neighbouring labels out so nothing overlaps
        sandwiched, long_stub = set(), set()
        for i, (net, px, py, d) in enumerate(ends):
            if i in done or net not in D.POWER_NETS or d[1] != 0:
                continue
            up, down = neighbour(px, py, d, -2.54), neighbour(px, py, d, 2.54)
            if all(e is not None and e[0] is not None and e[0] not in D.POWER_NETS for e in (up, down)):
                sandwiched.add(i)
                long_stub.update(j for j, e in enumerate(ends) if e is up or e is down)
        for i, (net, px, py, d) in enumerate(ends):
            if i in done:
                continue
            stub = 2.54
            if i in sandwiched:
                ex = px + d[0] * stub
                sch.wire(px, py, ex, py)
                sch.power(net, ex, py, d, value_horizontal=True)
                continue
            if i in long_stub:
                stub = 10.16
            elif net in D.POWER_NETS and d[1] == 0:
                # stagger neighbouring power symbols on the same side so their labels do not overlap
                prev = [e for j, e in enumerate(ends) if j not in done and e[0] in D.POWER_NETS and e[3] == d
                        and abs(e[1] - px) < 1e-6 and abs(py - e[2] - 2.54) < 1e-6]
                k = 0
                while prev:
                    k += 1
                    yy = py - 2.54 * (k + 1)
                    prev = [e for j, e in enumerate(ends) if j not in done and e[0] in D.POWER_NETS and e[3] == d
                            and abs(e[1] - px) < 1e-6 and abs(e[2] - yy) < 1e-6]
                stub = 2.54 + 5.08 * (k % 2) if k else 2.54
            sch.connect_pin(net, px, py, d, stub=stub)
    for net, x, y in D.PWR_FLAGS:
        sch.pwr_flag(net, x, y)
    for x, y, size, s in D.SHEET_TEXT:
        sch.text(s, x, y, size)
    sch.save(SCH)


def parse_netlist(path):
    with open(path, encoding="utf-8") as fh:
        tree = parse(fh.read())[0]
    comps = {}
    for c in walk(find(tree, "components"), "comp"):
        ref = str(find(c, "ref")[1])
        fp = find(c, "footprint")
        ts = find(c, "tstamps")
        desc = find(c, "description")
        fields = {}
        fl = find(c, "fields")
        for f in find_all(fl or [], "field"):
            nm = find(f, "name")
            if nm is not None and len(f) > 2 and not isinstance(f[2], list):
                fields[str(nm[1])] = str(f[2])
        dnp = any(str(find(p, "name")[1]) == "dnp" for p in find_all(c, "property") if find(p, "name"))
        comps[ref] = dict(value=str(find(c, "value")[1]), footprint=str(fp[1]) if fp else "",
                          tstamp=str(ts[1]) if ts else "", nets={}, description=str(desc[1]) if desc else "",
                          fields=fields, dnp=dnp)
    for n in walk(find(tree, "nets"), "net"):
        name = str(find(n, "name")[1])
        for node in find_all(n, "node"):
            ref, pin = str(find(node, "ref")[1]), str(find(node, "pin")[1])
            if ref in comps:
                comps[ref]["nets"][pin] = name
    return comps


# ====================================================================== board geometry
MM = pcbnew.FromMM


def P(x, y):
    """Panel coordinates (mm, origin top-centre) -> board VECTOR2I."""
    return pcbnew.VECTOR2I(MM(CFG.PAGE_ORIGIN[0] + x), MM(CFG.PAGE_ORIGIN[1] + y))


def outline_geometry():
    tw, bw, h = CFG.TOP_WIDTH / 2, CFG.BOTTOM_WIDTH / 2, CFG.HEIGHT
    tl, tr, br, bl = (-tw, 0.0), (tw, 0.0), (bw, h), (-bw, h)
    ux, uy = br[0] - tr[0], br[1] - tr[1]
    ln = math.hypot(ux, uy)
    ux, uy = ux / ln, uy / ln
    t = CFG.NOTCH_Y / h
    cx, cy = tr[0] + t * (br[0] - tr[0]), CFG.NOTCH_Y
    r = CFG.NOTCH_R
    nx, ny = -uy, ux                     # inward normal of the right edge
    if nx > 0:
        nx, ny = -nx, -ny
    a = (cx - r * ux, cy - r * uy)
    b = (cx + r * ux, cy + r * uy)
    m = (cx + r * nx, cy + r * ny)
    return [tl, tr, a], (a, m, b), [b, br, bl, tl]


def edge_x(y, side):
    """x of the slanted panel edge at height y (side=+1 right, -1 left)."""
    tw, bw = CFG.TOP_WIDTH / 2, CFG.BOTTOM_WIDTH / 2
    return side * (tw + (bw - tw) * y / CFG.HEIGHT)


def add_seg(board, a, b, layer=pcbnew.Edge_Cuts, w=0.1):
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(P(*a))
    s.SetEnd(P(*b))
    s.SetLayer(layer)
    s.SetWidth(MM(w))
    board.Add(s)


def add_outline(board):
    first, arc, rest = outline_geometry()
    for pts in (first, rest):
        for a, b in zip(pts, pts[1:]):
            add_seg(board, a, b)
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(pcbnew.SHAPE_T_ARC)
    s.SetArcGeometry(P(*arc[0]), P(*arc[1]), P(*arc[2]))
    s.SetLayer(pcbnew.Edge_Cuts)
    s.SetWidth(MM(0.1))
    board.Add(s)


def outline_polygon_points(step_deg=10):
    first, arc, rest = outline_geometry()
    pts = list(first)
    (ax, ay), (mx, my), (bx, by) = arc
    # circle through a, m, b: centre is the notch centre on the edge
    cx, cy = (ax + bx) / 2, (ay + by) / 2
    r = math.hypot(ax - cx, ay - cy)
    a0 = math.atan2(ay - cy, ax - cx)
    am = math.atan2(my - cy, mx - cx)
    a1 = math.atan2(by - cy, bx - cx)
    sweep = (am - a0) % (2 * math.pi)
    direction = 1 if sweep < math.pi else -1
    n = 18
    for i in range(1, n):
        ang = a0 + direction * math.pi * i / n
        pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    pts += rest[:-1]
    return pts


def add_text(board, s, x, y, layer, size=1.5, thick=0.25, justify="center", rot=0):
    """`justify` is relative to the front (top) view: 'left' = text grows towards +x."""
    t = pcbnew.PCB_TEXT(board)
    t.SetText(s)
    t.SetLayer(layer)
    t.SetTextSize(pcbnew.VECTOR2I(MM(size), MM(size)))
    t.SetTextThickness(MM(thick))
    t.SetPosition(P(x, y))
    if rot:
        t.SetTextAngleDegrees(rot)
    mirrored = layer in (pcbnew.B_SilkS, pcbnew.B_Fab, pcbnew.B_Cu)
    if mirrored:
        t.SetMirrored(True)
        justify = {"left": "right", "right": "left"}.get(justify, justify)
    t.SetHorizJustify({"left": pcbnew.GR_TEXT_H_ALIGN_LEFT, "right": pcbnew.GR_TEXT_H_ALIGN_RIGHT,
                       "center": pcbnew.GR_TEXT_H_ALIGN_CENTER}[justify])
    board.Add(t)
    return t


def move_ref(fp, x, y, justify="center"):
    r = fp.Reference()
    r.SetPosition(P(x, y))
    r.SetTextAngleDegrees(0)
    if fp.IsFlipped():
        justify = {"left": "right", "right": "left"}.get(justify, justify)
    r.SetHorizJustify({"left": pcbnew.GR_TEXT_H_ALIGN_LEFT, "right": pcbnew.GR_TEXT_H_ALIGN_RIGHT,
                       "center": pcbnew.GR_TEXT_H_ALIGN_CENTER}[justify])


def lset(*layers):
    ls = pcbnew.LSET()
    for layer in layers:
        ls.AddLayer(layer)
    return ls


def add_rule_area(board, pts, layers, name, pour=False):
    z = pcbnew.ZONE(board)
    z.SetIsRuleArea(True)
    z.SetLayerSet(lset(*layers))
    z.SetZoneName(name)
    z.SetDoNotAllowTracks(True)
    z.SetDoNotAllowVias(True)
    z.SetDoNotAllowZoneFills(not pour)
    z.SetDoNotAllowPads(False)
    z.SetDoNotAllowFootprints(False)
    ol = z.Outline()
    ol.NewOutline()
    for x, y in pts:
        v = P(x, y)
        ol.Append(v.x, v.y)
    board.Add(z)
    return z


def circle_pts(cx, cy, r, n=36):
    return [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n)) for i in range(n)]


def load_footprint(fpid):
    lib, name = fpid.split(":")
    path = FPLIB if lib == "TPMS" else os.path.join(FP_DIR, lib + ".pretty")
    fp = pcbnew.FootprintLoad(path, name)
    if fp is None:
        raise RuntimeError(f"footprint not found: {fpid}")
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    return fp


def courtyard_center(fp, side):
    layer = pcbnew.F_CrtYd if side == "F" else pcbnew.B_CrtYd
    fp.BuildCourtyardCaches()
    cy = fp.GetCourtyard(layer)
    if cy.OutlineCount():
        bb = cy.BBox()
        return pcbnew.VECTOR2I(int((bb.GetLeft() + bb.GetRight()) / 2), int((bb.GetTop() + bb.GetBottom()) / 2))
    bb = fp.GetBoundingBox(False)
    return bb.GetCenter()


def place(fp, side, x, y, rot):
    fp.SetPosition(pcbnew.VECTOR2I(0, 0))
    if side == "B":
        fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    if rot:
        fp.Rotate(fp.GetPosition(), pcbnew.EDA_ANGLE(float(rot), pcbnew.DEGREES_T))
    c = courtyard_center(fp, side)
    target = P(x, y)
    fp.Move(pcbnew.VECTOR2I(target.x - c.x, target.y - c.y))


def pad_xy(fp, num):
    out = []
    for p in fp.Pads():
        if p.GetNumber() == num:
            v = p.GetPosition()
            out.append((round(pcbnew.ToMM(v.x) - CFG.PAGE_ORIGIN[0], 2), round(pcbnew.ToMM(v.y) - CFG.PAGE_ORIGIN[1], 2)))
    return out


def build_board(comps):
    if os.path.exists(PCB):
        os.remove(PCB)
    board = pcbnew.NewBoard(PCB)
    board.SetCopperLayerCount(2)
    ds = board.GetDesignSettings()
    ds.SetBoardThickness(MM(1.6))
    ds.m_TentViasFront = True
    ds.m_TentViasBack = True

    add_outline(board)

    nets = {}
    for c in comps.values():
        for net in c["nets"].values():
            if net not in nets:
                ni = pcbnew.NETINFO_ITEM(board, net)
                board.Add(ni)
                nets[net] = ni

    fps = {}
    for ref in sorted(comps):
        c = comps[ref]
        if ref not in CFG.PLACEMENT:
            raise RuntimeError(f"no placement for {ref}")
        fp = load_footprint(c["footprint"])
        fp.SetReference(ref)
        fp.SetValue(c["value"])
        fp.SetPath(pcbnew.KIID_PATH("/" + c["tstamp"]))
        fp.SetSheetname("/")
        fp.SetSheetfile(NAME + ".kicad_sch")
        fp.SetField("Description", c["description"])
        for k, v in c["fields"].items():
            if k not in ("Footprint", "Datasheet", "Description", "Reference", "Value"):
                fp.SetField(k, v)
        for k in list(c["fields"]) + ["Description"]:
            f = fp.GetField(k)
            if f is not None and k not in ("Reference", "Value"):
                f.SetVisible(False)
                f.SetLayer(pcbnew.F_Fab)
        if c["dnp"]:
            fp.SetDNP(True)
        if c["footprint"].startswith("Rotary_Encoder:"):
            knob = pcbnew.FP_3DMODEL()
            knob.m_Filename = "${KIPRJMOD}/lib/3d/EC11_Knob.wrl"
            fp.Models().push_back(knob)
        board.Add(fp)
        for pad in fp.Pads():
            net = c["nets"].get(pad.GetNumber())
            if net:
                pad.SetNet(nets[net])
        side, x, y, rot = CFG.PLACEMENT[ref]
        place(fp, side, x, y, rot)
        fps[ref] = fp

    # keep the front panel clean: front-side reference/value text goes to the fab layer
    for ref, fp in fps.items():
        if CFG.PLACEMENT[ref][0] == "F":
            fp.Reference().SetLayer(pcbnew.F_Fab)
            fp.Value().SetLayer(pcbnew.F_Fab)
        else:
            fp.Value().SetLayer(pcbnew.B_Fab)
            fp.Reference().SetTextSize(pcbnew.VECTOR2I(MM(1.0), MM(1.0)))
            fp.Reference().SetTextThickness(MM(0.15))

    board.SynchronizeNetsAndNetClasses(True)
    return board, fps


def add_silk_seg(board, a, b, layer, w=0.2):
    add_seg(board, a, b, layer=layer, w=w)


def add_silk_arc(board, start, mid, end, layer, w=0.2):
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(pcbnew.SHAPE_T_ARC)
    s.SetArcGeometry(P(*start), P(*mid), P(*end))
    s.SetLayer(layer)
    s.SetWidth(MM(w))
    board.Add(s)


def add_car_outline(board, layer):
    """Top-view car silhouette between the four tyre LEDs (wheels)."""
    xs = [p[0] for p in CFG.LED_POSITIONS]
    ys = [p[1] for p in CFG.LED_POSITIONS]
    cx, hw = (min(xs) + max(xs)) / 2, (max(xs) - min(xs)) / 2 - 3.8   # body half-width inside the LED rings
    y0, y1, r = min(ys) - 5.5, max(ys) + 5.5, 2.2
    k = r * (1 - math.sqrt(0.5))
    x0, x1 = cx - hw, cx + hw
    add_silk_seg(board, (x0 + r, y0), (x1 - r, y0), layer)
    add_silk_seg(board, (x1, y0 + r), (x1, y1 - r), layer)
    add_silk_seg(board, (x1 - r, y1), (x0 + r, y1), layer)
    add_silk_seg(board, (x0, y1 - r), (x0, y0 + r), layer)
    add_silk_arc(board, (x1 - r, y0), (x1 - k, y0 + k), (x1, y0 + r), layer)
    add_silk_arc(board, (x1, y1 - r), (x1 - k, y1 - k), (x1 - r, y1), layer)
    add_silk_arc(board, (x0 + r, y1), (x0 + k, y1 - k), (x0, y1 - r), layer)
    add_silk_arc(board, (x0, y0 + r), (x0 + k, y0 + k), (x0 + r, y0), layer)
    add_silk_arc(board, (x0 + 0.6, min(ys) + 4.8), (cx, min(ys) + 3.6), (x1 - 0.6, min(ys) + 4.8), layer)  # windscreen
    add_silk_seg(board, (x0 + 0.6, max(ys) - 4.2), (x1 - 0.6, max(ys) - 4.2), layer)                      # rear window


def add_panel_graphics(board, fps):
    F, B = pcbnew.F_SilkS, pcbnew.B_SilkS
    for (x, y), lab in zip(CFG.LED_POSITIONS, CFG.LED_LABELS):
        add_text(board, lab, x + (-4.4 if x < 0 else 4.4), y, F, size=2.2, thick=0.35,
                 justify="right" if x < 0 else "left")
    if CFG.CAR_OUTLINE:
        add_car_outline(board, F)
    if CFG.INPUT_STYLE != "encoder":
        for y, lab in zip(CFG.BUTTON_YS, CFG.BUTTON_LABELS):
            add_text(board, lab, CFG.BUTTON_X + 6.0, y, F, size=1.8, thick=0.3, justify="left")

    add_text(board, "TPMS MONITOR PANEL  v1.0", -40.0, 4.0, B, size=1.8, thick=0.3)
    add_text(board, f"ESP32 + CC1101 315 MHz  -  A. Dahal  {TODAY}", -40.0, 7.2, B, size=1.1, thick=0.18)
    add_text(board, "12V IN (ACC)", -20.5, 123.6, B, size=1.0, thick=0.15, justify="right")
    add_text(board, "OPTIONAL MX-05V RX", 58.0, 9.6, B, size=1.0, thick=0.15)
    add_text(board, "EXPANSION", -58.0, 82.6, B, size=1.0, thick=0.15)
    add_text(board, "CC1101 ALT", -67.4, 57.3, B, size=1.0, thick=0.15)
    add_text(board, "JP1 close = 5V to OLED BC_VDD", 19.0, 5.3, B, size=1.0, thick=0.15)
    add_text(board, "JLCJLCJLCJLC", -40.0, 66.0, B, size=1.0, thick=0.15)   # JLCPCB order-number location

    # pin labels next to connector pads (back side): below a horizontal row, beside a vertical one
    labels = {
        "J1": {"1": "+12V", "2": "GND"},
        "J2": {"1": "GND", "2": "3V3", "3": "GDO0", "4": "CSN", "5": "SCK", "6": "MOSI", "7": "MISO", "8": "GDO2"},
        "J3": {"1": "VCC", "2": "DATA", "3": "DATA", "4": "GND"},
        "J4": {"1": "5V", "2": "3V3", "3": "GND", "4": "SDA", "5": "SCL", "6": "IO2", "7": "IO39"},
    }
    for ref, lab in labels.items():
        fp = fps[ref]
        pads = [(p.GetNumber(), pcbnew.ToMM(p.GetPosition().x) - CFG.PAGE_ORIGIN[0],
                 pcbnew.ToMM(p.GetPosition().y) - CFG.PAGE_ORIGIN[1]) for p in fp.Pads() if p.GetNumber() in lab]
        horizontal_row = max(p[2] for p in pads) - min(p[2] for p in pads) < 0.1
        for num, x, y in pads:
            if ref == "J1":
                add_text(board, lab[num], x, y - 6.9, B, size=1.0, thick=0.15)
            elif horizontal_row:
                add_text(board, lab[num], x, y + 4.0, B, size=1.0, thick=0.15, rot=90)
            else:
                add_text(board, lab[num], x + 2.3, y, B, size=1.0, thick=0.15, justify="left")
    move_ref(fps["J1"], -20.5, 121.4, "right")
    move_ref(fps["J2"], -55.8, 48.5, "left")
    move_ref(fps["J3"], 52.4, 14.0, "right")
    move_ref(fps["J4"], -66.5, 82.6)


def add_keepouts(board, fps):
    # ESP32 antenna end (no copper under the PCB antenna)
    a1 = fps["A1"]
    xs = [pcbnew.ToMM(p.GetPosition().x) - CFG.PAGE_ORIGIN[0] for p in a1.Pads()]
    ys = [pcbnew.ToMM(p.GetPosition().y) - CFG.PAGE_ORIGIN[1] for p in a1.Pads()]
    en = pad_xy(a1, "1")[0]
    vin = pad_xy(a1, "15")[0]
    toward_ant = 1 if en[0] > vin[0] else -1
    x_in = en[0] + toward_ant * 1.2
    x_out = en[0] + toward_ant * 8.9
    y0, y1 = min(ys) - 3.0, max(ys) + 3.0
    add_rule_area(board, [(x_in, y0), (x_out, y0), (x_out, y1), (x_in, y1)], (pcbnew.F_Cu, pcbnew.B_Cu),
                  "ESP32_ANTENNA_KEEPOUT")
    # panel-mount USB sockets: nothing under the front nut, no tracks next to the back body
    for i, (cx, cy) in enumerate(CFG.USB_HOLE_CENTERS):
        add_rule_area(board, circle_pts(cx, cy, CFG.USB_NUT_DIAMETER / 2), (pcbnew.F_Cu,), f"USB{i + 1}_NUT_F")
        add_rule_area(board, circle_pts(cx, cy, CFG.USB_BACK_KEEPOUT_DIAMETER / 2), (pcbnew.B_Cu,),
                      f"USB{i + 1}_BODY_B", pour=True)
    return xs


# ====================================================================== routing
def _poly_area(pts):
    return sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1])) / 2


def _cross(o, a, b):
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _triangulate(pts):
    """Ear-clipping triangulation of a simple polygon without holes."""
    clean = []
    for p in pts:
        if not clean or math.hypot(p[0] - clean[-1][0], p[1] - clean[-1][1]) > 1e-3:
            clean.append(p)
    if len(clean) > 1 and math.hypot(clean[0][0] - clean[-1][0], clean[0][1] - clean[-1][1]) < 1e-3:
        clean.pop()
    if _poly_area(clean) < 0:
        clean.reverse()
    changed = True
    while changed and len(clean) > 3:            # drop collinear vertices
        changed = False
        for k in range(len(clean)):
            a, b, c = clean[k - 1], clean[k], clean[(k + 1) % len(clean)]
            if abs(_cross(a, b, c)) < 1e-2:
                clean.pop(k)
                changed = True
                break
    idx = list(range(len(clean)))
    tris = []
    while len(idx) > 3:
        n = len(idx)
        for k in range(n):
            i0, i1, i2 = idx[k - 1], idx[k], idx[(k + 1) % n]
            a, b, c = clean[i0], clean[i1], clean[i2]
            if _cross(a, b, c) <= 0:
                continue
            if any(_cross(a, b, clean[j]) >= 0 and _cross(b, c, clean[j]) >= 0 and _cross(c, a, clean[j]) >= 0
                   for j in idx if j not in (i0, i1, i2)):
                continue
            tris.append((a, b, c))
            idx.pop(k)
            break
        else:
            raise RuntimeError("keepout triangulation failed")
    tris.append(tuple(clean[i] for i in idx))
    return tris


def rectangularize_dsn_boundary(dsn_path, clearance_mm=0.45):
    """Freerouting mis-handles slanted board outlines (pads near the slanted edges become unreachable).
    Hand it the bounding rectangle as the routing boundary and model everything outside the real outline,
    pulled in by the copper-to-edge clearance, as triangulated keepouts."""
    with open(dsn_path, encoding="utf-8") as fh:
        txt = fh.read()
    m = re.search(r"\(boundary\s*\(path pcb 0\s+([-\d\s\.]+)\)\s*\)", txt)
    if not m:
        raise RuntimeError("DSN boundary not found")
    nums = [float(v) for v in m.group(1).split()]
    pts = list(zip(nums[0::2], nums[1::2]))
    if pts[0] == pts[-1]:
        pts.pop()
    inner = pcbnew.SHAPE_POLY_SET()
    inner.NewOutline()
    for x, y in pts:                                    # DSN um -> nm
        inner.Append(int(round(x * 1000)), int(round(y * 1000)))
    inner.Deflate(int(clearance_mm * 1e6), pcbnew.CORNER_STRATEGY_ALLOW_ACUTE_CORNERS, 2000)
    bb = inner.BBox()
    x0, y0, x1, y1 = bb.GetLeft(), bb.GetTop(), bb.GetRight(), bb.GetBottom()
    outside = pcbnew.SHAPE_POLY_SET()
    outside.NewOutline()
    for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        outside.Append(x, y)
    outside.BooleanSubtract(inner)
    keepouts = []
    for i in range(outside.OutlineCount()):
        o = outside.Outline(i)
        opts = [(o.CPoint(j).x / 1000.0, o.CPoint(j).y / 1000.0) for j in range(o.PointCount())]
        if abs(_poly_area(opts)) < 1e4:                 # < 0.01 mm^2 slivers
            continue
        for tri in _triangulate(opts):
            body = "  ".join(f"{x:.1f} {y:.1f}" for x, y in tri + (tri[0],))
            keepouts.append(f'(keepout "" (polygon signal 0  {body}))')
    X0, Y0, X1, Y1 = x0 / 1000.0, y0 / 1000.0, x1 / 1000.0, y1 / 1000.0
    rect = [(X0, Y0), (X0, Y1), (X1, Y1), (X1, Y0), (X0, Y0)]
    if _poly_area(rect[:-1]) * _poly_area(pts) < 0:      # keep the exporter's winding
        rect = rect[::-1]
    boundary = "(boundary\n      (path pcb 0  " + "  ".join(f"{x:.1f} {y:.1f}" for x, y in rect) + ")\n    )"
    boundary += "".join("\n    " + k for k in keepouts)
    txt = txt[:m.start()] + boundary + txt[m.end():]
    with open(dsn_path, "w", encoding="utf-8") as fh:
        fh.write(txt)
    log(f"  DSN: rectangular boundary + {len(keepouts)} outside keepouts")


def _export_dsn(board, dsn):
    if os.path.exists(dsn):
        os.remove(dsn)
    polys = pcbnew.SHAPE_POLY_SET()
    if not board.GetBoardPolygonOutlines(polys, False):
        raise RuntimeError("board outline is not closed")
    if not pcbnew.ExportSpecctraDSN(board, dsn):
        raise RuntimeError("DSN export failed")
    rectangularize_dsn_boundary(dsn)


def _child_spans(txt, start):
    """Spans of the direct child lists of the S-expression list that opens at txt[start]."""
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
    """Same board, different component and net order (Freerouting routes in item order)."""
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


def _freeroute(dsn, ses, passes):
    """One Freerouting run; returns (unrouted, violations) or None."""
    if os.path.exists(ses):
        os.remove(ses)
    res = run([JAVA, "-jar", FREEROUTING_JAR, "-de", dsn, "-do", ses, f"--router.autorouter.max_passes={passes}",
               "--router.max_threads=8", "--router.automatic_neckdown=false", "--gui.enabled=false"],
              timeout=3600, check=False)
    text = res.stdout + res.stderr
    with open(os.path.join(BUILD, "freerouting.log"), "a", encoding="utf-8") as fh:
        fh.write(text)
    m = re.findall(r"Auto-routing stage completed.*?\((\d+) unrouted and (\d+) violations?\)", text)
    if not m or not os.path.exists(ses):
        return None
    return int(m[-1][0]), int(m[-1][1])


def autoroute(board, passes, attempts=6):
    """Route with Freerouting. It is deterministic for a given input and can stall with one or two
    connections left, so retries shuffle the component and net order in the DSN (same board, different
    routing order); the best attempt is kept."""
    os.makedirs(BUILD, exist_ok=True)
    if not os.path.exists(FREEROUTING_JAR):
        raise RuntimeError(f"Freerouting not found: {FREEROUTING_JAR} (set FREEROUTING_JAR)")
    dsn = os.path.join(BUILD, NAME + ".dsn")
    ses = os.path.join(BUILD, NAME + ".ses")
    open(os.path.join(BUILD, "freerouting.log"), "w").close()
    _export_dsn(board, dsn)
    with open(dsn, encoding="utf-8") as fh:
        base = fh.read()
    tries = [os.path.join(BUILD, f"{NAME}_try{i}.ses") for i in range(1, attempts + 1)]
    best = None
    for attempt, out in enumerate(tries, 1):
        if attempt > 1:
            with open(dsn, "w", encoding="utf-8") as fh:
                fh.write(_shuffle_dsn(base, attempt))
        result = _freeroute(dsn, out, passes)
        log(f"    attempt {attempt}: " + ("no result" if result is None else
                                          f"{result[0]} unrouted, {result[1]} violations"))
        if result is not None and (best is None or result < best[0]):
            best = (result, out)
        if result == (0, 0):
            break
    if best is None:
        raise RuntimeError("Freerouting did not produce a session file")
    shutil.copyfile(best[1], ses)
    for f in tries:
        if os.path.exists(f):
            os.remove(f)
    if not pcbnew.ImportSpecctraSES(board, ses):
        raise RuntimeError("SES import failed")


def normalize_vias(board, min_ring=0.15):
    """Specctra sessions carry no drill sizes, so KiCad takes the drill from the net class: a 0.6 mm via that
    Freerouting placed on a Power net comes back as 0.6/0.4 (0.1 mm ring). Shrink such drills."""
    fixed = 0
    for t in board.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T:
            dia = pcbnew.ToMM(t.GetWidth(pcbnew.F_Cu))
            if (dia - pcbnew.ToMM(t.GetDrillValue())) / 2 < min_ring - 1e-6:
                t.SetDrill(MM(round(dia - 2 * min_ring, 2)))
                fixed += 1
    return fixed


# ====================================================================== zones & stitching
def add_gnd_zones(board):
    gnd = board.FindNet("GND")
    pts = outline_polygon_points()
    zones = []
    for layer, name in ((pcbnew.F_Cu, "GND_FRONT"), (pcbnew.B_Cu, "GND_BACK")):
        z = pcbnew.ZONE(board)
        z.SetLayer(layer)
        z.SetNet(gnd)
        z.SetZoneName(name)
        z.SetLocalClearance(MM(0.3))
        z.SetMinThickness(MM(0.25))
        z.SetThermalReliefGap(MM(0.5))
        z.SetThermalReliefSpokeWidth(MM(0.5))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        z.SetAssignedPriority(0)
        ol = z.Outline()
        ol.NewOutline()
        for x, y in pts:
            v = P(x, y)
            ol.Append(v.x, v.y)
        board.Add(z)
        zones.append(z)
    return zones


def add_ldo_heatsink(board):
    """+3V3 copper pour on the back around the AMS1117 tab. At 100 % lit the OLED alone draws 345 mA
    (375 mA max) from 3.3 V, i.e. ~0.65 W in U4, so the tab needs more copper than a track."""
    u4 = next(fp for fp in board.GetFootprints() if fp.GetReference() == "U4")
    pads = {}
    for p in u4.Pads():
        pads.setdefault(p.GetNumber(), []).append(p)
    tab = max(pads["2"], key=lambda p: p.GetSize(pcbnew.B_Cu).x * p.GetSize(pcbnew.B_Cu).y)
    tx, ty = pcbnew.ToMM(tab.GetPosition().x), pcbnew.ToMM(tab.GetPosition().y)
    pins = pads["1"] + pads["3"]
    px = sum(pcbnew.ToMM(p.GetPosition().x) for p in pins) / len(pins)
    py = sum(pcbnew.ToMM(p.GetPosition().y) for p in pins) / len(pins)
    length = math.hypot(tx - px, ty - py)
    dx, dy = (tx - px) / length, (ty - py) / length          # unit vector from the pins to the tab
    nx, ny = -dy, dx
    near, far, half = 3.3, 9.0, 5.5
    corners = [(tx - near * dx - half * nx, ty - near * dy - half * ny),
               (tx - near * dx + half * nx, ty - near * dy + half * ny),
               (tx + far * dx + half * nx, ty + far * dy + half * ny),
               (tx + far * dx - half * nx, ty + far * dy - half * ny)]
    z = pcbnew.ZONE(board)
    z.SetLayer(pcbnew.B_Cu)
    z.SetNet(board.FindNet("+3V3"))
    z.SetZoneName("LDO_HEATSINK_3V3")
    z.SetLocalClearance(MM(0.3))
    z.SetMinThickness(MM(0.25))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    z.SetAssignedPriority(1)
    ol = z.Outline()
    ol.NewOutline()
    for x, y in corners:
        ol.Append(MM(x), MM(y))
    board.Add(z)
    return z


def fill_zones(board):
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())


def _seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def add_stitching_vias(board, zones, pitch=10.0, avoid=()):
    gnd = board.FindNet("GND")
    via_d, via_drill, clr = 0.6, 0.3, 0.35
    outline = pcbnew.SHAPE_POLY_SET()
    board.GetBoardPolygonOutlines(outline, False)
    outline.Deflate(MM(2.0), pcbnew.CORNER_STRATEGY_ALLOW_ACUTE_CORNERS, MM(0.05))
    rule_areas = [board.GetArea(i) for i in range(board.GetAreaCount()) if board.GetArea(i).GetIsRuleArea()]
    tracks = []
    for t in board.GetTracks():
        w = t.GetWidth(pcbnew.F_Cu) if t.Type() == pcbnew.PCB_VIA_T else t.GetWidth()
        tracks.append((pcbnew.ToMM(t.GetStart().x), pcbnew.ToMM(t.GetStart().y), pcbnew.ToMM(t.GetEnd().x),
                       pcbnew.ToMM(t.GetEnd().y), pcbnew.ToMM(w) / 2))
    boxes = []
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            bb = pad.GetBoundingBox()
            m = 0.9 if pad.GetDrillSizeX() == 0 else 1.0
            boxes.append((pcbnew.ToMM(bb.GetLeft()) - m, pcbnew.ToMM(bb.GetTop()) - m,
                          pcbnew.ToMM(bb.GetRight()) + m, pcbnew.ToMM(bb.GetBottom()) + m))
    fz, bz = zones
    added = 0
    tw = CFG.TOP_WIDTH / 2
    y = 3.0
    while y < CFG.HEIGHT - 2.0:
        x = -tw
        while x < tw:
            v = P(x, y)
            bx, by = pcbnew.ToMM(v.x), pcbnew.ToMM(v.y)
            ok = outline.Contains(v)
            if ok:
                ok = not any(z.Outline().Contains(v) for z in rule_areas)
            if ok:
                ok = not any(z.Outline().Contains(v) for z in avoid)
            if ok:
                ok = not any(b[0] <= bx <= b[2] and b[1] <= by <= b[3] for b in boxes)
            if ok:
                ok = all(_seg_dist(bx, by, *t[:4]) > t[4] + via_d / 2 + clr for t in tracks)
            if ok and (fz.HitTestFilledArea(pcbnew.F_Cu, v, 0) or bz.HitTestFilledArea(pcbnew.B_Cu, v, 0)):
                via = pcbnew.PCB_VIA(board)
                via.SetPosition(v)
                try:
                    via.SetWidth(MM(via_d))
                except TypeError:
                    via.SetWidth(pcbnew.F_Cu, MM(via_d))
                via.SetDrill(MM(via_drill))
                via.SetNet(gnd)
                board.Add(via)
                tracks.append((bx, by, bx, by, via_d / 2))
                added += 1
            x += pitch
        y += pitch
    return added


# ====================================================================== checks & outputs
def kicad_cli(*args, timeout=900, check=True):
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
    for v in (errors + warns)[:25]:
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
        for v in (errs + warns)[:30]:
            items = "; ".join(i.get("description", "") for i in v.get("items", []))
            log(f"    [{v.get('severity')}] {v.get('type')}: {v.get('description')} -- {items[:170]}")
    return summary


def export_outputs(render=True):
    gdir = os.path.join(PROD, "gerbers")
    os.makedirs(gdir, exist_ok=True)
    for fn in os.listdir(gdir):        # clear files only: OneDrive may lock the folder itself
        os.remove(os.path.join(gdir, fn))
    kicad_cli("pcb", "export", "gerbers", "-o", gdir + os.sep, "--layers",
              "F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts",
              "--subtract-soldermask", "--check-zones", PCB)
    kicad_cli("pcb", "export", "drill", "-o", gdir + os.sep, "--format", "excellon", "--excellon-units", "mm",
              "--excellon-zeros-format", "decimal", "--excellon-oval-format", "alternate", "--excellon-separate-th",
              "--generate-map", "--map-format", "gerberx2", PCB)
    zname = NAME + ("_gerbers_jlcpcb.zip" if CFG.DIMENSIONS_CONFIRMED else "_gerbers_jlcpcb_DRAFT_dims_unconfirmed.zip")
    for stale in (NAME + "_gerbers_jlcpcb.zip", NAME + "_gerbers_jlcpcb_DRAFT_dims_unconfirmed.zip"):
        if stale != zname and os.path.exists(os.path.join(PROD, stale)):
            os.remove(os.path.join(PROD, stale))
    zpath = os.path.join(PROD, zname)
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for fn in sorted(os.listdir(gdir)):
            z.write(os.path.join(gdir, fn), fn)
    log(f"  gerber zip: {zpath} ({len(os.listdir(gdir))} files)")

    os.makedirs(DOCS, exist_ok=True)
    kicad_cli("sch", "export", "pdf", "-o", os.path.join(DOCS, NAME + "_schematic.pdf"), SCH)
    export_fit_template()
    kicad_cli("pcb", "export", "pdf", "-o", os.path.join(DOCS, NAME + "_pcb_front.pdf"), "--layers",
              "F.Cu,F.SilkS,F.Mask,Edge.Cuts,F.Fab", "--mode-single", "--include-border-title", PCB, check=False)
    if render:
        common = ["--width", "2000", "--height", "1500", "--quality", "high", "--background", "opaque",
                  "--use-board-stackup-colors"]
        kicad_cli("pcb", "render", "-o", os.path.join(DOCS, "render_front.png"), "--side", "top", *common, PCB,
                  timeout=1800)
        kicad_cli("pcb", "render", "-o", os.path.join(DOCS, "render_back.png"), "--side", "bottom", *common, PCB,
                  timeout=1800)
        kicad_cli("pcb", "render", "-o", os.path.join(DOCS, "render_iso.png"), "--rotate", "-35,0,20",
                  "--perspective", "--zoom", "0.9", *common, PCB, timeout=1800)
        kicad_cli("pcb", "export", "step", "-o", os.path.join(DOCS, NAME + ".step"), "--subst-models", "--force",
                  PCB, timeout=1800, check=False)


def write_bom():
    rows = {}
    for p in D.PARTS:
        key = (p["footprint"], p["mpn"] or p["value"], p["dnp"])
        rows.setdefault(key, []).append(p)
    path = os.path.join(PROD, NAME + "_bom.csv")

    def refkey(r):
        return re.match(r"[A-Z]+", r).group(0), int(re.search(r"\d+", r).group(0))

    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Designators", "Qty", "Value", "Footprint", "Part / suggestion", "Description", "Populate"])
        for (fp, _, dnp), parts in sorted(rows.items(), key=lambda kv: min(refkey(p["ref"]) for p in kv[1])):
            parts.sort(key=lambda p: refkey(p["ref"]))
            refs = [p["ref"] for p in parts]
            values = list(dict.fromkeys(p["value"] for p in parts))
            descs = list(dict.fromkeys(p["desc"] for p in parts))
            desc = descs[0] if len(descs) == 1 else os.path.commonprefix(descs).strip() + "s"
            board_only = all(re.match(r"^(H|JP)\d", r) for r in refs)
            populate = "board feature (no part)" if board_only else ("optional" if dnp else "yes")
            w.writerow([" ".join(refs), len(refs), " / ".join(values), fp.split(":")[-1], parts[0]["mpn"], desc,
                        populate])
    log(f"  BOM: {path}")


def set_stackup_colors(path):
    """Black solder mask + white silkscreen (render colours; choose the same at JLCPCB)."""
    with open(path, encoding="utf-8") as fh:
        txt = fh.read()
    if "(stackup" in txt:
        return
    stack = ('\t\t(stackup\n'
             '\t\t\t(layer "F.SilkS" (type "Top Silk Screen") (color "White"))\n'
             '\t\t\t(layer "F.Paste" (type "Top Solder Paste"))\n'
             '\t\t\t(layer "F.Mask" (type "Top Solder Mask") (color "Black") (thickness 0.01))\n'
             '\t\t\t(layer "F.Cu" (type "copper") (thickness 0.035))\n'
             '\t\t\t(layer "dielectric 1" (type "core") (thickness 1.51) (material "FR4") (epsilon_r 4.5) '
             '(loss_tangent 0.02))\n'
             '\t\t\t(layer "B.Cu" (type "copper") (thickness 0.035))\n'
             '\t\t\t(layer "B.Mask" (type "Bottom Solder Mask") (color "Black") (thickness 0.01))\n'
             '\t\t\t(layer "B.Paste" (type "Bottom Solder Paste"))\n'
             '\t\t\t(layer "B.SilkS" (type "Bottom Silk Screen") (color "White"))\n'
             '\t\t\t(copper_finish "HAL lead-free")\n'
             '\t\t\t(dielectric_constraints no)\n'
             '\t\t)\n')
    txt = re.sub(r"(\(setup\s*\n)", lambda m: m.group(1) + stack, txt, count=1)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(txt)


# ====================================================================== 1:1 fit template (printable PDF)
MM_PT = 72.0 / 25.4
_HELV = {" ": 278, "!": 278, '"': 355, "#": 556, "%": 889, "&": 667, "'": 191, "(": 333, ")": 333, "*": 389,
         "+": 584, ",": 278, "-": 333, ".": 278, "/": 278, ":": 278, ";": 278, "<": 584, "=": 584, ">": 584,
         "?": 556, "[": 278, "]": 278, "_": 556, "|": 260, "~": 584, "°": 400, "×": 584, "Ø": 778, "µ": 556,
         "A": 667, "B": 667, "C": 722, "D": 722, "E": 667, "F": 611, "G": 778, "H": 722, "I": 278, "J": 500,
         "K": 667, "L": 556, "M": 833, "N": 722, "O": 778, "P": 667, "Q": 778, "R": 722, "S": 667, "T": 611,
         "U": 722, "V": 667, "W": 944, "X": 667, "Y": 667, "Z": 611, "f": 278, "i": 222, "j": 222, "l": 222,
         "m": 833, "r": 333, "t": 278, "w": 722, "c": 500, "k": 500, "s": 500, "v": 500, "x": 500, "y": 500,
         "z": 500}


class _FitPdf:
    """Minimal vector PDF writer: US Letter landscape, y measured downwards from the top, units in points."""
    W, H = 792.0, 612.0

    def __init__(self):
        self.pages = []
        self.ops = None

    def page(self):
        self.ops = []
        self.pages.append(self.ops)

    def stroke(self, width, rgb=(0, 0, 0), dash=None):
        d = f"[{' '.join(f'{v:.2f}' for v in dash)}] 0 d" if dash else "[] 0 d"
        self.ops.append(f"{width:.2f} w {rgb[0]:.3f} {rgb[1]:.3f} {rgb[2]:.3f} RG {d} 1 J 1 j")

    def fill(self, rgb):
        self.ops.append(f"{rgb[0]:.3f} {rgb[1]:.3f} {rgb[2]:.3f} rg")

    def path(self, pts, close=False, op="S"):
        s = f"{pts[0][0]:.3f} {self.H - pts[0][1]:.3f} m " + " ".join(f"{x:.3f} {self.H - y:.3f} l" for x, y in pts[1:])
        self.ops.append(s + (" h" if close else "") + f" {op}")

    def circle(self, cx, cy, r, op="S"):
        k, y = 0.5522847498 * r, self.H - cy
        self.ops.append(f"{cx + r:.3f} {y:.3f} m {cx + r:.3f} {y + k:.3f} {cx + k:.3f} {y + r:.3f} {cx:.3f} {y + r:.3f} c "
                        f"{cx - k:.3f} {y + r:.3f} {cx - r:.3f} {y + k:.3f} {cx - r:.3f} {y:.3f} c "
                        f"{cx - r:.3f} {y - k:.3f} {cx - k:.3f} {y - r:.3f} {cx:.3f} {y - r:.3f} c "
                        f"{cx + k:.3f} {y - r:.3f} {cx + r:.3f} {y - k:.3f} {cx + r:.3f} {y:.3f} c h {op}")

    @staticmethod
    def width(s, size):
        return sum(_HELV.get(ch, 556) for ch in s) * size / 1000.0

    def text(self, x, y, s, size=7.0, bold=False, rgb=(0.1, 0.1, 0.1), align="left", rot=0):
        w = self.width(s, size)
        off = {"left": 0.0, "center": -w / 2, "right": -w}[align]
        esc = s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        if rot == 90:      # reads bottom-to-top; the offset runs along the (vertical) baseline
            tm = f"0 1 -1 0 {x:.3f} {self.H - y + off:.3f}"
        else:
            tm = f"1 0 0 1 {x + off:.3f} {self.H - y:.3f}"
        self.ops.append(f"BT /{'F2' if bold else 'F1'} {size:.2f} Tf {rgb[0]:.3f} {rgb[1]:.3f} {rgb[2]:.3f} rg "
                        f"{tm} Tm ({esc}) Tj ET")

    def save(self, path):
        objs = []

        def add(body):
            objs.append(body)
            return len(objs)

        catalog, pages = add(b""), add(b"")
        f1 = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
        f2 = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
        kids = []
        for ops in self.pages:
            data = "\n".join(ops).encode("latin-1", "replace")
            cs = add(b"<< /Length %d >>\nstream\n" % len(data) + data + b"\nendstream")
            kids.append(add(f"<< /Type /Page /Parent {pages} 0 R /MediaBox [0 0 {self.W:.0f} {self.H:.0f}] "
                            f"/Resources << /Font << /F1 {f1} 0 R /F2 {f2} 0 R >> >> /Contents {cs} 0 R >>".encode()))
        # PrintScaling /None makes viewers default to "actual size" instead of "fit to page"
        objs[catalog - 1] = (f"<< /Type /Catalog /Pages {pages} 0 R "
                             f"/ViewerPreferences << /PrintScaling /None >> >>").encode()
        objs[pages - 1] = f"<< /Type /Pages /Kids [{' '.join(f'{k} 0 R' for k in kids)}] /Count {len(kids)} >>".encode()
        out = bytearray(b"%PDF-1.6\n%\xe2\xe3\xcf\xd3\n")
        offsets = []
        for i, body in enumerate(objs, 1):
            offsets.append(len(out))
            out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
        xref = len(out)
        out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
        for o in offsets:
            out += b"%010d 00000 n \n" % o
        out += b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, catalog, xref)
        with open(path, "wb") as fh:
            fh.write(out)


def _arc_points(s, m, e, step_deg=2.0):
    (x1, y1), (x2, y2), (x3, y3) = s, m, e
    d = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
    if abs(d) < 1e-9:
        return [s, e]
    ux = ((x1 * x1 + y1 * y1) * (y2 - y3) + (x2 * x2 + y2 * y2) * (y3 - y1) + (x3 * x3 + y3 * y3) * (y1 - y2)) / d
    uy = ((x1 * x1 + y1 * y1) * (x3 - x2) + (x2 * x2 + y2 * y2) * (x1 - x3) + (x3 * x3 + y3 * y3) * (x2 - x1)) / d
    r = math.hypot(x1 - ux, y1 - uy)
    a1, a2, a3 = (math.atan2(y - uy, x - ux) for x, y in (s, m, e))
    sweep13, sweep12 = (a3 - a1) % (2 * math.pi), (a2 - a1) % (2 * math.pi)
    sweep = sweep13 if sweep12 <= sweep13 else sweep13 - 2 * math.pi
    n = max(2, int(abs(math.degrees(sweep)) / step_deg) + 1)
    return [(ux + r * math.cos(a1 + sweep * i / n), uy + r * math.sin(a1 + sweep * i / n)) for i in range(n + 1)]


def _mm(v):
    return pcbnew.ToMM(v.x) - CFG.PAGE_ORIGIN[0], pcbnew.ToMM(v.y) - CFG.PAGE_ORIGIN[1]


def _geom(s):
    """PCB_SHAPE -> ('poly', points, closed) or ('circle', centre, radius), panel mm (front view)."""
    st = s.GetShape()
    if st == pcbnew.SHAPE_T_SEGMENT:
        return "poly", [_mm(s.GetStart()), _mm(s.GetEnd())], False
    if st in (pcbnew.SHAPE_T_RECTANGLE, pcbnew.SHAPE_T_RECT):
        (x1, y1), (x2, y2) = _mm(s.GetStart()), _mm(s.GetEnd())
        return "poly", [(x1, y1), (x2, y1), (x2, y2), (x1, y2)], True
    if st == pcbnew.SHAPE_T_CIRCLE:
        return "circle", _mm(s.GetCenter()), pcbnew.ToMM(s.GetRadius())
    if st == pcbnew.SHAPE_T_ARC:
        return "poly", _arc_points(_mm(s.GetStart()), _mm(s.GetArcMid()), _mm(s.GetEnd())), False
    if st == pcbnew.SHAPE_T_POLY:
        ol = s.GetPolyShape().Outline(0)
        return "poly", [_mm(ol.CPoint(i)) for i in range(ol.PointCount())], True
    return None


def export_fit_template(path=None):
    """1:1 printable template of the panel (front view) to test-fit it in the car: cut line, holes, front parts,
    and the outlines of tall parts behind the panel."""
    path = path or os.path.join(DOCS, NAME + "_fit_template_1to1.pdf")
    board = pcbnew.LoadBoard(PCB)
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}

    def layer_geoms(items, layer):
        return [g for g in (_geom(i) for i in items if isinstance(i, pcbnew.PCB_SHAPE) and i.GetLayerName() == layer)
                if g]

    edge = layer_geoms(board.GetDrawings(), "Edge.Cuts")
    usb_cut = [g for r in ("H5", "H6") for g in layer_geoms(fps[r].GraphicalItems(), "Edge.Cuts")]
    usb_nut = [g for r in ("H5", "H6") for g in layer_geoms(fps[r].GraphicalItems(), "F.Fab")]
    front = {r: layer_geoms(fps[r].GraphicalItems(), "F.Fab") for r in ("U2", "SW1", "D1", "D2", "D3", "D4")
             if r in fps}
    silk = layer_geoms(board.GetDrawings(), "F.Silkscreen")
    just = {pcbnew.GR_TEXT_H_ALIGN_LEFT: "left", pcbnew.GR_TEXT_H_ALIGN_RIGHT: "right"}
    labels = [(t.GetText(), _mm(t.GetPosition()), just.get(t.GetHorizJustify(), "center"))
              for t in board.GetDrawings() if isinstance(t, pcbnew.PCB_TEXT) and t.GetLayerName() == "F.Silkscreen"]
    behind = {  # ref: (label, approximate depth behind the panel, where to put the label)
        "A1": ("ESP32 DevKit on sockets", "~14 mm", "inside-bottom"), "U1": ("CC1101 + SMA", "~16 mm", "right"),
        "J1": ("12 V terminal", "~10 mm", "left"), "U3": ("5 V regulator", "~10 mm", "left"),
        "BZ1": ("buzzer", "~10 mm", "below"), "C1": ("47 µF cap", "~8 mm", "right")}
    back = {r: layer_geoms(fps[r].GraphicalItems(), "B.Fab") for r in behind if r in fps}
    holes = [(_mm(p.GetPosition()), pcbnew.ToMM(p.GetDrillSize().x), fp.GetReference()) for fp in fps.values()
             for p in fp.Pads() if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH]

    outline_pts = [p for kind, *rest in edge if kind == "poly" for p in rest[0]]
    x0, x1 = min(p[0] for p in outline_pts), max(p[0] for p in outline_pts)
    y0, y1 = min(p[1] for p in outline_pts), max(p[1] for p in outline_pts)
    bottom = [g[1] for g in edge if g[0] == "poly" and len(g[1]) == 2 and all(abs(p[1] - y1) < 0.01 for p in g[1])]
    bottom_w = abs(bottom[0][1][0] - bottom[0][0][0]) if bottom else 0.0
    notch = [g[1] for g in edge if g[0] == "poly" and len(g[1]) > 2]

    ox, oy = _FitPdf.W / 2, 74.0          # page position of the panel origin (top-centre)

    def P(x, y):
        return ox + x * MM_PT, oy + y * MM_PT

    def draw(pdf, geoms, width, rgb, dash=None, close_polys=False):
        pdf.stroke(width, rgb, dash)
        for g in geoms:
            if g[0] == "circle":
                pdf.circle(*P(*g[1]), g[2] * MM_PT)
            else:
                pdf.path([P(*p) for p in g[1]], close=g[2] or close_polys)

    def cross(pdf, x, y, size=2.0):
        pdf.path([P(x - size, y), P(x + size, y)])
        pdf.path([P(x, y - size), P(x, y + size)])

    def cut_layer(pdf):
        draw(pdf, edge, 1.1, (0, 0, 0))
        draw(pdf, usb_cut, 1.1, (0, 0, 0))
        pdf.stroke(0.35, (0, 0, 0))
        for g in usb_cut:
            cross(pdf, *g[1], 3.0)
        for (x, y), d, ref in holes:
            if ref.startswith("H"):
                pdf.stroke(0.6, (0, 0, 0))
                pdf.circle(*P(x, y), d / 2 * MM_PT)
                pdf.stroke(0.3, (0, 0, 0))
                cross(pdf, x, y, 2.2)

    def scale_bars(pdf, x, y):
        pdf.stroke(0.8, (0, 0, 0))
        pdf.path([(x, y), (x + 100 * MM_PT, y)])
        for i in range(11):
            t = 4.0 if i % 5 == 0 else 2.2
            pdf.path([(x + i * 10 * MM_PT, y - t), (x + i * 10 * MM_PT, y + t)])
        pdf.text(x + 50 * MM_PT, y - 6, "100 mm  (measure: must be exactly 100 mm)", 7, align="center")
        y2 = y + 22
        pdf.path([(x, y2), (x + 4 * 72.0, y2)])
        for i in range(9):
            t = 4.0 if i % 2 == 0 else 2.2
            pdf.path([(x + i * 36.0, y2 - t), (x + i * 36.0, y2 + t)])
        pdf.text(x + 2 * 72.0, y2 + 11, "4 in  (must be exactly 4 inches)", 7, align="center")

    pdf = _FitPdf()
    # ---------------------------------------------------------------- page 1: annotated template
    pdf.page()
    status = "DRAFT dimensions (scaled from the report image)" if not CFG.DIMENSIONS_CONFIRMED else "dimensions confirmed"
    pdf.text(36, 30, "TPMS panel - 1:1 fit template (front view, as seen from the driver's seat)", 12, bold=True)
    pdf.text(36, 44, f"{status}  -  generated {TODAY} from {NAME}.kicad_pcb  -  print at 100% / Actual size, "
                     "NOT 'Fit to page'", 7.5)
    # light 10 mm grid inside the trapezoid
    pdf.stroke(0.25, (0.82, 0.82, 0.82))
    half_top, half_bot = (x1 - x0) / 2, bottom_w / 2

    def half_width(y):
        return half_top + (half_bot - half_top) * (y - y0) / (y1 - y0)

    for gy in range(10, int(y1), 10):
        pdf.path([P(-half_width(gy), gy), P(half_width(gy), gy)])
    for gx in range(-int(half_top) // 10 * 10, int(half_top) + 1, 10):
        ymax = y1 if abs(gx) <= half_bot else (half_top - abs(gx)) * (y1 - y0) / (half_top - half_bot)
        if ymax > 1:
            pdf.path([P(gx, y0), P(gx, ymax)])
    # parts behind the panel (red dashed), labelled beside their outline
    red = (0.75, 0.1, 0.1)
    for ref, geoms in back.items():
        draw(pdf, geoms, 0.6, (0.85, 0.12, 0.12), dash=(3, 2))
        xs = [v for g in geoms for v in ([p[0] for p in g[1]] if g[0] == "poly" else [g[1][0] - g[2], g[1][0] + g[2]])]
        ys = [v for g in geoms for v in ([p[1] for p in g[1]] if g[0] == "poly" else [g[1][1] - g[2], g[1][1] + g[2]])]
        bx0, bx1, by0, by1 = min(xs), max(xs), min(ys), max(ys)
        cx, cy = (bx0 + bx1) / 2, (by0 + by1) / 2
        name, depth, where = behind[ref]
        ax, ay, align = {"inside-bottom": (cx, by1 - 4.6, "center"), "below": (cx, by1 + 3.2, "center"),
                         "left": (bx0 - 1.5, cy - 0.4, "right"), "right": (bx1 + 1.5, cy - 0.4, "left")}[where]
        pdf.text(*P(ax, ay), name, 6, rgb=red, align=align)
        pdf.text(*P(ax, ay + 2.6), f"{depth} behind", 5.5, rgb=red, align=align)
    # front parts (blue)
    blue = (0.0, 0.32, 0.78)
    for ref, geoms in front.items():
        draw(pdf, geoms, 0.6, blue)
    draw(pdf, usb_nut, 0.5, blue, dash=(2, 2))
    draw(pdf, silk, 0.4, (0.45, 0.45, 0.45))
    for s, (x, y), align in labels:
        pdf.text(*P(x, y + 1.2), s, 7, rgb=(0.4, 0.4, 0.4), align=align)
    for (x, y), d, ref in holes:
        if ref == "U2":
            pdf.stroke(0.4, blue)
            pdf.circle(*P(x, y), d / 2 * MM_PT)
    u2 = _mm(fps["U2"].GetPosition())
    u2_top = min(p[1] for g in front["U2"] if g[0] == "poly" for p in g[1])
    pdf.text(*P(u2[0], u2_top + 4.3), "DISPLAY NHD-2.7 module 82 × 47.5 mm", 7, rgb=blue, align="center")
    pdf.text(*P(u2[0], u2_top + 7.4), "glass ~7 mm in front of the board", 6, rgb=blue, align="center")
    shaft = [g[1] for g in front.get("SW1", []) if g[0] == "circle"]
    if shaft:
        sx, sy = shaft[0]
        pdf.stroke(0.6, blue, dash=(4, 2))
        pdf.circle(*P(sx, sy), CFG.KNOB_DIAMETER / 2 * MM_PT)
        pdf.stroke(0.35, blue)
        cross(pdf, sx, sy, 2.5)
        pdf.text(*P(sx, sy + CFG.KNOB_DIAMETER / 2 + 4), f"knob Ø{CFG.KNOB_DIAMETER:g} (shaft ~20 mm tall)", 6,
                 rgb=blue, align="center")
    for g in usb_cut:
        cx, cy = g[1]
        pdf.text(*P(cx, cy - CFG.USB_NUT_DIAMETER / 2 - 2.0), f"USB socket: cut Ø{2 * g[2]:g}, nut Ø{CFG.USB_NUT_DIAMETER:g}",
                 6, rgb=blue, align="center")
    cut_layer(pdf)
    # origin marker and dimensions
    pdf.stroke(0.4, (0, 0, 0))
    cross(pdf, 0, 0, 2.5)
    pdf.text(*P(1.5, 4.5), "0,0", 6)
    dim = (0.25, 0.25, 0.25)
    pdf.stroke(0.4, dim)
    yt = P(0, y0)[1] - 12
    pdf.path([(P(x0, 0)[0], yt), (P(x1, 0)[0], yt)])
    for xx in (x0, x1):
        pdf.path([(P(xx, 0)[0], yt - 3), (P(xx, 0)[0], yt + 3)])
    pdf.text(ox, yt - 3, f"{x1 - x0:.1f} mm (top edge)", 7, align="center")
    yb = P(0, y1)[1] + 12
    pdf.path([(P(-half_bot, 0)[0], yb), (P(half_bot, 0)[0], yb)])
    for xx in (-half_bot, half_bot):
        pdf.path([(P(xx, 0)[0], yb - 3), (P(xx, 0)[0], yb + 3)])
    pdf.text(ox, yb + 9, f"{bottom_w:.1f} mm (bottom edge)", 7, align="center")
    xl = P(x0, 0)[0] - 12
    pdf.path([(xl, P(0, y0)[1]), (xl, P(0, y1)[1])])
    for yy in (y0, y1):
        pdf.path([(xl - 3, P(0, yy)[1]), (xl + 3, P(0, yy)[1])])
    pdf.text(xl - 3, (P(0, y0)[1] + P(0, y1)[1]) / 2, f"{y1 - y0:.1f} mm (height)", 7, align="center", rot=90)
    if notch:
        nx = max(p[0] for p in notch[0])
        ny = sum(p[1] for p in notch[0]) / len(notch[0])
        pdf.text(*P(nx + 3, ny + 1), f"notch R{CFG.NOTCH_R:g}, centre {CFG.NOTCH_Y:g} mm below top", 6)
    # notes, legend, scale bars (everything stays >= 18 pt from the paper edge for printer margins)
    scale_bars(pdf, 36, 482)
    legend = [((0, 0, 0), None, "thick black = cut line (board edge, USB holes); small circles = M3 holes"),
              (blue, None, "blue = front parts: display, LEDs, knob (dashed), USB nut (dashed)"),
              ((0.85, 0.12, 0.12), (3, 2), "red dashed = tall parts behind the panel (depth noted)"),
              ((0.45, 0.45, 0.45), None, "grey = silkscreen; light grid = 10 mm")]
    ly = 476
    for rgb, dash, s in legend:
        pdf.stroke(1.0 if rgb == (0, 0, 0) else 0.7, rgb, dash)
        pdf.path([(330, ly - 2.5), (352, ly - 2.5)])
        pdf.text(358, ly, s, 7)
        ly += 11
    feats = [("display module centre", u2), ("knob / encoder shaft", shaft[0] if shaft else None)]
    names = dict(zip(("D1", "D2", "D3", "D4"), CFG.LED_LABELS))
    for r in ("D1", "D2", "D3", "D4"):
        c = [g[1] for g in front.get(r, []) if g[0] == "circle"]
        if c:
            feats.append((f"LED {names[r]}", c[0]))
    feats += [(f"USB socket {i + 1}", g[1]) for i, g in enumerate(usb_cut)]
    feats += [(f"mount hole {ref}", (x, y)) for (x, y), d, ref in sorted(holes, key=lambda h: h[2])
              if ref.startswith("H")]
    ty = 527
    pdf.text(330, ty, "Feature positions, mm from top-centre (x right, y down, front view):", 7, bold=True)
    def num(v):
        return f"{v:+.2f}".rstrip("0").rstrip(".")

    for i, (name, xy) in enumerate(f for f in feats if f[1]):
        col, row = divmod(i, 7)
        pdf.text(330 + col * 150, ty + 11 + row * 8.5, f"{name}: ({num(xy[0])}, {num(xy[1]).lstrip('+')})", 6.5)
    notes = ["How to use: print at 100% / Actual size and check both bars with a ruler.",
             "Cut along the thick black lines and hold it in the dash from the driver's side.",
             "Then measure the real opening and send the numbers.",
             "Sticks out in front: display ~7 mm, LEDs ~9 mm, knob ~22 mm.",
             "Behind: up to ~16 mm, plus the 315 MHz antenna, which leaves",
             "through the top edge at the CC1101 SMA connector."]
    for i, s in enumerate(notes):
        pdf.text(36, 536 + i * 9.5, s, 6.5)
    # ---------------------------------------------------------------- page 2: clean outline for tracing
    pdf.page()
    pdf.text(36, 30, "TPMS panel - 1:1 outline only (trace onto cardboard or cut)", 12, bold=True)
    pdf.text(36, 44, f"{status}  -  generated {TODAY}  -  print at 100% / Actual size", 7.5)
    cut_layer(pdf)
    pdf.stroke(0.4, (0, 0, 0))
    cross(pdf, 0, 0, 2.5)
    scale_bars(pdf, 36, 482)
    pdf.save(path)
    log(f"  fit template: {path}")
    return path


# ====================================================================== main
def remind_dimensions():
    if not CFG.DIMENSIONS_CONFIRMED:
        log("!! REMINDER: panel dimensions are NOT confirmed (panel_config.DIMENSIONS_CONFIRMED = False).")
        log("!!   Outline, notch, USB cut-outs and mounting holes are scaled from the report image.")
        log("!!   Enter the real dimensions (and set the flag) before ordering from JLCPCB.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-route", action="store_true", help="place only, skip autorouting")
    ap.add_argument("--no-render", action="store_true", help="skip 3D renders / STEP export")
    ap.add_argument("--passes", type=int, default=100, help="Freerouting max passes")
    ap.add_argument("--template-only", action="store_true",
                    help="only write the 1:1 printable fit template from the current board")
    args = ap.parse_args()
    if args.template_only:
        os.makedirs(DOCS, exist_ok=True)
        export_fit_template()
        remind_dimensions()
        return

    import faulthandler
    faulthandler.dump_traceback_later(3600, exit=True)   # a hidden KiCad dialog would otherwise hang forever

    for d in (LIBDIR, FPLIB, MODELDIR, PROD, DOCS, BUILD):
        os.makedirs(d, exist_ok=True)
    remind_dimensions()

    log("[1/8] libraries")
    customs = custom_symbols()
    write_symbol_library(customs)
    build_footprints()
    build_models()
    write_lib_tables()

    log("[2/8] project + schematic")
    write_project()
    build_schematic(customs)
    errors, _ = run_erc()
    if errors:
        raise SystemExit("ERC errors - fix design.py first")
    netfile = os.path.join(BUILD, NAME + ".net")
    kicad_cli("sch", "export", "netlist", "--format", "kicadsexpr", "-o", netfile, SCH)
    comps = parse_netlist(netfile)
    log(f"  netlist: {len(comps)} components, {len({n for c in comps.values() for n in c['nets'].values()})} nets")

    log("[3/8] board placement")
    board, fps = build_board(comps)
    add_panel_graphics(board, fps)
    add_keepouts(board, fps)
    for ref, pads in (("A1", ("1", "15", "16", "30")), ("U1", ("1", "2", "7")), ("J2", ("1", "8")),
                      ("U2", ("1", "20")), ("U3", ("1", "3")), ("J1", ("1", "2"))):
        log(f"  {ref}: " + ", ".join(f"pad{n}={pad_xy(fps[ref], n)}" for n in pads))
    pcbnew.SaveBoard(PCB, board)

    if not args.no_route:
        log("[4/8] autorouting (Freerouting)")
        board = pcbnew.LoadBoard(PCB)
        autoroute(board, args.passes)
        n = normalize_vias(board)
        if n:
            log(f"  vias with < 0.15 mm ring re-drilled: {n}")
        pcbnew.SaveBoard(PCB, board)

    log("[5/8] ground pours + stitching")
    board = pcbnew.LoadBoard(PCB)
    zones = add_gnd_zones(board)
    heatsink = add_ldo_heatsink(board)
    fill_zones(board)
    n = add_stitching_vias(board, zones, avoid=(heatsink,))
    fill_zones(board)
    log(f"  stitching vias: {n}")
    pcbnew.SaveBoard(PCB, board)
    set_stackup_colors(PCB)

    log("[6/8] DRC")
    summary = run_drc()

    log("[7/8] fabrication outputs")
    export_outputs(render=not args.no_render)
    write_bom()

    log("[8/8] done")
    log(json.dumps(summary))
    remind_dimensions()
    errors = sum(e for e, _ in summary.values())
    if errors and not args.no_route:
        log(f"!! DRC reported {errors} error(s): see build/drc.json - do NOT order these Gerbers")
        sys.exit(2)


if __name__ == "__main__":
    main()
