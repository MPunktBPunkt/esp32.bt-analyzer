# LAB P0 write11 capture — LAB_P0_WRITE11_CAP_SINGLE_20261117T2200Z

- hold.ok: **False**
- wait_class: `WATCHDOG_MISS_NO_ETCH_REPLY`
- abort: `wd_echo_miss_limit`
- center_ts: `1794949218.424` (±1.0s)
- tx_write_failed errno: `11 (EAGAIN)` attempted=89 tx_total=5250 since_rx=0.0004s
- rfcomm_closed: `write_error:11`

## Session TX

- HU: {"tx_frames": 93, "tx_bytes": 5250, "tx_max": 500, "rx_frames": 26, "rx_bytes": 2884, "mean_tx_gap_s": 0.0111, "min_tx_gap_s": 0.0, "last_methods": ["cds_getPropertyAsync", "cds_addPropertyChangedEventHandler", "cds_getPropertyAsync", "cds_addPropertyChangedEventHandler", "cds_getPropertyAsync", "cds_addPropertyChangedEventHandler", "cds_getPropertyAsync", "cds_addPropertyChangedEventHandler", "cds_getPropertyAsync", "cds_addPropertyChangedEventHandler", "cds_getPropertyAsync", "cds_addPropertyChangedEventHandler"]}
- Phone: {"tx_frames": 49, "tx_bytes": 4315, "tx_max": 559, "rx_frames": 63, "rx_bytes": 5250, "mean_tx_gap_s": 0.0128, "min_tx_gap_s": 0.0, "last_methods": ["cds_onPropertyChangedEvent", "_result_cds_getPropertyAsync", "cds_onPropertyChangedEvent", "_result_cds_addPropertyChangedEventHandler", "cds_onPropertyChangedEvent", "_result_cds_getPropertyAsync", "cds_onPropertyChangedEvent", "_result_cds_addPropertyChangedEventHandler", "cds_onPropertyChangedEvent", "_result_cds_getPropertyAsync", "cds_onPropertyChangedEvent", "_result_cds_addPropertyChangedEventHandler"]}

## Hints

- HU os.write failed with errno 11 (EAGAIN/EWOULDBLOCK) — transport not ready at write()
- phone classified abort as WATCHDOG_MISS_NO_ETCH_REPLY

## HU window (compact)

