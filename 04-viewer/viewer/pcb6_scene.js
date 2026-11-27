import * as THREE from "three";
import { STLLoader } from "three/addons/STLLoader.js";

/**
 * v2 carrier PCB (100 x 100 x 1.6 mm, 6 layers) and the 3-D printed enclosure around it.
 *
 * Units: metres. Z up = the PCB's parts side, which faces the enclosure lid. Origin at the PCB centre.
 * Zones follow the generated layout (01-hardware/v2/carrier/carrier_layout.py): template (x, y) in mm from the
 * top-left, parts side up -> viewer (x - 50, 50 - y). Each layer shows the real copper when the textures from
 * 04-viewer/make_pcb_textures.py are present (media/pcb/L1.png ... L6.png), else a drawn sketch. The keep-outs
 * (fan zone, SMA strip, pin-free corners) come from 01-hardware/enclosure/make_enclosure.py, which also writes
 * the assembly STLs loaded here.
 */

const MM = 0.001;
const PX = 5.12; // texture pixels per mm (512 px = 100 mm)

function makeBox(w, d, h, color, metalness = 0.25, roughness = 0.45) {
  const geo = new THREE.BoxGeometry(w * MM, d * MM, h * MM);
  const mat = new THREE.MeshStandardMaterial({ color, metalness, roughness });
  return new THREE.Mesh(geo, mat);
}

// fit-template rectangle (x, y, w, h) -> centre in viewer mm
const centre = (x, y, w, h) => [x + w / 2 - 50, 50 - (y + h / 2)];

// from carrier_layout.py (DEVKIT_BOARD, CC1101_BOARD, the buck macros, ANTENNA_KEEPOUT, FAN_ZONE, SMA_STRIP)
const ZONES = {
  esp32: [0.2, 14.4, 28.3, 50.8],
  cc1101: [70.8, 53.6, 15, 30],
  buck_pi: [53, 14, 19.5, 44],
  buck_esp: [30, 17, 23, 41],
  protect: [1, 66, 32, 23],
  j1: [11, 89, 21.5, 10.5],
  j5: [55.5, 2.5, 30.5, 10],
  jst: [33.5, 93.4, 56.3, 6.4],
  io: [33, 70, 36, 23],
  fan: [29, 30, 32, 32],
  sma: [86, 28.5, 14, 12],
  antenna: [0.2, 14.4, 28.2, 5.9],
};

function rectPx(ctx, [x, y, w, h], stroke = true) {
  if (stroke) ctx.strokeRect(x * PX, y * PX, w * PX, h * PX);
  else ctx.fillRect(x * PX, y * PX, w * PX, h * PX);
}

