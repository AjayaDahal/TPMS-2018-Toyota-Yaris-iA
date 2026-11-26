#!/usr/bin/env python3
"""1:1 fit template for the v2 build (no dependencies: the PDF is written directly).

Page 1: the Official Raspberry Pi 7" Touch Display, front view as seen by the driver, over the Yaris iA console
        opening, with the mounting holes, the Pi 4 standoffs and the flat cable.
Page 2: the 100 x 100 mm v2 carrier PCB with its mounting holes and planning zones.

    python 01-hardware/scripts/make_v2_fit_template.py   ->  01-hardware/docs/v2_fit_template_1to1.pdf

Print at 100 % ("Actual size") on US Letter landscape and check the 100 mm bar with a caliper.
Display data: Raspberry Pi 7" display mechanical drawing LMD-D/5624/KIT-LC-V3 rev 003 and product brief.
Console opening: the v1 paper fit (panel_config.py).
"""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import panel_config as CFG  # noqa: E402

OUT = HERE.parent / "docs" / "v2_fit_template_1to1.pdf"
PT = 72 / 25.4
PAGE_W, PAGE_H = 279.4, 215.9                      # US Letter landscape, like the v1 template

# Display, front view: x to the right, y down, origin at the top-left corner of the glass. The flat cable leaves
# the bottom edge. The drawing dimensions the back view, which is mirrored left-right.
GLASS_W, GLASS_H = 192.96, 110.76
ACTIVE = (19.44, 11.41, 154.08, 85.92)
FRAME = (GLASS_W - 11.89 - 166.2, GLASS_H - 3.53 - 100.6, 166.2, 100.6)
# The drawing dimensions the M3 holes from the outer frame flange (11.89 line: 20.0 from each side, so they are
# centred on the flange) and the M2.5 standoffs from the frame body (12.54 line).
M3 = [(GLASS_W - 11.89 - 20.0 - dx, GLASS_H - 23.53 - dy) for dx in (0, 126.2) for dy in (0, 65.65)]
M25 = [(GLASS_W - 12.54 - 48.45 - dx, GLASS_H - 34.33 - dy) for dx in (0, 58.0) for dy in (0, 49.0)]
FPC = (GLASS_W - 83.74 - 25.5, GLASS_H, 25.5, 39.62)

WIN_ANSI = {"×": 0xD7, "°": 0xB0, "Ø": 0xD8, "±": 0xB1, "–": 0x96, "—": 0x97, "µ": 0xB5, "’": 0x92, "·": 0xB7,
            "²": 0xB2}


def pdf_text(s):
    out = []
    for ch in s:
        if ch in "\\()":
            out.append("\\" + ch)
        elif ch in WIN_ANSI:
            out.append("\\%03o" % WIN_ANSI[ch])
        elif ord(ch) < 128:
            out.append(ch)
        else:
            out.append("?")
    return "".join(out)


