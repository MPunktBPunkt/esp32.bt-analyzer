# Analyse — Muster Feld+Lab 2026-11-14 (Vormittag)

```yaml
evidence_matrix: docs/evidence/FIELD_B2A_TX_MATRIX_20261114.md
dummy_session: docs/evidence/LAB_FIELDPREP_20261114T095848Z.md
phone_hu_logcat: docs/evidence/FIELD_PHONE_HU_LOGCAT_20261114T0924Z.md
prior_b2: docs/evidence/FIELD_B2_20261113T154728Z.md
massnahmen: docs/MASSNAHMEN_BCL_A6.md
```

## Drei parallele Welten (nicht vermischen)

| Welt | Pfad | Ergebnis heute |
|------|------|----------------|
| **A** Phone↔echte HU | OnePlus → `D4:…:CF:E1:B5` | Logcat: SPP **ch6 OPEN**, Phone TX, HU **0 RX** (silent) |
| **B** Phone↔Dummy | OnePlus → `.131` `…:7B:0A` | Nach CoD-Pin + App-Restart: **voller BCL** (INIT→HS→SP(2)→WD+Pong); AAIdrive **grün** |
| **C** Analyzer↔echte HU | `.87` → HU | A2DP/UI „BT-Analyzer verbunden“ möglich; **alle** `b2a-tx` ch5–10 → RFCOMM **DM** / `Connection refused` |

## Muster (FACT-Kern)

### M1 — A2DP-OK ≠ SPP-Accept (Analyzer)

HU zeigte „BT-Audio ist mit BT-Analyzer verbunden“ + PipeWire-Sink BMW aktiv. Parallel: `b2a-tx` ch6–10 und ch5 → Socket `Connection refused`; btmon: Mux oft **UA**, DLC-SABM → **DM**. Teilweise L2CAP `no resources`.

**Lesart:** Media-Eligibility und SPP-Server-Annahme sind entkoppelt. AVRCP-Hinweis „Titelinformationen nicht unterstützt“ = Metadaten-Lücke, kein BCL-Befund.

### M2 — B2-A-TX-Matrix negativ in diesem State

| Kanal | UUID/Dienst | Ergebnis |
|------:|-------------|----------|
| 5 | `deca-fade` | refused / DM |
| 6–10 | `0x1101` | refused / DM (auch nach ≥15 s ACL, auch AUDIOOK) |

Contrast gestern B2-A observe-only: ch6/5 **UA + empty**. Heute TX-Connect scheitert schon am DLC — anderer HU-/Stack-State oder Coex mit parallelem Phone↔HU-A2DP.

**H-E:** ch7–10 helfen **nicht** gegen DM in diesem Lauf → H-E für *Analyzer-TX-Bypass* **geschwächt** (Kanalwahl bleibt relevant für Phone-UUID-Fetch).

### M3 — Dummy braucht CoD+Name+ACL-Bounce

Drift auf Computer-CoD `0x4c0104` → AAIdrive „wartet auf Fahrzeug“, **0 RFCOMM**. Pin `0x340408` + Alias `BMW 38304` + Disconnect/Reconnect + MyBMW→AAIdrive Restart → RFCOMM in ~12 s.

Zwei „BMW 38304“ am Phone: echt `…:CF:E1:B5` vs Dummy `…:7B:0A`. AAIdrive-grün = Dummy, nicht Auto.

### M4 — Lab-BCL-Signatur (reproduziert)

Session `LAB_FIELDPREP_20261114T095848Z`: 6× RFCOMM, 4× INIT `12345678`, HANDSHAKE, SELECTPROTO payload `00050000000000020002` (**SP(2)**), WD `13 37 13 37` + Echo, große `deadbeef`/PEM-Frames. WD-Pongs ≫ 200. Passt zu C-L7/C-L11 — **nicht** F20-HU-Wire.

### M5 — Phone↔HU silent bleibt stehen

Logcat-Welt A unverändert: Transport OPEN, HU silent ch6. Analyzer kann denselben Handshake heute nicht erzwingen (M2).

## Hypothesen-Update

| ID | Update |
|----|--------|
| **H-A** | Handshake von **echter** HU weiter unproven; Phone silent + Analyzer DM. Dummy antwortet ≠ HU |
| **H-E** | Explizite ch7–10 ändern DM-Negativ **nicht** (dieser State) |
| **H-C** | MyBMW+Restart am Dummy = starker Eligibility-Hebel (Lab). Am Auto parallel unklar |
| **Neu H-G** | HU SPP-Accept hängt an **App-/Owner-State**, nicht nur ACL+A2DP — **[H]** |

## Nächste Schritte

1. Feld: Phone HCI-Snoop Hex (4/56 B) bei silent ch6 — P0 Epistemik.
2. Feld: `b2a-tx` nur wenn Phone **nicht** parallel A2DP zur HU hält; HU-UI „verbunden“ allein reicht nicht (M1).
3. Lab: Silent-HU-Dummy (kein HS/Pong) gegen Phone-Retry Typ A/B.
4. Kein B3 / kein ch5-als-BCL.
