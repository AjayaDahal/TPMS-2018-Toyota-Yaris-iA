# Premortem v2: blind-spot cameras + TPMS, and the 100 × 100 mm carrier PCB

**Date:** 2026-11-25. **Scope:** everything added for v2 — Raspberry Pi 4B, the Official 7" Touch Display, two mirror cameras, blinker sensing, amber blind-spot LEDs, a buzzer, and the 6-layer ESP32 carrier PCB — and whether that PCB can be ordered. The v1 TPMS panel keeps its own premortem in [PREMORTEM.md](PREMORTEM.md); its items still apply to the TPMS part.

## Short answer

**Did the earlier v2 premortem cover everything? No.** It had 12 items, and five of its "fixes" were wrong themselves (a CAN pin that breaks flashing, a power latch that was never designed, LEDs placed in the airbag path, a Pi hole pattern that lands under the ESP32). This pass found 40+ more risks. Everything that can be fixed on paper is now fixed and checked by tests or scripts. What is left needs your hands in the car or on the bench.

**Your two additions are in.** A printable enclosure holds the display, the Pi and the PCB as one unit: [01-hardware/enclosure](../01-hardware/enclosure/README.md), generated, with 38 automated fit checks. The touch screen replaces the v1 rotary encoder, menu buttons, OLED and tyre LEDs. One physical mute button stays, in a small wired pod with the buzzer: it works while the Pi is booting or has crashed, and you can find it without looking.

