# BT2 Status — HCI Interface Detection

**Firmware:** 0.1.2  
**Claim boundary:** USB descriptors classified as USB-HCI roles. **Not** packet capture. **Not** RF.

## Mapping (descriptor INFERENCE)

| USB endpoint | Classified role |
|--------------|-----------------|
| Interrupt IN | `hci_event` |
| Bulk OUT | `hci_command_acl_out` |
| Bulk IN | `hci_acl_in` |
| Isochronous | `hci_sco_iso_*` |

Wireless Controller iface: class `0xE0`, subclass `0x01`, protocol `0x01` = Primary Controller.

## Status JSON

`/api/status` → `hci.detected`, `hci.capabilities`, `hci.endpoints[].role`  
`hci.claim` = `descriptor_inference_not_capture`

## Lab exit (pending MEASURED)

| Check | Expectation |
|-------|-------------|
| BLE/Classic dongle | `hci.detected=true` |
| event + bulk endpoints | capabilities flags set |
| Non-BT USB device | `hci.detected=false`, safe |

## Next

**BT3** — subscribe/transfer on classified endpoints, raw HCI frames with timestamp.
