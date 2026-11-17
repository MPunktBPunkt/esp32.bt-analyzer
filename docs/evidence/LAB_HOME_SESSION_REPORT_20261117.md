# Lab Home Session Report — 2026-11-17

**claim_level:** LAB FACT (OnePlus 12 ↔ f20_sim on Proxmox `.108` / ESP `.131`)  
**HU:** `C8:C9:A3:CB:7B:0A` · Alias `BMW 38304` · CoD `0x340408` · SCN **6** · profile `f20_sim`  
**Phone:** OnePlus 12 `AC:C0:48:5E:CB:20`  
**Bridge:** `hci_tcp_bridge.py` → `192.168.178.131:9754` (later with `--local-name 'BMW 38304'`)  
**FW:** ESP hci-agent **0.3.20**

---

## Executive summary

| Area | Verdict |
|------|---------|
| Pairing / AAIdrive green / Spotify A2DP | **PASS** (re-pair after alias issues) |
| BCL stack (HS→SAS→AM/RHMI/CDS) | **PASS** when RFCOMM up |
| W0 checkResource Fall A (no HU reply) | **REJECTED** — HU replies; phone continues to setResource |
| CDS inject (battery/time/engine/fuel/VIN/…) | **PASS** across CONT3–13 |
| RHMI action TX | **PASS** (TX fact; no `ackActionEvent` logged) |
| AVRCP / A2DP control | **PASS** in CONT3/5/8 (Play/Next; transport active) |
| Alias race `BMW 38304` ↔ `BT-Analyzer-.87` | **ROOT CAUSE FIXED** in CONT12 |
| HCI bridge local-name pin | **deployed** (belt-and-suspenders) |
| Remaining risk | ESP `.131` panics / RFCOMM `write_error:11` / `eof` flaps |

---

## Timeline

| UTC≈ | ID | What was tested | Result |
|------|-----|-----------------|--------|
| Prep | `LAB_HOME_PREP` | Session prep, eligibility, bridges 0.3.20 | READY |
| 1652Z | `LAB_HOME` | OnePlus↔f20_sim pair, AAIdrive green, Spotify playing | **PASS** |
| 1701Z | `LAB_W0` | `BCL_RHMI_STOP_AFTER=description_check`; checkResource reply forensic | Fall A **REJECTED** |
| 1732Z | `CONTINUED` | Post-W0 continued session | green / alias fight noted |
| 1737Z | `CONT3` | CDS inject · RHMI actions×40 · AVRCP Play/Next/Pause | **PASS** |
| 1749Z | `GREEN` | Broad CDS (VIN/lang/drivingStyle) · RHMI×20 · hold green | **PASS** |
| 1751Z | `GREENPULSE` | Stability pulse | Connected + Alias BMW |
| 1759–1809Z | `CONT4–8` | CDS/RHMI/AVRCP loops; multi-app AM names; Alias race confirmed | functional **PASS**; race **CONFIRMED** |
| 1813–1820Z | `CONT9–11` | Alias mitigation (settings fix, faster pin, stale pin cleanup) | partial; race still open |
| 1930Z | `CONT12` | Bridge `--local-name`; **find+kill** `system-alias BT-Analyzer-.87` loop | race **FIXED**; CDS **PASS** |
| 1934Z | `CONT13` | Hold after fix; CDS inject; watchdog/handles | **PASS** (0 alias flips) |

---

## Detailed results

### 1. Pairing & phone UX (`LAB_HOME` 1652Z)

- Re-pair to HU `BMW 38304` after earlier “BMW wird verwendet” / connect failures.
- AAIdrive showed **green**; Spotify A2DP playback confirmed on phone.
- Wire: handshake, SAS login, AM register, RHMI setData/check/setResource, CDS live.
- Artifacts: `LAB_HOME_20261117T1652Z_{hu.jsonl,hu.btsnoop,summary.txt}`.

### 2. W0 — checkResource reply path (`LAB_W0` 1701Z)

