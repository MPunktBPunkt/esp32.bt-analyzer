# LAB Dual — `.87` MyBMW/AAIdrive sim ↔ `.131` f20_sim

**UTC:** see filename · **claim_level:** TOOLING PASS (host) · AIR TRANSPORT PARTIAL FAIL

## Setup
| Role | Board | BD | BlueZ (after bridge restart) |
|------|-------|----|------------------------------|
| HU `f20_sim` | `.131` FW 0.3.20 | `C8:C9:A3:CB:7B:0A` | hci2 |
| Phone MyBMW/AAIdrive sim | `.87` FW 0.3.19 | `C8:C9:A3:CB:37:96` | hci1 |

## What was added
- `PhoneClientSession.mybmw_sim`: after HS v5 / SP4 / KNOCK wire_v5 / OPEN 5001+4004 runs Etch client:
  `sas_certificate` → challenge → `sas_login` → `ver_getVersion` / `info_getSystemInfo` / `rhmi_getCapabilities` /
  `cds_create`+`am_create`+`rhmi_create`+`av_create` → 15× CDS subscribe+get → `am_registerApp` / `rhmi_checkResource` / `av_requestConnection`
- CLI: `bcl_dummy_hu_agent.py phone --mybmw-sim` (implies `--open-etch --wire-open5001`)

## Host byte-loop (no air) — PASS
```
HU methods: sas_certificate, sas_login, ver_getVersion, info_getSystemInfo, rhmi_getCapabilities,
  cds_create, am_create, rhmi_create, av_create, cds_addPropertyChangedEventHandler×15,
  cds_getPropertyAsync×15, am_registerApp, rhmi_checkResource, av_requestConnection
phone cds_events: 30 · mybmw_rpc_tx: 42 · stage=apps
```

## Air path `.87`↔`.131` — PARTIAL FAIL
| Step | Result |
|------|--------|
| Inquiry `.87`→`.131` | OK (RSSI ~−71) |
| SSP Pair (pair-agent always) | OK (both sides RequestConfirmation) |
| BlueZ `Connected` | intermittent; `Connect` often `br-connection-unknown` |
| ACL `hcitool con` | sometimes `state 1 AUTH ENCRYPT`, often ghost dual handles / drop |
| SDP browse phone→HU | empty / timeout |
| RFCOMM ch6 | **FAIL** timeout even with ACL AUTH ENCRYPT |
| HU `rfcomm_connected` | never seen in dual runs |
| Role swap HU=`.87` | `.131` inquiry did not find peer |

### Notes
- First pair of the evening reached `Connected: yes` + SPP UUID cached; subsequent A2DP `ConnectProfile` / bridge HCI errors (`Unexpected start frame`, earlier `command tx timeout` on hci1) correlated with ACL loss.
- Bridges were restarted; wifi_ps=`none`, coex=`prefer_bt` on both.
- Same dual-ESP RFCOMM path historically worked for B0.7 synth — tonight’s air RFCOMM to ProfileManager ch6 did not complete SABM/UA.

## Epistemic
- **YES:** MyBMW/AAIdrive Etch client state machine against `f20_sim` (LAB TEST).
- **YES:** Pairing + encrypted ACL can come up over air between the two D1s.
- **NO tonight:** end-to-end BCL/Etch over RFCOMM `.87`↔`.131` (transport, not protocol logic).
- **NO:** indistinguishability from real phone apps.

## Next
1. Stabilize dual-ESP ACL/RFCOMM (OTA `.87`→0.3.20, physical proximity, btmon SABM capture).
2. Re-run `phone --mybmw-sim` once RFCOMM6 connects; then CDS inject battery.
3. Until then, keep using real OnePlus ↔ `.131` f20_sim for UI FACT.
