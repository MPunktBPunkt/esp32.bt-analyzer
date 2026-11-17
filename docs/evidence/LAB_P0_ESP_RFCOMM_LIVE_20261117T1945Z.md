# P0 ESP/RFCOMM flap correlation

- hu: `/tmp/bcl_dummy/hu_recover.jsonl`
- flaps: **28**
- by_reason: `{'eof': 19, 'write_error:11': 9}`
- by_class: `{'eof_rehandshake': 18, 'tx_pressure_during_etch_reply': 6, 'write11_then_eof_rehandshake': 3, 'eof': 1}`
- hint: Many flaps during etch_reply TX → transport/ESP pressure candidate for missing phone-side replies (not Fall A).

- esp_once: `{'ts': 1794941231.0156755, 'ip': '192.168.178.131', 'uptime': '26min 27s', 'heap': 64148, 'resetReason': 'panic', 'restartCause': 'none', 'bootGen': 24, 'diagPrev': 530, 'diagSnaps': 2, 'recoveryHist': 1, 'recoveryLast': 'web_ota', 'hci_sessions': 2, 'hci_drops': 91, 'hci_framingErrors': 0, 'hci_writeRetries': 0, 'hci_client': '192.168.178.108', 'toHostBytes': 35475674, 'toCtrlBytes': 386293}`

1. ts=1794940074.703 reason=`eof` class=`eof_rehandshake` reconnect_s=5.132
2. ts=1794940198.406 reason=`eof` class=`eof_rehandshake` reconnect_s=4.72
3. ts=1794940211.93 reason=`eof` class=`eof_rehandshake` reconnect_s=5.12
4. ts=1794940317.205 reason=`write_error:11` class=`tx_pressure_during_etch_reply` reconnect_s=40.954
5. ts=1794940367.067 reason=`eof` class=`eof_rehandshake` reconnect_s=5.418
6. ts=1794940475.199 reason=`write_error:11` class=`tx_pressure_during_etch_reply` reconnect_s=41.989
7. ts=1794940526.201 reason=`eof` class=`eof_rehandshake` reconnect_s=6.439
8. ts=1794940536.245 reason=`eof` class=`eof` reconnect_s=None
