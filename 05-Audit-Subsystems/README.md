# Subsystem audit and premortem

Every subsystem of the project, audited one by one, each with a premortem: assume it failed in the car, and ask why. It covers:
- the v1 TPMS panel;
- the v2 blind-spot + TPMS unit (ESP32 carrier, Raspberry Pi 4, display, cameras, enclosure);
- the car install;
- the tooling.

Each page lists:
- what was **verified**, with the evidence;
- the **findings**, with a fix and a status;
- the **premortem** for that subsystem;
- what to do **before you move on**.

The [v2 premortem](../00-project-management/PREMORTEM_v2.md) remains the plan of record. These pages explain and extend it, and its rows link back here.

**Method.** Datasheets and manuals were fetched and read; the code was compiled, unit-tested, stress-tested and mutation-tested; the viewer was run in a browser and its server probed over HTTP. The v1 board was re-checked with KiCad. Five independent reviews were run in parallel (RF, v1 hardware, v2 firmware, viewer, a fact check of 18 claims about the car and the parts), and everything they reported was re-checked before it went into a page. Defects that could be fixed safely were fixed during the audit, each with a test that failed before the fix.

> **Display decided: the SunFounder TS-7.** The audit found the design built for the **Official Raspberry Pi 7" Touch Display** (800 × 480, DSI ribbon) while your inventory has the **SunFounder TS-7** (1024 × 600 IPS, HDMI + USB touch): [DSP-01](09-display-and-ui.md). Since then the enclosure, the 1:1 template, the power budget, the harness, the BOM, the premortem and the viewer have been redrawn for the TS-7. SunFounder publishes no drawing, so measure it before printing: [DSP-10](09-display-and-ui.md).

## Scorecard

**Verdicts:** **Sound**: no open issue that blocks the next step. **Watch**: open items, none blocking yet. **Act**: something must change or be decided before building on it.

**Severity:**
- **Critical**: it would cause a wrong safety alert or a failure in normal use.
- **High**: likely to defeat the subsystem.
- **Medium**: real, with a workaround.
- **Low**: minor.
- **Info**: a note.

"(TS-7)" or "(v2)" next to a severity means it applies only to that case.

| # | Subsystem | Verdict | Findings (C / H / M / L / I) | Fixed by the audit | Top open risk |
|---|---|---|---|---|---|
| 01 | [Power and protection](01-power-and-protection.md) | Watch | 0 / 1 / 4 / 4 / 1 | 5 (carrier design) | AM-band noise and buck heat show only on the built board (PWR-09, PWR-P6) |
| 02 | [ESP32 controller](02-esp32-controller.md) | Watch | 0 / 0 / 4 / 2 / 2 | — | No way to update the firmware once installed (ESP-01) |
| 03 | [Blinker sensing](03-blinker-sensing.md) | Watch | 1 / 2 / 3 / 2 / 1 | 5, incl. the Critical | Which wire to tap (BLK-05, G9); a dead input is silent (BLK-06) |
| 04 | [Speed sources](04-speed-sources.md) | Watch | 0 / 1 / 2 / 3 / 1 | 2 | Your OBD dongle isn't identified (SPD-04) |
| 05 | [Alerts and the piezo](05-alerts-and-alert-pod.md) | Watch | 0 / 0 / 9 / 3 / 1 | 7 | The piezo (now inside the unit) and the LEDs never heard or seen in the car (ALR-08, ALR-09) |
| 06 | [Raspberry Pi](06-raspberry-pi.md) | Watch | 0 / 2 / 5 / 2 / 0 | 1 | Heat throttling in summer (PI-04) |
| 07 | [ESP32 ↔ Pi link](07-esp32-pi-link.md) | Sound | 0 / 0 / 4 / 2 / 1 | 2 | TX-off while the Pi is unpowered exists only as a comment (LNK-03) |
| 08 | [Cameras and vision](08-cameras-and-vision.md) | **Act** | 0 / 3 / 4 / 1 / 1 | 2 (in the spec) | Two USB cameras on the Pi 4's single USB 2.0 hub (CAM-03); no camera chosen |
| 09 | [Display and UI](09-display-and-ui.md) | Watch | 0 / 2 / 7 / 2 / 0 | — | Its size comes from photos: measure it before printing (DSP-10) |
| 10 | [Enclosure and thermal](10-enclosure-and-thermal.md) | Watch | 0 / 2 / 8 / 3 / 1 | 1 | Heat (ENC-01); the TS-7's real size (ENC-03); the USB passthrough and the trim beside the opening are unmeasured (ENC-13) |
| 11 | [Carrier PCB](11-carrier-pcb.md) | Watch | 0 / 1 / 12 / 5 / 1 | 13 (carrier design) | Ready to order; check the polarized parts in JLCPCB's placement preview (PCB-P2) |
| 12 | [Vehicle integration](12-vehicle-integration.md) | Watch | 0 / 0 / 7 / 2 / 1 | — | ACC during cranking (VEH-01); the repeater wire (VEH-07) |
| 13 | [TPMS radio](13-tpms-radio.md) | Watch | 0 / 1 / 9 / 5 / 1 | 9 | No carrier-sense gating: noise can swamp the decoder in the car (RF-01) |
| 14 | [v1 panel](14-v1-panel.md) | Watch | 0 / 0 / 4 / 10 / 1 | 7 | The regulator's heatsink pour is split (V1-01): fix before ordering |
| 15 | [Viewer and tooling](15-viewer-and-tooling.md) | Sound | 0 / 1 / 10 / 9 / 0 | 15 | Hand-copied keep-outs in the viewer (VW-14) |
| 16 | [Safety and legal](16-safety-and-legal.md) | Watch | 0 / 1 / 5 / 6 / 0 | 1 | Trusting an untested aid (SAF-01) |
| 17 | [Project and repository](17-project-and-repo.md) | Sound | 0 / 0 / 4 / 3 / 1 | 2 | The plan was matched against an old inventory (PRJ-03) |
| | **Total** | | **1 / 17 / 101 / 64 / 14** (197) | **72** | |

