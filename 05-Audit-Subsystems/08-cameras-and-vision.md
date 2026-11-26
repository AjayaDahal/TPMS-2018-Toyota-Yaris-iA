# 08 · Cameras and vision

**Scope:** the two mirror cameras: which camera to buy and what to use from the inventory, lens and aim, mounting in the mirror cap, the cable into the car, the USB link to the computer, the car/motorcycle detector and the computer that runs it. The decision logic that turns a detection into an LED or a beep is in [alerts](05-alerts-and-alert-pod.md); the Pi itself in [Raspberry Pi](06-raspberry-pi.md).

**Maturity:** requirements and acceptance criteria written (premortem V1–V10); no car camera bought, nothing measured, the Pi software not written.

**Verdict: Act.** Three gaps in the camera spec could each make the system miss vehicles:
- The lens is specified as "90–110°" without saying horizontal, so a lens that meets it can be too narrow to see the zone.
- The aim is never specified. The harness says "aimed back along the car's side", which misses the area beside and just behind the driver.
- Two USB cameras on a Pi 4 share one USB 2.0 bus and may not stream at the same time.

All three are cheap to settle before buying.

## What was verified

| Check | Evidence | Result |
|---|---|---|
| Area the camera must see | Car geometry from the blueprint: camera 0.975 m from the centreline and 0.56 m ahead of mid-wheelbase, body side at 0.8475 m, rear bumper 2.21 m behind mid-wheelbase. Zone: 0.5–3.5 m out from the body side, from mid-wheelbase (about the driver's eyes) to 3 m behind the bumper. ISO 17387 uses 0.5–3.0 m; 3.5 m covers a whole lane | The zone spans **3.7° to 80.6° outward of straight back**, so 77° of horizontal view. Keeping a strip of the car's own side in the frame (the mis-aim check, V6) needs **83°**. The middle of that span is **~39° outward** |
| Lens maths | Sony IMX307, the usual 1/2.8" automotive sensor: 1920 × 1080 at 2.9 µm = 5.57 × 3.13 mm. 2.8 mm lens: **HFOV 89.7°**, DFOV 97.5°. 2.1 mm lens: **HFOV 105.9°**, DFOV 113.4°. Many cheap cameras make 720p by cutting out the sensor's centre: the 2.8 mm lens then sees **67°**, the 2.1 mm **83°** | A listing that says "100° lens" usually means the diagonal: that camera can be 90° wide at 1080p, and 67° wide in its 720p mode |
| Pixels per target | Detector input 320 px wide over 89.7° = 3.6 px per degree. Motorcycle (0.8 m wide): 27 px at 6 m, 11 px at 15 m. Car (1.8 m): 37 px at 10 m, 12 px at 30 m | Enough inside the zone (at most ~6 m from the camera). Not enough to warn about a fast car 20–30 m back: this is a blind-spot detector, not a closing-speed warning |
| USB power | Two cameras: 0.5 A typical, 0.7 A peak (power budget), from the Pi's USB ports; the Pi 4 limits all four ports together to 1.2 A | OK on their own. The SunFounder display takes its 5 V from J5, not from the Pi's USB, so only its touch data shares the ports ([DSP-03](09-display-and-ui.md), [PI-03](06-raspberry-pi.md)) |
| Cable length | USB 2.0 allows 5 m per cable. Runs: ~3 m left, ~3.5 m right, plus a 90° adapter | OK: no passive extensions on top |
| What the inventory has | `sen-usb-cam` × 4 (bare USB camera boards), `sen-rpicam-v13` (Pi Camera v1.3, OV5647, CSI), `sen-m12-board-cam` (M12 lens, 3-pin JST: probably analog video, sensor unknown), `sen-coral-camera` (OV5645 MIPI, belongs to the NavQPlus), `sen-d8m-gpio` (Terasic FPGA camera), `sen-fpc-cam`; computers: `sbc-rpi4` × 2, **`sbc-jetson-nano`** (P3450, 4 GB), `sbc-nxp-navqplus` (i.MX 8M Plus with NPU) | **No weatherproof camera in the inventory: buy the two car cameras.** The USB boards are right for the bench frame-rate test (V1). The Jetson Nano was in the inventory the plan was built from but was never considered: CAM-04 |

## Camera choice: use vs. buy

| Use | What | Why |
|---|---|---|
| Bench (use) | 2 × `sen-usb-cam` on the Pi 4 | Frame rate of two streams + detector (V1) and the two-camera USB test (CAM-03) before any money is spent |
| Bench (use) | Pi Camera v1.3 on the Pi 4's CSI port | A third view to try the detector on recorded drives; not for the car (ribbon can't go through a door) |
| Car (buy) | 2 × USB UVC cameras that pass the acceptance test below | Nothing in the inventory is weatherproof, small enough for a mirror cap, and made for −20 °C to a sun-soaked mirror |
| Fallback (buy) | 2 × AHD cameras + one 2-channel AHD-to-USB capture box | If no USB camera passes: the capture box is one USB device, which also avoids CAM-03 |

