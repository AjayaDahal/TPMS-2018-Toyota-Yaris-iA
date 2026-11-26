import * as THREE from "three";
import { OrbitControls } from "three/addons/OrbitControls.js";
import { STLLoader } from "three/addons/STLLoader.js";
import { createCarBlueprintScene } from "./car_scene.js";
import { createPcb6Scene } from "./pcb6_scene.js";

const stageEl = document.getElementById("scene");
const inspectHud = document.getElementById("inspect-hud");
const tipEl = document.getElementById("tip");
const mediaEl = document.getElementById("media");
const studioImgEl = document.getElementById("studio-img");
const captionEl = document.getElementById("caption");
const hudPreviewBox = document.getElementById("hud-preview-box");
const bsmStatePill = document.getElementById("bsm-state-pill");

const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
renderer.localClippingEnabled = true;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.15;
stageEl.appendChild(renderer.domElement);

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(38, 1, 0.005, 80);
camera.up.set(0, 0, 1);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;

scene.add(new THREE.HemisphereLight(0xdce8ff, 0x222a38, 1.55));
const key = new THREE.DirectionalLight(0xfff4ea, 2.2);
key.position.set(4.5, -5.0, 6.5);
scene.add(key);
const rim = new THREE.DirectionalLight(0x9ec5ff, 1.35);
rim.position.set(-4.0, 5.0, 3.0);
scene.add(rim);

const clipPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);

// Three mutually exclusive scene roots
const carRoot = new THREE.Group();
const pcb6Root = new THREE.Group();
const v1Root = new THREE.Group();
scene.add(carRoot, pcb6Root, v1Root);

const v1Grid = new THREE.GridHelper(0.4, 16, 0x3b485e, 0x1d2533);
v1Grid.rotation.x = Math.PI / 2;
v1Grid.position.z = -0.025;
v1Root.add(v1Grid);

const v1PartsGroup = new THREE.Group();
v1Root.add(v1PartsGroup);

const SUB_COLORS = { pcb: 0x166534, ui: 0xf04d10, rf_mcu: 0x228be6, power_io: 0xf59f00 };
const MM = 0.001;
const loader = new STLLoader();

let manifest = null;
let systemPlan = null;
let carCtx = null;
let pcb6Ctx = null;
let activeMode = "car"; // "car" | "pcb6" | "v1"

// v1 PCB state
const v1Records = [];
const hiddenParts = new Set();
let colorMode = "reference";
let selectedName = null;
let isolatedName = null;
let explodeAmt = 0;
let xrayOn = false;
let sectionOn = false;
let turntableOn = false;
let v1Loaded = false;

function resize() {
  const w = stageEl.clientWidth || 640, h = stageEl.clientHeight || 480;
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  renderer.setSize(w, h, false);
}
window.addEventListener("resize", resize);
resize();

function hideMedia() {
  mediaEl.hidden = true;
  studioImgEl.hidden = true;
}
function showStudioImage(src, title) {
  studioImgEl.src = src;
  studioImgEl.hidden = false;
  captionEl.textContent = `${title} · KiCad 10 PCB Render`;
  mediaEl.hidden = false;
}

function showInspectCard(info) {
  if (!info) {
    inspectHud.hidden = true;
    return;
  }
  const badgeClass =
    /INVENTORY|INSTALLED|OEM/i.test(info.source || "") ? "inv" :
    /BUY|JLCPCB/i.test(info.source || "") ? "buy" : "opt";
  inspectHud.innerHTML = `
    <div class="hud-top">
      <div>
        <strong>${info.title}</strong>
        <div class="muted">${info.category || ""}</div>
      </div>
      <span class="pill ${badgeClass}">${info.source || "INFO"}</span>
    </div>
    <div class="hud-grid">
      <span>Location</span><span>${info.location || "—"}</span>
      <span>Mount</span><span>${info.mount || "—"}</span>
      <span>Wiring</span><span>${info.wiring || "—"}</span>
    </div>
    <div class="hud-actions">
      <button class="hud-btn" id="inspect-close-btn">✕ Close</button>
    </div>
  `;
  inspectHud.hidden = false;
  const closeBtn = document.getElementById("inspect-close-btn");
  if (closeBtn) closeBtn.onclick = () => { inspectHud.hidden = true; };
}

// ---------------- v1 PCB helpers ----------------
function applyV1ColorsAndOpacity() {
  for (const r of v1Records) {
    const it = r.item;
    r.mesh.visible = !hiddenParts.has(it.name) && (!isolatedName || it.name === isolatedName);
    let hex;
    if (colorMode === "subsystem") hex = SUB_COLORS[it.subsystem] ?? 0x868e96;
    else if (colorMode === "parts") hex = new THREE.Color().setHSL(r.hue, 0.58, 0.58).getHex();
    else hex = new THREE.Color(...it.color).getHex();
    r.mat.color.setHex(hex);
    const isSel = selectedName && it.name === selectedName;
    const faded = (xrayOn && it.subsystem === "pcb" && !isSel) || (selectedName && !isSel && !isolatedName);
    r.mat.transparent = faded;
    r.mat.opacity = isSel ? 1.0 : (faded ? 0.22 : 1.0);
    r.mat.depthWrite = !faded;
    r.mat.emissive.setHex(isSel ? 0x5c1d05 : 0x000000);
    r.mat.clippingPlanes = sectionOn ? [clipPlane] : [];
    r.mat.needsUpdate = true;
  }
}

function updateV1Explode() {
  for (const r of v1Records) {
    const [ex, ey, ez] = r.item.explode_mm || [0, 0, 0];
    r.mesh.position.set(ex * MM * explodeAmt, ey * MM * explodeAmt, ez * MM * explodeAmt);
  }
}

