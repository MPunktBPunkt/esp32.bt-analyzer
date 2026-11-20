# Lab B3 Full-Auth Eval — 2026-11-20

```yaml
claim: LAB
ok: true
auth_state: AUTHENTICATED
comparable_to: LAB_B3_TCP_FULLAUTH_20261119T091257Z
crypto_wire_ref: docs/analysis/SAS_PAD_RSA_VERIFY_LAB_20261120.md
status_ref: docs/analysis/SAS_STATUS_CRYPTO_CLOSED_20261120.md
```

## Prep verdict

| Check | Result |
|-------|--------|
| Host AuthState / golden / A/B / B3 / etch unit tests | **PASS** |
| Lab A/B matrix (`LAB_AUTH_AB_GATE_20261120T085450Z`) | **4/4 PASS** |
| B3 tcp-lab full_auth_freeze | **ok=True / AUTHENTICATED** |
| Event counts vs 2026-11-19 FULLAUTH | **identical** (HS=1, bcl=15, etch=4, methods SAS×4) |
| B3 logger: `challenge_hex` | **yes** |
| B3 logger: `login_sig_len/hex/sha256` | **yes** (512 B) |
| HU logger: `sas_challenge_tx` / `sas_login_ok_tx` live | **yes** (flush-on-event fix) |
| Stub cert → `effective_serial_u32` / APP_AUTH pad | **N/A** (LABSIM fake PKCS7; inspect fails) |
| RSA-VERIFY on stub session | **skipped** (no real Wire cert) — expected |
| MyBMW crypto Wire FACT | **unchanged 8/8** (separate capture) |

## Comparability (stack)

New run matches prior FULLAUTH event histogram exactly:

```text
listening/accepted/relay_start/handshake/bcl_frame×15/etch×4/eof/relay_done
etch: sas_certificate → _result_sas_certificate → sas_login → _result_sas_login
```

State machine: `AuthState=AUTHENTICATED`, freeze before AM/RHMI drain (`bootstrap_state=HANDLES_CREATING`). Same as 2026-11-19.

## Logger vs MyBMW capture

| Field | Lab stub B3 | MyBMW→f20_sim (`hu_pre_browse`) |
|-------|-------------|----------------------------------|
| challenge[16] | logged | logged / RSA-VERIFY used |
| login_sig[512] | logged | logged / RSA-VERIFY VALID |
| pad u32 | default `0x02000000` in crosscheck | **FACT** `0x02000000` |
| Wire Cert inspect | fail (stub) | APP_AUTH TouchCommand |
| RSA-VERIFY | skipped | **8/8 VALID** |

→ Lab run validates **relay + AuthState + logger plumbing**.  
→ Crypto acceptance math remains the MyBMW Wire FACT doc.  
→ Field B3 with live MyBMW should fill `effective_serial_u32=0x02000000` + RSA-VERIFY.

## Fixes in this session

1. `lab_b3_tcp_logged_test.py`: resolve `--out` absolute (B3 cwd=`tools/` had written logs under `tools/docs/...`).
2. HU subprocess: flush SAS sess events live (were lost when harness killed HU before end dump).
3. `sas_pad_crosscheck.py --from-jsonl`: reads B3 `etch.sas` (challenge + sig); RSA-VERIFY needs cert PEM or `--from-bcl-jsonl`.

## Field readiness

```text
READY for B3 Phone↔F20 with live MyBMW APP/APP_AUTH
  - stack + freeze + logger: LAB PASS
  - credential context: still OPEN (Gate B)
  - do not start further technology-audit first
```