```json
[
  {
    "ts": 1794949217.498,
    "event": "rx_bytes",
    "n": 10
  },
  {
    "ts": 1794949217.498,
    "event": "frame",
    "cmd_name": "SELECTPROTO",
    "src": 0,
    "dest": 0
  },
  {
    "ts": 1794949217.498,
    "event": "phone_tx_classified",
    "cmd_name": "SELECTPROTO",
    "src": 0,
    "dest": 0
  },
  {
    "ts": 1794949217.498,
    "event": "dataack_tx"
  },
  {
    "ts": 1794949217.498,
    "event": "selectproto_rx"
  },
  {
    "ts": 1794949217.498,
    "event": "tx_bytes",
    "n": 12,
    "tx_total": 28,
    "tx_frames": 2
  },
  {
    "ts": 1794949217.595,
    "event": "rx_bytes",
    "n": 56
  },
  {
    "ts": 1794949217.595,
    "event": "frame",
    "cmd_name": "KNOCK",
    "src": 0,
    "dest": 0
  },
  {
    "ts": 1794949217.595,
    "event": "phone_tx_classified",
    "cmd_name": "KNOCK",
    "src": 0,
    "dest": 0
  },
  {
    "ts": 1794949217.595,
    "event": "dataack_tx"
  },
  {
    "ts": 1794949217.595,
    "event": "knock_rx"
  },
  {
    "ts": 1794949217.595,
    "event": "tx_bytes",
    "n": 12,
    "tx_total": 40,
    "tx_frames": 3
  },
  {
    "ts": 1794949217.6,
    "event": "rx_bytes",
    "n": 170
  },
  {
    "ts": 1794949217.604,
    "event": "frame",
    "cmd_name": "OPEN",
    "src": 5001,
    "dest": 5001
  },
  {
    "ts": 1794949217.604,
    "event": "frame",
    "cmd_name": "OPEN",
    "src": 10,
    "dest": 4004
  },
  {
    "ts": 1794949217.604,
    "event": "frame",
    "cmd_name": "DATA",
    "src": 10,
    "dest": 4004
  },
  {
    "ts": 1794949217.604,
    "event": "phone_tx_classified",
    "cmd_name": "OPEN",
    "src": 5001,
    "dest": 5001
  },
  {
    "ts": 1794949217.604,
    "event": "dataack_tx"
  },
  {
    "ts": 1794949217.604,
    "event": "phone_tx_classified",
    "cmd_name": "OPEN",
    "src": 10,
    "dest": 4004
  },
  {
    "ts": 1794949217.604,
    "event": "dataack_tx"
  },
  {
    "ts": 1794949217.604,
    "event": "etch_open_rx",
    "src": 10,
    "dest": 4004
  },
  {
    "ts": 1794949217.604,
    "event": "etch_open_probe",
    "src": 10
  },
  {
    "ts": 1794949217.604,
    "event": "phone_tx_classified",
    "cmd_name": "DATA",
    "src": 10,
    "dest": 4004
  },
  {
    "ts": 1794949217.604,
    "event": "dataack_tx"
  },
  {
    "ts": 1794949217.604,
    "event": "f20_rpc_rx",
    "method": "sas_certificate",
    "src": 10
  },
  {
    "ts": 1794949217.604,
    "event": "sas_challenge_tx",
    "src": 10
  },
  {
    "ts": 1794949217.604,
    "event": "etch_data_tx",
    "reason": "etch_reply",
    "src": 10,
    "dest": 4004
  },
  {
    "ts": 1794949217.604,
    "event": "tx_bytes",
    "n": 12,
    "tx_total": 52,
    "tx_frames": 4
  },
  {
    "ts": 1794949217.604,
    "event": "tx_bytes",
    "n": 12,
    "tx_total": 64,
    "tx_frames": 5
  },
  {
    "ts": 1794949217.604,
    "event": "tx_bytes",
    "n": 12,
    "tx_total": 76,
    "tx_frames": 6
  },
  {
    "ts": 1794949217.604,
    "event": "tx_bytes",
    "n": 75,
    "tx_total": 151,
    "tx_frames": 7
  },
  {
    "ts": 1794949217.604,
    "event": "rx_bytes",
    "n": 12
  },
  {
    "ts": 1794949217.604,
    "event": "frame",
    "cmd_name": "DATA",
    "src": 5001,
    "dest": 5001
  },
  {
    "ts": 1794949217.604,
    "event": "phone_tx_classified",
    "cmd_name": "DATA",
    "src": 5001,
    "dest": 5001
  },
  {
    "ts": 1794949217.604,
    "event": "dataack_tx"
  },
  {
    "ts": 1794949217.604,
    "event": "watchdog_echo"
  },
  {
    "ts": 1794949217.604,
    "event": "tx_bytes",
    "n": 12,
    "tx_total": 163,
    "tx_frames": 8
  },
  {
    "ts": 1794949217.604,
    "event": "tx_bytes",
    "n": 12,
    "tx_total": 175,
    "tx_frames": 9
  },
  {
    "ts": 1794949217.713,
    "event": "rx_bytes",
    "n": 559
  },
  {
    "ts": 1794949217.713,
    "event": "frame",
    "cmd_name": "DATA",
    "src": 10,
    "dest": 4004
  },
  {
    "ts": 1794949217.713,
    "event": "phone_tx_classified",
    "cmd_name": "DATA",
    "src": 10,
    "dest": 4004
  },
  {
    "ts": 1794949217.713,
    "event": "dataack_tx"
  },
  {
    "ts": 1794949217.713,
    "event": "f20_rpc_rx",
    "method": "sas_login",
    "src": 10
  },
  {
    "ts": 1794949217.713,
    "event": "sas_login_ok_tx",
    "src": 10
  },
  {
    "ts": 1794949217.713,
    "event": "etch_data_tx",
    "reason": "etch_reply",
    "src": 10,
    "dest": 4004
  },
  {
    "ts": 1794949217.713,
    "event": "tx_bytes",
    "n": 12,
    "tx_total": 187,
    "tx_frames": 10
  },
  {
    "ts": 1794949217.713,
    "event": "tx_bytes",
    "n": 52,
    "tx_total": 239,
    "tx_frames": 11
  },
  {
    "ts": 1794949217.81,
    "event": "rx_bytes",
    "n": 38
  },
  {
    "ts": 1794949217.81,
    "event": "frame",
    "cmd_name": "DATA",
    "src": 10,
    "dest": 4004
  },
  {
    "ts": 1794949217.81,
    "event": "phone_tx_classified",
    "cmd_name": "DATA",
    "src": 10,
    "dest": 4004
  },
  {
    "ts": 1794949217.81,
    "event": "dataack_tx"
  },
  {
    "ts": 1794949217.81,
    "event": "f20_rpc_rx",
    "method": "ver_getVersion",
    "src": 10
  },
  {
    "ts": 1794949217.81,
    "event": "etch_data_tx",
    "reason": "etch_reply",
    "src": 10,
    "dest": 4004
  },
  {
    "ts": 1794949217.81,
    "event": "tx_bytes",
    "n": 12,
    "tx_total": 251,
    "tx_frames": 12
  },
  {
    "ts": 1794949217.81,
    "event": "tx_bytes",
    "n": 83,
    "tx_total": 334,
    "tx_frames": 13
  },
  {
    "ts": 1794949217.902,
    "event": "rx_bytes",
    "n": 38
  },
  {
    "ts": 1794949217.903,
    "event": "frame",
    "cmd_name": "DATA",
    "src": 10,
    "dest": 4004
  },
  {
    "ts": 1794949217.903,
    "event": "phone_tx_classified",
    "cmd_name": "DATA",
    "src": 10,
    "dest": 4004
  },
  {
    "ts": 1794949217.903,
    "event": "dataack_tx"
  },
  {
    "ts": 1794949217.903,
    "event": "f20_rpc_rx",
    "method": "info_getSystemInfo",
    "src": 10
  },
  {
    "ts": 1794949217.903,
    "event": "etch_data_tx",
    "reason": "etch_reply",
    "src": 
```