function makeLayerTexture(layerIndex) {
  // Fallback sketch, shown until (or unless) the real copper image loads: see loadLayerImage()
  const c = document.createElement("canvas");
  c.width = 512;
  c.height = 512;
  const ctx = c.getContext("2d");
  const bg = ["#11161f", "#065f46", "#1e1b2e", "#047857", "#0f172a", "#11161f"][layerIndex];
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, 512, 512);
  if (layerIndex === 0) {
    ctx.strokeStyle = "rgba(226,232,240,0.5)";
    ctx.lineWidth = 2;
    ctx.setLineDash([8, 6]);
    for (const k of ["esp32", "cc1101", "buck_pi", "buck_esp", "protect", "j1", "j5", "jst", "io"]) rectPx(ctx, ZONES[k]);
    ctx.setLineDash([5, 4]);
    ctx.strokeStyle = "#f87171";
    rectPx(ctx, ZONES.fan);
    rectPx(ctx, ZONES.sma);
    for (const [x, y] of [[0, 0], [90, 0], [0, 90], [90, 90]]) rectPx(ctx, [x, y, 10, 10]);
    ctx.setLineDash([]);
    ctx.fillStyle = "#e2e8f0";
    ctx.font = "bold 12px monospace";
    const label = (t, z, dy = 14) => ctx.fillText(t, ZONES[z][0] * PX + 4, ZONES[z][1] * PX + dy);
    label("ESP32 DevKit", "esp32", 40);
    label("CC1101", "cc1101");
    label("5V_PI buck", "buck_pi");
    label("5V_ESP buck", "buck_esp");
    label("12 V protection", "protect");
    label("J1 12V", "j1");
    label("J5 5V", "j5");
    label("JST-GH", "jst");
    label("optos + drivers", "io");
    ctx.fillStyle = "#fca5a5";
    ctx.fillText("FAN ≤ 6 mm", 29 * PX + 6, 62 * PX - 6);
    ctx.fillText("SMA", 86 * PX + 10, 28.5 * PX + 36);
    ctx.fillStyle = "#facc15";
    ctx.fillText("run 04-viewer/make_pcb_textures.py for the real copper", 20, 505);
  } else {
    ctx.fillStyle = "#94a3b8";
    ctx.font = "bold 16px monospace";
    const text = ["", "L2: SOLID GND PLANE", "L3: SIGNALS + GND POUR", "L4: SIGNALS + GND POUR",
      "L5: SIGNALS + GND POUR", "L6: SIGNALS, POWER POURS"][layerIndex];
    ctx.fillText(text, 60, 260);
    ctx.fillStyle = "#0f172a";
    rectPx(ctx, ZONES.antenna, false);
  }
  const tex = new THREE.CanvasTexture(c);
  tex.anisotropy = 4;
  return tex;
}

// The real copper of each layer (written by 04-viewer/make_pcb_textures.py); keeps the sketch if it's missing
function loadLayerImage(layerIndex, mat) {
  new THREE.TextureLoader().load(`media/pcb/L${layerIndex + 1}.png`, (tex) => {
    tex.colorSpace = THREE.SRGBColorSpace;
    tex.anisotropy = 8;
    mat.map = tex;
    mat.needsUpdate = true;
  }, undefined, () => {});
}

function stlGeometry(buffer) {
  const geo = new STLLoader().parse(buffer);
  geo.scale(MM, MM, MM);
  geo.computeVertexNormals();
  return geo;
}

