#!/usr/bin/env python3
"""Re-run every automated check the subsystem audit relies on (see README.md in this folder).

    python 05-Audit-Subsystems/run_checks.py               # everything that is installed
    python 05-Audit-Subsystems/run_checks.py --skip kicad  # skip checks by name

Read-only: builds and regenerated files go to a temporary folder. Exit code 0 = no check failed
(checks whose tool is missing are reported as SKIP). Needs python with numpy and manifold3d, a C++17
compiler (`python -m ziglang c++`, g++ or clang++); optional: node (viewer syntax), KiCad 10's
kicad-cli (v1 and v2 carrier ERC/DRC).
"""
import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import struct
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
RESULTS = []


def record(name, ok, detail):
    RESULTS.append((name, "PASS" if ok is True else ("SKIP" if ok is None else "FAIL"), detail))


def run(cmd, cwd=ROOT, timeout=600):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=timeout)
    return r.returncode, (r.stdout + r.stderr).strip()


def cxx():
    for cmd in ([sys.executable, "-m", "ziglang", "c++"], ["g++"], ["clang++"]):
        try:
            if run(cmd + ["--version"], timeout=120)[0] == 0:
                return cmd
        except (OSError, subprocess.TimeoutExpired):
            continue
    return None


def host_test(name, folder, include, sources, tmp, compiler):
    if not compiler:
        return record(name, None, "no C++17 compiler found")
    exe = pathlib.Path(tmp) / f"{name}.exe"
    code, out = run(compiler + ["-std=c++17", "-O2", "-Wall", "-Wextra", f"-I{include}", *sources, "-o", str(exe)],
                    cwd=ROOT / folder)
    if code != 0:
        return record(name, False, "build failed: " + out[-300:])
    code, out = run([str(exe)], cwd=ROOT / folder)
    last = out.splitlines()[-1] if out else ""
    record(name, code == 0, last)


def check_pinmap():
    code, out = run([sys.executable, "01-hardware/v2/check_pinmap.py"])
    summary = next((l for l in out.splitlines() if "errors" in l), out[-120:])
    code2, out2 = run([sys.executable, "01-hardware/v2/check_pinmap.py", "--selftest"])
    record("pin map audit + self-test", code == 0 and code2 == 0, f"{summary}; self-test exit {code2}")


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def check_generator(tmp, script, report, label):
    """Run a printed-parts generator into tmp: its checks must pass and its outputs match the committed files."""
    try:
        import manifold3d  # noqa: F401
    except ImportError:
        return record(label, None, "manifold3d not installed")
    out_dir = pathlib.Path(tmp) / pathlib.Path(script).stem
    code, out = run([sys.executable, f"01-hardware/enclosure/{script}", "--out", str(out_dir)], timeout=900)
    checks = next((l for l in out.splitlines() if "checks passed" in l), "")
    committed = ROOT / "01-hardware" / "enclosure"
    stale = [p.name for p in sorted((out_dir / "stl").glob("*.stl"))
             if not (committed / "stl" / p.name).exists() or sha(p) != sha(committed / "stl" / p.name)]
    if not (out_dir / report).exists():
        return record(label, False, f"{script} wrote no {report}: " + out[-200:])
    new_rep = json.loads((out_dir / report).read_text(encoding="utf-8"))
    old_rep = json.loads((committed / report).read_text(encoding="utf-8"))
    if new_rep != old_rep:
        stale.append(report)
    ok = code == 0 and not stale
    record(label, ok, checks.split("->")[0].strip() + ("; stale: " + ", ".join(stale) if stale else "; committed STLs match"))


def check_enclosure(tmp):
    check_generator(tmp, "make_enclosure.py", "enclosure_report.json", "enclosure: fit checks, outputs up to date")
    check_generator(tmp, "make_mounts.py", "mounts_report.json", "mirror + LED mounts: checks, outputs up to date")


