# Tiefenforensik 16.11.2026 — Etch-Hash-Auflösung, SAS/RHMI/CDS auf dem F20-Wire & Rekonstruktion des 3-s-Fensters

**Datum:** 2026-11-16  
**Quellen:** alle acht `docs/bluetooth_20261115_*.log` + sieben `docs/bluetooth_20261114_*.log`, Feld-Captures `FIELD_P0_HOLD_*` / `FIELD_BURST_20261115/*`, Lab-Captures `LAB_SAS_*` / `LAB_ETCH_REPLY_SRC12_*` sowie lokaler BimmerGestalt-Stand (`BMWRemoting.etch`, `CDSProperty.kt`, `BclMultiplexer.kt`, `PrivateKeyHandling.kt`).

Dieses Dokument korrigiert und erweitert `ONEPLUS_BT_FORENSIC_20261115.md` und `FIELD_AAIDRIVE_BTLOG_20261115.md` an den Stellen, die dort mangels Etch-Hash-Tabelle als `UNKNOWN` oder „nicht SAS“ geführt wurden.

---

## 1. Apache-Etch-sdbm-Hash löst 100 % aller F20-Etch-Header auf

Apache Etch (`org.apache.etch.util.Hash`, BinaryTaggedData v3: `03 86 <u32BE hash> <nfields>`) hasht Typ- und Feldnamen mit sdbm auf Seed `5381`:

```python
h = 5381
for b in name.encode("utf-8"):
    h = (b + (h << 6) + (h << 16) - h) & 0xFFFFFFFF
```

Gegen `de.bmw.idrive.BMWRemoting` (`BMWRemoting.etch`) ergeben sich ohne einen einzigen unbekannten Rest-Hash **alle** in den F20-Logs gedumpten Nachrichtenköpfe:

| Hash (hex) | Aufgelöster Etch-Typ / Feld | Wo im F20-Feld beobachtet | Stufe |
|------------|-----------------------------|---------------------------|-------|
| `0x9c6372b8` | `BMWRemoting._result_sas_certificate` | `E-553` (`173553`) `17:36:33.611`, `src=15→4004`, `plen=67` (`etch_len=59`), `result = bytes(len=16, prefix=0194…)` | **FIELD FACT** |
| `0xa6b0ffca` | `BMWRemoting._result_sas_login` | `S-B` (`102058`) `10:21:31.972`, `src=10→4004`, `plen=44` (`etch_len=36`) | **FIELD FACT** |
| `0x19481364` | `BMWRemoting._result_rhmi_getCapabilities` | `E-520` `17:35:44.156` & `E-553` `17:36:31.846`, `src=10→4004`, **`plen=5306` (`0x14BA`)**, `etch_len=5298` (`0x14B2`) | **FIELD FACT** |
| `0xae0d3d69` | `BMWRemoting.cds_onPropertyChangedEvent` | 37× über `src=11, 12, 13, 14` (`S-B`, `E-520`, `E-637`) | **FIELD FACT** |
| `0xcd863443` | `BMWRemoting._result_cds_getPropertyAsync` | `S-A` (`102033`) `10:20:55.381` auf **SCN 10**, `src=13→4004`, `plen=186` | **FIELD FACT** |
| `0x…` (3×) | `BMWRemoting._result_cds_addPropertyChangedEventHandler` | `S-B` (`src=12`, 2×) & `E-637` (`src=14`, 1×), `plen=44` | **FIELD FACT** |
| `0xe52b6070` | `BMWRemoting._result_am_registerApp` | `S-B` `10:21:39.505`, `src=14→4004`, `plen=44` | **FIELD FACT** |
| `0xec3a5a1e` | `BMWRemoting._result_am_addAppEventHandler` | `E-637` `17:43:26.944`, `src=17→4004`, `plen=44` | **FIELD FACT** |
| `0xff7c4198` | `BMWRemoting._result_rhmi_initialize` | `E-520` `17:35:49.835`, `src=19→4004`, `plen=44` | **FIELD FACT** |
| `0x…` (6×) | `BMWRemoting._result_rhmi_setData` | `S-B`, `E-553`, `E-637` auf `src=17, 18, 19`, `plen=44` | **FIELD FACT** |
| `0x…` (1×) | `BMWRemoting._result_rhmi_setProperty` | `E-637` `17:43:24.286`, `src=19→4004`, `plen=44` | **FIELD FACT** |
| `0x304ba8bb` | `BMWRemoting.sas_certificate` (Request) | Lab Phone→Dummy (`src=10`), `7e002a4d` = `sas_login` | **LAB/DESK FACT** |
| `0x6306b468` / `0xeda8c9a6` / `0x8104fdc2` / `0x144a776f` | `_messageId` / `_inReplyTo` / `result` / `data` | in allen Reply-/Request-Structs | **FIELD FACT** |

