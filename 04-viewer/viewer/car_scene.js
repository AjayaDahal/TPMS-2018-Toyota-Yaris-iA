import * as THREE from "three";

/**
 * 2018 Toyota Yaris iA (Mazda2 DJ Sedan) 3-D Blueprint, Mounting, Wiring & Live BSM+TPMS Scene.
 *
 * Coordinate system (meters, Z-up matching existing viewer):
 *   X : lateral  (-X = Left / Driver side, +X = Right / Passenger side)
 *   Y : forward  (+Y = Nose / Front bumper, -Y = Trunk / Rear bumper, Y = 0 = mid-wheelbase)
 *   Z : vertical (Z = 0 = road plane, +Z = up)
 *
 * Verified 2018 Toyota Yaris iA (Mazda2 DJ Sedan) OEM dimensions:
 *   Length = 4.360 m | Body Width = 1.695 m | Mirror Span = 1.983 m | Height = 1.485 m
 *   Wheelbase = 2.570 m (Front axle Y = +1.285 m, Rear axle Y = -1.285 m)
 *   Front overhang = 0.865 m (Nose Y = +2.150 m) | Rear overhang = 0.925 m (Tail Y = -2.210 m)
 *   Track F/R = 1.495 / 1.485 m | Tires = 185/60R16 (OD 0.628 m, radius 0.314 m)
 */

const DIMS = {
  L: 4.36,
  W: 1.695,
  H: 1.485,
  WB: 2.57,
  Y_FA: 1.285,
  Y_RA: -1.285,
  Y_NOSE: 2.15,
  Y_TAIL: -2.21,
  TRACK_F: 1.495,
  TRACK_R: 1.485,
  WHEEL_R: 0.314,
  WHEEL_W: 0.185,
  MIRROR_X: 0.945,
  MIRROR_Y: 0.56,
  MIRROR_Z: 1.015,
};

function makeTube(points, radius, color, opacity = 0.95) {
  const curve = new THREE.CatmullRomCurve3(points.map((p) => new THREE.Vector3(...p)));
  const geo = new THREE.TubeGeometry(curve, Math.max(20, points.length * 10), radius, 8, false);
  const mat = new THREE.MeshStandardMaterial({
    color,
    emissive: color,
    emissiveIntensity: 0.28,
    roughness: 0.35,
    metalness: 0.15,
    transparent: opacity < 1,
    opacity,
  });
  return new THREE.Mesh(geo, mat);
}

function makeTextSprite(text, bg = "rgba(12,18,28,0.88)", fg = "#93c5fd", border = "#38bdf8") {
  const c = document.createElement("canvas");
  c.width = 320;
  c.height = 68;
  const ctx = c.getContext("2d");
  ctx.fillStyle = bg;
  ctx.strokeStyle = border;
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.roundRect(4, 4, c.width - 8, c.height - 8, 12);
  ctx.fill();
  ctx.stroke();
  ctx.fillStyle = fg;
  ctx.font = "bold 24px ui-monospace, SFMono-Regular, monospace";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(text, c.width / 2, c.height / 2 + 1);
  const tex = new THREE.CanvasTexture(c);
  const mat = new THREE.SpriteMaterial({ map: tex, depthTest: false, transparent: true });
  const sp = new THREE.Sprite(mat);
  sp.scale.set(0.68, 0.145, 1);
  return sp;
}

function buildSedanBody(bodyGroup) {
  // Side-view silhouette of 2018 Yaris iA / Mazda2 DJ sedan in (Y_forward, Z_up) plane
  const profile = new THREE.Shape();
  profile.moveTo(-2.16, 0.24);
  profile.lineTo(-2.21, 0.44);
  profile.lineTo(-2.14, 0.86);   // rear bumper/trunk edge
  profile.lineTo(-1.74, 0.96);   // short sedan trunk deck
  profile.lineTo(-1.12, 1.38);   // rear window slope
  profile.lineTo(-0.36, 1.485);  // roof apex (1485 mm)
  profile.lineTo(0.32, 1.44);    // top of windshield
  profile.lineTo(0.98, 1.02);    // base of windshield / cowl
  profile.lineTo(1.94, 0.84);    // long Mazda2 hood line
  profile.lineTo(2.14, 0.62);    // nose grille
  profile.lineTo(2.15, 0.30);    // front bumper lower lip
  profile.lineTo(1.88, 0.18);    // front undertray
  profile.lineTo(-1.90, 0.18);   // flat floorpan
  profile.closePath();

  const rawGeo = new THREE.ExtrudeGeometry(profile, {
    depth: DIMS.W - 0.12,
    bevelEnabled: true,
    bevelThickness: 0.06,
    bevelSize: 0.045,
    bevelSegments: 3,
  });
  const halfDepth = (DIMS.W - 0.12) / 2;
  const pAttr = rawGeo.attributes.position;
  for (let i = 0; i < pAttr.count; i++) {
    const sx = pAttr.getX(i); // longitudinal Y
    const sy = pAttr.getY(i); // vertical Z
    const sz = pAttr.getZ(i) - halfDepth; // lateral X
    // Subtle greenhouse tumblehome taper above beltline (Z > 0.96 m)
    const taper = sy > 0.95 ? 1 - 0.22 * Math.min(1, (sy - 0.95) / 0.55) : 1.0;
    // Nose/tail planform taper
    const planTaper =
      sx > 1.55 ? 1 - 0.14 * ((sx - 1.55) / 0.65) :
      sx < -1.65 ? 1 - 0.12 * ((-1.65 - sx) / 0.60) : 1.0;
    pAttr.setXYZ(i, sz * taper * planTaper, sx, sy);
  }
  rawGeo.computeVertexNormals();

  const shellMat = new THREE.MeshPhysicalMaterial({
    color: 0x3b82f6,
    metalness: 0.15,
    roughness: 0.25,
    transparent: true,
    opacity: 0.16,
    depthWrite: false,
    side: THREE.DoubleSide,
  });
  const shellMesh = new THREE.Mesh(rawGeo, shellMat);
  shellMesh.renderOrder = 2;
  bodyGroup.add(shellMesh);

  const wireGeo = new THREE.EdgesGeometry(rawGeo, 20);
  const wireMat = new THREE.LineBasicMaterial({
    color: 0x60a5fa,
    transparent: true,
    opacity: 0.55,
  });
  bodyGroup.add(new THREE.LineSegments(wireGeo, wireMat));

  // Floorpan blueprint grid plate
  const floor = new THREE.Mesh(
    new THREE.BoxGeometry(1.48, 3.3, 0.025),
    new THREE.MeshStandardMaterial({ color: 0x162030, roughness: 0.9, transparent: true, opacity: 0.65 })
  );
  floor.position.set(0, -0.02, 0.22);
  bodyGroup.add(floor);

  return { shellMat, wireMat };
}

function buildWheelsAndTpms(parent, pickables) {
  const wheelCoords = [
    { id: "wheel_fl", label: "FL Wheel · GM/Schrader EG53MA4 (315 MHz)", x: -DIMS.TRACK_F / 2, y: DIMS.Y_FA },
    { id: "wheel_fr", label: "FR Wheel · GM/Schrader EG53MA4 (315 MHz)", x: DIMS.TRACK_F / 2, y: DIMS.Y_FA },
    { id: "wheel_rl", label: "RL Wheel · GM/Schrader EG53MA4 (315 MHz)", x: -DIMS.TRACK_R / 2, y: DIMS.Y_RA },
    { id: "wheel_rr", label: "RR Wheel · GM/Schrader EG53MA4 (315 MHz)", x: DIMS.TRACK_R / 2, y: DIMS.Y_RA },
  ];
  const tireMat = new THREE.MeshStandardMaterial({ color: 0x1b2028, roughness: 0.85, metalness: 0.1 });
  const rimMat = new THREE.MeshStandardMaterial({ color: 0x94a3b8, roughness: 0.3, metalness: 0.75 });
  const sensorMat = new THREE.MeshStandardMaterial({
    color: 0x38bdf8, emissive: 0x0284c7, emissiveIntensity: 0.8, roughness: 0.2,
  });

  const rfRings = [];
  for (const w of wheelCoords) {
    const g = new THREE.Group();
    g.position.set(w.x, w.y, DIMS.WHEEL_R);

    const tire = new THREE.Mesh(new THREE.CylinderGeometry(DIMS.WHEEL_R, DIMS.WHEEL_R, DIMS.WHEEL_W, 28), tireMat);
    tire.rotation.z = Math.PI / 2;
    g.add(tire);

    const rim = new THREE.Mesh(new THREE.CylinderGeometry(0.205, 0.205, DIMS.WHEEL_W + 0.008, 16), rimMat);
    rim.rotation.z = Math.PI / 2;
    g.add(rim);

    // Valve stem TPMS sensor highlight
    const tpms = new THREE.Mesh(new THREE.BoxGeometry(0.055, 0.045, 0.045), sensorMat);
    tpms.position.set(w.x < 0 ? -0.07 : 0.07, 0.17, 0.06);
    tpms.userData.pickId = w.id;
    g.add(tpms);

    const ring = new THREE.Mesh(
      new THREE.RingGeometry(0.07, 0.095, 24),
      new THREE.MeshBasicMaterial({ color: 0x38bdf8, transparent: true, opacity: 0.65, side: THREE.DoubleSide })
    );
    ring.rotation.y = Math.PI / 2;
    ring.position.set(w.x < 0 ? 0.12 : -0.12, 0, 0);
    g.add(ring);
    rfRings.push({ ring, origin: new THREE.Vector3(w.x, w.y, DIMS.WHEEL_R) });

    pickables.push({
      id: w.id,
      mesh: tpms,
      title: w.label,
      category: "TPMS Sensor (315 MHz)",
      source: "INSTALLED IN TIRES",
      location: `Tire valve stem (${w.id.slice(-2).toUpperCase()}) · 185/60R16`,
      mount: "Clamp-in / snap-in valve sensor already installed in your 4 Yaris iA tires; woken with your EL-50448 OEC-T5 tool.",
      wiring: "Wireless 315.000 MHz OOK Manchester (123 µs half-bit, 120-bit frame) → CC1101 E07-M1101D on 6-layer PCB.",
    });

    parent.add(g);
  }
  return rfRings;
}

