#!/usr/bin/env python3
"""3-D printed mounts for the v2 parts that live outside the dash unit: a camera pod under each door mirror and an
aimed LED pod on each inner door sail. Companion to make_enclosure.py (same folder, same rules).

    python 01-hardware/enclosure/make_mounts.py                                   # STLs + report, runs every check
    python 01-hardware/enclosure/make_mounts.py --set CAM_D=20.5 CAM_BODY_L=34 CAP_PITCH=6

Writes, next to this file:
  stl/print_cam_pod_left.stl, print_cam_pod_right.stl   camera pods, mirror images (cap face down, no supports)
  stl/print_cam_drill_guide.stl                         template for the 3 holes in each cap (flip it for the left)
  stl/print_led_pod_left.stl, print_led_pod_right.stl   door-sail LED pods (base down, no supports)
  stl/asm_cam_*.stl, stl/asm_led_*.stl                  the parts as mounted, with dummies of the camera and the LED
  mounts_report.json                                    aims, sizes, hole positions, placement in the car, checks
and exits with status 1 if a check fails. Requires: pip install manifold3d numpy

Camera pod. The mirror cameras (USB UVC, IP67, a round body ~19 mm across behind a front lip: premortem V4) don't go
through the mirror cap. Each sits in a printed pod under the cap, stuck on with VHB and held by 2 x M3 from inside the
mirror, which sets the aim the audit worked out (CAM-02): 39 deg outward of straight back, 10 deg down. Only the cable
goes up into the mirror, through one hole in the cap. The lens face is the pod's rearmost plane, so nothing of the pod
can be in the picture. The body sits in a teardrop bore (it prints without support and drains rearward), held by its
lip, a set screw and neutral-cure RTV.

Door-sail LED pod. The 5 mm amber blind-spot LED (premortem C7) in a small wedge on the inner door sail, aimed at the
driver's eyes and recessed 3 mm: no direct light reaches the side window or the windscreen, so there is no amber
reflection next to the mirror at night, and the sun can't make it look lit by day.

Frames (mm). Camera pod: origin at the centre of the face that goes on the cap, +Z up into the cap, +Y toward the
car's front, +X outward. It is built as the right-hand pod, so with a level cap its frame is the car's (X right,
Y forward, Z up); the left pod is its mirror image. LED pod: origin at the centre of its base on the sail, +Z out of
the sail into the cabin, +Y up along the sail, +X = Y x Z. The report gives every frame's rotation into the car's.
"""
import argparse
import json
import math
import pathlib
import sys

import numpy as np
from manifold3d import CrossSection, Manifold, OpType

HERE = pathlib.Path(__file__).resolve().parent