### Korrekturen gegenüber Stand 15.11.

1. **SAS ist auf dem F20-Wire direkt beobachtet (`FIELD FACT`), nicht `UNKNOWN`:**
   - Sowohl die **16-Byte-SAS-Challenge** der HU (`_result_sas_certificate`, `0002000F0FA40043DEADBEEF0000003B03869C6372B803868104FDC28B100194…`) als auch die **Login-Bestätigung** (`_result_sas_login`, `0002000A0FA4002CDEADBEEF000000240386A6B0FFCA0286EDA8C9A687000001…`) stehen wörtlich in den Logs vom 15.11.
   - SAS liegt **nicht** als eigene Schicht vor Etch, sondern läuft **als Etch-RPC über `dest=4004`** (`sas_certificate(p7b)` → 16-B-Challenge → `MD5withRSA`-Signatur in `sas_login` → `_result_sas_login`).
2. **Die 667-B-UIH-Flut ist primär `_result_rhmi_getCapabilities`, nicht „CDS-Bursts“:**
   - Ein einzelner BCL-DATA-Frame der HU trägt `plen = 5306` (`0x14BA`, `8 B deadbeef + 5298 B Etch Map`). Auf RFCOMM (MTU **667 B** HU→Phone) zerfällt genau dieser Frame in **`7 × 667 + 1 × 645 = 5314` Byte** (`len=645` in `E-637` `17:43:18.985` gemessen!).
   - Die darin sichtbaren Strings (`_ENT_MTP_OFF = false`, `iva_ENT_USB_COVER_ART_IPOD`, `iva_MYV_LIGHT_INTERIOR*`, `iva_TC_REAR_WINDOW_C* = not_active`, `eco_conf_se*`) sind **HMI-/Codier-Capabilities der F20-HU** aus `rhmi_getCapabilities("", 255)`, keine CDS-Properties.
3. **Asymmetrische BCL-Fragmentierung & richtungsinvariantes `(src, dest)`:**
   - **Phone→HU** fragmentiert BCL-DATA bei **4000 B** Payload (`4008 B` Frame = `6 × 666 + 12 B` RFCOMM, Phone-TX-MTU = **666 B**).
   - **HU→Phone** sendet Pakete **> 4000 B** (`plen = 5306`, innerhalb ihres `bufferSize = 0x4000` = 16 384 B) unfragmentiert in **einem** BCL-DATA-Paket.
   - `Pair(src, dest)` ist in BCL **richtungsinvariant** (`BclMultiplexer.kt:50`): HU→Phone-Antworten tragen wie Phone→HU **`src = 10..19, dest = 4004`** (nicht `src=4004, dest=10`).

---

## 2. Lückenlose Rekonstruktion des 3-s-Fensters (Session S-B `102058`)

Aus den exakten `PORT_WriteDataCO`-Schreiblängen und den RX-Callbacks (`type=1`) löst sich das vermeintlich „blinde“ 3-s-Fenster vollständig auf:

| Zeit (`11-15`) | Δ | Richtung / Event | Länge | Bedeutung (Byte-Arithmetik) |
|----------------|---|------------------|------:|-----------------------------|
| `10:21:25.427` | 0 | RFCOMM `scn=6` offen | — | `dlci=12` (lokal log) / Client-Socket `uid=10479` |
| `10:21:25.440` | +13 ms | Phone→HU `WriteDataCO` | **4 B** | **1. `INIT` (`12 34 56 78`)** — HU antwortet noch nicht |
| `10:21:28.439` | **+2,999 s** | Phone→HU `WriteDataCO` | **4 B** | **2. `INIT`** auf dem festen **3,000-s-Retry-Timer** der MyBMW-App |
| `10:21:28.459` | **+20 ms** | HU→Phone `HS` | **16 B** | **`HANDSHAKE(v=5, iid=14, buf=0x4000)`** — echte HU-INIT-RTT = **20 ms**! |
| `10:21:31.441` | **+3,002 s** | Phone→HU `WriteDataCO` | **10 B** | nächster 3,0-s-App-Tick: **`SELECTPROTO(4)`** (`8 + 2`) |
| `10:21:31.446` | +5 ms | Phone→HU `WriteDataCO` | **56 B** | **`KNOCK(UUID, 1, 7)`** (`8 + 48`) |
| `10:21:31.458` | +12 ms | Phone→HU `WriteDataCO` | **8 B** | **`OPEN(5001, 5001)`** |
| `10:21:31.464` | +6 ms | Phone→HU `WriteDataCO` | **12 B** | erstes **`WATCHDOG DATA`** (`8 + 4`) |
| `10:21:31.471` | +7 ms | HU→Phone `DATAACK(10)` | **12 B** | ACK für `SELECTPROTO`; `.518`/`.523`: 2 weitere RX (ACK OPEN + WD-Echo) |
| `10:21:31.542–.549` | +71 ms | Phone→HU 3× `WriteDataCO` | **3 × 8 B** | **`OPEN(10, 4004)`**, **`OPEN(11, 4004)`**, **`OPEN(12, 4004)`** |
| `10:21:31.552–.554` | +3 ms | Phone→HU `6×666 + 12` | **4008 B** | `sas_certificate` Frag 1 auf `src=10` (`8 + 4000`) |
| `10:21:31.671` | +117 ms | Phone→HU `4×666 + 157` | **2821 B** | `sas_certificate` Frag 2 (`8 + 2813` → Cert-Call = **6813 B**) |
| `10:21:31.826/.835` | +155 ms | HU→Phone RX | (75 B) | `DATAACK` + **`_result_sas_certificate` (16-B-Challenge)** |
| `10:21:31.873` | **+38 ms** | Phone→HU `WriteDataCO` | **559 B** | **`sas_login` mit RSA-4096-Signatur**: `8 BCL + 8 deadbeef + 30 Etch + 512 RSA + 1 END = 559 B`! |
| `10:21:31.972` | **+99 ms** | HU→Phone RX | **52 B** | **`_result_sas_login` (`0xa6b0ffca`)** — HU verifiziert RSA-4096 in ~99 ms! |
| `10:21:31.978` | +6 ms | Phone→HU `WriteDataCO` | **52 B** | **`rhmi_getCapabilities("", 255)`** (`8 + 8 + 36 = 52 B`) |

**Erkenntnis:** Die ~3,012 s zwischen `HS` und `DATAACK(10)` sind **keine langsame Autorisierung**, sondern schlicht das **Schlaffenster des 3,000-s-INIT-Timers** in MyBMW (`25.440 → 28.439 → 31.441`). Sobald der Timer um `31.441` aufwacht, laufen **Bootstrap + PKCS7 + Challenge + RSA-4096-Login + Login-OK** komplett in **531 ms** durch!

---

## 3. Multi-Channel-Belegung (`src = 10..19`) und CDS-Katalog auf dem F20

Über denselben BCL-Tunnel (`SCN 6`, im Failover `SCN 10`) multiplexen MyBMW und AAIdrive mindestens **neun** Etch-Subkanäle zu `dest=4004`:

| `src` | Beobachtete Antworten der F20-HU | Rolle |
|------:|----------------------------------|-------|
| `10` | `_result_sas_login`, `_result_rhmi_getCapabilities` (`plen=5306`) | Primärer Discovery-/AM-Kanal |
| `11` | `cds_onPropertyChangedEvent` | zweiter Initial-Kanal (Lab: SmartThings/Cert 2) |
| `12` | `_result_cds_addPropertyChangedEventHandler` (2×), `cds_onPropertyChangedEvent` (34×) | Haupt-CDS-Subscription (`cdsbaseapp`) |
| `13` | `_result_cds_getPropertyAsync` (auch auf **SCN 10**), `cds_onPropertyChangedEvent` | CDS Einzelabfrage + Event |
| `14` | `_result_am_registerApp`, `_result_cds_addPropertyChangedEventHandler`, `cds_onPropertyChangedEvent` | App-Manager-Registrierung + CDS |
| `15` | `_result_sas_certificate` (16-B-Challenge) | eigene Sub-App-SAS-Session |
| `17` | `_result_am_addAppEventHandler`, `_result_rhmi_setData` (2×) | RHMI-/AM-App-Instanz |
| `18` | `_result_rhmi_setData` (3×) | RHMI-App-Instanz |
| `19` | `_result_rhmi_initialize`, `_result_rhmi_setProperty`, `_result_rhmi_setData` | RHMI-Widget-/UI-App-Instanz |