function buildCockpit(parent, pickables) {
  const dashMat = new THREE.MeshStandardMaterial({ color: 0x1e2533, roughness: 0.72, metalness: 0.1 });
  const trimMat = new THREE.MeshStandardMaterial({ color: 0x2c3547, roughness: 0.55, metalness: 0.25 });
  const chromeMat = new THREE.MeshStandardMaterial({ color: 0x94a3b8, roughness: 0.3, metalness: 0.8 });

  // Main dashboard crossbar
  const dash = new THREE.Mesh(new THREE.BoxGeometry(1.42, 0.42, 0.26), dashMat);
  dash.position.set(0, 0.66, 0.86);
  parent.add(dash);

  // Factory Mazda Connect 7" screen on top of dash
  const oemScreen = new THREE.Mesh(new THREE.BoxGeometry(0.185, 0.024, 0.115), trimMat);
  oemScreen.position.set(0, 0.60, 1.055);
  oemScreen.rotation.x = -0.12;
  oemScreen.userData.pickId = "oem_cmu";
  parent.add(oemScreen);
  pickables.push({
    id: "oem_cmu",
    mesh: oemScreen,
    title: "Factory Mazda Connect 7\" Display (CMU)",
    category: "OEM Vehicle Hardware",
    source: "OEM CAR",
    location: "Top-center of dashboard",
    mount: "Left stock. Its USB port does not give the turn-signal state, so v2 doesn't depend on it.",
    wiring: "v2 reads the lamp feeds through optos and the speed from your OBD-II dongle (or the GPS); listening to CAN comes later (phase 2) through a USB adapter on the Pi, listen-only.",
  });

  // 3 Rotary HVAC Dials (matching your Media.jpg photo)
  for (const dx of [-0.068, 0, 0.068]) {
    const dial = new THREE.Mesh(new THREE.CylinderGeometry(0.026, 0.028, 0.022, 20), chromeMat);
    dial.position.set(dx, 0.455, 0.785);
    dial.rotation.x = Math.PI / 2 - 0.28;
    parent.add(dial);
  }

  // Center console tunnel + trapezoidal pocket (191 top x 123 bottom x 129 H)
  const tunnel = new THREE.Mesh(new THREE.BoxGeometry(0.26, 1.12, 0.26), dashMat);
  tunnel.position.set(0, 0.06, 0.44);
  parent.add(tunnel);

  // Caliper-verified trapezoidal pocket frame (highlighted carbon trim)
  const pocket = new THREE.Mesh(
    new THREE.BoxGeometry(0.191, 0.10, 0.129),
    new THREE.MeshStandardMaterial({ color: 0x334155, roughness: 0.4, metalness: 0.45 })
  );
  pocket.position.set(0, 0.49, 0.64);
  pocket.rotation.x = -0.32;
  parent.add(pocket);

  // Automatic Gear Shifter (P-R-N-M-D) in front of pocket
  const shifterBase = new THREE.Mesh(new THREE.BoxGeometry(0.11, 0.18, 0.05), trimMat);
  shifterBase.position.set(0, 0.29, 0.56);
  parent.add(shifterBase);
  const shifterKnob = new THREE.Mesh(new THREE.CylinderGeometry(0.024, 0.018, 0.11, 16), trimMat);
  shifterKnob.position.set(0, 0.29, 0.65);
  shifterKnob.rotation.x = 0.18;
  parent.add(shifterKnob);

  // Steering wheel & column (Driver side X = -0.37 m)
  const col = new THREE.Mesh(new THREE.CylinderGeometry(0.042, 0.048, 0.34, 16), trimMat);
  col.position.set(-0.37, 0.50, 0.85);
  col.rotation.x = Math.PI / 2 - 0.32;
  parent.add(col);

  const wheel = new THREE.Mesh(new THREE.TorusGeometry(0.175, 0.018, 12, 32), trimMat);
  wheel.position.set(-0.37, 0.33, 0.90);
  wheel.rotation.x = Math.PI / 2 - 0.32;
  parent.add(wheel);

  // Simple driver & passenger front seat silhouettes for spatial scale
  const seatMat = new THREE.MeshStandardMaterial({ color: 0x1b2434, roughness: 0.9, transparent: true, opacity: 0.55 });
  for (const sx of [-0.37, 0.37]) {
    const cushion = new THREE.Mesh(new THREE.BoxGeometry(0.46, 0.48, 0.12), seatMat);
    cushion.position.set(sx, -0.08, 0.44);
    parent.add(cushion);
    const back = new THREE.Mesh(new THREE.BoxGeometry(0.45, 0.12, 0.64), seatMat);
    back.position.set(sx, -0.34, 0.78);
    back.rotation.x = -0.22;
    parent.add(back);
  }
}

