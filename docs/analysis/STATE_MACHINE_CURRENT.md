# STATE_MACHINE_CURRENT — IST aus Source (Phase A)

```yaml
date: 2026-11-18
phase: A
claim: SOURCE FACT only — no target states invented
primary: tools/bcl_dummy_hu.py (PhoneClientSession + DummyHuSession)
agent: tools/bcl_dummy_hu_agent.py
stub: tools/bcl_etch_stub.py
lab: tools/lab_p0_dual_esp_hold.py, lab_p0_rhmi_soak.py, lab_p0_rhmi_pidrive_seq.py
peripheral: controller/bmw_lab.py (GUI auth modes — not phone SM)
```

**Regel:** Nur Zustände, die im Source existieren. Zielarchitektur-Namen erscheinen hier **nicht** als Ist.

---

## 1. Existierende State-Träger (Variablen)

| Variable | Typ | Owner | Domain |
|----------|-----|-------|--------|
| `handshake` / `handshake_sent` | dict\|None / bool | Phone / DummyHu | Transport |
| `active` | bool | Phone | Transport (post-HS) |
| `selected_proto` / `selectproto` | int\|None | both | Transport |
| `knocked` / `skip_knock` / `knock_payload` | bool/bytes | both | Transport |
| `wire_open5001` / `open_etch` | bool | Phone | Transport→Etch |
| `_etch_stage` | str | Phone | Etch bootstrap |
| `_challenge` | bytes\|None | Phone | SAS |
| `_handles` | dict[str,int] | Phone | Bootstrap handles |
| `_rhmi_state` | str | Phone | **gemischte** SAS/AM/RHMI/Resource/Runtime |
| `_open_txns` | dict[int,dict] | Phone | Transaction |
| `_pending_check_mid` | int\|None | Phone | Resource wait |
| `_rhmi_plan` / `_rhmi_plan_i` | list/int | Phone | Resource plan |
| `_uploads_done` / `_cache_hits` | int | Phone | Resource counters |
| `_cds_props_queued` | bool | Phone | AM/CDS wave once |
| `_soak_phase` / `_soak_*` | str/… | Phone | Soak (test) |
| `_seq_phase` / `selected_action` | str | Phone | PiDrive seq (test/product) |
| `pending_pings` / `wd_misses` | local | agent `run_phone` | Watchdog |
| EAGAIN locals + `conn[eagain_total]` | — | agent `rfcomm_write_all` | TX backpressure |
| `abort_reason` / `wait_class` | str\|None | agent + snapshot | Diagnose |
| stub `stage` / `known_digests` | SasProbeStage / set | EtchSasCdsStub | HU-sim only |

---

## 2. Implementierte String-Zustände (`_rhmi_state`)

| State | Eintritt | Quelle |
|-------|----------|--------|
| `DISCONNECTED` | Default | `bcl_dummy_hu.py:618` |
| `SAS_AUTHENTICATED` | RX method `== "_result_sas_login"` | `:1482-1485` |
| `RHMI_CREATED` | `_result_rhmi_create` mit `result:int` | `:1499-1500` |
| `AM_REGISTERED` | `_queue_cds_and_apps` nach allen 4 Handles | `:832` |
| `RESOURCE_CHECKING` | Start Resource-Plan / next type | `:844`, `:1086` |
| `RESOURCE_UPLOAD` | Cache-Miss + lokale Payload | `:1050` |
| `RHMI_INITIALIZED` | TX-Queue `rhmi_initialize` (sofort) | `:1373` |
| `RUNTIME_ACTIVE` | unmittelbar nach `RHMI_INITIALIZED` | `:1374` |

### `_etch_stage` (separat, parallel)

| Value | Setzen |
|-------|--------|
| `idle` | default |
| `sas_cert` | `_start_mybmw` |
| `sas_login` | nach `_result_sas_certificate` |
| `bootstrap` | nach `_result_sas_login` / `_queue_bootstrap` |
| `apps` | `_queue_cds_and_apps` |
| `rhmi_runtime` | `_queue_rhmi_initialize_and_runtime` |
| `menu_upload` | **nur gelesen als Gate** — **nie assigned** → MISSING assign |

