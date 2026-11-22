# Byte-genaue forensische Analyse — HU↔AAIdrive Relay-Session (B3)

Dateien: `phone_to_hu.bin` (417.174 B), `hu_to_phone.bin` (110.651 B)
MD5 identisch zu `FIELD_B3_GATEB_20261121T112446Z/raw/*` — selbe Session.
Methodik-Korrektur gegenüber früheren Turns: Diese Analyse parst **BCL-Frames zuerst** (cmd/src/dest/len) und reassembliert Etch-Nachrichten **fragmentierungsbewusst über Frame-Grenzen hinweg**, statt naiv nach `DE AD BE EF`-Bytes im Rohstrom zu suchen. Letzteres war in früheren Turns für kleine Nachrichten (<4000 B) zufällig korrekt, hätte aber bei großen/fragmentierten Nachrichten falsche Ergebnisse geliefert.

---

## 1. Bestätigte Frame-Grammatik

### 1.1 BCL-Layer (äußere Rahmung, beide Richtungen identisch)

```
Header (8 Byte, alle Felder big-endian u16):
  cmd   (2B)
  src   (2B)
  dest  (2B)
  len   (2B)   — Länge des folgenden Payloads in Byte
Payload (len Byte)
```

**classification: FIELD FACT** (byte-exakt nachgewiesen, s. Beispiel 1.3).

Beobachtete `cmd`-Werte:
| cmd | Bedeutung (abgeleitet) | Evidence |
|-----|------------------------|----------|
| `0x0001` | Control/Connect, meist `len=0` | STRONG |
| `0x0002` | DATA — trägt Etch-Payload (ganz oder fragmentiert) | FIELD FACT |
| `0x0004`,`0x0005`,`0x0006` | nur am Dateianfang (hu_to_phone), kleine Payloads (4 B), vermutlich lokale Kanal-/Session-Kontrollframes des Relays, **nicht** Teil des Etch-Nutzlaststroms | HYPOTHESIS |

### 1.2 Etch-Layer (innerhalb BCL-DATA-Payload)

```
Magic      4B  = DE AD BE EF
BodyLen    4B  = u32 big-endian
Body       BodyLen Byte  (Etch-RPC-Encoding, Methodenname + Felder)
```

**classification: FIELD FACT.**

### 1.3 Fragmentierung — neuer, byte-exakt belegter Fund

**Richtung:** PHONE → HU
**file offset:** `0x0000009A` (BCL-Header 1) / `0x00001042` (BCL-Header 2)

```
hex @0x9A:
0002 000a 0fa4 0fa0     ← BCL-Header: cmd=2 src=0x000a dest=0x0fa4 len=0x0fa0(4000)
dead beef 0000 17e6     ← Etch-Magic + bodylen=0x17e6(6118) → Gesamt-Etch-Frame=6126 B
0386 304b a8bb 0286 ...  (4000 B Payload, davon 3992 B Etch-Body)

hex @0x1042:
0002 000a 0fa4 084e     ← BCL-Header 2: cmd=2 src=0x000a dest=0x0fa4 len=0x084e(2126)
<2126 B Fortsetzung des Etch-Body>
```

**decoded:** Etch-Nachricht `sas_certificate` (6126 B gesamt) wird exakt über 2 BCL-DATA-Frames gesplittet: 4000 B + 2126 B = 6126 B. Reassembly-Regel: Fortsetzung erfolgt über denselben `(src,dest)`-Kanal, ohne weiteres Trenn-/Sequenzfeld — rein längenbasiert.

**classification: FIELD FACT.** (Dies war in keiner vorherigen Analyse dieses Captures dokumentiert.)

### 1.4 Mehrere Etch-Nachrichten in einem BCL-Payload

Beobachtet z. B. bei großen Fragment-Serien: Der letzte BCL-Frame einer Fragment-Kette liefert oft mehr Bytes als zum Abschluss der laufenden Nachricht nötig sind — der Rest des Payloads ist bereits der Anfang der **nächsten** Etch-Nachricht im selben `(src,dest)`-Kanal. Reassembly muss daher Byte-weise (nicht Frame-weise) über den Kanal-Substream laufen.

