# esp32.bt-analyzer

![Version](https://img.shields.io/badge/version-0.3.16-blue)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Gate](https://img.shields.io/badge/gate-BT18%20GATT-yellow)](docs/GATES.md)

ESP **on-chip Bluetooth HCI analyzer** (VHCI): Controller ↔ Host über die Board-Radio, Capture nach Debian.  
**Kein USB-Dongle nötig** (Topologie **F_ONCHIP**).

> **v0.3.16 (ungetestet auf HW)** — `hci-agent-esp32`: D1 als BlueZ-Controller über TCP `:9754` → [`docs/HCI_TCP.md`](docs/HCI_TCP.md) (Basis für den Proxy) · Lab-UI `:8081` mit Agent-Datenrate und btmon-Live-Liste.  
> **v0.3.13** — Real Hammer FTMS PASS · Classic inquiry `0x22` · HD 4.40 seen on `.87` · [`FINDINGS_LAB_20261105.md`](docs/FINDINGS_LAB_20261105.md).  
> **Nicht claimed:** RF/Air · MITM · transparent BT proxy · A2DP in thin VHCI core.

Wissensbasis: [technology-audit / esp32-bt-analyzer](https://github.com/MPunktBPunkt/technology-audit/tree/main/projects/esp32-bt-analyzer) · Basis-FW: [ESP32.esp-hub](https://github.com/MPunktBPunkt/ESP32.esp-hub) `esp-hub-base` **v1.10.5**.

---

## Architecture

```text
Peer ESP / Phone
        │  BLE (S3) · Classic+BLE (.87)
        ▼
┌──────────────────────────┐
│ On-chip BT controller    │  VHCI thin host · HCI ring (PSRAM on S3)
│ .88 Central / .89 Peer   │  BTAC TCP :9753
│ .87 Classic+BLE          │
└────────────┬─────────────┘
             │ WiFi HTTP + BTAC
             ▼
┌──────────────────────────┐
│ Debian collector         │  Lab UI :8081 · control :9751
│ session → .btac          │  decode JSONL · PCAPNG LINKTYPE 201
└──────────────────────────┘
```

PROXY track (0.3.16, [`docs/PROXY.md`](docs/PROXY.md)) — D1s run `hci-agent-esp32` instead of the analyzer image:

```text
Phone ─BT─ D1 .131 ─TCP :9754─┐                         ┌─ Lab UI :8081 (agent rates · btmon live via SSH)
                              ├─ hci_tcp_bridge.py → BlueZ hci1/hci2 on .108 (or VM)
BMW HU ─BT─ D1 .87 ─TCP :9754─┘                         └─ btmon -w → Wireshark
```

| Layer | Was hier gemessen wird |
|-------|-------------------------|
| **L1** | HCI / VHCI frames (primär) |
| **L2** | bounded ATT Read By Type `0x2A00` over HCI ACL (Probe, kein Full-Stack) |
| **L0** | RF/Air — **out of scope** → [`docs/BT15_RF_AIR.md`](docs/BT15_RF_AIR.md) |

## Hard boundaries

| Claim | Status |
|-------|--------|
| ESP32-S3 Classic BR/EDR on-chip | **REJECTED** (Classic nur `.87`) |
| HCI capture = RF sniffer | **REJECTED** |
| Thin ATT name read = full GATT | **REJECTED** |
| USB-Dongle required | **REJECTED** for F_ONCHIP |

## Lab hardware

| IP | Board | Role |
|----|-------|------|
| `.88` | YD-ESP32-S3 N8R2 | OBSERVE_A · BLE Central |
| `.89` | YD-ESP32-S3 N8R2 | Peer Peripheral (advertise) |
| `.87` | D1 Mini ESP32 | Classic+BLE · discoverable / inquiry · PROXY car side (slot B) |
| `.131` | D1 Mini ESP32 | Classic+BLE · PROXY phone side (slot A) — first board for `hci-agent-esp32` |
| `.108` | Proxmox host (Intel 9260) | BlueZ host · `hci_tcp_bridge.py` · btmon ([`docs/HOST_BT.md`](docs/HOST_BT.md)) |

Methods: [`docs/LAB_METHODS.md`](docs/LAB_METHODS.md) · Evidence: [`docs/EVIDENCE.md`](docs/EVIDENCE.md) · Exits: [`docs/GATE_EXITS.md`](docs/GATE_EXITS.md).

### UIs

| UI | URL |
|----|-----|
| Node (`.88`) | `http://192.168.178.88/` · Tab **Analyzer** |
| **Debian bt-analyzer** | **`http://192.168.178.187:8081/`** · BTAC session + peer actions · HCI agents (B/s graph) · btmon live |
| Debian usb-analyzer (parallel) | `http://192.168.178.187:8080/` |

```bash
./tools/run_lab_controller.sh start   # :8081 + :9751
```

Session API: `POST /api/v1/session/start` `{ip}` · `stop` · `GET …/download`.  
Agent/btmon API: `GET /api/v1/agents` · `POST /api/v1/btmon/start` / `stop` · `GET /api/v1/btmon?since=&hci=` ([`controller/README.md`](controller/README.md)).

---

## Build / OTA

```bash
cd firmware/analyzer-node
# PlatformIO: ~/.platformio/penv/bin/pio
pio run -e analyzer-s3
./tools/flash_lab_ota.sh 192.168.178.88
./tools/flash_lab_ota.sh 192.168.178.89

pio run -e analyzer-esp32          # -Os; field OTA slot on .87 is 1966080 B
ENV=analyzer-esp32 ./tools/flash_lab_ota.sh 192.168.178.87

pio run -e hci-agent-esp32         # D1 as raw HCI over TCP for BlueZ (docs/HCI_TCP.md)
ENV=hci-agent-esp32 ./tools/flash_lab_ota.sh 192.168.178.131
sudo python3 tools/hci_tcp_bridge.py 192.168.178.131   # on .108 / VM → hciN
```

Portal SSID: `BT-Analyzer-Setup` · Device name: `bt-analyzer`.

Useful node APIs: `/api/bt/scan|advertise|connect|disconnect`, `/api/bt/gatt/read-name`, `/api/bt/discoverable/*`, `/api/bt/classic/name`, BTAC on `:9753`.  
Agent image: only `/api/status` (field `hciAgent`), OTA `/ota-upload`, H4 on `:9754` — no `/api/bt/*`, no BTAC.

Host tests (no hardware): [`tests/host/README.md`](tests/host/README.md).

## Lab / Gates

Primary topology **F_ONCHIP**. Status matrix: [`docs/GATES.md`](docs/GATES.md).

```bash
python3 tools/lab_run_gates.py          # BT5–BT14 + session gap classify
python3 tools/lab_gap_classify.py --host 192.168.178.88 --btac docs/evidence/….btac
python3 tools/lab_bt16_throughput.py    # ATT notify/write matrix
python3 tools/lab_gatt_client.py        # BT18 GATT Client Flavor
python3 tools/lab_hogp_ftms.py          # BT18b/c HOGP + FTMS Flavors
python3 tools/lab_ftms_control.py       # FTMS Control Point (2AD9)
python3 tools/lab_hogp_matrix.py        # HOGP map/input/output/burst
python3 tools/lab_l2cap_mtu_matrix.py   # MTU × payload → ACL frag observe
python3 tools/lab_bt_host_ssh.py show   # Proxmox BlueZ oracle
python3 tools/lab_avrcp_probe.py --local
python3 tools/lab_bt16_impact.py        # analyzer impact (WiFi STA constant)
python3 tools/lab_clock_sync.py         # multi-node offset estimate
python3 tools/lab_gate_exits.py
```

| Gate band | Stand (0.3.16) |
|-----------|----------------|
| BT0–BT13 | **CODE READY** / lab MEASURED |
| BT14 | **ready for external review** |
| BT15 | **deferred** (RF/Air) |
| BT16 | **CAPABILITY / BENCHMARK** ([`docs/BT16_THROUGHPUT.md`](docs/BT16_THROUGHPUT.md)) |
| BT17 | **scaffold** + AVRCP host probe ([`docs/AVRCP_MEASURE.md`](docs/AVRCP_MEASURE.md)) |
| BT18 | **GATT + HOGP + FTMS + CP** ([`docs/FLAVOR_BUS.md`](docs/FLAVOR_BUS.md)) |
| BT19 | **timeline** ([`docs/BT19_TIMELINE.md`](docs/BT19_TIMELINE.md)) — not PTP |
| BT20 | **window correlate** ([`docs/BT20_CORRELATION.md`](docs/BT20_CORRELATION.md)) |
| PROXY | P0 + P1.0 **PASS** (dual Classic visible) · HCI over TCP **code ready, HW open** ([`docs/HCI_TCP.md`](docs/HCI_TCP.md) A1–A6) · P1 AVRCP next · BCL over BT: plan + SDP probe ([`docs/BCL_BT.md`](docs/BCL_BT.md) B1) |
| Scope | HCI analyzer ≠ universal host ([`docs/SCOPE_HOST_VS_ANALYZER.md`](docs/SCOPE_HOST_VS_ANALYZER.md)) |

## License

- Project code / docs: MIT (this repo).
- Vendored `firmware/analyzer-node/src/core/` from ESP32.esp-hub: **GPL-3.0**.