### Soak / PiDrive (Test)

| FSM-artig | Values |
|-----------|--------|
| `_soak_phase` | `stabilize`, `setData_repeat`, `multi_model`, `actions_window`, `mixed` |
| `_seq_phase` | `stabilize`, `setData_done`, `await_action`, `pidrive_internal`, `complete` |
| `selected_action` | `PI_DRIVE_TEST` (**LAB ONLY**) |

---

## 3. IST-State-Matrix (Phone MyBMW-Pfad)

FSM = logische Domäne im **einen** String `_rhmi_state` bzw. Implizit-Flags.

| FSM | State | Eintritt durch | Aktion | Exit/Event | Next State | Quelle |
|-----|-------|----------------|--------|------------|------------|--------|
| Transport | *(implizit)* no HS | RFCOMM connect | wait | HANDSHAKE frame | HS stored, `active=True` | `:1401-1434` |
| Transport | *(implizit)* HS done | handshake set | TX SP/KNOCK/OPEN5001/OPEN4004 | — | `active` | `:1415-1434` |
| Etch | `_etch_stage=idle` | default | — | mybmw_sim+HS | `sas_cert` | `:740-747` |
| Etch | `sas_cert` | `_start_mybmw` | TX `sas_certificate` | `_result_sas_certificate` | `sas_login` | `:1472-1481` |
| Etch | `sas_login` | cert result | TX `sas_login` | `_result_sas_login` | `bootstrap` | `:1482-1485` |
| SAS⊂RHMI | `SAS_AUTHENTICATED` | **any** `_result_sas_login` | `_queue_bootstrap` | create handles | … | `:1482-1485` **BUG vs Ziel** |
| Bootstrap | *(implizit)* | bootstrap TX | wait `_result_*_create` | all 4 int handles | `_queue_cds_and_apps` | `:1502-1504` |
| AM⊂RHMI | `AM_REGISTERED` | apps queued | registerApp wave | immediate | `RESOURCE_CHECKING` | `:832-845` |
| Resource | `RESOURCE_CHECKING` | plan start | TX `rhmi_checkResource` | `_result_rhmi_checkResource` | hit→next / miss→UPLOAD | `:997+` |
| Resource | `RESOURCE_UPLOAD` | cache miss+data | TX `rhmi_setResource` | *(kein Wait auf result)* | next check | `:1050-1087` |
| RHMI | `RHMI_CREATED` | create handle | — | all handles | AM_REGISTERED path | `:1500` |
| RHMI | `RHMI_INITIALIZED` | init **TX queued** | setData shell TX | immediate | `RUNTIME_ACTIVE` | `:1373-1374` |
| Runtime | `RUNTIME_ACTIVE` | same call | soak/seq allowed | abort/close | — | `:1374` |
| Soak | phases… | wall clock | setData/Actions | phase timer | next phase | `:1253+` |
| PiDrive | seq phases… | RUNTIME_ACTIVE+flag | setData 100 / await 200 | action/ack | `complete` | `:1203+` |
| WD | *(implizit)* | OPEN 5001 | ping/echo | miss≥limit | abort | agent |
| TX | *(implizit)* | write | retry EAGAIN | recovered/fatal | — | agent `:46+` |
| Diagnose | `wait_class` | snapshot | classify | phone_done | — | `:655-684` |

---

## 4. Was setzt Zustände (Funktionen)

| Funktion | Setzt |
|----------|-------|
| `_set_rhmi_state` | `_rhmi_state` + Event `mybmw_rhmi_state` |
| `_start_mybmw` | `_etch_stage=sas_cert` |
| `_queue_bootstrap` | `_etch_stage=bootstrap` |
| `_queue_cds_and_apps` | `AM_REGISTERED`, `RESOURCE_CHECKING`, `_etch_stage=apps` |
| `_on_check_resource_result` | `RESOURCE_UPLOAD` / `RESOURCE_CHECKING` |
| `_queue_rhmi_initialize_and_runtime` | `RHMI_INITIALIZED`, `RUNTIME_ACTIVE`, `_etch_stage=rhmi_runtime` |
| `on_bytes` (Phone) | `SAS_AUTHENTICATED`, `RHMI_CREATED`, HS/`active` |
| `tick_rhmi_soak` / `tick_rhmi_pidrive_seq` | soak/seq phases |
| `rfcomm_write_all` | EAGAIN counters/events |
| `run_phone` | `abort_reason`, WD misses |

