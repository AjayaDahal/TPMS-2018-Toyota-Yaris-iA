# Premortem: how this TPMS panel could fail

**Date:** 2026-11-05, revised the same day.

**Scope:** everything except the panel dimensions, which are still to come.

## The setup

- **The car.** The Yaris iA's own TPMS is **indirect**: it compares ABS wheel speeds and has no sensors in the wheels. It keeps working on its own and never interacts with this panel.
- **The sensors.** You had four **GM/Schrader EG53MA4** sensors installed in the tyres, and this panel is their only receiver. Their protocol is known:
  - 315 MHz, OOK (on-off keying), Manchester coding, 123 µs half-bit;
  - a 120-bit message with ID, pressure, temperature and a checksum;
  - rtl_433 already decodes it as `Schrader-EG53MA4`.

> **Correction:** the first version of this premortem assumed factory Mazda sensors with an unknown protocol. That was wrong, and that risk doesn't exist.

The bring-up firmware now decodes these sensors directly. It lists each one's ID, pressure (kPa/psi), temperature and signal strength.
- The decoder follows rtl_433's slicer and frame checks.
- It's unit-tested with synthetic EG53MA4 transmissions: a valid frame, two repeats, a bad checksum and a truncated frame.
- It hasn't been tested against a real capture yet.

Imagine it's a year from now and the panel is sitting in a drawer. These are the most likely reasons, most likely first.

## Ranked failure stories

