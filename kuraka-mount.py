#!/usr/bin/env python3
"""kuraka-mount.py — mount the Kuraka vault into a consumer project.

Cross-platform (macOS / Linux / Windows) canonical implementation of the mount.
Replaces the old rsync/bash `mount-kuraka.sh` (which is now a thin wrapper around
this). No external dependencies — pure Python 3 + git. Sibling scripts are invoked
via `sys.executable` so it never assumes a `python3` on PATH (key on Windows).

What it does:
  1. banner + (TTY) interactive menu of categories / status-only + MCP detection
  2. pre-flight snapshot of local overrides, then copy the vault categories in
  3. re-apply project overrides on top, update .gitignore, register, offer restore
  4. auto-seed a migration-example layer, adoption check, command catalog + guide

Usage:  python3 kuraka-mount.py [target_dir] [--target claude|antigravity|cursor|codex]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from fnmatch import fnmatch
from pathlib import Path

# Emit UTF-8 regardless of the console code page (Windows cp1252/cp850 would
# otherwise crash with UnicodeEncodeError on our emoji/box-drawing output).
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError, OSError):
        pass

DEFAULT_VAULT = "/Users/xmn/Documents/Agentes/AgentesTrabajos/kuraka"


def _self_dir() -> Path:
    return Path(__file__).resolve().parent


VAULT = Path(os.environ.get("KURAKA_VAULT", "") or _self_dir()).expanduser().resolve()


# --------------------------------------------------------------------------- io

def _enable_windows_ansi() -> None:
    """Best-effort enable of ANSI/VT sequences on the Windows console."""
    if os.name != "nt":
        return
    try:
        import ctypes
        k = ctypes.windll.kernel32
        k.SetConsoleMode(k.GetStdHandle(-11), 7)
    except Exception:
        pass


def color_ok() -> bool:
    return sys.stdout.isatty() and not os.environ.get("NO_COLOR")


def run_py(script: str, *args: str, quiet: bool = False, check_env: bool = True):
    """Invoke a sibling vault script with the current interpreter."""
    import subprocess
    path = VAULT / script
    if not path.exists():
        return None
    env = dict(os.environ, KURAKA_VAULT=str(VAULT), PYTHONIOENCODING="utf-8") if check_env else None
    try:
        if quiet:
            r = subprocess.run([sys.executable, str(path), *args],
                               env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            r = subprocess.run([sys.executable, str(path), *args], env=env)
        return r.returncode
    except OSError:
        return None


def capture_py(script: str, *args: str) -> str:
    import subprocess
    path = VAULT / script
    if not path.exists():
        return ""
    try:
        r = subprocess.run([sys.executable, str(path), *args],
                           env=dict(os.environ, KURAKA_VAULT=str(VAULT), PYTHONIOENCODING="utf-8"),
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        return r.stdout
    except OSError:
        return ""


# ------------------------------------------------------------------------ banner

def banner() -> None:
    d = "\033[38;5;242m" if color_ok() else ""
    reset = "\033[0m" if color_ok() else ""
    ans = VAULT / "assets" / "kuraka-banner.ans"
    txt = VAULT / "assets" / "kuraka-banner.txt"
    print("")
    if color_ok() and ans.exists():
        sys.stdout.write(ans.read_text(encoding="utf-8", errors="ignore"))
    elif txt.exists():
        sys.stdout.write(d + txt.read_text(encoding="utf-8", errors="ignore") + reset)
    else:
        c = "\033[38;5;214m" if color_ok() else ""
        for line in (
            "   ██╗  ██╗██╗   ██╗██████╗  █████╗ ██╗  ██╗ █████╗ ",
            "   █████╔╝ ██║   ██║██████╔╝███████║█████╔╝ ███████║",
            "   ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝",
        ):
            print(f"{c}{line}{reset}")
    print(f"{d}        🪢  KURAKA · «el mayor» · framework multi-agente{reset}")
    print("")


# ---------------------------------------------------------------- file copying

def count_top(dstdir: Path) -> int:
    """Top-level .md/.sh files."""
    if not dstdir.is_dir():
        return 0
    return sum(1 for p in dstdir.iterdir() if p.is_file() and p.suffix in (".md", ".sh"))


def count_codex_skills(dstdir: Path) -> int:
    """Number of discoverable project-local Codex skills."""
    if not dstdir.is_dir():
        return 0
    return sum(1 for p in dstdir.iterdir() if p.is_dir() and (p / "SKILL.md").is_file())


def count_codex_agents(dstdir: Path) -> int:
    """Number of native Codex custom agent definitions."""
    if not dstdir.is_dir():
        return 0
    return sum(1 for p in dstdir.glob("*.toml") if p.is_file())


def _excluded(rel: Path, exclude: tuple[str, ...]) -> bool:
    return any(fnmatch(part, pat) for part in rel.parts for pat in exclude)


def sync_tree(src: Path, dst: Path, exclude: tuple[str, ...] = (), target_env: str = "claude") -> None:
    """Mirror src→dst with `rsync --update` semantics."""
    if not src.is_dir():
        return
    for root, _dirs, files in os.walk(src):
        for f in files:
            sp = Path(root) / f
            rel = sp.relative_to(src)
            if _excluded(rel, exclude):
                continue
            dp = dst / rel
            if dp.exists() and dp.stat().st_mtime >= sp.stat().st_mtime:
                continue
            copy_file(sp, dp, target_env=target_env)


def _expand_discipline(text: str) -> str:
    """Expand `<!-- kuraka:discipline:<name> -->` markers with the full manual
    discipline prose from <vault>/discipline/<name>.md. Claude renders keep the
    slim hook-note + marker (the harness enforces the rule there); non-Claude
    renders get the complete manual discipline back, so no platform loses the
    rule when Claude's prompts slim down."""
    import re as _re

    def _sub(m: "_re.Match[str]") -> str:
        block = VAULT / "discipline" / f"{m.group(1)}.md"
        if block.is_file():
            return block.read_text(encoding="utf-8", errors="ignore").rstrip("\n")
        return m.group(0)

    return _re.sub(r"<!-- kuraka:discipline:([A-Za-z0-9_-]+) -->", _sub, text)