def check_stl_watertight():
    import numpy as np
    bad = []
    files = sorted((ROOT / "01-hardware" / "enclosure" / "stl").glob("*.stl"))
    for p in files:
        b = p.read_bytes()
        n = struct.unpack_from("<I", b, 80)[0]
        if len(b) != 84 + 50 * n:
            bad.append(f"{p.name}: not a binary STL")
            continue
        tri = np.frombuffer(b, dtype=np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")]),
                            count=n, offset=84)["v"].astype(np.float64)
        q = np.round(tri.reshape(-1, 3) / 1e-4).astype(np.int64)
        _, inv = np.unique(q, axis=0, return_inverse=True)
        f = inv.reshape(-1, 3)
        e = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
        _, cnt = np.unique(np.sort(e, axis=1), axis=0, return_counts=True)
        _, dcnt = np.unique(e, axis=0, return_counts=True)
        vol = np.sum(np.einsum("ij,ij->i", tri[:, 0], np.cross(tri[:, 1], tri[:, 2]))) / 6.0
        if np.any(cnt != 2) or np.any(dcnt > 1) or vol <= 0:
            bad.append(p.name)
    record("enclosure STLs watertight", not bad and bool(files),
           f"{len(files)} files, all closed with consistent winding" if not bad else "bad: " + ", ".join(bad))


def check_sync():
    code, out = run([sys.executable, "04-viewer/sync_plan.py", "--check"])
    record("viewer data in sync with premortem + enclosure", code == 0, out.splitlines()[-1] if out else "")


def check_js(tmp):
    if not shutil.which("node"):
        return record("viewer JavaScript syntax", None, "node not installed")
    errs = []
    files = sorted(p.name for p in (ROOT / "04-viewer" / "viewer").glob("*.js"))   # the app's modules (not vendor/)
    for f in files:
        dst = pathlib.Path(tmp) / (f[:-3] + ".mjs")
        shutil.copy(ROOT / "04-viewer" / "viewer" / f, dst)
        code, out = run(["node", "--check", str(dst)])
        if code:
            errs.append(f"{f}: {out[-200:]}")
    record("viewer JavaScript syntax", not errs, f"{len(files)} files parse" if not errs else "; ".join(errs))


def slug(h):
    return re.sub(r"[^\w\- ]", "", h.strip().lower()).replace(" ", "-")


def check_links():
    files = [p for p in ROOT.rglob("*.md") if ".git" not in p.parts and "vendor" not in p.parts]
    anchors, bad, n = {}, [], 0
    for p in files:
        text = re.sub(r"```.*?```", "", p.read_text(encoding="utf-8"), flags=re.S)
        for m in re.finditer(r"\]\(([^)\s]+)\)", text):
            t = m.group(1)
            if t.startswith(("http://", "https://", "mailto:")):
                continue
            n += 1
            path, _, anc = t.partition("#")
            tgt = (p.parent / path).resolve() if path else p
            if not tgt.exists():
                bad.append(f"{p.relative_to(ROOT).as_posix()} -> {t}")
                continue
            if anc and tgt.suffix == ".md":
                if tgt not in anchors:
                    anchors[tgt] = {slug(mm.group(1)) for mm in
                                    re.finditer(r"(?m)^#+\s+(.*)$", tgt.read_text(encoding="utf-8"))}
                if anc not in anchors[tgt]:
                    bad.append(f"{p.relative_to(ROOT).as_posix()} -> {t} (anchor)")
    record("markdown links and anchors", not bad, f"{n} links in {len(files)} files" if not bad else "; ".join(bad[:6]))


def check_repo_hygiene():
    code, out = run(["git", "ls-files"])
    if code:
        return record("repo hygiene", None, "not a git checkout")
    leaks = []
    for rel in out.splitlines():
        p = ROOT / rel
        if p.suffix.lower() not in (".md", ".py", ".js", ".json", ".h", ".cpp", ".html", ".css", ".csv", ".ini", ".txt"):
            continue
        t = p.read_text(encoding="utf-8", errors="replace")
        if re.search(r"[A-Za-z]:[\\/]+Users[\\/]+\w|/home/\w+/|OneDrive[ ]-", t):   # [ ]: don't match this line
            leaks.append(rel)
    ignored = run(["git", "check-ignore", "-q", "01-hardware/build/x.net"])[0] == 0
    # Anything `git add -A` would pick up that is build output or personal KiCad state (a *_route.ses is a
    # route of record, committed on purpose)
    _, untracked = run(["git", "ls-files", "--others", "--exclude-standard"])
    exposed = [u for u in untracked.splitlines()
               if re.search(r"(^|/)build/|\.(net|dsn|kicad_prl|lck)$|(?<!_route)\.ses$|(^|/)(erc|drc)\.json$"
                            r"|freerouting\.log$", u)]
    record("repo hygiene: no local paths, build output ignored", not leaks and ignored and not exposed,
           ("local paths in: " + ", ".join(leaks[:5]) + "; " if leaks else "")
           + ("untracked build output: " + ", ".join(exposed[:4]) + "; " if exposed else "")
           + ("01-hardware/build ignored" if ignored else "01-hardware/build NOT ignored"))


