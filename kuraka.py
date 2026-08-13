#!/usr/bin/env python3
"""kuraka.py — cross-platform Kuraka CLI (macOS / Linux / Windows).

Python mirror of the bash `kuraka` dispatcher, for environments without bash
(Windows/PowerShell). Both CLIs invoke the same underlying Python scripts, so the
behaviour matches. Resolve the vault from $KURAKA_VAULT or this file's own dir.

  kuraka mount [dir]                       mount/update Kuraka into dir (Claude Code)
  kuraka mount --target codex|cursor|antigravity [dir]
  kuraka init  [dir]                       one-shot install (inspect+config+skeleton+mount+register)
  kuraka update                            update the framework in the project above CWD
  kuraka backup  [dir]                     snapshot this project's Kuraka state to the central store
  kuraka restore [dir]                     restore this project's Kuraka history from the store
  kuraka inspect [dir]                     detect the stack
  kuraka discover [...]                    find mounted projects + reconcile the registry
  kuraka dashboard [dir]                   aggregated telemetry dashboard
  kuraka validate [dir]                    validate mounted frontmatter
  kuraka doctor                            check the setup (vault, python, git, RTK)
  kuraka help                              this help
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

# Emit UTF-8 regardless of the console code page (Windows cp1252/cp850 would
# otherwise crash with UnicodeEncodeError on our emoji output).
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError, OSError):
        pass

VAULT = Path(os.environ.get("KURAKA_VAULT", "") or Path(__file__).resolve().parent).expanduser().resolve()
TARGETS = ("codex", "cursor", "antigravity")


def err(m: str) -> None:
    print(m, file=sys.stderr)


def py(script: str, *args: str) -> int:
    path = VAULT / script
    if not path.exists():
        err(f"❌ script no encontrado: {path}")
        return 1
    env = dict(os.environ, KURAKA_VAULT=str(VAULT), PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, str(path), *args], env=env).returncode


def find_project_root(start: Path | None = None) -> Path | None:
    d = (start or Path.cwd()).resolve()
    while True:
        if (d / ".claude").is_dir():
            return d
        if d.parent == d:
            return None
        d = d.parent


def usage() -> None:
    print(__doc__.strip())


def cmd_mount(args: list[str]) -> int:
    tgt = "claude"
    tgt_set = False
    dir_arg = None
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--target":
            tgt = args[i + 1] if i + 1 < len(args) else ""
            tgt_set = True
            i += 2
        elif a.startswith("--target="):
            tgt = a.split("=", 1)[1]
            tgt_set = True
            i += 1
        else:
            dir_arg = a
            i += 1
    target = Path(dir_arg or os.getcwd()).expanduser().resolve()
    if target == VAULT:
        err("❌ no se monta Kuraka dentro del propio vault. Corré 'kuraka mount' desde tu solución.")
        return 1

    if sys.stdin.isatty() and not tgt_set:
        print("🎯 ¿A qué entorno de IA querés montar Kuraka?")
        print("   (todos reciben agentes + comandos «/»; Claude usa subagentes nativos,")
        print("    los demás adoptan roles vía AGENTS.md)")
        print("   1) Claude Code (default)   2) Codex   3) Cursor   4) Antigravity")
        try:
            e = input("   > ").strip()
        except EOFError:
            e = ""
        tgt = {"2": "codex", "3": "cursor", "4": "antigravity"}.get(e, "claude")
        print("")

    if tgt in ("claude", "antigravity", "codex", "cursor"):
        return py("kuraka-mount.py", str(target), "--target", tgt)
    err(f"❌ target desconocido: {tgt}  (claude | codex | cursor | antigravity)")
    return 1


def cmd_doctor() -> int:
    print("🩺 kuraka doctor")
    print(f"   vault:        {VAULT}")
    print(f"   KURAKA_VAULT: {os.environ.get('KURAKA_VAULT', '(no seteado — usando dir del script)')}")
    print(f"   python:       {sys.executable} ({sys.version.split()[0]})")
    print(f"   git:          {'✓ ' + (shutil.which('git') or '') if shutil.which('git') else 'NO (instalalo)'}")
    if shutil.which("rtk"):
        try:
            v = subprocess.run(["rtk", "--version"], capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.strip()
        except OSError:
            v = ""
        print(f"   rtk:          {v or 'instalado'} ✓")
    else:
        print("   rtk:          no instalado — ver RECOMMENDED-COMPONENTS.md")
    return 0


def cmd_validate(args: list[str]) -> int:
    target = args[0] if args else os.getcwd()
    vpy = VAULT / "kuraka-validate.py"
    if vpy.exists():
        return py("kuraka-validate.py", target)
    sh = VAULT / "validate-kuraka.sh"
    if os.name != "nt" and sh.exists() and shutil.which("bash"):
        return subprocess.run(["bash", str(sh), target]).returncode
    err("❌ validate no disponible en este entorno (falta kuraka-validate.py o bash).")
    return 1


def main(argv: list[str]) -> int:
    if not VAULT.is_dir():
        err(f"❌ vault no encontrado: {VAULT}")
        err('   set KURAKA_VAULT="C:\\ruta\\a\\kuraka"  (o reinstalá con install.ps1)')
        return 1

    sub = argv[0] if argv else "help"
    rest = argv[1:]

    if sub == "mount":
        return cmd_mount(rest)
    if sub == "init":
        return py("kuraka-init.py", *(rest or [os.getcwd()]))
    if sub == "update":
        root = find_project_root()
        if not root:
            err(f"❌ no hay proyecto con .claude/ desde {os.getcwd()}")
            return 1
        return py("kuraka-mount.py", str(root))
    if sub == "backup":
        root = find_project_root(Path(rest[0])) if rest else find_project_root()
        return py("kuraka-backup.py", str(root or (rest[0] if rest else os.getcwd())))
    if sub == "restore":
        root = find_project_root(Path(rest[0])) if rest else find_project_root()
        return py("kuraka-restore.py", str(root or (rest[0] if rest else os.getcwd())))
    if sub == "inspect":
        return py("kuraka-inspect.py", *(rest or [os.getcwd()]))
    if sub == "discover":
        return py("kuraka-discover.py", *rest)
    if sub == "dashboard":
        return py("aggregate-telemetry.py", *(rest or [os.getcwd()]))
    if sub == "validate":
        return cmd_validate(rest)
    if sub == "doctor":
        return cmd_doctor()
    if sub in ("help", "-h", "--help"):
        usage()
        return 0
    err(f"❌ subcomando desconocido: {sub}\n")
    usage()
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
