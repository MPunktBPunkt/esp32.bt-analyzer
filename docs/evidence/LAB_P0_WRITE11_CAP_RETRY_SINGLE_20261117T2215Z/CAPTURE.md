# LAB P0 write11 capture — LAB_P0_WRITE11_CAP_RETRY_SINGLE_20261117T2215Z

- hold.ok: **True**
- wait_class: `None`
- abort: `None`
- center_ts: `None` (±1.0s)
- tx_write_failed errno: `None (None)` attempted=None tx_total=None since_rx=Nones
- rfcomm_closed: `None`
- eagain: `{"events": 2, "recovered": 2, "recovered_wait_s_max": 0.1179, "recovered_retries_max": 6}`

## Session TX

- HU: {"tx_frames": 179, "tx_bytes": 8195, "tx_max": 500, "rx_frames": 74, "rx_bytes": 18744, "mean_tx_gap_s": 0.4886, "min_tx_gap_s": 0.0, "last_methods": ["am_registerApp", "am_registerApp", "am_registerApp", "av_requestConnection", "rhmi_checkResource", "rhmi_setResource", "rhmi_checkResource", "rhmi_checkResource", "rhmi_initialize", "rhmi_setData", "rhmi_setData", "rhmi_setData"]}
- Phone: {"tx_frames": 59, "tx_bytes": 18524, "tx_max": 4008, "rx_frames": 121, "rx_bytes": 8195, "mean_tx_gap_s": 0.0458, "min_tx_gap_s": 0.0, "last_methods": ["_result_rhmi_setResource", "_result_rhmi_checkResource", "rhmi_checkResource", "_result_rhmi_checkResource", "rhmi_initialize", "rhmi_setData", "rhmi_setData", "rhmi_setData", "_result_rhmi_initialize", "_result_rhmi_setData", "_result_rhmi_setData", "_result_rhmi_setData"]}

## Hints

- EAGAIN recovered without close (2×) — write-policy mitigation held
- no terminal write_error:11 — session survived EAGAIN via retry/poll
- EAGAIN recovered 2× (max wait 0.1179s / retries 6)
- no write_error:11 in this capture (mitigation may be holding)

## HU window (compact)

```json
[]
```

## btmon kept-line tails

### hu (2099 lines)
```
        Handle: 129 Address: C0:B8:83:34:F4:62 (Intel Corporate)
        Channel: 66 [PSM 3 mode Basic (0x00)] {chan 2}
        Channel Latency: 110 msec (42-205 msec ~107 msec)
> ACL Data RX: Handle 129 flags 0x02 dlen 8              #582 [hci2] 103.543451
      Channel: 66 len 4 [PSM 3 mode Basic (0x00)] {chan 2}
      RFCOMM: Disconnect (DISC) (0x43)
< ACL Data TX: Handle 129 flags 0x00 dlen 8              #583 [hci2] 103.543585
      Channel: 66 len 4 [PSM 3 mode Basic (0x00)] {chan 2}
      RFCOMM: Unnumbered Ack (UA) (0x63)
> HCI Event: Number of Completed Packets (0x13) plen 5   #584 [hci2] 103.628109
        Num handles: 1
        Handle: 129 Address: C0:B8:83:34:F4:62 (Intel Corporate)
        Channel: 66 [PSM 3 mode Basic (0x00)] {chan 2}
        Channel Latency: 84 msec (42-205 msec ~95 msec)
> ACL Data RX: Handle 129 flags 0x02 dlen 8              #585 [hci2] 103.629042
      Channel: 66 len 4 [PSM 3 mode Basic (0x00)] {chan 2}
      RFCOMM: Disconnect (DISC) (0x43)
< ACL Data TX: Handle 129 flags 0x00 dlen 8              #586 [hci2] 103.629127
      Channel: 66 len 4 [PSM 3 mode Basic (0x00)] {chan 2}
      RFCOMM: Unnumbered Ack (UA) (0x63)
< ACL Data TX: Handle 129 flags 0x00 dlen 12             #587 [hci2] 103.629137
      L2CAP: Disconnection Request (0x06) ident 8 len 4
> HCI Event: Number of Completed Packets (0x13) plen 5   #588 [hci2] 103.727609
        Num handles: 1
        Handle: 129 Address: C0:B8:83:34:F4:62 (Intel Corporate)
        Channel: 66 [PSM 3 mode Basic (0x00)] {chan 2}
        Channel Latency: 98 msec (42-205 msec ~97 msec)
> HCI Event: Number of Completed Packets (0x13) plen 5   #589 [hci2] 103.728125
        Num handles: 1
        Handle: 129 Address: C0:B8:83:34:F4:62 (Intel Corporate)
> ACL Data RX: Handle 129 flags 0x02 dlen 12             #590 [hci2] 103.838154
      L2CAP: Disconnection Response (0x07) ident 8 len 4
> HCI Event: Disconnect Complete (0x05) plen 4           #591 [hci2] 105.911512
        Handle: 129 Address: C0:B8:83:34:F4:62 (Intel Corporate)
@ MGMT Event: Device Disconnected (0x000c) plen 8    {0x0001} [hci2] 105.911569
          Discoverable
@ MGMT Command: Set Discoverable (0x0006) plen 3     {0x0001} [hci2] 108.093466
        Discoverable: General (0x01)
      Set Discoverable (0x0006) plen 4
          Discoverable
```

