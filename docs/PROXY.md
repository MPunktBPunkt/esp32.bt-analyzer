# PROXY — Dual Classic controllers under Debian (AAIdrive / PiDrive)

```yaml
status: architecture_frozen_p0
package: "0.3.15-proxy-track"
anchor: semantic_bridge_not_hci_passthrough
classic_phone_side: "192.168.178.131"   # D1 Mini — flash NOT authorized yet (Heizung)
classic_car_side: "192.168.178.87"      # D1 Mini — bt-analyzer Classic 0.3.14
ble_observe: "192.168.178.88 / .89"     # S3 — analyzer only, never Classic proxy endpoints
hci_transport: network_hci_wifi         # primary; USB-UART HCI optional later
```

## Decisions (frozen defaults)

| Decision | Choice | Why |
|----------|--------|-----|
| `.131` overwrite | **blocked** until explicit lab auth | Live **Heizung/Metermaster** on `.131` today — do not OTA bt-analyzer blindly |
| HCI transport | **Network HCI over WiFi** | Matches Haus↔Auto; both D1s already on LAN; LXC cannot own AF_BLUETOOTH natively ([`HOST_BT.md`](HOST_BT.md)) |
| Proxy semantics | **Terminate profiles on Debian** | No raw `HCI→TCP→HCI` passthrough as the product proxy |
| S3 `.88`/`.89` | Observe/Capture only | No Classic radio |

## Target topology

```text
Phone
  │ Classic BT
  ▼
D1 .131  (phone-side radio / thin HCI agent)
  │ Network HCI (WiFi) + BTAC capture
  ▼
Debian / BlueZ-or-host-bridge  (.187 → SSH oracle .108 as needed)
  │ semantic bridge (SDP / AVRCP / later A2DP)
  │ Network HCI (WiFi) + BTAC capture
  ▼
D1 .87   (car-side radio / thin HCI agent)
  │ Classic BT
  ▼
BMW HU
```

S3 nodes stay parallel observers — not in the Classic proxy path.

## Explicit NO

| Item | Status |
|------|--------|
| Transparent HCI passthrough as “the proxy” | **NO** |
| A2DP/HFP in thin VHCI analyzer core | **NO** (separate host/bridge on Debian) |
| Classic proxy endpoints on S3 | **NO** |
| OTA `.131` while Heizung firmware | **NO** without operator auth |
| Claiming Air/RF from HCI | **NO** |

## Phases / gates

### P0 — Dual controller inventory + visibility

**Done when:** Debian Lab UI / API lists two Classic slots (`.87` live, `.131` role-detected); evidence JSON written; `.131` flash remains gated.

```bash
python3 tools/lab_dual_controller.py
# → docs/evidence/LAB_DUAL_CONTROLLER_<UTC>.{json,md}
```

Gate table:

| Check | Pass |
|-------|------|
| `.87` Classic ready + BD_ADDR | required |
| `.131` HTTP reachable + role classified | required |
| `.131` is bt-analyzer Classic | deferred until flash auth |
| Controllers A≠B (MAC / IP) | required |
| Independent status poll | required |

### P1 — AVRCP semantic proxy (after both D1s are analyzer Classic)

SDP + pairing/bonding both sides + AVRCP PLAY/PAUSE/NEXT with capture/modify hooks.  
Still **no** A2DP requirement for first PiDrive experiments.

### P2 — A2DP SBC

Only after P1 stable; SBC only.

### P3 — HFP

Deferred (SCO/eSCO timing).

## HCI transport design (Network HCI)

```text
Debian controller
  ├── Controller A agent  → HTTP/BTAC/HCI-cmd API on .131
  └── Controller B agent  → HTTP/BTAC/HCI-cmd API on .87
```

- **Capture:** existing BTAC `:9753` per node (already proven).
- **Host commands:** existing `/api/hci/write` + `/api/bt/*` on analyzer FW; later a dedicated `hci_agent` mode may strip thin-host profiles and expose raw HCI only.
- **BlueZ:** keep using Proxmox SSH oracle ([`HOST_BT.md`](HOST_BT.md)) for phone/HU visibility checks; do **not** require AF_BLUETOOTH inside the unprivileged CT.
- **Future:** optional USB-UART HCI when a D1 is plugged into `.108` — additive, not required for P0.

## Relation to OBSERVE

```text
esp32.bt-analyzer
  ├── OBSERVE / CAPTURE   (0.3.14 live frames + rates — shipped)
  ├── DECODE              (0.3.15+ FTMS/AVRCP plugins)
  └── PROXY               (this doc — P0 inventory → P1 AVRCP)
```

Proxy **extends** the analyzer; it does not replace capture.

## Flash when authorized

```bash
# ONLY after Heizung vacated / backup confirmed:
ENV=analyzer-esp32 ./tools/flash_lab_ota.sh 192.168.178.131
```

Record auth in evidence JSON (`flash_authorized: true`) before OTA.
