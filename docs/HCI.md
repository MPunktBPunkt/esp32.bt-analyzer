# HCI — transport notes

## What HCI is (in this project)

Host Controller Interface traffic between a **Bluetooth host stack** and a **Bluetooth controller**.

Primary transport for V1: **USB-HCI** via a commercial USB Bluetooth dongle attached to ESP32-S3 USB Host.

## Packet types (data model)

| Type | Direction (typical) | Notes |
|------|---------------------|-------|
| Command | host → controller | Opcode = OGF/OCF |
| Event | controller → host | event_code |
| ACL | both | L2CAP carrier |
| SCO / eSCO | both | Classic voice — controller-dependent |
| ISO | both | BLE Audio / modern controllers |

## Capture fields (minimum, BT3)

```json
{
  "seq": 1001,
  "ts_us": 123456789,
  "dir": "host_to_controller",
  "transport": "usb_hci",
  "type": "command",
  "endpoint": 2,
  "length": 3,
  "payload_hex": "010C20"
}
```

Raw capture must work **without** decoder.

## What HCI is not

- Not advertising channel 37/38/39 visibility
- Not PHY preamble / access address / CRC on air
- Not proof that an RF packet was transmitted

See method [`bt-passive-host-sniff`](https://github.com/MPunktBPunkt/technology-audit/blob/main/methods/bt-passive-host-sniff.md) in technology-audit.
