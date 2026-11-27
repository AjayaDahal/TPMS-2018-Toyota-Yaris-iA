# 06 · Raspberry Pi 4

**Scope:** the Pi 4 as the vision and touch-screen computer:
- its power-up sequencing (`PiPowerSequencer` in [pi_power.cpp](../02-firmware/v2/src/logic/pi_power.cpp));
- its supply, USB and thermal limits;
- the OS set-up (read-only root, UART, Bluetooth off);
- the software it still needs.

The cameras and the detector are in [cameras and vision](08-cameras-and-vision.md); the display in [display](09-display-and-ui.md).

**Maturity:** the start-up logic is written and tested; nothing runs on a Pi yet (vision app, set-up script, golden image).

**Verdict: Watch.** The audit fixed one high-severity bug: an ESP32 reset cut power to a running Pi. Heat is the real limit. The Pi 4 is specified for 0–50 °C ambient, and a parked car's cabin reaches 52–76 °C, so on summer days it will throttle until the cabin cools.

## What was verified

| Check | Evidence | Result |
|---|---|---|
| Start-up sequencing | Independent review: ACC bounce, a 0 V crank, 13.0 V ±50 mV ripple, 7.4/7.6 V dither, the 9.0/7.5 V thresholds: no false start, no false ACC loss; key in ACC only → on at 15 s; hot board → on when cooled or at 10 min | OK |
| ESP32 reset with the Pi running (new tests) | Fresh sequencer with the rail already up, at 14.2 V, at 12.4 V (ACC only) and at 65 °C | Never inhibits (was: cut for 1 s, 15 s or 10 min) |
| Supply limits | Raspberry Pi docs and datasheet: 5.1 V supply; undervoltage below 4.63 V ±5 %; USB ports 1.2 A total (datasheet: ~1.1 A) | See [PWR-01](01-power-and-protection.md), PI-03 |
| USB topology | Pi 4 docs: "USB 2.0 lines on all four ports are connected to a single USB 2.0 hub within the VL805" | Both cameras share one 480 Mbit/s bus ([CAM-03](08-cameras-and-vision.md)) |
| Thermal limits | Pi docs: Arm cores throttled progressively from 80 °C, hard limit 85 °C; rated ambient 0–50 °C. Parked-car studies (ASU 2018; Grundstein 2009): cabin air up to 52 °C after an hour, 41–76 °C all-day maxima, dashboard surfaces up to 85 °C | PI-04 |
| Heat in the box (estimate) | Pi 4 under vision load ~6 W, the carrier's Pi buck ~1–1.7 W, ESP32 ~0.7 W, rest ~0.3 W: **5–8.5 W**; the TS-7 (~2.4 W) sits in front of the plate, in the intake path. A 30 mm fan moving 0.6–1 L/s through the box warms the air 7–12 K; a heat-sunk Pi 4 SoC runs 25–35 K above its local air | **Throttling starts at a cabin temperature of about 40–45 °C** |
| Hardware MJPEG decode | Kernel `bcm2835-codec` maps MJPEG to the GPU decoder; raspberrypi/linux issue #5142: it works with some USB cameras and errors with others | PI-05 |

## Findings