# ------------------------------------------------------------------------------------------------- parameters
# MEASURE = check on your own parts or car (README "Mirror cameras and door LEDs") and pass it with --set.
P = dict(
    # USB mirror camera: measure the one you buy, after it passes the V4 acceptance test
    CAM_D=19.0,             # MEASURE: round body behind the lip (the bore is CAM_FIT larger)
    CAM_LIP_D=24.0,         # MEASURE: front lip; it seats on the pod's face over an O-ring or the camera's gasket
    CAM_LIP_T=3.0,          # MEASURE: lip and lens in front of the face
    CAM_BODY_L=30.0,        # MEASURE: back of the lip to the end of the cable's strain relief
    CAM_FIT=0.4,            # bore diameter over the body
    CAM_LENS_D=9.0,         # dummy only
    CABLE_D=4.5,
    PLUG_PASS_D=18.0,       # MEASURE: the cable channel passes this: a moulded USB-A plug (~16 x 8 mm). 8 if you splice
    CAM_YAW=39.0,           # aim, degrees outward of straight back (audit CAM-02)
    CAM_PITCH=10.0,         # aim, degrees down
    CAM_HFOV=95.0,          # acceptance minimum (premortem V4); the viewer draws the picture with it
    CAP_PITCH=0.0,          # MEASURE: slope of the cap's underside where the pod goes, front edge up = +
    CAP_ROLL=0.0,           # MEASURE: the same across the car, outer edge up = +
    WALL=3.0,               # least plastic round the bore and the channel
    PLATE_T=3.0,            # the face on the cap
    SEAT_RING=3.5,          # flat face round the lip
    MARGIN=2.0,             # plate beyond the solid's footprint
    CHANNEL_SLOPE=60.0,     # cable channel above horizontal: steep enough to print without support
    TEAR=40.0,              # half-angle of the teardrop holes' point: they print near-horizontal, point up
    SET_SCREW_AT=8.0,       # set screw this far behind the lip
    PILOT_D=2.6,            # M3 machine screw into ASA (as make_enclosure.py)
    PILOT_DEPTH=10.0,
    SCREW_CLEAR=3.4,        # holes in the cap for the M3 screws
    VHB_T=1.1,              # 3M 5952 foam tape between the pod and the cap
    GUIDE_T=1.6,            # drill guide
    # 5 mm amber LED in the door-sail pods (premortem C7)
    LED_D=5.0, LED_FLANGE_D=5.8, LED_FLANGE_T=1.0,
    LED_L=8.6,              # MEASURE: dome tip to the back of the flange
    LED_FIT=0.15,
    LED_RECESS=3.0,         # dome tip below the pod's face
    LED_WALL=2.2,
    LED_BASE_T=2.5,
    # car geometry (the viewer's car model, metres): the LED spots and a ~1.75 m driver's eyes
    LED_AT_L=(-0.70, 0.52, 0.97),
    LED_AT_R=(0.70, 0.52, 0.97),
    EYE=(-0.37, -0.20, 1.15),
    SAIL_YAW=25.0,          # MEASURE: the sail's face turned toward the rear from facing straight across the car
    SAIL_LEAN=10.0,         # MEASURE: top of the sail leaning inward (its face looks this much down)
    BED=(220.0, 220.0, 250.0),
    SEG=64,
)
OVERHANG_LIMIT = 50.0       # degrees from vertical that an ASA print takes without support
OVERHANG_AREA_MAX = 15.0    # mm² beyond it allowed: the flat tips of blind holes and the LED's 0.5 mm shoulder


def parse_args():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--set", nargs="*", default=[], metavar="NAME=VALUE",
                    help="override a parameter; tuples as comma lists, e.g. EYE=-0.37,-0.25,1.18")
    ap.add_argument("--out", default=str(HERE))
    a = ap.parse_args()
    for kv in a.set:
        k, v = kv.split("=", 1)
        if k not in P or not isinstance(P[k], (int, float, tuple)):
            sys.exit(f"unknown or non-numeric parameter {k}")
        if isinstance(P[k], tuple):
            vals = tuple(float(x) for x in v.split(","))
            if len(vals) != len(P[k]):
                sys.exit(f"{k} needs {len(P[k])} comma-separated values")
            P[k] = vals
        else:
            P[k] = float(v)
    return pathlib.Path(a.out)


# ------------------------------------------------------------------------------------------------- geometry helpers
def unit(v):
    v = np.asarray(v, dtype=float)
    return v / np.linalg.norm(v)


