# Technischer Gesamtbericht — RHMI Resource-Lifecycle Audit (2026-11-17)

**claim_level:** LAB/STRONG für Mechanismus-Trennung (BimmerGestalt) · FIELD für Stack bis AM/RHMI/CDS · OPEN für F20-Folge nach `checkResource(true)`  
**Quellen:** Audit A — IDriveConnectKit / AAIdrive · Audit B — esp32.bt-analyzer / F20 Connected Stack  
**Korrektur an:** P0–P2 Phone-Sim Annahme `checkResource → immer setResource`

## 1. Executive Summary

Der Connected-/RHMI-Stack ist weitgehend verstanden und im Labor reproduzierbar. Eine zentrale Annahme war falsch:

```text
checkResource(true) → setResource → initialize
```

ist **keine** zwingende Sequenz. Drei Mechanismen sind zu trennen:

| Mechanismus | Rolle |
|-------------|--------|
| `checkResource` | Cache-/Existenzprüfung |
| `verifyResource` / `SAS.Digests.*` | Autorisierung über Zertifikats-Digests |
| `setResource` | tatsächlicher Upload |

**Folge:** `checkResource(true)` kann bedeuten „bereits vorhanden“ → Client geht zum nächsten Typ oder zu `rhmi_initialize`. Fehlendes `setResource` ist **nicht** automatisch ein Fehler.

Der Watchdog-Abbruch im USB→Air→F20-Pfad ist damit **noch nicht** auf fehlenden Resource-Upload zurückgeführt. Nächster Feldtest: vollständige Resource-State-Machine aufzeichnen, nicht künstlich `setResource` erzwingen.

## 2. Audit-Umfang

**Audit A — BimmerGestalt RHMI-Resource-Lifecycle:** IDriveConnectKit, AAIdrive, check/set/verifyResource, Zertifikats-Digests, Screen-Mirror/Multimedia.

**Audit B — esp32.bt-analyzer / F20:** epistemische Stufen FIELD / LAB / STRONG / OPEN. Belegt: RFCOMM SCN6 → BCL → Etch → SAS → AM / RHMI / CDS.

## 3. Drei getrennte Mechanismen

### 3.1 checkResource

Parameter typisch: `handle`, `hash`, `size`, `name`, `type`.  
`true` = im Cache / verfügbar · `false` = Upload möglicherweise nötig.  
Primär Cache-/Existenzprüfung.

BimmerGestalt (`RHMIUtils.rhmi_setResourceCached`): MD5-Hash → `checkResource`; nur bei `!cached` → `setResource`.

### 3.2 verifyResource / SAS.Digests.*

Autorisierung separat: APP-Zertifikat → `SAS.Digests.RHMIDescriptions` / `ImageDatabases` / `TextDatabases` → verify. Nicht mit Cache-Status verwechseln.

### 3.3 setResource

Nur bei tatsächlichem Uploadbedarf (`handle`, `data`, `type`).

## 4. Mögliche Sequenzen

**Fall A — alles cached:**  
`checkResource(DESCRIPTION|TEXTDB|IMAGEDB) → true` → `rhmi_initialize` → `setData` (kein setResource).

**Fall B — Miss:**  
pro Typ `false` → `setResource` → weiter → `initialize` → `setData`.

**Fall C — Reject:**  
nicht autorisiert / inkonsistent → `ServiceException` / Abbruch.

AAIdrive-Feldmuster (`NotificationApp`): DESCRIPTION → TEXTDB → IMAGEDB → `initialize`.

## 5. Neubewertung Watchdog-Abbruch (USB→.131)

Ungültig: `checkResource(true) → setResource fehlt → Watchdog`.

Mögliche Ursachen u. a.: nächster check fehlt/falsch, Decode/`messageId`/`_inReplyTo`, Etch-Kanal, `initialize` nicht ausgelöst, Frame-Verlust, WD während Lifecycle, setResource trotz Hit oder trotz Miss unterlassen.

**Befund:** USB→Air erreicht Resource-Prüfung; RHMI-State-Machine danach noch nicht stabil bis initialize/setData.

## 6. Systemstand (kompakt)

| Pfad | Stand |
|------|--------|
| F20 Feld BT→BCL→Etch→SAS→AM/RHMI/CDS | FIELD-MEASURED |
| Lab f20_sim Cache-Miss→setResource→init→setData | LAB PASS |
| USB→.131→Air bis checkResource | PARTIAL (WD abort; Kausalität OPEN) |
| Dual-ESP `.87`↔`.131` | FAIL / sekundär |

## 7. Pfade trennen

- **Pfad A (Prio):** USB → `.131` → Air → F20 — Menü bis Action  
- **Pfad B:** `.87` ↔ `.131` — Inquiry/ACL/SDP/RFCOMM Relay  

## 8. Nächster Testplan W0–W5

| Step | Ziel |
|------|------|
| **W0** | Air-Watchdog über gesamten Resource-Lifecycle stabil |
| **W1** | Vollständige checkResource-Sequenz (DESCRIPTION/TEXTDB/IMAGEDB/…) inkl. messageId/inReplyTo |
| **W2** | setResource **nur** bei `result=false`; bytegenau vs Digest |
| **W3** | `rhmi_initialize` korreliert |
| **W4** | eigener `setData`-String (Lab-modelId z. B. 447 ≠ universelle F20-ID) |
| **W5** | Action/Event → PiDrive |

## 9. Lab-Empfehlungen (kurz)

Zustandsmaschine (DISCONNECTED…ACTION_EVENT); Cache vs Authorization entkoppeln; Transaction-Log; Strict/Auth/Replay-Modi; Negative Tests + Fault Injection.  
**Nicht:** freie Ressourcen als F20 markieren, Keys exportieren, SAS-Bypass, Lab-Erfolg als Feldbeweis.

## 10. Statusmatrix

| Ebene | Status |
|-------|--------|
| Pairing/ACL/SDP/RFCOMM6/BCL/WD/Etch/SAS/AM/RHMI/CDS | FIELD-MEASURED |
| RHMI-Resource-Cache-Lifecycle F20 | teilweise |
| checkResource(true)-Folge / setResource-Bedingung F20 | OPEN |
| initialize / eigener setData / Action am USB→Air | OPEN |
| Simulator-Lifecycle | LAB PASS |
| Dual-ESP Relay | FAIL/sekundär |

## Fazit

Wert des Audits = Korrektur des Resource-Lifecycle-Modells, keine neue Protokollschicht.  
Nächste Reihenfolge strikt W0→W5. Erster Menü-Proof bleibt: F20 Lifecycle → initialize → eigener setData → sichtbar → Action → Pi.