| # | How it fails | Likely? | Early warning | Mitigation | Status |
|---|---|---|---|---|---|
| 1 | OLED burn-in from a static screen | **High** (over months) | Ghost outlines | Firmware: dim or blank after ~30 s with no alarm, wake on knob or alarm, shift the layout a few pixels every few minutes | Firmware rule (below) |
| 2 | "It receives nothing" in the garage | **High** (early on) | Silence while parked | EG53MA4 sensors transmit when the wheel turns (about once a minute while driving) or when woken by the OEC-T5 tool. Parked, they stay quiet. Test by driving or with the tool | Documented; the bring-up firmware lists every sensor it hears |
| 3 | Readings from other cars, or the wrong wheel | Medium–High | Unknown IDs, values that jump, or swapped wheels after a tyre rotation | Learn the 4 IDs with the OEC-T5, one wheel at a time, and store them in NVS. Ignore all other IDs. Relearn after a rotation. Flag a wheel as stale if it hasn't been heard for 20 min while driving | Firmware rule; bring-up shows the IDs |
| 4 | Rear wheels drop out (weak signal) | Medium | Rear signal below about −95 dBm, or gaps | The E07 is tuned for 433 MHz (an estimated loss of up to ~10 dB). The FCC data still suggests 15–35 dB of margin. The radio now points its SMA down into the console pocket: use a 90° adapter with a 315 MHz antenna pointing straight back. If a rear wheel is weak, move the antenna out of the pocket on an extension cable, away from the steel floor tunnel. Check each wheel's signal strength with the bring-up firmware before the final install | Radio moved; measure |
| 5 | Board arrives and doesn't work, and it's unclear why | Medium | — | The self-test checks each part with a clear message. Power the bare board first and measure 5 V / 3V3 on the J4 pads before plugging in modules | Done |
| 6 | A module is plugged in rotated 180° (the CC1101's 2×4 header and the DevKit are symmetric) | Medium | Smoke | Before power, check the silkscreen: "1"/"SMA" on U1, "USB"/"ANTENNA" and pin names on A1, labels on J3 | Documented |
| 7 | Firmware never gets finished | Medium (lower now) | — | Reception and decoding are done in the bring-up firmware. Remaining work, in this order: learn mode → wheel layout UI → low-pressure alarm → burn-in protection → Wi-Fi/OTA (optional) | Plan |
| 8 | Vibration loosens the sockets | Medium | Random resets, blank display | Use machined round-pin gold sockets or solder the DevKit in. Add a dab of RTV on the modules. Put the antenna on an SMA extension. Crimp ferrules on the J1 wires | Documented |
| 9 | Heat in a parked car (70–90 °C) | Medium | Resets or a fading display in summer | The OLED, ESP32 and CC1101 are rated to 85 °C, so mount the panel out of direct sun. U4 has a copper heatsink pour. Avoid full-white screens (or use display jumper option #1 with JP1) | Pour done; mounting is your call |
| 10 | Random resets on the bench | Medium | Resets when the screen is bright or Wi-Fi is on | A laptop port (500 mA) can't supply the OLED's ~375 mA plus Wi-Fi peaks. Use a 12 V supply or a powered hub | Documented |
| 11 | One sensor goes quiet | Low–Medium (over years) | One wheel stops updating | Sensor battery life is typically 5–10 years, or a sensor may be in its off/storage mode. Show "stale" for that wheel and wake it with the OEC-T5 | Firmware rule |
| 12 | Garbled display or failed radio set-up from the shared SPI bus | Low | Random characters, a wrong CC1101 VERSION | The firmware uses 4 MHz SPI, transactions, and weaker SCK/MOSI drive for the ~100–130 mm tracks. The CC1101 releases MISO when it isn't selected | Done |
| 13 | Interrupt flood at boot from GDO0's 135 kHz default clock | Low | Watchdog resets | Configure the CC1101 before attaching the IO34 interrupt | Done in the firmware |
| 14 | Car battery drained | Low (if wired right) | Dead battery after a few days parked | ACC only, never constant 12 V. The panel draws ~1 W, which flattens a battery in about two weeks. Fuse the tap | Documented |
| 15 | AM radio buzz from the 5 V switcher | Low | Noise on AM | Add TRACO's EMC input filter to the 12 V lead | Documented |
| 16 | Expecting the two front USB sockets to charge phones | ? | — | They are **not powered** by this board (U3 is 1 A). To charge, wire them to a separate 12 V → 5 V/3 A car USB charger module | Decide |
| 17 | A substitute part doesn't fit | Low | — | Avoid: R-78E (28 V max), a passive buzzer, blue/white LEDs on 220 Ω, a WROVER or 38-pin DevKit | Documented |
| 18 | Doesn't fit the console opening once built | Medium | Paper template doesn't sit flush | The 2026-11-09 template photos match the opening under the HVAC controls. Still needed: the exact width, height, notch purpose, depth behind (12 V/USB/AUX strip at the top) and how it's held. See the checklist in hardware/README section 8 | Waiting for measurements |
| 19 | The shift knob (in P) hits a cable in the right USB socket | Medium | Cable touches the knob in P | Measure the gap; use a 90° USB cable, or move that socket up and left | Check |
| 20 | Losing the car's 12 V socket / USB / AUX behind the panel | Certain unless planned | — | Use the front USB sockets as extensions (car USB + a 12 V → USB charger). The 12 V socket can power the panel (ACC; verify 0 V with the key off) | Decide |

## Firmware rules that prevent several of these

- Configure the CC1101 before enabling the GDO0 interrupt. Never put the CC1101 in transmit mode.
- Only accept the 4 learned IDs. Store them in NVS when they change; ACC can cut power at any moment.
- Show "no data" or "stale" per wheel instead of an old value.
- Protect the OLED: dim or blank it when idle, and shift the layout periodically.
- Keep alarms audible (buzzer) and glanceable (wheel LEDs), so you don't need to read the screen while driving.

## Next steps, in order

1. **Optional quick check now:** run `rtl_433 -f 315M` on your RTL-SDR while driving. It should print `Schrader-EG53MA4` lines for all four tyres. Note their IDs, and wake each wheel with the OEC-T5 to see which ID belongs to which wheel.
2. Send the panel dimensions, rebuild, and order the PCB.
3. Assemble and run the bring-up firmware: self-test, then the sensor list with signal strength per wheel.
4. Build learn mode, the wheel layout, alarms and burn-in protection.
5. Install: fused ACC tap, antenna placement, vibration-proofing.
