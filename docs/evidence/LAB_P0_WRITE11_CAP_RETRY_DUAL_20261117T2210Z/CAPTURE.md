# LAB P0 write11 capture — LAB_P0_WRITE11_CAP_RETRY_DUAL_20261117T2210Z

- hold.ok: **True**
- wait_class: `None`
- abort: `None`
- center_ts: `None` (±1.0s)
- tx_write_failed errno: `None (None)` attempted=None tx_total=None since_rx=Nones
- rfcomm_closed: `None`
- eagain: `{"events": 2, "recovered": 2, "recovered_wait_s_max": 0.204, "recovered_retries_max": 11}`

## Session TX

- HU: {"tx_frames": 179, "tx_bytes": 8195, "tx_max": 500, "rx_frames": 80, "rx_bytes": 18744, "mean_tx_gap_s": 0.4875, "min_tx_gap_s": 0.0, "last_methods": ["am_registerApp", "am_registerApp", "am_registerApp", "av_requestConnection", "rhmi_checkResource", "rhmi_setResource", "rhmi_checkResource", "rhmi_checkResource", "rhmi_initialize", "rhmi_setData", "rhmi_setData", "rhmi_setData"]}
- Phone: {"tx_frames": 59, "tx_bytes": 18524, "tx_max": 4008, "rx_frames": 139, "rx_bytes": 8195, "mean_tx_gap_s": 0.0601, "min_tx_gap_s": 0.0, "last_methods": ["_result_rhmi_setResource", "_result_rhmi_checkResource", "rhmi_checkResource", "_result_rhmi_checkResource", "rhmi_initialize", "rhmi_setData", "rhmi_setData", "rhmi_setData", "_result_rhmi_initialize", "_result_rhmi_setData", "_result_rhmi_setData", "_result_rhmi_setData"]}

## Hints

- EAGAIN recovered without close (2×) — write-policy mitigation held
- no terminal write_error:11 — session survived EAGAIN via retry/poll
- EAGAIN recovered 2× (max wait 0.204s / retries 11)
- no write_error:11 in this capture (mitigation may be holding)

## HU window (compact)

```json
[]
```

## btmon kept-line tails

### hu (2106 lines)
```
      Channel: 66 len 4 [PSM 3 mode Basic (0x00)] {chan 2}
      RFCOMM: Unnumbered Ack (UA) (0x63)
> HCI Event: Number of Completed Packets (0x13) plen 5   #584 [hci2] 113.444527
        Num handles: 1
        Handle: 128 Address: C8:C9:A3:CB:37:96 (Espressif Inc.)
        Channel: 66 [PSM 3 mode Basic (0x00)] {chan 2}
        Channel Latency: 102 msec (51-204 msec ~102 msec)
> ACL Data RX: Handle 128 flags 0x02 dlen 8              #585 [hci2] 113.544888
      Channel: 66 len 4 [PSM 3 mode Basic (0x00)] {chan 2}
      RFCOMM: Disconnect (DISC) (0x43)
< ACL Data TX: Handle 128 flags 0x00 dlen 8              #586 [hci2] 113.545456
      Channel: 66 len 4 [PSM 3 mode Basic (0x00)] {chan 2}
      RFCOMM: Unnumbered Ack (UA) (0x63)
< ACL Data TX: Handle 128 flags 0x00 dlen 12             #587 [hci2] 113.545471
      L2CAP: Disconnection Request (0x06) ident 8 len 4
> HCI Event: Number of Completed Packets (0x13) plen 5   #588 [hci2] 113.652111
        Num handles: 1
        Handle: 128 Address: C8:C9:A3:CB:37:96 (Espressif Inc.)
        Channel: 66 [PSM 3 mode Basic (0x00)] {chan 2}
        Channel Latency: 106 msec (51-204 msec ~104 msec)
> HCI Event: Number of Completed Packets (0x13) plen 5   #589 [hci2] 113.654158
        Num handles: 1
        Handle: 128 Address: C8:C9:A3:CB:37:96 (Espressif Inc.)
> ACL Data RX: Handle 128 flags 0x02 dlen 12             #590 [hci2] 113.758764
      L2CAP: Disconnection Request (0x06) ident 9 len 4
< ACL Data TX: Handle 128 flags 0x00 dlen 12             #591 [hci2] 113.758830
      L2CAP: Disconnection Response (0x07) ident 9 len 4
> ACL Data RX: Handle 128 flags 0x02 dlen 12             #592 [hci2] 113.764511
      L2CAP: Disconnection Response (0x07) ident 8 len 4
> HCI Event: Number of Completed Packets (0x13) plen 5   #593 [hci2] 113.864134
        Num handles: 1
        Handle: 128 Address: C8:C9:A3:CB:37:96 (Espressif Inc.)
> HCI Event: Disconnect Complete (0x05) plen 4           #594 [hci2] 116.024936
        Handle: 128 Address: C8:C9:A3:CB:37:96 (Espressif Inc.)
@ MGMT Event: Device Disconnected (0x000c) plen 8    {0x0001} [hci2] 116.024999
          Discoverable
@ MGMT Command: Set Discoverable (0x0006) plen 3     {0x0001} [hci2] 118.633508
        Discoverable: General (0x01)
      Set Discoverable (0x0006) plen 4
          Discoverable
```

