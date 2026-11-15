# LAB FACT — AAIdrive green on `--sas-probe none` (2026-11-15)

## Verdict

**LAB FACT:** Mit Dummy-HU `f20` + `--sas-probe none` (kein Etch/SAS/CDS-TX) geht
AAIdrive auf dem OnePlus 12 **grün** und zeigt Fahrzeugdaten inkl. VIN.

Das **beweist nicht** einen SAS-Handshake und **nicht**, dass der Dummy die
Fahrzeugdaten geliefert hat.

## Session

| | |
|--|--|
| session_id | `LAB_SAS_NONE_20261115T121950Z` |
| peer | OnePlus 12 `AC:C0:48:5E:CB:20` |
| HU | `BMW 38304` / Dummy ch **6** / HS v5 iid14 buf 0x4000 |
| flags | `--sas-probe none --handshake-delay 3` + DATAACK + WD echo |
| capture | [`LAB_SAS_NONE_GREEN_20261115T121950Z.jsonl`](LAB_SAS_NONE_GREEN_20261115T121950Z.jsonl) |

## Wire (Dummy side)

| Beobachtung | Status |
|-------------|--------|
| INIT → HS (~3 s) → SP4 → KNOCK → OPEN 5001 / OPEN 4004 | gesehen |
| Phone PKCS7 auf src **10, 11, 12** → 4004 | gesehen (`SAS_CERT_CANDIDATE`) |
| DATAACK `8+len` (inkl. 4008) | gesehen |
| WD ping/pong stabil | gesehen (≥50) |
| HU `etch_data_tx` / `sas_challenge_tx` / CDS / VIN-Stub | **0** |
| Phone→HU ASCII mit VIN/sensors | **0** in dieser Capture |

## Interpretation

1. **Grün = BCL-Transport + App-Zustand**, nicht „SAS formal OK“.
2. Angezeigte VIN/Fahrzeugdaten kommen mit hoher Wahrscheinlichkeit aus
   **MyBMW-Konto / Cache / Backend**, nicht aus Dummy-Etch-Payloads
   (Dummy hat keine vehicle-artigen Bytes gesendet).
3. Stufe `none` bleibt die Kontrollgruppe: Phone sendet Certs und hält WD,
   auch ohne HU-Challenge.

## Next (nicht kumulativ ändern)

JSONL einfrieren (done). Erst danach getrennt:

1. `--sas-probe dataack` — erwartetes Verhalten ≈ wie hier (DATAACK war schon an)
2. `--sas-probe challenge` — suchen nach **neuer** Phone→HU-Aktion nach Challenge
3. Bei Interesse: Payload/UI-Differenz vs. diese Baseline dokumentieren
