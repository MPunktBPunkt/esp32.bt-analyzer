# Car runbook — A6 + B1 (F20 / NBT Evo)

```yaml
status: A6_PASS · next B1 then B2-A + B2-B
lab_closed: [HCI_TCP A1–A5, 62/37 gate, B0.5 BCL synth, B0.6 Dummy-HU SDP, A6 FIELD 2026-11-13]
next: B1 SDP states A–D · then B2-A (phone/ESP) + B2-B (HU, observe-only) — no B3, no channel-5 assumption
claim_level: VERIFY reuse expectations from technology-audit/bmw-bcl — not FACT until measured
rfcomm_initiator: UNKNOWN  # do not assume Phone→HU or HU→Phone on F20
secondary: technology-audit audits/supra-idrive6-android-auto-2026-secondary (4f70751; pin ac9a292)
method: docs/analysis/BCL_RFCOMM_TWO_MODE_20261113.md
boards: ".87 = car / HU side (BD c8:c9:a3:cb:37:96) · .131 = phone side (optional)"
linux: ".108 BlueZ + hci_tcp_bridge"
hu_bd: "D4:36:39:CF:E1:B5 (BMW 38304)"
a6_evidence: docs/evidence/FIELD_A6_HU_20261113T062824Z
measures: docs/MASSNAHMEN_BCL_A6.md
field_1h: docs/CAR_FIELD_1H.md
field_tool: tools/field_b1_b2.py
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
4. **F20 RFCOMM initiator = UNKNOWN** until SABM direction is measured. BclCarLink Phone→HU is Desk-FACT for that app only; nbt-aad HU→Phone is Secondary (NBT-Evo family), not F20-[B].
5. No B3/relay until B2-A or B2-B shows RFCOMM UIH payload that classifies as BCL (magic → valid header → HANDSHAKE). `12 34 56 78` alone = **candidate**.
6. **B2-A negative ≠ BCL absent** on the F20. Always pair with B2-B (or document why B2-B was skipped).

## B1 expectation table (verify / falsify)

| Layer | Expectation | Desk pin / status before A6 | Pass if measured |
|-------|-------------|------------------------------|------------------|
| BT link | `.87` pairs/connects to HU | **MEASURED PASS** FIELD_A6 | A6: stable ACL, HU lists ESP |
| SDP | some RFCOMM data service | REUSE (BclCarLink client needs SPP server) | any SPP/vendor128 + channel |
| UUID | SPP `00001101-0000-1000-8000-00805f9b34fb` | REUSE · EVID-BCLRF-002 | present **or** documented absent |
| RFCOMM channel | **X from SDP** (not 5) | UNKNOWN — lab Dummy used 5 only | integer channel recorded |
| Service name | maybe BMW/Connected hint | REUSE | name string logged (may differ) |
| RFCOMM role | **UNKNOWN on F20** | Desk: BclCarLink = Phone client (FACT); HU=server = INFERENCE · Secondary: HU may open Apps-Link | SABM in **B2-A and B2-B** |
| BCL framing | 8-byte BE header | REUSE · EVID-BG-001 | only after B2 payload |
| BCL init | `12 34 56 78` then HANDSHAKE | REUSE · EVID-BG-003–005 | B2+ only; record **version** |
| Etch dest | `0x0FA4` | REUSE · EVID-BG-002 | B2+ only |
| Watchdog dest | `0x1389` / ping `13371337` / 5 s / 20 s TO | REUSE · EVID-BCLRF-004 | B2+ only |
| SAS | after BCL tunnel | separate gate (AAIdrive/Addons) | do not claim today |
| AppTypes | A4A/TouchCommand/… possible | Desk dissector · EVID-BG-019 | filter hint only |

Lab note (2026-11-12): MyBMW+AAIdrive vs Dummy-HU = `NO_RFCOMM` — those apps are Etch consumers, not RFCOMM openers. Car B1 still required; optional lab peer = BclCarLink. Matrix: pidrive `HU-Technical-Facts.md` §10.4.

Secondary (2026-11-13, NBT-AAD / `4f70751`): HU SPP `/dev/btspp*`, MyBMW contention, AAIdrive ≠ BT owner, `12 34 56 78` heuristic — **plausible for F20, not proven**. Do not copy into F20-[B].

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

### B2 — two modes (both required unless operator documents skip)

Do not presuppose initiator. Run **B2-Control** first, then B2-A and B2-B.

#### B2-Control (Versuchsbedingung, kein Protokollfakt)

```text
MyBMW       OFF / force-stopped
AAIdrive    OFF / force-stopped
A2DP        document (on/off as measured)
```

Optional comparison runs after baseline: MyBMW ON / AAIdrive OFF; MyBMW OFF / AAIdrive ON; both ON. Log SDP deltas, RFCOMM build, initiator, first UIH, BCL vs non-BCL.

#### B2-A — Phone/ESP initiates

```text
ESP/.87 ── RFCOMM connect() ──► F20 HU
```

| # | Measure | Pass signal |
|---|---------|-------------|
| B2-A.1 | SDP endpoint from B1 | UUID + **channel X** + name used for connect |
| B2-A.2 | SABM from `.87`, UA from HU | initiator = phone/ESP |
| B2-A.3 | UIH + first payload | hex logged; `12 34 56 78` = candidate only |

Negative B2-A ⇒ **`B2-A negative`** only — **not** „BCL fehlt am F20“.

#### B2-B — HU initiates (observe-only server)

```text
ESP/.87: SPP register + RFCOMM server wait
F20 HU ──────────────── RFCOMM connect ──► .87
```

Reuse B0.6 ProfileManager path, but **observe-only** (no BCL TX from lab). Lab channel 5 remains lab-only for Dummy; for car, register the UUID/name under test and record what the HU actually dials.

`.87` must:

```text
SPP-Service registrieren · SDP sichtbar · RFCOMM-Server öffnen
eingehende Verbindung akzeptieren · HCI/RFCOMM vollständig mitschneiden
```

Also log: phone-service UUID, service name, RFCOMM channel, HU SDP browse if visible, HU-initiate timestamp, SABM direction, first UIH payload.

| # | Measure | Pass signal |
|---|---------|-------------|
| B2-B.1 | HU finds phone SPP and dials | SDP accept ≠ proven use — need SABM |
| B2-B.2 | SABM from HU, UA from `.87` | initiator = HU |
| B2-B.3 | UIH + first payload | hex logged unmodified |

**B2-B before classification — hard ban:**

```text
kein 12 34 56 78 senden
kein HANDSHAKE / SELECTPROTO / KNOCK / OPEN senden
keine BCL-Antwort simulieren
```

Server may only: accept RFCOMM, capture frames, log payload unchanged.

Negative B2-B ⇒ **`B2-B negative`** only — **not** „kein BCL“.

#### Shared B2 decode chain

```text
RFCOMM → first UIH → 12 34 56 78 (candidate) → valid BCL header
  → HANDSHAKE → version / instanceId / bufferSize
  → SELECTPROTO / KNOCK → ACTIVE
