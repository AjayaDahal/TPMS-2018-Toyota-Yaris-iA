# 315 MHz RF Bench Test Log (ESP32 + E07-M1101D + USRP B205mini)

**Goal:** Verify on real hardware that the ESP32 DOIT DevKit V1 + EBYTE E07-M1101D (CC1101) receive chain can scan and decode 315 MHz ASK/OOK TPMS signals (`Schrader-EG53MA4`), using the Ettus USRP B205mini-i as a controlled simulated 315 MHz ASK/OOK transmitter, and gather bench measurements for open audit findings ([13-tpms-radio.md](../../05-Audit-Subsystems/13-tpms-radio.md), notably **RF-01** carrier-sense gating).

---

## 1. Hardware Under Test

| Role | Hardware | Notes |
|---|---|---|
| MCU | ESP32 DOIT DevKit V1 (30-pin) | Bench USB-powered (`115200` baud serial monitor) |
| 315 MHz RX | EBYTE E07-M1101D (TI CC1101, 2×4 2.54 mm header) | **3.3 V ONLY**; board silkscreen says 433 MHz (see Section 2) |
| Simulated TX | Ettus Research USRP B205mini-i | 315.000 MHz simulated CW & Schrader EG53MA4 ASK/OOK frames |

---

## 2. Note on Using a 433 MHz-Labeled E07-M1101D at 315 MHz

