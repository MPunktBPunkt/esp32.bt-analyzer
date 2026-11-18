# STATE_MACHINE_TRANSITIONS — IST Transition-Matrix (Phase A/B)

```yaml
date: 2026-11-18
scope: PhoneClientSession mybmw_sim path + agent WD/TX
```

Nur **implementierte** Übergänge. Ziel-only Zustände: siehe GAP.

---

## 1. Transport / Session (implizit)

| From | Event | Action | To | File |
|------|-------|--------|-----|------|
| (no HS) | RFCOMM data, non-HS | log unexpected | (no HS) | `:1403-1405` |
| (no HS) | HANDSHAKE parse OK | store HS; TX SP?/KNOCK?/OPEN WD;/OPEN Etch; `active=True`; maybe `_start_mybmw` | HS+active | `:1406-1437` |
| HS+active | DATA non-Etch | ignore (mybmw) | same | `:1441-1445` |
| HS+active | Etch decode fail | event `mybmw_etch_decode_err` | same | `:1450-1457` |

Agent:

| From | Event | To |
|------|-------|-----|
| connected | controlled_init, not full_client | stop after HS (no further BCL client TX) |
| active+WD | echo miss ≥ limit | `abort_reason=wd_echo_miss_limit` → hold end |
| soak drain | OSError send | `abort_reason=tx_error` |

---

## 2. Etch stage + Auth (kritisch)

| From `_etch_stage` | Event | Action | To | `_rhmi_state` |
|--------------------|-------|--------|-----|---------------|
| `idle` | `_start_mybmw` | TX `sas_certificate` | `sas_cert` | unchanged (`DISCONNECTED`) |
| `sas_cert` | `_result_sas_certificate` | if result bytes→`_challenge`; **always** TX `sas_login` | `sas_login` | unchanged |
| `sas_login` | `_result_sas_login` | `_queue_bootstrap` | `bootstrap` | **`SAS_AUTHENTICATED`** |

**Fehlende Transitions (TARGET ONLY / MISSING):**

| From | Event | Should go (Ziel) | Ist |
|------|-------|------------------|-----|
| `sas_cert` | cert `ServiceException` | `CERTIFICATE_REJECTED` | weiter Login mit Zero-Challenge |
| `sas_login` | login `ServiceException` | `LOGIN_REJECTED` | **`SAS_AUTHENTICATED`** |
| Auth reject | — | stop bootstrap | bootstrap **läuft** |

---

## 3. Bootstrap / Handles / AM

| From | Event | Action | To |
|------|-------|--------|-----|
| `bootstrap` | TX ver/info/caps/cds/am/rhmi/av create | wait | same |
| waiting creates | `_result_*_create` + `result:int` | `_handles[k]=int` | partial handles |
| waiting creates | `_result_*_create` + non-int (SE) | **no handle store** | stuck partial — **kein** Reject-State |
| all 4 handles present | — | `_queue_cds_and_apps` | `_etch_stage=apps`; `_rhmi_state=AM_REGISTERED`→`RESOURCE_CHECKING` |

---

## 4. Resource

| From | Event | Action | To |
|------|-------|--------|-----|
| `RESOURCE_CHECKING` | TX `rhmi_checkResource` | `_pending_check_mid=mid` | waiting |
| waiting | `_result_rhmi_checkResource` result **True** | hit++; plan_i++; next check or init | `RESOURCE_CHECKING` or init |
| waiting | result **False** + local data | TX `setResource`; plan_i++ | `RESOURCE_UPLOAD` → next check |
| waiting | False + no data / stop_after | skip upload; plan_i++ | next / init |
| waiting | wrong `_inReplyTo` | orphan event `WATCHDOG_MISS_REPLY_UNMATCHED` | stay pending semantics broken |
| plan done | — | `_queue_rhmi_initialize_and_runtime` | `RHMI_INITIALIZED`→`RUNTIME_ACTIVE` |

**Kein** Übergang auf `_result_rhmi_setResource`.

---

## 5. Runtime / Soak / PiDrive

| From | Event | To |
|------|-------|-----|
| `RUNTIME_ACTIVE` + soak | timers | `_soak_phase` stabilize→setData_repeat→multi_model→actions_window→mixed |
| `RUNTIME_ACTIVE` + pidrive | timers | `_seq_phase` stabilize→setData_done→await_action |
| await_action | `rhmi_onActionEvent` actionId==200 | `selected_action=PI_DRIVE_TEST`; ack; later `complete` |
| any runtime | `_result_rhmi_setData` + ServiceException | event only; **state unchanged** |

LAB ONLY: modelId **100**, actionId **200**, sink **PI_DRIVE_TEST**.

---

## 6. Transaction (`_open_txns`)

| From | Event | To |
|------|-------|-----|
| — | `_queue_rpc` non-result | insert `{method,bcl_src,bcl_dest,…}` |
| open | any `_result_*` with `_inReplyTo` | pop mid |
| open check | orphan mid | event; no pop of expected |

Keine TIMEOUT-Transition implementiert.

---

## 7. Watchdog / TX / Diagnose

### Watchdog (agent)

| From | Event | To |
|------|-------|-----|
| WD open | ping TX | outstanding in `pending_pings` |
| outstanding | echo DATA 5001 | RTT log; clear |
| outstanding | miss streak | `wd_misses++`; abort if ≥ limit |

### TX EAGAIN (HU agent write path only)

| From | Event | To |
|------|-------|-----|
| writing | EAGAIN | poll/retry until budget |
| retry | success | `eagain_recovered` event |
| retry | budget exhausted | `write_failed` / close path |

### wait_class (snapshot)

| Condition | wait_class |
|-----------|------------|
| pending checkResource txn | `WATCHDOG_MISS_NO_ETCH_REPLY` |
| else `_rhmi_state==RESOURCE_CHECKING` | `STATE_MACHINE_WAIT` |
| `RHMI_INITIALIZED`/`RUNTIME_ACTIVE` | `None` |

---

## 8. Vollständiger Lab-Happy-Path (IST)

```
RFCOMM → HS → SP/KNOCK/OPEN → sas_cert → sas_login
  → SAS_AUTHENTICATED → bootstrap creates
  → handles → AM_REGISTERED → RESOURCE_CHECKING
  → (hit|upload)* → RHMI_INITIALIZED → RUNTIME_ACTIVE
  → [soak | pidrive seq]
```

## 9. Field-Reject-Path (IST, 2026-11-18)

```
RFCOMM → HS → … → sas_cert
  → _result_sas_certificate (SE: invalid cert)  # still advances
  → sas_login
  → _result_sas_login (SE: no cert yet)
  → SAS_AUTHENTICATED   # BUG
  → bootstrap create TX
  → _result_*_create (SE: not logged in)  # no int handles
  → stuck: no AM_REGISTERED / no RESOURCE / no RUNTIME
  → WD remains healthy
```

Ziel-Soll nach P1:

```
… → CERTIFICATE_REJECTED (or LOGIN_REJECTED)
  → stop; Bootstrap/AM/RHMI = NOT_REACHED
  → never SAS_AUTHENTICATED / RUNTIME_ACTIVE
```
