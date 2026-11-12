# BCL over Bluetooth — observe first, relay later (plan)

```yaml
status: lab closed → car · B0.5/B0.6 PASS · A6/B1 OPEN · runbook docs/CAR_A6_B1.md
depends_on: HCI_TCP A1–A6 (docs/HCI_TCP.md) — A1–A5 MEASURED, A6 OPEN
related: hu-probe Gate G2 "BCL wire" (USB AOA path, still open)
claim_level: HYPOTHESIS — "BCL primarily over BT RFCOMM" is not proven for NBT Evo / F20
architecture: controlled dual-leg HCI bridge — not passive Phone↔HU air sniff
audit_reuse: technology-audit technologies/bmw-bcl + projects/esp32-bt-analyzer/applications/bmw-bcl.md
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
| B1 | SDP of the HU (via `.87` controller) **and** of the phone with the app (via `.131`) | `tools/bcl_sdp_probe.py` | verdict `CANDIDATE*` on at least one side → B2 · `NONE` both sides → repeat with app active / Connected enabled in HU menu, then stop BT path |
| B2 | Who is RFCOMM server? Pair the side **without** the service to its D1, start the app, watch `btmon -i hciN` for `RFCOMM` SABM to the channel from B1 | btmon / Lab UI btmon card (filter `RFCOMM`) | first payload bytes match the BCL 8-byte header → G2 evidence over BT |
| B3 | Relay: D1 registers the service found in B1 (same UUID/channel), accepts the client, connects to the real server through the other D1, copies bytes, decodes BCL | new `tools/bcl_rfcomm_relay.py` (Python port of hu-probe `BclFramer`) | app reaches the same state as with a direct link; JSONL has BCL frames both directions |

B1 needs no pairing. B2 pairs a D1 with a real device (new BD_ADDR, so the HU or
phone sees a new device; remove it afterwards).

```bash
# on .108 — re-check hciN after bridge start (lab 2026-11-12: hci1=.87, hci2=.131)
python3 tools/bcl_sdp_probe.py -i hci1 hu=<HU BD_ADDR> --records --json /tmp/sdp_hu.json
python3 tools/bcl_sdp_probe.py -i hci2 phone=<phone BD_ADDR> --records --json /tmp/sdp_phone.json
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
| NBT Evo / F20 offers BCL over BT at all | UNKNOWN → B1 |
| RFCOMM server role (HU or phone) | UNKNOWN → B1/B2 |
| App accepts a D1 as "car" (name, CoD, SDP) | UNKNOWN → B3 |
| SAS/BCL timeouts over WiFi + HCI | expected fine in home LAN; car must be in WiFi range |
| iPhone | iAP2/MFi, out of scope |
| Car behind hotspot NAT | as in HCI_TCP: needs dial-out/VPN, not for B1–B3 |

## Decision rule

The capture decision comes before any relay code: B3 is written only after B2
shows BCL bytes on RFCOMM. If B1 is `NONE` on both sides, the BT path is
documented as negative and G2 stays with the USB track in hu-probe.
