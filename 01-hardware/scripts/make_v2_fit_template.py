#!/usr/bin/env python3
"""1:1 fit template for the v2 build (no dependencies: the PDF is written directly).

Page 1: the SunFounder TS-7 7" display in its printed bezel, front view as seen by the driver, over the Yaris iA
        console opening: board outline and ear holes, glass, sockets and plugs, cable slot, rear box. Lay the
        display face up on the printout to check its outline and holes before printing the enclosure.
Page 2: the 100 x 100 mm v2 carrier PCB with its mounting holes and planning zones.

    python 01-hardware/scripts/make_v2_fit_template.py   ->  01-hardware/docs/v2_fit_template_1to1.pdf

Print at 100 % ("Actual size") on US Letter landscape and check the 100 mm bar with a caliper.
Geometry: 01-hardware/enclosure/enclosure_report.json, so run make_enclosure.py first after changing a measurement.
Console opening: the v1 paper fit (panel_config.py).
"""
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import panel_config as CFG  # noqa: E402

OUT = HERE.parent / "docs" / "v2_fit_template_1to1.pdf"
PT = 72 / 25.4
PAGE_W, PAGE_H = 279.4, 215.9                      # US Letter landscape, like the v1 template

REPORT = HERE.parent / "enclosure" / "enclosure_report.json"
ENC = json.loads(REPORT.read_text(encoding="utf-8"))
FV, E = ENC["front_view_mm"], ENC["parameters"]

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
    pg.text(10, 9, "v2 fit template 1:1  ·  SunFounder TS-7 7\" display in the Yaris iA console", 11, True)
    pg.text(10, 14, "Front view from the driver's seat. Lay the display face up on this page: its board must cover the "
                    "blue outline and its ear holes the orange circles. Dashed = behind the display.", 7)
    bx0, bx1, by0, by1 = FV["bezel"]
    ox, oy = 9.0, 23.0                         # page position of the bezel's top-left corner

    def pt(x, y):                              # front view (X right, Y up, mm) -> page
        return ox + x - bx0, oy + by1 - y

    def box(r):
        (a, b), (c, d) = pt(r[0], r[3]), pt(r[1], r[2])
        pg.rect(a, b, c - a, d - b)

    def label(x, y, s, size=6.0, rgb=BLACK, center=False):
        pg.text(*pt(x, y), s, size, rgb=rgb, center=center)

    top, bottom, height = CFG.OPENING_TOP_WIDTH, CFG.OPENING_BOTTOM_WIDTH, CFG.OPENING_HEIGHT
    yf = FV["opening_bottom_y"]
    pg.style(RED, 0.3, (2.5, 1.5))
    pg.poly([pt(-top / 2, yf + height), pt(top / 2, yf + height), pt(bottom / 2, yf), pt(-bottom / 2, yf)])
    label(-bottom / 2 + 1, yf - 3.6, f"console opening {top:g} / {bottom:g} × {height:g}", 5.8, RED)

    pg.style(GREY, 0.25, (1.5, 1.0))
    box(FV["box"])
    x0, x1, y0, y1 = FV["box"]
    label(x0 + 2, y0 + 3, f"rear box {x1 - x0:.0f} × {y1 - y0:.0f}, {ENC['box_mm']['behind_plate']:.1f} deep "
                          f"(needs {ENC['box_mm']['clear_pocket_depth_needed']:.0f} mm of pocket depth)", 5.6, GREY)
    pg.style(RED, 0.3, (1.0, 0.8))
    box(FV["cable_slot"])
    cx0, cx1, cy0, cy1 = FV["cable_slot"]
    label(cx1 + 1, cy1 - 1, "cable slot:", 5.6, RED)
    label(cx1 + 1, cy1 - 3.6, "HDMI + USB go", 5.6, RED)
    label(cx1 + 1, cy1 - 6.2, "back here", 5.6, RED)

    pg.style(BLACK, 0.45)
    box(FV["bezel"])
    label(bx0 + 1.5, by1 + 1.6, f"printed bezel {bx1 - bx0:.1f} × {by1 - by0:.1f}", 6.5, BLACK)

    mx0, mx1, my0, my1 = FV["board"]
    mh, ew = FV["main_h"] / 2, FV["ear_w"]
    pg.style(BLUE, 0.35)
    pg.poly([pt(mx0, my1), pt(mx0 + ew, my1), pt(mx0 + ew, mh), pt(mx1 - ew, mh), pt(mx1 - ew, my1), pt(mx1, my1),
             pt(mx1, my0), pt(mx1 - ew, my0), pt(mx1 - ew, -mh), pt(mx0 + ew, -mh), pt(mx0 + ew, my0), pt(mx0, my0)])
    label(mx0 + ew + 2, mh + 2.0, f"TS-7 board {mx1 - mx0:.1f} × {my1 - my0:.1f} over the ears (MEASURE)", 6, BLUE)
    pg.style(ORANGE, 0.3)
    hs = FV["ear_holes"]
    for x, y in hs:
        pg.circle(*pt(x, y), E["HOLE_D"] / 2)
    xs, ys = sorted({h[0] for h in hs}), sorted({h[1] for h in hs})
    label(xs[0] + 4.0, ys[0] + 0.8, f"4× M3 ear holes {xs[1] - xs[0]:.1f} × {ys[1] - ys[0]:.1f} (MEASURE)", 6, ORANGE)

    pg.style(BLACK, 0.3)
    box(FV["glass"])
    pg.style(BLACK, 0.25, (3.0, 1.0))
    box(FV["window"])
    gx0, gx1, gy0, gy1 = FV["glass"]
    label(gx0 + 3, gy1 - 7.0, f"glass {gx1 - gx0:.1f} × {gy1 - gy0:.1f}; dashed = bezel window (the lip covers "
                              f"{E['LIP_COVER']:g} mm of the glass)", 6.5, BLACK)
    pg.style(BLUE, 0.25, (1.0, 1.0))
    box(FV["active"])
    ax0, ax1, ay0, ay1 = FV["active"]
    label((ax0 + ax1) / 2, (ay0 + ay1) / 2, f"active area {ax1 - ax0:.1f} × {ay1 - ay0:.1f} (1024 × 600, position "
                                            "estimated)", 7.5, BLUE, center=True)
    label((ax0 + ax1) / 2, (ay0 + ay1) / 2 - 5, f"screen {abs(E['SCREEN_DX']):g} mm toward the driver, so the plugs "
                                                "fit on the right", 6.5, BLUE, center=True)

    pg.style(GREY, 0.25, (1.5, 1.0))
    box(FV["lcd_flex"])
    fx0, fx1, fy0, fy1 = FV["lcd_flex"]
    label(fx0, fy0 - 3.0, "LCD flex wraps round this edge", 5.6, GREY)
    box(FV["hdmi_socket"])
    box(FV["usb_socket"])
    pg.style(ORANGE, 0.3, (1.5, 1.0))
    box(FV["hdmi_plug"])
    box(FV["usb_plug"])
    hx0, hx1, hy0, hy1 = FV["hdmi_plug"]
    label(hx0 + 0.8, hy1 - 3.0, "HDMI FPC", 5.4, ORANGE)
    label(hx0 + 0.8, hy1 - 5.6, "adapter", 5.4, ORANGE)
    ux0, ux1, uy0, uy1 = FV["usb_plug"]
    label(ux0 + 0.6, uy0 - 3.0, "90° micro-USB", 5.4, ORANGE)
    pg.style(GREY, 0.25)
    for x, y in FV["bezel_screws"]:
        pg.circle(*pt(x, y), 1.7, cross=False)

    x, y, w = 218.0, 25.0, 57.0
    y = pg.wrapped(x, y, w, "BEFORE PRINTING THE ENCLOSURE", 8, True, 4)
    notes = [
        "1. Lay the display face up on this page. If its board or ear holes miss the blue outline or the orange "
        "circles by more than 0.5 mm, measure them with calipers and regenerate (enclosure/README.md, Measure first).",
        "2. Measure: board height over the ears (SunFounder lists 121, its photos say ~124.4), ear holes, the "
        "HDMI and micro-USB socket centres, the tallest part on the back, your HDMI adapter and micro-USB plug.",
        f"3. Mock-up: cut out the bezel outline, glue it to foam board with a {ENC['box_mm']['width']:.0f} × "
        f"{ENC['box_mm']['height']:.0f} × {ENC['box_mm']['behind_plate']:.0f} mm block behind it. Check the shifter "
        f"through P-R-N-D-M, the HVAC knobs and the view. It stands {ENC['proud_of_trim_mm']:.0f} mm proud of the trim.",
        "4. IPS panel: readable from any angle, so it mounts the normal way up.",
        "5. Rated -10 to +60 °C (storage +70 °C): keep it out of direct sun; 250 cd/m² is dim in daylight.",
        "Sources: SunFounder TS-7 parameters and product photos; enclosure_report.json; v1 panel_config.py.",
    ]
    for n in notes:
        y = pg.wrapped(x, y, w, n, 6.4) + 1.4
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
    pg.text(bx, by + 110, "The Pi's ports face the driver's right, so its USB window is on the left of this view "
                          "(the board is seen from the lid side).", 6, rgb=GREY)

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
