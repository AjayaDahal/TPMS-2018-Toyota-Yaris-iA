# 16 · Safety and legal

**Scope:** what could hurt someone or break a rule:
- over-reliance and silent failures;
- distraction and the screen rules;
- the windshield view;
- airbags and crash retention;
- the alert lights;
- radio rules;
- the OBD port as an attack path;
- electrical fire;
- privacy.

California law is used as the example (Vehicle Code, "VC"); check your own state's rules.

**Maturity:** the rules are designed in (alert logic, routes, mount, receive-only radio); the user interface that must follow them isn't written.

**Verdict: Watch.** Nothing found is unsafe by design, and the main legal question has a clear answer: a camera view for manoeuvring and a TPMS readout are both exempt from California's screen ban. The real risk is human: trusting an untested aid. Treat it as an extra pair of eyes until a month of logged drives shows how often it misses and false-alarms.

## What was verified

| Check | Evidence | Result |
|---|---|---|
| Screen visible to the driver | VC 27602(a) bans a screen showing video "that produces entertainment or business applications" ahead of the driver's seat or visible to the driver. It exempts (b)(1) "a vehicle information display" and (b)(4) "a visual display used to enhance or supplement the driver's view … to the sides of a motor vehicle for the purpose of maneuvering" (text read from the code) | TPMS page: (b)(1). Camera view: (b)(4). No entertainment video |
| Windshield view | VC 26708(a)(2): nothing "in or upon the vehicle that obstructs or reduces the driver's clear view through the windshield"; (a)(1): nothing on the glass outside the corner squares of (b) | Option A (console) clear; Option B must stay below the sight line (SAF-05); GPS puck on the dash, not the glass |
| Alert lights | VC 25950(b): light visible from the rear must be red, except turn signals, backup lamps and a few others | LEDs inside the cabin only (SAF-08, now in the plan) |
| Radio | The CC1101 only receives: the firmware sends only the SRES, SIDLE and SRX strobes and never STX, and reads the status registers with the burst bit (without it, reading MARCSTATE at 0x35 would *be* the STX strobe). The ESP32 module and the Pi have their own certified radios. Home-built, not marketed, ≤ 5 units: no FCC authorization needed (47 CFR 15.23), but it must not cause harmful interference (15.5) | OK |
| Airbag keep-outs | Curtain airbags confirmed; every route avoids the A-pillar, the roof rail, the knee area and the SRS harness ([vehicle](12-vehicle-integration.md)) | OK |
| Silent failures | Faults now light the fault pattern and beep once: lost or frozen Pi link, a camera fault (missing until this audit, FW-06), a stuck blinker input, a Pi that never boots ([alerts](05-alerts-and-alert-pod.md)) | OK (firmware, tested) |

## Findings

