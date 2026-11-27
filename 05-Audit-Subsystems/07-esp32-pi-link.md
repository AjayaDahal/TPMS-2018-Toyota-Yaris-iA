# 07 · ESP32 ↔ Pi link

**Scope:** the UART between the ESP32 (UART2, GPIO16/17) and the Pi (GPIO14/15), and its line protocol (`$BSM`, `$ESP`, `$TPM`) in [link.cpp](../02-firmware/v2/src/logic/link.cpp). Physical layer: 115200 Bd, 3.3 V, 1 kΩ / 4.7 kΩ series resistors, ~10 cm inside the enclosure. Since rev A's J6 change, also the Pi's I2C6 switched onto the carrier's I2C bus (Q901/Q902, enabled by the Pi's GPIO18) and the other ways the two can talk (LNK-08).

**Maturity:** the framing, checksums and parsers are written and tested; the UART drivers on both sides, the Pi's OS settings and the I2C hand-over (LNK-10) are not done.

**Verdict: Sound** after one protocol change. The framing held up against everything the independent review threw at it. The gap was semantic: `seq` was parsed but never used, so a frozen vision loop could keep reporting "ready, all clear".

## What was verified

| Check | Evidence | Result |
|---|---|---|
| Field limits | Independent review: `seq` = 2³² − 1 and LED level 0/255 accepted; 2³², 256, −1, `+`, spaces, empty fields, extra or missing fields, `*` or `$` inside a field, an 11-digit `seq` rejected | OK |
| Line handling | 96-character line kept, 97 dropped; CR stripped; `$` always resyncs; bad checksum rejected | OK |
| Round trips | `formatEsp` / `formatTpm` at their field extremes parse back | OK |
| Back-powering | 1 kΩ / 4.7 kΩ series resistors limit the current into an unpowered Pi's pins (premortem P10) | OK by design, but see LNK-03 |

## Findings

| # | Severity | Finding | Fix | Status |
|---|---|---|---|---|
| LNK-01 | Medium | **`seq` meant nothing.** It was parsed and discarded, so the ESP32 couldn't tell a live vision loop from a frozen one whose reporting thread still sends `ready = 1` | `seq` is now the **vision frame counter**. A report whose `seq` hasn't moved doesn't refresh the link, so a stalled detector shows the fault pattern after 1 s ([ALR-06](05-alerts-and-alert-pod.md)). Protocol section of the [v2 README](../02-firmware/v2/README.md#protocol-uart2-115200-bd-33-v-pi-gpio1415) updated | **Fixed (audit)**; Pi side to implement |
| LNK-02 | Low | An overlong line cut short by the next `$` was dropped but not counted in `dropped()` | Counted now | **Fixed (audit)**, tested |
| LNK-03 | Medium | **UART TX while the Pi is off exists only as a comment** (premortem P10: "the ESP32 keeps TX off while the Pi rail is off"). If the app forgets, GPIO17 drives 3.3 V into an unpowered Pi through 4.7 kΩ: ~0.5 mA into its ESD diodes, enough to half-power parts of the Pi | In the app: keep GPIO17 as an input (high impedance) until PGOOD has been high for 1 s; back to input when PGOOD drops. Bench check: with the rail inhibited, measure the Pi's 3V3 rail (must stay at 0 V) | Open (app + bench) |
| LNK-04 | Medium | The Pi's default image puts Bluetooth or a login console on that UART (premortem E3) | Set-up script: `enable_uart=1`, `dtoverlay=disable-bt`, no `console=serial0` | Open (Pi set-up) |
| LNK-05 | Low | The XOR checksum catches every single-bit error and most bursts, but not two swapped characters. Over 10 cm inside the box at 115200 Bd that is acceptable; every field is also range-checked | Accepted | Accepted |
| LNK-06 | Info | The 8-bit `ledLevel` from the Pi is now floored at 48 by the ESP32 ([ALR-07](05-alerts-and-alert-pod.md)) | — | OK |
| LNK-07 | Medium | **The touch screen couldn't mute.** With the mute button dropped (2026-11-26), the docs said "touch mutes", but `$BSM` carried no mute and the ESP32 owns the buzzer | `$BSM` gains a 9th field, the touch screen's **mute counter** (+1 per tap, mod 256): each change is one `mutePressed()`. A lost line loses no tap and a repeated line adds none. The first report, and the first after a gap > 1 s (a restarted Pi counts from 0), only learn it. It works with a frozen vision loop too. Protocol section of the [v2 README](../02-firmware/v2/README.md#protocol-uart2-115200-bd-33-v-pi-gpio1415) updated | **Fixed**, 5 new checks; Pi side to implement |
| LNK-08 | Medium | **No room to grow (your request, 2026-11-27).** Only the UART and one spare line joined the two. Every usable DevKit GPIO is assigned (GPIO12 must stay open), so no ESP32 pin can be added: SPI is out, because an SPI slave needs four free pins and the ESP32's SPI bus belongs to the CC1101 | J6 becomes GH-6 (the same LCSC part as J7, no new fee). It now carries the Pi's I2C6 (GPIO22/23) onto the carrier bus through two 2N7002 switches (Q901/Q902) that the Pi's GPIO18 turns on. GPIO18 also powers the Pi-side pull-ups (R911/R912), and the ESP32 still reads it on expander P2. So the Pi can read the INA226s, the TMP75 and the expander itself (rescue, with the ESP32 out), and reach any I2C part added on J9 later. The DevKit's USB to a Pi port (lid off) is the flashing, log and reset path ([PCB-02](11-carrier-pcb.md)). The Pi's SPI0, I2C1 and UART2–5 stay free on the ribbon for Pi-side add-ons | **Fixed (rev A)** |
| LNK-09 | High (caught in design) | **The obvious wiring would have rebooted a halted Pi.** The usual I2C1 (GPIO2/3) has fixed 1.8 kΩ pull-ups, and GPIO3 low wakes a halted Pi 4. A one-FET switch passes the carrier's lows to the Pi side through its body diode (~0.6 V, under the Pi's 0.8 V VIL) even when it is off. So the ESP32's polling after the ACC-off shutdown would have woken the Pi, and the ESP32 would then have cut its power mid-boot. Gating the switches from the rail-up divider (PI_PGOOD) instead had two more problems. It would couple every I2C edge into GPIO15 (13 kΩ source, ~1.3 V kicks). It would also load the bus whenever the Pi's 3.3 V was down while 5V_PI was up | I2C6 on GPIO22/23: no fixed pull-ups, and not a wake pin. The gates and the Pi-side pull-ups hang on the Pi's own GPIO18, which `gpio=18=op,dl` holds low from power-on: nothing joins the bus unless a running Pi drives it high | **Fixed (rev A design)** |
| LNK-10 | Medium | **Two masters, no arbitration.** The BCM2711's I2C controller can't arbitrate, so a Pi transaction during the ESP32's polling corrupts both. Worst case is an expander or INA226 register written wrong | Rule: the ESP32 owns the bus. The Pi raises GPIO18 only with the DevKit out or held in reset, or after a `$I2C` hand-over on the UART (reserved in the protocol, not written). The ESP32 re-writes the expander's and INA226s' configuration every cycle, so a collision can't leave them wrong for long | Open (firmware + Pi set-up) |