function buildMirrorsAndCameras(parent, pickables) {
  const mirrorMat = new THREE.MeshStandardMaterial({ color: 0x334155, roughness: 0.35, metalness: 0.4 });
  const camBodyMat = new THREE.MeshStandardMaterial({ color: 0x06b6d4, emissive: 0x0891b2, emissiveIntensity: 0.5, roughness: 0.25 });
  const coneMatL = new THREE.MeshBasicMaterial({ color: 0x06b6d4, transparent: true, opacity: 0.11, side: THREE.DoubleSide, depthWrite: false });
  const coneMatR = new THREE.MeshBasicMaterial({ color: 0x06b6d4, transparent: true, opacity: 0.11, side: THREE.DoubleSide, depthWrite: false });
  const roiMatL = new THREE.MeshBasicMaterial({ color: 0x22c55e, transparent: true, opacity: 0.18, side: THREE.DoubleSide, depthWrite: false });
  const roiMatR = new THREE.MeshBasicMaterial({ color: 0x22c55e, transparent: true, opacity: 0.18, side: THREE.DoubleSide, depthWrite: false });

  const fovGroup = new THREE.Group();
  parent.add(fovGroup);

  const blinkerMats = { L: null, R: null };

  for (const side of ["L", "R"]) {
    const sign = side === "L" ? -1 : 1;
    const mx = sign * DIMS.MIRROR_X;
    const my = DIMS.MIRROR_Y;
    const mz = DIMS.MIRROR_Z;

    // Stalk + Mirror housing
    const stalk = new THREE.Mesh(new THREE.BoxGeometry(0.11, 0.08, 0.05), mirrorMat);
    stalk.position.set(sign * 0.82, my, mz - 0.02);
    parent.add(stalk);

    const housing = new THREE.Mesh(new THREE.BoxGeometry(0.17, 0.11, 0.12), mirrorMat);
    housing.position.set(mx, my, mz);
    parent.add(housing);

    // Turn-signal lamp material (used by the bumper lamps below; mirror repeaters on the Yaris iA are not verified)
    const bMat = new THREE.MeshStandardMaterial({ color: 0x451a03, emissive: 0xf59e0b, emissiveIntensity: 0.05 });
    blinkerMats[side] = bMat;

    // USB UVC camera in the lower mirror cap, aimed back along the car's side
    const cam = new THREE.Mesh(new THREE.CylinderGeometry(0.016, 0.019, 0.036, 16), camBodyMat);
    cam.position.set(mx + sign * 0.03, my - 0.01, mz - 0.072);
    cam.rotation.x = Math.PI / 2 - 0.14; // pitched slightly down
    cam.rotation.z = sign * 0.31;        // yawed outward
    cam.userData.pickId = `cam_${side}`;
    parent.add(cam);

    pickables.push({
      id: `cam_${side}`,
      mesh: cam,
      title: `${side === "L" ? "Left (driver)" : "Right (passenger)"} mirror camera (USB UVC)`,
      category: "Mirror vision (BUY after the bench test)",
      source: "BUY (~$45 each)",
      location: `Underside of the ${side === "L" ? "left" : "right"} mirror's lower cap, outer half`,
      mount: "Measure the camera barrel first and practise on a spare cap; step drill; printed wedge sets the angle; O-ring + neutral-cure (oxime) RTV. Keep a strip of the car's side in the frame: the Pi uses it to detect a folded or bumped mirror.",
      wiring: "Acceptance: MJPEG 720p30, Starvis WDR, no IR LEDs, −20…+70 °C, IP67, barrel ≤ 20 mm, ≥ 3 m lead. Lead: service loop through the hinge → door harness → door boot → kick panel → the Pi's USB 2.0 port (no JST-GH in the data path).",
    });

    // Exact 5-vertex 3-D FOV Pyramid from mirror camera lens back to adjacent-lane blind-spot zone
    const apex = [mx + sign * 0.03, my - 0.01, mz - 0.072];
    const farInBot = [sign * 1.05, -5.65, 0.03];
    const farOutBot = [sign * 3.35, -5.65, 0.03];
    const farOutTop = [sign * 3.35, -5.65, 1.50];
    const farInTop = [sign * 1.05, -5.65, 1.50];
    const verts = new Float32Array([
      ...apex, ...farInBot, ...farOutBot,
      ...apex, ...farOutBot, ...farOutTop,
      ...apex, ...farOutTop, ...farInTop,
      ...apex, ...farInTop, ...farInBot,
    ]);
    const coneGeo = new THREE.BufferGeometry();
    coneGeo.setAttribute("position", new THREE.BufferAttribute(verts, 3));
    coneGeo.computeVertexNormals();
    const cone = new THREE.Mesh(coneGeo, side === "L" ? coneMatL : coneMatR);
    fovGroup.add(cone);

    const coneEdgeVerts = new Float32Array([
      ...apex, ...farInBot, ...apex, ...farOutBot, ...apex, ...farOutTop, ...apex, ...farInTop,
      ...farInBot, ...farOutBot, ...farOutBot, ...farOutTop, ...farOutTop, ...farInTop, ...farInTop, ...farInBot,
    ]);
    const coneEdgeGeo = new THREE.BufferGeometry();
    coneEdgeGeo.setAttribute("position", new THREE.BufferAttribute(coneEdgeVerts, 3));
    fovGroup.add(new THREE.LineSegments(coneEdgeGeo, new THREE.LineBasicMaterial({ color: 0x38bdf8, transparent: true, opacity: 0.42 })));

    // Calibrated Adjacent-Lane Blind-Spot ROI Zone painted on road surface
    // Covers from B-pillar (Y=+0.3m) back to -5.5m behind bumper, width 1.05m..3.35m from centerline
    const roi = new THREE.Mesh(
      new THREE.PlaneGeometry(2.25, 6.2),
      side === "L" ? roiMatL : roiMatR
    );
    roi.position.set(sign * 2.12, -2.55, 0.015);
    fovGroup.add(roi);

    const roiOutline = new THREE.LineSegments(
      new THREE.EdgesGeometry(new THREE.PlaneGeometry(2.25, 6.2)),
      new THREE.LineBasicMaterial({ color: 0x38bdf8, transparent: true, opacity: 0.7 })
    );
    roiOutline.position.copy(roi.position);
    fovGroup.add(roiOutline);
  }

  // Front & rear bumper turn signal lamps for realistic visual blinking
  const extraBlinkers = { L: [], R: [] };
  for (const side of ["L", "R"]) {
    const sign = side === "L" ? -1 : 1;
    for (const [y, z] of [[2.11, 0.62], [-2.16, 0.76]]) {
      const lamp = new THREE.Mesh(new THREE.BoxGeometry(0.16, 0.05, 0.06), blinkerMats[side]);
      lamp.position.set(sign * 0.68, y, z);
      parent.add(lamp);
      extraBlinkers[side].push(lamp);
    }
  }

  return { fovGroup, roiMatL, roiMatR, coneMatL, coneMatR, blinkerMats };
}

