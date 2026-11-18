# Tiefenforensik 18.11.2026 — F20 Feld: Transport PASS × Lab-Auth REJECT

```yaml
date: 2026-11-18
claim_level: FIELD FACT
path: ".87 / hci1 C8:C9:A3:CB:37:96 → HU D4:36:39:CF:E1:B5 SCN 6"
client: "b2a-tx --full-client --mybmw-sim --knock wire_v5"
upstream_pin: "1100644 (Lab soak/seq); audit PR #37 lab-field-transfer"
evidence:
  - docs/evidence/FIELD_AUTH_PROBE_20261118T061541Z/
  - docs/evidence/FIELD_DUMP_20261118T061746Z/
related:
  - docs/analysis/DEEP_FORENSIC_ETCH_SAS_20261116.md
  - audits/esp32-bt-analyzer-lab-field-transfer-2026-11-17/  # technology-audit
```

**Kurzurteil:** Am echten F20 sind ACL/RFCOMM/BCL/Watchdog **grün**. Der Lab-`mybmw-sim`-Cert-Pfad wird von der HU **explizit abgewiesen**. CDS-/RHMI-Register und Action-IDs sind damit **nicht erreichbar**. Das bestätigt die Audit-Claim-Grenze *Lab PASS ≠ F20 Auto-ready* als **FIELD FACT**, nicht nur Desk-Inferenz.

---

## 1. Evidenz-Korpus

| Session | Dauer | Artefakte | Rolle |
|---------|-------|-----------|-------|
| `FIELD_AUTH_PROBE_20261118T061541Z` | ~70 s | `phone.jsonl` (274 Events), `hci1.btsnoop`, SUMMARY | Primär: Auth-Kette + WD-Statistik |
| `FIELD_DUMP_20261118T061746Z` | ~40 s BCL + SDP/HFP/SCN | `bcl.jsonl` (191), SDP, RSSI/LQ, HFP/SCN5 tries, `CAR_PARAMS.md` | Replikation + Nebenkanäle |

Beide BCL-Läufe sind **bitgleich im Auth-Ergebnis** (gleiche Exception-Längen/-Texte, gleiche RPC-Map) → kein Timing-Zufall.

---

## 2. Schicht A — Bluetooth-Identität & Link (FIELD FACT)

| Param | Wert | Quelle |
|-------|------|--------|
| Name / BD | BMW 38304 / `D4:36:39:CF:E1:B5` | BlueZ info |
| OUI / LMP | Texas Instruments · LMP **4.0** / sub `0x1b76` · Mfr 13 | `hcitool info` |
| Class | `0x340408` (Audio/Headset) | BlueZ |
| Modalias | `bluetooth:v05EBp0116d0103` | BlueZ |
| Bond | Paired + Bonded + Trusted | BlueZ |
| RSSI | **−46** (5× stabil) | `hcitool rssi` |
| Link quality | **209** (5×) | `hcitool lq` |
| TX power | **3** | `hcitool tpl` |
| ACL | AUTH + ENCRYPT; Rolle lab-seitig PERIPHERAL | `hcitool con` |

**SDP (browse unter ACL):**

| Service | Channel |
|---------|---------|
| SPP `0x1101` „SPP Server 1“ | **6** (BCL-Pfad) |
| Vendor `00000000-deca-fade-…` | **5** |
| SPP Server 2–5 | 7–10 |
| Handsfree `ALPS_HFM` | **3** |
| MAP MNS | 1 |
| OBEX Object Push | 11 |
| A2DP SNK | present (2 records) |

Nebenkanal-Negativ:
- HFP AT auf ch 1–3: *Connection refused*; ch **7** connectet (SPP), **0** AT-Antworten.
- SCN **5**: RFCOMM connect OK, **0** RX-Bytes in 2,5 s.
- SCN 9: reset by peer; SCN 10: timeout.
- Nach Dump: ACL instabil (`handle 3840 state 5`); Reconnect später *page-timeout* (Auto aus).

---

## 3. Schicht B — BCL Transport (FIELD FACT, reproduziert)