def rot_x(deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return np.array([[1.0, 0, 0], [0, c, -s], [0, s, c]])


def rot_y(deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return np.array([[c, 0, s], [0, 1.0, 0], [-s, 0, c]])


def basis(z_axis, y_hint):
    """Rotation whose columns are x, y, z: z along z_axis, y as close to y_hint as it can be."""
    z = unit(z_axis)
    y = np.asarray(y_hint, dtype=float)
    y = y - np.dot(y, z) * z
    if np.linalg.norm(y) < 1e-6:
        y = np.array([1.0, 0, 0]) - z[0] * z
    y = unit(y)
    return np.column_stack([np.cross(y, z), y, z])


def place(m, R, t=(0.0, 0.0, 0.0)):
    M = np.zeros((3, 4))
    M[:, :3] = R
    M[:, 3] = t
    return m.transform(M)


def cyl(p0, p1, r, seg=None):
    p0 = np.asarray(p0, dtype=float)
    d = np.asarray(p1, dtype=float) - p0
    n = float(np.linalg.norm(d))
    return place(Manifold.cylinder(n, r, r, seg or P["SEG"]), basis(d, (0, 0, 1) if abs(d[2]) < 0.9 * n else (0, 1, 0)),
                 p0)


def teardrop(p0, p1, r, tip_dir, seg=None):
    """A hole from p0 to p1, pointed on the tip_dir side (across the axis): printed with that side up, its roof
    leans at TEAR degrees and needs no support."""
    p0 = np.asarray(p0, dtype=float)
    d = np.asarray(p1, dtype=float) - p0
    tip = r / math.sin(math.radians(P["TEAR"]))
    cs = CrossSection.batch_hull([CrossSection.circle(r, seg or P["SEG"]),
                                  CrossSection.circle(0.01, 8).translate((0, tip))])
    return place(cs.extrude(float(np.linalg.norm(d))), basis(d, tip_dir), p0)


def rounded_rect(x0, x1, y0, y1, r):
    r = min(r, (x1 - x0) / 2 - 0.01, (y1 - y0) / 2 - 0.01)
    return CrossSection.batch_hull([CrossSection.circle(r, P["SEG"]).translate((x, y))
                                    for x in (x0 + r, x1 - r) for y in (y0 + r, y1 - r)])


def cyl_z(x, y, z0, z1, d, seg=None):
    return Manifold.cylinder(z1 - z0, d / 2, d / 2, seg or P["SEG"]).translate((x, y, z0))


def union(parts):
    parts = [p for p in parts if p is not None]
    return Manifold.batch_boolean(parts, OpType.Add) if len(parts) > 1 else parts[0]


def overlap(a, b):
    return (a ^ b).volume()


def mirror_x(m):
    return m.mirror((1.0, 0.0, 0.0))


def verts(m):
    return np.asarray(m.to_mesh().vert_properties, dtype=np.float64)[:, :3]


def overhang_area(m):
    """Area (mm²) of downward faces steeper than OVERHANG_LIMIT from vertical, off the bed: what would need support."""
    mesh = m.to_mesh()
    v = np.asarray(mesh.vert_properties, dtype=np.float64)[:, :3]
    tri = v[np.asarray(mesh.tri_verts, dtype=np.int64)]
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    ln = np.linalg.norm(n, axis=1)
    ok = ln > 1e-12
    nz = np.where(ok, n[:, 2] / np.where(ok, ln, 1), 0)
    off_bed = tri[:, :, 2].mean(axis=1) > 0.2
    steep = nz < -math.sin(math.radians(OVERHANG_LIMIT))
    return float((0.5 * ln)[steep & off_bed & ok].sum())


def angle(u, v):
    return math.degrees(math.acos(max(-1.0, min(1.0, float(np.dot(unit(u), unit(v)))))))


# ------------------------------------------------------------------------------------------------- camera pod
def cam_axis_car(sign):
    """Out of the lens in the car's frame (X right, Y forward, Z up); sign +1 = right mirror, -1 = left."""
    yaw, pit = math.radians(P["CAM_YAW"]), math.radians(P["CAM_PITCH"])
    return np.array([sign * math.sin(yaw) * math.cos(pit), -math.cos(yaw) * math.cos(pit), -math.sin(pit)])


def build_cam_pod():
    """The right-hand pod in its own frame, the dummy camera, and the facts the checks and the report use."""
    R = rot_x(P["CAP_PITCH"]) @ rot_y(-P["CAP_ROLL"])           # pod frame -> car frame
    a = R.T @ cam_axis_car(+1)                                  # camera axis, out of the lens, in the pod frame
    zh = np.array([0.0, 0.0, 1.0])
    down = unit(-zh + a[2] * a)                                 # "down" across the bore
    rb = P["CAM_D"] / 2 + P["CAM_FIT"] / 2
    rs = P["CAM_LIP_D"] / 2 + P["SEAT_RING"]
    re = rb + P["WALL"]
    rc = P["PLUG_PASS_D"] / 2
    s_end = -(P["CAM_BODY_L"] + 1.0)
    across = math.sqrt(max(0.0, 1.0 - a[2] ** 2))              # how far up a circle across the axis reaches
    # Built with the lens-face centre at the origin; the face on the cap goes at z_m above it.
    z_m = max(s_end * a[2] + rb * across + P["WALL"], rs * across)
    seat = cyl(-a * 0.5, np.zeros(3), rs)
    body = cyl(a * (s_end - P["WALL"]), -a * 0.5, re)
    c0 = -a * P["CAM_BODY_L"]                                   # where the cable leaves the camera
    p_ch = -a * (P["CAM_BODY_L"] - 8.0)                         # the channel starts on the bore's axis, inside it,
    th = math.radians(P["CHANNEL_SLOPE"])                       # so its end disc leaves no ledge to print over
    h = unit(np.array([-a[0], -a[1], 0.0]))
    c = unit(h * math.cos(th) + zh * math.sin(th))              # the channel climbs forward and inward
    T = p_ch + c * (z_m - p_ch[2]) / c[2]                       # its centre on the cap face
    chan_enc = cyl(p_ch - c * 1.0, T + c * (rc + P["WALL"]), rc + P["WALL"]).trim_by_plane((0, 0, -1), -z_m)
    lo = np.min([m.bounding_box()[:3] for m in (seat, body, chan_enc)], axis=0)
    hi = np.max([m.bounding_box()[3:] for m in (seat, body, chan_enc)], axis=0)
    x_flat = min(body.bounding_box()[0], chan_enc.bounding_box()[0])   # flat inner side, parallel to the car's
    plate = rounded_rect(x_flat - 3.0, hi[0] + P["MARGIN"], lo[1] - P["MARGIN"], hi[1] + P["MARGIN"], 6.0)
    plate = plate.extrude(P["PLATE_T"]).translate((0, 0, z_m - P["PLATE_T"]))
    solid = (Manifold.batch_hull([plate, seat, body, chan_enc])
             .trim_by_plane((0, 0, -1), -z_m)                   # nothing above the cap face
             .trim_by_plane((1, 0, 0), x_flat)                  # the flat inner side
             .trim_by_plane(tuple(-a), 0.0))                    # nothing behind the lens face

    bore = teardrop(a * 3.0, a * s_end, rb, down)
    chan = cyl(p_ch, T + c * (rc + 5.0), rc)
    u = unit(np.cross(zh, a))                                   # across the bore, level, outward and forward
    ps = -a * P["SET_SCREW_AT"]
    setscrew = teardrop(ps, ps + u * 40.0, P["PILOT_D"] / 2, -zh)
    hollow = union([bore, chan, setscrew])

    # two M3 pilots from the cap face, in solid plastic at least 2 mm from every cavity, as far apart as they go
    bb = solid.bounding_box()
    cands = []
    for x in np.arange(bb[0] + 4.0, bb[3] - 4.0 + 1e-9, 1.5):
        for y in np.arange(bb[1] + 4.0, bb[4] - 4.0 + 1e-9, 1.5):
            boss = cyl_z(x, y, z_m - P["PILOT_DEPTH"] - 2.0, z_m, P["PILOT_D"] + 4.0, 24)
            if (boss - solid).volume() < 1e-3 and overlap(boss, hollow) < 1e-3:
                cands.append((float(x), float(y)))
    if len(cands) < 2:
        raise SystemExit("no room for the two pilot holes: raise WALL or PLATE_T, or check the camera numbers")
    pts = np.array(cands)
    dist = np.linalg.norm(pts[:, None, :] - pts[None, :, :], axis=2)
    i, j = np.unravel_index(np.argmax(dist), dist.shape)
    pilots = [tuple(pts[i]), tuple(pts[j])]
    holes = union([cyl_z(x, y, z_m - P["PILOT_DEPTH"], z_m + 1.0, P["PILOT_D"], 24) for x, y in pilots])
    pod = solid - hollow - holes

    # dummy camera: lip and lens in front of the face, the body in the bore, the cable up the channel into the mirror
    camera = union([cyl(np.zeros(3), a * P["CAM_LIP_T"], P["CAM_LIP_D"] / 2),
                    cyl(a * P["CAM_LIP_T"], a * (P["CAM_LIP_T"] + 0.6), P["CAM_LENS_D"] / 2),
                    cyl(-a * (P["CAM_BODY_L"] - 8.0), np.zeros(3), P["CAM_D"] / 2),
                    cyl(-a * P["CAM_BODY_L"], -a * (P["CAM_BODY_L"] - 8.0), 4.0),
                    cyl(c0, T + c * 40.0, P["CABLE_D"] / 2, 24)])

    # the drill guide: the pod's footprint with the three holes the cap needs, and an arrow pointing rearward
    fp = solid.trim_by_plane((0, 0, 1), z_m - P["PLATE_T"]).project()     # the plate's outline
    guide = fp.extrude(P["GUIDE_T"]).translate((0, 0, z_m - P["GUIDE_T"]))
    guide = guide - union([cyl_z(x, y, z_m - P["GUIDE_T"] - 1, z_m + 1, P["SCREW_CLEAR"], 24) for x, y in pilots])
    guide = guide - chan
    cx, cy = (bb[0] + bb[3]) / 2, (bb[1] + bb[4]) / 2
    arrow = CrossSection([[(cx - 3.0, cy + 2.0), (cx, cy - 5.0), (cx + 3.0, cy + 2.0)]])     # counter-clockwise
    guide = guide - arrow.extrude(P["GUIDE_T"] + 2).translate((0, 0, z_m - P["GUIDE_T"] - 1))

    # final frame: the cap face at z = 0, centred on the footprint
    pb = pod.bounding_box()
    shift = np.array([-(pb[0] + pb[3]) / 2, -(pb[1] + pb[4]) / 2, -z_m])
    tr = tuple(shift)
    # where the channel meets the cap face: an ellipse, long axis along the channel's climb
    cut = chan.translate(tr).trim_by_plane((0, 0, 1), -0.05).trim_by_plane((0, 0, -1), -0.05).bounding_box()
    return dict(
        R=R, a=a, rb=rb, rs=rs, rc=rc, c=c, z_m=z_m, shift=shift,
        pod=pod.translate(tr), solid=solid.translate(tr), camera=camera.translate(tr), guide=guide.translate(tr),
        bore=bore.translate(tr), chan=chan.translate(tr), lens=shift.copy(),
        pilots=[(x + shift[0], y + shift[1]) for x, y in pilots],
        channel_exit=(T + shift), channel_cut=[cut[3] - cut[0], cut[4] - cut[1]],
        bend=angle(-a, c), set_screw_dir=u,
        bore_wall=cyl(-a * 0.5, a * s_end, rb + P["WALL"] - 0.3).translate(tr),
        chan_wall=cyl(p_ch + c * (rb - rc + 2.0), T + c * (rc + 5.0), rc + P["WALL"] - 0.3).translate(tr)
        .trim_by_plane((0, 0, -1), 0.0),
    )


# ------------------------------------------------------------------------------------------------- LED pods
def led_frame(sign):
    """LED pod frame -> car frame for the left (sign -1) or right (+1) door's inner sail."""
    yaw, lean = math.radians(P["SAIL_YAW"]), math.radians(P["SAIL_LEAN"])
    n = np.array([-sign * math.cos(lean) * math.cos(yaw), -math.cos(lean) * math.sin(yaw), -math.sin(lean)])
    return basis(n, (0, 0, 1))


def build_led_pod(sign):
    R = led_frame(sign)
    at = np.array(P["LED_AT_L"] if sign < 0 else P["LED_AT_R"])
    d = R.T @ unit(np.array(P["EYE"]) - at)                     # LED axis in the pod frame
    beta = math.acos(max(-1.0, min(1.0, d[2])))
    rcb = (P["LED_FLANGE_D"] + 0.3) / 2
    rb = (P["LED_D"] + P["LED_FIT"]) / 2
    rh = rcb + P["LED_WALL"]
    s_step = rcb * math.tan(beta) + 0.8 / math.cos(beta)       # the flange's shoulder, a full ring above the base
    s_tip = s_step + P["LED_L"] - P["LED_FLANGE_T"]
    s_face = s_tip + P["LED_RECESS"]
    head = cyl(np.zeros(3), d * s_face, rh)
    hb = head.bounding_box()
    base = rounded_rect(hb[0] - 1.5, hb[3] + 1.5, hb[1] - 1.5, hb[4] + 1.5, 4.0).extrude(P["LED_BASE_T"])
    solid = Manifold.batch_hull([base, head]).trim_by_plane((0, 0, 1), 0.0)
    holes = union([cyl(d * (s_step - 0.01), d * (s_face + 2.0), rb, 32), cyl(d * -10.0, d * s_step, rcb, 32)])
    pod = solid - holes
    led = union([cyl(d * (s_step - P["LED_FLANGE_T"]), d * s_step, P["LED_FLANGE_D"] / 2, 32),
                 cyl(d * (s_step - 0.1), d * (s_tip - P["LED_D"] / 2), P["LED_D"] / 2, 32),   # into the flange
                 # 0.05 mm under the body's radius: a dome tangent to the body leaves slivers that don't survive STL
                 Manifold.sphere(P["LED_D"] / 2 - 0.05, 32).translate(tuple(d * (s_tip - P["LED_D"] / 2)))])
    side_dir = basis(d, (0, 1, 0))[:, 0]
    legs = union([cyl(d * (s_step - P["LED_FLANGE_T"] + 0.1) + e, d * -12.0 + e, 0.25, 12)
                  for e in (side_dir * 1.27, -side_dir * 1.27)])
    pb = pod.bounding_box()
    tr = (-(pb[0] + pb[3]) / 2, -(pb[1] + pb[4]) / 2, 0.0)
    tip = d * s_tip + np.array(tr)
    return dict(R=R, d=d, beta=math.degrees(beta), at=at, pod=pod.translate(tr), led=(led + legs).translate(tr),
                tip=tip, s_face=s_face, rb=rb)


# ------------------------------------------------------------------------------------------------- export
def write_stl(man, path):
    mesh = man.to_mesh()
    v = np.asarray(mesh.vert_properties, dtype=np.float64)[:, :3]
    t = np.asarray(mesh.tri_verts, dtype=np.int64)
    tri = v[t]
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    n = n / np.where(ln == 0, 1, ln)
    rec = np.zeros(len(t), dtype=[("n", "<f4", (3,)), ("v", "<f4", (3, 3)), ("a", "<u2")])
    rec["n"], rec["v"] = n, tri
    with open(path, "wb") as fh:
        fh.write(b"Yaris iA v2 mounts (make_mounts.py), mm".ljust(80, b" "))
        fh.write(np.uint32(len(t)).tobytes())
        fh.write(rec.tobytes())
    return len(t)


def to_print(name, m):
    if name.startswith("cam_pod"):        # cap face down
        return m.rotate((180, 0, 0))
    if name == "cam_drill_guide":
        return m.translate((0, 0, P["GUIDE_T"]))
    return m                              # LED pods: base down already


# ------------------------------------------------------------------------------------------------- checks
def run_checks(parts, cam, leds):
    res = []

    def check(name, ok, detail):
        res.append(dict(check=name, ok=bool(ok), detail=detail))

    for name, m in parts.items():
        st = str(m.status())
        check(f"{name}: valid solid", st.endswith("NoError") and m.volume() > 0,
              f"{st.split('.')[-1]}, {m.volume() / 1000:.1f} cm³, genus {m.genus()}")
        pm = to_print(name, m)
        b = pm.bounding_box()
        size = (b[3] - b[0], b[4] - b[1], b[5] - b[2])
        bed = P["BED"]
        check(f"{name}: fits a {bed[0]:.0f} × {bed[1]:.0f} bed, flat face down", size[0] <= bed[0] - 5 and
              size[1] <= bed[1] - 5 and size[2] <= bed[2] and abs(b[2]) < 1e-6,
              f"print size {size[0]:.1f} × {size[1]:.1f} × {size[2]:.1f} mm")
        if name != "cam_drill_guide":
            area = overhang_area(pm)
            check(f"{name}: prints without supports", area <= OVERHANG_AREA_MAX,
                  f"{area:.1f} mm² steeper than {OVERHANG_LIMIT:.0f}° from vertical (small hole ends only)")

    pod = cam["pod"]
    for side, p, cam_dummy in (("right", pod, cam["camera"]), ("left", parts["cam_pod_left"],
                                                                mirror_x(cam["camera"]))):
        v = overlap(p, cam_dummy)
        check(f"cam_pod_{side}: camera and its cable clear the pod", v < 0.05, f"overlap {v:.3f} mm³")
    a_car = cam["R"] @ cam["a"]
    yaw = math.degrees(math.atan2(a_car[0], -a_car[1]))
    pitch = math.degrees(math.asin(-a_car[2]))
    check("camera aim as mounted (cap slope included)",
          abs(yaw - P["CAM_YAW"]) < 0.05 and abs(pitch - P["CAM_PITCH"]) < 0.05,
          f"{yaw:.1f}° outward of straight back, {pitch:.1f}° down; cap slope {P['CAP_PITCH']:+g}° pitch, "
          f"{P['CAP_ROLL']:+g}° roll")
    ahead = float(np.max((verts(pod) - cam["lens"]) @ cam["a"]))
    check("nothing of the pod in front of the lens", ahead <= 0.01,
          f"pod's rearmost point {ahead:+.2f} mm along the camera axis from the lens face")
    wb = (cam["bore_wall"] - cam["solid"]).volume()
    wc = (cam["chan_wall"] - cam["solid"]).volume()
    check(f"≥ {P['WALL'] - 0.3:.1f} mm of plastic round the bore and the cable channel", wb < 0.5 and wc < 0.5,
          f"wall shortfall {wb:.2f} mm³ (bore), {wc:.2f} mm³ (channel)")
    (x1, y1), (x2, y2) = cam["pilots"]
    gap = math.hypot(x2 - x1, y2 - y1)
    check("two M3 pilots in solid plastic, clear of the cavities", gap >= 25.0,
          f"{P['PILOT_DEPTH']:g} mm deep, ≥ 2 mm from the bore and the channel, {gap:.1f} mm apart")
    check("cable channel passes the USB plug and climbs steeply", P["PLUG_PASS_D"] <= 2 * cam["rc"] + 1e-6 and
          P["CHANNEL_SLOPE"] >= 45.0, f"Ø{2 * cam['rc']:.1f} mm at {P['CHANNEL_SLOPE']:g}° above horizontal; "
          f"the cable turns {cam['bend']:.0f}° out of the camera")
    depth = -cam["pod"].bounding_box()[2]
    check("pod stays compact under the mirror", depth <= 45.0,
          f"{depth:.1f} mm below the cap (+{P['VHB_T']:g} mm of VHB)")

    eye = np.array(P["EYE"])
    for side, L in leds.items():
        p = parts[f"led_pod_{side}"]
        v = overlap(p, L["led"])
        check(f"led_pod_{side}: LED clears its bore", v < 0.05, f"overlap {v:.3f} mm³")
        tip_car = L["at"] + L["R"] @ (L["tip"] / 1000.0)
        err = angle(L["R"] @ L["d"], eye - tip_car)
        cone = math.degrees(math.atan((L["rb"] + P["LED_D"] / 2) / P["LED_RECESS"]))
        sign = -1 if side == "left" else 1
        axis = L["R"] @ L["d"]
        glass = angle(axis, (sign, 0, 0))
        screen = angle(axis, (0, 1, 0))
        check(f"led_pod_{side}: aimed at the driver's eyes", err <= 1.0,
              f"{err:.2f}° off; tilted {L['beta']:.0f}° from the sail")
        check(f"led_pod_{side}: no direct light on the side window or the windscreen",
              min(glass, screen) >= cone + 10.0,
              f"light leaves within {cone:.0f}° of the axis; side window {glass:.0f}°, windscreen {screen:.0f}° off")
    return res


# ------------------------------------------------------------------------------------------------- main
COLORS = dict(cam_pod="#1f2937", cam="#0f172a", cam_drill_guide="#64748b", led_pod="#1f2937", led="#f59e0b")
LABELS = dict(
    cam_pod_left="Left mirror camera pod (print cap face down)", cam_pod_right="Right mirror camera pod (print cap "
    "face down)", cam_drill_guide="Drill guide for the 3 holes in each mirror cap (flip it over for the left)",
    led_pod_left="Left door-sail LED pod (print base down)", led_pod_right="Right door-sail LED pod (print base down)",
    cam_left="USB UVC camera and its lead (dummy)", cam_right="USB UVC camera and its lead (dummy)",
    led_left="5 mm amber LED (dummy)", led_right="5 mm amber LED (dummy)")


def _r(v, n=3):
    if isinstance(v, np.ndarray):
        v = v.tolist()
    return [_r(x, n) for x in v] if isinstance(v, (list, tuple)) else round(float(v), n)


def main():
    out = parse_args()
    cam = build_cam_pod()
    leds = {"left": build_led_pod(-1), "right": build_led_pod(+1)}
    parts = {"cam_pod_left": mirror_x(cam["pod"]), "cam_pod_right": cam["pod"], "cam_drill_guide": cam["guide"],
             "led_pod_left": leds["left"]["pod"], "led_pod_right": leds["right"]["pod"]}
    dummies = {"cam_left": mirror_x(cam["camera"]), "cam_right": cam["camera"], "led_left": leds["left"]["led"],
               "led_right": leds["right"]["led"]}
    checks = run_checks(parts, cam, leds)

    stl = out / "stl"
    stl.mkdir(parents=True, exist_ok=True)
    files = {}
    for name, m in parts.items():
        n = write_stl(to_print(name, m), stl / f"print_{name}.stl")
        files[f"print_{name}"] = dict(file=f"stl/print_{name}.stl", triangles=n, label=LABELS[name])
    for name, m in {**parts, **dummies}.items():
        if name == "cam_drill_guide":
            continue
        n = write_stl(m, stl / f"asm_{name}.stl")
        key = name.rsplit("_", 1)[0]
        files[f"asm_{name}"] = dict(file=f"stl/asm_{name}.stl", triangles=n, color=COLORS[key], label=LABELS[name])

    M = np.diag([-1.0, 1.0, 1.0])
    pb = cam["pod"].bounding_box()
    vfov = 2 * math.degrees(math.atan(math.tan(math.radians(P["CAM_HFOV"] / 2)) * 9 / 16))
    ex = cam["channel_exit"]
    report = dict(
        generator="01-hardware/enclosure/make_mounts.py",
        camera_pod=dict(
            aim_deg=dict(outward_of_straight_back=P["CAM_YAW"], down=P["CAM_PITCH"]),
            cap_slope_deg=dict(pitch_front_up=P["CAP_PITCH"], roll_outer_up=P["CAP_ROLL"]),
            fov_deg=dict(horizontal=P["CAM_HFOV"], vertical_16_9=round(vfov, 1)),
            frame_to_car=dict(right=_r(cam["R"], 5), left=_r(M @ cam["R"] @ M, 5)),
            right_pod_mm=dict(lens_centre=_r(cam["lens"], 2), axis=_r(cam["a"], 5),
                              channel_exit=_r(ex, 2), pilots=_r(cam["pilots"], 2)),
            size_mm=_r([pb[3] - pb[0], pb[4] - pb[1], pb[5] - pb[2]], 1),
            below_cap_mm=round(-pb[2], 1),
            cap_holes=dict(
                cable=f"Ø{max(cam['channel_cut']) + 1:.0f} mm (step drill), where the channel meets the cap: "
                      f"{cam['channel_cut'][0]:.1f} × {cam['channel_cut'][1]:.1f} mm",
                screws=f"2 × Ø{P['SCREW_CLEAR']:g} mm, {math.dist(*cam['pilots']):.1f} mm apart",
                screw="2 × M3 × 12 pan head from inside the mirror into the pod's pilots, plus 3M 5952 VHB",
                guide="print_cam_drill_guide.stl, the arrow points rearward and its flat side faces the car"),
            camera=dict(body_d=P["CAM_D"], lip_d=P["CAM_LIP_D"], lip_t=P["CAM_LIP_T"], body_l=P["CAM_BODY_L"],
                        plug_pass_d=P["PLUG_PASS_D"]),
            set_screw="M3 × 6 set screw (or M3 × 8 with a dab of RTV under its head) against the body; then a bead "
                      "of neutral-cure RTV round the lip"),
        led_pods={side: dict(frame_to_car=_r(L["R"], 5), at_m=_r(L["at"]), axis=_r(L["d"], 5),
                             axis_car=_r(L["R"] @ L["d"], 5), tilt_from_sail_deg=round(L["beta"], 1),
                             led_tip_mm=_r(L["tip"], 2), size_mm=_r(np.subtract(L["pod"].bounding_box()[3:],
                                                                           L["pod"].bounding_box()[:3]), 1))
                  for side, L in leds.items()},
        eye_m=list(P["EYE"]),
        sail_deg=dict(yaw_toward_rear=P["SAIL_YAW"], lean=P["SAIL_LEAN"]),
        parameters={k: (list(v) if isinstance(v, tuple) else v) for k, v in P.items()},
        volumes_cm3={k: round(m.volume() / 1000, 1) for k, m in parts.items()},
        files=files,
        checks=checks,
        all_ok=all(c["ok"] for c in checks),
    )
    (out / "mounts_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    def asc(t):                           # the Windows console may not be UTF-8
        for a, b_ in (("×", "x"), ("³", "3"), ("²", "2"), ("≥", ">="), ("≤", "<="), ("°", " deg"), ("Ø", "D")):
            t = t.replace(a, b_)
        return t

    w = max(len(c["check"]) for c in checks)
    for c in checks:
        print(asc(f"{'PASS' if c['ok'] else 'FAIL'}  {c['check']:<{w}}  {c['detail']}"))
    cp = report["camera_pod"]
    print(asc(f"\ncamera pod {cp['size_mm'][0]} × {cp['size_mm'][1]} × {cp['size_mm'][2]} mm, {cp['below_cap_mm']} mm "
              f"below the cap; LED pods tilted {leds['left']['beta']:.0f}° (left) and {leds['right']['beta']:.0f}° "
              f"(right) from the sail"))
    print(f"{sum(c['ok'] for c in checks)}/{len(checks)} checks passed -> {out / 'mounts_report.json'}")
    return 0 if report["all_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
