---
name: kuraka-ahorro
description: "Ultra Ahorro — implement ONE bounded, low-risk task directly in the main session: zero subagents, focused verification, one short cycle record. Use ONLY when the user selected the mode (`/kuraka-ahorro`, `/kuraka … --modo ultra-ahorro`) or `workflow.default_mode: ultra-ahorro`; never as a shortcut out of a delegated cycle."
argument-hint: "<tarea local acotada>"
model: sonnet
effort: medium
disallowed-tools: Task
---

# Ultra Ahorro

One bounded, low-risk task. The main session analyses, implements and verifies
it. **Zero subagents.** This is the selected-mode exception to Kuraka's delegated
phase discipline: the same executor implements and reviews, so independent review
is *not* provided — never claim a delegated cycle's coverage for it.

Entry: `/kuraka-ahorro <tarea>`, `/kuraka <tarea> --modo ultra-ahorro`, or
`workflow.default_mode: ultra-ahorro`. The task is the text after the entry; ask
for it if missing. A mode the user already selected is never re-confirmed.

*(Claude Code: the harness carries this — `disallowed-tools: Task` removes
delegation from the tool pool while the skill is active, `model: sonnet` +
`effort: medium` fix the cost profile, and the `orchestrator_guard` hook grants
the main session write access to exactly the files declared in §2. Do not spend
turns policing any of it. This is a workflow contract, not a sandbox: writes
through shell commands still need the final diff review in §4.)*

## 1. Decide whether the task qualifies

Read `kuraka.config.yaml` and the project instructions that already apply. No
config → say the project needs onboarding (`/amauta`) and stop; do not launch it
silently. `workflow.ultra_ahorro.enabled: false` means the project opted out: say
so and ask which mode to run. Then read the affected files and one or two
reference patterns.

Do **not** preload `kuraka.md`, `kuraka-modes.md`, `kuraka-policies.md`,
`implement-story`, the story set or `rules/17`: not paying for them is the point
of the mode. Instructions already in context keep applying — a short entry erases
nothing. Flag a real conflict instead of resolving it silently.

Eligible: one implementation layer plus its tests, behaviour you can state up
front, and **none** of — schema or migration, API contract or new endpoint,
auth/permissions, crypto or sensitive data, external integration, deploy,
dependency or infra config, shared global state, cross-cutting refactor.

Qualifying examples: local copy and styles, a component's visual states, a
bounded pure-calculation bug with a regression test, localized documentation. A
pricing, permissions or settlement function is **not** innocuous for being short.
A whole new screen is out. Unknown risk is a reason to investigate, not to
proceed — a small diff never proves eligibility by itself.

Reevaluate scope above **5 implementation files or 200 changed lines** (adds +
deletes) — or `workflow.ultra_ahorro.max_source_files` / `max_changed_lines`
when the project sets them. Tests and process artifacts count separately and may
never be used to hide implementation code. A safe mechanical replacement that
crosses the threshold needs reevaluation, not automatic rejection.

If the task does not qualify, name the criterion that fails, say what a regular
mode would add, and ask which one to run. Do not implement the prohibited part
while waiting, and do not launch a costlier pipeline on your own.

## 2. Declare the scope before editing

Announce in one line: `Ultra Ahorro · 0 subagentes · alcance: <archivos>`, the
verification you will run, and that review is by the same executor.

Record pre-existing work and preserve it — the cycle's diff is measured against
that baseline, never indiscriminately against HEAD. Never reset, check out or
stash to prepare the mode:

```bash
git status --porcelain
```

Scope files must be clean at this point. If one already carries uncommitted work,
say so and let the user decide whether that work belongs to this cycle; do not
absorb it silently. Unrelated dirty files stay untouched.

Then declare the scope. **On Claude Code** that is a file you write to
`.claude/ultra-ahorro/<cycle-id>.json`, with `<cycle-id>` =
`REQ-<YYYYMMDD>-AHORRO-<nn>` (sequential within the day); on a platform without
the guard hook the bundled helper below records the same thing instead, and you
do not hand-write this file:

