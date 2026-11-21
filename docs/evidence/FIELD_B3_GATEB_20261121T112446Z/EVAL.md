# Field B3 Gate B — EVAL 2026-11-21

```yaml
claim_level: FIELD MEASURED
gate_b: CLOSED
topology: OnePlus/AAIdrive → BMW 38304 …:7B:0A (.131) → b3_profile_relay → …:37:96 (.87) → F20 D4:36:39:CF:E1:B5
operator_obs: AAIdrive green; Spotify + menu on HU; Halestorm / I Prevail + cover art on HU
evidence: docs/evidence/FIELD_B3_GATEB_20261121T112446Z/
```

## Verdict

> **Gate B ist geschlossen.** Der echte F20 akzeptierte live MyBMW/AAIdrive `APP_AUTH` Cert+Sig über den B3-Profile-Relay.  
> Danach lief der volle Bootstrap (RHMI/AM/CDS/AV); Media-Metadaten inkl. **„Halestorm, I Prevail“** und **Spotify** sind im Raw-Capture.

Standalone-Signer ohne MyBMW bleibt **OPEN** (Signierträger), nicht die HU-Akzeptanz.

## Was geloggt ist (HAVE)

| Artifact | Inhalt |
|----------|--------|
| `b3.jsonl` (2315 events) | BCL/Etch decode, SAS challenge/login, RHMI/AM/CDS/AV methods |
| `raw/phone_to_hu.bin` (~417 KB) | byte-exact Phone→F20 inkl. Track/Artist/Spotify ASCII |
| `raw/hu_to_phone.bin` (~111 KB) | HU→Phone inkl. Cover-Art capability strings |
| `btmon/*.btsnoop` | HCI beider ESP-Adapter |
| `sas_b2a_tx_*.jsonl` | Arm-A Stub → `CERTIFICATE_REJECTED` (Kontrollmessung) |
| `sdp_f20_*.txt` | F20 SPP ch6 = BCL |
| `tools/b3_profile_relay.py` | SPP SDP + transparent relay (Fix für AAIdrive-Wait) |

### Best relay session (FIELD)

```text
elapsed ≈ 62.4 s
phone→hu: 349213 B / 411 BCL frames / 301 etch
hu→phone:  87266 B /  12 BCL frames /   2 etch (decoded in that summary window)
```

Zweite längere Session ≈ 34 s (erneuter Auth-Pfad).

## Gate B — Wire FACT

| Step | Evidence |
|------|----------|
| HU Challenge | `_result_sas_certificate` plen=67 → `challenge_hex=8f873bb740471e52f36aa26093f580da` (2. Challenge später `0cebb994…`) |
| Phone Login | `sas_login` plen=551 → `login_sig_len=512` |
| HU Accept | `_result_sas_login` plen=44, `inReplyTo` korreliert |
| Follow-on | `rhmi_*`, `am_*`, `cds_*`, `av_create` / `av_requestConnection` |

Pad-Transform (`--from-jsonl`): `pad_u32=0x02000000`, Digest gebildet.  
Offline RSA-VERIFY gegen Wire-Cert aus diesem Capture: **noch nicht** (Etch-Decode loggte kein `sas_certificate`-PEM; Raw enthält die Bytes — Reassembly offen).

## Media / UI (operator + raw)

| Observation | Source |
|-------------|--------|
| AAIdrive grün | Operator |
| Spotify + Menü auf HU | Operator |
| Cover + Song auf HU | Operator |
| ASCII `Halestorm, I Prevail` | `raw/phone_to_hu.bin` @ ~112841 |
| ASCII `Spotify` | raw @ ~203486 |
| Playlist/Cover-Titel (u. a. Pink Floyd Cover) | raw |
| HU capability `iva_ENT_IAP_BLUETOOTH_COVERART` etc. | `raw/hu_to_phone.bin` |

Etch-`rhmi_setData` (105×) ist method-geloggt; Payload-Text steckt primär im Raw, nicht als fertige Strings im JSONL.

## Method histogram (etch)

Top: `rhmi_setData` 105 · `cds_*` ~100 · `sas_login` 18 · `rhmi_setProperty` 16 · `rhmi_checkResource` 11 · `am_registerApp` 5 · `rhmi_initialize` 5 · `_result_sas_certificate` 2 · `_result_sas_login` 2 · `av_create` 1 · `av_requestConnection` 1

## Post-Auth Template (Addendum)

Siehe [`ADDENDUM_RHMI_AM_20261121.md`](ADDENDUM_RHMI_AM_20261121.md):

- fünf `am_registerApp` inkl. Package/Kategorie/Weights (**FIELD**)
- Spotify ≠ AM; Media über `me.hufman.androidautoidrive.music` (**FIELD** / Handle 23 **STRONG**)
- 11× `checkResource=true`, kein `setResource` (**STRONG**)
- Music DESCRIPTION **CLOSED** — [`resources/ui_description_multimedia_v3.xml`](resources/ui_description_multimedia_v3.xml) (MD5 `e9e31c31…` / 92 085 B / SHA-256 `8e1d0b21…`); siehe [`resources/EXTRACT.md`](resources/EXTRACT.md)
- CDS-Property-Namen + 123 `iva_*` (**FIELD**)

## Gaps (nicht blockierend für Gate B)

1. **`sas_certificate` Etch-TX** fehlt im Decode (Session startete mit Challenge-Reply) — Cert-Bytes vermutlich in Raw vor Challenge; RSA-VERIFY-Pipeline noch nachziehen.
2. **Viele kurze Relays** danach (`Connection reset` / `Connection refused`) als Auto/ACL weg — Noise nach dem Erfolgsfenster.
3. **`btmon/*.btmon.txt`** nicht archiviert (nur `.btsnoop`).
4. **Ideal-Freeze** bei `AUTHENTICATED` nicht erzwungen — Session lief absichtlich in RHMI/Media (Operator-Nutzen); Gate-B-Beweis trotzdem vollständig.
5. **Minimal RHMI PoC** aus Handle-23-Korrelation ([`resources/HANDLE23_CORRELATION.md`](resources/HANDLE23_CORRELATION.md)) — DESCRIPTION + ID-Schnittmenge geschlossen; PoC/Field-Test offen.

## Epistemic

| Claim | Level |
|-------|-------|
| F20 akzeptiert live APP_AUTH Cert+Sig | **FIELD FACT** |
| B3 Profile-Relay trägt Phone↔F20 Bytes | **FIELD FACT** |
| Pad `0x02000000` auf Field-Challenge | **FIELD** (transform) / RSA-VERIFY pending |
| Halestorm/Spotify auf Wire | **FIELD FACT** (raw ASCII) |
| Standalone ohne MyBMW | **OPEN** |

## Related

- Canonical status update: `docs/analysis/SAS_STATUS_CRYPTO_CLOSED_20261120.md`
- Tool: `tools/b3_profile_relay.py`
- Prior lab: `LAB_B3_TCP_FULLAUTH_20261120T090004Z`