- **No manufacturer programmer tool is needed.** The E07-M1101D has **no onboard MCU, flash, or EEPROM** — it exposes the raw TI CC1101 SPI interface directly. All CC1101 registers are volatile and configured by the ESP32 over SPI on every boot.
- **315 MHz registers are already in firmware.** [`cc1101.cpp`](src/cc1101.cpp) and [`main.cpp`](src/main.cpp) already configure the TI SmartRF / DN022 315 MHz OOK profile (`OOK bw203k 16kBd`):
  - `FREQ2/1/0 = 0x0C / 0x1D / 0x8A` → `315,000,061 Hz` (with 26 MHz crystal)
  - `TEST0 = 0x0B` (enables VCO selection calibration needed below ~323 MHz, instead of 433 MHz's `0x09`)
  - `MDMCFG4/3/2 = 0x89 / 0x4B / 0x30` → 203.1 kHz RX filter, 16,415 Bd demodulator filter, OOK, DC filter on
  - `AGCCTRL2/1/0 = 0x03 / 0x00 / 0x91`, `FOCCFG = 0x14`, `FREND1 = 0xB6`, `MCSM0 = 0x18` (auto-cal IDLE → RX)
- **RF front-end note ([RF-09](../../05-Audit-Subsystems/13-tpms-radio.md)):** The CC1101 IC natively covers `300–348 MHz`. A 433 MHz TI reference matching network only costs ~0.2–0.5 dB at 315 MHz, whereas a 433 MHz whip antenna costs ~9.5–11.7 dB. Use a **~23 cm 315 MHz quarter-wave wire/whip antenna** on the E07-M1101D for best results. Tests T4–T5 will directly verify this specific board's 315 MHz sensitivity and RSSI.

---

## 3. ESP32 ↔ E07-M1101D Wiring Diagram

Pin assignments match both [`include/pins.h`](include/pins.h) (v1 bring-up) and [`../v2/include/pins_v2.h`](../v2/include/pins_v2.h) (v2 carrier).

### Connection Table

| E07-M1101D Pin # | E07 Signal | ESP32 DOIT DevKit V1 Pin | Function |
|---|---|---|---|
| **1** | `GND` | `GND` | Ground |
| **2** | `VCC` | `3V3` | **3.3 V power ONLY (NEVER 5 V / VIN)** |
| **3** | `GDO0` | `GPIO 34` | Asynchronous OOK demodulated data out (ESP32 input-only) |
| **4** | `CSN` | `GPIO 5` | VSPI Chip Select |
| **5** | `SCK` | `GPIO 18` | VSPI Clock |
| **6** | `MOSI` | `GPIO 23` | VSPI MOSI |
| **7** | `MISO` (`GDO1`) | `GPIO 19` | VSPI MISO / chip-ready (`SO`) |
| **8** | `GDO2` | `GPIO 35` | Carrier sense (ESP32 input-only) |

### Physical 2×4 Header Reference & Wiring Diagram

Per [`CC1101_E07-M1101D_Socket.kicad_mod`](../../01-hardware/lib/TPMS.pretty/CC1101_E07-M1101D_Socket.kicad_mod) and [`CC1101_2x4_Socket.kicad_mod`](../../01-hardware/v2/carrier/lib/TPMS2.pretty/CC1101_2x4_Socket.kicad_mod) (always verify against the silkscreen printed on your specific E07-M1101D PCB before applying power):

```text
  E07-M1101D (2x4 header, 2.54 mm)                   ESP32 DOIT DevKit V1 (30-pin)
  [SMA / Antenna edge]
    Pin 2: VCC  --- 3.3V ONLY! --------------------> 3V3
    Pin 4: CSN  -----------------------------------> GPIO 5  (VSPI CS)
    Pin 6: MOSI -----------------------------------> GPIO 23 (VSPI MOSI)
    Pin 8: GDO2 -----------------------------------> GPIO 35 (Carrier Sense)
  ----------------------------------
    Pin 1: GND  (square pad) ----------------------> GND
    Pin 3: GDO0 -----------------------------------> GPIO 34 (OOK Async Data)
    Pin 5: SCK  -----------------------------------> GPIO 18 (VSPI SCK)
    Pin 7: MISO -----------------------------------> GPIO 19 (VSPI MISO)
```

### Critical Bench & RF Safety Notes

1. **3.3 V ONLY on `VCC`:** Connecting E07 `VCC` to `VIN` / `5V` will permanently damage the CC1101.
2. **Verify physical silkscreen:** Some CC1101 breakout variants swap or mirror row labels—match each wire to the silkscreen name (`GND`, `VCC`, `GDO0`, `CSN`, `SCK`, `MOSI`, `MISO`, `GDO2`) on your physical module.
3. **Keep SPI jumpers short (< 10–15 cm):** Avoid long loose loops on `SCK`/`MOSI`/`MISO`/`CSN` (`4 MHz` SPI clock).
4. **Never cable B205mini TX directly to E07-M1101D RX without ≥ 40–50 dB external inline attenuation.** Use low-gain over-the-air (OTA) bench transmission with small antennas separated on the desk (CC1101 max RF input is +10 dBm; B205mini can output up to ~+10 dBm+).
5. **Bare-ESP32 firmware note (before flashing):** In [`src/main.cpp`](src/main.cpp) (lines 270–272, 288–289), `PIN_ENC_A` (`GPIO 16`), `PIN_ENC_B` (`GPIO 17`), and `PIN_ENC_SW` (`GPIO 4`) are configured as `INPUT` (relying on v1 PCB external pull-ups) with `CHANGE` interrupts on `16`/`17`. On a bare DevKit without the v1 PCB, floating `16`/`17`/`4` can trigger spurious profile changes (`mode` leaving Profile 0) or button events; we should add a bare-bench build flag (e.g. `INPUT_PULLUP` / disable floating-pin interrupts) before flashing.

---

## 4. Toolchain & Environment Status

| Component | Status | Version / Details |
|---|---|---|
| Git Repository | ✅ Synced | `origin/main` at `efd06c8`; prior WIP stashed in `stash@{0}` (`local-wip-before-pull-2026-11-26`) |
| PlatformIO CLI | ✅ Installed | `6.2.0` via `uv` (`~/.local/bin/pio`) |
| ESP32 Toolchain & Build | ✅ Verified | `espressif32@6.13.0` (`esp32doit-devkit-v1`, Arduino, `U8g2@^2.36.18`); `pio run` succeeded (`48.72 s`, RAM `13.1%` / `42904 B`, Flash `22.7%` / `298029 B`) |
| Bring-up Host Decoder Tests | ✅ Passed | `test_decode.cpp` → `all decoder tests passed` |
| v2 Host Logic Tests | ✅ Passed | `test_logic.cpp` → `all 166 v2 logic checks passed` |
| Linux Serial / USB Permissions | ✅ Ready | User `aj` is in `dialout` and `plugdev` groups; ESP32 detected on `/dev/ttyUSB0` (`10c4:ea60` CP210x) |
| UHD / USRP B205mini Driver | ✅ Installed (no HW plugged in yet) | `uhd-host` / `python3-uhd` `4.6.0.0+ds1-5.1ubuntu0.24.04.1`; `/usr/share/uhd/images/usrp_b205mini_fpga.bin` present. Run scripts with `python3 -s` so `python3-uhd` uses system NumPy `1.26.4` instead of `~/.local` NumPy `2.5.5`. `uhd_find_devices` currently reports `No UHD Devices Found`. |
| B205mini Simulated TX Script | ✅ Self-tested | [`tools/b205_sim_tpms.py`](tools/b205_sim_tpms.py) `--self-test` passed (`69794` samples, 2×120-bit EG53MA4 payload `058F2001123456584DF6`) |

---

## 5. Bench Test Plan & Checklist

| ID | Test | Pass Criteria | Status |
|---|---|---|---|
| **T1** | USB serial detection & bare-ESP32 bring-up flash | `/dev/ttyUSB*` or `/dev/ttyACM*` detected; bare-bench guard prevents floating-pin `mode` drift; firmware flashes & boots at `115200` baud | ✅ **PASS** (`/dev/ttyUSB0`, `bench-cc1101` flashed) |
| **T2** | CC1101 SPI bring-up & 315 MHz RX state | `PARTNUM 0x00`, `VERSION 0x14`/`0x04`/`0x17`/`0x03`, `MARCSTATE 0x0D` (RX) | ✅ **PASS** (`PARTNUM=0x00`, `VERSION=0x14` TI chip, `MARCSTATE=0x0D`, registers verified) |
| **T3** | Idle 315 MHz noise floor & edge rate | Baseline `noise floor` (dBm) and 10 s idle `edges` count recorded | ✅ **MEASURED** (noise floor `-87` to `-89 dBm`, `26572 edges / 10 s`, `163 bursts`, `dropped=0`, `GDO2=1` at idle) |
| **T4** | USRP B205mini detection & 315 MHz CW RSSI / GDO2 check | `uhd_find_devices` detects B205mini; low-power 315.000 MHz CW raises CC1101 `rssiDbm()` & `GDO2` on the 433 MHz-labeled E07 | ✅ **PASS** (user bench session: RSSI jumped from `-90 dBm` idle to `-73 dBm` peak during `25 dB` TX bursts on the 433 MHz-labeled E07) |
| **T5** | Simulated Schrader EG53MA4 ASK/OOK TX → E07 RX decode | B205mini transmits synthetic EG53MA4 frame (40-bit zero preamble + 80-bit payload, Manchester 123 µs half-bit); ESP32 decodes exact ID / pressure / temp / flags & logs RSSI sweep | ⚠️ **Partial (2/60 decodes pre-fix; ready for re-test)** — `ID 123456` decoded cleanly (`31.9 psi`, `77 F`, `-73 dBm`), other bursts fragmented by untimed UHD TX underflows; TX script fixed (`500 kS/s` timed). Re-test with the squelch on and off (Entry #5) |
| **T6** | Carrier-sense gating & noise rejection (**RF-01**) | Reduce idle noise bursts/edges without losing sensitivity | ✅ **IDLE VERIFIED** — hardware `AGCCTRL1/2` CS (`0x03/0x07`, `0x04/0x07`) stayed `GDO2=1` at `-91 dBm`; adaptive `noiseFloor + 6 dB` RSSI squelch gate dropped idle noise from `~27,842 edges / 10 s` (`162 bursts`) to **`80 edges / 10 s` (`1 burst`)** (`99.7%` reduction). ⚠️ Decoding with the gate on is untested, and the review changed its timing (40 ms hold, dithered 0.5–1 ms RSSI reads): re-test both halves (Entry #5) |

---

## 6. Test Log

### Entry #1 — 2026-11-26 (Environment Setup & Pre-Hardware Verification)
- **Git state:** Stashed pre-existing local edits (`stash@{0}: local-wip-before-pull-2026-11-26`) and fast-forwarded `main` from `e74b4f4` to `efd06c8`.
- **Toolchain setup:** Installed PlatformIO Core `6.2.0` (`uv tool install platformio`).
- **Pre-build (`02-firmware/bringup`):** `pio run` downloaded `espressif32@6.13.0` + `U8g2` and compiled cleanly (`SUCCESS` in `48.72 s`; RAM `42904 B` / `13.1%`, Flash `298029 B` / `22.7%`).
- **Host unit tests:**
  - `02-firmware/bringup/test/host/test_decode.cpp` → `all decoder tests passed`
  - `02-firmware/v2/test/host/test_logic.cpp` → `all 166 v2 logic checks passed`
- **Hardware check (`lsusb` / `/dev/tty*`):** No ESP32 USB-UART or USRP B205mini plugged in yet.
- **Next action:** User wires ESP32 ↔ E07-M1101D, runs the `sudo` UHD install command, and plugs in ESP32 + B205mini for Tests T1–T5.

### Entry #2 — 2026-11-26 (Bare-Bench Firmware Flash, T1–T3 Live CC1101 Bring-Up, B205mini TX Script)
- **Firmware changes:** Added `[env:bench-cc1101]` (`-DTPMS_BENCH_BARE`) in [`platformio.ini`](platformio.ini) and guarded OLED/encoder/LED/buzzer in [`src/main.cpp`](src/main.cpp) so floating breadboard pins (`GPIO 16/17/4`) cannot trigger spurious profile switches; added `'d'` serial register dump and `GDO2` status in the 10 s log. Both `esp32doit-devkit-v1` and `bench-cc1101` built cleanly (`0` warnings).
- **T1 (Flash & Boot):** Flashed `bench-cc1101` (`RAM 12.5%`, `Flash 21.6%`) to `/dev/ttyUSB0` (`CP210x 10c4:ea60`, `ESP32-D0WDQ6 v1.0`, MAC `7c:9e:bd:39:8a:70`).
- **T2 (CC1101 SPI & 315 MHz RX):** **PASS.** Live serial output:
  - `CC1101: PARTNUM 0x00 VERSION 0x14 -> TI chip OK`
  - `CC1101: state 0x0D (0x0D = RX), noise floor -89 dBm at 315 MHz`
  - `mode 0: OOK bw203k 16kBd  (CC1101 in RX)`
  - Register dump (`d`): `PARTNUM=0x00 VERSION=0x14 MARCSTATE=0x0D RSSI=-87 dBm GDO0=1 GDO2=1`, `FREQ=0x0C1D8A MDMCFG4/3/2=0x89/0x4B/0x30 AGCCTRL2/1/0=0x03/0x00/0x91 FOCCFG=0x14 FREND1=0xB6 TEST0=0x0B`
- **T3 (Idle Noise Floor & Edge Rate):**
  - `[10 s] bursts 163 frames 0, edges 26572 (noise), dropped 0, RSSI now -89 dBm, GDO2=1`
  - **Observation (validates RF-01):** At `-87` to `-89 dBm` ambient/bench noise floor, the default `AGCCTRL1=0x00` keeps `GDO2=1` continuously and generates `~2,657` noise edges/sec on `GDO0`.
- **UHD / B205mini status:** `uhd-host` + `python3-uhd` (`4.6.0.0`) and `usrp_b205mini_fpga.bin` are installed (`python3 -s -c "import uhd"` succeeds with system NumPy `1.26.4`). Created and self-tested [`tools/b205_sim_tpms.py`](tools/b205_sim_tpms.py) (`--self-test` passed). `uhd_find_devices` reported `No UHD Devices Found` (B205mini not plugged in yet).
- **Next action:** Plug in USRP B205mini (with 315 MHz / wideband TX antenna attached; do **not** cable directly into E07-M1101D) to run Tests T4–T6.

### Entry #3 — 2026-11-26 (B205mini Enumeration Drop & Live Viewer RF Bench Mode Added)
- **B205mini USB drop:** When starting automated T4/T5 sweeps, `b205_sim_tpms.py` failed with `No devices found for type: b200`; `lsusb` confirmed `2500:0022` disconnected from USB (after earlier enumerating on USB 2.0 `Bus 003`). Idle raw pulse dump (`r`) on the ESP32 showed a periodic `~1 ms` (`~930 µs / ~70 µs`) interference train matching the `-86` to `-89 dBm` floor with `GDO2=1`.
- **Viewer RF Bench mode (`5. RF Bench (TX/RX)`):** Added [`04-viewer/rf_bench_backend.py`](../../04-viewer/rf_bench_backend.py), `/api/rf/*` endpoints in [`04-viewer/serve_viewer.py`](../../04-viewer/serve_viewer.py), and [`04-viewer/viewer/rf_bench.js`](../../04-viewer/viewer/rf_bench.js) so the viewer displays live CC1101 RSSI/`GDO2`, TX-vs-RX packet tables with correlation badges, ASK/OOK Manchester waveform preview, CC1101 register state, and serial console.

### Entry #4 — 2026-11-26 (First Live 315 MHz OTA EG53MA4 Decodes, TX Fragmentation Root Cause, & RF-01 Adaptive RSSI Gate)
- **Live milestone (user viewer session):** First real over-the-air 315 MHz **Schrader EG53MA4** decodes on the 433 MHz-labeled E07-M1101D (`ID 123456`, `31.9 psi / 220.0 kPa`, `77 F / 25 C`, `flags 058F2001`, peak `RSSI -73 dBm`, matched TX #5 and TX #9).
- **Root cause of `2/60` (`3.3%`) decode rate & why `ABCDEF` / `2FC871` / `3495AC` failed intermittently:**
  - Verified all 4 payloads encode/decode identically in `eg53ma4` logic (`b205_sim_tpms.py --self-test` passed all 4 presets).
  - Bit-level inspection of the ESP32 `chips` dumps (`173.825 s`, `175.206 s`) showed the exact `2FC871` and `3495AC` payload chips arriving at `-73..-74 dBm`, **broken mid-frame into truncated fragments** (`48`, `133`, `167` chips < 100 bits) because `b205_sim_tpms.py` previously called untimed `tx_stream.send()` at `1 MS/s` without checking `n_sent` or scheduling `md.has_time_spec = True`, causing UHD USB underflows.
  - Meanwhile, ungated RF-01 idle noise kept `GDO2=1` and injected `~27,842 edges / 10 s` (`~162 bursts / 10 s`).
- **Fixes applied & verified:**
  1. [`tools/b205_sim_tpms.py`](tools/b205_sim_tpms.py): Reduced sample rate to `500 kS/s` (`--lo-offset 150 kHz`), added exact sample-boundary timing, `md.has_time_spec = True` (`+50 ms` FIFO pre-fill), checked `tx_stream.send()` partial return counts, and added `TXAsyncMetadata` underflow checking. `--self-test` passed for all 4 presets.
  2. **RF-01 hardware CS test:** Tested `AGCCTRL2/1 = 0x03/0x07` and `0x04/0x07` with `GDO2` gating; CC1101 `GDO2` still asserted `1` at `-91 dBm` (`26,054 edges / 10 s`).
  3. **RF-01 adaptive RSSI squelch gate** ([`src/rf.h`](src/rf.h), [`src/rf_capture.cpp`](src/rf_capture.cpp), [`src/main.cpp`](src/main.cpp)): Restored TI DN022 `AGCCTRL2/1/0 = 0x03/0x00/0x91` for full sensitivity and gated `onEdge()` in `rf_capture.cpp` whenever `liveRssi >= noiseFloor + 6 dB` (`5 ms` holdover across gaps). Idle noise dropped from `~27,842 edges / 10 s` (`162 bursts`) to **`80 edges / 10 s` (`1 burst`)** (`floor=-90 dBm`, `gate=0`).
  4. [`04-viewer/viewer/index.html`](../../04-viewer/viewer/index.html): Raised default B205mini TX gain slider from `25` to `35 dB`.
- **Next action:** Hard-refresh the viewer (`http://127.0.0.1:28778/viewer/`), ensure the B205mini is connected on USB 3.0, and re-test all 4 presets (`FL 123456`, `FR ABCDEF`, `RL 2FC871`, `RR 3495AC`).

### Entry #5 — 2026-11-27 (Review: the Squelch Could Cut Frames, the RF Bench API Was Open to Other Web Pages; A/B Tooling)
- **Reviewed:** commits `714ff24` and `516cfd7` (bench env, B205mini tools, viewer RF Bench, timed TX fix, RF-01 squelch) against T1–T6 above. The bench work holds up: T1–T4 are clean, the T5 fragments are explained by the USRP underflows, and the squelch's idle result is real. Two problems found, both fixed:
- **1. The squelch could cut frames ([RF-17](../../05-Audit-Subsystems/13-tpms-radio.md)).** The gate read the RSSI every 2–3 ms (`millis()` ≥ 2 in `loop()`) and stayed open only 5 ms past the last reading above `floor + 6 dB`.
  - A Manchester OOK frame is "on" for half its chips, so a reading that lands on an "off" chip can return the noise floor.
  - A fixed reading period also stays in step with the preamble's 123 µs chips: 1 ms is ~8 chips, so the readings keep landing on the same chip phase.
  - The gate then shuts mid-frame, and the dropped edges break the pulse/gap alternation. T6 measured idle noise only, so this couldn't show yet.
  - Simulated worst case, 4,000 frames per cell. The RSSI follows the chip envelope, and a frame counts only if the gate opens within its first 20 preamble bits (what [`eg53ma4.cpp`](src/eg53ma4.cpp) tolerates) and then stays open:

    | RSSI read every | Hold 5 ms | Hold 40 ms | Hold 40 ms, sensor chips 118 / 128 µs |
    |---|---|---|---|
    | 2–3 ms (as benched) | 2.5 % | 69 % | 83 / 67 % |
    | 1–2 ms | 9 % | 84 % | 98 / 65 % |
    | 0.5–1 ms, dithered (**now**) | 77 % | **98 %** | 98 / 99 % |

    With dithered reads, a 10 ms hold already gives 98 % and 20 ms 98 %. The remaining 2 % are gates that open after the 20th preamble bit.
  - If the CC1101's RSSI averages over a few chips instead, the gate never sees the "off" chips and every row passes. That is likely at −73 dBm, where a 50 % duty frame still reads ~13 dB over the floor. The A/B re-test below shows which case the hardware is.
  - **Fix:**
    - [`src/rf_capture.cpp`](src/rf_capture.cpp): `kGateHoldUs` from 5 ms to **40 ms**, longer than a ~30 ms frame. A frame that opens the gate in its preamble then passes whole, whatever its RSSI does.
    - [`src/main.cpp`](src/main.cpp): the RSSI is read every **0.5–1 ms with a random interval** (`micros()`), so the reads can't stay in step with the chips.
    - New key **`g`**: squelch on/off (on after reset). The 10 s stats line ends with `squelch=on|off`.
    - The noise-floor estimate and the +6 dB threshold are unchanged.
  - **The cost, to measure:**
    - Each spurious opening now lets in up to 40 ms of noise (~100 edges), and the RSSI is read about twice as often. Expect more idle edges than the first version's 80 / 10 s; the target is still a large cut from ~27,800.
    - If it lets in too much, drop `kGateHoldUs` to 20 ms (still 98 % in the simulation above).
  - **Built (PlatformIO 6.2.0, espressif32 6.13.0, 0 warnings):** `bench-cc1101` RAM 12.6 % (41,180 B) / Flash 21.7 % (284,809 B); `esp32doit-devkit-v1` RAM 13.1 % (43,060 B) / Flash 22.9 % (300,053 B).
- **2. Any web page could drive the bench ([VW-22](../../05-Audit-Subsystems/15-viewer-and-tooling.md)).**
  - The `/api/rf/*` POSTs checked only the `Host` header and parsed the body as JSON whatever its type.
  - While the viewer ran, a page in another browser tab could send a "simple" cross-site POST (`text/plain`, no CORS preflight). That could start the B205mini transmitting at up to 55 dB gain, or send keys and reset pulses to the ESP32.
  - **Fix in [`serve_viewer.py`](../../04-viewer/serve_viewer.py):**
    - POSTs must be `Content-Type: application/json` (415 otherwise). A cross-site JSON POST needs a CORS preflight, which the server never grants.
    - POSTs that carry an `Origin` must come from the viewer's own address (403 otherwise).
    - A non-integer baud or a non-object body returns 400 instead of a traceback.
  - **Verified:** 17 HTTP probes passed, and in the browser the RF Bench tab's own buttons still work.
- **A/B tooling for the re-test:**
  - **Viewer:** the RF Bench tab has a **Toggle Squelch (g)** button, and the Demod Activity card shows `squelch on/off`. The backend now passes `g` through and parses the state.
  - [`tools/run_bench_tests.py`](tools/run_bench_tests.py) `--squelch on|off|both` sets the squelch with `g` before the idle check and T5. `both` runs the pair twice.
  - The idle check now prints the edge rate per second, taken between two 10 s stats lines (the `edges` counter is cumulative since boot).
- **Re-test (T5b / T6b), on your Linux bench:**
  1. Flash: `pio run -d 02-firmware/bringup -e bench-cc1101 -t upload`. The boot banner's key list should include `g = squelch on/off`.
  2. Keep the B205mini over the air at ≥ 40–50 dB separation. Use a 315 MHz quarter-wave (~23 cm) on the E07 if you have one (RF-09).
  3. In `02-firmware/bringup`, run `python3 tools/run_bench_tests.py --idle-sec 25 --t5 --squelch both`.
  4. **Pass:** with the squelch on, T5 decodes as many frames as with it off (within 1 per 10) at every gain that decodes. Idle edges/s with it on should be ≥ 90 % below the off run.
  5. In the viewer, with the squelch on, send all 4 presets (`123456`, `ABCDEF`, `2FC871`, `3495AC`) at 35 dB. Each should show a matched RX.
  6. **If decodes drop with the squelch on:** watch the RSSI during frames (`d` dumps). Try a +4 dB threshold before anything else.
  7. **If idle noise is too high:** shorten the hold to 20 ms.
  8. Then port the gate, as tuned, to the v2 receiver (RF-01).
