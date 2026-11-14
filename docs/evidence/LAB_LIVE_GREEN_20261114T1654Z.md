# LAB — Live green AAIdrive ↔ Dummy `.131` (non-destructive decode)

```yaml
id: LAB_LIVE_GREEN_20261114T1654Z
kind: lab_live_session
session_id: LAB_DUMMY_F20_20261114T165425Z
peer: Phone AC:C0:48:5E:CB:20 → Dummy C8:C9:A3:CB:7B:0A (.131 / hci2)
hu_agent: /tmp/bcl_dummy bcl_dummy_hu_agent.py --hu-profile f20
captured_at: 2026-11-14 ~18:11 CET (session still alive; WD ping ≥371)
summary: docs/evidence/LAB_LIVE_GREEN_summary.json
slim: docs/evidence/LAB_LIVE_GREEN_20261114T1654Z_session_slim.json
prior: docs/evidence/LAB_DUMMY_ETCH_20261114T1550Z.md
analysis: docs/analysis/LAB_DUMMY_ETCH_DEEP_20261114.md
```

## Verdict

Live-Grün **reproduziert** den bekannten Wire (HS v5 → SP4 → KNOCK → 3× Cert → WD). Neu gemessen: **Langstabilität** (~15 min+, **0** fehlende WD-Indexe) und: Stub sendet **3× SAS-Challenge** (`00…00`), Phone antwortet **nicht** mit `sas_login` — UI bleibt trotzdem grün nur auf WD-Echo.

Weitere Live-Tests an dieser Session bringen kaum Erkenntnisgewinn (Cert-Fenster ist zu). Nächster Lab-Hebel braucht **Reconnect** (besserer SAS-Stub) oder **Silent-HU** (Grün opfern).

## Wire (diese Session)

| Step | Wert |
|------|------|
| HS | version **5**, instanceId **14**, bufferSize **16384** (`0x4000`) |
| SELECTPROTO | **4** |
| KNOCK | serial `0e9b90c4-…56619`, appType **1**, param1 **7** |
| Certs | 6813 + 6126 + 6687 B (3× PKCS7 @ dest 4004) |
| SAS Challenge TX | 3×, `challenge_hex=0000…0000` (stub) |
| `sas_login_rx` | **0** |
| WD | ping 1…355+ @ mean **2.510 s** / median **2.512 s** (stdev 0.048) |

## Was Live-Grün **nicht** mehr klären kann

| Frage | Warum blockiert |
|-------|-----------------|
| Silent-Retry A/B (4@3 s) | braucht Dummy **ohne** HS/Pong |
| Echte SAS-Crypto / login | Challenge ist Null-Stub; Cert-Phase vorbei |
| F20-Proxy / HU Challenge | anderer Peer |
| HCI-Snoop Hex | Phone-Operator, nicht Dummy-JSONL |

## Recommendation

1. Grün belassen oder bewusst beenden.
2. **Next lab A:** Silent-HU (kein HS/Pong) → Feld-Retry kalibrieren.
3. **Next lab B:** Reconnect mit nicht-trivialem SAS-Stub / Simulator-Bridge → ob Phone `sas_login` sendet.
