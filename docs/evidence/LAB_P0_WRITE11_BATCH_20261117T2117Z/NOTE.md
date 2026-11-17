# Note on batch runs 1–2

Runs 1–2 failed Just-Works bond (`Page Timeout` / HU not found) and — due to an earlier hold-script fallback — executed **raw RFCOMM** instead of BCL. Those rows are **not** WATCHDOG/write11 evidence.

Runs **3–5** are valid BCL-only sessions: all aborted with `WATCHDOG_MISS_NO_ETCH_REPLY` + HU `write_error:11`, **bootGen stable** (25/3).

Hold script now fails closed when BCL is requested but bond is missing (no silent raw fallback).