```text
RFCOMM SCN6
  → INIT (controlled)
  → HANDSHAKE rx  version=5  instance_id=14  buffer_size=0x4000 (16384)
  → full-client: SP4 + KNOCK wire_v5 + OPEN 5001 + OPEN Etch 4004
  → Watchdog 13371337 @ 2.5 s
```

| Metrik | AUTH-Probe | DUMP |
|--------|------------|------|
| `bcl_classification` | `BCL_FIELD_CONFIRMED` | gleich |
| HS | v5 / 14 / 0x4000 | gleich |
| WD echoes / misses | **28 / 0** | **16 / 0** |
| WD RTT ms min / p50 / mean / max | 55 / 157 / 161 / 265 | 53 / 160 / 158 / 267 |
| Session abort | nein (`active=True`) | nein |

**DATAACK-Selektivität (AUTH, `hu_dataack`):**

| ack_n | n | Interpretation (8+payload) |
|-------|---|------------------------------|
| 10 | 1 | SP / kurzer Control |
| 8 | 2 | leeres OPEN o.ä. |
| 154 | 1 | **8+146** = ACK auf `sas_certificate` TX |
| 559 | 1 | **8+551** = ACK auf `sas_login` TX |
| 12 | 28 | WD-DATA (8+4) |
| 38 / 52 | 6 / 1 | weitere Etch/Control |

Passt zur Freeze-Regel aus `FIELD_P0_HOLD_FREEZE`: HU ACKt selektiv; Wert = 8+len wenn ACK kommt.

**Schluss Transport:** write11/W0 bleiben **nicht** der Engpass. BCL am F20 ist operativ — Audit „nicht reopen“ bleibt richtig.

---

## 4. Schicht C — Etch Auth-Kette (FIELD FACT: REJECT)

### 4.1 RPC-Zeitlinie (beide Läufe, &lt;1 s Burst nach HS)

| # | TX method | TX len | RX method | RX BCL plen | ASCII / Bedeutung |
|---|-----------|--------|-----------|-------------|-------------------|
| 1 | `sas_certificate` | 146 | `_result_sas_certificate` | **98** | „Certificate is invalid or expired.“ |
| 2 | `sas_login` | 551 | `_result_sas_login` | **107** | „Client has not sent an app certificate yet.“ |
| 3 | `ver_getVersion` | 30 | `_result_ver_getVersion` | 69 | (kein Klartext; Exception-Form) |
| 4 | `info_getSystemInfo` | 30 | `_result_info_getSystemInfo` | **91** | „param component is invalid.“ |
| 5 | `rhmi_getCapabilities` | 44 | `_result_rhmi_getCapabilities` | **88** | „param handle is invalid.“ |
| 6 | `cds_create` | 30 | `_result_cds_create` | **89** | „Session is not logged in.“ |
| 7 | `am_create` | 30 | `_result_am_create` | **89** | „Session is not logged in.“ |
| 8 | `rhmi_create` | 30 | `_result_rhmi_create` | **90** | „param metadata is invalid.“ |
| 9 | `av_create` | 30 | `_result_av_create` | **89** | „Session is not logged in.“ |

Vergleich AAIdrive-Feld (16.11.): `_result_rhmi_getCapabilities` **plen=5306**. Hier **88** → Fehler-PDU, keine Caps.

### 4.2 Etch-Hash-Auflösung in den Reject-PDUs

Aus `payload_hex` (BCL DATA = `deadbeef` + u32 len + Etch):

| Hash | Auflösung | Wo |
|------|-----------|-----|
| `0x9c6372b8` | `BMWRemoting._result_sas_certificate` | PDU 1 |
| `0xa6b0ffca` | `BMWRemoting._result_sas_login` | PDU 2 |
| `0x19481364` | `BMWRemoting._result_rhmi_getCapabilities` | PDU 5 |
| `0x8104fdc2` | Feld `result` | alle |
| `0x22d75bde` | Feld `errorMsg` (ASCII folgt) | SAS/Login-Texte |

Die HU antwortet also **typrichtige `_result_*`-Structs**, deren `result` eine **ServiceException-Payload** trägt — nicht „Silence“ und nicht Lab-Stub-Success.

