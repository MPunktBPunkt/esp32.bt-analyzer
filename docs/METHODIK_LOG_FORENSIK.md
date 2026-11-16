# Methodik für Log- & Protokoll-Forensik — Warum Standard-KI-Analysen scheitern und worauf man achten muss

**Stand:** 2026-11-16  
**Anlass:** Aus denselben bereits vorhandenen Telefon-Logs (`bluetooth_20261114/15_*.log`), `.btsnoop`-Captures, Lab-Zertifikaten und Referenz-Sourcen ließen sich nachträglich nahezu alle als *„UNKNOWN / nur mit Root-HCI lösbar“* eingestuften Parameter (SAS Challenge & Login, das „blinde“ 3-s-Fenster, die 667-B-Flut, CDS-Properties, LSTO, LMP-Matrix, PKI-Kette und zwei Bugs im eigenen Lab-Stub) exakt bestimmen.

Dieses Dokument beschreibt **erstens konkret**, wie diese Befunde aus den vorhandenen Daten gewonnen wurden, und leitet daraus **zweitens einen allgemein gültigen Leitfaden (inkl. Prompt-Vorlage)** für künftige Hardware-, Bus- und Protokoll-Analysen ab.

---

## Teil 1 — Warum frühere KI-Durchläufe die Lösung übersehen haben (6 konkrete Hebel am F20-Fall)

### Hebel 1: Vorwärts-Hashing aus der IDL statt Textsuche im Binär-Dump
- **Typischer KI-Fehler:** KIs suchen in Logs mit `grep -i "sas\|challenge\|login"`. Da Apache Etch Methodennamen nicht als Klartext überträgt, lieferte die Suche `0` Treffer — woraus frühere Analysen schlossen: *„SAS NOT OBSERVED / UNKNOWN“* und den Frame `0386A6B0FFCA…` als *„belanglose 44-B-Void-Completion, nicht SAS“* abtaten.
- **Der richtige Griff:** Wenn ein Protokoll Bezeichner komprimiert oder hasht und eine Schnittstellendatei (`BMWRemoting.etch`) vorliegt, baut man in 15 Zeilen Python die **Vorwärts-Hashtabelle** (`sdbm` mit Seed `5381` über alle 1.537 Bezeichner + `_result_`-Präfixe) und joined sie gegen alle `03 86 <4 Byte>`-Stellen im Roh-Log.
- **Ergebnis:** Null unbekannte Hashes übrig — `0x9c6372b8` entpuppte sich sofort als `_result_sas_certificate` (inkl. der echten **16-Byte-SAS-Challenge** der HU in `173553`!) und `0xa6b0ffca` in `102058` als **`_result_sas_login`**.

### Hebel 2: Seitenkanal-Arithmetik (Längen + Zeitdeltas) statt „Kein Hex = blind“
- **Typischer KI-Fehler:** Weil Oppo in Senderichtung (Phone→HU) nur `PORT_WriteDataCO: N bytes` ohne Hex loggt, wurde das 3,012-s-Fenster zwischen `HANDSHAKE` und `DATAACK(10)` als *„komplett blind“* abgehakt.
- **Der richtige Griff:** Jede Protokollnachricht hat einen **charakteristischen Größen-Fingerabdruck** (`Header + feste Felder`). Stellt man alle Schreiblängen und Empfangs-Callbacks auf eine gemeinsame Millisekunden-Achse, entsteht ein Gleichungssystem mit meist eindeutiger Lösung:
  1. **Zeitgitter prüfen:** `10:21:25.440` (`4 B`) → `10:21:28.439` (`4 B`, **Δ = 2,999 s**) → `10:21:28.459` (`HS`, **Δ = +20 ms!**) → `10:21:31.441` (`10 B`, **Δ = 3,002 s**). Das beweist sofort: Die HU braucht nur **20 ms**, und die ~3 s sind lediglich der feste **3,000-s-Poll-Timer** der App!
  2. **Byte-Summen exakt nachrechnen:**
     - `10 B` = `8 B BCL + 2 B` (`SELECTPROTO`), `56 B` = `8 + 48` (`KNOCK`), `8 B` = `OPEN`, `12 B` = `8 + 4` (`WATCHDOG`).
     - `6 × 666 + 12 = 4008 B` = `8 B BCL + 4000 B` (`MAX_PAYLOAD`-Fragment 1 von `sas_certificate`).
     - **`559 B`** (38 ms nach der Challenge) = `8 B BCL + 8 B deadbeef + 7 B Struct + 14 B _messageId + 9 B bytes(512) + 512 B RSA-4096-Signatur + 1 B END` = **`sas_login` auf das einzelne Byte genau!**

