// Live RF Bench UI module for 04-viewer: USRP B205mini TX + ESP32/E07-M1101D RX telemetry.

function esc(s) {
  return String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function buildPayloadBytes(idHex, psi, tempF, flagsHex) {
  const sensorId = (parseInt(idHex, 16) || 0x123456) & 0xffffff;
  const flags = (parseInt(flagsHex, 16) || 0x058f2001) >>> 0;
  const kpa = Number(psi) * 6.894757;
  const pRaw = Math.max(0, Math.min(255, Math.round(kpa / 2.5)));
  const tRaw = Math.max(0, Math.min(255, Math.round(Number(tempF))));
  const b = [
    (flags >>> 24) & 0xff,
    (flags >>> 16) & 0xff,
    (flags >>> 8) & 0xff,
    flags & 0xff,
    (sensorId >>> 16) & 0xff,
    (sensorId >>> 8) & 0xff,
    sensorId & 0xff,
    pRaw,
    tRaw,
    0,
  ];
  b[9] = b.slice(0, 9).reduce((a, v) => a + v, 0) & 0xff;
  return b;
}

function encodeEg53Chips(bytes) {
  const bits = new Array(40).fill(0);
  for (const byte of bytes) {
    for (let s = 7; s >= 0; s--) bits.push((byte >>> s) & 1);
  }
  const chips = [];
  for (const bit of bits) {
    chips.push(bit, bit ^ 1);
  }
  while (chips.length && chips[0] === 0) chips.shift();
  while (chips.length && chips[chips.length - 1] === 0) chips.pop();
  return chips;
}

function drawRssiChart(canvas, history) {
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const w = canvas.width;
  const h = canvas.height;
  ctx.clearRect(0, 0, w, h);

  ctx.fillStyle = "#090d14";
  ctx.fillRect(0, 0, w, h);

  const padL = 42, padR = 12, padT = 12, padB = 22;
  const pw = w - padL - padR;
  const ph = h - padT - padB;
  const minDb = -110, maxDb = -20;
  const yOf = (db) => padT + ph * (1 - (Math.max(minDb, Math.min(maxDb, db)) - minDb) / (maxDb - minDb));

  ctx.font = "10px ui-monospace, monospace";
  ctx.lineWidth = 1;
  for (const db of [-100, -80, -60, -40, -20]) {
    const y = Math.round(yOf(db)) + 0.5;
    ctx.strokeStyle = db === -100 ? "rgba(47, 179, 68, 0.35)" : "rgba(147, 163, 186, 0.14)";
    ctx.beginPath();
    ctx.moveTo(padL, y);
    ctx.lineTo(w - padR, y);
    ctx.stroke();
    ctx.fillStyle = db === -100 ? "#69db7c" : "#7e90aa";
    ctx.fillText(`${db}`, 6, y + 3);
  }
  ctx.fillStyle = "#69db7c";
  ctx.fillText("-100 dBm goal", w - padR - 86, yOf(-100) - 4);

  if (!history || !history.length) {
    ctx.fillStyle = "#7e90aa";
    ctx.font = "12px system-ui, sans-serif";
    ctx.fillText("Connect ESP32 serial to stream live CC1101 RSSI & GDO2 carrier sense...", padL + 16, padT + ph / 2);
    return;
  }

  const n = history.length;
  const stepX = n > 1 ? pw / (n - 1) : pw;

  // Draw TX active bands and GDO2=1 bottom bar
  for (let i = 0; i < n; i++) {
    const x = padL + i * stepX;
    const pt = history[i];
    if (pt.tx_active) {
      ctx.fillStyle = "rgba(240, 77, 16, 0.22)";
      ctx.fillRect(x - stepX * 0.5, padT, Math.max(3, stepX), ph);
    }
    if (pt.gdo2) {
      ctx.fillStyle = "rgba(47, 179, 68, 0.55)";
      ctx.fillRect(x - stepX * 0.5, h - padB + 4, Math.max(2, stepX), 6);
    }
  }

  // RSSI trace
  ctx.strokeStyle = "#38bdf8";
  ctx.lineWidth = 2;
  ctx.beginPath();
  history.forEach((pt, i) => {
    const x = padL + i * stepX;
    const y = yOf(pt.rssi ?? -110);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();

  // Latest sample marker
  const last = history[n - 1];
  const lx = padL + (n - 1) * stepX;
  const ly = yOf(last.rssi ?? -110);
  ctx.fillStyle = "#7dd3fc";
  ctx.beginPath();
  ctx.arc(lx, ly, 3.5, 0, Math.PI * 2);
  ctx.fill();

  ctx.fillStyle = "#93a3ba";
  ctx.font = "10px ui-monospace, monospace";
  ctx.fillText("GDO2=1", 6, h - padB + 11);
  ctx.fillText(`${history[0].ts}  ->  ${last.ts}`, padL + 8, h - 6);
}

function drawWaveform(canvas, metaEl, bytes, labelPrefix) {
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const w = canvas.width;
  const h = canvas.height;
  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = "#090d14";
  ctx.fillRect(0, 0, w, h);

  const chips = encodeEg53Chips(bytes);
  const hex = bytes.map((v) => v.toString(16).toUpperCase().padStart(2, "0")).join("");
  if (metaEl) {
    metaEl.textContent = `${labelPrefix} · 120 bits (${chips.length} chips @ 123 µs) · payload ${hex} · sum8=0x${bytes[9].toString(16).toUpperCase().padStart(2, "0")}`;
  }

  const padL = 12, padR = 12, padT = 20, padB = 18;
  const pw = w - padL - padR;
  const yHigh = padT + 6;
  const yLow = h - padB - 4;
  const dx = pw / Math.max(1, chips.length);

  // Region shading: preamble (first ~80 chips) vs 80-bit payload
  const preEnd = Math.min(chips.length, 79);
  ctx.fillStyle = "rgba(56, 189, 248, 0.08)";
  ctx.fillRect(padL, padT, preEnd * dx, yLow - yHigh + 8);
  ctx.fillStyle = "rgba(240, 77, 16, 0.07)";
  ctx.fillRect(padL + preEnd * dx, padT, (chips.length - preEnd) * dx, yLow - yHigh + 8);

  ctx.font = "10px ui-monospace, monospace";
  ctx.fillStyle = "#7dd3fc";
  ctx.fillText("40-bit zero preamble", padL + 4, 13);
  ctx.fillStyle = "#fb923c";
  ctx.fillText("80-bit payload (Flags | ID | P | T | Sum8)", padL + preEnd * dx + 6, 13);

  ctx.strokeStyle = "#69db7c";
  ctx.lineWidth = 1.6;
  ctx.beginPath();
  let prevY = yLow;
  ctx.moveTo(padL, prevY);
  for (let i = 0; i < chips.length; i++) {
    const x0 = padL + i * dx;
    const x1 = padL + (i + 1) * dx;
    const y = chips[i] ? yHigh : yLow;
    if (y !== prevY) ctx.lineTo(x0, y);
    ctx.lineTo(x1, y);
    prevY = y;
  }
  ctx.lineTo(padL + chips.length * dx, yLow);
  ctx.stroke();

  ctx.fillStyle = "#7e90aa";
  ctx.fillText("OOK 315.000 MHz Manchester (123 µs half-bit, ~29.5 ms / frame)", padL + 4, h - 4);
}

export function createRfBenchUI() {
  let active = false;
  let timer = null;
  let selectedTx = null;
  let lastState = null;

  const portSel = document.getElementById("rf-port-select");
  const btnConn = document.getElementById("rf-btn-connect");
  const btnDisc = document.getElementById("rf-btn-disconnect");
  const espStatus = document.getElementById("rf-esp-status");
  const usrpStatus = document.getElementById("rf-usrp-status");
  const btnProbe = document.getElementById("rf-btn-probe");
  const txMode = document.getElementById("rf-tx-mode");
  const txId = document.getElementById("rf-tx-id");
  const txPsi = document.getElementById("rf-tx-psi");
  const txTemp = document.getElementById("rf-tx-temp");
  const txFlags = document.getElementById("rf-tx-flags");
  const txGain = document.getElementById("rf-tx-gain");
  const txGainOut = document.getElementById("rf-tx-gain-out");
  const txRepeats = document.getElementById("rf-tx-repeats");
  const txCount = document.getElementById("rf-tx-count-in");
  const btnTx = document.getElementById("rf-btn-tx");
  const btnClear = document.getElementById("rf-btn-clear");
  const txMsg = document.getElementById("rf-tx-msg");

  const postJson = async (url, payload = {}) => {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json().catch(() => ({ ok: false, error: `HTTP ${res.status}` }));
    if (!res.ok && !data.error) data.error = `HTTP ${res.status}`;
    return data;
  };

  const renderWaveFromForm = () => {
    if (selectedTx && selectedTx.mode === "eg53ma4") {
      const bytes = [];
      for (let i = 0; i < selectedTx.payload_hex.length; i += 2) {
        bytes.push(parseInt(selectedTx.payload_hex.slice(i, i + 2), 16));
      }
      drawWaveform(
        document.getElementById("rf-wave-canvas"),
        document.getElementById("rf-wave-meta"),
        bytes,
        `TX #${selectedTx.id} (${selectedTx.sensor_id})`
      );
      return;
    }
    const bytes = buildPayloadBytes(txId.value, txPsi.value, txTemp.value, txFlags.value);
    drawWaveform(
      document.getElementById("rf-wave-canvas"),
      document.getElementById("rf-wave-meta"),
      bytes,
      "Next TX Preview"
    );
  };

  function renderState(st) {
    lastState = st;
    const esp = st.esp || {};
    const usrp = st.usrp || {};
    const sum = st.summary || {};

    // Update serial port options without wiping current choice
    const ports = st.ports || [];
    const curPort = portSel.value;
    portSel.innerHTML = ports.length
      ? ports.map((p) => `<option value="${esc(p)}">${esc(p)}</option>`).join("")
      : `<option value="">No /dev/ttyUSB* found</option>`;
    if (esp.port && ports.includes(esp.port)) portSel.value = esp.port;
    else if (curPort && ports.includes(curPort)) portSel.value = curPort;

    btnConn.disabled = !!esp.connected || !ports.length;
    btnDisc.disabled = !esp.connected;
    espStatus.innerHTML = esp.connected
      ? `<span class="pill pass">CONNECTED</span> ${esc(esp.port)} · ${esc(esp.mode_name || "")}`
      : `<span class="pill ${esp.error ? "fail" : "pa"}">${esp.error ? "ERROR" : "DISCONNECTED"}</span> ${esc(esp.error || "Click Connect")}`;

    usrpStatus.innerHTML = usrp.detected
      ? `<span class="pill pass">READY</span> ${esc(usrp.product || "B205mini")} (${esc(usrp.serial)})`
      : `<span class="pill fail">NOT FOUND</span> ${esc(usrp.error || "Plug in B205mini & click Re-scan")}`;
    btnTx.disabled = !!usrp.tx_busy;
    btnTx.textContent = usrp.tx_busy ? "⏳ Transmitting..." : "▶ Transmit Burst";

    // Top KPI cards
    const kCc = document.getElementById("rf-kpi-cc");
    if (esp.cc_ok === true) {
      kCc.innerHTML = `<strong>${esc(esp.partnum || "0x00")} / ${esc(esp.version || "0x14")}</strong><span>MARC ${esc(esp.marcstate || "0x0D")} (RX)</span>`;
    } else if (esp.connected) {
      kCc.innerHTML = `<strong>${esp.cc_ok === false ? "NOT FOUND" : "Polling..."}</strong><span>${esc(esp.port)}</span>`;
    } else {
      kCc.innerHTML = `<strong>Offline</strong><span>Connect ESP32</span>`;
    }

    const kRssi = document.getElementById("rf-kpi-rssi");
    kRssi.innerHTML = `<strong>${esp.rssi_dbm != null ? `${esp.rssi_dbm} dBm` : "—"}</strong><span>Noise floor ${esp.noise_floor_dbm != null ? `${esp.noise_floor_dbm} dBm` : "—"}</span>`;

    const kGdo2 = document.getElementById("rf-kpi-gdo2");
    if (esp.gdo2 == null) {
      kGdo2.innerHTML = `<strong>—</strong><span>GDO0=${esp.gdo0 ?? "—"}</span>`;
    } else {
      kGdo2.innerHTML = `<strong class="${esp.gdo2 ? "rf-warn-txt" : "rf-ok-txt"}">GDO2 = ${esp.gdo2}</strong><span>${esp.gdo2 ? "Carrier active" : "Idle quiet"} · GDO0=${esp.gdo0 ?? "—"}</span>`;
    }

    const kTx = document.getElementById("rf-kpi-tx");
    kTx.innerHTML = `<strong>${sum.tx_bursts ?? 0} bursts</strong><span>${sum.tx_expected_frames ?? 0} EG53 frames queued</span>`;

    const kRx = document.getElementById("rf-kpi-rx");
    const pct = sum.match_pct != null ? `${sum.match_pct}% matched` : "Waiting for RX";
    kRx.innerHTML = `<strong>${sum.rx_total_frames ?? 0} decoded</strong><span>${pct} (${sum.tx_matched_frames ?? 0} matched)</span>`;

    const kNoise = document.getElementById("rf-kpi-noise");
    kNoise.innerHTML = `<strong>${(esp.edges ?? 0).toLocaleString()} edges</strong><span>bursts ${esp.bursts ?? 0} · drop ${esp.dropped ?? 0} · squelch ${esc(esp.squelch ?? "—")}</span>`;

    // Register dump table
    const regsEl = document.getElementById("rf-regs-dl");
    const regs = esp.regs || {};
    const regKeys = Object.keys(regs);
    regsEl.innerHTML = regKeys.length
      ? regKeys.map((k) => `<dt>${esc(k)}</dt><dd>${esc(regs[k])}</dd>`).join("")
      : `<dt>Status</dt><dd>Waiting for dump (d)</dd>`;

    // RSSI chart
    drawRssiChart(document.getElementById("rf-rssi-canvas"), st.rssi_history || []);

    // TX Table
    const txList = st.tx_log || [];
    document.getElementById("rf-tx-count").textContent = `${txList.length} burst(s)`;
    const txBody = document.getElementById("rf-tx-body");
    txBody.innerHTML = txList.length
      ? txList.map((t) => {
          const stCls = t.status === "sent" ? "pass" : t.status === "transmitting" ? "pa" : "fail";
          const matchStr = t.mode === "eg53ma4" ? `${t.rx_matched}/${t.expected_frames}` : "CW";
          const selCls = selectedTx && selectedTx.id === t.id ? "active-row" : "";
          return `<tr class="${selCls}" data-tx-id="${t.id}">
            <td>#${t.id}</td>
            <td>${esc(t.ts)}</td>
            <td>${esc(t.mode.toUpperCase())}</td>
            <td><code>${t.mode === "eg53ma4" ? esc(t.sensor_id) : "—"}</code></td>
            <td>${t.mode === "eg53ma4" ? `${t.psi.toFixed(1)} psi / ${t.temp_f}F` : "—"}</td>
            <td>${t.gain_db.toFixed(0)} dB</td>
            <td title="${esc(t.error)}"><span class="pill ${stCls}" title="${esc(t.error)}">${esc(t.status)}</span></td>
            <td><span class="pill ${t.rx_matched > 0 ? "pass" : "opt"}">${esc(matchStr)}</span></td>
          </tr>`;
        }).join("")
      : `<tr><td colspan="8" class="muted">No USRP transmissions yet. Configure TX in the inspector and click Transmit Burst.</td></tr>`;

    if (txList.length && txList[0].status === "error" && txList[0].error) {
      txMsg.textContent = `TX #${txList[0].id} error: ${txList[0].error}`;
    } else if (txList.length && txList[0].status === "sent" && txMsg.textContent.startsWith("Queued TX")) {
      txMsg.textContent = `TX #${txList[0].id} sent`;
    }

    txBody.querySelectorAll("tr[data-tx-id]").forEach((tr) => {
      tr.onclick = () => {
        const id = Number(tr.dataset.txId);
        selectedTx = txList.find((x) => x.id === id) || null;
        renderWaveFromForm();
        renderState(lastState);
      };
    });

    // RX Table
    const rxList = st.rx_frames || [];
    document.getElementById("rf-rx-count").textContent = `${rxList.length} frame(s)`;
    const rxBody = document.getElementById("rf-rx-body");
    rxBody.innerHTML = rxList.length
      ? rxList.map((r) => {
          const corr = r.matched_tx_id
            ? `<span class="pill pass">TX #${r.matched_tx_id}${r.exact_match ? " ✓" : ""}</span>`
            : `<span class="pill pa">EXT/OTA</span>`;
          return `<tr>
            <td>${esc(r.ts)}</td>
            <td><code>${esc(r.id)}</code></td>
            <td>${r.psi.toFixed(1)} psi (${r.kpa.toFixed(1)} kPa)</td>
            <td>${r.temp_f} F (${r.temp_c} C)</td>
            <td><code>${esc(r.flags)}</code></td>
            <td>${r.rssi} dBm</td>
            <td>${corr}</td>
          </tr>`;
        }).join("")
      : `<tr><td colspan="7" class="muted">No EG53MA4 frames decoded yet. Waiting for 315 MHz OOK burst...</td></tr>`;

    // Serial console
    const serEl = document.getElementById("rf-serial-log");
    const wasBottom = serEl.scrollHeight - serEl.scrollTop - serEl.clientHeight < 28;
    const logs = st.serial_log || [];
    serEl.innerHTML = logs
      .map((item) => `<div class="ser-line ser-${esc(item.kind)}"><span>${esc(item.ts)}</span> ${esc(item.line)}</div>`)
      .join("");
    if (wasBottom) serEl.scrollTop = serEl.scrollHeight;
  }

  async function poll() {
    if (!active) return;
    try {
      const res = await fetch("/api/rf/state", { cache: "no-store" });
      if (res.ok) {
        const st = await res.json();
        renderState(st);
      }
    } catch (_) {
      // ignore transient poll failure
    }
  }

  // Bind UI actions
  btnConn.onclick = async () => {
    const res = await postJson("/api/rf/connect", { port: portSel.value });
    if (!res.ok) txMsg.textContent = res.error || "Connect failed";
    poll();
  };
  btnDisc.onclick = async () => {
    await postJson("/api/rf/disconnect");
    poll();
  };
  document.getElementById("rf-btn-reset").onclick = async () => {
    await postJson("/api/rf/cmd", { cmd: "reset" });
    setTimeout(poll, 350);
  };
  document.getElementById("rf-btn-dump").onclick = () => postJson("/api/rf/cmd", { cmd: "d" }).then(poll);
  document.getElementById("rf-btn-profile").onclick = () => postJson("/api/rf/cmd", { cmd: "p" }).then(poll);
  document.getElementById("rf-btn-raw").onclick = () => postJson("/api/rf/cmd", { cmd: "r" }).then(poll);
  document.getElementById("rf-btn-squelch").onclick = () => postJson("/api/rf/cmd", { cmd: "g" }).then(poll);
  btnProbe.onclick = async () => {
    usrpStatus.textContent = "Scanning UHD devices...";
    await postJson("/api/rf/probe-usrp");
    poll();
  };
  btnClear.onclick = async () => {
    selectedTx = null;
    await postJson("/api/rf/clear");
    renderWaveFromForm();
    poll();
  };

  txGain.oninput = () => {
    txGainOut.textContent = `${txGain.value} dB`;
  };
  [txId, txPsi, txTemp, txFlags].forEach((el) => {
    el.oninput = () => {
      selectedTx = null;
      renderWaveFromForm();
    };
  });

  document.querySelectorAll("#rf-tx-presets button").forEach((b) => {
    b.onclick = () => {
      selectedTx = null;
      txId.value = b.dataset.id;
      txPsi.value = b.dataset.psi;
      txTemp.value = b.dataset.temp;
      txFlags.value = b.dataset.flags;
      renderWaveFromForm();
    };
  });

  btnTx.onclick = async () => {
    txMsg.textContent = "";
    selectedTx = null;
    const res = await postJson("/api/rf/tx", {
      mode: txMode.value,
      id: txId.value,
      psi: Number(txPsi.value),
      temp_f: Number(txTemp.value),
      flags: txFlags.value,
      gain: Number(txGain.value),
      repeats: Number(txRepeats.value),
      count: Number(txCount.value),
    });
    if (!res.ok) {
      txMsg.textContent = res.error || "TX failed";
    } else {
      txMsg.textContent = `Queued TX #${res.tx.id}...`;
      renderWaveFromForm();
    }
    poll();
  };

  renderWaveFromForm();

  return {
    setActive(on) {
      active = on;
      if (timer) {
        clearInterval(timer);
        timer = null;
      }
      if (on) {
        renderWaveFromForm();
        poll();
        timer = setInterval(poll, 500);
      }
    },
  };
}