Aus `(str_len, 2-Byte-Präfix)` in den 37 `cds_onPropertyChangedEvent`-Headern gegen `CDSProperty.kt`:
- Eindeutig identifiziert: **`50: engine.RPMSpeed`** (7×), **`47: engine.info`** (2×), **`93: sensors.SOCBatteryHybrid = 255.00`** (1×, Invalid-Sentinel an einem 118d-Diesel → die HU exponiert das generische CDS-Gesamtschema).
- Nach Präfix+Länge eingegrenzt: `engine.status|torque` (22×), `engine.consumption|temperature` (20×), `driving.*` len 20/19 (17×), `navigation.*` len 26 (4×), `vehicle.type|time` (2×), `communication.currentCallInfo|controls.windowPassengerFront` (2×).

---

## 4. Klassische BT- & Radio-Parameter (OnePlus 12 ↔ F20 `e1:b5`)

1. **Controller-Identität:** LMP `0x06` (**BT 4.0**), Manufacturer `0x000D` (**Texas Instruments**), Subversion **`0x1B76`** (TI Automotive-Chip im ALPS-Modul). HU ist ACL-Master (Phone peripheral → kann Link-Supervision-Timeout nicht selbst setzen).
2. **Sniff Subrating aktiv:** Nach A2DP-Suspend wird **`SNIFF_SUBRATING (0x0811)`** mit **`max_latency = 0,75 s` (`0x04b0` Slots)** gesetzt — erklärt physikalisch das zweistufige BCL-Watchdog-RTT-Profil (`~150–165 ms` aktiv vs. `~240–360 ms` Sniff-Aufwachen).
3. **A2DP-Codec mit echtem Smartphone:** Obwohl die HU `seid=1` (SBC), `seid=2` (MP3) und `seid=3` (AAC) anbietet und das OnePlus Hardware-AAC-Offload besitzt, wählt der Phone-Stack **`seid=1` = SBC** (`mandatory codec preferred`, Bitpool `[2, 35]` low-latency, Delay Reporting `psc_mask=0x0102` aktiv, SCMS-T **nicht** erzwungen: `AudioSepHasContentProtection: not required`).
4. **AVRCP-SDP-Features der HU:** Controller `0x0105` (1.5), SDP-Feature-Maske **`0x004d`** → **Browsing = `true`**, **Cover Art = `false`**, **Absolute Volume = `false` (`abs_support: 0`)**. Das OnePlus publiziert AVRCP TG 1.6 inkl. BIP-OBEX-Server (`psm=0x1001`, `features=0x1d1`), ohne dass Steuerung/Metadaten an dieser F20-HU brechen.
5. **Vollständige HFP-Sequenz gegen echtes Phone (`083313`):** Nach `AT+BRSF=255` (`phone: 0x36f`), `AT+BAC=1,2` (**mSBC**), `CIND=?`/`CIND?`, `CMER=3,0,0,1` und `AT+CHLD=?` sendet die HU: `AT+CLIP=1`, **`AT+CGMI`** (Hersteller), `AT+CCWA=1`, `AT+CMEE=1`, **`AT+COPS=3,0`/`AT+COPS?`**, `AT+CLCC`, **`AT+NREC=0`** (schaltet Phone-EC/NR zugunsten des HU-DSP ab), **`AT+COPS=3,2`/`AT+COPS?`**, **`AT+CGMM`** (Modell), **`AT+CNUM`** (Rufnummer), danach **3,0-s-AT-Status-Poll**.

---

## 5. Zwei gefundene & behobene Bugs in `bcl_dummy_hu.py` / `bcl_etch_stub.py`

Warum lieferte `--sas-probe challenge` im Lab am 15.11. (`LAB_SAS_CHALLENGE_*`, `LAB_ETCH_REPLY_SRC12_*`) nie ein `sas_login` vom Telefon?

