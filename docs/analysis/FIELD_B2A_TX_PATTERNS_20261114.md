# Analyse — Muster Feld+Lab 2026-11-14

```yaml
evidence_matrix: docs/evidence/FIELD_B2A_TX_MATRIX_20261114.md
dummy_session: docs/evidence/LAB_FIELDPREP_20261114T095848Z.md
phone_hu_logcat: docs/evidence/FIELD_PHONE_HU_LOGCAT_20261114T0924Z.md
phone_btlogs_pm: docs/evidence/FIELD_PHONE_BTLOGS_20261114T1037Z.md
phone_hu_hs_v5: docs/evidence/FIELD_PHONE_HU_BCL_HS_V5_20261114T1113Z.md
prior_b2: docs/evidence/FIELD_B2_20261113T154728Z.md
massnahmen: docs/MASSNAHMEN_BCL_A6.md
consensus: Mistral M6–M10 · GPT Accept≠Application · Grok M11–M15 · Grok M16–M19 (HS v5)
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

### M16 — Echte HU liefert BCL-HANDSHAKE v5 **[FIELD FACT]**

`.87` → HU ch6: SABM→UA → INIT → HS **v5 / iid 14 / buf 0x4000**.

### M20 — HU WD-Echo ACTIVE nach OPEN 5001 **[FIELD FACT]**

Client-WD @ **2,5 s**: HU → DATAACK `0x0C` + DATA `13 37 13 37`. SP2/SP3 beide OK.  
Wire-OPEN `src=dst=5001`: HU-Echo ebenfalls 5001↔5001. Evidence: `…SP2_*`, `…SP3WD_*`, `…ETCH_*` (180 s).

### M21 — OPEN 4004 ≠ Etch-Payload von der HU **[FIELD FACT]**

Analyzer TX OPEN `src=10 dest=4004` → extra DATAACK `0x08`, aber **0** Frames/`deadbeef` von der HU in 180 s.  
Etch/PKCS7 ist **App→HU** (Lab Phone↔Dummy), nicht HU-unsolicited.

### M22 — Lab Dummy: AAIdrive Etch `deadbeef`/PKCS7 **[LAB FACT]**

`LAB_DUMMY_ETCH_20261114T1550Z`: car A2DP/ACL-Bounce → Phone→Dummy HS v5 → SP **`0004`** → KNOCK → OPEN5001+WD → OPEN4004 src 10/11/12 + PKCS7. Deep: [`LAB_DUMMY_ETCH_DEEP_20261114.md`](LAB_DUMMY_ETCH_DEEP_20261114.md).

### M23 — HS v5 ⇒ Phone SP(4)+KNOCK **[LAB FACT]**

Nicht Desk SP3, nicht Lab-v3 SP2. BclCarLink kommentiert „version 4 WD unknown“ — Wire nutzt SP4 trotzdem; WD bleibt ≈2.5 s.

### M24 — Official KNOCK = UUID-Serial + TouchCommand(1)/7 **[LAB FACT]**

BclPacket.Knock-Layout; Desk-Default (leer, A4A/0+1) ≠ MyBMW-Wire.

### M25 — Etch-Kanäle 10/11/12 = AM / SmartThings / cdsbaseapp **[LAB FACT]**

CN aus PKCS7; **cdsbaseapp** = MyBMW CDS-Cert-Pfad.

### M26 — Etch-Fragmentierung @4000 BCL-DATA **[LAB FACT]**

Reassembly: `deadbeef` + `u32BE(len)` → Gesamtlänge `8+len`.

### M27 — UI grün ohne HU-Etch-Reply / ohne DATAACK **[LAB FACT]**

Dummy TX nur HS + WD-Echo; AAIdrive bleibt grün (~760 s Capture).

### M28 — src11 CLOSE→OPEN vor Cert **[LAB FACT]**

Retry/Reset eines Etch-Kanals vor SmartThings-PKCS7.

### M17 — HS-Fingerprint peer-/versionsabhängig **[REPORTED]**

| Quelle | version | instanceId | bufferSize |
|--------|--------:|------------|------------|
| Dummy `7b:0a` | 3 | 1 | 0x8000 |
| Echte HU `e1:b5` | **5** | **0x0E** | **0x4000** |

`version>3` → Desk SELECTPROTO(3)+KNOCK-Branch — Wire-Verhalten nach HU-v5 noch UNKNOWN.

### M18 — HU-BCL-Session bleibt kurz **[REPORTED]**

~25 s dann CLOSE; kein stabiler WD-Echo wie Dummy (212× WD im selben Log).

### M19 — cmd 0x0006 HU→Phone = DATAACK **[REPORTED + Name korrigiert]**

Grok: „OPEN/SELECTPROTO-Kandidat“. Framer: cmd **6 = DATAACK** (OPEN=1, SELECTPROTO=5). Payload-Beispiel `00 00 00 0A`. Semantik F20 offen; später + WD-Fragment roh prüfen.

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
  ┌────────┴────────┐
  │                 │
silent (083313/     HS v5 REPORTED
 103731)            (Session 96)
  │                 │
 ???                DATAACK? → kurz CLOSE
                    │
                 WD ACTIVE (F20)
                    │
                 OPEN 4004 ACK only (HU)
                    │
         Lab Dummy: SP4+KNOCK+App PKCS7 (M23–M28)
```

## Hypothesen-Update

| ID | Update |
|----|--------|
| **H-A** | **FIELD CONFIRMED** HS v5 + WD. Etch am F20 = App/Proxy (M21); Lab Dummy liefert Cert-Pfad inkl. cdsbaseapp (M25) |
| **H-E** | Explizite ch7–10 ändern DM-Negativ **nicht** (dieser State) |
| **H-C** | MyBMW+Restart am Dummy = starker Eligibility-Hebel (Lab). Am Auto parallel unklar |
| **H-G** | HU SPP-Accept hängt an **App-/Owner-State**, nicht nur ACL+A2DP — **[H]**; M6/M7/M10 stützen |

## Nicht bewiesen

- MyBMW autorisiert RFCOMM (plausible Hypothese)
- CoD `0x340408` alleiniges Gate
- F20 liefert Etch/CDS ohne App-Cert-Push
- Analyzer-`.87` aktuell erreichbar (Timeout 16:04)
- Rohzeilen Session 96 (CLEANED noch nicht im Repo)
- KNOCK-UUID Semantik (Session-ID?) über eine Capture hinaus

## Nächste Schritte (Priorität)

1. **P0** F20-Proxy: WD halten + Lab-klassifizierte App-Etch (cdsbaseapp) auf 4004.
2. **P0** PhoneClientSession: nach HS v5 **SP4+KNOCK** (nicht Desk SP3).
3. **P0** `bluetooth_20261114_104405_CLEANED.log` ingestieren → REPORTED→FACT.
4. **P0.5** 2×2-Feldmatrix (M7) + btmon Security-Flags (M6/M15)
5. Kein B3 / kein ch5-als-BCL
