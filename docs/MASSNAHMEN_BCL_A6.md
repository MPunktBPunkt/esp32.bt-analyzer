# Maßnahmen — BCL Lab → A6 (Stand 2026-11-12)

```yaml
status: active · A6/B1A done · B2 state A DONE 2026-11-13 Abend · P0 next = state C (MyBMW ON, HFP OFF)
depends_on: [docs/BCL_BT.md, docs/CAR_A6_B1.md, technology-audit bmw-bcl / bmw-bcl-rfcomm / bmw-bcl-handshake / supra-idrive6-android-auto-2026-secondary]
trigger: 2026-11-13 secondary NBT-AAD + RFCOMM two-mode review (initiator UNKNOWN · B2-A/B2-B)
method: docs/analysis/BCL_RFCOMM_TWO_MODE_20261113.md
a6_evidence: docs/evidence/FIELD_A6_HU_20261113T062824Z
b1_evidence: docs/evidence/FIELD_B1_FROM_A6_20261113T062824Z
b2_evidence: docs/evidence/FIELD_B2_20261113T154728Z
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

**Watchdog:** Request `13 37 13 37` / dest 5001 / **Desk 5 s** — **Lab-Wire (AAIdrive/OnePlus) ≈ 2,5 s** (`LAB_PHONE_BCL_20261113T2201Z_DECODE`). 20 s TO + Pong-Bytes = **UNKNOWN** (Client zählt jedes Antwort-Byte).

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
5. **B1/B2 state C** (P0 jetzt) — MyBMW ON, HFP weiter OFF; optional B1-SDP-Delta (`d31fbf50`?); B2-A ch6/5 + B2-B. Dann D (+AAIdrive).
   Engpass nach B2: **Trigger** (Apps-Kontext?) × **Endpoint** (ch6 `0x1101`; ch7–10 Reserve).  
   **ch5 `deca-fade` = Apple iAP2/MFi** — nicht BCL (siehe `BCL_BT.md`). A2DP/AVRCP ≠ BCL-Trigger.
6. **B2-A-TX (billigster Diskriminator):** `field_b1_b2.py b2a-tx --channel 6` — einmal/mehrfach `12 34 56 78`, dann observe HANDSHAKE (kein KNOCK default). BclCarLink-Modell: Phone TX zuerst; observe-only B2-A **muss** leer bleiben. **B3** erst nach HANDSHAKE-Klassifikation; erwartetes MyBMW-`instanceId` **12–14**.

### Hypothesen nach B2 + BimmerGestalt-Abgleich (Stand 2026-11-13 Nacht)

| ID | Hypothese | Status |
|----|-----------|--------|
| **H-A** | BCL auf ch6, HU antwortet auf Phone-INIT | **offen / führend für Wire** — observe-only empty = **Vorhersage**, nicht Falsifikation; entscheidet `b2a-tx` |
| **H-B** | HU initiiert RFCOMM/BCL autonom | State A geschwächt für SABM; BCL-Knock bleibt phone-seitig (BclCarLink/Analysis) |
| **H-C** | MyBMW/Connected aktiviert Apps-Kontext (Handshake-Annahme) | **parallel** zu H-A — State C ± b2a-tx |
| **H-D** | ch5 `deca-fade` = Connected/BCL | **verworfen** — iAP2/MFi (öffentlich + `BCL_BT.md`) |
| **H-E** | ch7–10 relevant | UNKNOWN — nach negativem ch6 |
| **H-F** | BCL nicht über RFCOMM/SPP | unwahrscheinlich, F20 offen |

**B2-A scoped:** „UA + 0 Payload unter observe-only“ = BclCarLink-kompatibel (Client sendet INIT).  
**B2-B scoped:** kein HU-SABM zu *unserem* SPP in State A — nicht „HU öffnet nie SPP“.

### P1 — Lab (parallel / vor nächstem Feld, nicht statt B1)

7. **B2-B observe-only mode** auf bestehendem ProfileManager/Dummy-HU-Agent: SPP listen, Accept, Payload loggen, **BCL-TX hard-off**. Kein neuer BT-Stack. SABM/DLCI weiter über btmon.
8. **B0.7 Differential** — BclCarLink ↔ Dummy-HU (nicht AAIdrive-alone): raw TX == Capture; BCL frames; State OPENING→ACTIVE. Dummy: SPP + RFCOMM accept + HANDSHAKE auf Init; version 3 **und** 4 testen. (B0.7 ≠ B2-B observe-only.)
9. **B0.8** — BclCarLink (+ optional AAIdrive) ↔ **Simulator** :4006: ATTACHED → Etch → SAS-Stub. Epistemik: Simulator-Login ≠ Crypto-FACT.
10. **Phone HCI-Snoop (P1 Differential)** — optional zweites Auge (ACL/RFCOMM/UIH); ersetzt F20-Nachweis **nicht**.
    Beantwortet auch, welche Phone-App den HU-Dienst `deca-fade` (Kanal 5) öffnet.
    Gegen **F20-förmiges** Dummy-SDP (`lab_bcl_dummy_hu_f20_sdp.py`: ch5 `deca-fade` + ch6–10 `0x1101`) — Endpoint-Fingerabdruck; `NO_RFCOMM` bleibt erwartbar (C-L4/5).
11. Post-decode: Resync auf `12 34 56 78`, dann HANDSHAKE `len=8` verlangen — sonst `BCL_MISALIGNED` vs `NO_BCL` (siehe `docs/analysis/BCL_AUDIT_DEEP_20261112.md`).
11b. **Lab-Abend:** OnePlus→Dummy **BCL live** (`LAB_PHONE_BCL_*` + `_DECODE`) — Signatur eingefroren; SELECTPROTO(2); WD≈2,5 s; Certs myBMW/TouchCommand.  
11c. **Priorität ab jetzt:** (1) Baseline eingefroren. (2) **Feld P0:** OnePlus HCI-Snoop ↔ echte F20-HU (+ `.87` btmon Beobachter) — prüft INIT/HANDSHAKE/`instanceId` am Auto. (3) Lab-Orakel L1–L8 / Retry-Matrix / Modus A–C — gezielt nach Feldlücken, nicht blind. (4) Multi-`0x1101` auf **einem** BlueZ-Adapter = blockiert (`LAB_F20_SDP_MIRROR`); Kanalwahl ch6–10 bleibt Feld. (5) Kein B3-Inject / kein ch5-BCL / keine weiteren generischen Dummies vor Feld-Snoop.
11d. **Bimmer-vs-Wire** (`BCL_BIMMER_VS_WIRE_20261113`): Pin `7cfd959`; SELECTPROTO(2)/WD2.5s = Wire≠Desk; AAIdrive-Pin-Drift **unproven**. Desk INIT-Retry ≈**2 s**.  
11e. **CoD-Gate** (`LAB_EVENING_COD_GATE_*`): Computer-CoD → DEADBEEF+UUID-Probe; **`hciconfig hci1 class 0x340408`** stellt BCL INIT wieder her. Lab-Dummy CoD festnageln.

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

**A6/B1A/B2A done. Lab: F20-SDP-Spiegel PASS (`LAB_F20_SDP_MIRROR_*`). P0 nächster Autotermin: State C (MyBMW ON, HFP OFF). Phone-Dummy/B0.7 skipped 13.11. ohne Handy/APK. Negatives Phone-Connect ≠ negatives BCL. B3 blocked.**
