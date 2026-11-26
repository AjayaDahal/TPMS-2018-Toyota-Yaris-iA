# v2 enclosure (3-D printed)

One printed unit holds:
- the **SunFounder TS-7 7" HDMI touch display** (1024 × 600 IPS, the one in the inventory);
- the **Raspberry Pi 4** on four posts behind it;
- the **100 × 100 mm carrier PCB** behind the Pi.

The **12 V piezo** sits inside the unit, behind the intake slots right of the screen, and every beep stops by itself, so v2 has no physical button. Both **USB passthroughs from v1** move into one printed **twin USB wing** on the unit's right edge, in v1's Ø25.8 mm cut with 23.8 mm double-D flats (from your caliper photos: 25.16 mm thread, 23.28 mm across the flats). The rotary encoder, the menu buttons, the 2.7" OLED and the four tyre LEDs from the v1 panel aren't used in v2: the touch screen does menus, settings, TPMS pairing, camera calibration and mute.

Outside the dash unit, [`make_mounts.py`](make_mounts.py) makes a **camera pod** for under each door mirror and an aimed **LED pod** for each inner door sail: see [Mirror cameras and door LEDs](#mirror-cameras-and-door-leds). The viewer shows every printed part assembled, exploded and on the print bed: **3. Printed Parts & Assembly** ([04-viewer](../../04-viewer/README.md)).

```
python 01-hardware/enclosure/make_enclosure.py                                     # STLs + report + 63 checks
python 01-hardware/enclosure/make_enclosure.py --set MOD_H=124.6 HDMI_Y=23.5       # your measurements
python 01-hardware/enclosure/make_enclosure.py --set HDMI_PLUG=22,21,6.5           # tuples as comma lists
python 01-hardware/scripts/make_v2_fit_template.py                                 # then redraw the 1:1 template
```

Needs `pip install manifold3d numpy`. It writes:

- `stl/print_*.stl`: the four parts (bezel, housing, lid, USB wing) in print orientation, flat face on the bed, no supports.
- `stl/asm_*.stl`: the assembly with dummies of the display, its plugs, the Pi, the PCB, the fan, the piezo, the USB passthrough and the wing's screws, used by the [viewer](../../04-viewer/README.md).
- [enclosure_report.json](enclosure_report.json): dimensions, Z levels, PCB keep-outs, hardware, the piezo and the USB passthrough, the front-view outlines the [fit template](../docs/v2_fit_template_1to1.pdf) draws, and every check.

The script exits with an error if a check fails. The checks cover:

- every part is a closed solid and fits a 220 × 220 mm bed;
- no clash between any part and the display, its HDMI and micro-USB plugs and their leads, the Pi (with its 90° plugs and SD card), the PCB, its part-height budget, the fan, the SMA bulkhead, the bezel screw heads, the piezo, the USB passthrough with its cable, or the wing's screws;
- the display hangs on four bosses that touch only its ears;
- the bezel's lip covers the glass edge but clears the active area;
- the plugs fit inside the bezel;
- the PCB posts are on 92 × 92 mm, the Pi posts on 58 × 49 mm, and the Pi-to-PCB air gap holds;
- every vent is finger-safe;
- the box, its ears, the 90° USB plugs, the display leads, the antenna lead and both USB passthrough cables fit the console opening;
- the plate's cable slot opens into the pocket;
- the bezel stays below the HVAC panel;
- the piezo sits behind at least three intake slots with an air gap;
- both USB passthroughs use the v1 cut (with the measured double-D flats), their two 36 mm nuts spin on the bench and clear the trim when tightened, both plugs pass every opening one after the other (plug #2 alongside cable #1), the wing fits the trim beside the bezel and its 3 screws bite.

> **Measure the display first.** SunFounder publishes no drawing. Its table says the module is 165.30 × 121.00 × 7.75 mm, but four of its product photos give a board about **124.4 mm** tall over the ears, which is what the defaults use. The ear holes, socket positions and the height of the parts on the back are taken from photos. Lay the display on page 1 of the [fit template](../docs/v2_fit_template_1to1.pdf), measure the values in [Measure first](#measure-first-then---set), regenerate, then print.

## Result (default parameters)

| | |
|---|---|
| Overall | 205.6 × 129.0 × 70.3 mm (bezel front to lid), as tall as the console opening |
| In front of the trim | 21.8 mm (bezel front to the back of the plate, plus the 2 mm bumps). The official display's design stood 13 mm proud: check the shifter in P with the mock-up |
| Rear box | 112 × 124 mm (126 mm wide at the lid ears), 50.5 mm behind the plate |
| Console pocket (Option A) | needs **≥ 56 mm of clear depth** behind the trim. It fits the 191 / 123 × 129 mm opening with 3.0 mm to spare at the tightest point |
| Screen | 8 mm left of centre (toward the driver): the HDMI and micro-USB plugs need the room on its right |
| Twin USB wing | 32.9 × 81.2 mm on the trim against the bezel's right edge (2 sockets, 39 mm pitch), its front 15.1 mm proud of the bezel's; the sockets end 40.9 mm right of the bezel |
| Plastic | ~241 cm³ solid (bezel 47, housing 139, lid 35, USB wing 20), plus ~63 cm³ for the mounts (camera pods 2 × 28, drill guide 3, LED pods 4): ~304 cm³, under one 1 kg spool |

## Parts

| File | Print | What it does |
|---|---|---|
| `print_bezel.stl` | Face down | Front frame. The display **hangs by its four corner ears on four bosses** in the bezel (M3 × 6 from behind), so its glass carries no load and sits 0.3 mm behind the lip. The lip covers only the outer 2 mm of the glass; the glass's own black border does the rest. Behind the frame, a cavity on each side of the screen: the left one and the lower right one have **intake slots**, 2.5 mm wide; the upper right one holds the plugs. Three fingers on the skin hold the **piezo** behind the lower right slots. A side opening, hidden by the USB wing, lets the passthrough's cable in. Walls are only 2 mm top and bottom, so the frame is no taller than the opening |
| `print_housing.stl` | Plate (front) down | The **plate** behind the display, 0.4 mm clear of the parts on its back. It carries the bezel (6 × M3 × 10 from behind), three intake windows, and the **cable slot** (12.2 × 24 mm, rounded corners) where the display's leads and both car-USB cables go back into the pocket. Behind it, the **box**:<br>• the Pi on four posts and the PCB on four more;<br>• the window for the Pi's USB/Ethernet;<br>• the slot above it where the display leads come in;<br>• an SMA bulkhead hole;<br>• an AMPS 30 × 38 pattern with captive M4 nuts in the bottom wall;<br>• 2 mm bumps on the back of the plate. |
| `print_lid.stl` | Outside down | The 30 mm fan from the black Pi case sits under a finger-safe grille and blows **out**. Also a 22 × 8 mm cable exit (fit a split grommet) and a locating rim |
| `print_usb_wing.stl` | Front face down | Holds **both USB passthroughs from v1** beside the bezel's right (passenger) edge, stacked vertically (39 mm pitch), sockets facing the passenger, in v1's **Ø25.8 × 23.8 mm double-D cuts** (measured 25.16 mm thread, 23.28 mm across flats). The rear double-D flat sits on top during printing so both holes bridge flat with no supports. Open at the back (VHB to the trim), with room for both 36 mm hex nuts to spin on the bench (or mount from behind with the nut outside). 3 × M3 × 10 from inside the bezel's right cavity into its top, centre and bottom bosses; an 8 mm rear channel lets the lower cable climb behind the centre screw post |

### Why it is built this way

- **Stack** (Z = 0 at the glass front, toward the lid):
  - the display's board back (−7.75);
  - its tallest back part (−14.05) and the plate (−14.45 to −17.45);
  - the Pi on 5 mm posts (board −22.45, tallest part −40.85) and a 3 mm air gap;
  - the PCB (−46.35 / −47.95) with its 16 mm part budget;
  - the lid (−67.95).

  The PCB's flat underside faces the Pi and its parts face the lid, so taking the lid off shows every connector.
- **The Pi** sits the usual way round turned upside down (a rotation, not a mirror): USB/Ethernet toward the driver's right, so its HDMI / USB-C edge is on top and the GPIO header at the bottom. The two micro-HDMI ports and the USB-C socket face up into free space, where the 90° plugs fit.
- **Normal way up.** The TS-7 is IPS ("viewing direction: all", 170°), so unlike the official display it doesn't need to be turned over for contrast from above. No rotation in the Pi's settings; touch works out of the box (USB HID).
- **Display cables.** Both sockets are on the back of the display's board at its right edge, pointing right. The plugs sit in the bezel's right cavity:
  - **HDMI:** a straight HDMI-A flat-cable (FPC) adapter in the display, its flat cable folded up over the adapter;
  - **USB:** a 90° micro-USB plug, its lead leaving upward.

  Both rise to the plate's cable slot (12.2 × 24 mm, inside the opening's outline), pass into the pocket beside the box, and enter the box through the slot above the USB window. There the flat cable ends in a straight micro-HDMI adapter in the Pi's **HDMI0** (next to USB-C), folded toward the slot.
- **Display power and touch on one split lead.** The TS-7 takes 5 V (0.48 A typical) and its touch data on the same micro-USB. Powered from a Pi USB port, the display plus two cameras would come close to the 1.2 A the Pi shares between all four ports ([DSP-03](../../05-Audit-Subsystems/09-display-and-ui.md)). So the lead splits behind the plate:
  - **5 V and GND** go to **J5's second pair** on the carrier (the 5V_PI rail);
  - **D+, D− and GND** go to a 90° USB-A plug in one of the Pi's blue USB 3.0 ports, through the window.

  Cut the red (VBUS) wire on the Pi's leg: the two 5 V sources must not be joined. SunFounder asks for USB power before HDMI, and one rail powering both does exactly that.
- **Airflow.** Cabin air enters through the bezel's slots (771 mm², 2.5 mm wide), flows behind the display (cooling its scaler chip), through the plate's three windows, past the Pi and round the PCB, and leaves through the lid fan.
  - Option A (box in the console pocket): the 2 mm bumps hold the plate off the trim, so the air leaves round the edge of the frame. Don't seal that gap or the pocket.
  - Option B (dash top): the box is in free air.
- **Controls.** Touch does everything, mute included: there is no physical button. That's safe because no beep can nag:
  - a blind-spot episode beeps at once and again after 3 s, and is quiet from 4 s on while the door LED keeps flashing;
  - a TPMS warning beeps, reminds twice, then only the screen shows it;
  - a fault beeps once.

  While the Pi boots or after a crash, the ESP32 still warns on its own. The carrier's J4 keeps the button pins (IO4) if you ever want one.
- **Piezo inside.** A 23 mm 12 V active piezo hangs on three fingers on the bezel's skin, behind the lower right intake slots (5 slots, ~148 mm² in front of it), its face 2 mm off the skin: you hear it through the slots, and the cabin air still flows past it. Its two wires go up the right cavity and out through the plate's slot to J4 on the carrier.
- **Two USB passthroughs (from v1).** The display fills the console opening, so the passthroughs can't face the driver: their 25 mm bodies and 36 mm nuts have no room behind the bezel. Both sit stacked vertically (39 mm pitch) in one printed **twin wing** on the bezel's right (passenger) edge, facing the passenger, their bodies lying along the trim. The double-D cuts (Ø25.8 × 23.8 mm, from your caliper photos: 25.16 mm thread, 23.28 mm across flats; set `PASS_FLAT_W=0` for plain round) keep the USB-A slots horizontal and stop either socket twisting when you plug a cable in. Their cables:
  1. the lower cable climbs behind the centre screw post inside the wing's 8 mm rear channel;
  2. both enter the bezel through one 25 × 9.5 mm side opening (hidden by the wing);
  3. cross the right cavity above the display's plugs;
  4. drop through the plate's 12.2 × 24 mm cable slot into the pocket (the car's USB port + the second USB port or a flush 12 V USB charger).

  The 36 mm hex nut sets the wing's depth (15.1 mm proud of the bezel so the nut can spin freely on the bench, or mount from behind with the nut outside). Measure the remaining passthrough dimensions (below) and regenerate.
- **Fingers.** The boards stay out of reach: 2.5 mm slots, the bar grille on the fan, a grommet in the cable exit. The plate's windows are behind the display.

## Measure first (then `--set`)

Measure with calipers, front view (glass toward you), from the centre of the display's board.

| Parameter | Default | Measure |
|---|---|---|
| `MOD_H` | 124.4 | Board height over the ears. SunFounder lists 121.0; its photos say 124.1–124.8. The bezel and the opening allow up to ~124.9 |
| `MAIN_H`, `EAR_W` | 106.4, 7.6 | Board height between the ears; width of one ear |
| `HOLE_IN_X`, `HOLE_IN_Y` | 4.0, 5.0 | Ear-hole centre from the board's side edge and from its top/bottom edge (holes 157.3 × 114.4 apart). **Check against the fit template: the bosses must match within ~0.3 mm** |
| `GLASS_DY` | −0.5 | Glass centre above (+) or below (−) the board centre |
| `BACK_H` | 6.3 | Tallest part on the back of the board (the HDMI socket). Moves the plate and everything behind it |
| `HDMI_Y`, `USB_Y` | 25.0, 4.0 | Socket centres above the board centre (right edge, seen from the front) |
| `HDMI_PLUG` | 20, 22, 6 | Your straight HDMI-A FPC adapter: length past the socket face, width, thickness |
| `USB_PLUG` | 11, 12, 7 | Your 90° micro-USB plug: the same three |
| `LCD_FPC_X` | −16.5, 13.5 | Where the LCD's flex wraps round the bottom edge |
| `PI_TOP_H` | 17.0 | Tallest part above the Pi's board. The UART plug on the GPIO must be **90° or low-profile** Dupont: straight ones stand ~22 mm |
| `BUZ_D`, `BUZ_H` | 23.2, 12 | The 12 V active piezo you buy: diameter, height without its leads |
| `PASS_THREAD_D`, `PASS_HOLE_D` | 25.16, 25.8 | Thread Ø (measured from your caliper photos); the v1 cut. Keep 0.3–0.7 mm between them |
| `PASS_FLAT_D`, `PASS_FLAT_W` | 23.28, 23.8 | Across the two double-D flats (measured from your caliper photos); the double-D cut (`0` for plain round) |
| `PASS_COLLAR` | 28.2, 3 | **USB passthrough:** collar / flange diameter and thickness (or confirm rear-mounted with front nut) |
| `PASS_FRONT` | 24.2, 8 | The socket body in front of the panel: diameter; how far it stands out in all |
| `PASS_REAR_L` | 22.4 | Thread + body behind the panel, up to where the cable leaves |
| `PASS_NUT` | 36, 5 | The nut: across corners, thickness |
| `PASS_CABLE_D`, `PASS_PLUG` | 5.5; 16.5, 8.5 | The cable; the male plug's moulding (width, thickness). Every opening passes plug #2 alongside cable #1 |
| `PASS_YS` | 43.0, 4.0 | Upper and lower socket centres above the bezel's centre line (39 mm pitch) |
| `TRIM_RIGHT` | 36, 86 | Flat, free trim right of the bezel's edge where the twin wing lands: width, height. Nothing (vent, glovebox, a knee) within ~45 mm in front of it |
| Pocket | ≥ 56 mm | Clear depth behind the trim where the box goes (Option A), and where the car's USB / 12 V strip is. It sits behind the panel, ~34 mm below the top of the opening (v1 `panel_config.py`), right in front of the box: the passthrough's plug goes into the car's USB port there |
| Fan | 30 × 30 × 10, holes 24 mm | Your fan's thickness and hole spacing |

## Material and print settings

- **ASA** (best: UV-stable, heat-deflection ~93–103 °C) or **ABS**, both in an enclosed printer. **PETG** only for the test fit: its 68–78 °C is about the cabin air of a car parked all day in a hot climate, and the bezel carries the display ([audit ENC-04](../../05-Audit-Subsystems/10-enclosure-and-thermal.md)).
- **Never PLA:** it softens at ~55–60 °C; a parked car's cabin air reaches 52–76 °C and the dash top ~85 °C.
- No printer that does ASA? Order the parts in **MJF PA12** (e.g. JLC3DP) with the PCB.
- 0.2 mm layers, 4 perimeters (the bezel's top and bottom walls are 2 mm: 4–5 perimeters, no infill), 30–40 % gyroid, brim for ASA/ABS, no supports. The bezel and the housing need a bed of at least 210 × 135 mm.
- Print the **bezel first** (thin, ~2 h) and hang the display in it before spending ~10 h on the housing.

## Hardware

| Joint | Parts |
|---|---|
| Display → bezel | 4 × M3 × 6 pan or button head, from behind through the ears (M3 × 8 would reach the front face) |
| Bezel → plate | 6 × M3 × 10 from the back of the plate into 2.6 mm pilots, don't overtighten |
| Pi → posts | 4 × M2.5 × 6 into 2.2 mm pilots |
| Lid → box | 4 × M3 × 12 into the ears |
| PCB → posts | 4 × M3 × 6 |
| Fan → lid | 4 × M3 × 16 + nuts, label facing out (blowing out) |
| AMPS mount | 4 × M4 nuts pressed into the bottom bosses + M4 × 10 (Fgruh kit). Fits a RAM-B-202U round base or a car bracket |
| Twin USB wing → bezel | 3 × M3 × 10 socket cap from inside the bezel's right cavity, before the display goes in; 3M VHB on the wing's back edges to the trim |
| Piezo | A dab of neutral-cure RTV on each of its three fingers |
| Buy | **HDMI FPC kit:** a straight HDMI-A male adapter, a straight micro-HDMI male adapter and a 20 cm flat cable (the kit's 1 m HDMI to micro-HDMI cable is far too stiff for the box). **A 90° micro-USB lead** whose cable leaves along the plug's wide face ("left" or "right" angle, not up/down). Which of the two points upward depends on how the socket is mounted: check the display first, or buy both. Split it as described above. Also:<br>• a split rubber grommet for the cable exit;<br>• an SMA bulkhead to SMA pigtail (RG316, ~10 cm) plus a 30 cm RG316 extension;<br>• three 90° USB-A adapters or plugs (two cameras, touch);<br>• 90° Dupont housings;<br>• a 90° USB-C plug on the power pigtail. |

## Assembly

1. **Pi:** screw it onto its four posts in the housing (M2.5 × 6), ports into the window. Fit:
   - the micro-HDMI adapter in HDMI0 (the one next to USB-C);
   - the 90° USB-C pigtail;
   - the UART lead (90° Dupont on GPIO 14/15 + GND).
2. **Twin USB wing**, while the bezel is still empty:
   - On the bench, fit **both** USB passthroughs into the wing's double-D holes and tighten their hex nuts (leave two flats horizontal so they clear the trim; if your ALTW connectors are rear-mounted with a front nut, insert them from the open back and tighten the nuts from outside).
   - Lay the bezel face down on a soft cloth. Route the lower passthrough's cable up behind the wing's centre screw post, feed **both** USB plugs (one after the other) through the bezel's side opening into the right cavity, and screw the wing onto the bezel with 3 × M3 × 10 from inside the right cavity.
3. **Piezo:** press it into the three fingers below the wing's bottom screw, face on the ledges, a dab of RTV on each finger; lay its two wires up the right cavity.
4. **Display:** put it face down into the bezel and screw it to the four bosses through its ears (4 × M3 × 6). Plug in the HDMI adapter (fold its flat cable up over the adapter) and the 90° micro-USB plug (lead upward), and lay both leads up the bezel's right cavity.
5. **Close the front:** thread **both** passthrough USB plugs through the plate's cable slot **first** (one after the other — plug #2 passes alongside cable #1 before the display's leads go in), then both display leads and the piezo's wires. Set the housing on the bezel and screw it on from behind (6 × M3 × 10).
6. **Display leads:** behind the plate, feed the flat cable and the power leg into the box through the slot above the USB window. Click the flat cable into the micro-HDMI adapter. Plug the lead's USB-A leg into a blue USB 3.0 port through the window.
7. **PCB:** fit it on its posts, parts facing you. Connect:
   - the USB-C pigtail to J5 pair 1;
   - the display power leg to J5 pair 2;
   - the UART lead;
   - the piezo's two wires to J4 ("POD": + and −; the button pins stay free);
   - the RG316 pigtail from the CC1101 to the bulkhead;
   - the fan to the PCB's 5 V header.
8. **Lid:** feed the harness (12 V, blinkers, LEDs, GPS) through the lid's cable exit with a grommet and plug it in. Close the lid (4 × M3 × 12).
9. **In the car:**
   - Plug both passthrough cables into the car's USB ports (or car USB + flush 12 V USB charger) in the pocket.
   - The camera USB plugs go into the Pi's black USB 2.0 ports through the window, with 90° adapters when the box sits in the pocket.
   - VHB on the wing's back edges, then push the unit home so the wing lands flat on the trim.

## Before trusting it in the car

- **Display on the bench:** Raspberry Pi OS (Bookworm) finds the TS-7 on HDMI-A-1 at 1024 × 600 by itself. If the screen stays black, add `video=HDMI-A-1:1024x600@60` to `cmdline.txt`. SunFounder documents no brightness control: try `ddcutil detect` (DDC/CI over HDMI). If it answers, the Pi can dim the backlight at night; if not, use a dark UI at night ([DSP-04](../../05-Audit-Subsystems/09-display-and-ui.md)).
- **Thermal test T1:** a sun-soaked car, the vision app running, 30 minutes. Pass = `vcgencmd measure_temp` below 80 °C and `vcgencmd get_throttled` = `0x0`. If it fails:
  - lower the Pi's clock;
  - open the gap round the plate;
  - or move the PCB to its own vented box (the posts and the 92 × 92 pattern stay the same).
- **Mock-up first:** a foam block of the box size behind the template's bezel outline (fit template, note 3) answers the pocket-depth and shifter-clearance questions for free. Tape a cardboard twin USB wing (33 × 81 mm) to the trim right of it: check the passenger side for a vent, the glovebox or a knee, and that you can plug cables into both sockets.
- **Piezo through the slots:** assembled, with the fan running, play the danger and TPMS patterns: both must be clearly heard over road noise with the windows up. If not, regenerate with `BUZ_GAP=1` (face 1 mm off the skin) or buy a louder (≥ 90 dB at 10 cm) part of the same size.

## Mirror cameras and door LEDs

[`make_mounts.py`](make_mounts.py) (same rules as `make_enclosure.py`) makes the printed parts that live outside the dash unit. In the viewer: **3. Printed Parts & Assembly → Mirror cameras / Door LEDs**, with the camera's view and each LED's aim drawn.

```
python 01-hardware/enclosure/make_mounts.py                                        # STLs + report + 28 checks
python 01-hardware/enclosure/make_mounts.py --set CAM_D=20.5 CAM_BODY_L=34 CAP_PITCH=6
```

It writes the `print_cam_*`, `print_led_*` and `asm_cam_*` / `asm_led_*` STLs and [mounts_report.json](mounts_report.json) (aims, sizes, the cap holes, where each part sits in the car, every check), and exits with an error if a check fails. The checks:

- every part is a closed solid, fits a 220 × 220 mm bed and prints without supports;
- the camera and its cable clear the pod; as mounted (cap slope included) it aims 39° outward of straight back and 10° down; nothing of the pod is in front of the lens;
- at least 2.7 mm of plastic round the bore and the cable channel; two M3 pilots in solid plastic; the channel passes the USB plug and climbs at ≥ 45°; the pod hangs ≤ 45 mm below the cap;
- each LED clears its bore, aims at the driver's eyes within 1° and puts no direct light on the side window or the windscreen.

| File | Print | What it does |
|---|---|---|
| `print_cam_pod_left.stl`, `print_cam_pod_right.stl` | Cap face down | 45.7 × 50.3 × 33.2 mm, mirror images. Hangs under the mirror cap's outer half and sets the aim the audit worked out ([CAM-02](../../05-Audit-Subsystems/08-cameras-and-vision.md)): 39° outward of straight back, 10° down. The camera's body sits in a teardrop bore (it prints without support and drains rearward), its lip on the pod's rear face. That face is the pod's rearmost plane, so nothing of the pod can be in the picture. A set screw and a bead of neutral-cure RTV hold the camera. The lead climbs a Ø18 mm channel at 60° into the cap: only the cable goes into the mirror. The flat side faces the car |
| `print_cam_drill_guide.stl` | Flat | 1.6 mm template for the three holes in each cap: the arrow points rearward, the flat side faces the car. Flip it over for the left mirror |
| `print_led_pod_left.stl`, `print_led_pod_right.stl` | Base down | 20.6 × 18 × 14.1 and 15.3 × 16.8 × 13.6 mm. The 5 mm amber LED, aimed at the driver's eyes (left 46°, right 20° off the sail) and 3 mm deep: no direct light on the side window (no amber reflection next to the mirror at night) or the windscreen |

### Fitting a camera pod

1. Buy the camera only after the V4 bench test passes ([premortem](../../00-project-management/PREMORTEM_v2.md)). Measure it and regenerate (table below).
2. Take the mirror cap off, or look inside with a light, and mark the turn repeater and its wires before drilling ([VEH-06](../../05-Audit-Subsystems/12-vehicle-integration.md)). Practise on a spare cap.
3. Tape the drill guide under the cap's outer half (arrow rearward, flat side toward the car, its rear edge on the cap's rear edge). Drill 2 × Ø3.4 mm and a pilot for the cable hole, then open that to **Ø21 mm** with a step drill. A spliced lead needs only ~Ø10 mm: regenerate with `PLUG_PASS_D=8`.
4. Feed the camera's plug in at the pod's lens face, up the channel and through the cap, then through the mirror's hinge with a service loop and into the door.
5. Push the camera in until its lip seats. Set screw (M3 × 6), then a bead of RTV round the lip.
6. 3M 5952 VHB on the pod's top face; 2 × M3 × 12 pan head from inside the mirror into the pilots. Seal the cap hole round the cable with RTV.
7. Check the picture with cones at the zone's four corners: a strip of the car's side stays at the inner edge (it tells the Pi the mirror hasn't been folded or knocked).

### Fitting an LED pod

- On the inner door sail (the triangular trim inside the door, under the mirror). Not on the A-pillar trim (curtain airbag) and not outside the mirror ([premortem C7](../../00-project-management/PREMORTEM_v2.md)).
- Clean the trim with IPA, then VHB. Drill a Ø4 mm hole through the trim under the pod for the two wires, after checking that no speaker or window regulator sits right behind it.
- Push the LED in from the back until its flange sits on the shoulder; a dab of RTV. The 24 AWG pair runs inside the door card to the door boot, with the camera lead.

### Measure (then `--set`)

| Parameter | Default | Measure |
|---|---|---|
| `CAM_D`, `CAM_LIP_D`, `CAM_LIP_T` | 19, 24, 3 | The camera's round body, its front lip, and how far lip and lens stand in front of the face |
| `CAM_BODY_L` | 30 | Back of the lip to the end of the cable's strain relief |
| `PLUG_PASS_D` | 18 | What the channel and the cap hole must pass: a moulded USB-A plug is ~16 × 8 mm. 8 if you splice the lead |
| `CAP_PITCH`, `CAP_ROLL` | 0, 0 | Slope of the cap's underside where the pod goes, in degrees (front edge up +, outer edge up +). The pod's top follows it; the aim stays 39° / 10° |
| `SAIL_YAW`, `SAIL_LEAN` | 25, 10 | The sail's face turned toward the rear from facing straight across the car, and its top leaning inward |
| `LED_L` | 8.6 | Your LED: dome tip to the back of its flange |
| `EYE`, `LED_AT_L`, `LED_AT_R` | viewer car model | Your eye point and the two LED spots in metres (x right, y forward, z up from the road), if the aim looks off |

Hardware for both sides: 4 × M3 × 12 pan head, 2 × M3 × 6 set screws, 3M 5952 VHB, neutral-cure (oxime) RTV, 2 × 5 mm amber LEDs.

## PCB keep-outs for the layout (gate G7)

From `enclosure_report.json`.

| Rule | Value |
|---|---|
| Part height | ≤ 16 mm above the board. Connectors right-angle at the edges, so mated plugs stay under 16 mm |
| Pins under the board | ≤ 2.5 mm |
| Fan zone | 32 × 32 mm centred at (45, 46) mm from the top-left (parts side up): parts ≤ 6 mm |
| SMA strip | 14 × 12 mm on the right edge (away from the Pi's ports), centred 34.5 mm below the top edge: no parts |
| Corners | 10 × 10 mm round each mounting hole: no through-hole pins (posts and ribs underneath) |

The fit template ([v2_fit_template_1to1.pdf](../docs/v2_fit_template_1to1.pdf), page 2) draws these with the planned part zones.