1. **Falsches BCL-Tupel:** `DummyHuSession` antwortete ohne Override mit `(src=4004, dest=phone_src)`. `BclMultiplexer` schlägt Verbindungen aber über das richtungsinvariante `Pair(src, dest)` nach → `(4004, 10)` wurde im Multiplexer verworfen.
2. **Request-Hash statt Reply-Hash:** `build_sas_challenge_payload` nutzte `_LAB_ETCH_HDR` mit `0x304ba8bb` (**Request** `sas_certificate`) statt **`0x9c6372b8` (`_result_sas_certificate`)** + `result=bytes[16]` + `_inReplyTo`. Als `--etch-reply-src 12` das Paket erstmals durch den Multiplexer ließ (`LAB_ETCH_REPLY_SRC12`), brach Etch den Kanal folgerichtig sofort mit **`CLOSE(12, 4004)`** ab.

**Fix (2026-11-16, 112/112 Host-Tests grün):**
- `HU_PROFILES["f20"]` spiegelt `phone_src` automatisch auf `(phone_src, 4004)` (`etch_reply_src=0`).
- `bcl_etch_stub.py` baut wire-exakte `_result_sas_certificate` (59 B Etch / 67 B Payload, inkl. echtem `_inReplyTo` aus dem `sas_certificate`-Request) und `_result_sas_login` (36 B Etch / 44 B Payload) und erkennt eingehendes `sas_login` (`0x7e002a4d`).

---

## 6. Nachtrag: Verbleibende Baseband-, PKI- und RHMI-Parameter aus `.btsnoop`, `BQR`, `LAB_DUMMY_ETCH_*_certs` und `IDriveConnectKit`

### 6.1 Klassisches Bluetooth / Baseband (aus `FIELD_A6` + `FIELD_B2` `.btsnoop` & OnePlus `BQR`)

| Parameter | Gemessener Wert | Quelle |
|-----------|-----------------|--------|
| **EIR PnP / Device ID (`0x10`)** | `VendorIDSource = 0x0002` (USB-IF), **`VendorID = 0x044E` (Alps Electric Co., Ltd.)**, **`ProductID = 0x3020`**, **`Version = 0xB39B`** | `FIELD_A6_HU_20261113T062824Z.btsnoop` EIR |
| **Page Scan** | `Page Scan Repetition Mode = R1 (1)` (≤ 1,28 s), Clock Offset `0x3264` | `FIELD_A6` EIR |
| **LMP Features Page 0** | **`ff fe 2d fe db ff 7b 87`** — EDR ACL 2/3 Mbit/s, 3/5-Slot EDR, eSCO EV3/4/5 + 2/3 Mbit/s, AFH Master+Slave cap+class, Sniff + Sniff Subrating, EIR, SSP, Enhanced Power Control; **Park State = OFF** | `FIELD_A6` & `FIELD_B2` HCI Event `0x0B` |
| **LMP Extended Page 1** | **`01 00 00 00 00 00 00 00`** — `SSP (Host) = ON`, **`LE Supported (Host) = OFF`** → HU-Host spricht **kein BLE**, obwohl der TI-Controller LE-Bits auf Page 0 hat | `FIELD_A6` & `FIELD_B2` HCI Event `0x23` |
| **Role Switch & Master-Zwang** | HU lehnt Role-Switch zum Phone mit **`HCI_ERR_ROLE_CHANGE_NOT_ALLOWED (0x21)`** ab (`FIELD_B2` + `102058`) → HU bleibt zwingend **ACL-Master** | `.btsnoop` Event `0x12` + `102058` |
| **Link Supervision Timeout (`LSTO`)** | **`8000` Slots = exakt `5,000 s`** (von der HU als Master gesetzt; Phone kann wegen Peripheral-Rolle nicht überschreiben) | `FIELD_A6` & `FIELD_B2` Event `0x38` + OnePlus `BQR mLsto: 8000` |
| **Tatsächlicher Power-Mode (Sniff)** | SSR-Parameter `max_latency = 0,75 s` werden konfiguriert, aber während offenem `BTA_ID_JV`-RFCOMM-Kanal meldet der Stack `BTM_block_sniff_mode_for` / `Unable to set link into sniff mode` → Link bleibt im **Active Mode (`mode=0`)** (`interval=798` im Log gehörte zur Smartwatch `b7:21`!) | `102058` & `174331` (`btm_pm.cc`) |
| **Auth & Encryption** | `Connection Complete (enc=0)` → `LSTO=5,0 s` → `Remote Features p0/p1` → `Auth Complete` → `Encryption Change (enc=1)` → **Schlüssellänge = `16 Byte (128 Bit)`** | `FIELD_A6` & `FIELD_B2` (`Read_Encryption_Key_Size`) |
| **AFH & Pakettypen im Fahrzeug** | **`mUnusedAfhChannelCount = 49`** (30 aktive von 79 Kanälen, 2,4-GHz-WLAN-Ausblendung), Pakete `2-DH1 / 3-DH1 / 3-DH3`, `TxPower = 4..14 dBm`, `RSSI = -48..-57 dBm` | OnePlus `BQR` (`083313` / `174331`) |