## Premortem: the link failed. Why?

| # | How it fails | Likely | Impact | Prevention / detection | Status |
|---|---|---|---|---|---|
| LNK-P1 | The detector hangs; the reporter keeps saying "ready, nothing there" | Was Medium | False all-clear | LNK-01 | Fixed (ESP32) / Open (Pi) |
| LNK-P2 | A fresh OS image puts a login console on the UART; the ESP32 sees garbage and shows a fault | High on a default image | System down until fixed | LNK-04 set-up script; the fault pattern makes it obvious | Open |
| LNK-P3 | The ESP32 back-powers the Pi through TX after the key is turned to ACC with the Pi inhibited | Medium | Odd Pi states, SD risk | LNK-03 | Open |
| LNK-P4 | Electrical noise from the regulators corrupts bytes | Low | Dropped lines (counted), never wrong alerts | Checksums, strict parsing, a common ground at the regulator (E4, E5) | Fixed (design + firmware) |
| LNK-P5 | A later Pi feature uses the I2C bus while the ESP32 polls it | Medium, once someone tries | Wrong readings, a register written wrong | LNK-10's rule and the `$I2C` hand-over; the ESP32 rewrites its configuration registers every cycle | Open |
| LNK-P6 | A Pi that hangs with GPIO18 high and SDA low blocks the ESP32's bus | Low | No INA226, TMP75 or expander readings. The fan runs by default, and neither power rail depends on I2C | The ESP32 logs an I2C fault and, as a last resort, power-cycles the Pi (PI_INHIBIT); remove Q901/Q902 if it ever recurs | Open (firmware) |
| LNK-P7 | The ribbon's cut end (34 unused conductors, the Pi's 5 V on 2 and 4) frays and shorts against a neighbour or the board | Low with the edge sealed | The Pi's 5 V shorted to whatever it touches | Trim the unused conductors back and seal the edge ([Connecting the Pi](../01-hardware/v2/carrier/README.md#connecting-the-pi), step 2); ring the 5 V holes to nothing before power | Open (assembly) |

## Before you move on

- In the Pi app: send the detector's frame counter as `seq`, not a message counter.
- In the ESP32 app: gate UART TX on PGOOD.
- Pi set-up: `dtoverlay=i2c6` and `gpio=18=op,dl` (the [carrier README](../01-hardware/v2/carrier/README.md#connecting-the-pi)); keep the Pi off the I2C bus while the ESP32 runs until the `$I2C` hand-over exists.
