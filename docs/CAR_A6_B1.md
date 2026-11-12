# Car runbook — A6 + B1 (F20 / NBT Evo)

```yaml
status: ready_for_car
lab_closed: [HCI_TCP A1–A5, 62/37 gate, B0.5 BCL synth, B0.6 Dummy-HU SDP]
next: A6 then B1 only — no relay, no BCL TX, no channel-5 assumption
claim_level: VERIFY reuse expectations from technology-audit/bmw-bcl — not FACT until measured
boards: ".87 = car / HU side (hci1, BD c8:c9:a3:cb:37:96) · .131 = phone side (optional today)"
linux: ".108 BlueZ + hci_tcp_bridge"
```

## Lab already closed (do not re-litigate in the car)

| Gate | Result |
|------|--------|
| HCI TCP A1–A5 | PASS |
| 62-vs-37 | PASS_37 (~41–45 kB/s `none`; no sustained 62) |
| BCL framer + fragmentation | PASS (synthetic) |
| BCL bytes over RFCOMM Dummy | PASS (synthetic) |
| Dummy-HU SDP SPP/`0x1101`/"BMW Connected"/ch.5 | PASS / `CANDIDATE_STRONG` (**TEST**, not BMW) |

## Epistemic hard rules

1. **Channel 5 is lab-only.** Dummy registered ch.5. Real HU channel = **X from SDP**. Never assume 5.
2. Audit values (UUID, `12 34 56 78`, dest `0x0FA4`/`0x1389`) are **REUSE / expectation** until this car measures them.
3. B1 `NONE` is a valid, valuable result — capture and stop; do not invent a service.
4. No B3/relay until B2 shows RFCOMM payload matching the 8-byte BCL header.

## B1 expectation table (verify / falsify)

| Layer | Expectation | Status before A6 | Pass if measured |
|-------|-------------|------------------|------------------|
| BT link | `.87` pairs/connects to HU | UNKNOWN | A6: stable ACL, HU lists ESP |
| SDP | some RFCOMM data service | REUSE | any SPP/vendor128 + channel |
| UUID | SPP `00001101-0000-1000-8000-00805f9b34fb` | REUSE | present **or** documented absent |
| RFCOMM channel | **X from SDP** (not 5) | UNKNOWN | integer channel recorded |
| Service name | maybe BMW/Connected hint | REUSE | name string logged (may differ) |
| BCL framing | 8-byte BE header | REUSE | only after B2 payload |
| BCL init | `12 34 56 78` then HANDSHAKE | REUSE | B2+ only |
| Etch dest | `0x0FA4` | REUSE | B2+ only |
| Watchdog dest | `0x1389` | REUSE | B2+ only |
| SAS | after BCL tunnel | separate gate | do not claim today |

## Connectivity warning (read before driving)

`.87` is an **HCI TCP server** (`:9754`). If the car is only on a **phone hotspot**, `.108` often **cannot dial in** (NAT). Prefer:

- car / `.87` on home FRITZ WiFi, or
- WireGuard / dial-out path already known in the lab

Check before SDP: `curl -s http://192.168.178.87/api/status` from `.108` → `hciAgent.ready` + `client`.

## Car procedure (minimal)

### 0) Preflight on `.108`

```bash
# bridges (if not already up)
python3 /opt/bt-analyzer/tools/hci_tcp_bridge.py 192.168.178.87 &   # → hci for .87
# confirm mapping
hciconfig -a | egrep 'hci|Address|Name'
curl -s http://192.168.178.87/api/status | python3 -m json.tool | head
```

Live mapping (lab 2026-11-12): **hci1 = `.87` / esp87**, **hci2 = `.131`**. Re-check after restart.

### A6 — Bluetooth to HU only

1. HU Bluetooth on; phone Connected app **not** required yet.
2. On `.108`, select the `.87` controller, scan, find HU BD_ADDR.
3. Optional: pair / connect (note: new BD_ADDR → HU sees a new device; remove later).
4. Capture:

```bash
H=$(hciconfig | awk -v b='c8:c9:a3:cb:37:96' 'BEGIN{RS=""} tolower($0)~tolower(b){match($0,/hci[0-9]+/);print substr($0,RSTART,RLENGTH);exit}')
btmon -i "$H" -w /tmp/a6_hu_$(date -u +%Y%m%dT%H%M%SZ).btsnoop
```

**A6 PASS:** HU visible + ACL up (or clear documented fail with capture).

### B1 — SDP only (no RFCOMM data, no BCL TX)

```bash
# replace HU= with measured BD_ADDR; -i = .87 controller
python3 tools/bcl_sdp_probe.py -i hci1 hu=AA:BB:CC:DD:EE:FF --records \
  --json /tmp/sdp_hu_$(date -u +%Y%m%dT%H%M%SZ).json
```

Record: UUID list, service names, **RFCOMM channel X**, verdict.

| Verdict | Action |
|---------|--------|
| `CANDIDATE*` | stop; secure JSON + btsnoop; next session = B2 |
| `NONE` | retry with Connected enabled in HU / app active once; if still NONE → document negative |
| `IAP2_ONLY` | BT SPP path not usable for relay; keep USB track |

### Explicitly do **not** today

- RFCOMM connect / SABM
- send `12 34 56 78` or HANDSHAKE
- BCL relay
- assume channel 5
- enlarge HCI ring / wifi_ps tuning

## After the drive

Copy into `docs/evidence/`:

- `LAB_A6_*` or `FIELD_A6_*` md+json (link, BD_ADDR, btsnoop path)
- `FIELD_B1_SDP_*` from probe JSON

Then update `docs/BCL_BT.md` status line only from MEASURED results.
