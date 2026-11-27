#!/usr/bin/env python3
"""Render the v2 carrier's two copper layers as textures for the viewer's 3-D PCB scene.

    python 04-viewer/make_pcb_textures.py

Reads 01-hardware/v2/carrier/tpms_v2_carrier.kicad_pcb (run build_carrier.py first) with KiCad 10's kicad-cli and
writes viewer/media/pcb/L1.png and L2.png: 1024 x 1024 px for the 100 x 100 mm board, seen from the parts side
(L2 is not mirrored, so both layers line up when the stack is exploded). Both carry their silkscreen. Needs numpy
and either pymupdf or (pdftoppm + Pillow).
"""
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

import numpy as np

try:
    import pymupdf
except ImportError:
    pymupdf = None

try:
    from PIL import Image
except ImportError:
    Image = None

ROOT = pathlib.Path(__file__).resolve().parent.parent
PCB = ROOT / "01-hardware" / "v2" / "carrier" / "tpms_v2_carrier.kicad_pcb"
OUT = ROOT / "04-viewer" / "viewer" / "media" / "pcb"
BOARD_MM, ORIGIN_MM, PX = 100.0, 50.0, 1024           # the board sits at (50, 50) mm on the KiCad page

# (file, copper layer, silkscreen layer, solder-mask colour) - copper is drawn in one colour per layer
LAYERS = [("L1", "F.Cu", "F.Silkscreen", (17, 22, 31)),
          ("L2", "B.Cu", "B.Silkscreen", (17, 22, 31))]
COPPER = {"L1": (212, 160, 23), "L2": (180, 83, 9)}


def kicad_cli():
    cands = [shutil.which("kicad-cli"),
             os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "KiCad10", "bin", "kicad-cli.exe"),
             r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe"]
    found = next((c for c in cands if c and os.path.exists(c)), None)
    if found:
        return [found]
    if shutil.which("flatpak"):
        r = subprocess.run(["flatpak", "info", "org.kicad.KiCad"], capture_output=True)
        if r.returncode == 0:
            return ["flatpak", "run", "--filesystem=home", "--filesystem=/tmp",
                    "--command=kicad-cli", "org.kicad.KiCad"]
    return None


def mask(cli_cmd, layer, tmp):
    """Boolean array: True where `layer` has copper/ink, sampled on the board area."""
    pdf = pathlib.Path(tmp) / f"{layer.replace('.', '_')}.pdf"
    subprocess.run(cli_cmd + ["pcb", "export", "pdf", "-o", str(pdf), "--layers", layer, "--mode-single",
                              "--black-and-white", "--scale", "1", str(PCB)], check=True, capture_output=True)
    if pymupdf is not None:
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
    if Image is None or not shutil.which("pdftoppm"):
        sys.exit("need either pymupdf or (pdftoppm + Pillow)")
    dpi = 300.0
    prefix = pathlib.Path(tmp) / f"{layer.replace('.', '_')}_page"
    subprocess.run(["pdftoppm", "-png", "-gray", "-r", str(int(dpi)), "-singlefile", str(pdf), str(prefix)],
                   check=True, capture_output=True)
    with Image.open(f"{prefix}.png") as im:
        px_per_mm = dpi / 25.4
        x0 = round(ORIGIN_MM * px_per_mm)
        y0 = round(ORIGIN_MM * px_per_mm)
        x1 = round((ORIGIN_MM + BOARD_MM) * px_per_mm)
        y1 = round((ORIGIN_MM + BOARD_MM) * px_per_mm)
        crop = im.convert("L").crop((x0, y0, x1, y1)).resize((PX, PX), Image.Resampling.BILINEAR)
        a = np.asarray(crop, dtype=np.uint8)
    return a < 128


def main():
    cli_cmd = kicad_cli()
    if not cli_cmd:
        sys.exit("kicad-cli not found")
    if not PCB.exists():
        sys.exit(f"{PCB} not found: run build_carrier.py first")
    OUT.mkdir(parents=True, exist_ok=True)
    valid = {f"{name}.png" for name, *_ in LAYERS}
    for old in OUT.glob("L*.png"):
        if old.name not in valid:
            old.unlink()
    with tempfile.TemporaryDirectory() as tmp:
        for name, cu, silk, base in LAYERS:
            img = np.empty((PX, PX, 3), dtype=np.uint8)
            img[:] = base
            img[mask(cli_cmd, cu, tmp)] = COPPER[name]
            if silk:
                img[mask(cli_cmd, silk, tmp)] = (236, 240, 244)
            out_png = OUT / f"{name}.png"
            if pymupdf is not None:
                pix = pymupdf.Pixmap(pymupdf.csRGB, PX, PX, img.tobytes(), False)
                pix.save(str(out_png))
            elif Image is not None:
                Image.fromarray(img, mode="RGB").save(out_png)
            else:
                sys.exit("need pymupdf or Pillow to write PNG")
            print(out_png)


if __name__ == "__main__":
    main()
