import * as THREE from "three";
import { STLLoader } from "three/addons/STLLoader.js";

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

// Blind-spot zone and camera spec from the subsystem audit (05-Audit-Subsystems/08-cameras-and-vision.md).
// Zone: from the driver's seat (mid-wheelbase, y = 0) back to 3 m behind the bumper, 0.5-3.5 m out from the body
// side (ISO 17387 uses 0.5-3.0 m; 3.5 m covers a whole lane). Seen from the camera it spans 3.7-80.6 deg outward of
// straight back; with the car's side in the frame, 83 deg: hence HFOV >= 95 deg aimed ~39 deg outward.
const ZONE = { yNear: 0.0, yFar: DIMS.Y_TAIL - 3.0, xIn: DIMS.W / 2 + 0.5, xOut: DIMS.W / 2 + 3.5 };
const CAM = { hfovDeg: 95, yawDeg: 39, pitchDeg: 10, rangeM: 7.5 };

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
  const mirrors = {};

  // The lens's horizontal field of view on the road: a fan from the camera's ground point, HFOV wide, centred on the
  // aim, and its edges up to the lens. Rebuilt with the real lens position once the printed pods load.
  const fans = { L: [], R: [] };
  function makeFan(side, gx, gy, gz) {
    const sign = side === "L" ? -1 : 1;
    for (const o of fans[side]) {
      fovGroup.remove(o);
      o.geometry.dispose();
    }
    const a0 = CAM.yawDeg - CAM.hfovDeg / 2, a1 = CAM.yawDeg + CAM.hfovDeg / 2;
    const arc = [];
    for (let i = 0; i <= 24; i++) {
      const th = THREE.MathUtils.degToRad(a0 + (a1 - a0) * (i / 24));
      arc.push([gx + sign * Math.sin(th) * CAM.rangeM, gy - Math.cos(th) * CAM.rangeM, 0.01]);
    }
    const fanVerts = [];
    for (let i = 0; i < arc.length - 1; i++) fanVerts.push(gx, gy, 0.01, ...arc[i], ...arc[i + 1]);
    const fanGeo = new THREE.BufferGeometry();
    fanGeo.setAttribute("position", new THREE.BufferAttribute(new Float32Array(fanVerts), 3));
    const fan = new THREE.Mesh(fanGeo, side === "L" ? coneMatL : coneMatR);
    const apex = [gx, gy, gz];
    const edgeVerts = [...apex, ...arc[0], ...apex, ...arc[arc.length - 1]];
    for (let i = 0; i < arc.length - 1; i++) edgeVerts.push(...arc[i], ...arc[i + 1]);
    const coneEdgeGeo = new THREE.BufferGeometry();
    coneEdgeGeo.setAttribute("position", new THREE.BufferAttribute(new Float32Array(edgeVerts), 3));
    const edges = new THREE.LineSegments(coneEdgeGeo, new THREE.LineBasicMaterial({ color: 0x38bdf8, transparent: true, opacity: 0.42 }));
    fans[side] = [fan, edges];
    fovGroup.add(fan, edges);
  }

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

    // Turn-signal lamp material (bumper lamps below). The mirrors have LED turn-signal repeaters (Toyota feature pages,
    // owner's manual): their feed in each door is the planned blinker tap (premortem I1)
    const bMat = new THREE.MeshStandardMaterial({ color: 0x451a03, emissive: 0xf59e0b, emissiveIntensity: 0.05 });
    blinkerMats[side] = bMat;

    // USB UVC camera in the lower mirror cap, its barrel along the optical axis (audit CAM-02: ~39° outward of
    // straight back, ~10° down; a strip of the car's side at the inner edge of the picture)
    const cam = new THREE.Mesh(new THREE.CylinderGeometry(0.016, 0.019, 0.036, 16), camBodyMat);
    cam.position.set(mx + sign * 0.03, my - 0.01, mz - 0.072);
    const yaw = THREE.MathUtils.degToRad(CAM.yawDeg), pitch = THREE.MathUtils.degToRad(CAM.pitchDeg);
    const axis = new THREE.Vector3(sign * Math.sin(yaw) * Math.cos(pitch), -Math.cos(yaw) * Math.cos(pitch), -Math.sin(pitch));
    cam.quaternion.setFromUnitVectors(new THREE.Vector3(0, -1, 0), axis);
    cam.userData.pickId = `cam_${side}`;
    parent.add(cam);
    mirrors[side] = { housing, cam };

    pickables.push({
      id: `cam_${side}`,
      mesh: cam,
      title: `${side === "L" ? "Left (driver)" : "Right (passenger)"} mirror camera (USB UVC)`,
      category: "Mirror vision (BUY after the bench test)",
      source: "BUY (~$45 each)",
      location: `In a printed pod under the ${side === "L" ? "left" : "right"} mirror's cap, outer half, its lens face at the mirror's rear edge`,
      mount: `The pod (make_mounts.py) sets the aim: ${CAM.yawDeg}° outward of straight back, ${CAM.pitchDeg}° down; the camera's lip seats on the pod's lens face, a set screw and RTV hold it. Only the lead goes through the cap: one Ø21 mm hole and 2 × Ø3.4 mm from the printed drill guide. Practise on a spare cap. Keep a strip of the car's side in the frame: the Pi uses it to detect a folded or bumped mirror. Check with cones at the zone's four corners.`,
      wiring: `Acceptance: MJPEG 720p30 at full sensor width, HFOV ≥ ${CAM.hfovDeg}° measured (≥ 2.18 m of wall at 1 m), Starvis WDR, no IR LEDs, −20…+70 °C (+85 °C preferred), IP67, barrel ≤ 20 mm, ≥ 3.5 m lead, both cameras streaming at once on the Pi 4. Lead: service loop through the hinge → door harness → door boot → kick panel → the Pi's USB 2.0 port (no JST-GH in the data path).`,
    });

    makeFan(side, mx + sign * 0.03, my - 0.01, mz - 0.072);

    // Blind-spot zone painted on the road (ZONE): from the driver's seat back to 3 m behind the bumper,
    // 0.5-3.5 m out from the body side
    const zoneW = ZONE.xOut - ZONE.xIn, zoneL = ZONE.yNear - ZONE.yFar;
    const roi = new THREE.Mesh(
      new THREE.PlaneGeometry(zoneW, zoneL),
      side === "L" ? roiMatL : roiMatR
    );
    roi.position.set(sign * (ZONE.xIn + ZONE.xOut) / 2, (ZONE.yNear + ZONE.yFar) / 2, 0.015);
    fovGroup.add(roi);

    const roiOutline = new THREE.LineSegments(
      new THREE.EdgesGeometry(new THREE.PlaneGeometry(zoneW, zoneL)),
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

  return { fovGroup, roiMatL, roiMatR, coneMatL, coneMatR, blinkerMats, mirrors, makeFan };
}

