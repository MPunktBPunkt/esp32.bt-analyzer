# Deep Forensic — RHMI-Browse, YouTube & Screen-Mirror auf F20-HU (2026-11-17)

**claim_level:** FIELD FACT + LAB FACT (eigene deterministische Forensik, keine KI-Fremdkommentare)
**Peer:** F20 HU `d4:36:39:cf:e1:b5` (BMW 38304), App-UID `10479`, RFCOMM **SCN 6**
**Feld-Quellen (OnePlus `bluetooth_*.log`):**
- `docs/bluetooth_20261117_072945_12974.log` (3,28 MB) — **Schwanz Lauf 1 (Spotify)**, endet BT OFF
- `docs/bluetooth_20261117_073003_19188.log` (21,4 MB) — **Hauptbeweis: ein Connect-Zyklus mit Spotify → YouTube → Screen-Mirror**, endet BT OFF
- `docs/bluetooth_20261117_073249_22237.log` (354 KB) — nur BLE-Idle, kein Classic-Connect

**Lab-Quelle (eigener f20_sim, voller Wire):** `docs/evidence/LAB_F20SIM_LIVE_20261116T1741Z_hu.jsonl` + `LAB_RHMI_BROWSE_20261116T2002Z.*`
**Decoder:** `tools/etch_codec.py` (sdbm-Seed 5381; **Tiny-Int-Decode-Fix 2026-11-17**, s. §5)
**Reproduktion:** `scratch/car_forensic_complete_1117.py`, `scratch/full_deep_decode_1117.py`

> Dieser Bericht **korrigiert** `docs/analysis/FIELD_RHMI_BROWSE_20261117.md` an zwei Stellen (YouTube-Präsenz, Sitzungs-Framing) und ergänzt den `setData`-Exception-Decode.

---

## 1. Verdict

1. **Ein einziger Connect-Zyklus** (`19188`) enthält **beide** Medien-Phasen: zuerst **Spotify** (aktiver Player 07:30:14–07:31:20), danach **YouTube** (aktiver Player 07:31:32–07:32:15), dann BT OFF 07:32:48. Es sind **nicht** zwei getrennte Connected-Läufe.
2. **YouTube ist belegt** — `com.google.android.youtube` als Media-Session **und** als AAIdrive-`am_registerApp` (Frame-Größe 1123 B @07:31:08.69). Die alte Aussage „kein YouTube im Log" ist falsch.
3. Die HU wies **zwei `rhmi_setData`-Aufrufe mit einer `ServiceException` ab** (Typ-Hash `0x5A6F115C` = `de.bmw.idrive.BMWRemoting.ServiceException`, `src=17`, 07:31:08.316 & 07:31:10.352) — direkt aus dem 32-Byte-Dump dekodiert.
4. **Screen-Mirror** ist stark belegt: AAIdrive-App `io.bimmergestalt.idriveconnectaddons.screenmirror` (Lab bestätigt) + ~216-KiB-Bildburst nach dem 2. `onActionEvent` **während** YouTube-Wiedergabe (07:32:08).
5. **Der konkrete Song-/Videotitel ist aus den Feldlogs grundsätzlich nicht rekonstruierbar** (Handy = A2DP-Quelle). Beweisführung §6.

---

## 2. Sitzungs-Timeline (Wall-Clock, Log `19188`)

| Zeit | Ereignis | Beleg (Zeile) |
|------|----------|---------------|
| 07:30:01.848 | BT OFF Ende Lauf 1 | `12974` TURNING_OFF |
| 07:30:14.78 | Adapter ON, **Set active player = com.spotify.music** | L8117/L8207 |
| 07:30:47.99 | Phone **INIT** 4 B | L13801 |
| 07:30:48.03 | HU **HANDSHAKE** (Δ 37 ms) | L13940 |
| 07:30:51.00 | **SELECTPROTO** (Δ ≈ 2,97 s, 3-s-App-Timer) | L14541 |
| 07:30:51.7 / 07:30:52.8 | **sas_login** 559 B ×2 | L15448/L18556 |
| 07:31:04.8–07:31:11.6 | **am_registerApp**-Welle (Alexa, Readout, BT, **YouTube**) | §4 |
| 07:31:08.316 | **`setData` → ServiceException** (src17) | L39641 |
| 07:31:10.352 | **`setData` → ServiceException** (src17) | L48359 |
| 07:30:53–07:31:20 | Spotify player_state 3→2 (Play→Pause) | L19436…L65647 |
| 07:31:18.20 | YouTube als Wrapped-Media-Player (key 2) | L63142 |
| 07:31:32.08 | **Set active media session = YouTube** | L74063/L74130 |
| 07:31:34.19 | YouTube player_state 3 (Play) | L75940 |
| 07:31:42.5 / 07:32:07.8 | `rhmi_onActionEvent` #1/#2 (iDrive-Navigation) | L82285/L98708 |
| 07:32:08.6 | **~216 KiB Bildburst (324×666)** = Screen-Mirror/Asset | §4 |
| 07:32:15.39 | YouTube player_state 2 (Pause) | L107050 |
| 07:32:48.053 | **BT OFF** Ende Hauptzyklus | L128958 |