**Since the audit:**
- The TS-7 redesign closed 7 more findings (DSP-01, DSP-02, DSP-03, DSP-05, DSP-08, ENC-02, PI-03) and added 3 (DSP-10, DSP-11, RF-16).
- The carrier PCB (rev A, generated and checked) closed 18 (PWR-01, PWR-02, PWR-03, PWR-05, PWR-06, PCB-01, PCB-03, PCB-05, PCB-06, PCB-09–PCB-12, PCB-14, PCB-16–PCB-19) and added 13 (PWR-09, PWR-10, PCB-09–PCB-19).
- The alert redesign (2026-11-26: no alert pod and no button; the piezo inside the dash unit; beeps that mute themselves; the car's USB in a printed wing) added 6 (ALR-12, ALR-13, LNK-07, ENC-12, ENC-13, ENC-14), fixed 5 of them, and closed ALR-10 and ESP-05 (no button lead any more).

The counts above include all of them.

## The risks that matter most

Ranked by what they would cost if ignored. The Pi's 5 V margin (PWR-01) and the prose-only schematic (PCB-01), the top two of the original list, are now fixed by the generated carrier board.

1. **Heat** ([PI-04](06-raspberry-pi.md), [ENC-01](10-enclosure-and-thermal.md)). By estimate the Pi throttles at a cabin of ~40–45 °C. Add the cheap margin before printing: a real heatsink and a ball-bearing fan. Then thermal test T1.
2. **The cameras** ([CAM-01–03](08-cameras-and-vision.md)):
   - "100°" is usually diagonal;
   - a camera aimed straight back misses the car beside you (the spec now says ≥ 95° horizontal, aimed 39° outward);
   - two UVC cameras may refuse to stream together on the Pi 4's one USB 2.0 hub.

   Test both purchased cameras at once on the day they arrive.
3. **The TS-7's real size** ([DSP-10](09-display-and-ui.md), [ENC-03](10-enclosure-and-thermal.md)). SunFounder lists 121 mm; its photos say ~124.4 mm, and the bezel fills the console opening's height with the photo value. Measure the display and lay it on the fit template before printing anything.
4. **TPMS in a noisy car** ([RF-01](13-tpms-radio.md), [RF-16](13-tpms-radio.md)). Without carrier-sense gating, the demodulator's noise can keep bursts from ever ending, and the TS-7's HDMI flat cable is a new noise source. Watch the edge counter on the bench (B6), before writing the v2 app.
5. **Updating the ESP32 after install** ([ESP-01](02-esp32-controller.md), [PCB-02](11-carrier-pcb.md)). The board leaves the DevKit's USB reachable with the lid off; without a Wi-Fi update mode, every firmware fix still means opening the box.
6. **The first carrier boards on the bench** ([PCB-13](11-carrier-pcb.md), [PWR-P6](01-power-and-protection.md)). AM-band noise and the Pi buck's heat only show on a built board. Bring it up on a current-limited supply; the rework table has a fix for each.
7. **Trust** ([SAF-01](16-safety-and-legal.md)). Run the first month with the buzzer muted and log every alert, so the miss and false-alarm rates are known.

## What the audit fixed

Code (each fix has a test that failed before it):
- **Blinker:** hazards pressed during a turn signal read as a turn to the other side, and sounded a danger beep for that lane (Critical, BLK-01). A quick left → right change read as hazards (BLK-02). An input stuck lit was a permanent turn with no fault (BLK-03, now a fault after 1.5 s).
- **Pi power:** an ESP32 reset (watchdog, brown-out, update) cut power to a running Pi (PI-01, PGOOD read back).
- **Alerts:** a camera fault never beeped; fault beeps re-armed at every recovery; lower priorities cut higher ones; a Pi that never booted, or a frozen vision loop, was silent (ALR-01–07, LNK-01).
- **OBD-II:** three behaviours of cheap clone dongles left the speed unused or constantly resetting (SPD-01, SPD-02).
- **TPMS radio:** phantom interrupt edges, wrong FOCCFG for OOK, rejected frames with a swallowed preamble, an interrupt storm without a radio, FREND1, double-read status, a stray MX-05V mode (RF-02–14). Knob and button debounce on v1 (V1-11, V1-12).
- **Viewer and tools:**
  - the inspector couldn't be reopened;
  - hidden objects caught clicks;
  - a load race;
  - wrong status pills;
  - `sync_plan.py` dropped rows silently;
  - the local server exposed git-ignored personal files and let several servers share a port;
  - the camera view cone wasn't a lens (VW-01–20).
- **Repo:** build output with local paths wasn't git-ignored (PRJ-01); stale paths (PRJ-02).

Results:
- **v2 logic:** 154 checks (was 120) pass, plus a 13,622-case blinker stress sweep, clean under strict warnings and UBSan. 16 of 17 deliberate mutations were caught (the survivor is equivalent).
- **v1 board:** ERC/DRC 0/0 re-confirmed with KiCad 10.

Plan and text:
- camera spec and aim ([V4](../00-project-management/PREMORTEM_v2.md#vision-and-compute));
- the best blinker tap is the mirror repeater feed (I1);
- the 315 MHz loss is the antenna, not the module (R1);
- PETG out of the car (M3);
- drilling clear of the repeater (M6);
- door routing clear of the window (M8);
- LEDs inside the cabin only (C7);
- the first-month logging mode (S3);
- the v1 design audit's heatsink-pour and PTC numbers corrected (the pour itself still needs the build-script fix, V1-01).

## Decisions and gates still open

| Item | Who | Unblocks |
|---|---|---|
| Measure the TS-7 ([DSP-10](09-display-and-ui.md)); the display itself is decided ([DSP-01](09-display-and-ui.md)) | You | The enclosure print (G6) |
| Vision computer: Pi 4, or the inventory's Jetson Nano / NavQPlus ([CAM-04](08-cameras-and-vision.md), [PRJ-07](17-project-and-repo.md)) | You, after bench test V1 | The detector, the power budget |
| G7's last step: print the carrier's 1:1 assembly drawing and set the sockets and terminals on it · G8 JLCPCB quote and order ([order steps](../01-hardware/v2/carrier/README.md#order-it-at-jlcpcb)) | You | The v2 carrier boards |
| G3 every part on hand (against the live inventory) · G5 display location (mock-up) · G6 the TS-7 measured and test print | You | The enclosure |
| G4 bring-up and B1–B6 on the assembled carrier | You, when the boards arrive | The car install |
| G9 the blinker wire in each door · T1 thermal test | You, at install | Trusting it in the car |

## Re-running every check

```
python 05-Audit-Subsystems/run_checks.py               # everything that is installed
python 05-Audit-Subsystems/run_checks.py --skip kicad  # skip by name: kicad, enclosure, js, links
```

Read-only (builds go to a temporary folder). It runs:
- the v2 logic tests and the v1 decoder tests;
- the pin-map audit and its self-test;
- the enclosure regeneration, compared byte for byte with the committed STLs, and their watertightness;
- the viewer data sync and JavaScript syntax;
- every markdown link and anchor in the repo;
- repo hygiene (no local paths, build output ignored);
- the v1 KiCad ERC/DRC.

Run it before every commit.