function renderV1Inspector(rec) {
  if (!rec) {
    inspectHud.hidden = true;
    return;
  }
  const it = rec.item;
  inspectHud.innerHTML = `
    <div class="hud-top">
      <div>
        <strong>${it.label}</strong>
        <div class="muted">${it.name} · ${it.subsystem}</div>
      </div>
      <span class="pill pass">${it.subsystem.toUpperCase()}</span>
    </div>
    <div class="hud-grid">
      <span>Envelope</span><span>${it.dims_mm.join(" × ")} mm</span>
    </div>
    <div class="hud-actions">
      <button class="hud-btn" data-act="isolate">${isolatedName === it.name ? "Show All" : "Isolate"}</button>
      <button class="hud-btn" data-act="hide">Hide Part</button>
      <a class="hud-btn primary" href="../../01-hardware/docs/tpms_panel.step" download>STEP</a>
      <button class="hud-btn" data-act="close">✕</button>
    </div>
  `;
  inspectHud.hidden = false;
  inspectHud.querySelectorAll("[data-act]").forEach((btn) => {
    btn.onclick = () => {
      const a = btn.dataset.act;
      if (a === "close") { isolatedName = null; selectV1Part(null); }
      else if (a === "isolate") { isolatedName = isolatedName === it.name ? null : it.name; applyV1ColorsAndOpacity(); renderV1Inspector(rec); }
      else if (a === "hide") { hiddenParts.add(it.name); isolatedName = null; document.getElementById("show-all-btn").checked = false; selectV1Part(null); }
    };
  });
}

function selectV1Part(name) {
  selectedName = (name && selectedName === name) ? null : name;
  if (!selectedName) isolatedName = null;
  applyV1ColorsAndOpacity();
  renderV1Inspector(v1Records.find((r) => r.item.name === selectedName) || null);
}

async function ensureV1Loaded() {
  if (v1Loaded || !manifest) return;
  v1Loaded = true;
  for (let i = 0; i < (manifest.items || []).length; i++) {
    const it = manifest.items[i];
    const geo = await loader.loadAsync(it.url);
    geo.scale(MM, MM, MM);
    geo.computeVertexNormals();
    const mat = new THREE.MeshStandardMaterial({
      color: new THREE.Color(...it.color),
      roughness: it.subsystem === "pcb" ? 0.55 : 0.35,
      metalness: it.subsystem === "pcb" ? 0.1 : 0.35,
      side: THREE.DoubleSide,
    });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.userData.name = it.name;
    v1PartsGroup.add(mesh);
    v1Records.push({ item: it, mesh, mat, hue: (i * 0.618) % 1 });
  }
  applyV1ColorsAndOpacity();
}

// ---------------- Camera presets per mode ----------------
function setCarCamera(key) {
  hideMedia();
  const presets = {
    iso: [[-6.2, -7.2, 5.2], [0, -1.2, 0.65], "Full Blueprint Isometric"],
    top: [[0.01, -1.2, 11.2], [0, -1.2, 0.5], "Top Blueprint Plan View"],
    cockpit: [[-0.36, -0.35, 1.18], [0.02, 0.52, 0.78], "Driver Cockpit · 7\" Touch Enclosure, Door LEDs, Alert Pod"],
    mirror_l: [[-2.05, -0.45, 1.38], [-0.94, 0.54, 0.96], "Left Mirror Camera & Door Boot"],
    console: [[0.18, -0.22, 0.92], [0.0, 0.50, 0.66], "Console Pocket: Printed Enclosure (Display + Pi + PCB)"],
    footwell: [[-0.68, 0.06, 0.70], [-0.50, 0.58, 0.62], "Driver Footwell: OBD-II Dongle, ACC Fuse Tap, Blinker Feeds"],
    side: [[-6.4, -0.6, 1.3], [0, -0.6, 0.75], "Side Elevation (L = 4360 mm)"],
  };
  const p = presets[key] || presets.iso;
  camera.near = 0.03;
  camera.far = 80;
  camera.updateProjectionMatrix();
  camera.position.set(...p[0]);
  controls.target.set(...p[1]);
  controls.update();
  document.getElementById("view-label").textContent = p[2];
}

function setPcb6Camera(key) {
  hideMedia();
  const presets = {
    iso: [[0.165, -0.185, 0.16], [0, 0, 0], "6-Layer 100×100 PCB Isometric"],
    top: [[0, -0.004, 0.23], [0, 0, 0], "Parts Side (faces the enclosure lid)"],
    bottom: [[0, -0.004, -0.23], [0, 0, 0], "Underside (faces the Pi, 3 mm air gap)"],
    stack: [[0.21, -0.02, 0.04], [0, 0, 0], "6-Layer Stackup Edge View"],
  };
  const p = presets[key] || presets.iso;
  camera.near = 0.002;
  camera.far = 10;
  camera.updateProjectionMatrix();
  camera.position.set(...p[0]);
  controls.target.set(...p[1]);
  controls.update();
  document.getElementById("view-label").textContent = p[2];
}

function setV1Camera(key) {
  hideMedia();
  const presets = {
    iso: [[0.18, -0.22, 0.22], [0, 0, 0], "v1 TPMS Panel Isometric"],
    front: [[0, -0.01, 0.30], [0, 0, 0], "v1 Front (2.7\" OLED & Tyre LEDs)"],
    back: [[0, -0.01, -0.30], [0, 0, 0], "v1 Back (ESP32 & CC1101)"],
    side: [[0.30, 0, 0.04], [0, 0, 0], "v1 Side Profile"],
  };
  const p = presets[key] || presets.iso;
  camera.near = 0.002;
  camera.far = 10;
  camera.updateProjectionMatrix();
  camera.position.set(...p[0]);
  controls.target.set(...p[1]);
  controls.update();
  document.getElementById("view-label").textContent = p[2];
}

