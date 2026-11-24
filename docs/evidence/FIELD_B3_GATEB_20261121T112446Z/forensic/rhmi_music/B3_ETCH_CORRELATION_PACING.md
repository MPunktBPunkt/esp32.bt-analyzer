# B3 Etch — Request/Response Correlation & Phone Request Pacing

```yaml
date: 2026-11-24
capture: FIELD_B3_GATEB_20261121T112446Z
machine: B3_ETCH_CORRELATION_PACING.json
method: whole-bin DEADBEEF + tools/etch_codec.decode_etch_message
supersedes_partial_index: ../ETCH_TIMELINE.json (910 msgs; incomplete vs full scan)
parent: B3_RHMI_MUSIC_FORENSIC_TIMELINE.md
```

## Verdict

**Kausalität** (Request ↔ Response ↔ HU-Push) ist für diesen Capture geschlossen genug für State-Machine-Arbeit.  
**RTT / Antwortlatenz in ms** ist **nicht** messbar — kein Phone-Empfangszeitstempel der Antwort. Keine „Latenzmatrix“ committen.

## 1. Envelope counts (FACT)

| Side | Total envelopes | Decode OK | Decode err |
|------|----------------:|----------:|-----------:|
| Phone→HU | 468 | **442** | 26 |
| HU→Phone | **619** | **619** | 0 |

## 2. Correlation (FACT)

| Class | n | Meaning |
|-------|--:|---------|
| HU with `_inReplyTo` | **449** | marked as replies |
| … bit-exact match to a decoded Phone `_messageId` | **426** | **DIRECT** request↔response |
| … `_inReplyTo` present but Phone request not in OK set | **23** | Phone **decode gap** on request body |
| HU with **no** `_inReplyTo` | **170** | **HU_PUSH** (no request expected) |

### 170 HU_PUSH — fully explained

| Method | n |
|--------|--:|
| `cds_onPropertyChangedEvent` | 155 |
| `rhmi_onHmiEvent` | 9 |
| `rhmi_onActionEvent` | 4 |
| `av_requestPlayerState` | 1 |
| `av_connectionGranted` | 1 |

These are **not** unmatched responses and **not** a correlation hole.

### 23 residual `_inReplyTo` without decoded Phone request

| Method | n | Cause |
|--------|--:|-------|
| `_result_sas_certificate` | 19 | Phone `sas_certificate` envelopes fail `etch_codec` (0/… decoded in this pass) |
| `_result_rhmi_setData` | 4 | Phone request envelope decode fail (incl. large cover-class bodies) |

→ **Decode-Lücke auf Phone-Requests**, nicht „HU-initiiert unklar“.

### Note on older `ETCH_TIMELINE.json` numbers

Partial index reported ~319/427 matches and ~108 misses (mostly `_result_rhmi_setData` / `setProperty`). **Full scan supersedes that** for correlation completeness: pushes = 170 explained; remaining miss class = 23 decode-linked.

## 3. What the IDs allow / forbid

| Allowed | Forbidden |
|---------|-----------|
| Pair via Phone `_messageId` ↔ HU `_inReplyTo` | Round-trip latency (ms) |
| Classify **REQUEST** / **RESPONSE** / **HU_PUSH** | HU-internal processing time |
| Phone outbound **request gaps** on Phone clock | Shared Phone↔HU wall clock |
| Annotate Music spine causally (Action = PUSH, `_result_*` = RESPONSE) | Treating HU `message_id` counter as session wall time |

Phone send mid is on Phone clock; HU reply mid is HU counter / µs-scale — **correlation key only**, not a second time base for RTT.

## 4. Phone request pacing (FACT — outbound gaps only)

Gaps = consecutive Phone `_messageId` deltas for the **same method** (ms).  
**Not** HU answer time. Useful as AAIdrive pacing reference for PiDrive.

| Method | n | Median gap | P95 | Max |
|--------|--:|----------:|----:|----:|
| `rhmi_setData` | 192 | **23 ms** | 111 | 444 |
| `rhmi_setProperty` | 50 | **37 ms** | 370 | 1702 |
| `rhmi_checkResource` | 11 | **~16 ms** | 362 | 362 |
| `rhmi_initialize` | 5 | **46 ms** | 399 | 399 |
| `am_registerApp` | 5 | **142 ms** | 2487 | 2487 |
| `sas_login` | 18 | **31 ms** | 12119 | 98166 |

Large SAS / AM maxima = **reconnect / multi-INIT concat waves**, not steady-state Music UI pacing.

## 5. Impact on Music forensic timeline

Spine order unchanged:

```text
Action 336 (HU_PUSH) → ack/AV REQUEST/RESPONSE → NP setData → PLAY → 661 → 248 (HU_PUSH) → 660
```

Upgrade: annotate each step as REQUEST / RESPONSE / HU_PUSH using `_inReplyTo` where present.  
Do **not** re-sort by invented RTT.

## 6. Next (priority)

1. Causally classified full-session chain (Connect → Music) — higher value than CSV dump of all envelopes.  
2. Optional: fix `sas_certificate` / large `setData` decode so the 23 residual pairs become DIRECT.  
3. Dual-plane capture with shared monotone clock — only path to real transport latency (P0 audio boundary).
