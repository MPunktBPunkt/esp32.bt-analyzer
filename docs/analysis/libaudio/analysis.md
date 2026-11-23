Auftrag: Vollständige forensische Analyse von "libaudio.so"

Analysiere die bereitgestellte Datei "libaudio.so" vollständig und systematisch als natives Binary.

Das Ziel ist nicht nur, die bisher bekannte SAS-/APP_AUTH-Frage zu beantworten. Ziel ist, aus der Library ein möglichst vollständiges, wiederverwendbares technisches Modell zu gewinnen, mit dem anschließend auch andere bisher unbekannte Funktionen, Protokolle, Sicherheitsmechanismen, Kommunikationswege, Datenstrukturen und Verhaltensweisen untersucht werden können.

Arbeite wie bei einer forensischen Reverse-Engineering-Untersuchung.

---

0. Grundregeln

Evidenzdisziplin

Jede Aussage muss einer Kategorie zugeordnet werden:

- FACT – direkt aus dem Binary, Disassembly, Daten, XREFs oder reproduzierbarer Analyse belegt.
- INFERENCE – logisch aus mehreren FACTs abgeleitet.
- HYPOTHESIS – plausible, aber noch nicht ausreichend belegte Erklärung.
- UNKNOWN – mit dem aktuellen Material nicht entscheidbar.
- REJECTED – untersuchte Erklärung/Hypothese wird durch die Evidenz widerlegt.

Keine Hypothese darf als FACT formuliert werden.

Wenn eine Funktion nur aufgrund ihres Namens, Strings oder einer ähnlichen API als etwas Bestimmtes interpretiert wird, ist das zunächst höchstens INFERENCE, nicht FACT.

---

1. Binary-Grundinventar

Erstelle zunächst einen vollständigen technischen Fingerabdruck der Datei.

Ermitteln:

- Dateigröße
- SHA-256
- SHA-1 / MD5, falls sinnvoll
- ELF-Klasse
- Endianness
- Architektur
- ABI
- OS/Android-Kontext
- ELF Type
- Entry Point
- Program Header
- Section Header
- Load Segments
- Alignment
- relevante Flags
- SONAME
- benötigte Shared Libraries
- Dynamic Section
- Relocations
- Symboltabellen
- Debug-/Unwind-Informationen
- Build-ID, falls vorhanden
- Compiler-/Linker-Indizien
- Stripped vs. unstripped
- vorhandene Version Sections
- GNU/Android-spezifische ELF-Strukturen

Erstelle daraus einen reproduzierbaren Binary Fingerprint.

Wichtig:

«Nicht nur "file" ausführen und das Ergebnis übernehmen. Die ELF-Struktur muss tatsächlich untersucht werden.»

---

2. Vollständige ELF-Struktur erfassen

Untersuche mindestens:

- ".text"
- ".rodata"
- ".data"
- ".bss"
- ".plt"
- ".got"
- ".got.plt"
- ".dynsym"
- ".dynstr"
- ".rela.*"
- ".eh_frame"
- ".eh_frame_hdr"
- ".init"
- ".fini"
- ".init_array"
- ".fini_array"
- weitere vorhandene Sections

Für jede relevante Section:

- Adresse
- Offset
- Größe
- Flags
- Alignment
- Beziehung zu anderen Sections

Erzeuge daraus eine Memory-/Section-Map.

Ziel:

Es muss später möglich sein, eine Adresse wie "0xbd73c", "0xbdf84", "0x12e564" oder ähnliche Offsets eindeutig einzuordnen.

---

3. Dynamic Linking vollständig rekonstruieren

Analysiere alle Imports und Exports.

Insbesondere:

- libc
- libdl
- pthread
- OpenSSL/BoringSSL
- crypto
- SSL/TLS
- JNI
- Android Runtime
- Binder
- logging
- filesystem
- sockets
- networking
- Bluetooth
- USB
- IPC
- compression
- serialization
- cryptographic APIs

Erstelle eine Liste:

Imported API
    ↓
mögliche Funktionalität
    ↓
XREFs / Call Sites
    ↓
konkrete Verwendung
    ↓
Evidenzstatus

Nicht aus dem Importnamen allein auf die tatsächliche Verwendung schließen.

---

4. String-Forensik

Extrahiere alle relevanten Strings, nicht nur offensichtliche Fehlermeldungen.

Kategorien bilden:

A. Security

Beispiele:

