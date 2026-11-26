# 14 · v1 TPMS panel (189 × 128 mm)

**Scope:** the orderable v1 board: KiCad project, Gerbers, BOM, fit in the console opening, protection front end. Also the bring-up firmware outside the radio (encoder, button, SPI sharing, self-test). The radio itself is in [TPMS radio](13-tpms-radio.md).

**Maturity:** complete and orderable: ERC 0, DRC 0, Gerbers generated and checked.

**Verdict: Watch.** The fabrication data is sound and current. The independent review re-derived everything:
- KiCad 10.0.7 reproduces ERC 0, DRC 0, 0 unconnected and 0 parity errors;
- the order zip is byte-identical to a fresh export;
- the outline is exactly 189.000 × 128.000 mm;
- all 20 firmware GPIOs match the netlist.

Nothing Critical or High was found. One thermal claim was wrong: the regulator's heatsink pour is cut by a track, so fix it before ordering if you order v1 at all. In v2, the 7" display takes the console opening ([PREMORTEM_v2](../00-project-management/PREMORTEM_v2.md#short-answer)), so v1 is for Option B or a TPMS-only first step.

## What was verified

| Check | Evidence | Result |
|---|---|---|
| ERC / DRC | `kicad-cli` with all severities, schematic parity, and again after a zone refill: 0 / 0 / 0 unconnected / 0 parity. With the 15 "ignored" checks re-enabled, only library-table lookups, the documented A1-under-U2 courtyard overlap and footprint-filter notes appear | OK |
| Gerbers | All 14 zip members byte-equal to `03-manufacturing/production/gerbers`; a re-export with the build script's flags differs only in date lines. Copper, masks, silk, paste, outline, PTH/NPTH drills, drill maps, job file; vias tented | OK |
| Outline and fit | Edge cuts 189.000 × 128.000 mm (121.000 at the bottom); side gaps 0.97–1.22 mm in the 191/123 × 129 mm opening, still ≥ 0.77 mm with JLCPCB's ±0.2 mm routing tolerance; every courtyard inside the outline | OK |
| USB passthrough holes | Ø25.800 mm at ±40.40 mm; Ø38 mm parts-free circles; nearest track 18.48 mm from the centre | OK (but see V1-08) |
| JLCPCB limits (fetched) | Min drill 0.30 mm, min track 0.187 mm, clearance ≥ 0.20 mm, PTH ring ≥ 0.25 mm, edge clearance 0.4 mm | OK (see V1-09) |
| Netlist and BOM | 54 footprints, 46 nets; `design.py` vs PCB: 168 pins, values, footprints and DNP flags, 0 mismatches; BOM vs PCB 54/54 | OK |
| Pin map | `pins.h` matches the A1 pad nets for all 20 GPIOs; no ADC2 pin read as analog; strapping pins idle correctly | OK |
| Power front end | TSR 1-2450 6.5–36 V with C1 47 µF/50 V (TRACO needs 22 µF/50 V above 32 V); SMAJ22CA clamps at 35.5 V, so U3 sees ≤ 35.1 V; SS34 blocks reverse polarity; all polarities correct | OK |
| OLED | NHD datasheet rev 6: pinout, 4-wire SPI straps, 345 mA typ / 375 mA max, holes on 77 × 42.5 mm | OK |
| Shared SPI and encoder interrupt | Both chip selects high before `SPI.begin`; both drivers use SPI transactions; the encoder ISR is IRAM, volatile, and its state table ignores bounce | OK |

## Findings

