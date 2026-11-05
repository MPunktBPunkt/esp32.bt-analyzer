(function () {
  const nodesEl = document.getElementById("nodes");
  const logEl = document.getElementById("log");
  const targetEl = document.getElementById("target");
  const canvas = document.getElementById("rate-chart");
  const ctx = canvas.getContext("2d");
  let auto = false;
  let timer = null;
  const hist = { appTx: [], appRx: [], hciTx: [], hciRx: [], btac: [] };
  const HMAX = 60;

  function esc(s) {
    return String(s ?? "").replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
    );
  }

  async function jget(url) {
    const r = await fetch(url);
    if (!r.ok) throw new Error(url + " HTTP " + r.status);
    return r.json();
  }

  async function jpost(url, body) {
    const r = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
    const t = await r.text();
    logEl.textContent = url + " → " + t;
    try {
      return JSON.parse(t);
    } catch (_) {
      return { raw: t };
    }
  }

  function pushRate(fromStatus) {
    const nodes = fromStatus.nodes || [];
    const host = nodes.find((n) => n.ip === "192.168.178.88") || nodes[0];
    const st = (host && host.status) || {};
    const oc = st.onchip || {};
    const hc = st.hciCapture || {};
    const bt = st.btac || {};
    const sample = {
      appTx: (oc.appTxBps || 0) / 1000,
      appRx: (oc.appRxBps || 0) / 1000,
      hciTx: (hc.aclTxBps || 0) / 1000,
      hciRx: (hc.aclRxBps || 0) / 1000,
      btac: (bt.fwdBps || 0) / 1000,
    };
    Object.keys(hist).forEach((k) => {
      hist[k].push(sample[k]);
      if (hist[k].length > HMAX) hist[k].shift();
    });
    document.getElementById("rate-now").textContent =
      `appTX ${sample.appTx.toFixed(1)}  appRX ${sample.appRx.toFixed(1)}  ` +
      `hciTX ${sample.hciTx.toFixed(1)}  hciRX ${sample.hciRx.toFixed(1)}  ` +
      `btac ${sample.btac.toFixed(1)} kB/s · dropS=${(st.capture || {}).droppedSession} gapS=${bt.seqGapsSession}`;
    drawChart();
  }

  function drawChart() {
    const w = canvas.width;
    const h = canvas.height;
    ctx.fillStyle = "#0d1117";
    ctx.fillRect(0, 0, w, h);
    const series = [
      { k: "appTx", c: "#3fb950" },
      { k: "appRx", c: "#58a6ff" },
      { k: "hciTx", c: "#e3b341" },
      { k: "hciRx", c: "#d2a8ff" },
      { k: "btac", c: "#f85149" },
    ];
    let max = 1;
    series.forEach((s) => hist[s.k].forEach((v) => (max = Math.max(max, v))));
    ctx.strokeStyle = "#21262d";
    ctx.beginPath();
    for (let i = 0; i < 4; i++) {
      const y = (h * i) / 4;
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
    }
    ctx.stroke();
    series.forEach((s) => {
      const arr = hist[s.k];
      if (arr.length < 2) return;
      ctx.strokeStyle = s.c;
      ctx.beginPath();
      arr.forEach((v, i) => {
        const x = (i / (HMAX - 1)) * w;
        const y = h - (v / max) * (h - 8) - 4;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();
    });
  }

  function renderNode(n) {
    const st = n.status || {};
    const oc = st.onchip || {};
    const cap = st.capture || {};
    const hc = st.hciCapture || {};
    const btac = st.btac || {};
    const ok = !!n.ok;
    return `
      <div class="card" data-ip="${esc(n.ip)}">
        <h3>${esc(n.role)} <span class="pill ${ok ? "on" : ""}">${ok ? "online" : "down"}</span></h3>
        <table>
          <tr><td>IP</td><td class="mono"><a href="http://${esc(n.ip)}/" style="color:#58a6ff">${esc(n.ip)}</a></td></tr>
          <tr><td>FW</td><td class="mono">${esc(st.version)}</td></tr>
          <tr><td>onchip</td><td class="mono">ready=${esc(oc.ready)} state=${esc(oc.state)} mtu=${esc(oc.attMtu)} thr=${esc(oc.thrRunning)}</td></tr>
          <tr><td>rates</td><td class="mono">app ${esc(oc.appTxBps)}/${esc(oc.appRxBps)} · hci ${esc(hc.aclTxBps)}/${esc(hc.aclRxBps)} · btac ${esc(btac.fwdBps)} B/s</td></tr>
          <tr><td>Capture</td><td class="mono">drop=${esc(cap.dropped)} dropS=${esc(cap.droppedSession)} fill=${esc(cap.fill)}/${esc(cap.capacity)} hwS=${esc(cap.highWaterSession)}</td></tr>
          <tr><td>BTAC</td><td class="mono">fwd=${esc(btac.forwarded)} gap=${esc(btac.seqGaps)} gapS=${esc(btac.seqGapsSession)}</td></tr>
        </table>
      </div>`;
  }

  function renderSession(s) {
    const el = document.getElementById("c-session");
    const dl = document.getElementById("btn-sess-dl");
    const sr = document.getElementById("sess-rate");
    if (!s || (!s.active && !s.frames)) {
      el.textContent = "idle";
      dl.style.display = "none";
      if (sr) sr.textContent = "session: idle";
      return;
    }
    el.textContent =
      (s.active ? "LIVE " : "stopped ") +
      s.ip +
      " frames=" +
      s.frames +
      " bytes=" +
      s.bytes +
      " gaps=" +
      s.gaps;
    dl.style.display = s.path ? "inline" : "none";
    if (sr) {
      sr.textContent =
        `session: ${s.active ? "LIVE" : "stopped"} · ${esc(s.rate_fps || 0)} fps · ` +
        `RX ${esc(s.rate_rx_Bps || 0)} B/s · TX ${esc(s.rate_tx_Bps || 0)} B/s · gaps=${esc(s.gaps)}`;
    }
  }

  async function refreshFrames() {
    const list = document.getElementById("frame-list");
    if (!list) return;
    try {
      const data = await jget("/api/v1/session/frames?n=48");
      const frames = data.frames || [];
      if (!frames.length) {
        list.textContent = data.active ? "(waiting for frames…)" : "(no frames — start BTAC)";
        return;
      }
      list.textContent = frames
        .map((f) => {
          const ts = f.ts_us != null ? String(f.ts_us).padStart(10, " ") : "—";
          const hx = f.payload_hex || "";
          let mark = "";
          if (f.type === "evt" && hx.startsWith("04")) {
            const ev = hx.slice(2, 4);
            if (ev === "05") mark = " [DISC 0x" + (hx.slice(12, 14) || "?") + "]";
            else if (ev === "3e" && hx.slice(6, 8) === "01") mark = " [LE_CONN]";
          }
          return `#${f.seq} ${ts} ${f.dir||"?"} ${f.type||"?"}${mark} len=${f.length} ${f.payload_hex_short || ""}`;
        })
        .join("\n");
    } catch (e) {
      list.textContent = String(e);
    }
  }

  async function refreshLabDevices() {
    const el = document.getElementById("lab-devs");
    if (!el) return;
    const ip = targetEl.value || "192.168.178.87";
    try {
      const data = await jget(`/api/v1/node/${ip}/devices`);
      const list = data.devices || [];
      if (!list.length) {
        el.textContent = `${ip}: keine Geräte`;
        return;
      }
      el.innerHTML = list
        .map((d) => {
          const tag = (d.classic ? "C " : "") + (d.ble ? "BLE" : "");
          const btn = d.ble
            ? ` <button type="button" class="secondary" data-conn="${esc(d.addr)}" data-at="${esc(d.addrType || 0)}">Connect</button>`
            : "";
          return `<div><span class="mono">${esc(d.addr)}</span> ${esc(d.name || "—")} ${tag} rssi=${esc(d.rssi)}${btn}</div>`;
        })
        .join("");
      el.querySelectorAll("[data-conn]").forEach((b) => {
        b.onclick = () => {
          document.getElementById("peer-addr").value = b.getAttribute("data-conn");
          return jpost(`/api/v1/node/192.168.178.88/connect`, {
            addr: b.getAttribute("data-conn"),
            addrType: b.getAttribute("data-at") || "0",
          }).then(refreshNodes);
        };
      });
    } catch (e) {
      el.textContent = String(e);
    }
  }

  async function refreshProxy() {
    const el = document.getElementById("proxy-ctl");
    if (!el) return;
    try {
      const p = await jget("/api/v1/proxy/controllers");
      const lines = (p.controllers || []).map((c) => {
        const cl = c.classified || {};
        const ready = cl.classic_ready ? "CLASSIC_READY" : cl.class || "?";
        const bd = cl.bd_addr || cl.label || "—";
        const block = cl.flash_blocked ? " · FLASH_BLOCKED" : "";
        return `slot ${c.slot} ${c.id} ${c.ip} → ${ready} ${bd}${block}`;
      });
      el.textContent =
        `transport=${p.hci_transport || "?"} dual=${p.dual_classic_ready}\n` + lines.join("\n");
    } catch (e) {
      el.textContent = String(e);
    }
  }

  async function refreshHealth() {
    const h = await jget("/api/v1/health");
    document.getElementById("svc-ver").textContent = "ctrl " + (h.version || "?");
    document.getElementById("c-health").innerHTML = h.ok
      ? '<span class="ok">ok</span>'
      : '<span class="bad">fail</span>';
    document.getElementById("c-uptime").textContent = (h.uptime_s || 0) + " s";
    renderSession(h.session || {});
  }

  async function refreshNodes() {
    await refreshHealth();
    const data = await jget("/api/v1/nodes");
    nodesEl.innerHTML = (data.nodes || []).map(renderNode).join("");
    pushRate(data);
    const ips = (data.nodes || []).map((n) => n.ip);
    const cur = targetEl.value;
    targetEl.innerHTML = ips.map((ip) => `<option value="${esc(ip)}">${esc(ip)}</option>`).join("");
    if (cur && ips.includes(cur)) targetEl.value = cur;
    const sess = await jget("/api/v1/session");
    renderSession(sess.session || {});
    await refreshFrames();
    await refreshProxy();
    await refreshProxySession();
  }

  document.getElementById("btn-refresh").onclick = () => refreshNodes().catch(console.error);
  document.getElementById("btn-auto").onclick = function () {
    auto = !auto;
    this.textContent = "Auto 1s: " + (auto ? "on" : "off");
    if (timer) clearInterval(timer);
    if (auto) timer = setInterval(() => refreshNodes().catch(console.error), 1000);
  };

  document.getElementById("btn-sess-start").onclick = async () => {
    await jpost("/api/v1/session/start", { ip: targetEl.value });
    await refreshNodes();
  };
  document.getElementById("btn-sess-stop").onclick = async () => {
    await jpost("/api/v1/session/stop", {});
    await refreshNodes();
  };
  document.getElementById("btn-proxy-sess").onclick = async () => {
    await jpost("/api/v1/proxy/session/start", {});
    await refreshNodes();
  };
  document.getElementById("btn-proxy-sess-stop").onclick = async () => {
    await jpost("/api/v1/proxy/session/stop", {});
    await refreshNodes();
  };

  async function refreshProxySession() {
    const el = document.getElementById("proxy-sess");
    if (!el) return;
    try {
      const p = await jget("/api/v1/proxy/session");
      const px = p.proxy || {};
      const a = px.phone_side || {};
      const b = px.car_side || {};
      el.textContent =
        `proxy dual=${px.dual_active} · phone frames=${a.frames || 0} fps=${a.rate_fps || 0} · ` +
        `car frames=${b.frames || 0} fps=${b.rate_fps || 0}`;
    } catch (e) {
      el.textContent = String(e);
    }
  }

  document.getElementById("btn-adv").onclick = () =>
    jpost(`/api/v1/node/192.168.178.89/advertise-start`, { name: "bt-peer-89" }).then(refreshNodes);
  document.getElementById("btn-scan").onclick = () =>
    jpost(`/api/v1/node/192.168.178.88/scan-start`, {}).then(() => {
      refreshNodes();
      setTimeout(refreshLabDevices, 2500);
    });
  document.getElementById("btn-inquiry").onclick = () =>
    jpost(`/api/v1/node/192.168.178.87/inquiry-start`, {}).then(() => {
      refreshNodes();
      setTimeout(refreshLabDevices, 9000);
    });
  document.getElementById("btn-devs").onclick = () => refreshLabDevices().catch(console.error);
  document.getElementById("btn-connect").onclick = () => {
    const addr = document.getElementById("peer-addr").value.trim() || "68:b6:b3:2b:c5:69";
    return jpost(`/api/v1/node/192.168.178.88/connect`, { addr, addrType: "0" }).then(refreshNodes);
  };
  document.getElementById("btn-gatt").onclick = () =>
    jpost(`/api/v1/node/192.168.178.88/gatt-read-name`, {}).then(refreshNodes);
  document.getElementById("btn-thr-n").onclick = async () => {
    await jpost(`/api/v1/node/192.168.178.89/throughput-start`, { mode: "notify", payload: "20", mtu: "247" });
    await jpost(`/api/v1/node/192.168.178.88/throughput-start`, { mode: "notify", payload: "20", mtu: "247" });
    await refreshNodes();
  };
  document.getElementById("btn-thr-w").onclick = async () => {
    await jpost(`/api/v1/node/192.168.178.89/throughput-start`, { mode: "write", payload: "20", mtu: "247" });
    await jpost(`/api/v1/node/192.168.178.88/throughput-start`, { mode: "write", payload: "20", mtu: "247" });
    await refreshNodes();
  };
  document.getElementById("btn-thr-stop").onclick = async () => {
    await jpost(`/api/v1/node/192.168.178.88/throughput-stop`, {});
    await jpost(`/api/v1/node/192.168.178.89/throughput-stop`, {});
    await refreshNodes();
  };
  document.getElementById("btn-disco").onclick = () =>
    jpost(`/api/v1/node/192.168.178.87/discoverable-start`, {}).then(refreshNodes);

  document.getElementById("btn-drain").onclick = async () => {
    const ip = targetEl.value;
    const r = await fetch(`/api/v1/node/${ip}/drain?n=32`);
    logEl.textContent = (await r.text()) || "(empty drain)";
  };

  document.getElementById("btn-inject").onclick = async () => {
    const ip = targetEl.value;
    const hex = document.getElementById("hex").value.trim();
    await jpost(`/api/v1/node/${ip}/inject`, { hex });
    await refreshNodes();
  };

  refreshNodes().catch((e) => {
    logEl.textContent = String(e);
  });
})();
