import * as THREE from "three";
import { OrbitControls } from "three/addons/OrbitControls.js";
import { STLLoader } from "three/addons/STLLoader.js";

const stageEl = document.getElementById("scene");
const inspectHud = document.getElementById("inspect-hud");
const tipEl = document.getElementById("tip");
const mediaEl = document.getElementById("media");
const studioImgEl = document.getElementById("studio-img");
const captionEl = document.getElementById("caption");

const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
renderer.localClippingEnabled = true;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.15;
stageEl.appendChild(renderer.domElement);

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(36, 1, 0.002, 10);
camera.up.set(0, 0, 1);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;

scene.add(new THREE.HemisphereLight(0xdce8ff, 0x262c38, 1.45));
const key = new THREE.DirectionalLight(0xfff4ea, 2.3);
key.position.set(0.3, -0.4, 0.5);
scene.add(key);
const rim = new THREE.DirectionalLight(0x9ec5ff, 1.3);
rim.position.set(-0.3, 0.4, -0.3);
scene.add(rim);

const assemblyGrid = new THREE.GridHelper(0.4, 16, 0x3b485e, 0x1d2533);
assemblyGrid.rotation.x = Math.PI / 2;
assemblyGrid.position.z = -0.025;
scene.add(assemblyGrid);

const clipPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
const rootGroup = new THREE.Group();
scene.add(rootGroup);

const SUB_COLORS = { pcb: 0x166534, ui: 0xf04d10, rf_mcu: 0x228be6, power_io: 0xf59f00 };
const MM = 0.001;
const loader = new STLLoader();

let manifest = null;
const records = [];
const hiddenParts = new Set();
let colorMode = "reference";
let selectedName = null;
let isolatedName = null;
let explodeAmt = 0;
let xrayOn = false;
let sectionOn = false;
let turntableOn = false;

function resize() {
  const w = stageEl.clientWidth || 640, h = stageEl.clientHeight || 480;
  camera.aspect = w / h; camera.updateProjectionMatrix();
  renderer.setSize(w, h, false);
}
window.addEventListener("resize", resize);
resize();

function hideMedia() { mediaEl.hidden = true; studioImgEl.hidden = true; }
function showStudioImage(src, title) {
  studioImgEl.src = src; studioImgEl.hidden = false;
  captionEl.textContent = `${title} · KiCad 10 PCB Render`;
  mediaEl.hidden = false;
}

