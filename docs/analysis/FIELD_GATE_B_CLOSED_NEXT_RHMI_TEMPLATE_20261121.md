# Field Gate B CLOSED → Next: F20 RHMI App Template

```yaml
date: 2026-11-21
gate_b: CLOSED
evidence: docs/evidence/FIELD_B3_GATEB_20261121T112446Z/
addendum: …/ADDENDUM_RHMI_AM_20261121.md
status_doc: SAS_STATUS_CRYPTO_CLOSED_20261120.md
```

## Situation

```
SAS ACCEPT (F20)  →  AM  →  RHMI  →  CDS  →  AV
```

ist **FIELD FACT**. Protokoll-RE für Auth/Transport ist nicht mehr der Engpass.

## Claim hygiene

| Claim | Level |
|-------|-------|
| F20 akzeptiert live MyBMW/AAIdrive APP_AUTH | FIELD FACT |
| B3 profile relay trägt Bytes | FIELD FACT |
| 5× `am_registerApp` (Google/Alexa/BT/YouTube/ScreenMirror) | FIELD FACT |
| Spotify ≠ diese AM-Liste | FIELD FACT |
| Media-UI = RHMI app `…music` | STRONG |
| 11/11 `checkResource=true`, kein Upload | STRONG |
| RSA-VERIFY dieses Captures | OPEN |
| Music DESCRIPTION 92 085 B im Repo | nicht gefunden → OPEN extract |
| Eigenes PiDrive-Menü am F20 | OPEN (machbar, nicht bewiesen) |

## Next workstream (ordered)

1. **Extract** Music DESCRIPTION (+ TEXTDB/IMAGEDB) — hash/size check against addendum fingerprint  
2. Catalog **modelIds / actionIds / events** from DESCRIPTION + field `setData`  
3. Reproduce minimal Multimedia template in `f20_sim` / iDriveSim stub  
4. Wire **one** PiDrive action sink  
5. **One** field variable: AAIdrive session + PiDrive test entry  

**Not next:** Standalone signer, AOA, Screen-Mirroring-first, further `libaudio` dig.

## Tooling

- Field SPP: `tools/b3_profile_relay.py`  
- Cross-check pad: `tools/sas_pad_crosscheck.py`  
- Lab HU: bt-analyzer `f20_sim` / idrivesim Etch stub (needs FIELD-sized caps eventually)
