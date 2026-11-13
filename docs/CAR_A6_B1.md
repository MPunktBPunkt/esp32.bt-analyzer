# Car runbook — A6 + B1 (F20 / NBT Evo)

```yaml
status: A6_PASS · next B1
lab_closed: [HCI_TCP A1–A5, 62/37 gate, B0.5 BCL synth, B0.6 Dummy-HU SDP, A6 FIELD 2026-11-13]
next: B1 SDP states A–D then B2 split — no relay, no BCL TX, no channel-5 assumption
claim_level: VERIFY reuse expectations from technology-audit/bmw-bcl — not FACT until measured
boards: ".87 = car / HU side (BD c8:c9:a3:cb:37:96) · .131 = phone side (optional)"
linux: ".108 BlueZ + hci_tcp_bridge"
hu_bd: "D4:36:39:CF:E1:B5 (BMW 38304)"
a6_evidence: docs/evidence/FIELD_A6_HU_20261113T062824Z
measures: docs/MASSNAHMEN_BCL_A6.md
note: "lab 2026-11-13 live mapping was hci2=.87 / hci1=.131 — re-check after bridge restart"
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

| Layer | Expectation | Desk pin / status before A6 | Pass if measured |
|-------|-------------|------------------------------|------------------|
| BT link | `.87` pairs/connects to HU | **MEASURED PASS** FIELD_A6 | A6: stable ACL, HU lists ESP |
| SDP | some RFCOMM data service | REUSE (BclCarLink client needs SPP server) | any SPP/vendor128 + channel |
| UUID | SPP `00001101-0000-1000-8000-00805f9b34fb` | REUSE · EVID-BCLRF-002 | present **or** documented absent |
| RFCOMM channel | **X from SDP** (not 5) | UNKNOWN — lab Dummy used 5 only | integer channel recorded |
| Service name | maybe BMW/Connected hint | REUSE | name string logged (may differ) |
| RFCOMM role | HU server / phone client | INFERENCE · EVID-BCLRF-001/003 | SABM direction in B2 |
| BCL framing | 8-byte BE header | REUSE · EVID-BG-001 | only after B2 payload |
| BCL init | `12 34 56 78` then HANDSHAKE | REUSE · EVID-BG-003–005 | B2+ only; record **version** |
| Etch dest | `0x0FA4` | REUSE · EVID-BG-002 | B2+ only |
| Watchdog dest | `0x1389` / ping `13371337` / 5 s / 20 s TO | REUSE · EVID-BCLRF-004 | B2+ only |
| SAS | after BCL tunnel | separate gate (AAIdrive/Addons) | do not claim today |
| AppTypes | A4A/TouchCommand/… possible | Desk dissector · EVID-BG-019 | filter hint only |

Lab note (2026-11-12): MyBMW+AAIdrive vs Dummy-HU = `NO_RFCOMM` — those apps are Etch consumers, not RFCOMM openers. Car B1 still required; optional lab peer = BclCarLink. Matrix: pidrive `HU-Technical-Facts.md` §10.4.

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

Pairing agent (docs/PAIRING.md) must be active, otherwise the HU's Numeric
Comparison is never answered on our side:

```bash
systemctl is-active bt-pair-agent        # active
python3 /opt/bt-analyzer/bt_pair_agent.py --status | python3 -m json.tool | head -40
```

### A6 — Bluetooth to HU only

1. HU Bluetooth on; phone Connected app **not** required yet.
2. On `.108`, select the `.87` controller, scan, find HU BD_ADDR. `.87` is
   discoverable as "BT-Analyzer-Phone" with a smartphone Class of Device.
3. Optional: pair / connect (note: new BD_ADDR → HU sees a new device; remove later).
   Start pairing from iDrive ("Neues Gerät verbinden") or from `.108`. iDrive shows a
   six-digit number; the Lab UI card **Pairing** shows the same number with
   `RequestConfirmation → yes` (agent). **Confirm in iDrive** — that side cannot be
   automated. PiDrive reference: passkey dialog, then HU lists the device
   (`iDriveBt.md` §8, field test 2026-09-16).
4. Capture (start before step 3 to keep the SSP exchange):

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

### B1 states (repeat SDP — service may be state-dependent)

| State | Condition |
|-------|-----------|
| A | paired only |
| B | + A2DP connected |
| C | + MyBMW/Connected active |
| D | + AAIdrive active (control: Etch consumer must not invent SPP) |

Single `NONE` ≠ final “no BCL service” until A–D are covered.

### B2 split (if ACL up and operator time allows)

| # | Measure | Pass signal |
|---|---------|-------------|
| B2.1 | SDP endpoint | UUID + **channel X** + name |
| B2.2 | SABM/UA direction | initiator recorded |
| B2.3 | first payload | `12 34 56 78` candidate → then stop or continue to B3 observe-only |

Do **not** TX BCL from lab scripts in the car. Observe only. `OPEN 4004` is **not** required for BCL bootstrap (consumer-triggered).

### Explicitly do **not** today

- RFCOMM connect / SABM initiated by us
- send `12 34 56 78` or HANDSHAKE from lab
- BCL relay
- assume channel 5
- treat missing OPEN 4004 as fail without AAIdrive/consumer
- enlarge HCI ring / wifi_ps tuning

## After the drive

Copy into `docs/evidence/`:

- `LAB_A6_*` or `FIELD_A6_*` md+json (link, BD_ADDR, btsnoop path)
- `FIELD_B1_SDP_*` from probe JSON
- pairing events: `/var/log/bt-analyzer/pair_events.jsonl` (passkey, answer, reason)

Remove the lab device from the HU afterwards (iDrive device list) and on `.108`:
`python3 tools/lab_pair_agent.py remove C8:C9:A3:CB:37:96 <HU_BD>`.

Then update `docs/BCL_BT.md` status line only from MEASURED results.