## btmon kept-line tails

### hu (1281 lines)
```
> ACL Data RX: Handle 129 flags 0x02 dlen 20              #361 [hci2] 31.543513
      Channel: 66 len 16 [PSM 3 mode Basic (0x00)] {chan 2}
      RFCOMM: Unnumbered Info with Header Check (UIH) (0xef)
> ACL Data RX: Handle 129 flags 0x02 dlen 8               #362 [hci2] 36.559282
      Channel: 66 len 4 [PSM 3 mode Basic (0x00)] {chan 2}
      RFCOMM: Disconnect (DISC) (0x43)
< ACL Data TX: Handle 129 flags 0x00 dlen 8               #363 [hci2] 36.559348
      Channel: 66 len 4 [PSM 3 mode Basic (0x00)] {chan 2}
      RFCOMM: Unnumbered Ack (UA) (0x63)
> HCI Event: Number of Completed Packets (0x13) plen 5    #364 [hci2] 36.661109
        Num handles: 1
        Handle: 129 Address: C0:B8:83:34:F4:62 (Intel Corporate)
        Channel: 66 [PSM 3 mode Basic (0x00)] {chan 2}
        Channel Latency: 101 msec (60-193 msec ~117 msec)
> ACL Data RX: Handle 129 flags 0x02 dlen 8               #365 [hci2] 36.761824
      Channel: 66 len 4 [PSM 3 mode Basic (0x00)] {chan 2}
      RFCOMM: Disconnect (DISC) (0x43)
< ACL Data TX: Handle 129 flags 0x00 dlen 8               #366 [hci2] 36.761916
      Channel: 66 len 4 [PSM 3 mode Basic (0x00)] {chan 2}
      RFCOMM: Unnumbered Ack (UA) (0x63)
< ACL Data TX: Handle 129 flags 0x00 dlen 12              #367 [hci2] 36.761934
      L2CAP: Disconnection Request (0x06) ident 8 len 4
> HCI Event: Number of Completed Packets (0x13) plen 5    #368 [hci2] 36.857789
        Num handles: 1
        Handle: 129 Address: C0:B8:83:34:F4:62 (Intel Corporate)
        Channel: 66 [PSM 3 mode Basic (0x00)] {chan 2}
        Channel Latency: 95 msec (60-193 msec ~106 msec)
> HCI Event: Number of Completed Packets (0x13) plen 5    #369 [hci2] 36.865525
        Num handles: 1
        Handle: 129 Address: C0:B8:83:34:F4:62 (Intel Corporate)
> ACL Data RX: Handle 129 flags 0x02 dlen 12              #370 [hci2] 36.867801
      L2CAP: Disconnection Response (0x07) ident 8 len 4
> HCI Event: Disconnect Complete (0x05) plen 4            #371 [hci2] 39.114691
        Handle: 129 Address: C0:B8:83:34:F4:62 (Intel Corporate)
@ MGMT Event: Device Disconnected (0x000c) plen 8     {0x0001} [hci2] 39.114723
          Discoverable
@ MGMT Command: Set Discoverable (0x0006) plen 3      {0x0001} [hci2] 41.508316
        Discoverable: General (0x01)
      Set Discoverable (0x0006) plen 4
          Discoverable
```