def kicad_cli():
    cands = [shutil.which("kicad-cli"),
             os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "KiCad10", "bin", "kicad-cli.exe"),
             r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe"]
    return next((c for c in cands if c and os.path.exists(c)), None)


def check_kicad(tmp):
    cli = kicad_cli()
    if not cli:
        return record("v1 KiCad ERC/DRC", None, "kicad-cli not found")
    hw = pathlib.Path(tmp) / "hw"
    shutil.copytree(ROOT / "01-hardware", hw, ignore=shutil.ignore_patterns("build", "*.kicad_prl", "enclosure"))
    code, out = run([cli, "sch", "erc", "--format", "json", "--severity-error", "--severity-warning",
                     "--output", str(hw / "erc.json"), "tpms_panel.kicad_sch"], cwd=hw)
    erc = json.loads((hw / "erc.json").read_text(encoding="utf-8")) if (hw / "erc.json").exists() else None
    n_erc = sum(len(s.get("violations", [])) for s in erc.get("sheets", [])) if erc else None
    code2, out2 = run([cli, "pcb", "drc", "--format", "json", "--schematic-parity", "--severity-error",
                       "--severity-warning", "--output", str(hw / "drc.json"), "tpms_panel.kicad_pcb"], cwd=hw)
    drc = json.loads((hw / "drc.json").read_text(encoding="utf-8")) if (hw / "drc.json").exists() else None
    n_drc = (len(drc.get("violations", [])) + len(drc.get("unconnected_items", []))
             + len(drc.get("schematic_parity", []))) if drc else None
    ok = n_erc == 0 and n_drc == 0
    record("v1 KiCad ERC/DRC (errors + warnings)", ok if n_erc is not None and n_drc is not None else False,
           f"ERC {n_erc}, DRC {n_drc} (incl. unconnected and schematic parity)")


CARRIER = ROOT / "01-hardware" / "v2" / "carrier"
CARRIER_PROD = ROOT / "03-manufacturing" / "v2_carrier"


def check_carrier(tmp):
    """The generated v2 carrier: ERC and DRC (with schematic parity) on a copy of the committed files."""
    cli = kicad_cli()
    if not cli:
        return record("v2 carrier KiCad ERC/DRC", None, "kicad-cli not found")
    dst = pathlib.Path(tmp) / "carrier"
    shutil.copytree(CARRIER, dst, ignore=shutil.ignore_patterns("build", "docs", "*.kicad_prl", "__pycache__"))
    run([cli, "sch", "erc", "--format", "json", "--severity-error", "--severity-warning",
         "--output", str(dst / "erc.json"), "tpms_v2_carrier.kicad_sch"], cwd=dst)
    run([cli, "pcb", "drc", "--format", "json", "--schematic-parity", "--severity-error", "--severity-warning",
         "--output", str(dst / "drc.json"), "tpms_v2_carrier.kicad_pcb"], cwd=dst, timeout=1200)
    erc = json.loads((dst / "erc.json").read_text(encoding="utf-8")) if (dst / "erc.json").exists() else None
    drc = json.loads((dst / "drc.json").read_text(encoding="utf-8")) if (dst / "drc.json").exists() else None
    n_erc = sum(len(s.get("violations", [])) for s in erc.get("sheets", [])) if erc else None
    parts = {k: len(drc.get(k, [])) for k in ("violations", "unconnected_items", "schematic_parity")} if drc else {}
    ok = n_erc == 0 and drc is not None and not any(parts.values())
    record("v2 carrier KiCad ERC/DRC (errors + warnings)", ok,
           f"ERC {n_erc}, DRC {parts.get('violations')}, unconnected {parts.get('unconnected_items')}, "
           f"parity {parts.get('schematic_parity')}")


