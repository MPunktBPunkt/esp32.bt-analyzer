# Feld — RHMI-Browse mit Spotify auf HU (2026-11-17)

**claim_level:** FIELD FACT (Wire aus OnePlus `bluetooth_*.log`)  
**Quellen:**  
- `docs/bluetooth_20261117_072945_12974.log` (Schwanz-Session)  
- `docs/bluetooth_20261117_073003_19188.log` (**Hauptbeweis**)  
- `docs/bluetooth_20261117_073249_22237.log` (abgebrochener Re-Enable)  
**Peer:** F20 HU `d4:36:39:cf:e1:b5` (BMW 38304), App-UID `10479`, RFCOMM **SCN 6**  
**Methodik:** `docs/METHODIK_LOG_FORENSIK.md`  
**Parser:** `tools/field_btlog_forensic_20261117.py` → `docs/analysis/FIELD_BTLOG_FORENSIC_20261117.json`  
**Hashes:** `tools/etch_codec.py` (`HASH_REGISTRY`, sdbm seed 5381)

---

## 1. Verdict

Im Hauptlauf (`19188`) sind **RHMI-Menüdaten auf dem Wire belegt**: HU→Phone `_result_rhmi_setData` **×19** (+×2 in `12974` = **Σ21**), `rhmi_onActionEvent` **×2**, `_result_rhmi_ackActionEvent` **×1**, parallel zu **A2DP + `com.spotify.music`**.

Das ist das **Gegenstück** zu `docs/evidence/LAB_RHMI_BROWSE_20261116T2002Z.md` (A2DP an, Music-RHMI/`setData` = 0).

**Nicht** in diesen Logs: Spotify-Artist/Album/Titel-Strings, Cover-Pixels, YouTube-Titel (siehe §6).

---

## 2. Log-Rollen

| Datei | Wall-Clock | Rolle |
|-------|------------|--------|
| `…_12974` | 07:29:45–07:30:02 | Schwanz Connected (~296 KiB TX), setData×2, dann BT OFF |
| `…_19188` | 07:30:03–07:32:48 | **Vollzyklus** OFF→ON→BCL/SAS/RHMI/Browse→OFF |
| `…_22237` | 07:32:49–07:34:40 | nur BLE_ON, kein classic Connected |

---

## 3. Entscheidende Fundstellen (Zeile + Zeitstempel)

Alle Zeilen beziehen sich auf **`docs/bluetooth_20261117_073003_19188.log`**, sofern nicht anders angegeben.  
Suchschlüssel: `oplus_send_data_to_app_dump` (HU→Phone Hex), `PORT_WriteDataCO` (Phone→HU Länge), `RFCOMM_BufDataInd` (UIH).

### 3.1 Adapter / Spotify / A2DP

| Was | Zeile | Zeit | Log-Snippet / Beweis |
|-----|------:|------|----------------------|
| Active player Spotify | **8117**, 8129 | 07:30:14.784 | `Set active player … com.spotify.music` |
| Adapter **ON** | **8207** | 07:30:14.805 | `[AdapterState] ON : entered` |
| HU Cover-Art SDP **false** | **9468** | 07:30:42.746 | `browse supported true, cover art supported false` |
| NowPlaying-Liste null | **10453** | 07:30:42.984 | `getNowPlayingList: Got a null now playing list` |
| A2DP started | **13186** | 07:30:47.869 | `btif_av_stream_started_ready … e1:b5` |
| Spotify player_state | **19436** | 07:30:53.153 | `player_name: com.spotify.music, player_state: 3` |
| Metadata leer (Beispiel) | **19433** | 07:30:53.147 | `com.spotify.music tried to update with no new data` (182× gesamt) |
| Adapter **TURNING_OFF** | **128958** | 07:32:48.053 | Ende Hauptzyklus |

### 3.2 BCL-Bootstrap (Längen + HS-Hex)

| Was | Zeile | Zeit | Beweis |
|-----|------:|------|--------|
| Phone **INIT** 4 B | **13801** | 07:30:47.996 | `PORT_WriteDataCO: 4 bytes` |
| HU **HANDSHAKE** | **13940** | 07:30:48.033 | `data_hex=00040000000000080005000E00004000` → **Δ = 37 ms** |
| **SELECTPROTO** 10 B | **14541** | 07:30:51.002 | `PORT_WriteDataCO: 10 bytes` → **Δ ≈ 2,969 ms** nach HS (App-3-s-Timer) |
| **KNOCK** 56 B | **14602** | 07:30:51.016 | `PORT_WriteDataCO: 56 bytes` |
| **sas_login** #1 559 B | **15448** | 07:30:51.739 | `PORT_WriteDataCO: 559 bytes` |
| **sas_login** #2 559 B | **18556** | 07:30:52.846 | `PORT_WriteDataCO: 559 bytes` |
| Caps-Request 52 B | **18366** | 07:30:52.803 | `PORT_WriteDataCO: 52 bytes` (= `rhmi_getCapabilities`-Größe) |

