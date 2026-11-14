# LAB — OnePlus ↔ Dummy `.131` (Abend-BT-Logs, 2026-11-14 ~17:32–17:55)

```yaml
id: LAB_PHONE_DUMMY_BTLOGS_20261114T1732Z
kind: lab_phone_btlog
peers: OnePlus 12 (AC:C0:48:5E:CB:20) ↔ Dummy BMW 38304 C8:C9:A3:CB:7B:0A (.131)
also_seen: F20 HU D4:36:39:CF:E1:B5 (ACL only) · OTHER 78:85:F4:F7:B7:21 (Wear/SPP scn16)
operator_script: BT an → verbunden → AAIdrive → MyBMW an → AAIdrive grün → BT aus (mehrfach)
source: Android BT-Stack Verbose Logcat (operator upload)
raw:
  - docs/bluetooth_20261114_173248_05337.log  # 5.1 MiB / 32475 lines · 17:32:46–17:35:27
  - docs/bluetooth_20261114_173632_05287.log  # 5.5 MiB / 35827 lines · 17:36:31–17:38:57
  - docs/bluetooth_20261114_173859_26210.log  # 330 KiB / 2021 lines · 17:38:58–17:39:25 (abort)
  - docs/bluetooth_20261114_174045_06218.log  # 5.6 MiB / 36172 lines · 17:40:41–17:55:16
analysis: docs/analysis/LAB_PHONE_DUMMY_SPP_EVENING_20261114.md
contrast_field: docs/evidence/FIELD_PHONE_HU_LOGCAT_20261114T0924Z.md
verified: 2026-11-14 local recount
```

## Verdict (kurz)

| Ebene | Status | Aussage |
|-------|--------|---------|
| 4× BT-on Zyklen | **MEASURED** | Jede Datei = neuer `AdapterService` / `offToBleOn` |
| AAIdrive-Ziel | **LAB FACT** | UID **10479** → immer `7B:0A` (Dummy), **nie** `E1:B5` |
| SPP `0x1101` → SCN **6** | **LAB FACT** | SDP + `remote_scn:6` + `on_cli_rfc_connect` |
| RFCOMM OPEN (grün) | **LAB FACT** | L1 + L2 volle BCL-Sessions; L4 1× kurz nach HU-Restart |
| DLCI | **MEASURED** | **12** (Phone öffnet Mux) — Feld-HU war DLCI **13** |
| Phone TX nach OPEN | **LAB FACT** | `4` → `10+56` → Cert-Burst (`990`×…) → **`12` @ 2,506 s** |
| Dummy RX | **LAB FACT** | `PORT_DataInd` **dlci 12** ≫ 0 (L1: **80**) — Dummy antwortet |
| echte HU SPP | **absent** | 0× `connectSocket` / `on_cli` auf `E1:B5` in allen 4 Files |
| BCL Hex | **UNKNOWN** | kein `data_hex` (Größen/Kadenz + Lab-HU-JSONL) |

**Kern:** Abend-Logs sind **Lab-Dummy-Grün**, nicht Feld-HU. Gegen den antwortenden Dummy wechselt AAIdrive nach Handshake auf **12‑Byte-Writes @ ~2,5 s** (mit RX). Das Morgen-Feld gegen stumme HU blieb bei **4 B @ 3,0 s** ohne RX.

## Zyklus-Tabelle

| # | File | Wall | Dummy ACL | SPP `1101`/SCN6 | BCL-artig | Ende |
|---|------|------|-----------|-----------------|-----------|------|
| L1 | `…173248…` | 17:32:46–17:35:27 | 17:34:00 up | OPEN 17:34:08 uid 10479 | **ja** ~78 s WD `12`@2,5 s + Certs | Capture end (BT aus) |
| L2 | `…173632…` | 17:36:31–17:38:57 | 17:38:05 / 17:38:38 | OPEN 17:38:45 | **ja** kurz (~12 s) bis BT aus | RFCOMM DISC 17:38:57 |
| L3 | `…173859…` | 17:38:58–17:39:25 | — | nein | abort / nur Stack-Start | früh abgebrochen |
| L4 | `…174045…` | 17:40:41–17:55:16 | flaps + 17:50:46 / 17:52:02 | **62** `btsock_connect`, **59** fail `scn:0`, **1** OK 17:54:27 | OK nur **~0,7 s** (1×4 B) | dumpsys 17:55:16 |

L4-Zeitfenster 17:50–17:54 = Dummy-HU **tot** (kein SPP-Server) → AAIdrive spammt Retries. Erster UA nach Lab-HU-Restart ~17:54:27.

## L1 — volle Grün-Session (Referenz)

```text
17:34:00   ACL up 7b:0a
17:34:06   connectSocket(UUID 0x1101) uid→10479
17:34:07   SDP OK → remote_scn:6
17:34:08.748  UA / SetRfcommPortOpen  uuid=0x1101  dlci=12  (Phone-Mux)
17:34:08.750  on_cli_rfc_connect scn:6 app_uid:10479
17:34:08.768  Write 4 B          ← INIT
17:34:11.759  Write 10 B
17:34:11.770  Write 56 B         ← Probe / DEADBEEF-Klasse
17:34:11.79x  Write 8+12
17:34:12.36…  Burst 990×4 + 48 + 990×2 + 154   ← Cert #1
17:34:13.06…  Burst 990×4 + 48 + 990×2 + 841   ← Cert #2
17:34:14.29…  12 + Burst 990×4 + 48 + 990×2 + 715 ← Cert #3
17:34:14.3 → 17:35:26   Write 12 B alle ≈2,506 s  (31×)  ← WD live
            DataInd dlci12: 80 Frames (Dummy-Pong/HS/Etch-TX)
```

Port-Handle RFCOMM: **27**. ACL-Handle: **4**.

## L2 — verkürzt durch BT-aus

Gleiches Muster (INIT 4 → 56 → Cert-Burst → `12`@2,5 s), Abbruch nach 4× `12`-Writes durch Stack-Teardown (17:38:56–57).

## L4 — Fail-Sturm dann Mikro-OPEN

| Metric | Count |
|--------|------:|
| `btsock_connect` …`7b:0a` uid 10479 | 62 |
| `cleanup_rfc_slot` …`scn: 0` | 59 |
| `on_cli_rfc_connect` …`scn: 6` | **1** (17:54:27.199) |
| Writes auf dem OPEN-Handle | **1× 4 B** |
| Session-Länge OPEN→DISC | **~0,7 s** |

## Neben-Peer `b7:21` (nicht AAIdrive)

In L1/L2 vor Dummy: ACL + RFCOMM. `connectSocket` UUID `82ff3820-…`, später auch `0x1101` **scn 16**, **uid 10464**. Write-Muster (47 B, 990 B, …) ≠ BCL-WD. Nicht mit AAIdrive vermengen.

## Was **nicht** behauptet wird

- Bytes der 4/12/56/990 = exakte BCL-Opcodes — **Inferenz** über Lab-HU-JSONL / Größen, kein `data_hex`.
- L4-Mikro-OPEN = „grün“ in der UI — zu kurz; UI-Grün gehört zu L1/L2 bzw. Post-Capture.
- echte HU habe Abend SPP gesprochen — **widerlegt** (0 Connects auf `E1:B5`).
