# 04 — Interactive 3-D Viewer & Renders (2018 Yaris iA · TPMS + Dual-Camera BSM)

Three.js r160 engineering viewer. It needs no internet, but it must be served by `serve_viewer.py`: browsers block module scripts on `file://` pages. It has three modes:

1. **Car Blueprint & Wiring:** a dimensioned Mazda2 DJ sedan (Yaris iA) shell with:
   - the two mount options for the 7" display + Pi 4 enclosure: A in the console pocket, B on the dash top;
   - the mirror cameras with their view cones and blind-spot zones;
   - amber door-sail LEDs, the alert pod (mute button + piezo) by the shifter, and colour-coded harnesses through the door boots;
   - the GPS on the dash top and the optional OBD-II Bluetooth dongle (dashed link to the enclosure), the two speed sources.

   A live simulator runs passing cars and motorcycles, the blinkers, the speed gate and the 3 kHz beep cadence of the firmware, with a picture-in-picture of the touch-screen HUD.
2. **6-Layer PCB (100 × 100 mm):**
   - the carrier's JLCPCB 6-layer stackup (explodable L1–L6), each layer textured with the real copper of the generated board ([01-hardware/v2/carrier](../01-hardware/v2/carrier/README.md));
   - its functional blocks (DevKit, CC1101, the two bucks, the 12 V protection, the connectors) and the enclosure keep-out boxes, at their positions in the layout;
   - the printed enclosure (bezel, housing, lid, display, Pi and PCB dummies) loaded from `01-hardware/enclosure/stl/`, with an explode slider. Hide it to click through to the board.
3. **v1 TPMS Panel (189 × 128 mm):** the KiCad STEP/STL assembly (43 solids), BOM, Gerbers and KiCad ray-traced renders.

The inspector tabs:

| Tab | Content |
|---|---|
| Car & Sim | Simulator controls (speed, auto drive, night, sound, HUD PiP) |
| 6L PCB | Stackup layers, functional blocks, keep-outs and the enclosure fit report |
| Wiring | The harness table and per-rail power totals |
| Inv/Buy | The BOM: use-from-inventory vs. buy |
| Checklists | Collect, buy, measure, bench tests, tools and the 16 build steps; ticks are saved in the browser, per address (same port) |
| Premortem | The v2 order-gate verdict (G1–G8) and all premortem items with status and category filters |
| v1 PCB / Renders | The v1 board |

```bash
python3 04-viewer/make_viewer.py        # rebuild manifest + parts from the v1 KiCad STEP (only after a v1 change)
python3 04-viewer/sync_plan.py          # refresh the premortem / order gate / enclosure data in system_plan.json
python3 04-viewer/make_pcb_textures.py  # re-render the 6 copper layers after a carrier rebuild (KiCad 10, pymupdf)
python3 04-viewer/serve_viewer.py       # -> http://127.0.0.1:28776/viewer/
```

`serve_viewer.py` listens on 127.0.0.1 only, answers only requests addressed to localhost, and serves only the repository's own files (tracked, or new and not git-ignored), never ignored personal files or build output. A port that is already in use is an error, not a second server sharing it.

`sync_plan.py` reads [PREMORTEM_v2.md](../00-project-management/PREMORTEM_v2.md) and [enclosure_report.json](../01-hardware/enclosure/enclosure_report.json) and rewrites only the `premortem`, `order_gate` and `enclosure` keys of `viewer/system_plan.json`; the rest of that file is hand-edited. It is strict: a table row outside a table, a cell count that doesn't match the header, an unknown table header, status word or gate state, or a duplicate id stops it with the line number, and it prints the ids it added or removed.

Run it after changing either source. `python3 04-viewer/sync_plan.py --check` exits non-zero if `system_plan.json` is out of date.

- `viewer/`: `index.html`, `style.css`, `app.js`, `car_scene.js`, `pcb6_scene.js`, `system_plan.json`, `manifest.json`, `vendor/` (Three.js r160 + OrbitControls, STLLoader), `parts/`, `media/` (`media/pcb/L1–L6.png`: the carrier's copper, from `make_pcb_textures.py`)
- `renders/`: KiCad front, back and isometric ray-traced renders of the v1 PCB