---

## 3. `setData`-Exception hart dekodiert (Feld)

Die beiden `plen=99`-Frames (BCL `0002 0011 0FA4 0063`: cmd=DATA, **src=17**, dest=4004, len=99) tragen:

```
… 03 86 9358A564   _result_rhmi_setData
   03 86 8104FDC2   Feld „result"
   95 86 5A6F115C   TypeCode CUSTOM(0x95) + Typ-Hash ServiceException
```

`0x5A6F115C = etch_hash("de.bmw.idrive.BMWRemoting.ServiceException")` — **eindeutig aus den ersten 32 Bytes**. Die HU hat also zwei `setData`-Aufrufe abgelehnt; die übrigen 7 gleichen Hashes sind void-OK (`plen=44`, nur `_inReplyTo`).

- **FIELD FACT:** `result` = CUSTOM `ServiceException`, `src=17`, 07:31:08.316 & 07:31:10.352.
- **STRONG (Lab-korrespondiert):** entspricht dem AAIdrive-`MockBMWRemotingServer`-Pfad `throw ServiceException(213, "SetData was not successful.")` beim Setzen eines `ImageID`-Modells auf 0 (Cover-/Bild-nicht-verfügbar). `errorCode`/`detailMessage` liegen jenseits von Byte 32 → feldseitig **nicht** beweisbar, nur der Typ.

---

## 4. App-/Frame-Rosetta (Lab-Größe → Feld-Frame)

Aus dem **vollen** Lab-Wire dekodierte `am_registerApp`-Größen, im Feld über die Phone→HU-Frame-Summe wiedergefunden:

| AAIdrive-App (`appId`) | BCL-Größe | Feld `19188` Treffer (Zeit) |
|------------------------|----------:|------------------------------|
| `…assistant.com.amazon.dee.app` (Alexa) | 2409 | 07:31:04.78 ✅ |
| `…notification.readout` | 1874 | 07:31:07.70 / 07:31:11.58 ✅ |
| `…com.android.bluetooth` | 3255 | 07:31:08.48 ✅ |
| `…com.google.android.youtube` | 1123 | **07:31:08.69 ✅** |
| `…assistant.com.google.android.googlequicksearchbox` | 2362 | (koalesziert, nicht isoliert) |
| `io.bimmergestalt.idriveconnectaddons.screenmirror` | 1332 | (nicht isoliert; Burst s. u.) |

- **FIELD FACT:** YouTube-, Alexa-, Readout-, BT-App registrieren sich im Feld (exakte Frame-Summen).
- **STRONG:** Screen-Mirror — der **~216-KiB-Burst** (324×666+587) um 07:32:08 fällt in die YouTube-Wiedergabe und folgt dem 2. `onActionEvent`; das ist das Muster des `screenmirror`-Providers (JPEG-Frames via `rhmi_setData` an ein RaImageModel, Qualität 60).

---

## 5. Tooling-Fund: Etch-Tiny-Int-Decode-Bug (behoben)

`tools/etch_codec.py` las Einzelbyte-Integers nur im Bereich `0x00–0x1F` / `0xE0–0xFF`. Apache-Etch-BinaryTaggedData kodiert sie aber über **`0x00–0x7F` (0…127)** und **`0xC0–0xFF` (−64…−1)** (das Band `0x80–0xBF` sind TypeCodes). Dadurch brach der Decoder mitten in vielen `rhmi_setData`-Nachrichten ab → sie wurden **nur als Länge** protokolliert.

**Fix (2026-11-17):** `read_int`, `read_type_or_field_id`, `read_value` auf den vollen gültigen Bereich erweitert; Regressionstest `test_tiny_int_decode_full_etch_range` ergänzt. **Host-Tests: 122/122 OK.**

**Wirkung am Lab-Datensatz `LIVE_1741`** (volle Reassemblierung mit gefixtem Codec):

| Metrik | vor Fix (Lab-Eval 16.11.) | nach Fix |
|--------|---------------------------|----------|
| `rhmi_setData` dekodierte Modelle | `None × 2896` (len-only) | **40 Modelle** (`445/446/447/451/452/458/462/456…`) |
| Decode-Fehler | — (Abbruch) | **0** |
| Track-Timeline | leer | **80 Einträge mit Klartext** |

---

## 6. Prüffrage Metadaten — konkreter Titel nicht rekonstruierbar (Feld)

| Signal | Befund | Beleg |
|--------|--------|-------|
| `updateSourceMetadata: metadata tags size` | **immer 0** (2× in `12974`, 19× in `19188`) | Histogramm `{0: …}` |
| NowPlaying-Liste | `Got a null now playing list` | `getNowPlayingList` |
| Track-ID | Platzhalter `curr_song_id= NowPlayingId32` | `OplusTrackChangedNotificationResponse` |
| `getSongInfo` / `GetElementAttributes` | kein folgender Titel/Artist/Album | 0 Kontexttreffer |
| Artist/Album/Titel-String | **nicht vorhanden** | keine lesbaren Zuweisungen |

