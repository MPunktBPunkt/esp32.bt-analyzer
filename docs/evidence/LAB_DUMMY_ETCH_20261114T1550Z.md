# LAB — Dummy HU Etch capture (AAIdrive grün, 2026-11-14 ~15:50)

status: captured · deep-analyzed  
peer: Phone `AC:C0:48:5E:CB:20` → Dummy **`.108` hci2**  
raw: `LAB_DUMMY_ETCH_20261114T1550Z_hu.jsonl`  
decode: `LAB_DUMMY_ETCH_20261114T1550Z_decode.json` · certs: `LAB_DUMMY_ETCH_20261114T1550Z_certs/`  
analysis: [`../analysis/LAB_DUMMY_ETCH_DEEP_20261114.md`](../analysis/LAB_DUMMY_ETCH_DEEP_20261114.md)

## Trigger

Car-side ACL bounce + A2DP_Source/AVRCP restore → Phone verbindet Dummy → AAIdrive grün → Etch-Push.

## BCL bootstrap (Phone → Dummy)

| Step | Wire |
|------|------|
| INIT | `12345678` |
| HS | Dummy TX v5 / iid **1** / buf **0x8000** |
| SELECTPROTO | Phone **`0004`** (~+3.2 s) |
| KNOCK | UUID-Serial + appType=**1**/param1=**7** (TouchCommand) |
| OPEN 5001 | `src=dst=5001` + WD `13371337` @ **≈2.5 s** (173×) |
| OPEN 4004 | **sequenziell** src 10 → 11 (CLOSE/re-OPEN) → 12 |

## Etch / Layer E **[LAB FACT]**

| src | PKCS7 leaf (kurz) | Bytes |
|-----|-------------------|------:|
| 10 | myBMW `applicationmanager` (`CDS=true&RHMI=true&APPID=myBMW&Make=BMW,MINI,J29&…`) | 6126 |
| 11 | SmartThings | 6813 |
| 12 | myBMW **`cdsbaseapp`** (erweiterte cds.*/rhmi.* Permissions) | 6687 |

Fragmentierung @4000 BCL-DATA; Magic `deadbeef` + `u32BE(len)`.  
Dummy TX danach nur WD-Echo — **kein** Etch-Reply, UI trotzdem grün (M27/M40).  
src↔bmw/mini/j29 = **INFERENCE** (nicht FACT).

## vs Bimmer / Prior Lab

- BclCarLink: SP**3** + leerer Knock A4A — hier SP**4** + UUID/TouchCommand/7.
- `LAB_PHONE_BCL_*` (HS v3): SP**2**, kein Knock.
- F20: OPEN 4004 → DATAACK `0x08` = Frame-ACK (M41), keine App-Certs von HU.
- Abgleich: [`../analysis/FIELD_STAND_Grok_GPT_20261114.md`](../analysis/FIELD_STAND_Grok_GPT_20261114.md)

## Next

**P0 Proxy:** PKCS7 unverändert an F20 → SAS Challenge.