// ---------------- Tab & Mode switching ----------------
const TABS = [
  ["tab-car", "Car & Sim"],
  ["tab-pcb6", "6L PCB"],
  ["tab-wiring", "Wiring"],
  ["tab-bom", "Inv/Buy"],
  ["tab-checklists", "Checklists"],
  ["tab-premortem", "Premortem"],
  ["tab-v1", "v1 PCB"],
  ["tab-docs", "Renders"],
];

function activateTab(tabId) {
  document.querySelectorAll("#tabs button").forEach((b) => {
    b.classList.toggle("active", b.dataset.tab === tabId);
  });
  TABS.forEach(([id]) => {
    const sec = document.getElementById(id);
    if (sec) sec.hidden = id !== tabId;
  });
  if (tabId !== "tab-docs") hideMedia();
}

async function switchMode(mode, syncTab = true) {
  activeMode = mode;
  hideMedia();
  inspectHud.hidden = true;

  carRoot.visible = mode === "car";
  pcb6Root.visible = mode === "pcb6";
  v1Root.visible = mode === "v1";

  document.querySelectorAll(".mode-switch button").forEach((b) => {
    b.classList.toggle("active", b.dataset.mode === mode);
  });

  const pipChecked = document.getElementById("sim-hud-pip")?.checked;
  hudPreviewBox.hidden = !(mode === "car" && pipChecked);

  if (mode === "car") {
    document.getElementById("eyebrow").textContent = "2018 TOYOTA YARIS iA (MAZDA2 DJ SEDAN) · FULL-CAR BLUEPRINT";
    document.getElementById("stage-title").textContent = "TPMS + Dual-Camera Blind-Spot System";
    document.getElementById("dimension").textContent = "4360 × 1695 × 1485 mm · WB 2570 mm · Mirrors 1983 mm";
    setCarCamera("iso");
    if (syncTab) activateTab("tab-car");
  } else if (mode === "pcb6") {
    document.getElementById("eyebrow").textContent = "JLCPCB 6-LAYER · ENIG · 100 × 100 mm · PROMO PRICE TO CONFIRM AT CHECKOUT";
    document.getElementById("stage-title").textContent = "100 × 100 mm ESP32 Carrier + Printed Display Enclosure";
    document.getElementById("dimension").textContent = "PCB 100.0 × 100.0 × 1.6 mm · enclosure 205.6 × 127.9 × 71.8 mm · layout pending (gate G7)";
    setPcb6Camera("iso");
    if (syncTab) activateTab("tab-pcb6");
  } else {
    document.getElementById("eyebrow").textContent = "ORIGINAL v1 TPMS MONITOR PANEL · 2-LAYER KiCad 10";
    document.getElementById("stage-title").textContent = "315 MHz Dash TPMS Receiver PCB (189×128 mm)";
    const d = (manifest && manifest.dims_mm) || [189, 128, 27.1];
    document.getElementById("dimension").textContent = `${d[0]} × ${d[1]} × ${d[2]} mm · ERC/DRC 0/0 · orderable, but no room for it if the 7" display takes the pocket`;
    await ensureV1Loaded();
    setV1Camera("iso");
    if (syncTab) activateTab("tab-v1");
  }
}

