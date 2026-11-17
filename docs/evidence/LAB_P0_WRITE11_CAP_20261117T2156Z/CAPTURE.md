# LAB P0 write11 capture — LAB_P0_WRITE11_CAP_20261117T2156Z

- hold.ok: **False**
- wait_class: `WATCHDOG_MISS_NO_ETCH_REPLY`
- abort: `wd_echo_miss_limit`
- center_ts: `1794948986.751` (±1.0s)
- tx_write_failed errno: `11 (EAGAIN)` attempted=89 tx_total=5250 since_rx=0.0006s
- rfcomm_closed: `write_error:11`

## Session TX

- HU: {"tx_frames": 93, "tx_bytes": 5250, "tx_max": 500, "rx_frames": 33, "rx_bytes": 2884, "mean_tx_gap_s": 0.012, "min_tx_gap_s": 0.0, "last_methods": ["cds_getPropertyAsync", "cds_addPropertyChangedEventHandler", "cds_getPropertyAsync", "cds_addPropertyChangedEventHandler", "cds_getPropertyAsync", "cds_addPropertyChangedEventHandler", "cds_getPropertyAsync", "cds_addPropertyChangedEventHandler", "cds_getPropertyAsync", "cds_addPropertyChangedEventHandler", "cds_getPropertyAsync", "cds_addPropertyChangedEventHandler"]}
- Phone: {"tx_frames": 49, "tx_bytes": 4315, "tx_max": 559, "rx_frames": 66, "rx_bytes": 5250, "mean_tx_gap_s": 0.015, "min_tx_gap_s": 0.0, "last_methods": ["cds_onPropertyChangedEvent", "_result_cds_getPropertyAsync", "cds_onPropertyChangedEvent", "_result_cds_addPropertyChangedEventHandler", "cds_onPropertyChangedEvent", "_result_cds_getPropertyAsync", "cds_onPropertyChangedEvent", "_result_cds_addPropertyChangedEventHandler", "cds_onPropertyChangedEvent", "_result_cds_getPropertyAsync", "cds_onPropertyChangedEvent", "_result_cds_addPropertyChangedEventHandler"]}

## Hints

- HU os.write failed with errno 11 (EAGAIN/EWOULDBLOCK) — transport not ready at write()
- phone classified abort as WATCHDOG_MISS_NO_ETCH_REPLY

## HU window (compact)

