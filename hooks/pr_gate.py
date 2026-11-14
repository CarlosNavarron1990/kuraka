#!/usr/bin/env python3
"""Kuraka hook — validar-pr gate (PreToolUse, matcher: Bash). Claude-only.

Enforces the `validar-pr` skill deterministically (semantics of the team hook
`hook-claude.py` it was adopted from, guai-agents-platform-azure 2026-11):
- `gh pr create|new|ready` passes only when `.git/validar-pr/<HEAD>.md` exists
  and its FIRST line is the exact APROBABLE marker for HEAD
  (`<!-- validar-pr sha=<HEAD> base=<40hex> veredicto=APROBABLE -->`). Only the
  first line counts: the reviewer's text below could quote the marker.
- `git push` to a protected branch (named, or implicit via the current branch /
  its upstream) is blocked, and a push may not skip the pre-push hook
  (`--no-verify`, `HUSKY=0`, `-c core.hooksPath`). Commits are never checked.

The command is split into segments (`&&` `||` `;` `|` parens newlines) with
shlex, so quoted text (a commit message) is never read as an option; wrappers
(env/command/sudo/nohup/time/exec) are unwrapped and `bash|sh|zsh -c "…"` /
`eval "…"` are analysed recursively.

WHEN IT ACTS — only when the project adopted the VAULT validar-pr:
- adopted = `.claude/project/validar-pr/config.sh` (the layer), or the legacy
  `.claude/skills/validar-pr/config.sh` when that skill dir is NOT tracked by
  the project's git;
- inert when the project OWNS its own validar-pr (the skill dir is tracked in
  its git, or its settings already wire `validar-pr/scripts/hook-claude`): the
  team's hook gates, Kuraka must not double-gate;
- `workflow.validar_pr.enforce_hook: false` in kuraka.config.yaml turns it off;
- `VALIDAR_PR_DENTRO` (the blind reviewer itself) → inert.
Protected branches: `VP_RAMAS_PROTEGIDAS="…"` in that config.sh, else main
master develop dev release.

FAILURE POLICY (deliberate exception to the Kuraka fail-open convention, as in
the team hook): on an adopted project, anything that prevents checking — an
unreadable payload, no git to read HEAD, an internal error — BLOCKS only when
the command touches what the gate guards (`gh … pr …` or `push`); every other
command passes. Exit 2 = block (reason on stderr, Claude reads it).
"""
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

DEFAULT_PROTECTED = {"main", "master", "develop", "dev", "release"}
PUSH_OPTS_WITH_VALUE = {"-o", "--push-option", "--repo", "--receive-pack", "--exec"}
WRAPPERS = {"env", "command", "sudo", "nohup", "time", "exec", "builtin"}
SHELLS = {"bash", "sh", "zsh", "dash", "ksh"}
VALIDATE_CMD = "bash .claude/skills/validar-pr/scripts/validar-pr.sh --crear-pr"


class Block(Exception):
    pass


def _segments(cmd: str):
    try:
        lex = shlex.shlex(cmd.replace("\n", " ; "), posix=True, punctuation_chars="();&|")
        lex.whitespace_split = True
        toks = list(lex)
    except ValueError:
        for part in re.split(r"&&|\|\||;|\||\n|\(|\)", cmd):
            if part.strip():
                yield part.split()
        return
    cur: list[str] = []
    for tok in toks:
        if tok and set(tok) <= set("();&|"):
            if cur:
                yield cur
            cur = []
        else:
            cur.append(tok)
    if cur:
        yield cur


def _strip_prefixes(toks):
    while toks:
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", toks[0]):
            toks = toks[1:]
        elif toks[0] in WRAPPERS:
            toks = toks[1:]
            while toks and toks[0].startswith("-"):
                toks = toks[1:]
        else:
            break
    return toks


def _git(cwd: Path, *args) -> str:
    try:
        return subprocess.check_output(["git", "-C", str(cwd), *args], text=True,
                                       stderr=subprocess.DEVNULL, timeout=10).strip()
    except Exception:
        return ""


