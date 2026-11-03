# BT1 Status — USB Host Enumeration

**Firmware:** 0.1.1  
**Claim boundary:** USB Host stack saw device descriptors (enum). **Not** HCI. **Not** RF/Air.

## Implementation

| Piece | Path |
|-------|------|
| EspUsbHost 2.10.1 | `platformio.ini` |
| Enum service | `firmware/analyzer-node/src/usb/UsbHostEnum.*` |
| AppCore module | `firmware/analyzer-node/src/app/BtAnalyzerModule.*` |
| Status | `/api/status` → `usbHost`, `otg`, `dut`, `vbus`, `lastUsbEvent` |
| Routes | `/api/usb/status`, `/api/usb/last-event` |
| Hub ios | `usb_devs`, `usb_att`, `usb_vid`, `usb_pid` |

## Lab exit (pending MEASURED)

| Check | Expectation |
|-------|-------------|
| known BT dongle enumerates | `dut.present=true`, `vid`/`pid`, interfaces, endpoints |
| `dut.wirelessController` | true if class `0xE0` / subclass `0x01` |
| unknown USB device | safe (no crash), descriptors if supported |
| disconnect / reconnect | `lastUsbEvent` removed → enumerated |
| VBUS | `boardSourcesVbus=false` — use self-powered hub/dongle |

## Repro

```bash
cd firmware/analyzer-node && pio run -e analyzer-s3
./tools/flash_lab_ota.sh <IP>
# Serial on UART/COM; plug dongle into OTG (via powered hub if needed)
curl -s http://<IP>/api/usb/status | jq .
```

## Epistemics

| Claim | Status |
|-------|--------|
| Descriptors observed via EspUsbHost | MEASURED after lab |
| Device is Bluetooth HCI capable | INFERENCE from class/subclass only until BT2 |
| HCI packets captured | UNKNOWN (BT3) |
