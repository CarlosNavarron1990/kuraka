#!/usr/bin/env python3
"""Kuraka hook — telemetry appender (PostToolUse Task|Agent + SubagentStop).

Appends JSONL rows to <docs_process_root>/agent-telemetry/HOOK-LOG.jsonl,
deterministically and at zero model cost. This guarantees telemetry
COMPLETENESS (the framework's #1 documented regression: REQ-20260801 recorded
19 of 31 runs; the cycle's real cost was +57% over the reported one). The
orchestrator's job is to ENRICH (phase, budget_ok) and consolidate into the
REQ's curated telemetry JSON — never to remember to capture.

Two rows per subagent, joined by `agent_id`:

  event "launch"  PostToolUse. Claude Code launches subagents in the
                  BACKGROUND: the tool response is only an `async_launched`
                  ack (agentId, resolvedModel) and carries NO usage. Reading
                  tokens here is why 869/869 rows across 9 projects logged
                  total_tokens null, twice "fixed" by parsing more key names.
  event "stop"    SubagentStop. The payload names `agent_transcript_path`;
                  the cost is computed from that transcript (one usage per
                  API message, de-duplicated by message id). CUMULATIVE over
                  the whole transcript: a resumed agent writes another stop
                  row with a higher `seq` — consumers keep the last one.

A launch with no stop is an agent that never finished (lost, killed, session
closed). A synchronous response that does carry usage is logged as a single
event "run". `total_tokens` is the harness-equivalent figure (context + output
of the LAST turn), comparable with the budgets; the *_sum fields are the real
spend across turns.

Fail-open by design: any unexpected input exits 0. Only active in projects
with a kuraka.config.yaml.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


# Usage keys as the harness may emit them. The PostToolUse payload for Task/Agent
# carries a STRUCTURED tool_response (camelCase: totalTokens / totalToolUseCount /
# totalDurationMs); async hand-backs carry a <usage> XML block (snake_case). The
# first version only regex-scraped snake_case off the serialized blob, so 100% of
# rows logged total_tokens/duration_ms null in 6 projects (guai, azure, possuite,
# sie-integraciones, petsuite, piscosdalston) — the Phase-7 cross-check could
# confirm a run happened but never what it cost.
_USAGE_KEYS = {
    "total_tokens": ("totalTokens", "total_tokens", "subagent_tokens", "subagentTokens"),
    "tool_uses": ("totalToolUseCount", "tool_uses", "toolUses", "tool_use_count"),
    "duration_ms": ("totalDurationMs", "duration_ms", "durationMs"),
}


def _as_int(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return int(v)
    if isinstance(v, str) and v.strip().isdigit():
        return int(v.strip())
    return None


def _walk(obj, depth=0):
    if depth > 6:
        return
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _walk(v, depth + 1)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v, depth + 1)


def extract_usage(resp, blob: str) -> dict:
    """Structured fields first (any nesting), then <usage> XML tags, then a
    `key: N` regex over the blob. Never raises; missing stays None (null, not 0)."""
    out = {k: None for k in _USAGE_KEYS}
    try:
        parsed = resp
        if isinstance(resp, str):
            try:
                parsed = json.loads(resp)
            except Exception:
                parsed = None
        for d in _walk(parsed):
            for field, keys in _USAGE_KEYS.items():
                if out[field] is not None:
                    continue
                for k in keys:
                    if k in d:
                        iv = _as_int(d[k])
                        if iv is not None:
                            out[field] = iv
                            break
    except Exception:
        pass
    for field, keys in _USAGE_KEYS.items():
        if out[field] is not None:
            continue
        for k in keys:
            mm = re.search(rf"<{k}>\s*(\d+)\s*</{k}>", blob) or \
                 re.search(rf"[\"']?{k}[\"']?\s*[:=]\s*(\d+)", blob)
            if mm:
                out[field] = int(mm.group(1))
                break
    return out


def _ts(s):
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return None


def transcript_usage(path) -> dict:
    """Cost of one subagent from its transcript JSONL. The transcript writes one
    row per content block, repeating the API message's usage — de-duplicate by
    message id. Never raises; an unreadable transcript yields all-None."""
    out = {"total_tokens": None, "tool_uses": None, "duration_ms": None,
           "model": None, "turns": None, "output_tokens_sum": None,
           "input_tokens_sum": None, "cache_creation_sum": None,
           "cache_read_sum": None, "last_text": ""}
    try:
        lines = Path(path).read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return out
    usages: dict = {}
    tools: set = set()
    first = last = None
    n_tools_anon = 0
    for line in lines:
        try:
            row = json.loads(line)
        except Exception:
            continue
        if not isinstance(row, dict):
            continue
        t = _ts(row.get("timestamp"))
        if t:
            first = first or t
            last = t
        msg = row.get("message")
        if not isinstance(msg, dict) or msg.get("role") != "assistant":
            continue
        u = msg.get("usage")
        if isinstance(u, dict):
            key = msg.get("id") or row.get("requestId") or row.get("uuid")
            usages[key] = u  # same id repeats per block; last write is the fullest
            if msg.get("model") and not str(msg["model"]).startswith("<"):
                out["model"] = msg["model"]
        content = msg.get("content")
        if isinstance(content, str) and content.strip():
            out["last_text"] = content
        if isinstance(content, list):
            texts = [b.get("text", "") for b in content
                     if isinstance(b, dict) and b.get("type") == "text"]
            if any(t.strip() for t in texts):
                out["last_text"] = "\n".join(texts)
            for b in content:
                if isinstance(b, dict) and b.get("type") == "tool_use":
                    if b.get("id"):
                        tools.add(b["id"])
                    else:
                        n_tools_anon += 1
    if not usages:
        return out

    def g(u, k):
        return _as_int(u.get(k)) or 0

    us = list(usages.values())
    lu = us[-1]
    out["total_tokens"] = (g(lu, "input_tokens") + g(lu, "cache_creation_input_tokens")
                           + g(lu, "cache_read_input_tokens") + g(lu, "output_tokens"))
    out["turns"] = len(us)
    out["output_tokens_sum"] = sum(g(u, "output_tokens") for u in us)
    out["input_tokens_sum"] = sum(g(u, "input_tokens") for u in us)
    out["cache_creation_sum"] = sum(g(u, "cache_creation_input_tokens") for u in us)
    out["cache_read_sum"] = sum(g(u, "cache_read_input_tokens") for u in us)
    out["tool_uses"] = len(tools) + n_tools_anon
    if first and last:
        out["duration_ms"] = int((last - first).total_seconds() * 1000)
    return out


def _norm(s) -> str:
    return " ".join(str(s or "").split())


def settled_usage(path, final_message, tries: int = 6, pause: float = 0.25) -> "tuple[dict, bool]":
    """SubagentStop can fire BEFORE the agent's final turn reaches the
    transcript (measured: 45,263 tokens read at stop vs 49,674 real — the last
    turn was missing). Wait briefly for the transcript to show the message the
    payload says was last; if it never does, return what there is and
    partial=True so kuraka-close recomputes it from `transcript` later."""
    want = _norm(final_message)
    usage = transcript_usage(path)
    for _ in range(max(tries - 1, 0)):
        if not want or _norm(usage.get("last_text")) == want:
            break
        time.sleep(pause)
        usage = transcript_usage(path)
    partial = bool(want) and _norm(usage.get("last_text")) != want
    return usage, partial


def _agent_meta(transcript_path) -> dict:
    """The harness writes agent-<id>.meta.json beside the transcript
    (agentType, description). Best effort."""
    try:
        p = Path(transcript_path)
        return json.loads(p.with_name(p.stem + ".meta.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def _prior_stops(log: Path, agent_id) -> int:
    if not agent_id or not log.is_file():
        return 0
    n = 0
    try:
        for line in log.read_text(encoding="utf-8", errors="ignore").splitlines():
            if agent_id in line and '"stop"' in line:
                n += 1
    except Exception:
        pass
    return n


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    event = data.get("hook_event_name") or "PostToolUse"
    if event not in ("PostToolUse", "SubagentStop"):
        return 0
    if event == "PostToolUse" and data.get("tool_name") not in (None, "Task", "Agent"):
        return 0

    proj = Path(os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd())
    config = proj / "kuraka.config.yaml"
    if not config.is_file():
        return 0  # not a Kuraka project

    try:
        cfg = config.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        cfg = ""
    m = re.search(r"docs_process_root:\s*\"?([^\"\n#]+?)\"?\s*$", cfg, re.M)
    docs_root = (m.group(1).strip() if m else "docs/process").strip("/")
    outdir = proj / docs_root / "agent-telemetry"
    log = outdir / "HOOK-LOG.jsonl"
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    if event == "SubagentStop":
        tpath = data.get("agent_transcript_path")
        agent_id = data.get("agent_id")
        if not tpath and agent_id and data.get("transcript_path"):
            sp = Path(str(data["transcript_path"]))
            tpath = sp.with_suffix("") / "subagents" / f"agent-{agent_id}.jsonl"
        usage, partial = (settled_usage(tpath, data.get("last_assistant_message"))
                          if tpath else (transcript_usage(""), False))
        usage.pop("last_text", None)
        meta = _agent_meta(tpath) if tpath else {}
        desc = meta.get("description")
        for bt in data.get("background_tasks") or []:
            if isinstance(bt, dict) and bt.get("id") == agent_id and bt.get("description"):
                desc = bt["description"]
        if (not data.get("agent_type") and not meta.get("agentType")
                and usage.get("total_tokens") is None
                and not (tpath and Path(str(tpath)).exists())):
            # Claude Code fires a second SubagentStop a few seconds after every
            # launch for an internal helper: another agent_id, no agent_type, no
            # transcript on disk. It is not a subagent of the cycle — logging it
            # doubled the invocation count (estimator-v2: 8 real runs, 16 rows).
            return 0
        seq = _prior_stops(log, agent_id) + 1
        entry = {
            "ts": now, "source": "hook", "event": "stop",
            "agent": data.get("agent_type") or meta.get("agentType"),
            "agent_id": agent_id, "description": desc,
            "model": usage.pop("model"),
            **usage,
            "seq": seq, "resumed": seq > 1,
            "partial": partial,
            "transcript": str(tpath) if tpath else None,
            "session_id": data.get("session_id"),
        }
    else:
        ti = data.get("tool_input") or {}
        resp = data.get("tool_response")
        blob = ""
        try:
            blob = resp if isinstance(resp, str) else json.dumps(resp, ensure_ascii=False)
        except Exception:
            pass
        usage = extract_usage(resp, blob)
        rd = resp if isinstance(resp, dict) else {}
        is_async = bool(rd.get("isAsync")) or rd.get("status") == "async_launched"
        complete = usage["total_tokens"] is not None and not is_async
        entry = {
            "ts": now, "source": "hook",
            "event": "run" if complete else "launch",
            "agent": ti.get("subagent_type"),
            "agent_id": rd.get("agentId") or rd.get("agent_id"),
            "description": ti.get("description"),
            "model": ti.get("model") or rd.get("resolvedModel"),
            "total_tokens": usage["total_tokens"] if complete else None,
            "tool_uses": usage["tool_uses"] if complete else None,
            "duration_ms": usage["duration_ms"] if complete else None,
            "session_id": data.get("session_id"),
        }

    try:
        outdir.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
