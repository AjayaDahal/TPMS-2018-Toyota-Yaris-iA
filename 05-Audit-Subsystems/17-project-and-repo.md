# 17 · Project, documentation and repository

**Scope:** how the project is kept consistent: sources of truth, generated files, checks, the inventory the plan was matched against, and the public GitHub repository.

**Verdict: Sound, with one blind spot.** Everything that can be checked by a tool is now checked by one command. The blind spot is inputs that change outside the repo: the lab inventory grew from 226 to 264 items after the plan was made, and one new item replaced a core part: the design now uses it ([DSP-01](09-display-and-ui.md)).

## What was verified

| Check | Evidence | Result |
|---|---|---|
| One command re-runs every check | [run_checks.py](run_checks.py) (new): v2 logic tests (166), v1 decoder tests, pin-map audit + self-test, enclosure (63 checks) and mounts (28) regeneration compared byte-for-byte with the committed STLs, STL watertightness, viewer data sync, viewer JS syntax (4 files), markdown links, repo hygiene, the carrier's JLCPCB files, v1 and v2 carrier KiCad ERC/DRC | All 13 pass (2026-11-26) |
| v1 board is what the repo says | KiCad 10 `kicad-cli`, run on a copy: ERC 0, DRC 0 including unconnected items and schematic parity | OK (independent of the earlier claim) |
| Generated files are current | Re-running `make_enclosure.py --out <temp>` reproduces every committed STL and the report exactly | OK: the generator is deterministic |
| Nothing private in the public repo | Scan of every tracked text file for local paths (`C:\Users\…`, `/home/…`, the OneDrive folder name) and secrets; binaries checked byte-exact when pushed | OK |
| Remote in sync | `main` = `origin/main` after the v2 push (5 commits) | OK |

## Findings

| # | Severity | Finding | Fix | Status |
|---|---|---|---|---|
| PRJ-01 | Medium | **v1 build output was not git-ignored.** The root `.gitignore` ignored `hardware/build/`, but after the folder reorganization the build script writes to `01-hardware/build/` (`BUILD = os.path.join(HW, "build")`). That folder holds netlists and DRC reports with local absolute paths, and a rebuild would have offered them for commit to the public repo. Fixing only the new path then exposed the old one: a local, untracked `hardware/` folder from before the rename still holds the Nov 9 build output (`.net`, `.dsn`, `.ses`, router log, ERC/DRC JSON) | `.gitignore` now ignores every `build/` folder (no tracked file lives in one), which covers both. `run_checks.py` checks it two ways: `git check-ignore`, and no untracked netlist/DSN/SES/ERC/DRC/`.kicad_prl` file that `git add -A` would pick up (tested against the old rule: it fails). The local `hardware/` folder itself is yours to delete; it also holds your `git_ignore_me` photos, which stay ignored | **Fixed (audit)** |
| PRJ-02 | Low | **Stale paths from the reorganization**: the v1 build command in [01-hardware/README.md](../01-hardware/README.md) (`hardware\scripts\…`), two `firmware/bringup` paths in the [bring-up README](../02-firmware/bringup/README.md), and comments in `pins.h` and `test_decode.cpp` | Paths corrected. Left as is: the comment `build_tpms_panel.py` writes into the generated v1 schematic (changing it would make a rebuild differ from the committed board for a cosmetic reason) | **Fixed (audit)** |
| PRJ-03 | Medium | **The plan was matched against an inventory snapshot that is now out of date.** The snapshot had 226 items; the live inventory has 264. One of the new items is the display you actually have, a SunFounder TS-7 (DSP-01: the design now uses it). Others offer options (table below) | Re-match the BOM against the live inventory at G3. The table below lists the new items that matter | Open (you, G3) |
| PRJ-04 | Medium | **Facts are repeated in prose.** Counts, part numbers and dimensions appear in the premortem, five READMEs, `system_plan.json` and strings inside `car_scene.js`. This pass and the last one both found stale copies. `sync_plan.py` covers only the premortem, the order gate and the enclosure | Keep numbers out of prose where possible and link to the generated source; `run_checks.py` before every commit. This audit changed the test count in 8 places by hand (120 → 154) | Open (habit) |
| PRJ-05 | Low | **No CI.** The checks only run when someone runs them | A GitHub Actions job running `python 05-Audit-Subsystems/run_checks.py --skip kicad` on push (Linux has g++, node and Python) | Open (optional) |
| PRJ-06 | Low | `make_v2_fit_template.py` has no `--out`, so the committed template can't be checked for staleness without overwriting it | Add `--out` when the template next changes | Open (optional) |
| PRJ-07 | Medium | **The plan never considered the inventory's strongest vision computer.** The NVIDIA Jetson Nano 4 GB (P3450) was already in the 226-item snapshot the plan was matched against, yet v2 sizes everything for the Pi 4. It runs TensorRT detectors on its GPU, drives HDMI only, and so pairs with the SunFounder TS-7 | Decide after bench test V1 ([CAM-04](08-cameras-and-vision.md)); when matching against the inventory, search by function ("vision computer"), not only for the part the plan names | Open (decision) |
| PRJ-08 | Info | The three KiCad renders exist twice (`01-hardware/docs/` and `04-viewer/renders/`, ~1.3 MB) | Harmless; dedupe only if the repo size matters | — |

