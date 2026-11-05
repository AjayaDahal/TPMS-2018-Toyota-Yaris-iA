# Premortem: how this TPMS panel could fail

**Date:** 2026-11-05

**Scope:** everything except the panel dimensions, which are still to come.

Imagine it's a year from now and the panel is sitting in a drawer instead of the dashboard. These are the most likely reasons, from most to least likely. Each comes with the early warning signs and what has been done about it.

## The big one: the car's sensors can't be decoded

The design and the report were built around the **GM/Schrader EG53MA4** (OOK at 315 MHz, Manchester, ~123 µs chips). That is the sensor you tested on the bench with the GM OEC-T5 tool.

Your car is a **2018 Toyota Yaris iA**, a Mazda2 built by Mazda. Its factory sensor is **not** the EG53MA4:

| | What we know |
|---|---|
| Part number | Mazda catalogs list BHA4-37-140 → BHA4-37-140A → GDDL-37-140 for the Mazda2 family. This is inferred from the platform; no catalog names the Yaris iA itself |
| Maker | Probably TRW/ZF (the part is resold as a "TRW TPMS sensor"). **Not verified** |
| Frequency | 315 MHz (from parts cross-references) |
| FCC ID, modulation, bit rate, frame format | **Not public.** No rtl_433 decoder and no GitHub project covers it |
| Toyota fitment table (Bartec) | Lists Pacific/TRW for every Toyota model except the Yaris iA, whose row is blank |

So the protocol has to be discovered by capturing it. The hardware can receive almost anything at 315 MHz: the CC1101 does OOK and FSK, and FSK is likely. The MX-05V can only do OOK.

- **Warning sign:** no frames at all, or frames that never repeat with a stable ID.
- **Already done:** the [bring-up firmware](../firmware/bringup/README.md) is also a sniffer.
  - It has one OOK and three FSK receive profiles.
  - It decodes any sensor burst as Manchester and differential Manchester, and also prints the raw chips, so no protocol has to be assumed.
  - It compiles, and its decoder passes 8 unit tests with synthetic GM, Toyota/Pacific-style and noise bursts.
  - The tests caught one real bug, which is fixed: differential Manchester was dropping the last bit of every frame.
- **Your action, ideally before ordering the PCB:**
  1. Capture the car now with your RTL-SDR: run `rtl_433 -f 315M -A` while driving, or next to the car while letting a little air out of a tyre. If rtl_433 already recognises the sensor, you're done. If not, its analyzer shows the modulation, chip length and bits.
  2. At the next tyre service, ask the shop to read a sensor with their TPMS tool. It shows the sensor type, the ID and often the part number.
  3. **Fallback if it can't be cracked:** use external valve-cap TPMS sensors with a known 315 MHz protocol that rtl_433 decodes. The panel reads those instead, and the factory sensors keep feeding the car's own warning light.

## Ranked failure stories

