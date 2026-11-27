# 01 · Power and protection

**Scope:** everything from the fuse tap to the 5 V and 3.3 V rails, all on the [carrier PCB](11-carrier-pcb.md):
- the Add-A-Circuit (5 A) on an ACC fuse → J1 (screw terminal) → the carrier's 4 A fuse, SMCJ24CA TVS, SUD50P06-15 P-MOSFET reverse protection, π filter and 12 V shunt;
- the Pi buck (TPS54560B, 5.17 V / 5 A) with its EN start delay and the ESP32's `PI_INHIBIT`;
- the ESP32 buck (TPS54560B, 5.17 V / 1 A), the XC6206 3.3 V LDO and the radio's filtered 3V3_RF;
- the ACC-sense divider, the two INA226 monitors, and the power budget.

The start-up logic that drives `PI_INHIBIT` is in [Raspberry Pi](06-raspberry-pi.md) and [ESP32](02-esp32-controller.md).

**Maturity:** generated schematic and layout, ERC/DRC clean ([carrier PCB](11-carrier-pcb.md)). Not built yet: the bench tests B1–B6 now run on the assembled board, following the [bring-up steps](../01-hardware/v2/carrier/README.md#first-power-up-bench-before-the-car).

**Verdict: Watch.** The earlier weak spot, the Pi's 5 V margin (PWR-01), is fixed by design: the carrier makes its own 5.17 V. What's left can only be measured: the regulator's heat in the box, AM-band noise, and the car's ACC during START.

## What was verified

| Check | Evidence | Result |
|---|---|---|
| Component ratings | From the datasheets: TPS54560B 4.5–60 V in, 5 A, 0.8 V ±1 % reference, RT 100 kHz–2.5 MHz, 135 ns minimum on-time, EN threshold with hysteresis current. SMCJ24CA: 24 V stand-off, 26.7 V minimum breakdown, 38.9 V clamp. SUD50P06-15: −60 V, ±20 V gate. SS56C (Preferred, replaces B560C): 60 V, 5 A Schottky, 680 mV @ 5 A. ICPL-356-50CEAXW (Preferred, SOP-4 LTV-357T drop-in: 80 V, CTR 200–400 %), INA226 (bus and shunt inputs to 40 V absolute) | All above their worst case |
| 5 V at the Pi | 82 k / 15 k → **5.17 V** at the regulator (5.07–5.27 V with the reference and 1 % resistors). Minus the 10 mΩ shunt (33 mV at 3.3 A) and the lead to the Pi (30–50 mΩ: 100–165 mV): **4.87–5.17 V at the Pi at peak**, typically ~5.0 V. The Pi flags undervoltage at 4.63 V ±5 % (4.40–4.86 V) | Above the threshold even in the worst case (PWR-01 fixed) |
| Over-voltage | The TVS clamps at ≤ 38.9 V. Downstream: the bucks are rated 60 V, the P-FET −60 V, the INA226 inputs 40 V absolute; the Pi buck's EN divider puts ≤ 5.1 V on EN at 39 V | OK |
| Reverse battery | The P-FET blocks; the TVS is bidirectional; the AUX input on J1 is behind an opto | OK |
| P-FET gate | 33 k / 47 k from the source: Vgs = −5 V at 12 V, −16 V at 39 V, inside ±20 V; ~0.1 W in the FET at 2.5 A | OK |
| Start-up | EN 1 M / 150 k: on at 8.0 V, off at 4.6 V. On the Pi buck, 10 µF (C213) delays the start **1.2–1.4 s** after ACC, and D202 empties it when the 12 V drops. The ESP32's buck starts at once, so the ESP32 boots before the Pi rail and can hold it off through `PI_INHIBIT` (2N7002, pulled down: the Pi rail comes up if the ESP32 is in reset) | OK; measure in B1/B2 |
| Compensation | 18 k / 4.7 nF / 47 pF on COMP: ~33 kHz crossover, well below the 441 kHz switching | OK; check the load step in bring-up step 5 |
| π filter | 6.8 µH with 10 µF in, and 2 × 10 µF + 47 µF electrolytic out (the electrolytic's ESR damps it) | Damped (PWR-05 fixed) |
| Budget | 5V_PI 2.38 A typical / 3.90 A peak (Pi, cameras, the TS-7's 0.48 / 0.6 A) on a 5 A buck (78 %). 5V_ESP 0.32 / 0.64 A with the lid fan, on a 5 A part. 12 V input at 90 %: **1.3 A typical / 2.2 A peak at 12 V, 2.9 A peak at 9 V** | OK for the 4 A fuse and the 5 A tap |
| Losses | Pi buck at 3 A: diode ~1.0 W, IC ~0.5 W, inductor ~0.2 W: ~1.7 W (~90 %) | In the box's heat budget ([ENC-01](10-enclosure-and-thermal.md)) |
| Current paths | The 4–5 A paths are wide copper straps laid by design (see [PCB-09](11-carrier-pcb.md)) | OK |
| Monitors | INA226 at 0x40 measures the 12 V input current and voltage, 0x41 the Pi's 5 V current and voltage, both on Kelvin taps; TMP75 at 0x48 the board temperature | Firmware can log all three |
| Parked drain | ACC-only: nothing is connected with the key out | OK by construction (the OBD dongle is separate: [SPD-04](04-speed-sources.md)) |

## Findings

| # | Severity | Finding | Fix | Status |
|---|---|---|---|---|
| PWR-01 | High | The Pi's 5 V margin could be zero with a fixed 5.0 V ±4 % module | A 5.17 V buck on the carrier (decision (b) of the earlier audit), a 10 mΩ shunt to watch it, and three 5 V / GND pairs on J5. B4 still measures at the Pi's GPIO 5 V pin: pass ≥ 4.95 V under full load | **Fixed (design)**; confirm in B4 |
| PWR-02 | Medium | The reverse-protection MOSFET's −40 V was below the TVS's worst clamp | SUD50P06-15, −60 V | **Fixed** |
| PWR-03 | Medium | The TRACO's 36 V maximum was 0.5 V above the TVS clamp | Gone: both rails use 60 V bucks | **Fixed** |
| PWR-04 | Medium | **What ACC does during START isn't documented publicly**, nor the charging voltage | In the car, before installing: scope the fuse tap through a push-button start, and log the ACC voltage at idle and at speed (the `$ESP` line carries it, and the INA226 at 0x40 too) | Open (car) |
| PWR-05 | Low | The π filter could ring | 47 µF/50 V electrolytic across its output | **Fixed** |
| PWR-06 | Low | The TRACO derates to ~60 % at 80 °C | Gone: the ESP32 rail's buck is a 5 A part carrying ≤ 0.64 A | **Fixed** |
| PWR-07 | Low | Whatever pulls EN low must survive VIN | The 2N7002 (60 V, open drain) pulls the Pi buck's EN; EN never sees more than 5.1 V | OK (design) |
| PWR-08 | Info | A load dump above ~39 V on a car without central suppression | Accepted: the TVS clamps to 38.9 V, every part downstream takes ≥ 40 V, and the fused tap limits the damage | Accepted |
| PWR-09 | Medium | **AM radio:** 441 and 485 kHz harmonics fall in the AM band | π filter, a solid GND plane right under the bucks, tight hot loops. If B5 hears it: RT R206 / R306 → 43 kΩ moves the buck to ~2.2 MHz, above the band (~0.5 W more heat at 3 A) | Open (B5), rework ready |
| PWR-10 | Low | A dead buck on a first board | Every value is a 0603 on the board; failing that, remove the 0 Ω links and wire a 5 V module through J11 / J12 ([rework table](../01-hardware/v2/carrier/README.md#fixing-it-in-house)) | Rework path |

## Premortem: the power system failed. Why?

| # | How it fails | Likely | Impact | Prevention / detection | Status |
|---|---|---|---|---|---|
| PWR-P1 | The Pi shows the undervoltage flag on hot days with both cameras streaming | Low | Vision drops out | 5.17 V buck (PWR-01); B4 measured at the Pi; the INA226 at 0x41 logs the rail | Fixed (design) + B4 |
| PWR-P2 | The crank dips the ACC line while the Pi is booting | Low | SD writes cut | Start at 8.0 V plus the 1.3 s delay; the firmware holds the Pi until the engine runs or 15 s; read-only root (P1, P3) | Fixed (design + firmware) |
| PWR-P3 | A jump start or a big transient kills the reverse-protection MOSFET | Low | No power | −60 V FET (PWR-02); if it dies open anyway, bridge its tab to pin 3 | Fixed |
| PWR-P4 | The fuse tap is on a circuit that drops in START, or on the wrong side of the fuse | Medium | Brown-outs, blown tap | Meter the tap in ACC, ON and START (P7, PWR-04) | Open (you) |
| PWR-P5 | AM radio buzz from the bucks | Medium | Annoyance | PWR-09; B5 with the AM radio | Open (bench), rework ready |
| PWR-P6 | The Pi buck overheats in the box on a summer afternoon | Low | Shutdown | ~1.7 W at 3 A on GND and switch-node copper with 6 PowerPAD vias into the L2 plane and the GND pours; the TMP75 watches the board; bring-up step 5 and T1 | Open (bench, T1) |

## Before you move on

- Bring the board up on a current-limited bench supply ([README](../01-hardware/v2/carrier/README.md#first-power-up-bench-before-the-car)) before it goes near the car.
- B4 with a meter on the Pi's GPIO 5 V pin, not at the regulator; B5 with an AM radio next to it.
- In the car, meter the fuse tap through START (PWR-04).
