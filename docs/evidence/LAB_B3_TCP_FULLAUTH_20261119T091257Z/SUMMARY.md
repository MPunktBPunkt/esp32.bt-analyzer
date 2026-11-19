# B3 tcp-lab logged test

- **ok:** True
- claim: **LAB**
- mode: `full_auth_freeze`
- auth_state: `AUTHENTICATED`
- freeze_event: `AUTHENTICATED`
- bootstrap_state: `HANDLES_CREATING`
- handshake: 1
- bcl_frames: 15
- etch events: 4
- etch methods: `{'sas_certificate': 1, '_result_sas_certificate': 1, 'sas_login': 1, '_result_sas_login': 1}`
- raw: ['phone_to_hu.bin', 'hu_to_phone.bin']

Sequence target: INIT → HS → SELECTPROTO/KNOCK → OPEN → sas_certificate → challenge → sas_login → positive login → AUTHENTICATED freeze.