Kausalkette:

```text
Lab-Cert (mybmw-sim)
    → _result_sas_certificate { errorMsg: invalid/expired }
    → sas_login ohne akzeptiertes Cert
    → _result_sas_login { errorMsg: no app certificate yet }
    → create/getCapabilities ohne Session
    → Session is not logged in / invalid handle|component|metadata
```

### 4.3 Epistemik-Falle: lokaler Sim-State

`phone_done.rhmi_state = SAS_AUTHENTICATED` ist **lab-intern und falsch fürs Feld**. Wire-Beweis widerspricht. Claim-Hygiene:

| Claim | Status |
|-------|--------|
| Lab sim state ⇒ F20 SAS ok | **REJECTED** |
| HU Etch ASCII Exceptions | **FIELD FACT** |
| CDS vehicle.* live aus diesem Pfad | **not reached** |

---

## 5. Was bewusst *nicht* gemessen wurde / nicht ging

| Ziel | Status | Warum |
|------|--------|-------|
| `vehicle.VIN`, `sensors.fuel`, `driving.*` | **blocked** | `cds_create` → not logged in |
| RHMI Caps / Model-/Action-IDs | **blocked** | Caps-Fehler-PDU; keine DESCRIPTION |
| Resource check/set/verify am F20 | **not reached** | nach Auth |
| HFP Indicators (AT+CIND) | **FAIL** | ch3 refuse; ch7≠HFP |
| SCN5 Vendor-Payload | **leer** | connect ohne RX |

---

## 6. Abgleich mit Audit `lab-field-transfer-2026-11-17`

| Audit-These | Heute am F20 |
|-------------|--------------|
| Lab Soak/Seq = LAB FACT, nicht Auto-ready | **bestätigt** — Transport ok, Semantik/Auth tot |
| Resource-Auth OPEN | **verschärft zu FIELD FACT: Lab-Cert REJECT** |
| actionId 200 / PI_DRIVE_TEST ≠ F20 map | unberührt (Pfad nicht erreicht) — bleibt REJECTED als Map |
| write11/W0 nicht reopen | **unterstützt** (WD 0 misses, stabile RTT) |
| car_next = Auth + echte IDs | **operativ bestätigt** als nächster Engpass |

---

## 7. Systembild (nach diesem Morgen)

```text
                 ┌─────────────────────────────┐
 Phone-Radio .87 │ ACL+RFCOMM+BCL+WD           │  FIELD PASS
                 │ Etch OPEN 4004              │  FIELD PASS
                 │ Lab mybmw-sim Cert/Login    │  FIELD REJECT
                 │ CDS / RHMI / AM / AV create │  blocked
                 └─────────────────────────────┘
                              │
                              ▼
                 Nächster Nutzen nur mit:
                   • echtem APP-.p7b / Digest-Match
                   • oder Phone-AAIdrive Relay (Bodies)
                 Nicht: weiterer Transport-Hold / Lab-Soak
```

---

## 8. Repro (kurz)

```bash
# on .108, bridges up, HU paired on .87 / hci1
python3 /tmp/bcl_dummy/bcl_dummy_hu_agent.py b2a-tx \
  --adapter-bd C8:C9:A3:CB:37:96 \
  --hu-bd D4:36:39:CF:E1:B5 \
  --channel 6 --seconds 70 --init-count 2 \
  --full-client --mybmw-sim --knock wire_v5 \
  --selectproto 4 --wd-interval 2.5 \
  --origin f20 --source field \
  --log /tmp/bcl_dummy/probe.jsonl
```

Erwartung ohne echtes Cert: gleiche Exception-Map wie §4.1; WD weiterhin grün.

---

## 9. Dateien

- Evidence: `docs/evidence/FIELD_AUTH_PROBE_20261118T061541Z/` · `docs/evidence/FIELD_DUMP_20261118T061746Z/`
- Parameter-Kurzblatt: `…/FIELD_DUMP_…/CAR_PARAMS.md`
- Diese Analyse: `docs/analysis/DEEP_FORENSIC_FIELD_AUTH_REJECT_20261118.md`