class Page:
    def __init__(self):
        self.ops = []

    def _p(self, x, y):
        return x * PT, (PAGE_H - y) * PT

    def style(self, rgb=(0, 0, 0), width=0.25, dash=None):
        r, g, b = rgb
        self.ops.append(f"{r:.3f} {g:.3f} {b:.3f} RG {r:.3f} {g:.3f} {b:.3f} rg {width * PT:.3f} w")
        self.ops.append(f"[{dash[0] * PT:.2f} {dash[1] * PT:.2f}] 0 d" if dash else "[] 0 d")

    def line(self, x1, y1, x2, y2):
        a, b = self._p(x1, y1), self._p(x2, y2)
        self.ops.append(f"{a[0]:.3f} {a[1]:.3f} m {b[0]:.3f} {b[1]:.3f} l S")

    def poly(self, pts, close=True):
        a = self._p(*pts[0])
        path = [f"{a[0]:.3f} {a[1]:.3f} m"] + [f"{p[0]:.3f} {p[1]:.3f} l" for p in (self._p(*q) for q in pts[1:])]
        self.ops.append(" ".join(path) + (" h S" if close else " S"))

    def rect(self, x, y, w, h):
        self.poly([(x, y), (x + w, y), (x + w, y + h), (x, y + h)])

    def circle(self, cx, cy, r, cross=True):
        k = 0.5523 * r
        pts = [(cx + r, cy), (cx + r, cy + k), (cx + k, cy + r), (cx, cy + r), (cx - k, cy + r), (cx - r, cy + k),
               (cx - r, cy), (cx - r, cy - k), (cx - k, cy - r), (cx, cy - r), (cx + k, cy - r), (cx + r, cy - k),
               (cx + r, cy)]
        p = [self._p(*q) for q in pts]
        seg = [f"{p[0][0]:.3f} {p[0][1]:.3f} m"]
        for i in range(1, 13, 3):
            seg.append(" ".join(f"{p[j][0]:.3f} {p[j][1]:.3f}" for j in (i, i + 1, i + 2)) + " c")
        self.ops.append(" ".join(seg) + " S")
        if cross:
            self.line(cx - r - 1, cy, cx + r + 1, cy)
            self.line(cx, cy - r - 1, cx, cy + r + 1)

    def text(self, x, y, s, size=7.0, bold=False, rgb=(0, 0, 0), center=False):
        if center:
            x -= len(s) * size * 0.5 / PT / 2
        px, py = self._p(x, y)
        r, g, b = rgb
        self.ops.append(f"BT {r:.3f} {g:.3f} {b:.3f} rg /{'F2' if bold else 'F1'} {size:.1f} Tf "
                        f"{px:.3f} {py:.3f} Td ({pdf_text(s)}) Tj ET")

    def wrapped(self, x, y, width, s, size=7.0, bold=False, lead=3.3, rgb=(0, 0, 0)):
        per_line = max(10, int(width * PT / (size * 0.5)))
        words, line = s.split(), ""
        for w in words:
            if line and len(line) + 1 + len(w) > per_line:
                self.text(x, y, line, size, bold, rgb)
                y += lead
                line = w
            else:
                line = f"{line} {w}" if line else w
        if line:
            self.text(x, y, line, size, bold, rgb)
            y += lead
        return y

    def scale_bar(self, x, y):
        self.style((0, 0, 0), 0.35)
        self.line(x, y, x + 100, y)
        for i in range(11):
            self.line(x + 10 * i, y, x + 10 * i, y - (2.5 if i % 5 == 0 else 1.5))
        self.text(x, y + 4, "100 mm: print at 100 % (Actual size) and check this bar with a caliper", 6.5)


BLACK, GREY, RED, BLUE, GREEN, ORANGE = (0, 0, 0), (0.45, 0.45, 0.45), (0.8, 0.1, 0.1), (0.1, 0.3, 0.8), \
    (0.1, 0.5, 0.2), (0.85, 0.45, 0.0)