class Gate:
    def __init__(self, proj: Path, protected: set[str]):
        self.proj = proj
        self.protected = protected
        self.wants_pr = False

    def text(self, cmd: str, depth: int = 0):
        if depth > 3:
            return
        for seg in _segments(cmd):
            self.segment(seg, depth)

    def segment(self, toks, depth):
        no_husky = any(re.fullmatch(r"HUSKY=[\"']?0[\"']?", t) for t in toks[:6])
        toks = _strip_prefixes(toks)
        if not toks:
            return
        head = os.path.basename(toks[0])
        if head in SHELLS:
            for i, a in enumerate(toks[1:], start=1):
                if re.fullmatch(r"-[a-zA-Z]*c[a-zA-Z]*", a) and i + 1 < len(toks):
                    self.text(toks[i + 1], depth + 1)
                    return
        elif head == "eval":
            self.text(" ".join(toks[1:]), depth + 1)
        elif head == "gh":
            rest, k = [], 1
            while k < len(toks):
                if toks[k] in ("-R", "--repo"):
                    k += 2
                    continue
                if not toks[k].startswith("-"):
                    rest.append(toks[k])
                k += 1
            if len(rest) >= 2 and rest[0] == "pr" and rest[1] in ("create", "new", "ready"):
                self.wants_pr = True
        elif head == "git":
            sub, args, cdir, hooks = self._git_sub(toks)
            if sub == "push":
                self.push(args, cdir, hooks or no_husky)

    @staticmethod
    def _git_sub(toks):
        j, cdir, hooks = 1, None, False
        while j < len(toks) and toks[j].startswith("-"):
            if toks[j] in ("-C", "-c") and j + 1 < len(toks):
                if toks[j] == "-C":
                    cdir = toks[j + 1]
                elif toks[j + 1].lower().startswith("core.hookspath"):
                    hooks = True
                j += 2
                continue
            if toks[j].lower().startswith("-ccore.hookspath"):
                hooks = True
            j += 1
        if j >= len(toks):
            return None, [], cdir, hooks
        return toks[j], toks[j + 1:], cdir, hooks

    def _blocked_branch(self, branch):
        raise Block(f"'{branch}' solo se alcanza por PR. Sube tu rama feature con su nombre "
                    f"(… origin <tu-rama>) y abre la PR con: {VALIDATE_CMD}")

    def push(self, args, cdir, skips_hooks):
        if skips_hooks or any(a.startswith("--no-veri") for a in args):
            raise Block("una subida no se salta el pre-push (--no-verify, HUSKY=0 o core.hooksPath).")
        where = Path(cdir) if cdir else self.proj
        positional, k = [], 0
        while k < len(args):
            if args[k] in PUSH_OPTS_WITH_VALUE:
                k += 2
                continue
            if not args[k].startswith("-"):
                positional.append(args[k])
            k += 1
        current = _git(where, "branch", "--show-current")
        upstream = _git(where, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
        upstream = upstream.split("/", 1)[-1] if upstream else ""
        if len(positional) < 2:
            for b in (current, upstream):
                if b in self.protected:
                    self._blocked_branch(b)
            return
        for ref in positional[1:]:
            dest = re.sub(r"^refs/heads/", "", ref.lstrip("+").split(":")[-1])
            if dest == "HEAD":
                dest = current
            if dest in self.protected:
                self._blocked_branch(dest)

    def report_ok(self) -> tuple[str, bool]:
        sha = _git(self.proj, "rev-parse", "HEAD")
        gd = _git(self.proj, "rev-parse", "--git-common-dir")
        if not sha or not gd:
            return sha, False  # no git -> cannot check the report -> fail CLOSED
        gdir = Path(gd) if os.path.isabs(gd) else self.proj / gd
        rep = gdir / "validar-pr" / f"{sha}.md"
        try:
            first = rep.read_text(encoding="utf-8").splitlines()[0].strip()
        except (OSError, UnicodeDecodeError, IndexError):
            return sha, False
        pat = r"<!-- validar-pr sha=%s base=[0-9a-f]{40} veredicto=APROBABLE -->" % sha
        return sha, re.fullmatch(pat, first) is not None


def _tracked(proj: Path, rel: str) -> bool:
    out = _git(proj, "ls-files", "--", rel)
    return bool(out.strip())


def _project_owns_gate(proj: Path) -> bool:
    """The project versions its OWN validar-pr (or wires its own Claude hook)."""
    if _tracked(proj, ".claude/skills/validar-pr"):
        return True
    for name in ("settings.json", "settings.local.json"):
        try:
            if "validar-pr/scripts/hook-claude" in (proj / ".claude" / name).read_text(encoding="utf-8"):
                return True
        except Exception:
            continue
    return False


def _adopted_config(proj: Path) -> Path | None:
    layer = proj / ".claude/project/validar-pr/config.sh"
    legacy = proj / ".claude/skills/validar-pr/config.sh"
    if _project_owns_gate(proj):
        return None
    if layer.is_file():
        return layer
    if legacy.is_file():
        return legacy
    return None


def _enforce_disabled(proj: Path) -> bool:
    try:
        cfg = (proj / "kuraka.config.yaml").read_text(encoding="utf-8")
    except Exception:
        return False
    m = re.search(r"validar_pr:\s*\n((?:[ \t]+.*\n?)*)", cfg)
    return bool(m and re.search(r"^\s*enforce_hook:\s*false\b", m.group(1), re.M))


def _protected(config_sh: Path) -> set[str]:
    try:
        txt = config_sh.read_text(encoding="utf-8")
    except Exception:
        return set(DEFAULT_PROTECTED)
    m = re.findall(r'^\s*(?:export\s+)?VP_RAMAS_PROTEGIDAS=["\']?([^"\'\n]*)', txt, re.M)
    return set(m[-1].split()) if m and m[-1].strip() else set(DEFAULT_PROTECTED)


TOUCHES_GATE = re.compile(
    r"(^|[^A-Za-z0-9_-])gh[^|;&]*[^A-Za-z0-9_-]pr[^A-Za-z0-9_-]|(^|[^A-Za-z0-9_-])push([^A-Za-z0-9_-]|$)")


def _project_dir(data: dict | None) -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or (data or {}).get("cwd") or os.getcwd())