### 6.2 Vollständige SAS-Zertifikatskette & Signaturmechanismus (`src10..12_b0.pem` + `SecurityModuleManager.kt`)

Aus den im Lab mitgeschnittenen Original-PKCS7-Ketten des OnePlus (`LAB_DUMMY_ETCH_20261114T1550Z_certs/*.pem`) und `IDriveConnectKitAndroid`:

1. **Drei-Zertifikate-Struktur jedes `.p7b`-Bundles (`CertMangling.mergeBMWCert`):**
   - **CA-Zertifikat:** `CN=a4a_android-ca`, ausgestellt von **`CN=a4a_root-ca`** (**RSA-2048**).
   - **App-Permission-Zertifikat (`SAS.CertificateType=APP`, RSA-4096):** trägt die Rechte (`CDS=true&RHMI=true&…`) und die **SHA-256-Whitelist** `SAS.Digests.RHMIDescriptions`, `ImageDatabases`, `TextDatabases` (z. B. `src10`: `a4a_app_myBMW.perm___applicationmanager_…`, `src11`: `a4a_app_mobile___com_smartthings_android_00.00.03`, `src12`: `a4a_app_myBMW.perm___cdsbaseapp_…`). Dafür braucht die App **keinen** eigenen privaten Schlüssel!
   - **Gemeinsames Signing-Zertifikat (`SAS.CertificateType=APP_AUTH`, RSA-4096):** **`CN=a4a_app_BMWTouchCommand_Connection_00.00.10`**! Weil dieses Blatt `APP_AUTH` und RSA-4096 ist, gilt auf dem F20 zwingend die **XOR-Signaturvariante** (`challenge XOR MD5(02 00 00 00)`, danach `MD5withRSA` → **512 Byte Signatur** = `559 B` `sas_login`-Frame!).
2. **Wie modernes MyBMW (`de.bmw.connected.mobile20.*`) ohne Binder-Export signiert (`SecurityModuleManager.kt:69–100`):**
   - AAIdrive lädt per `context.createPackageContext("de.bmw.connected.mobile20.row", CONTEXT_IGNORE_SECURITY | CONTEXT_INCLUDE_CODE)` direkt die native JNI-Klasse `com.bmwgroup.connected.core.security.SecurityModule` (Fallback `AudioModule`) aus der installierten MyBMW-APK in den eigenen Prozess (`init("bmw")` → `createSecurityContext` → `getCertificates` → `signChallenge`).

### 6.3 Wichtige Korrektur zu RHMI (`rhmi_getCapabilities` ≠ Widget-Baum!)

