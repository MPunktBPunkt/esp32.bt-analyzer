# Lab ↔ iDriveSim Umschalten (.108)

**datum:** 2026-11-19  
**anlass:** OnePlus → `.131` / `7B:0A` schien tot; AAIdrive grün nach Korrektur.  
**Cursor-Rule:** `.cursor/rules/lab-bt-host-gotchas.mdc` (alwaysApply)

## First 60s (nicht ESP zuerst)

```bash
# orphan pin loops (Alias BMW auf Phone!)
fuser -v /tmp/bcl_dummy/alias_pin_persist.log \
         /tmp/bcl_dummy/cod_pin_home.log \
         /tmp/bcl_dummy/phone87_hold.log 2>&1
# ggf. fuser -k … dann Alias prüfen (≥10s stabil):
busctl get-property org.bluez /org/bluez/hci1 org.bluez.Adapter1 Alias Powered
busctl get-property org.bluez /org/bluez/hci2 org.bluez.Adapter1 Alias Powered
# idrivesim vs lab ch6?
systemctl is-active idrivesim-rfcomm-bridge.service
pgrep -af 'idrivesim|bcl_dummy_hu_agent' | head
```

## Ressourcen-Konflikt iDriveSim ↔ Lab (Lösung)

**Eine** Seite besitzt RFCOMM **ch6** und die BMW-Pair-Agent-Drop-Ins — nie parallel.

| | iDriveSim | bt-analyzer Lab |
|---|-----------|-----------------|
| ch6 | `idrivesim-rfcomm-bridge.service` | `bcl_dummy_hu_agent … f20_sim` |
| Drop-Ins | `idrivesim-hu.conf` / `idrivesim-csr.conf` aktiv | nach `bt-pair-agent.service.d.off/` |
| Fail-Symptom | — | `failed to register accept channel 6` |

**Lab freischalten:** `systemctl stop idrivesim-rfcomm-bridge` + `pkill -f /opt/idrivesim/` + `idrivesim-*.conf` → `.d.off/` + `daemon-reload`.  
**Zurück:** HU-Agent stoppen, Drop-Ins zurück, beide Units restart.  
Details: Abschnitte „Schnell: → bt-analyzer Lab“ / „→ iDriveSim“ unten.

## Ursache (heute)

Nicht „ESP kaputt“, sondern **falsche/konkurrierende Host-Rolle auf `.108`**:

1. **HU-Adapter `.131` (`C8:C9:A3:CB:7B:0A`, `hci2`) war `Powered: no` / `DOWN`.**  
   ESP-HCI-Agent + `hci_tcp_bridge` liefen, BlueZ hatte den Virtual-Controller aber soft-off.
2. **`idrivesim-rfcomm-bridge` hielt RFCOMM ch6** (Service auf Adapter **`.87`**), dadurch  
   `bcl_dummy_hu_agent … f20_sim` → `failed to register accept channel 6`.
3. **Pair-Agent-Drop-Ins drehten die Identitäten um** (letzte `ExecStart=` gewinnt):
   - `idrivesim-hu.conf` → BMW auf **`.87`**, `.131` = Phone
   - `idrivesim-csr.conf` → zweites BMW auf **CSR USB**
   - Lab braucht: BMW nur auf **`.131`**, Rest Phone/Lab
4. **Sichtbare Symptome am Phone:** mehrere „BMW 38304“, Connect auf falschen Adapter (z. B. CSR),  
   Meldung „wird verwendet“, AAIdrive nicht grün bis ACL+SPP auf `7B:0A`.

## Rollenkarte

| Adapter | BD | bt-analyzer Lab (Phone→HU) | iDriveSim (Stand 2026-11-19) |
|---------|----|----------------------------|------------------------------|
| ESP `.131` | `C8:C9:A3:CB:7B:0A` | **HU / BMW 38304** | oft Phone (siehe drop-in) |
| ESP `.87` | `C8:C9:A3:CB:37:96` | Phone / aus | **HU** für `idrivesim-rfcomm-bridge` |
| USB | `C0:B8:83:34:F4:62` | Phone / aus | Phone |
| CSR USB | `00:1A:7D:DA:71:02` | aus / nicht BMW | optional 2. BMW (vermeiden bei Phone-Test) |

Phone (OnePlus): `AC:C0:48:5E:CB:20`.

## Drop-Ins auf `.108`

Pfad: `/etc/systemd/system/bt-pair-agent.service.d/`

| Datei | Für |
|-------|-----|
| `bmw-alias.conf` | Lab: `.131`=BMW, `.87`=Phone |
| `cod-pin.conf` | CoD pin (`hci2`/`hci3`) — bricht Unit, wenn Adapter DOWN |
| `idrivesim-hu.conf` / `idrivesim-csr.conf` | iDriveSim-Rollen (bei Lab nach `…/bt-pair-agent.service.d.off/` schieben) |

## Schnell: → bt-analyzer Lab (Phone → `.131` / f20_sim)

