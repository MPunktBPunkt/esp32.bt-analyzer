(function () {
  const nodesEl = document.getElementById("nodes");
  const logEl = document.getElementById("log");
  const targetEl = document.getElementById("target");
  let auto = false;
  let timer = null;

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
          <tr><td>onchip</td><td class="mono">ready=${esc(oc.ready)} state=${esc(oc.state)} bd=${esc(oc.bdAddr)}</td></tr>
          <tr><td>roles</td><td class="mono">scan=${esc(oc.leScanning)} adv=${esc(oc.leAdvertising)} conn=${esc(oc.leConnected)} gatt=${esc(oc.gattName)}</td></tr>
          <tr><td>Capture</td><td class="mono">cap=${esc(cap.captured)} drop=${esc(cap.dropped)} fill=${esc(cap.fill)}/${esc(cap.capacity)} psram=${esc(cap.psram)}</td></tr>
          <tr><td>HCI/BTAC</td><td class="mono">rx=${esc(hc.rx)} tx=${esc(hc.tx)} btacFwd=${esc(btac.forwarded)} listen=${esc(btac.listening)}</td></tr>
        </table>
      </div>`;
  }

  function renderSession(s) {
    const el = document.getElementById("c-session");
    const dl = document.getElementById("btn-sess-dl");
    if (!s || (!s.active && !s.frames)) {
      el.textContent = "idle";
      dl.style.display = "none";
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
    const ips = (data.nodes || []).map((n) => n.ip);
    const cur = targetEl.value;
    targetEl.innerHTML = ips.map((ip) => `<option value="${esc(ip)}">${esc(ip)}</option>`).join("");
    if (cur && ips.includes(cur)) targetEl.value = cur;
    const sess = await jget("/api/v1/session");
    renderSession(sess.session || {});
  }

  document.getElementById("btn-refresh").onclick = () => refreshNodes().catch(console.error);
  document.getElementById("btn-auto").onclick = function () {
    auto = !auto;
    this.textContent = "Auto 3s: " + (auto ? "on" : "off");
    if (timer) clearInterval(timer);
    if (auto) timer = setInterval(() => refreshNodes().catch(console.error), 3000);
  };

  document.getElementById("btn-sess-start").onclick = async () => {
    await jpost("/api/v1/session/start", { ip: targetEl.value });
    await refreshNodes();
  };
  document.getElementById("btn-sess-stop").onclick = async () => {
    await jpost("/api/v1/session/stop", {});
    await refreshNodes();
  };

  document.getElementById("btn-adv").onclick = () =>
    jpost(`/api/v1/node/192.168.178.89/advertise-start`, { name: "bt-peer-89" }).then(refreshNodes);
  document.getElementById("btn-scan").onclick = () =>
    jpost(`/api/v1/node/192.168.178.88/scan-start`, {}).then(refreshNodes);
  document.getElementById("btn-connect").onclick = () => {
    const addr = document.getElementById("peer-addr").value.trim() || "68:b6:b3:2b:c5:69";
    return jpost(`/api/v1/node/192.168.178.88/connect`, { addr, addrType: "0" }).then(refreshNodes);
  };
  document.getElementById("btn-gatt").onclick = () =>
    jpost(`/api/v1/node/192.168.178.88/gatt-read-name`, {}).then(refreshNodes);
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