### phone (1112 lines)
```
> HCI Event: Number of Completed Packets (0x13) plen 5    #355 [hci0] 31.531843
        Num handles: 1
        Handle: 256 Address: C8:C9:A3:CB:7B:0A (Espressif Inc.)
        Channel: 66 [PSM 3 mode Basic (0x00)] {chan 2}
        Channel Latency: 8 msec (4-110 msec ~25 msec)
< ACL Data TX: Handle 256 flags 0x00 dlen 8               #356 [hci0] 36.531670
      Channel: 66 len 4 [PSM 3 mode Basic (0x00)] {chan 2}
      RFCOMM: Disconnect (DISC) (0x43)
> ACL Data RX: Handle 256 flags 0x02 dlen 8               #357 [hci0] 36.621431
      Channel: 66 len 4 [PSM 3 mode Basic (0x00)] {chan 2}
      RFCOMM: Unnumbered Ack (UA) (0x63)
< ACL Data TX: Handle 256 flags 0x00 dlen 8               #358 [hci0] 36.621493
      Channel: 66 len 4 [PSM 3 mode Basic (0x00)] {chan 2}
      RFCOMM: Disconnect (DISC) (0x43)
> HCI Event: Number of Completed Packets (0x13) plen 5    #359 [hci0] 36.621907
        Num handles: 1
        Handle: 256 Address: C8:C9:A3:CB:7B:0A (Espressif Inc.)
        Channel: 66 [PSM 3 mode Basic (0x00)] {chan 2}
        Channel Latency: 90 msec (4-110 msec ~57 msec)
> HCI Event: Number of Completed Packets (0x13) plen 5    #360 [hci0] 36.725937
        Num handles: 1
        Handle: 256 Address: C8:C9:A3:CB:7B:0A (Espressif Inc.)
        Channel: 66 [PSM 3 mode Basic (0x00)] {chan 2}
        Channel Latency: 104 msec (4-110 msec ~81 msec)
> ACL Data RX: Handle 256 flags 0x02 dlen 8               #361 [hci0] 36.826906
      Channel: 66 len 4 [PSM 3 mode Basic (0x00)] {chan 2}
      RFCOMM: Unnumbered Ack (UA) (0x63)
> ACL Data RX: Handle 256 flags 0x02 dlen 12              #362 [hci0] 36.826908
      L2CAP: Disconnection Request (0x06) ident 8 len 4
< ACL Data TX: Handle 256 flags 0x00 dlen 12              #363 [hci0] 36.826954
      L2CAP: Disconnection Response (0x07) ident 8 len 4
> HCI Event: Number of Completed Packets (0x13) plen 5    #364 [hci0] 36.927927
        Num handles: 1
        Handle: 256 Address: C8:C9:A3:CB:7B:0A (Espressif Inc.)
< HCI Command: Disconnect (0x01|0x0006) plen 3            #365 [hci0] 38.887489
        Handle: 256 Address: C8:C9:A3:CB:7B:0A (Espressif Inc.)
      Disconnect (0x01|0x0006) ncmd 1
> HCI Event: Disconnect Complete (0x05) plen 4            #367 [hci0] 39.017971
        Handle: 256 Address: C8:C9:A3:CB:7B:0A (Espressif Inc.)
@ MGMT Event: Device Disconnected (0x000c) plen 8     {0x0001} [hci0] 39.018013
```