function buildDisplayAndElectronics(parent, pickables) {
  // Live 800x480 UI of the Official 7" Touch Display, drawn into a CanvasTexture
  const hudCanvas = document.createElement("canvas");
  hudCanvas.width = 640;
  hudCanvas.height = 384;
  const hudTex = new THREE.CanvasTexture(hudCanvas);
  hudTex.anisotropy = 4;

  // Printed enclosure (01-hardware/enclosure): bezel + plate 205.6 x 127.9 x 11.3 mm in front, rear box
  // 112 x 120 x 60.5 mm behind it with the Pi 4 on the display's standoffs and the carrier PCB on 4 posts.
  // Group frame: X right, Y = depth (the screen faces -Y, toward the driver), Z up. Mounted upside down
  // (cable edge up), so the box centre sits 4.5 mm left of and 5.6 mm below the glass centre.
  const displayGroup = new THREE.Group();
  const plastic = new THREE.MeshStandardMaterial({ color: 0x1f2937, roughness: 0.72, metalness: 0.05 });
  const bezel = new THREE.Mesh(new THREE.BoxGeometry(0.2056, 0.0113, 0.1279), plastic);
  bezel.userData.pickId = "rpi_display";
  displayGroup.add(bezel);

  const screenPlane = new THREE.Mesh(new THREE.PlaneGeometry(0.154, 0.086), new THREE.MeshBasicMaterial({ map: hudTex }));
  screenPlane.rotation.set(Math.PI / 2, 0, 0); // normal toward -Y (driver), texture top = +Z (up), right = +X
  screenPlane.position.set(0, -0.0059, -0.001);
  screenPlane.userData.pickId = "rpi_display";
  displayGroup.add(screenPlane);

  const boxMat = new THREE.MeshStandardMaterial({ color: 0x475569, roughness: 0.7, transparent: true, opacity: 0.45, depthWrite: false });
  const rearBox = new THREE.Mesh(new THREE.BoxGeometry(0.112, 0.0605, 0.1202), boxMat);
  rearBox.position.set(-0.0045, 0.0057 + 0.03025, -0.0056);
  rearBox.userData.pickId = "enclosure_box";
  displayGroup.add(rearBox);

  const rpi4 = new THREE.Mesh(new THREE.BoxGeometry(0.085, 0.0184, 0.056), new THREE.MeshStandardMaterial({ color: 0x15803d, roughness: 0.45 }));
  rpi4.position.set(0.0035, 0.0332, -0.0035);
  rpi4.userData.pickId = "rpi4_sbc";
  displayGroup.add(rpi4);

  const pcb6 = new THREE.Mesh(
    new THREE.BoxGeometry(0.100, 0.0016, 0.100),
    new THREE.MeshStandardMaterial({ color: 0x059669, emissive: 0x047857, emissiveIntensity: 0.35, roughness: 0.35 })
  );
  pcb6.position.set(-0.0045, 0.0487, -0.0015);
  pcb6.userData.pickId = "pcb6_carrier";
  displayGroup.add(pcb6);

  const fan = new THREE.Mesh(new THREE.BoxGeometry(0.030, 0.010, 0.030), new THREE.MeshStandardMaterial({ color: 0x111827 }));
  fan.position.set(0.0005, 0.062, 0.0025);
  displayGroup.add(fan);

  parent.add(displayGroup);

  pickables.push(
    {
      id: "rpi_display",
      mesh: bezel,
      title: "Printed enclosure + Official 7\" Touch Display",
      category: "Display + enclosure",
      source: "INVENTORY display (confirm the glass) + printed parts",
      location: "Option A: in front of the console opening, rear box in the pocket · Option B: dash top on a RAM / AMPS base",
      mount: "The display screws to the housing's plate through its own 4 × M3 frame holes; the bezel lip sits 0.3 mm clear of the glass. Upside down (cable edge up) for contrast from above. 205.6 × 127.9 × 71.8 mm; make_enclosure.py runs 38 fit checks.",
      wiring: "Inside: the Pi on the display's standoffs and the carrier PCB behind it. Air: chin intake → lid fan. Cameras plug into the Pi through the box window (90° adapters); harness through the lid grommet; antenna on an SMA bulkhead.",
    },
    {
      id: "enclosure_box",
      mesh: rearBox,
      title: "Rear box: Pi 4 + carrier PCB + 30 mm fan",
      category: "Printed enclosure",
      source: "ASA / ABS print (never PLA) or MJF PA12",
      location: "Behind the display; in Option A it drops into the console pocket (needs ≥ 66 mm clear depth)",
      mount: "112 × 120 mm, 60.5 mm deep behind the plate. 2 mm bumps on the plate let the fan's air out round the bezel, so the pocket is never sealed. AMPS 30 × 38 M4 nuts in the bottom wall.",
      wiring: "Thermal test T1 in a sun-soaked car: SoC < 80 °C and get_throttled 0x0, or lower the clock / move the PCB to its own box.",
    },
    {
      id: "rpi4_sbc",
      mesh: rpi4,
      title: "Raspberry Pi 4 Model B (vision + UI)",
      category: "Compute (INVENTORY)",
      source: "INVENTORY (2 in the lab; needs ≥ 2 GB)",
      location: "On the display's own standoffs, inside the rear box; ports to the driver's right",
      mount: "Heatsinks; the lid fan pulls air past it. GPIO plugs 90° / low profile (height budget).",
      wiring: "Bookworm with a read-only root, overlay FS, watchdog. Two UVC streams, 320 × 320 detector, touch UI; talks to the ESP32 over its GPIO UART (checksummed $BSM / $ESP / $TPM lines).",
    },
    {
      id: "pcb6_carrier",
      mesh: pcb6,
      title: "100 × 100 mm 6-layer carrier PCB (ESP32 + CC1101 + power)",
      category: "Custom PCB (layout pending, gate G7)",
      source: "JLCPCB 6-layer (promo price to confirm)",
      location: "Inside the rear box, on 4 posts behind the Pi; parts face the lid",
      mount: "4 × M3 on 92 × 92 into the housing's posts. Its underside is 3 mm above the Pi's tallest part. Switch to the 6-layer mode at the top for the layers and the keep-outs.",
      wiring: "P1 power, ACC only: fuse, SMCJ22CA, P-MOSFET, π filter → Pololu 5V_PI (on by default) + TSR 5V_ESP → 3V3. ESP32 pins from pins_v2.h (audited).",
    }
  );

  // Amber blind-spot LEDs on the inner door sails (door side, not the A-pillar trim: curtain airbag)
  const ledMats = {};
  for (const side of ["L", "R"]) {
    const sign = side === "L" ? -1 : 1;
    const mat = new THREE.MeshStandardMaterial({ color: 0x334155, emissive: 0xf59e0b, emissiveIntensity: 0.0, roughness: 0.2 });
    const m = new THREE.Mesh(new THREE.SphereGeometry(0.016, 16, 16), mat);
    m.position.set(sign * 0.70, 0.52, 0.97);
    m.userData.pickId = `door_led_${side}`;
    parent.add(m);
    ledMats[side] = mat;
    pickables.push({
      id: `door_led_${side}`,
      mesh: m,
      title: `${side === "L" ? "Left" : "Right"} amber blind-spot LED (inner door sail)`,
      category: "Visual alert",
      source: "BUY (amber 5 mm + bezel)",
      location: `Inside the ${side === "L" ? "driver's" : "passenger's"} door, at the mirror's base, facing the driver`,
      mount: "On the door's inner sail or the mirror housing, not in the A-pillar trim: the Yaris iA has side-curtain airbags behind it. The wires ride with the camera cable through the door boot.",
      wiring: `Low-side MOSFET on ${side === "L" ? "IO25" : "IO14"}. Steady = vehicle in the blind spot; flashing = you are signalling towards it. PWM level from the Pi (night dimming).`,
    });
  }

  // Alert pod next to the shifter: mute / acknowledge button + 12 V active piezo
  const podG = new THREE.Group();
  const pod = new THREE.Mesh(new THREE.BoxGeometry(0.060, 0.030, 0.028), plastic);
  pod.userData.pickId = "alert_pod";
  podG.add(pod);
  const btn = new THREE.Mesh(new THREE.CylinderGeometry(0.0062, 0.0062, 0.006, 20), new THREE.MeshStandardMaterial({ color: 0x94a3b8, metalness: 0.8, roughness: 0.3 }));
  btn.rotation.x = Math.PI / 2;
  btn.position.set(-0.016, 0, 0.017);
  btn.userData.pickId = "alert_pod";
  podG.add(btn);
  const piezoMat = new THREE.MeshStandardMaterial({ color: 0xe11d48, emissive: 0xf43f5e, emissiveIntensity: 0.15 });
  const grille = new THREE.Mesh(new THREE.CylinderGeometry(0.008, 0.008, 0.002, 20), piezoMat);
  grille.rotation.x = Math.PI / 2;
  grille.position.set(0.014, 0, 0.0145);
  grille.userData.pickId = "alert_pod";
  podG.add(grille);
  podG.position.set(-0.085, 0.33, 0.585);
  parent.add(podG);

  const piezoWave = new THREE.Mesh(
    new THREE.RingGeometry(0.012, 0.02, 24),
    new THREE.MeshBasicMaterial({ color: 0xf43f5e, transparent: true, opacity: 0.0, side: THREE.DoubleSide })
  );
  piezoWave.position.set(-0.071, 0.33, 0.605);
  parent.add(piezoWave);

  pickables.push({
    id: "alert_pod",
    mesh: pod,
    title: "Alert pod: mute button + 12 V piezo (wired)",
    category: "Audio alert + the one physical control",
    source: "INVENTORY button + BUY piezo + printed pod",
    location: "On the console next to the shifter, where your hand falls (not on the steering column or the knee bolster)",
    mount: "Printed pod (make_enclosure.py: pod_shell + pod_base), VHB tape + 2 × M3; one 4-pin JST-GH lead to the carrier.",
    wiring: "Button → IO4 (v1 RC): mutes the current turn and acknowledges a TPMS alarm, even while the Pi boots or after it crashes. Piezo ← IO13 low-side MOSFET from 12 V. Danger: short triple beep, at most every 3 s; hazards silent; quiet below 8 mph.",
  });

  // u-blox NEO-M8N GPS on the dash top (speed gate)
  const gps = new THREE.Mesh(
    new THREE.BoxGeometry(0.045, 0.045, 0.018),
    new THREE.MeshStandardMaterial({ color: 0x10b981, emissive: 0x059669, emissiveIntensity: 0.35 })
  );
  gps.position.set(0.46, 0.78, 1.01);
  gps.userData.pickId = "gps_module";
  parent.add(gps);
  pickables.push({
    id: "gps_module",
    mesh: gps,
    title: "u-blox NEO-M8N GPS (fallback speed)",
    category: "Speed gate (INVENTORY)",
    source: "INVENTORY (Holybro kit or 3DR GTPA010)",
    location: "Dash top under the windshield (needs sky)",
    mount: "VHB on the dash top; the cable runs behind the instrument panel, never through the A-pillar trim.",
    wiring: "UART1 (IO33 RX / IO27 TX, 9600 Bd) on a JST-GH. The speed gate uses the OBD-II speed while the dongle answers, else this GPS. No alerts below 8 mph (back on at 12); both lost: last decision held 10 s, then LEDs only.",
  });

  // OBD-II port with your Bluetooth dongle: the car's own speed (optional); the blinker stays on the lamp taps
  const obd = new THREE.Group();
  const obdPort = new THREE.Mesh(
    new THREE.BoxGeometry(0.05, 0.022, 0.02),
    new THREE.MeshStandardMaterial({ color: 0x1f2937 })
  );
  const dongle = new THREE.Mesh(
    new THREE.BoxGeometry(0.042, 0.02, 0.034),
    new THREE.MeshStandardMaterial({ color: 0x334155, emissive: 0x2563eb, emissiveIntensity: 0.5 })
  );
  dongle.position.set(0, 0, -0.026);
  obdPort.userData.pickId = "obd_dongle";
  dongle.userData.pickId = "obd_dongle";
  obd.add(obdPort, dongle);
  obd.position.set(-0.58, 0.52, 0.715);
  parent.add(obd);
  pickables.push({
    id: "obd_dongle",
    mesh: dongle,
    title: "OBD-II port + your Bluetooth dongle (optional speed)",
    category: "Speed gate (OPTIONAL)",
    source: "OPTIONAL (your ELM327-type dongle)",
    location: "Under the dash, driver's side",
    mount: "Low-profile dongle, or a short right-angle extension tied up out of the footwell. Pin 16 is always live: measure its parked current first (B8, keep it in only below ~5 mA).",
    wiring: "Bluetooth Classic to the ESP32: PID 0x0D (vehicle speed) at 5 Hz, preferred over GPS while < 1 s old. Not for the blinker: standard OBD-II has no turn-signal data, so the lamps stay on the opto taps.",
  });

  // Driver kick panel: interior fuse box (one ACC tap) + turn-signal feeds
  const fuseBox = new THREE.Mesh(
    new THREE.BoxGeometry(0.08, 0.14, 0.11),
    new THREE.MeshStandardMaterial({ color: 0xf59e0b, emissive: 0xd97706, emissiveIntensity: 0.25 })
  );
  fuseBox.position.set(-0.70, 0.62, 0.48);
  fuseBox.userData.pickId = "fuse_bcm_obd";
  parent.add(fuseBox);
  pickables.push({
    id: "fuse_bcm_obd",
    mesh: fuseBox,
    title: "Driver kick panel: fuse box (one ACC tap) + turn-signal feeds",
    category: "Power & vehicle signals",
    source: "OEM CAR + BUY Add-A-Circuit",
    location: "Left kick panel / lower dash",
    mount: "One Add-A-Circuit (5 A) on a non-critical ACC fuse, metered first: hot in ACC and ON, dead with the key out; never an SRS or engine fuse. Ring terminal on a chassis ground stud. Turn-signal feeds found with the wiring diagram and a meter (or at the tail lamps).",
    wiring: "ACC only: zero draw when parked. The OBD-II port nearby takes your Bluetooth dongle (optional speed source); listening to CAN is phase 2 (USB adapter on the Pi, listen-only).",
  });

  return { displayGroup, hudCanvas, hudTex, ledMats, piezoMat, piezoWave };
}