```json
[
  {
    "ts": 1794948985.813,
    "event": "rx_bytes",
    "n": 10
  },
  {
    "ts": 1794948985.813,
    "event": "frame",
    "cmd_name": "SELECTPROTO",
    "src": 0,
    "dest": 0
  },
  {
    "ts": 1794948985.813,
    "event": "phone_tx_classified",
    "cmd_name": "SELECTPROTO",
    "src": 0,
    "dest": 0
  },
  {
    "ts": 1794948985.813,
    "event": "dataack_tx"
  },
  {
    "ts": 1794948985.813,
    "event": "selectproto_rx"
  },
  {
    "ts": 1794948985.813,
    "event": "tx_bytes",
    "n": 12,
    "tx_total": 28,
    "tx_frames": 2
  },
  {
    "ts": 1794948985.815,
    "event": "rx_bytes",
    "n": 56
  },
  {
    "ts": 1794948985.815,
    "event": "frame",
    "cmd_name": "KNOCK",
    "src": 0,
    "dest": 0
  },
  {
    "ts": 1794948985.815,
    "event": "phone_tx_classified",
    "cmd_name": "KNOCK",
    "src": 0,
    "dest": 0
  },
  {
    "ts": 1794948985.815,
    "event": "dataack_tx"
  },
  {
    "ts": 1794948985.815,
    "event": "knock_rx"
  },
  {
    "ts": 1794948985.815,
    "event": "tx_bytes",
    "n": 12,
    "tx_total": 40,
    "tx_frames": 3
  },
  {
    "ts": 1794948985.817,
    "event": "rx_bytes",
    "n": 8
  },
  {
    "ts": 1794948985.818,
    "event": "frame",
    "cmd_name": "OPEN",
    "src": 5001,
    "dest": 5001
  },
  {
    "ts": 1794948985.818,
    "event": "phone_tx_classified",
    "cmd_name": "OPEN",
    "src": 5001,
    "dest": 5001
  },
  {
    "ts": 1794948985.818,
    "event": "dataack_tx"
  },
  {
    "ts": 1794948985.818,
    "event": "tx_bytes",
    "n": 12,
    "tx_total": 52,
    "tx_frames": 4
  },
  {
    "ts": 1794948985.821,
    "event": "rx_bytes",
    "n": 8
  },
  {
    "ts": 1794948985.821,
    "event": "frame",
    "cmd_name": "OPEN",
    "src": 10,
    "dest": 4004
  },
  {
    "ts": 1794948985.821,
    "event": "phone_tx_classified",
    "cmd_name": "OPEN",
    "src": 10,
    "dest": 4004
  },
  {
    "ts": 1794948985.821,
    "event": "dataack_tx"
  },
  {
    "ts": 1794948985.821,
    "event": "etch_open_rx",
    "src": 10,
    "dest": 4004
  },
  {
    "ts": 1794948985.821,
    "event": "etch_open_probe",
    "src": 10
  },
  {
    "ts": 1794948985.821,
    "event": "tx_bytes",
    "n": 12,
    "tx_total": 64,
    "tx_frames": 5
  },
  {
    "ts": 1794948985.822,
    "event": "rx_bytes",
    "n": 154
  },
  {
    "ts": 1794948985.826,
    "event": "frame",
    "cmd_name": "DATA",
    "src": 10,
    "dest": 4004
  },
  {
    "ts": 1794948985.826,
    "event": "phone_tx_classified",
    "cmd_name": "DATA",
    "src": 10,
    "dest": 4004
  },
  {
    "ts": 1794948985.826,
    "event": "dataack_tx"
  },
  {
    "ts": 1794948985.826,
    "event": "f20_rpc_rx",
    "method": "sas_certificate",
    "src": 10
  },
  {
    "ts": 1794948985.826,
    "event": "sas_challenge_tx",
    "src": 10
  },
  {
    "ts": 1794948985.826,
    "event": "etch_data_tx",
    "reason": "etch_reply",
    "src": 10,
    "dest": 4004
  },
  {
    "ts": 1794948985.826,
    "event": "tx_bytes",
    "n": 12,
    "tx_total": 76,
    "tx_frames": 6
  },
  {
    "ts": 1794948985.826,
    "event": "tx_bytes",
    "n": 75,
    "tx_total": 151,
    "tx_frames": 7
  },
  {
    "ts": 1794948985.826,
    "event": "rx_bytes",
    "n": 12
  },
  {
    "ts": 1794948985.827,
    "event": "frame",
    "cmd_name": "DATA",
    "src": 5001,
    "dest": 5001
  },
  {
    "ts": 1794948985.827,
    "event": "phone_tx_classified",
    "cmd_name": "DATA",
    "src": 5001,
    "dest": 5001
  },
  {
    "ts": 1794948985.827,
    "event": "dataack_tx"
  },
  {
    "ts": 1794948985.827,
    "event": "watchdog_echo"
  },
  {
    "ts": 1794948985.827,
    "event": "tx_bytes",
    "n": 12,
    "tx_total": 163,
    "tx_frames": 8
  },
  {
    "ts": 1794948985.827,
    "event": "tx_bytes",
    "n": 12,
    "tx_total": 175,
    "tx_frames": 9
  },
  {
    "ts": 1794948986.014,
    "event": "rx_bytes",
    "n": 559
  },
  {
    "ts": 1794948986.015,
    "event": "frame",
    "cmd_name": "DATA",
    "src": 10,
    "dest": 4004
  },
  {
    "ts": 1794948986.015,
    "event": "phone_tx_classified",
    "cmd_name": "DATA",
    "src": 10,
    "dest": 4004
  },
  {
    "ts": 1794948986.015,
    "event": "dataack_tx"
  },
  {
    "ts": 1794948986.015,
    "event": "f20_rpc_rx",
    "method": "sas_login",
    "src": 10
  },
  {
    "ts": 1794948986.015,
    "event": "sas_login_ok_tx",
    "src": 10
  },
  {
    "ts": 1794948986.015,
    "event": "etch_data_tx",
    "reason": "etch_reply",
    "src": 10,
    "dest": 4004
  },
  {
    "ts": 1794948986.015,
    "event": "tx_bytes",
    "n": 12,
    "tx_total": 187,
    "tx_frames": 10
  },
  {
    "ts": 1794948986.015,
    "event": "tx_bytes",
    "n": 52,
    "tx_total": 239,
    "tx_frames": 11
  },
  {
    "ts": 1794948986.222,
    "event": "rx_bytes",
    "n": 128
  },
  {
    "ts": 1794948986.223,
    "event": "frame",
    "cmd_name": "DATA",
    "src": 10,
    "dest": 4004
  },
  {
    "ts": 1794948986.223,
    "event": "frame",
    "cmd_name": "DATA",
    "src": 10,
    "dest": 4004
  },
  {
    "ts": 1794948986.223,
    "event": "frame",
    "cmd_name": "DATA",
    "src": 10,
    "dest": 4004
  },
  {
    "ts": 1794948986.223,
    "event": "phone_tx_classified",
    "cmd_name": "DATA",
    "src": 10,
    "dest": 4004
  },
  {
    "ts": 1794948986.223,
    "event": "dataack_tx"
  },
  {
    "ts": 1794948986.223,
    "event": "f20_rpc_rx",
    "method": "ver_getVersion",
    "src": 10
  },
  {
    "ts": 1794948986.223,
    "event": "etch_data_tx",
    "reason": "etch_reply",
    "src": 10,
    "dest": 4004
  },
  {
    "ts": 1794948986.223,
    "event": "phone_tx_classified",
    "cmd_name": "DATA",
    "src": 10,
    "dest": 4004
  },
  {
    "ts": 1794948986.223,
    "event": "dataack_tx"
  },
  {
    "ts": 1794948986.223,
    "event": "f20_rpc_rx",
    "method": "info_getSystemInfo",
    "src": 10
  },
  {
    "ts": 1794948986.223,
    "event": "etch_data_tx",
    "reason": "etch_reply",
    "src": 10,
    "dest": 4004
  },
  {
    
```

