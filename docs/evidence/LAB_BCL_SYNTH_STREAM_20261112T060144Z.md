# LAB BCL synthetic stream — PASS

**UTC:** 20261112T060144Z · mode `offline` · claim: decoder/messkette TEST only

| Check | Result |
|-------|--------|
| overall | PASS |
| stream_bytes | 47 |
| frames_decoded | 3 |
| handshake_cmd4 | PASS |
| data_synth01 | PASS |
| unknown_cmd_ee | PASS |
| payload_too_large | PASS |
| oneshot_matches_chunked_count | PASS |

## Frames

- [0] cmd=HANDSHAKE(4) src=0 dest=0(-) len=8 payload=`0000000000000000`
- [1] cmd=DATA(2) src=1 dest=4004(Etch) len=7 payload=`53594e54483031`
- [2] cmd=UNKNOWN(238) src=0 dest=0(-) len=0 payload=``

**Terminal error (expected for lab stream):** `{'t_us': 1794463304211336, 'error_code': 1, 'error_name': 'PAYLOAD_TOO_LARGE', 'error_detail': 'payload_len_exceeds_kMaxPayload', 'chunk_i': 5}`

## Epistemic boundary

```text
YES:  synthetic BCL bytes → framer → JSONL events
YES:  fragmentation / PayloadTooLarge sticky error
NO:   BMW HU / Connected app wire claim
```

Next: Dummy-HU SDP/RFCOMM with known service, then A6/B1 on real HU.
