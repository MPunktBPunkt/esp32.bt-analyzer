# Lab-Standardtopologie (.108) — 2026-11-22

**Status:** Kanonisch. Cursor-Rule: `.cursor/rules/lab-bt-host-gotchas.mdc`  
**Proof:** ACL + RFCOMM ch6 `.87`↔`.131` OK (`/tmp/bcl_dummy/LAB_87_131_CONNECT_20261122T213400Z/` auf Host)

## Standard (immer, außer explizitem Umschalten)

| Rolle | Gerät | BD | Air-Name | CoD | Power |
|-------|-------|-----|----------|-----|-------|
| **Lab-HU** | ESP `.131` | `C8:C9:A3:CB:7B:0A` | **BMW 38304** | `0x340408` AV | **ON**, discoverable |
| **Lab-Phone** | ESP `.87` | `C8:C9:A3:CB:37:96` | **BT-Analyzer-Phone** | Phone (`0x5a020c`) | ON für Dual-ESP; sonst off |
| **USB** | `.108` dongle | `C0:B8:83:34:F4:62` | BT-Analyzer-PhoneUSB | — | **OFF** (nie discoverable im Lab-HU-Modus) |
| **CSR** | optional | `00:1A:7D:DA:71:02` | — | — | nur gezielt; sonst aus |

Laufend:

- `hci_tcp_bridge` → `.131` `--local-name "BMW 38304"`
- optional `hci_tcp_bridge` → `.87` `--local-name "BT-Analyzer-Phone"`
- `bt_pair_agent` **nur** `7B:0A=car_audio:BMW 38304` + `37:96=phone:BT-Analyzer-Phone` (kein PhoneUSB)
- Lab-HU: `bcl_dummy_hu_agent.py hu --hu-profile f20_sim --channel 6`
- iDriveSim: **aus** (`idrivesim-rfcomm-bridge` stop, Drop-Ins in `.d.off/`)
- beide ESP: `wifi_ps=none`

Schnell-Smoke Phone→HU:

```bash
# auf .108: bridges up, dann
bluetoothctl select C8:C9:A3:CB:37:96
bluetoothctl connect C8:C9:A3:CB:7B:0A
# ACL beide Seiten; RFCOMM ch6 → f20_sim
```

## Was das Problem war (iPhone-Lab 2026-11-22)

Symptom: iPhone „koppelt, ist aber phone“ / sieht falsches Gerät / CoD-Chaos (PC vs Auto).

**Ursache (Host, nicht RF):**

1. **PhoneUSB (`hci0` / `F4:62`)** war powered/discoverable und im Pair-Agent mit `always` → iPhone pairte an **BT-Analyzer-PhoneUSB**, nicht an BMW `7B:0A`.
2. **`.87` Bridge/Advertising** als zweites „Phone“ auf der Luft → Sichtbarkeits-Chaos neben BMW.
3. **CoD Drift** auf `.131`: Inquiry zeitweise `0x400104` (Computer/PC-Icon), obwohl Alias BMW — nach HCI Write Class `0x340408` ok.
4. **BlueZ Alias ≠ HCI Local Name**; Name-Pin nur über Bridge/`hciconfig name` zuverlässig auf der Luft.
5. iDriveSim war diesmal nicht aktiv; der Störer war USB + Agent-Scope.

**Fix:** USB down + aus Agent; nur BMW discoverable; `.87` nur als Lab-Phone (nicht parallel als zweites Auto); CoD-Pin auf HU; Dual-ESP-Proof ACL+ch6.

Evidence-Start: `docs/evidence/LAB_IPHONE_CSR_20261122T192432Z/`  
Related: `docs/analysis/LAB_IDRIVESIM_SWITCH_20261119.md`