---

## 5. Implizite Zustände (kein Enum)

- Transport Progress: nur `handshake`/`active`/Flags — **kein** `TransportState` Enum.
- Etch OPEN: Flag `open_etch`, kein `EtchState`.
- Auth Reject / Challenge Received: **MISSING** als State (Exception in `result` wird bei SAS **nicht** geprüft).
- Per-Handle Bootstrap (CDS/AM/RHMI/AV einzeln): nur `_handles` dict — **kein** `BootstrapState` / per-handle FSM.
- `AmState.REGISTERED` vs `RhmiState.INITIALIZED`: vermischt in `_rhmi_state`.
- verifyResource / Digests-Auth: **MISSING** (nur stub `known_digests` = Cache-Whitelist).
- Transaction lifecycle CREATED/SENT/WAITING/…: nur open dict + pop — **PARTIAL**.
- WatchdogState enum: **MISSING** (Zähler).
- TX_READY/BLOCKED/…: **MISSING** (lokale Retry-Schleife).
- Diagnose-Split `NO_HCI_RX` / `NO_RFCOMM_RX` / …: **MISSING** (nur 2–3 wait_class Strings).

---

## 6. Fehlerzustände (implementiert)

| Mechanismus | Werte | Anmerkung |
|-------------|-------|-----------|
| `wait_class` | `WATCHDOG_MISS_NO_ETCH_REPLY`, `STATE_MACHINE_WAIT` | Snapshot |
| Event | `WATCHDOG_MISS_REPLY_UNMATCHED` | orphan check mid |
| `abort_reason` | `tx_error`, `wd_echo_miss_limit`, remap→wait_class | agent |
| `mybmw_setdata_service_exception` | event only | SE 213 **beendet Session nicht** |
| SAS/Login ServiceException | **kein State** | trotzdem `SAS_AUTHENTICATED` möglich |

---

## 7. Kritische Source-FACTS (Feld-relevant)

1. **`SAS_AUTHENTICATED` ohne Positiv-Prüfung** (`:1482-1485`): Jeder dekodierte `_result_sas_login`-Methodenname reicht — auch wenn `result` eine `ServiceException` ist.  
   → FIELD_AUTH_PROBE: Wire Reject + lokaler State `SAS_AUTHENTICATED` (**widerspricht Zielregel**).

2. **`RUNTIME_ACTIVE` ohne Wait auf `_result_rhmi_initialize`**: State wird beim **Queue** der Init/setData gesetzt (`:1373-1374`).

3. **`AM_REGISTERED` ohne Wait auf `_result_am_registerApp`**: State beim Queue der Register-Calls (`:832`).

4. **checkResource=true → kein setResource**: implementiert (`:1035-1036`) — Zielregel Cache≠Upload **bereits IST**.

5. **setResource-Resultat nicht abgewartet** vor next check/init (`:1083-1087`).

6. **ServiceException 213** auf setData: Event, Session bleibt (`:1511-1522`) — Zielregel Transaktionsfehler **teilweise IST**.

---

## 8. DummyHu / Stub (Lab-HU, nicht Phone-FSM)

- Transport Flags: `handshake_sent`, `knocked`, `selected_proto`, WD counters.
- `sas_probe` stages: `none|dataack|challenge|challenge_rhmi|adaptive|f20_full`.
- `known_digests`: Cache-Hit-Whitelist für `rhmi_checkResource` — **nicht** SAS.Digests-Auth.

`bmw_lab.auth_mode` (`SIMULATED_AUTHORIZATION` / `F20_STRICT_WHITELIST`) steuert die GUI-Sim — **nicht** `PhoneClientSession._rhmi_state`.