def copy_file(src: Path, dst: Path, target_env: str = "claude") -> None:
    import shutil
    if not src.is_file():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    if target_env != "claude" and src.suffix == ".md":
        # Non-Claude renders SUBTRACT from the Claude-native vault superset:
        # first drop Claude-only harness frontmatter (tools/maxTurns/...),
        # re-expand the manual discipline prose the Claude hooks replace, then
        # apply the platform's path projection. The claude target below stays a
        # byte-identical copy — required by detect_overrides().
        from kuraka_common import strip_claude_frontmatter
        text = src.read_text(encoding="utf-8", errors="ignore")
        text = strip_claude_frontmatter(text)
        text = _expand_discipline(text)
        if target_env == "antigravity":
            text = text.replace(".claude/skills/", ".agents/skills/")
            text = text.replace(".claude/rules/", ".agents/rules/")
            text = text.replace(".claude/agents/", ".agents/agents/")
            text = text.replace(".claude/project/", ".agents/project/")
            text = text.replace(".claude/stack-profiles/", ".agents/stack-profiles/")
            text = text.replace(".claude/templates/", ".agents/templates/")
        elif target_env == "codex":
            text = adapt_codex_paths(text)
        dst.write_text(text, encoding="utf-8")
    else:
        shutil.copy2(src, dst)


def merge_claude_hook_settings(platform_dir: Path):
    """Merge the vault's hooks/settings-hooks.json wiring into the consumer's
    .claude/settings.json (claude target only). Non-destructive and idempotent:
    entries whose command path contains `.claude/hooks/` are kuraka-owned and
    replaced; every user-added hook entry is preserved. Returns True if the
    file changed, False if already up to date, or an error string (the mount
    never clobbers a settings.json it cannot parse)."""
    tmpl = VAULT / "hooks" / "settings-hooks.json"
    if not tmpl.is_file():
        return False
    try:
        desired = json.loads(tmpl.read_text(encoding="utf-8")).get("hooks", {})
    except Exception as e:
        return f"unreadable template: {e}"
    sfile = platform_dir / "settings.json"
    settings = {}
    if sfile.is_file():
        try:
            settings = json.loads(sfile.read_text(encoding="utf-8"))
        except Exception:
            return "existing settings.json is not valid JSON — fix it and re-mount"
    hooks = settings.setdefault("hooks", {})

    def _is_kuraka(entry: dict) -> bool:
        return any(".claude/hooks/" in h.get("command", "")
                   for h in entry.get("hooks", []) if isinstance(h, dict))

    changed = False
    for event, entries in desired.items():
        current = hooks.get(event, [])
        kept = [e for e in current if not _is_kuraka(e)]
        new = kept + entries
        if new != current:
            hooks[event] = new
            changed = True
    if changed:
        sfile.write_text(json.dumps(settings, indent=2, ensure_ascii=False) + "\n",
                         encoding="utf-8")
    return changed


def sync_claude_skills(src_skills: Path, dst_skills: Path) -> int:
    """Claude-native skills: each vault skills/<n>.md lands BOTH as the
    registered directory form .claude/skills/<n>/SKILL.md (what current Claude
    Code discovers — flat .md files in skills/ are NOT registered) and as the
    legacy flat .claude/skills/<n>.md (transition compat: agent prompts still
    Read the flat path; retire the flat copy one suite version after all
    references move). Both copies are byte-identical to the vault — required by
    the override subsystem's byte comparison (kuraka_common canonicalizes
    skills/<n>/SKILL.md to the skills/<n>.md baseline). Subdirectories are
    synced as-is.

    EXCEPTION — name collision with a slash command: a registered skill SHADOWS
    a same-named `.claude/commands/<n>.md`, so mounting `skills/kuraka/SKILL.md`
    made `/kuraka` resolve to the (non-invocable) skill instead of the command
    entrypoint. For any skill whose name matches a command, only the flat copy
    is mounted (the orchestrator and the command read it by path anyway) and any
    previously mounted directory form is removed."""
    dst_skills.mkdir(parents=True, exist_ok=True)
    command_names = {c.stem for c in (VAULT / "commands").glob("*.md")}
    count = 0
    for p in sorted(src_skills.glob("*.md")):
        skill_dir = dst_skills / p.stem
        if p.stem in command_names:
            # Never register a skill that would shadow the /<n> command.
            legacy = skill_dir / "SKILL.md"
            if legacy.is_file():
                legacy.unlink()
                if not any(skill_dir.iterdir()):
                    skill_dir.rmdir()
            copy_file(p, dst_skills / p.name, target_env="claude")
            count += 1
            continue
        skill_dir.mkdir(parents=True, exist_ok=True)
        copy_file(p, skill_dir / "SKILL.md", target_env="claude")
        copy_file(p, dst_skills / p.name, target_env="claude")
        count += 1
    for d in src_skills.iterdir():
        if d.is_dir():
            sync_tree(d, dst_skills / d.name, target_env="claude")
    return count


