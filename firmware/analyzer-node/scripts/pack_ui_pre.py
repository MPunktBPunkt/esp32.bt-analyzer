Import("env")
from pathlib import Path

root = Path(env["PROJECT_DIR"])
pack = root / "tools" / "pack_ui.py"
if pack.is_file():
    env.Execute(f"$PYTHONEXE {pack}")
else:
    print(f"pack_ui_pre: missing {pack}")
