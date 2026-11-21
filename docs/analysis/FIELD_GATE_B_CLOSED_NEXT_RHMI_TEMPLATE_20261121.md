# Field Gate B CLOSED → Next: F20 RHMI App Template

```yaml
date: 2026-11-21
gate_b: CLOSED
music_description: CLOSED
handle23_correlation: FIRST_CUT
evidence: docs/evidence/FIELD_B3_GATEB_20261121T112446Z/
addendum: …/ADDENDUM_RHMI_AM_20261121.md
description_extract: …/resources/EXTRACT.md
correlation: …/resources/HANDLE23_CORRELATION.md
control_plane: BT_CONTROL_PLANE_CLOSED_20261121.md
lab_stub_plan: MUSIC_NP_SPINE_LAB_STUB_20261121.md
status_doc: SAS_STATUS_CRYPTO_CLOSED_20261120.md
```

## Situation

```
SAS ACCEPT (F20)  →  AM  →  RHMI  →  CDS  →  AV
```

ist **FIELD FACT**. Bluetooth Control Plane = **CLOSED** — siehe [`BT_CONTROL_PLANE_CLOSED_20261121.md`](BT_CONTROL_PLANE_CLOSED_20261121.md).  
Kein weiterer allgemeiner Technology-Audit.

Music DESCRIPTION **CLOSED**; Handle-23 Field∩XML **first cut** — 78 modelIds / 20 components / actions 336·248 / events 660·661.  
NP-Spine: `audioHmiState` 24 → models 444–447 (+ Zeit/Progress/Playlist).

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
| H23 Field modelIds ⊆ DESCRIPTION | **STRONG** (78/78) |
| Eigenes PiDrive-Menü am F20 | OPEN (machbar, nicht bewiesen) |

## Next workstream (ordered)

Frozen plan: [`MUSIC_NP_SPINE_LAB_STUB_20261121.md`](MUSIC_NP_SPINE_LAB_STUB_20261121.md)

1. Lab stub = **only** IDs **444, 445, 446/447, 660, 661, 336, 248**  
2. Prove: `initialize` → `setData` NP → render → action 336/248 → events 660/661  
3. **One** F20 field trial — question: which Music-RHMI defs suffice for a foreign RHMI client UI?  
4. Then: PiDrive implementation (not more Wire-RE)  

**Not next:** BT-stack work, general technology-audit, Standalone signer as blocker, AOA, Screen-Mirroring-first, `libaudio` dig, DESCRIPTION reassembly, full 78-model port.

## Tooling

- Field SPP: `tools/b3_profile_relay.py`  
- Cross-check pad: `tools/sas_pad_crosscheck.py`  
- Lab HU: bt-analyzer `f20_sim` / idrivesim Etch stub (needs FIELD-sized caps eventually)
