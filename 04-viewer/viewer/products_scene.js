import * as THREE from "three";
import { STLLoader } from "three/addons/STLLoader.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

/**
 * "Printed Parts" mode: every 3-D printed part of the v2 build, assembled with the parts it holds, and on the
 * print bed.
 *
 * Products: the dash unit (bezel, housing and lid around the TS-7, the Pi 4, the fan and the real carrier PCB from
 * KiCad), the mirror camera pods, the door-sail LED pods, the print beds, and everything to scale.
 * Sources (all generated, nothing drawn by hand):
 *   01-hardware/enclosure/enclosure_report.json + stl/   make_enclosure.py
 *   01-hardware/enclosure/mounts_report.json + stl/      make_mounts.py
 *   01-hardware/v2/carrier/docs/tpms_v2_carrier.glb      build_carrier.py (KiCad's glTF export; the DevKit and
 *   the CC1101 are VRML-only models, so they are filled in from lib/3d/*.wrl)
 * Frame: metres, Z up. The dash unit faces -Y (toward you in the front view); the mounts sit in the car's frame
 * (X right, Y forward, Z up), as in the car scene.
 */

const MM = 0.001;
const ENC = "../../01-hardware/enclosure/";
const CARRIER = "../../01-hardware/v2/carrier/";
const MFG = "../../03-manufacturing/v2_carrier/";

const PRINT = 0x4a566b;                 // printed parts (ASA; lighter than the real black so the shapes read)
const PRINT_LIGHT = 0x5b687e;
const stlLoader = new STLLoader();

function material(color, o = {}) {
  const opacity = o.opacity ?? 1;
  return new THREE.MeshStandardMaterial({
    color, roughness: o.roughness ?? 0.62, metalness: o.metalness ?? 0.04, transparent: opacity < 1, opacity,
    depthWrite: opacity >= 0.5, side: THREE.DoubleSide, emissive: o.emissive ?? 0x000000,
    emissiveIntensity: o.emissiveIntensity ?? 0,
  });
}

async function fetchOk(url) {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`${url}: HTTP ${res.status}`);
  return res;
}

async function loadStl(rel) {
  const geo = stlLoader.parse(await (await fetchOk(ENC + rel)).arrayBuffer());
  geo.scale(MM, MM, MM);
  geo.computeVertexNormals();
  return geo;
}

// Our own simple VRML (build_carrier.py, class Wrl): boxes as IndexedFaceSets, in 0.1" units, Y up = -footprint Y.
// Returned in a glTF node's frame as KiCad exports it: X = footprint x, Y = up, Z = footprint y (page down).
function parseWrl(text) {
  const out = [];
  for (const chunk of text.split("Shape {").slice(1)) {
    const col = /diffuseColor\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)/.exec(chunk);
    const pts = /point\s*\[([^\]]*)\]/.exec(chunk);
    const idx = /coordIndex\s*\[([^\]]*)\]/.exec(chunk);
    if (!pts || !idx) continue;
    const p = pts[1].split(",").map((s) => s.trim().split(/\s+/).map(Number)).filter((v) => v.length === 3);
    const ids = idx[1].split(/[\s,]+/).filter(Boolean).map(Number);
    const pos = [];
    let face = [];
    for (const i of ids) {
      if (i >= 0) { face.push(i); continue; }
      for (let k = 1; k + 1 < face.length; k++) {
        for (const j of [face[0], face[k], face[k + 1]]) {
          const [x, y, z] = p[j];
          pos.push(x * 2.54 * MM, z * 2.54 * MM, -y * 2.54 * MM);
        }
      }
      face = [];
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
    geo.computeVertexNormals();
    const c = col ? new THREE.Color(+col[1], +col[2], +col[3]) : new THREE.Color(0x222222);
    out.push(new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ color: c, roughness: 0.5, metalness: 0.2 })));
  }
  return out;
}

function parseCsv(text) {
  const rows = [];
  for (const line of text.split(/\r?\n/)) {
    if (!line.trim()) continue;
    const cells = [];
    let cur = "", q = false;
    for (let i = 0; i < line.length; i++) {
      const ch = line[i];
      if (q) {
        if (ch === '"' && line[i + 1] === '"') { cur += '"'; i++; } else if (ch === '"') q = false; else cur += ch;
      } else if (ch === '"') q = true;
      else if (ch === ",") { cells.push(cur); cur = ""; } else cur += ch;
    }
    cells.push(cur);
    rows.push(cells);
  }
  const [head, ...body] = rows;
  return body.map((r) => Object.fromEntries(head.map((h, i) => [h.replace(/^\uFEFF/, ""), r[i] ?? ""])));
}

function makeLabel(text, height = 0.012, border = "#38bdf8") {
  const lines = String(text).split("\n");
  const fs = 30;
  const c = document.createElement("canvas");
  const ctx = c.getContext("2d");
  ctx.font = `600 ${fs}px system-ui, sans-serif`;
  const w = Math.ceil(Math.max(...lines.map((l) => ctx.measureText(l).width)) + 28);
  const h = lines.length * (fs + 8) + 16;
  c.width = w;
  c.height = h;
  ctx.font = `600 ${fs}px system-ui, sans-serif`;
  ctx.fillStyle = "rgba(15,23,42,0.86)";
  ctx.beginPath();
  ctx.roundRect(1, 1, w - 2, h - 2, 10);
  ctx.fill();
  ctx.strokeStyle = border;
  ctx.lineWidth = 2;
  ctx.stroke();
  ctx.fillStyle = "#e2e8f0";
  ctx.textBaseline = "top";
  lines.forEach((l, i) => ctx.fillText(l, 14, 9 + i * (fs + 8)));
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, depthTest: false, transparent: true }));
  sp.scale.set((height * w) / h, height, 1);
  sp.renderOrder = 20;
  sp.userData.noFrame = true;
  return sp;
}

function line(points, color = 0x38bdf8, opacity = 0.85) {
  const geo = new THREE.BufferGeometry().setFromPoints(points.map((p) => new THREE.Vector3(...p)));
  const l = new THREE.Line(geo, new THREE.LineBasicMaterial({ color, transparent: true, opacity }));
  l.userData.noFrame = true;
  return l;
}

function rotationFrom(rows) {
  const m = new THREE.Matrix4().set(rows[0][0], rows[0][1], rows[0][2], 0, rows[1][0], rows[1][1], rows[1][2], 0,
    rows[2][0], rows[2][1], rows[2][2], 0, 0, 0, 0, 1);
  return new THREE.Quaternion().setFromRotationMatrix(m);
}

