# Addendum — RHMI/AM Template-Extraktion (2026-11-21)

```yaml
parent: EVAL.md
claim_levels: FIELD FACT | STRONG | OPEN separated
source_capture: FIELD_B3_GATEB_20261121T112446Z
cross_check: independent deep-decode of same raw/jsonl
```

## Verdict

Gate B bleibt **CLOSED**. Zusätzlich ist der **Post-Auth Stack** so weit entschlüsselt, dass der nächste Schritt **Template-Extraktion** (nicht neues Protokoll-RE) ist.

## FIELD FACT (dieser Capture, raw + jsonl)

### AM — fünf `am_registerApp` (type `0x714679ad`)

| Anzeigename | Kategorie | Package / Addon-ID | weight (field 5, u16) |
|-------------|-----------|--------------------|------------------------|
| Google | OnlineServices | `com.google.android.googlequicksearchbox` | 745 (`0x02e9`) |
| Amazon Alexa | OnlineServices | `com.amazon.dee.app` | 782 (`0x030e`) |
| Bluetooth | Multimedia | `com.android.bluetooth` | (siehe Raw nach PNG) |
| YouTube | Multimedia | `com.google.android.youtube` | 464 (`0x01d0`) |
| Screen Mirroring | Multimedia | `io.bimmergestalt.idriveconnectaddons.screenmirror` | 1500 (`0x05dc`) |

Payload-Längen (jsonl): 2354 / 1324 / 2401 / 3247 / 1115 B.  
Icons: PNG 48×48 im Register-Block; **17** PNG-Signaturen im Phone→HU-Raw.

**Nicht** unter den fünf: Spotify / generische Media-Session.

### Spotify / Music — Abgrenzung

| Claim | Level |
|-------|-------|
| ASCII `Spotify` + Now-Playing `Halestorm, I Prevail` im Phone→HU-Raw | **FIELD FACT** |
| Package `com.spotify.music` in diesem Raw | **nicht gefunden** (nicht behaupten) |
| Addon `me.hufman.androidautoidrive.music` im Wire | **FIELD FACT** |
| Spotify ≠ `am_registerApp` in diesem Capture | **FIELD FACT** |
| Media-UI läuft über generische RHMI-App `…music` (Handle 23) | **STRONG** (deep-decode; Identifier auch in Raw) |

### Weitere AAIdrive-IDs im Wire (nicht alle = AM-Menü)

`me.hufman.androidautoidrive.notification.readout` · `.calendar` · `.music` · `.mapview` · `…assistant` · `io.bimmergestalt…screenmirror`

### CDS — konkrete Property-Namen (Raw)

u. a. `vehicle.VIN`, `vehicle.type/units/language/country/time/productiondate/productline/bordnet`,  
`driving.speedActual/odometer/mode/averageSpeed/averageConsumption/…`,  
`sensors.fuel/battery/temperatureExterior/SOCBatteryHybrid`, `entertainment.multimedia`.

### HU capabilities

**123** `iva_*`-Flags im HU→Phone-Raw, u. a. `iva_A4A_FOR_ANDROID`, `iva_CDMM_BLUETOOTH_AUDIO`, `iva_ENT_IAP_BLUETOOTH_COVERART`, DAB/SDARS/Cover-Flags.

### SAS

Zwei erfolgreiche Login-Zyklen (Challenges `8f873bb7…80da` und `0cebb994…aa29`), jeweils `_result_sas_login` korreliert.  
Pad-Transform `0x02000000` = FIELD; **RSA-VERIFY** gegen Wire-Cert dieses Captures = **OPEN**.

### Action-Pfad in *diesem* jsonl

| Method | Count |
|--------|------:|
| `rhmi_ackActionEvent` | 3 |
| `rhmi_triggerEvent` | 2 |
| `rhmi_onActionEvent` | **0** (hier nicht geloggt; älterer Capture ggf. separat) |

## STRONG — deep-decode (gleiche Evidence, unabhängige Auswertung)

### RHMI create handles ↔ App-ID

| Handle | App-ID | Rolle |
|-------:|--------|------|
| 21 | `me.hufman.androidautoidrive.notification.readout` | Readout |
| 22 | `me.hufman.androidautoidrive.calendar` | Calendar |
| 23 | `me.hufman.androidautoidrive.music` | Media UI |
| 24 | `me.hufman.androidautoidrive.mapview` | Map |
| 25 | `io.bimmergestalt…screenmirror` | Screen Mirroring (ggf. 2. Instanz) |

`am_addAppEventHandler` ident bestätigt u. a. `…assistant`, `…screenmirror`, `…music`.

### Resource cache

`_result_rhmi_checkResource` × **11** → result **True** (alle); **kein** `setResource` in dieser Session.  
= Fall „alles cached“ → `checkResource` → `initialize`.

### Music resource fingerprint (Handle 23)

| Resource | Hash (algorithm) | Size | Status |
|----------|------------------|-----:|--------|
| DESCRIPTION | MD5 `e9e31c31110680e13b7a112a7d77eb55` | 92 085 B | **CLOSED** — [`resources/ui_description_multimedia_v3.xml`](resources/ui_description_multimedia_v3.xml) |
| TEXTDB | `1a1f84fb…` | 393 B | OPEN extract |
| IMAGEDB | `0b010109…` | 162 483 B | OPEN extract |

**Hash hygiene:** Wire `checkResource` trägt **MD5** (16 B). SHA-256 der DESCRIPTION-Datei = `8e1d0b21f6d7d554…` (= Lab CONT10 `rhmi_resource_rx` Upload). `e9e31c31…` ist **nicht** SHA-256.

**Hinweis:** mapview/screenmirror teilen in der Decode-Tabelle denselben DESCRIPTION/IMAGEDB-Hash — nicht ungeprüft als getrennte Templates übernehmen.

### DESCRIPTION extract — CLOSED 2026-11-21

Siehe [`resources/EXTRACT.md`](resources/EXTRACT.md).

| Check | Value | Match |
|-------|-------|:-----:|
| size | 92 085 B | ✓ |
| MD5 (`checkResource` Field B3) | `e9e31c31110680e13b7a112a7d77eb55` | ✓ |
| SHA-256 (Lab CONT10 upload) | `8e1d0b21f6d7d554683e341d47d57aa50768a81679d9846c2b02306dfefafd76` | ✓ |

Provenance: AAIdrive Git `@ 246e11d4` `app/src/test/resources/ui_description_multimedia_v3.xml` (unmodified). Root: `<pluginApp applicationType="Multimedia" …>`.

## Epistemic hygiene

- Fünf `am_registerApp` ≠ fünf sichtbare Menüeinträge.
- „Spotify = ausschließlich AVRCP“ = **zu stark**; FACT: nicht AM-registriert; Media über `…music` RHMI + Player-Session.
- Offline BCL-Reassembly von `phone_to_hu.bin` (einfacher Framer) liefert kaum DATA-Frames — Live-`b3.jsonl` bleibt Methodenquelle.

## Next (PiDrive Weg A)

1. Music-DESCRIPTION Models/Actions/Events gegen Field B3 Handle-23 `setData`/`setProperty` korrelieren  
2. Minimales PiDrive-Menü aus Music-Template ableiten (nicht Screen Mirroring zuerst)  
3. Lab `f20_sim` reproduzieren → ein Feldversuch (eine Variable)  
4. Optional: TEXTDB/IMAGEDB extract; RSA-VERIFY Field-Raw; Standalone-Signer später