### phone (1702 lines)
```
      Channel: 66 len 16 [PSM 3 mode Basic (0x00)] {chan 2}
      RFCOMM: Unnumbered Info with Header Check (UIH) (0xef)
> ACL Data RX: Handle 256 flags 0x02 dlen 20             #525 [hci0] 100.728445
      Channel: 66 len 16 [PSM 3 mode Basic (0x00)] {chan 2}
      RFCOMM: Unnumbered Info with Header Check (UIH) (0xef)
< ACL Data TX: Handle 256 flags 0x00 dlen 8              #526 [hci0] 103.534038
      Channel: 66 len 4 [PSM 3 mode Basic (0x00)] {chan 2}
      RFCOMM: Disconnect (DISC) (0x43)
> HCI Event: Number of Completed Packets (0x13) plen 5   #527 [hci0] 103.539592
        Num handles: 1
        Handle: 256 Address: C8:C9:A3:CB:7B:0A (Espressif Inc.)
        Channel: 66 [PSM 3 mode Basic (0x00)] {chan 2}
        Channel Latency: 5 msec (3-109 msec ~16 msec)
> ACL Data RX: Handle 256 flags 0x02 dlen 8              #528 [hci0] 103.592431
      Channel: 66 len 4 [PSM 3 mode Basic (0x00)] {chan 2}
      RFCOMM: Unnumbered Ack (UA) (0x63)
< ACL Data TX: Handle 256 flags 0x00 dlen 8              #529 [hci0] 103.592598
      Channel: 66 len 4 [PSM 3 mode Basic (0x00)] {chan 2}
      RFCOMM: Disconnect (DISC) (0x43)
> HCI Event: Number of Completed Packets (0x13) plen 5   #530 [hci0] 103.620590
        Num handles: 1
        Handle: 256 Address: C8:C9:A3:CB:7B:0A (Espressif Inc.)
        Channel: 66 [PSM 3 mode Basic (0x00)] {chan 2}
        Channel Latency: 27 msec (3-109 msec ~22 msec)
> ACL Data RX: Handle 256 flags 0x02 dlen 8              #531 [hci0] 103.696470
      Channel: 66 len 4 [PSM 3 mode Basic (0x00)] {chan 2}
      RFCOMM: Unnumbered Ack (UA) (0x63)
> ACL Data RX: Handle 256 flags 0x02 dlen 12             #532 [hci0] 103.696474
      L2CAP: Disconnection Request (0x06) ident 8 len 4
< ACL Data TX: Handle 256 flags 0x00 dlen 12             #533 [hci0] 103.696569
      L2CAP: Disconnection Response (0x07) ident 8 len 4
> HCI Event: Number of Completed Packets (0x13) plen 5   #534 [hci0] 103.797614
        Num handles: 1
        Handle: 256 Address: C8:C9:A3:CB:7B:0A (Espressif Inc.)
< HCI Command: Disconnect (0x01|0x0006) plen 3           #535 [hci0] 105.719461
        Handle: 256 Address: C8:C9:A3:CB:7B:0A (Espressif Inc.)
      Disconnect (0x01|0x0006) ncmd 1
> HCI Event: Disconnect Complete (0x05) plen 4           #537 [hci0] 105.834639
        Handle: 256 Address: C8:C9:A3:CB:7B:0A (Espressif Inc.)
@ MGMT Event: Device Disconnected (0x000c) plen 8    {0x0001} [hci0] 105.834708
```