| # | Severity | Finding | Fix | Status |
|---|---|---|---|---|
| PI-01 | High | **An ESP32 reset cut power to a running Pi.** After any reset (watchdog, brown-out, a firmware update over Wi-Fi) the sequencer started in "wait" and held `PI_INHIBIT` high: 1 s with the engine running, 15 s with the key in ACC, up to 10 min with a hot board. That contradicted the README ("never cuts the Pi's power") and risks the SD card whenever the read-only root is off during development | The sequencer reads the regulator's power-good (`PI_PGOOD`, GPIO15): a rail already up means a running Pi, left on. `setup()` reads PGOOD before it drives `PI_INHIBIT` | **Fixed (audit)**, tested |
| PI-02 | Medium | **"Engine running" relies on 13.0 V.** The engine computer may hold the alternator lower (not documented publicly), and the ESP32's ADC isn't calibrated ([ESP-03](02-esp32-controller.md)). If it never sees 13.0 V, the Pi simply starts 15 s after ACC | Accepted as a fallback. Log the ACC voltage while driving (`$ESP` line) and lower `engineRunMv` if needed | Accepted / Open (car) |
| PI-03 | Medium | **USB current:** about 1.1 A for all four ports. Two cameras peak at 0.7 A. A display powered from a Pi USB port (the SunFounder TS-7: 0.48 A typical) would exceed the limit | The TS-7 takes its 5 V from 5V_PI (J5 pair 2) on a split micro-USB lead; only its touch data uses a Pi USB port ([DSP-03](09-display-and-ui.md)) | **Fixed (TS-7 redesign)** |
| PI-04 | High | **Heat.** The Pi is specified for 50 °C ambient. A parked car's cabin reaches 52–76 °C, and the enclosure adds ~10 K. At ~40–45 °C cabin the SoC reaches 80 °C and throttles; vision frame rates fall in the first minutes of a summer drive. The hot-start hold (board 60 → 55 °C, at most 10 min) shortens, but can't remove, that window | Heatsink with the inventory's thermal paste; the lid fan; console mount (shaded), never dash top in summer; cap the CPU (`arm_freq=1200`) if T1 shows throttling; the vision app lowers its frame rate rather than stalling; the ESP32's `camFault` shows a stalled side. Test T1 in a sun-soaked car | Open (T1) |
| PI-05 | Medium | **Hardware MJPEG decode depends on the camera.** Some USB cameras' MJPEG streams make the GPU decoder fail (issue #5142); the software decoder costs CPU the detector needs | Test the purchased cameras with `v4l2jpegdec` on the bench (V1); keep `jpegdec` as the fallback and count its cost in the frame-rate budget | Open (bench) |
| PI-06 | Medium | **SD card wear and power cuts** (premortem P3) | Read-only root (overlay file system), logs in RAM, settings in the ESP32's NVS, a high-endurance card, a golden image | Open (Pi set-up) |
| PI-07 | Medium | **Default OS settings break the link**: the UART carries Bluetooth or a login console (E3) | `enable_uart=1`, `dtoverlay=disable-bt`, no `console=serial0` in `cmdline.txt`; for the I2C link `dtoverlay=i2c6` and `gpio=18=op,dl` ([LNK-10](07-esp32-pi-link.md)): in the set-up script | Open (Pi set-up) |
| PI-08 | Low | The Pi's RAM isn't confirmed (≥ 2 GB needed, V2) | `free -h` (G3) | Open (G3) |
| PI-09 | Low | **The Pi software doesn't exist yet**: capture, detector, zone mask, `seq` as the frame counter, the car-flank check (V6), systemd `Restart=always` + watchdog | Write it in phase 1 of the build, starting with the bench test V1 | Open (Pi software) |

## Premortem: the Pi failed. Why?

| # | How it fails | Likely | Impact | Prevention / detection | Status |
|---|---|---|---|---|---|
| PI-P1 | A Wi-Fi firmware update of the ESP32 while driving cuts the Pi; with the overlay off, the SD card is corrupted | Was Medium | Rebuild the card | PI-01 | Fixed |
| PI-P2 | Every summer afternoon the vision runs at 2 fps for the first 15 minutes | High | Late or missed detections | PI-04; the frame-rate drop shows on the screen | Open (T1) |
| PI-P3 | Undervoltage resets the USB bus; both cameras vanish for seconds | Medium | Blind for seconds | [PWR-01](01-power-and-protection.md); `camFault` per side | Open |
| PI-P4 | The SD card dies after a year | Medium | System down (now a fault, not silence: [ALR-05](05-alerts-and-alert-pod.md)) | High-endurance card, read-only root, a spare golden card | Open |
| PI-P5 | An OS update breaks OpenCV, NCNN or the camera stack (V10) | Medium | Vision down | Pinned versions, provisioning script, golden image, no automatic updates | Open |
| PI-P6 | The Pi boots during the crank because the ESP32 started late | Low | Brown-out mid-boot | ESP32 drives `PI_INHIBIT` within 0.6 s ([ESP-02](02-esp32-controller.md)); read-only root makes it harmless | Open (B2) |

## Before you move on

- Bench test V1 with the two inventory USB boards: frame rate, hardware decode, both cameras at once.
- Write the set-up script (UART, Bluetooth off, read-only root, pinned packages) before the vision app, and make a golden image.
- Plan T1 for a hot day with the real enclosure.
