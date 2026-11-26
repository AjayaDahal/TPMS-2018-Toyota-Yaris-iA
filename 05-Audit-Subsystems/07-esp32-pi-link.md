# 07 · ESP32 ↔ Pi link

**Scope:** the UART between the ESP32 (UART2, GPIO16/17) and the Pi (GPIO14/15), and its line protocol (`$BSM`, `$ESP`, `$TPM`) in [link.cpp](../02-firmware/v2/src/logic/link.cpp). Physical layer: 115200 Bd, 3.3 V, 1 kΩ / 4.7 kΩ series resistors, ~10 cm inside the enclosure.

**Maturity:** the framing, checksums and parsers are written and tested; the UART drivers on both sides and the Pi's OS settings are not done.

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

## Premortem: the link failed. Why?

| # | How it fails | Likely | Impact | Prevention / detection | Status |
|---|---|---|---|---|---|
| LNK-P1 | The detector hangs; the reporter keeps saying "ready, nothing there" | Was Medium | False all-clear | LNK-01 | Fixed (ESP32) / Open (Pi) |
| LNK-P2 | A fresh OS image puts a login console on the UART; the ESP32 sees garbage and shows a fault | High on a default image | System down until fixed | LNK-04 set-up script; the fault pattern makes it obvious | Open |
| LNK-P3 | The ESP32 back-powers the Pi through TX after the key is turned to ACC with the Pi inhibited | Medium | Odd Pi states, SD risk | LNK-03 | Open |
| LNK-P4 | Electrical noise from the regulators corrupts bytes | Low | Dropped lines (counted), never wrong alerts | Checksums, strict parsing, a common ground at the regulator (E4, E5) | Fixed (design + firmware) |

## Before you move on

- In the Pi app: send the detector's frame counter as `seq`, not a message counter.
- In the ESP32 app: gate UART TX on PGOOD.
