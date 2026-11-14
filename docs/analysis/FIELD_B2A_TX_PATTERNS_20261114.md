# Analyse — Muster Feld+Lab 2026-11-14

```yaml
evidence_matrix: docs/evidence/FIELD_B2A_TX_MATRIX_20261114.md
dummy_session: docs/evidence/LAB_FIELDPREP_20261114T095848Z.md
phone_hu_logcat: docs/evidence/FIELD_PHONE_HU_LOGCAT_20261114T0924Z.md
phone_btlogs_pm: docs/evidence/FIELD_PHONE_BTLOGS_20261114T1037Z.md
prior_b2: docs/evidence/FIELD_B2_20261113T154728Z.md
massnahmen: docs/MASSNAHMEN_BCL_A6.md
consensus: Mistral M6–M10 · GPT Accept≠Application · Grok M11–M15
```

## Drei parallele Welten (nicht vermischen)

| Welt | Pfad | Ergebnis heute |
|------|------|----------------|
| **A** Phone↔echte HU | OnePlus → `D4:…:CF:E1:B5` | SPP **ch6 OPEN**, Phone TX (4/56 B-Größen), HU **0 RX** (silent) — Vormittag + Nachmittag |
| **B** Phone↔Dummy | OnePlus → `.131` `…:7B:0A` | Nach CoD-Pin + App-Restart: **voller BCL** (INIT→HS→SP(2)→WD+Pong); AAIdrive **grün** |
| **C** Analyzer↔echte HU | `.87` → HU | A2DP/UI „BT-Analyzer verbunden“ möglich; **alle** `b2a-tx` ch5–10 → RFCOMM **DM** / `Connection refused` |

**Qualitativer Sprung:** Die Frage ist nicht mehr „funktioniert SPP?“, sondern **unter welchen Eligibility-/Session-Bedingungen lässt die HU welchen Peer auf den DLC?**

## Muster (FACT-Kern) — M1–M5

### M1 — A2DP-OK ≠ SPP-Accept (Analyzer)

HU zeigte „BT-Audio ist mit BT-Analyzer verbunden“ + PipeWire-Sink BMW aktiv. Parallel: `b2a-tx` ch6–10 und ch5 → Socket `Connection refused`; btmon: Mux oft **UA**, DLC-SABM → **DM**. Teilweise L2CAP `no resources`.

**Lesart (geschärft mit M6/M10):** Media-Eligibility und SPP-Admission sind entkoppelt; die HU entscheidet **aktiv differently pro Peer**. AVRCP „Titelinformationen nicht unterstützt“ = weiteres Indiz für fehlende App-Session (M10), kein BCL-Befund.

### M2 — B2-A-TX-Matrix negativ in diesem State

| Kanal | UUID/Dienst | Ergebnis |
|------:|-------------|----------|
| 5 | `deca-fade` | refused / DM |
| 6–10 | `0x1101` | refused / DM (auch nach ≥15 s ACL, auch AUDIOOK) |

Contrast gestern B2-A observe-only: ch6/5 **UA + empty**. Heute TX-Connect scheitert schon am DLC — **State-Artefakt unter Verdacht** (M7), nicht „Kanal falsch“.

**H-E:** ch7–10 helfen **nicht** gegen DM in diesem Lauf → H-E für *Analyzer-TX-Bypass* **geschwächt** (Kanalwahl bleibt relevant für Phone-UUID-Fetch).

### M3 — Dummy braucht CoD+Name+ACL-Bounce

Drift auf Computer-CoD `0x4c0104` → AAIdrive „wartet auf Fahrzeug“, **0 RFCOMM**. Pin `0x340408` + Alias `BMW 38304` + Disconnect/Reconnect + MyBMW→AAIdrive Restart → RFCOMM in ~12 s.

Zwei „BMW 38304“ am Phone: echt `…:CF:E1:B5` vs Dummy `…:7B:0A`. AAIdrive-grün = Dummy, nicht Auto.

### M4 — Lab-BCL-Signatur (reproduziert)

Session `LAB_FIELDPREP_20261114T095848Z`: 6× RFCOMM, 4× INIT `12345678`, HANDSHAKE, SELECTPROTO payload `00050000000000020002` (**SP(2)**), WD `13 37 13 37` + Echo, große `deadbeef`/PEM-Frames. WD-Pongs ≫ 200. Passt zu C-L7/C-L11 — **nicht** F20-HU-Wire.

### M5 — Phone↔HU silent bleibt stehen

Logcat-Welt A (Vormittag + `FIELD_PHONE_BTLOGS_*` Nachmittag): Transport OPEN, HU silent ch6. Analyzer kann denselben Handshake heute nicht erzwingen (M2).

## Erweiterte Muster — M6–M15 (Konsens)

### M6 — Peer-Asymmetrie auf DLC-Ebene **[STRONG]**

