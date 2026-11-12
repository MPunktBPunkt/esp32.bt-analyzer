(function () {
  const nodesEl = document.getElementById("nodes");
  const logEl = document.getElementById("log");
  const targetEl = document.getElementById("target");
  const canvas = document.getElementById("rate-chart");
  let auto = false;
  let timer = null;
  const HMAX = 60;
  // Idle samples kept after a burst before the chart freezes, so the last burst stays visible.
  const IDLE_KEEP = 5;

  function makeHist(keys) {
    return { keys, data: Object.fromEntries(keys.map((k) => [k, []])), idleRun: 0, lastActive: null, peak: 0 };
  }

  function clearHist(h) {
    h.keys.forEach((k) => (h.data[k] = []));
    h.idleRun = 0;
    h.lastActive = null;
    h.peak = 0;
  }

  function pushSample(h, sample) {
    const active = h.keys.some((k) => sample[k] > 0);
    const frozen = h.lastActive !== null && h.idleRun > IDLE_KEEP;
    if (active) {
      if (frozen) h.keys.forEach((k) => h.data[k].push(NaN));
      h.idleRun = 0;
      h.lastActive = Date.now();
      h.keys.forEach((k) => (h.peak = Math.max(h.peak, sample[k])));
    } else {
      h.idleRun++;
      if (frozen) return;
    }
    h.keys.forEach((k) => {
      h.data[k].push(sample[k]);
      while (h.data[k].length > HMAX) h.data[k].shift();
    });
  }

  function activityText(h) {
    if (h.lastActive === null) return "noch keine Aktivität";
    const ago = Math.round((Date.now() - h.lastActive) / 1000);
    const at = new Date(h.lastActive).toLocaleTimeString();
    const state = h.idleRun > IDLE_KEEP ? `eingefroren, letzte Aktivität ${at} (vor ${ago} s)` : "live";
    return `${state} · Spitze ${h.peak.toFixed(1)} kB/s`;
  }

  const hist = makeHist(["appTx", "appRx", "hciTx", "hciRx", "btac"]);

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
    const host = nodes.find((n) => n.ip === "192.168.178.88" && n.status && n.status.onchip);
    if (!host) {
      document.getElementById("rate-now").textContent =
        "keine On-Chip-Node (.88) online — diese Grafik gilt nur für Topologie F_ONCHIP; HCI-TCP-Raten oben bei den HCI agents";
      return;
    }
    const st = host.status;
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
    pushSample(hist, sample);
    document.getElementById("rate-now").textContent =
      `appTX ${sample.appTx.toFixed(1)}  appRX ${sample.appRx.toFixed(1)}  ` +
      `hciTX ${sample.hciTx.toFixed(1)}  hciRX ${sample.hciRx.toFixed(1)}  ` +
      `btac ${sample.btac.toFixed(1)} kB/s · dropS=${(st.capture || {}).droppedSession} gapS=${bt.seqGapsSession} · ` +
      activityText(hist);
    drawChart();
  }

  function drawChart() {
    drawSeries(canvas, hist, [
      { k: "appTx", c: "#3fb950" },
      { k: "appRx", c: "#58a6ff" },
      { k: "hciTx", c: "#e3b341" },
      { k: "hciRx", c: "#d2a8ff" },
      { k: "btac", c: "#f85149" },
    ]);
  }

  function drawSeries(cv, hist, series) {
    const ctx = cv.getContext("2d");
    const w = cv.width;
    const h = cv.height;
    ctx.fillStyle = "#0d1117";
    ctx.fillRect(0, 0, w, h);
    let max = 1;
    series.forEach((s) => hist.data[s.k].forEach((v) => (max = Number.isFinite(v) ? Math.max(max, v) : max)));
    ctx.strokeStyle = "#21262d";
    ctx.beginPath();
    for (let i = 0; i < 4; i++) {
      const y = (h * i) / 4;
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
    }
    ctx.stroke();
    ctx.fillStyle = "#8b949e";
    ctx.font = "12px monospace";
    ctx.fillText(`${max.toFixed(1)} kB/s`, 6, 14);
    series.forEach((s) => {
      const arr = hist.data[s.k];
      ctx.strokeStyle = s.c;
      ctx.fillStyle = s.c;
      ctx.beginPath();
      let pen = false;
      arr.forEach((v, i) => {
        if (!Number.isFinite(v)) {
          pen = false;
          return;
        }
        const x = (i / (HMAX - 1)) * w;
        const y = h - (v / max) * (h - 8) - 4;
        if (pen) ctx.lineTo(x, y);
        else ctx.moveTo(x, y);
        pen = true;
        if (arr.length === 1) ctx.fillRect(x, y - 1, 3, 3);
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

  const agentHist = makeHist(["pCtrl", "pHost", "cCtrl", "cHost"]);

  async function refreshAgents() {
    const el = document.getElementById("agents");
    if (!el) return;
    try {
      const data = await jget("/api/v1/agents");
      const agents = data.agents || [];
      el.innerHTML = agents
        .map((a) => {
          if (!a.ok) return `${esc(a.id)} ${esc(a.ip)} <span class="bad">down</span>`;
          if (!a.is_agent) return `${esc(a.id)} ${esc(a.ip)} <span class="warn">keine Agent-FW</span> (${esc(a.version)})`;
          const g = a.agent || {};
          const r = {};
          Object.entries(a.rates || {}).forEach(([k, v]) => (r[k] = Math.round(v)));
          const client = g.client
            ? `<span class="ok">Brücke ${esc(g.client)}</span>`
            : '<span class="warn">keine Brücke</span>';
          return (
            `${esc(a.id)} ${esc(a.ip)} ${esc(g.bdAddr)} ready=${esc(g.ready)} ${client} · ` +
            `→ctrl ${esc(r.toCtrlBytesPs)} B/s ${esc(r.toCtrlPktsPs)} pkt/s · ` +
            `→host ${esc(r.toHostBytesPs)} B/s ${esc(r.toHostPktsPs)} pkt/s · ` +
            `drops=${esc(g.drops)} framing=${esc(g.framingErrors)} sess=${esc(g.sessions)}`
          );
        })
        .join("<br>");
      const rate = (id, key) => {
        const a = agents.find((x) => x.id === id);
        return ((a && a.rates && a.rates[key]) || 0) / 1000;
      };
      const sample = {
        pCtrl: rate("phone_side", "toCtrlBytesPs"),
        pHost: rate("phone_side", "toHostBytesPs"),
        cCtrl: rate("car_side", "toCtrlBytesPs"),
        cHost: rate("car_side", "toHostBytesPs"),
      };
      pushSample(agentHist, sample);
      document.getElementById("agent-now").textContent =
        `Handy-Seite →ctrl ${sample.pCtrl.toFixed(1)} →host ${sample.pHost.toFixed(1)} · ` +
        `Auto-Seite →ctrl ${sample.cCtrl.toFixed(1)} →host ${sample.cHost.toFixed(1)} kB/s · ` +
        activityText(agentHist);
      drawAgentChart();
    } catch (e) {
      el.textContent = String(e);
    }
  }

  function drawAgentChart() {
    drawSeries(document.getElementById("agent-chart"), agentHist, [
      { k: "pCtrl", c: "#e3b341" },
      { k: "pHost", c: "#58a6ff" },
      { k: "cCtrl", c: "#f85149" },
      { k: "cHost", c: "#3fb950" },
    ]);
  }

  // Own 1 s poll: rates are deltas between polls, independent of "Auto" and the slower node refresh.
  let agentBusy = false;
  setInterval(() => {
    if (document.hidden || agentBusy) return;
    agentBusy = true;
    refreshAgents().finally(() => (agentBusy = false));
  }, 1000);
  document.getElementById("btn-agent-clear").onclick = () => {
    clearHist(agentHist);
    drawAgentChart();
  };

  const btmon = { seq: 0, blocks: [], timer: null };
  const BTMON_KEEP = 400;
  const btmonList = document.getElementById("btmon-list");

  function btmonLine(b, details) {
    const hci = b.hci != null ? `[hci${b.hci}] ` : "";
    const arrow = { tx: "<", rx: ">", mgmt: "@", note: "=" }[b.dir] || "?";
    let s =
      `<span class="bt-${esc(b.dir)}">${hci}${arrow} </span>` +
      `<span class="bt-proto">${esc(b.proto).padEnd(6)}</span> ` +
      `<span class="bt-${esc(b.dir)}">${esc(b.title)}</span>` +
      (b.meta ? ` <span class="bt-meta">${esc(b.meta)}</span>` : "");
    if (details && b.details && b.details.length) {
      s += "\n" + b.details.map((d) => `<span class="bt-det">${esc(d)}</span>`).join("\n");
    }
    return s;
  }

  function renderBtmon() {
    const q = document.getElementById("btmon-filter").value.trim().toLowerCase();
    const details = document.getElementById("btmon-details").checked;
    const shown = btmon.blocks.filter(
      (b) =>
        !q ||
        [b.proto, b.title, b.meta, ...(b.details || [])].join("\n").toLowerCase().includes(q)
    );
    const atBottom = btmonList.scrollTop + btmonList.clientHeight >= btmonList.scrollHeight - 30;
    btmonList.innerHTML = shown.length
      ? shown.slice(-300).map((b) => btmonLine(b, details)).join("\n")
      : "(noch keine Pakete)";
    if (atBottom) btmonList.scrollTop = btmonList.scrollHeight;
  }

  async function pollBtmon() {
    const hci = document.getElementById("btmon-hci").value;
    try {
      const d = await jget(`/api/v1/btmon?since=${btmon.seq}&hci=${hci}`);
      const fresh = d.blocks || [];
      if (fresh.length) {
        btmon.seq = fresh[fresh.length - 1].seq;
        btmon.blocks = btmon.blocks.concat(fresh).slice(-BTMON_KEEP);
        renderBtmon();
      }
      document.getElementById("btmon-state").textContent =
        (d.running ? "läuft" : "gestoppt") +
        ` · ${d.ssh} · Pakete gesamt ${d.last_seq}` +
        (d.error ? ` · Fehler: ${d.error}` : "");
      if (!d.running && btmon.timer) {
        clearInterval(btmon.timer);
        btmon.timer = null;
      }
    } catch (e) {
      document.getElementById("btmon-state").textContent = String(e);
    }
  }

  function btmonReset() {
    btmon.seq = 0;
    btmon.blocks = [];
    renderBtmon();
  }

  document.getElementById("btn-btmon-start").onclick = async () => {
    await jpost("/api/v1/btmon/start", {});
    if (!btmon.timer) btmon.timer = setInterval(pollBtmon, 700);
    pollBtmon();
  };
  document.getElementById("btn-btmon-stop").onclick = async () => {
    await jpost("/api/v1/btmon/stop", {});
    pollBtmon();
  };
  document.getElementById("btn-btmon-clear").onclick = () => {
    btmon.blocks = [];
    renderBtmon();
  };
  const PAIR_PASSKEY_SHOW_S = 120;
  const pairEvt = (e) =>
    `${new Date(e.ts * 1000).toLocaleTimeString()} ${(e.hci || "-").padEnd(5)} ${(e.role || "").padEnd(10)} ` +
    `${e.method.padEnd(21)} ${e.device || ""} ${e.name ? "(" + e.name + ") " : ""}${e.detail || ""}` +
    (e.answer && e.answer !== "-" ? ` → ${e.answer}` : "") + (e.reason ? ` · ${e.reason}` : "");

  function renderPairing(d) {
    const stateEl = document.getElementById("pair-state");
    if (!d.ok) {
      stateEl.innerHTML = `<span class="bad">nicht erreichbar</span> · ${esc(d.ssh || "")} · ${esc(d.error || "")}`;
      return;
    }
    const svc = d.service === "active" ? '<span class="ok">aktiv</span>' : `<span class="bad">${esc(d.service || "?")}</span>`;
    stateEl.innerHTML =
      `Dienst ${svc} · Regel ${esc(d.mode || "?")} · ${esc(d.capability || "")}` +
      ` · Fenster ${d.window_s > 0 ? Math.round(d.window_s) + " s offen" : "zu"} · ${esc(d.ssh)}`;

    const events = d.events || [];
    const pk = [...events].reverse().find((e) => e.method === "RequestConfirmation" || e.method === "DisplayPasskey");
    const pkEl = document.getElementById("pair-passkey");
    if (pk && d.now - pk.ts < PAIR_PASSKEY_SHOW_S) {
      const code = (pk.detail.match(/passkey=(\d+)/) || [])[1] || "?";
      pkEl.style.display = "";
      pkEl.innerHTML =
        `Passkey <b>${esc(code)}</b> · ${esc(pk.hci)} (${esc(pk.role)}) ↔ ${esc(pk.name || pk.device)} · ` +
        `unsere Seite: ${esc(pk.answer || "-")} — jetzt am Gegenüber vergleichen und bestätigen`;
    } else {
      pkEl.style.display = "none";
    }

    document.getElementById("pair-adapters").innerHTML = (d.adapters || [])
      .map((a) => {
        if (a.error) return esc(a.error);
        const cls = a.cls_ok === false ? `${a.cls} (soll ${a.cls_wanted})` : a.cls;
        const devs = (a.devices || [])
          .map((v) => `&nbsp;&nbsp;${esc(v.mac)} ${esc(v.name)} · ${v.paired ? "gekoppelt" : "-"}` +
            `${v.trusted ? " · trusted" : ""}${v.connected ? ' · <span class="ok">verbunden</span>' : ""}`)
          .join("<br>");
        return `<b>${esc(a.hci)}</b> ${esc(a.bd)} · ${esc(a.role)} · „${esc(a.alias)}“ · Klasse ${esc(cls)} · ` +
          `${a.discoverable ? "sichtbar" : "unsichtbar"} · ${a.pairable ? "koppelbar" : "nicht koppelbar"}` +
          (devs ? "<br>" + devs : "");
      })
      .join("<br>") || "(keine Adapter)";

    document.getElementById("pair-events").textContent = events.length
      ? events.slice().reverse().map(pairEvt).join("\n")
      : "(keine Ereignisse)";
  }

  async function refreshPairing() {
    try {
      renderPairing(await jget("/api/v1/pairing"));
    } catch (e) {
      document.getElementById("pair-state").textContent = String(e);
    }
  }

  let pairBusy = false;
  setInterval(() => {
    if (document.hidden || pairBusy) return;
    pairBusy = true;
    refreshPairing().finally(() => (pairBusy = false));
  }, 3000);
  refreshPairing();
  document.getElementById("btn-pair-refresh").onclick = refreshPairing;
  document.getElementById("btn-pair-window").onclick = async () => {
    await jpost("/api/v1/pairing/window", { seconds: 300 });
    refreshPairing();
  };

  document.getElementById("btmon-hci").onchange = btmonReset;
  document.getElementById("btmon-filter").oninput = renderBtmon;
  document.getElementById("btmon-details").onchange = renderBtmon;

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
