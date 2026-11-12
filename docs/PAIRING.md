# Pairing on the BlueZ host

```yaml
status: implemented_not_run      # .108 not reachable from the desk instance
host: .108 bluetoothd (owns pairing + link keys); ESPs forward HCI only
agent: tools/bt_pair_agent.py · unit tools/bt-pair-agent.service · /opt/bt-analyzer
origin: PiDrive bt_agent_dbus.py (BMW field test 2026-09-16, passkey dialog confirmed in iDrive)
```

## Who decides what

| Part | Role in pairing |
|------|-----------------|
| ESP D1 (.131, .87) | controller only; SSP runs in the controller, decisions come from the host via HCI |
| bluetoothd on .108 | host stack; stores link keys per controller BD under `/var/lib/bluetooth/<ESP-BD>/` |
| default agent | answers `RequestConfirmation` etc. when the **remote** side starts pairing |
| Cursor / lab scripts | SSH to .108 only; deploy, query, open a window — never in the pairing path |
| phone / iDrive | shows the same six-digit number; a person must confirm there |

Link keys are stored by controller BD, not `hciN`: a bridge reconnect (new index)
keeps the bond. A different ESP (new BD) is a new device for the HU and the phone.

## Why the agent is a service

BlueZ asks the default agent. Without one, remote-initiated pairing (HU or phone
starts) is cancelled. PiDrive learned this the hard way: its `bluetoothctl` agent
only answered pairings the Pi started itself. In this repo `ensure_agent()` ran
`bluetoothctl agent NoInputNoOutput` as a one-shot — the agent ended with the
process, so nothing answered.

| bluetoothctl use | own agent? | who answers |
|------------------|------------|-------------|
| one-shot `bluetoothctl pair X` | no | default agent (service) |
| piped / interactive session | yes (until quit) | that session for its own `pair`; default agent for the other side |
| session with `default-agent` | takes the default role until it exits | — avoid while the service runs |
| `busctl call … Device1 Pair` | no | default agent for both sides |

`DisplayYesNo` matters: with `NoInputNoOutput` on our side SSP falls back to Just
Works (no MITM protection). The BMW uses Numeric Comparison with PiDrive's
DisplayYesNo agent (FACT, PiDrive field test); whether it accepts Just Works is
UNKNOWN.

## Agent behaviour

- Rule `always | window | never` (`BT_PAIR_CONFIRM`, default `always`) for
  configured adapters; unconfigured adapters (host's own hci0) only inside a window.
- Trust after `RequestConfirmation` and on `Paired=true`.
- Audio UUIDs (A2DP, AVRCP, AVDTP, AVCTP) authorized without asking.
- Per configured adapter (matched by BD, re-applied when the bridge brings it back):
  Alias, Discoverable/Pairable without timeout, Class of Device via `hciconfig`.

| Adapter | Faces | Plays | Alias | Class |
|---------|-------|-------|-------|-------|
| .131 `C8:C9:A3:CB:7B:0A` | phone | car audio | BT-Analyzer-Car | `0x200420` |
| .87 `C8:C9:A3:CB:37:96` | HU | smartphone | BT-Analyzer-Phone | `0x5A020C` |

Class is best effort: bluetoothd ORs in service bits of registered profiles and
may rewrite it on power-on. The state shows actual vs wanted (`cls_ok`); extra
service bits count as OK. Whether iDrive filters on Class is UNKNOWN. B0.7 still
sets its own alias (`BCL-HU-Dummy`) per run.

Files on .108: state `/run/bt-analyzer/pair_agent.json`, events
`/var/log/bt-analyzer/pair_events.jsonl`, window `/run/bt-analyzer/pair_window`.

## Use

```bash
python3 tools/lab_pair_agent.py deploy          # copy, install unit, enable, show journal
python3 tools/lab_pair_agent.py status          # adapters, bonded devices, last events
python3 tools/lab_pair_agent.py window 300      # rule window: accept for 5 min
python3 tools/lab_pair_agent.py remove <adapter-BD> <device-BD>
```

Lab UI `:8081`, card **Pairing**: service state, rule, window, the latest passkey
(two minutes) with adapter and peer, adapters with bonded devices, event list.
Button opens a five-minute window.

## Open

| Item | Status |
|------|--------|
| deploy + first run on .108 | OPEN (host unreachable from desk) |
| phone → .131 pairing via agent | OPEN (expect `RequestConfirmation`, number on phone) |
| HU → .87 pairing via agent (A6) | OPEN (expect Numeric Comparison like PiDrive) |
| Class of Device survives power-on | OPEN (check `cls_ok` after bridge reconnect) |
