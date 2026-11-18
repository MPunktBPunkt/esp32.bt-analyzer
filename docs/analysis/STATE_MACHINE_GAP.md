# STATE_MACHINE_GAP — Ist vs. Zielarchitektur (Phase B)

```yaml
date: 2026-11-18
phase: B
prerequisite: STATE_MACHINE_CURRENT.md
rule: no code changes until GAP review
```

Legende: `EXISTS` · `PARTIAL` · `IMPLICIT` · `MISSING` · `TARGET ONLY`

---

## 1. Gap-Matrix nach Ziel-FSM

### TransportState

| Target | Gap | Ist-Äquivalent |
|--------|-----|----------------|
| DISCONNECTED | IMPLICIT | kein Named State; vor HS |
| RFCOMM_CONNECTED | IMPLICIT | Socket up, vor/ohne HS |
| BCL_INIT_SENT | IMPLICIT | `inits_sent` / INIT TX (agent) |
| HANDSHAKE_RECEIVED | PARTIAL | `handshake` dict / `handshake_sent` |
| PROTOCOL_SELECTED | PARTIAL | `selected_proto` / TX SP |
| KNOCK_SENT | PARTIAL | TX knock; HU `knocked` |
| BCL_ACTIVE | PARTIAL | `active=True` + WD |

**Kein** eigenes `TransportState`-Enum → insgesamt **PARTIAL/IMPLICIT**.

### EtchState

| Target | Gap | Ist |
|--------|-----|-----|
| CLOSED | IMPLICIT | vor OPEN 4004 |
| OPEN | IMPLICIT | `open_etch` + OPEN TX |
| RPC_ACTIVE | PARTIAL | `_etch_stage` ≠ idle / mybmw running |

### AuthState

| Target | Gap | Ist |
|--------|-----|-----|
| IDLE | IMPLICIT | vor `_start_mybmw` |
| CERTIFICATE_SENT | PARTIAL | `_etch_stage=sas_cert` |
| CHALLENGE_RECEIVED | PARTIAL | `_challenge` bytes **nur wenn** `result` bytes |
| LOGIN_SENT | PARTIAL | `_etch_stage=sas_login` |
| AUTHENTICATED | EXISTS **aber falsch gebunden** | `_rhmi_state=SAS_AUTHENTICATED` ohne Positiv-`result` |
| CERTIFICATE_REJECTED | **MISSING** | Field: Exception in cert result — State nicht gesetzt |
| LOGIN_REJECTED | **MISSING** | Field: Exception in login result — trotzdem AUTHENTICATED |
| SESSION_NOT_LOGGED_IN | **MISSING** | nur ASCII in PDU / create fails |
| TIMEOUT | **MISSING** | |
| PROTOCOL_ERROR | **MISSING** | decode_err Event only |

**Priorität #1:** AuthState härten (Zielregel AUTHENTICATED).

### BootstrapState + per-Handle

| Target | Gap | Ist |
|--------|-----|-----|
| NOT_STARTED / HANDLES_CREATING / HANDLES_READY | **MISSING** Enum | `_etch_stage=bootstrap` + `_handles` |
| CDS/AM/RHMI/AV einzeln | PARTIAL | Keys in `_handles` nur bei `result:int` |
| „alle ok“-Gate | EXISTS | `all(k in _handles for need)` — aber **kein** Reject-State pro Handle |

### AmState

| Target | Gap | Ist |
|--------|-----|-----|
| NOT_CREATED…REGISTERED… | **MISSING** | vermischt: `AM_REGISTERED` in `_rhmi_state` **bei TX-Queue**, nicht bei Register-ACK |

### ResourceState

| Target | Gap | Ist |
|--------|-----|-----|
| IDLE | IMPLICIT | vor Plan |
| CHECKING | EXISTS | `RESOURCE_CHECKING` |
| CACHE_HIT / CACHE_MISS | PARTIAL | Event `cache=hit|miss`, kein State |
| UPLOADING | EXISTS | `RESOURCE_UPLOAD` |
| UPLOADED / READY | **MISSING** | kein Wait auf setResource result |
| REJECTED | **MISSING** | |
| check≠set≠verify | PARTIAL | check≠set **EXISTS**; verify **MISSING** |

### RhmiState

| Target | Gap | Ist |
|--------|-----|-----|
| NOT_CREATED | IMPLICIT | |
| CREATED | EXISTS | `RHMI_CREATED` |
| INITIALIZING | **MISSING** | |
| INITIALIZED | PARTIAL | `RHMI_INITIALIZED` = TX queued |
| RUNTIME_ACTIVE | PARTIAL | gesetzt ohne Auth/AM/Resource-Erfolgsgate gegen Wire |
| BLOCKED | **MISSING** | |

Zielregel „RUNTIME_ACTIVE nur wenn Auth+nötige Schritte ok“: **nicht erfüllt** (Lab stub OK; Field Auth-Bug zeigt Mischzustand).

### RuntimeState

| Target | Gap | Ist |
|--------|-----|-----|
| IDLE/ACTIVE/… | **MISSING** Enum | überdeckt von `RUNTIME_ACTIVE` + soak |
| ACTION_PENDING/RECEIVED | PARTIAL | seq_phase / events |
| SE ≠ Session-Abort | EXISTS | setData SE 213 Event only |

### TransactionState (`_open_txns`)

| Target field/state | Gap | Ist |
|--------------------|-----|-----|
| CREATED/SENT/WAITING/MATCHED/… | **MISSING** Enum | dict open + pop on `_result_*` |
| message_id | EXISTS | key |
| etch_method | EXISTS | `method` |
| bcl_src/dest | EXISTS | |
| in_reply_to / timestamps / raw req/resp / result / exception | **MISSING** oder nur transient in decode | |

