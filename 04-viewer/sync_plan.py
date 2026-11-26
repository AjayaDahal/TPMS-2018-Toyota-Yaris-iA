#!/usr/bin/env python3
"""Copy the v2 premortem, order gate and enclosure summary into the viewer's system_plan.json.

    python 04-viewer/sync_plan.py           # update viewer/system_plan.json
    python 04-viewer/sync_plan.py --check   # exit 1 if it is out of date

Sources (single source of truth): 00-project-management/PREMORTEM_v2.md (its markdown tables) and
01-hardware/enclosure/enclosure_report.json (written by make_enclosure.py). Everything else in system_plan.json is
edited by hand.
"""
import argparse
import html
import json
import pathlib
import posixpath
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PLAN = ROOT / "04-viewer" / "viewer" / "system_plan.json"
PREMORTEM = ROOT / "00-project-management" / "PREMORTEM_v2.md"
ENCLOSURE = ROOT / "01-hardware" / "enclosure" / "enclosure_report.json"


def inline(md, base="00-project-management"):
    """Markdown cell -> small HTML: bold, code, links (made relative to the viewer page)."""
    t = html.escape(md.strip(), quote=False)

    def link(m):
        text, url = m.group(1), m.group(2)
        if url.startswith(("http://", "https://")):
            return f'<a href="{url}" target="_blank" rel="noopener">{text}</a>'
        if url.startswith("#"):
            return text
        path = posixpath.normpath(posixpath.join(base, url.split("#")[0]))
        return f'<a href="../../{path}" target="_blank">{text}</a>'

    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link, t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    return t


def tables(md):
    """Yield (heading, header cells, rows) for every markdown table, with the nearest heading above it."""
    heading, lines = "", md.splitlines()
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("#"):
            heading = ln.lstrip("#").strip()
        if ln.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:|-]+\|$", lines[i + 1].strip()):
            head = [c.strip() for c in ln.strip().strip("|").split("|")]
            rows, i = [], i + 2
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([c.strip() for c in split_row(lines[i])])
                i += 1
            yield heading, head, rows
            continue
        i += 1


def split_row(line):
    # split on | that are not inside backticks
    cells, cur, code = [], "", False
    for ch in line.strip().strip("|"):
        if ch == "`":
            code = not code
        if ch == "|" and not code:
            cells.append(cur)
            cur = ""
        else:
            cur += ch
    cells.append(cur)
    return cells


def status_keys(text):
    t = text.lower()
    keys = []
    if "fixed" in t or t.startswith("done"):
        keys.append("fixed")
    if "you" in t:
        keys.append("you")
    if "phase 2" in t:
        keys.append("phase2")
    if "accepted" in t:
        keys.append("accepted")
    if any(w in t for w in ("plan", "decision", "buy", "g7", "next", "pi software")) and "fixed" not in keys:
        keys.append("plan")
    return keys or ["plan"]


def build():
    md = PREMORTEM.read_text(encoding="utf-8")
    premortem, gate = [], []
    for heading, head, rows in tables(md):
        h = [c.lower() for c in head]
        if heading.startswith("Order gate"):
            for r in rows:
                st = r[2]
                key = "done" if st.lower().startswith("**done") or st.lower().startswith("done") else (
                    "next" if st.lower().startswith("next") else "you")
                gate.append(dict(id=r[0], needed=inline(r[1]), status=key, detail=inline(r[2])))
        elif heading.startswith("Corrections"):
            for r in rows:
                premortem.append(dict(id=r[0], category="Corrections to the earlier plan", likelihood="Caught",
                                      title=inline(r[1]), cause=inline(r[2]), fix=inline(r[3]),
                                      status="Fixed", status_keys=["fixed"]))
        elif h[:2] == ["#", "how it fails"]:
            for r in rows:
                premortem.append(dict(id=r[0], category=heading, likelihood=inline(r[2]), title=inline(r[1]),
                                      cause="", fix=inline(r[3]), status=inline(r[4]), status_keys=status_keys(r[4])))
    if not gate or not premortem:
        sys.exit("PREMORTEM_v2.md: order gate or failure tables not found")
    rep = json.loads(ENCLOSURE.read_text(encoding="utf-8"))
    enclosure = dict(
        overall_mm=rep["overall_mm"], box_mm=rep["box_mm"], z_levels_mm=rep["z_levels_mm"], mount=rep["mount"],
        ports_face=rep["ports_face"], pcb_constraints=rep["pcb_constraints"], hardware=rep["hardware"],
        volumes_cm3=rep["volumes_cm3"],
        checks=dict(passed=sum(c["ok"] for c in rep["checks"]), total=len(rep["checks"]), all_ok=rep["all_ok"]),
        assembly=[dict(name=k[4:], file="../../01-hardware/enclosure/" + v["file"], color=v["color"], label=v["label"])
                  for k, v in rep["files"].items() if k.startswith("asm_")],
        print_files=["../../01-hardware/enclosure/" + v["file"] for k, v in rep["files"].items()
                     if k.startswith("print_")])
    return premortem, gate, enclosure


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    premortem, gate, enclosure = build()
    new = dict(plan, premortem=premortem, order_gate=gate, enclosure=enclosure)
    text = json.dumps(new, indent=2, ensure_ascii=False) + "\n"
    if a.check:
        ok = text == PLAN.read_text(encoding="utf-8")
        print("system_plan.json is up to date" if ok else "system_plan.json is OUT OF DATE: run sync_plan.py")
        return 0 if ok else 1
    PLAN.write_text(text, encoding="utf-8")
    cats = sorted({p["category"] for p in premortem})
    print(f"{PLAN}: {len(premortem)} premortem items in {len(cats)} groups, {len(gate)} gates, enclosure "
          f"{enclosure['checks']['passed']}/{enclosure['checks']['total']} checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