### phone (1718 lines)
```
> ACL Data RX: Handle 129 flags 0x02 dlen 8              #739 [hci1] 113.453811
      Channel: 66 len 4 [PSM 3 mode Basic (0x00)] {chan 2}
      RFCOMM: Unnumbered Ack (UA) (0x63)
< ACL Data TX: Handle 129 flags 0x00 dlen 8              #740 [hci1] 113.453891
      Channel: 66 len 4 [PSM 3 mode Basic (0x00)] {chan 2}
      RFCOMM: Disconnect (DISC) (0x43)
> HCI Event: Number of Completed Packets (0x13) plen 5   #741 [hci1] 113.551541
        Num handles: 1
        Handle: 129 Address: C8:C9:A3:CB:7B:0A (Espressif Inc.)
        Channel: 66 [PSM 3 mode Basic (0x00)] {chan 2}
        Channel Latency: 97 msec (49-757 msec ~161 msec)
> ACL Data RX: Handle 129 flags 0x02 dlen 8              #742 [hci1] 113.652897
      Channel: 66 len 4 [PSM 3 mode Basic (0x00)] {chan 2}
      RFCOMM: Unnumbered Ack (UA) (0x63)
< ACL Data TX: Handle 129 flags 0x00 dlen 12             #743 [hci1] 113.652965
      L2CAP: Disconnection Request (0x06) ident 9 len 4
> ACL Data RX: Handle 129 flags 0x02 dlen 12             #744 [hci1] 113.661313
      L2CAP: Disconnection Request (0x06) ident 8 len 4
< ACL Data TX: Handle 129 flags 0x00 dlen 12             #745 [hci1] 113.661402
      L2CAP: Disconnection Response (0x07) ident 8 len 4
> HCI Event: Number of Completed Packets (0x13) plen 5   #746 [hci1] 113.761528
        Num handles: 1
        Handle: 129 Address: C8:C9:A3:CB:7B:0A (Espressif Inc.)
> HCI Event: Number of Completed Packets (0x13) plen 5   #747 [hci1] 113.767865
        Num handles: 1
        Handle: 129 Address: C8:C9:A3:CB:7B:0A (Espressif Inc.)
> ACL Data RX: Handle 129 flags 0x02 dlen 12             #750 [hci1] 113.868082
      L2CAP: Disconnection Response (0x07) ident 9 len 4
< HCI Command: Disconnect (0x01|0x0006) plen 3           #753 [hci1] 115.695464
        Handle: 129 Address: C8:C9:A3:CB:7B:0A (Espressif Inc.)
      Disconnect (0x01|0x0006) ncmd 5
> HCI Event: Disconnect Complete (0x05) plen 4           #755 [hci1] 115.941675
        Handle: 129 Address: C8:C9:A3:CB:7B:0A (Espressif Inc.)
@ MGMT Event: Device Disconnected (0x000c) plen 8    {0x0001} [hci1] 115.941731
        TX power: 3 dBm
          Discoverable
@ MGMT Command: Set Discoverable (0x0006) plen 3     {0x0001} [hci1] 118.632896
        Discoverable: General (0x01)
      Set Discoverable (0x0006) plen 4
          Discoverable
```

