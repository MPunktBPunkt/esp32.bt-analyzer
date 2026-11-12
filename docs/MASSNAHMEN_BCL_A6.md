# Maßnahmen — BCL Lab → A6 (Stand 2026-11-12)

```yaml
status: active
depends_on: [docs/BCL_BT.md, docs/CAR_A6_B1.md, technology-audit bmw-bcl / bmw-bcl-rfcomm / bmw-bcl-handshake]
trigger: multi-analysis 2026-11-12 (Transport-Owner vs Etch-Consumer · Simulator · OPEN-4004 · B2 split)
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
| **T** | Pairing → ACL → SDP → RFCOMM | B0.6 Dummy | A6 / B1 / B2.1–B2.2 |
| **B** | `12 34 56 78` → HANDSHAKE → Negotiate → ACTIVE → OPEN **5001** | B0.7 BclCarLink↔Dummy | B2.3 / B3.1–B3.7 |
| **E** | localhost :4007 → OPEN **4004** → Etch/SAS | B0.8 BclCarLink↔Simulator (+ AAIdrive) | Capture X vs Y |

**Korrektur:** `OPEN 4004` ist **Consumer-triggered** (EtchProxy erst nach TCP auf :4007), **nicht** deterministischer Bootstrap. Fehlen von OPEN 4004 nach HANDSHAKE ≠ Fehler.

**Watchdog:** Request `13 37 13 37` / dest 5001 / 5 s / 20 s TO = Desk-FACT. HU-Pong-Bytes = **UNKNOWN** (Client zählt jedes Antwort-Byte).

## Priorisierte Maßnahmen

### P0 — Feld (nächster Erkenntnissprung)

1. **A6** — `.87` ↔ NBT Evo: ACL + Pairing + `btmon -w` (Runbook `CAR_A6_B1.md`).
2. **B1 zustandsweise** — SDP in Zuständen A→D (kein channel=5):
   - A: nur gekoppelt  
   - B: + A2DP connected  
   - C: + MyBMW/Connected aktiv  
   - D: + AAIdrive aktiv (Kontrolle: Consumer öffnet keinen SPP)
3. **B2 split** — getrennt protokollieren:
   - B2.1 SDP endpoint (UUID / channel X / name)  
   - B2.2 SABM/UA-Richtung  
   - B2.3 first payload / BCL-INIT-Richtung (`12 34 56 78`?)
4. **B3 nur bei Payload** — INIT → HANDSHAKE → **version** → Branch (≤3 vs >3 SELECTPROTO+KNOCK) → OPEN 5001. OPEN 4004 erst wenn Consumer aktiv (Capture Y).
5. **Capture-Paar X/Y** — X: Transport only (kein AAIdrive); Y: + AAIdrive → isoliert Layer B vs E.

### P1 — Lab (nur wenn A6 wartet / parallel, nicht statt Feld)

6. **B0.7 Differential** — BclCarLink ↔ Dummy-HU (nicht AAIdrive-alone): raw TX == Capture; BCL frames; State OPENING→ACTIVE. Dummy: SPP + RFCOMM accept + HANDSHAKE auf Init; version 3 **und** 4 testen.
7. **B0.8** — BclCarLink (+ optional AAIdrive) ↔ **Simulator** :4006: ATTACHED → Etch → SAS-Stub. Epistemik: Simulator-Login ≠ Crypto-FACT.
8. **Pre-A6 Smoke (klein)** — einmal verifizieren: `btmon` auf `.87`-hciN zeigt RFCOMM-Payload-Bytes; `bcl_framer` frisst denselben Byte-Stream (Session-Init + 8+N). Kein neuer großer Stack — nur Gap-Check. Lab UI btmon-Karte reicht für A6-Rohcapture.

### P2 — Docs / Epistemik (kurz, kein Doc-Block vor A6)

9. Sheets/Runbooks: OPEN 4004 = optional/E; Watchdog-Pong ≠ FACT; MyBMW-Opener = **UNKNOWN** (nur BclCarLink = FACT-Client).
10. BclCarLink `BclOutputStream`@7cfd959 Bugs **dokumentiert** (pidrive HU-Technical-Facts **C-D27**): `write(Int)`→`ByteArray(b)`; `sliceArray(off until len)`. **Nicht** in unseren Repos „korrigiert“ (Fremd-Upstream). B0.7/B0.8: Full-Array-Writes bevorzugen; Partial/Etch-Proxy misstrauen.
11. Lab-Evidence `C-L*` / `NO_RFCOMM` in Audit belassen; `field_evidence` erst nach B1+.
12. Post-A6 decode: Resync auf `12 34 56 78`, dann HANDSHAKE `len=8` verlangen — sonst `BCL_MISALIGNED` vs `NO_BCL` (siehe `docs/analysis/BCL_AUDIT_DEEP_20261112.md`).
13. Evidence-Labels strikt: `BT_TRANSPORT` / `BCL_TRANSPORT` / `WD` / `ETCH_TUNNEL` / `SAS` / `RHMI` — nie „Connected works“.

### Explizit **nicht** tun

- Weiter AAIdrive/MyBMW-alone gegen Dummy (NO_RFCOMM erwartet).
- Channel 5 als BMW-Soll.
- USB/ENET-BCL als REJECTED.
- Relay/B3-Code vor first BCL payload.
- Große Doc-Kampagne vor A6.
- Simulator-Erfolg als HU-Auth oder F20-Wire werten.
- „Connected funktioniert“ ohne Layer-Tags (T/B/E/WD/SAS/RHMI).

## Gate-Kurzmatrix (Kill)

| Gate | Kill | Bedeutung |
|------|------|-----------|
| T1 HU identity | unsichtbar | BT/Placement |
| T2 SDP | NONE in A–D | Service absent **oder** zustandsabhängig — dokumentieren |
| T3 RFCOMM | SDP ja, kein Link | Transport-Mismatch |
| B1 INIT | RFCOMM, kein `12 34 56 78` | BCL-Pfad unproven |
| B2 HANDSHAKE | INIT, kein HANDSHAKE | HU/BCL mismatch |
| B3 negotiate | version>3 ohne SELECTPROTO/KNOCK | Branch fail |
| B4 WD | ACTIVE, 20 s tot | WD fail/unknown |
| E1 Etch | kein Consumer → kein 4004 | **OK**; Consumer aktiv + kein 4004 → fail |

## One-liner

**Simulator = stark für B0.8 (Etch nach Tunnel). Dummy = T/B. A6 = P0. Kein weiterer Doc-/Dummy-Overbuild vor dem F20-Capture.**
