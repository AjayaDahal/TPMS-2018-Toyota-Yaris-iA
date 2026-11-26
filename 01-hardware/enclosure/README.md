# v2 enclosure (3-D printed)

One printed unit holds:
- the **SunFounder TS-7 7" HDMI touch display** (1024 × 600 IPS, the one in the inventory);
- the **Raspberry Pi 4** on four posts behind it;
- the **100 × 100 mm carrier PCB** behind the Pi.

A small wired **alert pod** carries the mute button and the buzzer. The rotary encoder, the menu buttons, the 2.7" OLED and the four tyre LEDs from the v1 panel aren't used in v2: the touch screen does menus, settings, TPMS pairing and camera calibration.

```
python 01-hardware/enclosure/make_enclosure.py                                     # STLs + report + 43 checks
python 01-hardware/enclosure/make_enclosure.py --set MOD_H=124.6 HDMI_Y=23.5       # your measurements
python 01-hardware/enclosure/make_enclosure.py --set HDMI_PLUG=22,21,6.5           # tuples as comma lists
python 01-hardware/scripts/make_v2_fit_template.py                                 # then redraw the 1:1 template
```

Needs `pip install manifold3d numpy`. It writes:

- `stl/print_*.stl`: the five parts in print orientation, flat face on the bed, no supports.
- `stl/asm_*.stl`: the assembly with dummies of the display, its plugs, the Pi, the PCB and the fan, used by the [viewer](../../04-viewer/README.md).
- [enclosure_report.json](enclosure_report.json): dimensions, Z levels, PCB keep-outs, hardware, the front-view outlines the [fit template](../docs/v2_fit_template_1to1.pdf) draws, and every check.

The script exits with an error if a check fails. The checks cover:

- every part is a closed solid and fits a 220 × 220 mm bed;
- no clash between any part and the display, its HDMI and micro-USB plugs and their leads, the Pi (with its 90° plugs and SD card), the PCB, its part-height budget, the fan, the SMA bulkhead or the bezel screw heads;
- the display hangs on four bosses that touch only its ears;
- the bezel's lip covers the glass edge but clears the active area;
- the plugs fit inside the bezel;
- the PCB posts are on 92 × 92 mm, the Pi posts on 58 × 49 mm, and the Pi-to-PCB air gap holds;
- every vent is finger-safe;
- the box, its ears, the 90° USB plugs, the display leads and the antenna lead fit the console opening;
- the plate's cable slot opens into the pocket;
- the bezel stays below the HVAC panel.

> **Measure the display first.** SunFounder publishes no drawing. Its table says the module is 165.30 × 121.00 × 7.75 mm, but four of its product photos give a board about **124.4 mm** tall over the ears, which is what the defaults use. The ear holes, socket positions and the height of the parts on the back are taken from photos. Lay the display on page 1 of the [fit template](../docs/v2_fit_template_1to1.pdf), measure the values in [Measure first](#measure-first-then---set), regenerate, then print.

## Result (default parameters)

| | |
|---|---|
| Overall | 205.6 × 129.0 × 70.3 mm (bezel front to lid), as tall as the console opening |
| In front of the trim | 21.8 mm (bezel front to the back of the plate, plus the 2 mm bumps). The official display's design stood 13 mm proud: check the shifter in P with the mock-up |
| Rear box | 112 × 124 mm (126 mm wide at the lid ears), 50.5 mm behind the plate |
| Console pocket (Option A) | needs **≥ 56 mm of clear depth** behind the trim. It fits the 191 / 123 × 129 mm opening with 3.0 mm to spare at the tightest point |
| Screen | 8 mm left of centre (toward the driver): the HDMI and micro-USB plugs need the room on its right |
| Plastic | ~241 cm³ solid (bezel 48, housing 139, lid 35, pod 19): under one 1 kg spool |

## Parts

| File | Print | What it does |
|---|---|---|
| `print_bezel.stl` | Face down | Front frame. The display **hangs by its four corner ears on four bosses** in the bezel (M3 × 6 from behind), so its glass carries no load and sits 0.3 mm behind the lip. The lip covers only the outer 2 mm of the glass; the glass's own black border does the rest. Behind the frame, a cavity on each side of the screen: the left one and the lower right one have **intake slots**, 2.5 mm wide; the upper right one holds the plugs. Walls are only 2 mm top and bottom, so the frame is no taller than the opening |
| `print_housing.stl` | Plate (front) down | The **plate** behind the display, 0.4 mm clear of the parts on its back. It carries the bezel (6 × M3 × 10 from behind), three intake windows, and the **cable slot** where the display's leads go back into the pocket. Behind it, the **box**:<br>• the Pi on four posts and the PCB on four more;<br>• the window for the Pi's USB/Ethernet;<br>• the slot above it where the display leads come in;<br>• an SMA bulkhead hole;<br>• an AMPS 30 × 38 pattern with captive M4 nuts in the bottom wall;<br>• 2 mm bumps on the back of the plate. |
| `print_lid.stl` | Outside down | The 30 mm fan from the black Pi case sits under a finger-safe grille and blows **out**. Also a 22 × 8 mm cable exit (fit a split grommet) and a locating rim |
| `print_pod_shell.stl`, `print_pod_base.stl` | Top down / flat | Alert pod: the inventory panel-mount pushbutton (mute) and a 12 V active piezo behind a grille. VHB tape plus 2 × M3, one 4-wire lead to the PCB |

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

  Both rise to the plate's cable slot (9 × 20 mm, inside the opening's outline), pass into the pocket beside the box, and enter the box through the slot above the USB window. There the flat cable ends in a straight micro-HDMI adapter in the Pi's **HDMI0** (next to USB-C), folded toward the slot.
