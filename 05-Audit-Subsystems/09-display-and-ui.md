# 09 · Display and UI (v2)

**Scope:** the 7" touch display, its orientation, touch input, brightness and temperature limits, and the screen the Pi shows (tyre tiles, camera view on the blinker).

**Maturity:** decided: the design now uses the **SunFounder TS-7** you have. The enclosure, the 1:1 template, the power budget, the harness, the BOM, the premortem and the viewer were redrawn for it after this audit. Its dimensions come from SunFounder's tables and product photos (there is no drawing); nothing is printed yet. The UI exists only as the [viewer's](../04-viewer/README.md) HUD mock-up; the Pi app is not written.

**Verdict: Watch.** The display decision (DSP-01, the audit's top risk) is made and designed in. What is left: measure the TS-7 before printing (DSP-10), and on the bench check cold starts (DSP-11) and whether the backlight can be dimmed (DSP-04).

## The two displays

| | Official Raspberry Pi 7" (the first design; dropped) | SunFounder TS-7 "7-Inch DIY Touchscreen" (in your inventory; the design now uses it) |
|---|---|---|
| Source | Raspberry Pi docs, product brief, drawing `SPF-SH800480T026-IAC02` | [SunFounder TS-7 parameters](https://docs.sunfounder.com/projects/ts-7/en/latest/parameters.html), [assembly](https://docs.sunfounder.com/projects/ts-7/en/latest/assembly_instructions.html), [store page](https://www.sunfounder.com/products/7inch-ips-touchscreen), four product photos measured |
| In the inventory | Only the **adapter board** ("Touch Display Adapter v1.1"); the LCD glass, touch panel and ribbons are not listed | Retail box (`disp-sunfounder-7in`, photo `PXL_20261126_001454617`) |
| Video / touch | DSI ribbon / I²C over the DSI connector | **HDMI** (a 20 cm HDMI flat-cable kit to the Pi's HDMI0; the kit's stiff cables aren't used) / **USB** (micro-USB, which also powers it) |
| Panel | 800 × 480, TN, 6 o'clock viewing (docs: 50° from the top, 70° from the bottom) | **1024 × 600 IPS**, viewing direction "All", 170° |
| Size | Glass 192.96 × 110.76 mm; frame M3 pattern 126.2 × 65.65 mm | Module **165.30 × 121.00 × 7.75 mm** listed, but the photos give **~124.4 mm** over its 4 mounting ears (DSP-10); ear holes ~157.3 × 114.4 mm apart (photos); active area 154.2 × 85.9 mm; a blue driver board; HDMI and micro-USB sockets on its back at the right edge |
| Pi mounting | On the display's own standoffs | None: the Pi sits on its own 4 posts in the housing (the kit's brass standoffs are desk feet) |
| Power | ~0.2 A at 5 V | **0.48 A typical** at 5 V over the micro-USB: from J5 pair 2 on a split lead (DSP-03) |
| Temperature | Product brief 0–50 °C; docs −20…+70 °C operating | Operating −10…+60 °C, storage −20…+70 °C |
| Brightness | 250 cd/m², 500:1 | 250 cd/m² (store page); contrast not given; no documented dimming (DSP-04) |

## What was verified

| Check | Evidence | Result |
|---|---|---|
| Which display the design uses | [make_enclosure.py](../01-hardware/enclosure/make_enclosure.py) (63 checks), the [v2 fit template](../01-hardware/docs/v2_fit_template_1to1.pdf) (page 1 drawn from the enclosure report), [PREMORTEM_v2](../00-project-management/PREMORTEM_v2.md) C12/C13/C17/C18 and D1–D9, the power budget, the BOM and the viewer | TS-7 (since the redesign) |
| Which display is on hand | Live inventory: `disp-sunfounder-7in`; the official display appears only as its adapter board (`disp-rpiadapter`); you confirmed the TS-7 | TS-7 |
| Official display facts | Earlier pass (C17, C18): M3 positions dimensioned from the frame flange, 250 cd/m², viewing angles, temperature ratings | No longer used |
| TS-7 facts | SunFounder's parameter tables (size, active area, 480 mA, temperatures), its store page (250 cd/m², 170°), its docs ("connect the USB first, then the HDMI"), and four product photos (width / height 1.324–1.332 for the 165.3 mm board, ear holes, sockets, the LCD flex) | As in the table; the listed height disagrees with the photos (DSP-10) |

## Findings

| # | Severity | Finding | Fix | Status |
|---|---|---|---|---|
| DSP-01 | High | **The design was for a display you may not have.** Built for the official display: the enclosure (bezel, plate, Pi seat on the display's standoffs), the 1:1 template, power budget, B7 rotation commands and the viewer's models. The display physically on hand is the TS-7, and the official display's LCD has never been confirmed (G3) | **Decided: the TS-7.** The enclosure (Pi on its own posts, HDMI and USB cabling, no chin), the template, the power budget, the harness, the BOM, the premortem and the viewer are redrawn for it | **Fixed (TS-7 redesign)** |
| DSP-02 | High (TS-7) | **It's tall for the opening.** The TS-7 board is 121.0 mm tall by SunFounder's table and ~124.4 mm by its photos, against the 129 mm console opening: the 10 mm air-intake chin couldn't stay | 2 mm top and bottom walls; intake slots beside the screen instead of the chin. With the photos' 124.4 mm the bezel is 129.0 mm, the opening's full height (checked by the generator); the real height is DSP-10 | **Fixed (TS-7 redesign)**; height: DSP-10 |
| DSP-03 | Medium (TS-7) | **Power through the Pi's USB.** The TS-7 takes 0.48 A typ over its micro-USB. Together with two cameras (~0.5–0.7 A) that approaches the Pi 4's 1.2 A limit shared by all its USB ports ([PI-03](06-raspberry-pi.md)): camera resets and USB brown-outs | A split micro-USB lead: 5 V + GND from `5V_PI` (J5 pair 2), only D+ / D− + GND to a Pi USB port, the red wire cut on that leg. Check with a meter that the two legs' 5 V aren't joined | **Fixed (TS-7 redesign)** + You (B7) |
| DSP-04 | Medium (TS-7) | **No documented brightness control.** SunFounder documents no backlight control. Its FAQ mentions "brightness and contrast under the Color menu", which suggests an on-screen menu, but neither the docs nor the photos show how to open it, and a menu is manual anyway. The official display's backlight is software-dimmable; the plan's night dimming (D4) relied on that | Look for menu buttons on the board. Try DDC/CI over the HDMI on the bench: `ddcutil detect`, then `ddcutil setvcp 10 <0–100>`. Monitor scalers often answer DDC/CI; this board's (a Realtek RTD2513A, from the photos) is untested. If it doesn't: a dark UI at night and a fixed backlight, or dim it in hardware (rework) | Open (bench, B7) |
| DSP-05 | Low (TS-7) | **HDMI cabling in a small box.** Full-size HDMI and micro-HDMI plugs are stiff, unlatched and need a large bend radius | An HDMI flat-cable kit: a straight HDMI-A adapter in the display, a 20 cm flat cable folded once inside the bezel, a straight micro-HDMI adapter in the Pi; a 90° micro-USB plug. The generator checks that the plugs fit inside the bezel. Strain relief and RTV ([M14](../00-project-management/PREMORTEM_v2.md#mechanical-and-installation)) | **Fixed (TS-7 redesign)** + You (assembly) |
| DSP-06 | Medium | **Daylight readability.** The TS-7 gives 250 cd/m², like the official display: it washes out in direct sun | Shaded console mount (Option A); high-contrast UI; full backlight by day; test the mock-up in the sun (G5) | Open (you, G5) |
| DSP-07 | Medium | **The display isn't automotive-rated.** TS-7: −10…+60 °C operating, −20…+70 °C storage (the official display: 0–50 °C in its product brief). A car parked in summer exceeds these on the dash top, and in hot climates possibly in the console ([16-safety](16-safety-and-legal.md)) | Option A only; sunshade; expect a shorter life; keep a spare. The Pi's hot-start hold protects the Pi, not the display's storage rating | Accepted (risk) |
| DSP-08 | Low | **The upside-down mount was only for the official display.** It compensated the official panel's 6 o'clock viewing; an IPS panel doesn't need it | The TS-7 is mounted the normal way up, no rotation; the generator's `--mount` option is gone | **Fixed (TS-7 redesign)** |
| DSP-09 | Medium | **The UI doesn't exist yet.** Rules it must follow are spread over the premortem (D5, V8, S3): nothing needs touch while moving; camera view only on blinker or danger; a visible "blind-spot assist unavailable" state; works at reduced frame rate when the Pi throttles | Collect these into a short UI spec before writing the Pi app, at 1024 × 600 | Open (plan) |
| DSP-10 | Medium (TS-7) | **SunFounder's height disagrees with its photos.** Its table says 121.0 mm; four product photos give 124.1–124.8 mm over the ears (width / height 1.324–1.332 for the 165.3 mm board, like the generic 7" HDMI boards). The ear holes, the sockets, the parts on the back and the plugs are photo estimates too. The enclosure uses 124.4 mm, so the bezel fills the opening's height: a board taller than ~124.9 mm, or ear holes more than ~0.3 mm off the bosses, won't fit | Measure before printing ([enclosure README, Measure first](../01-hardware/enclosure/README.md#measure-first-then---set)); lay the display on the template's page 1; `--set` and regenerate; print the bezel alone first (G6) | Open (you, G6) |
| DSP-11 | Medium (TS-7) | **Black screen after a cold start.** SunFounder asks for USB power before HDMI. If the Pi reads the display before its scaler answers, the desktop can come up with no HDMI output, or the touch may not enumerate; in a car that happens at every start | One 5 V rail powers both, so the display is never later than the Pi. B7 cold-starts it 10 times; if one fails: `video=HDMI-A-1:1024x600@60D` in `cmdline.txt` forces the output on ([D9](../00-project-management/PREMORTEM_v2.md#display-and-driver-interface)) | Open (bench, B7) |

## Premortem: the display failed. Why?

| # | How it fails | Likely | Impact | Prevention / detection | Status |
|---|---|---|---|---|---|
| DSP-P1 | The enclosure is printed from the photo estimates and the real TS-7 doesn't fit: holes off, board taller | Medium until DSP-10 | ~12 h of printing wasted | Measure first (DSP-10); print the bezel alone as a fit test (G6) | Open |
| DSP-P2 | The screen is unreadable at noon and glaring at night | Medium | The camera view is useless when needed | DSP-04, DSP-06; test in the car by day and night | Open |
| DSP-P3 | The panel fails after a summer of parking (bubbles, dead backlight, delamination) | Medium | Display replaced | DSP-07; shaded mount; sunshade | Accepted |
| DSP-P4 | Touch lands in the wrong place, or ghost touches with the cameras streaming | Low | Confusing UI | No rotation (IPS); B7 taps the four corners with the cameras running | Open (bench) |
| DSP-P5 | The driver pokes the screen at speed | Medium | Distraction | DSP-09: nothing needs touch while moving; mute is the physical button | Fixed (design) + Open (UI) |
| DSP-P6 | The bezel presses on the glass: phantom touches or a crack | Low | Glass replaced | The display hangs on its ears; the lip is 0.3 mm in front of the glass, over its outer 2 mm only, ≥ 1.8 mm outside the active area | Fixed (TS-7 redesign) + You (after assembly) |
| DSP-P7 | The HDMI flat cable or a plug works loose on rough roads: black screen | Medium | Camera view lost | DSP-05; one fold, Kapton over the latches, RTV, the leads tied at the plate's slot ([M14](../00-project-management/PREMORTEM_v2.md#mechanical-and-installation)) | Fixed (procedure) + You |
| DSP-P8 | The display's USB load plus the cameras trips the Pi's USB current limit | Was Medium | Cameras reset | DSP-03: the display takes its 5 V from J5 | Fixed (TS-7 redesign) |
| DSP-P9 | Some mornings the screen stays black | Medium | No camera view that drive | DSP-11; B7 cold starts | Open (bench) |

## Before you move on

1. **Measure the TS-7 (DSP-10)** with calipers: the board's height over the ears, the ear-hole positions, the glass position, the tallest part on the back, the HDMI and micro-USB socket positions, and your HDMI adapter and 90° micro-USB plug. Lay it on page 1 of the fit template, `--set` the values, regenerate, then print the bezel.
2. **Bench B7:** 10 cold starts on one 5 V source, the four corners, `ddcutil detect` (DSP-04, DSP-11).
3. **Buy for it:** the HDMI flat-cable kit (shielded if you can find one: [RF-16](13-tpms-radio.md)), two 90° micro-USB leads (left and right angle; the one that leads upward stays), a third 90° USB-A adapter for the touch lead.
