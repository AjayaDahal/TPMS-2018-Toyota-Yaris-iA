# v2 enclosure (3-D printed)

One printed unit holds the **Official Raspberry Pi 7" Touch Display**, the **Raspberry Pi 4** on its back, and the **100 × 100 mm carrier PCB** behind the Pi. A small wired **alert pod** carries the mute button and the buzzer. The rotary encoder, the menu buttons, the 2.7" OLED and the four tyre LEDs from the v1 panel are not used in v2: the touch screen does menus, settings, TPMS pairing and camera calibration.

```
python 01-hardware/enclosure/make_enclosure.py                       # STLs + report + 38 checks
python 01-hardware/enclosure/make_enclosure.py --mount normal        # cable edge down (e.g. dash top)
python 01-hardware/enclosure/make_enclosure.py --set PI_SEAT=21.5 BUTTON_D=16.2   # your measurements
```

Needs `pip install manifold3d numpy`. It writes:

- `stl/print_*.stl`: the five parts in print orientation, flat face on the bed, no supports.
- `stl/asm_*.stl`: the assembly with dummies of the display, Pi, PCB and fan, used by the [viewer](../../04-viewer/README.md).
- [enclosure_report.json](enclosure_report.json): dimensions, Z levels, PCB keep-outs, hardware and every check.

The script exits with an error if a check fails. The checks cover:

- every part is a closed solid and fits a 220 × 220 mm bed;
- no clash between any part and the display, the Pi (with its adapter board, ribbons, jumpers and a 90° USB-C plug), the PCB, its part-height budget, the fan or the SMA bulkhead;
- the display's M3 pattern matches the drawing and its screws stay reachable;
- the PCB posts are on 92 × 92 mm;
- the Pi-to-PCB air gap holds and every vent is finger-safe;
- the box, its ears, 90° USB plugs and the antenna lead fit the console opening, and the bezel is no taller than the opening.

## Result (default parameters)

| | |
|---|---|
| Overall | 205.6 × 127.9 × 71.8 mm (bezel front to lid) |
| Rear box | 112 × 120 mm (126 mm wide at the lid ears), 60.5 mm behind the plate |
| Console pocket (Option A) | needs **≥ 66 mm of clear depth** behind the trim. It fits the 191 / 123 × 129 mm opening with 1.3 mm to spare at the tightest point |
| Plastic | ~225 cm³ solid (bezel 46, housing 127, lid 34, pod 19): well under one 1 kg spool |

## Parts

| File | Print | What it does |
|---|---|---|
| `print_bezel.stl` | Face down | Front frame. 2 mm lip over the glass's black border, 0.3 mm clear of the glass, so it never presses on the touch panel. A 10 mm **chin** below the glass with 20 air-intake slots, 2.5 mm wide. 6 × M3 into the side walls and the chin |
| `print_housing.stl` | Plate (front) down | The display screws to the **plate** through its own 4 × M3 holes; the glass carries no load. The rear **box** holds the Pi on the display's standoffs and the PCB on 4 posts. It has a window for the Pi's USB/Ethernet, an SMA bulkhead hole, an AMPS 30 × 38 pattern with captive M4 nuts in the bottom wall, and 2 mm bumps on the back of the plate |
| `print_lid.stl` | Outside down | The 30 mm fan from the black Pi case sits under a finger-safe grille and blows **out**. Also a 22 × 8 mm cable exit (fit a split grommet) and a locating rim |
| `print_pod_shell.stl`, `print_pod_base.stl` | Top down / flat | Alert pod: the inventory panel-mount pushbutton (mute) and a 12 V active piezo behind a grille. VHB tape plus 2 × M3, one 4-wire lead to the PCB |

### Why it is built this way

- **Stack.** Glass (0 mm), then the display module back (−5.96), the plate, the Pi seat (−24.0), the Pi's tallest part (−42.4), a 3 mm air gap, the PCB (−47.9 / −49.5), its 16 mm part budget, and the lid (−69.5). The PCB's flat underside faces the Pi, its parts face the lid, so taking the lid off shows every connector.
- **Mounted upside down** (cable edge up, `MOUNT=inverted`). The drawing gives a 6 o'clock viewing direction, and the docs give 50° from the top vs 70° from the bottom. In the console you look down at the screen, so turn it over and rotate the image 180°: Screen Configuration → Orientation → Inverted, plus `dtoverlay=vc4-kms-dsi-7inch,invx,invy` for touch. Test both ways on the bench. The Pi's ports then face the driver's right.
- **Airflow.** Cabin air enters at the chin, flows past the Pi and around the PCB edges (3.5 mm gaps, 11 mm at the bottom), and leaves through the lid fan.
  - Option A (box in the console pocket): the bumps hold the plate 2 mm off the trim, so the air can escape round the edge of the bezel. Don't seal that gap or the pocket.
  - Option B (dash top): the box is in free air.
- **Controls.** Touch does everything except mute. The physical button stays because:
  - it works while the Pi is booting or has crashed: the ESP32 still beeps for low tyres;
  - it can be found without looking.

  It is in a **pod near the shifter**, not in the bezel. The inventory button's threaded body (~20 mm) and a sharp-tone piezo don't fit a bezel that must stay inside the 129 mm opening height. A beep from the console, close to the driver, is clearly audible.
- **Display warning.** The Raspberry Pi docs require an enclosure that keeps the circuit boards unreachable, vents included. Hence 2.5 mm slots, the bar grille on the fan and a grommet in the cable exit.

