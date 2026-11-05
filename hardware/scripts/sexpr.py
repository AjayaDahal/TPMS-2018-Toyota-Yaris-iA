"""Minimal S-expression reader/writer for KiCad files (symbols, schematics, netlists)."""
import copy
import re


class Sym(str):
    """Unquoted atom (keyword or number)."""


class QStr(str):
    """Quoted string atom."""


_TOKEN = re.compile(r'\s*(?:(\()|(\))|"((?:[^"\\]|\\.)*)"|([^\s()"]+))', re.S)


def _unescape(s):
    return s.replace('\\"', '"').replace("\\n", "\n").replace("\\\\", "\\")


def _escape(s):
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def parse(text):
    stack = [[]]
    pos, n = 0, len(text)
    while pos < n:
        m = _TOKEN.match(text, pos)
        if not m:
            if text[pos:].strip():
                raise ValueError(f"S-expression parse error at {pos}: {text[pos:pos + 60]!r}")
            break
        pos = m.end()
        lp, rp, qs, atom = m.groups()
        if lp:
            node = []
            stack[-1].append(node)
            stack.append(node)
        elif rp:
            stack.pop()
        elif qs is not None:
            stack[-1].append(QStr(_unescape(qs)))
        elif atom is not None:
            stack[-1].append(Sym(atom))
    return stack[0]


def _atom(a):
    if isinstance(a, QStr):
        return '"' + _escape(a) + '"'
    if isinstance(a, bool):
        return "yes" if a else "no"
    if isinstance(a, float):
        s = f"{a:.4f}".rstrip("0").rstrip(".")
        return "0" if s in ("-0", "") else s
    if isinstance(a, int):
        return str(a)
    if isinstance(a, Sym):
        return str(a)
    # plain python str -> quoted
    return '"' + _escape(str(a)) + '"'


def dumps(node, indent=0):
    if not isinstance(node, list):
        return _atom(node)
    if not any(isinstance(x, list) for x in node):
        return "(" + " ".join(_atom(x) for x in node) + ")"
    pad = "\t" * (indent + 1)
    head = []
    rest = []
    for x in node:
        if isinstance(x, list) or rest:
            rest.append(x)
        else:
            head.append(x)
    out = "(" + " ".join(_atom(x) for x in head)
    for x in rest:
        out += "\n" + pad + dumps(x, indent + 1)
    return out + "\n" + "\t" * indent + ")"


def find(node, key):
    """First child list whose head is `key`."""
    for x in node:
        if isinstance(x, list) and x and x[0] == key:
            return x
    return None


def find_all(node, key):
    return [x for x in node if isinstance(x, list) and x and x[0] == key]


def walk(node, key):
    """Recursively yield all lists whose head is `key`."""
    if isinstance(node, list):
        if node and node[0] == key:
            yield node
        for x in node:
            if isinstance(x, list):
                yield from walk(x, key)


def deepcopy(node):
    return copy.deepcopy(node)