### 3.3 Capabilities = UIH-Arithmetik (ohne Hash im Dump)

Erster vollständiger Cluster **7×667 + 645 = 5314** (= 8 BCL + `plen=5306`):

| Fragment | Zeile | Zeit | `buf_len` |
|----------|------:|------|----------:|
| 1.–7. | **15670** … **158xx** | 07:30:51.800+ | 667 |
| Rest | **15939** | 07:30:51.830 | **645** |

Weitere 5314-Cluster enden u. a. bei L**16323**, L**18835**, L**20969**.  
Capability-ASCII in App-Dumps (Fortsetzung der Map):

| Zeile | Zeit | Inhalt |
|------:|------|--------|
| **24126** | 07:31:01.561 | `false` / `iva_MYV_LIGHT_INTERIOR…` |
| **24950** | 07:31:02.860 | `rear_window_curtain` |

### 3.4 AM / checkResource / setData / Actions (Etch-Hash)

Hash-Auflösung: `0386` + sdbm → `tools/etch_codec.HASH_REGISTRY`  
(Truncated Dumps: 4-Nibble-Präfix eindeutig, z. B. `E52B` → `_result_am_registerApp`).

| Was | Hash | Zeile | Zeit | src (BCL) |
|-----|------|------:|------|-----------|
| `_result_am_addAppEventHandler` | `EC3A5A1E` (Präfix) | **26119** | 07:31:04.001 | 18 |
| `_result_am_registerApp` | `E52B6070` | **26545**, **26883**, **27618** | 07:31:04.772+ | 15/18 |
| `_result_rhmi_checkResource` | `0E18858E` | **30396** | 07:31:06.739 | 18; `result=true` (`0x83`) |
| `_result_rhmi_setData` **erstes** | `9358A564` | **39641** | 07:31:08.316 | 17; **valued** `plen=99` |
| `_result_rhmi_setData` void | `9358A564` | **43846** | 07:31:09.340 | 19; `plen=44` |
| `_result_rhmi_setData` void | | **45299** | 07:31:09.844 | 18 |
| `_result_rhmi_setData` valued | | **48359** | 07:31:10.352 | 17; `plen=99` |
| `cds_onPropertyChangedEvent` | `AE0D3D69` | **60821** … | 07:31:14.361+ | 13 |
| `rhmi_onActionEvent` #1 | `6008ACFA` | **82285** | 07:31:42.522 | 19; `_messageId=1632` |
| `_result_rhmi_ackActionEvent` | `633A9623` | **91782** | 07:31:58.946 | 19 |
| `rhmi_onActionEvent` #2 | `6008ACFA` | **98708** | 07:32:07.827 | 19 |
| `_result_rhmi_setData` letztes | | **125018** | 07:32:42.429 | 19 |

**setData gesamt in `19188`:** 19 Dumps mit `03869358…` (L39641–L125018).  
**Zusätzlich `12974`:** L**5984** @07:29:48.915, L**12280** @07:29:52.790.

### 3.5 Große Phone→HU-Uploads (Menü-/Asset-Kandidaten)

Nur Längen (`PORT_WriteDataCO: 666`) — Hex fehlt. Parser zählt contiguous 666-Runs:

| Start (approx) | n×666 + rem | ~Payload | Kontext |
|----------------|-------------|---------|---------|
| 07:30:53.441 | 62+41 | ~41 KiB | nach Caps / vor AM |
| 07:31:23.994 | 158+651 | ~106 KiB | vor setData @07:31:35.871 |
| 07:31:36.288 | 262+424 | ~175 KiB | zwischen Actions |
| **07:32:08.605** | **324+587** | **~216 KiB** | nach 2. `onActionEvent` (Screen-Share-Kandidat) |

Wiederholte kleine TX-Größen im Browse-Fenster (setData-Templates): **92×25, 81×20, 83×15, 88×12, 84×9**.

### 3.6 Log `22237` — negativer Beleg