**Grund:** Das OnePlus ist in allen drei Captures die **A2DP-Quelle**. Android loggt in dieser Rolle nur, *dass* Metadaten gepusht wurden, nicht deren Inhalt. Die RHMI-`setData`-Strings (Modelle 445/446/447) laufen **Phone→HU** und werden von Oppo nur als Länge geloggt; HU→Phone-Dumps sind auf 32 Byte gekürzt.

**Beweisbar ist nur die Player-Identität:** `com.spotify.music` (07:30:14–07:31:20) und `com.google.android.youtube` (07:31:32–07:32:15).

**Gegenbeweis Lab:** Im f20_sim steht die **HU** auf der Logger-Seite → voller Inhalt. Dekodierte NowPlaying-Tupel (Modelle 445/446/447):

- `Scorpions – Best – Still Loving You`
- `HIM – Greatest Love Songs Vol. 666 – Wicked Game`
- `Disturbed – Ten Thousand Fists – Land of Confusion`

---

## 7. Lab-Lauf-Auswertung (f20_sim, 2026-11-16)

### Was geklappt hat 🟢
- **11c (phone↔f20_sim) PASS**: UI grün (AAIdrive/MyBMW), SAS-Login, CDS + RHMI live.
- **SAS**: 42× `sas_certificate` + 42× `sas_login`, 5× `sas_logout` sauber.
- **CDS-Inject → UI bestätigt**: `speed 87 / battery 42 / RPM 4321` und `speed 99 / RPM 5555 / battery 77 / odo 114321` sichtbar; 195 `cds_property_tx` über 33 Properties.
- **RHMI komplett**: 2896 `rhmi_setData`, 219 `setProperty`, 47 `setResource` (DESCRIPTION-XML `calendar`/`News_1`/`OnlineServices`/**`Multimedia` 92085 B**, IMAGEDB bis 162483 B, TEXTDB).
- **am_registerApp** mit echten appIds (googlequicksearch/Alexa/Readout/**ScreenMirror 1332**/YouTube/BT).
- **A2DP-Audio + Cover**: Cover-JPEG auf Modell 456, Artist/Album-Icons.
- **Voll-Decode freigeschaltet** durch den Codec-Fix (§5): 0 Decode-Fehler, 192 Resyncs tolerant.

### Was nicht geklappt hat 🔴
- **AVRCP↔RHMI-Regelkreis instabil**: nach Action-Flut/Reconnect blieb NowPlaying `stale`; A2DP spielt ohne frisches `setData`.
- **Dual-ESP-Luft-RFCOMM** `.87↔.131` **FAIL** (`.87` noch auf FW 0.3.19) — `LAB_DUAL_MYBMW_SIM_20261116T1901Z.md`.
- **Browse-only-Lauf** `BROWSE_2002`: 0 `rhmi_setData` bei reinem A2DP — bestätigt, dass A2DP ≠ RHMI-Fokus; der ursprüngliche 114-`framer_error`-Zustand war ein Nicht-Resync-Artefakt des Offline-Framers (meine resiliente Reassemblierung: 32 Resyncs, 1 Restfehler).
- **len-only-Lücke** aus der Lab-Eval ist **durch den Codec-Fix geschlossen** (§5).

---

## 8. Claim-Split

| Status | Claim |
|--------|--------|
| 🟢 FIELD FACT | Ein Connect-Zyklus `19188` mit Spotify **und** YouTube; BT OFF 07:32:48 |
| 🟢 FIELD FACT | YouTube als Media-Session + `am_registerApp` (1123 B @07:31:08.69) |
| 🟢 FIELD FACT | 2× `setData` → `ServiceException` (`0x5A6F115C`), src17 |
| 🟢 FIELD FACT | am_registerApp Alexa/Readout/BT via exakter Frame-Summe |
| 🟢 LAB FACT | Codec-Fix: 40 Modelle + 80 Tracks + 0 Fehler (vorher len-only) |
| 🟡 STRONG | Screen-Mirror = 216-KiB-Burst in YouTube-Wiedergabe nach 2. onActionEvent |
| 🟡 STRONG | `ServiceException` = `(213,"SetData was not successful.")` (ImageID→0) |
| 🔴 kein Beleg | konkreter Spotify-Song / YouTube-Titel aus Feldlog |

---

## 9. Reproduktion

```bash
# Feld
python scratch/car_forensic_complete_1117.py       # → scratch/car_forensic_complete_1117.json
# Lab (voller Wire, gefixter Codec)
python scratch/full_deep_decode_1117.py            # → scratch/full_lab_reassembled_1117.json
# Host-Tests
python -m pytest tests/host -q                     # 122 passed
```