**OBD-II or tapping the indicators? Tap the indicators.** Standard OBD-II has no turn-signal data. On this car the blinker exists only as a Mazda-private CAN broadcast, which a Bluetooth ELM327 can't follow reliably, and a dropped Bluetooth link would look like "not signalling": no warning, silently. Your dongle is still useful: the car's own speed (PID 0x0D) is now the preferred input of the speed gate, with the GPS as the fallback. No PCB change. Details: [OBD-II dongle](#obd-ii-dongle-optional-speed-source).

| Board | Verdict | Why |
|---|---|---|
| **v2 carrier, 100 × 100 mm, 6-layer** | **Not yet.** The electrical design is frozen and audited; the layout comes next. | Gates G3–G6 below need you: parts on hand, the power-path breadboard test, the display mock-up, and `PI_SEAT` plus a test print of the enclosure (it sets the PCB's keep-outs). Then the KiCad layout and its checks (G7) and the quote (G8). |
| **v1 TPMS panel, 189 × 128 mm** | **Ready** (ERC/DRC 0/0, paper fit done) | It fills the whole console opening. If the 7" display goes there (Option A), v1 has no place in the car: order it only for Option B or as a TPMS-only first step. |

## Order gate for the v2 PCB

| Gate | Needed before ordering | Status |
|---|---|---|
| G1 | Electrical spec frozen; pin map passes the audit | **Done:** [pins_v2.h](../02-firmware/v2/include/pins_v2.h), `python 01-hardware/v2/check_pinmap.py` → 0 errors, its self-test catches all six earlier pin errors |
| G2 | Safety logic written and unit-tested (power-up, blinker, alerts, Pi link, OBD-II speed) | **Done:** [02-firmware/v2](../02-firmware/v2/README.md), 120 host checks pass; removing the hazard fixes, the TPMS acknowledge or the OBD fallbacks makes them fail |
| G3 | Every part physically on hand and identified | **You:** 7" LCD glass + touch + both ribbons (the inventory lists only the adapter board), Pi 4 RAM ≥ 2 GB, CC1101 module pinout, GPS cable pinout, Pololu D36V50F5 bought |
| G4 | Power path breadboarded: EN delay, inhibit, crank dip, 4 A load, `vcgencmd get_throttled` = `0x0` | **You:** procedure in [Bench test B1–B6](#bench-tests-before-layout) |
| G5 | Display location chosen with the 1:1 mock-up (Option A console or B dash top) | **You:** print [v2_fit_template_1to1.pdf](../01-hardware/docs/v2_fit_template_1to1.pdf), tape a 112 × 120 × 61 mm foam block behind the glass outline (the enclosure's rear box), check ≥ 66 mm of pocket depth, the shifter, the HVAC knobs and the car's USB/12 V strip |
| G6 | `PI_SEAT` measured and the enclosure regenerated; bezel and housing test-printed and fitted to the real display and Pi | **You:** 1 measurement + ~12 h of printing. The PCB's keep-outs (fan zone, SMA strip, corners, 16 mm height) come from this |
| G7 | KiCad schematic and layout inside the enclosure's keep-outs, ERC/DRC 0/0, independent Gerber check, footprints printed 1:1 and test-fitted with the real parts | Next step, after G3–G6 (generator based on the v1 build script) |
| G8 | JLCPCB quote confirms the 6-layer 100 × 100 mm promo price and options | **You**, at checkout. Verified from JLCPCB's capability page: 6+ layer FR-4 is ENIG only (no HASL), inner copper is 0.5 oz by default |

Not a PCB gate, but needed before installing: G9, the blinker wire location (any 12 V lamp feed works with the opto inputs). The OBD-II dongle is optional and changes nothing on the PCB: the Bluetooth is inside the ESP32.

A rev-A at $2 is a cheap experiment, so these gates only cover what would make the board useless. Don't wait for anything else.

## Corrections to the earlier v2 plan

| # | Earlier plan said | Problem | Now |
|---|---|---|---|
| C1 | HS-CAN on ESP32 GPIO2 plus an MCP2515 on IO15 for MS-CAN | GPIO2 must be low at reset or serial flashing fails, and a CAN receiver idles high. The MCP2515 also needs an interrupt pin, and no pins were left | CAN moves to a USB CAN adapter (CANable / gs_usb) on the Pi in phase 2: SocketCAN, listen-only, no PCB change |
| C2 | Power latch from 12 V BAT with an "OR gate" and a "30 s hardware watchdog" | Never designed; a stuck latch flattens the battery, and the ESP32 controlled the Pi's power | **ACC-only power (P1).** No latch, no battery tap, zero draw parked by construction. A read-only root makes hard power-off safe |
| C3 | The ESP32 enables the Pi rail | Flashing the ESP32 from the Pi resets it, the rail drops, the Pi dies mid-flash: deadlock | The Pi regulator is **on by default** with ACC (Pololu EN has an internal 100 kΩ pull-up). The ESP32 can only delay it (`PIN_PI_INHIBIT`, pulled down) |
| C4 | Pololu D36V50F5 treated as a 36 V part | Pololu's page: 5.5–50 V in, reverse protection to 40 V, ~5.5 A, EN on by default, 3 A per header pin | Kept, with its real ratings. Power pins on both header rows (6 A per pair) |
| C5 | 1.5KE24CA TVS | Minimum breakdown 22.8 V: it conducts on a 24 V jump start and burns | SMCJ22CA: 24.4 V minimum breakdown, 35.5 V clamp, 1500 W. Same choice as the v1 audit, sized up |
| C6 | (implied) series Schottky for reverse polarity | ~1 W at 2.5 A in an SMA package | P-MOSFET reverse protection (−40 V, ≤ 20 mΩ, e.g. AOD4185) with a 12 V gate clamp |
| C7 | Blind-spot LEDs in the "A-pillar mirror-sail triangles, zero door-boot wires" | The Yaris iA has side-curtain airbags behind the A-pillar trim, and the triangle at the mirror base belongs to the door | LEDs on the inner door sail or in the mirror housing, wired with the camera cable through the door boot. Nothing in the A-pillar trim or on the dash top |
| C8 | Piezo under the steering-column lower shroud | Next to the collapsible column and the knee-bolster area | In the alert pod with the mute button, near the shifter: one 4-wire lead |
| C9 | Bi-colour amber/red LEDs | Red light near the windshield is a legal grey zone and isn't the OEM convention | Amber only: steady = vehicle in the blind spot, flashing = you are signalling towards it |
| C10 | "50 Ω microstrip from the CC1101 to an SMA" on the PCB | The module has its own SMA; there is no RF trace | Module at the board edge with its SMA overhanging; ground plane under it |
| C11 | Pi 4 M2.5 hole pattern (58 × 49 mm) so the PCB can stack behind the Pi | Those holes land under the ESP32 DevKit and the CC1101, and stacking blocks the Pi's fan and USB | Dropped from rev A; 4 × M3 on 92 × 92 mm only |
| C12 | The 7" display "floats in the pocket and clears the shifter" | The glass is 192.96 mm wide; the opening is 191 mm at the top and 132.6 mm at the glass's bottom edge | It can only sit in front of the trim, overhanging ~30 mm per side. Decide with the 1:1 mock-up |
| C13 | The display is "in inventory" | The inventory lists only the Touch Display **Adapter v1.1** board | Confirm the LCD glass, touch panel and both ribbons exist (G3) |
| C14 | Blinker inputs on IO36 / IO39 as interrupts | ESP32 errata 3.11: these pins glitch low for ~80 ns when the ADC or Wi-Fi powers up | Polled at 1 kHz with an RC filter (`poll` tag, enforced by the audit) |
| C15 | "Mirror LED turn signals" on the Yaris iA (drawn in the viewer) | Not verified | Check your mirrors; the plan no longer depends on them |
| C16 | v2 still listed the v1 front-panel controls (EC11 encoder, menu buttons) plus a "camera toggle" button | The 7" touch screen does menus, settings, TPMS pairing and camera calibration; the 2.7" OLED and the 4 tyre LEDs are redundant too | All removed. One mute/acknowledge button stays (IO4, same RC as v1), in the alert pod with the buzzer: it works while the Pi is down, and you can find it without looking |
| C17 | Our own fit template placed the display's M3 holes 0.65 mm off | The drawing dimensions them from the outer frame flange (11.89 line), not the frame body (12.54) | Fixed: x = 34.87 / 161.07 mm (front view), now centred on the flange. Template regenerated; the enclosure uses the same values |
| C18 | Display "0–50 °C, brightness not specified" | The product brief's safety notes say 0–50 °C; the documentation page lists −20 to +70 °C operating, −30 to +80 °C storage, 250 cd/m², 500:1, viewing 50° top / 70° bottom | Design for the brief; 250 cd/m² is dim in daylight (D2); the viewing angles confirm the upside-down mount (D3) |
| C19 | "The Pi's USB end can face either side" | The docs photo shows the documented way: GPIO on top and ports to the right, seen from behind | The enclosure is built for it (ports to the driver's right when mounted upside down). Turned round, 2 fit checks fail |
| C20 | Phase 2: "HS-CAN speed/reverse, MS-CAN turn signals" | For the 2016–21 Mazdas that openpilot supports, the turn lamps (`BLINK_INFO`, 0x9A) and the stalk (`TURN_SWITCH`, 0x91) are on the powertrain HS-CAN, next to the speed (`ENGINE_DATA`, 0x202). This car uses that message family: Metasploit's `mazda_ic_mover` drives the Mazda 2 / Scion iA / Yaris iA cluster with one 0x202 frame | Phase 2 listens on HS-CAN (OBD pins 6/14). The IDs come from opendbc's reverse-engineered `mazda_2017.dbc`: confirm each one on this car (B8) before relying on it |

## Ranked failure stories

Imagine it is a year from now and the system is out of the car. These are the likely reasons, grouped by area, most likely first inside each group. *Status:* **Fixed (design)** = in the spec, pin map or template. **Fixed (firmware)** = in `02-firmware/v2` and unit-tested. **You** = needs a measurement or bench test. **Phase 2** = deliberately later.

### Power and wiring

| # | How it fails | Likely? | Fix | Status |
|---|---|---|---|---|
| P1 | The key passes through ACC on the way to START; the Pi starts booting and the crank browns it out, or it boot-loops | High | Pololu EN RC delay (22 kΩ + 100 µF: ~1.3–1.6 s at 12.6–14.4 V, no start below ~7.5 V). Firmware holds the Pi until the engine runs (≥ 13.0 V for 1 s) or 15 s in ACC | Fixed (design + firmware) |
| P2 | Battery flat after a week parked | High with a latch | ACC-only power: nothing is connected when the key is out | Fixed (design) |
| P3 | SD card corrupted by hard power-off | High without protection | Read-only root (`raspi-config` overlay FS), journal in RAM, settings in ESP32 NVS, a high-endurance card | Fixed (design) + You (Pi setup) |
| P4 | 5 V sags under load: undervoltage flag, USB cameras drop out | High | 5.5 A regulator, 18 AWG under 0.5 m, 470 µF at the Pi end; budget ~2.4 A typical, ~3.8 A peak. Pass = `get_throttled` 0x0 after a 30-minute load test | Fixed (design) + You (B4) |
| P5 | Load dump, jump start, reverse battery or negative spikes kill the board | Medium | Onboard 4 A fuse + SMCJ22CA + P-MOSFET; downstream ratings TSR 1-2450 36 V, Pololu 50 V, MOSFET 40 V. A load dump above 35 V on a car without central suppression is an accepted trade-off (as in v1) | Fixed (design) |
| P6 | AM radio buzz: the ~500 kHz regulator's harmonics fall in the AM band | Medium | π filter (ferrite + 2.2 µH + 2 × 10 µF) on 12 V, short twisted leads, ferrites. Test with the AM radio. Rev B could use a 2.1 MHz automotive buck | Fixed (design) + You (B5) |
| P7 | A fuse tap on the wrong fuse (SRS, engine ECU) or the wrong way round | Medium | One Add-A-Circuit, 5 A, on a non-critical ACC fuse. Meter it: hot in ACC and ON, dead with the key out; note whether it drops in START. Never a yellow SRS circuit | You |
| P8 | Hand-soldering a 6-layer board: through-hole pins on inner planes won't wet | High if solid | Thermal reliefs on all plane connections; ENIG | Fixed (layout rule) |
| P9 | 5 A on 0.5 oz inner copper overheats | Medium | High-current paths as ≥ 3 mm outer-layer pours with stitching vias | Fixed (layout rule) |
| P10 | The ESP32 back-powers an unpowered Pi through the UART | Medium | 1 k / 4.7 k series resistors; firmware keeps UART TX off while the Pi rail is off | Fixed (design + firmware rule) |
| P11 | Opto resistors overheat on a load dump | Low | 2 × 1.1 kΩ 1206 in series per input (0.5 W), 1N4148 reverse diode | Fixed (design) |

### ESP32 and the Pi link

| # | How it fails | Likely? | Fix | Status |
|---|---|---|---|---|
| E1 | A strapping pin is misused: GPIO12 high at reset (wrong flash voltage), GPIO2 high (flashing fails) | High (the earlier drafts did it twice) | Pin map audit with rules for strapping, input-only, flash, boot-glitch, ADC1 and UART0 pins | Fixed (`check_pinmap.py`) |
| E2 | Opening `/dev/ttyUSB0` toggles DTR/RTS and resets the ESP32 | Medium | The runtime link is the GPIO UART (Pi GPIO14/15 ↔ ESP32 UART2); USB is only for flashing. The Pi's power no longer depends on the ESP32 | Fixed (design) |
| E3 | The Pi's UART carries Bluetooth or a login console | High on a default image | `enable_uart=1`, `dtoverlay=disable-bt`, remove `console=serial0,...` from `cmdline.txt` | You (Pi setup checklist) |
| E4 | Garbage, partial lines or a corrupted message trigger a wrong alert | Medium | NMEA-style lines with XOR checksum, strict field parsing, resync on `$`, overlong lines dropped | Fixed (firmware) |
| E5 | A ground offset or noise between the boards corrupts the UART | Low | Common star ground at the regulator; 115200 Bd over < 1 m | Fixed (design) |

### Vision and compute

| # | How it fails | Likely? | Fix | Status |
|---|---|---|---|---|
| V1 | Pi 4 too slow for two streams plus YOLO | High | 320 × 320 NCNN, alternate sides, blinker side first, hardware JPEG decode; fall back to motion-in-ROI. Measure in phase 1 with the two USB cameras you already have, before buying cameras | You (bench) |
| V2 | The Pi 4 has 1 GB of RAM | Medium | `free -h`; need ≥ 2 GB | You (G3) |
| V3 | The Pi throttles in a hot cabin, worse inside a closed enclosure | High in summer | Enclosure airflow: chin intake slots → past the Pi and round the PCB → 30 mm lid fan (inventory) blowing out → a 2 mm gap round the plate (bumps), so the pocket is never sealed. Heatsinks; hot-start hold (board ≥ 60 °C: wait for 55 °C, at most 10 min). Test T1 in a sun-soaked car: SoC < 80 °C, `get_throttled` = `0x0`. If it fails: lower clock, bigger gap, or the PCB in its own box | Fixed (design + firmware) + You (T1) |
| V4 | No small USB camera fits under the mirror (most "mirror cameras" are analog/AHD) | High | Acceptance criteria before buying: UVC MJPEG 720p30, WDR (Starvis), no IR LEDs, −20…+70 °C, IP67, barrel ≤ 20 mm, ≥ 3 m cable, 90–110° lens. Fallback: AHD cameras + a 2-channel USB capture. Measure the barrel before drilling | Decision + You |
| V5 | Cutting the USB cable for the door boot breaks USB 2.0 high-speed | Medium | No JST-GH in the data path: splice with the pairs kept twisted and the shield continuous, or a solder-type USB-A plug. Pass = no resets in `dmesg` on a 30-minute drive | Fixed (design) + You |
| V6 | A folded or bumped mirror points the camera elsewhere; the blind-spot zone is wrong | Medium | At start-up the Pi compares the car-body edge with the stored reference; on mismatch it sets `camFault` for that side → fault pattern on that LED, no alerts from that side | Fixed (protocol + ESP32 logic); Pi side to implement |
| V7 | Night, rain or low sun hides vehicles; motorcycles are tiny | High | Starvis WDR, no IR LEDs, hydrophobic lens coating, headlight-blob fallback in the ROI, lower motorcycle threshold with persistence | Pi software (phase 2 of the build) |
| V8 | The vision app crashes or freezes and the system fails silently | Medium | systemd `Restart=always` + watchdog on the Pi; the ESP32 shows the fault pattern and gives one fault beep after 1 s without a fresh report | Fixed (firmware) |
| V9 | 20–35 s boot: no blind-spot help just after starting | Certain | Lamp test when the system becomes ready, so you know when it works | Fixed (firmware) |
| V10 | OpenCV / NCNN / Python dependency breakage on a later image | Medium | Pinned versions, a provisioning script, a golden SD-card image | You |

### Display and driver interface

| # | How it fails | Likely? | Fix | Status |
|---|---|---|---|---|
| D1 | The display is damaged by a parked car's heat | High on the dash top | Ratings disagree (brief 0–50 °C, docs −20…+70 °C operating, −30…+80 °C storage): design for the brief. Shaded console mount preferred, sunshade, AMPS quick-release for heat waves, hot-start hold | Decision (G5) + Fixed (firmware) |
| D2 | Washed out in sunlight: the docs give only 250 cd/m² and 500:1 | High by day | Shaded mount; the bezel lip shades the border; full backlight by day; high-contrast UI (white on black, large icons). Test in the sun with the mock-up | You (G5) |
| D3 | Poor contrast from the driver's seat | High in the console | **6 o'clock viewing direction**; the docs give 50° from the top, 70° from the bottom. Looking down at it: mount it upside down (the enclosure's default, `MOUNT=inverted`). Rotate the image 180° (Screen Configuration → Inverted, or in the app); touch: `dtoverlay=vc4-kms-dsi-7inch,invx,invy` | Fixed (design) + You (bench check) |
| D4 | The screen and LEDs glare at night | Medium | LED level sent by the Pi (from camera exposure); backlight dimming; optional VL6180X light sensor on I2C | Fixed (protocol + firmware) |
| D5 | Distraction: touching the screen while driving | Medium | Nothing needs touch while moving; camera view only on blinker or danger; the one action you need while driving (mute) is the physical pod button | Fixed (design) + Pi software |
| D6 | A video screen visible to the driver is illegal | Low | Camera views for manoeuvring are generally allowed (e.g. California VC 27602(b)(4)); no entertainment video. Check your state | Accepted |
| D7 | Touch-only controls: no way to silence an alarm while the Pi boots (20–35 s) or after it crashes; gloves | Medium | Mute/acknowledge button in the alert pod, wired to the ESP32 (IO4), which also drives the buzzer and the TPMS logic on its own | Fixed (design + firmware) |
| D8 | Phantom touches or a cracked glass from a bezel that presses on it | Low | The display hangs on its own 4 × M3 frame holes; the lip sits 0.3 mm clear of the glass and only over the black border, outside the touch area | Fixed (enclosure) + You (check after assembly) |

### Mechanical and installation

| # | How it fails | Likely? | Fix | Status |
|---|---|---|---|---|
| M1 | The display doesn't fit: shifter in P/R/N/D/M, your hand, the HVAC knobs | High | 1:1 template + a foam block the size of the enclosure's rear box. The bezel is 127.9 mm tall, under the 129 mm opening, so it doesn't climb onto the HVAC panel (checked by the generator) | You (G5) |
| M2 | The enclosure's rear box (112 × 120 × 61 mm) is deeper than the pocket or hits the car's USB/12 V strip, which sits behind the panel ~34 mm below the top of the opening | High | Measure ≥ 66 mm clear depth with the mock-up. If not: the car's USB moves to a passthrough, or the PCB goes in its own box (same 92 × 92 posts) and the enclosure shrinks to ~45 mm | You (G5) |
| M3 | Printed parts warp or creep in the heat | High in PLA | You can print: ASA or ABS (enclosed printer), PETG only in the shaded console, never PLA (soft at ~55–60 °C). Or MJF PA12 from JLC3DP with the PCB | Plan |
| M4 | The display comes loose in a crash or on bumps | Medium | The display bolts to the housing through its own M3 frame holes; the housing bolts to the car via the AMPS M4 nuts or a pocket bracket, never tape only; no sharp edges; nothing in airbag zones | Fixed (enclosure) |
| M5 | Vibration loosens sockets and connectors | Medium | Latching connectors (Micro-Fit, JST-GH), strain relief, machined sockets + a dab of RTV (v1 rule), nylon lock nuts | Fixed (design rule) |
| M6 | Cracking the mirror cap while drilling | Medium | Practise on a used mirror cap; step drill; measure the camera barrel first | You |
| M7 | Water in the camera, the door or the footwell | Medium | O-ring + neutral-cure (oxime) RTV, drip loop, silicone grease only on the boot, **reseal the door's vapour barrier with butyl** after routing | Fixed (procedure) |
| M8 | Cables break in the mirror hinge or the door boot | Medium | Service loop, follow the factory harness, cycle door / window / mirror 50 times after the install | Fixed (procedure) + You |
| M9 | Cables snag the pedals, the steering column or the seat rails | Low | Tie them up high along existing harnesses; never splice into the yellow SRS harness | Fixed (procedure) |
| M10 | The enclosure is drawn from estimates: the Pi seat height isn't in any drawing; straight Dupont plugs stand ~22 mm on the Pi's GPIO and would hit the PCB | Medium | `PI_SEAT` and `PI_TOP_H` are parameters: measure, regenerate, and the 38 checks re-run. Use 90° or low-profile GPIO housings. Print the bezel first (~2 h) as a fit test | You (G6) |
| M11 | Screws into the display's frame bottom out and press on the panel | Low | M3 × 6 through a 3 mm plate; check the thread depth first | You (assembly) |
| M12 | Fingers reach the boards through vents (Raspberry Pi docs: the enclosure must make the boards unreachable) | Low | Chin slots 2.5 mm; fan grille with 2.5 mm gaps; split grommet in the cable exit | Fixed (enclosure) |
| M13 | The camera USB plugs and the antenna lead don't fit beside the box in the pocket | Medium | 90° USB-A adapters and an SMA bulkhead; the generator checks plugs (+15 mm) and the lead inside the opening's outline (1.3 mm margin at the tightest point) | Fixed (enclosure) + You (mock-up) |

### Vehicle integration

| # | How it fails | Likely? | Fix | Status |
|---|---|---|---|---|
| I1 | No 12 V turn-signal wire found at the kick panel | High | Get the wiring diagram (the Yaris iA is in Toyota's service information, techinfo.toyota.com, short subscriptions) and confirm with a meter. Fallback: the tail-lamp feeds in the trunk. Phase 2: CAN | You (G9) |
| I2 | The body control module drives the lamps with PWM; a simple input sees noise | Medium | The detector bridges PWM gaps up to 25 ms and needs 50 ms to count, so PWM reads as a steady flash and spikes are ignored | Fixed (firmware) |
| I3 | Hazards cause a danger beep (both sides look like turns) | High | Hazards are recognised when both sides light within 150 ms; a single side is reported only after that window, and after hazards end only after a fresh flash | Fixed (firmware) |
| I4 | The added load trips bulb-out detection (fast flash) | Low | Each opto input draws ~6 mA | Fixed (design) |
| I5 | Our electronics desensitise the 315 MHz key fob receiver | Low | ACC-only: everything is off when you use the fob | Fixed (design) |
| I6 | CAN not on the OBD port, or behind a gateway | Unknown | Doesn't matter for the speed: OBD-II requires every car to answer standard requests such as PID 0x0D at the port. Only the phase-2 CAN cross-check needs the broadcasts on pins 6/14: check with a filtered sniff (B8) | Phase 2 |

### OBD-II dongle (optional speed source)

Can OBD-II replace the indicator taps? Not well, but it can feed the speed gate. Sources: SAE J1979 (standard PIDs), the ELM327 datasheet (Elm Electronics), opendbc's `mazda_2017.dbc` and `carstate.py`, and Metasploit's `mazda_ic_mover` module.

| # | How it fails | Likely? | Fix | Status |
|---|---|---|---|---|
| O1 | The blinker is read from the dongle instead of the lamp wires, and a dropped Bluetooth link looks like "not signalling": no danger beep, silently | High if done | Standard OBD-II has no turn-signal data; the lamps exist only as a Mazda-private broadcast (0x9A). The blinker stays on the opto taps (G9); OBD is used for the speed only. A CAN blinker is at most a phase-2 cross-check on a wired, listen-only adapter | Fixed (design) |
| O2 | The ELM327 is asked to listen to the bus (`AT MA`) and overflows | High if done | Datasheet: a 512-byte buffer, and at the 38.4 kbaud a typical Bluetooth clone uses inside, printing one frame takes ~5.2 ms, while a 40 %-loaded 500 kbit/s bus delivers one every ~0.35 ms: `BUFFER FULL`. Monitoring also blocks requests. The firmware only *requests* PID 0x0D (`010D1`), one at a time | Fixed (firmware) |
| O3 | The dongle sleeps, hangs, answers `?` or `NO DATA`, or the link drops; the speed goes stale | High (cheap clones) | 1 s timeouts, a reset (`ATZ`) after 3 failures, plain `010D` for clones without the response-count digit, reconnect. OBD speed counts only while < 1 s old; then the GPS takes over, then the 10 s hold, then LEDs only. A bad dongle can only make the buzzer quieter | Fixed (firmware) |
| O4 | Flat battery: the dongle is powered from OBD pin 16, always on. ELM327 datasheet: "about as much current as a dome lamp" (29.8 mA for its reference circuit, 17.6 mA in low-power mode) | High for no-name clones | Measure its parked current (B8). Keep it plugged in only if it sleeps below ~5 mA; otherwise unplug it when parked for days, or use an OBD extension with a switch | You (B8) |
| O5 | Anyone in Bluetooth range connects with the default PIN and injects CAN frames: `mazda_ic_mover` moves this car's cluster needles with one 0x202 frame | Low | A dongle that needs a button press to pair, or sleeps its radio when parked; change the PIN if it allows; unplug it for long parking. The ESP32 itself only sends the setup `AT` commands and `010D` | You (choice of dongle) |
| O6 | Bluetooth on the ESP32 disturbs the 315 MHz decoder's edge interrupt or the 1 kHz loop | Low | Bluetooth stack on core 0; the RF edge interrupt (`rf_capture.cpp`) and the 1 kHz loop on core 1. B8 compares the TPMS decode rate with the link on and off | You (B8) |
| O7 | The Pi would be the natural Bluetooth host, but its Bluetooth is off (`dtoverlay=disable-bt`: the PL011 UART carries the ESP32 link) | Certain | The ESP32 talks to the dongle: the WROOM-32 has Bluetooth Classic. Connect by MAC address (a name search takes seconds), PIN usually 1234 or 0000. No change on the Pi or the PCB | Fixed (design) |
| O8 | The dongle is BLE-only (if it works with an iPhone, it is BLE or Wi-Fi), so Bluetooth Classic serial can't reach it | Medium | Identify it first. The client logic doesn't depend on the transport: a BLE dongle needs a GATT client (NimBLE) instead of `BluetoothSerial`; a Wi-Fi one is out (the ESP32's Wi-Fi stays off) | You |
| O9 | A long dongle or an extension at the driver's knee catches a foot or a knee | Low | Low-profile dongle, or a short right-angle extension tied up out of the footwell | Plan |

### TPMS radio

| # | How it fails | Likely? | Fix | Status |
|---|---|---|---|---|
| R1 | The 433 MHz-tuned CC1101 module loses up to ~10 dB at 315 MHz; rear wheels drop out | Medium | Buy a 315 MHz-tuned CC1101 module with the same 2 × 4 pinout (~$3); keep the 433 one as a spare. Check RSSI per wheel | Buy + You |
| R2 | The Pi 4, its USB 3 ports, the display and the regulator raise the 315 MHz noise floor | Medium-High | The antenna leaves the enclosure: CC1101 → short RG316 → SMA bulkhead in the box wall → 30 cm RG316 → whip away from the Pi; cameras on the USB 2.0 ports; ferrites. Compare the noise floor with everything on and off | You (B6) |
| R3 | The EG53MA4 decoder fails on real frames | Medium | Not yet tested on a real capture: drive with `rtl_433 -f 315M` first (v1 premortem step 1) | You |

### Safety and nuisance

| # | How it fails | Likely? | Fix | Status |
|---|---|---|---|---|
| S1 | Nuisance alerts in parking lots, drive-thrus and queues | High | No alerts below 8 mph, on again at 12 mph (hysteresis); hazards silent; the mute button silences the current turn only; at most one danger beep per 3 s, and a flickering detection can't beep more than once a second | Fixed (firmware) |
| S2 | GPS lost under a bridge or in a tunnel: alerts stop or go wild | Medium | The car's own speed from the OBD dongle covers tunnels, garages and GPS cold starts. Without both, the last moving/slow decision is held 10 s; after that the LEDs keep working and the buzzer stays quiet | Fixed (firmware) |
| S3 | Trusting it: a missed motorcycle at night | Medium | It is an aid: always look over your shoulder. Disclaimer on the start screen | Accepted |
| S4 | A silent failure looks like "all clear" | Medium | Fault pattern + one beep on a lost Pi link; per-side fault for a camera | Fixed (firmware) |
| S5 | The blind-spot beep is drowned out by a TPMS reminder or vice versa | Low | Priorities: danger, then fault, then TPMS; TPMS repeats at most every 10 minutes | Fixed (firmware) |

### Project

| # | How it fails | Likely? | Fix | Status |
|---|---|---|---|---|
| J1 | Scope creep: the project never finishes | High | Ship in useful steps: (1) the camera view switches on the blinker, no AI; (2) detection, LEDs and buzzer; (3) CAN and the 60 GHz radar | Plan |
| J2 | Footprint errors (Pololu module, DevKit, connectors) | Medium | Print the layout 1:1 and set the real parts on it before ordering, as for v1 | G7 |
| J3 | Inventory entries are wrong or incomplete | Medium | Collect every part before the layout freeze (G3) | You |
| J4 | Tools missing for the car work | Medium | Multimeter, trim tools, fine crimper for JST-GH (or pre-crimped leads), solder-type USB-A plugs, step drill, heat gun: see the tools checklist in the viewer | Plan |
| J5 | The enclosure becomes the long pole (~12 h of printing per try, ASA needs an enclosed printer) | Medium | Parametric generator with fit checks; print the bezel first; foam mock-up before any printing; MJF PA12 as the no-printer route | Plan |

## The v2 design after this pass

**Enclosure:** [make_enclosure.py](../01-hardware/enclosure/make_enclosure.py) builds:

- a bezel with an air-intake chin;
- a housing: the plate the display screws to, and the rear box for the Pi and the PCB;
- a lid with the fan;
- the alert pod.

Overall 205.6 × 127.9 × 71.8 mm, mounted upside down (cable edge up). The rear box (112 × 120 mm, 60.5 mm deep) drops into the console pocket, or the AMPS pattern takes a RAM base on the dash. The PCB sits behind the Pi, parts facing the lid, inside these keep-outs: 16 mm part height, a fan zone, the SMA strip, corners free of pins.

**Controls:** the touch screen for everything. One mute/acknowledge button (IO4) and the 12 V piezo (IO13) sit in the alert pod on one 4-pin JST-GH. No encoder, menu buttons, OLED or tyre LEDs.

**Blinker and speed:** the blinker comes from the two opto taps on the 12 V lamp feeds (G9), never from OBD-II. The speed gate takes the car's own speed from your OBD-II dongle while it answers (PID 0x0D: ESP32 Bluetooth Classic → ELM327, 5 Hz), else the GPS, else the 10 s hold, then LEDs only. The `$ESP` line tells the Pi which source is in use (`O` / `G` / `N`).

**Power (P1, ACC-only):** one Add-A-Circuit (5 A) on a non-critical ACC fuse → J1 Micro-Fit 3.0 (2 × ACC, 2 × GND) → 4 A fuse → SMCJ22CA → P-MOSFET reverse protection → π filter + 47 µF/50 V → `12V_PROT`.

- `12V_PROT` → TRACO TSR 1-2450 → `5V_ESP` (DevKit VIN, LEDs, GPS) → AMS1117-3.3 + 22 µF tantalum → `3V3` (CC1101, I2C).
- `12V_PROT` → Pololu D36V50F5 → `5V_PI` → J5 Micro-Fit (2 × 5 V, 2 × GND) → 90° USB-C pigtail to the Pi + 5 V/GND to the display adapter; a 2-pin header for the lid fan. EN: internal 100 kΩ to VIN, 22 kΩ + 100 µF to GND (start delay), 2N7002 through 100 Ω to pull it low on `PI_INHIBIT`; PG → GPIO15 with 10 kΩ to 3V3.
- `12V_PROT` → 33 Ω + SMAJ18A → J POD → 12 V active piezo (3–24 V type) in the alert pod, low-side MOSFET on GPIO13; the pod's mute button returns on the same connector to GPIO4.
- ACC sense: 100 kΩ / 10 kΩ + BAT54S clamp + 100 nF → GPIO32.

**Pins:** [pins_v2.h](../02-firmware/v2/include/pins_v2.h). The CC1101, I2C and buzzer pins are those of v1, so the v1 radio driver and EG53MA4 decoder are reused unchanged. All 25 DevKit GPIOs are used; GPIO12 stays unconnected.

**Pi side:** Bookworm 64-bit Lite, overlay file system on, `enable_uart=1`, `dtoverlay=disable-bt`, no serial console, `dtparam=watchdog=on`, the app as a systemd service with `Restart=always`, journal in RAM.

**Phase 2 (no PCB change):** a CANable-type USB CAN adapter on the Pi, listen-only on HS-CAN (OBD pins 6/14): wheel speeds, gear, and the blinker broadcast as a cross-check of the lamp taps (opendbc's 2017 Mazda IDs, to confirm on this car, C20). The Infineon 60 GHz radar on Pi GPIOs.

## Bench tests before layout

Power the breadboard from the ATX supply's 12 V rail or the 3S LiPo (both in the inventory) through a 5 A fuse.

| Test | Do | Pass |
|---|---|---|
| B1 | Pololu with EN = 22 kΩ + 100 µF; apply 12.6 V, then 14.4 V | 5 V appears 1.3–1.6 s after power; nothing below ~7.5 V |
| B2 | Pull EN low through a 2N7002 + 100 Ω from a 3.3 V source | Output off within ms; ~1.5 s restart after release |
| B3 | Crank simulation: 12.4 V for 0.5 s, 0 V for 1.5 s, then 14.2 V | The Pi starts only after the "engine" voltage, never during the dip |
| B4 | Pi 4 + display + both cameras + fan, CPU stressed 30 min | `vcgencmd get_throttled` = `0x0`, regulator < 80 °C |
| B5 | Car AM radio near the running setup (or a portable AM radio) | No audible whine on 530–1700 kHz with the π filter fitted |
| B6 | CC1101 noise floor with the Pi, display and cameras off, then on | Rise < 6 dB; otherwise move the antenna out on RG316 and add ferrites |
| B7 | Display upside down: rotate 180° (Screen Configuration → Inverted), `dtoverlay=vc4-kms-dsi-7inch,invx,invy`; look at it from your seat's angle both ways | Touch lands where you tap; the inverted way has better contrast from above |
| B8 | Your OBD-II dongle (optional), in the car: (a) its current from pin 16 after 15 min with the key out (OBD extension + multimeter); (b) the ESP32 paired with it over Bluetooth Classic, with the 315 MHz decoder running; (c) optional, from a phone serial-terminal app: `ATH1`, `ATSP6`, `ATCRA 09A`, `ATMA` while signalling | (a) below ~5 mA, else unplug it when parked; (b) speed within ~3 s of connecting and matching the speedometer, TPMS decode rate unchanged; (c) byte 2 bits 2 / 3 follow the lamps: note it for phase 2 |
| T1 | In the printed enclosure, in the car, after it has sat in the sun: vision app running for 30 min | `vcgencmd measure_temp` < 80 °C and `get_throttled` = `0x0` |

## What to do next, in order

1. Collect the parts (G3) and run `rtl_433 -f 315M` while driving to log the four tyre IDs. Identify your OBD-II dongle (Bluetooth Classic or BLE, PIN, MAC address) and measure its parked current (B8a); it is optional and blocks nothing.
2. Print the template and tape the foam block (the rear box) behind the glass outline. Mock it up in the car and choose Option A or B (G5).
3. Measure `PI_SEAT` on the real display, regenerate the enclosure, and print the bezel, then the housing. Fit the display and the Pi (G6), then run B7.
4. Breadboard the power path and run B1–B6 (G4).
5. Then the KiCad layout (G7) inside the enclosure's keep-outs, with the generator, ERC/DRC, Gerber check and 1:1 footprint fit; then the quote and order (G8).
6. After the board is built: T1 in the car.
