# P1 AuthState — Implementierung (2026-11-18)

```yaml
scope: classify_result + AuthState + ETCH_REPLY_EXCEPTION + menu_upload dead-gate
frozen: write11/EAGAIN, BCL/RFCOMM transport, WD root cause, Dual-ESP, F20 IDs
tests: tests/host/test_auth_state_p1.py (T1–T4, R5, field reject)
```

## Änderungen

| Item | Verhalten |
|------|-----------|
| `classify_result()` | EXCEPTION ≻ CHALLENGE ≻ VOID_OK ≻ OK_INT ≻ UNPARSED |
| `PhoneClientSession._auth_state` | AUTH_IDLE→…→AUTHENTICATED; Neg: CERTIFICATE_REJECTED, LOGIN_REJECTED, … |
| `SAS_AUTHENTICATED` | nur wenn `AuthState==AUTHENTICATED` (positiver Login: VOID_OK\|OK_INT + inReplyTo match) |
| Bootstrap | geblockt nach Auth-Exception (`NOT_REACHED`) |
| `wait_class` | `ETCH_REPLY_EXCEPTION` bei Auth-Reject |
| `menu_upload` | Dead-Gate entfernt; Reentrancy nur `rhmi_runtime`; Event-Name `mybmw_menu_upload_queued` bleibt |

## Evidence-Semantik

| Kontext | Vorher | Nachher |
|---------|--------|---------|
| FIELD_AUTH_PROBE Lab-sim Cert | Wire Reject + lokaler `SAS_AUTHENTICATED` | `CERTIFICATE_REJECTED`, kein Bootstrap |
| Lab f20_sim Stub | AUTH + RUNTIME | unverändert (T1 + p0_p2) |
| setData SE 213 | Session bleibt | unverändert (R5) |

## menu_upload Inventur

| Frage | Antwort |
|-------|---------|
| Wo gelesen? | `_queue_rhmi_initialize_and_runtime` Reentrancy-Guard |
| Wo gesetzt? | **nirgends** |
| Maßnahme | Gate-Zweig entfernt; kein Dummy-Assign |