def main() -> int:
    if os.environ.get("VALIDAR_PR_DENTRO"):
        return 0  # the blind reviewer itself
    raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
    try:
        data = json.loads(raw)
        cmd = (data.get("tool_input") or {}).get("command") or ""
    except Exception:
        data, cmd = None, None
    try:
        proj = _project_dir(data)
        cfg = _adopted_config(proj)
        if cfg is None or _enforce_disabled(proj):
            return 0
    except Exception:
        return 0  # cannot even tell whether the project adopted the gate
    if cmd is None:
        # Unreadable payload on an adopted project: block only what the gate guards.
        if TOUCHES_GATE.search(raw):
            print("validar-pr: no se pudo leer el comando y toca una PR o una subida: "
                  "se bloquea por precaución.", file=sys.stderr)
            return 2
        return 0
    if not cmd or not re.search(r"\bgh\b|\bpush\b", cmd):
        return 0
    try:
        gate = Gate(proj, _protected(cfg))
        gate.text(cmd)
        if gate.wants_pr:
            sha, ok = gate.report_ok()
            if not ok:
                raise Block(
                    f"no hay validación APROBABLE del commit {(sha or 'desconocido')[:8]}.\n"
                    "Ejecuta la validación completa (fusión con la base, suite, revisión y punta a punta):\n"
                    f'  {VALIDATE_CMD} --titulo "<tipo>(<ámbito>): <descripción> (PROJ-123)"\n'
                    "Si sale CAMBIOS, corrige lo que diga el informe y repite.")
    except Block as b:
        print(f"validar-pr: {b}", file=sys.stderr)
        return 2
    except Exception as e:  # internal error: fail closed on what the gate guards
        if TOUCHES_GATE.search(cmd):
            print(f"validar-pr: el hook falló ({type(e).__name__}) y no puede comprobar la PR "
                  "o la subida: se bloquea por precaución.", file=sys.stderr)
            return 2
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
