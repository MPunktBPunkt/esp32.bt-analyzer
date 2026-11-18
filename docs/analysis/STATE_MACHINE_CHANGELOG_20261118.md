# State-Machine Audit Changelog — 2026-11-18

```yaml
phase: A+B complete; Phase Impl deferred pending GAP review
commits_docs: STATE_MACHINE_CURRENT / GAP / TRANSITIONS
code_changes: none
```

## Artefakte

| File | Inhalt |
|------|--------|
| [`STATE_MACHINE_CURRENT.md`](STATE_MACHINE_CURRENT.md) | IST aus Source |
| [`STATE_MACHINE_GAP.md`](STATE_MACHINE_GAP.md) | Ist vs Ziel + Minimalplan |
| [`STATE_MACHINE_TRANSITIONS.md`](STATE_MACHINE_TRANSITIONS.md) | Transition-Matrix |
| [`DEEP_FORENSIC_FIELD_AUTH_REJECT_20261118.md`](DEEP_FORENSIC_FIELD_AUTH_REJECT_20261118.md) | Field Wire-Beweis |

## LAB FACT (bleibt)

- RHMI lifecycle → `RUNTIME_ACTIVE` auf f20_sim nach EAGAIN-Retry (`ffd28aa` / lifecycle PASS).
- Soak ~604 s: 97× setData, Multi-Model, 105 Actions/Acks, EAGAIN recovered, kein Abort (`a5187cb`).
- PiDrive seq: setData(100,"PiDrive") → Action(200) → `PI_DRIVE_TEST` → Ack (`1100644`).
- checkResource=true ⇒ kein automatisches setResource (Source `:1035+`).
- setData ServiceException 213 ⇒ Event, kein Session-Kill (Source `:1511+`).
- EAGAIN Retry-Budget 2 s / Poll 20 ms (nicht anfassen).

**IDs 100 / 200 / PI_DRIVE_TEST = LAB ONLY** — nicht F20.

## FIELD FACT (18.11.)

- Transport BCL_ACTIVE-äquivalent: HS v5/14/0x4000, WD stabil.
- Lab-Cert: HU Reject („Certificate is invalid or expired.“ / „Session is not logged in.“).
- Nachgelagerte AM/RHMI/CDS/Resource: **NOT_REACHED**, nicht widerlegt als „FAILED“.

## UNKNOWN

- Ob F20 nach **echtem** Cert denselben Resource-/AM-Pfad wie Lab nimmt.
- F20 Action-/Model-IDs / Handles.
- Ob Diagnose `NO_HCI_RX` vs `NO_ETCH_RX` mit heutiger Instrumentierung unterscheidbar (ohne neue Messpunkte → bei Impl `UNKNOWN`).

## Verworfene Annahmen (durch Audit + Field)

| Alte Annahme | Status |
|--------------|--------|
| `rhmi_state=SAS_AUTHENTICATED` ⇒ Wire-Auth OK | **REJECTED** (Field + Source `:1482-1485`) |
| Lab Soak/Seq ⇒ F20 Auto-ready | **REJECTED** (Audit PR #37 + Field) |
| `AM_REGISTERED` / `RUNTIME_ACTIVE` = Wire-ACK | **REJECTED** als Wire-Claim (TX-Queue States) |
| `WATCHDOG_MISS_NO_ETCH_REPLY` = eindeutige Ursache | **WEAK** — Sammelklasse, Split noch MISSING |
| checkResource=true ⇒ Upload fehlt = Fehler | **REJECTED** (seit Resource-Audit) |

## Tests / Commit-Policy

- **Jetzt:** nur Analyse-Docs committen.
- **Nach GAP-Review:** P1 AuthState zuerst; Tests für CERTIFICATE_REJECTED / LOGIN_REJECTED / AUTHENTICATED-positiv; Lab RUNTIME_ACTIVE Regression.
- Keine F20-Feldbehauptung aus Lab-Verhalten.
