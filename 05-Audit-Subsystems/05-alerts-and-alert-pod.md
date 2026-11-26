# 05 · Alerts and the alert pod

**Scope:**
- `AlertArbiter` in [alerts.cpp](../02-firmware/v2/src/logic/alerts.cpp), which decides what the two amber LEDs and the buzzer do;
- the two amber door LEDs;
- the alert pod by the shifter: the inventory panel-mount mute button and a 12 V active piezo on one 4-wire lead.

**Maturity:** the arbiter is written and tested, with its rules strengthened by this audit. The buzzer player, the LED drivers and the pod hardware are designed but not built. The piezo isn't bought.

**Verdict: Watch.** Before the audit, several promises in the README weren't in the code:
- a camera fault never beeped;
- a flapping link beeped 15 times a minute;
- a TPMS beep could cut a danger beep;
- a tyre hovering at the threshold beeped 7 times a minute;
- a Pi that never booted stayed silent forever.

All of these are fixed and tested. What remains is physical: can you hear the piezo over the radio, and see the LEDs in the sun?

## What was verified

| Check | Evidence | Result |
|---|---|---|
| Danger beep cadence (1 ms loop) | Continuous danger: 3.0 s gaps. Detection flickering at 400 ms: at least 1.6 s between beeps | OK |
| Mute | Ignored without a turn signal; lasts one activation; a new activation beeps again | OK |
| TPMS acknowledge | Works with the Pi down; same tyre stays acknowledged; a new low tyre re-raises once | OK |
| Lamp test vs fault | Pi lost during the lamp test gives the fault pattern and one beep | OK |
| Faults (new tests) | Camera fault while running and from the first report; frozen vision loop (`seq` not moving); Pi powered 90 s and never ready; stuck blinker input; Pi link flapping (1.2 s gaps every 4 s for 60 s) | One fault beep per fault episode; the next only after 30 s without any fault |
| Priority over time (new tests) | Danger at t, TPMS at t+1 ms; TPMS at t, danger at t+1 ms | The TPMS pattern waits for the danger pattern to finish; a danger beep that cuts a TPMS beep has it replayed |
| LED level | Pi sends level 0 | Floored at 48/255 |
| Mutation | Removing any of the audit's alert fixes fails a test (10 of 10 alert mutants caught) | OK |

## Findings

