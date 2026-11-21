# Field Gate B CLOSED → Next: F20 RHMI App Template

```yaml
date: 2026-11-21
gate_b: CLOSED
music_description: CLOSED
evidence: docs/evidence/FIELD_B3_GATEB_20261121T112446Z/
addendum: …/ADDENDUM_RHMI_AM_20261121.md
description_extract: …/resources/EXTRACT.md
status_doc: SAS_STATUS_CRYPTO_CLOSED_20261120.md
```

## Situation

```
SAS ACCEPT (F20)  →  AM  →  RHMI  →  CDS  →  AV
```

ist **FIELD FACT**. Protokoll-RE für Auth/Transport ist nicht mehr der Engpass.

Music DESCRIPTION (92 085 B) ist **DESK+FIELD cross-validated** — siehe [`resources/ui_description_multimedia_v3.xml`](../evidence/FIELD_B3_GATEB_20261121T112446Z/resources/ui_description_multimedia_v3.xml).  
Offen: Korrelation Models/Actions/Events ↔ Field `setData`/`setProperty`.

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
| Music DESCRIPTION = `ui_description_multimedia_v3.xml` (MD5 `e9e31c31…`, 92 085 B) | **CLOSED** (DESK+FIELD) |
| Eigenes PiDrive-Menü am F20 | OPEN (machbar, nicht bewiesen) |

## Next workstream (ordered)

1. Catalog **modelIds / actionIds / events** from DESCRIPTION + Field B3 Handle-23 `setData`/`setProperty`  
2. Optional: extract TEXTDB/IMAGEDB against addendum fingerprints  
3. Reproduce minimal Multimedia template in `f20_sim` / iDriveSim stub  
4. Wire **one** PiDrive action sink  
5. **One** field variable: AAIdrive session + PiDrive test entry  

**Not next:** Standalone signer, AOA, Screen-Mirroring-first, further `libaudio` dig, B3-blob reassembly of DESCRIPTION.

## Tooling

- Field SPP: `tools/b3_profile_relay.py`  
- Cross-check pad: `tools/sas_pad_crosscheck.py`  
- Lab HU: bt-analyzer `f20_sim` / idrivesim Etch stub (needs FIELD-sized caps eventually)