function buildUI() {
  // Top mode buttons
  document.querySelectorAll(".mode-switch button").forEach((btn) => {
    btn.onclick = () => switchMode(btn.dataset.mode, true);
  });

  // Inspector tabs
  const tabsEl = document.getElementById("tabs");
  TABS.forEach(([id, label], i) => {
    const btn = document.createElement("button");
    btn.textContent = label;
    btn.dataset.tab = id;
    if (i === 0) btn.classList.add("active");
    btn.onclick = () => {
      activateTab(id);
      if (id === "tab-car" && activeMode !== "car") switchMode("car", false);
      else if (id === "tab-pcb6" && activeMode !== "pcb6") switchMode("pcb6", false);
      else if (id === "tab-v1" && activeMode !== "v1") switchMode("v1", false);
    };
    tabsEl.appendChild(btn);
  });

  // ---- TAB 1: CAR BLUEPRINT & SIM ----
  const carViewsEl = document.getElementById("car-views");
  [
    ["iso", "Blueprint Iso"], ["top", "Top Plan"],
    ["cockpit", "Driver Cockpit"], ["mirror_l", "Left Mirror Cam"],
    ["console", "Console Pocket"], ["side", "Side Profile"],
    ["footwell", "Footwell: OBD + Taps"],
  ].forEach(([k, lbl]) => {
    const b = document.createElement("button");
    b.textContent = lbl;
    b.onclick = () => { if (activeMode !== "car") switchMode("car", false); setCarCamera(k); };
    carViewsEl.appendChild(b);
  });

  const mountDescEl = document.getElementById("mount-desc");
  const updateMountCard = (id) => {
    const opt = systemPlan?.mount_options?.[id];
    if (!opt) return;
    mountDescEl.innerHTML = `<strong>${opt.name}</strong><br>${opt.summary}<br><span class="muted">DSI: ${opt.dsi_cable}</span>`;
  };
  updateMountCard("console_float");
  document.querySelectorAll("#mount-opts button").forEach((btn) => {
    btn.onclick = () => {
      document.querySelectorAll("#mount-opts button").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      carCtx.setMountOption(btn.dataset.mount);
      updateMountCard(btn.dataset.mount);
    };
  });

  // Blinker simulator buttons
  document.querySelectorAll("#sim-blinker button").forEach((btn) => {
    btn.onclick = () => {
      document.querySelectorAll("#sim-blinker button").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      carCtx.sim.blinker = btn.dataset.blink;
    };
  });

  // Target type & side
  document.querySelectorAll("#sim-target button[data-target]").forEach((btn) => {
    btn.onclick = () => {
      document.querySelectorAll("#sim-target button[data-target]").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      carCtx.sim.targetType = btn.dataset.target;
    };
  });
  const sideBtn = document.getElementById("btn-target-side");
  sideBtn.onclick = () => {
    carCtx.sim.targetSide = carCtx.sim.targetSide === "L" ? "R" : "L";
    sideBtn.textContent = `Side: ${carCtx.sim.targetSide === "L" ? "Left Lane" : "Right Lane"}`;
  };

  const targetYSlider = document.getElementById("target-y");
  targetYSlider.oninput = (e) => {
    carCtx.sim.autoDrive = false;
    document.getElementById("sim-auto").checked = false;
    carCtx.sim.targetY = Number(e.target.value) / 10;
    document.getElementById("target-y-out").textContent = `${carCtx.sim.targetY.toFixed(1)} m`;
  };
  document.getElementById("speed-mph").oninput = (e) => {
    carCtx.sim.speedMph = Number(e.target.value);
    document.getElementById("speed-out").textContent = `${e.target.value} mph`;
  };
  document.getElementById("sim-auto").onchange = (e) => { carCtx.sim.autoDrive = e.target.checked; };
  document.getElementById("sim-audio").onchange = (e) => {
    carCtx.sim.audioOn = e.target.checked;
    if (e.target.checked) carCtx.playPiezoBeep(3000, 0.08);
  };
  document.getElementById("sim-night").onchange = (e) => { carCtx.sim.nightMode = e.target.checked; };
  document.getElementById("sim-hud-pip").onchange = (e) => {
    hudPreviewBox.hidden = !(activeMode === "car" && e.target.checked);
  };
  document.getElementById("btn-tpms-beep").onclick = () => {
    const prev = carCtx.sim.audioOn;
    carCtx.sim.audioOn = true;
    carCtx.triggerTpmsChime();
    carCtx.sim.audioOn = prev;
  };

  document.getElementById("car-xray").onchange = (e) => carCtx.setShellXray(e.target.checked);
  document.getElementById("car-fov").onchange = (e) => carCtx.setFovVisible(e.target.checked);
  document.getElementById("car-dims").onchange = (e) => carCtx.setDimsVisible(e.target.checked);
  ["cameras", "power", "signals", "alerts", "sensors", "rf"].forEach((k) => {
    document.getElementById(`h-${k}`).onchange = (e) => carCtx.setHarnessVisible(k, e.target.checked);
  });

  // ---- TAB 2: 6-LAYER PCB ----
  const p6ViewsEl = document.getElementById("pcb6-views");
  [["iso", "Isometric"], ["top", "Top (L1)"], ["bottom", "Bottom (L6)"], ["stack", "Stackup Edge"]].forEach(([k, lbl]) => {
    const b = document.createElement("button");
    b.textContent = lbl;
    b.onclick = () => { if (activeMode !== "pcb6") switchMode("pcb6", false); setPcb6Camera(k); };
    p6ViewsEl.appendChild(b);
  });
  document.getElementById("pcb6-explode").oninput = (e) => {
    document.getElementById("pcb6-explode-out").textContent = `${e.target.value}%`;
    pcb6Ctx.setExplode(Number(e.target.value) / 100);
  };
  document.getElementById("pcb6-stack").onchange = (e) => {
    pcb6Ctx.setMountStackVisible(e.target.checked);
    document.getElementById("enclosure-card").hidden = !e.target.checked;
    if (e.target.checked) {
      camera.position.set(0.30, -0.34, 0.26);
      controls.target.set(0, 0, -0.01);
      controls.update();
      document.getElementById("view-label").textContent = "Printed enclosure: bezel, housing, lid (+ display, Pi, PCB dummies)";
    } else {
      setPcb6Camera("iso");
    }
  };
  document.getElementById("pcb6-xray").onchange = (e) => pcb6Ctx.setXray(e.target.checked);
  document.getElementById("pcb6-subcolor").onchange = (e) => pcb6Ctx.setColorMode(e.target.checked ? "subsystem" : "ref");

  const pinoutEl = document.getElementById("v1-v2-pinout");
  (systemPlan?.v1_v2_pinout || []).forEach((r) => {
    const cls = r.match === "EXACT" ? "inv" : (r.match === "FIXED" ? "buy" : "opt");
    const div = document.createElement("div");
    div.className = "wire-card";
    div.innerHTML = `<div style="display:flex;justify-content:space-between;gap:6px;align-items:center;"><strong style="font-family:monospace">${r.pin}</strong><span class="pill ${cls}">${r.match}</span></div><div class="muted">v1: ${r.v1}</div><div>v2: ${r.v2}</div>`;
    pinoutEl.appendChild(div);
  });

  const p6LayersEl = document.getElementById("pcb6-layers");
  (systemPlan?.pcb6_stackup || []).forEach((ly, idx) => {
    const row = document.createElement("label");
    row.className = "layer-row";
    row.innerHTML = `<input type="checkbox" checked data-lidx="${idx}" /><span class="layer-swatch" style="background:${ly.color}"></span><span><b>${ly.layer}</b> · <span class="muted">${ly.role.slice(0, 44)}…</span></span>`;
    row.querySelector("input").onchange = (e) => pcb6Ctx.setLayerVisible(idx, e.target.checked);
    p6LayersEl.appendChild(row);
  });

  const p6BlocksEl = document.getElementById("pcb6-blocks");
  pcb6Ctx.pickables.filter((p) => p.id.startsWith("p6_")).forEach((p) => {
    const btn = document.createElement("button");
    btn.className = "item-btn";
    const cls = /INVENTORY/i.test(p.source) ? "inv" : (/OPTIONAL/i.test(p.category) ? "opt" : "buy");
    btn.innerHTML = `<span><b>${p.title.split("(")[0].trim()}</b><br><small class="muted">${p.category}</small></span><span class="pill ${cls}">${p.source.split(" ")[0]}</span>`;
    btn.onclick = () => {
      if (activeMode !== "pcb6") switchMode("pcb6", false);
      showInspectCard(p);
    };
    p6BlocksEl.appendChild(btn);
  });

  // ---- TAB 3: WIRING & POWER ----
  const bp = systemPlan?.vehicle_blueprint || {};
  document.getElementById("bp-dl").innerHTML = [
    ["Vehicle", bp.model],
    ["L × W × H", `${bp.length_mm} × ${bp.width_body_mm} × ${bp.height_mm} mm`],
    ["Mirror Span", `${bp.width_mirrors_mm} mm`],
    ["Wheelbase", `${bp.wheelbase_mm} mm`],
    ["Track F / R", `${bp.track_front_mm} / ${bp.track_rear_mm} mm`],
    ["Tires", bp.tire_size],
    ["Console Pocket", bp.console_pocket_mm],
    ["7\" RPi Display", bp.rpi_7in_display_mm],
    ["6-Layer PCB", bp.carrier_pcb_mm],
  ].map(([k, v]) => `<dt>${k}</dt><dd style="text-align:right">${v || "—"}</dd>`).join("");

  const wiringListEl = document.getElementById("wiring-list");
  (systemPlan?.wiring_harness || []).forEach((w) => {
    const div = document.createElement("div");
    div.className = "wire-card";
    div.innerHTML = `<strong>${w.name}</strong><div class="wire-meta">${w.cable}</div><div>${w.route}</div><div class="muted" style="margin-top:3px;">Protection: ${w.protection}</div>`;
    wiringListEl.appendChild(div);
  });

  const pwrEl = document.getElementById("power-list");
  const railTot = {};
  const rows = (systemPlan?.power_budget || []).map((p) => {
    const r = (railTot[p.rail] = railTot[p.rail] || { typ: 0, peak: 0 });
    r.typ += p.typ_a;
    r.peak += p.peak_a;
    return `<dt>${p.load} <span class="muted">(${p.rail})</span></dt><dd>${p.typ_a.toFixed(2)} A / ${p.peak_a.toFixed(2)} A pk</dd>`;
  }).join("");
  const limits = { "5V_PI": "Pololu D36V50F5, 5.5 A", "5V_ESP": "TSR 1-2450, 1 A", "12V_PROT": "4 A fuse" };
  const totals = Object.entries(railTot).map(([k, v]) =>
    `<dt><b>${k} total</b> <span class="muted">(${limits[k] || ""})</span></dt><dd style="color:#fb923c;">${v.typ.toFixed(2)} A / ${v.peak.toFixed(2)} A pk</dd>`).join("");
  pwrEl.innerHTML = `<dl>${rows}${totals}</dl>`;

  // ---- TAB 4: INVENTORY VS BUY BOM ----
  let bomFilterSrc = "ALL";
  const sysBom = systemPlan?.system_bom || [];
  const renderSysBom = () => {
    const q = (document.getElementById("sys-bom-search").value || "").trim().toLowerCase();
    const listEl = document.getElementById("sys-bom-list");
    listEl.innerHTML = "";
    let invCount = 0, buyCost = 0, optCost = 0;
    for (const r of sysBom) {
      if (r.source === "INVENTORY") invCount++;
      else if (r.source === "BUY") buyCost += r.cost_usd || 0;
      else optCost += r.cost_usd || 0;
    }
    document.getElementById("sys-bom-summary").innerHTML =
      `<b>${invCount}</b> core items reused from your lab inventory (<span style="color:#34d399">$0</span>) · Core Buy Est: <b style="color:#fb923c">~$${buyCost}</b> (+shipping) · Optional Phase 2: <b style="color:#7dd3fc">~$${optCost}</b>`;

    for (const r of sysBom) {
      if (bomFilterSrc !== "ALL" && r.source !== bomFilterSrc) continue;
      if (q && !`${r.item} ${r.category} ${r.notes} ${r.source}`.toLowerCase().includes(q)) continue;
      const cls = r.source === "INVENTORY" ? "inv" : (r.source === "BUY" ? "buy" : "opt");
      const badge = r.source === "INVENTORY" ? `IN LAB (×${r.inv_stock})` : (r.cost_usd ? `BUY ~$${r.cost_usd}` : "IN LAB (OPT)");
      const card = document.createElement("div");
      card.className = "wire-card";
      card.innerHTML = `<div style="display:flex;justify-content:space-between;gap:6px;align-items:flex-start;"><strong>${r.item}</strong><span class="pill ${cls}">${badge}</span></div><div class="muted">${r.category} · Qty ${r.qty}</div><div style="margin-top:2px;">${r.notes}</div>`;
      listEl.appendChild(card);
    }
  };
  document.querySelectorAll("#bom-filter-pills button").forEach((btn) => {
    btn.onclick = () => {
      document.querySelectorAll("#bom-filter-pills button").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      bomFilterSrc = btn.dataset.src;
      renderSysBom();
    };
  });
  document.getElementById("sys-bom-search").oninput = renderSysBom;
  renderSysBom();

  // ---- TAB 5: INTERACTIVE CHECKLISTS (localStorage persisted) ----
  const CHK_STORE_KEY = "yaris_ia_bsm_tpms_checklists_v2";
  let chkDone = {};
  try { chkDone = JSON.parse(localStorage.getItem(CHK_STORE_KEY) || "{}"); } catch { chkDone = {}; }
  let activeChkGroup = "collect";

  const CHK_GROUPS = {
    collect: "checklist_collect", buy: "checklist_buy", measure: "checklist_measure",
    bench: "checklist_bench", tools: "checklist_tools", steps: "build_steps",
  };
  const getChkItems = (g) => systemPlan?.[CHK_GROUPS[g]] || [];

  const renderChecklists = () => {
    Object.keys(CHK_GROUPS).forEach((g) => {
      const arr = getChkItems(g);
      const doneCnt = arr.filter((x) => chkDone[x.id]).length;
      const el = document.getElementById(`chk-cnt-${g}`);
      if (el) el.textContent = `${doneCnt}/${arr.length}`;
    });

    const items = getChkItems(activeChkGroup);
    const doneCnt = items.filter((x) => chkDone[x.id]).length;
    const pct = items.length ? Math.round((doneCnt / items.length) * 100) : 0;
    document.getElementById("chk-prog-bar").style.width = `${pct}%`;
    document.getElementById("chk-prog-label").textContent = `${doneCnt} of ${items.length} completed (${pct}%) — saved automatically in browser`;

    const listEl = document.getElementById("chk-list");
    listEl.innerHTML = "";
    for (const it of items) {
      const checked = Boolean(chkDone[it.id]);
      const row = document.createElement("label");
      row.className = `chk-row${checked ? " done" : ""}`;
      const meta = it.where || it.cost || it.phase || "";
      row.innerHTML = `
        <input type="checkbox" ${checked ? "checked" : ""} />
        <div>
          ${meta ? `<div class="chk-phase">${meta}</div>` : ""}
          <div class="chk-txt">${it.text}</div>
        </div>
      `;
      row.querySelector("input").onchange = (e) => {
        chkDone[it.id] = e.target.checked;
        try { localStorage.setItem(CHK_STORE_KEY, JSON.stringify(chkDone)); } catch {}
        renderChecklists();
      };
      listEl.appendChild(row);
    }
  };

  document.querySelectorAll("#chk-subtabs button").forEach((btn) => {
    btn.onclick = () => {
      document.querySelectorAll("#chk-subtabs button").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      activeChkGroup = btn.dataset.chk;
      renderChecklists();
    };
  });
  document.getElementById("chk-reset").onclick = () => {
    chkDone = {};
    try { localStorage.removeItem(CHK_STORE_KEY); } catch {}
    renderChecklists();
  };
  renderChecklists();

  // ---- TAB 6: ORDER GATE + PREMORTEM (generated from PREMORTEM_v2.md by 04-viewer/sync_plan.py) ----
  const gate = systemPlan?.order_gate || [];
  const open = gate.filter((g) => g.status !== "done");
  document.getElementById("gate-verdict").innerHTML = open.length
    ? `<b style="color:#f87171">v2 PCB: not yet.</b> ${gate.length - open.length} of ${gate.length} gates done; open: ${open.map((g) => g.id).join(", ")}. The v1 panel is orderable (ERC/DRC 0/0) but has no place in the car if the 7" display takes the pocket.`
    : `<b style="color:#34d399">All gates green: the v2 PCB can be ordered.</b>`;
  const GATE_PILL = { done: ["pass", "DONE"], you: ["buy", "YOU"], next: ["opt", "NEXT"] };
  const gateEl = document.getElementById("gate-list");
  gate.forEach((g) => {
    const [cls, txt] = GATE_PILL[g.status] || ["pa", g.status];
    const div = document.createElement("div");
    div.className = "wire-card";
    div.innerHTML = `<div style="display:flex;justify-content:space-between;gap:6px;align-items:flex-start;"><strong>${g.id} · ${g.needed}</strong><span class="pill ${cls}">${txt}</span></div><div class="muted" style="margin-top:2px;">${g.detail}</div>`;
    gateEl.appendChild(div);
  });

  const pms = systemPlan?.premortem || [];
  const STATUS_PILL = { fixed: ["pass", "FIXED"], you: ["buy", "YOU"], plan: ["opt", "PLAN"], phase2: ["opt", "PHASE 2"], accepted: ["pa", "ACCEPTED"] };
  const catSel = document.getElementById("pm-category");
  ["All groups", ...new Set(pms.map((p) => p.category))].forEach((c, i) => {
    const o = document.createElement("option");
    o.value = i === 0 ? "" : c;
    o.textContent = i === 0 ? `All groups (${pms.length})` : `${c} (${pms.filter((p) => p.category === c).length})`;
    catSel.appendChild(o);
  });
  let pmStatus = "all";
  const pmEl = document.getElementById("premortem-list");
  const renderPremortem = () => {
    pmEl.innerHTML = "";
    const shown = pms.filter((p) => (!catSel.value || p.category === catSel.value) &&
      (pmStatus === "all" || p.status_keys.includes(pmStatus)));
    document.getElementById("pm-count").textContent =
      `${pms.length} items · ${pms.filter((p) => p.status_keys.includes("fixed")).length} fixed · ${pms.filter((p) => p.status_keys.includes("you")).length} need you`;
    for (const pm of shown) {
      const pills = pm.status_keys.map((k) => `<span class="pill ${(STATUS_PILL[k] || ["pa"])[0]}">${(STATUS_PILL[k] || [0, k])[1]}</span>`).join(" ");
      const div = document.createElement("div");
      div.className = "wire-card";
      div.innerHTML = `
        <div style="display:flex;justify-content:space-between;gap:6px;align-items:flex-start;">
          <strong>${pm.id} · ${pm.title}</strong><span style="white-space:nowrap">${pills}</span>
        </div>
        <div class="muted" style="margin-top:2px;">${pm.category} · Likely: ${pm.likelihood}${pm.cause ? ` · ${pm.cause}` : ""}</div>
        <div class="pm-fix">${pm.fix}</div>
        ${pm.status && pm.status !== "Fixed" ? `<div class="muted" style="margin-top:2px;">Status: ${pm.status}</div>` : ""}
      `;
      pmEl.appendChild(div);
    }
    if (!shown.length) pmEl.innerHTML = `<div class="muted">Nothing in this filter.</div>`;
  };
  catSel.onchange = renderPremortem;
  document.querySelectorAll("#pm-status-pills button").forEach((btn) => {
    btn.onclick = () => {
      document.querySelectorAll("#pm-status-pills button").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      pmStatus = btn.dataset.st;
      renderPremortem();
    };
  });
  renderPremortem();

  // ---- Enclosure summary card (from enclosure_report.json via sync_plan.py) ----
  const enc = systemPlan?.enclosure;
  const encCard = document.getElementById("enclosure-card");
  if (enc && encCard) {
    const o = enc.overall_mm, b = enc.box_mm, pc = enc.pcb_constraints;
    encCard.innerHTML = `<strong>Printed enclosure (${enc.mount}, ${enc.checks.passed}/${enc.checks.total} fit checks pass)</strong><br>
      Overall ${o.width} × ${o.height} × ${o.depth} mm · rear box ${b.width} × ${b.height} mm, ${b.behind_plate} mm behind the plate (pocket ≥ ${b.clear_pocket_depth_needed} mm) · Pi ports face the ${enc.ports_face}.<br>
      <span class="muted">PCB keep-outs: parts ≤ ${pc.max_part_height_mm} mm · ${pc.fan_zone} · ${pc.sma_strip} · ${pc.corners}.</span><br>
      <a href="../../01-hardware/enclosure/README.md" target="_blank">Enclosure README</a> · STL: ${enc.print_files.map((f) => `<a href="${f}" download>${f.split("/").pop().replace("print_", "").replace(".stl", "")}</a>`).join(" · ")}`;
  }

  // ---- TAB 5: ORIGINAL v1 PCB ----
  const viewsEl = document.getElementById("views");
  [["iso", "Isometric"], ["front", "Front (OLED)"], ["back", "Back (MCU/RF)"], ["side", "Side Profile"]].forEach(([k, lbl]) => {
    const b = document.createElement("button");
    b.textContent = lbl;
    b.onclick = async () => { if (activeMode !== "v1") await switchMode("v1", false); setV1Camera(k); };
    viewsEl.appendChild(b);
  });
  const colorsEl = document.getElementById("colors");
  [["reference", "PCB Reference"], ["subsystem", "Subsystem"], ["parts", "By Solid"]].forEach(([k, lbl], i) => {
    const b = document.createElement("button");
    b.textContent = lbl;
    if (i === 0) b.classList.add("active");
    b.onclick = () => {
      colorMode = k;
      colorsEl.querySelectorAll("button").forEach((x) => x.classList.remove("active"));
      b.classList.add("active");
      applyV1ColorsAndOpacity();
    };
    colorsEl.appendChild(b);
  });
  document.getElementById("explode").oninput = (e) => {
    explodeAmt = Number(e.target.value) / 100;
    document.getElementById("amount").textContent = `${e.target.value}%`;
    updateV1Explode();
  };
  document.getElementById("xray").onchange = (e) => { xrayOn = e.target.checked; applyV1ColorsAndOpacity(); };
  document.getElementById("section").onchange = (e) => { sectionOn = e.target.checked; applyV1ColorsAndOpacity(); };
  document.getElementById("spin").onchange = (e) => { turntableOn = e.target.checked; };
  document.getElementById("show-all-btn").onchange = (e) => {
    if (e.target.checked) { hiddenParts.clear(); isolatedName = null; applyV1ColorsAndOpacity(); }
  };
  document.getElementById("reset").onclick = () => {
    selectedName = null; isolatedName = null; hiddenParts.clear();
    explodeAmt = 0; xrayOn = false; sectionOn = false; turntableOn = false;
    document.getElementById("explode").value = "0"; document.getElementById("amount").textContent = "0%";
    document.getElementById("xray").checked = false; document.getElementById("section").checked = false;
    document.getElementById("spin").checked = false; document.getElementById("show-all-btn").checked = true;
    updateV1Explode(); renderV1Inspector(null); applyV1ColorsAndOpacity(); setV1Camera("iso");
  };

  const bom = manifest?.bom || [];
  document.getElementById("part-count").textContent = bom.length;
  const bomEl = document.getElementById("bom-list");
  bomEl.style.cssText = "display:flex;flex-direction:column;gap:5px;max-height:240px;overflow-y:auto;";
  const renderV1Bom = (q = "") => {
    bomEl.innerHTML = "";
    const ql = q.trim().toLowerCase();
    for (const r of bom) {
      if (ql && !`${r.designators} ${r.value} ${r.part} ${r.description}`.toLowerCase().includes(ql)) continue;
      const div = document.createElement("div");
      div.className = "item-btn";
      div.innerHTML = `<span><b>${r.designators}</b> · ${r.value}<br><small class="muted">${r.description || r.part}</small></span><span class="pill ${r.populate === "yes" ? "pass" : "pa"}">×${r.qty}</span>`;
      bomEl.appendChild(div);
    }
  };
  renderV1Bom();
  document.getElementById("filter").oninput = (e) => renderV1Bom(e.target.value);

  // ---- TAB 6: RENDERS & DOCS ----
  const studioEl = document.getElementById("studio-list");
  for (const r of manifest?.studio_renders || []) {
    const b = document.createElement("button");
    b.className = "item-btn";
    b.innerHTML = `<span>${r.title}</span><span class="pill pass">PNG</span>`;
    b.onclick = () => showStudioImage(r.file, r.title);
    studioEl.appendChild(b);
  }
  const dlEl = document.getElementById("dl-list");
  dlEl.style.cssText = "display:flex;flex-direction:column;gap:6px;";
  for (const d of manifest?.downloads || []) {
    const a = document.createElement("a");
    a.className = "item-btn";
    a.href = d.href;
    a.style.textDecoration = "none";
    a.innerHTML = `<span>${d.label}</span><span class="pill pass">${d.badge}</span>`;
    dlEl.appendChild(a);
  }
  const hw = manifest?.hardware || {};
  document.getElementById("hw-dl").innerHTML = [
    ["MCU", hw.mcu], ["Primary RF", hw.rf_primary], ["OLED Display", hw.display],
    ["Power Tree", hw.power], ["Wheel Sensors", hw.sensors], ["v1 Status", hw.status],
  ].map(([k, v]) => `<dt>${k}</dt><dd style="text-align:right">${v || "—"}</dd>`).join("");

  const fw = manifest?.firmware || {};
  document.getElementById("fw-dl").innerHTML = [
    ["Framework", fw.framework], ["Source Path", fw.path], ["Capabilities", fw.modes],
  ].map(([k, v]) => `<dt>${k}</dt><dd style="text-align:right">${v || "—"}</dd>`).join("");

  document.getElementById("media-close").onclick = hideMedia;
  document.getElementById("back-3d").onclick = hideMedia;
  document.getElementById("collapse").onclick = (e) => {
    const c = document.querySelector("main").classList.toggle("collapsed");
    e.target.textContent = c ? "Show" : "Hide";
    setTimeout(resize, 20);
  };
}