### New inventory items that matter (live list, 2026-11-25)

| Item | Relevance | Where |
|---|---|---|
| SunFounder TS-7 7" DIY touchscreen | **The display on hand**: the design now uses it | [DSP-01](09-display-and-ui.md) |
| NXP NavQPlus (i.MX 8M Plus, NPU, 4 GB) | A much stronger vision computer than the Pi 4 if the bench test V1 fails; different software stack and power | [CAM-04](08-cameras-and-vision.md) |
| Board-level camera, M12 lens, 3-pin JST | Probably composite video: a bench part for the plan's analog/AHD fallback; identify its output first | [08-cameras](08-cameras-and-vision.md) |
| DFRobot Gravity LED buttons (white, yellow) | Not used: v2 has no physical button (the touch screen mutes, and the beeps stop by themselves) | [05-alerts](05-alerts-and-alert-pod.md) |
| DFPlayer PRO + mini cavity speaker | Optional spoken alerts from the Pi; the ESP32's piezo stays as the fail-safe | [05-alerts](05-alerts-and-alert-pod.md) |
| Stubby articulated SMA/RP-SMA antenna | Band unknown; probably 2.4 GHz. Don't use it at 315 MHz without checking | [13-tpms-radio](13-tpms-radio.md) |
| Thermal paste | For the Pi 4's heatsink | [06-raspberry-pi](06-raspberry-pi.md) |

## Premortem: the project failed. Why?

| # | How it fails | Likely | Impact | Prevention / detection | Status |
|---|---|---|---|---|---|
| PRJ-P1 | Parts are printed or ordered for a component you don't have (the display, a camera) | High (it already happened once on paper) | Wasted prints and boards | G3 against the live inventory; this audit's DSP-01 | Open |
| PRJ-P2 | A doc says one thing and the design another; a wrong number is built | Medium | Rework | PRJ-04; `run_checks.py` | Open (habit) |
| PRJ-P3 | Local paths or secrets end up in the public repo | Low now | Privacy | PRJ-01 fixed; hygiene check in `run_checks.py` | Fixed |
| PRJ-P4 | Scope creep: cameras, AI, CAN and radar all at once; nothing works end to end | High | Project stalls | Ship in steps ([PREMORTEM_v2 J1](../00-project-management/PREMORTEM_v2.md#project)): camera view on the blinker first, then detection, then extras | Plan |
| PRJ-P5 | A regenerated file silently changes (STLs, Gerbers, viewer data) | Low | Wrong parts printed | Deterministic generators; byte-compare in `run_checks.py` | Fixed |