- certificate
- security
- challenge
- signature
- RSA
- AES
- MD5
- SHA
- PKCS
- SSL
- key
- private/public
- credential
- authentication
- authorization
- trust
- verify
- sign

B. Kommunikation

- Bluetooth
- RFCOMM
- SPP
- socket
- TCP
- UDP
- HTTP
- HTTPS
- Binder
- IPC
- USB
- AOA
- Android

C. BMW / Connected / RHMI / Etch

- BMW
- Connected
- AAIdrive
- RHMI
- Etch
- BCL
- SAS
- APP_AUTH
- AudioModule
- SecurityModule
- Media
- Music
- CDS
- AM

D. Dateien / Ressourcen

- XML
- JSON
- protobuf
- SQLite
- assets
- resource
- cache
- config
- certificate files
- keystore
- PKCS#12
- PFX

E. Debugging / Fehler

- Error
- Warning
- failed
- invalid
- rejected
- exception
- timeout
- retry

Für jeden interessanten String:

1. Adresse
2. Section
3. XREFs
4. referenzierende Funktionen
5. Call-Graph-Kontext
6. mögliche Bedeutung
7. Evidenzstatus

---

5. Funktionsinventar rekonstruieren

Auch wenn das Binary stripped ist:

Rekonstruiere so weit wie möglich alle Funktionen.

Für jede Funktion erfassen:

- Startadresse
- Endadresse
- Größe
- Name, falls vorhanden
- rekonstruierter Name, falls unbekannt
- XREFs
- Caller
- Callees
- verwendete Strings
- verwendete globale Variablen
- verwendete Imports
- Speicherzugriffe
- Return Values
- Parameter
- mögliche Seiteneffekte
- Evidenzstatus

Wenn ein automatischer Decompiler Namen erzeugt, diese klar von echten Symbolnamen unterscheiden.

Beispiel:

FUN_000BD73C

ist nicht automatisch

native_sign_impl()

Der rekonstruierte Name muss begründet werden.

---

6. Call-Graph rekonstruieren

Erstelle einen möglichst vollständigen Call-Graph.

Besonders interessant:

- JNI Entry Points
- Java → Native Übergänge
- Native → Crypto
- Native → Network
- Native → Filesystem
- Native → IPC
- Native → Security
- Native → Audio
- Native → RHMI/Etch/BCL

Suche nach zentralen Gatekeeper-Funktionen.

Typische Kandidaten:

initialize
create
open
connect
authenticate
authorize
start
stop
send
receive
sign
verify
encrypt
decrypt
load
save
get
set
dispatch
callback

Ziel:

Nicht nur einzelne Funktionen verstehen, sondern die Architektur der Library rekonstruieren.

---

7. JNI- und Java-Native-Grenze

Falls JNI vorhanden ist:

Rekonstruiere vollständig:

Java/Kotlin
    ↓
JNI registration
    ↓
native function
    ↓
native subsystem

Identifiziere:

- "JNI_OnLoad"
- "RegisterNatives"
- JNI Method Names
- Method Signatures
- Java-Klassen
- native entry points
- Java → native Parameter
- native → Java Callbacks

Wenn möglich, rekonstruiere daraus die öffentliche Native API der Library.

---

8. Globale Daten und State Machines

Suche nach:

- globalen Variablen
- Singleton-Strukturen
- Context Objects
- Security Objects
- Session Objects
- Audio Objects
- Connection Objects
- Callback Tables
- Function Pointer Tables
- VTables
- State Variables

Besonders wichtig:

Welche Funktionen lesen und schreiben dieselben Speicherbereiche?

Erstelle bei interessanten Globals:

Global
  ↓
Writer(s)
  ↓
Reader(s)
  ↓
Function context
  ↓
Lifecycle

Damit sollen interne Objektstrukturen und State Machines rekonstruiert werden.

---

9. Datenstrukturen rekonstruieren

Versuche aus den Speicherzugriffen C-artige Strukturen abzuleiten.

Beispiel:

struct SecurityContext {
    ...
};

Aber nur als rekonstruierte Struktur kennzeichnen.

Für jede vermutete Struktur:

- Basisadresse
- Felder
- Offsets
- Feldgröße
- Reader
- Writer
- Initialisierung
- Lebensdauer
- Evidenz

Besonders untersuchen:

- "global + offset"
- Pointer Chains
- "malloc/new"
- "memcpy"
- "memset"
- Strukturkopien
- Pointer auf OpenSSL/BoringSSL Objekte

