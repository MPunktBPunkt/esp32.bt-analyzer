# BT15 — RF / Air investigation (deferred)

```yaml
status: deferred
layer: L0
relation_to_bt_analyzer: out_of_scope_sibling
```

## Why deferred

`esp32.bt-analyzer` is an **HCI / VHCI (L1)** instrument. Promoting HCI MEASURED to RF/Air FACT is **REJECTED**.

Air capture needs different hardware (e.g. nRF sniffer), different claim language, and a **separate** project/repo so epistemics stay clean.

## When to open

- Explicit stakeholder need for L0 evidence
- Named RF instrument + method sheet in technology-audit
- Cross-link only: HCI sessions may *correlate* with Air, never substitute

## Non-goals here

- Channel hopping sniffer firmware on ESP32-S3 analyzer nodes
- Relabeling BTAC/PCAPNG HCI as “Bluetooth sniffer”

## Pointer

technology-audit: `projects/esp32-bt-analyzer/FOLLOW-ON-IDEAS.md` · Capture family `bt-sniffing-capture-refs`.