// ---------------- Unified Raycasting ----------------
const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();
let downPos = null;

function pickCurrent(clientX, clientY) {
  if (!mediaEl.hidden || !carCtx || !pcb6Ctx) return null;
  const rect = renderer.domElement.getBoundingClientRect();
  pointer.x = ((clientX - rect.left) / rect.width) * 2 - 1;
  pointer.y = -((clientY - rect.top) / rect.height) * 2 + 1;
  raycaster.setFromCamera(pointer, camera);

  if (activeMode === "v1") {
    const hits = raycaster.intersectObjects(v1Records.filter((r) => r.mesh.visible).map((r) => r.mesh), false);
    if (!hits.length) return null;
    const rec = v1Records.find((r) => r.mesh === hits[0].object);
    return rec ? { kind: "v1", rec, tip: `${rec.item.label} (${rec.item.dims_mm.join("×")} mm)` } : null;
  }

  const root = activeMode === "car" ? carRoot : pcb6Root;
  const pickList = activeMode === "car" ? carCtx.pickables : pcb6Ctx.pickables;
  const hits = raycaster.intersectObjects(root.children, true);
  for (const h of hits) {
    let obj = h.object;
    while (obj && obj !== root) {
      if (obj.userData && obj.userData.pickId) {
        const info = pickList.find((p) => p.id === obj.userData.pickId);
        if (info) return { kind: "info", info, tip: `${info.title} · ${info.source}` };
      }
      obj = obj.parent;
    }
  }
  return null;
}

