# P0 ESP/RFCOMM flap correlation

- hu: `docs/evidence/LAB_HOME_GREEN_20261117T1749Z_hu.jsonl`
- flaps: **9**
- by_reason: `{'write_error:11': 3, 'eof': 6}`
- by_class: `{'other': 1, 'write11_then_eof_rehandshake': 1, 'eof_rehandshake': 5, 'tx_pressure_during_etch_reply': 1, 'eof': 1}`
- hint: Many flaps during etch_reply TX → transport/ESP pressure candidate for missing phone-side replies (not Fall A).

1. ts=1794934922.826 reason=`write_error:11` class=`write11_then_eof_rehandshake` reconnect_s=39.311
2. ts=1794934970.841 reason=`eof` class=`eof_rehandshake` reconnect_s=37.48
3. ts=1794935021.917 reason=`eof` class=`eof_rehandshake` reconnect_s=934.103
4. ts=1794935982.739 reason=`write_error:11` class=`tx_pressure_during_etch_reply` reconnect_s=39.287
5. ts=1794936031.027 reason=`eof` class=`eof_rehandshake` reconnect_s=5.015
6. ts=1794936168.993 reason=`eof` class=`eof_rehandshake` reconnect_s=743.021
7. ts=1794937010.918 reason=`eof` class=`eof_rehandshake` reconnect_s=38.455
8. ts=1794937310.186 reason=`eof` class=`eof` reconnect_s=None
