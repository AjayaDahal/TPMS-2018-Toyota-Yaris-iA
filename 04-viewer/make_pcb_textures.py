#!/usr/bin/env python3
"""Render the v2 carrier's six copper layers as textures for the viewer's 3-D PCB scene.

    python 04-viewer/make_pcb_textures.py

Reads 01-hardware/v2/carrier/tpms_v2_carrier.kicad_pcb (run build_carrier.py first) with KiCad 10's kicad-cli and
writes viewer/media/pcb/L1.png ... L6.png: 1024 x 1024 px for the 100 x 100 mm board, seen from the parts side
(L6 is not mirrored, so every layer lines up when the stack is exploded). L1 and L6 carry their silkscreen. Needs
pymupdf and numpy.
"""
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

import numpy as np
import pymupdf

ROOT = pathlib.Path(__file__).resolve().parent.parent
PCB = ROOT / "01-hardware" / "v2" / "carrier" / "tpms_v2_carrier.kicad_pcb"
OUT = ROOT / "04-viewer" / "viewer" / "media" / "pcb"
BOARD_MM, ORIGIN_MM, PX = 100.0, 50.0, 1024           # the board sits at (50, 50) mm on the KiCad page

# (file, copper layer, silkscreen layer, solder-mask colour) - copper is drawn in one colour per layer
LAYERS = [("L1", "F.Cu", "F.Silkscreen", (17, 22, 31)), ("L2", "In1.Cu", None, (6, 40, 32)),
          ("L3", "In2.Cu", None, (24, 20, 40)), ("L4", "In3.Cu", None, (6, 40, 32)),
          ("L5", "In4.Cu", None, (15, 23, 42)), ("L6", "B.Cu", "B.Silkscreen", (17, 22, 31))]
COPPER = {"L1": (212, 160, 23), "L2": (16, 185, 129), "L3": (239, 68, 68), "L4": (5, 150, 105),
          "L5": (59, 130, 246), "L6": (180, 83, 9)}


def kicad_cli():
    cands = [shutil.which("kicad-cli"),
             os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "KiCad10", "bin", "kicad-cli.exe"),
             r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe"]
    return next((c for c in cands if c and os.path.exists(c)), None)


def mask(cli, layer, tmp):
    """Boolean array: True where `layer` has copper/ink, sampled on the board area."""
    pdf = pathlib.Path(tmp) / f"{layer.replace('.', '_')}.pdf"
    subprocess.run([cli, "pcb", "export", "pdf", "-o", str(pdf), "--layers", layer, "--mode-single",
                    "--black-and-white", "--scale", "1", str(PCB)], check=True, capture_output=True)
    doc = pymupdf.open(pdf)
    try:
        k = 72 / 25.4
        clip = pymupdf.Rect(ORIGIN_MM * k, ORIGIN_MM * k, (ORIGIN_MM + BOARD_MM) * k, (ORIGIN_MM + BOARD_MM) * k)
        zoom = PX / (BOARD_MM * k)
        pix = doc[0].get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=clip, colorspace=pymupdf.csGRAY)
    finally:
        doc.close()
    a = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
    a = a[:PX, :PX]
    if a.shape != (PX, PX):
        a = np.pad(a, ((0, PX - a.shape[0]), (0, PX - a.shape[1])), constant_values=255)
    return a < 128


def main():
    cli = kicad_cli()
    if not cli:
        sys.exit("kicad-cli not found")
    if not PCB.exists():
        sys.exit(f"{PCB} not found: run build_carrier.py first")
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for name, cu, silk, base in LAYERS:
            img = np.empty((PX, PX, 3), dtype=np.uint8)
            img[:] = base
            img[mask(cli, cu, tmp)] = COPPER[name]
            if silk:
                img[mask(cli, silk, tmp)] = (236, 240, 244)
            pix = pymupdf.Pixmap(pymupdf.csRGB, PX, PX, img.tobytes(), False)
            pix.save(str(OUT / f"{name}.png"))
            print(f"{OUT / (name + '.png')}")


if __name__ == "__main__":
    main()
