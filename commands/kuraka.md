---
description: "Kuraka orchestrator: drive a full requirement through the gated multi-phase multi-agent dev workflow (PO analysis → story refinement → test planning → architect+schema-freeze → implementation → code/security review → tests/E2E/deploy-verify → final audit), scaling phases to the change's risk. The main entry point for any feature or change."
argument-hint: "<requerimiento / ticket Jira / alcance> [— modo normal|reducido|lite|ultra-ahorro]"
---

Act as the **Kuraka** development orchestrator for the requirement described in the arguments below.

Arguments (requirement / Jira ticket / scope): $ARGUMENTS

Steps:

0. **Ultra Ahorro short-circuit — decide this BEFORE reading anything else.**
   If `$ARGUMENTS` says `--modo ultra-ahorro` (or `modo ultra ahorro`), or
   `kuraka.config.yaml` sets `workflow.default_mode: ultra-ahorro` and the
   arguments name no other mode, then invoke the `kuraka-ahorro` skill with the
   requirement and follow it instead of this command. Do NOT read step 1's files
   first: loading the pipeline is exactly the cost that mode exists to avoid.
   The skill itself decides whether the task is eligible and says so if it is not.

1. Read the orchestrator definition and its companion files, in this order:
   - `.claude/skills/kuraka.md` — main orchestrator (8-phase multi-agent workflow, plus subphases)
   - `.claude/skills/kuraka-modes.md` — how to scale the pipeline to the change's risk
   - `.claude/skills/kuraka-policies.md` — execution policies and gates

2. Apply rule `.claude/rules/17-kuraka-token-optimizations.md` BEFORE launching any
   subagent: evaluate the change surface (Rule 0), pick the minimum set of phases,
   announce the proposed pipeline with per-phase justification and the number of
   planned agent invocations (the cycle's budget), and request user confirmation
   before invoking the first subagent.

   If `$ARGUMENTS` already names a mode ("modo normal", "lite", "reducido",
   "ultra-ahorro"), that choice is BINDING: run it without re-proposing a cheaper
   one. The only exception is a request to run Lite or Ultra Ahorro on a change
   that breaks its safety criteria (migration / contract / auth / integration) —
   say once which criterion fails, then proceed as the user decides. See
   `kuraka.md` §The user can FIX the mode.

3. Drive the workflow exactly as `kuraka.md` specifies: PO analysis → Story
   refinement → Test planning → Architect review → Implementation → Code review →
   Security → Tests → E2E → Deployment → Final audit, skipping phases per the
   mode/risk decision.

   **Agent binding (HARD):** every phase invocation uses the exact mapped
   `subagent_type` (never `general-purpose`/`Explore`/`Plan`/`fork`, never a
   `model:` override); if the agent is missing, STOP and point to
   `kuraka-doctor` / `kuraka-mount --update` — see `kuraka.md` §Agent binding.

4. Honor every project rule in `.claude/rules/` and the backup rule
   (`16-agent-backup.md`) for any agent/skill/doc you create or modify.

If `$ARGUMENTS` is empty, ask the user for the requirement or Jira ticket before
starting Phase 1.