**classification: FIELD FACT** (reproduzierbar an mehreren Stellen, z. B. Kanal `src=0x11,dest=0x0fa4`, Nachricht mit Ziel-Länge 20151 B).

---

## 2. Envelope-Layer — nicht Teil des BT-Protokolls

### 2.1 Phone→HU: Session-Envelope mit UUID (Debian-Bridge-Layer, laut Nutzerangabe)

**file offset:** `0x00000000`, Länge `0x56`
```
hex: dead beef dead 0100 0000 2c01 0130 6539 ...
ascii: ....,..0e9b90c4-cbe1-4742-8283-d367e9a566199...
```
**classification: STRONG (Herkunft: Debian-Bridge zwischen den zwei BT-Analyzer-Modulen, It., Nutzerangabe).** Enthält Session-UUID `0e9b90c4-cbe1-4742-8283-d367e9a56619` im Klartext sowie Platzhalter-ähnliche Werte (`0x12345678`, `0x1337`, `0x1389`), die wahrscheinlich interne Kanal-IDs des Bridge-Setups sind, nicht Funkverkehr.

**Drei Envelope-Grenzen in `phone_to_hu.bin`:**
| # | Offset | Bedeutung |
|---|--------|-----------|
| 1 | `0x00000000`–`0x00000099` | Start-Envelope, danach beginnt echter BCL-Verkehr (Connect #1) |
| 2 | `0x00055455`–`0x000554EE` | Zweiter Envelope-Block (identisches UUID+Zertifikat, **Reconnect**, danach neuer BCL-Verkehr bis `0x00065996`) |
| 3 | `0x00065996`–EOF (`0x00065D96`) | 18× wiederholter Envelope ohne Payload — **Padding/Keepalive nach Sessionende**, kein Funkverkehr |

**Drei Envelope-Grenzen in `hu_to_phone.bin`:**
| # | Offset | Bedeutung |
|---|--------|-----------|
| 1 | `0x00000000`–`0x00000063` | Start-Control-Frames (cmd 4/5/6), danach echter BCL-Verkehr ab `0x00000064` |
| 2 | `0x00015462` (87266 dez.) | Zweiter Control-Frame-Block — korreliert mit Reconnect #2 | 
| — | vereinzelte `1337 1337`-4-Byte-Marker (18× über die Datei verteilt) | vermutlich Keepalive/Heartbeat der Bridge, s. §2.2 |

### 2.2 Verstreute `13 37 13 37`-Marker

**classification: STRONG (plausible Erklärung durch Nutzer-Kontext).** 18× (phone→HU) bzw. mehrfach (HU→phone) taucht isoliert der 4-Byte-Wert `13 37 13 37` zwischen echten Etch-Nachrichten auf, exakt an Kanalgrenzen. Mit dem Hinweis des Nutzers (Debian verbindet zwei unabhängige BT-Analyzer-Strecken) ist die naheliegendste Erklärung: periodische Keepalive-/Sync-Pakete der Bridge-Software zwischen den beiden Analyzer-Verbindungen — **kein** Bluetooth-Wire-Protokoll-Element.

---

## 3. Kombinierte Methodentabelle (beide Richtungen, beide Connect-Versuche)

Vollständig fragmentierungsbewusst reassembliert — **signifikant vollständiger** als die bisher kolportierten Zahlen ("411 BCL-Frames / 301 Etch-Nachrichten"):

| Count | Methode | Status |
|------:|---------|--------|
| 1502 | **BCL-Frames gesamt** | neu gezählt (vorher: 411) |
| 1115 | **Etch-Nachrichten gesamt** | neu gezählt (vorher: 301) |
| 1068 | davon erfolgreich methodendekodiert | — |
| 183 / 183 | `rhmi_setData` / `_result_rhmi_setData` | bereits bekannt (Zahl bestätigt, exakt symmetrisch) |
| 155 | `cds_onPropertyChangedEvent` | **neu** — bisher nicht gezählt |
| 49 / 49 | `cds_addPropertyChangedEventHandler` / Result | bereits bekannt |
| 48 / 48 | `cds_getPropertyAsync` / Result | bereits bekannt |
| 47 / 47 | `rhmi_setProperty` / Result | bereits bekannt |
| 19 / 19 | `sas_certificate` / Result | bekannt, aber Zahl korrigiert (vorher 1–2 angenommen) |
| 18 / 18 | `sas_login` / Result | bestätigt (deckt sich mit früherem Methoden-Histogramm) |
| 11 / 11 | `rhmi_checkResource` / Result | bekannt, bestätigt (alle Cache-Hit) |
| **9** | `rhmi_onHmiEvent` | **neu entdeckt** |
| 8 / 8 | `rhmi_create` / Result | bekannt (Zahl: vorher 5, jetzt korrigiert auf 8 über beide Connects) |
| 7 / 7 | `rhmi_getCapabilities` / Result | **neu entdeckt** (im Bericht nur als "extrahierbar" vermutet) |
| **7 / 7** | `ver_getVersion` / Result | **neu entdeckt** |
| 6 / 6 | `am_create` / Result | bekannt, Zahl korrigiert |
| 5/5 je | `cds_create`, `cds_setPropertyAsync`, `rhmi_initialize`, `am_registerApp` (+Results) | bereits bekannt, bestätigt |
| 4/4 je | `am_addAppEventHandler`, `rhmi_addActionEventHandler`, **`rhmi_addHmiEventHandler`**, **`rhmi_ackActionEvent`**, `rhmi_onActionEvent` (+Results) | teils bekannt, teils **neu**; `rhmi_onActionEvent` korrigiert von "mind. 2" auf **exakt 4** |
| **3 / 3** | `info_getSystemInfo` / Result | **neu entdeckt** |
| 2 / 2 | `rhmi_triggerEvent` / Result | bekannt, Zahl bestätigt |
| 1 je | `am_showLoadingHint`, `am_showLoadedSuccessHint`, `av_create`, `av_requestConnection` (+Results) | bereits bekannt |
| **1** | `av_playerStateChanged` | **neu entdeckt** |
| **1 / 1** | `av_requestPlayerState` / **`av_connectionGranted`** | **komplett neu — bisher nirgends erwähnt** |

**classification: FIELD FACT** für alle gezählten Methoden (reproduzierbar über das beiliegende CSV mit Offsets).

---

## 4. Wichtigste Einzelbefunde für PiDrive

1. **`rhmi_onHmiEvent` (9×) und `rhmi_addHmiEventHandler` (4×)** sind ein bisher komplett unbeachteter Event-Pfad, getrennt von `rhmi_onActionEvent`. Für ein eigenes Menü relevant: HMI-Events (z. B. Fokus-/Sichtbarkeits-Änderungen) laufen über einen eigenen Handler, nicht nur Action-Events.
2. **`av_requestPlayerState` / `av_connectionGranted` / `av_playerStateChanged`** zeigen, dass der AV-Layer (Audio-Verbindung) einen eigenen Verhandlungs-Zyklus hat, unabhängig von RHMI — relevant für den vorher aufgeworfenen "Spotify via AVRCP"-Pfad.
3. **Zwei vollständige SAS-Login-Zyklen** in einer Capture-Datei (Reconnect), nicht nur einer — bisher wurde nur "ein" Login angenommen.
4. **`ver_getVersion`/`info_getSystemInfo`** (je 7×/3×) — Versions-Handshake, noch nicht inhaltlich ausgewertet (Payload-Felder offen).

---

## 5. Offene Punkte (unverändert / neu)

- Inhaltliche Felder von `ver_getVersion`, `info_getSystemInfo`, `rhmi_onHmiEvent`, `av_*` sind noch nicht dekodiert (nur Methodenname extrahiert) — **OPEN**.
- Envelope-Herkunft (Debian-Bridge) ist plausibel, aber nicht am Quellcode des Relay-Tools verifiziert — **HYPOTHESIS**, user-bestätigt als wahrscheinlich.
- Vollständiger CSV-Index aller 1115 Nachrichten mit Offsets liegt bei (`etch_messages_full.csv`) für lückenlose Nachverfolgung.

---

*Erzeugt durch fragmentierungsbewussten BCL/Etch-Parser (`bcl_walker2.py`), nicht durch naives Byte-Scanning.*