def ensure_claude_md_block(target: Path) -> bool:
    """Guarantee the consumer's CLAUDE.md carries the kuraka managed block
    (claude target only): a native @import of the always-on evidence rule, so
    rule 19 binds EVERY session — not only the ones entered through /kuraka.
    Idempotent; content between the markers is owned and rewritten by the
    mount, everything else in the file is untouched."""
    begin, end = "<!-- kuraka:managed:begin -->", "<!-- kuraka:managed:end -->"
    block = (
        f"{begin}\n"
        "<!-- Managed by kuraka-mount — do not edit inside the markers. -->\n"
        "@.claude/rules/19-evidence.md\n"
        f"{end}"
    )
    cm = target / "CLAUDE.md"
    if cm.is_file():
        text = cm.read_text(encoding="utf-8", errors="ignore")
        if begin in text and end in text:
            head, _, rest = text.partition(begin)
            _, _, tail = rest.partition(end)
            new = head + block + tail
        else:
            new = text.rstrip("\n") + "\n\n" + block + "\n"
    else:
        new = ("# Project instructions\n\n" + block + "\n")
    if cm.is_file() and new == cm.read_text(encoding="utf-8", errors="ignore"):
        return False
    cm.write_text(new, encoding="utf-8")
    return True


def sync_antigravity_skills(src_skills: Path, dst_skills: Path) -> int:
    """Sync vault skills to .agents/skills/ in Antigravity native skill structure:
    each skill is a directory .agents/skills/<skill_name>/SKILL.md, plus preserving
    subdirectories like evals/ and sentry-triage/."""
    dst_skills.mkdir(parents=True, exist_ok=True)
    count = 0
    for p in src_skills.glob("*.md"):
        skill_name = p.stem
        skill_dir = dst_skills / skill_name
        skill_dir.mkdir(parents=True, exist_ok=True)
        copy_file(p, skill_dir / "SKILL.md", target_env="antigravity")
        copy_file(p, dst_skills / p.name, target_env="antigravity")
        count += 1
    for d in src_skills.iterdir():
        if d.is_dir():
            sync_tree(d, dst_skills / d.name)
    return count


def _codex_skill_text(name: str, description: str, body: str, source_kind: str) -> str:
    """Render a Codex-native SKILL.md. Codex discovers project-local skills only
    from .codex/skills/<name>/SKILL.md, so vault skills and Kuraka agents are
    normalized into that shape for the Codex target."""
    description = adapt_codex_paths(description)
    body = adapt_codex_paths(body)
    platform_override = ""
    if name in {"kuraka", "kuraka-policies"}:
        platform_override = """## Codex Platform Override

This override takes precedence over Claude-specific wording below. When the
workflow says to invoke an agent, delegate to the matching native custom agent
in `.codex/agents/<name>.toml`, wait for its structured handoff, and apply the
gate before the next phase. The orchestrator never adopts a specialist role.

Codex may not expose Claude's `<usage>` block. Keep the telemetry file and
record phase, agent, attempt, timestamps, status, and produced artifacts.
Record unavailable token, tool-use, or duration values as `null` or `unknown`;
never fabricate `0`. Missing optional usage metrics do not block a gate.

"""
    return (
        "---\n"
        f"name: {name}\n"
        f'description: "{description}"\n'
        "---\n\n"
        f"> Kuraka Codex {source_kind}. Loaded from this project via `.codex/skills/{name}/SKILL.md`.\n\n"
        f"{platform_override}"
        f"{body.lstrip()}"
    )


