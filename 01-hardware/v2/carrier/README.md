# v2 carrier PCB, rev A

100 × 100 mm, 6 layers, 1.6 mm, ENIG. It carries the ESP32 DevKit and the CC1101 module on sockets, and powers the Raspberry Pi 4, the TS-7 display and itself from the car's 12 V ACC. It also senses both blinkers and drives the door LEDs, the alert pod (piezo and mute button), the lid fan, the Pi UART link and the GPS port. It sits behind the Pi in the [printed enclosure](../../enclosure/README.md), parts facing the lid.

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
| 5V_PI (J5) | TPS54560B, 441 kHz, 6.8 µH, B560C, 4 × 47 µF → 5.17 V, 5 A | 10 mΩ shunt + INA226 at 0x41; SMBJ6.0A clamp; EN start delay ~1.3 s; `PI_INHIBIT` (GPIO26) can only hold it off; rail-up divider to GPIO15 |
| 5V_ESP | TPS54560B, 485 kHz → 5.17 V, 1 A | SS14 into the DevKit's VIN (a USB-powered DevKit can't back-feed the board); XC6206 → 3V3 for the I2C chips; ferrite → 3V3_RF for the CC1101 |
| Inputs | 3 × LTV-357T optos: left and right blinker, AUX (J1 pin 3) | 2 × 1.2 kΩ + indicator LED per input; each lamp return has its own pin |
| Outputs | 2 × AO3400A door LEDs (PWM), 2N7002 piezo (12 V from after the shunt, through a PTC), AO3400A fan (on by default) | — |
| Monitors | TMP75 (0x48) board temperature, beside the Pi buck; TCA9534 (0x20) expander: AUX in, fan, Pi AUX, 5 spare pins | — |
| Ports | J2/J3 doors, J4 pod, J6 Pi UART, J7 GPS (JST-GH); J8 fan | GPS is optional: a fallback speed source after the OBD-II dongle, on the standard 6-pin Pixhawk pinout |

Every ESP32 signal passes a series resistor next to its DevKit pin. It limits fault current, and it's a cut point for rework.

## Order it at JLCPCB

1. **PCB:** upload `tpms_v2_carrier_gerbers_jlcpcb.zip`. Choose:
   - layers 6, 100 × 100 mm, 1.6 mm, quantity 5;
   - ENIG (the only finish on 6 layers), outer copper 1 oz, inner 0.5 oz;
   - via covering: "Epoxy Filled & Capped". It is the default on 6 layers, and the PowerPAD vias need it;
   - the standard stack-up: Economic assembly only takes standard stack-ups, and nothing on this board needs controlled impedance.

   The order number prints where the silkscreen says `JLCJLCJLCJLC` (top left), so choose "Specify a location".
2. **Assembly:** PCB Assembly on:
   - **Economic**, top side only, quantity **2**;
   - upload `tpms_v2_carrier_bom_jlcpcb.csv` and `tpms_v2_carrier_cpl_jlcpcb.csv`.

   Every line should match its LCSC part. Parts that aren't in the files (sockets, terminals, DNP options) are in `tpms_v2_carrier_hand_solder_and_dnp.csv`.
3. **Placement preview:** check every polarized part before you confirm:
   - the diodes: B560C at D201/D301, SMBJ6.0A at D203/D302, SS14 at D304, the 1N4148Ws; the SMCJ24CA at D101 is bidirectional, so either way is fine;
   - the LEDs: D102, D204, D303, D305, D501, D503, D505;
   - the electrolytic C104;
   - pin 1 of every IC: U101, U201, U202, U301, U302, U501–U503, U801, U802;
   - Q101's tab.

   The CPL rotations are fitted to JLCPCB's own footprints by the build, and it reports the worst fit, but the preview is the last check.
4. **Price:** expect the board promo plus Economic assembly. The 16 extended parts cost about $3 each per order, on top of the parts and the setup fee: see [Cost](#cost).

## Hand soldering

Fit these after the boards arrive (the list with part numbers is `tpms_v2_carrier_hand_solder_and_dnp.csv`):

| Ref | Part | Notes |
|---|---|---|
| A1 | 2 × 1×15 female headers, 2.54 mm | The footprint has both DevKit widths: rows 0.9" and 1.0" apart (silkscreen `0.9` / `1.0`). **Measure your DevKit first** and solder the right-hand socket in the matching row |
| A2 | 2×4 female header, 2.54 mm | The CC1101 module plugs in with its SMA toward the board's top edge (silkscreen `CC1101: SMA END`). The 2×4 is symmetric: turned round, it swaps VCC and a signal |
| J1 | 4-pole screw terminal, 5.08 mm | Wire entries toward the board edge |
| J5 | 6-pole screw terminal, 5.08 mm | Same |
| J8 | 1×2 right-angle pin header, 2.54 mm | Lid fan |

The ground pins connect to the solid GND plane on L2 and the GND pours on the other layers, through thermal reliefs. Use a 60–80 W iron with a chisel tip and keep it on a little longer than for a 2-layer board.

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
| The CC1101 module has another pinout | Leave A2 empty, fit J10 (1×8) and wire the module to it |
| A blinker should use board ground | Fit R505 (left) or R510 (right), 0 Ω. For an isolated AUX input, remove R515 |
| The fan must always run | Remove R612: R611 then holds it on |
| More capacitance | Empty pads: C204/C304 (input, 1206), C210/C310 (output, 1206) |
| The XC6206 (3V3) fails | Remove R311 and fit R312 (0 Ω): the DevKit's own 3.3 V then feeds the I2C chips and the radio |
| Something draws too much | Read the INA226s (0x40: 12 V in, 0x41: Pi 5 V) and the TMP75; probe the test pads |

There are 23 signal and rail test pads plus 2 GND pads, all on the parts side.

## Cost

An estimate for 5 boards with 2 assembled. JLCPCB's quote at checkout is the real number.

| Item | Estimate |
|---|---|
| 5 bare boards: 6 layers, 100 × 100 mm, 1.6 mm, ENIG, epoxy-filled and capped vias | ~$2 at the current 6-layer promo |
| Economic PCBA: setup fee and stencil | ~$8 + ~$1.50 |
| Extended-part fees: 16 lines × ~$3, charged once per order | ~$48 |
| Parts for 2 boards: the 16 extended lines come to ~$12 a board (the two TPS54560B and two INA226 are ~$7 of it), the 41 basic lines to ~$2; plus surplus where a part has a minimum order | ~$30 |
| Placement: 173 parts and 441 solder joints a board at ~$0.0017 a joint | ~$2 |
| **Total before shipping** | **~$90** |
| Shipping, depending on the carrier | ~$10–30 |

Then the parts you solder yourself: the five items in [Hand soldering](#hand-soldering), from your own stock or ~$5. The three spare bare boards cost nothing extra and can be hand-built if needed.