function buildHarnesses(parent, pickables) {
  const groups = {
    cameras: new THREE.Group(),
    power: new THREE.Group(),
    signals: new THREE.Group(),
    alerts: new THREE.Group(),
    sensors: new THREE.Group(),
    rf: new THREE.Group(),
  };
  Object.values(groups).forEach((g) => parent.add(g));

  // Mirror cameras: cap -> hinge service loop -> door harness -> door boot -> kick panel -> under the console
  // -> the Pi's USB ports on the enclosure's right side
  const camL = makeTube([
    [-0.975, 0.55, 0.943], [-0.84, 0.56, 0.99], [-0.79, 0.50, 0.86],
    [-0.78, 0.52, 0.66], [-0.79, 0.61, 0.62], [-0.74, 0.65, 0.68],
    [-0.68, 0.63, 0.64], [-0.42, 0.60, 0.70], [-0.12, 0.56, 0.62], [0.06, 0.53, 0.63],
  ], 0.0085, 0x06b6d4);
  const camR = makeTube([
    [0.975, 0.55, 0.943], [0.84, 0.56, 0.99], [0.79, 0.50, 0.86],
    [0.78, 0.52, 0.66], [0.79, 0.61, 0.62], [0.74, 0.65, 0.68],
    [0.68, 0.63, 0.64], [0.42, 0.60, 0.69], [0.14, 0.55, 0.65], [0.065, 0.525, 0.64],
  ], 0.0085, 0x06b6d4);
  camL.userData.pickId = "harness_cam";
  camR.userData.pickId = "harness_cam";
  groups.cameras.add(camL, camR);

  // 12 V ACC feed: one fuse tap -> J1 on the carrier (through the lid grommet)
  const pwrMain = makeTube([
    [-0.70, 0.62, 0.48], [-0.56, 0.62, 0.54], [-0.30, 0.58, 0.57], [-0.03, 0.53, 0.61],
  ], 0.011, 0xef4444);
  pwrMain.userData.pickId = "harness_pwr";
  groups.power.add(pwrMain);

  // Turn-signal sense pair
  const sigBlinker = makeTube([
    [-0.68, 0.58, 0.51], [-0.48, 0.56, 0.58], [-0.22, 0.54, 0.60], [-0.02, 0.53, 0.62],
  ], 0.0075, 0xfacc15);
  sigBlinker.userData.pickId = "harness_sig";
  groups.signals.add(sigBlinker);

  // Door-sail LEDs ride with the camera cables through the door boots; the alert pod lead runs under the trim
  const ledL = makeTube([
    [-0.70, 0.52, 0.97], [-0.785, 0.51, 0.86], [-0.775, 0.53, 0.66], [-0.785, 0.62, 0.62],
    [-0.735, 0.66, 0.68], [-0.675, 0.64, 0.64], [-0.42, 0.61, 0.69], [-0.12, 0.57, 0.63], [-0.02, 0.535, 0.625],
  ], 0.0055, 0xe879f9);
  const ledR = makeTube([
    [0.70, 0.52, 0.97], [0.785, 0.51, 0.86], [0.775, 0.53, 0.66], [0.785, 0.62, 0.62],
    [0.735, 0.66, 0.68], [0.675, 0.64, 0.64], [0.42, 0.61, 0.68], [0.12, 0.57, 0.64], [0.02, 0.535, 0.625],
  ], 0.0055, 0xe879f9);
  const podWire = makeTube([
    [-0.085, 0.345, 0.585], [-0.08, 0.42, 0.575], [-0.04, 0.50, 0.60], [-0.02, 0.53, 0.62],
  ], 0.0055, 0xf43f5e);
  ledL.userData.pickId = "harness_alerts";
  ledR.userData.pickId = "harness_alerts";
  podWire.userData.pickId = "harness_alerts";
  groups.alerts.add(ledL, ledR, podWire);

  // GPS lead behind the instrument panel
  const gpsWire = makeTube([
    [0.46, 0.78, 1.01], [0.42, 0.72, 0.84], [0.20, 0.62, 0.70], [0.03, 0.53, 0.62],
  ], 0.0065, 0x10b981);
  gpsWire.userData.pickId = "harness_sensors";
  groups.sensors.add(gpsWire);

  // Bluetooth link from the OBD-II dongle to the ESP32 in the enclosure: no wire, drawn dashed
  const btCurve = new THREE.CatmullRomCurve3([
    new THREE.Vector3(-0.58, 0.52, 0.67), new THREE.Vector3(-0.30, 0.50, 0.70), new THREE.Vector3(-0.03, 0.50, 0.64),
  ]);
  const btLink = new THREE.Group();
  const DASHES = 12;
  for (let k = 0; k < DASHES; k++) {
    const a = btCurve.getPoint((2 * k) / (2 * DASHES - 1));
    const b = btCurve.getPoint((2 * k + 1) / (2 * DASHES - 1));
    const dash = makeTube([[a.x, a.y, a.z], [b.x, b.y, b.z]], 0.0045, 0x60a5fa, 0.85);
    dash.userData.pickId = "obd_bt_link";
    btLink.add(dash);
  }
  groups.sensors.add(btLink);

  // 315 MHz TPMS from the four wheels to the antenna on its lead next to the console
  const wheelPts = [
    [-DIMS.TRACK_F / 2, DIMS.Y_FA, DIMS.WHEEL_R],
    [DIMS.TRACK_F / 2, DIMS.Y_FA, DIMS.WHEEL_R],
    [-DIMS.TRACK_R / 2, DIMS.Y_RA, DIMS.WHEEL_R],
    [DIMS.TRACK_R / 2, DIMS.Y_RA, DIMS.WHEEL_R],
  ];
  for (const wp of wheelPts) {
    const mid = [wp[0] * 0.45, (wp[1] + 0.54) * 0.5, 0.68];
    const arc = makeTube([wp, mid, [-0.09, 0.55, 0.60]], 0.004, 0x38bdf8, 0.48);
    groups.rf.add(arc);
  }

  pickables.push(
    {
      id: "harness_cam", mesh: camL, title: "Mirror camera USB leads (~3 / 3.5 m)",
      category: "Wiring harness", source: "The cameras' own leads",
      location: "Mirror cap → hinge service loop → door harness → door boot → kick panel → under the console → the Pi's USB 2.0 ports (enclosure window)",
      mount: "Not cut; if a splice is unavoidable: pairs kept twisted, shield continuous. No JST-GH in the USB data path (high-speed USB 2.0). 90° USB-A adapters at the Pi.",
      wiring: "O-ring + neutral-cure RTV at the cap, drip loop, butyl on the door's vapour barrier, ferrite near the Pi. Pass: no USB resets in dmesg over a 30-minute drive.",
    },
    {
      id: "harness_pwr", mesh: pwrMain, title: "12 V ACC feed (one fuse tap, 18 AWG)",
      category: "Power harness", source: "BUY Add-A-Circuit + 18 AWG TXL",
      location: "Driver's fuse box → under the dash → J1 Micro-Fit on the carrier (lid grommet)",
      mount: "Add-A-Circuit (5 A) on a metered, non-critical ACC fuse + chassis ground stud.",
      wiring: "On the board: 4 A fuse, SMCJ22CA, P-MOSFET reverse protection, π filter. No latch, no battery feed: everything is off with the key out.",
    },
    {
      id: "harness_sig", mesh: sigBlinker, title: "Turn-signal sense (2 × 22 AWG)",
      category: "Vehicle signals", source: "BUY PC817 (on the board)",
      location: "Lamp feeds (found with the wiring diagram) → carrier JST-GH",
      mount: "Solder or T-tap + heat-shrink on one 12 V lamp feed per side.",
      wiring: "PC817 optos (~6 mA each) → IO36 / IO39, polled at 1 kHz; PWM gaps bridged, spikes ignored, hazards recognised. Not from OBD-II: standard OBD-II has no turn-signal data (a CAN cross-check is phase 2).",
    },
    {
      id: "harness_alerts", mesh: ledL, title: "Door LEDs + alert pod leads",
      category: "Alert harness", source: "BUY LEDs + piezo",
      location: "Carrier → door boots → inner door sails; carrier → under the console trim → pod",
      mount: "The LED pairs ride with the camera cables through the door boots; nothing in the A-pillar trim.",
      wiring: "LEDs on IO25 / IO14 (PWM, low-side MOSFETs); pod on one 4-pin JST-GH: button IO4, piezo IO13 (12 V).",
    },
    {
      id: "harness_sensors", mesh: gpsWire, title: "GPS lead",
      category: "Sensor harness", source: "INVENTORY",
      location: "Dash top → behind the instrument panel → carrier JST-GH",
      mount: "4-pin JST-GH (5 V, GND, TX, RX); check the module's own connector pinout first.",
      wiring: "Fallback speed: the OBD-II speed wins while the dongle answers. Speed gate on at ≥ 12 mph, off below 8 mph; both lost → last decision held 10 s, then LEDs only.",
    },
    {
      id: "obd_bt_link", mesh: btLink.children[0], title: "Bluetooth: OBD-II dongle → ESP32 (optional speed)",
      category: "Sensor link (no wire)", source: "OPTIONAL (your dongle) + the ESP32's Bluetooth Classic",
      location: "OBD-II port under the dash → the enclosure in the console",
      mount: "Nothing to route. Pair once (PIN usually 1234 or 0000) and store the dongle's MAC address; the ESP32 reconnects at every start.",
      wiring: "ELM327: ATZ, ATE0, ATS0, ATH0, ATSP6, then 010D1 at 5 Hz (requests only, never AT MA). Fresh OBD speed wins over GPS; otherwise GPS, then the 10 s hold, then LEDs only. Never used for the blinker.",
    }
  );

  return groups;
}