def _frontmatter_and_body(path: Path) -> tuple[dict[str, str], str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    fm: dict[str, str] = {}
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            block = text[3:end]
            body = text[end + 4:].lstrip("\n")
            for raw in block.splitlines():
                if ":" not in raw:
                    continue
                k, _, v = raw.partition(":")
                fm[k.strip()] = v.strip().strip('"').strip("'")
            return fm, body
    return fm, text


def adapt_codex_paths(text: str) -> str:
    """Translate Claude paths and command mentions to the Codex projection.

    Root Markdown skills become SKILL.md directories in Codex, so convert the
    common explicit `.md` references before applying the broader replacements.
    """
    import re

    text = re.sub(
        r"\.claude/skills/([A-Za-z0-9_-]+)\.md",
        r".codex/skills/\1/SKILL.md",
        text,
    )
    text = (text.replace(".claude/skills/", ".codex/skills/")
                .replace(".claude/rules/", ".codex/rules/")
                .replace(".claude/agents/", ".codex/agents/")
                .replace(".claude/project/", ".codex/project/")
                .replace(".claude/stack-profiles/", ".codex/stack-profiles/")
                .replace(".claude/templates/", ".codex/templates/")
                .replace(".claude/", ".codex/")
                .replace("Requires a Claude Code restart afterward.",
                         "Requires a new Codex session afterward."))
    text = text.replace(
        'kuraka-backup.py" <project-root>',
        'kuraka-backup.py" <project-root> --layer-root .codex/project --skip-overrides',
    )
    command_names = (
        "checkmarx-remediation", "kuraka-wizard", "kuraka-backup",
        "kuraka-update", "kuraka", "amauta", "inti", "arki",
    )
    for name in command_names:
        text = text.replace(f"/prompts:{name}", f"${name}")
        text = re.sub(
            rf"(?<![A-Za-z0-9_.$/])/{re.escape(name)}(?![A-Za-z0-9_.-])",
            f"${name}",
            text,
        )
    return text


def sync_codex_skills(src_skills: Path, dst_skills: Path) -> int:
    """Sync only reusable Kuraka skills as Codex-native project skills.

    Agent roles are rendered separately to `.codex/agents/*.toml`; publishing
    them as skills duplicates the catalog and prevents native delegation.
    """
    dst_skills.mkdir(parents=True, exist_ok=True)
    count = 0

    if src_skills.is_dir():
        for p in sorted(src_skills.glob("*.md")):
            if p.name.endswith(".append.md"):
                continue
            fm, body = _frontmatter_and_body(p)
            name = fm.get("name") or p.stem
            desc = fm.get("description") or f"Kuraka workflow skill: {name}"
            skill_dir = dst_skills / name
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text(_codex_skill_text(name, desc, body, "skill"), encoding="utf-8")
            count += 1
        for d in src_skills.iterdir():
            if d.is_dir():
                sync_tree(d, dst_skills / d.name, target_env="codex")

    return count


CODEX_REASONING_EFFORT = {
    "frontier": "high",
    "heavy": "high",
    "balanced": "medium",
    "fast": "low",
}

CODEX_READ_ONLY_AGENTS = {
    "architect-reviewer",
    "code-reviewer",
    "security-reviewer",
    "final-auditor",
    "migration-reviewer",
    "pattern-detector",
}


def read_codex_agent_settings(vault: Path) -> dict[str, tuple[str | None, str]]:
    """Resolve Codex model settings from MODEL-ROUTING.yaml without PyYAML.

    A placeholder such as `<most-capable available>` intentionally omits the
    `model` key so the custom agent inherits the user's valid Codex model.
    """
    routing = vault / "MODEL-ROUTING.yaml"
    if not routing.is_file():
        return {}
    agent_tiers: dict[str, str] = {}
    codex_models: dict[str, str] = {}
    section = ""
    platform = ""
    for raw in routing.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        line = raw.strip().split(" #", 1)[0].strip()
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if indent == 0:
            section = key
            platform = ""
        elif section == "agents":
            agent_tiers[key] = value
        elif section == "platforms" and indent == 2:
            platform = key
        elif section == "platforms" and platform == "codex" and indent >= 4:
            codex_models[key] = value

    settings: dict[str, tuple[str | None, str]] = {}
    for name, tier in agent_tiers.items():
        model = codex_models.get(tier)
        if model and (model.startswith("<") or model == "inherit"):
            model = None
        settings[name] = (model, CODEX_REASONING_EFFORT.get(tier, "medium"))
    return settings


def _toml_multiline_literal(text: str) -> str:
    """Encode instructions as a TOML multiline literal string."""
    if "'''" in text:
        raise ValueError("Codex agent source contains unsupported TOML literal delimiter")
    return "'''\n" + text.rstrip() + "\n'''"


def render_codex_agent_toml(name: str, description: str, body: str,
                             model: str | None, reasoning_effort: str,
                             sandbox_mode: str) -> str:
    """Render a native Codex custom agent from a Claude-source agent body."""
    instructions = f"""# Kuraka Codex Agent Contract

You are the `{name}` subagent in a gated Kuraka workflow. Work only on the
phase and inputs supplied by the orchestrator. Do not advance phases, invoke
other Kuraka agents, or request approval from the user directly.

Load the referenced skills, project layer, stack profile, rules, and output
schema before acting. Preserve evidence with file paths and run only the
validation appropriate to this phase.

Return exactly one handoff status:
- `DONE`: list produced or inspected artifacts and validation evidence.
- `CLARIFY`: state the blocking question and why it prevents a valid output.
- `BLOCKED`: state the missing dependency or failed precondition.
- `VALIDATION_FAILED`: state the failed check and affected artifacts.

The orchestrator owns checkpoints, telemetry, phase gates, user interaction,
and final decisions. Never invent unavailable usage metrics; report them as
`unknown` when requested.

--- Source role instructions ---

{adapt_codex_paths(body)}
"""
    lines = [
        f"name = {json.dumps(name)}",
        f"description = {json.dumps(adapt_codex_paths(description))}",
    ]
    if model:
        lines.append(f"model = {json.dumps(model)}")
    lines.extend([
        f"model_reasoning_effort = {json.dumps(reasoning_effort)}",
        f"sandbox_mode = {json.dumps(sandbox_mode)}",
        f"developer_instructions = {_toml_multiline_literal(instructions)}",
        "",
    ])
    return "\n".join(lines)


def sync_codex_agents(src_agents: Path, dst_agents: Path, vault: Path) -> int:
    """Compile Claude-source Markdown agents to native Codex TOML agents."""
    dst_agents.mkdir(parents=True, exist_ok=True)
    settings = read_codex_agent_settings(vault)
    count = 0
    for source in sorted(src_agents.glob("*.md")):
        fm, body = _frontmatter_and_body(source)
        name = fm.get("name") or source.stem
        description = fm.get("description") or f"Kuraka specialist agent: {name}."
        model, effort = settings.get(name, (None, "medium"))
        sandbox = "read-only" if name in CODEX_READ_ONLY_AGENTS else "workspace-write"
        rendered = render_codex_agent_toml(name, description, body, model, effort, sandbox)
        (dst_agents / f"{name}.toml").write_text(rendered, encoding="utf-8")
        count += 1
    return count


def ensure_codex_agent_config(config_path: Path) -> bool:
    """Add Kuraka's safe concurrency default without replacing user config."""
    key = "max_concurrent_threads_per_session"
    default = f"{key} = 4"
    if not config_path.exists():
        config_path.write_text("[agents]\n" + default + "\n", encoding="utf-8")
        return True

    lines = config_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    section_start = None
    section_end = len(lines)
    for index, line in enumerate(lines):
        if line.strip() == "[agents]":
            section_start = index
            continue
        if section_start is not None and line.strip().startswith("["):
            section_end = index
            break
    if section_start is None:
        suffix = "\n" if lines else ""
        config_path.write_text("\n".join(lines) + suffix + "\n[agents]\n" + default + "\n", encoding="utf-8")
        return True
    if any(line.strip().startswith(key + " =") for line in lines[section_start + 1:section_end]):
        return False
    lines.insert(section_end, default)
    config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return True


# ------------------------------------------------------------------------- main

def main() -> int:
    _enable_windows_ansi()

    # argument parsing for target directory and target platform
    target_dir_arg = None
    target_env = "claude"

    args_list = sys.argv[1:]
    if any(arg in ("-h", "--help") for arg in args_list):
        print("Usage: python3 kuraka-mount.py [target_dir] [--target claude|antigravity|cursor|codex] [--update]")
        print("Mount Kuraka framework artifacts into a consumer project.")
        print("")
        print("  --update / -u / update   Framework-only refresh: updates agents, skills,")
        print("                           commands, rules, hooks, contexts, stack-profiles,")
        print("                           templates and tests/kuraka from the vault, re-applies")
        print("                           your overrides, and NEVER touches project history")
        print("                           (docs/process/**, checkpoints, .claude/project/,")
        print("                           kuraka.config.yaml). Non-interactive.")
        print("                           PLATFORM-AWARE: without --target it auto-detects the")
        print("                           platform(s) already mounted in the project (.claude /")
        print("                           .agents / .codex / .cursor) and refreshes EACH with")
        print("                           its own render — it never first-mounts a platform.")
        print("                           Restart the session afterwards to re-register")
        print("                           agents/skills/hooks.")
        return 0
    update_mode = False
    target_env_explicit = False
    i = 0
    while i < len(args_list):
        a = args_list[i]
        if a in ("--target", "-t"):
            if i + 1 < len(args_list):
                target_env = args_list[i + 1]
                target_env_explicit = True
                i += 2
            else:
                i += 1
        elif a.startswith("--target="):
            target_env = a.split("=", 1)[1]
            target_env_explicit = True
            i += 1
        elif a in ("--update", "-u", "update"):
            update_mode = True
            i += 1
        else:
            if not target_dir_arg:
                target_dir_arg = a
            i += 1

    target = Path(target_dir_arg or os.getcwd()).expanduser().resolve()

    if not VAULT.is_dir():
        print(f"❌ ERROR: vault no encontrado en {VAULT}", file=sys.stderr)
        return 1
    if not target.is_dir():
        print(f"❌ ERROR: target no existe: {target}", file=sys.stderr)
        return 1

    # --update is PLATFORM-AWARE: it refreshes what is already mounted, with
    # that platform's own render — mounting Claude-only material into an
    # Antigravity/Codex/Cursor project (or vice versa) is exactly the failure
    # mode this block prevents. An update never first-mounts a platform.
    ENV_DIRS = {"claude": ".claude", "antigravity": ".agents",
                "codex": ".codex", "cursor": ".cursor"}

    def _mounted_for(env: str) -> bool:
        return (target / ENV_DIRS[env] / "agents").is_dir()

    if update_mode:
        if target_env_explicit:
            if target_env not in ENV_DIRS:
                print(f"❌ ERROR: target desconocido '{target_env}'", file=sys.stderr)
                return 1
            if not _mounted_for(target_env):
                print(f"❌ ERROR: este proyecto NO está montado para '{target_env}' "
                      f"(no existe {ENV_DIRS[target_env]}/agents/).", file=sys.stderr)
                print("   --update solo refresca plataformas ya montadas; para estrenar una,",
                      file=sys.stderr)
                print(f"   corre el mount completo: kuraka-mount.py {target} --target {target_env}",
                      file=sys.stderr)
                return 1
        else:
            detected = [e for e in ("claude", "antigravity", "codex", "cursor")
                        if _mounted_for(e)]
            if not detected:
                print("❌ ERROR: ninguna plataforma Kuraka montada en este proyecto "
                      "(.claude/.agents/.codex/.cursor sin agents/).", file=sys.stderr)
                print("   Corre primero el mount completo: kuraka-mount.py <target> "
                      "[--target <plataforma>]", file=sys.stderr)
                return 1
            if len(detected) == 1:
                target_env = detected[0]
                print(f"🪢 kuraka update — plataforma detectada: {target_env}")
            else:
                import subprocess as _sp
                print(f"🪢 kuraka update — plataformas montadas detectadas: {', '.join(detected)}")
                print("   → actualizando cada una con su propio render…")
                print("")
                rc = 0
                for env in detected:
                    r = _sp.run([sys.executable, str(Path(__file__).resolve()),
                                 str(target), "--update", "--target", env])
                    rc = max(rc, r.returncode)
                return rc

    banner()
    print(f"   vault:    {VAULT}")
    print(f"   target:   {target}")
    print(f"   entorno:  {target_env}")
    if update_mode:
        print("   modo:     UPDATE — solo framework; historial del proyecto intacto")
        print("             (docs/process/**, checkpoints, .claude/project/ y")
        print("             kuraka.config.yaml no se tocan; overrides se preservan)")
    print("")

    # Determine platform customization directory
    if target_env == "antigravity":
        platform_dir = target / ".agents"
    elif target_env == "cursor":
        platform_dir = target / ".cursor"
    elif target_env == "codex":
        platform_dir = target / ".codex"
    else:
        platform_dir = target / ".claude"

    platform_dir.mkdir(parents=True, exist_ok=True)
    if target_env == "codex" and ensure_codex_agent_config(platform_dir / "config.toml"):
        print("   ✓ .codex/config.toml: límite de 4 subagentes concurrentes")

    selected = {"agents", "skills", "commands", "rules", "artifacts"}
    menu_mode = "all"
    tty = sys.stdin.isatty() and not update_mode  # update mode is non-interactive

    if tty:
        if (platform_dir / "agents").is_dir():
            print(f"ℹ️  Kuraka YA está montado en este proyecto ({platform_dir.name}) → esto es un re-mount (update).")
        else:
            print(f"🆕 Primer montaje de Kuraka en este proyecto ({platform_dir.name}).")
        hist = capture_py("kuraka-restore.py", str(target), "--check")
        for line in hist.splitlines():
            if "historia en central" in line:
                print(f"   📦 El vault guarda historia de este proyecto: {line.split('central:',1)[1].strip()}")
                print("      → al terminar el montaje se te preguntará si restaurarla para continuar el trabajo.")
                break
        print("")
        print("¿Qué querés montar?")
        print("   [Enter] todo   ·   c) elegir categorías   ·   s) solo ver estado (sin montar)")
        try:
            choice = input("   > ").strip()
        except EOFError:
            choice = ""
        if choice.lower() == "c":
            print("   Categorías: agents  skills  commands  rules  artifacts")
            try:
                sel = input("   Ingresá las que querés (separadas por espacio) [todo]: ").strip()
            except EOFError:
                sel = ""
            if sel:
                selected = set(sel.split())
            print("")
        elif choice.lower() == "s":
            menu_mode = "status"

    if tty:
        run_py("kuraka-init.py", "--recommend-only", "--target", str(target))

    if menu_mode == "status":
        print("ℹ️  Modo 'solo estado' — no se montó nada.")
        return 0

    def want(cat: str) -> bool:
        return cat in selected

    # pre-flight: snapshot local overrides BEFORE the copy overwrites them.
    if target_env != "codex" and (platform_dir / "agents").is_dir():
        if run_py("kuraka-backup.py", str(target), "--overrides-only", quiet=True) == 0:
            print("   ✓ overrides locales respaldados al store central (pre-mount)")
            print("")

    # --- sync personal categories ---
    synced_agents = False
    for category in ("agents", "skills", "commands", "hooks"):
        wcat = "agents" if category == "hooks" else category
        if not want(wcat):
            continue
        if category == "hooks" and target_env != "claude":
            # Hooks are CLAUDE-ONLY harness enforcement. Other platforms keep
            # the full manual discipline prose via _expand_discipline instead.
            continue
        src = VAULT / category
        dst = platform_dir / category
        if src.is_dir():
            if target_env == "codex" and category == "commands":
                # kuraka-export.py compiles command entrypoints to project-local
                # Codex skills. Current Codex does not discover .codex/commands
                # or .codex/prompts as custom slash commands.
                print("   → commands/  (se compilarán como skills Codex)")
                continue
            dst.mkdir(parents=True, exist_ok=True)
            if target_env == "codex" and category == "agents":
                before = count_codex_agents(dst)
            elif target_env == "codex" and category == "skills":
                before = count_codex_skills(dst)
            else:
                before = count_top(dst)
            if category == "skills" and target_env == "claude":
                sync_claude_skills(src, dst)
            elif category == "skills" and target_env == "antigravity":
                sync_antigravity_skills(src, dst)
            elif category == "skills" and target_env == "codex":
                sync_codex_skills(src, dst)
            elif category == "agents" and target_env == "codex":
                sync_codex_agents(src, dst, VAULT)
            else:
                sync_tree(src, dst, exclude=("*.append.md",), target_env=target_env)
            if target_env == "codex" and category == "agents":
                after = count_codex_agents(dst)
            elif target_env == "codex" and category == "skills":
                after = count_codex_skills(dst)
            else:
                after = count_top(dst)
            delta = after - before
            if delta > 0:
                print(f"   + {category}/  ({delta} new, {after} total)")
                if category == "agents":
                    synced_agents = True
            else:
                print(f"   ✓ {category}/  (up to date, {after} total)")

    # Claude hook wiring: merge the vault's hook config into settings.json
    if target_env == "claude" and want("agents"):
        merged = merge_claude_hook_settings(platform_dir)
        if merged is True:
            print("   ✓ hooks/  cableados en .claude/settings.json")
        elif isinstance(merged, str):
            print(f"   ⚠ hooks NO cableados: {merged}")

    # Claude managed CLAUDE.md block: always-on evidence rule via @import
    if target_env == "claude" and want("rules"):
        if ensure_claude_md_block(target):
            print("   ✓ CLAUDE.md — bloque gestionado kuraka (regla 19 siempre activa)")

    # contexts sub-directory
    if want("agents") and (VAULT / "agents" / "contexts").is_dir():
        sync_tree(VAULT / "agents" / "contexts", platform_dir / "agents" / "contexts", target_env=target_env)
        print("   ✓ agents/contexts/")

    # personal rules (meta-rules of the agent system)
    if want("rules"):
        for rule in ("16-agent-backup.md", "17-kuraka-token-optimizations.md",
                     "18-duplication-aware-refactor.md", "19-evidence.md"):
            src = VAULT / "rules" / rule
            if src.is_file():
                copy_file(src, platform_dir / "rules" / rule, target_env=target_env)
                print(f"   ✓ rules/{rule}")

    # framework-level artifacts outside platform_dir
    artifacts = VAULT / "kuraka-artifacts"
    if want("artifacts") and artifacts.is_dir():
        print("")
        print("[kuraka-mount] restoring Kuraka artifacts...")
        # docs/process templates are SEEDS: only copied when the project doesn't
        # have the file yet. A project's accumulated lessons-learned / dashboard
        # is implementation HISTORY and must never be clobbered by a re-mount.
        # (Skipped entirely in --update mode.)
        ll = artifacts / "docs" / "process" / "lessons-learned.md"
        ll_dst = target / "docs" / "process" / "lessons-learned.md"
        if ll.is_file() and not update_mode and not ll_dst.exists():
            copy_file(ll, ll_dst)
            print("   ✓ docs/process/lessons-learned.md (sembrado — no existía)")
        dash = artifacts / "docs" / "process" / "agent-telemetry" / "DASHBOARD.md"
        dash_dst = target / "docs" / "process" / "agent-telemetry" / "DASHBOARD.md"
        if dash.is_file() and not update_mode and not dash_dst.exists():
            copy_file(dash, dash_dst)
            print("   ✓ docs/process/agent-telemetry/DASHBOARD.md (sembrado — no existía)")
        if (artifacts / "tests" / "kuraka").is_dir():
            sync_tree(artifacts / "tests" / "kuraka", target / "tests" / "kuraka",
                      exclude=(".pytest_cache", "__pycache__"))
            print("   ✓ tests/kuraka/")
        if (artifacts / "stack-profiles").is_dir():
            sync_tree(artifacts / "stack-profiles", platform_dir / "stack-profiles", target_env=target_env)
            if target_env == "antigravity":
                sync_tree(artifacts / "stack-profiles", target / ".claude" / "stack-profiles")
            print("   ✓ stack-profiles/")
        if (artifacts / "templates").is_dir():
            sync_tree(artifacts / "templates", platform_dir / "templates", target_env=target_env)
            if target_env == "antigravity":
                sync_tree(artifacts / "templates", target / ".claude" / "templates")
            print("   ✓ templates/")

    # Export AGENTS.md + slash commands / workflows for target platform
    if target_env in ("antigravity", "cursor", "codex"):
        run_py("kuraka-export.py", str(target), "--target", target_env)

    # record mount manifest
    try:
        import kuraka_common as _kc
        mounted_cats = tuple(c for c in _kc.OVERRIDE_CATEGORIES if want(c))
        if mounted_cats:
            n = _kc.write_mount_manifest(target, VAULT, mounted_cats, platform=platform_dir.name)
            print(f"   ✓ mount manifest ({n} vault baselines → {platform_dir.name}/{_kc.MOUNT_MANIFEST_NAME})")
    except ImportError:
        print("   ⚠ kuraka_common.py not found — mount manifest skipped")

    # re-apply project-specific overrides
    if target_env != "codex":
        run_py("kuraka-restore.py", str(target), "--overrides-only", "--target", target_env)

    # --- ensure .gitignore excludes personal content ---
    gitignore = target / ".gitignore"
    if target_env == "antigravity":
        patterns = [
            "# Kuraka framework files (versioned externally; not source of this repo)",
            ".agents/agents/",
            ".agents/skills/",
            ".agents/commands/",
            ".agents/rules/16-agent-backup.md",
            ".agents/rules/17-kuraka-token-optimizations.md",
            ".agents/rules/18-duplication-aware-refactor.md",
            ".agents/rules/19-evidence.md",
            ".agents/.kuraka-mount-manifest.json",
            ".agent/workflows/",
            "# Per-cycle telemetry JSONs (noise; the consolidated DASHBOARD.md is tracked)",
            "docs/process/agent-telemetry/*.json",
            "# Tool scratch dirs (never track)",
            ".playwright-mcp/",
            ".pytest_cache/",
        ]
    elif target_env == "codex":
        patterns = [
            "# Kuraka framework files (versioned externally; not source of this repo)",
            ".codex/agents/",
            ".codex/skills/",
            ".codex/commands/",
            ".codex/prompts/",
            ".codex/rules/16-agent-backup.md",
            ".codex/rules/17-kuraka-token-optimizations.md",
            ".codex/rules/18-duplication-aware-refactor.md",
            ".codex/rules/19-evidence.md",
            ".codex/.kuraka-mount-manifest.json",
            "# Per-cycle telemetry JSONs (noise; the consolidated DASHBOARD.md is tracked)",
            "docs/process/agent-telemetry/*.json",
            "# Tool scratch dirs (never track)",
            ".playwright-mcp/",
            ".pytest_cache/",
        ]
    else:
        patterns = [
            "# Kuraka framework files (versioned externally; not source of this repo)",
            ".claude/agents/",
            ".claude/skills/",
            ".claude/commands/",
            ".claude/hooks/",
            ".claude/rules/16-agent-backup.md",
            ".claude/rules/17-kuraka-token-optimizations.md",
            ".claude/rules/18-duplication-aware-refactor.md",
            ".claude/rules/19-evidence.md",
            ".claude/.kuraka-mount-manifest.json",
            "# Per-cycle telemetry JSONs (noise; the consolidated DASHBOARD.md is tracked)",
            "docs/process/agent-telemetry/*.json",
            "# Tool scratch dirs (never track)",
            ".playwright-mcp/",
            ".pytest_cache/",
        ]

    existing = gitignore.read_text(encoding="utf-8", errors="ignore").splitlines() if gitignore.exists() else []
    to_add = [p for p in patterns if p not in existing]
    if to_add:
        with gitignore.open("a", encoding="utf-8") as fh:
            for p in to_add:
                fh.write(p + "\n")
        print("")
        print(f"   + {len(to_add)} entradas añadidas a .gitignore")

    print("")
    if update_mode:
        print(f"✅ Framework Kuraka ACTUALIZADO en {target}/{platform_dir.name}/ — historial intacto.")
        print("   → Reiniciá Claude Code en el proyecto (/exit + sesión nueva) para")
        print("     re-registrar agentes, skills y hooks.")
        print("")
        return 0
    print(f"✅ Kuraka montado en {target}/{platform_dir.name}/")
    print("")

    # auto-register in the vault registry
    if run_py("kuraka-init.py", "--target", str(target), "--register-only", "--yes", quiet=True) == 0:
        print("   ✓ registrado en el registro del vault (projects/)")
        print("")

    # offer to restore Kuraka history
    if (VAULT / "kuraka-restore.py").exists():
        restore_layer_args = (("--layer-root", ".codex/project", "--skip-overrides")
                              if target_env == "codex" else ())
        if tty:
            run_py("kuraka-restore.py", str(target), *restore_layer_args)
        else:
            run_py("kuraka-restore.py", str(target), "--check")
            print("   ℹ️  Para restaurar la historia (si la hay):")
            layer_hint = (' --layer-root .codex/project --skip-overrides'
                          if target_env == "codex" else '')
            print(f'      python3 "{VAULT / "kuraka-restore.py"}" "{target}"{layer_hint}   # pregunta antes de pegar')
        print("")

    # auto-seed from a pre-populated migration-example layer
    seed_src = artifacts / "migration-examples" / f"{target.name}-project-layer"
    if seed_src.is_dir():
        seeded = False
        if not (target / "kuraka.config.yaml").exists() and (seed_src / "kuraka.config.yaml").is_file():
            copy_file(seed_src / "kuraka.config.yaml", target / "kuraka.config.yaml")
            print(f"   ✓ kuraka.config.yaml sembrado (migration-examples/{target.name}-project-layer → raíz)")
            seeded = True

        proj_dst = platform_dir / "project"
        if not proj_dst.is_dir():
            sync_tree(seed_src, proj_dst, exclude=("kuraka.config.yaml", "README.md"))
            if target_env == "antigravity":
                sync_tree(seed_src, target / ".claude" / "project", exclude=("kuraka.config.yaml", "README.md"))
            print(f"   ✓ {platform_dir.name}/project/ sembrado (migration-examples/{target.name}-project-layer)")
            seeded = True
        if seeded:
            print("")

    # adoption check
    has_config = (target / "kuraka.config.yaml").exists()
    has_project = (platform_dir / "project").is_dir() or (target / ".claude" / "project").is_dir()
    layer_src = seed_src
    if not has_config or not has_project:
        print("⚠️  ATENCIÓN — ADOPCIÓN INCOMPLETA")
        print("")
        if not has_config:
            print("   ❌ kuraka.config.yaml NO existe en el proyecto.")
        if not has_project:
            print(f"   ❌ {platform_dir.name}/project/ NO existe en el proyecto.")
        print("")
        print("   Los agentes refactorizados (v0.3+) leen kuraka.config.yaml para")
        print(f"   paths y comandos, y {platform_dir.name}/project/ para convenciones y lecciones.")
        print("   Sin esos dos artefactos, los agentes van a fallar o degradar a")
        print("   guidance genérico.")
        print("")
        print("   Para completar la adopción:")
        print("")
        print(f'     export KURAKA_VAULT="{VAULT}"')
        if layer_src.is_dir():
            print(f'     SRC="$KURAKA_VAULT/kuraka-artifacts/migration-examples/{target.name}-project-layer"')
            if not has_config:
                print('     cp "$SRC/kuraka.config.yaml" ./kuraka.config.yaml   # config pre-rellenado → RAÍZ del repo')
            if not has_project:
                print(f"     mkdir -p {platform_dir.name}/project")
                print(f'     cp -R "$SRC/." {platform_dir.name}/project/   # (excepto kuraka.config.yaml y README.md)')
        else:
            if not has_config:
                print('     cp "$KURAKA_VAULT/kuraka-artifacts/config-schema.yaml" ./kuraka.config.yaml')
                print("     # editá kuraka.config.yaml con los valores reales del proyecto")
            if not has_project:
                print(f"     mkdir -p {platform_dir.name}/project")
                print("     # creá los archivos del layer a medida (ver kuraka-artifacts/migration-examples/README.md)")
        print("")

    # command catalog + start guide
    if target_env == "antigravity":
        cmd_dir = target / ".agent" / "workflows"
    elif target_env == "cursor":
        cmd_dir = target / ".cursor" / "commands"
    elif target_env == "codex":
        cmd_dir = target / ".codex" / "skills"
    else:
        cmd_dir = target / ".claude" / "commands"

    run_py("kuraka-export.py", "--catalog", str(cmd_dir), "--env", target_env, str(target))

    print("📋 NOTAS DEL MONTAJE:")
    print("")
    print("  • Unstage cualquier fichero personal ya indexado en git:")
    if target_env == "codex":
        print("     git restore --staged .codex/agents/ .codex/skills/ 2>/dev/null || true")
        print("     git restore --staged .codex/rules/16-agent-backup.md .codex/rules/17-kuraka-token-optimizations.md 2>/dev/null || true")
    else:
        print(f"     git restore --staged {platform_dir.name}/agents/ {platform_dir.name}/skills/ {platform_dir.name}/commands/ 2>/dev/null || true")
        print(f"     git restore --staged {platform_dir.name}/rules/16-agent-backup.md {platform_dir.name}/rules/17-kuraka-token-optimizations.md 2>/dev/null || true")
    print("")
    if synced_agents:
        print(f"  • Agentes sincronizados en {platform_dir.name}/.")
    else:
        print("  • Agentes ya presentes y sincronizados.")
    print("")
    print("  • (Recomendado) Componentes que potencian Kuraka:")
    print(f"     {VAULT}/RECOMMENDED-COMPONENTS.md")
    print("     → RTK (ahorro 70-90% de tokens), ui-ux-pro-max, Playwright MCP...")
    print("")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