```json
{
  "schema_version": 1,
  "mode": "ultra-ahorro",
  "cycle_id": "REQ-20260914-AHORRO-01",
  "status": "active",
  "objective": "Corregir el espaciado del formulario de clientes",
  "allowed_files": ["src/components/ClientForm.vue", "tests/ClientForm.spec.ts"],
  "baseline_dirty": []
}
```

`allowed_files` are project-relative paths — the complete set you may write,
tests included. Declaring a directory, a glob, `..` or an absolute path is
invalid. `baseline_dirty` lists files already modified before the cycle. Widening
the scope means updating this file *and* re-checking §1; if the new surface
breaks an eligibility criterion, leave the mode instead.

*(Claude Code: this file is the guard's authorization. The first write under a
code root binds the cycle to this session, and another session cannot use it.
A `status` other than `active` revokes the exception immediately.)*
<!-- kuraka:discipline:ultra-ahorro-evidence -->

## 3. Implement

Edit directly. No `po-analyst`, `story-refiner`, `backend-developer`,
`frontend-developer`, reviewer, `test-engineer` or `final-auditor`, and no
exploration agent — needing one is a transition to another mode, announced as
such, not something to slip in.

Write no separate REQ, story or test-plan document. Add a regression test when it
gives real evidence about a behavioural bug; do not invent trivial tests for copy
or styling just to fill a template.

## 4. Verify

Run the project's canonical commands for the surface you touched (`test_cmd`,
`lint_cmd`, `typecheck_cmd` from config), scoped to the affected files. Group the
checks at the end of a coherent batch of edits; repeat one only after a change
that can affect its result, or while a failure is open. Gate commands are never
piped — the exit code is the verdict.

Two unsuccessful attempts at the same failure (or
`workflow.ultra_ahorro.max_fix_attempts`) trigger reevaluation: report it and
ask. Do not loop, do not restart the cycle to hide the cost, and do not delegate
your way out. If a relevant check is unavailable, close as incomplete or hand
over the blocker — never declare PASS for lack of tooling.

Review the final diff yourself, against the §2 baseline:

```bash
git status --porcelain
git diff -- <allowed_files>
```

Any change outside `allowed_files` blocks a PASS close: explain it, and revert it
only if you caused it. Never erase the user's work to satisfy the scope check.

## 5. Close

One narrative record, no more: `RETRO-<cycle-id>.md` under
`${architecture.paths.docs_process_root}/agent-retrospectives/` with objective,
scope, what changed, evidence (each command and its exit code), what is pending,
and `## Confidence: HIGH|MEDIUM|LOW` as the final line, one value.

Write the matching telemetry to `agent-telemetry/<cycle-id>-telemetry.json`:
`mode: "ultra-ahorro"`, `subagents: 0`, and a single run with `"phase": "U"`,
`"agent": "claude-main"`, `"status": "ok"`, the timestamps and the artifacts.
Report what you actually know: the `<usage>` block if the harness gave you one,
otherwise `null` with `"usage_source": "unavailable"`. Never write `0` for an
unknown, and never convert local tokens into a percentage of a weekly quota.

Set `status` to `closed` in the scope file, then run the backup once:

```bash
python3 "$KURAKA_VAULT/kuraka-backup.py" <project-root>
```

No commit, push, deployment or framework update is implied by this mode.

## 6. Leaving the mode

For a blocker, a scope expansion or a cancellation: set `status` to `aborted`
with a reason in the scope file, keep every edit, and report what remains plus
the suggested next step. State the transition explicitly — an escalation the user
did not choose is a cost they did not agree to.

Recommend a fresh session when the task changes; if context grows large — the
project may set an advisory `workflow.ultra_ahorro.context_warning_tokens` —
leave a short checkpoint first. Report the figure only if the harness actually
gave you one; otherwise say `unknown` rather than estimating. Never run `/clear`
or compact on your own.