def check_carrier_outputs():
    """The JLCPCB files match the design: every assembled part in both BOM and CPL with an LCSC number, nothing
    hand-soldered or DNP in them, and the Gerber zip has all 6 copper layers, masks, silk, paste, outline, drill."""
    import csv
    import importlib.util
    import zipfile
    name = "tpms_v2_carrier"
    files = {k: CARRIER_PROD / f"{name}_{k}" for k in ("bom_jlcpcb.csv", "cpl_jlcpcb.csv", "gerbers_jlcpcb.zip")}
    missing = [f.name for f in files.values() if not f.exists()]
    if missing:
        return record("v2 carrier JLCPCB files", False, "missing: " + ", ".join(missing))
    spec = importlib.util.spec_from_file_location("carrier_design", CARRIER / "carrier_design.py")
    design = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(design)
    want = {p["ref"]: p["lcsc"] for p in design.PARTS if p["lcsc"] and not p["hand"] and not p["dnp"]}
    with open(files["bom_jlcpcb.csv"], newline="", encoding="utf-8") as fh:
        bom = list(csv.DictReader(fh))
    with open(files["cpl_jlcpcb.csv"], newline="", encoding="utf-8") as fh:
        cpl = {r["Designator"] for r in csv.DictReader(fh)}
    in_bom = {ref: row["LCSC Part #"] for row in bom for ref in row["Designator"].split(",")}
    problems = []
    if set(in_bom) != set(want):
        problems.append(f"BOM refs differ: {sorted(set(in_bom) ^ set(want))[:6]}")
    if cpl != set(want):
        problems.append(f"CPL refs differ: {sorted(cpl ^ set(want))[:6]}")
    wrong = [r for r in want if in_bom.get(r) not in (None, want[r])]
    if wrong:
        problems.append(f"LCSC numbers differ: {wrong[:6]}")
    with zipfile.ZipFile(files["gerbers_jlcpcb.zip"]) as z:
        names = z.namelist()
    for ext in (".gtl", ".g1", ".g2", ".g3", ".g4", ".gbl", ".gts", ".gbs", ".gto", ".gtp", ".gm1", "PTH.drl"):
        if not any(n.endswith(ext) for n in names):
            problems.append(f"zip lacks *{ext}")
    record("v2 carrier JLCPCB files", not problems,
           "; ".join(problems) if problems else f"{len(want)} placements, {len(bom)} BOM lines, {len(names)} files in the zip")


DOC_FACTS = [   # counts quoted in prose, each group tied to a live result (audit PRJ-04: stale copies kept recurring)
    (r"\b(\d+) (?:host unit |host |v2 logic )checks\b", ("logic",)),
    (r"test_logic \((\d+) checks\)", ("logic",)),
    (r"\b(\d+) (?:automated )?fit checks\b", ("enclosure",)),
    (r"make_enclosure\.py\)?,? \(?(\d+) checks\b", ("enclosure",)),
    (r"\benclosure \((\d+) checks\)", ("enclosure",)),
    (r"make_mounts\.py\)?,? \(?(\d+) checks\b", ("mounts",)),
    (r"\bmounts \((\d+)(?: checks)?\)", ("mounts",)),
    (r"\b(\d+) placements\b", ("placements",)),
    (r"\b(\d+) BOM lines\b", ("bom_lines",)),
    (r"\b(\d+) extended (?:parts|lines)\b", ("extended",)),
    (r"\b(\d+) extended \+ (\d+) preferred \+ (\d+) basic\b", ("extended", "preferred", "basic")),
    (r"\b(\d+) basic \+ (\d+) preferred\b", ("basic", "preferred")),
]