## btmon kept-line tails

### hu (1275 lines)
```
      RFCOMM: Unnumbered Info with Header Check (UIH) (0xef)
> ACL Data RX: Handle 128 flags 0x02 dlen 8               #362 [hci2] 42.074287
      Channel: 66 len 4 [PSM 3 mode Basic (0x00)] {chan 2}
      RFCOMM: Disconnect (DISC) (0x43)
< ACL Data TX: Handle 128 flags 0x00 dlen 8               #363 [hci2] 42.074369
      Channel: 66 len 4 [PSM 3 mode Basic (0x00)] {chan 2}
      RFCOMM: Unnumbered Ack (UA) (0x63)
> HCI Event: Number of Completed Packets (0x13) plen 5    #364 [hci2] 42.174622
        Num handles: 1
        Handle: 128 Address: C8:C9:A3:CB:37:96 (Espressif Inc.)
        Channel: 66 [PSM 3 mode Basic (0x00)] {chan 2}
        Channel Latency: 100 msec (62-176 msec ~97 msec)
> ACL Data RX: Handle 128 flags 0x02 dlen 8               #365 [hci2] 42.285670
      Channel: 66 len 4 [PSM 3 mode Basic (0x00)] {chan 2}
      RFCOMM: Disconnect (DISC) (0x43)
< ACL Data TX: Handle 128 flags 0x00 dlen 8               #366 [hci2] 42.285747
      Channel: 66 len 4 [PSM 3 mode Basic (0x00)] {chan 2}
      RFCOMM: Unnumbered Ack (UA) (0x63)
< ACL Data TX: Handle 128 flags 0x00 dlen 12              #367 [hci2] 42.285754
      L2CAP: Disconnection Request (0x06) ident 8 len 4
> HCI Event: Number of Completed Packets (0x13) plen 5    #368 [hci2] 42.380207
        Num handles: 1
        Handle: 128 Address: C8:C9:A3:CB:37:96 (Espressif Inc.)
        Channel: 66 [PSM 3 mode Basic (0x00)] {chan 2}
        Channel Latency: 94 msec (62-176 msec ~96 msec)
> HCI Event: Number of Completed Packets (0x13) plen 5    #369 [hci2] 42.382588
        Num handles: 1
        Handle: 128 Address: C8:C9:A3:CB:37:96 (Espressif Inc.)
> ACL Data RX: Handle 128 flags 0x02 dlen 12              #370 [hci2] 42.485335
      L2CAP: Disconnection Request (0x06) ident 9 len 4
> ACL Data RX: Handle 128 flags 0x02 dlen 12              #371 [hci2] 42.485343
      L2CAP: Disconnection Response (0x07) ident 8 len 4
< ACL Data TX: Handle 128 flags 0x00 dlen 12              #372 [hci2] 42.485400
      L2CAP: Disconnection Response (0x07) ident 9 len 4
> HCI Event: Number of Completed Packets (0x13) plen 5    #373 [hci2] 42.584048
        Num handles: 1
        Handle: 128 Address: C8:C9:A3:CB:37:96 (Espressif Inc.)
> HCI Event: Disconnect Complete (0x05) plen 4            #374 [hci2] 44.648515
        Handle: 128 Address: C8:C9:A3:CB:37:96 (Espressif Inc.)
@ MGMT Event: Device Disconnected (0x000c) plen 8     {0x0001} [hci2] 44.648552
```

