# 04 — Interactive 3-D Viewer & Renders (2018 Yaris iA · TPMS + Dual-Camera BSM)

Offline Three.js r160 engineering viewer. It has three modes:

1. **Car Blueprint & Wiring:** a dimensioned Mazda2 DJ sedan (Yaris iA) shell with:
   - the two mount options for the 7" display + Pi 4 enclosure: A in the console pocket, B on the dash top;
   - the mirror cameras with their view cones and blind-spot zones;
   - amber door-sail LEDs, the alert pod (mute button + piezo) by the shifter, and colour-coded harnesses through the door boots;
   - the GPS on the dash top and the optional OBD-II Bluetooth dongle (dashed link to the enclosure), the two speed sources.

   A live simulator runs passing cars and motorcycles, the blinkers, the speed gate and the 3 kHz beep cadence of the firmware, with a picture-in-picture of the touch-screen HUD.
2. **6-Layer PCB (100 × 100 mm):**
   - the carrier's JLCPCB 6-layer stackup (explodable L1–L6);
   - the planned functional blocks and keep-out boxes, at the positions of the 1:1 fit template;
   - the printed enclosure (bezel, housing, lid, display, Pi and PCB dummies) loaded from `01-hardware/enclosure/stl/`, with an explode slider. Hide it to click through to the board.
3. **v1 TPMS Panel (189 × 128 mm):** the KiCad STEP/STL assembly (43 solids), BOM, Gerbers and KiCad ray-traced renders.

The inspector tabs:

| Tab | Content |
|---|---|
| Car & Sim | Simulator controls (speed, auto drive, night, sound, HUD PiP) |
| 6L PCB | Stackup layers and functional blocks |
| Wiring | The harness table and per-rail power totals |
| Inv/Buy | The BOM: use-from-inventory vs. buy |
| Checklists | Collect, buy, measure, bench tests, tools and the 16 build steps; ticks are saved in the browser |
| Premortem | The v2 order-gate verdict (G1–G8), all premortem items with status and category filters, and the enclosure fit report |
| v1 PCB / Renders | The v1 board |

```bash
python3 04-viewer/make_viewer.py      # rebuild manifest + parts from the v1 KiCad STEP (only after a v1 change)
python3 04-viewer/sync_plan.py        # refresh the premortem / order gate / enclosure data in system_plan.json
python3 04-viewer/serve_viewer.py     # -> http://127.0.0.1:28776/viewer/
```

`sync_plan.py` reads [PREMORTEM_v2.md](../00-project-management/PREMORTEM_v2.md) and [enclosure_report.json](../01-hardware/enclosure/enclosure_report.json) and rewrites only the `premortem`, `order_gate` and `enclosure` keys of `viewer/system_plan.json`; the rest of that file is hand-edited.

Run it after changing either source. `python3 04-viewer/sync_plan.py --check` exits non-zero if `system_plan.json` is out of date.

- `viewer/`: `index.html`, `style.css`, `app.js`, `car_scene.js`, `pcb6_scene.js`, `system_plan.json`, `manifest.json`, `vendor/` (Three.js r160 + OrbitControls, STLLoader), `parts/`, `media/`
- `renders/`: KiCad front, back and isometric ray-traced renders of the v1 PCB
