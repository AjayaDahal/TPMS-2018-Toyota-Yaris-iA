#!/usr/bin/env python3
"""Build TPMS Panel (2018 Yaris iA) 3-D viewer manifest, STL parts exported from tpms_panel.step, BOM, and renders.

Run:
  python3 04-viewer/make_viewer.py
"""
from __future__ import annotations

import csv
import json
import pathlib
import shutil

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
VIEWER = HERE / "viewer"
PARTS_OUT = VIEWER / "parts"
MEDIA_OUT = VIEWER / "media"
HW_DOCS = ROOT / "01-hardware" / "docs"
PROD_DIR = ROOT / "03-manufacturing" / "production"
RENDERS = HERE / "renders"
STEP_PATH = HW_DOCS / "tpms_panel.step"


def classify_solid(idx: int, sx: float, sy: float, sz: float, cx: float, cy: float, cz: float):
    """Classify each solid in tpms_panel.step by its geometry for color, subsystem, and explode vector."""
    if sx > 150 and sy > 90 and sz < 3.0:
        return ("pcb_board", "PCB Substrate (189×128×1.6 mm FR-4)", "pcb", [0.08, 0.36, 0.22], [0, 0, 0])
    if 4.5 < sx < 6.5 and 4.5 < sy < 6.5 and sz > 10.0:
        pos_lbl = f"Tyre LED ({'FL' if cx < 150 and cy > -111 else ('FR' if cx >= 150 and cy > -111 else ('RL' if cx < 150 else 'RR'))})"
        return (f"led_{idx:02d}", pos_lbl, "ui", [0.94, 0.30, 0.06], [0, 0, 22])
    if sx > 50 and sy > 25:
        return (f"display_oled_{idx:02d}", "NHD-2.7-12864WDW3 OLED Display (128×64 SPI)", "ui", [0.10, 0.12, 0.16], [0, 0, 32])
    if 10 < sx < 18 and 10 < sy < 18 and sz > 15:
        return (f"rotary_encoder_{idx:02d}", "EC11 Rotary Encoder + Push Switch", "ui", [0.75, 0.78, 0.82], [0, 0, 26])
    if cz < -3.0 and sz > 8.0:
        return (f"rear_module_{idx:02d}", f"Rear Connector / Module #{idx}", "rf_mcu", [0.18, 0.45, 0.78], [0, 0, -24])
    if cz > 0.5:
        return (f"front_comp_{idx:02d}", f"Front Component #{idx}", "power_io", [0.68, 0.72, 0.78], [0, 0, 18])
    return (f"smd_comp_{idx:02d}", f"Rear SMD / THT Part #{idx}", "power_io", [0.45, 0.48, 0.54], [0, 0, -14])


def export_step_to_stls():
    """Export centered per-solid binary STLs from tpms_panel.step when build123d is available."""
    items = []
    try:
        from build123d import import_step, export_stl, Pos
        sh = import_step(str(STEP_PATH))
        bb_all = sh.bounding_box()
        c_all = bb_all.center()
        solids = sh.solids()
        for idx, s in enumerate(solids):
            bb = s.bounding_box()
            c = bb.center()
            name, label, subsystem, col, ex = classify_solid(
                idx, bb.size.X, bb.size.Y, bb.size.Z, c.X, c.Y, c.Z
            )
            centered = Pos(-c_all.X, -c_all.Y, -c_all.Z) * s
            stl_file = f"{name}.stl"
            export_stl(centered, str(PARTS_OUT / stl_file), tolerance=0.05, angular_tolerance=0.2)
            items.append({
                "name": name,
                "label": label,
                "url": f"parts/{stl_file}",
                "subsystem": subsystem,
                "color": col,
                "dims_mm": [round(bb.size.X, 1), round(bb.size.Y, 1), round(bb.size.Z, 1)],
                "explode_mm": ex,
            })
        dims_total = [round(bb_all.size.X, 1), round(bb_all.size.Y, 1), round(bb_all.size.Z, 1)]
        return items, dims_total
    except Exception as e:
        print(f"Note: build123d STEP export skipped ({e}); reusing existing parts/*.stl if present")
        existing = VIEWER / "manifest.json"
        if existing.exists():
            old = json.loads(existing.read_text(encoding="utf-8"))
            return old.get("items", []), old.get("dims_mm", [189.0, 128.0, 27.1])
        return [], [189.0, 128.0, 27.1]


