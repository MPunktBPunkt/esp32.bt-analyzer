# HCI — transport notes

## What HCI is (in this project)

Host Controller Interface traffic between a **thin host** (bt-analyzer) and the **on-chip Bluetooth controller** via **VHCI** (H4 framing).

Primary transport: **`onchip_vhci`**. USB-HCI dongle path is optional/legacy.

## Packet types (data model)

| Type | Direction (typical) | Notes |
|------|---------------------|-------|
| Command | host → controller | Opcode = OGF/OCF |
| Event | controller → host | event_code |
| ACL | both | L2CAP carrier |
| SCO / eSCO | both | Classic — ESP32 only |
| ISO | both | BLE Audio / modern controllers |

## On-chip VHCI (primary)

- Controller init + `esp_vhci_host_register_callback`
- Send: `esp_vhci_host_send_packet` (H4, leading type byte)
- Recv: `notify_host_recv` → CaptureRing
- Status: `transport: onchip_vhci`, `hciCapture.eventCapture: vhci`

## USB-HCI endpoint map (legacy BT2)

Bluetooth USB transport (Wireless Controller `0xE0` / `0x01`) when `BT_ANALYZER_ENABLE_USB_HOST=1`:

| Endpoint | Role string | Packet types |
|----------|-------------|--------------|
| Interrupt IN | `hci_event` | Event |
| Bulk OUT | `hci_command_acl_out` | Command + ACL |
| Bulk IN | `hci_acl_in` | ACL |

## Capture fields (minimum)

```json
{
  "seq": 1001,
  "ts_us": 123456789,
  "dir": "controller_to_host",
  "transport": "onchip_vhci",
  "type": "event",
  "endpoint": 0,
  "length": 8,
  "payload_hex": "040e0401030c00"
}
```

## What HCI is not

- Not RF/Air sniffer
- Not a claim that “Bluetooth works” without layer
- Not Classic on ESP32-S3