function buildDisplayAndElectronics(parent, pickables) {
  // Live 1024x600 UI of the SunFounder TS-7, drawn into a CanvasTexture of the same shape
  const hudCanvas = document.createElement("canvas");
  hudCanvas.width = 640;
  hudCanvas.height = 375;
  const hudTex = new THREE.CanvasTexture(hudCanvas);
  hudTex.anisotropy = 4;

  // Printed enclosure (01-hardware/enclosure/enclosure_report.json): bezel + plate 205.6 x 129.0 x 19.75 mm in front
  // of the trim, rear box 112 x 124 x 50.5 mm behind it with the Pi 4 on four posts and the carrier PCB on four more.
  // Group frame: X right, Y = depth (the screen faces -Y, toward the driver), Z up; origin at the bezel's centre.
  // The display sits 8 mm toward the driver, so its HDMI and micro-USB plugs fit on its right.
  const displayGroup = new THREE.Group();
  const plastic = new THREE.MeshStandardMaterial({ color: 0x1f2937, roughness: 0.72, metalness: 0.05 });
  const bezel = new THREE.Mesh(new THREE.BoxGeometry(0.2056, 0.01975, 0.129), plastic);
  bezel.userData.pickId = "rpi_display";
  displayGroup.add(bezel);

  const screenPlane = new THREE.Mesh(new THREE.PlaneGeometry(0.1542, 0.0859), new THREE.MeshBasicMaterial({ map: hudTex }));
  screenPlane.rotation.set(Math.PI / 2, 0, 0); // normal toward -Y (driver), texture top = +Z (up), right = +X
  screenPlane.position.set(-0.0092, -0.0102, 0.0027);
  screenPlane.userData.pickId = "rpi_display";
  displayGroup.add(screenPlane);

  const boxMat = new THREE.MeshStandardMaterial({ color: 0x475569, roughness: 0.7, transparent: true, opacity: 0.45, depthWrite: false });
  const rearBox = new THREE.Mesh(new THREE.BoxGeometry(0.112, 0.0505, 0.124), boxMat);
  rearBox.position.set(0, 0.03513, -0.0015);
  rearBox.userData.pickId = "enclosure_box";
  displayGroup.add(rearBox);

  const rpi4 = new THREE.Mesh(new THREE.BoxGeometry(0.085, 0.0184, 0.056), new THREE.MeshStandardMaterial({ color: 0x15803d, roughness: 0.45 }));
  rpi4.position.set(0.008, 0.02407, -0.008);
  rpi4.userData.pickId = "rpi4_sbc";
  displayGroup.add(rpi4);

  const pcb6 = new THREE.Mesh(
    new THREE.BoxGeometry(0.100, 0.0016, 0.100),
    new THREE.MeshStandardMaterial({ color: 0x059669, emissive: 0x047857, emissiveIntensity: 0.35, roughness: 0.35 })
  );
  pcb6.position.set(0, 0.03958, 0.0045);
  pcb6.userData.pickId = "pcb6_carrier";
  displayGroup.add(pcb6);

  const fan = new THREE.Mesh(new THREE.BoxGeometry(0.030, 0.010, 0.030), new THREE.MeshStandardMaterial({ color: 0x111827 }));
  fan.position.set(0.005, 0.05287, 0.0085);
  displayGroup.add(fan);

  parent.add(displayGroup);

  pickables.push(
    {
      id: "rpi_display",
      mesh: bezel,
      title: "Printed enclosure + SunFounder TS-7 7\" display",
      category: "Display + enclosure",
      source: "INVENTORY display (SunFounder TS-7, 1024 × 600 IPS) + printed parts",
      location: "Option A: in front of the console opening, rear box in the pocket · Option B: dash top on a RAM / AMPS base",
      mount: "The display hangs by its four ears on bosses in the bezel (M3 × 6 from behind); the lip covers 2 mm of the glass, 0.3 mm clear of it. Normal way up (IPS). 205.6 × 129.0 × 70.3 mm, 21.8 mm proud of the trim, plus the USB wing on its right edge; make_enclosure.py checks every fit. Measure the display first: SunFounder lists 121 mm tall, its photos ~124.4.",
      wiring: "HDMI flat cable and a split micro-USB lead (5 V from J5, touch data to a Pi USB port) leave the display's right edge, go back through the plate's cable slot and into the box. Inside: the Pi on 4 posts, the carrier PCB behind it, and the 12 V piezo behind the right slots. Air: slots beside the screen → behind the display → lid fan. Cameras plug into the Pi through the box window (90° adapters); harness through the lid grommet; antenna on an SMA bulkhead.",
    },
    {
      id: "enclosure_box",
      mesh: rearBox,
      title: "Rear box: Pi 4 + carrier PCB + 30 mm fan",
      category: "Printed enclosure",
      source: "ASA / ABS print (never PLA) or MJF PA12",
      location: "Behind the display; in Option A it drops into the console pocket (needs ≥ 56 mm clear depth)",
      mount: "112 × 124 mm, 50.5 mm deep behind the plate. 2 mm bumps on the plate let the fan's air out round the bezel, so the pocket is never sealed. AMPS 30 × 38 M4 nuts in the bottom wall.",
      wiring: "Thermal test T1 in a sun-soaked car: SoC < 80 °C and get_throttled 0x0, or lower the clock / move the PCB to its own box.",
    },
    {
      id: "rpi4_sbc",
      mesh: rpi4,
      title: "Raspberry Pi 4 Model B (vision + UI)",
      category: "Compute (INVENTORY)",
      source: "INVENTORY (2 in the lab; needs ≥ 2 GB)",
      location: "On 4 posts behind the plate, inside the rear box; ports to the driver's right, HDMI / USB-C edge on top",
      mount: "Heatsinks; the lid fan pulls air past it. GPIO plugs 90° / low profile (height budget).",
      wiring: "Bookworm with a read-only root, overlay FS, watchdog. HDMI0 → the TS-7 (1024 × 600 on HDMI-A-1), touch over USB. Two UVC streams, 320 × 320 detector; talks to the ESP32 over its GPIO UART (checksummed $BSM / $ESP / $TPM lines).",
    },
    {
      id: "pcb6_carrier",
      mesh: pcb6,
      title: "100 × 100 mm 6-layer carrier PCB (ESP32 + CC1101 + power)",
      category: "Custom PCB, rev A (routed, DRC clean)",
      source: "JLCPCB 6-layer + Economic PCBA (promo price to confirm)",
      location: "Inside the rear box, on 4 posts behind the Pi; parts face the lid",
      mount: "4 × M3 on 92 × 92 into the housing's posts. Its underside is 3 mm above the Pi's tallest part. The real board with every part: 3. Printed Parts → Dash unit (see-through shell).",
      wiring: "12 V ACC in (J1): 4 A fuse, SMCJ24CA, SUD50P06 P-FET (reverse battery), π filter → two TPS54560B bucks: 5V_PI 5.17 V / 5 A for the Pi and the display (J5), 5V_ESP 1 A for the DevKit; XC6206 → 3V3. INA226 monitors, blinker optos, LED / piezo / fan drivers. ESP32 pins from pins_v2.h (audited).",
    }
  );

  // Amber blind-spot LEDs on the inner door sails (door side, not the A-pillar trim: curtain airbag)
  const ledMats = {};
  const ledMeshes = {};
  for (const side of ["L", "R"]) {
    const sign = side === "L" ? -1 : 1;
    const mat = new THREE.MeshStandardMaterial({ color: 0x334155, emissive: 0xf59e0b, emissiveIntensity: 0.0, roughness: 0.2 });
    const m = new THREE.Mesh(new THREE.SphereGeometry(0.016, 16, 16), mat);
    m.position.set(sign * 0.70, 0.52, 0.97);
    m.userData.pickId = `door_led_${side}`;
    parent.add(m);
    ledMats[side] = mat;
    ledMeshes[side] = m;
    pickables.push({
      id: `door_led_${side}`,
      mesh: m,
      title: `${side === "L" ? "Left" : "Right"} amber blind-spot LED (inner door sail)`,
      category: "Visual alert",
      source: "BUY (amber 5 mm + bezel)",
      location: `Inside the ${side === "L" ? "driver's" : "passenger's"} door, at the mirror's base, facing the driver`,
      mount: "In a small printed pod on the door's inner sail (make_mounts.py), inside the cabin, aimed at the driver's eyes; the LED sits 3 mm deep so no light reaches the side window or the windscreen. VHB + a Ø4 mm wire hole. Not in the A-pillar trim (the Yaris iA has side-curtain airbags behind it) and not on the outside of the mirror (an amber light seen from behind isn't allowed). The wires ride with the camera cable through the door boot.",
      wiring: `Low-side MOSFET on ${side === "L" ? "IO25" : "IO14"}. Steady = vehicle in the blind spot; flashing = you are signalling towards it. PWM level from the Pi (night dimming).`,
    });
  }

  // 12 V piezo inside the dash unit, behind the bezel's right intake slots: the ring in front of the slots shows its
  // beeps (moved onto the real spot once the STLs load)
  const piezoMat = new THREE.MeshStandardMaterial({ color: 0xe11d48, emissive: 0xf43f5e, emissiveIntensity: 0.15 });
  const piezoWave = new THREE.Mesh(
    new THREE.RingGeometry(0.012, 0.02, 24),
    new THREE.MeshBasicMaterial({ color: 0xf43f5e, transparent: true, opacity: 0.0, side: THREE.DoubleSide, depthWrite: false })
  );
  piezoWave.rotation.x = Math.PI / 2;                       // faces the driver (-Y)
  piezoWave.position.set(0.0874, -0.0111, -0.0166);
  piezoWave.userData.pickId = "dash_piezo";
  displayGroup.add(piezoWave);

  // USB wing on the bezel's right edge: the car's USB socket, facing the passenger (stand-in box until the STL loads)
  const wing = new THREE.Mesh(new THREE.BoxGeometry(0.0279, 0.0344, 0.0418), plastic);
  wing.position.set(0.1168, -0.0053, 0.043);
  wing.userData.pickId = "usb_wing";
  displayGroup.add(wing);

  pickables.push(
    {
      id: "dash_piezo",
      mesh: piezoWave,
      title: "12 V active piezo (inside the dash unit)",
      category: "Audio alert",
      source: "BUY (12 V active piezo, ~23 mm)",
      location: "Inside the bezel's right cavity, below the display's plugs, firing through the right intake slots",
      mount: "Three printed fingers on the bezel's skin hold it with its face 2 mm behind the slots (the cabin air still flows); a dab of RTV. No separate pod, no physical button: mute from the touch screen.",
      wiring: "The carrier's 4-pin buzzer JST-GH: IO13 low-side MOSFET from 12 V (the button pins, IO4, stay unused). Danger: a short triple beep, repeated after 3 s, then quiet after 4 s while the door LED keeps flashing; it re-arms after 2 s clear or a new signal. TPMS: two reminders, then only the screen. Hazards silent; quiet below 8 mph.",
    },
    {
      id: "usb_wing",
      mesh: wing,
      title: "USB wing: the car's USB socket, moved to the unit's side",
      category: "Printed part + the v1 USB passthrough",
      source: "PRINT (make_enclosure.py: print_usb_wing) + the v1 panel-mount USB extension",
      location: "On the trim against the bezel's right (passenger) edge; the socket faces the passenger, its end ~36 mm right of the bezel",
      mount: "2 × M3 × 10 from inside the bezel's right cavity into its tabs, VHB on its back to the trim. The v1 panel's Ø25.8 cut; its front wall holds the nut, so the socket tightens from outside.",
      wiring: "Its cable enters the bezel through the side wall behind the wing, crosses above the display's plugs and drops through the plate's cable slot into the pocket, to the car's own USB port. Measure your passthrough before printing (enclosure README).",
    }
  );

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
    mount: "One Add-A-Circuit (5 A) on a non-critical ACC fuse, metered first: hot in ACC and ON, dead with the key out; never an SRS or engine fuse. Ring terminal on a chassis ground stud. Turn-signal sense comes from the mirror repeater feeds in the doors (fallback: here, found with the wiring diagram and a meter).",
    wiring: "ACC only: zero draw when parked. The OBD-II port nearby takes your Bluetooth dongle (optional speed source); listening to CAN is phase 2 (USB adapter on the Pi, listen-only).",
  });

  return {
    displayGroup, hudCanvas, hudTex, ledMats, piezoMat, piezoWave,
    prims: { bezel, screenPlane, rearBox, rpi4, pcb6, fan, ledMeshes, wing, plastic },
  };
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

  // Door-sail LEDs ride with the camera cables through the door boots (the piezo is inside the dash unit)
  const ledL = makeTube([
    [-0.70, 0.52, 0.97], [-0.785, 0.51, 0.86], [-0.775, 0.53, 0.66], [-0.785, 0.62, 0.62],
    [-0.735, 0.66, 0.68], [-0.675, 0.64, 0.64], [-0.42, 0.61, 0.69], [-0.12, 0.57, 0.63], [-0.02, 0.535, 0.625],
  ], 0.0055, 0xe879f9);
  const ledR = makeTube([
    [0.70, 0.52, 0.97], [0.785, 0.51, 0.86], [0.775, 0.53, 0.66], [0.785, 0.62, 0.62],
    [0.735, 0.66, 0.68], [0.675, 0.64, 0.64], [0.42, 0.61, 0.68], [0.12, 0.57, 0.64], [0.02, 0.535, 0.625],
  ], 0.0055, 0xe879f9);
  ledL.userData.pickId = "harness_alerts";
  ledR.userData.pickId = "harness_alerts";
  groups.alerts.add(ledL, ledR);

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
      wiring: "On the board: 4 A fuse, SMCJ24CA, SUD50P06 P-FET reverse protection, π filter. No latch, no battery feed: everything is off with the key out.",
    },
    {
      id: "harness_sig", mesh: sigBlinker, title: "Turn-signal sense (2 × 22 AWG)",
      category: "Vehicle signals", source: "BUY PC817 (on the board)",
      location: "Each mirror's LED turn-signal repeater feed, inside the door at the mirror connector → with the camera cable through the door boot → carrier JST-GH",
      mount: "Solder + heat-shrink (no T-taps) on the repeater feed, found with the wiring diagram and metered: flashing 12 V with that side's signal and the hazards. Fallbacks: kick-panel feed, rear amber WY21W bulbs.",
      wiring: "PC817 optos (~6 mA each) → IO36 / IO39, polled at 1 kHz; PWM gaps bridged, spikes ignored, hazards = both lamps lit together ≥ 50 ms, an input lit > 1.5 s is flagged as a fault. Not from OBD-II: standard OBD-II has no turn-signal data (a CAN cross-check is phase 2).",
    },
    {
      id: "harness_alerts", mesh: ledL, title: "Door LED leads",
      category: "Alert harness", source: "BUY LEDs",
      location: "Carrier → door boots → inner door sails",
      mount: "The LED pairs ride with the camera cables through the door boots; nothing in the A-pillar trim.",
      wiring: "LEDs on IO25 / IO14 (PWM, low-side MOSFETs). The piezo needs no lead out: it sits inside the dash unit on the carrier's 4-pin buzzer JST-GH (IO13, 12 V; the button pins stay unused).",
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

// The real printed parts (01-hardware/enclosure: make_enclosure.py and make_mounts.py) replace the stand-in boxes
// once their STL files load; if they don't load, the boxes stay.
const ENC_DIR = "../../01-hardware/enclosure/";
const MM = 0.001;

async function loadPrintedParts(parent, pickables, disp, mir) {
  const stl = new STLLoader();
  const get = async (url) => {
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) throw new Error(`${url}: HTTP ${res.status}`);
    return res;
  };
  const geo = async (rel) => {
    const g = stl.parse(await (await get(ENC_DIR + rel)).arrayBuffer());
    g.scale(MM, MM, MM);
    g.computeVertexNormals();
    return g;
  };
  const rot = (r) => new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().set(
    r[0][0], r[0][1], r[0][2], 0, r[1][0], r[1][1], r[1][2], 0, r[2][0], r[2][1], r[2][2], 0, 0, 0, 0, 1));
  const [enc, mr] = await Promise.all([(await get(ENC_DIR + "enclosure_report.json")).json(),
    (await get(ENC_DIR + "mounts_report.json")).json()]);
  const { prims } = disp;
  const plastic = prims.plastic;

  // Dash unit: the generator's assembly frame (PCB centre, parts up +Z) -> the display group (X right, Y depth with
  // the screen toward -Y, Z up; origin at the bezel's centre, mid-way through the bezel + plate)
  const fv = enc.front_view_mm, zl = enc.z_levels_mm;
  const [cx, cy] = enc.viewer_frame.pcb_center_mm;
  const cz = enc.viewer_frame.z_mid_mm;
  const bx = (fv.bezel[0] + fv.bezel[1]) / 2, bz = (fv.bezel[2] + fv.bezel[3]) / 2;
  const yMid = -(zl.lip_front + zl.plate_back) / 2;
  const asm = new THREE.Group();
  new THREE.Matrix4().set(-1, 0, 0, (cx - bx) * MM, 0, 0, 1, (-cz - yMid) * MM, 0, 1, 0, (cy - bz) * MM, 0, 0, 0, 1)
    .decompose(asm.position, asm.quaternion, asm.scale);
  const shell = new THREE.MeshStandardMaterial({ color: 0x334155, roughness: 0.72, transparent: true, opacity: 0.5, depthWrite: false });
  const dash = [
    ["bezel", plastic, "rpi_display"], ["housing", shell, "enclosure_box"], ["lid", shell, "enclosure_box"],
    ["display", new THREE.MeshStandardMaterial({ color: 0x0b1220, roughness: 0.4 }), "rpi_display"],
    ["cables", new THREE.MeshStandardMaterial({ color: 0xf97316, roughness: 0.5 }), "rpi_display"],
    ["pi", new THREE.MeshStandardMaterial({ color: 0x15803d, roughness: 0.45 }), "rpi4_sbc"],
    ["pcb", prims.pcb6.material, "pcb6_carrier"],
    ["pcb_parts", new THREE.MeshStandardMaterial({ color: 0x1e293b, roughness: 0.5 }), "pcb6_carrier"],
    ["fan", new THREE.MeshStandardMaterial({ color: 0x111827 }), "enclosure_box"],
    ["buzzer", disp.piezoMat, "dash_piezo"],
    ["usb_wing", plastic, "usb_wing"],
    ["usb_pass", new THREE.MeshStandardMaterial({ color: 0x94a3b8, metalness: 0.6, roughness: 0.35 }), "usb_wing"],
  ];
  const dashGeos = await Promise.all(dash.map(([n]) => geo(enc.files[`asm_${n}`].file)));
  dash.forEach(([, mat, id], k) => {
    const m = new THREE.Mesh(dashGeos[k], mat);
    m.userData.pickId = id;
    asm.add(m);
  });
  disp.displayGroup.add(asm);
  for (const p of [prims.bezel, prims.rearBox, prims.rpi4, prims.pcb6, prims.fan, prims.wing]) p.visible = false;
  prims.screenPlane.position.y = -(yMid * MM) - 0.0002;        // just in front of the glass, behind the bezel's lip
  const [pzx, pzy] = fv.buzzer;                                // the beep ring: in front of the slots over the piezo
  disp.piezoWave.position.set((pzx - bx) * MM, (-zl.lip_front - yMid) * MM - 0.0012, (pzy - bz) * MM);

  // Mirror camera pods: cap face on the mirror's underside (+ the VHB), outer half, lens face 4 mm behind the glass
  const cp = mr.camera_pod, rp = cp.right_pod_mm;
  const [podL, podR, camL, camR] = await Promise.all(["asm_cam_pod_left", "asm_cam_pod_right", "asm_cam_left", "asm_cam_right"]
    .map((k) => geo(mr.files[k].file)));
  const camMat = new THREE.MeshStandardMaterial({ color: 0x0f172a, roughness: 0.35, metalness: 0.4 });
  for (const side of ["L", "R"]) {
    const s = side === "L" ? -1 : 1;
    const { housing, cam } = mir.mirrors[side];
    const g = new THREE.Group();
    g.quaternion.copy(rot(cp.frame_to_car[side === "L" ? "left" : "right"]));
    const lens = new THREE.Vector3(s * rp.lens_centre[0], rp.lens_centre[1], rp.lens_centre[2]).multiplyScalar(MM)
      .applyQuaternion(g.quaternion);
    const hp = housing.position, hb = housing.geometry.parameters;
    g.position.set(hp.x + s * 0.03, hp.y - hb.height / 2 - 0.004 - lens.y, hp.z - hb.depth / 2 - mr.parameters.VHB_T * MM);
    const pod = new THREE.Mesh(side === "L" ? podL : podR, plastic);
    pod.userData.pickId = `cam_pod_${side}`;
    const camM = new THREE.Mesh(side === "L" ? camL : camR, camMat);
    camM.userData.pickId = `cam_${side}`;
    g.add(pod, camM);
    parent.add(g);
    cam.visible = false;
    const lw = lens.clone().add(g.position);
    mir.makeFan(side, lw.x, lw.y, lw.z);
    pickables.push({
      id: `cam_pod_${side}`,
      mesh: pod,
      title: `${side === "L" ? "Left" : "Right"} mirror camera pod (printed)`,
      category: "Printed mount (make_mounts.py)",
      source: "PRINT (ASA / ABS, cap face down, no supports)",
      location: `Under the mirror's cap, outer half: ${cp.size_mm.join(" × ")} mm, ${cp.below_cap_mm} mm below the cap`,
      mount: `${cp.cap_holes.screw}. Cap: ${cp.cap_holes.cable}; ${cp.cap_holes.screws}. Its flat side faces the car.`,
      wiring: `Aims the camera ${cp.aim_deg.outward_of_straight_back}° outward of straight back, ${cp.aim_deg.down}° down (audit CAM-02). The lead climbs a Ø${mr.parameters.PLUG_PASS_D} mm channel into the mirror, then the hinge, the door and the door boot. See 3. Printed Parts → Mirror cameras.`,
    });
  }

  // Door-sail LED pods: base on the sail at at_m, the LED (driven by the door LED's material) aimed at the eyes
  for (const side of ["L", "R"]) {
    const key = side === "L" ? "left" : "right";
    const L = mr.led_pods[key];
    const [pg, lg] = await Promise.all([geo(mr.files[`asm_led_pod_${key}`].file), geo(mr.files[`asm_led_${key}`].file)]);
    const g = new THREE.Group();
    g.quaternion.copy(rot(L.frame_to_car));
    g.position.set(...L.at_m);
    const pod = new THREE.Mesh(pg, plastic);
    const led = new THREE.Mesh(lg, disp.ledMats[side]);
    pod.userData.pickId = `door_led_${side}`;
    led.userData.pickId = `door_led_${side}`;
    g.add(pod, led);
    parent.add(g);
    prims.ledMeshes[side].visible = false;
  }
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
  const { fovGroup, roiMatL, roiMatR, coneMatL, coneMatR, blinkerMats, mirrors, makeFan } = buildMirrorsAndCameras(group, pickables);
  const { displayGroup, hudCanvas, hudTex, ledMats, piezoMat, piezoWave, prims } = buildDisplayAndElectronics(group, pickables);
  const harnesses = buildHarnesses(group, pickables);
  const target = buildTargetVehicle(group);
  const dimGroup = buildBlueprintDimensions(group);
  loadPrintedParts(group, pickables, { displayGroup, ledMats, piezoMat, piezoWave, prims }, { mirrors, makeFan })
    .catch((err) => console.warn(`car scene: printed parts not loaded, keeping the stand-ins (${err.message})`));

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
  let lastDangerBeep = -1e9;
  // Danger episodes mute themselves, as AlertArbiter does: one starts with a new turn signal, or when the danger comes
  // back after 2 s without it; it beeps at once, again 3 s later, and is quiet from 4 s on (the door LED keeps flashing)
  let lastBlinker = "OFF", activation = 0, episodeActivation = -1, episodeStart = -1e9, dangerLast = -1e9, episodeBeeped = false;
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
      displayGroup.position.set(0, 0.433, 0.6583);
      displayGroup.rotation.set(-0.32, 0, 0);
    } else {
      // Option B: dash top on a RAM / AMPS base beside the factory screen
      displayGroup.position.set(-0.22, 0.59, 1.045);
      displayGroup.rotation.set(-0.14, 0, 0.16);
    }
  }
  applyMountPosition();

  // Draw the live HUD of the 7" TS-7 (TPMS + automatic mirror camera / YOLO bounding box)
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

    // Blind-spot occupancy: any part of the target inside the zone (ZONE, the painted area)
    const halfLen = sim.targetType === "car" ? 2.15 : 1.05;
    const inRoi = sim.targetType !== "none" && sim.targetY - halfLen <= ZONE.yNear && sim.targetY + halfLen >= ZONE.yFar;
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

    // Piezo (inside the dash unit): a triple beep when a danger episode starts, once more after 3 s, then quiet
    if (sim.blinker !== lastBlinker) {
      if (sim.blinker === "L" || sim.blinker === "R") activation++;
      lastBlinker = sim.blinker;
    }
    if (danger) {
      if (activation !== episodeActivation || nowMs - dangerLast >= 2000) {
        episodeActivation = activation;
        episodeStart = nowMs;
        episodeBeeped = false;
      }
      dangerLast = nowMs;
    }
    const autoMuted = nowMs - episodeStart >= 4000;
    if (danger && !autoMuted) {
      const pulse = (nowMs % 320) / 320;
      piezoMat.emissiveIntensity = pulse < 0.45 ? 3.5 : 0.2;
      piezoWave.material.opacity = Math.max(0, 0.85 - pulse * 1.1);
      const s = 1 + pulse * 3.8;
      piezoWave.scale.set(s, s, 1);
      if (nowMs - lastDangerBeep >= (episodeBeeped ? 3000 : 1000)) {
        lastDangerBeep = nowMs;
        episodeBeeped = true;
        for (const d of [0, 0.14, 0.28]) playPiezoBeep(3000, 0.08, d);
      }
    } else {
      piezoMat.emissiveIntensity = 0.15;
      piezoWave.material.opacity = 0;
    }

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
    const status = { occL, occR, dangerL, dangerR, danger, activeCam, speedGateOk, hazard, beepMuted: danger && autoMuted };
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
    // TPMS warning: two longer beeps on the same piezo (the real one reminds twice, 10 min apart, then only the screen)
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