// The TS-7's screen in the dash unit: a still of the v2 UI (TPMS + the camera on blinker)
function drawScreen(c) {
  const ctx = c.getContext("2d");
  const W = c.width, H = c.height;
  ctx.fillStyle = "#04070d";
  ctx.fillRect(0, 0, W, H);
  ctx.fillStyle = "#0f172a";
  ctx.fillRect(0, 0, W, 64);
  ctx.font = "bold 30px system-ui, sans-serif";
  ctx.fillStyle = "#e2e8f0";
  ctx.fillText("YARIS iA · TPMS + BLIND SPOT", 26, 43);
  ctx.fillStyle = "#f59e0b";
  ctx.fillText("◀ LEFT LANE: CAR", W - 330, 43);
  // camera view (left mirror, on the left blinker)
  const cx = 24, cy = 84, cw = 640, ch = 490;
  const sky = ctx.createLinearGradient(0, cy, 0, cy + ch);
  sky.addColorStop(0, "#1e293b");
  sky.addColorStop(0.45, "#334155");
  sky.addColorStop(0.46, "#2b2f36");
  sky.addColorStop(1, "#16181c");
  ctx.fillStyle = sky;
  ctx.fillRect(cx, cy, cw, ch);
  ctx.strokeStyle = "#e5e7eb";
  ctx.lineWidth = 5;
  ctx.setLineDash([34, 26]);
  ctx.beginPath();
  ctx.moveTo(cx + 120, cy + ch);
  ctx.lineTo(cx + 420, cy + ch * 0.46);
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.fillStyle = "#475569";                       // our own car's side: the reference strip
  ctx.beginPath();
  ctx.moveTo(cx + cw, cy + ch * 0.4);
  ctx.lineTo(cx + cw, cy + ch);
  ctx.lineTo(cx + cw - 120, cy + ch);
  ctx.closePath();
  ctx.fill();
  ctx.fillStyle = "#0b1220";                       // the car in the next lane
  ctx.fillRect(cx + 190, cy + 250, 190, 120);
  ctx.fillStyle = "#1f2937";
  ctx.fillRect(cx + 210, cy + 210, 150, 52);
  ctx.strokeStyle = "#ef4444";
  ctx.lineWidth = 6;
  ctx.strokeRect(cx + 176, cy + 196, 218, 188);
  ctx.fillStyle = "#ef4444";
  ctx.font = "bold 24px system-ui, sans-serif";
  ctx.fillText("car 0.92", cx + 180, cy + 188);
  ctx.strokeStyle = "#38bdf8";
  ctx.lineWidth = 3;
  ctx.strokeRect(cx, cy, cw, ch);
  // tyres
  ctx.font = "bold 26px system-ui, sans-serif";
  ctx.fillStyle = "#94a3b8";
  ctx.fillText("TYRES (psi)", 712, 120);
  const tyres = [["FL", 34, 712, 150], ["FR", 33, 852, 150], ["RL", 32, 712, 360], ["RR", 34, 852, 360]];
  for (const [n, v, x, y] of tyres) {
    ctx.fillStyle = "#0f172a";
    ctx.fillRect(x, y, 128, 170);
    ctx.strokeStyle = "#22c55e";
    ctx.lineWidth = 3;
    ctx.strokeRect(x, y, 128, 170);
    ctx.fillStyle = "#94a3b8";
    ctx.fillText(n, x + 12, y + 36);
    ctx.fillStyle = "#22c55e";
    ctx.font = "bold 56px system-ui, sans-serif";
    ctx.fillText(String(v), x + 26, y + 118);
    ctx.font = "bold 26px system-ui, sans-serif";
  }
}

