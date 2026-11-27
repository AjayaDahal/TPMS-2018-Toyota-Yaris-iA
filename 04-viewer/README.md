# 04 — Interactive 3-D Viewer & Renders (2018 Yaris iA · TPMS + Dual-Camera BSM)

Three.js r160 engineering viewer. It needs no internet, but it must be served by `serve_viewer.py`: browsers block module scripts on `file://` pages. It has four modes:

1. **Car Blueprint & Wiring:** a dimensioned Mazda2 DJ sedan (Yaris iA) shell with:
   - the two mount options for the 7" display + Pi 4 enclosure: A in the console pocket, B on the dash top;
   - the mirror cameras in their printed pods, with their view cones (drawn from the real lens position) and blind-spot zones;
   - amber LEDs in printed pods on the door sails, the piezo inside the dash unit (its beep ring in front of the right slots), the twin USB wing with both car USB sockets, and colour-coded harnesses through the door boots;
   - the GPS on the dash top and the optional OBD-II Bluetooth dongle (dashed link to the enclosure), the two speed sources.

   The dash unit (with the piezo and the USB wing), the camera pods and the LED pods are the real printed parts from `01-hardware/enclosure/stl/`. A live simulator runs passing cars and motorcycles, the blinkers, the speed gate and the firmware's beep rules (a danger episode beeps at once and after 3 s, then the LED alone from 4 s; a new signal re-arms it), with a picture-in-picture of the touch-screen HUD.
2. **2-Layer PCB (100 × 100 mm):**
   - the carrier's JLCPCB 2-layer stackup (explodable L1–L2), each layer textured with the real copper of the generated board ([01-hardware/v2/carrier](../01-hardware/v2/carrier/README.md));
   - its functional blocks (DevKit, CC1101, the two bucks, the 12 V protection, the connectors) and the enclosure keep-out boxes, at their positions in the layout;
   - the printed enclosure (bezel, housing, lid, display, Pi and PCB dummies) loaded from `01-hardware/enclosure/stl/`, with an explode slider. Hide it to click through to the board.
3. **Printed Parts & Assembly:** every 3-D printed part, from the generated STL files ([01-hardware/enclosure](../01-hardware/enclosure/README.md)), to scale:
   - **Dash unit:** bezel, housing and lid round the TS-7, the Pi 4 and the **real carrier PCB** (KiCad's 3-D model, `tpms_v2_carrier.glb`, every part clickable with its BOM line), the fan, the piezo behind the right slots, the **twin USB wing** with both v1 passthroughs, their cables and screws, and the console trim and pocket around it. Close-ups of the wing (front and behind) and of the piezo (it turns the shell see-through);
   - **Mirror cameras:** both camera pods under their mirrors with the camera, the screws, the 95° view and the 39° / 10° aim; close-ups of each pod;
   - **Door LEDs** (laid out round the driver's eyes so the aims are true; one view from the eye point), **Print beds** (all nine print files as they go on a 220 × 220 mm bed, with download links), and **All, to scale**.

   Views per product, an explode slider, a section cut, a see-through shell (click the parts inside), the car context, the camera view / LED aim, and a turntable.
4. **v1 TPMS Panel (189 × 128 mm):** the KiCad STEP/STL assembly (43 solids), BOM, Gerbers and KiCad ray-traced renders.

The inspector tabs:

| Tab | Content |
|---|---|
| Car & Sim | Simulator controls (speed, auto drive, night, sound, HUD PiP) |
| 2L PCB | Stackup layers, functional blocks, keep-outs and the enclosure fit report |
| Printed Parts | Product, views, explode, section and see-through; the card with sizes, holes and STL links; the part list |
| Wiring | The harness table and per-rail power totals |
| Inv/Buy | The BOM: use-from-inventory vs. buy |
| Checklists | Collect, buy, measure, bench tests, tools and the 16 build steps; ticks are saved in the browser, per address (same port) |
| Premortem | The v2 order-gate verdict (G1–G8) and all premortem items with status and category filters |
| v1 PCB / Renders | The v1 board |

```bash
python3 04-viewer/make_viewer.py        # rebuild manifest + parts from the v1 KiCad STEP (only after a v1 change)
python3 04-viewer/sync_plan.py          # refresh the premortem / order gate / enclosure data in system_plan.json
python3 04-viewer/make_pcb_textures.py  # re-render the 2 copper layers after a carrier rebuild (KiCad 10)
python3 04-viewer/serve_viewer.py       # -> http://127.0.0.1:28776/viewer/
```

`serve_viewer.py` listens on 127.0.0.1 only, answers only requests addressed to localhost, and serves only the repository's own files (tracked, or new and not git-ignored), never ignored personal files or build output. A port that is already in use is an error, not a second server sharing it. Every response says `Cache-Control: no-cache`, so a reload always picks up regenerated STLs and edited scripts (the browser revalidates and gets a cheap 304 when nothing changed).

`sync_plan.py` reads [PREMORTEM_v2.md](../00-project-management/PREMORTEM_v2.md) and [enclosure_report.json](../01-hardware/enclosure/enclosure_report.json) and rewrites only the `premortem`, `order_gate` and `enclosure` keys of `viewer/system_plan.json`; the rest of that file is hand-edited. It is strict: a table row outside a table, a cell count that doesn't match the header, an unknown table header, status word or gate state, or a duplicate id stops it with the line number, and it prints the ids it added or removed.

Run it after changing either source. `python3 04-viewer/sync_plan.py --check` exits non-zero if `system_plan.json` is out of date.

- `viewer/`: `index.html`, `style.css`, `app.js`, `car_scene.js`, `pcb6_scene.js`, `products_scene.js` (Printed Parts), `system_plan.json`, `manifest.json`, `vendor/` (Three.js r160 + OrbitControls, STLLoader, GLTFLoader), `parts/`, `media/` (`media/pcb/L1–L2.png`: the carrier's copper, from `make_pcb_textures.py`)
- The Printed Parts and the car scene read `01-hardware/enclosure/{enclosure,mounts}_report.json` and `stl/`, the carrier's `docs/tpms_v2_carrier.glb` (written by `build_carrier.py`) and its BOM / hand-solder lists in `03-manufacturing/v2_carrier/`; regenerate those and reload.
- `renders/`: KiCad front, back and isometric ray-traced renders of the v1 PCB
