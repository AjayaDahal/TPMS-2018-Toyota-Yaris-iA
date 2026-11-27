# 15 · Viewer and tooling

**Scope:** the interactive viewer ([04-viewer](../04-viewer/README.md): `index.html`, `app.js`, `car_scene.js`, `pcb6_scene.js`, `system_plan.json`), `sync_plan.py`, `serve_viewer.py`, `make_viewer.py`, and the audit's own [run_checks.py](run_checks.py).

**Maturity:** in daily use as the project dashboard; checked here by an independent review (code, data, an in-browser run, an in-process HTTP test) and by this audit in a browser.

**Verdict: Sound** after fixes. The data was in sync and every count matched its source. The defects were in interaction and robustness:
- **High:** the inspector couldn't be reopened once hidden.
- Clicks went to hidden objects.
- There was a race on the first v1 visit.
- Status pills were wrong for several items (VW-04).
- `sync_plan.py` could drop rows silently.
- The local server exposed git-ignored personal files.

All fixed and re-tested. The camera view cone also drew a geometry that no real lens has (VW-19).

## What was verified

| Check | Evidence | Result |
|---|---|---|
| Data sync and counts | `sync_plan.py --check`; pinout rows vs `pins_v2.h`; rail totals; BOM totals; 67 checklist ids, 96 premortem items, 8 gates, scene pick ids: no duplicates | OK |
| Reproducibility | `make_enclosure.py` rebuilds the report and 17 STLs byte-identical, `make_mounts.py` its report and 13 STLs; `make_viewer.py` rebuilds `manifest.json` byte-identical | OK |
| Syntax and load | `node --check` on the three scripts; a cache-free reload in the browser: no console errors or warnings | OK |
| Inspector Hide/Show (after the fix) | At 487 px and at 1400 px: collapsed, the Show button stays on screen (a rail at the right edge on desktop), `aria-expanded` follows, the stage widens from 1010 to 1356 px, Show restores the panel | OK |
| v1 race (after the fix) | Switch to v1, back to the car within 30 ms, wait for the 43 STLs: car mode, car tab, car camera; a later v1 visit loads normally | OK |
| Camera geometry (after the fix) | Built the scene in the page and measured it: the fans span 8.5° inward to 86.5° outward of straight back on both sides. The zones run 1.35–4.35 m from the centreline (0.5–3.5 m from the body side), from mid-wheelbase (y = 0) back to y = −5.21 m (3 m behind the bumper). The cameras are aimed 39° outward and 10° down | Matches [CAM-02](08-cameras-and-vision.md) |
| `serve_viewer.py` (after the fix) | Live HTTP probes: tracked and new-but-not-ignored files 200; ignored photos, old build output, `.git`, the 8.3 name `GIT~1`, `..` and `%2e%2e` paths 404; a foreign `Host` 421; `.md` as `text/plain`, `.js` as `text/javascript`; a second server on the same port refused | OK |
| `sync_plan.py` (after the fix) | In-memory breakage cases: a renamed Corrections heading still parses (96 items); a blank line inside a table, a renamed column, a row without its leading pipe, an unescaped pipe, an unknown status or gate word, and a duplicate id each stop it with the line number; an escaped `\|` and a fenced `# line` are handled | OK |

## Findings