function applyColorsAndOpacity() {
  for (const r of records) {
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

function updateExplode() {
  for (const r of records) {
    const [ex, ey, ez] = r.item.explode_mm || [0, 0, 0];
    r.mesh.position.set(ex * MM * explodeAmt, ey * MM * explodeAmt, ez * MM * explodeAmt);
  }
}

function renderPartInspector(rec) {
  const detail = document.getElementById("detail");
  if (!rec) {
    inspectHud.hidden = true;
    detail.textContent = "Click any 3-D solid in the viewport or inspect BOM rows above.";
    return;
  }
  const it = rec.item;
  const html = `
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
  inspectHud.innerHTML = html;
  inspectHud.hidden = false;
  detail.innerHTML = html;
  const wire = (root) => {
    root.querySelectorAll("[data-act]").forEach((btn) => {
      btn.onclick = () => {
        const a = btn.dataset.act;
        if (a === "close") { isolatedName = null; selectPart(null); }
        else if (a === "isolate") { isolatedName = isolatedName === it.name ? null : it.name; applyColorsAndOpacity(); renderPartInspector(rec); }
        else if (a === "hide") { hiddenParts.add(it.name); isolatedName = null; document.getElementById("show-all-btn").checked = false; selectPart(null); }
      };
    });
  };
  wire(inspectHud); wire(detail);
}

function selectPart(name) {
  selectedName = (name && selectedName === name) ? null : name;
  if (!selectedName) isolatedName = null;
  applyColorsAndOpacity();
  renderPartInspector(records.find((r) => r.item.name === selectedName) || null);
}

function setCameraView(key) {
  hideMedia();
  const presets = {
    iso: [[0.18, -0.22, 0.22], [0, 0, 0], "Isometric"],
    front: [[0, -0.01, 0.30], [0, 0, 0], "Front (OLED & LEDs)"],
    back: [[0, -0.01, -0.30], [0, 0, 0], "Back (ESP32 & CC1101)"],
    side: [[0.30, 0, 0.04], [0, 0, 0], "Side Profile"],
  };
  const p = presets[key] || presets.iso;
  camera.position.set(...p[0]);
  controls.target.set(...p[1]);
  controls.update();
  document.getElementById("view-label").textContent = p[2];
}

function buildUI() {
  const tabsDef = [
    ["model", "Model"], ["parts", "BOM"], ["hardware", "Hardware"],
    ["mfg", "Gerbers"], ["studio", "Renders"], ["firmware", "Firmware"],
  ];
  const tabsEl = document.getElementById("tabs");
  tabsDef.forEach(([id, label], i) => {
    const btn = document.createElement("button");
    btn.textContent = label;
    if (i === 0) btn.classList.add("active");
    btn.onclick = () => {
      tabsEl.querySelectorAll("button").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      tabsDef.forEach(([sid]) => { document.getElementById(sid).hidden = sid !== id; });
      if (id !== "studio") hideMedia();
    };
    tabsEl.appendChild(btn);
  });

  const viewsEl = document.getElementById("views");
  [["iso", "Isometric"], ["front", "Front (OLED)"], ["back", "Back (MCU/RF)"], ["side", "Side Profile"]].forEach(([k, lbl]) => {
    const b = document.createElement("button");
    b.textContent = lbl;
    b.onclick = () => setCameraView(k);
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
      applyColorsAndOpacity();
    };
    colorsEl.appendChild(b);
  });

  document.getElementById("explode").oninput = (e) => {
    explodeAmt = Number(e.target.value) / 100;
    document.getElementById("amount").textContent = `${e.target.value}%`;
    updateExplode();
  };
  document.getElementById("xray").onchange = (e) => { xrayOn = e.target.checked; applyColorsAndOpacity(); };
  document.getElementById("section").onchange = (e) => { sectionOn = e.target.checked; applyColorsAndOpacity(); };
  document.getElementById("spin").onchange = (e) => { turntableOn = e.target.checked; };
  document.getElementById("show-all-btn").onchange = (e) => {
    if (e.target.checked) { hiddenParts.clear(); isolatedName = null; applyColorsAndOpacity(); }
  };
  document.getElementById("reset").onclick = () => {
    selectedName = null; isolatedName = null; hiddenParts.clear();
    explodeAmt = 0; xrayOn = false; sectionOn = false; turntableOn = false;
    document.getElementById("explode").value = "0"; document.getElementById("amount").textContent = "0%";
    document.getElementById("xray").checked = false; document.getElementById("section").checked = false;
    document.getElementById("spin").checked = false; document.getElementById("show-all-btn").checked = true;
    updateExplode(); renderPartInspector(null); applyColorsAndOpacity(); setCameraView("iso");
  };
  document.getElementById("media-close").onclick = hideMedia;
  document.getElementById("back-3d").onclick = hideMedia;
  document.getElementById("collapse").onclick = (e) => {
    const c = document.querySelector("main").classList.toggle("collapsed");
    e.target.textContent = c ? "Show" : "Hide";
    setTimeout(resize, 20);
  };

  // BOM tab
  const bom = manifest.bom || [];
  document.getElementById("part-count").textContent = bom.length;
  const bomEl = document.getElementById("bom-list");
  bomEl.style.cssText = "display:flex;flex-direction:column;gap:5px;max-height:280px;overflow-y:auto;";
  const renderBom = (q = "") => {
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
  renderBom();
  document.getElementById("filter").oninput = (e) => renderBom(e.target.value);

  // Hardware tab
  const hw = manifest.hardware || {};
  document.getElementById("hw-dl").innerHTML = [
    ["MCU", hw.mcu], ["Primary RF", hw.rf_primary], ["Alt RF", hw.rf_alt],
    ["OLED Display", hw.display], ["User I/O", hw.ui], ["Power Tree", hw.power],
    ["Wheel Sensors", hw.sensors], ["USB Cutouts", hw.usb_holes], ["Order Status", hw.status],
  ].map(([k, v]) => `<dt>${k}</dt><dd style="text-align:right">${v || "—"}</dd>`).join("");

  // Manufacturing downloads
  const dlEl = document.getElementById("dl-list");
  dlEl.style.cssText = "display:flex;flex-direction:column;gap:6px;";
  for (const d of manifest.downloads || []) {
    const a = document.createElement("a");
    a.className = "item-btn";
    a.href = d.href;
    a.style.textDecoration = "none";
    a.innerHTML = `<span>${d.label}</span><span class="pill pass">${d.badge}</span>`;
    dlEl.appendChild(a);
  }

  // Renders tab
  const studioEl = document.getElementById("studio-list");
  for (const r of manifest.studio_renders || []) {
    const b = document.createElement("button");
    b.className = "item-btn";
    b.innerHTML = `<span>${r.title}</span><span class="pill pass">PNG</span>`;
    b.onclick = () => showStudioImage(r.file, r.title);
    studioEl.appendChild(b);
  }

  // Firmware tab
  const fw = manifest.firmware || {};
  document.getElementById("fw-dl").innerHTML = [
    ["Framework", fw.framework], ["Source Path", fw.path], ["Capabilities", fw.modes],
  ].map(([k, v]) => `<dt>${k}</dt><dd style="text-align:right">${v || "—"}</dd>`).join("");

  const d = manifest.dims_mm || [189, 128, 27.1];
  document.getElementById("dimension").textContent = `${d[0]} × ${d[1]} × ${d[2]} mm · Ready to Order`;
}

// Raycast hover & click
const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();
let downPos = null;
function pickMesh(clientX, clientY) {
  if (!mediaEl.hidden) return null;
  const rect = renderer.domElement.getBoundingClientRect();
  pointer.x = ((clientX - rect.left) / rect.width) * 2 - 1;
  pointer.y = -((clientY - rect.top) / rect.height) * 2 + 1;
  raycaster.setFromCamera(pointer, camera);
  const hits = raycaster.intersectObjects(records.filter((r) => r.mesh.visible).map((r) => r.mesh), false);
  return hits.length ? hits[0].object : null;
}
renderer.domElement.addEventListener("pointermove", (e) => {
  const hit = pickMesh(e.clientX, e.clientY);
  if (!hit) { tipEl.hidden = true; renderer.domElement.style.cursor = "grab"; return; }
  const rec = records.find((r) => r.mesh === hit);
  if (!rec) { tipEl.hidden = true; return; }
  renderer.domElement.style.cursor = "pointer";
  tipEl.textContent = `${rec.item.label} (${rec.item.dims_mm.join("×")} mm)`;
  tipEl.style.left = `${e.clientX + 14}px`; tipEl.style.top = `${e.clientY + 14}px`;
  tipEl.hidden = false;
});
renderer.domElement.addEventListener("pointerleave", () => { tipEl.hidden = true; });
renderer.domElement.addEventListener("pointerdown", (e) => { downPos = [e.clientX, e.clientY]; });
renderer.domElement.addEventListener("pointerup", (e) => {
  if (!downPos || Math.hypot(e.clientX - downPos[0], e.clientY - downPos[1]) > 5) return;
  const hit = pickMesh(e.clientX, e.clientY);
  if (hit) selectPart(hit.userData.name);
});
window.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    if (!mediaEl.hidden) hideMedia();
    else { isolatedName = null; selectPart(null); }
  }
});

async function init() {
  manifest = await fetch("manifest.json", { cache: "no-store" }).then((r) => r.json());
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
    rootGroup.add(mesh);
    records.push({ item: it, mesh, mat, hue: (i * 0.618) % 1 });
  }
  buildUI();
  applyColorsAndOpacity();
  setCameraView("iso");

  let last = performance.now();
  function tick(now) {
    requestAnimationFrame(tick);
    const dt = Math.min(0.05, (now - last) * 0.001);
    last = now;
    if (turntableOn && mediaEl.hidden) rootGroup.rotation.z += dt * 0.45;
    controls.update();
    renderer.render(scene, camera);
  }
  requestAnimationFrame(tick);
}

init();
