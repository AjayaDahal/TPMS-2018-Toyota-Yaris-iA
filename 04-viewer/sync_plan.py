#!/usr/bin/env python3
"""Copy the v2 premortem, order gate and enclosure summary into the viewer's system_plan.json.

    python 04-viewer/sync_plan.py           # update viewer/system_plan.json
    python 04-viewer/sync_plan.py --check   # exit 1 if it is out of date

Sources (single source of truth): 00-project-management/PREMORTEM_v2.md (its markdown tables) and
01-hardware/enclosure/enclosure_report.json (written by make_enclosure.py). Everything else in system_plan.json is
edited by hand.

The parser is strict, so an edit can't drop rows silently: tables are found by their header row, every row must have
the header's column count, table rows outside a table (a blank line inside a table), duplicate ids, unknown status
words and unknown gate states are errors, and the ids added or removed are printed.
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

GATE_HEAD = ["Gate", "Needed before ordering", "Status"]
CORRECTION_HEAD = ["#", "Earlier plan said", "Problem", "Now"]
FAILURE_HEAD = ["#", "How it fails"]
# Status words, read from the start of each "+"/";" part outside parentheses -> filter pill
STATUS_WORDS = [("fixed", "fixed"), ("done", "fixed"), ("you", "you"), ("phase 2", "phase2"),
                ("accepted", "accepted"), ("decision", "plan"), ("plan", "plan"), ("buy", "plan"), ("g7", "plan"),
                ("next", "plan"), ("pi software", "plan"), ("pi side", "plan")]


class PlanError(Exception):
    pass


def inline(md, base="00-project-management"):
    """Markdown cell -> small HTML: bold, code, links (made relative to the viewer page)."""
    t = html.escape(md.strip(), quote=False)

    def link(m):
        text, url = m.group(1), m.group(2)
        attr = url.replace('"', "&quot;").replace("'", "&#x27;")
        if url.startswith(("http://", "https://")):
            return f'<a href="{attr}" target="_blank" rel="noopener">{text}</a>'
        if url.startswith("#"):
            return text
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", url):  # javascript:, data:, mailto: ... no link
            return text
        path = posixpath.normpath(posixpath.join(base, url.split("#")[0]))
        path = path.replace('"', "&quot;").replace("'", "&#x27;")
        return f'<a href="../../{path}" target="_blank">{text}</a>'

    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link, t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    return t


def split_row(line):
    """Cells of a table row; | inside backticks or escaped as \\| is text."""
    cells, cur, code, i = [], "", False, 0
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    while i < len(s):
        ch = s[i]
        if ch == "\\" and i + 1 < len(s) and s[i + 1] == "|":
            cur += "|"
            i += 2
            continue
        if ch == "`":
            code = not code
        if ch == "|" and not code:
            cells.append(cur)
            cur = ""
        else:
            cur += ch
        i += 1
    cells.append(cur)
    return [c.strip() for c in cells]


def tables(md):
    """Yield (heading, header cells, rows, line number) for every markdown table outside code fences. A table row
    that isn't part of a table (e.g. after a blank line inside one) is an error."""
    lines, heading, fence, i, used, found = md.splitlines(), "", False, 0, set(), []
    while i < len(lines):
        ln = lines[i]
        if ln.lstrip().startswith("```"):
            fence = not fence
        elif not fence and ln.startswith("#"):
            heading = ln.lstrip("#").strip()
        elif not fence and ln.startswith("|") and i + 1 < len(lines) and \
                re.match(r"^\|[\s:|-]+\|$", lines[i + 1].strip()):
            head, start = split_row(ln), i
            used.update((i, i + 1))
            rows, i = [], i + 2
            while i < len(lines) and lines[i].startswith("|"):
                row = split_row(lines[i])
                if len(row) != len(head):
                    raise PlanError(f"PREMORTEM_v2.md:{i + 1}: {len(row)} cells, the header has {len(head)} "
                                    f"(an unescaped | in a cell?)")
                rows.append(row)
                used.add(i)
                i += 1
            found.append((heading, head, rows, start + 1))
            continue
        i += 1
    fence = False
    for n, ln in enumerate(lines):
        if ln.lstrip().startswith("```"):
            fence = not fence
        elif not fence and ln.startswith("|") and n not in used:
            raise PlanError(f"PREMORTEM_v2.md:{n + 1}: table row outside a table (blank line inside a table?)")
        elif not fence and n not in used and len(re.findall(r"(?<!\\)\|", re.sub(r"`[^`]*`", "", ln))) >= 4:
            raise PlanError(f"PREMORTEM_v2.md:{n + 1}: looks like a table row without its leading |")
    return found


def split_status(text):
    parts, cur, depth = [], "", 0
    for ch in text:
        depth += ch == "("
        depth -= ch == ")" and depth > 0
        if ch in "+;" and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    return [p.strip() for p in parts if p.strip()]


