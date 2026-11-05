# Bring-up firmware and 315 MHz sniffer

This firmware does two jobs:
1. It checks a freshly assembled panel part by part.
2. It finds out what your car's TPMS sensors actually transmit.

The second job matters because the 2018 Yaris iA's sensor protocol isn't publicly documented (see [../../docs/premortem.md](../../docs/premortem.md)). It is not the GM/Schrader EG53MA4 analysed in the report.

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

## Finding out what your sensors send (do this before the real decoder, and ideally before ordering)

1. Take a laptop and the panel into the car, powered from the laptop's USB. The car's wiring isn't needed.
2. Select a receive profile:
   - Start with `FSK d25k bw135k` (turn the knob or send `p`).
   - Drive: sensors send about once a minute when moving and rarely when parked.
   - A TPMS activation tool, or letting a little air out, makes them send immediately.
3. A good result looks like this:
   - Frames keep coming with the same chip length and bit count.
   - They come from four different sensors (the ID part of the bits stays constant per wheel).
   - Signal strength is around −60 to −90 dBm.
4. Try the other FSK profiles, then OOK. Keep the one that decodes the most frames.
5. Each frame prints three versions of the same bits: `MAN` (Manchester), `DMAN` (differential Manchester) and the raw `chips`.
   - The bits alone can't show which line code the sensor uses, or whether the polarity is inverted.
   - Find the decoding where the ID repeats, the pressure changes when you add air, and a checksum or CRC matches.
   - rtl_433 with your RTL-SDR (`rtl_433 -f 315M -A`) and its BitBench tool help with this.
6. Send `r` to also print the raw pulse widths for offline analysis.
7. Write down the wheel each ID belongs to: deflate one tyre slightly, or note which ID changes.

## Decoder unit test (on a PC, no hardware)

From `firmware/bringup`, with any C++17 compiler (here using the pip-installable zig compiler):

```
python -m ziglang c++ -std=c++17 -O2 -Isrc test/host/test_decode.cpp src/rf_decode.cpp -o test_decode.exe
test_decode.exe
```

The test feeds synthetic sensor bursts through the decoder:
- GM-style OOK Manchester at 123 µs per chip, normal and inverted;
- FSK Manchester at 52 µs with 15 % jitter;
- Toyota/Pacific-style differential Manchester at 52 µs and 100 µs;
- a sync word in front of the data;
- random noise and too-short bursts, which must be rejected.

It prints `all decoder tests passed` and exits with 0.
