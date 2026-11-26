# 10 · Enclosure and thermal

**Scope:** the printed v2 unit ([01-hardware/enclosure](../01-hardware/enclosure/README.md)): bezel, housing (plate and rear box), lid with the 30 mm fan, and the USB wing for the car's USB passthrough; the piezo inside the bezel. The alert pod was dropped on 2026-11-26. Also the generator `make_enclosure.py` and its 62 checks, the fit in the console opening, materials, and how heat leaves the box.

**Maturity:** generated and checked in software only; nothing is printed yet. Redrawn after this audit for the SunFounder TS-7 you have ([DSP-01](09-display-and-ui.md)). Its main input is an estimate: the TS-7's size, ear holes, sockets and back-part height come from SunFounder's table and photos ([DSP-10](09-display-and-ui.md)).

**Verdict: Watch.** The geometry is sound: every part is a closed solid, nothing clashes, and it fits the opening. The risks are physical, and only a print and a hot car can settle them:
- **heat:** the Pi throttles at a warm, not a hot, cabin;
- **material creep** on a summer dashboard;
- **retention** in a crash;
- the **TS-7's real dimensions**: measure them before printing.

## What was verified

| Check | Evidence | Result |
|---|---|---|
| Reproducible output | `make_enclosure.py` rebuilds `enclosure_report.json` and all 17 STLs byte-identical (also part of [run_checks.py](run_checks.py)) | OK |
| Printed parts are valid solids | Re-loaded the four `print_*.stl`: closed and manifold; volumes 47.4 / 138.9 / 35.2 / 10.6 cm³ match the report | OK |
| 62 fit checks | All pass: no clash between any pair of parts and dummies (including the display's HDMI and micro-USB plugs and their leads, the piezo, the USB passthrough with its cable and the wing's screws); the display hangs on 4 bosses at its ear holes (157.3 × 114.4 mm, from photos); the lip clears the active area; the plugs fit inside the bezel; PCB posts on 92 × 92 mm, Pi posts on 58 × 49 mm, 3 mm Pi-to-PCB air gap; finger-safe vents; the piezo behind 5 slots with a 2 mm gap; the passthrough in the v1 Ø25.8 cut with its nut held by the wing; its plug through every opening | OK |
| Console opening | Box, ears, 90° USB plugs, the display leads, the antenna lead and the car-USB cable inside the 191 / 123 × 129 mm opening, 3.0 mm to spare at the tightest point; the plate's cable slot ≥ 1.2 mm inside the opening's edge; bezel 129.0 mm tall: the opening's full height, its top at the opening's top edge | OK (on paper; test fit in G6) |
| Pocket depth needed | 55.5 mm: the box's 50.5 mm behind the plate plus 5 mm of margin (the report's `clear_pocket_depth_needed`); [M2](../00-project-management/PREMORTEM_v2.md#mechanical-and-installation) asks for ≥ 56 mm measured. The unit stands 21.8 mm proud of the trim | Not measured yet (G5) |
| Print size | Largest parts 205.6 × 129.0 mm (bezel and housing): needs a bed of ≥ 210 × 135 mm. The generator checks a 220 × 220 bed, so smaller beds (180 × 180) fail without warning | OK for 220 × 220 |
| Material heat limits (published heat-deflection temperatures at 0.45 MPa) | ASA 93–103 °C, ABS ~100 °C, PETG 68–78 °C, PLA 55–60 °C. Parked car: dash surfaces up to ~85 °C, cabin air 52 °C (1-hour tests) to 76 °C (all-day maxima) | ASA/ABS OK in the shade; PETG marginal (ENC-04) |
| Heat out of the box | Estimate: 5–8 W inside the box (Pi 4 with two streams and the detector, the carrier's regulators). The TS-7 (~2.4 W in all, most of it in its backlight) sits in front of the plate, and the intake air passes behind it first. A 30 mm fan through slots and gaps moves maybe 0.6–1 L/s, so the box air runs ~7–12 K above the cabin. The SoC sits ~25–35 K above that with small heatsinks | Throttles from ~40–45 °C cabin (ENC-01) |

## Findings

| # | Severity | Finding | Fix | Status |
|---|---|---|---|---|
| ENC-01 | High | **Heat.** By the estimate, the Pi reaches its 80 °C throttle point at a cabin of about 40–45 °C (the estimate's range is 33–48 °C). A summer car is hotter than that for the first part of every drive. The hot-start hold (board ≥ 60 °C: wait for 55 °C, at most 10 min) only delays the start ([PI-04](06-raspberry-pi.md)) | Before printing, add the cheap margin: a real heatsink with thermal paste on the SoC; a ball-bearing fan. Then T1 in a sun-soaked car. If it still throttles: `arm_freq=1200`, a duct from the fan to the SoC, or the PCB in its own box (same 92 × 92 posts) | Open (T1) |
| ENC-02 | High | **The whole stack was drawn round the official display:** the bezel lip, the plate's M3 pattern, the flat-cable relief and the Pi on the display's own standoffs. The SunFounder TS-7 has a different size, holes and no Pi standoffs ([DSP-01, DSP-02](09-display-and-ui.md)) | Regenerated for the TS-7: it hangs on 4 bezel bosses at its ear holes; a flat plate with a cable slot; the Pi on 4 posts; the HDMI and micro-USB plugs inside the bezel; 43 checks | **Fixed (TS-7 redesign)** |
| ENC-03 | Medium | **The TS-7's dimensions are estimates** (SunFounder's table and photos: [DSP-10](09-display-and-ui.md)). `BACK_H`, the tallest part on its back, sets where the plate and everything behind it sit; the ear holes set the bosses. A straight Dupont plug on the Pi's GPIO (22 mm) breaks the 3 mm Pi-to-PCB gap ([M10](../00-project-management/PREMORTEM_v2.md#mechanical-and-installation)) | Measure them ([Measure first](../01-hardware/enclosure/README.md#measure-first-then---set)), `--set`, regenerate; 90° or low-profile plugs on the GPIO. Gate G6 | Open (G6) |
| ENC-04 | Medium | **PETG isn't safe in the console either.** The plan allows PETG for the shaded console, but its heat-deflection temperature (68–78 °C) is the same as the cabin air of a car parked all day in a hot climate (up to 76 °C), and the plate carries the display's weight and screw preload, so it creeps. ASA (93–103 °C) keeps 8–18 K of margin even on an 85 °C dash top | ASA or ABS for every printed part, or MJF PA12 from JLC3DP. PETG only for the test fit. Premortem M3 and the enclosure README now say so | **Fixed (audit)**, text |
| ENC-05 | Medium | **Screws cut their own threads in printed pilots.** The bezel (6 × M3 into 2.6 mm pilots) and the lid (4 × M3 × 12 into the ears) strip after a few openings, and hot plastic relaxes, so the screws loosen | M3 heat-set brass inserts in the lid ears and the bezel bosses (the lid is opened for every service); the generator needs a parameter for the insert hole | Open (generator) |
| ENC-06 | Medium | **Hot exhaust can come straight back in.** In the console pocket (Option A) the lid fan blows into the closed pocket; the air leaves through the 2 mm gap round the bezel, and the intake is the slots in the bezel's face beside the screen, a few centimetres from that gap | Seal the gap along both sides with a foam strip, so the exhaust leaves at the top and the bottom. In T1, log the intake air temperature against the cabin's | Open (T1) |
| ENC-07 | Medium | **Nothing holds the box in the pocket yet.** M4 says "AMPS M4 nuts or a pocket bracket, never tape only", but no pocket bracket exists. The unit is roughly 0.6 kg; in a 30 g crash that's ~180 N on whatever holds it | Design the bracket after G5: the AMPS pattern to a console screw point, or a strap round the rear box to the pocket's floor. Not glue, not tape, not the display's glass ([SAF](16-safety-and-legal.md)) | Open (after G5) |
| ENC-08 | Medium | **The camera plugs hang on the Pi's USB sockets** (and so does the display's touch lead). USB-A has no latch; with a 90° adapter and ~3.5 m of cable, vibration levers it out of the socket (the cable has no anchor inside the box) | A cable-tie anchor on the housing next to the window; leave a little slack between the anchor and the plug; a dab of RTV after the bench test | Open (generator) |
| ENC-09 | Low | **A dead fan is silent.** The fan has no tachometer, and a sleeve-bearing fan from a cheap case doesn't last long at 60–80 °C. The first symptom would be a slow vision app | Ball-bearing fan. The Pi app shows a warning when the SoC is > 70 °C at idle or `get_throttled` is set | Open (Pi app) |
| ENC-10 | Low | **Bed size isn't checked against your printer.** The generator says "fits a 220 × 220 bed" for a 205.6 × 129.0 mm part | Fine for 220 × 220 and larger. On a 180 × 180 printer, order the bezel and the housing in MJF instead | Accepted |
| ENC-11 | Info | The Raspberry Pi docs ask for boards out of reach: 2.5 mm slots, the fan grille and the grommet do that (M12) | — | OK |
| ENC-12 | Medium | **The car's USB port lost its place.** The v1 panel had the passthrough in its face; the 7" display now fills the console opening, and the passthrough's 25 mm body and 36 mm nut have no room behind the bezel | A printed **USB wing** on the bezel's right edge holds it in the v1 Ø25.8 cut, facing the passenger, its body along the trim; the cable goes through the bezel's side wall and the plate's slot to the car's port in the pocket. The wing prints front face down without supports, holds the nut (the socket tightens from outside) and is held by 2 × M3 × 10 from inside the bezel plus VHB | **Fixed (design, 62 checks)** |
| ENC-13 | Medium | **The wing is drawn round the v1 3-D model's passthrough and an assumed free trim** (32 × 46 mm right of the bezel). Its front stands 12.6 mm proud of the bezel's, and the socket ends 35.9 mm right of it | Measure the passthrough and the trim (`PASS_*`, `TRIM_RIGHT`) and regenerate; a cardboard wing in the G5 mock-up ([M15, M16](../00-project-management/PREMORTEM_v2.md#mechanical-and-installation)). Without the nut (body glued) the front drops to ~7 mm | Open (G5, G6) |
| ENC-14 | Low | **The piezo sits in the intake air path,** behind 5 of the right slots | Three fingers hold its face 2 mm off the skin, so the air flows round it and the slots stay open (771 mm² in all); check in T1 | Fixed (enclosure) |

## Premortem: the enclosure failed. Why?

| # | How it fails | Likely | Impact | Prevention / detection | Status |
|---|---|---|---|---|---|
| ENC-P1 | Every summer afternoon the vision runs slowly for the first 10–20 minutes | High | Late detections | ENC-01, T1, the frame-rate shown on screen ([PI-P2](06-raspberry-pi.md)) | Open (T1) |
| ENC-P2 | ~12 h of printing for a display whose real size differs from the photos | Medium until DSP-10 | Time, filament | ENC-03; measure first; print the bezel alone as a fit test first | Open (G6) |
| ENC-P3 | After a summer, the plate has crept: the bezel gap opens, the screws are loose, the display sags | Medium | Rattles, a loose display | ENC-04, ENC-05 | Open |
| ENC-P4 | The rear box doesn't fit the pocket (depth, the car's USB/12 V strip), or the unit, 21.8 mm proud of the trim, hits the shifter | Medium | Redesign | G5 foam mock-up, ≥ 56 mm measured ([M1, M2](../00-project-management/PREMORTEM_v2.md#mechanical-and-installation)) | Open (G5) |
| ENC-P5 | The fan stops; the box cooks quietly | Medium | Throttling, shorter Pi life | ENC-09 | Open |
| ENC-P6 | A camera plug works loose on a rough road; one side goes dark | Medium | Blind side (shown as a camera fault) | ENC-08; the ESP32's `camFault` ([ALR](05-alerts-and-alert-pod.md)) | Open |
| ENC-P7 | The pocket fills with the box's own hot air | Medium | Higher SoC temperature | ENC-06 | Open (T1) |
| ENC-P8 | In a hard stop or a crash, the unit leaves the pocket | Low | Injury | ENC-07 | Open |
| ENC-P9 | The passthrough doesn't fit its wing, or the wing doesn't fit the trim | Medium | A reprint of the wing (~1 h) | ENC-13: measure first, cardboard wing in the mock-up | Open (G5, G6) |

## Before you move on

- Measure the TS-7 (DSP-10), then do G5 (a 112 × 124 × 51 mm foam block in the pocket; the shifter against the 21.8 mm protrusion) and G6 (regenerate, print the bezel first).
- Measure the USB passthrough and the trim right of the opening; tape a 28 × 42 mm cardboard wing there in the G5 mock-up.
- Print in ASA or ABS (or order MJF PA12); PETG only for the test fit.
- Plan T1 before you trust the camera view in summer.
