# 1‑Stunden Feldfenster — B1 + B2-A + B2-B

```yaml
goal: maximaler Wire-Erkenntnisgewinn in ≤60 min
tx_policy: kein BCL-TX (observe-only)
hu: D4:36:39:CF:E1:B5
phone_esp: C8:C9:A3:CB:37:96 (.87)
host: .108 via SSH
tools: tools/field_b1_b2.py
```

## Vor der Fahrt (daheim, 5 min)

```bash
# Laptop → .108 erreichbar? .87 Agent?
python3 tools/field_b1_b2.py preflight
```

- Pairing zu BMW 38304 noch gültig? Sonst neu pairen (A6-Pfad).
- Phone: **MyBMW force-stop**, **AAIdrive force-stop** (B2-Control).
- Optional: Phone HCI-Snoop einschalten (B2-C, P1).

## Im Auto (Ziel: 45–55 min)

| Min | Schritt | Befehl / Aktion |
|----:|---------|-----------------|
| 0–3 | Preflight + btmon | `preflight` · `btmon-start` |
| 3–12 | **B1 state A** (paired only) | `b1 --state A` → **Kanal X notieren** |
| 12–18 | B1 state B optional | A2DP connect → `b1 --state B` |
| 18–28 | **B2-A** | `b2a --channel X --seconds 25` · btmon: SABM von `.87`? |
| 28–50 | **B2-B** | `b2b --hold 90` · iDrive/Apps ruhig; warten ob HU dialt |
| 50–55 | Stop + pull | btmon stop; Evidence unter `docs/evidence/FIELD_*` |
| 55–60 | Kurznotiz | Initiator / first UIH / Klassifikation |

```bash
python3 tools/field_b1_b2.py btmon-start
python3 tools/field_b1_b2.py b1 --state A --mybmw OFF --aaidrive OFF
# channel X from JSON:
python3 tools/field_b1_b2.py b2a --channel X --seconds 25
python3 tools/field_b1_b2.py b2b --hold 90
```

## Was heute beantwortet werden kann

| Frage | Quelle |
|-------|--------|
| HU SDP / Kanal X | B1 |
| Phone-init RFCOMM möglich? | B2-A (SABM in btmon) |
| HU-init RFCOMM? | B2-B |
| first UIH / BCL-Kandidat? | Payload + `bcl_classify` |
| Initiator am F20 | SABM-Richtung A vs B |

## Was heute **nicht** Ziel ist

- B3 / Relay / BCL-TX
- Simulator / Etch / SAS
- Channel 5 als HU-Soll
- B2-A-Negativ = „kein BCL“
- MyBMW/AAIdrive Contention-Matrix (nur Baseline OFF)

## Nach der Fahrt (daheim)

```bash
# UIH-Hex aus JSONL / btmon → Klassifikation
python3 tools/bcl_classify.py --hex '...' --json
```

Stufen: `UNKNOWN` → `BCL_CANDIDATE` (`12 34 56 78`) → `STRONG_BCL_CANDIDATE` → `BCL_FIELD_CONFIRMED` (HANDSHAKE).

B2-B Evidence muss `tx_bytes_events: 0` haben.

## Simulator / großer Analyzer-Umbau

**Nicht heute.** `Simulator-kt` = Layer E TCP `:4006` only. Minimal-Analyzer-Patch (Klassifikation + observe-only) ist vorbereitet; voller HCI→Etch-Umbau = Wochen, nicht nötig für B1/B2.
