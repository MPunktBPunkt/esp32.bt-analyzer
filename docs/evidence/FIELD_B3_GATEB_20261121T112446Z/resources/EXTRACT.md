# Music DESCRIPTION extract — CLOSED 2026-11-21

```yaml
claim_level: DESK + FIELD cross-validated
file: ui_description_multimedia_v3.xml
size: 92085
md5: e9e31c31110680e13b7a112a7d77eb55
sha256: 8e1d0b21f6d7d554683e341d47d57aa50768a81679d9846c2b02306dfefafd76
```

## Verdict

> Music DESCRIPTION ist **bekannt**. `checkResource`-Fingerprint aus Field B3 = MD5 dieser Datei.  
> Offen ist nur noch die Korrelation Models/Actions/Events ↔ Field `rhmi_setData` / `setProperty` (Handle 23).

## Hash hygiene

| Algorithm | Value | Role |
|-----------|-------|------|
| **MD5** | `e9e31c31110680e13b7a112a7d77eb55` | Wire `rhmi_checkResource` (16 B) — Field B3 + Lab |
| **SHA-256** | `8e1d0b21f6d7d554683e341d47d57aa50768a81679d9846c2b02306dfefafd76` | Lab `rhmi_resource_rx` upload (`LAB_HOME_CONT10…`) |
| size | 92 085 B | Field addendum + Lab upload |

`e9e31c31…` ist **nicht** SHA-256.

## Provenance

- Source: BimmerGestalt/AAIdrive `@ 246e11d4` (parent of `de350bb`)  
  `app/src/test/resources/ui_description_multimedia_v3.xml`
- Unmodified copy; AAIdrive later loads RHMI assets from external APKs (`de350bb`), but this blob remains byte-identical to what the phone `checkResource`/`setResource`s for Music.
- Cross-check: Lab CONT10 uploaded DESCRIPTION with same size + SHA-256 after `checkResource` MD5 miss on the same digest.

## Root

```xml
<pluginApps>
  <pluginApp applicationType="Multimedia" text="basecore" applicationWeight="500">
```

~907 numeric `id=` attributes (643 unique, range 1…661).

## Next

Catalog model/action/event IDs against Field B3 Handle-23 `rhmi_setData` / `setProperty` sequence → PiDrive Weg A template.