Kein `AdapterState ON`, kein `PORT_WriteDataCO`, kein `oplus_send_data_to_app_dump` gegen `e1:b5`. Nur Bond-Cache um L~924 @07:32:49.924 und `BLE_ON` @07:32:49.977.

---

## 4. Claim split

| Status | Claim |
|--------|--------|
| 🟢 FIELD FACT | BCL SCN6 / UID10479 / HS v5 buf=0x4000 |
| 🟢 FIELD FACT | INIT→HS 37 ms; SELECTPROTO ~3 s App-Timer |
| 🟢 FIELD FACT | 2× sas_login 559 B |
| 🟢 FIELD FACT | 4× Caps-Cluster 5314 B UIH |
| 🟢 FIELD FACT | Σ21 `_result_rhmi_setData`; 2× `onActionEvent` |
| 🟢 FIELD FACT | AM register/addHandler; CDS events; A2DP+Spotify parallel |
| 🟢 FIELD FACT | AVRCP-Metadaten **ohne** Artist/Album/Titel in diesem Capture |
| 🟡 STRONG | 666-Bursts = setResource DESCRIPTION/IMAGEDB |
| 🟡 STRONG | ~216 KiB nach Action ≈ Screen-Share/Assets (kein Miracast im Log) |
| 🔴 kein Beleg | konkreter Spotify-Titel / Cover-Aussehen / YouTube-Titel |
| 🔴 kein Beleg | zweiter Connected-Zyklus in `22237` |

---

## 5. Wie das Menü beschrieben wird

Zwei Schichten (Kit + Lab; Feld nur über ACK/Längen):

```text
sas → rhmi_create → checkResource → setResource(DESCRIPTION|IMAGEDB|…)
  → initialize → Action/Hmi-Handler
  → laufend setData(handle, modelId, value) / setProperty
  ← HU: rhmi_onActionEvent (iDrive-Navigation)
```

- **DESCRIPTION:** binäre RHMI-DB (Lab-Größen ~13,6–13,9 KiB), kein Klartext-Menü.  
- **setData:** Laufzeitwerte; Lab-Beispiel NowPlaying `modelId 445/446/447` = Artist/Album/Titel — **in diesem Feld-Capture nicht lesbar** (Phone→HU ohne Hex).  
- **Capabilities** (`rhmi_getCapabilities`) ≠ Widget-Baum (149 System-Flags).

---

## 6. Prüffrage Metadaten (negativ, bewusst)

Gefragt: Artist, Album, Song, Cover-Aussehen, YouTube-Titel.

| Signal | Befund | Fundstelle |
|--------|--------|------------|
| Artist/Album/Titel | **nicht vorhanden** | nur `tried to update with no new data` (z. B. L19433); `metadata tags size: 0` |
| Cover | **nicht vorhanden** | HU `cover art supported false` L9468; kein JPEG/PNG in Dumps |
| YouTube | **nicht vorhanden** | kein `youtube` / `com.google.android.youtube` im Log |
| Was da ist | Player-Paket | `com.spotify.music` L8117 / L19436 |

Oppo loggt Phone→HU nur als Länge; HU-Dumps oft nach ~32–64 Hexzeichen mit `...` abgeschnitten. Deshalb: Mechanismus **ja**, Inhalt **nein**.

---

## 7. Abgleich Lab 16.11. vs Feld 17.11.

| Signal | Lab browse (A2DP-only) | Feld 17.11. |
|--------|------------------------|-------------|
| `rhmi_setData` | 0 | **21 ACK** |
| `rhmi_onActionEvent` | 0 | **2** |
| A2DP Spotify | an | an |
| Schluss | A2DP ≠ RHMI-Fokus | Menü-Browse aktiviert RHMI-Wire |

---

## 8. Reproduktion der Analyse

```bash
python3 tools/field_btlog_forensic_20261117.py
# → stdout + docs/analysis/FIELD_BTLOG_FORENSIC_20261117.json
```

Manuell im Hauptlog:

```bash
rg -n '03869358|03866008ACFA|03860E18858E|PORT_WriteDataCO: 559|com.spotify.music' \
  docs/bluetooth_20261117_073003_19188.log
```

---

## 9. Next

1. Parallel **B3-RFCOMM-Relay** → setResource/setData-Bodies (welche App, welche modelIds).  
2. Screen-Share mit Zeitmarkern + optional WLAN-Capture.  
3. Zweiten BT-ON erst loggen nach sichtbarem `AdapterState ON` + `PORT_WriteDataCO: 4`.  
4. Lab Test B: Spotify *innerhalb* Connected — erwartet denselben setData/Action-Fingerabdruck.
