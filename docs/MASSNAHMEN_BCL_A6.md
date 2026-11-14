# Maßnahmen — BCL Lab → A6 (Stand 2026-11-12)

```yaml
status: active · A6/B1A/B2A done · Phone↔HU Logcat 2026-11-14 FIELD FACT (SPP 1101→SCN6 OPEN, HU silent ch6)
depends_on: [docs/BCL_BT.md, docs/CAR_A6_B1.md, technology-audit bmw-bcl / bmw-bcl-rfcomm / bmw-bcl-handshake / supra-idrive6-android-auto-2026-secondary]
trigger: 2026-11-13 secondary NBT-AAD + RFCOMM two-mode review (initiator UNKNOWN · B2-A/B2-B)
method: docs/analysis/BCL_RFCOMM_TWO_MODE_20261113.md
a6_evidence: docs/evidence/FIELD_A6_HU_20261113T062824Z
b1_evidence: docs/evidence/FIELD_B1_FROM_A6_20261113T062824Z
b2_evidence: docs/evidence/FIELD_B2_20261113T154728Z
phone_hu_logcat: docs/evidence/FIELD_PHONE_HU_LOGCAT_20261114T0924Z.md
phone_hu_analysis: docs/analysis/FIELD_PHONE_HU_SPP_20261114.md
raw_full: docs/bluetooth_20261114_083313_01892.txt
raw_reduced: docs/bmw_aaidrive_field_reduced_20261114.txt
hfp_analysis: docs/analysis/HFP_SLC_A6_20261113.md
```

## Simulator: hilft — aber wo?