**Acceptance test for the car cameras** (replaces the "90–110° lens" line):
- UVC MJPEG at 1280 × 720 / 30 fps (or 1920 × 1080 scaled down), **full sensor width in that mode**.
- **HFOV ≥ 95° measured**: 1 m from a wall, the picture shows at least **2.18 m** of wall.
- Starvis-class WDR sensor, no IR LEDs, IP67, barrel ≤ 20 mm, lead ≥ 3.5 m, rated −20 °C to at least +70 °C.
- **Both cameras stream at once on the Pi 4 for 30 minutes** at the chosen mode with no `-28` / "No space left on device" in `dmesg` (CAM-03).

Buy from a seller that takes returns, and run this test the day they arrive.

## Findings

| # | Severity | Finding | Fix | Status |
|---|---|---|---|---|
| CAM-01 | High | **The lens spec can't guarantee coverage.** "90–110° lens" doesn't say horizontal or diagonal, and doesn't rule out a 720p mode that crops the sensor. A camera that meets it can see 67–90° horizontally; the zone plus the car's flank needs 83°, plus margin for aim | Spec now: **HFOV ≥ 95° at the streamed resolution, measured** (wall test above). Typical match: 2.1–2.4 mm lens on a 1/2.8" or 1/3" sensor | **Fixed (spec):** [PREMORTEM_v2.md](../00-project-management/PREMORTEM_v2.md) V4 and the BOM note updated |
| CAM-02 | High | **The aim is never specified.** The harness says "aimed back along the car's side"; the viewer draws the camera 18° outward. A 95° camera pointed 18° outward sees up to 66° outward: a car **beside the driver's shoulder (66–81° outward) is missed**, and that is where a car sits when you start to change lanes | Aim the camera **~39° outward of straight back, ~10° down**, with the car's side as a thin strip at the inner edge of the picture. A printed wedge in the mirror cap sets the angle. Check it on the ground: cones at the zone's corners, all four in the picture | **Fixed (spec):** premortem V4 and the harness route; Open: wedge (You, after measuring the cap) |
| CAM-03 | High | **Two USB cameras may not stream together on a Pi 4.** All four USB ports on the Pi 4 share one USB 2.0 link: the VL805 controller's internal hub. A UVC camera reserves isochronous bandwidth for its MJPEG mode, and many reserve the maximum, 3 × 1024 bytes per 125 µs. Two of those need 6144 bytes, but USB 2.0 allows only 6000 bytes per microframe for streams. The second camera then fails with `-28` (no space left on device), however small the actual frames are. The Linux driver's bandwidth quirk only applies to uncompressed formats | Make it part of the acceptance test (above), with **both purchased cameras at once**; the inventory USB boards don't prove it for other models. If it fails: a lower mode that reserves less, or the AHD fallback (one capture device for both) | Open (bench, before mounting) |
| CAM-04 | Medium | **The inventory's strongest vision computer was never evaluated.** The plan sizes everything for the Pi 4 (320 × 320 NCNN, alternating sides, V1). The lab also has a **Jetson Nano 4 GB** with a CUDA GPU that runs TensorRT detectors several times faster than the Pi 4's CPU, and the NavQPlus with an NPU. Trade-offs: the Jetson runs JetPack 4.6 (Ubuntu 18.04, end of life); it takes 5 V at up to 4 A (10 W mode); it is 100 × 80 × 29 mm with its heatsink, so it won't sit on the display's back; and it drives **HDMI only**, so it can't use the official DSI display, but it can use the **SunFounder TS-7** (HDMI + USB touch) | Keep the Pi 4 as plan A and measure V1 first. If the Pi can't hold **≥ 5 detections per second per side** at 320 px, move vision to the Jetson Nano with the TS-7, and the enclosure gets a separate computer box. The ESP32, the protocol and the PCB don't change: the link is the same UART | Open (decision after V1; the TS-7 suits either, [DSP-01](09-display-and-ui.md)) |
| CAM-05 | Medium | **False alerts from the car behind you.** A rear-facing camera sees the car following in your own lane near the inner edge of the picture, and parked cars and guardrails at the outer edge. Without a calibrated lane mask they look like blind-spot vehicles | Calibrate the region of interest on the ground (build step st_14), excluding your own lane. Count a detection only if its bottom edge (the tyres) is inside the zone. Require it in 2–3 frames in a row; the speed gate already silences parking lots | Open (Pi software) |
| CAM-06 | Medium | **Heat at the mirror.** The camera sits in a dark mirror housing in full sun; the acceptance spec asks only for +70 °C operating. The car's paint and mirror caps run far above air temperature on a summer day | Prefer cameras rated to +85 °C; mount on the shaded underside of the cap; let the Pi read the camera's frame rate and flag a dropout as a camera fault (already in the protocol: `camFault`) | Open (choice of camera) |
| CAM-07 | Medium | **Night, rain and low sun** (V7): headlights bloom, rain drops sit on a rear-facing lens, a motorcycle is a single headlight | Already planned: WDR sensor, no IR LEDs, hydrophobic lens coating, a headlight-blob detector in the zone at night, a lower motorcycle threshold with persistence. Record a few drives to test it before trusting it | Open (Pi software, phase 2 of the build) |
| CAM-08 | Low | Splicing the USB cable for the door boot (V5) | No connector in the data path; pairs twisted, shield continuous; pass = no USB resets in `dmesg` on a 30-minute drive | Open (install) |
| CAM-09 | Info | The mirror glass moves when you adjust it, but the cap doesn't: the camera only moves when the mirror is folded or knocked. The car-flank strip in the picture (V6) catches both | — | OK |