| # | Severity | Finding | Fix | Status |
|---|---|---|---|---|
| ALR-01 | Medium | **A camera fault never beeped**, although the README and the header promised one: only a lost Pi link did. A camera that died mid-drive showed only the LED fault pattern | One fault beep whenever a side becomes faulted: camera, Pi link, blinker input or boot timeout | **Fixed (audit)** |
| ALR-02 | Medium | **"One fault beep" re-armed at every recovery**: a Pi reporting with 1.2 s gaps every 4 s gave 15 fault beeps a minute | Another fault beep only after 30 s without any fault (`faultRearmMs`) | **Fixed (audit)** |
| ALR-03 | Medium | **Priority held only within one update.** `Beep` meant "start this pattern now", so a TPMS beep 1 ms after a danger beep cut it off, and a TPMS beep cut off by a danger beep still counted as played (next reminder 10 min later) | The arbiter tracks the pattern playing and its length (danger 400 ms, fault 600 ms, TPMS 800 ms: `beepMs` in the output). Lower priorities wait; a higher one cuts, and the cut pattern is replayed | **Fixed (audit)**; the player must use the same lengths |
| ALR-04 | Medium | **A tyre hovering at the threshold beeped at every crossing** after acknowledge (7 beeps/min), and an alarm flag flapping on and off beeped every time | A tyre re-raises the alarm once per alarm; an alarm that clears and returns within 60 s is the same alarm. The caller should still apply per-wheel hysteresis | **Fixed (audit)** |
| ALR-05 | Medium | **A Pi that never becomes ready was silent forever** (a dead SD card): the fault pattern only appeared after the Pi had been ready once | The app tells the arbiter when the Pi's rail is on (`piPower`); not ready 90 s later is a fault on both sides plus one beep | **Fixed (audit)** |
| ALR-06 | Medium | **A frozen vision loop looked healthy**: if the detector hangs but the reporting thread keeps sending `ready = 1`, the LEDs show "all clear". `seq` was parsed but never checked | `seq` is now defined as the vision frame counter; a report whose `seq` hasn't moved doesn't refresh the link, so after 1 s it is a fault ([LNK-01](07-esp32-pi-link.md)) | **Fixed (audit)**; Pi side must send the frame counter |
| ALR-07 | Low | LED level 0 from the Pi made the danger flash and the fault pattern invisible | Level floored at 48/255 | **Fixed (audit)** |
| ALR-08 | Medium | **Nobody has heard the piezo in the car.** The enclosure README says a beep from the console "is clearly audible", but that's unverified, with music, road noise or the fan on | Bench, then in the car: radio at your normal volume, windows up and down at 70 mph. Pick the piezo by its rated SPL (≥ 85 dB at 30 cm). The pod is by the shifter, close to you, which helps | Open (bench + car) |
| ALR-09 | Medium | **The amber LEDs in daylight and at night are unproven.** A 5 mm amber LED in the door sail must be seen in peripheral vision in the sun, without glaring at night | Mock it up before drilling the trim: a 5 mm LED behind a bezel, checked from the driver's seat in sun and dark. The Pi's level and the 48/255 floor set the night brightness | Open (mock-up) |
| ALR-10 | Low | The mute button lead is ~0.8 m to GPIO4 with no ESD part ([ESP-05](02-esp32-controller.md)) | TVS/ESD diode at the pod connector | Open (G7) |
| ALR-11 | Info | Inventory options: two DFRobot illuminated buttons (`proto-dfrobot-led-button`) could replace the plain mute button and show the system state (lit = armed, flashing = fault) at a glance. A DFPlayer Pro + cavity speaker (`sen-dfplayer-pro`, `sen-mini-cavity-speaker`) could speak "car on the left", but a voice is slower to react to than a sharp beep, and it needs the Pi or a free GPIO (none left) | Consider the lit button; keep the piezo for warnings | Optional |

## Premortem: the alerts failed. Why?

| # | How it fails | Likely | Impact | Prevention / detection | Status |
|---|---|---|---|---|---|
| ALR-P1 | The Pi's link flaps on a hot day and the fault beep nags every few seconds; you unplug the buzzer | Was Medium | All warnings lost | ALR-02 | Fixed |
| ALR-P2 | A TPMS reminder cuts off a danger beep at the worst moment | Was Low | Missed warning | ALR-03 | Fixed |
| ALR-P3 | The beep isn't heard over the radio | Medium | Missed warning | ALR-08 test; a louder piezo; it beeps while the LED flashes, so there are two cues | Open |
| ALR-P4 | The LEDs wash out in the sun or dazzle at night | Medium | Ignored or annoying | ALR-09 mock-up | Open |
| ALR-P5 | The SD card dies, the Pi never boots, and the LEDs stay dark: "no cars" | Was Medium | False all-clear | ALR-05 | Fixed |
| ALR-P6 | The detector hangs while the reporting thread says "ready" | Was Medium | False all-clear | ALR-06 (Pi must send the frame counter) | Fixed (ESP32) / Open (Pi) |
| ALR-P7 | The buzzer player is written to interrupt every new pattern, undoing ALR-03 | Low | Priority lost | Player plays `beep` for `beepMs`, never interrupts on its own | Open (app) |

## Before you move on

- Buy the piezo by its rated sound level and test it over music.
- Mock up one door LED before drilling the trim.
- When writing the app: the buzzer player plays each pattern for `out.beepMs`; the Pi sends its vision frame counter as `seq`; call `piPower()` when the Pi's rail turns on.