| # | Severity | Finding | Fix | Status |
|---|---|---|---|---|
| V1-01 | Medium | **U4's heatsink pour is 31.9 mm², not 124 mm².** The pour outline is 135 mm², but the +5V track from U4 pin 3 to the DevKit's VIN splits it, and island removal deletes the rest. At 0.67 W (full-white OLED) that is close to the ~110 °C/W of no pour: about a 70 °C rise | Add a track keep-out over the pour before routing in `build_tpms_panel.py`, rebuild, and check the fill is ≥ 120 mm². Until then keep the UI dark (few lit pixels). The design audit and the v1 premortem now say so | Open (before ordering v1) |
| V1-02 | Medium | A 35 V suppressed load dump lasting 0.1–0.4 s puts 5–50 J into the 400 W SMAJ22CA (~0.6 J rated): it shorts, the PTC trips, the panel goes dark. A 24–28 V jump start is similar | v1.1: a 60 V front end (surge stopper or SMCJ + a 40–60 V buck). The fused ACC tap limits the damage | Accepted |
| V1-03 | Medium | **The build can overwrite the order zip without a passing DRC.** It exports before it reports the DRC result, and with `--no-route` it still writes `tpms_panel_gerbers_jlcpcb.zip` from an unrouted board | Export to `build/` and copy to `production/` only when the DRC has 0 errors, 0 unconnected and the board is routed; otherwise name the zip `_DRAFT`. Until then the v1 README tells you to check the last build's DRC line before uploading | Open (code) |
| V1-04 | Medium | The build folder with local paths wasn't git-ignored ([PRJ-01](17-project-and-repo.md)) | `build/` ignored everywhere | **Fixed (audit)** |
| V1-05 | Low | The PTC derating quoted (0.49 A at 70 °C, 0.43 A at 85 °C) is for the MF-MSMF075/24, not the ordered /24X: 0.45 A at 70 °C and **0.37 A at 85 °C, equal to the 0.37 A worst-case input** | Text corrected in the design audit. For margin, MF-MSMF110/24X (0.61 A at 85 °C); change `design.py` and the BOM with the next rebuild | Open (next rebuild) |
| V1-06 | Low | Stale paths after the reorganization (`hardware\scripts\…`, `production/…`, `firmware/bringup`) | Corrected in the READMEs and source comments | **Fixed (audit)** |
| V1-07 | Low | The design audit said the minimum track is 0.25 mm; one BUZ_C segment is 0.187 mm (still far above JLCPCB's 0.10 mm) | Text corrected | **Fixed (audit)** |
| V1-08 | Low | The README said the USB holes are copper-free to Ø30 mm; the back GND pour reaches Ø26.6 mm | Text corrected: file to Ø26.4 mm at most | **Fixed (audit)** |
| V1-09 | Low | The EC11's plated mounting slots are 1.5 × 2.8 mm (length/width 1.87), below JLCPCB's "length ≥ 2 × width" | Lengthen to 3.0 mm, or expect an engineering query from JLCPCB | Open (next rebuild) |
| V1-10 | Low | The BOM is underspecified: "5 mm LED" (220 Ω only suits red, amber or yellow) and an EC11 without pulses/detents (the firmware assumes 4 counts per click) | Specify the LED colour and a 20-pulse / 20-detent EC11 part number | Open (BOM) |
| V1-11 | Low | Wiggling the knob at a detent (4 → 3 → 4 counts) stepped the profile twice, reconfiguring the radio each time | One step per full detent with hysteresis | **Fixed (audit)** |
| V1-12 | Low | Button bounce on release counted as a second press (extra beep) | 20 ms stable level on both edges | **Fixed (audit)** |
| V1-13 | Low | One knob step backwards from boot selected the MX-05V mode and attached an interrupt to the floating IO36 | Mode compiled in only with `-DTPMS_MX05V` ([RF-13](13-tpms-radio.md)) | **Fixed (audit)** |
| V1-14 | Low | `sexpr.py` unescapes `\n` before `\\`, so `"C:\\new"` round-trips wrong | One-pass unescape; no current KiCad string contains such a sequence, so the board isn't affected | Open (code) |
| V1-15 | Info | Depth behind the panel quoted as 16 and 17 mm; the self-test can't check the OLED, LEDs or buzzer itself (it shows and lets you look); timer deadlines misbehave after 49.7 days of uptime (unreachable with ACC power) | Depth aligned (16–17 mm) | Fixed (text) / Accepted |

## Premortem: the v1 panel failed. Why?

| # | How it fails | Likely | Impact | Prevention / detection | Status |
|---|---|---|---|---|---|
| V1-P1 | Summer plus a bright screen: U4 nears 125 °C, 3V3 sags, the display or radio drops out | Medium | Dropouts | V1-01; a 15-minute full-white test measuring the U4 tab | Open |
| V1-P2 | A rebuild with a failed DRC (or `--no-route`) replaces the order zip, and that zip is uploaded | Low | Unusable boards | V1-03; check the last build's DRC line first | Open |
| V1-P3 | The CC1101 or the DevKit is plugged in rotated 180° (DevKit VIN then lands on IO23) | Medium | Dead ESP32 or radio | Silk markers; a paint dot; first power-up without modules (v1 premortem) | Open (you) |
| V1-P4 | Vibration loosens the sockets; trimmed socket pins chafe the OLED's flex | Medium | Resets, dead display | Machined sockets or solder the DevKit; RTV; Kapton over the pin stubs | Open (assembly) |
| V1-P5 | The wrong EC11 or LED variant is bought | Medium | Knob steps every 2 clicks; dim LEDs | V1-10 | Open |
| V1-P6 | The shifter in P hits a cable in the right USB socket | Medium | Damaged cable | Check in the car; 90° plug | Open (you) |

## Before you move on

- If v1 will be ordered: fix V1-01 in the build script first, rebuild, re-run the checks, and look at the DRC line before uploading (V1-03).
- Confirm the E07-M1101D's pin-1 corner against its SMA end before soldering U1's socket.