| Question | Verdict |
|----------|---------|
| checkResource RX on HU | yes (`rhmi_check_resource`, known/result false) |
| HU Etch reply TX | yes — immediate `etch_data_tx` / `_result_rhmi_checkResource` (`03860e18858e`) |
| Phone continues to setResource | yes → miss reply was delivered |
| Fall A (no reply) | **REJECTED** on this phone→f20_sim path |

Note: `STOP_AFTER=description_check` only limits HU follow-on; it does not stop phone-driven multi-app check/set.

### 3. CDS / RHMI / AVRCP continuous runs (CONT3–11, GREEN)

Repeated while Connected:

- **CDS inject** → matching `cds_property_tx` (engine, battery, time, fuel, nav, VIN, language, drivingStyle, …).
- **RHMI action matrices** (dozens of TX) without forcing UI ack; phone still sent `rhmi_setData` / `setProperty`.
- **AVRCP**: Play/Next/Pause sequences; MediaTransport active when Spotify routed (CONT3/5/8).
- **AM apps observed:** screenmirror, YouTube addon, assistants, notification readout, etc. (CONT5).

### 4. Alias race — diagnosis & fix (CONT8–12)

**Symptom:** Alias / mgmt local name flipped every ~4s between `BMW 38304` and `BT-Analyzer-.87`, fighting pin scripts and confusing the phone.

**False leads:** ESP default name alone; bridge rewrite insufficient (kernel commits outbound Write Local Name before vhci rewrite).

**Root cause (CONT12):** Abandoned systemd `session-11364.scope` / `bash -s` (PID 3830904, since ~17:36) looping:

```text
bluetoothctl system-alias BT-Analyzer-.87
```

**Fix:** Kill that loop; keep `bt-pair-agent` + light Alias pin; deploy `hci_tcp_bridge --local-name 'BMW 38304'` / `HCI_PIN_LOCAL_NAME`.

**Verification:** 20–30s holds with **0 flips**; Alias and btmgmt name both `BMW 38304`. CONT13 repeat **PASS**.

### 5. Tooling change

`tools/hci_tcp_bridge.py`:

- `--local-name` / `HCI_PIN_LOCAL_NAME`
- Rewrite HCI Write Local Name (host→controller) and Read Local Name Complete (controller→host)

Useful after ESP panic/reinit; **not** a substitute for killing host `system-alias` writers.

---

## Freeze / next priority

See `docs/analysis/FREEZE_C5CB0E6_HOME_SESSION_20261117.md`.  
P0 workstream: `docs/evidence/LAB_P0_ESP_RFCOMM_20261117.md` (ESP panic ↔ RFCOMM flap correlation). Do **not** re-litigate F20 `WATCHDOG_MISS_NO_ETCH_REPLY` until transport is stable.

## Open issues (not blocking today’s green claims)

1. **ESP `.131` panics** / **RFCOMM flaps** — P0; often `write_error:11` during `etch_reply` TX (transport pressure).
2. **No `ackActionEvent`** in HU logs for action sweeps (TX-only fact).
3. **AVRCP track metadata** often empty in HU plaintext even when Spotify plays.
4. **W0 full A_or_C isolate** with parallel phone-sim jsonl still optional follow-up.

---

## Artifact index

| Doc | Role |
|-----|------|
| `LAB_HOME_PREP_20261117.md` | Prep / eligibility |
| `LAB_HOME_20261117T1652Z.md` (+ jsonl/btsnoop/summary) | Initial green pair |
| `LAB_W0_20261117T1701Z.md` (+ jsonl/btsnoop) | checkResource Fall A reject |
| `LAB_HOME_CONTINUED_*` / `CONT3`–`CONT11` | Continuous CDS/RHMI/AVRCP / alias hunt |
| `LAB_HOME_GREEN_*` / `GREENPULSE_*` | Green hold + broad CDS |
| `LAB_HOME_CONT12_20261117T1930Z.md` | Alias root cause + bridge pin |
| `LAB_HOME_CONT13_20261117T1934Z.md` | Post-fix hold |
| This file | Session rollup |

Binary captures (`.jsonl` / `.btsnoop`) live next to the matching `.md` where collected.
