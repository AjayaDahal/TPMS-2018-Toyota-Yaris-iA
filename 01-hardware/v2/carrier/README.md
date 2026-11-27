# v2 carrier PCB, rev A

100 × 100 mm, 6 layers, 1.6 mm, ENIG. It carries the ESP32 DevKit and the CC1101 module on sockets, and powers the Raspberry Pi 4, the TS-7 display and itself from the car's 12 V ACC. It also senses both blinkers and drives the door LEDs, the piezo (J4 "BUZ": the piezo sits inside the dash unit, and J4's button pins 1–2 stay free), the lid fan, the Pi link (UART, plus I2C the Pi switches on) and the GPS port. It sits behind the Pi in the [printed enclosure](../../enclosure/README.md), parts facing the lid.

Everything here is generated. Don't edit the KiCad files by hand: change the Python and rebuild.

| File | What |
|---|---|
| [carrier_design.py](carrier_design.py) | The circuit: every part, net, value, LCSC number, DNP and hand-solder flag |
| [carrier_layout.py](carrier_layout.py) | Placement, enclosure keep-outs, and the high-current straps |
| [build_carrier.py](build_carrier.py) | Generator: schematic → ERC → board → placement checks → straps and GND fan-out → Freerouting (plus a repair pass) → pours → DRC with schematic parity → Gerbers, BOM, CPL, PDFs |
| `tpms_v2_carrier_route.ses` / `.json` | The route of record and the board fingerprint it belongs to |
| [docs/](docs/) | Schematic PDF, 1:1 assembly drawing, copper plots, renders |
| [03-manufacturing/v2_carrier/](../../../03-manufacturing/v2_carrier/) | **What you upload:** Gerber zip, JLCPCB BOM and CPL, and the hand-solder and DNP list |

Rebuild (KiCad 10, Java 21+, Freerouting 2.5):

```powershell
& "$env:LOCALAPPDATA\Programs\KiCad10\bin\python.exe" build_carrier.py
```

The route of record is committed: `tpms_v2_carrier_route.ses` (the Freerouting session) and `tpms_v2_carrier_route.json` (the fingerprint of the board it belongs to: parts, pads, nets, straps, rules). A rebuild of the same board reuses it, even on a fresh clone, so changing values, text or docs never changes the copper (`--reroute` forces a new route). Freerouting isn't deterministic and often leaves a few connections behind in the crowded spots. So each attempt gets a repair pass on the routed board, and the build runs up to four attempts (`--attempts`) until one leaves nothing unconnected by KiCad's count; one attempt takes 10–25 minutes. The DRC at the end is the gate: the build exits with code 2 and "do NOT order yet" if anything is unconnected. Then check the pin map against the netlist: `python ..\check_pinmap.py`.

## The circuit in one screen