```

`OPEN 4004` is **not** required for BCL bootstrap (consumer-triggered).

#### Capture Pflichtfelder

`session_id`, `hci_adapter`, `local_bdaddr`, `remote_bdaddr`, `hci_timestamp`, `acl_handle`, `acl_direction`, `rfcomm_channel`, `rfcomm_dlci`, `rfcomm_frame_type`, `frame_direction`, `sabm`/`ua`/`dm`/`disc`/`uih`, `payload_length`, `payload_hex`, `first_uih_timestamp`, `first_uih_direction`, `connection_state` · plus SDP/BCL candidate fields when known.

ACL-Richtung ≠ RFCOMM-Richtung ≠ BCL-Payload-Richtung.

Optional P1: Android phone `btsnoop` as **differential** evidence — does not replace F20 proof.

### Explicitly do **not** today

- Treat B2-A alone as full RFCOMM/BCL verdict
- send BCL (`12 34 56 78`, HANDSHAKE, …) during **B2-B** observe-only
- BCL relay / B3 before classified BCL payload
- assume channel 5 or a fixed initiator
- treat missing OPEN 4004 as fail without AAIdrive/consumer
- upgrade Secondary NBT-AAD claims to F20-[B]
- enlarge HCI ring / wifi_ps tuning

## After the drive

Copy into `docs/evidence/`:

- `LAB_A6_*` or `FIELD_A6_*` md+json (link, BD_ADDR, btsnoop path)
- `FIELD_B1_SDP_*` from probe JSON
- pairing events: `/var/log/bt-analyzer/pair_events.jsonl` (passkey, answer, reason)

Remove the lab device from the HU afterwards (iDrive device list) and on `.108`:
`python3 tools/lab_pair_agent.py remove C8:C9:A3:CB:37:96 <HU_BD>`.

Then update `docs/BCL_BT.md` status line only from MEASURED results.
