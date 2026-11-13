# Maßnahmen — BCL Lab → A6 (Stand 2026-11-12)

```yaml
status: active · A6 done 2026-11-13 · P0 now B1 then B2-A+B2-B
depends_on: [docs/BCL_BT.md, docs/CAR_A6_B1.md, technology-audit bmw-bcl / bmw-bcl-rfcomm / bmw-bcl-handshake / supra-idrive6-android-auto-2026-secondary]
trigger: 2026-11-13 secondary NBT-AAD + RFCOMM two-mode review (initiator UNKNOWN · B2-A/B2-B)
method: docs/analysis/BCL_RFCOMM_TWO_MODE_20261113.md
a6_evidence: docs/evidence/FIELD_A6_HU_20261113T062824Z
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

**Watchdog:** Request `13 37 13 37` / dest 5001 / 5 s / 20 s TO = Desk-FACT. HU-Pong-Bytes = **UNKNOWN** (Client zählt jedes Antwort-Byte).

## Priorisierte Maßnahmen

### P0 — Feld (nächster Erkenntnissprung)

1. ~~**A6** — `.87` ↔ NBT Evo: ACL + Pairing + `btmon -w`~~ → **PASS** `FIELD_A6_HU_20261113T062824Z` (BMW 38304 / SPP UUID seen).
2. **B1 zustandsweise** — SDP in Zuständen A→D (kein channel=5); HU=`D4:36:39:CF:E1:B5`, Controller `.87` (hciN neu mappen):
   - A: nur gekoppelt  
   - B: + A2DP connected  
   - C: + MyBMW/Connected aktiv  
   - D: + AAIdrive aktiv (Kontrolle: Consumer öffnet keinen SPP)
3. **B2-A + B2-B** — Initiator **nicht** voraussetzen (`docs/analysis/BCL_RFCOMM_TWO_MODE_20261113.md`):
   - B2-Control: MyBMW/AAIdrive OFF (Versuchsbedingung)  
   - B2-A: `.87` connect() → HU; SABM von Phone; negativ ≠ BCL absent  
   - B2-B: `.87` SPP-Server **observe-only** (kein BCL-TX); SABM von HU; negativ ≠ kein BCL  
   - shared: DLCI / first UIH / magic=`candidate` / header / HANDSHAKE
4. **B3 nur nach BCL-Klassifikation** — INIT → HANDSHAKE → **version** → Branch (≤3 vs >3 SELECTPROTO+KNOCK) → OPEN 5001. OPEN 4004 erst wenn Consumer aktiv (Capture Y).
5. **Capture-Paar X/Y** — X: Transport only (kein AAIdrive); Y: + AAIdrive → isoliert Layer B vs E. Pflichtschema siehe Runbook.

### P1 — Lab (parallel / vor nächstem Feld, nicht statt B1)

6. **B2-B observe-only mode** auf bestehendem ProfileManager/Dummy-HU-Agent: SPP listen, Accept, Payload loggen, **BCL-TX hard-off**. Kein neuer BT-Stack. SABM/DLCI weiter über btmon.
7. **B0.7 Differential** — BclCarLink ↔ Dummy-HU (nicht AAIdrive-alone): raw TX == Capture; BCL frames; State OPENING→ACTIVE. Dummy: SPP + RFCOMM accept + HANDSHAKE auf Init; version 3 **und** 4 testen. (B0.7 ≠ B2-B observe-only.)
8. **B0.8** — BclCarLink (+ optional AAIdrive) ↔ **Simulator** :4006: ATTACHED → Etch → SAS-Stub. Epistemik: Simulator-Login ≠ Crypto-FACT.
9. **Phone HCI-Snoop (P1 Differential)** — optional zweites Auge (ACL/RFCOMM/UIH); ersetzt F20-Nachweis **nicht**.
10. Post-decode: Resync auf `12 34 56 78`, dann HANDSHAKE `len=8` verlangen — sonst `BCL_MISALIGNED` vs `NO_BCL` (siehe `docs/analysis/BCL_AUDIT_DEEP_20261112.md`).

### P2 — Docs / Epistemik

11. Sheets/Runbooks: F20-Initiator = **UNKNOWN**; OPEN 4004 = optional/E; Watchdog-Pong ≠ FACT; MyBMW-Opener = **UNKNOWN** (nur BclCarLink = FACT-Client).
12. BclCarLink `BclOutputStream`@7cfd959 Bugs **dokumentiert** (pidrive HU-Technical-Facts **C-D27**): `write(Int)`→`ByteArray(b)`; `sliceArray(off until len)`. **Nicht** in unseren Repos „korrigiert“ (Fremd-Upstream). B0.7/B0.8: Full-Array-Writes bevorzugen; Partial/Etch-Proxy misstrauen.
13. Lab-Evidence `C-L*` / `NO_RFCOMM` + Secondary `C-S*` / `EVID-SUPRA-*` belassen; `field_evidence` erst nach B1+. Secondary **nie** still zu F20-[B].
14. Evidence-Labels strikt: `BT_TRANSPORT` / `BCL_TRANSPORT` / `WD` / `ETCH_TUNNEL` / `SAS` / `RHMI` — nie „Connected works“.

### Explizit **nicht** tun

- Weiter AAIdrive/MyBMW-alone gegen Dummy (NO_RFCOMM erwartet).
- Channel 5 als BMW-Soll.
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

**A6 PASS. Heute: B1→B2-A+B2-B observe-only (`CAR_FIELD_1H`). Simulator = Layer E später. Negatives Phone-Connect ≠ negatives BCL.**
