# 13 · TPMS radio (315 MHz)

**Scope:** the receive chain for your four GM/Schrader EG53MA4 tyre sensors:
- the CC1101 module (EBYTE E07-M1101D) and its register set in [cc1101.cpp](../02-firmware/bringup/src/cc1101.cpp);
- the GDO0 edge capture in [rf_capture.cpp](../02-firmware/bringup/src/rf_capture.cpp);
- the EG53MA4 decoder in [eg53ma4.cpp](../02-firmware/bringup/src/eg53ma4.cpp);
- the antenna and the link budget.

The same radio, pins and code carry over to v2.

**Maturity:** decoder proven on real captures; firmware compiled and host-tested; never run on a real CC1101 receiving a real sensor (premortem R3).

**Verdict: Watch.** The protocol layer is right: the decoder decoded **64 of 64 real EG53MA4 frames** from SDR captures with the same values rtl_433 reports. The audit fixed several register and driver details and the capture interrupt. The open risk is the front end on real hardware. Nothing ends a burst while the demodulator outputs noise, so a noisy car could close no bursts at all. That needs the bench to tune.

## What was verified

| Check | Evidence | Result |
|---|---|---|
| Frequency | FREQ = 0x0C1D8A = 315,000,061 Hz with a 26 MHz crystal (+61 Hz) | OK |
| OOK modem | MDMCFG4/3/2 = 0x89/0x4B/0x30: 203.1 kHz filter, 16,415 Bd demodulator filter, OOK, no sync, DC filter on; the asynchronous output is sampled at 131 kS/s (7.6 µs) | OK |
| AGC, TEST and calibration registers | AGCCTRL 0x03/0x00/0x91 (TI DN022's OOK range); TEST2/1/FIFOTHR 0x81/0x35/0x47 (DN022, filters ≤ 325 kHz); TEST0 0x0B (VCO selection calibration below ~323 MHz); autocalibration on IDLE → RX | OK |
| Never transmits | Only SRES / SCAL / SRX / SIDLE strobes exist; PATABLE is never written | OK |
| SPI and reset | Read, burst and strobe framing; chip-ready wait with timeout; reset per datasheet 19.1.2 | OK |
| Decoder vs rtl_433 | Constants, Manchester zero-bit slicer and frame checks compared line by line with rtl_433's `pulse_slicer.c` and `schraeder.c` | Identical |
| **Real captures** | rtl_433's test set (`Schrader_EG53MA4_TPMS/01`, gfile001–004) → envelope detector → the unchanged capture + decoder code, built for a PC: **16/16 frames in each file**, IDs 2FC871 / 2EAAF9 / 3495AC / 2FC780, the same values as rtl_433's JSON | OK |
| Synthetic frames | 500 random frames each: nominal, asymmetric pulses (±14 µs), ±20 % jitter, ±20 % + 10 µs latency: all decoded. Inverted, truncated, bad checksum, payload bit flips: none decoded, no wrong readings | OK |
| Units | Pressure byte × 2.5 kPa (gauge), temperature byte in °F | OK |
| Interference lines | 26 MHz harmonics (312 / 338 MHz), 40/80 MHz, the Pi's 54 MHz × 6 = 324 MHz, SPI 4 MHz × 79 = 316 MHz: none within 315 ± 0.1 MHz | OK |
| v2 carry-over | `pins_v2.h` uses the same CC1101 pins; Arduino-ESP32 runs the loop and GPIO interrupts on core 1, the Bluetooth controller on core 0 | OK |

## Findings

| # | Severity | Finding | Fix | Status |
|---|---|---|---|---|
| RF-01 | High | **No carrier-sense gating.** In asynchronous mode the CC1101 outputs raw demodulated data, noise included. A burst ends only after 2.5 ms of silence and stops growing at 1,024 pulses. In simulation, 10+ ms of noise around a frame gave 0 % decodes | Gate the capture on carrier sense: GDO2 is already configured as carrier sense; set a carrier-sense threshold (AGCCTRL1, or an RSSI floor ~9 dB over the measured noise) and end the burst when it drops. Use a sliding window instead of the hard 1,024 cap. Tune on the bench with the 10 s `edges` counter; the bring-up README now flags it | Open (bench, before the v2 app) |
| RF-02 | Medium | **Phantom edges.** The interrupt didn't check whether the level had changed, so a glitch shorter than the interrupt latency (the CC1101's asynchronous output has ~38 ns ones) added an entry that broke the pulse/gap alternation: 1 of 300 frames decoded with glitches, against 300 of 300 fixed | The interrupt ignores an "edge" whose level equals the last one | **Fixed (audit)**; host-simulated (a glitch no longer adds a pulse) |
| RF-03 | Medium | FOCCFG = 0x16 (FOC_LIMIT = 2) was written in OOK mode; the datasheet says FOC_LIMIT must be 0 for ASK/OOK | 0x14 for OOK, 0x16 for the FSK profiles | **Fixed (audit)** |
| RF-04 | Medium | **Exactly 120 bits were required.** If the receiver's AGC swallows the first preamble pulse, the frame is rejected (rtl_433 behaves the same) | Frames of 100–119 bits are accepted when the bits left before the 80-bit payload are all zeros (the real preamble is 40 zeros); full frames are checked exactly as rtl_433 does | **Fixed (audit)**, tested (20 truncations decode; 99 bits or a 1 in the preamble rejected) |
| RF-05 | Medium | Timing margin is thin with asymmetric pulses: a 2-chip low measured 224 µs against a 184.5 µs threshold; with ±20 % jitter on top, 88 of 500 decoded (rtl_433 the same) | Estimate the chip length and the high/low bias from each frame's zero preamble | Open (after real CC1101 captures) |
| RF-06 | Medium | The GDO0 interrupt was attached even when no CC1101 answered; after reset GDO0 outputs a 135 kHz clock (~271 k interrupts/s). Premortem #13 said "Done" | Not attached without a CC1101 (`rf::detach()`) | **Fixed (audit)** |
| RF-07 | Medium (v2) | The GPIO interrupt isn't IRAM-registered, so it is masked during flash writes (NVS, Bluetooth bonding): frames arriving then are lost | No NVS writes while receiving, or an IRAM-flagged interrupt / RMT capture in the v2 app | Open (v2 app) |
| RF-08 | Medium (v2) | A full ring drops an edge without marking the burst, which corrupts it (dense noise with the loop blocked 60 ms: 1,213 of 17,388 edges lost) | An overflow flag that discards the current burst; drain the ring in its own core-1 task | Open (v2 app) |
| RF-09 | Medium | **The antenna, not the module, is the big 315 MHz loss.** Simulating TI's 433 MHz reference matching at 315 MHz costs 0.2–0.5 dB (assuming the E07 follows TI's design; EBYTE documents only 387–464 MHz). A 433 MHz quarter-wave whip used at 315 MHz is 0.17 λ long: **9.5–11.7 dB** of mismatch loss | Use a **315 MHz quarter-wave antenna (~23 cm)**; swap to a 315 MHz-matched module only if an RSSI A/B test shows a gain. Don't use the inventory's stubby articulated SMA antenna (probably 2.4 GHz) | Open (buy; premortem R1 updated) |
| RF-10 | Low | FREND1 was 0x56; TI DN022 gives 0xB6 for filters wider than 101 kHz (all profiles here) | 0xB6 | **Fixed (audit)** |
| RF-11 | Low | A manual SCAL with `delay(1)` (which can return before the 735 µs calibration ends) was redundant with autocalibration, and SRX was never retried | SCAL removed; `setMode()` re-strobes SRX if RX isn't reached within 20 ms | **Fixed (audit)** |
| RF-12 | Low | RSSI and MARCSTATE were read once (errata SWRZ020: they can change during the read) | Read until two reads agree. (A median RSSI per burst is left for the v2 app) | **Fixed (audit)** |
| RF-13 | Low | The MX-05V mode attached an interrupt to IO36, which floats when R9/R10/J3 aren't fitted | Compiled in only with `-DTPMS_MX05V` | **Fixed (audit)** |
| RF-14 | Low | Documentation drift: the README register table (0x88 vs the firmware's 0x89, no FOCCFG/FREND1), stale `firmware/bringup` paths | Corrected | **Fixed (audit)** |
| RF-15 | Info | The EG53MA4's 8-bit sum only catches single-bit errors reliably; temperatures below 0 °F aren't tested | Rely on the learned-ID whitelist in the app; check one cold morning | Accepted |
| RF-16 | Medium (v2) | **The TS-7's HDMI flat cable is a new noise source in the unit.** Added with the TS-7 redesign: an unshielded flat cable carries the TMDS data (~0.5 Gb/s per lane at 1024 × 600) and the pixel clock (~50 MHz). The data's spectrum is broadband, so some of it lands in the 315 MHz channel whatever the clock; a pixel-clock harmonic could land on it too | The design keeps them apart: the cable runs on the Pi's port side (+X), the CC1101's SMA strip is on the opposite edge, and the antenna leaves the box (R2). Buy a shielded flat cable if you can find one. In B6, with the cable in its final route, compare the noise floor with the display on and off; read the mode's pixel clock (`kmsprint`) and check that no harmonic falls within 315 ± 0.1 MHz. If the floor rises: a clip-on ferrite or grounded copper tape over the cable | Open (bench, B6) |

## Premortem: the TPMS radio failed. Why?

| # | How it fails | Likely | Impact | Prevention / detection | Status |
|---|---|---|---|---|---|
| RF-P1 | In the car the demodulator outputs constant noise and bursts never close: "nothing received" | Medium-High | No TPMS | RF-01 gating; watch the `edges` counter while no sensor sends | Open |
| RF-P2 | The rear wheels drop out | Medium | Missing rear readings | RF-09 315 MHz antenna out of the enclosure, away from the Pi; RSSI per wheel | Open |
| RF-P3 | The Pi 4, its USB 3, the TS-7's HDMI flat cable and the ~500 kHz regulators raise the noise floor (a 500 kHz comb line lands in the 203 kHz channel ~41 % of the time) | Medium-High | Range loss, more noise edges | Antenna on a 30 cm lead out of the box; ferrites; carrier-sense threshold above the floor; B6 with everything on and off (RF-16) | Open (B6) |
| RF-P4 | v2's Bluetooth or a flash write drops edges at the wrong moment | Medium | Sporadic misses | RF-07, RF-08; B8 compares decode rates with Bluetooth on and off | Open |
| RF-P5 | The radio silently leaves RX (failed SRX, brown-out) | Low | Silent TPMS | Periodic MARCSTATE check (double read); "not heard for N minutes" per wheel in the app | Open (app) |

## Before you move on

- Phase 0 (already the first build step): drive with `rtl_433 -f 315M`, log the four IDs.
- Bench with the real CC1101: watch the idle `edges` counter, dump raw pulses (`r`) next to `rtl_433`, then set the carrier-sense threshold (RF-01) before writing the v2 receiver.
- Buy a 315 MHz quarter-wave antenna (~23 cm).