function buildTargetVehicle(parent) {
  const group = new THREE.Group();

  // Sedan target sub-group
  const carG = new THREE.Group();
  const cBody = new THREE.Mesh(
    new THREE.BoxGeometry(1.78, 4.30, 0.92),
    new THREE.MeshStandardMaterial({ color: 0xf97316, roughness: 0.35, metalness: 0.4, transparent: true, opacity: 0.82 })
  );
  cBody.position.set(0, 0, 0.68);
  const cCab = new THREE.Mesh(
    new THREE.BoxGeometry(1.50, 2.05, 0.56),
    new THREE.MeshStandardMaterial({ color: 0xfb923c, roughness: 0.3, metalness: 0.3, transparent: true, opacity: 0.85 })
  );
  cCab.position.set(0, -0.15, 1.28);
  // Headlights
  const hlMat = new THREE.MeshBasicMaterial({ color: 0xfef08a });
  for (const hx of [-0.62, 0.62]) {
    const hl = new THREE.Mesh(new THREE.BoxGeometry(0.28, 0.06, 0.14), hlMat);
    hl.position.set(hx, 2.15, 0.74);
    carG.add(hl);
  }
  carG.add(cBody, cCab);
  group.add(carG);

  // Motorcycle target sub-group
  const motoG = new THREE.Group();
  const mFrame = new THREE.Mesh(
    new THREE.BoxGeometry(0.46, 1.95, 0.62),
    new THREE.MeshStandardMaterial({ color: 0xec4899, roughness: 0.3, metalness: 0.5 })
  );
  mFrame.position.set(0, 0, 0.62);
  const mRider = new THREE.Mesh(
    new THREE.CylinderGeometry(0.18, 0.22, 0.72, 12),
    new THREE.MeshStandardMaterial({ color: 0xf472b6, roughness: 0.5 })
  );
  mRider.position.set(0, -0.15, 1.24);
  const mHl = new THREE.Mesh(new THREE.SphereGeometry(0.11, 12, 12), hlMat);
  mHl.position.set(0, 0.98, 0.86);
  motoG.add(mFrame, mRider, mHl);
  motoG.visible = false;
  group.add(motoG);

  parent.add(group);
  return { group, carG, motoG };
}

function buildBlueprintDimensions(parent) {
  const g = new THREE.Group();
  const lineMat = new THREE.LineBasicMaterial({ color: 0x475569, transparent: true, opacity: 0.7 });

  const addDimLine = (a, b, labelText, labelPos) => {
    const geo = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(...a), new THREE.Vector3(...b)]);
    g.add(new THREE.Line(geo, lineMat));
    const sp = makeTextSprite(labelText);
    sp.position.set(...labelPos);
    g.add(sp);
  };

  // Overall Length 4,360 mm
  addDimLine([-1.35, DIMS.Y_TAIL, 0.03], [-1.35, DIMS.Y_NOSE, 0.03], "L = 4,360 mm", [-1.62, 0, 0.14]);
  // Wheelbase 2,570 mm
  addDimLine([1.22, DIMS.Y_RA, 0.03], [1.22, DIMS.Y_FA, 0.03], "WB = 2,570 mm", [1.54, 0, 0.14]);
  // Mirror-to-mirror width 1,983 mm
  addDimLine([-0.992, DIMS.Y_NOSE + 0.32, 0.03], [0.992, DIMS.Y_NOSE + 0.32, 0.03], "Mirrors = 1,983 mm", [0, DIMS.Y_NOSE + 0.42, 0.14]);

  // Road lane markings (dashed adjacent lanes for clear blind-spot spatial reference)
  const laneMat = new THREE.LineBasicMaterial({ color: 0x334155, transparent: true, opacity: 0.65 });
  for (const lx of [-3.3, -1.05, 1.05, 3.3]) {
    const geo = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(lx, -7.5, 0.006),
      new THREE.Vector3(lx, 4.5, 0.006),
    ]);
    g.add(new THREE.Line(geo, laneMat));
  }

  parent.add(g);
  return g;
}

