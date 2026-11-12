# LAB BCL synthetic stream — PASS

**UTC:** 20261112T060654Z · mode `rfcomm` · claim: decoder/messkette TEST only

| Check | Result |
|-------|--------|
| overall | PASS |
| stream_bytes | 47 |
| frames_decoded | 3 |
| transport_ok | PASS |
| decode_ok | PASS |
| RFCOMM channel | 5 |
| capture on host | `/tmp/bcl_synth_20261112T060649Z` |

## Frames

- [0] cmd=HANDSHAKE(4) src=0 dest=0(-) len=8 payload=`0000000000000000`
- [1] cmd=DATA(2) src=1 dest=4004(Etch) len=7 payload=`53594e54483031`
- [2] cmd=UNKNOWN(238) src=0 dest=0(-) len=0 payload=``

**Terminal error (expected for lab stream):** `{'error_code': 1, 'error_detail': 'payload_len_exceeds_kMaxPayload'}`

## Epistemic boundary

```text
YES:  synthetic BCL bytes → framer → JSONL events
YES:  fragmentation / PayloadTooLarge sticky error
NO:   BMW HU / Connected app wire claim
```

Next: Dummy-HU SDP/RFCOMM with known service, then A6/B1 on real HU.
