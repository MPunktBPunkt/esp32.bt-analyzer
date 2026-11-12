# LAB BCL synthetic stream — FAIL

**UTC:** 20261112T060426Z · mode `rfcomm` · claim: decoder/messkette TEST only

| Check | Result |
|-------|--------|
| overall | FAIL |
| stream_bytes | 47 |
| frames_decoded | 0 |
| transport_ok | FAIL |
| decode_ok | FAIL |
| RFCOMM channel | 5 |
| capture on host | `/tmp/bcl_synth_20261112T060425Z` |

## Frames


**Terminal error (expected for lab stream):** `{'error_code': None, 'error_detail': None}`

## Epistemic boundary

```text
YES:  synthetic BCL bytes → framer → JSONL events
YES:  fragmentation / PayloadTooLarge sticky error
NO:   BMW HU / Connected app wire claim
```

Next: Dummy-HU SDP/RFCOMM with known service, then A6/B1 on real HU.