export function createCarBlueprintScene(parentGroup) {
  const group = new THREE.Group();
  parentGroup.add(group);

  // Subtle blueprint road grid
  const roadGrid = new THREE.GridHelper(16, 32, 0x263449, 0x151e2c);
  roadGrid.rotation.x = Math.PI / 2;
  roadGrid.position.set(0, -1.0, 0.002);
  group.add(roadGrid);

  const pickables = [];
  const { shellMat, wireMat } = buildSedanBody(group);
  const rfRings = buildWheelsAndTpms(group, pickables);
  buildCockpit(group, pickables);
  const { fovGroup, roiMatL, roiMatR, coneMatL, coneMatR, blinkerMats } = buildMirrorsAndCameras(group, pickables);
  const { displayGroup, hudCanvas, hudTex, ledMats, piezoMat, piezoWave } = buildDisplayAndElectronics(group, pickables);
  const harnesses = buildHarnesses(group, pickables);
  const target = buildTargetVehicle(group);
  const dimGroup = buildBlueprintDimensions(group);

  // Simulator state
  const sim = {
    mountOption: "console_float", // "console_float" | "dash_top"
    blinker: "OFF",               // "OFF" | "L" | "R" | "HAZARD"
    targetType: "car",            // "car" | "motorcycle" | "none"
    targetSide: "L",              // "L" | "R"
    targetY: -2.4,                // longitudinal center of target (-7.5 .. +2.5 m)
    autoDrive: true,
    speedMph: 62,
    showFov: true,
    xrayBody: true,
    audioOn: false,
    nightMode: false,
  };

  // Web Audio stand-in for the 12 V active piezo: one fixed tone, alerts differ by pattern
  let audioCtx = null;
  let dangerWas = false;
  let lastDangerBeep = -1e9;
  function playPiezoBeep(freq = 3000, dur = 0.08, delay = 0) {
    if (!sim.audioOn) return;
    try {
      if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      if (audioCtx.state === "suspended") audioCtx.resume();
      const t0 = audioCtx.currentTime + delay;
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.type = "square";
      osc.frequency.value = freq;
      gain.gain.setValueAtTime(0.055, t0);
      gain.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
      osc.connect(gain);
      gain.connect(audioCtx.destination);
      osc.start(t0);
      osc.stop(t0 + dur);
    } catch {
      // Ignore browser autoplay restrictions until user interacts
    }
  }

  function applyMountPosition() {
    if (sim.mountOption === "console_float") {
      // Option A: the bezel's back face on the pocket's front face (pocket box: centre (0, 0.49, 0.64), 100 mm deep,
      // tilted -0.32 rad), so only the rear box sits inside the pocket, below the HVAC dials
      displayGroup.position.set(0, 0.437, 0.657);
      displayGroup.rotation.set(-0.32, 0, 0);
    } else {
      // Option B: dash top on a RAM / AMPS base beside the factory screen
      displayGroup.position.set(-0.22, 0.59, 1.045);
      displayGroup.rotation.set(-0.14, 0, 0.16);
    }
  }
  applyMountPosition();

  // Draw live 7" RPi Touch Display HUD (TPMS + automatic Mirror Camera / YOLO bounding box)
  let lastHudRedraw = 0;
  function drawDisplayHud(now, status) {
    if (now - lastHudRedraw < 85) return;
    lastHudRedraw = now;
    const ctx = hudCanvas.getContext("2d");
    const W = hudCanvas.width, H = hudCanvas.height;

    const showCam = status.activeCam !== null;
    ctx.fillStyle = sim.nightMode ? "#050911" : "#0b1322";
    ctx.fillRect(0, 0, W, H);

    // Top status bar
    ctx.fillStyle = "#111c30";
    ctx.fillRect(0, 0, W, 44);
    ctx.fillStyle = "#38bdf8";
    ctx.font = "bold 18px ui-monospace, monospace";
    ctx.fillText("YARIS iA · RPi4 + 7\" TOUCH · TPMS+BSM", 14, 28);
    ctx.fillStyle = sim.speedMph >= 12 ? "#4ade80" : "#94a3b8";
    ctx.textAlign = "right";
    ctx.fillText(`${Math.round(sim.speedMph)} MPH OBD  ${sim.nightMode ? "NIGHT" : "DAY"}`, W - 14, 28);
    ctx.textAlign = "left";

    if (showCam) {
      // Simulated live Starvis mirror camera view with road lane + YOLO car/motorcycle detection box
      const side = status.activeCam;
      const occupied = side === "L" ? status.occL : status.occR;
      const danger = status.danger;

      // Sky + Asphalt perspective
      const grad = ctx.createLinearGradient(0, 44, 0, H - 64);
      grad.addColorStop(0, sim.nightMode ? "#060b16" : "#1e3a5f");
      grad.addColorStop(0.32, sim.nightMode ? "#0f172a" : "#334155");
      grad.addColorStop(0.33, sim.nightMode ? "#111827" : "#1f2937");
      grad.addColorStop(1, "#0f172a");
      ctx.fillStyle = grad;
      ctx.fillRect(0, 44, W, H - 108);

      // Ego Yaris car body reference (15% inner edge)
      ctx.fillStyle = "#334155";
      const bodyX = side === "L" ? W - 92 : 0;
      ctx.fillRect(bodyX, 118, 92, H - 182);
      ctx.fillStyle = "#94a3b8";
      ctx.font = "12px monospace";
      ctx.fillText("EGO BODY", bodyX + 12, H - 82);

      // Adjacent lane perspective lines & ROI polygon
      ctx.strokeStyle = occupied ? "rgba(239,68,68,0.85)" : "rgba(34,197,94,0.65)";
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      if (side === "L") {
        ctx.moveTo(W - 96, H - 66);
        ctx.lineTo(W - 190, 145);
        ctx.lineTo(130, 145);
        ctx.lineTo(40, H - 66);
      } else {
        ctx.moveTo(96, H - 66);
        ctx.lineTo(190, 145);
        ctx.lineTo(W - 130, 145);
        ctx.lineTo(W - 40, H - 66);
      }
      ctx.closePath();
      ctx.stroke();

      // Target vehicle + YOLO bounding box inside camera view
      if (sim.targetType !== "none" && sim.targetSide === side && sim.targetY > -7.2 && sim.targetY < 1.8) {
        const norm = Math.max(0, Math.min(1, (sim.targetY + 7.2) / 8.8)); // 0=far, 1=close
        const scale = 0.35 + norm * 0.85;
        const bw = (sim.targetType === "motorcycle" ? 74 : 165) * scale;
        const bh = (sim.targetType === "motorcycle" ? 115 : 122) * scale;
        const cx = side === "L" ? 260 + (1 - norm) * 40 : W - 260 - (1 - norm) * 40;
        const cy = 175 + norm * 65;

        // Simple vehicle shape
        ctx.fillStyle = sim.targetType === "motorcycle" ? "#ec4899" : "#f97316";
        ctx.fillRect(cx - bw * 0.42, cy - bh * 0.4, bw * 0.84, bh * 0.8);
        // Bright headlights
        ctx.fillStyle = "#fef08a";
        ctx.fillRect(cx - bw * 0.32, cy - bh * 0.1, bw * 0.18, bh * 0.14);
        if (sim.targetType === "car") {
          ctx.fillRect(cx + bw * 0.14, cy - bh * 0.1, bw * 0.18, bh * 0.14);
        }

        // YOLOv8n detection box
        ctx.strokeStyle = occupied ? "#ef4444" : "#facc15";
        ctx.lineWidth = 3.5;
        ctx.strokeRect(cx - bw / 2, cy - bh / 2, bw, bh);
        const clsText = sim.targetType === "motorcycle" ? "MOTORCYCLE 0.86" : "CAR 0.94";
        ctx.fillStyle = occupied ? "#ef4444" : "#f59e0b";
        ctx.fillRect(cx - bw / 2, cy - bh / 2 - 24, 170, 24);
        ctx.fillStyle = "#fff";
        ctx.font = "bold 15px monospace";
        ctx.fillText(clsText, cx - bw / 2 + 6, cy - bh / 2 - 7);
      }

      // Camera header badge
      ctx.fillStyle = "rgba(15,23,42,0.82)";
      ctx.fillRect(12, 54, 248, 30);
      ctx.fillStyle = "#38bdf8";
      ctx.font = "bold 15px monospace";
      ctx.fillText(`LIVE ${side === "L" ? "LEFT" : "RIGHT"} MIRROR CAM · 30 FPS`, 20, 74);

      // Flashing red border when danger (blinker + vehicle in blind spot + speed >= 12 mph)
      if (danger && Math.floor(now / 110) % 2 === 0) {
        ctx.strokeStyle = "#ef4444";
        ctx.lineWidth = 14;
        ctx.strokeRect(7, 7, W - 14, H - 14);
        ctx.fillStyle = "rgba(220,38,38,0.92)";
        ctx.fillRect(W / 2 - 190, 52, 380, 36);
        ctx.fillStyle = "#fff";
        ctx.font = "bold 20px monospace";
        ctx.textAlign = "center";
        ctx.fillText(`⚠ BLIND SPOT ${sim.targetType.toUpperCase()}`, W / 2, 76);
        ctx.textAlign = "left";
      }

      // Compact TPMS strip along bottom of camera view
      ctx.fillStyle = "#0f172a";
      ctx.fillRect(0, H - 64, W, 64);
      ctx.fillStyle = "#94a3b8";
      ctx.font = "bold 16px monospace";
      ctx.fillText("TPMS 315MHz   FL 32.4   FR 32.1   RL 31.8   RR 32.0 PSI", 18, H - 26);
    } else {
      // Full 4-Wheel TPMS Dashboard + Side BSM Status Cards
      const tires = [
        { k: "FL", psi: "32.4", temp: "26°C", rssi: "-71 dBm", x: 36, y: 74 },
        { k: "FR", psi: "32.1", temp: "26°C", rssi: "-74 dBm", x: 424, y: 74 },
        { k: "RL", psi: "31.8", temp: "25°C", rssi: "-82 dBm", x: 36, y: 220 },
        { k: "RR", psi: "32.0", temp: "25°C", rssi: "-84 dBm", x: 424, y: 220 },
      ];
      for (const t of tires) {
        ctx.fillStyle = "#131f35";
        ctx.strokeStyle = "#2dd4bf";
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.roundRect(t.x, t.y, 180, 118, 10);
        ctx.fill();
        ctx.stroke();
        ctx.fillStyle = "#94a3b8";
        ctx.font = "bold 16px monospace";
        ctx.fillText(`${t.k} · EG53MA4`, t.x + 14, t.y + 26);
        ctx.fillStyle = "#f8fafc";
        ctx.font = "bold 36px monospace";
        ctx.fillText(`${t.psi}`, t.x + 14, t.y + 72);
        ctx.fillStyle = "#2dd4bf";
        ctx.font = "bold 15px monospace";
        ctx.fillText("PSI", t.x + 120, t.y + 72);
        ctx.fillStyle = "#64748b";
        ctx.font = "14px monospace";
        ctx.fillText(`${t.temp} · ${t.rssi}`, t.x + 14, t.y + 102);
      }

      // Center car outline + L/R blind-spot status pills
      ctx.strokeStyle = "#475569";
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.roundRect(268, 92, 104, 224, 24);
      ctx.stroke();
      ctx.fillStyle = status.occL ? "#f59e0b" : "#1e293b";
      ctx.fillRect(230, 160, 26, 110);
      ctx.fillStyle = status.occR ? "#f59e0b" : "#1e293b";
      ctx.fillRect(384, 160, 26, 110);

      ctx.fillStyle = "#cbd5e1";
      ctx.font = "bold 14px monospace";
      ctx.textAlign = "center";
      ctx.fillText("YARIS iA", 320, 200);
      ctx.fillStyle = status.occL || status.occR ? "#fbbf24" : "#4ade80";
      ctx.fillText(status.occL || status.occR ? "BSM ACTIVE" : "BSM CLEAR", 320, 225);
      ctx.textAlign = "left";
    }

    hudTex.needsUpdate = true;
    // Also mirror into 2D HUD preview canvas if visible in DOM
    const preview = document.getElementById("hud-preview-canvas");
    if (preview && !preview.hidden) {
      const pctx = preview.getContext("2d");
      pctx.drawImage(hudCanvas, 0, 0, preview.width, preview.height);
    }
  }

  function update(dt, nowMs) {
    // Auto-drive target vehicle smoothly through blind spot (-7.0 m to +2.0 m)
    if (sim.autoDrive && sim.targetType !== "none") {
      sim.targetY += dt * 1.45;
      if (sim.targetY > 2.2) sim.targetY = -7.0;
    }

    target.group.visible = sim.targetType !== "none";
    target.carG.visible = sim.targetType === "car";
    target.motoG.visible = sim.targetType === "motorcycle";
    target.group.position.set(sim.targetSide === "L" ? -2.12 : 2.12, sim.targetY, 0);

    // Blind-spot occupancy test against calibrated ROI (-5.65 m to +0.55 m)
    const inRoi = sim.targetType !== "none" && sim.targetY >= -5.65 && sim.targetY <= 0.65;
    const occL = inRoi && sim.targetSide === "L";
    const occR = inRoi && sim.targetSide === "R";

    const blinkL = sim.blinker === "L" || sim.blinker === "HAZARD";
    const blinkR = sim.blinker === "R" || sim.blinker === "HAZARD";
    const hazard = sim.blinker === "HAZARD";
    const speedGateOk = sim.speedMph >= 12;

    const dangerL = occL && sim.blinker === "L" && speedGateOk && !hazard;
    const dangerR = occR && sim.blinker === "R" && speedGateOk && !hazard;
    const danger = dangerL || dangerR;

    // 1.5 Hz exterior turn-signal flash
    const blinkPhase = Math.floor(nowMs / 333) % 2 === 0;
    blinkerMats.L.emissiveIntensity = blinkL && blinkPhase ? 2.4 : 0.05;
    blinkerMats.R.emissiveIntensity = blinkR && blinkPhase ? 2.4 : 0.05;

    // Door-sail LEDs, amber only: steady when the lane is occupied, flashing when you signal towards it
    const flash = Math.floor(nowMs / 160) % 2 === 0;
    const updateLed = (side, occ, dng) => {
      const mat = ledMats[side];
      if (dng) {
        mat.color.setHex(0xf59e0b);
        mat.emissive.setHex(0xf59e0b);
        mat.emissiveIntensity = flash ? (sim.nightMode ? 2.2 : 4.2) : 0.1;
      } else if (occ && speedGateOk) {
        mat.color.setHex(0xf59e0b);
        mat.emissive.setHex(0xf59e0b);
        mat.emissiveIntensity = sim.nightMode ? 1.1 : 2.2;
      } else {
        mat.color.setHex(0x334155);
        mat.emissiveIntensity = 0.0;
      }
    };
    updateLed("L", occL, dangerL);
    updateLed("R", occR, dangerR);

    // ROI floor zone colors
    roiMatL.color.setHex(dangerL ? 0xef4444 : (occL ? 0xf59e0b : 0x22c55e));
    roiMatL.opacity = dangerL ? 0.38 : (occL ? 0.28 : 0.14);
    roiMatR.color.setHex(dangerR ? 0xef4444 : (occR ? 0xf59e0b : 0x22c55e));
    roiMatR.opacity = dangerR ? 0.38 : (occR ? 0.28 : 0.14);
    coneMatL.color.setHex(dangerL ? 0xef4444 : 0x06b6d4);
    coneMatR.color.setHex(dangerR ? 0xef4444 : 0x06b6d4);

    // Alert pod: triple beep when danger starts, repeated at most every 3 s (as AlertArbiter does)
    if (danger) {
      const pulse = (nowMs % 320) / 320;
      piezoMat.emissiveIntensity = pulse < 0.45 ? 3.5 : 0.2;
      piezoWave.material.opacity = Math.max(0, 0.85 - pulse * 1.1);
      const s = 1 + pulse * 3.8;
      piezoWave.scale.set(s, s, 1);
      if (!dangerWas || nowMs - lastDangerBeep >= 3000) {
        lastDangerBeep = nowMs;
        for (const d of [0, 0.14, 0.28]) playPiezoBeep(3000, 0.08, d);
      }
    } else {
      piezoMat.emissiveIntensity = 0.15;
      piezoWave.material.opacity = 0;
    }
    dangerWas = danger;

    // Subtle pulsing 315 MHz TPMS rings on wheels
    const rfPhase = (nowMs * 0.0014) % 1;
    for (let i = 0; i < rfRings.length; i++) {
      const p = (rfPhase + i * 0.25) % 1;
      const sc = 0.8 + p * 2.2;
      rfRings[i].ring.scale.set(sc, sc, 1);
      rfRings[i].ring.material.opacity = groupsVisible(harnesses.rf) ? (1 - p) * 0.65 : 0;
    }

    // Active camera display logic
    const activeCam = sim.blinker === "L" ? "L" : (sim.blinker === "R" ? "R" : null);
    const status = { occL, occR, dangerL, dangerR, danger, activeCam, speedGateOk, hazard };
    drawDisplayHud(nowMs, status);
    return status;
  }

  function groupsVisible(g) { return g.visible; }

  function setShellXray(on) {
    sim.xrayBody = on;
    shellMat.opacity = on ? 0.15 : 0.58;
    wireMat.opacity = on ? 0.55 : 0.35;
  }

  function setFovVisible(on) {
    sim.showFov = on;
    fovGroup.visible = on;
  }

  function setDimsVisible(on) {
    dimGroup.visible = on;
  }

  function setHarnessVisible(key, on) {
    if (harnesses[key]) harnesses[key].visible = on;
  }

  function setMountOption(opt) {
    sim.mountOption = opt;
    applyMountPosition();
  }

  function triggerTpmsChime() {
    // TPMS reminder: two longer beeps on the same piezo (the real one repeats at most every 10 min)
    playPiezoBeep(3000, 0.2, 0);
    playPiezoBeep(3000, 0.2, 0.35);
  }

  return {
    group,
    sim,
    pickables,
    update,
    setShellXray,
    setFovVisible,
    setDimsVisible,
    setHarnessVisible,
    setMountOption,
    triggerTpmsChime,
    playPiezoBeep,
  };
}
