# 02 · ESP32 controller (v2)

**Scope:** the ESP32-WROOM-32 DevKit (30-pin) on the carrier: pin map, boot and strapping, ACC sensing, its three UARTs (USB, GPS, Pi), Bluetooth Classic to the OBD-II dongle, watchdog and settings storage, and how its firmware gets updated. The decision logic it runs is audited by subsystem: [blinker](03-blinker-sensing.md), [speed](04-speed-sources.md), [alerts](05-alerts-and-alert-pod.md), [Pi power](06-raspberry-pi.md), [link](07-esp32-pi-link.md).

**Maturity:** pin map final and audited; decision logic written and unit-tested (154 host checks after the audit's fixes); the application around it (drivers, tasks, Bluetooth, OTA) not written yet.

**Verdict: Watch.** The pin map is clean. Three things the paper design never settled: how to reflash the ESP32 after install, the boot race with the Pi regulator, and the task layout once Bluetooth is running.

## What was verified

| Check | Evidence | Result |
|---|---|---|
| Strapping pins | GPIO12 unconnected (flash voltage); GPIO2 held low by the DevKit LED's resistor; GPIO5 (CC1101 CS) idles high; GPIO15 (the Pi rail-up sense, pulled down) low at boot only mutes the ROM log; GPIO0 unused | OK (`check_pinmap.py` rules R4–R6) |
| Input-only pins | GPIO34/35 (CC1101 GDO0/2), GPIO36/39 (blinker optos) are inputs; 36/39 are polled, never interrupts (ESP32 errata 3.11) | OK |
| ADC | ACC sense on GPIO32 = ADC1_CH4, so it works with the radio on; 100 kΩ / 10 kΩ divider, BAT54S clamp, 100 nF at the pin | OK |
| Outputs safe at reset | LED, buzzer and PI_INHIBIT gates have pull-downs: LEDs and buzzer off, the Pi regulator free to start | OK |
| v1 reuse | CC1101 SPI, GDO0/2, I2C, buzzer and button pins are those of v1 (`[v1]` tags, audited), so the v1 radio driver and decoder carry over | OK |
| Every GPIO assigned once | 25 pins, no duplicates, no free GPIO left | OK (and a constraint: any new signal must go to the Pi or I2C) |
| Self-test of the audit | `check_pinmap.py --selftest` catches all six pin errors of the earlier drafts | OK |

## Findings

| # | Severity | Finding | Fix | Status |
|---|---|---|---|---|
| ESP-01 | Medium | **No way to update the firmware after install.** The plan says the DevKit's USB is "only for flashing", but no cable from the Pi, no opening in the box and no OTA path exist. Today a firmware fix means taking the enclosure out of the dash and the lid off. | (1) **Service mode** in the ESP32 app: hold the mute button while switching ACC on → Wi-Fi access point + OTA for 10 minutes; Wi-Fi stays off otherwise. The Pi (its Wi-Fi works; only its Bluetooth is disabled) or a laptop pushes the image. (2) Layout rule [PCB-02](11-carrier-pcb.md): the DevKit's USB end reachable with the lid off, EN/BOOT buttons too | Open (firmware + G7) |
| ESP-02 | Medium | **Boot race with the Pi regulator.** PI_INHIBIT (GPIO26) is pulled down, so the Pi buck starts after its EN delay (1.2–1.4 s after ACC: see [power](01-power-and-protection.md)). If the ESP32 hasn't booted and driven INHIBIT high by then, the Pi starts during the crank. (The audit's PGOOD fix, [PI-01](06-raspberry-pi.md), means a late ESP32 now leaves that Pi running rather than cutting it: no power blip, but no crank protection either) | First thing in `setup()`: read PGOOD, run the sequencer's first update and drive INHIBIT. Measure "ACC on → INHIBIT high" on the bench (add to B2; pass: < 0.6 s, under half the shortest EN delay). If it fails, raise the EN delay capacitor C213 (10 µF → 22 µF) | Open (firmware + B2) |
| ESP-03 | Medium | **ACC voltage reading isn't calibrated.** The ESP32 ADC is non-linear and its reference varies from chip to chip. Through the 11:1 divider, a few tens of mV of error becomes several hundred mV of battery voltage, and the "engine running" threshold (13.0 V) has to tell 12.8–13.2 V apart ([PI-02](06-raspberry-pi.md)) | Use the eFuse calibration (`esp_adc_cal` / `analogReadMilliVolts`). Add a one-time calibration against a meter, stored in NVS. Log the reading in the `$ESP` line (already there: ACC mV) and check it on the bench (B1) | Open (firmware + bench) |
| ESP-04 | Medium | **Task layout with Bluetooth isn't designed.** `BluetoothSerial::connect()` blocks for seconds while it searches or pages. If it runs in the same loop as the 1 kHz blinker polling and the alert logic, the LEDs and buzzer freeze while the dongle is out of range | Pin the logic task (1 kHz) and the RF capture to core 1. Run Bluetooth, the OBD client and GPS parsing in their own task on core 0, passing data through a queue. Enable the task watchdog with panic → reboot; the outputs default to off at reset | Open (firmware) |
| ESP-05 | Low | **ESD on the long leads.** The pod button lead (~0.8 m) goes straight to GPIO4 through the v1 RC network. The blinker leads are isolated by optos; the LED leads are on MOSFET drains | Add a TVS/ESD diode on the button input at the J POD connector | Open (G7) |
| ESP-06 | Low | GPIO14 (right LED) outputs a PWM burst during boot: the right door LED flickers at every start | Accepted and documented in `pins_v2.h` | Accepted |
| ESP-07 | Info | Two 3.3 V domains: the DevKit's own regulator feeds the ESP32; the carrier's XC6206 feeds the CC1101 and I2C. Both come from 5V_ESP and rise together, so neither back-powers the other. A DevKit on USB with the carrier unpowered can't push its 5 V into the board (SS14 on VIN), and its SPI and GPS lines go through 1 kΩ ([PCB-11](11-carrier-pcb.md)) | Keep the I2C pull-ups on the carrier's 3V3 | — |
| ESP-08 | Info | `millis()` wraps after 49.7 days. All timing in the logic uses unsigned differences, and ACC-only power restarts it every drive | — | OK |