| Block | Parts | Notes |
|---|---|---|
| 12 V in (J1) | 4 A NANO2 fuse → SMCJ24CA TVS → SUD50P06-15 P-FET (−60 V, reverse battery) → π filter (6.8 µH, 3 × 10 µF, 47 µF electrolytic for damping) → 10 mΩ shunt | INA226 at 0x40 measures the 12 V input voltage and the current to both bucks and the piezo |
| 5V_PI (J5) | TPS54560B, 441 kHz, 6.8 µH, SS56C (5 A / 60 V), 4 × 47 µF → 5.17 V, 5 A | 10 mΩ shunt + INA226 at 0x41; SMBJ6.0CA clamp; EN start delay ~1.3 s; `PI_INHIBIT` (GPIO26) can only hold it off; rail-up divider to GPIO15 |
| 5V_ESP | TPS54560B, 485 kHz → 5.17 V, 1 A | SS14 into the DevKit's VIN (a USB-powered DevKit can't back-feed the board); XC6206 → 3V3 for the I2C chips; ferrite → 3V3_RF for the CC1101 |
| Inputs | 3 × ICPL-356-50C SOP-4 optos (CTR 200–400 %, 80 V): left and right blinker, AUX (J1 pin 3) | 2 × 1.2 kΩ + indicator LED per input; each lamp return has its own pin |
| Outputs | 2 × AO3400A door LEDs (PWM), 2N7002 piezo (12 V from after the shunt, through a PTC), AO3400A fan (on by default) | — |
| Monitors | TMP75 (0x48) board temperature, beside the Pi buck; TCA9534 (0x20) expander: AUX in, fan, the Pi's I2C-enable line (input), 5 spare pins | — |
| Pi link (J6) | UART: Pi UART0 ↔ ESP32 UART2 through 1 kΩ / 4.7 kΩ. I2C: the Pi's I2C6 (GPIO22/23) onto the carrier bus through two 2N7002 switches (Q901/Q902) | Only the Pi's GPIO18 turns the switches on, and it also powers their Pi-side pull-ups (R911/R912): off, halted or booting, the Pi can't touch the ESP32's bus. See [Connecting the Pi](#connecting-the-pi) |
| Ports | J2/J3 doors, J4 piezo (`BUZ`), J6 Pi link, J7 GPS (JST-GH); J8 fan | GPS is optional: a fallback speed source after the OBD-II dongle, on the standard 6-pin Pixhawk pinout |

Every ESP32 signal passes a series resistor next to its DevKit pin. It limits fault current, and it's a cut point for rework.

## Order it at JLCPCB

1. **PCB:** upload `tpms_v2_carrier_gerbers_jlcpcb.zip`. Choose:
   - layers 6, 100 × 100 mm, 1.6 mm, quantity 5. The outline's outer edge is exactly 100.0 × 100.0 mm: its centre line is inset by half the 0.1 mm line, because a size check that counts the line would read 100.1 and leave the 100 × 100 price tier. If the quote shows anything over 100 × 100, stop: the zip is an old one;
   - ENIG (the only finish on 6 layers), outer copper 1 oz, inner 0.5 oz;
   - via covering: "Epoxy Filled & Capped". It is the default on 6 layers, and the PowerPAD vias need it;
   - the standard stack-up: Economic assembly only takes standard stack-ups, and nothing on this board needs controlled impedance;
   - everything else at JLCPCB's defaults: green mask, white silk, no gold fingers, castellated holes or impedance control. An option that adds a fee means something was mis-detected: this board needs none.

   The order number prints where the silkscreen says `JLCJLCJLCJLC` (top left), so choose "Specify a location".
2. **Assembly:** PCB Assembly on:
   - **Economic**, top side only, quantity **2**;
   - upload `tpms_v2_carrier_bom_jlcpcb.csv` and `tpms_v2_carrier_cpl_jlcpcb.csv`.

   Every line should match its LCSC part. Parts that aren't in the files (the ten SMD power parts, the sockets, the terminals and the DNP options) are in `tpms_v2_carrier_hand_solder_and_dnp.csv`.
3. **Placement preview:** check every polarized part before you confirm:
   - the diodes: SS56C at D201/D301, SS14 at D304, the 1N4148Ws; the SMCJ24CA at D101 and SMBJ6.0CA at D203/D302 are bidirectional, so either way is fine;
   - the LEDs: D102, D204, D303, D305, D501, D503, D505;
   - pin 1 of every IC: U101, U201, U202, U301, U302, U501–U503, U801, U802.

   The CPL rotations are fitted to JLCPCB's own footprints by the build, and it reports the worst fit (0.29 mm), but the preview is the last check.
4. **Price:** expect the board promo plus Economic assembly. Four former extended lines were swapped to JLCPCB Preferred ($0 fee) and the ten large 2/3-pad SMD power parts (6 lines) moved to hand-solder, leaving only **6 extended parts** (~$3.07 each) on top of the parts and the setup fee: see [Cost](#cost).

## Hand soldering

Fit these after the boards arrive (the list with LCSC/MPN numbers is `tpms_v2_carrier_hand_solder_and_dnp.csv`). Buy the ten SMD power parts in one LCSC order (~$4 for two boards, plus shipping): JLCPCB leaves their pads empty. Fit them first, before the sockets and terminals, while the board lies flat: smallest first (F601, F901, R104, R211, F101), then Q101 and C104, then the three inductors. The board won't power up without F101, Q101, L101 and R104 (12 V in), L201 and R211 (the Pi's 5 V) and L301 (the ESP32's 5 V).

| Ref | Part | Notes |
|---|---|---|
| A1 | 2 × 1×15 female headers, 2.54 mm, standard 8.5 mm tall | The footprint has both DevKit widths: rows 0.9" and 1.0" apart (silkscreen `0.9` / `1.0`). **Measure your DevKit first** and solder the right-hand socket in the matching row |
| A2 | 2×4 female header, 2.54 mm (or two 1×4 strips side by side) | The CC1101 module plugs in with its SMA toward the board's top edge (silkscreen `CC1101: SMA END`). The 2×4 is symmetric: turned round, it swaps VCC and a signal |
| J1 | 4-pole screw terminal, 5.08 mm: or 2 of your blue 2-pole blocks, slid together | Wire entries toward the board edge |
| J5 | 6-pole screw terminal, 5.08 mm: or 3 blue 2-pole blocks | Same |
| J8 | 1×2 right-angle pin header, 2.54 mm | Lid fan |
| C104 | 47 µF / 50 V electrolytic, 6.3×7.7 SMD (`C970679`) | Or a leaded 47 µF / 50 V electrolytic from your lab bin, bent onto the two pads (check polarity: `+` toward `12V_PROT`). Its − pad is the only hand-soldered pad on the GND planes, so it has thermal spokes |
| F101 | 4 A 2410 NANO2 fast SMD fuse (`C27515`, Littelfuse `0451004.MRL`) | Large 6 mm 2-pad SMD; easy to replace if it ever blows |
| F601, F901 | 2 × 0.5 A / 60 V 1812 PTC polyfuse (`C70113`, `mSMD050-60V`) | Large 4.5 mm 2-pad SMD |
| L101, L201, L301 | 3 × 6.8 µH 11×10 mm shielded inductor (`C408485`, `MWSA1004S-6R8MT`) | Large 2-pad SMD; pads extend 1.3 mm past each end of the body |
| Q101 | −60 V P-MOSFET TO-252 DPAK (`C7503186`, `SUD50P06-15`) | Large drain tab + 2 gull-wing leads |
| R104, R211 | 2 × 10 mΩ 1 % 2 W 2512 current shunt (`C192580`, `RLM25FEER010`) | Large 6.3 mm 2-pad SMD |

The ground pins connect to the solid GND plane on L2 and the GND pours on the other layers, through thermal reliefs. The SMD power parts join small copper pours solid, for the current (the largest, under R211, is ~4.4 cm² a side). Use flux, a 60–80 W iron with a big chisel tip, and keep it on a little longer than for a 2-layer board; a hot-air station or a preheated board makes the inductors and Q101's tab easier.

## Connectors from your lab

Every connector on the board mates with something in the lab inventory; nothing needs a JST-GH crimper.

| On the board | Footprint | From your lab | Notes |
|---|---|---|---|
| J1 (12 V in) | 4-pole 5.08 mm screw terminal, 1.3 mm holes | 2 blue 2-pole screw blocks, slid together | 5.0 or 5.08 mm pitch both fit (0.3 mm play a hole). Wire entries toward the board edge |
| J5 (5 V out) | 6-pole, the same | 3 blue 2-pole blocks | So 5 blocks a board, 10 for two |
| J2, J3, J4 (doors, piezo) | JST-GH 4-pin, assembled by JLCPCB | 3 × 4-pin elechawk GH1.25 → Dupont pigtails (20 cm, pre-crimped) | The door cable joins the pigtail with solder and heat-shrink: a Dupont joint doesn't lock and the door run vibrates |
| J6 (Pi link) | JST-GH 6-pin | 1 × 6-pin pigtail + your 40-pin GPIO ribbon | See [Connecting the Pi](#connecting-the-pi) |
| J7 (GPS) | JST-GH 6-pin, Pixhawk pinout | The GPS's own GH cable if it has one, or a 6-pin pigtail | Pins: 1 5 V, 2 TX (to the GPS's RX), 3 RX (from its TX), 4 SCL, 5 SDA, 6 GND. Check the GPS cable against this first; R907/R908 swap TX and RX |
| J8 (fan) | 1×2 2.54 mm right-angle male header | A right-angle strip from the Dupont kit, or a straight one bent 90° | The fan's Dupont plug fits it |
| A1 (DevKit) | 2 × 1×15 female 2.54 mm | Female header strips | Standard 8.5 mm tall: the enclosure allows 16 mm over the board for socket plus DevKit. Cutting a strip costs one position a cut, so plan ~1.5 × 1×40 strips a board |
| A2 (CC1101) | 2×4 female 2.54 mm | A 2×4 socket or two 1×4 strips side by side | — |
| J9–J12 (DNP) | 2.54 mm headers | Male strips, only if you ever need them | — |

The Preciva PR-3254 crimps Dupont (and JST-XH) contacts, not the 1.25 mm GH ones; the pre-crimped pigtails cover all of those. The JST-XH kit isn't used on this board. **Count before you order:** 3 × 4-pin and 1–2 × 6-pin GH pigtails a unit, 5 two-pole blocks a board, and the female strips. The pigtails' Dupont ends are usually female: check yours, it decides how the Pi's ribbon joins J6.

## Connecting the Pi

J6 (GH-6, silkscreen `PI`) is the whole Pi ↔ ESP32 link. At the Pi it uses your 40-pin GPIO ribbon cable: its IDC plug stands ~12.5 mm on the header, where straight Dupont plugs (~22 mm) would hit this board.

| J6 pin | Signal | Pi header pin | Pi GPIO | On the carrier |
|---|---|---|---|---|
| 1 | GND | 6 | — | GND |
| 2 | Pi TX | 8 | GPIO14, UART0 TXD | R901 1 kΩ → ESP32 IO16 (UART2 RX); test pad TP15 |
| 3 | Pi RX | 10 | GPIO15, UART0 RXD | R902 4.7 kΩ ← ESP32 IO17 (UART2 TX); test pad TP16 |
| 4 | I2C enable | 12 | GPIO18 | Gates of Q901/Q902, the Pi-side pull-ups R911/R912, and expander P2 through R903 (the ESP32 reads it) |
| 5 | SDA | 15 | GPIO22, I2C6 SDA | Q901 → I2C_SDA |
| 6 | SCL | 16 | GPIO23, I2C6 SCL | Q902 → I2C_SCL |

**Wiring it:**

1. Push the ribbon's IDC onto the Pi's GPIO header with the red stripe (conductor 1) on pin 1, the header's end away from the USB ports. Conductor n is then pin n.
2. Cut the ribbon ~10 cm from that plug and peel off conductors 6, 8, 10, 12, 15 and 16. Trim the other 34 back a few millimetres and seal their cut edge with heat-shrink or tape: pins 2 and 4 are the Pi's 5 V. Strip 3 mm of each of the six.
3. Join each to its pigtail lead from the table. For the car, solder and heat-shrink them. For the bench, crimp male Dupont pins on the ribbon wires (PR-3254; the 28 AWG ribbon wire is below its 26 AWG die, so fold the stripped end double) and plug them into the pigtail's female housings.
4. Before power, and before the IDC goes on the Pi, plug the pigtail into J6 and ring each join from its IDC hole (a male Dupont pin in the hole makes a probe point) to the board: GND, TP15, TP16, R903, Q901, Q902. Check that the 5 V holes (2, 4) reach nothing.

**Pi set-up**, in `config.txt`, with no `console=serial0,...` in `cmdline.txt`:

```
enable_uart=1
dtoverlay=disable-bt     # the PL011 UART on GPIO14/15 carries the ESP32 link
dtoverlay=i2c6           # I2C6 on GPIO22/23 (pins 15/16): /dev/i2c-6
gpio=18=op,dl            # GPIO18 low from power-on: the Pi stays off the carrier's I2C bus
```

**The I2C bus has one master at a time.** The ESP32 owns it: it polls the INA226s, the TMP75 and the expander all the time, and the Pi's I2C controller can't arbitrate with a second master. So the Pi raises GPIO18 only when the ESP32 isn't using the bus:

- **On the bench, or to rescue a dead ESP32:** DevKit out of its socket (or its EN button held down), then on the Pi `pinctrl set 18 op dh` and `i2cdetect -y 6` lists 0x20, 0x40, 0x41 and 0x48 (and the GPS compass if R909/R910 are fitted). `pinctrl set 18 op dl` when you're done.
- **With the ESP32 running:** only after a hand-over on the UART (a `$I2C` request and grant, reserved in the [protocol](../../../02-firmware/v2/README.md), not written yet). Until then the Pi gets the readings from the ESP32's status lines.

Why I2C6 and not the usual I2C1 (pins 3/5): I2C1 has fixed 1.8 kΩ pull-ups, and GPIO3 low wakes a halted Pi 4. A FET switch lets the carrier's lows through its body diode even when it's off, so the ESP32's polling after shutdown would have booted the Pi again ([LNK-09](../../../05-Audit-Subsystems/07-esp32-pi-link.md)).

**Other links between the two, now and later:**

- **USB:** with the lid off, a 90° micro-USB lead from the DevKit to a free Pi USB port lets the Pi flash the ESP32 (`esptool`, with automatic reset), read its log and reset it. The Wi-Fi OTA service mode is the other way in.
- **SPI isn't possible.** Every usable GPIO of the 30-pin DevKit is taken (GPIO12 must stay open), so there are no pins for an SPI slave. Its SPI bus belongs to the CC1101, and a bus can't have two masters.
- **Room to grow:** I2C devices on J9 (DNP 2×5: 3V3, GND, I2C, the expander's P3–P7 and its interrupt) are reachable from both the ESP32 and the Pi. The rest of the Pi's header (I2C1, SPI0, UART2–5) stays free on the ribbon for Pi-only add-ons.

## First power-up (bench, before the car)

Use a bench supply with a current limit, the DevKit and the CC1101 out of their sockets, and nothing on J5.

1. Look over the INA226s (U101, U202, 0.5 mm pitch) and the TCA9534 (U802) for bridges. With the power off, measure J1 + to − (more than 10 kΩ), TP4 (5V_PI) to GND and TP6 (3V3) to GND (both more than 100 Ω).
2. 12.0 V, limit **0.25 A**. D102 (green, 12 V) lights. TP1 and TP2 read ~12 V. After ~1.3 s TP3/TP4 read **5.17 V ± 2 %**, TP5 (5V_ESP) 5.17 V, TP6 and TP7 3.30 V. With no load the input current stays under ~50 mA.
3. Reverse polarity, limit 0.1 A: no current, nothing lights.
4. Insert the DevKit (antenna end at the `ESP32 ANTENNA END` mark) and flash the firmware. Run an I2C scan: 0x20, 0x40, 0x41, 0x48.
5. Load J5 (an electronic load or power resistors): 1 A, then 3 A, then 5 A for a minute each, with the supply's limit at 3 A. Pass: ≥ 5.05 V at J5 at 5 A, and U201, D201 and L201 below 85 °C after 10 minutes at 3 A.
6. `PI_INHIBIT` high: 5V_PI goes off within milliseconds and comes back ~1.3 s after release.
7. 12 V on J2 pins 1–2: D501 lights and TP12 (BLINK_L_OC) goes low; the same on J3 for the right side. Then the LEDs, piezo and fan from the firmware's test mode.
8. Insert the CC1101 and run bench test B6 (the noise floor with the Pi and the cameras on).
9. The Pi link ([Connecting the Pi](#connecting-the-pi)), with the Pi on J5 and the DevKit out: `pinctrl set 18 op dh` and `i2cdetect -y 6` list 0x20, 0x40, 0x41, 0x48; then `pinctrl set 18 op dl`. With the DevKit back in and its firmware running, `$ESP` status lines arrive on the Pi's `/dev/serial0` at 115200 Bd.

## Fixing it in house

Rev A is built to be reworked, not reordered:

| If… | …do this |
|---|---|
| The Pi buck misbehaves | Remove R201 and R202 (two 1206 0 Ω links). Wire a 5 V / 5 A module (for example the UCTRONICS buck) from J11 (12 V + GND, fit a 2×2 header) to J5's 5 V and GND terminals |
| The ESP32 buck misbehaves | Remove R301 and feed a 5 V module into J12 (5V_ESP_RAW + GND) |
| A rail needs trimming | Top feedback resistor R203 (Pi) or R303 (ESP), 0603: 82 kΩ → 5.17 V, 80.6 kΩ → 5.10 V, 78.7 kΩ → 5.00 V |
| The AM radio buzzes | The 441/485 kHz harmonics land in the AM band. RT R206 (Pi) or R306 (ESP) → **43 kΩ** moves the switching above the band (~2.2 MHz), for ~0.5 W more heat at 3 A |
| The Pi starts too early or too late | C213 (EN delay); remove Q201 to disable `PI_INHIBIT` |
| Q101 (reverse-protection FET) dies open | Bridge its tab to pin 3 with a short wire: it runs without reverse protection until you replace the FET |
| You want to measure a bucks' input current with a meter | Lift R104 (the 12 V shunt) and put the meter across its pads |
| A GPIO is wrong or damaged | Lift its series resistor beside the DevKit pin and wire the signal to another pin; five spare expander pins (P3–P7) and I2C are on J9 (fit a 2×5 header) |
| The GPS has TX and RX swapped | Move R905/R906 to R907/R908 |
| The GPS has a compass | Fit R909/R910 (0 Ω) to join it to the I2C bus |
| The Pi's I2C link upsets the ESP32's bus | Remove Q901 and Q902: the Pi is off the bus for good, and the UART is untouched |
| The CC1101 module has another pinout | Leave A2 empty, fit J10 (1×8) and wire the module to it |
| A blinker should use board ground | Fit R505 (left) or R510 (right), 0 Ω. For an isolated AUX input, remove R515 |
| The fan must always run | Remove R612: R611 then holds it on |
| More capacitance | Empty pads: C204/C304 (input, 1206), C210/C310 (output, 1206) |
| The XC6206 (3V3) fails | Remove R311 and fit R312 (0 Ω): the DevKit's own 3.3 V then feeds the I2C chips and the radio |
| Something draws too much | Read the INA226s (0x40: 12 V in, 0x41: Pi 5 V) and the TMP75; probe the test pads |

There are 23 signal and rail test pads plus 2 GND pads, all on the parts side.

## Cost

An estimate for 5 boards with 2 assembled, from JLCPCB's live part prices with their attrition and minimum quantities (2026-11-27). JLCPCB's quote at checkout is the real number.

| Item | Estimate |
|---|---|
| 5 bare boards: 6 layers, 100 × 100 mm, 1.6 mm, ENIG, epoxy-filled and capped vias | ~$2 at the current 6-layer promo |
| Economic PCBA: setup fee and stencil | ~$9.70 ($8.18 + $1.53) |
| Extended-part fees: **6 lines** × ~$3.07 (4 lines moved to Preferred at $0, 10 large 2/3-pad SMD parts on 6 lines moved to hand-solder) | ~$18.40 |
| Parts for 2 boards: 6 extended + 4 preferred + 41 basic, with JLCPCB's attrition and minimum quantities | ~$23–24 |
| Placement: 167 parts and ~430 solder joints a board at ~$0.0016 a joint | ~$1.40 |
| **Total before shipping (before any $6–$10 monthly SMT coupon)** | **~$55** |
| Shipping, depending on the carrier | ~$10–30 |

Then the parts you solder yourself: the 10 SMD power parts (~$4 for 2 boards on one LCSC order, plus its shipping; `C104` can come from your lab bin) and the 5 THT items in [Hand soldering](#hand-soldering) (~$5). The three spare bare boards cost nothing extra and can be hand-built if needed.
