# TPMS monitor panel + blind-spot cameras (2018 Toyota Yaris iA)

A dash unit for the Yaris iA in two stages:

- **v1, TPMS panel (done; orderable after one fix):** receives the car's 315 MHz tyre-pressure (TPMS) sensors and shows the pressures on an OLED display, with four tyre LEDs and a rotary encoder. It is based on my ECE 6723 Embedded Systems project ([report](00-project-management/TPMS_project_report_ECE6723.pdf)).
- **v2, TPMS + blind-spot assist (designed; the carrier PCB is ready to order):** adds two mirror cameras with car/motorcycle detection on a Raspberry Pi 4, shown on your SunFounder TS-7 7" HDMI touch display (1024 × 600 IPS). When a vehicle is in a blind spot, an amber LED lights in that door sail; signalling towards it sounds a sharp beep and shows that camera. The touch screen replaces the v1 encoder, buttons and OLED, and the mute button too: the buzzer sits inside the unit and every beep stops by itself (a blind-spot beep after 4 s, while the LED keeps flashing). Both car USB passthroughs from v1 move into a printed twin wing on the unit's side, in v1's Ø25.8 × 23.8 mm double-D cuts. A 100 × 100 mm 2-layer ESP32 carrier board does the TPMS radio, the blinker inputs (wired to the lamp feeds), the speed gate (the car's own speed from your Bluetooth OBD-II dongle, GPS as the fallback), the alerts and the Pi's power sequencing. The display, the Pi and the board share one 3D-printed enclosure.

![front](04-viewer/renders/render_front.png)

**v1 hardware:**
- **Receiver:** CC1101 module (EBYTE E07-M1101D) on 315 MHz. The report's original MX-05V superregenerative receiver can still be fitted for comparison.
- **MCU:** ESP32 DevKit V1 (DOIT, 30-pin).
- **Display:** Newhaven NHD-2.7-12864WDW3 (128×64 OLED, SSD1322, SPI).
- **Power:** 12 V ACC → protection → 5 V switcher → 3.3 V LDO.

## Interactive 3-D Viewer & Quick Start

```bash
python3 04-viewer/serve_viewer.py    # -> http://127.0.0.1:28776/viewer/
```

The viewer shows the car blueprint with both cameras, LEDs and harnesses and a live blind-spot simulator, the v2 2-layer board inside the printed enclosure, and the v1 panel. It also has the checklists (collect, buy, measure, bench tests, tools, build steps) and the v2 premortem with its order gate.

## Repository Map

| Folder | Content |
|---|---|
| [00-project-management](00-project-management/README.md) | [PREMORTEM.md](00-project-management/PREMORTEM.md) (v1), [PREMORTEM_v2.md](00-project-management/PREMORTEM_v2.md) (v2: corrections, ranked failure stories, order gate, bench tests, next steps), [TPMS_project_report_ECE6723.pdf](00-project-management/TPMS_project_report_ECE6723.pdf) |
| [01-hardware](01-hardware/README.md) | v1: KiCad 10 project (schematic, PCB, libraries, `scripts/`), [design_audit.md](01-hardware/docs/design_audit.md), `tpms_panel.step`, [1:1 car fit template](01-hardware/docs/tpms_panel_fit_template_1to1.pdf). v2: [v2/carrier/](01-hardware/v2/carrier/README.md) (the 2-layer carrier PCB: generator, KiCad project, order steps, bring-up, rework), [enclosure/](01-hardware/enclosure/README.md) (printed enclosure and mirror/door mounts: generators + STLs), [v2 fit template](01-hardware/docs/v2_fit_template_1to1.pdf), [pin-map audit](01-hardware/v2/check_pinmap.py) |
| [02-firmware](02-firmware/README.md) | [bringup/](02-firmware/bringup/README.md): ESP32 PlatformIO self-test and 315 MHz TPMS decoder. [v2/](02-firmware/v2/README.md): v2 safety logic, pin map and host unit tests |
| [03-manufacturing](03-manufacturing/README.md) | v1 JLCPCB Gerber/drill zip (`production/tpms_panel_gerbers_jlcpcb.zip`) & BOM CSV; v2 carrier (`v2_carrier/`): Gerber zip, JLCPCB BOM + CPL, hand-solder list |
| [04-viewer](04-viewer/README.md) | Offline Three.js r160 3-D viewer (`viewer/`), KiCad renders (`renders/`), `make_viewer.py`, `sync_plan.py`, `serve_viewer.py` |
| [05-Audit-Subsystems](05-Audit-Subsystems/README.md) | Audit of every subsystem with its own premortem (17 pages), the scorecard and top risks, and [run_checks.py](05-Audit-Subsystems/run_checks.py), which re-runs every automated check |

> **Sensors:** the Yaris iA's own TPMS is indirect (ABS-based, no wheel sensors). Four GM/Schrader EG53MA4 sensors were added to the tyres, and this panel is their receiver.

> **v1 status: ready to order after one fix.** The audit found the regulator's heatsink pour split by a track ([V1-01](05-Audit-Subsystems/14-v1-panel.md)): fix it in the build script and rebuild first. The outline was accepted from the in-car paper fit (board 1 mm smaller than the opening on the sides and bottom), and the USB holes are Ø25.8 mm for the measured 25.16 mm thread.
> The order file is `03-manufacturing/production/tpms_panel_gerbers_jlcpcb.zip`. If the 7" display takes the console opening (v2 Option A), v1 has no place in the car: order it only for the dash-top option or as a TPMS-only first step.

> **v2 status: the carrier PCB (rev A) is ready to order.**
> - Done: the electrical design and pin map (audited); the safety logic (166 host checks); the 2-layer carrier PCB, generated and checked (ERC/DRC 0, JLCPCB BOM + CPL under-$59 hybrid: ~$53–$57 merchandise for 5 boards with 2 assembled so Global Standard Direct Line unlocks, plus 8 hand-solder SMD parts from LCSC: [order steps](01-hardware/v2/carrier/README.md#order-it-at-jlcpcb)); the printed enclosure for the TS-7 (63 fit checks) and the mirror camera and door LED mounts (28 checks).
> - Before you order: print the 1:1 assembly drawing and set the real parts on it (G7), then check JLCPCB's quote and placement preview (G8): [order gate](00-project-management/PREMORTEM_v2.md#order-gate-for-the-v2-pcb).
> - Before you print or install: every part on hand (G3), a mock-up in the car (G5), the TS-7's and the passthroughs' measurements and a test print (G6: SunFounder publishes no drawing, see the [enclosure README](01-hardware/enclosure/README.md#measure-first-then---set)), and the blinker wire in each door (G9).