renderer.domElement.addEventListener("pointermove", (e) => {
  const hit = pickCurrent(e.clientX, e.clientY);
  if (!hit) { tipEl.hidden = true; renderer.domElement.style.cursor = "grab"; return; }
  renderer.domElement.style.cursor = "pointer";
  tipEl.textContent = hit.tip;
  tipEl.style.left = `${e.clientX + 14}px`;
  tipEl.style.top = `${e.clientY + 14}px`;
  tipEl.hidden = false;
});
renderer.domElement.addEventListener("pointerleave", () => { tipEl.hidden = true; });
renderer.domElement.addEventListener("pointerdown", (e) => { downPos = [e.clientX, e.clientY]; });
renderer.domElement.addEventListener("pointerup", (e) => {
  if (!downPos || Math.hypot(e.clientX - downPos[0], e.clientY - downPos[1]) > 5) return;
  const hit = pickCurrent(e.clientX, e.clientY);
  if (!hit) return;
  if (hit.kind === "v1") selectV1Part(hit.rec.item.name);
  else showInspectCard(hit.info);
});

window.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    if (!mediaEl.hidden) hideMedia();
    else if (activeMode === "v1") { isolatedName = null; selectV1Part(null); }
    else inspectHud.hidden = true;
  }
});

async function init() {
  [manifest, systemPlan] = await Promise.all([
    fetch("manifest.json", { cache: "no-store" }).then((r) => r.json()),
    fetch("system_plan.json", { cache: "no-store" }).then((r) => r.json()),
  ]);

  carCtx = createCarBlueprintScene(carRoot);
  pcb6Ctx = createPcb6Scene(pcb6Root, systemPlan.pcb6_stackup || [], systemPlan.enclosure || null);

  buildUI();
  await switchMode("car", true);

  let last = performance.now();
  function tick(now) {
    requestAnimationFrame(tick);
    const dt = Math.min(0.05, (now - last) * 0.001);
    last = now;

    if (activeMode === "car" && carCtx) {
      const st = carCtx.update(dt, now);
      if (carCtx.sim.autoDrive) {
        const sEl = document.getElementById("target-y");
        if (sEl) sEl.value = String(Math.round(carCtx.sim.targetY * 10));
        const oEl = document.getElementById("target-y-out");
        if (oEl) oEl.textContent = `${carCtx.sim.targetY.toFixed(1)} m`;
      }
      if (st.danger) {
        bsmStatePill.className = "pill danger";
        bsmStatePill.textContent = "⚠ DANGER · BEEP";
      } else if (st.hazard) {
        bsmStatePill.className = "pill pa";
        bsmStatePill.textContent = "HAZARD · SILENT";
      } else if (st.occL || st.occR) {
        bsmStatePill.className = "pill pa";
        bsmStatePill.textContent = st.speedGateOk ? `OCCUPIED (${st.occL ? "L" : "R"})` : "LOW SPD GATE";
      } else {
        bsmStatePill.className = "pill pass";
        bsmStatePill.textContent = "CLEAR";
      }
    } else if (activeMode === "v1" && turntableOn && mediaEl.hidden) {
      v1PartsGroup.rotation.z += dt * 0.45;
    }

    controls.update();
    renderer.render(scene, camera);
  }
  requestAnimationFrame(tick);
}

init();