def status_keys(text):
    """Filter pills for a status cell, one per part: 'Decision (G5) + Fixed (firmware)' -> plan, fixed."""
    keys = []
    for part in split_status(re.sub(r"\*\*|`", "", text)):
        head = re.sub(r"\([^)]*\)", "", part).strip().lower()
        key = next((k for word, k in STATUS_WORDS if re.match(re.escape(word) + r"\b", head)), None)
        if key is None:
            raise PlanError(f"unknown status \"{part}\" in \"{text}\": start each part with one of "
                            + ", ".join(sorted({w for w, _ in STATUS_WORDS})))
        if key not in keys:
            keys.append(key)
    return keys or ["plan"]


def gate_key(status):
    s = re.sub(r"\*\*", "", status).strip().lower()
    for word in ("done", "next", "you"):
        if re.match(word + r"\b", s):
            return word
    raise PlanError(f"order gate status \"{status}\" must start with Done, Next or You")


def build():
    md = PREMORTEM.read_text(encoding="utf-8")
    premortem, gate, kinds = [], [], set()
    for heading, head, rows, line in tables(md):
        if head == GATE_HEAD:
            kinds.add("gate")
            for r in rows:
                gate.append(dict(id=r[0], needed=inline(r[1]), status=gate_key(r[2]), detail=inline(r[2])))
        elif head[:4] == CORRECTION_HEAD:
            kinds.add("corrections")
            for r in rows:
                premortem.append(dict(id=r[0], category="Corrections to the earlier plan", likelihood="Caught",
                                      title=inline(r[1]), cause=inline(r[2]), fix=inline(r[3]),
                                      status="Fixed", status_keys=["fixed"]))
        elif head[:2] == FAILURE_HEAD:
            if len(head) != 5:
                raise PlanError(f"PREMORTEM_v2.md:{line}: a failure table needs 5 columns "
                                f"(# | How it fails | Likely? | Fix | Status)")
            kinds.add("failures")
            for r in rows:
                premortem.append(dict(id=r[0], category=heading, likelihood=inline(r[2]), title=inline(r[1]),
                                      cause="", fix=inline(r[3]), status=inline(r[4]), status_keys=status_keys(r[4])))
        elif head and head[0] == "#":
            raise PlanError(f"PREMORTEM_v2.md:{line}: unknown table header \"{' | '.join(head)}\" (a renamed "
                            f"column would drop the table from the viewer)")
    missing = {"gate", "corrections", "failures"} - kinds
    if missing:
        raise PlanError("PREMORTEM_v2.md: no " + ", ".join(sorted(missing)) + " table found (header changed?)")
    ids = [p["id"] for p in premortem] + [g["id"] for g in gate]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise PlanError("PREMORTEM_v2.md: duplicate ids " + ", ".join(dupes))
    rep = json.loads(ENCLOSURE.read_text(encoding="utf-8"))
    enclosure = dict(
        display=rep["display"], overall_mm=rep["overall_mm"], proud_of_trim_mm=rep["proud_of_trim_mm"],
        box_mm=rep["box_mm"], z_levels_mm=rep["z_levels_mm"], mount=rep["mount"], ports_face=rep["ports_face"],
        display_mount=rep["display_mount"], pcb_constraints=rep["pcb_constraints"], hardware=rep["hardware"],
        volumes_cm3=rep["volumes_cm3"],
        checks=dict(passed=sum(c["ok"] for c in rep["checks"]), total=len(rep["checks"]), all_ok=rep["all_ok"]),
        assembly=[dict(name=k[4:], file="../../01-hardware/enclosure/" + v["file"], color=v["color"], label=v["label"])
                  for k, v in rep["files"].items() if k.startswith("asm_")],
        print_files=["../../01-hardware/enclosure/" + v["file"] for k, v in rep["files"].items()
                     if k.startswith("print_")])
    return premortem, gate, enclosure


def id_changes(old, new):
    o = [p["id"] for p in old.get("premortem", [])] + [g["id"] for g in old.get("order_gate", [])]
    n = [p["id"] for p in new["premortem"]] + [g["id"] for g in new["order_gate"]]
    added, removed = [i for i in n if i not in o], [i for i in o if i not in n]
    return ("added " + ", ".join(added) if added else "") + ("; " if added and removed else "") + \
        ("REMOVED " + ", ".join(removed) if removed else "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    try:
        premortem, gate, enclosure = build()
    except PlanError as err:
        print(f"error: {err}", file=sys.stderr)
        return 2
    new = dict(plan, premortem=premortem, order_gate=gate, enclosure=enclosure)
    text = json.dumps(new, indent=2, ensure_ascii=False) + "\n"
    changes = id_changes(plan, new)
    if a.check:
        ok = text == PLAN.read_text(encoding="utf-8")
        print("system_plan.json is up to date" if ok else
              "system_plan.json is OUT OF DATE: run sync_plan.py" + (f" ({changes})" if changes else ""))
        return 0 if ok else 1
    PLAN.write_text(text, encoding="utf-8")
    cats = sorted({p["category"] for p in premortem})
    print(f"{PLAN}: {len(premortem)} premortem items in {len(cats)} groups, {len(gate)} gates, enclosure "
          f"{enclosure['checks']['passed']}/{enclosure['checks']['total']} checks" + (f"; {changes}" if changes else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
