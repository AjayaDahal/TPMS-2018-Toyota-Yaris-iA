# 12 · Vehicle integration

**Scope:** everything that touches the car:
- the 12 V fuse tap and ground;
- the blinker taps;
- the routes through the doors, kick panels and console;
- drilling the mirror caps;
- the LED and GPS locations, and the USB wing beside the console opening (the car's own USB port, extended by the v1 passthrough);
- the OBD-II dongle;
- the airbag keep-outs;
- reversibility.

The electrical design behind each input is in [power](01-power-and-protection.md), [blinker](03-blinker-sensing.md) and [speed](04-speed-sources.md).

**Maturity:** planned route by route in the [harness data](../04-viewer/viewer/system_plan.json) and the build steps; nothing is installed, and the car's wiring diagram hasn't been checked against any tap.

**Verdict: Watch.** The routes respect the car: no A-pillar, no roof rail, no SRS harness, one fused tap. They also follow the factory harness through the door boots. What remains are facts only the car can give:
- what the ACC line does while cranking;
- which wire is the mirror repeater feed;
- whether a USB plug passes the mirror base and the door boot;
- where the mirror cap can be drilled.

## What was verified

| Check | Evidence | Result |
|---|---|---|
| Curtain airbags | Owner's manual and the facts review: front, side and **curtain** airbags; curtains deploy along the roof rail and over the A- and B-pillars | Present, so no cable or LED in the A-pillar trim or along the roof rail |
| Routes avoid airbag zones | All 12 harness routes read: cameras and LEDs go mirror → door harness → door boot → kick panel; GPS lead behind the instrument panel, "not through the A-pillar trim"; the pod not on the steering column or knee bolster; "never splice into the yellow SRS harness" (M9) | OK |
| Blinker source | Mirror LED turn-signal repeaters are standard on MY2017/2018 (Toyota specs), so each door has a turn feed on the camera's path. Rear turn lamps are separate amber WY21W bulbs, a fallback with no brake circuit mixed in ([BLK-05](03-blinker-sensing.md)) | OK (wire colour unknown: G9) |
| Added load on the lamp circuit | ~6 mA per opto input (3.5 mA at 9 V), adding load rather than removing it, so it can't cause fast flashing (I4) | OK |
| 12 V load on the tap | 1.1 A typical, 2.0 A peak at 12 V, 2.7 A peak at 9 V (doc 01) through a 5 A Add-A-Circuit | OK for any ≥ 10 A ACC slot |
| OBD-II | ISO 15765-4 CAN at 500 kbit/s; 11- or 29-bit identifiers not published, so the client asks for automatic search with CAN 11/500 as the default (`ATSPA6`). PID 0x0D for speed; no turn-signal data in standard OBD-II (O1) | OK (`ATSPA6` fixed by the audit, [SPD](04-speed-sources.md)) |
| Key fob | The car's receiver also uses 315 MHz; everything here is off without ACC, so nothing runs while you use the fob (I5) | OK |

## Findings

| # | Severity | Finding | Fix | Status |
|---|---|---|---|---|
| VEH-01 | Medium | **The ACC line during cranking isn't documented,** nor is the charging voltage the engine computer holds. The power-up logic assumes ACC may dip during START and treats ≥ 13.0 V as "engine running" ([PWR-04](01-power-and-protection.md), [PI-02](06-raspberry-pi.md)) | Meter the chosen fuse slot in ACC, ON and START, and log the running voltage at idle with the headlights and the blower on ([P7](../00-project-management/PREMORTEM_v2.md#power-and-wiring)) | Open (you) |
| VEH-02 | Medium | **The tap can be on the wrong side of its fuse.** An Add-A-Circuit fitted backwards is fed through the original fuse, so the original circuit's fuse carries our 2–2.7 A too ([PWR-P4](01-power-and-protection.md)). A slot that is hot in OFF drains the battery | Choose a slot rated ≥ 10 A that is hot only in ACC and ON; not SRS, engine, lighting or anything safety-related. Find the slot's hot terminal with the meter (fuse removed) and fit the tap so that terminal feeds both fuses, with the 5 A fuse in the tap's new-circuit position. Ground on a body stud with a ring terminal, not on a trim screw | Open (you) |
| VEH-03 | Info | **Airbag keep-outs** (curtains, the knee area, the passenger airbag door) | Already in every route; Option B on the dash top must also stay clear of the passenger airbag door ([SAF](16-safety-and-legal.md)) | OK (design) |
| VEH-04 | Medium | **The door is a wet, moving space.** A cable that sags into the glass channel, the window regulator or the lock rods is cut or jams the window; water runs down the inside of the outer skin | Follow and tie to the factory harness on the inner (dry) side, above the window's travel; reseal the vapour barrier with butyl (M7); cycle the window, the door and the mirror 50 times after the install (M8, now naming the glass and the regulator) | Fixed (procedure) + you |
| VEH-05 | Medium | **The USB plug may not pass the mirror base or the door boot.** A USB-A overmould is ~16 × 8 mm; the factory openings are sized for the mirror's own small connector | Feed a pull wire first, plug end inward. If it doesn't pass, splice the cable inside the car with the pairs kept twisted and the shield continuous, then a 30-minute drive with no USB resets in `dmesg` ([CAM-08](08-cameras-and-vision.md)) | Open (install) |
| VEH-06 | Medium | **Drilling the mirror cap can hit the turn repeater, its wires, or the mirror motor and heater wiring.** A damaged repeater is a lighting defect, not just our problem | Take the cap off (or look inside with a light) and mark the repeater, its wires and the clips before drilling; practise on a spare cap; step drill (M6); then check the repeater flashes | Open (install) |
| VEH-07 | Medium | **The repeater feed's wire colour isn't known.** The wrong wire (heater, puddle lamp, fold motor) reads as a stuck lamp or nothing | G9: wiring diagram, then a meter at the mirror connector: 12 V flashing with that side's signal and with the hazards, 0 V otherwise. Solder and heat-shrink, not T-taps (BLK-P4). The firmware reports a stuck input as a fault (I7) | Open (G9) |
| VEH-08 | Medium | **The OBD dongle is powered all the time** from pin 16, can drain the battery while parked, and anyone in range with the default PIN can send CAN frames (O4, O5) | Measure its parked current (B8); unplug it for long parking, or choose one that sleeps below ~5 mA or needs a button to pair ([SPD-04, SPD-06](04-speed-sources.md)) | Open (B8) |
| VEH-09 | Low | **Trim clips break when panels come off** (kick panels, the console side trim, the door card) | Trim tools; buy a bag of the car's clips before starting; photograph each panel's clip positions | Open (you) |
| VEH-10 | Low | **Reversibility.** The fuse tap, the plugs and the AMPS mount come out cleanly; the mirror-cap holes and the soldered taps don't | Splice into the repeater feed with a solder joint that can be cut and re-insulated later; keep the original caps if you buy spares to drill | Accepted |

## Premortem: the install failed. Why?

| # | How it fails | Likely | Impact | Prevention / detection | Status |
|---|---|---|---|---|---|
| VEH-P1 | The tap's circuit drops in START; the Pi browns out on every start | Medium | SD-card risk, slow start | VEH-01; the Pi is held off until the engine runs (read-only root) | Open (you) |
| VEH-P2 | A camera cable is cut by the window regulator a month later | Medium | One side blind (shown as a camera fault) | VEH-04; the 50-cycle test | Open (install) |
| VEH-P3 | The drill takes out the repeater LED's wire | Medium | A turn signal out (a defect) plus rework | VEH-06 | Open (install) |
| VEH-P4 | The tap is on the heater wire: the side reads lit whenever the heater is on | Low | A fault for that side | VEH-07; I7 reports it | Open (G9) |
| VEH-P5 | A two-week trip ends with a flat battery | Medium | Car won't start | VEH-08 | Open (B8) |
| VEH-P6 | A cable or a box ends up in an airbag's path | Low | Injury | VEH-03 and the routes; check before closing every panel | Fixed (design) + you |
| VEH-P7 | Water follows the camera cable into the door connector | Low | Corrosion, a dead tap | Drip loops below every entry (M7), tap on the dry side | Fixed (procedure) |

## Before you move on

- G9: find and meter the repeater feed on both sides before buying connectors for it.
- Meter the fuse slot in ACC, ON and START (VEH-01, VEH-02).
- Do the door routing with the window fully down and up, and run the 50-cycle test.
