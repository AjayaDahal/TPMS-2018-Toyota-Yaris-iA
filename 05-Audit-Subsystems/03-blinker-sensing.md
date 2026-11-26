# 03 · Blinker sensing

**Scope:** how the system knows you are signalling:
- the two lamp taps and their PC817 opto inputs (2 × 1.1 kΩ + 1N4148 per side, polled on GPIO36/39);
- `BlinkerDetector` in [blinker.cpp](../02-firmware/v2/src/logic/blinker.cpp), which turns the two raw inputs into off / left / right / hazard plus an input-fault mask.

Why lamp taps and not OBD-II is settled in the premortem ([O1](../00-project-management/PREMORTEM_v2.md#obd-ii-dongle-optional-speed-source)).

**Maturity:** logic written and tested on a PC (now part of 154 checks, plus a 13,622-case stress sweep run for this audit). The opto circuit is a prose design. The tap point on this car isn't found yet (G9).

**Verdict: Watch** (it was **Act** before the audit's fixes). The audit found a critical bug: hazards pressed during a turn signal could read as a turn to the *other* side, and sound a danger beep for that lane. Two high-severity bugs came with it. All three are fixed and covered by tests. What's left needs the car: where to tap, and what the lamps look like on a scope.

## What was verified

| Check | Evidence | Result |
|---|---|---|
| Flash rates and duty | Independent review: 60–240 flashes/min (bulb-out fast flash included), 30–70 % duty, polled at exactly 1 kHz and at random 0.5–3 ms: 190 runs | Turn reported within 150 ms, one activation, released within 925 ms of the last flash |
| Lamp PWM from the body control module | 40–400 Hz at 30–90 % duty, 10 phases, both polling modes: 1,320 runs | 0 failures |
| Hazards pressed during a turn signal (the critical case) | Audit stress sweep: the other lamp joining at **every millisecond** of two flash periods, at 185, 333 and 500 ms flashes; the body control module restarting both lamps at every millisecond | Never reads as the other side; hazard always found. Before the fix: 4 of 18 press times read as the other side |
| Quick left → right (and back) | Every millisecond of a flash period, both directions, three flash rates | Never hazard; the new side within 150 ms of its first flash. Before: 5 of 12 switch points read as hazard, with the right warning up to 1.5 s late |
| Hazard skew | 0–150 ms between the sides (0–100 ms at the fast flash), either side first | Never a single side |
| Irregular polling | 300 turns and 300 hazards at random 1–3 ms steps | Correct |
| Stuck-lit input | Left input lit for 11 s | Flagged after 1.5 s, treated as dark, a right turn then reads as right; the fault clears 2 s after the input goes dark |
| `millis()` wrap | Hazards and a spike placed across the 49.7-day wrap | Correct (only reachable with power on for 49 days: ACC-only power restarts it every drive) |
| Load on the lamp circuit | ~6 mA per input at 13.5 V (premortem I4) | Too small to trigger bulb-out fast flash |
| Mutation | 16 of 17 mutants of the audit's fixes caught. The survivor, a wrap-unsafe timestamp comparison, only moves the hazard onset by a few ms | OK |

## Findings

| # | Severity | Finding | Fix | Status |
|---|---|---|---|---|
| BLK-01 | Critical | **Hazards during a turn signal read as a turn to the other side.** Hazards were "both sides switched on within 150 ms". When you are signalling right and press the hazards, the left lamp may join in the middle of the right lamp's flash. The right side then has no new rising edge, the left is the most recent, and it was reported as a left turn. With the left lane occupied: a danger beep for a lane you aren't moving into, for example when pulling onto the shoulder | Hazard = **both lamps lit at the same time for 50 ms**: a turn signal never lights both sides. A side is reported only 150 ms after its lamp edge and while the other lamp is dark. The 50 ms equals the debounce, so a lamp that joins in the last milliseconds of the other's flash is a hazard as soon as it is long enough to count at all | **Fixed (audit)**, tested |
| BLK-02 | High | **A quick left → right change read as hazards.** Switching within 150 ms of a left flash starting made both sides "switch on within 150 ms": hazard, then a 900 ms hold-off, then the right turn **1.5 s late**, in exactly the situation where the right-side warning matters | Same overlap rule. The old lamp's bridged tail overlaps the new one by at most 25 ms, under the 50 ms threshold | **Fixed (audit)**, tested |
| BLK-03 | High | **An input stuck lit gave a permanent turn and no fault.** A failed opto, a shorted input, a broken pull-up or the wrong wire read as signalling forever: danger beeps whenever that lane was occupied, and hazards read as a turn | A lamp lit for more than 1.5 s without a break is an input fault (normal flashes are ≤ 0.5 s). That side counts as dark, shows the fault pattern, gives one fault beep, and danger beeps stop until it clears: with one side stuck, hazards and turns can't be told apart (`faultMask()` → [alerts](05-alerts-and-alert-pod.md)) | **Fixed (audit)**, tested |
| BLK-04 | Medium | The hazard window was effectively 100 ms, not 150: it was timed from the lamp edge, but the other side's edge was only seen after its 50 ms debounce. Skews of 110–150 ms gave a brief single side | The new rule watches the bridged lamp level, which is known at once | **Fixed (audit)**, tested |
| BLK-05 | Medium | **Which wire to tap isn't decided (G9).** The facts review settled the options. The car has **LED turn-signal repeaters in both mirrors**, standard (Toyota's MY2017/2018 feature pages; the owner's manual lists the side turn lights as LED). The rear turn lamps are separate **amber WY21W** bulbs, not shared with the brake lamps, so the trunk fallback works too | **Tap each mirror's repeater feed in the door harness** (left mirror = left signal), at the mirror connector. It is on the path the camera cable and the LED pair already take through the door boot, so it adds one 22 AWG pair per side and no kick-panel hunt. Confirm the wire with the wiring diagram and a meter: flashing 12 V with that side's signal and with the hazards, dead otherwise. The stuck-input fault (BLK-03) still catches a wrong wire | Open (you, G9) |
| BLK-06 | Medium | **A dead input (opto open, wire cut) is silent:** it looks exactly like "not signalling", so the danger beep never comes for that side | After install, and once a month: signal each way with the system on; the camera view must switch to that side (the Pi shows the turn state). Add it to the install checklist | Open (you, procedure) |
| BLK-07 | Low | A lit pulse must last at least one poll (1 ms) to be seen. At low duty (≤ 10 %) and 200–400 Hz lamp PWM, 1 kHz polling can miss it entirely. The header used to say "poll at 4× the PWM frequency", which isn't enough | Doc corrected. Scope the real lamp feed on the bench. If it is PWM at low duty, raise the opto's RC so it stretches the pulses | Open (bench) |
| BLK-08 | Low | A lit pulse of 27 ms already counts (25 ms of PWM bridge + 50 ms debounce); the README said 50 ms | README corrected | **Fixed (audit)** |
| BLK-09 | Info | The opto LED current falls with the battery voltage: ~6 mA at 13.5 V, ~3.5 mA at 9 V. A PC817 (CTR ≥ 50 % at 5 mA) still pulls the input low through its pull-up at 3.5 mA | Check the input switches at 9 V on the bench (B1) | Open (bench) |

## Premortem: the blinker sensing failed. Why?

| # | How it fails | Likely | Impact | Prevention / detection | Status |
|---|---|---|---|---|---|
| BLK-P1 | You pull onto the shoulder, signal right, press the hazards, and it beeps for the left lane; you switch the buzzer off for good | Was High | Real warnings ignored | BLK-01 | Fixed |
| BLK-P2 | A quick lane change left then right: the warning for the right comes 1.5 s late | Was Medium | Missed warning | BLK-02 | Fixed |
| BLK-P3 | The tap is on the wrong wire (a parking lamp, the brake circuit), so the input lights steadily or with the brakes | Low now | Nuisance beeps, faults | BLK-05: the mirror repeater feed, metered; BLK-03 flags a wire lit for over 1.5 s | Open (G9) |
| BLK-P4 | A crimp or T-tap corrodes and one input goes dead; nobody notices for months | Medium | Silent loss of one side's beep | BLK-06 monthly check; solder + heat-shrink, not T-taps | Open (procedure) |
| BLK-P5 | The body control module drives LED lamps with low-duty PWM that the 1 kHz poll misses | Low | No turn detected | BLK-07 scope check; RC stretch | Open (bench) |
| BLK-P6 | A load dump or jump start burns the opto resistors | Low | Input dead | 2 × 1.1 kΩ 1206 in series (0.5 W), 1N4148 reverse diode (P11) | Fixed (design) |

## Before you move on

- Find the tap point with the wiring diagram and a meter (G9): each mirror's LED repeater feed in the door is the first choice.
- Put a scope or a cheap logic analyser on the feed while signalling: PWM or not, duty, frequency.
- After install: signal left, right and hazards with the system on. The camera view must follow, and hazards must stay silent.
