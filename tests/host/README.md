# Host tests

Offline decoder / framing tests without ESP hardware (BT7+).

BT0: no tests required beyond firmware build.

```bash
python3 -m unittest tests/host/test_hci_tcp_bridge.py tests/host/test_controller_live.py tests/host/test_bcl_sdp_probe.py
cd tests/host && c++ -std=c++17 -I ../../firmware/analyzer-node/src test_h4_framer.cpp -o h4 && ./h4
```