### WatchdogState

| Target | Gap | Ist |
|--------|-----|-----|
| DISABLED/ACTIVE | IMPLICIT | flags/OPEN |
| Ping NOT_SENT…TIMEOUT | PARTIAL | `pending_pings`, `wd_misses` |
| Orthogonalität | PARTIAL | wait_class vermischt WD↔RHMI wait |

### TX Backpressure

| Target | Gap | Ist |
|--------|-----|-----|
| TX_READY…TX_FATAL | **MISSING** Enum | Retry-Schleife + Events `*_write_eagain*` |
| EAGAIN ≠ AUTH/RHMI abort | EXISTS | separate path; **nicht anfassen** |

### Diagnose wait_class Split

| Target | Gap |
|--------|-----|
| NO_HCI_RX / NO_RFCOMM_RX / NO_BCL_RX / NO_ETCH_RX / … | **MISSING** |
| WATCHDOG_MISS_NO_ETCH_REPLY | EXISTS (zu breit) |
| STATE_MACHINE_WAIT | EXISTS |
| ETCH_REPLY_UNMATCHED | PARTIAL (`WATCHDOG_MISS_REPLY_UNMATCHED` event) |
| ETCH_REPLY_EXCEPTION | **MISSING** as wait_class |
| UNKNOWN | **MISSING** explicit |

### SoakState / PiDriveSequenceState

| Target | Gap | Ist |
|--------|-----|-----|
| Soak phases | PARTIAL | Namen weichen ab (`setData_repeat` vs `SETDATA`, kein PASS/FAIL State) |
| PiDrive phases | PARTIAL | nahe Ziel; `DISPATCHED`/`SINK_UPDATED`/`ACK_SENT` als Events, nicht Enum |
| LAB ONLY IDs 100/200/PI_DRIVE_TEST | EXISTS in Code — **müssen** als LAB ONLY markiert bleiben |

---

## 2. Feld-Evidenzgrenze (Mapping auf Ziel)

Aus `DEEP_FORENSIC_FIELD_AUTH_REJECT_20261118` + Source-Verhalten:

| Ziel-FSM | Field 2026-11-18 | Begründung |
|----------|------------------|------------|
| TransportState | ≈ BCL_ACTIVE | HS v5/14/0x4000, WD 0 miss |
| EtchState | ≈ RPC_ACTIVE | OPEN 4004 + RPC TX/RX |
| AuthState | ≈ CERTIFICATE_REJECTED (**TARGET label**; Ist-State **MISSING**) | Wire: invalid cert |
| Ist `_rhmi_state` | fälschlich `SAS_AUTHENTICATED` | Bug |
| Bootstrap/AM/Resource/RHMI/Runtime | **NOT_REACHED** (nicht FAILED) | Handles nicht int; Apps nicht gequeued |

---

## 3. Minimal Implementation Plan (nach Review — noch nicht ausführen)

### P1 — AuthState (breaking claim fix, Lab-kompatibel)

1. Neue klare Auth-Auswertung in `on_bytes` für `_result_sas_certificate` / `_result_sas_login`:
   - `result` bytes/challenge → CHALLENGE_RECEIVED / weiter
   - `ServiceException` / errorMsg → `CERTIFICATE_REJECTED` / `LOGIN_REJECTED`
   - **AUTHENTICATED nur** wenn Login-Result **kein** Exception und (Lab: void-OK Stub **oder** explizites OK-Feld)
2. `_rhmi_state=SAS_AUTHENTICATED` entkoppeln oder nur noch setzen wenn AuthState=AUTHENTICATED.
3. Bootstrap **nicht** queueen nach Reject.
4. Tests: Lab stub weiterhin AUTHENTICATED; Fixture mit Exception-PDU → REJECTED, kein bootstrap.

### P2 — Bootstrap / AM Trennung

1. Per-handle Status in `_handles` meta (`pending|ok|exception`).
2. `AM_REGISTERED` erst nach erfolgreichen Register-Results **oder** bewusstes Lab-Flag `assume_am_ok` für Soak-Kompatibilität.
3. `HANDLES_READY` Gate explizit.

### P3 — ResourceState

1. States CACHE_HIT/MISS/UPLOADED/REJECTED.
2. Optional wait `_result_rhmi_setResource` (Lab-Default: heutiges Fire-and-forget behalten hinter Flag, um Soak nicht zu brechen).

### P4 — TransactionState

1. Felder `ts_tx`, `result_class`, `exception` an `_open_txns` ohne Full-Rewrite.
2. Enum-ähnliche `status` Strings.

### P5 — Diagnose

1. wait_class nur splitten, wo Messdaten unterscheidbar (sonst `UNKNOWN`).
2. `ETCH_REPLY_EXCEPTION` wenn Auth/create SE gesehen.

### P6 — Runtime/Product

1. Nur soweit für Gates nötig; Soak/PiDrive Phasen belassen.
2. RUNTIME_ACTIVE Gate: AuthState==AUTHENTICATED (+ Lab stub path).

### Explizit nicht in diesem Plan

write11/EAGAIN Logic, BCL/RFCOMM/WD Root Cause, Dual-ESP, F20 Action/Model IDs, PiDrive Field Mapping.

---

## 4. Regressions-Schutz (bei späterer Impl)

- Host: vorhandene Unit/Decode-Tests + neue Auth-Transition-Tests
- Lab: Dual/Single RHMI lifecycle → `RUNTIME_ACTIVE`; Soak Kriterien; PiDrive seq `PI_DRIVE_TEST`
- Field: Reject-Pfad darf **nicht** mehr `SAS_AUTHENTICATED` loggen

**Review-Gate:** Keine Codeänderung bis dieses Dokument freigegeben.
