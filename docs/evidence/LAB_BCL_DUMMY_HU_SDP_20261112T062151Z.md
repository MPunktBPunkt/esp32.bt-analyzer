# LAB BCL Dummy-HU SDP — PASS

**UTC:** 20261112T062151Z · channel 5 · service `BMW Connected`
**claim:** ProfileManager SPP visible via phone-side sdptool — TEST, not BMW FACT

| Check | Result |
|-------|--------|
| overall | PASS |
| profile registered | True |
| link prep | False |
| SDP verdict | `CANDIDATE_STRONG: RFCOMM data service with BMW/Connected name` |
| records | 15 |

## Records

- - classes=0x1200 rfcomm=None tags=[]
- Generic Access Profile classes=0x1800 rfcomm=None tags=[]
- Generic Attribute Profile classes=0x1801 rfcomm=None tags=[]
- Device Information classes=0x180a rfcomm=None tags=[]
- AVRCP CT classes=0x110e,0x110f rfcomm=None tags=[]
- AVRCP TG classes=0x110c rfcomm=None tags=[]
- SIM Access Server classes=0x112d,0x1204 rfcomm=8 tags=['rfcomm8']
- Headset Voice gateway classes=0x1112,0x1203 rfcomm=12 tags=['rfcomm12']
- Headset unit classes=0x1108,0x1131,0x1203 rfcomm=3 tags=['rfcomm3']
- Hands-Free Voice gateway classes=0x111f,0x1203 rfcomm=13 tags=['rfcomm13']
- Hands-Free unit classes=0x111e,0x1203 rfcomm=7 tags=['rfcomm7']
- Audio Source classes=0x110a rfcomm=None tags=[]
- Audio Sink classes=0x110b rfcomm=None tags=[]
- Vendor specific classes=03b80e5a-ede8-4b33-a751-6ce34ec4c700 rfcomm=None tags=['vendor128']
- BMW Connected classes=0x1101 rfcomm=5 tags=['spp', 'rfcomm5', 'name_hint']

## Epistemic

```text
YES:  Dummy-HU can advertise SPP/RFCOMM over BlueZ SDP
YES:  bcl_sdp_probe verdict path works against a known service
NO:   what the real BMW HU offers
```