def live_counts():
    """The numbers the docs quote, from this run's results (a check that failed or was skipped gives none)."""
    found = {}
    for name, status, detail in RESULTS:
        if status != "PASS":
            continue
        for key, check, pattern in (("logic", "v2 logic host tests", r"all (\d+) v2 logic checks"),
                                    ("enclosure", "enclosure: fit checks", r"(\d+)/\d+ checks passed"),
                                    ("mounts", "mirror + LED mounts", r"(\d+)/\d+ checks passed"),
                                    ("placements", "v2 carrier JLCPCB files", r"(\d+) placements"),
                                    ("bom_lines", "v2 carrier JLCPCB files", r"(\d+) BOM lines")):
            m = re.search(pattern, detail)
            if name.startswith(check) and m:
                found[key] = int(m.group(1))
    bom = CARRIER_PROD / "tpms_v2_carrier_bom_jlcpcb.csv"
    if bom.exists():
        import csv
        with open(bom, newline="", encoding="utf-8") as fh:
            libs = [r["Library"] for r in csv.DictReader(fh)]
        found.update({k: libs.count(k) for k in ("basic", "preferred", "extended")})
    return found


def check_doc_counts():
    """Every count the docs, the viewer data and the premortem quote (tests, fit checks, BOM lines...) matches the
    live result. Quoted history is skipped: a count in quotes, or after "was"."""
    live = live_counts()
    if not live:
        return record("counts quoted in the docs are current", None, "no live counts (their checks were skipped)")
    stale, seen, files = [], 0, set()
    for p in sorted(ROOT.rglob("*")):
        if p.suffix not in (".md", ".json", ".js", ".html") or not p.is_file():
            continue
        rel = p.relative_to(ROOT)
        if set(rel.parts) & {".git", "node_modules", "git_ignoreme", "vendor", "build", "__pycache__"}:
            continue
        for n, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            for pattern, keys in DOC_FACTS:
                for m in re.finditer(pattern, line):
                    before = line[max(0, m.start() - 40):m.start()]
                    if before.endswith(('"', "“", "'")) or re.search(r"\bwas\s*$", before):
                        continue
                    for i, key in enumerate(keys, 1):
                        if key not in live:
                            continue
                        seen += 1
                        files.add(rel)
                        if int(m.group(i)) != live[key]:
                            stale.append(f"{rel.as_posix()}:{n} says {m.group(i)} ({key}), live {live[key]}")
    record("counts quoted in the docs are current", not stale,
           "; ".join(stale[:6]) + (f" (+{len(stale) - 6} more)" if len(stale) > 6 else "") if stale else
           f"{seen} quoted counts in {len(files)} files match: " + ", ".join(f"{k} {v}" for k, v in live.items()))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--skip", nargs="*", default=[], help="kicad, enclosure, js, links, docs")
    a = ap.parse_args()
    compiler = cxx()
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        host_test("v2 logic host tests", "02-firmware/v2", "src/logic",
                  ["test/host/test_logic.cpp"] + [f"src/logic/{m}.cpp" for m in
                                                  ("blinker", "pi_power", "alerts", "link", "obd")], tmp, compiler)
        host_test("v1 TPMS decoder host tests", "02-firmware/bringup", "src",
                  ["test/host/test_decode.cpp", "src/rf_decode.cpp", "src/eg53ma4.cpp"], tmp, compiler)
        check_pinmap()
        if "enclosure" not in a.skip:
            check_enclosure(tmp)
        check_stl_watertight()
        check_sync()
        if "js" not in a.skip:
            check_js(tmp)
        if "links" not in a.skip:
            check_links()
        check_repo_hygiene()
        check_carrier_outputs()
        if "kicad" not in a.skip:
            check_kicad(tmp)
            check_carrier(tmp)
        if "docs" not in a.skip:
            check_doc_counts()
    width = max(len(n) for n, _, _ in RESULTS)
    for name, status, detail in RESULTS:
        print(f"{status:4s}  {name:{width}s}  {detail}".encode("ascii", "replace").decode())
    failed = sum(s == "FAIL" for _, s, _ in RESULTS)
    print(f"\n{len(RESULTS)} checks: {sum(s == 'PASS' for _, s, _ in RESULTS)} passed, {failed} failed, "
          f"{sum(s == 'SKIP' for _, s, _ in RESULTS)} skipped")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
