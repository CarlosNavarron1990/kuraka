#!/usr/bin/env python3
"""kuraka-map.py — emit the LIVE wiring graph of the mounted Kuraka suite as JSON.

Single source: the real vault files. Nothing here is hand-curated — edit an
agent/skill .md and the next run re-wires the graph:

  agents/*.md      frontmatter (model, maxTurns, tools, disallowedTools,
                   skills, memory, description) + body markers the agents
                   already declare: **Phase:**, **Receives from:**,
                   **Delivers to:** (backticked agent refs become edges) and
                   **Skill(s):** (backticked skill refs become usage links).
  skills/*.md      frontmatter name/description + invocability flags.
  hooks/*          the enforcement pack (first doc line of each).
  commands/*.md    the mounted slash commands.
  rules/1[6-9]*.md the framework meta-rules.

Usage:
  python3 kuraka-map.py                # JSON to stdout
  python3 kuraka-map.py --out map.json
  python3 kuraka-map.py --inject proto.html   # replace /*__KURAKA_DATA__*/ marker

This is the data layer of the kuraka-control node board: the consumer frontend
renders whatever this emits (prototype: embedded snapshot; live version: fetch).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

VAULT = Path(__file__).resolve().parent

FM_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)
TICK = re.compile(r"`([A-Za-z0-9_./-]+)`")

HOOK_EVENTS = {
    "telemetry_append.py": "PostToolUse · Task",
    "gate_integrity.py": "PreToolUse · Bash",
    "orchestrator_guard.py": "PreToolUse · Write/Edit",
    "output_validate.py": "SubagentStop",
}


def fm_and_body(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    m = FM_RE.match(text)
    fm: dict[str, str] = {}
    body = text
    if m:
        body = text[m.end():]
        for line in m.group(1).splitlines():
            if ":" in line and not line.startswith((" ", "\t")):
                k, _, v = line.partition(":")
                fm[k.strip()] = v.strip().strip('"').strip("'")
    return fm, body


def marker(body: str, label: str) -> str:
    m = re.search(rf"\*\*{label}:?\*\*:?\s*(.+)", body)
    return m.group(1).strip() if m else ""


def refs(text: str, universe: set[str]) -> list[str]:
    out = []
    for t in TICK.findall(text):
        t = t.strip("/")
        if t in universe and t not in out:
            out.append(t)
    return out


def build() -> dict:
    agent_files = sorted((VAULT / "agents").glob("*.md"))
    skill_files = sorted((VAULT / "skills").glob("*.md"))
    agent_ids = {p.stem for p in agent_files}
    skill_ids = {p.stem for p in skill_files}

    skills = []
    for p in skill_files:
        fm, _ = fm_and_body(p)
        skills.append({
            "id": p.stem,
            "desc": fm.get("description", ""),
            "invocable": fm.get("user-invocable", "true") != "false",
            "fork": fm.get("context") == "fork",
            "raw": p.read_text(encoding="utf-8", errors="ignore"),
        })

    agents, edges, skill_links = [], [], []
    for p in agent_files:
        fm, body = fm_and_body(p)
        aid = p.stem
        fm_skills = [s.strip() for s in
                     fm.get("skills", "").strip("[]").split(",") if s.strip()]
        recv_raw = marker(body, "Receives from")
        deliv_raw = marker(body, "Delivers to")
        phase = (marker(body, "Phase") or marker(body, "Phases") or
                 marker(body, "Invoked") or marker(body, "Trigger") or
                 marker(body, "Mode"))
        # a second "### Phase N" section (dual-phase agents) enriches the label
        extra = re.findall(r"^### Phase ([\d.]+)", body, re.M)
        if extra and len(extra) > 1:
            phase = "Phases " + " + ".join(extra)
        for src in refs(recv_raw, agent_ids):
            edges.append({"from": src, "to": aid, "label": "", "src": "recv"})
        for dst in refs(deliv_raw, agent_ids):
            edges.append({"from": aid, "to": dst, "label": "", "src": "deliv"})
        # auto-trigger relations ("Auto-triggered by `x`", "Invoked by `x`")
        for src in refs(marker(body, "Trigger") + " " + marker(body, "Invoked"),
                        agent_ids):
            if src != aid:
                edges.append({"from": src, "to": aid, "label": "auto", "src": "auto"})
        body_skills = [s for s in refs(body, skill_ids) if s not in fm_skills]
        for s in fm_skills:
            skill_links.append({"skill": s, "agent": aid, "kind": "preloaded"})
        for s in body_skills:
            skill_links.append({"skill": s, "agent": aid, "kind": "uses"})
        agents.append({
            "id": aid,
            "model": fm.get("model", ""),
            "maxTurns": int(fm["maxTurns"]) if fm.get("maxTurns", "").isdigit() else None,
            "tools": fm.get("tools", ""),
            "disallowed": fm.get("disallowedTools", ""),
            "memory": fm.get("memory", ""),
            "skills": fm_skills,
            "desc": fm.get("description", ""),
            "phase": phase,
            "raw": p.read_text(encoding="utf-8", errors="ignore"),
        })

    # dedupe symmetric recv/deliv declarations
    seen, uniq = set(), []
    for e in edges:
        k = (e["from"], e["to"])
        if k in seen or e["from"] == e["to"]:
            continue
        seen.add(k)
        uniq.append(e)

    hooks, scripts = [], []
    hooks_dir = VAULT / "hooks"
    if hooks_dir.is_dir():
        for p in sorted(hooks_dir.iterdir()):
            if p.suffix == ".py":
                m = re.search(r'"""(.+?)$', p.read_text(encoding="utf-8"), re.M)
                hooks.append({"id": p.name, "event": HOOK_EVENTS.get(p.name, "hook"),
                              "desc": (m.group(1).strip() if m else "")})
            elif p.suffix == ".sh":
                lines = [l for l in p.read_text(encoding="utf-8").splitlines()
                         if l.startswith("# ") and "usage" not in l.lower()]
                scripts.append({"id": p.name,
                                "desc": lines[0][2:].strip() if lines else ""})

    # commands (the runnable workflows): full prompt + the agents/skills each
    # one references in its body (backticked names + skills/<n>.md paths)
    commands = []
    for p in sorted((VAULT / "commands").glob("*.md")):
        fm, body = fm_and_body(p)
        s_paths = set(re.findall(r"skills/([a-z0-9-]+)(?:\.md|/SKILL)", body))
        commands.append({
            "id": p.stem,
            "desc": fm.get("description", ""),
            "agents": [a for a in refs(body, agent_ids) if a != p.stem or a in agent_ids],
            "skills": sorted((set(refs(body, skill_ids)) | (s_paths & skill_ids))),
            "raw": p.read_text(encoding="utf-8", errors="ignore"),
        })
    rules = [p.name for p in sorted((VAULT / "rules").glob("1[6-9]-*.md"))]
    suite = ((VAULT / "SUITE-VERSION").read_text(encoding="utf-8").strip()
             if (VAULT / "SUITE-VERSION").is_file() else "?")

    return {"generated": date.today().isoformat(), "suite": suite,
            "agents": agents, "edges": uniq, "skills": skills,
            "skillLinks": skill_links, "hooks": hooks, "scripts": scripts,
            "commands": commands, "rules": rules}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", help="write JSON to this file")
    ap.add_argument("--inject", help="replace the /*__KURAKA_DATA__*/ marker "
                                     "in this HTML file with the JSON")
    args = ap.parse_args()
    data = build()
    js = json.dumps(data, ensure_ascii=False, indent=1)
    if args.inject:
        p = Path(args.inject)
        text = p.read_text(encoding="utf-8")
        marker_re = re.compile(r"const DATA = .*?;\s*/\*__KURAKA_DATA_END__\*/", re.S)
        replacement = f"const DATA = {js};\n/*__KURAKA_DATA_END__*/"
        if "/*__KURAKA_DATA_END__*/" not in text:
            sys.exit("❌ marker /*__KURAKA_DATA_END__*/ not found in " + args.inject)
        p.write_text(marker_re.sub(lambda _: replacement, text, count=1),
                     encoding="utf-8")
        print(f"✓ datos inyectados en {args.inject} "
              f"({len(data['agents'])} agentes, {len(data['edges'])} relevos, "
              f"{len(data['skills'])} skills)")
        return
    if args.out:
        Path(args.out).write_text(js + "\n", encoding="utf-8")
        print(f"✓ {args.out}")
    else:
        print(js)


if __name__ == "__main__":
    main()