### Hebel 3: Schichten strikt trennen (Transport-MTU vs. Applikations-Länge)
- **Typischer KI-Fehler:** Im Log stand 48× `len=667`. Frühere Läufe deuteten „667-B-Bursts“ als eigenes Applikations-Nachrichtenformat für CDS-Fahrzeugdaten.
- **Der richtige Griff:** Immer prüfen, auf **welcher OSI-/Stack-Schicht** eine Länge gemessen wird, und im ersten Paket eines Bursts das Längenfeld der **darüberliegenden** Schicht lesen:
  - Im ersten 667-B-Frame (`173520` / `173553`) stand im BCL-Header `plen = 0x14BA = 5306` (`_result_rhmi_getCapabilities`, **149 System-Flags**, kein CDS!).
  - In `173637` tauchte ein einzelner Restframe mit `len = 645` auf.
  - Probe: **`7 × 667 + 1 × 645 = 5314 = 8 B BCL-Header + 5306 B Payload`**. Damit waren auf einen Schlag sowohl die asymmetrische RFCOMM-MTU (`667 B` HU→Phone vs. `666 B` Phone→HU) als auch die Bedeutung der 667-B-Flut bewiesen.

### Hebel 4: Abgeschnittene Felder gegen endliche Kataloge schneiden
- **Typischer KI-Fehler:** Wenn ein String wegen des 32-Byte-Log-Limits nach 2 Zeichen abbricht (`0x93 0x12 65 6e` = `"en…"`), geben KIs auf (*„String abgeschnitten“*).
- **Der richtige Griff:** Im Binärpräfix `0x93 0x12` steckt zusätzlich die **exakte Gesamtlänge** (`0x12 = 18` Zeichen!). Schneidet man `(len == 18 AND startswith("en"))` gegen den endlichen Katalog aller bekannten Properties (`CDSProperty.kt`), schrumpft die Kandidatenmenge von ~110 auf 1–2 Einträge (so wurden `50: engine.RPMSpeed`, `47: engine.info` und `93: sensors.SOCBatteryHybrid = 255.00` eindeutig bestimmt).

### Hebel 5: „Beifang“-Telemetrie und Roh-Binärdateien statt bisheriger Markdown-Berichte lesen
- **Typischer KI-Fehler:** Sobald im Repo schon Analyse-Markdowns (`*_ANALYSIS.md`, `*_FORENSIC.md`) liegen, übernehmen Sprachmodelle deren Aussagen („LSTO offen“, „LMP offen“, „Sniff aktiv“), statt die Binärdateien und Neben-Subsysteme neu zu parsen.
- **Der richtige Griff:**
  1. **Hersteller-Diagnoseblöcke im selben Log suchen:** Android/Oppo schreibt alle 6 s `BluetoothQualityReport` (`BQR`)-Blöcke — darin standen `mLsto: 8000` (`5,000 s`) und `mUnusedAfhChannelCount: 49` im Klartext!
  2. **Eigene `.btsnoop`-Binärdateien auf HCI-Event-Ebene parsen:** HCI-Events `0x0B` (`fffe2dfedbff7b87`), `0x23` (`LE Host = OFF`), `0x12` (`Role Change 0x21 rejected`), `0x1408` (`Key Size = 16 B`) und `0x2F` (EIR PnP `0x044E:0x3020` Alps) standen schon seit dem ersten Feldtag komplett in `FIELD_A6` und `FIELD_B2`.
  3. **Strikter Peer-Filter (MAC / Handle / UID):** Ein `status:sniff interval:798` im Log gehörte zur parallel verbundenen Smartwatch (`…:b7:21`), während der Stack für die BMW-MAC (`…:e1:b5`) explizit `Unable to set link into sniff mode` meldete.

### Hebel 6: Fehlgeschlagene Lab-Läufe mit dem Referenzcode kreuzen
- **Beobachtung:** In `LAB_SAS_CHALLENGE` passierte nichts, in `LAB_ETCH_REPLY_SRC12` schickte das Handy plötzlich sofort `CLOSE(12, 4004)`.
- **Schlussfolgerung:** Warum reagierte das Handy erst bei `--etch-reply-src 12` überhaupt auf unser Paket? Ein Blick in `BclMultiplexer.kt:50` (`val key = Pair(packet.src, packet.dest)`) bewies: `(src, dest)` darf in Antworten **nicht** umgedreht werden — und das anschließende `CLOSE` bewies, dass unser Etch-Header noch den Request-Hash (`0x304ba8bb`) statt des Reply-Hashes (`0x9c6372b8`) trug.

---

## Teil 2 — Allgemein gültiger Leitfaden: 10 Regeln für Protokoll- & Log-Forensik (mit KI)

Diese zehn Regeln gelten unabhängig von Bluetooth oder BMW für **jedes** Embedded-, USB-, CAN-, Netzwerk- oder proprietäre Binärprotokoll:

1. **Rohdaten schlagen Zusammenfassungen (Anti-Anchoring):** Verbiete der KI, Aussagen wie `UNKNOWN` oder `NOT OBSERVED` ungeprüft aus älteren Projekt-Markdowns zu übernehmen. Jede Behauptung muss per Skript direkt an den Rohlogs/Captures verifiziert werden.
2. **Kein LLM-Augenmaß bei großen Logs — immer ein Parser-Skript schreiben lassen:** Ein Sprachmodell darf ein 15-MB-Log niemals „durchblättern“ oder nur 20 Grep-Zeilen lesen. Es soll ein deterministisches Python-Skript schreiben, das **100 % aller Zeilen/Pakete** parst, zählt und strukturiert ausgibt.
3. **Spezifikation vorwärts kompilieren (Hashes, CRCs, Enums, Magic Bytes):** Suche in Binärprotokollen nie nach ASCII-Funktionsnamen. Berechne aus IDLs, Header-Dateien (`.h`, `.proto`, `.etch`, `.dbc`) oder Referenzcode vorab alle Hashes/IDs und mappe sie maschinell gegen den Dump.
4. **Exakte Byte-Arithmetik statt „ungefähr“:** Behandle jede krumme Zahl (`559`, `645`, `667`, `4008`, `5306`) als mathematischen Fingerabdruck. Prüfe immer `N = k × MTU + Rest` und `Frame = OuterHeader + InnerHeader + Payload + Trailer`. Wenn eine Gleichung auf das **einzelne Byte** aufgeht, ist die Struktur bewiesen.
5. **Zeitdifferenzen (`Δt`) auf Rastersuche prüfen:** Rechne Zeitstempel immer in Deltas um. Exakte Vielfache (`2,999 s` / `3,002 s` oder `2238,78 ms` bei USB-TUR) entlarven sofort Software-Poll-Timer und trennen App-Wartezeiten von echter Hardware-Reaktionszeit (`20 ms`).
6. **Protokollschichten niemals vermischen:** Halte Transport-Fragmentierung (USB-4-KiB-Callback vs. 120-KiB-SCSI-CBW; RFCOMM-667-B-UIH vs. 5306-B-BCL-Frame) strikt getrennt von der Anwendungsnachricht.
7. **Strikte Entitäten-Isolation (Handle / MAC / Port / UID / Bus-ID):** In realen Logs laufen fast immer Störquellen parallel (Smartwatch, zweiter USB-Endpunkt, HFP neben SPP, Post-Finalize-Upload). Jede Auswertung muss zuerst hart nach Peer-Handle/Adresse filtern.
8. **Partielle Daten mit Domänen-Katalogen kreuzen:** Selbst gekappte Logs liefern Längenfelder, Typ-Tags und Präfixe. Gegen ein bekanntes Enum-/Property-Verzeichnis reicht oft schon `(Typ, Länge, 2 Bytes)` für eine 1:1-Identifikation.
9. **Alle Datenquellen im Workspace zusammenführen:** Ein Log allein hat blinde Flecken — die Kombination aus *Geräte-Capture (`.btsnoop`) + Host-Textlog (`BQR`/Stack) + mitgeschnittenen Artefakten (`.pem`) + Referenzcode* schließt fast jede Lücke ohne neue Messung.
10. **Negative Experimente und Abbrüche als Orakel lesen:** Ein `DM`, `ERROR`, `NAK` oder `CLOSE` an einer ganz bestimmten Stelle verrät genau, **welche Prüfregel** der Gegenseite gerade gegriffen hat.

---

## Teil 3 — Wiederverwendbare Prompt-Vorlage für künftige Analysen

Wenn du künftig (egal mit welcher KI) ein neues Log- oder Bus-Problem untersuchst, kannst du diesen Block direkt mitgeben:

```text
Führe eine deterministische Rohdaten-Tiefenanalyse durch. Halte dich strikt an diese Regeln:
1. Übernimm KEINE "UNKNOWN"- oder "nicht beobachtet"-Aussagen ungeprüft aus bestehenden Markdown-Berichten, sondern prüfe die Rohdateien (.log, .btsnoop, .jsonl, .pcap, .pem) selbst per Python-Skript.
2. Suche in Binärdaten nicht nur nach ASCII-Wörtern: berechne aus vorhandenen IDLs/Headern/Sourcen alle Type-IDs, Hashes, Opcodes und Konstanten vorwärts und matche sie gegen alle Hex-Fragmente.
3. Isoliere strikt nach Peer (MAC, Handle, Socket/UID, Bus-Adresse), damit keine Fremdgeräte (z. B. Smartwatch, parallele Profile) eingemischt werden.
4. Nutze Seitenkanäle: stelle Sende-/Empfangslängen und exakte Zeitdeltas (ms) auf eine gemeinsame Achse, prüfe periodische Timer-Raster und rechne krumme Paketgrößen bytegenau gegen Header + MTU-Fragmentierung (N = k * MTU + Rest) nach.
5. Schneide abgeschnittene Felder über (Typ-Tag, exakte Länge, Präfix) gegen bekannte Kataloge im Code.
6. Prüfe auch Diagnose-/Neben-Events im Log (z. B. Quality Reports, HCI-Setup-Events, Fehler-/Close-Codes) und gib jede Erkenntnis mit exaktem Dateinamen, Zeitstempel und Belegstufe an.
```