export function createPcb6Scene(parentGroup, stackupMeta = [], enclosureMeta = null) {
  const group = new THREE.Group();
  parentGroup.add(group);

  const grid = new THREE.GridHelper(0.24, 24, 0x334155, 0x1b2434);
  grid.rotation.x = Math.PI / 2;
  grid.position.z = -0.028;
  group.add(grid);

  const pickables = [];
  const layerMeshes = [];
  const partEntries = [];

  const defaultLayers = [
    { id: "layer_L1", label: "L1 parts side (faces the lid)", z: 0.78, explodeZ: 18, role: "Parts, the high-current straps, signals, power and GND pours." },
    { id: "layer_L2", label: "L2 solid GND plane", z: 0.48, explodeZ: 11, role: "Every GND pad has its own via into it; nothing routed on it; no copper under the ESP32 antenna." },
    { id: "layer_L3", label: "L3 signals + GND pour", z: 0.16, explodeZ: 4, role: "Autorouted signals and small power branches. Inner copper is 0.5 oz: the high current stays on L1/L6." },
    { id: "layer_L4", label: "L4 signals + GND pour", z: -0.16, explodeZ: -4, role: "Autorouted signals; GND pour in the gaps." },
    { id: "layer_L5", label: "L5 signals + GND pour", z: -0.48, explodeZ: -11, role: "Autorouted signals; GND pour in the gaps." },
    { id: "layer_L6", label: "L6 underside (faces the Pi)", z: -0.78, explodeZ: -18, role: "Signals, power pours under the bucks and the 12 V chain stitched to L1; pins ≤ 2.5 mm, 3 mm air gap to the Pi." },
  ];

  defaultLayers.forEach((ld, idx) => {
    const mat = new THREE.MeshStandardMaterial({
      map: makeLayerTexture(idx),
      roughness: idx === 0 || idx === 5 ? 0.42 : 0.3,
      metalness: idx === 0 || idx === 5 ? 0.18 : 0.55,
    });
    loadLayerImage(idx, mat);
    const thickness = idx === 0 || idx === 5 ? 0.28 : 0.16;
    const geo = new THREE.BoxGeometry(100 * MM, 100 * MM, thickness * MM);
    if (idx === 5) {
      // The textures are drawn from the parts side, so the layers line up in the exploded stack. Seen from below, the
      // real underside is the mirror image of that drawing, so u is flipped on the box's bottom face (vertices 20-23):
      // the Bottom (L6) view then matches KiCad's bottom view, its silkscreen reading the right way round.
      const uv = geo.attributes.uv;
      for (let i = 20; i < 24; i++) uv.setX(i, 1 - uv.getX(i));
      uv.needsUpdate = true;
    }
    const mesh = new THREE.Mesh(geo, mat);
    mesh.position.set(0, 0, ld.z * MM);
    mesh.userData.pickId = ld.id;
    group.add(mesh);
    layerMeshes.push({ id: ld.id, mesh, mat, baseZ: ld.z, explodeZ: ld.explodeZ, subsystem: "pcb", label: ld.label });
    pickables.push({
      id: ld.id,
      mesh,
      title: ld.label,
      category: "6-layer stackup",
      source: "JLCPCB 6-layer (ENIG)",
      location: `Layer ${idx + 1} of 6 · 100.0 × 100.0 × 1.6 mm FR-4`,
      mount: "JLCPCB 6+ layer FR-4 is ENIG only; inner copper 0.5 oz; epoxy-filled, capped vias (the default). Thermal reliefs on every through-hole pad (hand soldering).",
      wiring: (stackupMeta[idx] && stackupMeta[idx].role) || ld.role,
    });
  });

  function addPart(cfg) {
    const g = new THREE.Group();
    const [x, y] = cfg.zone ? centre(...cfg.zone) : [cfg.x, cfg.y];
    const w = cfg.zone ? cfg.zone[2] : cfg.w;
    const d = cfg.zone ? cfg.zone[3] : cfg.d;
    const baseZ = 0.92 + cfg.h / 2;
    g.position.set(x * MM, y * MM, baseZ * MM);
    const mainMesh = makeBox(w, d, cfg.h, cfg.color, cfg.metalness ?? 0.3, cfg.roughness ?? 0.4);
    if (cfg.opacity) {
      mainMesh.material.transparent = true;
      mainMesh.material.opacity = cfg.opacity;
      mainMesh.material.depthWrite = false;
    }
    mainMesh.userData.pickId = cfg.id;
    g.add(mainMesh);
    if (cfg.decorate) cfg.decorate(g, cfg.id, w, d);
    group.add(g);
    partEntries.push({ id: cfg.id, group: g, mesh: mainMesh, baseZ, explodeZ: 34, subsystem: cfg.subsystem, origColor: cfg.color });
    pickables.push({
      id: cfg.id,
      mesh: mainMesh,
      title: cfg.title,
      category: cfg.category,
      source: cfg.source,
      location: `Template zone (${cfg.zone ? cfg.zone.slice(0, 2).join(", ") : `${x}, ${y}`}) · ${w}×${d}×${cfg.h} mm`,
      mount: cfg.mount,
      wiring: cfg.wiring,
    });
  }

  addPart({
    id: "p6_esp32", zone: ZONES.esp32, h: 15.5, color: 0x1e293b, subsystem: "rf_mcu", opacity: 0.85,
    title: "A1: ESP32 DevKit (30-pin) on two 1×15 sockets",
    category: "Real-time µC", source: "INVENTORY (2 in the lab)",
    mount: "Female headers, ~15.5 mm with the module (16 mm budget). The footprint carries both row spacings (0.9\" and 1.0\", marked): solder the socket that matches your DevKit. Antenna end toward the top edge (silkscreen ESP32 ANTENNA END, no copper under it on any layer); USB end toward J1, reachable for a 90° lead with the lid off.",
    wiring: "Pins from 02-firmware/v2/include/pins_v2.h, checked against the board's netlist by check_pinmap.py: CC1101 5/18/19/23/34/35 and I2C 21/22, buzzer 13, button 4 as on v1; blinkers 36/39 (polled); ACC 32; GPS 33/27; Pi UART 16/17; PI_INHIBIT 26; rail-up sense 15; LEDs 25/14; GPIO12 and 2 unconnected. Every signal passes a series resistor beside its pin (a cut point for rework).",
    decorate: (g, pid) => {
      const shield = makeBox(18, 16, 3.2, 0xcbd5e1, 0.85, 0.22);
      shield.position.set(0, 11 * MM, 6.5 * MM);
      shield.userData.pickId = pid;
      const usb = makeBox(8, 6, 3.2, 0x94a3b8, 0.9, 0.25);
      usb.position.set(0, -23 * MM, 6.0 * MM);
      usb.userData.pickId = pid;
      g.add(shield, usb);
    },
  });

  addPart({
    id: "p6_cc1101", zone: ZONES.cc1101, h: 15.5, color: 0x1d4ed8, subsystem: "rf_mcu", opacity: 0.85,
    title: "A2: CC1101 315 MHz module on a 2 × 4 socket",
    category: "TPMS radio", source: "BUY the 315 MHz-tuned module (~$3)",
    mount: "Stands 11 mm over the board with parts underneath (the 3.3 V LDO and its capacitors). SMA end toward the top (silkscreen CC1101: SMA END): the 2 × 4 is symmetric, so turned round it would swap power pins. J10 (not fitted) is a breakout for a module with another pinout.",
    wiring: "VSPI 18/19/23 through 1 kΩ, CS 5 through 1 kΩ, GDO0 34, GDO2 35: the v1 driver and decoder are reused. 3V3_RF behind a ferrite. Its SMA → 10 cm RG316 → bulkhead in the enclosure wall → 30 cm RG316 → whip away from the Pi.",
    decorate: (g, pid, w, d) => {
      const sma = new THREE.Mesh(
        new THREE.CylinderGeometry(3.2 * MM, 3.2 * MM, 9 * MM, 16),
        new THREE.MeshStandardMaterial({ color: 0xeab308, metalness: 0.9, roughness: 0.2 })
      );
      sma.position.set(0, (d / 2 + 4.5) * MM, 2.5 * MM);
      sma.userData.pickId = pid;
      g.add(sma);
    },
  });

  addPart({
    id: "p6_buck_pi", zone: ZONES.buck_pi, h: 4.5, color: 0x0f766e, subsystem: "power_io",
    title: "U201: 5V_PI buck — TPS54560B, 5.17 V / 5 A, 441 kHz",
    category: "Power (P1, ACC only)", source: "JLCPCB assembly",
    mount: "6.8 µH MWSA1004S, SS56C catch diode, 2 × 10 µF in, 4 × 47 µF out, all on 2 mm straps; PowerPAD with 6 filled vias into the planes. 10 mΩ shunt + INA226 (0x41) on Kelvin taps; SMBJ6.0CA clamp.",
    wiring: "Starts at 8.0 V, 1.2–1.4 s after ACC (EN 1 MΩ / 150 kΩ + 10 µF), so the ESP32 boots first; Q201 (IO26, PI_INHIBIT) can only hold it off; a 22 k / 33 k rail-up divider → IO15. Remove R201/R202 to isolate it and feed J5 from a module via J11. RT → 43 kΩ moves it above the AM band if B5 hears it.",
  });

  addPart({
    id: "p6_buck_esp", zone: ZONES.buck_esp, h: 4.5, color: 0xf59e0b, subsystem: "power_io",
    title: "U301: 5V_ESP buck — TPS54560B, 5.17 V / 1 A, 485 kHz; XC6206 → 3V3",
    category: "Power", source: "JLCPCB assembly",
    mount: "Same power stage as the Pi buck, in the fan zone (≤ 6 mm tall). Its 12 V feed is a strap from the bus around the Pi buck.",
    wiring: "5V_ESP → the DevKit's VIN through an SS14 (a USB-powered DevKit can't back-feed the board), the GPS (PTC), the door LEDs and the lid fan; XC6206 → 3V3 for the I2C parts; ferrite → 3V3_RF for the CC1101. Remove R301 to isolate it, J12 takes a module's 5 V.",
  });

  addPart({
    id: "p6_protect", zone: ZONES.protect, h: 7.7, color: 0xdc2626, subsystem: "power_io",
    title: "12 V in: 4 A fuse, SMCJ24CA, SUD50P06-15 (−60 V), π filter, 10 mΩ shunt + INA226 (0x40)",
    category: "12 V protection", source: "JLCPCB assembly",
    mount: "Under the DevKit's USB end, all on 2 mm straps; the 47 µF / 50 V electrolytic damps the π filter.",
    wiring: "SMCJ24CA: 26.7 V minimum breakdown (survives a 24 V jump start), 38.9 V clamp; every part after it takes ≥ 40 V. The P-MOSFET blocks reverse battery (gate at −5 V, −16 V at the clamp). If it ever dies open, bridge its tab to pin 3.",
  });

  addPart({
    id: "p6_j1", zone: ZONES.j1, h: 10, color: 0x7f1d1d, subsystem: "power_io",
    title: "J1: 12 V in — 4-pole 5.08 mm screw terminal",
    category: "Connectors", source: "INVENTORY (2 blue 2-pole screw blocks side by side, hand-soldered)",
    mount: "Wire entries toward the bottom edge, under the lid's cable exit.",
    wiring: "+12 V (ACC), GND, AUX sense in, AUX return; 18 AWG from one Add-A-Circuit (5 A) on a metered ACC fuse. No battery feed: zero draw when parked.",
  });

  addPart({
    id: "p6_j5", zone: ZONES.j5, h: 10, color: 0xea580c, subsystem: "power_io",
    title: "J5: 5V_PI out — 6-pole 5.08 mm screw terminal",
    category: "Connectors", source: "INVENTORY (3 blue 2-pole screw blocks side by side, hand-soldered)",
    mount: "Wire entries toward the top edge (a clear strip in front of them for the wire bend).",
    wiring: "1–2 → 90° USB-C pigtail to the Pi (470 µF at the Pi end); 3–4 → the TS-7's 5 V on its split micro-USB lead (its touch data goes to a Pi USB port); 5–6 spare. Fed by 2 mm straps from the shunt.",
  });

  addPart({
    id: "p6_jst", zone: ZONES.jst, h: 4.3, color: 0x10b981, subsystem: "signals",
    title: "J4, J2, J3, J6, J7: JST-GH — piezo (\"BUZ\"), doors L / R, Pi link, GPS",
    category: "Connectors", source: "JLCPCB assembly (SMD); the leads: the lab's elechawk GH-to-Dupont pigtails",
    mount: "Keyed, latching; mouths on the bottom edge next to the cable exit.",
    wiring: "BUZ (4-pin): the 12 V piezo inside the dash unit on pins 3 (+) and 4 (−); the button pins 1–2 (IO4, GND) stay unused (the touch screen mutes). DOOR L / R (4-pin): blinker sense pair + amber LED. PI (6-pin): GND, TXD, RXD, GPIO18, SDA6, SCL6 → the Pi's header pins 6, 8, 10, 12, 15, 16 through the 40-pin ribbon; UART through 1 kΩ / 4.7 kΩ, I2C through Q901 / Q902, which only the Pi's GPIO18 switches on. GPS (6-pin Pixhawk): 5 V, TX, RX, SCL, SDA, GND; swap TX/RX with R907/R908.",
  });

  addPart({
    id: "p6_io", zone: ZONES.io, h: 3, color: 0xfacc15, subsystem: "signals",
    title: "ICPL-356-50C blinker / AUX optos + door LED, piezo and fan drivers",
    category: "Blinker sensing and alerts (tested in firmware)", source: "JLCPCB assembly",
    mount: "Per input: 2 × 1.2 kΩ + indicator LED + opto, 1N4148W reverse diode, separate lamp return. Low-side AO3400A for the LEDs and the fan, 2N7002 (60 V) for the piezo behind a 0.5 A PTC.",
    wiring: "Opto outputs active-low with 10 k pull-ups, polled at 1 kHz (ESP32 errata 3.11). LEDs: steady = vehicle in the blind spot, flashing = you are signalling towards it. The fan runs by default; the TCA9534 (0x20) can stop it. TMP75 (0x48) drives the hot-start hold.",
  });

  // Keep-outs from the enclosure generator
  const keepMat = (color) => new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.16, depthWrite: false });
  const addKeep = (id, zone, h, color, title, wiring) => {
    const [x, y] = centre(...zone);
    const m = new THREE.Mesh(new THREE.BoxGeometry(zone[2] * MM, zone[3] * MM, h * MM), keepMat(color));
    m.position.set(x * MM, y * MM, (0.92 + h / 2) * MM);
    m.userData.pickId = id;
    m.userData.lowPriority = true;  // a volume around parts: a click on a part inside it selects the part
    group.add(m);
    pickables.push({ id, mesh: m, title, category: "Enclosure keep-out", source: "make_enclosure.py",
      location: `Template zone (${zone[0]}, ${zone[1]}) · ${zone[2]}×${zone[3]} mm`, mount: "Rule for the KiCad layout (gate G7).", wiring });
  };
  addKeep("keep_fan", ZONES.fan, 6, 0xef4444, "Fan zone: parts ≤ 6 mm", "The 30 mm lid fan sits 7.5 mm above the board here, blowing out through the lid.");
  addKeep("keep_sma", ZONES.sma, 16, 0xef4444, "SMA bulkhead strip: no parts", "The antenna bulkhead and its nut reach 9 mm into the box from the wall on this side.");

  // ---------------- printed enclosure (STLs from 01-hardware/enclosure) ----------------
  const mountStackGroup = new THREE.Group();
  const stackTiers = [];
  const ENC = {
    bezel: { color: 0x1f2937, opacity: 1, explode: -40, title: "Bezel (print face down)", mount: "The display hangs by its four ears on four bosses (M3 × 6 from behind). The lip covers the outer 2 mm of the glass, 0.3 mm clear of it. Intake slots (2.5 mm) beside the screen; 2 mm top / bottom walls keep it as tall as the opening. 6 × M3 × 10 from the back of the plate." },
    housing: { color: 0x475569, opacity: 0.55, explode: 0, title: "Housing: plate + rear box (print plate down)", mount: "The plate sits 0.4 mm behind the display's back parts, with three intake windows and a cable slot for the display's leads. The box holds the Pi on 4 posts (58 × 49) and this PCB on 4 more (92 × 92). USB/Ethernet window with the display-lead slot above it, SMA bulkhead, AMPS 30 × 38 M4 nuts, 2 mm bumps so air leaves round the plate." },
    lid: { color: 0x64748b, opacity: 0.5, explode: 40, title: "Lid with the 30 mm fan (print outside down)", mount: "The inventory fan blows out through a 2.5 mm bar grille; cable exit with a split grommet; locating rim; 4 × M3 into the ears." },
    display: { color: 0x0b1a3a, opacity: 1, explode: -28, title: "SunFounder TS-7 7\" display (dummy)", mount: "1024 × 600 IPS, readable from any angle: mounted the normal way up. HDMI and micro-USB sockets on the back at its right edge. Board ~165.3 × 124.4 mm over its ears: measure it first (SunFounder lists 121)." },
    cables: { color: 0xf97316, opacity: 1, explode: -28, title: "Display plugs and leads (dummy)", mount: "Straight HDMI-A FPC adapter (flat cable folded up over it) and a 90° micro-USB plug (lead upward), rising to the plate's cable slot; then into the pocket and into the box above the USB window." },
    pi: { color: 0x15803d, opacity: 1, explode: -14, title: "Raspberry Pi 4 + its plugs (dummy)", mount: "On 4 posts behind the plate, ports to the driver's right (window in the box wall), HDMI / USB-C edge on top: micro-HDMI adapter in HDMI0, 90° USB-C pigtail. GPIO plugs 90° / low profile." },
    fan: { color: 0x111827, opacity: 1, explode: 40, title: "30 mm fan (dummy)", mount: "Under the lid, over the PCB's fan zone." },
    pcb_parts: { color: 0xf59e0b, opacity: 0.12, explode: 0, title: "PCB part-height budget (16 mm, 6 mm under the fan)", mount: "From the enclosure generator; the KiCad layout must stay inside it." },
  };
  const encInfo = enclosureMeta
    ? `${enclosureMeta.overall_mm.width} × ${enclosureMeta.overall_mm.height} × ${enclosureMeta.overall_mm.depth} mm overall · ${enclosureMeta.checks.passed}/${enclosureMeta.checks.total} fit checks pass`
    : "";
  const loading = (enclosureMeta?.assembly || []).filter((a) => ENC[a.name]).map(async (a) => {
    try {
      const res = await fetch(a.file, { cache: "no-store" });
      if (!res.ok) throw new Error(`${res.status}`);
      const geo = stlGeometry(await res.arrayBuffer());
      const spec = ENC[a.name];
      const mat = new THREE.MeshStandardMaterial({
        color: spec.color, roughness: 0.75, metalness: 0.05, transparent: spec.opacity < 1,
        opacity: spec.opacity, depthWrite: spec.opacity >= 0.5, side: THREE.DoubleSide,
      });
      const mesh = new THREE.Mesh(geo, mat);
      mesh.userData.pickId = `enc_${a.name}`;
      mountStackGroup.add(mesh);
      stackTiers.push({ obj: mesh, baseZ: 0, explodeZ: spec.explode });
      pickables.push({ id: `enc_${a.name}`, mesh, title: spec.title, category: "Printed enclosure", source: "01-hardware/enclosure",
        location: encInfo, mount: spec.mount, wiring: a.label });
    } catch (err) {
      console.warn(`enclosure part ${a.name} not loaded (${err.message}); run make_enclosure.py`);
    }
  });
  Promise.all(loading).then(() => setExplode(currentExplode));

  const SUB_COLORS = { pcb: 0x059669, rf_mcu: 0x2563eb, power_io: 0xf59e0b, signals: 0x38bdf8, ui: 0xe879f9 };
  let currentExplode = 0;

  function setExplode(amount01) {
    currentExplode = amount01;
    for (const l of layerMeshes) l.mesh.position.z = (l.baseZ + l.explodeZ * amount01) * MM;
    for (const p of partEntries) p.group.position.z = (p.baseZ + p.explodeZ * amount01) * MM;
    for (const t of stackTiers) t.obj.position.z = (t.baseZ + t.explodeZ * amount01) * MM;
  }

  function setMountStackVisible(on) {
    // detached when hidden, so hidden parts can't be picked
    if (on && !mountStackGroup.parent) group.add(mountStackGroup);
    if (!on && mountStackGroup.parent) group.remove(mountStackGroup);
    grid.position.z = on ? -0.075 : -0.028;
  }

  function setLayerVisible(layerIdx, visible) {
    if (layerMeshes[layerIdx]) layerMeshes[layerIdx].mesh.visible = visible;
  }

  function setColorMode(mode) {
    for (const p of partEntries) {
      const hex = mode === "subsystem" ? (SUB_COLORS[p.subsystem] ?? p.origColor) : p.origColor;
      p.mesh.material.color.setHex(hex);
    }
  }

  function setXray(on) {
    for (const l of layerMeshes) {
      l.mat.transparent = on;
      l.mat.opacity = on ? 0.42 : 1.0;
      l.mat.needsUpdate = true;
    }
  }

  return { group, pickables, layerMeshes, setExplode, setMountStackVisible, setLayerVisible, setColorMode, setXray };
}
