# Lab Home Live — Tiefenanalyse 2026-11-21

```yaml
datum: 2026-11-21 (Abend ~19:20–20:10 CET)
topology: OnePlus 12 AC:C0:48:5E:CB:20 → ESP .131 C8:C9:A3:CB:7B:0A → .108 f20_sim
claim_level: LAB FACT (unless marked INFERENCE)
bt_stack: CLOSED — no stack widening
upstream:
  - BT_CONTROL_PLANE_CLOSED_20261121.md
  - MUSIC_NP_SPINE_LAB_STUB_20261121.md
  - LAB_MUSIC_NP_SPINE_SEQ_DUAL_20261121T133709Z (Dual-ESP stub PASS earlier same day)
evidence:
  - docs/evidence/LAB_HOME_20261121T1840Z/
  - docs/evidence/LAB_HOME_20261121T1900Z/
  - docs/evidence/LAB_MUSIC_NP_LIVE_INJECT_20261121T1909Z/
```

## 1. Executive verdict

| Frage | Antwort |
|-------|---------|
| Kann Live-AAIdrive gegen `f20_sim` auf `7B:0A` grün werden? | **Ja — LAB FACT** |
| Ist der Music-NP-Spine (445–447) live befüllt? | **Ja — LAB FACT** (Handle-23 Modelle) |
| Reicht Description-Action-Inject (336/248) für Live-Ack? | **Nein — LAB FACT** (TX ok, 0 `rhmi_ackActionEvent`) |
| Dual-ESP Stub Music NP Spine? | **PASS** (früher am Tag, separat) |
| Blockiert etwas den Control Plane? | **Nein** — Bleibt CLOSED |

**Handoff:** Nächster wertvoller Schritt ist **ein F20-Field-Lauf** für sichtbares/interaktives NP — nicht mehr Lab-Action-ID-Raten, nicht iDriveSim parallel zu Lab-ch6.

---

## 2. Timeline (Operator + Wire)

| Zeit (CET) | Ereignis |
|------------|----------|
| ~19:20 | iDriveSim-Bridge gestoppt/disabled; ch6 für Lab freigegeben; CSR zweites BMW powered-off |
| 19:28 | `f20_sim` HU-Agent start; SPP registered |
| 19:28–19:33 | Nur `knock_envelope` (56 B) → close; **kein** BCL `12345678` |
| 19:34 | busctl Disconnect/Connect → INIT → HS → SAS → **AAIdrive grün** |
| 19:35–19:40 | Erste stabile Session; AM inkl. **screenmirror**; Music NP 3 Doors Down / Kryptonite |
| 19:40 | Evidence-Pull `LAB_HOME_20261121T1840Z` |
| 19:43 | Operator: Testbenachrichtigung — App `notification.readout` + DESCRIPTION/popupEvents geladen; **kein** decoded Test-Text / kein `rhmi_triggerEvent`-Popup-Nachweis |
| 19:45:23 | RFCOMM **`write_error:11`** unter Resource-Flut → Session tot |
| 19:46–19:55 | Mehrere Reconnects; screenmirror oft weg; Music/Mapview RHMI wieder da |
| 19:54 | Mapview/Music Description-Action-Inject — TX, kaum App-Reaktion |
| 19:57 | HU-Agent-Restart (Inject-API `am_onAppEvent` / `onHmiEvent`); kurz grau |
| 19:58–20:00 | Reconnect → grün; NP = BFMV / The Poison / Tears Don't Fall |
| 20:08 | Live Music-NP Inject 336+248 + HMI focus — **TX, 0 Acks** |
| 20:09 | Evidence `LAB_MUSIC_NP_LIVE_INJECT_…` |

---

## 3. Quantitative Auswertung

### 3.1 Session-Fenster

| Artifact | Span | HS | SAS OK | `f20_rpc` | RFCOMM open/close | Fatal close |
|----------|-----:|---:|-------:|----------:|------------------:|-------------|
| T1840 pull | 678 s | 1 | 10 | 726 | 16/16 | eof only |
| T1900 pre-restart | 1703 s | 5 | 50 | 1995 | 24/24 | **write_error:11** ×1 |
| T1900 post-restart | 201 s | 1 | 11 | 1550 | 1/0 | none |

### 3.2 Music NP models (Handle-23 Schnittmenge)

| Fenster | 444 | 445 | 446 | 447 | Beispiel |
|---------|----:|----:|----:|----:|---------|
| T1840 | 0 | 44 | 44 | 44 | 3 Doors Down / The Better Life / Kryptonite |
| T1900 pre | 0 | 89 | 89 | 89 | + Anthrax / Got The Time |
| T1900 post | 0 | 135 | 135 | 135 | BFMV / The Poison / Tears Don't Fall |
| Live inject @20:08 | — | — | — | — | NP-Updates im Watch-Fenster ausgesetzt |

**FACT:** Live-AAIdrive befüllt **445/446/447** kontinuierlich. **444** (source) in diesen Captures **nicht** als String-`setData` gesehen (INFERENCE: ungenutzt, anders kodiert, oder selten).

### 3.3 AM registrations (unique über Abend)

- Assistants: Google + Alexa  
- `io.bimmergestalt.idriveconnectaddons.screenmirror` (nur frühe Fenster)  
- YouTube + Bluetooth media helpers  
- `notifications` / `notification.readout`  
- Packages ohne AM: `mapview`, `music`, `calendar` (RHMI-only auf eigenen Etch-srcs)

### 3.4 Etch src → Rolle (typisch, post-restart)