- **Display power and touch on one split lead.** The TS-7 takes 5 V (0.48 A typical) and its touch data on the same micro-USB. Powered from a Pi USB port, the display plus two cameras would come close to the 1.2 A the Pi shares between all four ports ([DSP-03](../../05-Audit-Subsystems/09-display-and-ui.md)). So the lead splits behind the plate:
  - **5 V and GND** go to **J5's second pair** on the carrier (the 5V_PI rail);
  - **D+, D− and GND** go to a 90° USB-A plug in one of the Pi's blue USB 3.0 ports, through the window.

  Cut the red (VBUS) wire on the Pi's leg: the two 5 V sources must not be joined. SunFounder asks for USB power before HDMI, and one rail powering both does exactly that.
- **Airflow.** Cabin air enters through the bezel's slots (771 mm², 2.5 mm wide), flows behind the display (cooling its scaler chip), through the plate's three windows, past the Pi and round the PCB, and leaves through the lid fan.
  - Option A (box in the console pocket): the 2 mm bumps hold the plate off the trim, so the air leaves round the edge of the frame. Don't seal that gap or the pocket.
  - Option B (dash top): the box is in free air.
- **Controls.** Touch does everything except mute. The physical button stays because:
  - it works while the Pi is booting or has crashed: the ESP32 still beeps for low tyres;
  - it can be found without looking.

  It is in a **pod near the shifter**, not in the bezel: the inventory button's threaded body (~20 mm) and a sharp-tone piezo don't fit a bezel that must stay inside the 129 mm opening height.
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
| `BUTTON_D` | 12.2 | Thread of the inventory panel-mount pushbutton (+0.2) |
| `POD_BUZ_D`, `POD_BUZ_H` | 23.2, 12 | The 12 V active piezo you buy |
| Pocket | ≥ 56 mm | Clear depth behind the trim where the box goes (Option A), and where the car's USB / 12 V strip is. It sits behind the panel, ~34 mm below the top of the opening (v1 `panel_config.py`), right in front of the box |
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
| Pod | 2 × M3 × 8, VHB tape |
| Buy | **HDMI FPC kit:** a straight HDMI-A male adapter, a straight micro-HDMI male adapter and a 20 cm flat cable (the kit's 1 m HDMI to micro-HDMI cable is far too stiff for the box). **A 90° micro-USB lead** whose cable leaves along the plug's wide face ("left" or "right" angle, not up/down). Which of the two points upward depends on how the socket is mounted: check the display first, or buy both. Split it as described above. Also:<br>• a split rubber grommet for the cable exit;<br>• an SMA bulkhead to SMA pigtail (RG316, ~10 cm) plus a 30 cm RG316 extension;<br>• three 90° USB-A adapters or plugs (two cameras, touch);<br>• 90° Dupont housings;<br>• a 90° USB-C plug on the power pigtail. |

## Assembly

1. **Pi:** screw it onto its four posts in the housing (M2.5 × 6), ports into the window. Fit:
   - the micro-HDMI adapter in HDMI0 (the one next to USB-C);
   - the 90° USB-C pigtail;
   - the UART lead (90° Dupont on GPIO 14/15 + GND).
2. **Display:** lay the bezel face down on a soft cloth and put the display face down into it. Screw it to the four bosses through its ears (4 × M3 × 6). Plug in the HDMI adapter (fold its flat cable up over the adapter) and the 90° micro-USB plug (lead upward), and lay both leads up the bezel's right cavity.
3. **Close the front:** thread both leads through the plate's cable slot, set the housing on the bezel and screw it on from behind (6 × M3 × 10).
4. **Display leads:** behind the plate, feed the flat cable and the power leg into the box through the slot above the USB window. Click the flat cable into the micro-HDMI adapter. Plug the lead's USB-A leg into a blue USB 3.0 port through the window.
5. **PCB:** fit it on its posts, parts facing you. Connect:
   - the USB-C pigtail to J5 pair 1;
   - the display power leg to J5 pair 2;
   - the UART lead;
   - the RG316 pigtail from the CC1101 to the bulkhead;
   - the fan to the PCB's 5 V header.
6. **Lid:** feed the harness (12 V, blinkers, LEDs, GPS, alert pod) through the lid's cable exit with a grommet and plug it in. Close the lid (4 × M3 × 12).
7. **In the car:** the camera USB plugs go into the Pi's black USB 2.0 ports through the window, with 90° adapters when the box sits in the pocket.

## Before trusting it in the car

- **Display on the bench:** Raspberry Pi OS (Bookworm) finds the TS-7 on HDMI-A-1 at 1024 × 600 by itself. If the screen stays black, add `video=HDMI-A-1:1024x600@60` to `cmdline.txt`. SunFounder documents no brightness control: try `ddcutil detect` (DDC/CI over HDMI). If it answers, the Pi can dim the backlight at night; if not, use a dark UI at night ([DSP-04](../../05-Audit-Subsystems/09-display-and-ui.md)).
- **Thermal test T1:** a sun-soaked car, the vision app running, 30 minutes. Pass = `vcgencmd measure_temp` below 80 °C and `vcgencmd get_throttled` = `0x0`. If it fails:
  - lower the Pi's clock;
  - open the gap round the plate;
  - or move the PCB to its own vented box (the posts and the 92 × 92 pattern stay the same).
- **Mock-up first:** a foam block of the box size behind the template's bezel outline (fit template, note 3) answers the pocket-depth and shifter-clearance questions for free.

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