---

10. Kryptographie vollständig inventarisieren

Dies ist ein eigener Analyseblock.

Suche nicht nur nach Strings, sondern nach tatsächlichen Crypto-Operationen.

Erfassen:

Hashing

- MD5
- SHA-1
- SHA-256
- SHA-384
- SHA-512
- HMAC

Public Key

- RSA
- ECDSA
- ECDH
- DH
- Ed25519 etc.

Symmetrisch

- AES
- DES/3DES
- ChaCha20
- GCM
- CBC
- CTR
- ECB

Encoding

- Base64
- ASN.1
- DER
- PEM
- PKCS#1
- PKCS#7
- PKCS#8
- PKCS#12
- CMS
- X.509

Für jede Crypto-Operation:

Input
 ↓
Transformation
 ↓
Crypto primitive
 ↓
Output

rekonstruieren.

---

11. Schlüsselmaterial untersuchen

Suche nach:

- RSA Public Keys
- RSA Moduli
- EC Public Keys
- Zertifikaten
- DER
- PEM
- PKCS#12
- PFX
- private-key-Strukturen
- ASN.1-Strukturen
- verschlüsseltem Keymaterial
- Passphrasen
- Key aliases
- Key IDs
- Certificate fingerprints

Wichtig:

Nicht automatisch jedes gefundene Keymaterial demselben Protokoll zuordnen.

Für jeden Key:

Key/Object
    ↓
Format
    ↓
Algorithmus
    ↓
Key size
    ↓
XREFs
    ↓
Verwendung
    ↓
konkrete Operation
    ↓
Protokollzuordnung

---

12. Security-/SAS-Pfad gezielt untersuchen

Erst nachdem die allgemeine Architektur erfasst wurde, die bisher bekannte SAS-Spur überprüfen.

Ausgangspunkt:

SecurityModule.signChallenge()
        ↓
AudioModule.g()
        ↓
native signing path
        ↓
EVP_PKEY*
        ↓
EVP_PKEY_sign / EVP_SignFinal

Untersuche insbesondere:

createSecurityContext
        ↓
Security Object
        ↓
global + 0x108
        ↓
EVP_PKEY*

Zu beweisen oder zu widerlegen:

1. Existiert dort tatsächlich ein "EVP_PKEY"?
2. Welche Key Size?
3. Ist es RSA?
4. Sind es 512 Byte / RSA-4096?
5. Stimmt der Modulus mit dem Feld-APP_AUTH-SPKI überein?
6. Woher stammt der Key?
7. Wird er aus einem eingebetteten Objekt geladen?
8. Gibt es einen externen Signer?
9. Gibt es Keystore/TEE/Binder?
10. Gibt es mehrere alternative Signer?

---

13. SAS-Algorithmus unabhängig rekonstruieren

Suche im Binary nach der tatsächlichen Berechnung:

CertificateType
        ↓
MD5(CertificateType)
        ↓
Challenge XOR Pad
        ↓
MD5(...)
        ↓
RSA PKCS#1 v1.5
        ↓
DigestInfo-MD5
        ↓
Signature

Insbesondere überprüfen:

0x02000000

und die genaue Byte-Reihenfolge.

Ziel ist eine Binary-basierte Rekonstruktion, nicht nur die Bestätigung bereits bekannter Wire-Daten.

---

14. Alle Kommunikationspfade untersuchen

Nicht nur SAS.

Suche nach:

Bluetooth

- RFCOMM
- SPP
- L2CAP
- sockets
- channel numbers
- Bluetooth UUIDs

Netzwerk

- TCP
- UDP
- HTTP
- HTTPS
- DNS
- IP/Port-Konstanten

Android IPC

- Binder
- AIDL
- Parcel
- Intent
- Service
- ContentProvider

USB

- USB descriptors
- AOA
- accessory
- bulk endpoints
- control transfers

BMW-spezifisch

- BCL
- Etch
- RHMI
- CDS
- AM
- SAS

Für jeden Kommunikationspfad:

Endpoint
 ↓
Transport
 ↓
Framing
 ↓
Message construction
 ↓
Parser
 ↓
State machine

rekonstruieren.

---

15. Protokoll-Parser und Message Builder finden

Suche nach:

- festen Message IDs
- Magic Values
- Length Fields
- Type Fields
- Command IDs
- Event IDs
- TLV-Strukturen
- Switch/dispatch tables
- Parsern
- Serializern
- Byte-Buffer-Manipulation