| # | Severity | Finding | Fix | Status |
|---|---|---|---|---|
| SAF-01 | High | **Trusting an untested aid.** It isn't tested against anything: no measured miss rate, no false-alarm rate. Motorcycles at night, a car arriving fast from behind, a mis-aimed camera, and a summer-throttled Pi (2 detections a second) all miss. The zone and its purpose resemble a Type I (blind-spot) lane-change aid in ISO 17387, but none of that standard's tests have been done | An aid, never a replacement: shoulder checks stay. A disclaimer on the start screen (S3). For the first month, run it with the buzzer muted, log every alert, and compare with what you see; switch the buzzer on when the misses and false alarms are known | Open (you + Pi app) |
| SAF-02 | Medium | **A failure that looks like "all clear".** The dangerous state is a dark LED that means "broken", not "empty" | Fault pattern and one beep for every detected failure (S4, [ALR](05-alerts-and-alert-pod.md)); dead blinker inputs can't be detected, so a monthly blinker check ([BLK-06](03-blinker-sensing.md)) | Fixed (firmware) + you |
| SAF-03 | Medium | **Distraction.** The screen sits below the line of sight; anything that pulls your eyes there for more than a glance costs more than it gives. NHTSA's voluntary guidelines for in-car displays use glances of 2 s and 12 s per task as limits | The primary alerts are the LED by the mirror (where you look anyway) and the beep. The screen shows a camera only with the blinker or a danger; nothing needs touch while moving; the beeps stop by themselves (a danger episode after 4 s, [ALR-12](05-alerts-and-alert-pod.md)), so you never reach for a mute (D5, [DSP-09](09-display-and-ui.md)) | Fixed (design) + Open (UI) |
| SAF-04 | Low | **Screen rules differ by state.** California's exemptions are above; other states have their own | Keep the screen to vehicle information and the manoeuvring view while moving (D6); no video playback or browsing | Accepted |
| SAF-05 | Medium | **Option B on the dash top can block the windshield view** (VC 26708(a)(2)), sits in direct sun (the display's ratings, [DSP-07](09-display-and-ui.md)) and may be close to the passenger airbag door | Prefer Option A, the console. If B: below the sight line over the hood, clear of the passenger airbag door, quick-release for heat waves | Open (G5) |
| SAF-06 | Medium | **Airbags.** Curtain airbags run behind the A-pillar trim and the roof rail; the passenger airbag opens through the dash top | No cables, LEDs or mounts there; never splice the yellow SRS harness ([VEH-03](12-vehicle-integration.md)) | Fixed (design) + you |
| SAF-07 | Medium | **The unit in a crash.** Roughly 0.6 kg (estimate) beside the front occupants' knees: tape or a friction fit lets it fly | Bolted to the car through the AMPS pattern or a bracket ([ENC-07](10-enclosure-and-thermal.md)); the display hangs on its own M3 holes, not the glass (M4) | Open (bracket) |
| SAF-08 | Low | **The LEDs were allowed on the mirror housing.** Outside the car, an amber light seen from behind isn't a permitted colour (VC 25950(b)); it would also take water and sun | Inner door sail only, inside the cabin, facing the driver; the plan, the harness route and the viewer now say so. Dim at night (D4) | **Fixed (audit)** |
| SAF-09 | Low | **Radio rules.** A receive-only radio plus certified modules; the home-built unit must still not cause harmful interference (47 CFR 15.5) | Checks that exist: the AM radio buzz test (B5) and the key fob test (I5) | OK |
| SAF-10 | Low | **The OBD dongle is a way into the car's network.** With the default PIN, anyone in range can send CAN frames ([SPD-06](04-speed-sources.md), O5) | A dongle that needs a button to pair or sleeps its radio; unplug it when parked for long. The ESP32 itself sends only speed requests | Open (B8) |
| SAF-11 | Low | **Electrical fire.** A pinched 12 V feed shorts to the body | 5 A fuse at the tap on 18 AWG (rated far above 5 A); grommets at every metal edge; ties every 15–20 cm along existing harnesses | Fixed (design) |
| SAF-12 | Low | **Privacy.** The cameras film other road users | Record only to tune the detector, video without audio, keep it local and delete it; don't publish plates or faces | Open (Pi app) |

## Premortem: someone got hurt or got a ticket. Why?

| # | How it fails | Likely | Impact | Prevention / detection | Status |
|---|---|---|---|---|---|
| SAF-P1 | A dark LED, a lane change, a motorcycle in the zone | Medium | Collision | SAF-01: shoulder checks; a measured miss rate before trusting it | Open |
| SAF-P2 | Constant false alarms in traffic; you mute it for good, then forget it's off | High without CAM-05 | Protection gone | Lane mask and persistence ([CAM-05](08-cameras-and-vision.md)); mute only silences the current turn (S1) | Open (Pi app) |
| SAF-P3 | Pulled over for a screen showing video | Low | Ticket | Camera only with the blinker or a danger; no playback while moving | Fixed (design) |
| SAF-P4 | In a crash, the unit or a bracket hits a knee, or an airbag throws a cable bundle | Low | Injury | SAF-06, SAF-07 | Open (bracket) |
| SAF-P5 | The 12 V feed chafes through on a sharp edge | Low | Fire | SAF-11 | Fixed (design) |
| SAF-P6 | Someone uses the dongle to play with the car | Low | Distraction, damage | SAF-10 | Open |

## Before you move on

- Write the disclaimer and the "buzzer muted, logging" first-month mode into the Pi app's plan.
- Choose Option A unless the mock-up proves B clear of the windshield view and the airbag door.
