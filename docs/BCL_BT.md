# BCL over Bluetooth — observe first, relay later (plan)

```yaml
status: A6/B1A/B2A PASS · Logcat HU silent ch6 · B2-A-TX Matrix 2026-11-14 NEGATIVE (DM ch5–10) · Lab Dummy BCL PASS parallel
depends_on: HCI_TCP A1–A6 (docs/HCI_TCP.md) — A1–A5 MEASURED, A6 MEASURED 2026-11-13
related: hu-probe Gate G2 "BCL wire" (USB AOA path, still open)
claim_level: TRANSPORT FIELD FACT (SCN6 OPEN) · BCL payload HYPOTHESIS — HU silent on ch6; Analyzer TX refused
rfcomm_initiator: MIXED  # ACL+Mux HU→Phone; SPP DLC Phone-client (UID 10479) — docs/evidence/FIELD_PHONE_HU_LOGCAT_20261114T0924Z.md
secondary: technology-audit audits/supra-idrive6-android-auto-2026-secondary @4f70751
method: docs/analysis/BCL_RFCOMM_TWO_MODE_20261113.md · docs/analysis/FIELD_PHONE_HU_SPP_20261114.md · docs/analysis/FIELD_B2A_TX_PATTERNS_20261114.md
architecture: controlled dual-leg HCI bridge — not passive Phone↔HU air sniff
audit_reuse: technology-audit technologies/bmw-bcl + projects/esp32-bt-analyzer/applications/bmw-bcl.md
next: Phone HCI-Snoop Hex · Silent-HU Lab · b2a-tx isoliert (kein paralleles Phone-A2DP)
```

## Why

BMW Connected tunnels Etch/SAS/RHMI inside **BCL** (BMW Connected link layer).
The transport is either USB (AOA / iAP) or Bluetooth SPP (RFCOMM). hu-probe has
seen no BCL on USB AOA so far (G2 open). bimmergestalt's `BclCarLink` speaks BCL
over RFCOMM, which makes the Bluetooth path the second independent chance.
Connected traffic is cleartext above the transport (C-D11). On HCI it is also
above link encryption, so a capture shows the BCL frames directly.

The HCI agent gives a **controlled** capture point (Phone⇄`.131` and, after A6,
`.87`⇄HU), not a passive listen on an existing Phone↔HU air link. For PiDrive
the value is correlating BCL/HCI timestamps with USB-MSC events once B2 proves
RFCOMM bytes on the real HU.

## Target picture (B3, only if B1/B2 say yes)

```text
Phone (Connected app) ─BT─ D1 .131 (acts as "car")   ═╗
                                                      ╠═ RFCOMM relay on .108 → BCL decoder → JSONL
BMW HU ─BT─ D1 .87 (acts as "phone")                 ═╝   + btmon (RFCOMM payload in clear)
```

The relay copies RFCOMM bytes 1:1 and only logs. SAS authentication stays end to
end between app and HU; nothing is modified or bypassed.

## Steps

| # | Step | Tool | Pass / decision |
|---|------|------|-----------------|
| B0 | HCI_TCP A1–A6 | `docs/HCI_TCP.md` | both D1 as BlueZ controllers |
| B0.5 | Synthetic BCL stream (hu-probe CaC1) offline + optional RFCOMM Dummy-HU `.87`↔`.131` | `tools/bcl_framer.py`, `tools/lab_bcl_synth_stream.py` | framer emits HANDSHAKE/DATA(`SYNTH01`)/UNKNOWN then sticky `PayloadTooLarge`; RFCOMM mode proves bytes survive HCI TCP ↔ BlueZ — **not** BMW wire FACT |
| B0.6 | Dummy-HU advertises SPP `"BMW Connected"` ch.5 via ProfileManager; phone-side `sdptool browse` | `tools/lab_bcl_dummy_hu_sdp.py` | `bcl_sdp_probe` verdict `CANDIDATE_STRONG` — messkette for B1 ready without real HU |
| B0.7 | Dummy-HU on `.131` = SPP server **and** A2DP sink; keeps RFCOMM open, answers `12 34 56 78` with HANDSHAKE, logs frames (JSONL). Synthetic: `.87` pairs, A2DP-connects, checks the BclCarLink gate, then runs init → HANDSHAKE → (SELECTPROTO) → KNOCK → watchdog. External: real phone with the app | `tools/lab_bcl_dummy_hu_a2dp.py` (+ `bcl_dummy_hu.py`, `bcl_dummy_hu_agent.py`) | synthetic `PASS`; external `BCL_INIT_SEEN` / `BCL_KNOCK_SEEN` = the app speaks BCL over BT to a D1 — still not HU wire |
| B1 | SDP of the HU (via `.87` controller) **and** of the phone with the app (via `.131`) | `tools/bcl_sdp_probe.py` | verdict `CANDIDATE*` on at least one side → B2 · `NONE` both sides → repeat with app active / Connected enabled in HU menu, then stop BT path |
| B2-A | Phone/ESP initiates RFCOMM to HU channel X from B1; `btmon` SABM/UA/UIH | btmon + optional RFCOMM client | SABM from `.87`; first UIH classifies BCL (candidate → header → HANDSHAKE). Negative ≠ BCL absent |
| B2-B | `.87` registers SPP + RFCOMM **observe-only** server; wait for HU dial | ProfileManager (B0.6 reuse) + btmon | SABM from HU; payload logged unmodified; **no** BCL TX from lab. Negative ≠ kein BCL |
| B3 | Relay: D1 registers the service found in B1 (same UUID/channel), accepts the client, connects to the real server through the other D1, copies bytes, decodes BCL | new `tools/bcl_rfcomm_relay.py` (Python port of hu-probe `BclFramer`) | app reaches the same state as with a direct link; JSONL has BCL frames both directions · **only after** B2 BCL classification |