Besonders interessant:

switch(command)
switch(message_id)
switch(event_id)

Diese können unbekannte Protokollfunktionen sichtbar machen.

---

16. Audio-/Media-Funktionalität vollständig untersuchen

Da es "libaudio.so" ist, darf nicht angenommen werden, dass die Library ausschließlich Security enthält.

Untersuche:

- Audio Sessions
- Player
- Decoder
- Metadata
- Media controls
- playback state
- volume
- track state
- source selection
- callbacks
- media browsing
- RHMI Music
- Bluetooth audio
- USB/media integration

Ziel:

Eine tatsächliche Funktionslandkarte der Library erstellen.

---

17. Ressourcen und eingebettete Dateien

Suche nach eingebetteten:

- Zertifikaten
- XML
- JSON
- Strings
- Konfigurationen
- Audio-/Media-Daten
- Protobuf-Schemas
- ASN.1
- Keys
- Tabellen
- Kompressionsblöcken

Auch nach komprimierten oder verschleierten Daten suchen.

Wenn ein Bereich verdächtig aussieht:

1. Offset
2. Größe
3. Entropie
4. mögliche Signatur/Magic
5. Dekodierungsversuch
6. XREFs
7. Ergebnis

---

18. Obfuscation / Packing / Verschlüsselung

Prüfen:

- String Obfuscation
- Control-Flow Obfuscation
- Function Flattening
- Packed Sections
- XOR encoded data
- encrypted constants
- runtime decoding
- dynamic symbol resolution
- "dlopen"
- "dlsym"
- selbstmodifizierenden Code

Wenn vorhanden:

verschlüsselter Bereich
    ↓
Decoder
    ↓
Key
    ↓
Runtime-Struktur
    ↓
Verwendung

rekonstruieren.

---

19. Automatische Analysetools kombinieren

Verwende mehrere unabhängige Werkzeuge, soweit verfügbar, z.B.:

- "file"
- "readelf"
- "objdump"
- "nm"
- "strings"
- "xxd"
- "radare2" / "rizin"
- Ghidra
- Binary Ninja
- IDA
- Python-Skripte
- Capstone
- LIEF
- pyelftools

Nicht blind einem Tool vertrauen.

Wenn Ghidra beispielsweise eine Funktion falsch erkennt, anhand von Disassembly/XREFs prüfen.

---

20. Ghidra-Projekt sauber strukturieren

Falls Ghidra verwendet wird:

- Binary importieren
- korrekte Architektur prüfen
- Auto Analysis durchführen
- Function Signatures prüfen
- Strings/XREFs analysieren
- Imports/Exports prüfen
- Function Graphs erzeugen
- Decompiler überprüfen
- wichtige Funktionen umbenennen
- Strukturen definieren
- Kommentare mit Evidenz versehen

Wichtig:

Namen wie

FUN_00123456

dürfen erst nach ausreichender Evidenz in einen semantischen Namen geändert werden.

Beispiel:

FUN_00123456
→ candidate_sign_challenge
→ native_sign_challenge
→ APP_AUTH_RSA4096_sign

Die jeweils höhere Spezifität erst dann verwenden, wenn sie belegt ist.

---

21. Cross-Reference-Matrix

Erstelle eine zentrale Matrix:

Objekt| Adresse| Typ| XREFs| Funktion| Verwendung| Evidenz
String| ...| string| ...| ...| ...| FACT
Key| ...| RSA| ...| ...| ...| FACT
Function| ...| native| ...| ...| ...| FACT
Global| ...| pointer| ...| ...| ...| INFERENCE

Damit soll später jede wichtige Erkenntnis rückwärts auf das Binary zurückgeführt werden können.

---

22. Architekturmodell erstellen

Am Ende der Analyse eine Gesamtarchitektur rekonstruieren:

Java / Kotlin
      │
      ▼
JNI
      │
      ▼
libaudio.so
      │
 ┌────┼──────────────┐
 ▼    ▼              ▼
Audio Security   Communication
 │      │              │
 │      │         Bluetooth / IPC /
 │      │         Network / USB
 │      │
 ▼      ▼
Media  Crypto
              │
              ▼
          Key Material

Die tatsächliche Architektur muss aus den Befunden entstehen und darf nicht einfach dieses Beispiel übernehmen.

---

23. Fragen beantworten, die wir heute noch gar nicht gestellt haben