def page_display():
    pg = Page()
    pg.text(10, 9, "v2 fit template 1:1  ·  Official Raspberry Pi 7\" Touch Display in the Yaris iA console", 11, True)
    pg.text(10, 14, "Front view as seen from the driver's seat. Dashed = on the back of the display, seen through "
                    "the glass. Red = console opening from the v1 paper fit.", 7)
    ox, oy = 12.0, 24.0
    cx = ox + GLASS_W / 2

    top, bottom, height = CFG.OPENING_TOP_WIDTH, CFG.OPENING_BOTTOM_WIDTH, CFG.OPENING_HEIGHT
    pg.style(RED, 0.3, (2.5, 1.5))
    pg.poly([(cx - top / 2, oy), (cx + top / 2, oy), (cx + bottom / 2, oy + height), (cx - bottom / 2, oy + height)])
    width_at_glass_bottom = top - (top - bottom) * GLASS_H / height
    pg.text(ox, oy + 155, f"Console opening (v1 paper fit): {top:g} top / {bottom:g} bottom × {height:g} high. "
                          f"At the glass's bottom edge it is only {width_at_glass_bottom:.1f} mm wide, so the glass",
            6.8, rgb=RED)
    pg.text(ox, oy + 158.3, f"overhangs the trim by ~{(GLASS_W - width_at_glass_bottom) / 2:.0f} mm on each side: "
                            "it can only sit in front of the opening, never inside it.", 6.8, rgb=RED)

    pg.style(GREY, 0.25, (1.5, 1.0))
    fx, fy, fw, fh = FRAME
    pg.rect(ox + fx, oy + fy, fw, fh)
    pg.text(ox + fx + 1.5, oy + fy + fh - 1.6, "back metal frame 166.2 × 100.6", 6, rgb=GREY)
    px, py, pw, ph = FPC
    pg.rect(ox + px, oy + py, pw, ph)
    pg.text(ox + px + pw / 2, oy + py + 6, "flat cable", 6, rgb=GREY, center=True)
    pg.text(ox + px + pw / 2, oy + py + 9, "(folds behind)", 6, rgb=GREY, center=True)

    xs, ys = sorted({p[0] for p in M25}), sorted({p[1] for p in M25})
    pg.style(GREEN, 0.25, (1.5, 1.0))
    # Seen from behind, the Pi sits the usual way round on the official display (GPIO header on top, ports to the
    # right: Raspberry Pi documentation photo), so in this front view its USB/Ethernet end is on the left.
    pg.rect(ox + xs[0] - 23.5, oy + ys[0] - 3.5, 85.0, 56.0)
    pg.text(ox + xs[0] - 22, oy + ys[1] + 2.4, "Pi 4 (85 × 56): USB/Ethernet end on this side (check yours)", 6,
            rgb=GREEN)
    for x, y in M25:
        pg.circle(ox + x, oy + y, 1.35)
    pg.text(ox + xs[0] + 2, oy + ys[0] - 1.4, "4× M2.5 Pi standoffs, 58.0 × 49.0", 6, rgb=GREEN)

    pg.style(ORANGE, 0.25, (1.5, 1.0))
    for x, y in M3:
        pg.circle(ox + x, oy + y, 1.5)
    hx = max(p[0] for p in M3)
    hy = min(p[1] for p in M3)
    pg.text(ox + hx - 30, oy + hy - 2.6, "4× M3 bracket holes, 126.2 × 65.65", 6, rgb=ORANGE)

    pg.style(BLACK, 0.4)
    pg.rect(ox, oy, GLASS_W, GLASS_H)
    pg.text(ox + 2, oy + 4.5, f"GLASS {GLASS_W} × {GLASS_H} (5.96 mm thick)", 7, True)
    pg.text(ox + 2, oy + GLASS_H - 1.3, "cable edge = bottom (drawing: viewing direction 6 o'clock)", 6)
    ax, ay, aw, ah = ACTIVE
    pg.style(BLUE, 0.3)
    pg.rect(ox + ax, oy + ay, aw, ah)
    pg.text(ox + ax + aw / 2, oy + ay + ah / 2, f"active area {aw} × {ah} (800 × 480)", 8, rgb=BLUE, center=True)

    x, y, w = 211.0, 26.0, 62.0
    y = pg.wrapped(x, y, w, "BEFORE ORDERING THE v2 PCB", 8, True, 4)
    notes = [
        "1. Cut out the glass outline, glue it to 5 mm foam board and tape a 112 × 120 × 61 mm block behind it, "
        "centred under the glass: that is the printed enclosure's rear box (enclosure/README.md). Overall "
        "205.6 × 127.9 × 71.8 mm.",
        "2. Hold it where you would mount it with the shifter in P. Check the shifter through P-R-N-D-M with your hand "
        "on it, the HVAC knobs, the 12 V/USB/AUX ports behind the opening, and the view from your seat. The box "
        "needs about 66 mm of clear depth in the pocket.",
        "3. Viewing direction 6 o'clock = best seen from below (docs: 50° from the top, 70° from the bottom). In the "
        "console you look down at it, so mount it upside down (cable edge up) and rotate the image 180°.",
        "4. Rated 0-50 °C in the product brief's safety notes (the docs page lists -20 to +70 °C). Keep it out of "
        "direct sun; 250 cd/m² is dim in daylight.",
        "5. Option B (dash top) gets more sun and heat; check the windshield view and stay clear of the passenger "
        "airbag area.",
        "Sources: Raspberry Pi 7\" display mechanical drawing LMD-D/5624/KIT-LC-V3 rev 003, product brief, "
        "documentation page; v1 panel_config.py.",
    ]
    for n in notes:
        y = pg.wrapped(x, y, w, n, 6.8) + 1.6
    pg.scale_bar(12, 196)
    return pg