## Premortem: the ESP32 side failed. Why?

| # | How it fails | Likely | Impact | Prevention / detection | Status |
|---|---|---|---|---|---|
| ESP-P1 | A firmware bug shows up after install, and fixing it means pulling the enclosure out of the dash | High without ESP-01 | Fixes never get made | Service-mode OTA + lid-off USB access | Open |
| ESP-P2 | The Pi starts during the crank because the ESP32 boots slower than the EN delay | Medium | Brown-out mid-boot, SD wear | ESP-02 measurement; PGOOD + INHIBIT first in `setup()` | Open |
| ESP-P3 | The dongle is out of range and Bluetooth connect attempts freeze the blinker loop: the danger beep comes seconds late | Medium | Missed warning | ESP-04 task split; watchdog | Open |
| ESP-P4 | The ESP32 hangs (stack overflow, I2C lock-up); the LEDs freeze in whatever state they were in | Low | Wrong steady LED for ≤ 5 s | Task watchdog → reboot; outputs default off; the Pi shows a fault when `$ESP` lines stop | Open (firmware) |
| ESP-P5 | Power is cut while settings are being written | Low | Settings lost | ESP-IDF NVS is power-fail safe; write only on change | Fixed (by design) |
| ESP-P6 | A static zap through the pod button resets or damages GPIO4 | Low | Mute button dead | ESP-05 | Open |
| ESP-P7 | A pin is wired differently from the pin map on the new board | Medium | Respin | Netlist check against `pins_v2.h` ([PCB-01](11-carrier-pcb.md)) | Open (G7) |

## Before you move on

- Decide the update path (ESP-01) before the layout: it sets where the DevKit's USB end goes.
- Write the ESP32 app with the task split of ESP-04 from the start; it is much harder to add later.
