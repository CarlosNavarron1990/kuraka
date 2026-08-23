**Manual output validation (platforms without the Kuraka SubagentStop hook):**
before returning, run the `verify-output` skill against your produced output —
read your section of `.claude/agents/contexts/output-schemas.md`, check every
required section is present, at the right path, with the `## Confidence:
HIGH / MEDIUM / LOW` line at the end. First failure: fix silently and
re-validate. Second failure: return an explicit `VALIDATION_FAILED` marker
listing the missing sections so the orchestrator can decide instead of passing
invalid output downstream.
