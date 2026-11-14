# 1‑Stunden Feldfenster — B2-A (Kanal 6 + 5) + B2-B

```yaml
goal: maximaler Wire-Erkenntnisgewinn in ≤60 min
tx_policy: B2-A-TX Matrix ch6–10 (INIT 3s); observe after TX
hu: D4:36:39:CF:E1:B5
phone_esp: C8:C9:A3:CB:37:96 (.87)
host: .108 via SSH
tools: tools/field_b1_b2.py · tools/lab_hfp_stack.py · tools/btsnoop_decode.py
b1_sdp_state_a: PASS / MEASURED — docs/evidence/FIELD_B1_FROM_A6_20261113T062824Z.md
b2_state_a: DONE 2026-11-13 — docs/evidence/FIELD_B2_20261113T154728Z.md
phone_hu_logcat: DONE 2026-11-14 — docs/evidence/FIELD_PHONE_HU_LOGCAT_20261114T0924Z.md (1101→SCN6 OPEN; HU silent ch6)
lab_f20_sdp_mirror: PASS LAB_TEST — docs/evidence/LAB_F20_SDP_MIRROR_20261113T174006Z.md (ch5+ch6; ch7–10 BlueZ UUID limit)
next: b2a-tx ch6–10 @ 3s, start ≥15s after ACL; optional HCI-Snoop for 4/56B hex
note: "Phone app hits only first 0x1101 (=ch6); ch7–10 need explicit channel"
```

## Stand aus A6 (2026-11-13)

HU-SDP ist bekannt (MEASURED, `FIELD_B1_FROM_A6_20261113T062824Z`):

| HU-Kanal | Dienst | Bedeutung für B2 |
|---:|---|---|
| 5 | „SPP Server 0“, UUID `00000000-deca-fade-deca-deafdecacaff` | **Apple iAP2/MFi** — nicht BCL; B2-A ch5 nur Referenz/Transport |
| 6 | „SPP Server 1“, SPP `0x1101` | Erster `0x1101` → BclCarLink-Ziel — **B2-A / B2-A-TX** |
| 7–10 | „SPP Server 2–5“, SPP `0x1101` | Reserve |
| 2 / 1 / 11 | HFP 1.6 HF / MAP-MNS / OPP | nicht BCL |

- HU-Kanal 5 = `deca-fade` der HU. **Nicht** der Lab-Dummy-Kanal 5 — nie gleichsetzen.
- In state A hat die HU **keinen** SPP-/BCL-Kanal geöffnet; einziger RFCOMM-Verkehr war HFP.
- HFP-SLC scheitert an `AT+CHLD=?` → HU öffnet alle 20–35 s unseren Kanal 13 neu
  ([`HFP_SLC_A6_20261113.md`](analysis/HFP_SLC_A6_20261113.md)). Vor B2 abschalten.

## Vor der Fahrt (daheim, 10 min)

```bash
python3 tools/lab_hfp_stack.py diag               # Stack auf .108 (erwartet: pipewire-native)
python3 tools/lab_hfp_stack.py hfp-off            # Trockenlauf: Drop-in prüfen
python3 tools/lab_hfp_stack.py hfp-off --apply    # A2DP bleibt, HFP/HSP weg
python3 tools/field_b1_b2.py preflight            # darf keine HFP-AG-Warnung mehr zeigen
```

- Pairing zu BMW 38304 gültig (A6). Sonst neu pairen, Agent-Fenster: `python3 tools/lab_pair_agent.py window 300`.
- Phone: **MyBMW force-stop**, **AAIdrive force-stop** (B2-Control).
- Optional: Phone HCI-Snoop einschalten (B2-C, P1).

## Im Auto (Ziel: 45–55 min)