- **`rhmi_getCapabilities("", 255)` enthält KEINE Screens, Widgets, Property-IDs oder Events!** Es liefert eine flache `Map<String, String>` mit **149 System-Flags** (`nfields=149` in `174331` @ `17:44:06.777`: `hmi.type`, `vehicle.type`, `a4axl`, `tts`, `navi`, `iva_ENT_USB_COVER_ART_IPOD`, `_ENT_MTP_OFF`, …).
- **Das RHMI-Objektmodell muss NICHT aus Logs reverse-engineert werden** — es liegt vollständig in `IDriveConnectKit` vor:
  - **26 `RHMIProperty.PropertyId`-Werte (`RHMIProperty.kt`):** `ENABLED=1`, `SELECTABLE=2`, `VISIBLE=3`, `VALID=4`, `TOOLBARHMISTATE_PAGING=5`, `LIST_COLUMNWIDTH=6`, `LIST_HASIDCOLUMN=7`, `LABEL_WAITINGANIMATION=8`, `WIDTH=9`, `HEIGHT=10`, `ALIGNMENT=17`, `OFFSET_X=18`, `OFFSET_Y=19`, `POSITION_X=20`, `POSITION_Y=21`, `BOOKMARKABLE=22`, `SPEAKABLE=23`, `HMISTATE_TABLETYPE=24`, `CURSOR_WIDTH=25`, `HMISTATE_TABLELAYOUT=26`, `TOOLBARHMISTATE_PAGING_LIMITED=35`, `SPEEDLOCK=36`, `CUTTYPE=37`, `CHECKED=53`, `UUID=55`, `MODAL=56`.
  - **12 Komponenten (`RHMIComponent.kt`):** `Separator`, `Image`, `Label`, `List`, `EntryButton`, `InstrumentCluster`, `ToolbarButton`, `Button`, `Checkbox`, `Gauge`, `Input`, `CalendarDay`.
  - **Exakter App-Lifecycle (`ID5StatusbarApp.kt` / `MusicApp.kt`):**
    `OPEN(src, 4004)` → `sas_certificate(merged_p7b)` → `sas_login(rsa4096_sig)` → `rhmi_create` → `rhmi_setResource(DESCRIPTION | IMAGEDB | WIDGETDB [| TEXTDB])` *(SHA-256 muss zum `APP`-Zertifikat passen!)* → `rhmi_initialize` → `rhmi_addActionEventHandler` + `rhmi_addHmiEventHandler` → laufend `rhmi_setData(handle, modelId, val)` / `rhmi_setProperty(handle, compId, propId, {0: val})` / `rhmi_triggerEvent`.
- **Was die Oppo-Textlogs prinzipiell NICHT enthalten können:** die Phone→HU-Payloads auf `src=17/18/19` (`rhmi_setData`/`setProperty`/`setResource`), weil `PORT_WriteDataCO` nur Längen loggt und HU→Phone darauf nur mit 44-B-Void-`_result_*` antwortet. Wer die vollen 149 Capability-Einträge des F20 lesen will, schneidet sie einmalig über das **B3-RFCOMM-Relay** mit.

### 6.4 USB-AOA- & Cross-Plane-Aufklärung für `hu-probe` (aus `logcat.crash`, `MusicAppMode.kt`, `UsbStatus.kt`, `CDSProperty.kt`)

1. **Auflösung des 30.10.-Lab-Rätsels (`AAIdrive grün`, aber `0 B` Bulk / Timeout):**
   - `UsbStatus.kt:64` in AAIdrive prüft nur `manufacturer.contains("BMW")` für die UI, öffnet aber **niemals** `/dev/usb_accessory`.
   - Den Accessory-FD öffnet allein MyBMWs `com.bmwgroup.carconnection.usb.UsbAccessoryLaunchActivity` bei exaktem Match auf **`mAccessoryStrings = ["BMW Group", "BMW"|"MINI", " ", "1.0", "market://details?id=com.bmwgroup.connected.*", "VIN"]`** + `bRequest=58` (`audio_source`) (`logcat.crash` Z. 34789–40412 → `127.0.0.1:4004`, `instanceId=12`).
   - Im Lab am 30.10. wurde `"BMW"` / `"NBT Evo"` gesendet → AAIdrive grün, MyBMW blieb aus, Bulk blieb ohne Reader.
2. **Warum `aoa_phone_like` (`04E8:6860`) am F20 sofort abgelehnt wurde:** `AoaObserveGadget.cpp` präsentierte Vendor-only `0xFF` ohne MTP-Interface (`0x06`), obwohl die HU vor `51` ein echtes MTP-Gerät erwartet (`_ENT_MTP_OFF = false`).
3. **Elektronisches Orakel für `HU-PROBE-GATE-01` (USB-MSC Play-Intent vs. Eager-Read):** Über den aktiven BT-Connected-Kanal liefern **`CDS 54: entertainment.multimedia`** (`BimmerScrobbler`) und **`636–642: entertainment.md.*`** (`statusPlayback`, `statusMetaInfo`, `coverArt`) live den echten Abspielzustand der HU parallel zu den `READ10`-Captures auf USB.


