# FIELD REPLAY — FSM report

**origin:** `field` · **transport:** `replay` · **epistemic_status:** `field_measured`
**auth_verdict:** `fsm_certificate_rejected`
**source:** `docs/evidence/FIELD_DUMP_20261118T061746Z/bcl.jsonl`

> REPLAY FACT only — not FIELD PROTOCOL FACT; auth_verdict reflects our FSM classification of captured replies.

## Transport

```
{
  "RFCOMM_CONNECTED": true,
  "HANDSHAKE_RECEIVED": true,
  "handshake": {
    "version": 5,
    "instance_id": 14,
    "buffer_size": 16384
  },
  "PROTOCOL_SELECTED": true,
  "KNOCK_SENT": true,
  "BCL_ACTIVE": true,
  "claim": "REPLAY FACT"
}
```

## Etch

```
{
  "RPC_ACTIVE": true,
  "claim": "REPLAY FACT"
}
```

## Auth

```
{
  "AuthState": "CERTIFICATE_REJECTED",
  "rhmi_state_legacy": "DISCONNECTED",
  "claim": "REPLAY FACT"
}
```

## Bootstrap / AM / Resource / RHMI / Runtime

```
{
  "bootstrap": {
    "BootstrapState": "NOT_REACHED",
    "claim": "REPLAY FACT"
  },
  "am": {
    "AmState": "NOT_REACHED",
    "claim": "REPLAY FACT"
  },
  "resource": {
    "ResourceState": "NOT_REACHED",
    "claim": "REPLAY FACT"
  },
  "rhmi": {
    "RhmiState": "NOT_REACHED",
    "claim": "REPLAY FACT"
  },
  "runtime": {
    "RuntimeState": "NOT_REACHED",
    "claim": "REPLAY FACT"
  }
}
```

## Classified field replies (sample)

| method | classification | error_text |
|--------|----------------|------------|
| `_result_sas_certificate` | `EXCEPTION` | Certificate is invalid or expired. |

## phone forensic_snapshot

```json
{
  "rhmi_state": "DISCONNECTED",
  "auth_state": "CERTIFICATE_REJECTED",
  "etch_stage": "sas_cert",
  "bootstrap_state": "NOT_REACHED",
  "pending_check_mid": null,
  "open_txns": [],
  "plan_i": 0,
  "uploads": 0,
  "cache_hits": 0,
  "wait_class": "ETCH_REPLY_EXCEPTION",
  "last_result_class": "EXCEPTION",
  "last_exception_text": "Certificate is invalid or expired.",
  "soak_phase": null,
  "soak_counts": {},
  "soak_elapsed_s": null,
  "selected_action": null,
  "seq_phase": null
}
```
