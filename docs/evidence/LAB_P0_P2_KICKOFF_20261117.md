# LAB P0–P2 Kickoff — 2026-11-17

**baseline:** `861ade0` (Deep Forensic RHMI/YouTube/Screen-Mirror + Etch Tiny-Int Fix)  
**lab online:** `.131` FW 0.3.20 · `.87` FW 0.3.19 · `.108` bridges up · `BMW 38304` on hci

## Scope

| Prio | Arbeit |
|------|--------|
| P0 | HU-Stub: `ServiceException` bei kaputtem `rhmi_setData` (ImageID→0); `checkResource` Digest-Whitelist; Resource-Persist mit SHA-256 |
| P1 | Phone-Sim: nach `checkResource=False` DESCRIPTION/`setResource`→`initialize`→`setData` (Apps/Browse) + multi-`am_registerApp` |
| P2 | Dual-ESP / lokal: Phone-Sim ↔ `f20_sim` Smoke; Evidence + Auswertung |

Quellen: `DEEP_FORENSIC_RHMI_SCREENMIRROR_20261117.md`, AAIdrive `MusicApp` / ScreenMirror Addon.

**Ergebnis:** → [`LAB_P0_P2_RESULT_20261117.md`](LAB_P0_P2_RESULT_20261117.md) (in-process PASS · dual-ESP air FAIL).