| Min | Schritt | Befehl / Aktion |
|----:|---------|-----------------|
| 0–3 | Preflight + btmon | `preflight` · `btmon-start` |
| 3–8 | Ruhephase gekoppelt | nichts tun; prüft, dass HU ohne HFP **keinen** Kanal mehr öffnet |
| 8–12 | Ruhe ≥15 s nach ACL | Feld: 5× DM vor erstem UA — nicht zu früh TX |
| 12–22 | **B2-A-TX ch 6** | `b2a-tx --channel 6` INIT @ **3 s**; UA erwartet; HU-RX auf ch6 im Logcat = 0 |
| 22–40 | **Matrix ch 7–10** | je `b2a-tx --channel N` (explizit; UUID-Fetch trifft nur ch6) |
| 40–46 | optional ch5 | nur iAP2-Referenz; nicht BCL |
| 46–55 | Stop + pull + decode | `btmon-stop` → Klassifikation pro Kanal |
| 55–60 | Kurznotiz | Silent vs HANDSHAKE; welcher Kanal antwortet |

```bash
python3 tools/field_b1_b2.py btmon-start
python3 tools/field_b1_b2.py b2a --channel 6 --seconds 30          # expect empty (BclCarLink model)
python3 tools/field_b1_b2.py b2a-tx --channel 6 --init-count 3     # INIT → wait HANDSHAKE
python3 tools/field_b1_b2.py b2b --hold 180                        # State C: MyBMW ON
python3 tools/field_b1_b2.py btmon-stop --session-id FIELD_B2_<stamp>
```

`btmon-stop` legt `FIELD_B2_<stamp>.btsnoop` + `_decode.json/.md` unter `docs/evidence/` ab
(SDP, RFCOMM-Sitzungen mit Initiator, erste UIH, `bcl_classify`-Stufe, Pflichtschema).

B1 nur wiederholen, wenn sich der HU-Zustand ändert (state C/D: Phone-App aktiv) — dann
`b1 --state C|D` vor B2. State A/B liefern keine neue Information.

## Was heute beantwortet werden kann

| Frage | Quelle |
|-------|--------|
| Phone-init RFCOMM ch6 möglich? | B2-A (SABM/UA) |
| HU spricht BCL zuerst? | B2-A observe — unter BclCarLink **nein erwartet** |
| HU antwortet auf `12 34 56 78`? | **B2-A-TX** → HANDSHAKE? (`instanceId` 12–14 = MyBMW-ish) |
| HU-init RFCOMM? | B2-B |
| first UIH / BCL-Kandidat? | `btmon-stop` → `bcl_classification` pro Sitzung |
| Initiator am F20 | SABM-Richtung B2-A vs B2-B |

## Lesart

- B2-A ohne UIH von der HU ≠ „kein BCL“: Bei BCL sendet vermutlich das Phone `12 34 56 78` zuerst, und wir senden nicht.
- B2-A mit DM auf Kanal 5 heißt nur, dass `deca-fade` in diesem Zustand nicht annimmt.
- B2-B erwartet einen SABM der HU auf **unseren** SPP-Kanal. In A6 hat die HU unser SDP nur nach HFP abgefragt.

## Was heute **nicht** Ziel ist

- B3 / Relay / BCL-TX
- Simulator / Etch / SAS
- Lab-Dummy-Kanal 5 als HU-Soll (HU-Kanal 5 = `deca-fade`, separat)
- B2-A-Negativ = „kein BCL“
- MyBMW/AAIdrive Contention-Matrix (nur Baseline OFF)
- HFP reparieren (nach dem Feldtermin: `lab_hfp_stack.py hfp-on --apply`)

## Nach der Fahrt (daheim)

```bash
python3 tools/btsnoop_decode.py docs/evidence/FIELD_B2_<stamp>.btsnoop
python3 tools/bcl_classify.py --hex '...' --json      # Einzel-Payload nachprüfen
python3 tools/lab_hfp_stack.py hfp-on --apply         # nur wenn HFP wieder gebraucht wird
```

Stufen: `UNKNOWN` → `BCL_CANDIDATE` (`12 34 56 78`) → `STRONG_BCL_CANDIDATE` → `BCL_FIELD_CONFIRMED` (HANDSHAKE).

B2-B Evidence muss `tx_bytes_events: 0` haben.

## Simulator / großer Analyzer-Umbau

**Nicht heute.** `Simulator-kt` = Layer E TCP `:4006` only. Minimal-Analyzer-Patch (Klassifikation + observe-only) ist vorbereitet; voller HCI→Etch-Umbau = Wochen, nicht nötig für B1/B2.
