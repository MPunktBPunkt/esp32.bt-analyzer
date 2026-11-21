# Bluetooth Control Plane — CLOSED 2026-11-21

```yaml
checkpoint: 7603efe (+ Handle-23 correlation)
claim: Bluetooth research strand closed; remaining work is RHMI ID correlation → PoC
no_next: general technology-audit
```

## Status table

| Bereich | Status | Begründung |
|---------|--------|------------|
| Bluetooth Classic / SDP | **CLOSED** | Field Evidence |
| RFCOMM / BCL | **CLOSED** | Field + Lab |
| Etch | **CLOSED** | Field + Lab |
| SAS-Protokoll | **CLOSED** | Field + Crypto/Lab |
| OEM-SAS live | **CLOSED** | B3 Field Gate |
| RHMI | **CLOSED** | Field + Source |
| AM | **CLOSED** | B3 Field |
| CDS / AV | **CLOSED** | B3 Field |
| Music DESCRIPTION | **CLOSED** | 92 085 B + MD5-Match + Lab SHA-256-Match |
| Music RHMI Tree | **KNOWN** | XML vorhanden |
| Handle 23 | **KNOWN** | `me.hufman.androidautoidrive.music` |
| Models / Actions / Events → B3 | **OPEN** → *in progress* | Korrelation (siehe unten) |
| eigener RHMI-PoC | **OPEN** | noch kein F20 Field-PoC |
| Standalone-Signer | **OPEN** | Implementierungs-/Credential-Thema |

## Triple chain (DESCRIPTION)

```
AAIdrive Source
    │  ui_description_multimedia_v3.xml
    ▼
92 085 Bytes
    ├── MD5     = e9e31c31110680e13b7a112a7d77eb55  ← B3 checkResource
    └── SHA-256 = 8e1d0b21f6d7d554…                 ← LAB setResource
```

`e9e31c31…` = **MD5** (Wire `checkResource`). Nicht SHA-256.

Artifact: [`…/resources/ui_description_multimedia_v3.xml`](../evidence/FIELD_B3_GATEB_20261121T112446Z/resources/ui_description_multimedia_v3.xml) · [`EXTRACT.md`](../evidence/FIELD_B3_GATEB_20261121T112446Z/resources/EXTRACT.md)

## What this is *not*

Kein allgemeiner Technology-Audit mehr. Protokollwissen Control Plane ist weitgehend geschlossen.

## What remains (narrow)

```
Handle 23  me.hufman.androidautoidrive.music
        │
        ▼
92 085-B XML
        ├── Model / Property / Action / Event IDs
        ▼
B3 Field Traffic  (setData / setProperty / ackAction / triggerEvent)
        ▼
minimal RHMI PoC → F20 Field Test
```

Method: XML parse → Field-ID collect → **intersection** → only used IDs → minimal chain.  
Nicht 643/907 IDs blind einzeln.

## Handle-23 correlation (first cut, same day)

Evidence: magic-scan decode of `raw/phone_to_hu.bin` ∩ DESCRIPTION XML.  
Detail: [`HANDLE23_CORRELATION.md`](../evidence/FIELD_B3_GATEB_20261121T112446Z/resources/HANDLE23_CORRELATION.md)

| Metric | Value |
|--------|------:|
| XML unique numeric IDs | 643 |
| H23 `setData` calls / unique modelIds | 117 / **78** (100 % in XML) |
| H23 `setProperty` calls / components | 38 / **20** (100 % in XML) |
| H23 actions observed | `336`, `248` |
| H23 events observed | `661` (statusbar), `660` (multimediaInfo) |

Now-Playing spine (`audioHmiState` id=24): models **444–447**, **451–452**, **440/462**, list **458** — Field strings include `Spotify` / `Halestorm, I Prevail` / track title.

## Next

1. Finish minimal PoC ID set from correlation (NP + 1–2 toolbar actions)  
2. Lab `f20_sim` stub with that subset  
3. One F20 field variable  
4. Optional: TEXTDB/IMAGEDB; Standalone-Signer (parallel, not blocking PoC design)