| # | How it fails | Likely? | Early warning | Mitigation | Status |
|---|---|---|---|---|---|
| 1 | Car's sensor protocol can't be decoded | **High** | No stable IDs in the sniffer or rtl_433 | Capture and identify first; tyre-shop read-out; cap-sensor fallback | Sniffer done; capture is your action |
| 2 | "It receives nothing" during bench or garage tests | **High** (early) | Silence while parked | Sensors send about once a minute only when moving. Drive, use an activation tool, or change the pressure | Documented |
| 3 | OLED burn-in from a static screen | **High** (over months) | Ghost outlines | Firmware: dim or blank after ~30 s with no alarm, wake on knob or alarm, shift the layout a few pixels every few minutes | Firmware rule (below) |
| 4 | Wrong readings: neighbours' sensors, or swapped wheels after a tyre rotation | Medium–High | Unknown IDs, values that jump | Learn the 4 IDs once and store them in NVS; ignore all others; add a relearn mode; flag a wheel as stale if not heard for 20 min while driving | Firmware rule |
| 5 | Rear wheels drop out (weak signal) | Medium | Rear signal below about −95 dBm, gaps | The E07 is tuned for 433 MHz. Use a 315 MHz antenna on an SMA extension placed behind plastic, not metal. Check per-wheel signal strength in the sniffer before the final install. Last resort: a 315 MHz-tuned module (J2 accepts other pinouts) | Sniffer shows signal strength |
| 6 | Board arrives and doesn't work, and it's unclear why | Medium | — | The self-test checks each part with a clear message. Power the bare board first and measure 5 V / 3V3 on the J4 pads before plugging in modules | Done |
| 7 | A module is plugged in rotated 180° (the CC1101's 2×4 header and the DevKit are symmetric) | Medium | Smoke | Before power, check the silkscreen: "1" and "SMA" on U1, "USB"/"ANTENNA" and pin names on A1, labels on J3 | Documented |
| 8 | Firmware never gets finished | Medium | — | Work in stages: self-test → capture → decode one sensor → 4 IDs + learn mode → UI → alarms → Wi-Fi/OTA last | Plan |
| 9 | Vibration loosens the sockets | Medium | Random resets, blank display | Use machined (round-pin, gold) sockets or solder the DevKit in. Add a dab of RTV on the modules. Don't hang the antenna on the module; use an SMA extension. Put ferrules on the J1 wires | Documented |
| 10 | Heat in a parked car (70–90 °C) | Medium | Resets or a fading display in summer | The OLED, ESP32 and CC1101 are rated to 85 °C, so mount the panel out of direct sun. U4 has a copper heatsink pour. Avoid full-white screens (or use display jumper option #1 with JP1) | Pour done; mounting is your call |
| 11 | Random resets on the bench | Medium | Resets when the screen is bright or Wi-Fi is on | A laptop USB port (500 mA) can't supply the OLED's ~375 mA plus Wi-Fi peaks. Use a 12 V bench supply or a powered hub | Documented |
| 12 | Garbled display or failed radio set-up from the shared SPI bus | Low | Random characters, a wrong CC1101 VERSION | The firmware uses 4 MHz SPI, transactions, weaker SCK/MOSI drive for the ~100–130 mm tracks, and keeps the CC1101's MISO released when not selected | Done |
| 13 | Interrupt flood at boot from GDO0's 135 kHz default clock | Low | Watchdog resets | Configure the CC1101 before attaching the IO34 interrupt | Done in the firmware |
| 14 | Car battery drained | Low (if wired right) | Dead battery after a few days parked | ACC only, never constant 12 V. The panel draws ~1 W, which flattens a battery in about two weeks. Fuse the tap | Documented |
| 15 | AM radio buzz from the 5 V switcher | Low | Noise on AM | Add TRACO's EMC input filter to the 12 V lead | Documented |
| 16 | Expecting the two front USB sockets to charge phones | ? | — | They are **not powered** by this board (U3 is 1 A). To charge, wire them to a separate 12 V → 5 V/3 A car USB charger module | Decide |
| 17 | A substitute part doesn't fit | Low | — | Avoid: R-78E (28 V max), a passive buzzer, blue/white LEDs on 220 Ω, a WROVER or 38-pin DevKit | Documented |

## Firmware rules that prevent several of these

- Configure the CC1101 before enabling the GDO0 interrupt. Never put the CC1101 in transmit mode.
- Only accept the 4 learned IDs. Store them in NVS when they change; ACC can cut power at any moment.
- Show "no data" or "stale" per wheel instead of an old value.
- Protect the OLED: dim or blank it when idle, and shift the layout periodically.
- Keep alarms audible (buzzer) and glanceable (wheel LEDs), so you don't need to read the screen while driving.

## Next steps, in order

1. **Capture and identify the Yaris sensors** (RTL-SDR now, the panel sniffer later). This decides whether the project works.
2. Send the panel dimensions, rebuild, and order the PCB.
3. Assemble and run the bring-up self-test.
4. Write the decoder and learn mode for the identified protocol.
5. Build the UI, alarms and burn-in protection.
6. Install: fused ACC tap, antenna placement, vibration-proofing.
