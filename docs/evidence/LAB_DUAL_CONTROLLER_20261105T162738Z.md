# LAB Dual Controller P0 — PASS

**UTC:** 20261105T162738Z
**dual_classic_ready:** False
**hci_transport:** network_hci_wifi
**flash_131_authorized:** False

| Slot | IP | Class | Classic ready |
|------|----|-------|---------------|
| A phone | 192.168.178.131 | `HEIZUNG_METERMASTER` | False |
| B car | 192.168.178.87 | `BT_ANALYZER` | True |

- car BD: `c8:c9:a3:cb:37:96` · FW `0.3.14`
- phone detail: label=Heizung unit=kWh value=14946.0
- next: flash .131 with ENV=analyzer-esp32 after Heizung vacated

OTA `.131` is **blocked** while class is `HEIZUNG_METERMASTER` unless operator auth.
