import * as THREE from "three";
import { STLLoader } from "three/addons/STLLoader.js";

/**
 * v2 carrier PCB (100 x 100 x 1.6 mm, 6 layers) and the 3-D printed enclosure around it.
 *
 * Units: metres. Z up = the PCB's parts side, which faces the enclosure lid. Origin at the PCB centre.
 * Part zones follow the fit template (01-hardware/docs/v2_fit_template_1to1.pdf, page 2): template (x, y) in mm
 * from the top-left, parts side up -> viewer (x - 50, 50 - y). The keep-outs (fan zone, SMA strip, pin-free
 * corners) come from 01-hardware/enclosure/make_enclosure.py, which also writes the assembly STLs loaded here.
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

const ZONES = {
  cc1101: [62, 2.5, 30, 18],
  esp32: [0, 12, 28, 52],
  pololu: [64, 62, 25.4, 25.4],
  tsr: [64, 42, 20, 16],
  protect: [36, 70, 24, 14],
  j1: [34, 88, 12, 10],
  j5: [50, 88, 12, 10],
  jst: [11, 88, 21, 10],
  enrc: [64, 88, 14, 10],
  fan: [29, 30, 32, 32],
  sma: [86, 28.5, 14, 12],
  antenna: [0, 50, 28, 14],
};

function rectPx(ctx, [x, y, w, h], stroke = true) {
  if (stroke) ctx.strokeRect(x * PX, y * PX, w * PX, h * PX);
  else ctx.fillRect(x * PX, y * PX, w * PX, h * PX);
}

function makeLayerTexture(layerIndex) {
  const c = document.createElement("canvas");
  c.width = 512;
  c.height = 512;
  const ctx = c.getContext("2d");

  if (layerIndex === 0) {
    // L1: parts side, black soldermask, planning zones and the enclosure keep-outs
    ctx.fillStyle = "#11161f";
    ctx.fillRect(0, 0, 512, 512);
    ctx.strokeStyle = "rgba(226,232,240,0.5)";
    ctx.lineWidth = 2;
    ctx.setLineDash([8, 6]);
    for (const k of ["cc1101", "esp32", "pololu", "tsr", "protect", "j1", "j5", "jst", "enrc"]) rectPx(ctx, ZONES[k]);
    ctx.setLineDash([5, 4]);
    ctx.strokeStyle = "#f87171";
    rectPx(ctx, ZONES.fan);
    rectPx(ctx, ZONES.sma);
    for (const [x, y] of [[0, 0], [90, 0], [0, 90], [90, 90]]) rectPx(ctx, [x, y, 10, 10]);
    ctx.setLineDash([]);
    ctx.fillStyle = "#e2e8f0";
    ctx.font = "bold 13px monospace";
    ctx.fillText("CC1101 315 MHz → SMA", 62 * PX + 4, 2.5 * PX + 16);
    ctx.fillText("ESP32 DevKit", 4, 12 * PX + 18);
    ctx.fillText("Pololu 5V_PI", 64 * PX + 4, 62 * PX + 16);
    ctx.fillText("TSR + 3V3", 64 * PX + 4, 42 * PX + 16);
    ctx.fillText("12 V protection", 36 * PX + 4, 70 * PX + 16);
    ctx.font = "bold 11px monospace";
    ctx.fillText("J1 12V", 34 * PX + 2, 88 * PX + 14);
    ctx.fillText("J5 5V", 50 * PX + 2, 88 * PX + 14);
    ctx.fillText("JST-GH", 11 * PX + 4, 88 * PX + 14);
    ctx.fillStyle = "#fca5a5";
    ctx.font = "bold 12px monospace";
    ctx.fillText("FAN ZONE ≤ 6 mm", 29 * PX + 6, 30 * PX + 18);
    ctx.fillText("SMA", 86 * PX + 10, 28.5 * PX + 36);
    ctx.fillStyle = "#facc15";
    ctx.font = "bold 12px monospace";
    ctx.fillText("v2 carrier · 6 layers · 100×100", 150, 505);
    ctx.strokeStyle = "#eab308";
    ctx.lineWidth = 7;
    for (const [x, y] of [[4, 4], [96, 4], [4, 96], [96, 96]]) {
      ctx.beginPath();
      ctx.arc(x * PX, y * PX, 11, 0, Math.PI * 2);
      ctx.stroke();
    }
  } else if (layerIndex === 1 || layerIndex === 3) {
    // L2 / L4: solid ground planes, no copper under the ESP32's PCB antenna
    ctx.fillStyle = layerIndex === 1 ? "#065f46" : "#047857";
    ctx.fillRect(0, 0, 512, 512);
    ctx.strokeStyle = "rgba(167,243,208,0.22)";
    ctx.lineWidth = 1;
    for (let g = 32; g < 512; g += 32) {
      ctx.beginPath(); ctx.moveTo(g, 0); ctx.lineTo(g, 512); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(0, g); ctx.lineTo(512, g); ctx.stroke();
    }
    ctx.fillStyle = "#0f172a";
    rectPx(ctx, ZONES.antenna, false);
    ctx.fillStyle = "#94a3b8";
    ctx.font = "bold 11px monospace";
    ctx.fillText("antenna", 6, 50 * PX + 30);
    ctx.fillStyle = "#ecfdf5";
    ctx.font = "bold 18px monospace";
    ctx.fillText(layerIndex === 1 ? "L2: SOLID GND (reference for L1)" : "L4: SOLID GND (shields L5)", 70, 260);
  } else if (layerIndex === 2) {
    // L3: low-current power distribution (the 5 A path stays on the outer layers)
    ctx.fillStyle = "#1e1b2e";
    ctx.fillRect(0, 0, 512, 512);
    ctx.fillStyle = "#b91c1c";
    ctx.fillRect(170, 330, 330, 170);
    ctx.fillStyle = "#d97706";
    ctx.fillRect(300, 190, 200, 130);
    ctx.fillStyle = "#2563eb";
    ctx.fillRect(10, 10, 480, 170);
    ctx.fillStyle = "#fff";
    ctx.font = "bold 18px monospace";
    ctx.fillText("3V3 (CC1101, DevKit)", 120, 100);
    ctx.fillText("5V_ESP", 350, 260);
    ctx.fillText("12V_PROT", 280, 420);
    ctx.font = "bold 13px monospace";
    ctx.fillText("L3: low current only · 0.5 oz inner copper", 40, 500);
  } else if (layerIndex === 4) {
    // L5: slow signals
    ctx.fillStyle = "#0f172a";
    ctx.fillRect(0, 0, 512, 512);
    ctx.strokeStyle = "#38bdf8";
    ctx.lineWidth = 4;
    for (let i = 0; i < 6; i++) {
      ctx.beginPath();
      ctx.moveTo(60 + i * 18, 460);
      ctx.lineTo(60 + i * 18, 200 + i * 12);
      ctx.lineTo(150, 200 + i * 12);
      ctx.stroke();
    }
    ctx.strokeStyle = "#facc15";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(150, 120); ctx.lineTo(330, 120); ctx.lineTo(330, 60);
    ctx.stroke();
    ctx.fillStyle = "#93c5fd";
    ctx.font = "bold 16px monospace";
    ctx.fillText("L5: BLINKER · UARTS · I2C · SPI", 70, 492);
  } else {
    // L6: underside, faces the Pi with a 3 mm air gap
    ctx.fillStyle = "#11161f";
    ctx.fillRect(0, 0, 512, 512);
    ctx.fillStyle = "rgba(217,119,6,0.55)";
    ctx.fillRect(170, 300, 300, 200);
    ctx.fillStyle = "#eab308";
    for (let x = 190; x <= 450; x += 26) {
      for (let y = 320; y <= 480; y += 26) {
        ctx.beginPath();
        ctx.arc(x, y, 3.5, 0, Math.PI * 2);
        ctx.fill();
      }
    }
    ctx.fillStyle = "#cbd5e1";
    ctx.font = "bold 14px monospace";
    ctx.fillText("L6: 5V_PI / 12 V pour, stitched to L1", 60, 470 - 200);
    ctx.fillText("pins ≤ 2.5 mm (faces the Pi)", 60, 490 - 200);
  }

  const tex = new THREE.CanvasTexture(c);
  tex.anisotropy = 4;
  return tex;
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
    { id: "layer_L1", label: "L1 parts side (faces the lid)", z: 0.78, explodeZ: 18, role: "Parts and routing; 5 V / 12 V on wide outer pours." },
    { id: "layer_L2", label: "L2 solid ground", z: 0.48, explodeZ: 11, role: "Reference plane for L1; no copper under the ESP32 antenna." },
    { id: "layer_L3", label: "L3 power distribution (low current)", z: 0.16, explodeZ: 4, role: "12V_PROT, 5V_ESP, 3V3. Inner copper is 0.5 oz: the 5 A path stays outside." },
    { id: "layer_L4", label: "L4 solid ground", z: -0.16, explodeZ: -4, role: "Shields the L5 signals from L3." },
    { id: "layer_L5", label: "L5 slow signals", z: -0.48, explodeZ: -11, role: "Blinker optos, Pi and GPS UARTs, I2C, SPI to the CC1101." },
    { id: "layer_L6", label: "L6 underside (faces the Pi)", z: -0.78, explodeZ: -18, role: "5V_PI / 12 V pour stitched to L1; pins ≤ 2.5 mm, 3 mm air gap to the Pi." },
  ];

  defaultLayers.forEach((ld, idx) => {
    const mat = new THREE.MeshStandardMaterial({
      map: makeLayerTexture(idx),
      roughness: idx === 0 || idx === 5 ? 0.42 : 0.3,
      metalness: idx === 0 || idx === 5 ? 0.18 : 0.55,
    });
    const thickness = idx === 0 || idx === 5 ? 0.28 : 0.16;
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(100 * MM, 100 * MM, thickness * MM), mat);
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
      mount: "JLCPCB 6+ layer FR-4 is ENIG only; inner copper 0.5 oz by default. Thermal reliefs on every through-hole pad (hand soldering).",
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
    id: "p6_esp32", zone: ZONES.esp32, h: 13, color: 0x1e293b, subsystem: "rf_mcu",
    title: "A1: ESP32-WROOM-32 DevKit (30-pin, on sockets)",
    category: "Real-time µC", source: "INVENTORY (2 in the lab)",
    mount: "Machined sockets (~13 mm total height, inside the 16 mm budget). USB at the top edge for flashing; no copper under its PCB antenna (bottom end).",
    wiring: "Pins from 02-firmware/v2/include/pins_v2.h (audited by check_pinmap.py): CC1101 5/18/19/23/34/35 and I2C 21/22, buzzer 13, button 4 as on v1; blinkers 36/39 (polled); ACC 32; GPS 33/27; Pi UART 16/17; PI_INHIBIT 26; PGOOD 15; LEDs 25/14; status LED 2; GPIO12 unconnected.",
    decorate: (g, pid) => {
      const shield = makeBox(18, 16, 3.2, 0xcbd5e1, 0.85, 0.22);
      shield.position.set(0, -14 * MM, 6.5 * MM);
      shield.userData.pickId = pid;
      const usb = makeBox(8, 6, 3.2, 0x94a3b8, 0.9, 0.25);
      usb.position.set(0, 24 * MM, 6.0 * MM);
      usb.userData.pickId = pid;
      g.add(shield, usb);
    },
  });

  addPart({
    id: "p6_cc1101", zone: ZONES.cc1101, h: 12, color: 0x1d4ed8, subsystem: "rf_mcu",
    title: "U1: CC1101 315 MHz module (same 2 × 4 pinout as v1)",
    category: "TPMS radio", source: "BUY the 315 MHz-tuned module (~$3)",
    mount: "Module on a 2 × 4 socket over the L2 ground plane, its own SMA pointing at the right edge. No RF trace on this board.",
    wiring: "VSPI 18/19/23, CS 5, GDO0 34, GDO2 35: the v1 driver and the EG53MA4 decoder are reused unchanged. Its SMA → 10 cm RG316 → bulkhead in the enclosure wall → 30 cm RG316 → whip away from the Pi.",
    decorate: (g, pid, w) => {
      const sma = new THREE.Mesh(
        new THREE.CylinderGeometry(3.2 * MM, 3.2 * MM, 9 * MM, 16),
        new THREE.MeshStandardMaterial({ color: 0xeab308, metalness: 0.9, roughness: 0.2 })
      );
      sma.rotation.z = Math.PI / 2;
      sma.position.set((w / 2 + 3) * MM, 0, 1 * MM);
      sma.userData.pickId = pid;
      g.add(sma);
    },
  });

  addPart({
    id: "p6_pololu", zone: ZONES.pololu, h: 15, color: 0x0f766e, subsystem: "power_io",
    title: "U3: Pololu D36V50F5 → 5V_PI (Pi + display + cameras + fan)",
    category: "Power (P1, ACC only)", source: "BUY (~$20)",
    mount: "On 0.1\" sockets; power pins on both rows (3 A per pin). 5.5–50 V in, ~5.5 A out, reverse-protected to 40 V.",
    wiring: "EN has an internal 100 k pull-up: ON by default with ACC. 22 kΩ + 100 µF to ground give a ~1.3–1.6 s start delay; a 2N7002 (IO26) can only hold it off. PG → IO15. Budget ~2.2 A typical, ~3.7 A peak.",
  });

  addPart({
    id: "p6_tsr", zone: ZONES.tsr, h: 11, color: 0xf59e0b, subsystem: "power_io",
    title: "U2 / U4: TRACO TSR 1-2450 → 5V_ESP, AMS1117-3.3 + 22 µF tantalum → 3V3",
    category: "Power", source: "BUY (~$8)",
    mount: "TSR vertical SIP (~10 mm), next to the DevKit's VIN.",
    wiring: "5V_ESP feeds the DevKit, the GPS and the LEDs; 3V3 feeds the CC1101 and the I2C sensors. The v1 C5 tantalum stability fix is kept.",
  });

  addPart({
    id: "p6_protect", zone: ZONES.protect, h: 6, color: 0xdc2626, subsystem: "power_io",
    title: "F1 / D1 / Q1 / FL1: 4 A fuse, SMCJ22CA, AOD4185 reverse protection, π filter",
    category: "12 V protection", source: "BUY (~$8)",
    mount: "Low parts (≤ 6 mm); the 47 µF / 50 V bulk capacitor sits beside the Pololu.",
    wiring: "SMCJ22CA: 24.4 V minimum breakdown (survives a 24 V jump start), 35.5 V clamp. P-MOSFET instead of a hot Schottky. Ferrite + 2.2 µH + 2 × 10 µF against AM-band noise (bench test B5).",
  });

  addPart({
    id: "p6_j1", zone: ZONES.j1, h: 10, color: 0x7f1d1d, subsystem: "power_io",
    title: "J1: 12 V ACC in (Micro-Fit 3.0, right angle)",
    category: "Connectors", source: "BUY",
    mount: "Right-angle at the bottom edge, under the lid's cable exit; mated height < 16 mm.",
    wiring: "2 × ACC + 2 × GND, 18 AWG, from one Add-A-Circuit (5 A) on a metered ACC fuse. No battery feed: zero draw when parked.",
  });

  addPart({
    id: "p6_j5", zone: ZONES.j5, h: 10, color: 0xea580c, subsystem: "power_io",
    title: "J5: 5V_PI out (Micro-Fit 3.0) + fan header",
    category: "Connectors", source: "BUY",
    mount: "Right-angle at the bottom edge.",
    wiring: "Pair 1 → 90° USB-C pigtail to the Pi (470 µF at the Pi end); pair 2 → display adapter 5 V / GND; a 2-pin header powers the lid fan.",
  });

  addPart({
    id: "p6_jst", zone: ZONES.jst, h: 6, color: 0x10b981, subsystem: "signals",
    title: "J6–J11: JST-GH harness (blinkers, LEDs, alert pod, GPS, Pi UART, I2C)",
    category: "Connectors", source: "BUY / INVENTORY (JST-GH kit)",
    mount: "Keyed, latching; right-angle at the bottom edge next to the cable exit.",
    wiring: "Blinker L/R (2 × 2-pin), LED L/R (2 × 2-pin), alert pod (4-pin: BTN IO4, GND, BUZ+, BUZ−), GPS (4-pin, UART1 33/27, 5 V), Pi UART (3-pin, 16/17 with 1 k / 4.7 k), I2C (4-pin, 21/22).",
  });

  addPart({
    id: "p6_enrc", zone: ZONES.enrc, h: 9, color: 0x6366f1, subsystem: "power_io",
    title: "Pi start delay and inhibit: 22 kΩ + 100 µF, Q2 2N7002 (IO26)",
    category: "Power sequencing (tested in firmware)", source: "BUY",
    mount: "Next to the Pololu; the 100 µF can is ~9 mm tall, outside the fan zone.",
    wiring: "The Pi rail starts by itself with ACC; the ESP32 holds it off while cranking (PiPowerSequencer: engine ≥ 13.0 V for 1 s, or 15 s in ACC; hot hold ≥ 60 °C). Bench tests B1–B3.",
  });

  // Low parts in the fan zone
  const [fx, fy] = centre(...ZONES.fan);
  addPart({
    id: "p6_opto", x: fx - 8, y: fy + 7, w: 14, d: 10, h: 4, color: 0xfacc15, subsystem: "signals",
    title: "U5 / U6: PC817 blinker inputs (IO36 / IO39)",
    category: "Blinker sensing (tested in firmware)", source: "BUY",
    mount: "In the fan zone (parts ≤ 6 mm). 2 × 1.1 kΩ 1206 in series + 1N4148 reverse diode per input (~6 mA).",
    wiring: "Active-low outputs with 10 k pull-ups, polled at 1 kHz (ESP32 errata 3.11). BlinkerDetector: bridges PWM gaps ≤ 25 ms, 50 ms debounce, 900 ms hold, hazard window 150 ms.",
  });
  addPart({
    id: "p6_drivers", x: fx + 8, y: fy + 7, w: 14, d: 10, h: 3, color: 0xe879f9, subsystem: "ui",
    title: "Q3–Q5: amber LED and piezo drivers (IO25 / IO14 / IO13)",
    category: "Alerts (tested in firmware)", source: "BUY",
    mount: "Low-side MOSFETs; 33 Ω + SMAJ18A on the piezo's 12 V feed.",
    wiring: "LEDs: steady = vehicle in the blind spot, flashing = you are signalling towards it, PWM level from the Pi. Piezo in the alert pod. AlertArbiter: speed gate 12 / 8 mph, hazards silent, mute = this turn + TPMS acknowledge, fault pattern when the Pi goes quiet.",
  });
  addPart({
    id: "p6_acc", x: fx, y: fy - 9, w: 16, d: 8, h: 2, color: 0x94a3b8, subsystem: "signals",
    title: "ACC sense (IO32) + LM75A board temperature (I2C)",
    category: "Sensing", source: "BUY",
    mount: "100 kΩ / 10 kΩ + BAT54S clamp + 100 nF; LM75A in the middle of the board.",
    wiring: "ACC ≥ 9.0 V = on, < 7.5 V = off; ≥ 13.0 V for 1 s = engine running. The LM75A drives the hot-start hold (≥ 60 °C: wait for 55 °C, at most 10 min).",
  });

  // Keep-outs from the enclosure generator
  const keepMat = (color) => new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.16, depthWrite: false });
  const addKeep = (id, zone, h, color, title, wiring) => {
    const [x, y] = centre(...zone);
    const m = new THREE.Mesh(new THREE.BoxGeometry(zone[2] * MM, zone[3] * MM, h * MM), keepMat(color));
    m.position.set(x * MM, y * MM, (0.92 + h / 2) * MM);
    m.userData.pickId = id;
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
    bezel: { color: 0x1f2937, opacity: 1, explode: -40, title: "Bezel (print face down)", mount: "2 mm lip over the glass's black border, 0.3 mm clear of the glass (no pressure on the touch panel). 10 mm chin with 20 intake slots, 2.5 mm wide. 6 × M3 into the side walls and the chin." },
    housing: { color: 0x475569, opacity: 0.55, explode: 0, title: "Housing: plate + rear box (print plate down)", mount: "The display screws to the plate through its own 4 × M3 frame holes. The box holds the Pi (on the display's standoffs) and this PCB on 4 posts (92 × 92). USB/Ethernet window, SMA bulkhead, AMPS 30 × 38 M4 nuts, 2 mm bumps so air leaves round the plate." },
    lid: { color: 0x64748b, opacity: 0.5, explode: 40, title: "Lid with the 30 mm fan (print outside down)", mount: "The inventory fan blows out through a 2.5 mm bar grille; cable exit with a split grommet; locating rim; 4 × M3 into the ears." },
    display: { color: 0x0b1a3a, opacity: 1, explode: -28, title: "Official 7\" Touch Display (dummy)", mount: "Mounted upside down (cable edge up): 6 o'clock viewing direction, docs 50° top / 70° bottom. Rotate the image 180° and invert touch." },
    pi: { color: 0x15803d, opacity: 1, explode: -14, title: "Raspberry Pi 4 + adapter + ribbons (dummy)", mount: "On the display's own standoffs, ports to the driver's right (window in the box wall). GPIO plugs 90° / low profile." },
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
