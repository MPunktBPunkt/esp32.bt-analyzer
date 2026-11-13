# BCL RFCOMM two-mode methodology (2026-11-13)

```yaml
status: desk_verified
trigger: post-secondary NBT-AAD audit + method review
secondary: technology-audit audits/supra-idrive6-android-auto-2026-secondary (commit 4f70751)
upstream_pin: Sq00ky/Supra-iDrive6-Android-Auto@ac9a292  # not a local git object
claims_doc: pidrive HU-Technical-Facts §10
runbook: docs/CAR_A6_B1.md
measures: docs/MASSNAHMEN_BCL_A6.md
```

Epistemic: **No new F20 wire FACT.** Secondary = NBT-Evo family hint only.

## 1. Verdict

The secondary finding is methodically relevant and does **not** change F20 BCL status.

```text
F20 Bluetooth ACL:     FIELD-MEASURED (A6 PASS)
F20 RFCOMM initiator:  UNKNOWN
F20 BCL:               UNKNOWN
```

Hard consequence:

> **RFCOMM initiator on this F20 must not be presupposed.**

Two models must coexist until HCI/RFCOMM capture resolves them:

| Source | Model | Classification |
|--------|-------|----------------|
| BimmerGestalt / BclCarLink | Phone opens RFCOMM client → HU SPP | Desk-FACT for BclCarLink |
| nbt-aad / NBT-Evo secondary | HU opens BMW-Apps link → phone | SECONDARY EVIDENCE · NBT-EVO FAMILY · F20 plausibel, nicht bewiesen |

Do **not** resolve by declaring one source wrong. Possible: different generations, apps, session phases, services, observation points, or AA vs BMW-Apps paths.

## 2. Block A — Repository abgleich

| Check | Result |
|-------|--------|
| `4f70751` in technology-audit | **present** — secondary note + sheet/app cross-links |
| `ac9a292` as local git object | **absent** — upstream pin only (`reviewed_commit` in secondary README) |
| Secondary marked SECONDARY / NBT-family | **yes** in technology-audit; must stay out of F20-[B] |
| Accidental `[B]` / FIELD / MEASURED for F20 RFCOMM/BCL | **none** found for initiator/BCL; A6 ACL remains MEASURED |
| Phone→HU vs HU→Phone Spannung explicit | **yes** in secondary evidence + bmw-bcl sheet; runbooks updated here |

Secondary claims allowed only as:

```text
SECONDARY EVIDENCE
NBT-EVO FAMILY
F20-RELEVANZ: plausibel, nicht bewiesen
```

Not as `HU-Technical-Facts` F20-[B].

## 3. Block B — Runbook deltas (applied)

- B2 becomes **B2-A** (phone/ESP initiates) + **B2-B** (HU initiates, `.87` listen).
- Negative B2-A ≠ „BCL fehlt am F20“.
- B2-B = **observe-only** before classification (no `12 34 56 78` / HANDSHAKE / SELECTPROTO / KNOCK / OPEN TX).
- B3 stays gated on first UIH → BCL classification.
- Channel 5 remains lab-only.
- `12 34 56 78` alone = **BCL candidate**, not full proof.

## 4. Block C — ProfileManager / B0.6 reuse for B2-B

Existing tools (`lab_bcl_dummy_hu_sdp.py`, `bcl_dummy_hu_agent.py` hu mode):

| Need for B2-B | Status |
|---------------|--------|
| Register SPP / SDP announce | **yes** (ProfileManager1, Role=server) |
| Accept incoming RFCOMM | **yes** (`NewConnection`) |
| Stay in listen mode | **partial** — `--hold` then exit; OK for timed sessions |
| No outbound connect | **yes** in hu mode |
| HCI events before accept | **via btmon**, not in agent |
| SABM/UA/DLCI direction | **via btmon**, not in Profile1 callbacks |
| Full UIH payload store | **partial** — agent logs `hex` truncated to 64 B; use btmon/btsnoop for full |
| BCL transmitter off | **no** — `DummyHuSession` auto-answers init with HANDSHAKE |
| Multi-session separation | **partial** — per-fd sessions; need explicit `session_id` in evidence |

Conclusion: **reuse B0.6 stack**, add explicit **`B2-B observe-only server mode`** (no BCL TX). No new Bluetooth stack required. SABM/DLCI remain btmon-primary.

**Implemented 2026-11-13:** `bcl_dummy_hu_agent.py` modes `b2b`/`b2a` (tx hard-off + `tx_blocked`), `ObserveOnlySession`, `bcl_classify.py` levels, `field_b1_b2.py`, runbook `docs/CAR_FIELD_1H.md`.

## 5. Block D — Capture Pflichtschema

Required fields (session JSON / decode notes):

```text
session_id, hci_adapter, local_bdaddr, remote_bdaddr, hci_timestamp,
acl_handle, acl_direction, rfcomm_channel, rfcomm_dlci, rfcomm_frame_type,
frame_direction, sabm, ua, dm, disc, uih, payload_length, payload_hex,
first_uih_timestamp, first_uih_direction, connection_state
```

Additional when available:

```text
sdp_uuid, service_name, service_description, rfcomm_server_channel, sdp_timestamp,
bcl_candidate, bcl_magic_offset, bcl_header_valid, bcl_command,
bcl_source, bcl_destination, bcl_data_length
```

Separations (already methodological rule):

```text
ACL-Richtung ≠ RFCOMM-Richtung ≠ BCL-Payload-Richtung
SDP-Provider ≠ SABM-Initiator ≠ BCL-Initiator ≠ Etch-Consumer
```

Phone `btsnoop` = **P1 Differential Evidence**, not a substitute for F20 proof / not a B1/B2 prerequisite.

## 6. Decision table

| Result | Statement |
|--------|-----------|
| B2-A +, B2-B − | Phone-initiated path under that condition |
| B2-A −, B2-B + | HU-initiated path under that condition |
| both + | multiple services/states/roles possible |
| both − | not a BCL counter-proof — check tooling, state, SDP, contention |
| RFCOMM without UIH | transport up, no BCL yet |
| UIH without BCL marker | unknown/other payload |
| `12 34 56 78` alone | BCL candidate |
| valid BCL header | strong BCL candidate |
| valid HANDSHAKE | BCL practically confirmed |
| ACTIVE / Watchdog | fuller session evidence |
| Etch `OPEN 4004` | consumer path after BCL — not transport proof |

## 7. Field order

```text
B1 SDP (A–D)
  → B2-A phone/ESP initiate
  +  B2-B HU initiate (observe-only)
  → SABM/UA/DLCI/UIH
  → first payload → BCL classification
  → B3 only after that
```

Central working rule:

> A negative phone-side RFCOMM connect test must no longer be read as a negative BCL finding.