| # | Severity | Finding | Fix | Status |
|---|---|---|---|---|
| VW-01 | High | "Hide" shrank the inspector to 0 px and pushed "Show" off-screen | Collapses to a 44 px rail that keeps the button; `aria-expanded` updated | **Fixed (audit)**, tested in the browser |
| VW-02 | Medium | Hidden objects stayed clickable (Three.js ignores `visible` when ray-casting), and the fan keep-out box caught every click on the parts inside it | Picking skips anything hidden itself or under a hidden group; keep-out volumes are picked only when no part is behind the click | **Fixed (audit)** |
| VW-03 | Medium | First v1 visit: switching away while the 43 STLs loaded one by one ended in car mode with the v1 tab and camera; one failed STL left v1 half-built for good | Parts load in parallel once, a failure resets the loader with a visible message, and the mode switch stops if you left | **Fixed (audit)**, tested in the browser |
| VW-04 | Medium | Status pills matched substrings: "layout" contains "you" (P8, P9 tagged YOU); "Fixed" hid open work in D1, D5, V6, V8; V7's "phase 2 of the build" landed in the CAN/radar Phase 2 pill | Each `+`/`;` part is read by its leading word outside parentheses; unknown words are an error. The pill is now "Phase 2 (CAN, radar)" | **Fixed (audit)** |
| VW-05 | Medium | The 12V_PROT total (0.05 A) counted only the piezo and optos, not the regulators fed through the same fuse | The 12 V input is in [PWR](01-power-and-protection.md): 1.1 A typical / 2.0 A peak at 12 V, 2.7 A at 9 V. Showing it in the Wiring tab needs efficiencies in the data | Open (Low) |
| VW-06 | Medium | `serve_viewer.py` served the whole checkout to any `Host`: your git-ignored personal PDF, photos and old build output were readable by a DNS-rebinding page while it ran | Serves only the repository's files (`git ls-files --cached --others --exclude-standard`), localhost `Host` only | **Fixed (audit)**, probed |
| VW-07 | Medium | `sync_plan.py` dropped rows silently on ordinary edits (renamed heading or column, a blank line, a missing pipe, an unescaped pipe, a gate starting "Blocked") | Tables found by their header; strict row, header, status and id checks; added and removed ids printed | **Fixed (audit)**, breakage cases tested |
| VW-08 | Medium | No error path: a bad hand edit or a failed fetch left empty tabs with only a console message; the README called it "offline" although it can't run from `file://` | A visible error banner with the likely cause; README says it needs the local server | **Fixed (audit)** |
| VW-09 | Medium | "Reset All Checklists" wiped every tick with one click; the documented port was already taken | Asks first; a port in use is now an error with a hint (ticks are stored per address) | **Fixed (audit)** |
| VW-10 | Low | `inline()` didn't escape `"` in link URLs (an attribute could be injected from the markdown); `javascript:` was only neutralised by accident | Quotes escaped; only `http(s)` and relative links become links | **Fixed (audit)** |
| VW-11 | Low | `.md` links downloaded instead of displaying; on GitHub Pages (no `.nojekyll`) they would 404 | Served as text; Pages isn't enabled | **Fixed (audit)** / Open (if Pages) |
| VW-12 | Low | Text drift: P4's 2.4/3.8 A vs the Wiring tab's 2.20/3.72 A; the README put the enclosure report in the wrong tab; the buy checklist totalled $303 vs the BOM's $300 | P4 rewritten (and see PWR-01); README tab fixed; the $3 line corrected. The "$2" PCB price in the header stays: it's your figure, and the gate G8 checks it | **Fixed (audit)** |
| VW-13 | Low | "Phase 2" meant three things; I1 cited G9, which isn't in the gate list | Pill renamed; G9 stays an install gate described under the table | **Fixed (audit)** / Accepted |
| VW-14 | Low | Keep-out zones, the enclosure size and "38 fit checks" were copied by hand into `pcb6_scene.js`; they wouldn't follow a regenerated enclosure | Since the TS-7 redesign the enclosure size, the check count and the display data are read from `systemPlan.enclosure`. The keep-out zones (fan zone, SMA strip) are still copied: they match the TS-7 report today | Open (Low) |
| VW-15 | Low | The v1 presets said "Front (OLED)" and "Back (MCU/RF)", but those modules aren't in the STEP model | Renamed; the view label says the modules aren't modelled | **Fixed (audit)** |
| VW-16 | Low | `make_viewer.py` turns any export failure into a note and still prints "43 solids"; stale parts are never removed | Fail loudly, verify the files, clear `parts/` first | Open (Low) |
| VW-17 | Low | 2.2 MB at start, 527 KB of enclosure STLs loaded while hidden, unminified Three.js, rendering every frame | Lazy-load, allow caching, the minified build, render on demand | Open (Low) |
| VW-18 | Low | Accessibility: plain buttons in a `tablist`, colour-only active tab, placeholder-only search boxes, low contrast in a few places | ARIA tabs and labels, a darker accent | Open (Low) |
| VW-19 | Medium | **The camera view cone was not a lens.** It joined the camera to the far end of the zone, the camera was yawed 18°, and the painted zone started level with the camera (a 90°-outward corner no rear camera can see) | A 95° fan aimed 39° outward and 10° down, and the zone from the driver's seat to 3 m behind the bumper, 0.5–3.5 m out; the simulator's occupancy uses the same zone | **Fixed (audit)**, measured in the browser |
| VW-20 | Medium | **Three stale viewer servers were bound to the same ports and answered with empty replies.** On Windows, Python's server sets `SO_REUSEADDR`, which lets a second server share a port | `serve_viewer.py` binds exclusively on Windows. The three stale servers were stopped and one fixed server started on 28776 | **Fixed (audit)** |
| VW-21 | Low | **The 6-layer scene's Bottom (L6) view showed a mirror image of the underside** (found with the back's signature, 2026-11-27). The layer textures are drawn from the parts side so the exploded stack lines up, and three.js maps a box's bottom face to read correctly from below, so the underside came out mirrored: the antenna keep-out on the wrong side, and the silkscreen backwards | u flipped on the L6 box's bottom face only; the Bottom preset turns the board over like KiCad's bottom view. Checked in the browser against `render_bottom.png`: the signature reads, the keep-out and J5 sit where KiCad has them, and the top view is unchanged | **Fixed** |

## Premortem: the viewer misled you. Why?

| # | How it fails | Likely | Impact | Prevention / detection | Status |
|---|---|---|---|---|---|
| VW-P1 | The premortem is restructured and rows vanish from the viewer; its verdict looks greener than the document | Was High | Wrong go/no-go | VW-07 strict parser; `run_checks.py` runs `--check` | Fixed |
| VW-P2 | A hand-copied count drifts (the test count changed in 8 places during this audit) | High | Misleading status | [PRJ-04](17-project-and-repo.md); generate counts | Open |
| VW-P3 | The enclosure is regenerated, but the viewer's keep-outs stay old and the layout follows them | Medium | PCB misfit | VW-14; the layout follows `enclosure_report.json`, not the viewer | Open |
| VW-P4 | Checklist ticks "vanish" after a port change or a Reset click | Medium | Steps skipped | VW-09 confirm; same port; an export button would help | Partly fixed |
| VW-P5 | A Three.js upgrade of the addons alone breaks loading | Low | Viewer down | Upgrade `vendor/` as one unit | Accepted |

## Before you move on

- Use `python 04-viewer/serve_viewer.py`, one at a time; it now refuses a busy port.
- Run `python 05-Audit-Subsystems/run_checks.py` before every commit.
