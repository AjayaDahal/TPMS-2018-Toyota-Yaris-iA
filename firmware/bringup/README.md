# Bring-up firmware and 315 MHz receiver test

This firmware does two jobs:
1. It checks a freshly assembled panel part by part.
2. It receives your four GM/Schrader EG53MA4 tyre sensors and shows each one's ID, pressure, temperature and signal strength. That proves the whole receive chain before the real application is written.

The car's own TPMS is indirect (ABS-based), so these sensors are heard only by this panel. Their frame format is the one rtl_433 decodes as `Schrader-EG53MA4`. Bursts that aren't EG53MA4 frames are printed as raw bits for analysis, in case you ever try other sensors.

The CC1101 is only ever put in receive mode; this firmware never transmits.

## Build and flash

- Use PlatformIO (the VS Code extension, or the CLI).
- Open `firmware/bringup`, run `pio run -t upload`, then `pio device monitor` (115200 baud).
- The build is pinned to `espressif32@6.13.0` (Arduino-ESP32 2.0.x). The only library is U8g2.
- The DevKit's USB powers the whole panel on the bench, so no 12 V is needed. Plug in the DevKit, CC1101 and display only after checking the 5 V / 3V3 pads on J4 with a meter.
- Behind a corporate TLS-inspecting proxy, PlatformIO fails with SSL errors. Fix it by running `pip install pip-system-certs` in PlatformIO's Python environment.

## Self-test (printed at every boot)

| Line | Good | If not |
|---|---|---|
| `CC1101: PARTNUM 0x00 VERSION 0x14` | 0x14 or 0x04 = TI chip; 0x17 or 0x03 = clone chip that works | `0xFF 0xFF` means no answer: check U1 orientation (pin 1 / SMA end), 3V3 on J4 pin 2, and the CSN/SPI pins |
| `state 0x0D` | 0x0D = receiving | The CC1101 didn't calibrate: check 3V3 and the crystal |
| `noise floor` | about −100 dBm or lower | Higher means interference from the board (TSR switcher, OLED boost) or nearby devices |
| OLED test screen | 5 lines of text | Blank: check the 3V3 rail, the display orientation and pin 1. Upside down: change `U8G2_R0` to `U8G2_R2` |
| LEDs and buzzer | FL, FR, RR, RL light in turn, then one beep | Check LED polarity (square pad = cathode). A passive buzzer only clicks; it needs a tone |
| Knob and button | The screen's "knob" count changes by 1 per click; pressing beeps | Check the encoder solder joints |

## Checking your four sensors

1. Take a laptop and the panel into the car, powered from the laptop's USB. The car's wiring isn't needed.
2. Keep the first profile, `OOK bw203k 16kBd`; it's the one for the EG53MA4.
3. Wake each wheel with the OEC-T5 tool, or drive. The sensors send about once a minute when moving and stay quiet when parked.
4. Each decoded frame prints a line like this:
   ```
   12.345 s  EG53MA4 id 123456  220.0 kPa = 31.9 psi   77 F ( 25 C)  flags 058F2001  rssi  -71 dBm
   ```
   The OLED lists up to four sensors with their psi, °F and how many seconds ago each was heard.
5. Write down the wheel each ID belongs to; with the OEC-T5 you can trigger one wheel at a time. The real application will learn and store these IDs.
6. Check the signal strength of each wheel, especially the rear ones, with the panel where it will be mounted:
   - −60 to −90 dBm is fine.
   - Close to −100 dBm means the antenna needs a better spot (use an SMA extension, keep it away from metal).
7. Frames from other cars' sensors (other IDs) are normal; the application will ignore IDs it hasn't learned.
8. Bursts that aren't EG53MA4 frames are printed as `MAN` / `DMAN` / `chips` bit dumps. Send `r` to also print raw pulse widths.

If no EG53MA4 frame ever appears but `chips` dumps do, send `r` to capture the raw pulse widths. Then compare them with `rtl_433 -f 315M -A` on your RTL-SDR.

## Decoder unit test (on a PC, no hardware)

From `firmware/bringup`, with any C++17 compiler (here using the pip-installable zig compiler):

```
python -m ziglang c++ -std=c++17 -O2 -Isrc test/host/test_decode.cpp src/rf_decode.cpp src/eg53ma4.cpp -o test_decode.exe
test_decode.exe
```

The test feeds synthetic bursts through both decoders:
- EG53MA4 messages built to rtl_433's format:
  - a normal frame, with ID, pressure (kPa and psi), temperature and flags all checked;
  - two repeats in one burst;
  - a bad checksum and a 119-bit frame, which must be rejected.
- Generic decoder cases:
  - OOK Manchester at 123 µs, normal and inverted;
  - FSK Manchester at 52 µs with 15 % jitter;
  - differential Manchester at 52 µs and 100 µs;
  - a sync word in front of the data;
  - random noise and too-short bursts, which must be rejected.

It prints `all decoder tests passed` and exits with 0.
