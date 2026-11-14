# FIELD — Phone BT-Logs Nachmittag + Konsens M6–M15 (2026-11-14)

```yaml
id: FIELD_PHONE_BTLOGS_20261114T1037Z
kind: field_logcat_batch
peers: OnePlus ↔ HU D4:36:39:CF:E1:B5 · Dummy …:7B:0A (A2DP only in this window)
sources:
  - docs/bluetooth_20261114_083313_01892.log   # 15.2 MiB · morning (≈ .txt already analyzed)
  - docs/bluetooth_20261114_093023_07506.log   # 0.37 MiB · BT restart / no SPP session
  - docs/bluetooth_20261114_103731_10775.log   # 19.2 MiB · midday field window ★
  - docs/BT_HCI_2026_1114_104405.cfa          # 16 B · empty BTSnoop header only
analysis: docs/analysis/FIELD_B2A_TX_PATTERNS_20261114.md
prior: docs/evidence/FIELD_PHONE_HU_LOGCAT_20261114T0924Z.md
consensus: Mistral M6–M10 · GPT Accept≠Application · Grok M11–M15
verified: 2026-11-14 local parse on full .log files
```

## Verdict (kurz)

| Befund | Status |
|--------|--------|
| Phone→HU `0x1101` → SDP **SCN 6** → DLCI **13** | **FACT** (Vormittag + Nachmittag) |
| RFCOMM OPEN (UA-Pfad) reproduziert | **FACT** — 4× OPEN 10:42–10:44 |
| HU→Phone Payload auf DLCI 13 | **FACT empty** — **0×** `PORT_DataInd` dlci:13 |
| Phone TX nach OPEN | **FACT** — L2CAP `Len:8` @ **3,000 s**; Typ‑A zusätzlich `Len:61` (~56 B UIH) |
| Close am 6. Ping-Tick (15,06 s) | **MEASURED** auf echter F20 (M9 gestützt) |
| Hex der 4/56 B Nutzdaten | **UNKNOWN** — RFCOMM-Snoop-Filter **an**; `.cfa` leer |
| Analyzer `.87`→HU DM vs Phone→HU UA | **STRONG** (M6) — parallele Matrix |

**Kern:** Accept ≠ Application (M11). Die HU lässt den Phone-DLC zu und bleibt stumm; `.87` wird auf DLC-Ebene abgelehnt. Hex fehlt weiter — P0 HCI-Snoop mit RFCOMM-Filter **aus**.

## Dateien

| Datei | Fenster | Inhalt |
|-------|---------|--------|
| `…083313_01892.log` | ~08:33–09:29 | Vormittag Phone↔HU SPP (bereits in `FIELD_PHONE_HU_LOGCAT_*`) |
| `…093023_07506.log` | kurz | Stack-Restart; **0** `connectSocket` / PortOpen |
| `…103731_10775.log` | 10:37–10:44 | Nachmittag: Dummy-A2DP + Phone↔HU SPP-Retries |
| `BT_HCI_…104405.cfa` | — | nur Header `btsnoop` + version; **0 Pakete** |

Snoop-Filter in `103731` (10:37:31):

```
persist.bluetooth.snooplogfilter.profiles.rfcomm.enabled: true
Snoop Logs filtered mode enabled
```

## Nachmittag — Phone↔HU SCN6 (aus `103731`)

UID **10479**, UUID `00001101-…`, `BTA_JvRfcommConnect remote_scn:6`, DLCI 13, N1/MTU 666.

### Establish-Mix (wichtig für M6/M7)

| Ergebnis | n | Bedeutung |
|----------|--:|-----------|
| `PORT_DlcEstablishCnf result:0` → `OPEN_EVT` | **4** | HU akzeptiert DLC (UA-Pfad) |
| `result:1` „Unable to establish“ → `CLOSE_EVT` | **8** Attempts | Concurrent/Race — kein stabiles OPEN |

Auch der **Phone**-Pfad ist also nicht „immer UA“, sondern zustands-/race-abhängig. Erfolgreiche Opens genügen, um „Kanal 6 tot“ zu verwerfen.

### Erfolgreiche Sessions