```bash
ssh root@192.168.178.108
systemctl stop idrivesim-rfcomm-bridge.service
pkill -f /opt/idrivesim/ || true
pkill -f bcl_dummy_hu_agent.py || true
pkill -f a2dp_bcl_watch.py || true

# idrivesim-Drop-Ins weg, Lab-Alias behalten
mkdir -p /etc/systemd/system/bt-pair-agent.service.d.off
mv /etc/systemd/system/bt-pair-agent.service.d/idrivesim-*.conf \
   /etc/systemd/system/bt-pair-agent.service.d.off/ 2>/dev/null || true
systemctl daemon-reload

# nur HU powered + BMW
busctl set-property org.bluez /org/bluez/hci0 org.bluez.Adapter1 Powered b false
busctl set-property org.bluez /org/bluez/hci1 org.bluez.Adapter1 Powered b false
busctl set-property org.bluez /org/bluez/hci3 org.bluez.Adapter1 Powered b false
busctl set-property org.bluez /org/bluez/hci1 org.bluez.Adapter1 Alias s "BT-Analyzer-Phone"
busctl set-property org.bluez /org/bluez/hci3 org.bluez.Adapter1 Alias s "Lab-CSR-USB"
hciconfig hci2 up
busctl set-property org.bluez /org/bluez/hci2 org.bluez.Adapter1 Powered b true
busctl set-property org.bluez /org/bluez/hci2 org.bluez.Adapter1 Alias s "BMW 38304"
busctl set-property org.bluez /org/bluez/hci2 org.bluez.Adapter1 Discoverable b true
busctl set-property org.bluez /org/bluez/hci2 org.bluez.Adapter1 Pairable b true
hciconfig hci2 name "BMW 38304" class 0x340408 piscan

# pair agent (ohne cod-pin-Fail auf down-hci3: manuell oder Unit fixen)
systemctl stop bt-pair-agent.service
python3 /opt/bt-analyzer/bt_pair_agent.py \
  --adapter='C8:C9:A3:CB:7B:0A=car_audio:BMW 38304' \
  --adapter='C8:C9:A3:CB:37:96=phone:BT-Analyzer-Phone' \
  --adapter='C0:B8:83:34:F4:62=phone:BT-Analyzer-Phone' \
  --adapter='00:1A:7D:DA:71:02=phone:Lab-CSR-USB' &
```

Vom Repo-Host: `./tools/lab_home_session_prep.sh`  
Phone: **BMW 38304** / `7B:0A` → A2DP → MyBMW+AAIdrive neu → grün erwarten.

**Verify:** `hci2` UP, Alias BMW, Discoverable; `hu_ready=registered`; idrivesim inactive; kein zweites BMW powered.

## Schnell: → iDriveSim

```bash
ssh root@192.168.178.108
pkill -f bcl_dummy_hu_agent.py || true
pkill -f '/opt/bt-analyzer/bt_pair_agent.py' || true

mv /etc/systemd/system/bt-pair-agent.service.d.off/idrivesim-*.conf \
   /etc/systemd/system/bt-pair-agent.service.d/ 2>/dev/null || true
systemctl daemon-reload
systemctl restart bt-pair-agent.service   # ggf. cod-pin nur auf powered hci
systemctl restart idrivesim-rfcomm-bridge.service
# Bridge-Adapter laut Unit: derzeit .87 — HU-Power/Alias daran ausrichten
```

## Fallstricke

- `hci_tcp_bridge … --local-name BMW 38304` ≠ BlueZ `Powered` — immer `bluetoothctl`/`busctl` prüfen.
- Nur **ein** powered Adapter mit Alias **BMW 38304**.
- ch6: entweder idrivesim **oder** `bcl_dummy_hu_agent`, nie parallel.
- `cod-pin.conf` `hciconfig hci3 class …` failt hard, wenn `hci3` DOWN → Unit bleibt „activating/failed“.

## Evidence 2026-11-19

Nach Umschaltung: OnePlus `AC:C0:48:5E:CB:20` ↔ `7B:0A`, AAIdrive grün;  
`/tmp/bcl_dummy/hu_home.jsonl` Session `LAB_HOME_20261119T0627Z` (SAS/RHMI/CDS, kein vorzeitiges `rfcomm_closed`).

## Field am Auto (später 2026-11-19) — Lab-Fehler

**Symptom:** F20 `D4:36:39:CF:E1:B5` page’t `.87` / BT-Analyzer-Phone → ACL `Connected` ~1–2 s → sofort wieder weg (mehrfach).

**Lab-Ursachen (nicht „ESP tot“):**

1. **Smoking gun:** seit **2026-11-17 19:30** orphan `python3 -` (PID damals 74990), Log  
   `/tmp/bcl_dummy/alias_pin_persist.log` — forciert dauernd Alias **`BMW 38304` auf hci1 (Phone)**.  
   Nach Kill bleibt Alias `BT-Analyzer-Phone` stabil.
2. Zusätzliche Prep-Loops: `cod_pin_home` / `phone87_hold` / `hciconfig class 0x340408` auf Phone.
3. **Stale `hci_tcp_bridge`** nach ESP-Reboot → Connect-Flaps `hci1 removed` / `Errno 6`.
4. WiFi am neuen Platz ~−80…−84; vor Connect `wifi_ps=none` (`POST /api/hci/wifi_ps` Form `mode=none`).

**Cleanup vor dem nächsten Auto-Versuch:**

```bash
fuser -k /tmp/bcl_dummy/alias_pin_persist.log \
         /tmp/bcl_dummy/cod_pin_home.log \
         /tmp/bcl_dummy/cod_pin_home_fast.log \
         /tmp/bcl_dummy/phone87_hold.log
pkill -f 'cod_pin|phone87_hold|alias_pin_persist|hciconfig hci[0-9] class' || true
# bridges neu, NACHDEM ESPs ready
pkill -f hci_tcp_bridge.py; sleep 1
python3 /tmp/hci_tcp_bridge.py 192.168.178.87 --port 9754 --local-name 'BT-Analyzer-Phone' &
python3 /tmp/hci_tcp_bridge.py 192.168.178.131 --port 9754 --local-name 'BMW 38304' &
busctl set-property org.bluez /org/bluez/hci1 org.bluez.Adapter1 Alias s 'BT-Analyzer-Phone'
# verify: Alias bleibt Phone ≥10s
```

Host-Notiz: `/tmp/bcl_dummy/LAB_FAULT_20261119_FIELD.md`