| | Mux (DLCI 0) | SPP-DLC | Payload |
|---|---|---|---|
| Phone → HU | UA | **UA / OPEN** (auch result:1-Races) | HU **stumm** (0× DataInd dlci 13) |
| Analyzer `.87` → HU | UA | **DM** | — |

RFCOMM-Server lebt und entscheidet **aktiv**. Verwerfe „SPP wird von der HU nicht akzeptiert“ → präzise: **SPP/RFCOMM wird zustands-/peer-abhängig akzeptiert oder verworfen.**

### M7 — gestern UA+empty vs heute Analyzer-DM **[STRONG]**

Gleicher Tool-Kanal, anderer HU-/Peer-State. „Channel 6 ist falsch“ / „HU kennt keinen SPP“ praktisch unhaltbar. **Hebel nächster Feldlauf:** 2×2 MyBMW ON/OFF × Phone-A2DP ON/OFF → Messwert SABM→UA|DM.

### M8 — Dummy-Erfolg nicht faktorisiert **[INFERENCE]**

CoD `0x340408` + ACL-Bounce + MyBMW/Restart **zusammen** = Eligibility-Hebel. Nicht „CoD allein = Hebel“. P1 Faktorisierung nach Phone-Snoop.

### M9 — Close am 6. Ping-Tick **[MEASURED Feld / Hypothese Modell]**

Nachmittag Session #2: OPEN → 5× L2CAP-`Len:8` @ 3,000 s → CLOSE bei **15,060 s** (= 6. Tick). Modell „15 s pre-HS WD vs 20 s post-HS“ bleibt Hypothese → Silent-HU-Lab.

### M10 — AVRCP-Metadaten verweigert **[SUPPORTING]**

A2DP ja, Titel-Info nein → Profiltrennung / fehlende App-Session.

### M11 — Accept ≠ Application **[FACT / zentral]**

```
Phone  ↔ HU      :  SABM → UA   →  0 B RX beobachtet
.87    ↔ HU      :  SABM → DM
Phone  ↔ Dummy   :  SABM → UA   →  BCL (HS + WD)
```

Transport-Akzeptanz und BCL-Anwendung sind **zwei Stufen**. Architektur:

```
BT Identity → Eligibility → RFCOMM admission → BCL handshake → BCL application
```

Der Block **UA → ??? → HU BCL-Bytes** ist die größte offene Fläche → Phone-HCI-Snoop.

### M12 — HU ist kein passiver SPP-Server **[MODEL]**

Incoming SABM → BMW Eligibility/Session Gate → reject(DM) | accept(UA) → Session/Owner → BCL?

### M13 — Eligibility sitzt oberhalb von A2DP **[STRONG]**

A2DP = Identity/Audio-Carrier, nicht BCL-Freigabe.

### M14 — Kurze Phone-Sessions = Retry **[FACT]**

A/B-Alternation + parallele `result:1` Establish-Fails. Dummy hält Minuten wegen WD-Pong.

### M15 — Security/Bond als Diskriminator **[UNTESTED]**

(a) Service-Autorisierung vs (b) App-Session (H-G). Log: oft `BTM_SUCCESS_NO_SECURITY` — zu dünn. btmon Security-Flags zum SABM.

## Zustandsmaschine (Stand heute)

```
Peer / HU State
       │
  ┌────┴────┐
  │         │
eligible  ineligible
  │         │
SABM→UA   SABM→DM
  │
RFCOMM open
  │
Payload?
  │
Phone: leer (beobachtet)   Dummy: BCL
  │
 ???  ← HCI-Snoop Hex
```

## Hypothesen-Update

| ID | Update |
|----|--------|
| **H-A** | Handshake von **echter** HU weiter unproven; Phone silent + Analyzer DM. Dummy antwortet ≠ HU |
| **H-E** | Explizite ch7–10 ändern DM-Negativ **nicht** (dieser State) |
| **H-C** | MyBMW+Restart am Dummy = starker Eligibility-Hebel (Lab). Am Auto parallel unklar |
| **H-G** | HU SPP-Accept hängt an **App-/Owner-State**, nicht nur ACL+A2DP — **[H]**; M6/M7/M10 stützen |

## Nicht bewiesen

- MyBMW autorisiert RFCOMM (plausible Hypothese)
- CoD `0x340408` alleiniges Gate
- ch6 definitiv BCL der echten HU (stark indiziert; Payload-Hex fehlt)
- HU sendet dem Phone *nie* BCL (nur: beobachteter RX-Pfad leer)

## Nächste Schritte (Priorität)

1. **P0** Phone HCI-Snoop F20, RFCOMM-Filter **aus** — Hex 4/56 B, Richtung, INIT/HS/WD?
2. **P0.5** 2×2-Feldmatrix (M7) + btmon Security-Flags (M6/M15)
3. **P1** Silent-HU-Lab (M9) · Dummy-Faktorisierung (M8)
4. Kein B3 / kein ch5-als-BCL
