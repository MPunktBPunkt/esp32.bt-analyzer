# LAB Deep Dive — Dummy Etch / AAIdrive (2026-11-14 ~15:50)

session: `LAB_DUMMY_ETCH_20261114T1550Z`  
raw: `docs/evidence/LAB_DUMMY_ETCH_20261114T1550Z_hu.jsonl` (731 events, ~760 s)  
decode: `…_decode.json` · certs: `…_certs/`  
peer: Phone `AC:C0:48:5E:CB:20` → Dummy **`.108` hci2** (nicht `.131`)  
trigger: car-side A2DP/ACL-Bounce → AAIdrive grün

## Verdict

Nach HS **v5** spricht das offizielle Phone-Stack **SELECTPROTO(4) + KNOCK** (UUID-Serial, appType=TouchCommand/7), öffnet WD@2.5 s und pusht **sequenziell** drei Etch-PKCS7 an dest 4004 (ApplicationManager → SmartThings → **cdsbaseapp**). Das weicht klar von BclCarLink@`7cfd959` (SP3+leerer Knock, WD 5 s) und vom Lab-Abend mit Dummy-HS **v3** (SP2, kein Knock) ab. UI bleibt grün **ohne** HU-Etch-Reply / ohne Dummy-DATAACK — nur HS + WD-Echo (**≠** SAS/RHMI/CDS).

Siehe auch: [`FIELD_STAND_Grok_GPT_20261114.md`](FIELD_STAND_Grok_GPT_20261114.md) (M29–M44, Proxy-Soll-Sequenz).

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
| Cert src 10/11/12 | sequenziell AM → SmartThings → **cdsbaseapp** | Grantor ab 10 | ja (ähnliches Muster) |

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

**cdsbaseapp** = MyBMW-eingebettete CDS-App. CarProber@3e93419: `j29Cert` = „optional cdsBaseApp from MyBMW“ — Wire-CN bestätigt cdsbaseapp; **src↔bmw/mini/j29** bleibt INFERENCE.

### Cert-Permissions (OID `1.3.6.1.4.1.513.59.4.2`) **[LAB FACT]**

Leaf src10 (applicationmanager): `CDS=true&RHMI=true&APPID=myBMW&Make=BMW,MINI,J29&SAS.CertificateType=APP&AVS=true&…`  
Leaf src12 (cdsbaseapp): zusätzlich `cds.*=1`, viele `rhmi.*`, `MAP=true`, `AVS=false`, …

## Muster (M23–M28; Fortsetzung M29–M44 in FIELD_STAND)

| ID | Muster | Status |
|----|--------|--------|
| **M23** | HS **v5** → Phone **SP(4)+KNOCK** | LAB FACT |
| **M24** | Official KNOCK = UUID-Serial + TouchCommand(1)/7 | LAB FACT |
| **M25** | ~~parallele~~ → **sequenzielle** Cert-Pushes src10→11→12 (AM / SmartThings / cdsbaseapp) | LAB FACT (korrigiert) |
| **M26** | Etch fragmentiert @4000; Reassembly `8+be_len` | LAB FACT |
| **M27/M40** | UI grün ohne HU-Etch-Reply — nur BCL/WD | LAB FACT |
| **M28** | src11 CLOSE→OPEN vor Cert | LAB FACT |
| **M35** | Timing: HS@0.2 s → SP/KNOCK@~3.2 s → OPEN5001 → OPEN4004@~3.7 s | LAB FACT |
| **M36** | WD parallel zu Etch-Bootstrap | LAB FACT |
| **M39** | PKCS7 = Capability-Landkarte (CDS/RHMI/APPID/Make/SAS) | LAB FACT |
| **M42** | SP folgt HS-version; iid/buf Fingerprint | LAB FACT |

## Konsequenzen

1. **b2a-tx / PhoneClient:** nach HU-HS v5 → **SP4+KNOCK(UUID,1,7)**; WD 2.5 s; Echo erst nach OPEN 5001 (M29).
2. **F20-Proxy P0:** unveränderte App-PKCS7 an 4004 durchreichen → erste erwartete HU-Antwort = **SAS Challenge**.
3. OPEN 4004 + DATAACK `0x08` allein = BCL-ACK, nicht Etch-OK (M41).
4. Dummy iid/buf dürfen von F20 abweichen; Version steuert SP-Pfad.

## Nicht in diesem Log

- `sas_*` / Challenge / `cds_*` Callbacks (Dummy = kein Etch-Server)
- DATAACK von der Dummy-„HU“
- Beweis src10=BMW / src11=MINI / src12=J29