### phone (1109 lines)
```
        Channel Latency: 167 msec (79-167 msec ~158 msec)
> ACL Data RX: Handle 129 flags 0x02 dlen 8               #435 [hci1] 41.174624
      Channel: 66 len 4 [PSM 3 mode Basic (0x00)] {chan 2}
      RFCOMM: Unnumbered Ack (UA) (0x63)
< ACL Data TX: Handle 129 flags 0x00 dlen 8               #436 [hci1] 41.174702
      Channel: 66 len 4 [PSM 3 mode Basic (0x00)] {chan 2}
      RFCOMM: Disconnect (DISC) (0x43)
> HCI Event: Number of Completed Packets (0x13) plen 5    #439 [hci1] 41.281849
        Num handles: 1
        Handle: 129 Address: C8:C9:A3:CB:7B:0A (Espressif Inc.)
        Channel: 66 [PSM 3 mode Basic (0x00)] {chan 2}
        Channel Latency: 107 msec (79-167 msec ~133 msec)
> ACL Data RX: Handle 129 flags 0x02 dlen 8               #440 [hci1] 41.382568
      Channel: 66 len 4 [PSM 3 mode Basic (0x00)] {chan 2}
      RFCOMM: Unnumbered Ack (UA) (0x63)
< ACL Data TX: Handle 129 flags 0x00 dlen 12              #441 [hci1] 41.382624
      L2CAP: Disconnection Request (0x06) ident 9 len 4
> ACL Data RX: Handle 129 flags 0x02 dlen 12              #442 [hci1] 41.392106
      L2CAP: Disconnection Request (0x06) ident 8 len 4
< ACL Data TX: Handle 129 flags 0x00 dlen 12              #443 [hci1] 41.392139
      L2CAP: Disconnection Response (0x07) ident 8 len 4
> HCI Event: Number of Completed Packets (0x13) plen 5    #444 [hci1] 41.485335
        Num handles: 1
        Handle: 129 Address: C8:C9:A3:CB:7B:0A (Espressif Inc.)
> HCI Event: Number of Completed Packets (0x13) plen 5    #445 [hci1] 41.485343
        Num handles: 1
        Handle: 129 Address: C8:C9:A3:CB:7B:0A (Espressif Inc.)
> ACL Data RX: Handle 129 flags 0x02 dlen 12              #446 [hci1] 41.590363
      L2CAP: Disconnection Response (0x07) ident 9 len 4
< HCI Command: Disconnect (0x01|0x0006) plen 3            #451 [hci1] 43.439712
        Handle: 129 Address: C8:C9:A3:CB:7B:0A (Espressif Inc.)
      Disconnect (0x01|0x0006) ncmd 5
> HCI Event: Disconnect Complete (0x05) plen 4            #453 [hci1] 43.563839
        Handle: 129 Address: C8:C9:A3:CB:7B:0A (Espressif Inc.)
@ MGMT Event: Device Disconnected (0x000c) plen 8     {0x0001} [hci1] 43.563892
          Discoverable
@ MGMT Command: Set Discoverable (0x0006) plen 3      {0x0001} [hci1] 46.552267
        Discoverable: General (0x01)
      Set Discoverable (0x0006) plen 4
          Discoverable
```

