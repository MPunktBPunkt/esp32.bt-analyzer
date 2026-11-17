# LAB Home continued tests — 20261117T1732Z

**link:** OnePlus Connected · HU f20_sim · log `hu_w0.jsonl`

## Results

| Test | Result |
|------|--------|
| CDS inject (VIN/RPM/fuel/odometer/lang) | **PASS** — `inject_cds_request` open_conns=1, TX on RFCOMM |
| RHMI action inject (actionId=541, handles 13–19) | **PASS (TX)** — `inject_rhmi_request` + `etch_data_tx` reason=inject_rhmi_action; phone ack not required for TX fact |
| AVRCP Play | **PASS** — Status paused→playing |
| AVRCP Next / Pause | issued (Pause after Next) |
| Alias race | still fights to BT-Analyzer-.87; pin loop active |

## Notes

- RFCOMM had brief `write_error:11` / eof flap earlier; session re-handshaked + SAS ok before injects.
- STOP_AFTER agent still running; full RHMI lifecycle continues phone-driven.
