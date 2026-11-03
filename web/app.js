(function () {
  const nodesEl = document.getElementById("nodes");
  const logEl = document.getElementById("log");
  const targetEl = document.getElementById("target");
  let auto = false;
  let timer = null;

  function esc(s) {
    return String(s ?? "").replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    }[c]));
  }

  async function jget(url) {
    const r = await fetch(url);
    if (!r.ok) throw new Error(url + " HTTP " + r.status);
    return r.json();
  }

  function renderNode(n) {
    const st = n.status || {};
    const usb = n.usb || {};
    const dut = (usb.dut || st.dut || {});
    const hci = (usb.hci || st.hci || {});
    const cap = st.capture || {};
    const hc = st.hciCapture || {};
    const ok = !!n.ok;
    return `
      <div class="card" data-ip="${esc(n.ip)}">
        <h3>${esc(n.role)} <span class="pill ${ok ? "on" : ""}">${ok ? "online" : "down"}</span></h3>
        <table>
          <tr><td>IP</td><td class="mono"><a href="http://${esc(n.ip)}/" style="color:#58a6ff">${esc(n.ip)}</a></td></tr>
          <tr><td>Name / FW</td><td>${esc(st.name)} · <span class="mono">${esc(st.version)}</span></td></tr>
          <tr><td>USB state</td><td>${esc((usb.otg || st.otg || {}).state || "—")}</td></tr>
          <tr><td>DUT</td><td class="mono">${dut.present ? esc(dut.id) + " · " + esc(dut.product) : "none"}</td></tr>
          <tr><td>HCI detected</td><td class="${hci.detected ? "ok" : "warn"}">${hci.detected ? "yes" : "no"}</td></tr>
          <tr><td>Capture</td><td class="mono">cap=${esc(cap.captured)} drop=${esc(cap.dropped)} fill=${esc(cap.fill)}/${esc(cap.capacity)} psram=${esc(cap.psram)}</td></tr>
          <tr><td>HCI cap</td><td class="mono">armed=${esc(hc.armed)} open=${esc(hc.openOk)} aclIn=${esc(hc.aclIn)} inj=${esc(hc.inject)} evt=${esc(hc.eventCapture)}</td></tr>
        </table>
      </div>`;
  }

  async function refreshHealth() {
    const h = await jget("/api/v1/health");
    document.getElementById("svc-ver").textContent = "ctrl " + (h.version || "?");
    document.getElementById("c-health").innerHTML = h.ok
      ? '<span class="ok">ok</span>'
      : '<span class="bad">fail</span>';
    document.getElementById("c-uptime").textContent = (h.uptime_s || 0) + " s";
  }

  async function refreshNodes() {
    await refreshHealth();
    const data = await jget("/api/v1/nodes");
    nodesEl.innerHTML = (data.nodes || []).map(renderNode).join("");
    const ips = (data.nodes || []).map((n) => n.ip);
    const cur = targetEl.value;
    targetEl.innerHTML = ips.map((ip) => `<option value="${esc(ip)}">${esc(ip)}</option>`).join("");
    if (cur && ips.includes(cur)) targetEl.value = cur;
  }

  document.getElementById("btn-refresh").onclick = () => refreshNodes().catch(console.error);
  document.getElementById("btn-auto").onclick = function () {
    auto = !auto;
    this.textContent = "Auto 3s: " + (auto ? "on" : "off");
    if (timer) clearInterval(timer);
    if (auto) timer = setInterval(() => refreshNodes().catch(console.error), 3000);
  };

  document.getElementById("btn-drain").onclick = async () => {
    const ip = targetEl.value;
    const r = await fetch(`/api/v1/node/${ip}/drain?n=32`);
    const t = await r.text();
    logEl.textContent = t || "(empty drain)";
  };

  document.getElementById("btn-inject").onclick = async () => {
    const ip = targetEl.value;
    const hex = document.getElementById("hex").value.trim();
    const r = await fetch(`/api/v1/node/${ip}/inject`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ hex }),
    });
    const t = await r.text();
    logEl.textContent = "inject → " + t;
    await refreshNodes();
  };

  refreshNodes().catch((e) => {
    logEl.textContent = String(e);
  });
})();
