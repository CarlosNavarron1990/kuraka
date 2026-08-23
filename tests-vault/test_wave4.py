"""Vault-side tests for Wave 4 — agent memory, digest protocol, evidence
registry, and the orchestrator scripts (liveness watcher + review mechanics).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

VAULT = Path(__file__).resolve().parents[1]

PIPELINE_13 = ["po-analyst", "story-refiner", "architect-reviewer", "code-reviewer",
               "security-reviewer", "backend-developer", "frontend-developer",
               "test-engineer", "e2e-tester", "deployment-verifier",
               "migration-reviewer", "final-auditor", "pattern-detector"]


def test_digest_protocol_present_in_all_pipeline_agents():
    missing = [n for n in PIPELINE_13
               if "Digest protocol" not in (VAULT / "agents" / f"{n}.md").read_text(encoding="utf-8")]
    assert not missing, f"agents without the digest protocol block: {missing}"


def test_memory_emitted_for_cross_cycle_agents():
    for name in ("final-auditor", "pattern-detector"):
        head = (VAULT / "agents" / f"{name}.md").read_text(encoding="utf-8").split("\n---", 2)[1]
        assert "memory: project" in head, name


def test_evidence_registry_exists_and_covers_cited_incidents():
    text = (VAULT / "agents" / "contexts" / "EVIDENCE.md").read_text(encoding="utf-8")
    for incident in ("REQ-20260703", "REQ-20260801", "REQ-20260611", "DD-1031",
                     "LL-014", "LL-017", "LL-020"):
        assert incident in text, f"EVIDENCE.md missing {incident}"


def test_orchestrator_scripts_exist_and_parse():
    for script in ("liveness_watch.sh", "review_mechanics.sh"):
        p = VAULT / "hooks" / script
        assert p.is_file(), script
        r = subprocess.run(["bash", "-n", str(p)], capture_output=True, text=True)
        assert r.returncode == 0, f"{script}: {r.stderr}"


def test_review_mechanics_smoke(tmp_path):
    proj = tmp_path / "proj"
    (proj / "backend").mkdir(parents=True)
    (proj / "kuraka.config.yaml").write_text(
        "architecture:\n  paths:\n    backend_root: backend\n", encoding="utf-8")
    (proj / "backend" / "app.ts").write_text(
        'console.log("debug")\nconst password = "hunter2"\n', encoding="utf-8")
    r = subprocess.run(["bash", str(VAULT / "hooks" / "review_mechanics.sh")],
                       cwd=proj, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "Review mechanics" in r.stdout
    assert "⚠" in r.stdout                      # both plants must be flagged
    assert "console.log" in r.stdout and "password" in r.stdout


def test_e2e_tester_trimmed_and_playbook_relocated():
    agent = (VAULT / "agents" / "e2e-tester.md").read_text(encoding="utf-8")
    assert len(agent.splitlines()) <= 220, \
        "e2e-tester should stay trimmed for haiku (was 282 pre-Wave-4)"
    ctx = (VAULT / "agents" / "contexts" / "e2e-tester-rules.md").read_text(encoding="utf-8")
    assert "CRUD test playbook" in ctx and "### CREATE" in ctx
    assert "CRUD test playbook" in agent  # pointer remains
