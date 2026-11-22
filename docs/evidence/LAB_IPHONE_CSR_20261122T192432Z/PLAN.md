# LAB iPhone → CSR 71:02 — Analyse (Path B)

```yaml
topology: iPhone → CSR 00:1A:7D:DA:71:02 (hci3) → .108 f20_sim ch6 (optional answer)
goal: classify control path independently of AAIdrive B3
not_goal: B3 relay / F20 yet
```

## Hypothese (noch kein FACT)

```
Pfad A  Android+AAIdrive → BCL/Etch/SAS → RHMI H23 → Spotify UI
Pfad B  iPhone+BT        → ???          → Spotify UI (BMW-dokumentiert iDrive6)
```

Pfad B kann iAP2/MFi (`deca-fade`), AVRCP(+Browsing), BCL/SPP, oder Mix sein.
`f20_sim` antwortet nur SPP/`0x1101` ch6 — **kein** iAP2-Stub. Erste Frage: was öffnet das iPhone?

## Capture

| Artifact | Path |
|----------|------|
| btmon HCI | `btmon/csr_hci3.btsnoop` |
| HU jsonl | `/tmp/bcl_dummy/hu_iphone.jsonl` (symlink/copy here after) |
| snapshots | `snapshots/` (SDP, device props, MediaPlayer) |

## Operator A/B (während Session)

1. Spotify starten → UI-Fakten (Icon/Browse/Cover/NP/Transport)
2. Spotify force-quit (BT connected lassen) → Menü weg / cached / tot?
3. Apple Music / andere Media-App → gleiches Menü oder nur AVRCP-NP?
4. Optional: AAIdrive-OnePlus später gleicher Track (Vergleich, nicht matchen)

## Klassifikation (nach Capture)

- [ ] ACL + A2DP SEP/codec
- [ ] AVRCP CT/TG + Track/Player + Browsing?
- [ ] SDP: `0x1101` SPP / `deca-fade` iAP2 / andere
- [ ] RFCOMM open channels + BCL magic `12345678`?
- [ ] SAS/APP_AUTH / RHMI / AM in jsonl?
- [ ] UI identity vs B3 Handle-23 (Operator, nicht Wire-match)

## Repo anchors (pre-capture)

- AAIdrive path: `GESAMTSTAND_F20_AAIDRIVE_SPOTIFY_20261122.md`, Handle-23 correlation
- F20 SDP: ch5 `deca-fade` = Apple iAP2/MFi, **not** BCL; ch6–10 = SPP (`MASSNAHMEN_BCL_A6.md`)
- `BCL_BT.md` marked iPhone iAP2 historically „out of scope“ / „not usable for a relay“ — **re-open for classification**, not for B3 yet
- AVRCP HU browsing=`true`, Cover Art=`false` (`DEEP_FORENSIC_ETCH_SAS_20261116.md`)
- No prior iPhone↔CSR wire corpus in this repo — this capture is the first Path-B dataset

## Lab gap (honest)

Real F20 advertises **iAP2 (`deca-fade`)** + SPP. This lab answers **only SPP ch6** (`f20_sim`).  
If Path B is iAP2-only, we still learn that from SDP/RFCOMM attempts in btmon; we will **not** get a full native Spotify UI on `f20_sim`. That is still a successful classification.

## Postmortem (same evening) — wrong pair target

iPhone paired to **BT-Analyzer-PhoneUSB** (`hci0` / `F4:62`), not BMW `7B:0A`.  
Also: `.87` advertising + CoD drift (`0x400104` PC icon on HU).  

**Standard restored:** `.131`=BMW HU, `.87`=Phone, USB **off**, pair-agent ohne USB.  
Write-up: `docs/analysis/LAB_STANDARD_TOPOLOGY_20261122.md`  
Dual-ESP proof: ACL+RFCOMM ch6 `.87`↔`.131` OK.