| # | OPEN | CLOSE | Dauer | Phone TX (L2CAP Len auf RFCOMM-CID) |
|--:|------|-------|------:|-------------------------------------|
| 1 | 10:42:54.794 | 10:42:57.797 | **3,003 s** | `8` + `61` (~Typ A, früh abgebrochen) |
| 2 | 10:43:01.435 | 10:43:16.495 | **15,060 s** | 5× `8` @ 3,000 s → CLOSE (Typ B / M9) |
| 3 | 10:43:47.785 | 10:43:50.792 | **3,007 s** | `8` + `61` |
| 4 | 10:43:55.051 | 10:44:03.913 | **8,862 s** | 3× `8` @ 3 s (Capture/Session-Ende) |

**Typ-B-Session #2 (M9):**

```
10:43:01.445  L2W 8   (OPEN+1)
10:43:04.448  L2W 8   +3,003 s
10:43:07.447  L2W 8
10:43:10.452  L2W 8
10:43:13.456  L2W 8   (5. Ping)
10:43:16.461  L2W 4   (DISC-Pfad)
10:43:16.495  CLOSE   = 5×3,0 s + ε  → 6. Tick
```

L2CAP `Len:8` ≈ RFCOMM-UIH-Framing + **~4 B** User-Payload (wie Vormittag „4 B“); `Len:61` ≈ Framing + **~56 B**. Hex weiter UNKNOWN.

### RX

- `PORT_DataInd` dlci:**13** = **0** (beide großen Logs)
- DataInd nur auf fremden DLCIs (HFP dlci 8/2, Peer `B7:21` dlci 32, …) — **nicht** BCL/ch6

## Dummy `…:7B:0A` in diesem Fenster

Profil-Queue: UUID `111F` (HFP) + `110A` (A2DP). **Kein** `connectSocket(0x1101)` / kein SCN6-OPEN zum Dummy in `103731`.  
AAIdrive-grün / voller BCL = frühere Desk-Session (`LAB_FIELDPREP_*`), nicht dieser Auto-Fenster-Ausschnitt.

## Security-Flags zum SABM (M15 / Diskriminator)

Wiederholt um Phone→HU SABM:

```
l2c_link_sec_comp: BTM_SUCCESS_NO_SECURITY  peer=…:e1:b5
btm_sec_service_access_request: BTM_SUCCESS
```

Kein Link-Key-Typ / Encrypt-On im Klartext. Diskriminator (a) Bond-Auth vs (b) App-Session bleibt **offen** → btmon Security-Flags beim nächsten Feldlauf.

## Abgleich Konsens M6–M15

| ID | Aussage | Log-Status |
|----|---------|------------|
| **M6** | Peer-Asymmetrie Phone UA vs `.87` DM | **STRONG** (Phone OPEN hier; Matrix DM) |
| **M7** | State: gestern UA+empty / heute Analyzer DM | **STRONG**; Phone weiterhin UA-fähig |
| **M8** | CoD nicht faktorisiert | unverändert Lab |
| **M9** | Close am 6. Ping-Tick (~15 s) | **MEASURED** Session #2 (15,060 s) |
| **M10** | AVRCP-Metadaten verweigert | Feldbeobachtung (UI), nicht in diesem Log |
| **M11** | Accept ≠ Application | **FACT** — OPEN + 0 RX + Phone TX |
| **M12** | HU kein passiver SPP-Server | gestützt (Admission + Silent) |
| **M13** | Eligibility oberhalb A2DP | gestützt (M1+M6) |
| **M14** | Kurze Sessions = Retry | **FACT** — A/B + result:1 races |
| **M15** | Security als Diskriminator | **ungetestet** (Flags dünn) |

## Nicht bewiesen

- Hex `12 34 56 78` / WD `13 37…` auf der echten HU (Filter + leeres `.cfa`)
- „MyBMW autorisiert RFCOMM“ als alleinige Ursache
- CoD allein = Gate
- HU sendet *nie* BCL (nur: beobachteter PORT_DataInd-Pfad leer)

## Nächste Schritte (Priorität)

1. **P0** Phone HCI-Snoop, RFCOMM-Filter **aus** — Hex der ersten UIH nach OPEN (4/56 B).
2. **P0.5** 2×2-Feldmatrix MyBMW × Phone-A2DP → `.87` SABM→UA|DM (M7).
3. **P1** Silent-HU-Lab (M9-Kriterium) · Dummy-Faktorisierung (M8).
4. Kein B3 · kein ch5-als-BCL.
