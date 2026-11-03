# BT3 Status — Raw HCI Capture

**Firmware:** 0.1.3  
**Claim boundary:** Raw USB-HCI frames with timestamp/direction/type/payload.  
**Not** RF. **Not** full profile decode. **Not** lossless claim (BT6).

## Implemented

| Path | Status |
|------|--------|
| PSRAM capture ring | yes |
| Bulk IN → ACL frames (`onVendorData`) | yes (needs BT dongle + `hci.detected`) |
| Host→controller write (`/api/hci/write`) | yes when `vendorOpen` OK |
| Synthetic inject (`/api/capture/inject`) | yes (lab / no dongle) |
| Drain JSONL (`/api/capture/drain`) | yes |
| Interrupt IN → HCI Event | **pending** (`eventCapture=pending_interrupt_in`) |

## APIs

```bash
curl -s http://<IP>/api/status | jq '.capture,.hciCapture,.hci'
curl -s 'http://<IP>/api/capture/drain?n=32'
curl -s -X POST -d 'hex=040e0401030c00' http://<IP>/api/capture/inject
curl -s -X POST -d 'hex=01030c00' http://<IP>/api/hci/write   # needs open HCI
```

## Epistemics

| Claim | Status |
|-------|--------|
| Frame fields from USB bulk IN | MEASURED after dongle lab |
| Type=ACL for bulk IN | INFERENCE (USB-HCI endpoint role) |
| Event path | UNKNOWN until interrupt IN |
| Inject path | MEASURED synthetic only |

## Lab note

`.88` may still have a non-BT gadget on OTG. Plug a USB Bluetooth dongle (self-powered hub) for `hci.detected=true` and live ACL capture.