| src | Rolle |
|----:|-------|
| 14 | notification.readout |
| 15 | calendar |
| 16 | assistant |
| 17 | mapview |
| 18 | notifications |
| 19 | music (+ YT/BT AM) |

---

## 4. Root-Cause-Analyse der Störungen

### 4.1 Knock-only ohne INIT (vor 19:34)

**Symptom:** RFCOMM accept → 56 B `deadbeef`+UUID `0e9b90c4-…` → eof; 0× `12345678`.

**Ursache (LAB FACT + Ops):** SPP kam erst nach ACL-Connect; Phone-Probe ohne vollen BCL-Client. Nach forced Disconnect/Connect: normales INIT→HS.

**Regel:** Nach HU-Agent-Start ACL neu aufbauen (oder Apps force-stop), sonst bleibt AAIdrive grau trotz „connected“.

### 4.2 `write_error:11` (19:45:23)

**Symptom:** TX EAGAIN-Kaskade → `tx_write_failed` → RFCOMM close während paralleler `setResource` (DESCRIPTION/IMAGEDB) mehrerer Apps.

**INFERENCE:** Host/ESP-HCI-Pfad sättigt unter Multi-App-Resource-Burst; nicht Auth-Fail.

**Mitigation (bereits im Dual-ESP Spine):** `BCL_RHMI_CACHE_HIT=1` + Digest-Seed (vermeidet 92 KiB DESCRIPTION-Upload).

### 4.3 iDriveSim „Verbindungsprobleme“

**Ursache (LAB FACT):** Absichtlich Lab-Modus — `idrivesim-rfcomm-bridge` disabled, `bcl_dummy_hu_agent` besitzt ch6 host-global, Web :38304 gestoppt.  
Zusätzlich historisch: `Address already in use` + DBus `org.idrivesim.SppProfile` AccessDenied (Warnung, SPP registrierte trotzdem).

**Lösung:** xor-Umschaltung laut `LAB_IDRIVESIM_SWITCH_20261119.md` — **nicht** parallel zu Lab.

### 4.4 Screenmirror / Mapview „starten“

| Versuch | Ergebnis |
|---------|----------|
| Screenmirror starten | Oft kein `am_registerApp` nach Flaps → nicht startbar |
| Mapview Description-Actions (164…) | TX, 1× `setProperty`, kein Ack |
| Music Description-Actions + 336/248 | TX, **0 Ack** auf Live-AAIdrive |
| Dual-ESP stub spine (früher) | **PASS** inkl. Ack/Sink |

**INFERENCE:** Live-Phone-Ack-Pfad ≠ Stub-PhoneClientSession; Description-raAction-IDs allein sind kein zuverlässiger „App starten“-Hebel. Braucht vermutlich echten AM-Focus (`am_onAppEvent`) *wenn* registriert, oder F20-seitig sichtbare NP ohne Fake-Click.

### 4.5 Testbenachrichtigung

Notification-App + popup DESCRIPTION geladen; **kein** Klartext „Test“ / kein nachweisliches Popup-Trigger im jsonl. UI-seitige Benachrichtigung ≠ Wire-FACT ohne `setData`-String oder `triggerEvent`-Decode.

---

## 5. Tooling-Änderungen (dieser Abend)

`bcl_dummy_hu.py` / `bcl_dummy_hu_agent.py`:

- Inject **`_rhmi_hmi`** → `rhmi_onHmiEvent`
- Inject **`_am_event`** → `am_onAppEvent`
- Bestehendes `_rhmi_action` unverändert nutzbar

Live-Validierung: Action/HMI-TX geloggt; AM-Event auf Live-Session noch nicht erfolgreich für App-Start genutzt (screenmirror fehlte).

---

## 6. Epistemik / Claims

| Claim | Level |
|-------|-------|
| OnePlus ↔ f20_sim `7B:0A` AAIdrive grün nach ACL-Rediscover | **LAB FACT** |
| Music NP models 445–447 live von AAIdrive | **LAB FACT** |
| Model 444 absent in captures | **LAB FACT** (Abwesenheit) |
| Screenmirror AM intermittent | **LAB FACT** |
| `write_error:11` beendet Session unter Resource-Flut | **LAB FACT** |
| Live 336/248 ohne Ack | **LAB FACT** |
| Dual-ESP Music NP Spine PASS | **LAB FACT** (andere Topology, früher) |
| Live braucht `am_onAppEvent` für App-Start | **INFERENCE** |
| Nächster Schritt = F20 Field NP visibility | **PLAN** (aligned control-plane closed) |

---

## 7. Next (eng)

1. **F20 Field:** eine Variable — sichtbares/interaktives Music-NP mit Spine-IDs (nicht „BT tot?“).  
2. Lab optional: Reconfirm Dual-ESP spine nur bei Regression.  
3. Nicht: iDriveSim parallel, ch6-Kampf, Notification-Jagd, PKCS12/TEE.

---

## 8. Evidence index

| Path | Inhalt |
|------|--------|
| `docs/evidence/LAB_HOME_20261121T1840Z/` | Erster Green-Pull (~7.8 MB) |
| `docs/evidence/LAB_HOME_20261121T1900Z/hu_home_pre_restart.jsonl` | Voller Abend vor Agent-Restart (~29 MB) |
| `docs/evidence/LAB_HOME_20261121T1900Z/hu_home.jsonl` | Post-Restart green (~5.4 MB) |
| `docs/evidence/LAB_MUSIC_NP_LIVE_INJECT_20261121T1909Z/` | 336/248 + HMI inject slice |
| `docs/evidence/LAB_MUSIC_NP_SPINE_SEQ_DUAL_20261121T133709Z/` | Stub PASS (Referenz) |