def page_pcb():
    pg = Page()
    pg.text(10, 9, "v2 fit template 1:1  ·  100 × 100 mm carrier PCB (6-layer)", 11, True)
    pg.text(10, 14, "Parts side up, as you see it with the enclosure lid off. Zones are planning estimates until the "
                    "KiCad layout exists; the keep-outs come from the enclosure generator.", 7)
    bx, by = 34.0, 36.0
    pg.style(BLACK, 0.4)
    pg.rect(bx, by, 100, 100)
    pg.style(ORANGE, 0.3)
    for x in (4, 96):
        for y in (4, 96):
            pg.circle(bx + x, by + y, 1.6)
    pg.text(bx + 7, by + 98.8, "4× M3, 92 × 92 (enclosure posts)", 6, rgb=ORANGE)

    pg.style(GREY, 0.25, (1.5, 1.0))
    zones = [
        ((62, 2.5, 30, 18), "CC1101 + SMA (to the right)"),
        ((0, 12, 28, 52), "ESP32 DevKit (USB up)"),
        ((64, 62, 25.4, 25.4), "Pololu D36V50F5"),
        ((34, 88, 12, 10), "J1 12 V"),
        ((50, 88, 12, 10), "J5 5 V/5 A"),
        ((11, 88, 21, 10), "JST-GH harness"),
    ]
    for (x, y, w, h), label in zones:
        pg.rect(bx + x, by + y, w, h)
        pg.text(bx + x + 1, by + y + 3.5, label, 5.8, rgb=GREY)
    pg.style(RED, 0.3, (1.0, 0.8))
    pg.rect(bx + 29, by + 30, 32, 32)
    pg.text(bx + 30, by + 34, "FAN ZONE: parts max 6 mm", 5.8, rgb=RED)
    pg.text(bx + 30, by + 37.5, "(lid fan above)", 5.8, rgb=RED)
    pg.rect(bx + 86, by + 28.5, 14, 12)
    pg.text(bx + 86.5, by + 26.5, "SMA bulkhead", 5.8, rgb=RED)
    for x in (0, 90):
        for y in (0, 90):
            pg.rect(bx + x, by + y, 10, 10)
    pg.text(bx + 11, by + 8.5, "corners: no pins", 5.8, rgb=RED)

    pg.text(bx + 50, by - 3, "top edge: DevKit USB, CC1101", 6.5, center=True)
    pg.text(bx + 50, by + 105, "bottom edge: 12 V ACC in, 5 V / 5 A to the Pi, JST-GH harness (right-angle; the lid's "
                               "cable exit is above J1)", 6.5, center=True)
    pg.text(bx - 31, by + 46.5, "left edge: the Pi's", 6.5)
    pg.text(bx - 31, by + 50, "USB window side", 6.5)
    pg.text(bx + 103, by + 46.5, "right edge:", 6.5)
    pg.text(bx + 103, by + 50, "SMA bulkhead wall", 6.5)
    pg.text(bx, by + 110, "Drawn for the default mount (cable edge up). With --mount normal the left and right "
                          "keep-outs swap sides.", 6, rgb=GREY)

    x, y, w = 176.0, 36.0, 95.0
    notes = [
        "The board rides in the printed enclosure behind the Pi, parts facing the lid, on 4 posts (M3, 92 × 92 mm). "
        "Its flat underside faces the Pi with a 3 mm air gap: through-hole pins at most 2.5 mm long.",
        "Height budget 16 mm above the board (DevKit on sockets ~13, Pololu on sockets ~15). Connectors: right-angle "
        "at the board edges, so mated plugs stay under 16 mm. Under the lid fan (red square): parts max 6 mm.",
        "Antenna: the CC1101's own SMA takes a short RG316 lead to a bulkhead SMA in the enclosure wall (red strip: no "
        "parts), then a 30 cm lead takes the 315 MHz whip away from the Pi, the display and the camera cables.",
        "Power on Micro-Fit 3.0 (5 A per contact, 18 AWG); signals on keyed JST-GH. The alert pod (mute button + "
        "buzzer) plugs into one 4-pin JST-GH.",
        "Hand soldering a 6-layer board: through-hole pads on the inner planes need thermal reliefs (layout rule).",
    ]
    for n in notes:
        y = pg.wrapped(x, y, w, n, 7) + 2
    pg.scale_bar(34, 196)
    return pg


def write_pdf(pages, path):
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", None,
            "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
            "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>"]
    kids = []
    for pg in pages:
        stream = "\n".join(pg.ops).encode("latin-1")
        objs.append(f"<< /Length {len(stream)} >>\nstream\n".encode("latin-1") + stream + b"\nendstream")
        content = len(objs)
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_W * PT:.2f} {PAGE_H * PT:.2f}] "
                    f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents {content} 0 R >>")
        kids.append(len(objs))
    objs[1] = f"<< /Type /Pages /Kids [{' '.join(f'{k} 0 R' for k in kids)}] /Count {len(kids)} >>"

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode("latin-1")
        out += body if isinstance(body, bytes) else body.encode("latin-1")
        out += b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode("latin-1")
    out += "".join(f"{o:010d} 00000 n \n" for o in offsets).encode("latin-1")
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("latin-1")
    path.write_bytes(out)


if __name__ == "__main__":
    write_pdf([page_display(), page_pcb()], OUT)
    print(OUT)
