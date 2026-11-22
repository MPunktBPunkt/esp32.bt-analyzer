# Field B3 Gate B — EVAL 2026-11-21 (rev. 2026-11-22)

```yaml
claim_level: FIELD MEASURED
gate_b: CLOSED
app_auth_rsa_verify: CLOSED (18/18)
topology: OnePlus/AAIdrive → BMW 38304 …:7B:0A (.131) → b3_profile_relay → …:37:96 (.87) → F20 D4:36:39:CF:E1:B5
operator_obs: AAIdrive green; Spotify + menu on HU; Halestorm / I Prevail + cover art on HU
evidence: docs/evidence/FIELD_B3_GATEB_20261121T112446Z/
raw_forensic: RAW_FORENSIC_ANALYSIS.md
rhmi_music: forensic/rhmi_music/RHMI_MUSIC_UI_STATE_MACHINE.md
gesamtstand: docs/analysis/GESAMTSTAND_F20_AAIDRIVE_SPOTIFY_20261122.md
```

## Verdict

> **Gate B ist geschlossen.** Der F20 akzeptierte live MyBMW/AAIdrive `APP_AUTH` Cert+Sig.  
> **RSA-VERIFY dieses Captures ist CLOSED:** 18/18 HU-akzeptierte 512-B-Logins gegen Wire-Leaf `a4a_app_BMWTouchCommand_Connection_00.00.10` (RSA-4096, Pad `0x02000000`).  
> Post-Auth: RHMI/AM/CDS/AV; Music-UI = Handle **23** (`…music`); Spotify ≠ AM.

Standalone-Signer ohne MyBMW bleibt **OPEN** (Signierträger).

## Artifacts (HAVE)

| Artifact | Inhalt |
|----------|--------|
| `raw/*.bin` | Byte-exact Phone↔HU |
| `RAW_FORENSIC_ANALYSIS.md` + `forensic/` | BCL/Etch reassembly, SAS cert/sigs, crypto |
| `SAS_CRYPTO_VERIFY.json` | **18/18 VALID** |
| `SAS_CERTIFICATE.der` / `.p7b` | TouchCommand leaf + PKCS#7 |
| `forensic/rhmi_music/` | Handle-23 graph, setData catalog, Spotify→modelIds |
| `b3.jsonl` | sekundär (Cert-TX / Fragments unterdekodiert) |
| `resources/ui_description_multimedia_v3.xml` | Music DESCRIPTION (MD5 `e9e31c31…`) |

## Gate B — Wire FACT

| Step | Evidence |
|------|----------|
| Cert | `sas_certificate` in Raw (PKCS#7); leaf RSA-4096 |
| Challenge | u. a. `8f873bb740471e52f36aa26093f580da` (+ 18 weitere) |
| Login | 512-B Sig; **RSA-VERIFY PASS** |
| Accept | `_result_sas_login` |
| Follow-on | RHMI/AM/CDS/AV + Music NP |

## Music / Spotify (rev. 2026-11-22)

| Observation | Level |
|-------------|-------|
| Handle 23 = `me.hufman.androidautoidrive.music` | **FACT** |
| `setData` 444+655 = `"Spotify"` | **FACT** |
| 445 artist / 446·447 title / 456 cover JPEG | **FACT** (+ XML roles **STRONG**) |
| AV `…music` → ENTERTAINMENT → PLAY | **FACT** |
| Spotify ∈ `am_registerApp` | **REJECTED** |
| Exakte Home-Menü-Widget-ID | **OPEN** |

## Epistemic

| Claim | Level |
|-------|-------|
| F20 akzeptiert live APP_AUTH | **FIELD FACT** |
| RSA-VERIFY Field raw | **FACT — CRYPTO VERIFIED** |
| Pad `0x02000000` | **FACT** |
| Halestorm/Spotify/Cover auf Wire | **FIELD FACT** |
| Standalone ohne MyBMW | **OPEN** |

## Related

- [`RAW_FORENSIC_ANALYSIS.md`](RAW_FORENSIC_ANALYSIS.md)
- [`ADDENDUM_RHMI_AM_20261121.md`](ADDENDUM_RHMI_AM_20261121.md)
- [`forensic/rhmi_music/RHMI_MUSIC_UI_STATE_MACHINE.md`](forensic/rhmi_music/RHMI_MUSIC_UI_STATE_MACHINE.md)
- [`GESAMTSTAND_F20_AAIDRIVE_SPOTIFY_20261122.md`](../../analysis/GESAMTSTAND_F20_AAIDRIVE_SPOTIFY_20261122.md)
- [`SAS_STATUS_CRYPTO_CLOSED_20261120.md`](../../analysis/SAS_STATUS_CRYPTO_CLOSED_20261120.md)
