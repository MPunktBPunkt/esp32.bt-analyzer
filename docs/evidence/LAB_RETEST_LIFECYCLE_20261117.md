# LAB Retest — Resource-Lifecycle (post-audit) — 2026-11-17

**claim_level:** In-process PASS (miss+hit) · USB→`.131` air PARTIAL · Dual-ESP FAIL  
**code:** lifecycle Phone-Sim + `wd_miss_limit=0` fix · unittest fixture-seed fix  
**FW:** `.131` / `.87` beide **0.3.20** sketch `1919808`

## Matrix

| Test | Result |
|------|--------|
| Host / `.108` unittest (6) | **PASS** |
| In-process Fall B (miss → setResource DESCRIPTION → init) | **PASS** (uploads=1, TEXTDB/IMAGEDB skip, ServiceException 213) |
| In-process Fall A (cache hit → kein setResource) | **PASS** (uploads=0, cache_hits≥1) |
| USB `hci0` → `.131` f20_sim SCN6 | **PARTIAL** |
| Dual-ESP `.87` → `.131` | **FAIL** (RFCOMM timeout) |

## In-process (`.108`)

```
miss: DESCRIPTION miss→upload 13598 B; TEXTDB/IMAGEDB miss→skip; initialize; setData→ServiceException(213)
hit:  DESCRIPTION hit; uploads=0; initialize reached
plan: DESCRIPTION → TEXTDB → IMAGEDB
```

## USB air (Pfad A)

| Gate | Status |
|------|--------|
| RFCOMM / HS v5/14/0x4000 | PASS |
| SAS / creates / CDS / 4× AM | PASS (phone TX); HU saw creates+CDS |
| `mybmw_rhmi_plan` | PASS |
| `rhmi_checkResource` DESCRIPTION TX | PASS (1×) |
| `_result_rhmi_checkResource` | **FAIL** — HU jsonl zeigt **keinen** `rhmi_checkResource` RX |
| setResource / initialize / setData | not reached |
| Watchdog | HU nur **1×** echo; Phone `wd_misses=27` mit `--wd-miss-limit 0` → **kein** hold_abort (W0-Fix wirkt) |

**Lesart (Audit):** Abbruch/Stagnation ≠ „fehlendes setResource“. Session bleibt mit miss_limit=0 offen, aber der erste check-Reply kommt auf dem Air-Pfad nicht an (Transport/Scheduling vor Cache-Entscheidung).

## Dual-ESP

Inquiry/RFCOMM weiterhin **FAIL** — sekundär; entwertet USB-Pfad nicht.

## Artefakte

- `LAB_RETEST_LIFECYCLE_20261117.json`
- `LAB_RETEST_USB_{phone,hu}_20261117.jsonl`
- `LAB_RETEST_DUAL_phone_20261117.jsonl`

## Next (unverändert W0→W1)

1. W0: HU-seitige WD-Echos über Resource-Fenster stabilisieren (nicht nur Client miss_limit).  
2. W1: warum `checkResource` TX die HU nicht erreicht / Reply fehlt — BCL/Etch-Korrelation vor künstlichem setResource.