## Premortem: the cameras failed. Why?

| # | How it fails | Likely | Impact | Prevention / detection | Status |
|---|---|---|---|---|---|
| CAM-P1 | The cameras arrive, are 100° "diagonal" and 67° in 720p; the zone beside the driver isn't in the picture | High without CAM-01 | Misses the most important vehicle | Wall test on arrival; return them | Fixed (spec) |
| CAM-P2 | The camera is mounted pointing straight back; it works in testing on the highway (cars come from behind) but misses the car already beside you | High without CAM-02 | Missed warning | 39° wedge; cone check at the four corners | Fixed (spec) + You |
| CAM-P3 | The second camera won't open (`-28`), discovered after both are drilled into the mirrors | Medium | One side blind; rework | Two-camera test on the day they arrive | Open |
| CAM-P4 | The Pi 4 manages 2 detections per second per side; vehicles cross the zone between frames | Medium | Late or missed alerts | V1 bench test; CAM-04 Jetson Nano route | Open |
| CAM-P5 | Constant alerts from the car behind in heavy traffic; you mute it forever | High without CAM-05 | System ignored | Lane mask, tyre-point rule, persistence | Open |
| CAM-P6 | A summer afternoon cooks the camera; it drops out every hot day | Medium | One side blind | 85 °C-rated camera; `camFault` shows it, so it never fails silently | Open |
| CAM-P7 | Water gets past the barrel seal into the mirror cap | Medium | Camera dies, mirror corrosion | O-ring + neutral-cure RTV, drip loop (M7) | Fixed (procedure) |
| CAM-P8 | The USB lead breaks in the mirror hinge or the door boot after a few months | Medium | One side dead | Service loop; 50 door / mirror cycles after install (M8); `camFault` | Fixed (procedure) |

## Before you move on

- Run the bench test V1 with two inventory USB boards now: it decides between the Pi 4 and the Jetson Nano (CAM-04). The TS-7 (HDMI) works with either.
- Buy the car cameras only with the acceptance test above, and test both at once on the day they arrive.
- Measure the mirror cap (`ms_mirror`) and print the 39° wedge before drilling.
