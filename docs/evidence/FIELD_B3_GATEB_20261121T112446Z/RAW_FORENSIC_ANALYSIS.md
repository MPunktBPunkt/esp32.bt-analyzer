# RAW Forensic Analysis — FIELD_B3_GATEB_20261121T112446Z

**claim_level:** mixed (see epistemic tags per finding)
**raw_primary:** `raw/phone_to_hu.bin`, `raw/hu_to_phone.bin`
**artifacts:** `forensic/` (this analysis; originals untouched)
**generated_by:** `forensic/run_raw_forensic.py` + crypto pairing follow-up

---

## 1. Executive Summary

Byte-genaue Reassembly der erfolgreichen OnePlus/AAIdrive → B3-Relay → F20-Session zeigt:

1. **Transport:** BCL (BE u16 cmd/src/dest/len) trägt Apache-Etch-`DEADBEEF` envelopes; Phone fragmentiert Etch bei 4000-B-BCL-DATA, HU sendet bis 5306 B in einem Frame. **FACT — RAW**
2. **Coverage:** `hu_to_phone.bin` 100 % BCL-dekodiert; `phone_to_hu.bin` ≈99.76 % mit bekannten Desync-Gaps (Etch-Restfragment ohne BCL-Header + Session-2-Rauschen). **FACT — DECODED**
3. **APP_AUTH:** 12× `sas_certificate` (PKCS#7 PEM), 19× Challenges, 18× `sas_login` (512-B-Signaturen), 18× HU `_result_sas_login` Accept. **FACT — RAW**
4. **Crypto (NEU geschlossen):** Alle 18 HU-akzeptierten Login-Signaturen verifizieren gegen das Wire-Leaf-Zertifikat `a4a_app_BMWTouchCommand_Connection_00.00.10` (RSA-4096) mit
   `Digest = MD5(challenge XOR MD5(0x02000000))` und PKCS#1 v1.5 DigestInfo-MD5. **FACT — CRYPTO VERIFIED**
5. **Post-Auth:** RHMI (Handle **23** dominant), AM (5 Apps, kein Spotify-AM), CDS (u. a. `entertainment.multimedia`), AV (`me.hufman.androidautoidrive.music` → connectionGranted → PLAY), Media-ASCII (Halestorm/Spotify) + Cover-JPEG/PNG. **FACT — FIELD / DECODED**
6. **Dissector-Gap:** `b3.jsonl` enthält **kein** dekodiertes `sas_certificate`; Challenges teils nur in `bytes.hex_head`; viele HU-Results/`rhmi_setData` fehlen gegenüber Raw-Scan. **FACT — DECODED**

Zentrale Antwort: Der APP_AUTH-Handshake ist aus dem Feld-Capture **vollständig rekonstruierbar und kryptographisch verifiziert**. Die Wire-Signaturen stammen vom TouchCommand-Leaf-Pubkey; der Signierpfad in `libaudio.so` (`signChallenge` / `EVP_SignFinal` / `CertificateType`) bleibt der passende Codepfad — der **private** Key liegt nicht im Capture. **FACT — CRYPTO VERIFIED** + **INFERENCE** (libaudio path)

---

## 2. Untersuchungsgegenstand

| Item | Wert |
|------|------|
| Session | FIELD_B3_GATEB_20261121T112446Z |
| Topology | OnePlus/AAIdrive → B3 Profile-Relay → BMW F20 NBT Evo |
| Raw Phone→HU | `raw/phone_to_hu.bin` |
| Raw HU→Phone | `raw/hu_to_phone.bin` |
| Korrelation (sekundär) | `b3.jsonl`, `EVAL.md`, `libaudio.so` |
| Operator | Spotify-Menü + Cover auf HU (bereits bekannt / FIELD) |

Primärquelle = Raw-Bytes. Bekanntes aus EVAL nur als Korrelation markiert.

---

## 3. Hashes und Integrität der Raw-Dateien

### `phone_to_hu`
- size: **417174** bytes
- SHA-256: `86272e98c3d8d6f123159c48c557b6e47b4be9ff6c39735995eb32db3a5c158c`
- SHA-1: `3a64ccba9bfafe02f3d66998ab71c55a9e4c5dae`
- MD5: `1c07a16855c0728860063296fec5e8ac`
- offset 0: `deadbeefdead010000002c010130653962393063342d636265312d343734322d`
- end (last 32 B @ 417173): `65312d343734322d383238332d64333637653961353636313900deadbeefbeef`

### `hu_to_phone`
- size: **110651** bytes
- SHA-256: `0ca169d1abaebd69a6a34e5c04d9ed3a7b01ba775c94752569c455de6d37ab2d`
- SHA-1: `297db51d29dcc2ad02cce922b0343176b037d574`
- MD5: `1fbf97ca5cc7ca26877e0991ec468043`
- offset 0: `00040000000000080005000e0000400000060000000000040000000a00060000`
- end (last 32 B @ 110650): `138900041337133700060000000000040000000c000213891389000413371337`

**FACT — RAW** — Dateien unverändert gelesen; Schreibzugriffe nur unter `forensic/`.

---

## 4. Transport-/Frame-Grammatik

### 4.1 Gemeinsame BCL-Grammatik (beide Richtungen)

```
BCL_FRAME :=
  u16BE cmd | u16BE src | u16BE dest | u16BE len | payload[len]

cmd ∈ {1=OPEN,2=DATA,3=CLOSE,4=HANDSHAKE,5=SELECTPROTO,6=DATAACK,
        7=ACK,8=KNOCK,9=LAUNCH,10=HANGUP,11=BROADCAST,12=REGISTER}

INIT_MAGIC := 12 34 56 78   # session delimiter (phone only in this capture)
```

**FACT — DECODED** (konsistent mit bestehendem `bcl_framer.py`; hier aus Raw unabhängig bestätigt).

### 4.2 Etch-Envelope in BCL DATA

```
ETCH := DE AD BE EF | u32BE(body_len) | body
body := 03 | 86 <type_hash_u32BE> | ... Apache Etch BinaryTaggedData v3
```

- Phone: große Etch-Bodies werden über **mehrere** BCL DATA (typ. `len=4000`) fragmentiert; nur das erste Fragment beginnt mit `DEADBEEF`. **FACT — RAW**
- HU: Etch oft in **einem** BCL DATA (`len=5306`, `etch_elen=5298`) — erklärt frühere Parser-Fails bei `MAX_PAYLOAD=4000`. **FACT — RAW**
- Watchdog: DATA src=dest=5001 payload `13 37 13 37`. **FACT — RAW**

### 4.3 Phone-Preamble (56 B vor INIT)

| Feld | Offset | Bytes |
|------|--------|-------|
| Knock/Etch-artig | 0x00000000 | `deadbeef dead 0100 00002c01 ...` + UUID `0e9b90c4-cbe1-4742-8283-d367e9a56619` + `deadbeefbeef` |
| INIT | 0x00000038 | `12345678` |

**FACT — RAW** / **INFERENCE:** 56-B-Knock-Envelope (bereits in Lab-Doku bekannt) vor BCL-INIT.

### 4.4 Coverage-Matrix

| Datei | decoded BCL/INIT | preamble | desync gaps | unparsed tail | coverage |
|-------|------------------|----------|-------------|---------------|----------|
| phone_to_hu | 404599+4 | 56 | 12515 | 1008 | 99.76% |
| hu_to_phone | 110651 | 0 | 0 | 0 | 100.00% |

Phone-Desync @ `0x00052a8b`: Etch `elen=20143` nach 5×4000-B-Fragmenten fehlen 151 B Rest **ohne** BCL-Header im Capture; danach Sliding-Resync. Zusätzliche Gaps/Truncations in Session-Tail. **FACT — RAW** / **HYPOTHESIS:** Relay-/RFCOMM-Capture verlor Header-Bytes des letzten Fragments (kein Protokollwechsel).

---

## 5. Vollständige Nachrichtenchronologie

Echte Millisekunden-Zeitstempel sind in den `.bin`-Dateien **nicht** enthalten → Sequenznummern / File-Offsets. Externe Zeiten nur aus `b3.jsonl` als Korrelation.

### 5.1 Bootstrap (Session 1, Phone offsets)

| # | Dir | Offset | Event |
|---|-----|--------|-------|
| 1 | P→H | 0x00000000 | 56-B Knock preamble |
| 2 | P→H | 0x00000038 | INIT |
| 3 | P→H | after INIT | SELECTPROTO / KNOCK / OPEN 5001+4004 |
| 4 | H→P | 0x00000000 | HANDSHAKE + DATAACKs |
| 5 | P→H | 0x000000a2 | `sas_certificate` mid=1795260913532 |
| 6 | H→P | 0x0000006c | `_result_sas_certificate` challenge=`8f873bb740471e52f36aa26093f580da` |
| 7 | P→H | 0x000018a0 | `sas_login` 512-B sig |
| 8 | H→P | 0x000000c3 | `_result_sas_login` ACCEPT (irt=login mid) |
| 9 | P→H | … | weitere Cert/Login-Kanäle (parallel OPEN 4004 src 10..19) |
| 10 | P→H | ~0x14xxx | `am_registerApp` ×5, `av_create`, RHMI init/setData |
| 11 | P→H | 0x0001B8C9 | ASCII `Halestorm, I Prevail` in RHMI/media payload |
| 12 | P→H | 0x00031B3E | ASCII `Spotify` |
| 13 | P→H | 0x0005548D | 2. INIT (Reconnect/Noise-Session) |

Vollständige Indizes: `forensic/RAW_FRAME_INDEX.jsonl`, `CHRONO_PHONE.json`, `CHRONO_HU.json`, `ETCH_TIMELINE.json`.

---

## 6. Phone→HU

- BCL cmds: `{'SELECTPROTO': 1, 'KNOCK': 1, 'OPEN': 21, 'DATA': 442, 'CLOSE': 2}`
- Frame kinds: `{'INIT': 1, 'BCL': 467, 'ETCH_REASSEMBLED': 343, 'ETCH_PARTIAL': 2}`
- DATA überwiegend `dest=4004` (Etch), `src∈{10..19}` plus WD `5001`.
- Zwei INIT-Sessions im gleichen File (Concatenation mehrerer Relay-Läufe). **FACT — RAW**

---

## 7. HU→Phone

- BCL cmds: `{'HANDSHAKE': 2, 'DATAACK': 461, 'DATA': 598}`
- Kein INIT im HU-Raw (Relay startete HU-Seite nach Phone-INIT / Capture-Schnitt). **FACT — RAW**
- `DATAACK` korreliert 1:1 mit Phone-DATA; große DATA tragen RHMI/CDS Results + Challenges.

---

## 8. BCL

Siehe Frame-Index. Auffällig:

| Phänomen | Evidence | Class |
|----------|----------|-------|
| HU DATA len=5306 | mehrfach, etch_elen=5298 | FACT — RAW |
| Phone DATA len=4000 Fragmente | 63+ in Session 1 | FACT — RAW |
| OPEN/CLOSE churn src=11 | Session 2 | FACT — RAW |
| REGISTER/BROADCAST | nicht beobachtet | FACT — RAW |

---

## 9. Etch

Raw-Scan (DEADBEEF-Iterator, vollständige Envelopes): **siehe METHOD_COMPARE** Methodenklassen; Timeline in `ETCH_TIMELINE.json`.

Häufigste (Reassembler, inkl. Duplikatrisiko Inline+Reassembled):

- `_result_rhmi_setData`: 349
- `cds_onPropertyChangedEvent`: 242
- `rhmi_setData`: 202
- `cds_addPropertyChangedEventHandler`: 98
- `cds_getPropertyAsync`: 96
- `_result_cds_getPropertyAsync`: 93
- `_result_rhmi_setProperty`: 86
- `_result_cds_addPropertyChangedEventHandler`: 75
- `_result_sas_certificate`: 38
- `sas_login`: 36
- `_result_sas_login`: 36
- `rhmi_setProperty`: 30
- `rhmi_checkResource`: 22
- `_result_rhmi_checkResource`: 22
- `rhmi_onHmiEvent`: 17
- `rhmi_create`: 16
- `_result_rhmi_create`: 16
- `rhmi_getCapabilities`: 14
- `ver_getVersion`: 14
- `_result_rhmi_getCapabilities`: 14
- `_result_ver_getVersion`: 14
- `sas_certificate`: 12
- `am_create`: 12
- `_result_am_create`: 12
- `cds_setPropertyAsync`: 10

DEADBEEF-Scan ohne Duplikate (sauberer): siehe `METHOD_COMPARE.json` / Abschnitt Cross-Corr.

Keine unbekannten Type-Hashes (`0x…`) im erfolgreichen Decode — alle Methoden mappten auf `HASH_REGISTRY`. **FACT — DECODED**

---

## 10. SAS / APP_AUTH

| Schritt | Count (unique off) |
|---------|-------------------|
| sas_certificate | 12 |
| _result_sas_certificate (challenge) | 19 |
| sas_login | 18 |
| _result_sas_login | 18 |

Alle 18 Logins haben korrespondierendes HU-Accept (`inReplyTo` = login `_messageId`). **FACT — DECODED**

Multi-Channel: parallele BCL-`src` auf dest 4004 → mehrere unabhängige Cert/Challenge/Login-Sequenzen (nicht nur eine). **FACT — RAW** / **INFERENCE:** ein SecurityContext/Service-Instanz pro OPEN-Kanal.

---

## 11. Certificate

| Artifact | Wert |
|----------|------|
| Wire blob | `forensic/SAS_CERTIFICATE.p7b` (PKCS#7 PEM, 8001 B) |
| SHA-256 (p7b file) | `b4364f34ebc4bf282eeb2c8f97723011357d56db5d22477c47496e545ef28e49` |
| Bundle CNs | spotify APP, android-ca, **BMWTouchCommand APP_AUTH** |
| cert_types | `APP`, `APP_AUTH` (`uses_app_auth_xor=true`) |
| Leaf | `CN=a4a_app_BMWTouchCommand_Connection_00.00.10` serial=`0x0AA9` |
| Leaf DER | `forensic/SAS_CERTIFICATE.der` SHA-256 `991517428f7f5213897a9538e5deef7666ab3bc246a19b3a4289b04158626877` |
| Leaf FP SHA-256 | `99:15:17:42:8F:7F:52:13:89:7A:95:38:E5:DE:EF:76:66:AB:3B:C2:46:A1:9B:3A:42:89:B0:41:58:62:68:77` |
| Public key | RSA-**4096**, Exponent 65537 (openssl text) |
| Validity | Not Before 2014-10-31 / Not After 2015-07-30 (SHA1-signed X.509 — BMW legacy) |
| RHMI whitelist digests | in PKCS7 permissions (u. a. `8e1d0b21…` Music DESCRIPTION) |

**FACT — RAW / DECODED.** Erste vollständige Cert-Reassembly aus diesem Capture (EVAL: Decode fehlte).

First cert TX:
- PHONE→HU file offset **0x000000a2**, method `sas_certificate`, `_messageId=1795260913532`

---

## 12. Challenge

**19** Challenges (16 B) in HU→Phone `_result_sas_certificate`:

| HU offset | challenge_hex | inReplyTo (cert mid) |
|----------|---------------|----------------------|
| 0x0000006c | `8f873bb740471e52f36aa26093f580da` | 1795260913532 |
| 0x00002b95 | `cee0993409fcc7424cb956f9a5ff2134` | 1795260916880 |
| 0x00005d16 | `865cebc6a40a189774baf807af78e17e` | 1795260920019 |
| 0x0000740c | `587bb2617779a3c333fabcd8f9de0c80` | 1795260921027 |
| 0x0000c1f3 | `3af846de025f7676196e7ec9e65f473e` | 1795260933149 |
| 0x0000c2b6 | `daf99f51724314a53dd17d36af8ab6e9` | 1795260933149 |
| 0x0000c325 | `82fdc8845c3efa75ac783e92d885d0b2` | 1795260933146 |
| 0x0000c416 | `7e6f04f1b21896efe91426989edc8220` | 1795260933180 |
| 0x0000c563 | `d94aa435889eab3417e9c6ef6f96a1ed` | 1795260933198 |
| 0x0000c7c3 | `05a5deb8be75a7a789cd4027aac24783` | 1795260933431 |
| 0x0001554e | `0cebb9948964c8a04d8e8fbc2431aa29` | 1795261031597 |
| 0x00016afb | `d688e194fd893c86567cad003ef4844a` | 1795261033414 |
| 0x00016ba6 | `df3dde69a1a609ee3499ab58ca5581a0` | 1795261034106 |
| 0x00016bfd | `dd6335dbec716142ed0f432b03c775e3` | 1795261034107 |
| 0x00016c6c | `04534ca5f955932dee3e85b893065971` | 1795261034103 |
| 0x00016ccf | `698e4c55ffad98ecbcdb17c0a28ca3a6` | 1795261034107 |
| 0x00016d3e | `dfef4bd844de05331d8aebb0904421fa` | 1795261034121 |
| 0x0001826f | `d26d4fd11be7bdd7c2d49764603a0a3f` | 1795261034124 |
| 0x0001afc8 | `2955176e341ca151a68c0137d12331a3` | 1795261040076 |

Bereits bekannt (EVAL): `8f873bb7…`, `0cebb994…`. **Neu:** 17 weitere eindeutige Challenges im selben Capture. **FACT — RAW**

---

## 13. Login / Signature

**18** `sas_login`, jeweils `login_sig_len=512`. Signaturen unter `forensic/SAS_SIGNATURES/`.

| Phone offset | mid | sig SHA-256 (head) |
|--------------|-----|--------------------|
| 0x000018a0 | 1795260913569 | `732e655d980394ec97a7ddcbc308f25b…` |
| 0x00003640 | 1795260916917 | `1c0c5c8635d5237f9ed6ca0433d20cf8…` |
| 0x000056f6 | 1795260920056 | `05f42fd81e3b363a50fae4998a2ccc39…` |
| 0x0000745c | 1795260921064 | `61fddc2ea03b18949b643715b5118ae1…` |
| 0x000136e5 | 1795260933186 | `b1b2fa447dee37285409d566c5710692…` |
| 0x00013914 | 1795260933186 | `cd4955f5ef7cda90b943600f39383b2c…` |
| 0x00013b69 | 1795260933183 | `d673c6bab565196d7f2129fc1ab14c16…` |
| 0x00013d98 | 1795260933217 | `46eacd14546dcc2fb889c7b9dafb1f3c…` |
| 0x00013fd3 | 1795260933235 | `de94c7fc8d4592807de845a88b1b3f2e…` |
| 0x00014418 | 1795260933468 | `9fd39074e6f33f369bf9a73aabe3a9c1…` |
| 0x00056cf5 | 1795261031634 | `9e9b4b89876982c4e0ba2dcd7270972c…` |
| 0x00062cde | 1795261033451 | `c9aa6be7e0826f37670c9ba8bf718505…` |
| 0x00062f19 | 1795261034143 | `b5e453003ed6d7b1b1afe08ca3b7416a…` |
| 0x00063148 | 1795261034144 | `1b7cae6c7a1f61aba3832b3ea834db7e…` |
| 0x00063377 | 1795261034140 | `25f8314d38ba0246fc428bad515bca36…` |
| 0x000635a6 | 1795261034144 | `5b7e13487e1dcb75848a899a4d946307…` |
| 0x000637d5 | 1795261034158 | `0d2c34ee363f8e8fcf94f99e50475ea2…` |
| 0x00063b8e | 1795261034161 | `05eed0de5cc5c78f5ae1680e1026fa6f…` |

**FACT — RAW:** unterschiedliche Challenges → unterschiedliche Signaturen (18 unique sig hashes). Gleiche Challenge kommt nicht zweimal mit anderer Sig vor. **FACT — CRYPTO VERIFIED** (Determinismus PKCS#1 v1.5 + MD5).

---

## 14. Kryptographische Verifikation

### Formel (Wire + libaudio-Theorie)

```
Pad16    = MD5(02 00 00 00)          # CertificateType APP_AUTH
X        = Challenge16 XOR Pad16
Digest16 = MD5(X)
Sig512   = RSA-4096-PKCS#1-v1.5-Sign(DigestInfo-MD5 || Digest16)
Verify   = RSA_public_leaf(TouchCommand)
```

**Ergebnis:** `18 / 18` HU-akzeptierte Logins → **VALID** (`rsa_verify_ok` ∧ `digest_match`).

Signer (alle VALID):
`CN=a4a_app_BMWTouchCommand_Connection_00.00.10 | serial=0AA9`

Details: `forensic/SAS_CRYPTO_VERIFY.json`.

| Classification | |
|----------------|--|
| RSA-Verify PASS für Gate-B-Challenge `8f873bb7…` | **FACT — CRYPTO VERIFIED** (NEU gegenüber EVAL „RSA-VERIFY pending“) |
| Pad `0x02000000` | bestätigt gegen **alle** 18 Paare |
| Private Key im Capture | **nicht** vorhanden (nur Public) — Security-Regel eingehalten |

---

## 15. RHMI

Handle-Histogram (Raw-Scan): `{21: 12, 22: 33, 23: 180, 24: 34, 25: 26, -1: 3, 255: 4}`

- Handle **23** dominiert (`rhmi_setData` / Properties) — korreliert mit bekannter Music-App-Zuordnung. **FACT — DECODED** + **bereits bekannt (STRONG)**
- `rhmi_checkResource` vorhanden; `rhmi_setResource` im Raw-Scan **nicht** gesehen (Whitelist-Hit). **FACT — DECODED** / bereits bekannt
- Unmittelbar vor sichtbarem Spotify-ASCII (`0x00031B3E`): intensive `rhmi_setData`/`setProperty` mit Track-Metadaten und Cover. **FACT — RAW**

Events: `forensic/RHMI_EVENTS.json`.

---

## 16. AM

Fünf `am_registerApp` (handle=1), **kein** Spotify als AM-App:

- off 0x00014bdc: `appId=androidautoidrive.assistant.com.google.android.googlequicksearchbox` name='Google'
- off 0x00015699: `appId=io.bimmergestalt.idriveconnectaddons.screenmirror` name='Screen Mirroring'
- off 0x00015c7b: `appId=androidautoidrive.assistant.com.amazon.dee.app` name='Amazon Alexa'
- off 0x00019342: `appId=androidautoidrive.com.android.bluetooth` name='Bluetooth'
- off 0x0001a173: `appId=androidautoidrive.com.google.android.youtube` name='YouTube'

**FACT — DECODED.** Bestätigt bekannte Aussage „Spotify ≠ AM“.

---

## 17. CDS

Top Properties (Raw-Scan counts):

- `hmi.graphicalContext`: 23
- `entertainment.multimedia`: 12
- `vehicle.units`: 10
- `driving.odometer`: 10
- `sensors.fuel`: 10
- `vehicle.language`: 10
- `sensors.SOCBatteryHybrid`: 10
- `navigation.currentPositionDetailedInfo`: 10
- `engine.info`: 10
- `driving.drivingStyle`: 10
- `api.ipaThirdParty`: 10
- `vehicle.VIN`: 10
- `vehicle.time`: 8
- `sensors.battery`: 6
- `vehicle.type`: 5
- `navigation.infoToNextDestination`: 5
- `navigation.finalDestinationDetailedInfo`: 5
- `controls.windowDriverFront`: 5
- `communication.lastCallInfo`: 5
- `sensors.temperatureExterior`: 5
- `controls.windowPassengerFront`: 5
- `vehicle.country`: 5
- `driving.averageSpeed`: 5
- `navigation.GPSExtendedInfo`: 5
- `controls.windowDriverRear`: 5

Neu/hervorhebenswert gegenüber Minimal-Listen: `entertainment.multimedia`, `api.ipaThirdParty`, `cds.apiRegistry`, Navigation-/Window-Properties. **FACT — DECODED**

Voll: `forensic/CDS_PROPERTY_COUNTS.json`.

---

## 18. AV

| Off | Dir | Method | Params |
|-----|-----|--------|--------|
| 0x0001912c | phone_to_hu | `av_create` | `{"_messageId": 1795260936029, "instanceID": 14, "id": "me.hufman.androidautoidrive.music"}` |
| 0x00020bba | phone_to_hu | `av_requestConnection` | `{"connectionType": "EtchStruct(type_name='AVConnectionType', fields={'AV_CONNECTION_TYPE_ENTERTAINMENT': True}, type_hash=2024883215)", "handle": 1, "_messageId` |
| 0x000315a6 | phone_to_hu | `av_playerStateChanged` | `{"connectionType": "EtchStruct(type_name='AVConnectionType', fields={'AV_CONNECTION_TYPE_ENTERTAINMENT': True}, type_hash=2024883215)", "handle": 1, "_messageId` |
| 0x00010be7 | hu_to_phone | `_result_av_create` | `{"result": 1, "_inReplyTo": 1795260936029, "_messageId": 1795260388672429}` |
| 0x000123fd | hu_to_phone | `_result_av_requestConnection` | `{"_inReplyTo": 1795260937768, "_messageId": 1795260388672511}` |
| 0x00012528 | hu_to_phone | `av_requestPlayerState` | `{"connectionType": "EtchStruct(type_name='AVConnectionType', fields={'AV_CONNECTION_TYPE_ENTERTAINMENT': True}, type_hash=2024883215)", "_messageId": 1795260388` |
| 0x000127bd | hu_to_phone | `av_connectionGranted` | `{"connectionType": "EtchStruct(type_name='AVConnectionType', fields={'AV_CONNECTION_TYPE_ENTERTAINMENT': True}, type_hash=2024883215)", "_messageId": 1795260388` |
| 0x00012b93 | hu_to_phone | `_result_av_playerStateChanged` | `{"_inReplyTo": 1795260937953, "_messageId": 1795260388672530}` |

**FACT — DECODED:** Music-Instance `me.hufman.androidautoidrive.music` → handle 1 → `AV_CONNECTION_TYPE_ENTERTAINMENT` → `av_connectionGranted` → `AV_PLAYERSTATE_PLAY`.

---

## 19. Media / Spotify

| String | phone_to_hu offsets (first) |
|--------|------------------------------|
| Halestorm | 0x0001B8C9, … |
| I Prevail | 0x0001B8D4 |
| can u see me in the dark? | 0x0001B918, … |
| Zufallswiedergabe… | 0x0001AA64, … |
| Spotify | 0x00031B3E, 0x00032010 |
| me.hufman.androidautoidrive.music | 0x000146BE, … |

Transportweg Media: **RHMI setData/setProperty auf Handle 23** (+ AV player state), nicht AM. **FACT — RAW** / **INFERENCE** (Architektur)

---

## 20. Cover Art

Extrahiert: **10** Unique Images → `forensic/EXTRACTED_MEDIA/`

| Offset | Format | Len | SHA-256 | Kontext |
|--------|--------|-----|---------|---------|
| 0x00014c70 | png | 1971 | `3a3338d9f145ee89…` | am_registerApp |
| 0x00015725 | png | 723 | `c34ace270a1082cb…` | am_registerApp |
| 0x00015d00 | png | 1895 | `a1822c1c05717b5d…` | am_registerApp |
| 0x000193bd | png | 2824 | `c0c624d25e21823f…` | am_registerApp |
| 0x0001a1f1 | png | 735 | `4df5b3262cf7645f…` | am_registerApp |
| 0x0001af4f | png | 422 | `e3f49ee034e8e1a4…` | rhmi_setProperty |
| 0x0001b152 | png | 864 | `1f624d71d2f42842…` | rhmi_setData |
| 0x000544ce | png | 354 | `6ed93a6cfd3e1d75…` | rhmi_setData |
| 0x0001be8b | jpg | 18442 | `8aa23b8cc83757dd…` | rhmi_setData |
| 0x00032000 | png | 1555 | `650e67eafb6d7d68…` | rhmi_setData |

Größtes Cover: JPEG 18442 B @ `0x0001BE8B` in `rhmi_setData`. Zusätzlich PNG-Icons in `am_registerApp`. **FACT — RAW**

Hinweis: Ein weiteres JPEG beginnt innerhalb des fragmentierten Etch @ `0x0004DC43` (jpeg @ +64 im Partial); Desync schnitt das Frame — Partial in Gap. **FACT — RAW**

---

## 21. Strings

Keyword-Hits (Counts): `{'BMW': 12, 'Spotify': 2, 'music': 19, 'media': 35, 'SAS': 2, 'AUTH': 4, 'Connected': 1, 'CDS': 14, 'Halestorm': 9, 'Prevail': 1, 'androidautoidrive': 40, 'RSA': 10, 'iva_': 1230, 'a4a_': 10}`

Voll: `forensic/STRING_HITS.json`. UTF-16LE-Scan mitgelaufen; dominante Treffer ASCII/UTF-8 in Etch-String-Feldern.

---

## 22. Unbekannte Binärdaten

| Region | Off | Len | Klassifikation |
|--------|-----|-----|----------------|
| Phone preamble | 0x0 | 56 | Knock envelope (bekannt) |
| Desync gap | 0x52A8B | 5813 | Etch-Rest + Media-ASCII/JPEG/PNG ohne BCL-Sync |
| Unparsed tail | 0x65A66 | 1008 | Session-Ende / Knock-UUID Echo |
| Etch partials | diverse | 4000 | abgeschnittene grosse setData |

Kein Private-Key-Material. RSA-Blöcke = öffentliche Signaturen (512 B). **FACT — RAW**

---

## 23. Unbekannte Nachrichten

Siehe `forensic/UNKNOWN_FRAMES.md`. Keine neuen Etch-Methodennamen außerhalb der BMWRemoting-Registry im erfolgreichen Decode.

Markant „einmalig vor Spotify“: `av_playerStateChanged(PLAY)` @ phone `0x000315A6` kurz vor Spotify-ASCII. **FACT — DECODED**

---

## 24. Cross-Correlation mit b3.jsonl

| Thema | Raw | b3.jsonl | Bewertung |
|-------|-----|----------|-----------|
| sas_certificate decode | 12 | **0** (method) | Dissector/Log-Gap — Cert nur im Raw |
| Challenges | 19 | ~4 `_result_sas_certificate` + bytes hex_head | unterdekodiert |
| sas_login | 18 | 18 | teilweise |
| rhmi_setData | ~192 (scan) | 105 | Fragmentierung → decode_error 93× |
| etch_decode_error | — | 93 | Raw-Reassembly behebt viele |
| Gate-B challenge `8f873bb7…` | HU off 0x6C | in `bytes.hex_head` | korreliert |

**FACT — DECODED:** Der aktuelle B3-Dissector ist für Gate-B-Beweis nützlich, aber **nicht vollständig** — Cert-TX und viele HU-Results/Fragment-Etch fehlen.

---

## 25. Cross-Correlation mit libaudio.so

| Needle | In libaudio.so? | Offset |
|--------|-----------------|--------|
| `pad_u32_be` | True | 210 |
| `APP_AUTH` | False | None |
| `CertificateType` | True | 334118 |
| `createSecurityContext` | True | 257793 |
| `sas_certificate` | False | None |
| `sas_login` | False | None |
| `signChallenge` | True | 314575 |
| `EVP_SignFinal` | True | 249561 |
| `EVP_PKEY_sign` | True | 261934 |

RSA-Modulus des Wire-Leafs: **nicht** als Klartext-Konstante in `libaudio.so` gefunden (erwartet — Key kommt aus Runtime/Keystore/P12-Ladepfad). **FACT — RAW**

Passender Codepfad (bereits bekannt, durch Verify gestärkt):
`createSecurityContext` → APP_AUTH/`CertificateType` → `signChallenge` → MD5-XOR-Pad → `EVP_SignFinal` / `EVP_PKEY_sign` → 512-B-Sig.

Neue Suchwerte aus diesem Capture: Leaf-FP `99151742…`, Challenges, 512-B-Sig-Hashes — für dynamische Traces, nicht als SO-Strings. **INFERENCE**

---

## 26. Neue Erkenntnisse

1. **RSA-VERIFY CLOSED** auf echtem Feld-Cert+Sig (18/18).
2. **19 Challenges** (nicht nur 2) — Multi-Channel-AUTH.
3. **Cert-Bundle vollständig** aus Raw (PKCS7 mit APP+APP_AUTH+Spotify leafs).
4. HU BCL **>4000** Payload (5306) — Parser-Limit-Bug-Ursache.
5. Phone-Etch-Fragmentierung + Capture-Desync-Mechanik dokumentiert.
6. `av_playerStateChanged` + Spotify-ASCII-Offsets byte-genau.
7. Cover-JPEG 18 442 B + AM-Icons extrahiert.
8. b3.jsonl unterdekodiert Cert/Fragments — Dissector-Backlog.

---

## 27. Widersprüche zu bisheriger Dokumentation

| Aussage vorher | Raw-Befund |
|----------------|------------|
| RSA-VERIFY pending | **PASS** 18/18 |
| sas_certificate fehlt im Capture-Decode | Cert **ist** in Raw @ phone≥162; nur JSONL-Decode fehlte |
| „12 BCL / 2 etch“ HU in EVAL-Kurzfenster | Gesamtes HU-Raw: 598 DATA / hunderte Etch |
| Feature-PKI PFX = APP_AUTH | **weiter REJECTED** (Leaf hier RSA-4096 TouchCommand; PFX war RSA-1536 Feature) |

---

## 28. Offene Punkte

1. Private Signing Key / Keystore-Load in AAIdrive — nicht aus Wire ableitbar.
2. Exakte BCL-Header-Loss-Ursache im 151-B-Fragment (Relay vs. RFCOMM).
3. Session-2 (2. INIT) Auth-Noise vollständig semantisch zuordnen.
4. b3-Dissector: Cert-TX + Fragment-Reassembly nachziehen.
5. Ob **alle** parallelen AUTH-Kanäle eigene RHMI-Instanzen öffnen oder nur Security-Warmup sind — **HYPOTHESIS**.

---

## 29. Reproduzierbarkeit

```bash
cd bt-analyzer
python3 docs/evidence/FIELD_B3_GATEB_20261121T112446Z/forensic/run_raw_forensic.py
# crypto pairing + leaf export: siehe SAS_CRYPTO_VERIFY.json / SAS_CERTIFICATE.der
sha256sum docs/evidence/FIELD_B3_GATEB_20261121T112446Z/raw/*.bin
```

Originale Raw-Dateien werden nicht geschrieben.

---

## 30. Gesamtfazit

```
AAIdrive
   │  sas_certificate  phone_off≥0xA2  PKCS7/APP_AUTH
   ▼
HU
   │  _result_sas_certificate  hu_off=0x6C
   │  challenge=8f873bb740471e52f36aa26093f580da
   ▼
AAIdrive
   │  preprocessing: MD5(chal XOR MD5(0x02000000))
   │  RSA-4096 PKCS#1 v1.5  [CRYPTO VERIFIED]
   │  sas_login 512-B  phone_off=0x18A0
   ▼
HU
   │  _result_sas_login ACCEPT  hu_off=0xC3
   ▼
SecurityContext × N Kanäle
   ▼
RHMI (handle 23 music) + AM (5 apps) + CDS + AV(music)
   ▼
Spotify UI / Halestorm metadata / cover JPEG
```

**Was wir neu wissen:** Der erfolgreiche Feld-Capture enthält genug Bytes, um APP_AUTH **ende-zu-ende mathematisch zu schließen** und die Lücke „Wire-Sig ↔ Leaf-Pubkey“ zu füllen. Die Lücke „Leaf-Pubkey ↔ privater Signer in libaudio/Keystore“ bleibt OPEN — aber die Gleichung und der Public Key sind jetzt Feld-Fakten, nicht Theorie.

---

## Anhang A — Bekannt vs. neu

| Erkenntnis | Status vorher | Ergebnis dieser Analyse |
|------------|---------------|-------------------------|
| APP_AUTH 512-B Sig | bekannt | bestätigt, 18 Instanzen |
| SAS Pad 0x02000000 | bekannt (transform) | **CRYPTO VERIFIED** ×18 |
| Zertifikat Wire | teilweise offen | **geschlossen** (PKCS7+Leaf DER) |
| RSA Verify | offen | **PASS** |
| Multi-Challenge | 2 bekannt | **19** |
| Spotify≠AM | bekannt | bestätigt (5 AM apps) |
| Handle 23 | bekannt STRONG | 180 RHMI refs |
| Cover art | Operator | JPEG/PNG extrahiert+gehasht |
| HU DATA>4000 | Parser-Symptom | **5306** gemessen |
| b3 Dissector completeness | unbekannt | **lückenhaft** (kein cert decode) |
| libaudio Signer private key | OPEN | weiter OPEN |

---

## Anhang B — Epistemic Legend

- **FACT — RAW** — direkt aus Bytes/Offsets
- **FACT — DECODED** — Etch/BCL-Decode mit Registry
- **FACT — CRYPTO VERIFIED** — openssl RSA verify
- **FACT — FIELD** — Operator + Wire
- **INFERENCE** / **HYPOTHESIS** / **UNKNOWN** / **REJECTED** — wie markiert

