# v2 firmware: ESP32 on the 100 × 100 mm carrier

The ESP32 is the real-time half of v2. It receives the TPMS sensors, reads the blinkers and the vehicle speed (your OBD-II dongle over Bluetooth, else the GPS), drives the two amber blind-spot LEDs and the buzzer, and sequences the Raspberry Pi's power.

The Pi 4 runs the cameras, the vehicle detector and the 7" touch screen, and reports to the ESP32 over a UART. The alerts are decided on the ESP32, so they keep working, and fail loudly, while the Pi boots or if it crashes.

**Status:**
- **Done:** the safety logic and the pin map. The logic is written and unit-tested on a PC: 120 checks, no ESP32 needed. The pin map passes the audit (gate G1). This is gate G2 of the [v2 order gate](../../00-project-management/PREMORTEM_v2.md#order-gate-for-the-v2-pcb).
- **Next, phase 1 of the [build steps](../../00-project-management/PREMORTEM_v2.md#what-to-do-next-in-order):**
  - the ESP32 application around the logic: the CC1101 driver and EG53MA4 decoder from [bringup/](../bringup/README.md), unchanged because the pins are the same, plus GPS NMEA, LEDC PWM, UART2 and `BluetoothSerial` for the OBD-II dongle;
  - the Pi vision app.

## Files

| Path | Content |
|---|---|
| [include/pins_v2.h](include/pins_v2.h) | Pin map, the single source of truth. Audited by `python 01-hardware/v2/check_pinmap.py` (strapping pins, input-only pins, boot glitches, ADC1, duplicates, pins shared with v1); `--selftest` proves the audit catches the six earlier pin errors |
| [src/logic/blinker.h](src/logic/blinker.h) / `.cpp` | Turn-signal detector for the two opto inputs |
| [src/logic/pi_power.h](src/logic/pi_power.h) / `.cpp` | Pi 5 V start-up sequencing (ACC-only power) |
| [src/logic/alerts.h](src/logic/alerts.h) / `.cpp` | Alert arbiter: LEDs and buzzer for the blind spots and the TPMS |
| [src/logic/link.h](src/logic/link.h) / `.cpp` | ESP32 ↔ Pi line protocol |
| [src/logic/obd.h](src/logic/obd.h) / `.cpp` | ELM327 client for the OBD-II dongle: vehicle speed (PID 0x0D) |
| [test/host/test_logic.cpp](test/host/test_logic.cpp) | Host unit tests for all five modules, with a simulated ELM327 |

The logic files are pure C++17 with no hardware access. The ESP32 application calls them from its 1 kHz loop.

## What the logic does

**Blinker** (`BlinkerDetector`, poll at 1 kHz):
- Gaps up to 25 ms inside a flash are bridged, so a lamp PWM-driven by the body control module reads as steady. Short spikes are ignored, because a level must hold for 50 ms.
- Each side stays active for 900 ms after the lamp goes dark, so the camera view doesn't drop between flashes.
- Left and right lighting within 150 ms of each other means hazard flashers. Hazards never show up as a brief left or right turn first.
- GPIO36/39 are polled, never used as interrupts (ESP32 errata 3.11).

**Pi power** (`PiPowerSequencer`):
- The Pololu regulator is on by default whenever ACC is present, after an RC delay of ~1.5 s. The ESP32 can only *hold it off* through `PI_INHIBIT`, so an ESP32 crash, reset or firmware update never cuts the Pi's power.
- The Pi is held off while the key passes through ACC to START, so the crank can't brown it out mid-boot.
- The Pi starts:
  - when the alternator voltage shows the engine is running (13.0 V for 1 s);
  - or after 15 s in ACC without the engine.
- In a hot car the start waits for the board to cool from 60 °C to 55 °C, but at most 10 min. Every hold has a deadline.

**Alerts** (`AlertArbiter`):
- A vehicle in a blind spot lights that side's LED steady. Signalling towards it flashes the LED and sounds the buzzer. The beep repeats every 3 s at most, and a new event needs 1 s after the last beep.
- Speed gate with hysteresis: nothing below 8 mph, nothing until 12 mph. Parking lots and drive-thrus stay quiet.
- Speed source: the car's own speed from the OBD-II dongle while it is under 1 s old (exact at walking pace, no sky needed), else the GPS. With neither for more than 10 s, the LEDs keep working and the buzzer stays quiet. A dongle that stops answering only hands over to the GPS, so it can make the buzzer quieter, never louder.
- Hazard flashers never sound the buzzer.
- **Mute/acknowledge button** (in the alert pod):
  - silences the blind-spot buzzer for the current turn-signal activation only;
  - acknowledges a TPMS alarm: no more reminders until the alarm clears or another tyre goes low. An unacknowledged alarm reminds every 10 min.
  - Both work while the Pi is down.
- Lamp test when the Pi first reports ready. After that, a stale Pi link (> 1 s) or a faulted camera shows the fault pattern on that side's LED and gives one fault beep. The system never fails silently.
- Buzzer priority: blind-spot danger, then fault, then TPMS.

**OBD-II dongle** (`obd::ElmClient`, optional):
- Talks to an ELM327-type dongle over a byte stream: `ATZ`, `ATE0`, `ATS0`, `ATH0`, `ATSP6`, then `010D1` every 200 ms. The trailing `1` makes the ELM327 return after the first reply instead of waiting out its 200 ms timer. A clone that answers `?` to it is polled with plain `010D`.
- Replies are accepted with or without spaces and 11-bit headers (`410D3C`, `7E8 03 41 0D 3C`); everything else (`NO DATA`, `STOPPED`, `SEARCHING...`) is not a speed.
- A command without a `>` prompt within 1 s (3 s for `ATZ`) failed; 3 failures in a row reset the dongle. A slow reply that the next request interrupts (`STOPPED`) resyncs without a reset.
- Speed only, never the blinker: standard OBD-II has no turn-signal data, and listening to the bus (`AT MA`) overflows the ELM327's 512-byte buffer. See [OBD-II dongle](../../00-project-management/PREMORTEM_v2.md#obd-ii-dongle-optional-speed-source) in the premortem.
- The ESP32 application connects with `BluetoothSerial` (Bluetooth Classic; the Pi's Bluetooth is off because its UART carries this link) by MAC address, with the PIN set (usually 1234 or 0000). Keep the Bluetooth stack on core 0, and the RF edge interrupt and the 1 kHz loop on core 1 (bench test B8). A BLE-only dongle needs a GATT client instead; the client logic stays the same.

## Protocol (UART2, 115200 Bd, 3.3 V, Pi GPIO14/15)

NMEA-style text lines: `$TYPE,field,...*HH\n`, where `HH` is the XOR of every character between `$` and `*`.

```
Pi -> ESP32, 10-20 Hz:
  $BSM,<seq>,<ready>,<occL>,<occR>,<camFaultL>,<camFaultR>,<ledLevel 0-255>*HH
ESP32 -> Pi, 10 Hz and on every turn change:
  $ESP,<seq>,<turn O/L/R/H>,<speed deci-mph, -1 = unknown>,<ACC mV>,<Pi PGOOD>,<button presses>,<BSM available>,
       <speed source N/G/O = none / GPS / OBD-II>*HH
ESP32 -> Pi, when a learned tyre sensor is heard:
  $TPM,<slot 0-3>,<sensor id hex>,<kPa x10>,<temp C>,<RSSI dBm>,<age s>*HH
```

A `$` always starts a new line, so garbage before it is dropped. Lines over 96 characters are discarded and counted. A bad checksum rejects the line.

## Running the tests

From this folder (`02-firmware/v2`), with any C++17 compiler (`pip install ziglang` gives one on Windows):

```bash
python -m ziglang c++ -std=c++17 -O2 -Wall -Wextra -Isrc/logic test/host/test_logic.cpp \
    src/logic/blinker.cpp src/logic/pi_power.cpp src/logic/alerts.cpp src/logic/link.cpp src/logic/obd.cpp \
    -o test_logic.exe
./test_logic.exe        # -> all 120 v2 logic checks passed (exit code 0)
```

The tests cover:
- PWM, spikes and hazards on the blinker;
- the crank, ACC-only and hot-car holds and their deadlines;
- the speed gate, GPS loss, OBD speed winning over GPS and handing over when it goes silent or invalid, mute per activation, the TPMS acknowledge (and a new low tyre re-raising it), lamp test, fault beeps and priorities;
- protocol framing, checksums, overflow, the format/parse round trips and the speed-source field;
- the ELM327 client against a simulated dongle (as its datasheet describes, plus clone quirks): setup order, 5 Hz polling, the plain-`010D` fallback, `NO DATA` with the key in ACC, a hung dongle, a slow reply (`STOPPED`), a dropped link, noise; and the reply parser.

Breaking the hazard handling, the TPMS acknowledge, the OBD priority, its fallbacks or the new protocol field makes them fail (checked by mutation).
