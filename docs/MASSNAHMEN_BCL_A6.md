# Maßnahmen — BCL Lab → A6 (Stand 2026-11-12)

```yaml
status: active · analyzer→F20 TRANSPORT FACT (2026-11-15 Hold/Burst) · Content gate after OPEN4004 · KNOCK isolation next
depends_on: [docs/BCL_BT.md, docs/CAR_A6_B1.md, technology-audit bmw-bcl / bmw-bcl-rfcomm / bmw-bcl-handshake / supra-idrive6-android-auto-2026-secondary]
trigger: 2026-11-15 field Hold/Burst + GPT/Grok DATAACK/KNOCK revision (M48)
method: docs/analysis/BCL_RFCOMM_TWO_MODE_20261113.md · docs/analysis/FIELD_B2A_TX_PATTERNS_20261114.md · docs/analysis/LAB_DUMMY_ETCH_DEEP_20261114.md · docs/analysis/FIELD_STAND_Grok_GPT_20261114.md · docs/evidence/FIELD_VS_LAB_INSIGHTS_20261115.md
field_hold_insights: docs/evidence/FIELD_VS_LAB_INSIGHTS_20261115.md
field_p0_freeze: docs/evidence/FIELD_P0_HOLD_FREEZE_20261115.md
oneplus_forensic: docs/analysis/ONEPLUS_BT_FORENSIC_20261115.md
bmw_bt_evening: docs/analysis/BMW_BT_CONNECTION_ANALYSIS_20261115.md
oneplus_forensic_stats: docs/analysis/oneplus-bt-forensic-stats-20261115.json
lab_dummy_etch: docs/evidence/LAB_DUMMY_ETCH_20261114T1550Z.md
lab_dummy_f20_profile: docs/evidence/LAB_DUMMY_F20_PROFILE_TEMPLATE.md
stand_grok_gpt: docs/analysis/FIELD_STAND_Grok_GPT_20261114.md
a6_evidence: docs/evidence/FIELD_A6_HU_20261113T062824Z
b1_evidence: docs/evidence/FIELD_B1_FROM_A6_20261113T062824Z
b2_evidence: docs/evidence/FIELD_B2_20261113T154728Z
b2a_tx_matrix: docs/evidence/FIELD_B2A_TX_MATRIX_20261114.md
lab_fieldprep: docs/evidence/LAB_FIELDPREP_20261114T095848Z.md
phone_hu_logcat: docs/evidence/FIELD_PHONE_HU_LOGCAT_20261114T0924Z.md
phone_btlogs_pm: docs/evidence/FIELD_PHONE_BTLOGS_20261114T1037Z.md
phone_hu_hs_v5: docs/evidence/FIELD_PHONE_HU_BCL_HS_V5_20261114T1113Z.md
phone_hu_analysis: docs/analysis/FIELD_PHONE_HU_SPP_20261114.md
lab_dummy_evening_btlogs: docs/evidence/LAB_PHONE_DUMMY_BTLOGS_20261114T1732Z.md
lab_dummy_evening_analysis: docs/analysis/LAB_PHONE_DUMMY_SPP_EVENING_20261114.md
lab_live_green: docs/evidence/LAB_LIVE_GREEN_20261114T1654Z.md
raw_full: docs/bluetooth_20261114_083313_01892.log
raw_midday: docs/bluetooth_20261114_103731_10775.log
raw_cleaned_pending: docs/bluetooth_20261114_104405_CLEANED.log
raw_reduced: docs/bmw_aaidrive_field_reduced_20261114.txt
raw_evening:
  - docs/bluetooth_20261114_173248_05337.log
  - docs/bluetooth_20261114_173632_05287.log
  - docs/bluetooth_20261114_173859_26210.log
  - docs/bluetooth_20261114_174045_06218.log
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

**Watchdog:** Request `13 37 13 37` / dest 5001 / **Desk 5 s** — **Lab-Wire ≈ 2,5 s** (`LAB_PHONE_BCL_*`). **Korrektur 2026-11-15:** Silent-HU / Feld-„4‑B @ 3 s“ = **INIT `12345678`**, nicht WD (`LAB_SILENT_HU_INIT_KNOCK_20261115`). 20 s TO + Pong-Bytes = **UNKNOWN**. Desk-WD-Werte ≠ Wire (MyBMW-Generation).

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
   UID 10479 → UUID `0x1101` → SDP **SCN 6** → RFCOMM OPEN (DLCI 13, MTU~666); **10** Opens; Phone TX 5×56 B + 24×4 B @ **3,0 s**; HU auf ch6 **0 RX** (`PORT_DataInd` nur dlci 8/HFP); ACL role=peripheral (HU pages). BCL-Bytes damals UNKNOWN — **4‑B jetzt = INIT** (Silent-HU LAB FACT).
5b. ~~**Phone BT-Logs AAIdrive golden (2026-11-15)**~~ → **DONE** `FIELD_AAIDRIVE_BTLOG_20261115*`: Session B SCN6 → HS v5 → DATA→4004 → CDS-Fragmente (`sensors.SOCBatter*`, …). Session A: SCN6 DM → SCN10 BCL/Etch. Hex-Coverage ~1,65 %. **P0 jetzt: btsnoop_hci Session B (+A)**.
6. ~~**B2-A-TX Matrix ch 6–10**~~ → **DONE / NEGATIVE** `FIELD_B2A_TX_MATRIX_20261114` (+ AUDIOOK-Lauf): ch5–10 Socket refuse; Wire SABM→**DM**. A2DP „BT-Analyzer verbunden“ ändert Accept **nicht**. Analyse: `FIELD_B2A_TX_PATTERNS_20261114`. **M6 herabstufen:** DM ist transient/admission (Session A/B), nicht Peer-Auth-Diskriminierung.
7. ~~**Phone↔Dummy BCL parallel**~~ → **PASS** `LAB_FIELDPREP_20261114T095848Z` (CoD `0x340408` + Alias + App-Restart; SP(2)+WD-Pong; AAIdrive grün).
7b. ~~**Phone BT-Logs Nachmittag**~~ → **DONE** `FIELD_PHONE_BTLOGS_20261114T1037Z`: SCN6 OPEN×4; 0× DataInd dlci13; Typ-B **15,060 s** (M9); Snoop-Filter an / `.cfa` leer; Konsens M6–M15.
7c. **Phone Log ~10:44–11:24 (Grok)** → **REPORTED** `FIELD_PHONE_HU_BCL_HS_V5_*`: HU→Phone HANDSHAKE **v5 / iid 0x0E / buf 0x4000**; cmd6=DATAACK; Session ~25 s. CLEANED-Log noch PENDING.
7d. ~~**B2-A-TX ch6 LIVE**~~ → **PASS / BCL_FIELD_CONFIRMED** `FIELD_B2A_TX_CH6_LIVE_20261114T1525Z`: `.87` ACL+AUTH+ENCRYPT+A2DP → SABM→**UA** → INIT → HU **HS v5/iid14/buf0x4000**.
7e. ~~**B2-A-TX ch6 FULL**~~ → **PASS / HS+DATAACK** `FIELD_B2A_TX_CH6_FULL_20261114T1528Z`: SP(3)+KNOCK+OPEN5001 → DATAACK; **kein WD-TX** (Agent-Bug, fixed).
7f. ~~**SP(2)+WD**~~ → **PASS / WD live** `FIELD_B2A_TX_CH6_SP2_20261114T1531Z`: 90 s, 35× HU-Echo `13371337` + DATAACK `0x0C`.
7g. ~~**SP(3)+WD Kontrolle**~~ → **PASS / WD live** `FIELD_B2A_TX_CH6_SP3WD_20261114T1534Z`: gleich; SP2≠Diskriminator.
7h. ~~**OPEN Etch 4004 + wire OPEN5001**~~ → **WD PASS / Etch empty** `FIELD_B2A_TX_CH6_ETCH_20261114T1539Z`: 180 s, 70× WD-Echo; HU sendet kein `deadbeef`/4004-Payload (OPEN 4004 → extra ACK `0x08`).

### Hypothesen nach F20 WD-ACTIVE + Etch-Negativ (Stand 2026-11-14 ~15:43)

| ID | Hypothese | Status |
|----|-----------|--------|
| **H-A** | BCL auf ch6, HU antwortet auf Phone/Analyzer-INIT | **FIELD CONFIRMED** HS v5 + **WD-Echo ACTIVE** (SP2/SP3). Etch/OPEN4004 weiter offen; DM-Läufe = anderer State |
| **H-B** | HU initiiert RFCOMM/BCL autonom | ACL+Mux **ja**; SPP-DLC Phone-Client (Logcat) |
| **H-C** | MyBMW/Connected aktiviert Apps-Kontext | Lab Dummy: Restart-Hebel **gestärkt**; F20 parallel offen |
| **H-D** | ch5 `deca-fade` = Connected/BCL | **verworfen** |
| **H-E** | ch7–10 als Analyzer-TX-Bypass | **geschwächt** (Matrix: gleicher DM) · UUID-Fetch-only-ch6 steht |
| **H-F** | BCL nicht über RFCOMM/SPP | unwahrscheinlich |
| **H-G** | HU SPP-Accept braucht App-/Owner-State ≠ nur ACL+A2DP | **[H]** gestärkt (M6/M7/M10/M11) |

**B2-A scoped:** „UA + 0 Payload unter observe-only“ = BclCarLink-kompatibel (Client sendet INIT).  
**B2-B scoped:** kein HU-SABM zu *unserem* SPP in State A — nicht „HU öffnet nie SPP“.

**Forschungsfrage (Stand Nachmittag):** Welche Eligibility-/Session-Bedingung veranlasst die HU, genau diesen Peer für RFCOMM/BCL zuzulassen? (nicht nur „wie SPP ch6 starten“)

### P0 / P0.5 / P1 — Priorität (Stand 2026-11-15 Hold/Burst)

7z. ~~**P0 — Analyzer→F20 Transport**~~ → **FIELD FACT** `FIELD_P0_HOLD_*` / `FIELD_BURST_20261115` / `FIELD_VS_LAB_INSIGHTS_20261115`: SCN6 INIT→HS v5/14/0x4000→SP2|SP4→KNOCK→OPEN5001→WD **ohne** MyBMW; OPEN4004→ACK8→Stille; 0× unsolicited 4004 im Hold; **M48** DATAACK selektiv (kein ACK56 nach KNOCK).
8. ~~**P0 — Etch/Layer E Lab**~~ → **DEEP** `FIELD_STAND_Grok_GPT_20261114`. Dummy Etch ≠ F20 Content; UI-Grün ≠ SAS.
9. **P0 — MyBMW-owned btsnoop / Modell-D UI-Hold:** SAS/Etch-Bodies. **Kein** weiterer OPEN4004-Spam ohne Owner-Kontext. Oppo-Textlogs ersetzen HCI **nicht** (`ONEPLUS_BT_FORENSIC_20261115` §7/§20E) — `btsnoop_hci` Session S-B (+S-A) bleibt P0.
9a. ~~**Phone BT-Logs 15.11. Abend+Vormittag Forensik**~~ → **DONE** `ONEPLUS_BT_FORENSIC_20261115` + `BMW_BT_CONNECTION_ANALYSIS_20261115`: HU page→ACL; ~3,0 s HS→DATAACK10; SCN6 golden / SCN10 nur S-A-Failover; 56 B Phone-TX vor ACK10; CDS 667 B ~+10 s ACL; SAS **NOT OBSERVED** in Textlogs.
9b. ~~**P0 — Wire-Client Freeze**~~ → **DONE** `FIELD_P0_HOLD_FREEZE_20261115`; `--knock none` ready.
9c. **P1 — KNOCK-Isolation (nächster Feldlauf):** SP2/4 × KNOCK ja/nein → OPEN5001→WD? Dann KNOCK-ACK-Semantik.
10. **P1 — Admission 2×2 (M7/M33)** UA vs DM; Positive = ACL+AUTH+ENCRYPT + WD.
11. ~~**P1 — Dummy-Feldsignatur**~~ → **SHIPPED** `--hu-profile f20`. Template: `LAB_DUMMY_F20_PROFILE_TEMPLATE`.
11b. ~~**P1 — SAS-Probe-Stufen**~~ → **SHIPPED** `LAB_SAS_PROBE_STAGES_20261115`. **Korrektur:** DATAACK `8+len` für *quittierte* Frames; KNOCK-Ausnahme = M48.
11c. Kein B3 / kein ch5-als-BCL; keine Negativ-Matrix ohne State-Kontrolle.
11d. Bimmer-vs-Wire / CoD / WD-Docs belassen.
11e. **B0.8** Simulator :4006 nach Proxy-Bedarf (SAS-Stub), nicht vor Proxy-Feldtest.
11f. WD-RTT: Cluster ~155 ms + Schwanz ~250–360 ms; HU Miss-Timeout = UNKNOWN (Ping-FIFO+seq gefixt).

### P2 — Docs / Epistemik

12. Sheets/Runbooks: F20-Initiator = **UNKNOWN**; OPEN 4004 = optional/E; Watchdog-Pong ≠ FACT; MyBMW-Opener = **UNKNOWN** (nur BclCarLink = FACT-Client).
13. BclCarLink `BclOutputStream`@7cfd959 Bugs **dokumentiert** (pidrive HU-Technical-Facts **C-D27**): `write(Int)`→`ByteArray(b)`; `sliceArray(off until len)`. **Nicht** in unseren Repos „korrigiert“ (Fremd-Upstream). B0.7/B0.8: Full-Array-Writes bevorzugen; Partial/Etch-Proxy misstrauen.
14. Lab-Evidence `C-L*` / `NO_RFCOMM` + Secondary `C-S*` / `EVID-SUPRA-*` belassen; `field_evidence` erst nach B1+. Secondary **nie** still zu F20-[B].
15. Evidence-Labels strikt: `BT_TRANSPORT` / `BCL_TRANSPORT` / `WD` / `ETCH_TUNNEL` / `SAS` / `RHMI` — nie „Connected works“.

### Explizit **nicht** tun

- AAIdrive/MyBMW gegen Dummy **ohne** CoD `0x340408` / Alias BMW (NO_RFCOMM erwartet; mit Pin = PASS möglich).
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

**Transport FACT (.87→F20 SCN6 HS/WD, no MyBMW). Content gate after OPEN4004 (ACK only). M48: no ACK56 after KNOCK. Next: KNOCK isolation + MyBMW btsnoop/Modell-D. B3 blocked. Dummy green ≠ F20 SAS.**
