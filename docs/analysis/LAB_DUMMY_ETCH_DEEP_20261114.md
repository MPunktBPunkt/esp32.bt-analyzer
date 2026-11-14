# LAB Deep Dive — Dummy Etch / AAIdrive (2026-11-14 ~15:50)

session: `LAB_DUMMY_ETCH_20261114T1550Z`  
raw: `docs/evidence/LAB_DUMMY_ETCH_20261114T1550Z_hu.jsonl` (731 events, ~760 s)  
decode: `…_decode.json` · certs: `…_certs/`  
peer: Phone `AC:C0:48:5E:CB:20` → Dummy **`.108` hci2** (nicht `.131`)  
trigger: car-side A2DP/ACL-Bounce → AAIdrive grün

## Verdict

Nach HS **v5** spricht das offizielle Phone-Stack **SELECTPROTO(4) + KNOCK** (UUID-Serial, appType=TouchCommand/7), öffnet WD@2.5 s und pusht **drei** Etch-PKCS7 an dest 4004 (ApplicationManager, SmartThings, **cdsbaseapp**). Das weicht klar von BclCarLink@`7cfd959` (SP3+leerer Knock, WD 5 s) und vom Lab-Abend mit Dummy-HS **v3** (SP2, kein Knock) ab. UI bleibt grün **ohne** HU-Etch-Reply / ohne Dummy-DATAACK — nur HS + WD-Echo.

## Timeline (relativ zu `rfcomm_connected`)

| t | Wire |
|---|------|
| 0 | RFCOMM connect Phone→Dummy ch6 |
| +0.20 s | INIT `12345678` |
| +0.20 s | Dummy HS v5 / iid **1** / buf **0x8000** |
| +3.19 s | Phone SELECTPROTO payload **`0004`** |
| +3.20 s | Phone KNOCK (48 B) |
| +3.28 s | OPEN 5001↔5001 + erste WD `13371337` |
| +3.72 s | OPEN src=10→4004 |
| +4.6… s | Etch DATA src10 (6126 B, frag 4000+2126) |
| +5.1 s | OPEN 11 → **CLOSE 11** → OPEN 11 → Etch src11 (6813 B) |
| +5.9 s | OPEN 12 → Etch src12 (6687 B) |
| danach | nur WD @ **p50 2.509 s** (173×); Dummy TX = Echo only |

## Abgleich Bimmer-Quellen

| Marker | Diese Messung | BclCarLink@7cfd959 | Lab `LAB_PHONE_BCL_*` (HS v3) |
|--------|---------------|--------------------|------------------------------|
| HS version | **5** (Dummy) | wartet auf HU | **3** |
| SELECTPROTO | **4** | **3** wenn version>3 („v4 WD unknown“) | **2**, kein KNOCK |
| KNOCK | UUID-Serial + appType=**1**/param1=**7** | leere Felder + appType=**0**/param1=**1** | — |
| WD interval | **≈2.5 s** | **5 s** / timeout 20 s | ≈2.5 s |
| OPEN 5001 vor 4004 | ja | ja | ja |
| Etch dest 4004 / magic `deadbeef` | ja | ja | ja |
| Cert src 10/11/12 | ja (AM / SmartThings / **cdsbaseapp**) | Grantor ab 10 | ja (ähnliches Muster) |

Quellen: `BclClientTransport.selectProtocol` / `doKnock` · Analysis CDS · `bmw-bcl-handshake.md` · `bmw-bcl-wire-vs-desk-2026-11-14`.

### KNOCK-Layout (Wire = BclPacket.Knock)

```
u16 serial_len=36
ascii  0e9b90c4-cbe1-4742-8283-d367e9a56619
u16 bt=0, mac=0, wifi=0
u16 appType=1   # TouchCommand (Desk-Kommentar: alt 1+7)
u16 param1=7
```

Desk-Default (A4A/0+1) ist **nicht** der MyBMW-Wire nach HS v5.

### Etch / PKCS7

Fragmentierung: BCL DATA max **4000** B beobachtet; Msg = `deadbeef` + `u32BE(len)` + Body.  
Body: 16 B Etch-Vorspann + PEM PKCS7 (3 Certs) + 15 B Trailer `866306b46887…`.

| src | App (CN) | Bytes |
|-----|----------|------:|
| 10 | `a4a_app_myBMW.perm___applicationmanager_…` + TouchCommand + android-ca | 6126 |
| 11 | `a4a_app_mobile___com_smartthings_android_…` (+ CLOSE/re-OPEN) | 6813 |
| 12 | `a4a_app_myBMW.perm___cdsbaseapp_…` | 6687 |

**cdsbaseapp** = MyBMW-eingebettete CDS-App (Vehicle Status / `cds_*`) — deckt sich mit Analysis/Diskussion #346. Ohne echte HU-Antwort kein `cds_onPropertyChangedEvent` im Dummy-Log.

## Neue Muster (M23–M28)

| ID | Muster | Status |
|----|--------|--------|
| **M23** | HS **v5** → Phone **SP(4)+KNOCK** (nicht Desk SP3, nicht Lab-v3 SP2) | LAB FACT |
| **M24** | Official KNOCK = UUID-Serial + TouchCommand(1)/7 | LAB FACT |
| **M25** | Drei parallele Etch-Kanäle 10/11/12 = AM / SmartThings / **cdsbaseapp** | LAB FACT |
| **M26** | Etch über BCL fragmentiert @4000; Reassembly via `8+be_len` | LAB FACT |
| **M27** | AAIdrive grün mit Dummy: **kein** HU-Etch-Reply, **kein** DATAACK nötig — HS+WD-Echo reicht für UI | LAB FACT |
| **M28** | src11 CLOSE→OPEN vor Cert-Push (Retry/Reset-Kanal) | LAB FACT |

## Konsequenzen

1. **PhoneClientSession / b2a-tx:** nach HU-HS v5 Wire-treu **SP(4)+KNOCK(UUID,1,7)** modellieren — nicht BclCarLink-SP3.
2. **F20:** Analyzer-OPEN 4004 allein ≠ Etch; App-Certs (bes. cdsbaseapp) müssen vom Phone/Proxy kommen (M21 bestätigt).
3. **CDS:** Cert-Pfad ist da (src12); Property-JSON erst nach SAS auf echter HU/Simulator.
4. **Dummy-HS Fingerprint:** iid1/buf 0x8000 ≠ F20 iid14/buf 0x4000 — Phone akzeptiert trotzdem SP4-Pfad.

## Nicht in diesem Log

- `sas_*` / Challenge / `cds_*` Callbacks (Dummy spricht kein Etch-Server)
- DATAACK von der „HU“
- Zweite BCL-Session / HANGUP
