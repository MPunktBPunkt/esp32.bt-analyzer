# LAB_BMW_SIM_20261113T181344Z.btsnoop

- ACL `1/129` → `AC:C0:48:5E:CB:20` connected 395.876 s

## SDP records of the remote device

| Handle | Name | Classes | RFCOMM | L2CAP PSM | Profiles |
|---|---|---|---|---|---|
| 65543 | Headset Gateway | 0x1112 HSP-AG, 0x1203 GenericAudio | 3 |  | 0x1108 HSP 1.2 |
| 65544 | Handsfree Gateway | 0x111f HFP-AG, 0x1203 GenericAudio | 4 |  | 0x111e HFP 1.7 |
| 65550 | AMA SPP Server | 931c7e8a-540f-4686-b798-e8df0a2ad9f7 | 5 |  |  |
| 65555 | NearbySharing | a82efa21-ae5c-3dde-9bbc-f16da7b16c5a | 6 |  |  |
| 65554 | OBEX Object Push | 0x1105 OPP | 12 |  | 0x1105 OPP 1.2 |
| 65549 | OBEX Phonebook Access Server | 0x112f PBAP-PSE | 19 |  | 0x1130 PBAP 1.2 |
| 65547 | SMS/MMS | 0x1132 MAP-MAS | 26 |  | 0x1134 MAP 1.4 |
| 65545 | Android Network Access Point | 0x1116 NAP |  | 15 | 0x1116 NAP 1.0 |
| 65546 | Android Network User | 0x1115 PANU |  | 15 | 0x1115 PANU 1.0 |
| 65541 | AV Remote Control | 0x110e AVRCP, 0x110f AVRCP-Controller |  | 23 | 0x110e AVRCP 1.4 |
| 65542 | AV Remote Control Target | 0x110c AVRCP-Target |  | 23 | 0x110e AVRCP 1.6 |
| 65539 | Advanced Audio Source | 0x110a A2DP-Source |  | 25 | 0x110d A2DP 1.3 |
| 65536 |  | 0x1801 |  | 31 |  |
| 65537 |  | 0x1800 |  | 31 |  |
| 65548 |  | 0x1855 |  | 31 |  |
| 65551 |  | 0xfcf1 |  | 31 |  |
| 65552 |  | 0xfef3 |  | 31 |  |
| 65553 |  | 0xbb15 |  | 31 |  |

## RFCOMM sessions

| t open | Channel | Opened by | Service | Accepted | Closed by | Payload |
|---|---|---|---|---|---|---|
| 560.537 | 5 | local | AMA SPP Server | True | remote | local: BCL_CANDIDATE (4 B) |
| 561.97 | 6 | local | NearbySharing | True | remote | local: BCL_CANDIDATE (20 B) |

## AVDTP

- 398.232 s remote DISCOVER CMD
- 398.232 s local DISCOVER ACC [{"seid": 1, "in_use": false, "sink": false}, {"seid": 2, "in_use": false, "sink": true}, {"seid": 3, "in_use": false, "sink": false}, {"seid": 4, "in_use": false, "sink": true}, {"seid": 5, "in_use": false, "sink": false}, {"seid": 6, "in_use": false, "sink": true}, {"seid": 7, "in_use": false, "sink": false}, {"seid": 8, "in_use": false, "sink": true}, {"seid": 9, "in_use": false, "sink": false}, {"seid": 10, "in_use": false, "sink": false}, {"seid": 11, "in_use": false, "sink": false}, {"seid": 12, "in_use": false, "sink": false}, {"seid": 13, "in_use": false, "sink": false}, {"seid": 14, "in_use": false, "sink": false}, {"seid": 15, "in_use": false, "sink": false}, {"seid": 16, "in_use": false, "sink": true}, {"seid": 17, "in_use": false, "sink": false}, {"seid": 18, "in_use": false, "sink": true}, {"seid": 19, "in_use": false, "sink": false}]
- 398.538 s remote GET_ALL_CAPS CMD
- 398.538 s local GET_ALL_CAPS ACC seid 2 [{"codec": "vendor", "info": "d70000002400f207ffffff"}, {"delay_reporting": true}]
- 398.641 s remote GET_ALL_CAPS CMD
- 398.641 s local GET_ALL_CAPS ACC seid 4 [{"codec": "vendor", "info": "4f0000000100f2"}, {"delay_reporting": true}]
- 398.848 s remote GET_ALL_CAPS CMD
- 398.848 s local GET_ALL_CAPS ACC seid 6 [{"codec": "vendor", "info": "e000000001009f"}, {"delay_reporting": true}]
- 398.948 s remote GET_ALL_CAPS CMD
- 398.948 s local GET_ALL_CAPS ACC seid 8 [{"codec": "SBC", "info": "ffff0240", "rates": ["16000", "32000", "44100", "48000"], "modes": ["mono", "dual", "stereo", "joint"], "blocks": ["4", "8", "12", "16"], "subbands": ["4", "8"], "allocation": ["snr", "loudness"], "bitpool": [2, 64]}, {"delay_reporting": true}]
- 399.05 s remote GET_ALL_CAPS CMD
- 399.05 s local GET_ALL_CAPS ACC seid 16 [{"codec": "vendor", "info": "f105000005104000ffffff0f1f0000000000000000000000"}, {"delay_reporting": true}]
- 399.153 s remote GET_ALL_CAPS CMD
- 399.153 s local GET_ALL_CAPS ACC seid 18 [{"codec": "vendor", "info": "f105000005104000ffffff0f1f00004000ffffff0f1f0000"}, {"delay_reporting": true}]
- 399.357 s remote SET_CONF CMD seid 2 [{"codec": "vendor", "info": "d700000024001200000000"}, {"delay_reporting": true}]
- 399.362 s local SET_CONF ACC
- 399.363 s local DELAY_REPORT CMD
- 399.46 s remote OPEN CMD
- 399.46 s remote DELAY_REPORT ACC
- 399.46 s local OPEN ACC

A2DP media bytes: `{}`