def main() -> int:
    for d in (PARTS_OUT, MEDIA_OUT):
        d.mkdir(parents=True, exist_ok=True)

    items, dims_mm = export_step_to_stls()

    # Parse BOM CSV
    bom = []
    bom_csv = PROD_DIR / "tpms_panel_bom.csv"
    if bom_csv.exists():
        with bom_csv.open(encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                bom.append({
                    "designators": r.get("Designators", ""),
                    "qty": r.get("Qty", "1"),
                    "value": r.get("Value", ""),
                    "footprint": r.get("Footprint", ""),
                    "part": r.get("Part / suggestion", ""),
                    "description": r.get("Description", ""),
                    "populate": r.get("Populate", "yes"),
                })

    # Copy renders
    studio_renders = []
    if RENDERS.exists():
        for f in sorted(RENDERS.iterdir()):
            if f.suffix.lower() in (".png", ".jpg"):
                shutil.copyfile(f, MEDIA_OUT / f.name)
                studio_renders.append({
                    "file": f"media/{f.name}",
                    "title": f.stem.replace("_", " ").title(),
                    "kind": "PNG",
                })

    manifest = {
        "vehicle": "TPMS Monitor Panel",
        "subtitle": "2018 Toyota Yaris iA · 315 MHz CC1101 + ESP32 + 2.7\" OLED Dash Panel",
        "dims_mm": dims_mm,
        "items": items,
        "bom": bom,
        "studio_renders": studio_renders,
        "hardware": {
            "mcu": "ESP32 DevKit V1 (30-pin DOIT)",
            "rf_primary": "CC1101 (EBYTE E07-M1101D-SMA, 315 MHz OOK)",
            "rf_alt": "MX-05V superregenerative socket (J3)",
            "display": "Newhaven NHD-2.7-12864WDW3 (128×64 OLED, SSD1322, 4-wire SPI)",
            "ui": "4× 5 mm Tyre LEDs (FL/FR/RL/RR) + EC11 Rotary Encoder + 5 V Buzzer",
            "power": "12 V ACC → PTC 0.75A + SS34 + SMAJ22CA TVS → TRACO TSR 1-2450 (5V) → AMS1117-3.3 (3.3V)",
            "sensors": "4× GM / Schrader EG53MA4 315 MHz wheel sensors",
            "usb_holes": "2× Ø25.8 mm panel-mount USB 3.0 passthrough cutouts",
            "status": "READY TO ORDER (JLCPCB Gerbers + 1:1 car fit verified)",
        },
        "firmware": {
            "framework": "PlatformIO (ESP32 Arduino / bringup)",
            "path": "02-firmware/bringup/",
            "modes": "Hardware self-test (LEDs, OLED, encoder, buzzer, SPI) + 315 MHz GM/Schrader OOK TPMS decoder",
        },
        "downloads": [
            {"label": "JLCPCB Gerbers & Drill (.zip)", "href": "../../03-manufacturing/production/tpms_panel_gerbers_jlcpcb.zip", "badge": "ZIP"},
            {"label": "BOM CSV", "href": "../../03-manufacturing/production/tpms_panel_bom.csv", "badge": "CSV"},
            {"label": "3-D STEP Assembly", "href": "../../01-hardware/docs/tpms_panel.step", "badge": "STEP"},
            {"label": "1:1 Car Fit Template (US Letter)", "href": "../../01-hardware/docs/tpms_panel_fit_template_1to1.pdf", "badge": "PDF"},
            {"label": "Schematic PDF", "href": "../../01-hardware/docs/tpms_panel_schematic.pdf", "badge": "PDF"},
            {"label": "PCB Front Layout PDF", "href": "../../01-hardware/docs/tpms_panel_pcb_front.pdf", "badge": "PDF"},
            {"label": "ECE 6723 Project Report", "href": "../../00-project-management/TPMS_project_report_ECE6723.pdf", "badge": "PDF"},
        ],
    }
    (VIEWER / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(
        f"TPMS viewer built: {len(items)} 3-D STEP solids, {len(bom)} BOM rows, "
        f"{len(studio_renders)} renders -> 04-viewer/viewer/manifest.json"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
