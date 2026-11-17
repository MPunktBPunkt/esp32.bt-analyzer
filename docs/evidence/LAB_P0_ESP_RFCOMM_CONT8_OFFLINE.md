# P0 ESP/RFCOMM flap correlation

- hu: `docs/evidence/LAB_HOME_CONT8_20261117T1809Z_hu.jsonl`
- flaps: **7**
- by_reason: `{'eof': 5, 'write_error:11': 2}`
- by_class: `{'eof_rehandshake': 5, 'tx_pressure_during_etch_reply': 2}`
- hint: Many flaps during etch_reply TX → transport/ESP pressure candidate for missing phone-side replies (not Fall A).

1. ts=1794938214.749 reason=`eof` class=`eof_rehandshake` reconnect_s=33.651
2. ts=1794938273.697 reason=`write_error:11` class=`tx_pressure_during_etch_reply` reconnect_s=38.034
3. ts=1794938321.044 reason=`eof` class=`eof_rehandshake` reconnect_s=5.838
4. ts=1794938504.551 reason=`eof` class=`eof_rehandshake` reconnect_s=34.958
5. ts=1794938633.208 reason=`eof` class=`eof_rehandshake` reconnect_s=5.232
6. ts=1794938647.235 reason=`eof` class=`eof_rehandshake` reconnect_s=5.53
7. ts=1794938762.868 reason=`write_error:11` class=`tx_pressure_during_etch_reply` reconnect_s=87.223