Nach Abschluss der strukturellen Analyse ausdrücklich fragen:

«Welche Fähigkeiten des Binary sind bisher in unseren Untersuchungen überhaupt nicht berücksichtigt worden?»

Suche insbesondere nach:

- unbekannten Protokollen
- unbekannten Zertifikaten
- unbekannten Keys
- alternativen Authentifizierungswegen
- alternativen Signern
- versteckten Kommunikationskanälen
- zusätzlichen Message IDs
- weiteren RHMI-/Etch-Funktionen
- unbekannten State Machines
- Debug-/Testmodi
- Feature Flags
- Konfigurationsschaltern
- Fallback-Verhalten
- Offline-Modi
- Caches
- Credential Stores
- Provisioning
- Update-/OTA-Funktionen

---

24. Bestehende Erkenntnisse gegen das Binary validieren

Die bereits bekannten Erkenntnisse dürfen nicht einfach übernommen werden.

Für jede bisherige Aussage:

Bisherige Behauptung
        ↓
Binary-Evidenz?
        ↓
JA → bestätigt / präzisiert
NEIN → weiterhin extern belegt
Widerspruch → untersuchen

Insbesondere prüfen:

- "SecurityModule.signChallenge()"
- "AudioModule.g()"
- "native_sign_impl"
- "EVP_PKEY_sign"
- eingebettetes PKCS#12
- RSA-4096
- APP_AUTH
- "0x02000000"
- MD5
- Challenge XOR
- "createSecurityContext"
- "global + 0x108"
- "0x19e494"
- "0xbdf84"
- "0x12e564"
- Feature-PFX bei "0x5249e"

Bereits REJECTED Hypothesen nicht ohne neue Evidenz wiederbeleben.

---

25. Explizite Trennung der Key-/PKI-Welten

Besonders wichtig:

Nicht automatisch folgende Dinge zusammenwerfen:

APP_AUTH RSA-4096
Feature-PKI RSA-1536
CMS/PKCS#7
PFX/PKCS#12
X.509 certificates
Keystore/TEE
Remote signer

Für jedes Key-/Certificate-Objekt eine eigene Identität vergeben.

Erst über:

- Modulus
- Key Size
- Algorithmus
- XREF
- Verwendung
- Signaturformat
- Zertifikatszuordnung

eine Verbindung herstellen.

---

26. Negative Analyse

Suche ausdrücklich nach Dingen, die nicht vorhanden sind.

Beispiele:

- kein Binder-Pfad
- kein Keystore-Pfad
- kein Network-Pfad
- kein Private-Key
- kein RSA-4096
- kein bestimmter Algorithmus
- kein bestimmter Message Type

Aber:

«„Nicht gefunden“ ist nur dann ein belastbares REJECTED/NEGATIVE-EVIDENCE-Ergebnis, wenn die Suchabdeckung ausreichend dokumentiert wurde.»

Sonst:

UNKNOWN.

---

27. Ergebnisformat

Erstelle am Ende mindestens folgende Ergebnisse.

A. Executive Summary

Maximal wenige Seiten:

- Was ist "libaudio.so"?
- Welche Hauptkomponenten enthält sie?
- Welche Kommunikationswege?
- Welche Security-Funktionen?
- Welche Audio-/Media-Funktionen?
- Welche Keys/Zertifikate?
- Welche Protokolle?
- Welche überraschenden Funde?
- Welche bisher unbekannten Fähigkeiten?

---

B. Binary Fingerprint

Alle technischen Basisdaten.

---

C. Architektur

Gesamtarchitektur mit Komponenten und Abhängigkeiten.

---

D. Function Map

Die wichtigsten Funktionen mit:

- Adresse
- Name
- Zweck
- Caller/Callee
- Evidenz

---

E. Security Map

Certificate
Key
Signer
Verifier
Challenge
Hash
Signature
Transport
Acceptance

---

F. Communication Map

Alle gefundenen Kommunikationswege.

---

G. Protocol Map

Alle gefundenen Message-/Command-/Event-Strukturen.

---

H. Key/Certificate Inventory

Für jedes Objekt:

- Offset/Adresse
- Format
- Algorithmus
- Key Size
- Fingerprint
- Verwendung
- XREF
- Evidenz

---

I. Unknowns / Open Questions

Nur echte offene Fragen.

---

J. Rejected Hypotheses

Alle belastbar widerlegten Erklärungen mit Begründung.

