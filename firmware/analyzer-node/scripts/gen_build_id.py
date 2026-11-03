Import("env")
from pathlib import Path
import subprocess

root = Path(env["PROJECT_DIR"])
out = root / "include" / "build_id.h"
out.parent.mkdir(parents=True, exist_ok=True)

sha = "unknown"
try:
    sha = subprocess.check_output(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=root.parents[1],
        stderr=subprocess.DEVNULL,
        text=True,
    ).strip()
except Exception:
    pass

out.write_text(
    "#pragma once\n"
    f'#ifndef GIT_SHA\n#define GIT_SHA "{sha}"\n#endif\n',
    encoding="utf-8",
)
print(f"gen_build_id: GIT_SHA={sha}")