## Measure first (then `--set`)

| Parameter | Default | Measure |
|---|---|---|
| `PI_SEAT` | 24.0 | From the glass front to the top of the display's standoffs, where the Pi's board sits. Not in any drawing; estimated from the docs photo |
| `PI_TOP_H` | 17.0 | Tallest part above the Pi's board. The GPIO plugs (display power jumpers, UART to the PCB) must be **90° or low-profile** Dupont: straight ones stand ~22 mm tall |
| Pi orientation | ports to the right, seen from behind | Check on your display. The docs photo and the adapter's connector positions say this way, and the box is built for it. `--set PI_ROT180=1` models a Pi turned round: the box then moves ~13 mm sideways, blocks a display M3 screw and no longer fits the opening (2 checks fail). So mount the Pi the documented way |
| `BUTTON_D` | 12.2 | Thread of the inventory panel-mount pushbutton (+0.2) |
| `POD_BUZ_D`, `POD_BUZ_H` | 23.2, 12 | The 12 V active piezo you buy |
| Display M3 depth | M3 × 6 | Depth of the threads in the display's frame. A screw that bottoms out can press on the panel |
| Pocket | ≥ 66 mm | Clear depth behind the trim where the box goes (Option A), and where the car's USB / 12 V strip is. It sits behind the panel, ~34 mm below the top of the opening (v1 `panel_config.py`), right in front of the box |
| Fan | 30 × 30 × 10, holes 24 mm | Your fan's thickness and hole spacing |

## Material and print settings

- **ASA** (best: UV-stable, softens ~95 °C) or **ABS**, both in an enclosed printer. **PETG** only for a shaded console mount.
- **Never PLA:** it softens at ~55–60 °C, and a parked car's cabin reaches 60–80 °C, the dash top more.
- No printer that does ASA? Order the parts in **MJF PA12** (e.g. JLC3DP) with the PCB.
- 0.2 mm layers, 4 perimeters, 30–40 % gyroid, brim for ASA/ABS, no supports. The bezel and the housing need a bed of at least 210 × 135 mm.
- Print the **bezel first** (thin, ~2 h) and test-fit the display before spending ~10 h on the housing.

## Hardware

| Joint | Parts |
|---|---|
| Display → plate | 4 × M3 × 6 button head (VIGRUE kit) |
| Bezel → plate | 6 × M3 × 10 into 2.6 mm pilots, don't overtighten |
| Lid → box | 4 × M3 × 12 into the ears |
| PCB → posts | 4 × M3 × 6 |
| Fan → lid | 4 × M3 × 16 + nuts, label facing out (blowing out) |
| AMPS mount | 4 × M4 nuts pressed into the bottom bosses + M4 × 10 (Fgruh kit). Fits a RAM-B-202U round base or a car bracket |
| Pod | 2 × M3 × 8, VHB tape |
| Buy | Split rubber grommet for the cable exit; SMA bulkhead to SMA pigtail (RG316, ~10 cm) plus a 30 cm RG316 extension; two 90° USB-A adapters for the camera plugs; 90° Dupont housings; a 90° USB-C plug on the power pigtail |

## Assembly

1. Screw the Pi to the display's standoffs (supplied M2.5). Connect the DSI ribbon and the display power jumpers with 90° housings.
2. Lay the display face down. Place the housing over it and screw it on through the plate with 4 × M3 × 6. Check that the flat cable sits in its relief.
3. Fit the bezel from the front (6 × M3 × 10 from the back of the plate).
4. Fit the PCB on the posts, parts facing you. Then connect:
   - the 90° USB-C pigtail from J5 to the Pi;
   - the UART lead to the Pi's GPIO 14/15;
   - the RG316 pigtail from the CC1101 to the bulkhead;
   - the fan to the PCB's 5 V header.
5. Feed the harness (12 V, blinkers, LEDs, GPS, alert pod) through the lid's cable exit with a grommet and plug it in. Close the lid (4 × M3 × 12).
6. Camera USB plugs go into the Pi through the window, with 90° adapters if the box sits in the pocket.

## Before trusting it in the car

- **Thermal test T1:** a sun-soaked car, the vision app running, 30 minutes. Pass = `vcgencmd measure_temp` below 80 °C and `vcgencmd get_throttled` = `0x0`. If it fails:
  - lower the Pi's clock;
  - open the gap round the plate;
  - or move the PCB to its own vented box (the posts and the 92 × 92 pattern stay the same).
- **Mock-up first:** a foam block of the box size (fit template note 1) answers the pocket-depth and shifter-clearance questions for free.

## PCB keep-outs for the layout (gate G7)

From `enclosure_report.json`, for the default mount. With `--mount normal` the left and right sides swap.

| Rule | Value |
|---|---|
| Part height | ≤ 16 mm above the board. Connectors right-angle at the edges, so mated plugs stay under 16 mm |
| Pins under the board | ≤ 2.5 mm |
| Fan zone | 32 × 32 mm centred at (45, 46) mm from the top-left (parts side up): parts ≤ 6 mm |
| SMA strip | 14 × 12 mm on the right edge (away from the Pi's ports), centred 34.5 mm below the top edge: no parts |
| Corners | 10 × 10 mm round each mounting hole: no through-hole pins (posts and ribs underneath) |

The fit template ([v2_fit_template_1to1.pdf](../docs/v2_fit_template_1to1.pdf), page 2) draws these with the planned part zones.