B0.7 order matters: the dummy must run **before** the phone pairs or connects,
otherwise the phone's cached SDP has no SPP UUID and the app skips the device
(Android: re-pair or toggle BT). HU replies after HANDSHAKE are unknown; the
dummy stays silent, so a BclCarLink-like client drops the link after the 20 s
watchdog timeout unless `--echo-watchdog` is set.

B0.7 external and B2 need `bt-pair-agent` on `.108` (`docs/PAIRING.md`): the
phone starts pairing, the passkey shows in the Lab UI card **Pairing**, confirm on
the phone. Synthetic B0.7 uses the agent too (Numeric Comparison on both D1s via
`busctl`); without it the script falls back to Just Works and records
`pair_agent: false`.

```bash
python3 tools/lab_bcl_dummy_hu_a2dp.py                       # synthetic, .131 = HU-dummy
python3 tools/lab_bcl_dummy_hu_a2dp.py --hu-version 4        # phone must send SELECTPROTO(3)
python3 tools/lab_bcl_dummy_hu_a2dp.py --peer external --seconds 180 --echo-watchdog
```

B1 needs no pairing. B2 pairs a D1 with a real device (new BD_ADDR, so the HU or
phone sees a new device; remove it afterwards with `tools/lab_pair_agent.py remove`).

```bash
# on .108 — re-check hciN after bridge start (2026-11-13 live: hci2=.87, hci1=.131)
python3 tools/bcl_sdp_probe.py -i hci2 hu=D4:36:39:CF:E1:B5 --records \
  --json /tmp/sdp_hu_$(date -u +%Y%m%dT%H%M%SZ).json
python3 tools/bcl_sdp_probe.py -i hci1 phone=<phone BD_ADDR> --records --json /tmp/sdp_phone.json
```

Car procedure + B1 expectation table: [`CAR_A6_B1.md`](CAR_A6_B1.md).
**Do not assume RFCOMM channel 5** (Dummy-HU lab only); measure **X** from HU SDP.

The verdict marks SPP (`0x1101`) and vendor 128-bit UUIDs with an RFCOMM channel
as candidates. A BMW/Connected service name upgrades the verdict to
`CANDIDATE_STRONG`. iAP2-only (`…deca-fade…`) means the Apple accessory path
(MFi), which is not usable for a relay.

## Unknowns and risks

| Item | State |
|------|-------|
| A6 `.87`↔HU ACL + Numeric Comparison | **MEASURED PASS** `FIELD_A6_HU_20261113T062824Z` (BMW 38304 / `D4:36:39:CF:E1:B5`) |
| HU advertises SPP `00001101` after bond | **MEASURED** (BlueZ UUID list; SDP channel X still B1) |
| NBT Evo / F20 offers BCL over BT at all | UNKNOWN → B1 (SPP present ≠ BCL) |
| RFCOMM initiator on **this F20** | **UNKNOWN** — do not assume. BclCarLink Phone→HU = Desk-FACT; nbt-aad HU→Phone = Secondary NBT-family (`supra-idrive6-android-auto-2026-secondary` / `4f70751`) |
| HU = SDP server / phone = client | Desk **INFERENCE** (EVID-BCLRF-003) for BclCarLink path only → falsify with B2-A **and** B2-B |
| App only tries A2DP-connected devices that list SPP | FACT for **BclCarLink** (`BtClientService`); **not** the AAIdrive/MyBMW opener path |
| MyBMW + AAIdrive open RFCOMM to Dummy-HU (A2DP+SPP up) | **REJECTED** for this setup — `LAB_BCL_DUMMY_HU_A2DP_20261112T172006Z` `NO_RFCOMM` (AAIdrive = Etch consumer; needs Connected/BclCarLink as link owner) |
| HU SPP `/dev/btspp*`, MyBMW contention, `looksLikeBmwBcl` | SECONDARY (NBT-Evo family) — F20-plausible, **not** F20-[B] |
| App accepts a D1 as "car" (name, CoD, SDP) | UNKNOWN → needs BclCarLink peer or real HU B3 |
| SAS/BCL timeouts over WiFi + HCI | expected fine in home LAN; car must be in WiFi range |
| iPhone | iAP2/MFi, out of scope |
| Car behind hotspot NAT | as in HCI_TCP: needs dial-out/VPN, not for B1–B3 |
| USB/ENET BCL vs BT-only | Desk **Contradiction/HYPOTHESIS** (EVID-BG-020) — not REJECTED; AOA+car can resolve |

**Next (epistemic order):** **B1** SDP on bonded HU (`hu=D4:36:39:CF:E1:B5`, `-i hci2` — re-check mapping) states A→D · then **B2-A + B2-B**. Method [`BCL_RFCOMM_TWO_MODE_20261113.md`](analysis/BCL_RFCOMM_TWO_MODE_20261113.md) · Runbook [`CAR_A6_B1.md`](CAR_A6_B1.md) · Maßnahmen [`MASSNAHMEN_BCL_A6.md`](MASSNAHMEN_BCL_A6.md). Optional lab: **B0.7** BclCarLink↔Dummy, **B2-B observe-only mode** on ProfileManager, **B0.8** Simulator — not AAIdrive-alone.

## Decision rule

The capture decision comes before any relay code: B3 is written only after B2
shows BCL bytes on RFCOMM. If B1 is `NONE` on both sides, the BT path is
documented as negative and G2 stays with the USB track in hu-probe.