| Frage | Antwort |
|-------|---------|
| Hilft der BimmerGestalt-**Simulator** (:4006 Etch + SAS-Stub) stark im Lab? | **Ja für Layer E (Post-Handshake)**, nein als Ersatz für A6 |
| Was er beweist | Etch/SAS/**RHMI-Consumer**-Verhalten nach lokalem Tunnel (B0.8) |
| Was er **nicht** beweist | HU-SDP, RFCOMM-Kanal X, SABM-Richtung, echte BCL-**version**, F20-Wire |
| Abgrenzung zu Dummy-HU | Dummy = Layer T/B (SDP/RFCOMM/BCL bootstrap). Simulator = Layer E (Etch@4006). Nicht vermischen |

**Fazit:** Simulator = starker **B0.8**-Hebel nach BclCarLink-Tunnel. **P0 bleibt A6** am F20.

## Schichten (nicht vermischen)

| Layer | Inhalt | Lab | Feld |
|-------|--------|-----|------|
| **T** | Pairing → ACL → SDP → RFCOMM (beide Initiator-Modi) | B0.6 Dummy · B2-B observe-only | A6 / B1 / B2-A / B2-B |
| **B** | `12 34 56 78` → HANDSHAKE → Negotiate → ACTIVE → OPEN **5001** | B0.7 BclCarLink↔Dummy | first UIH klassifiziert / B3.1–B3.7 |
| **E** | localhost :4007 → OPEN **4004** → Etch/SAS | B0.8 BclCarLink↔Simulator (+ AAIdrive) | Capture X vs Y |

**Korrektur:** `OPEN 4004` ist **Consumer-triggered** (EtchProxy erst nach TCP auf :4007), **nicht** deterministischer Bootstrap. Fehlen von OPEN 4004 nach HANDSHAKE ≠ Fehler.

**Watchdog:** Request `13 37 13 37` / dest 5001 / **Desk 5 s** — **Lab-Wire ≈ 2,5 s** (`LAB_PHONE_BCL_*`) — **Feld↔HU (silent) 4‑B-Writes @ 3,0 s** (`FIELD_PHONE_HU_LOGCAT_*`; Hex unproven). 20 s TO + Pong-Bytes = **UNKNOWN**.

## Priorisierte Maßnahmen

### P0 — Feld (nächster Erkenntnissprung)

1. ~~**A6** — `.87` ↔ NBT Evo: ACL + Pairing + `btmon -w`~~ → **PASS** `FIELD_A6_HU_20261113T062824Z` (BMW 38304 / SPP UUID seen).
2. **B1 zustandsweise** — HU=`D4:36:39:CF:E1:B5`, Controller `.87` (hciN neu mappen):
   - ~~A: nur gekoppelt~~ → **DONE** aus A6-Capture (`FIELD_B1_FROM_A6_20261113T062824Z`, `tools/btsnoop_decode.py`):
     HU-Kanal 5 = `deca-fade`-Vendor-UUID („SPP Server 0“), 6–10 = SPP `0x1101`, 2 = HFP 1.6, 1 = MAP-MNS, 11 = OPP;
     A2DP 1.3 (SBC 2..53 / AAC / MPEG-1,2, SCMS-T), AVRCP CT 1.5 **mit Browsing**. HU öffnete in A **keinen** SPP-Kanal.
   - ~~B: + A2DP connected~~ → in A6 mit enthalten (A2DP OPEN/START/SUSPEND), SDP unverändert.
   - C: + MyBMW/Connected aktiv — nur wiederholen, wenn dieser Zustand herstellbar ist
   - D: + AAIdrive aktiv (Kontrolle: Consumer öffnet keinen SPP)
3. ~~**HFP vor B2 abschalten**~~ → **DONE** (`hfp-off` + 50-bt-lab A2DP-only); B2-Capture **0×** `AT+`.
4. ~~**B2-A + B2-B state A**~~ → **DONE** `FIELD_B2_20261113T154728Z`:
   - B2-A ch **6** + ch **5**: SABM local → **UA remote**, 0 Payload, DISC local; BCL **UNKNOWN** (negativ ≠ absent)
   - B2-B observe-only 180 s: **kein** HU-SABM inbound unter Control (Apps/HFP off)
5. ~~**Phone↔HU Logcat (OnePlus, 2026-11-14)**~~ → **DONE** `FIELD_PHONE_HU_LOGCAT_20261114T0924Z`:
   UID 10479 → UUID `0x1101` → SDP **SCN 6** → RFCOMM OPEN (DLCI 13, MTU~666); **10** Opens; Phone TX 5×56 B + 24×4 B @ **3,0 s**; HU auf ch6 **0 RX** (`PORT_DataInd` nur dlci 8/HFP); ACL role=peripheral (HU pages). BCL-Bytes **UNKNOWN**.
6. **B2-A-TX Matrix ch 6–10** (P0 jetzt) — `connectSocket(0x1101)` trifft **nur** ch6; Reserve ch7–10 nur mit explizitem Kanal. Pro Kanal: `field_b1_b2.py b2a-tx --channel N` mit INIT `12 34 56 78` im **3‑s-Takt**, Start **≥15 s nach ACL** (Feld: 5× DM vor erstem UA). Erfolg = UA + UIH-Klassifikation. HFP weiter OFF.
   Engpass: **Trigger** (Apps-State?) × **Endpoint** (ch6 silent gemessen; ch7–10 offen).  
   **ch5 `deca-fade` = Apple iAP2/MFi** — nicht BCL. A2DP/AVRCP ≠ BCL-Trigger.

### Hypothesen nach B2 + Phone-HU-Logcat (Stand 2026-11-14)

| ID | Hypothese | Status |
|----|-----------|--------|
| **H-A** | BCL auf ch6, HU antwortet auf Phone-INIT | **Transport ja / Antwort nein** (Logcat: HU silent ch6) — `b2a-tx` + State C weiter; Handshake weiter offen |
| **H-B** | HU initiiert RFCOMM/BCL autonom | ACL+Mux **ja** (Phone peripheral); SPP-DLC **Phone-Client** (UID 10479) |
| **H-C** | MyBMW/Connected aktiviert Apps-Kontext (Handshake-Annahme) | **parallel** — State mit App + ggf. A2DP-Stream |
| **H-D** | ch5 `deca-fade` = Connected/BCL | **verworfen** — iAP2/MFi (öffentlich + `BCL_BT.md`) |
| **H-E** | ch7–10 relevant | **P0** — ch6 silent; UUID-Fetch trifft nur ersten Record |
| **H-F** | BCL nicht über RFCOMM/SPP | unwahrscheinlich, F20 offen |

**B2-A scoped:** „UA + 0 Payload unter observe-only“ = BclCarLink-kompatibel (Client sendet INIT).  
**B2-B scoped:** kein HU-SABM zu *unserem* SPP in State A — nicht „HU öffnet nie SPP“.

### P1 — Lab (parallel / vor nächstem Feld)

7. **Silent-HU-Modus** — Dummy ohne HS/Pong → Retry Typ A (~10 s/56 B) + Typ B (5×4 B @ 3 s); Pong-Modus ≠ F20-default (`FIELD_PHONE_HU_SPP_20261114`).
8. **B2-B observe-only mode** auf bestehendem ProfileManager/Dummy-HU-Agent: SPP listen, Accept, Payload loggen, **BCL-TX hard-off**.
9. **B0.7 Differential** — BclCarLink ↔ Dummy-HU: raw TX == Capture; version 3 **und** 4.
10. **B0.8** — BclCarLink (+ optional AAIdrive) ↔ **Simulator** :4006. Epistemik: Simulator-Login ≠ Crypto-FACT.
11. **Phone HCI-Snoop** — Hex der Feld-Writes (4/56 B); HU-RX ch6 bereits logcat-leer. Optional `deca-fade` ch5-Owner.
11b. **Lab-Abend:** OnePlus→Dummy **BCL live** (`LAB_PHONE_BCL_*` + `_DECODE`) — Signatur eingefroren; SELECTPROTO(2); WD≈2,5 s.  
11c. **Priorität:** (1) B2-A-TX Matrix ch6–10. (2) Silent-HU Lab. (3) optional HCI-Snoop Hex. (4) kein B3 / kein ch5-BCL.
11d. **Bimmer-vs-Wire** (`BCL_BIMMER_VS_WIRE_20261113`): Pin `7cfd959`; SELECTPROTO(2)/WD2.5s = Wire≠Desk.  
11e. **CoD-Gate** / **WD-Pong** / EOD: unverändert (`LAB_COD_*`, `LAB_WD_PONG_*`, `LAB_EOD_20261114T0030Z`).

### P2 — Docs / Epistemik

12. Sheets/Runbooks: F20-Initiator = **UNKNOWN**; OPEN 4004 = optional/E; Watchdog-Pong ≠ FACT; MyBMW-Opener = **UNKNOWN** (nur BclCarLink = FACT-Client).
13. BclCarLink `BclOutputStream`@7cfd959 Bugs **dokumentiert** (pidrive HU-Technical-Facts **C-D27**): `write(Int)`→`ByteArray(b)`; `sliceArray(off until len)`. **Nicht** in unseren Repos „korrigiert“ (Fremd-Upstream). B0.7/B0.8: Full-Array-Writes bevorzugen; Partial/Etch-Proxy misstrauen.
14. Lab-Evidence `C-L*` / `NO_RFCOMM` + Secondary `C-S*` / `EVID-SUPRA-*` belassen; `field_evidence` erst nach B1+. Secondary **nie** still zu F20-[B].
15. Evidence-Labels strikt: `BT_TRANSPORT` / `BCL_TRANSPORT` / `WD` / `ETCH_TUNNEL` / `SAS` / `RHMI` — nie „Connected works“.

### Explizit **nicht** tun

- Weiter AAIdrive/MyBMW-alone gegen Dummy (NO_RFCOMM erwartet).
- Lab-Dummy-Channel 5 als BMW-Soll. (HU-Kanal 5 existiert, ist aber `deca-fade`, nicht SPP `0x1101` — zufällige Gleichheit der Nummer.)
- B2 mit aktivem HFP-AG fahren (Kanal-13-Rauschen auf dem RFCOMM-Mux).
- RFCOMM-Initiator am F20 voraussetzen (Phone→HU oder HU→Phone).
- B2-A-Negativ als „BCL fehlt“ lesen.
- BCL-TX während B2-B observe-only.
- USB/ENET-BCL als REJECTED.
- Relay/B3-Code vor klassifiziertem BCL payload.
- Secondary NBT-AAD-Claims als F20-[B] übernehmen.
- Simulator-Erfolg als HU-Auth oder F20-Wire werten.
- „Connected funktioniert“ ohne Layer-Tags (T/B/E/WD/SAS/RHMI).

## Gate-Kurzmatrix (Kill)

| Gate | Kill | Bedeutung |
|------|------|-----------|
| T1 HU identity | unsichtbar | BT/Placement |
| T2 SDP | NONE in A–D | Service absent **oder** zustandsabhängig — dokumentieren |
| T3 RFCOMM | SDP ja, kein Link in **beiden** B2-Modi | Transport-Mismatch (nach B2-A **und** B2-B) |
| B1 INIT | RFCOMM, kein `12 34 56 78` | BCL-Pfad unproven (noch Kandidat/anders) |
| B2 HANDSHAKE | INIT, kein HANDSHAKE | HU/BCL mismatch |
| B3 negotiate | version>3 ohne SELECTPROTO/KNOCK | Branch fail |
| B4 WD | ACTIVE, 20 s tot | WD fail/unknown |
| E1 Etch | kein Consumer → kein 4004 | **OK**; Consumer aktiv + kein 4004 → fail |

## Simulator-kt / Analyzer-Umbau (2026-11-13)

| Welt | Werkzeug | Ersetzt F20 B1/B2? |
|------|----------|-------------------|
| A Feldtransport | B1/B2 am F20 | — (einzige Wire-Antwort) |
| B BCL/RFCOMM-Lab | Dummy-HU + BclCarLink + `bcl_framer` / `bcl_classify` | nein |
| C Etch/RHMI-Lab | **Simulator-kt TCP :4006** (SAS-Stub, RHMI, wenig CDS) | nein |

`Simulator-kt` = **Layer E only** — kein BT/SDP/RFCOMM/BCL. B0.8-direkt = AAIdrive→`:4006`. Gateway BCL→Etch = **P2**, nicht vor B1/B2.

Analyzer: **kein** Multi-Wochen-Umbau. Minimal (done/in tree): Klassifikation + B2 observe-only + `field_b1_b2.py`. 1‑h Feld: [`CAR_FIELD_1H.md`](CAR_FIELD_1H.md).

## One-liner

**A6/B1A/B2A done. Phone↔HU Logcat: SPP 1101→SCN6 OPEN FACT, HU silent ch6. P0: B2-A-TX Matrix ch6–10 (3 s INIT, ≥15 s nach ACL) + Lab Silent-HU. B3 blocked.**