---

K. New Discoveries

Explizit alles aufführen, was vor Beginn der Analyse nicht bekannt war.

---

28. Wichtigstes Endergebnis: wiederverwendbares Analysemodell

Die Untersuchung soll nicht in einem einmaligen Bericht enden.

Erzeuge ein Modell, mit dem wir später Fragen stellen können wie:

Wo werden Zertifikate verarbeitet?

Welche Funktion signiert Daten?

Welche Funktion verifiziert Signaturen?

Welche RSA-Keys existieren?

Welche Funktionen kommunizieren über Bluetooth?

Welche Message IDs kennt die Library?

Welche Funktionen hängen von RHMI ab?

Welche Funktionen hängen von Etch ab?

Welche Funktionen können ohne Netzwerk arbeiten?

Wo werden Credentials geladen?

Welche Daten werden persistent gespeichert?

Welche unbekannten Features gibt es?

Welche Funktionen könnten für AOA relevant sein?

Welche Funktionen könnten für iAP2 relevant sein?

Welche Funktionen könnten für Connected Music relevant sein?

Welche Funktionen könnten für SAS relevant sein?

Jede Antwort muss auf konkrete Binary-Evidenz zurückführbar sein.

---

29. Abschlussprüfung

Bevor die Analyse als abgeschlossen gilt, prüfe:

Binary Coverage

- [ ] ELF vollständig untersucht
- [ ] Sections untersucht
- [ ] Imports untersucht
- [ ] Exports untersucht
- [ ] Strings untersucht
- [ ] XREFs untersucht
- [ ] Funktionen inventarisiert
- [ ] Call Graph untersucht
- [ ] Globals untersucht
- [ ] Datenstrukturen untersucht
- [ ] JNI untersucht
- [ ] Ressourcen untersucht

Security Coverage

- [ ] Crypto APIs
- [ ] Zertifikate
- [ ] Keys
- [ ] Signer
- [ ] Verifier
- [ ] Key Loading
- [ ] Keystore/TEE/Binder
- [ ] PKCS#12/PFX
- [ ] X.509
- [ ] RSA
- [ ] Hashing

Communication Coverage

- [ ] Bluetooth
- [ ] RFCOMM/SPP
- [ ] Network
- [ ] IPC
- [ ] Binder
- [ ] USB/AOA
- [ ] BCL
- [ ] Etch
- [ ] RHMI

Protocol Coverage

- [ ] Parser
- [ ] Serializer
- [ ] Message IDs
- [ ] Event IDs
- [ ] State Machines
- [ ] Dispatch Tables

Forensic Quality

- [ ] FACT/INFERENCE/HYPOTHESIS/UNKNOWN/REJECTED getrennt
- [ ] Jede wichtige Aussage auf Binary-Evidenz zurückführbar
- [ ] keine ungeprüfte Namensinterpretation
- [ ] keine Vermischung verschiedener Key-/PKI-Systeme
- [ ] negative Evidenz dokumentiert
- [ ] bisherige Hypothesen erneut validiert
- [ ] neue Erkenntnisse explizit identifiziert
- [ ] verbleibende Unknowns explizit dokumentiert

---

30. Besonders wichtig

Nicht nach einem ersten Treffer aufhören.

Wenn beispielsweise der SAS-Signer gefunden wurde, ist die Untersuchung nicht abgeschlossen.

Der SAS-Signer ist nur ein Teil der Library.

Das eigentliche Ziel ist:

«Die interne technische Landkarte von "libaudio.so" so weit wie möglich zu rekonstruieren, sodass wir anschließend nicht mehr primär raten müssen, welche Funktion oder welches Protokoll relevant sein könnte, sondern gezielt aus dem Binary heraus neue Untersuchungen starten können.»

Priorität:

Binary verstehen
      ↓
Architektur verstehen
      ↓
Datenflüsse verstehen
      ↓
Security verstehen
      ↓
Kommunikation verstehen
      ↓
Protokolle verstehen
      ↓
State Machines verstehen
      ↓
unbekannte Fähigkeiten entdecken
      ↓
gezielte Hypothesen testen
      ↓
Feld-/Laborexperimente ableiten

Keine unnötige Dokumentation erzeugen, die lediglich bereits vorhandene Erkenntnisse dupliziert.

Erst analysieren, dann dokumentieren.
Die Dokumentation muss das Ergebnis der Analyse sein, nicht deren Ersatz.
