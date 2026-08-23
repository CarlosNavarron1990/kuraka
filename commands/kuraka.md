---
description: "Kuraka orchestrator: drive a full requirement through the gated multi-phase multi-agent dev workflow (PO analysis → story refinement → test planning → architect+schema-freeze → implementation → code/security review → tests/E2E/deploy-verify → final audit), scaling phases to the change's risk. The main entry point for any feature or change."
argument-hint: "<requerimiento / ticket Jira / alcance>"
---

Act as the **Kuraka** development orchestrator for the requirement described in the arguments below.

Arguments (requirement / Jira ticket / scope): $ARGUMENTS

Steps:

1. Read the orchestrator definition and its companion files, in this order:
   - `.claude/skills/kuraka.md` — main orchestrator (8-phase multi-agent workflow, plus subphases)
   - `.claude/skills/kuraka-modes.md` — how to scale the pipeline to the change's risk
   - `.claude/skills/kuraka-policies.md` — execution policies and gates

2. Apply rule `.claude/rules/17-kuraka-token-optimizations.md` BEFORE launching any
   subagent: evaluate the change surface (Rule 0), pick the minimum set of phases,
   announce the proposed pipeline with per-phase justification, and request user
   confirmation before invoking the first subagent.

3. Drive the workflow exactly as `kuraka.md` specifies: PO analysis → Story
   refinement → Test planning → Architect review → Implementation → Code review →
   Security → Tests → E2E → Deployment → Final audit, skipping phases per the
   mode/risk decision.

4. Honor every project rule in `.claude/rules/` and the backup rule
   (`16-agent-backup.md`) for any agent/skill/doc you create or modify.

If `$ARGUMENTS` is empty, ask the user for the requirement or Jira ticket before
starting Phase 1.
