# Field vs Lab — insights 2026-11-15 (HU session end)

```yaml
field_legs: ".87/hci1 ↔ F20 D4:36:39:CF:E1:B5"
lab_legs: "OnePlus ↔ .131 Dummy-HU (parallel)"
artifacts:
  - FIELD_B2A_TX_20261115T131825Z
  - FIELD_P0_HOLD_20261115T132501Z / T132919Z
  - FIELD_BURST_20261115 (SP2/SP4/ETCH10)
  - LAB_PAR_131_* / prior LAB_SAS_* / LAB_WD_MAX3_*
hu_end: page-timeout / Host is down during SP3/Desk retries
```

## Burst matrix (this session)

| Pattern | RFCOMM | HS v5 | WD echo | OPEN 4004 TX | HU Etch/SAS RX | Note |
|---------|--------|-------|---------|--------------|----------------|------|
| SP4 + wire_v5 + OPEN5001 | ok | ok | ok ~150–300 ms | no | — | control |
| SP4 + wire_v5 + OPEN 4004 src10 | ok | ok | ok | **yes** (`0001000a0fa4`) | **none** | HU DATAACK **8** extra (= ACK empty OPEN) |
| SP2 + wire_v5 + OPEN5001 | ok | ok | ok | no | — | **SP2 tolerated** after HS v5 |
| SP4 + OPEN4004 src12 | busy | — | — | — | — | inconclusive |
| SP3 / Desk knock | busy / reset then **page-timeout** | — | — | — | — | HU powering down |

## New FIELD facts (vs prior Lab)

1. **F20 speaks BCL on SCN 6 as server** when `.87` is phone-client: INIT→HS **v5/iid14/0x4000**→SP→KNOCK→OPEN5001→WD — confirmed live (not Dummy).
2. **WD echo RTT** first real curve: Hold2 p50 **~159 ms**, p95 **~308 ms** (WiFi/HCI path); misses happen (abort after 3) — RF/range sensitive (`.87` RSSI ~−80).
3. **HU DATAACK = `8+len` on WD**: dominant **12** (=8+4). Also **10** (SP u16) and **8** (empty OPEN / 0-payload). Formula holds; **8** is real on wire, not only 10/44/4008.
4. **SP2 after HS v5 still yields stable WD** (n=1). SP4 not uniquely required for keepalive — tolerance **FIELD**, not yet n≥2.
5. **Phone OPEN 4004 alone does not elicit SAS/Etch from F20** (18 s window, src10). HU ACKs the OPEN (`ack_n=8`) then silence on 4004 → **Modell A (auto HU→4004) not observed** without app/UI; **SAS challenge ≠ automatic on our OPEN**.
6. **Hold ~2–3 min without iDrive: 0× `hu_unsolicited` 4004** — OPEN4004 not idle-automatic in this window.
7. **No BCL relay yet**: parallel topology (Phone↔Dummy + `.87`↔F20) ≠ proxy; B3 still missing.

## Lab facts that still stand (not replaced)

| Lab | Still valid? |
|-----|----------------|
| AAIdrive green on Dummy with WD-only / challenge stubs | yes — green ≠ proof of real SAS to F20 |
| Dummy `deadbeef`/PKCS7 Etch path | lab-only; **not** seen from F20 in this field burst |
| WD-max3 Dummy keeps UI green | lab UX; F20 miss-limit aborts analyzer hold |
| CoD `0x340408` + alias gate for phone→Dummy | unchanged |
| SCN 6 first `0x1101`, failover 10 | SDP reconfirmed today (ch 6–10 SPP; ch5 iAP2) |

## Architecture implications

- **Relay vs Emulator:** Field shows F20 will do BCL transport + WD with a thin analyzer client, but **Etch/SAS content did not appear** from OPEN4004 alone. Emulating Dummy Etch is **not** how F20 answered us. Next high-value: MyBMW-owned session btsnoop, or UI-triggered hold (Modell D) while analyzer is passive mid-session — not more OPEN4004 spam.
- **Proxy B3:** Still blocked on “classified phone↔HU Etch,” not on ACL/RFCOMM — transport P0 is green; content P0 is not.
- **Frozen phone bootstrap** (`FIELD_P0_HOLD_FREEZE_20261115`) remains the default for future factor runs when HU is back.

## Open (explicitly unsolved today)

- SP3 / Desk-KNOCK / Etch src12/18 — **no clean trial** (RFCOMM busy → HU off)
- WD-Pong ≠ `13371337`, DATAACK omit, WD timeout ladder — not run
- Whether F20 ever HU-initiates 4004 (Modell A) under real MyBMW UI