export function createProductsScene(parentGroup) {
  const group = new THREE.Group();
  parentGroup.add(group);
  const pickables = [];
  const stage = new THREE.Group();                 // turntable
  group.add(stage);

  // A floor grid and a little extra light for small dark parts (lights inside this group only act in this mode)
  const grid = new THREE.GridHelper(1.2, 48, 0x334155, 0x1b2434);
  grid.rotation.x = Math.PI / 2;
  grid.userData.noFrame = true;
  group.add(grid);
  const fill = new THREE.DirectionalLight(0xffffff, 1.1);
  fill.position.set(-0.6, -1.2, 0.8);
  group.add(fill);
  const under = new THREE.DirectionalLight(0xcbd5e1, 0.7);
  under.position.set(0.3, -0.4, -1.0);
  group.add(under);

  const products = {};                             // id -> { group, explode: [], section, card }
  const options = { bought: true, context: true, section: false, fov: true, glow: true, turntable: false, xray: false };
  let current = "dash";
  let focused = false;                             // the current view frames one part (cams: one pod)
  let explodeT = 0;
  let data = null;
  let loadPromise = null;
  const sectionPlane = new THREE.Plane(new THREE.Vector3(-1, 0, 0), 0);
  const glowMats = [];

  function addPick(obj, id, info) {
    obj.userData.pickId = id;
    if (!pickables.some((p) => p.id === id)) pickables.push({ id, mesh: obj, ...info });
  }

  function addExplode(product, obj, dir, dist) {
    product.explode.push({ obj, base: obj.position.clone(), dir: new THREE.Vector3(...dir).normalize(), dist });
  }

  function stlMesh(geo, color, o = {}) {
    const m = new THREE.Mesh(geo, material(color, o));
    m.userData.printed = !!o.printed;
    return m;
  }

  // ------------------------------------------------------------------ dash unit
  async function buildDash(enc) {
    const p = { group: new THREE.Group(), explode: [], context: [], bought: [], focus: {} };
    const asm = new THREE.Group();                 // the generator's assembly frame (PCB centre, parts up +Z)
    const [cx, cy] = enc.viewer_frame.pcb_center_mm;
    const cz = enc.viewer_frame.z_mid_mm;
    new THREE.Matrix4().set(-1, 0, 0, cx * MM, 0, 0, 1, -cz * MM, 0, 1, 0, cy * MM, 0, 0, 0, 1)
      .decompose(asm.position, asm.quaternion, asm.scale);           // a rotation: nothing is mirrored
    p.group.add(asm);
    const o = enc.overall_mm;
    const info = `${o.width} × ${o.height} × ${o.depth} mm overall · ${enc.checks.filter((c) => c.ok).length}/${enc.checks.length} fit checks`;
    const parts = [         // [name, colour, explode (mm along the depth, or an [x, y, z] move in this frame), printed, ...]
      ["bezel", PRINT, -50, true, "Bezel (printed, face down)", "The display hangs by its four ears on four bosses (4 × M3 × 6 from behind); the lip covers the outer 2 mm of the glass. Intake slots beside the screen; the plugs sit in its right cavity, and three fingers on its skin hold the piezo behind the right slots. A side opening, hidden by the USB wing, lets the car-USB cable in. 6 × M3 × 10 from the back of the plate."],
      ["housing", PRINT_LIGHT, 0, true, "Housing: plate + rear box (printed, plate down)", "The plate behind the display carries the bezel, three intake windows and the cable slot (the display's leads and the car-USB cable). The box holds the Pi on 4 posts and the carrier on 4 more; USB window, SMA bulkhead, AMPS M4 nuts, 2 mm bumps on the plate's back."],
      ["lid", PRINT, 62, true, "Lid with the 30 mm exhaust fan (printed, outside down)", "Finger-safe bar grille over the fan, which blows out; cable exit with a split grommet; locating rim; 4 × M3 × 12 into the box's ears."],
      ["display", 0x0b1220, -30, false, "SunFounder TS-7 7\" display (dummy)", "1024 × 600 IPS on HDMI, touch and 5 V on micro-USB. Board ~165.3 × 124.4 mm over its ears: measure it before printing."],
      ["cables", 0xf97316, -30, false, "HDMI FPC adapter + 90° micro-USB plug (dummy)", "Both rise in the bezel's right cavity to the plate's cable slot, then into the box above the USB window."],
      ["buzzer", 0xe11d48, -38, false, "12 V active piezo (dummy)", "Inside the dash unit: three fingers on the bezel's skin hold it 2 mm behind the right intake slots, so you hear it and the air still flows. IO13 low-side from 12 V. A blind-spot beep stops after 4 s (the door LED keeps flashing); a TPMS warning beeps twice, then only the screen shows it. Mute from the touch screen."],
      ["usb_wing", PRINT, [-28, 0, -50], true, "Twin USB wing (printed, front face down)", "Holds both car USB passthroughs beside the bezel's right edge (39 mm pitch), in v1's Ø25.8 × 23.8 mm double-D cuts (measured 25.16 thread / 23.28 flats). 3 × M3 × 10 from inside the bezel's right cavity into its top, centre and bottom bosses; VHB on its back to the trim. Both 36 mm hex nuts fit and spin from the open back on the bench (or from outside if rear-mounted)."],
      ["usb_pass", 0x94a3b8, [-58, 0, -50], false, "2× USB passthroughs from v1 (dummy)", "Both sockets face the passenger side (car USB port + second USB / 12 V charger). The lower cable climbs behind the centre screw post inside the wing; both enter the bezel through one side opening, cross above the display's plugs and drop through the plate's cable slot into the pocket. Thread Ø25.16 and flats 23.28 are measured from your caliper photos; measure the remaining dimensions before printing."],
      ["wing_screws", 0xcbd5e1, [14, 0, -50], false, "3 × M3 × 10 socket cap (twin USB wing)", "Driven from inside the bezel's right cavity, before the display goes in, through the bezel's 3 mm wall into the wing's top, centre and bottom bosses."],
      ["pi", 0x15803d, 14, false, "Raspberry Pi 4 + its plugs (dummy)", "On 4 posts behind the plate, ports to the driver's right through the box window; micro-HDMI adapter in HDMI0, 90° USB-C pigtail, and the 40-pin ribbon's IDC on the GPIO header (UART + I2C to the carrier's J6)."],
      ["fan", 0x111827, 62, false, "30 mm fan (dummy)", "Under the lid, over the carrier's fan zone, blowing out."],
    ];
    const geos = await Promise.all(parts.map(([name]) => (enc.files[`asm_${name}`] ? loadStl(enc.files[`asm_${name}`].file) : null)));
    parts.forEach(([name, color, ex, printed, title, mount], k) => {      // in list order: the panel lists them so
      const f = enc.files[`asm_${name}`];
      if (!geos[k]) return;
      const mesh = stlMesh(geos[k], color, { printed, roughness: printed ? 0.7 : 0.45, metalness: name === "wing_screws" ? 0.8 : 0.05 });
      asm.add(mesh);
      const v = Array.isArray(ex) ? ex : [0, 0, ex];
      addExplode(p, mesh, v, Math.hypot(...v) * MM);
      if (!printed) p.bought.push(mesh);
      if (name === "usb_wing") p.focus.wing = mesh;
      if (name === "buzzer") p.focus.piezo = mesh;
      addPick(mesh, `pp_dash_${name}`, {
        title, category: printed ? "Printed part (ASA)" : "Bought part (dummy shape)", source: printed ? "PRINT · 01-hardware/enclosure" : "INVENTORY / BUY",
        location: info, mount, wiring: f.label,
      });
    });

    // the real carrier PCB (KiCad), centred at the asm origin, parts up
    const pcbG = new THREE.Group();
    asm.add(pcbG);
    try {
      const gltf = await new GLTFLoader().loadAsync(CARRIER + "docs/tpms_v2_carrier.glb");
      const root = gltf.scene;
      const a1 = root.getObjectByName("A1");
      const top = a1 ? a1.position.y : 0.00155;
      for (const [ref, file] of [["A1", "ESP32_DevKit_30pin.wrl"], ["A2", "CC1101_Module.wrl"]]) {
        const node = root.getObjectByName(ref);
        if (!node) continue;
        try {
          const text = await (await fetchOk(CARRIER + "lib/3d/" + file)).text();
          for (const m of parseWrl(text)) node.add(m);
        } catch (err) {
          console.warn(`carrier: ${file} not loaded (${err.message})`);
        }
      }
      const holder = new THREE.Group();
      holder.rotation.x = Math.PI / 2;            // glTF Y-up -> Z-up; KiCad's Y (page down) -> -Y
      holder.position.z = -top / 2;
      holder.add(root);
      pcbG.add(holder);
      const refs = await componentInfo();
      root.traverse((n) => {
        if (n.material) for (const m of [].concat(n.material)) m.side = THREE.DoubleSide;
      });
      for (const node of root.children[0]?.children || root.children) {
        const ref = node.name;
        if (!ref || !/^[A-Z]+\d+$/.test(ref)) continue;
        const r = refs[ref];
        addPick(node, `pp_pcb_${ref}`, {
          title: `${ref}${r ? `: ${r.value}` : ""}`, category: "Carrier PCB component (KiCad 3-D model)",
          source: r?.source || "Carrier PCB",
          location: "100 × 100 mm 2-layer carrier, rev A (DRC clean), on 4 posts behind the Pi, parts toward the lid",
          mount: r?.mount || "Placed by JLCPCB (Economic PCBA)", wiring: r?.note || "See the carrier README and the schematic PDF.",
        });
      }
      addPick(holder, "pp_dash_pcb", {
        title: "Carrier PCB, rev A (real KiCad model)", category: "Custom PCB", source: "JLCPCB 2-layer + Economic PCBA",
        location: info, mount: "4 × M3 × 6 on 92 × 92 mm into the housing's posts, parts toward the lid; 3 mm air gap above the Pi's tallest part.",
        wiring: "Two TPS54560B bucks (5.17 V / 5 A for the Pi and the display, 1 A for the ESP32 side), 12 V protection, INA226 monitors, blinker optos, LED / piezo / fan drivers, ESP32 DevKit and CC1101 on sockets.",
      });
    } catch (err) {
      console.warn(`carrier GLB not loaded (${err.message}); using the plain board`);
      const f = enc.files.asm_pcb;
      if (f) pcbG.add(stlMesh(await loadStl(f.file), 0x065f46));
    }
    addExplode(p, pcbG, [0, 0, 1], 36 * MM);
    p.bought.push(pcbG);

    // the screen: the active area, just in front of the glass
    const act = enc.front_view_mm.active;
    const canvas = document.createElement("canvas");
    canvas.width = 1024;
    canvas.height = 600;
    drawScreen(canvas);
    const tex = new THREE.CanvasTexture(canvas);
    tex.colorSpace = THREE.SRGBColorSpace;
    tex.anisotropy = 4;
    const screen = new THREE.Mesh(new THREE.PlaneGeometry((act[1] - act[0]) * MM, (act[3] - act[2]) * MM),
      new THREE.MeshBasicMaterial({ map: tex, toneMapped: false }));
    screen.rotation.x = Math.PI / 2;               // faces -Y, texture up = +Z
    screen.position.set(((act[0] + act[1]) / 2) * MM, -0.15 * MM, ((act[2] + act[3]) / 2) * MM);
    p.group.add(screen);
    addExplode(p, screen, [0, -1, 0], 30 * MM);
    p.bought.push(screen);
    addPick(screen, "pp_dash_display", { title: "SunFounder TS-7 7\" display", category: "Display", source: "INVENTORY", location: info, mount: "Normal way up (IPS).", wiring: "HDMI0 from the Pi; touch over USB; 5 V from the carrier's J5." });

    // the console: trim with the 191 / 123 × 129 mm opening, the pocket behind it
    const op = enc.console_opening_mm;
    const zTrim = -(enc.z_levels_mm.plate_back - 2.0);           // the 2 mm bumps hold the plate off the trim
    const yb = op.bottom_y, yt = op.bottom_y + op.height;
    const trap = [[-op.bottom_width / 2, yb], [op.bottom_width / 2, yb], [op.top_width / 2, yt], [-op.top_width / 2, yt]];
    const trim = new THREE.Shape([[-175, yb - 70], [175, yb - 70], [175, yt + 95], [-175, yt + 95]].map(([x, y]) => new THREE.Vector2(x * MM, y * MM)));
    trim.holes.push(new THREE.Path(trap.map(([x, y]) => new THREE.Vector2(x * MM, y * MM))));
    const trimMesh = new THREE.Mesh(new THREE.ExtrudeGeometry(trim, { depth: 3 * MM, bevelEnabled: false }),
      material(0x1e2533, { opacity: 0.9, roughness: 0.8 }));
    trimMesh.rotation.x = Math.PI / 2;
    trimMesh.position.y = (zTrim + 3) * MM;
    const wall = new THREE.Shape(trap.map(([x, y]) => new THREE.Vector2((x + Math.sign(x) * 2) * MM, (y + (y > yb ? 2 : -2)) * MM)));
    wall.holes.push(new THREE.Path(trap.map(([x, y]) => new THREE.Vector2(x * MM, y * MM))));
    const pocket = new THREE.Mesh(new THREE.ExtrudeGeometry(wall, { depth: 62 * MM, bevelEnabled: false }),
      material(0x334155, { opacity: 0.28, roughness: 0.8 }));
    pocket.rotation.x = Math.PI / 2;
    pocket.position.y = (zTrim + 3 + 62) * MM;
    for (const m of [trimMesh, pocket]) {
      m.userData.noFrame = true;
      p.group.add(m);
      p.context.push(m);
      addPick(m, "pp_dash_console", {
        title: "Console trim and pocket (Option A, for scale)", category: "Car", source: "OEM CAR",
        location: `Opening ${op.top_width} top / ${op.bottom_width} bottom × ${op.height} mm (v1 paper fit)`,
        mount: `The plate's 2 mm bumps rest on the trim; the box drops into the pocket, which needs ≥ ${enc.box_mm.clear_pocket_depth_needed} mm of clear depth. The unit stands ${enc.proud_of_trim_mm} mm proud of the trim.`,
        wiring: "Air leaves round the frame's edge: don't seal the gap or the pocket.",
      });
    }
    const lab = makeLabel(`Dash unit · ${o.width} × ${o.height} × ${o.depth} mm`, 0.011);
    lab.position.set(0, -0.02, (enc.front_view_mm.bezel[3] + 14) * MM);
    p.group.add(lab);
    p.titles = [lab];                              // hidden in the close-ups
    p.section = { point: [cx * MM, 0, 0], normal: [-1, 0, 0] };   // vertical cut through the PCB's centre
    p.views = [["front", "Front", [0, -1, 0.1]], ["iso", "Isometric", [-0.85, -1, 0.6]], ["rear", "Rear (lid)", [0.75, 1, 0.55]],
      ["side", "Side / cut", [1, -0.12, 0.2]], ["top", "Top", [0.001, -0.25, 1]],
      ["wing", "USB wing", [0.95, -0.8, 0.35], "wing", 1.9], ["wing_back", "USB wing · from behind", [0.55, 1, -0.35], "wing", 1.9, { context: false }],
      ["piezo", "Piezo (see-through)", [0.3, -1, 0.2], "piezo", 3.4, { xray: true }]];
    return p;
  }

  async function componentInfo() {
    const out = {};
    try {
      const bom = parseCsv(await (await fetchOk(MFG + "tpms_v2_carrier_bom_jlcpcb.csv")).text());
      for (const r of bom) {
        for (const ref of (r.Designator || "").split(",")) {
          out[ref.trim()] = { value: r.Comment, source: `JLCPCB assembly · LCSC ${r["LCSC Part #"]}`, mount: `${r.Footprint} · ${r.Library} part`, note: "Placed and reflowed by JLCPCB (Economic PCBA)." };
        }
      }
      const hand = parseCsv(await (await fetchOk(MFG + "tpms_v2_carrier_hand_solder_and_dnp.csv")).text());
      for (const r of hand) {
        const ref = (r.Designator || "").trim();
        if (!ref) continue;
        out[ref] = { value: r.What || "", source: "Hand-soldered by you", mount: r["Buy / fit"] || "", note: r.Notes || "Fit after the boards arrive (carrier README, Hand soldering)." };
      }
    } catch (err) {
      console.warn(`carrier part list not loaded (${err.message})`);
    }
    return out;
  }

  // ------------------------------------------------------------------ mirror camera pods
  async function buildCams(mr) {
    const p = { group: new THREE.Group(), explode: [], context: [], bought: [], fov: [], focus: {}, wideOnly: [] };
    const cp = mr.camera_pod;
    const rp = cp.right_pod_mm;
    const vhb = mr.parameters.VHB_T;
    const [hf, vf] = [cp.fov_deg.horizontal, cp.fov_deg.vertical_16_9].map((d) => THREE.MathUtils.degToRad(d / 2));
    const headMat = material(0x9aa5b8, { opacity: 0.42, roughness: 0.35, metalness: 0.3 });
    const glassMat = new THREE.MeshStandardMaterial({ color: 0x9fb6cc, metalness: 0.9, roughness: 0.08, side: THREE.DoubleSide });
    const sideMat = material(0x64748b, { opacity: 0.16, roughness: 0.6 });
    const fovMat = new THREE.MeshBasicMaterial({ color: 0x06b6d4, transparent: true, opacity: 0.05, side: THREE.DoubleSide, depthWrite: false });
    const [podGeoL, podGeoR, camGeoL, camGeoR] = await Promise.all(
      ["asm_cam_pod_left", "asm_cam_pod_right", "asm_cam_left", "asm_cam_right"].map((k) => loadStl(mr.files[k].file)));
    for (const side of ["left", "right"]) {
      const s = side === "left" ? -1 : 1;
      const sideG = new THREE.Group();
      sideG.position.x = s * 0.165;
      p.group.add(sideG);
      sideG.userData.home = sideG.position.clone();
      // mirror head (rounded block) above the pod, its rear face = the glass
      const hw = 0.2, hd = 0.095, hh = 0.125;
      const shape = new THREE.Shape();
      const r = 0.03;
      shape.moveTo(-hw / 2 + r, 0);
      shape.lineTo(hw / 2 - r, 0);
      shape.quadraticCurveTo(hw / 2, 0, hw / 2, r);
      shape.lineTo(hw / 2, hh - r * 1.6);
      shape.quadraticCurveTo(hw / 2, hh, hw / 2 - r * 1.6, hh);
      shape.lineTo(-hw / 2 + r, hh);
      shape.quadraticCurveTo(-hw / 2, hh, -hw / 2, hh - r);
      shape.lineTo(-hw / 2, r);
      shape.quadraticCurveTo(-hw / 2, 0, -hw / 2 + r, 0);
      const head = new THREE.Mesh(new THREE.ExtrudeGeometry(shape, { depth: hd, bevelEnabled: true, bevelThickness: 0.006, bevelSize: 0.004, bevelSegments: 3, curveSegments: 10 }), headMat);
      head.rotation.x = Math.PI / 2;                // shape Y -> Z, extrusion -> -Y
      head.scale.x = s;                             // the outer end is the round one
      head.position.set(0, hd / 2, vhb * MM + 0.004);
      const glass = new THREE.Mesh(new THREE.PlaneGeometry(hw - 0.03, hh - 0.03), glassMat);
      glass.rotation.x = Math.PI / 2;
      glass.position.set(0, -hd / 2 - 0.0062, vhb * MM + 0.004 + hh / 2);
      const stalk = new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.05, 0.04), headMat);
      stalk.position.set(-s * 0.125, 0.012, vhb * MM + 0.03);
      const door = new THREE.Mesh(new THREE.PlaneGeometry(0.26, 0.42), sideMat);
      door.rotation.y = Math.PI / 2;                // in the car's side plane: 0.42 m fore-aft, 0.26 m tall
      door.position.set(-s * 0.15, -0.15, -0.09);
      for (const m of [head, glass, stalk, door]) {
        m.userData.noFrame = m === door;
        sideG.add(m);
        p.context.push(m);
      }
      addPick(head, `pp_cam_mirror_${side}`, {
        title: `${side === "left" ? "Left" : "Right"} door mirror (for scale)`, category: "Car", source: "OEM CAR",
        location: "The pod goes under the cap's outer half, its lens face at or just behind the mirror's rear edge",
        mount: "Take the cap off (or look inside with a light) and mark the turn repeater and its wires before drilling (audit VEH-06).",
        wiring: "The camera lead goes up through the cap, through the mirror's hinge with a service loop, into the door harness and through the door boot.",
      });
      addPick(door, `pp_cam_door_${side}`, { title: "The car's side (reference strip)", category: "Car", source: "OEM CAR", location: "Door skin / glass below the mirror", mount: "A thin strip of it stays at the picture's inner edge: the Pi uses it to spot a folded or knocked mirror (V6).", wiring: "—" });

      // the pod and the camera, in the pod frame turned into the car's
      const podG = new THREE.Group();
      podG.quaternion.copy(rotationFrom(cp.frame_to_car[side]));
      const lens = new THREE.Vector3(s * rp.lens_centre[0], rp.lens_centre[1], rp.lens_centre[2]).multiplyScalar(MM);
      podG.position.set(s * 0.045, -hd / 2 - 0.008 - lens.y, 0);    // lens face just behind the mirror glass
      sideG.add(podG);
      const pod = stlMesh(side === "left" ? podGeoL : podGeoR, PRINT, { printed: true, roughness: 0.7 });
      const cam = stlMesh(side === "left" ? camGeoL : camGeoR, 0x111827, { roughness: 0.35, metalness: 0.4 });
      podG.add(pod, cam);
      p.bought.push(cam);
      const axis = new THREE.Vector3(s * rp.axis[0], rp.axis[1], rp.axis[2]);
      addExplode(p, pod, [0, 0, -1], 0.03);
      addExplode(p, cam, axis.toArray(), 0.075);
      const screws = new THREE.Group();
      for (const [x, y] of rp.pilots) {
        const sc = new THREE.Mesh(new THREE.CylinderGeometry(1.4 * MM, 1.4 * MM, 14 * MM, 12), material(0xcbd5e1, { metalness: 0.8, roughness: 0.3 }));
        sc.rotation.x = Math.PI / 2;
        sc.position.set(s * x * MM, y * MM, (vhb + 2.5 - 5) * MM);
        const hd2 = new THREE.Mesh(new THREE.CylinderGeometry(2.8 * MM, 2.8 * MM, 2 * MM, 16), sc.material);
        hd2.rotation.x = Math.PI / 2;
        hd2.position.set(s * x * MM, y * MM, (vhb + 2.5 + 1.0) * MM);
        screws.add(sc, hd2);
      }
      podG.add(screws);
      p.bought.push(screws);
      addExplode(p, screws, [0, 0, 1], 0.03);
      const pb = mr.camera_pod;
      addPick(pod, `pp_cam_pod_${side}`, {
        title: `${side === "left" ? "Left" : "Right"} mirror camera pod (printed, cap face down)`,
        category: "Printed part (ASA)", source: "PRINT · make_mounts.py",
        location: `${pb.size_mm.join(" × ")} mm, ${pb.below_cap_mm} mm below the cap; aim ${pb.aim_deg.outward_of_straight_back}° outward of straight back, ${pb.aim_deg.down}° down (audit CAM-02)`,
        mount: `${pb.cap_holes.screw}. Cap holes: ${pb.cap_holes.cable}; ${pb.cap_holes.screws} (drill guide). Its flat side faces the car, parallel to the car's side.`,
        wiring: `The camera's body sits in a teardrop bore (drains rearward), held by its lip, a ${pb.set_screw}. The lead climbs a Ø${mr.parameters.PLUG_PASS_D} mm channel at ${mr.parameters.CHANNEL_SLOPE}° into the cap.`,
      });
      addPick(cam, `pp_cam_${side}`, {
        title: `${side === "left" ? "Left" : "Right"} USB UVC camera (dummy: measure yours)`, category: "Bought part", source: "BUY after the V4 acceptance test",
        location: `Assumed: body Ø${pb.camera.body_d} × ${pb.camera.body_l} mm, lip Ø${pb.camera.lip_d} mm`,
        mount: "Measure the one you buy and regenerate: python 01-hardware/enclosure/make_mounts.py --set CAM_D=… CAM_LIP_D=… CAM_BODY_L=…",
        wiring: "MJPEG 720p30 at full sensor width, HFOV ≥ 95° measured, IP67, both streaming at once on the Pi 4 (premortem V4).",
      });

      // what the camera sees: a 95° × 63° pyramid from the lens, and the 39° from straight back
      const lensW = lens.clone().applyQuaternion(podG.quaternion).add(podG.position);
      const f = axis.clone().applyQuaternion(podG.quaternion).normalize();
      const rgt = new THREE.Vector3().crossVectors(f, new THREE.Vector3(0, 0, 1)).normalize();
      const up = new THREE.Vector3().crossVectors(rgt, f).normalize();
      const L = 0.2;
      const corners = [[1, 1], [-1, 1], [-1, -1], [1, -1]].map(([sx, sy]) => f.clone()
        .addScaledVector(rgt, Math.tan(hf) * sx).addScaledVector(up, Math.tan(vf) * sy).multiplyScalar(L).add(lensW));
      const tri = [];
      for (let i = 0; i < 4; i++) tri.push(lensW, corners[i], corners[(i + 1) % 4]);
      const fov = new THREE.Mesh(new THREE.BufferGeometry().setFromPoints(tri), fovMat);
      fov.userData.noFrame = true;
      const edges = line([...corners.map((c) => c.toArray()), corners[0].toArray()], 0x38bdf8, 0.5);
      const rays = corners.map((c) => line([lensW.toArray(), c.toArray()], 0x38bdf8, 0.45));
      const back = line([lensW.toArray(), [lensW.x, lensW.y - 0.2, lensW.z]], 0xf8fafc, 0.7);
      const arc = [];
      const yaw = THREE.MathUtils.degToRad(pb.aim_deg.outward_of_straight_back);
      for (let i = 0; i <= 20; i++) {
        const t = (yaw * i) / 20;
        arc.push([lensW.x + s * Math.sin(t) * 0.09, lensW.y - Math.cos(t) * 0.09, lensW.z]);
      }
      const arcL = line(arc, 0xf59e0b, 0.95);
      const aimL = line([lensW.toArray(), lensW.clone().addScaledVector(f, 0.2).toArray()], 0xf59e0b, 0.95);
      const lab = makeLabel(`${pb.aim_deg.outward_of_straight_back}° outward · ${pb.aim_deg.down}° down\nHFOV ${cp.fov_deg.horizontal}°`, 0.016, "#f59e0b");
      lab.position.set(lensW.x + s * 0.07, lensW.y - 0.12, lensW.z + 0.03);
      for (const m of [fov, edges, ...rays, back, arcL, aimL, lab]) {
        sideG.add(m);
        p.fov.push(m);
      }
      const nl = makeLabel(side === "left" ? "LEFT mirror" : "RIGHT mirror", 0.014);
      nl.position.set(0, 0, vhb * MM + 0.15);
      sideG.add(nl);
      p.context.push(nl);
      p.wideOnly.push(nl);
      if (side === "right") {                       // the section: a vertical cut along the right camera's axis
        p.section = { point: lensW.clone().add(sideG.position).toArray(), normal: rgt.clone().negate().toArray() };
      }
      p.focus[side] = podG;
    }
    // [key, label, direction to the camera, focus (one pod), padding round it]
    p.views = [["l_rear", "Left pod · rear ¾", [0.22, -1, -0.5], "left", 2.6], ["l_below", "Left pod · from below", [-0.12, -0.3, -1], "left", 2.6],
      ["l_out", "Left pod · from outboard", [-1, -0.22, -0.25], "left", 2.6], ["r_rear", "Right pod · rear ¾", [-0.22, -1, -0.5], "right", 2.6],
      ["both", "Both mirrors", [0.12, -1, -0.3]], ["iso", "Isometric", [0.8, -1, 0.45]]];
    return p;
  }

  // ------------------------------------------------------------------ door-sail LED pods
  // Laid out round the driver's eyes (the origin): each pod sits back along its own aim line at 0.15 × its real
  // distance, so the directions and the aim are true and both rays end at the eyes.
  async function buildLeds(mr) {
    const p = { group: new THREE.Group(), explode: [], context: [], bought: [], fov: [], focus: {} };
    const sailMat = material(0x2c3547, { opacity: 0.85, roughness: 0.8 });
    const eye = new THREE.Vector3(...mr.parameters.EYE);
    const K = 0.1;
    const eyeM = new THREE.Mesh(new THREE.SphereGeometry(0.003, 20, 14), material(0xf8fafc, { emissive: 0x38bdf8, emissiveIntensity: 0.6 }));
    const eyeL = makeLabel("driver's eyes", 0.01, "#38bdf8");
    eyeL.position.set(0, -0.004, 0.014);
    p.group.add(eyeM, eyeL);
    p.fov.push(eyeM, eyeL);
    p.wideOnly = [eyeM, eyeL];                       // the close-ups look along the aim, through the eye point
    const closeUps = [];
    for (const side of ["left", "right"]) {
      const s = side === "left" ? -1 : 1;
      const L = mr.led_pods[side];
      const axisCar = new THREE.Vector3(...L.axis_car).normalize();
      const rot = rotationFrom(L.frame_to_car);
      const tip = new THREE.Vector3(...L.led_tip_mm).multiplyScalar(MM);
      const dist = new THREE.Vector3(...L.at_m).add(tip.clone().applyQuaternion(rot)).distanceTo(eye);   // LED tip -> eyes
      const podG = new THREE.Group();
      podG.quaternion.copy(rot);
      podG.position.copy(axisCar.clone().multiplyScalar(-dist * K)).sub(tip.clone().applyQuaternion(podG.quaternion));
      p.group.add(podG);
      const [podGeo, ledGeo] = await Promise.all([loadStl(mr.files[`asm_led_pod_${side}`].file), loadStl(mr.files[`asm_led_${side}`].file)]);
      const pod = stlMesh(podGeo, PRINT, { printed: true, roughness: 0.7 });
      const ledMat = material(0xf59e0b, { emissive: 0xf59e0b, emissiveIntensity: 0.6, roughness: 0.25 });
      glowMats.push(ledMat);
      const led = new THREE.Mesh(ledGeo, ledMat);
      podG.add(pod, led);
      p.bought.push(led);
      const axis = new THREE.Vector3(...L.axis);
      addExplode(p, pod, [0, 0, 1], 0.012);
      addExplode(p, led, axis.clone().negate().toArray(), 0.02);
      const sail = new THREE.Mesh(new THREE.ShapeGeometry(new THREE.Shape([[-0.035, -0.03], [0.04, -0.03], [-0.02, 0.05]].map(([x, y]) => new THREE.Vector2(x, y)))), sailMat);
      sail.position.z = -0.0005;
      sail.userData.noFrame = true;
      podG.add(sail);
      p.context.push(sail);
      addPick(sail, `pp_led_sail_${side}`, { title: `${side === "left" ? "Driver's" : "Passenger's"} door sail (for scale)`, category: "Car", source: "OEM CAR", location: "The triangular trim inside the door, under the mirror", mount: "Clean with IPA before the VHB; check the window regulator and the speaker don't sit right behind the Ø4 mm wire hole.", wiring: "The LED pair runs inside the door card to the door boot with the camera lead." });
      const ray = line([tip.toArray(), tip.clone().addScaledVector(axis, dist * K).toArray()], 0xf59e0b, 0.9);
      const normal = line([tip.toArray(), [tip.x, tip.y, tip.z + 0.03]], 0xf8fafc, 0.6);   // the sail's normal: the tilt is the angle
      podG.add(ray, normal);
      p.fov.push(ray, normal);
      const lab = makeLabel(`${side === "left" ? "Left" : "Right"} door · ${L.tilt_from_sail_deg}° off the sail\n${dist.toFixed(2)} m from the driver's eyes`, 0.011, "#f59e0b");
      lab.position.copy(podG.position).add(new THREE.Vector3(-s * 0.03, 0.02, 0.03));
      p.group.add(lab);
      p.fov.push(lab);
      p.wideOnly.push(lab);
      p.focus[side] = podG;
      // tilt view: square to the plane of the sail's normal and the aim, so the angle between them shows
      const sailN = new THREE.Vector3(0, 0, 1).applyQuaternion(podG.quaternion);
      const sideDir = new THREE.Vector3().crossVectors(sailN, axisCar).normalize();
      if (sideDir.z < 0) sideDir.negate();         // from above
      closeUps.push([`${side[0]}_eye`, `${side === "left" ? "Left" : "Right"} pod · from the driver's eyes`, { from: [0, 0, 0] }, side],
        [`${side[0]}_side`, `${side === "left" ? "Left" : "Right"} pod · its ${L.tilt_from_sail_deg}° tilt`, sideDir.toArray(), side, 3.2]);
      addPick(pod, `pp_led_pod_${side}`, {
        title: `${side === "left" ? "Left" : "Right"} door-sail LED pod (printed, base down)`, category: "Printed part (ASA)", source: "PRINT · make_mounts.py",
        location: `${L.size_mm.join(" × ")} mm on the ${side === "left" ? "driver's" : "passenger's"} inner door sail, inside the cabin, ${dist.toFixed(2)} m from the driver's eyes`,
        mount: "3M VHB on the sail trim; a Ø4 mm hole through the trim under it for the two wires. Not in the A-pillar trim (curtain airbag) and not outside the mirror (premortem C7).",
        wiring: `Aimed at the driver's eyes: ${L.tilt_from_sail_deg}° off the sail's normal. The LED sits ${mr.parameters.LED_RECESS} mm deep, so no direct light reaches the side window or the windscreen.`,
      });
      addPick(led, `pp_led_${side}`, { title: `${side === "left" ? "Left" : "Right"} 5 mm amber LED`, category: "Bought part", source: "BUY", location: "Pushed in from the back, its flange on the pod's shoulder", mount: "A dab of RTV; legs + 24 AWG pair back through the trim with the camera lead.", wiring: `Low-side MOSFET on ${side === "left" ? "IO25" : "IO14"}: steady = car in the blind spot, flashing = you signal towards it.` });
      if (side === "left") {                       // the section: a vertical cut along the left LED's axis
        const tipW = tip.clone().applyQuaternion(podG.quaternion).add(podG.position);
        p.section = { point: tipW.toArray(), normal: new THREE.Vector3().crossVectors(axisCar, new THREE.Vector3(0, 0, 1)).normalize().toArray() };
      }
    }
    p.views = [["shoulder", "Over the driver's shoulder", [-0.3, -1, 0.3]], ...closeUps, ["top", "Top (plan)", [0.001, -0.15, 1]]];
    return p;
  }

  // ------------------------------------------------------------------ print beds
  async function buildPlates(enc, mr) {
    const p = { group: new THREE.Group(), explode: [], context: [], bought: [] };
    const beds = [
      ["Bezel · face down", [["enc", "print_bezel"]]],
      ["Housing · plate down", [["enc", "print_housing"]]],
      ["Lid · outside down", [["enc", "print_lid"]]],
      ["Camera pods L + R + drill guide", [["mnt", "print_cam_pod_left"], ["mnt", "print_cam_pod_right"], ["mnt", "print_cam_drill_guide"]]],
      ["USB wing + door-sail LED pods", [["enc", "print_usb_wing"], ["mnt", "print_led_pod_left"], ["mnt", "print_led_pod_right"]]],
    ];
    const bedMat = material(0xb9a36a, { roughness: 0.5, metalness: 0.35 });
    const vols = { ...enc.volumes_cm3, ...mr.volumes_cm3 };
    let i = 0;
    for (const [title, list] of beds) {
      const bed = new THREE.Group();
      bed.position.set(((i % 3) - 1) * 0.26, Math.floor(i / 3) * -0.27 + 0.13, 0);
      p.group.add(bed);
      const slab = new THREE.Mesh(new THREE.BoxGeometry(0.22, 0.22, 0.003), bedMat);
      slab.position.z = -0.0015;
      const g = new THREE.GridHelper(0.22, 11, 0x6b5b2e, 0x8a7744);
      g.rotation.x = Math.PI / 2;
      g.position.z = 0.0002;
      bed.add(slab, g);
      const geos = await Promise.all(list.map(([src, name]) => loadStl((src === "enc" ? enc : mr).files[name].file)));
      const sizes = geos.map((geo) => { geo.computeBoundingBox(); return geo.boundingBox; });
      const gap = 0.012;
      const total = sizes.reduce((a, b) => a + (b.max.x - b.min.x), 0) + gap * (sizes.length - 1);
      let x = -total / 2;
      geos.forEach((geo, k) => {
        const b = sizes[k];
        const m = stlMesh(geo, PRINT_LIGHT, { printed: true, roughness: 0.65 });
        m.position.set(x - b.min.x, -(b.min.y + b.max.y) / 2, -b.min.z);
        x += b.max.x - b.min.x + gap;
        bed.add(m);
        const [src, name] = list[k];
        const key = name.replace("print_", "");
        const dims = [b.max.x - b.min.x, b.max.y - b.min.y, b.max.z - b.min.z].map((v) => (v / MM).toFixed(1));
        addPick(m, `pp_plate_${key}`, {
          title: `${name}.stl`, category: "Print file (print orientation, no supports)", source: src === "enc" ? "make_enclosure.py" : "make_mounts.py",
          location: `${dims.join(" × ")} mm · ${vols[key] ?? "?"} cm³ solid`,
          mount: "ASA or ABS in an enclosed printer (PETG only for the test fit, never PLA), 0.2 mm layers, 4 perimeters, 30–40 % gyroid, brim.",
          wiring: `Download: 01-hardware/enclosure/stl/${name}.stl`,
        });
      });
      const lab = makeLabel(`${i + 1} · ${title}`, 0.02);
      lab.position.set(0, 0.128, 0.012);
      bed.add(lab);
      i++;
    }
    p.section = null;
    p.views = [["top", "Top", [0.001, -0.3, 1]], ["iso", "Isometric", [-0.45, -1, 0.85]]];
    return p;
  }

  // ------------------------------------------------------------------ cards
  function cards(enc, mr) {
    const dl = (src, name) => `<a href="${ENC}stl/${name}.stl" download>${name.replace("print_", "")}</a>`;
    const o = enc.overall_mm, cp = mr.camera_pod, ok = (r) => `${r.checks.filter((c) => c.ok).length}/${r.checks.length}`;
    return {
      dash: `<strong>Dash unit · ${o.width} × ${o.height} × ${o.depth} mm · ${ok(enc)} fit checks</strong><br>
        Bezel, housing and lid in ASA around the SunFounder TS-7, the Pi 4 on four posts, the real carrier PCB (rev A, from KiCad) on four more, and the 30 mm fan in the lid. ${enc.proud_of_trim_mm} mm proud of the trim; the box needs ≥ ${enc.box_mm.clear_pocket_depth_needed} mm of pocket.<br>
        The 12 V piezo is inside, behind the right intake slots (view "Piezo"); the touch screen mutes it and a blind-spot beep stops by itself after 4 s. Both car USB passthroughs move into the <b>twin USB wing</b> on the bezel's right (${enc.usb_passthrough.wing_mm.slice(0, 2).map((v) => v.toFixed(0)).join(" × ")} mm on the trim, 2× v1 Ø${enc.parameters.PASS_HOLE_D} × ${enc.parameters.PASS_FLAT_W} double-D cuts, sockets facing the passenger); measure the remaining passthrough dimensions and the trim there before printing it.<br>
        <span class="muted">Solid plastic: bezel ${enc.volumes_cm3.bezel}, housing ${enc.volumes_cm3.housing}, lid ${enc.volumes_cm3.lid}, USB wing ${enc.volumes_cm3.usb_wing} cm³. Print without supports.</span><br>
        STL: ${dl("enc", "print_bezel")} · ${dl("enc", "print_housing")} · ${dl("enc", "print_lid")} · ${dl("enc", "print_usb_wing")} · <a href="${ENC}README.md" target="_blank">Enclosure README</a> · <a href="${CARRIER}docs/tpms_v2_carrier.glb" download>carrier.glb</a>`,
      cams: `<strong>Mirror camera pods · ${cp.size_mm.join(" × ")} mm · ${ok(mr)} checks</strong><br>
        One under each mirror cap: aims the USB camera ${cp.aim_deg.outward_of_straight_back}° outward of straight back and ${cp.aim_deg.down}° down (audit CAM-02); the lens face is its rearmost point, so the pod is never in the picture. ${cp.below_cap_mm} mm below the cap.<br>
        Cap: ${cp.cap_holes.cable}; ${cp.cap_holes.screws}. ${cp.cap_holes.screw}.<br>
        <span class="muted">Camera assumed Ø${cp.camera.body_d} body, Ø${cp.camera.lip_d} lip, ${cp.camera.body_l} mm long: measure yours and run make_mounts.py --set CAM_D=… (and CAP_PITCH / CAP_ROLL for the cap's slope).</span><br>
        STL: ${dl("mnt", "print_cam_pod_left")} · ${dl("mnt", "print_cam_pod_right")} · ${dl("mnt", "print_cam_drill_guide")} · <a href="${ENC}README.md#mirror-cameras-and-door-leds" target="_blank">mounting steps</a>`,
      leds: `<strong>Door-sail LED pods · aimed at the driver</strong><br>
        The amber blind-spot LEDs sit on the inner door sails, inside the cabin, each in a small wedge aimed at the driver's eyes (left ${mr.led_pods.left.tilt_from_sail_deg}°, right ${mr.led_pods.right.tilt_from_sail_deg}° off the sail). The LED is ${mr.parameters.LED_RECESS} mm deep: no direct light on the side window (no reflection next to the mirror at night) or the windscreen.<br>
        <span class="muted">Measure the sail's angle (SAIL_YAW / SAIL_LEAN) if the aim looks off and regenerate with make_mounts.py.</span><br>
        STL: ${dl("mnt", "print_led_pod_left")} · ${dl("mnt", "print_led_pod_right")}`,
      plates: `<strong>Print beds · every printed part, as sliced</strong><br>
        Flat face down, no supports, each fits a 220 × 220 mm bed. ASA or ABS (enclosed printer), 0.2 mm layers, 4 perimeters, 30–40 % gyroid, brim; or order MJF PA12 from JLC3DP with the PCBs. Never PLA.<br>
        <span class="muted">Solid volume ${Object.values({ ...enc.volumes_cm3, ...mr.volumes_cm3 }).reduce((a, b) => a + b, 0).toFixed(0)} cm³ for the full set (dash unit, USB wing, both camera pods, both LED pods, the drill guide): well under one 1 kg spool.</span>`,
      all: `<strong>All v2 products, to scale</strong><br>
        The dash unit (with its piezo and the USB wing), the two mirror camera pods with their cameras and the two door-sail LED pods. Click any part for what it is and how it mounts.`,
    };
  }

  // ------------------------------------------------------------------ public
  const LIST = [["dash", "Dash unit"], ["cams", "Mirror cameras"], ["leds", "Door LEDs"], ["plates", "Print beds"], ["all", "All, to scale"]];
  const ALL_LAYOUT = { dash: [0, 0, 0], cams: [0, 0.02, 0.135], leds: [0, -0.06, -0.1] };

  function load() {
    if (loadPromise) return loadPromise;
    loadPromise = (async () => {
      const [enc, mr] = await Promise.all([(await fetchOk(ENC + "enclosure_report.json")).json(), (await fetchOk(ENC + "mounts_report.json")).json()]);
      const [dash, cams, leds, plates] = await Promise.all([buildDash(enc), buildCams(mr), buildLeds(mr), buildPlates(enc, mr)]);
      Object.assign(products, { dash, cams, leds, plates });
      for (const p of Object.values(products)) {
        p.group.visible = false;
        stage.add(p.group);
      }
      data = { enc, mr, cards: cards(enc, mr) };
      setProduct(current);
      return data;
    })();
    return loadPromise;
  }

  function visibleProducts() {
    return current === "all" ? ["dash", "cams", "leds"] : [current];
  }

  function applyOptions() {
    for (const [id, p] of Object.entries(products)) {
      const shown = visibleProducts().includes(id);
      p.group.visible = shown;
      p.group.position.set(...(current === "all" ? ALL_LAYOUT[id] || [0, 0, 0] : [0, 0, 0]));
      for (const m of p.context) m.visible = options.context && current !== "all";
      for (const m of p.bought) m.visible = options.bought;
      for (const m of p.fov || []) m.visible = options.fov && current !== "all";
      for (const m of p.wideOnly || []) m.visible = m.visible && !focused;
      for (const m of p.titles || []) m.visible = !focused;
      const planes = options.section && shown && p.section ? [sectionPlane] : [];
      p.group.traverse((o) => {
        if (o.userData.printed) {                  // see-through shell: printed parts only, never on the print beds
          const see = options.xray && id !== "plates";
          const m = o.material;
          m.transparent = see;
          m.opacity = see ? 0.2 : 1;
          m.depthWrite = !see;
        }
        if (!o.material || o.isSprite || o.isLine) return;
        for (const m of [].concat(o.material)) {
          if ((m.clippingPlanes || []).length !== planes.length) {
            m.clippingPlanes = planes;
            m.needsUpdate = true;
          }
        }
      });
    }
    grid.visible = ["dash", "all"].includes(current);            // a floor only where there is one
    placeGrid();
  }

  function placeGrid() {                           // the floor just under what is on show
    if (grid.visible) grid.position.z = frameBox().min.z - 0.002;
  }

  function setProduct(id) {
    current = id;
    stage.rotation.z = 0;
    if (!data) return;
    applyOptions();
    setExplode(explodeT);
  }

  function setExplode(t) {
    explodeT = t;
    for (const p of Object.values(products)) {
      for (const e of p.explode) e.obj.position.copy(e.base).addScaledVector(e.dir, e.dist * t);
    }
    if (data) placeGrid();
  }

  function setOption(name, on) {
    options[name] = on;
    if (data) applyOptions();
  }

  function frameBox(root = stage) {
    const box = new THREE.Box3();
    const tmp = new THREE.Box3();
    stage.updateMatrixWorld(true);
    const walk = (o) => {
      if (!o.visible || o.userData.noFrame) return;
      if (o.isMesh && o.geometry) {
        if (!o.geometry.boundingBox) o.geometry.computeBoundingBox();
        tmp.copy(o.geometry.boundingBox).applyMatrix4(o.matrixWorld);
        box.union(tmp);
      }
      for (const c of o.children) walk(c);
    };
    walk(root);
    if (box.isEmpty()) box.setFromCenterAndSize(new THREE.Vector3(), new THREE.Vector3(0.2, 0.2, 0.2));
    return box;
  }

  const ALL_VIEWS = [["iso", "Isometric", [-0.7, -1, 0.55]], ["front", "Front", [0, -1, 0.08]], ["top", "Top", [0.001, -0.25, 1]]];

  function views() {
    const p = current === "all" ? { views: ALL_VIEWS } : products[current];
    return (p?.views || []).map(([k, label]) => [k, label]);
  }

  function getView(key, fovDeg = 38) {
    const p = current === "all" ? { views: ALL_VIEWS } : products[current];
    const v = (p?.views || []).find((x) => x[0] === key) || p?.views?.[0];
    const focus = v?.[3] && p.focus?.[v[3]];
    focused = !!focus;
    for (const m of p?.wideOnly || []) {           // names only in the wide views
      m.visible = (p.fov?.includes(m) ? options.fov : options.context) && current !== "all" && !focused;
    }
    for (const m of p?.titles || []) m.visible = !focused;
    const box = frameBox(focus || stage);
    const sphere = box.getBoundingSphere(new THREE.Sphere());
    const label = (LIST.find((x) => x[0] === current) || [0, ""])[1];
    if (v && v[2]?.from) {                         // a fixed viewpoint (in the product's frame), e.g. the driver's eyes
      p.group.updateMatrixWorld(true);
      const pos = p.group.localToWorld(new THREE.Vector3(...v[2].from));
      const d = pos.distanceTo(sphere.center);
      return { pos, target: sphere.center.clone(), label: `${label} · ${v[1]}`, near: Math.max(0.0005, d / 400), far: d * 40 };
    }
    const dist = (sphere.radius / Math.sin(THREE.MathUtils.degToRad(fovDeg / 2))) * (v?.[4] ?? 1.02);
    const dir = new THREE.Vector3(...(v ? v[2] : [0, -1, 0.5])).normalize();
    return { pos: sphere.center.clone().addScaledVector(dir, dist), target: sphere.center.clone(), label: `${label} · ${v ? v[1] : ""}`, near: Math.max(0.0005, dist / 400), far: dist * 30, set: v?.[5] };
  }

  function update(dt, nowMs) {
    if (options.turntable) stage.rotation.z += dt * 0.35;
    const pulse = 0.5 + 0.5 * Math.sin(nowMs * 0.012);
    for (const m of glowMats) m.emissiveIntensity = options.glow ? 0.4 + 2.6 * pulse : 0.15;
    const p = products[current];
    if (options.section && p?.section) {
      const pt = new THREE.Vector3(...p.section.point);
      const n = new THREE.Vector3(...p.section.normal);
      p.group.updateMatrixWorld(true);
      const nm = new THREE.Matrix3().getNormalMatrix(p.group.matrixWorld);
      sectionPlane.setFromNormalAndCoplanarPoint(n.applyMatrix3(nm).normalize(), pt.applyMatrix4(p.group.matrixWorld));
    }
  }

  // what the click-to-inspect list shows per product (the carrier's ~170 components stay clickable in 3-D only)
  const PREFIX = { dash: ["pp_dash_"], cams: ["pp_cam_"], leds: ["pp_led_"], plates: ["pp_plate_"], all: ["pp_dash_", "pp_cam_", "pp_led_"] };
  function partsFor(id) {
    return pickables.filter((p) => (PREFIX[id] || []).some((k) => p.id.startsWith(k)) && p.mesh.visible && !/console|mirror_|door_|sail_/.test(p.id));
  }

  function raycastRoots() {
    return Object.values(products).filter((p) => p.group.visible).map((p) => p.group);
  }

  // a hit to ignore: cut away by the section, or a see-through printed part (so the parts inside can be clicked)
  function skipHit(hit) {
    if (options.xray && hit.object.userData.printed && current !== "plates") return true;
    return options.section && !!products[current]?.section && sectionPlane.distanceToPoint(hit.point) < 0;
  }

  function caption(id) {
    if (!data) return "Loading the STL files…";
    const { enc, mr } = data;
    const o = enc.overall_mm, cp = mr.camera_pod, L = mr.led_pods;
    const n = (r) => `${r.checks.filter((c) => c.ok).length}/${r.checks.length}`;
    return {
      dash: `Dash unit ${o.width} × ${o.height} × ${o.depth} mm · ${enc.proud_of_trim_mm} mm proud of the trim · piezo inside · USB wing on the right · ${n(enc)} fit checks · real carrier PCB from KiCad`,
      cams: `Camera pod ${cp.size_mm.join(" × ")} mm, ${cp.below_cap_mm} mm under the cap · aim ${cp.aim_deg.outward_of_straight_back}° out, ${cp.aim_deg.down}° down · ${n(mr)} mount checks`,
      leds: `LED pods ${L.left.size_mm.join(" × ")} / ${L.right.size_mm.join(" × ")} mm · ${L.left.tilt_from_sail_deg}° / ${L.right.tilt_from_sail_deg}° toward the driver`,
      plates: `${Object.keys({ ...enc.volumes_cm3, ...mr.volumes_cm3 }).length} print files on 5 beds · no supports · each fits 220 × 220 mm`,
      all: "Every v2 product to scale (grid: 25 mm squares)",
    }[id] || "";
  }

  return {
    group, pickables, list: LIST, load, setProduct, setExplode, setOption, views, getView, update,
    partsFor, raycastRoots, skipHit, caption,
    card: (id) => (data ? data.cards[id] || "" : "Loading the parts…"),
    get current() { return current; },
    get options() { return { ...options }; },
  };
}
