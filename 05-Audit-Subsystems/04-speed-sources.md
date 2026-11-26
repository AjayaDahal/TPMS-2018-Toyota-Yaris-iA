# 04 · Speed sources (OBD-II dongle and GPS)

**Scope:** the speed gate's two inputs:
- your Bluetooth ELM327-type dongle, through `obd::ElmClient` in [obd.cpp](../02-firmware/v2/src/logic/obd.cpp), PID 0x0D, Bluetooth Classic on the ESP32;
- the u-blox NEO-M8N GPS on UART1.

Also the hand-over between them in `AlertArbiter` ([alerts](05-alerts-and-alert-pod.md)). The speed gate keeps the buzzer quiet below 8 mph and wakes it at 12 mph.

**Maturity:** the ELM327 client and the hand-over logic are written and tested against a simulated dongle (clone quirks included); the GPS NMEA parser and the Bluetooth connection code are not written; your dongle isn't identified yet (Classic or BLE, parked current).

**Verdict: Watch.** The logic is sound. Three clone-dongle behaviours would have left a cheap dongle permanently unused or constantly resetting; they're fixed. What remains is identifying your dongle (B8).

## What was verified

| Check | Evidence | Result |
|---|---|---|
| Speed gate thresholds | Independent review: 11.9 mph off, 12.0 on, 8.0 keeps, 7.9 off | OK |
| Source priority | OBD while its reading is < 1 s old, else GPS (< 2 s old), else the last decision held 10 s, then LEDs only (tests) | OK |
| Reply parser | Spaces, headers (`7E8 03 41 0D 3C`), lower case, `410D00`, `410DFF` (1584 deci-mph); 14 malformed lines rejected | OK |
| ELM327 behaviour | Simulated dongle per the datasheet: echo, prompts, `STOPPED` when interrupted, `SEARCHING...`, `NO DATA`; NUL padding, bytes split across calls, stray prompts, reconnect with stale bytes | OK |
| Conversion | km/h → deci-mph rounds correctly around the gate (12 km/h → 7.5 mph, 20 km/h → 12.4 mph) | OK |
| Never listens to the bus | Only `AT` setup commands and `010D1` / `010D` are ever sent (premortem O2) | OK |

## Findings

| # | Severity | Finding | Fix | Status |
|---|---|---|---|---|
| SPD-01 | High | **Common clone dongles were never used.** Three behaviours each broke the client: (1) a clone that answers `?` to `ATSP6` searches the protocols on the first request (1.5–3 s); the 1 s timeout interrupted the search every time: 0 speeds, 39 resets a minute. (2) A banner without "ELM327" in it (many clones say "OBDII v1.5") kept it resetting forever. (3) `NO DATA` with the key in ACC counted as a dongle failure: a reset every 4 s | Any reset banner is accepted; once the dongle says `SEARCHING...` the client waits up to 8 s; `NO DATA` is counted (`noData()`) but isn't a failure | **Fixed (audit)**, tested with a fake dongle for each |
| SPD-02 | Low | A reply delayed in the Bluetooth link past the 1 s timeout was credited to the next request: a 1.1 s-old speed reported as fresh, and the next real reply dropped | After a timeout the client waits 300 ms and ignores late bytes before the next request | **Fixed (audit)**, tested |
| SPD-03 | Low | The README said a failing dongle "can only make the buzzer quieter, never louder". Inside the 8–12 mph hysteresis band that isn't true: OBD at 10 mph (gate closed) plus a 1.2 s dongle gap with the GPS reading 12.5 mph opens the gate, and it stays open while OBD reads 10 mph | Accepted: it needs both a dongle hiccup and a GPS error of 2+ mph while crawling. README reworded | Accepted (doc fixed) |
| SPD-04 | Medium | **Your dongle isn't identified.** If it works with an iPhone it is BLE or Wi-Fi, and `BluetoothSerial` (Classic) can't reach it. Its parked current is unknown (ELM327 reference: ~30 mA awake, ~18 mA in low-power mode) | Bench test B8: Classic or BLE, PIN, `ATZ` banner, current with the key out. Unplug it when parking for days if it doesn't sleep below ~5 mA | Open (you, B8) |
| SPD-05 | Medium | **The GPS needs sky, and a cold start takes about half a minute.** Without the dongle, the first ~30 s of each drive and every garage or tunnel have no speed: LEDs only, no buzzer (by design) | Mount the puck under the windshield on the dash top (not in the console); keep the dongle as the first source. Check the time to first fix in the car | Open (install) |
| SPD-06 | Low | A dongle answering in Bluetooth range with the default PIN can be used by anyone to inject CAN frames (premortem O5) | Prefer a dongle that needs a button press to pair or sleeps its radio; change the PIN; unplug for long parking | Open (choice of dongle) |
| SPD-07 | Info | PID 0x0D has 1 km/h resolution (0.62 mph); the 12 / 8 mph thresholds sit between steps (19/20 km/h and 12/13 km/h). Fine | — | OK |

## Premortem: the speed sources failed. Why?

| # | How it fails | Likely | Impact | Prevention / detection | Status |
|---|---|---|---|---|---|
| SPD-P1 | Your no-name dongle prints "OBDII v1.5" and ignores `ATSP6`: it never gives a speed | Was High | Buzzer quiet in tunnels and garages | SPD-01 | Fixed |
| SPD-P2 | The dongle drains the battery during a two-week trip | Medium | Flat battery | SPD-04 parked-current test; unplug | Open |
| SPD-P3 | The dongle is BLE-only and never connects | Medium | GPS only | SPD-04; a NimBLE client if needed (the client logic is transport-free) | Open |
| SPD-P4 | Bluetooth connect attempts block the 1 kHz loop while the dongle is out of range | Medium | Late or missed beeps | Task split, Bluetooth on core 0 ([ESP-04](02-esp32-controller.md)) | Open (app) |
| SPD-P5 | The GPS puck in the console never gets a fix | Medium | No speed without the dongle | SPD-05: dash top under the windshield | Open (install) |
| SPD-P6 | Garbage on the GPS UART reads as a speed | Low | Wrong gate | NMEA checksum and fix-valid flag in the parser (not written yet) | Open (app) |

## Before you move on

- Bench test B8 with your dongle: Classic or BLE, banner, `ATSP6` answer, speed with the engine running, current with the key out.
- When writing the GPS parser: checksum every sentence, use the RMC/VTG speed only with a valid fix.
