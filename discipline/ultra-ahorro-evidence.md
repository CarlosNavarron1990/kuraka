**Manual evidence protocol — this platform, which has no Kuraka guard hook:**

The Claude-only notes above do not apply here: no harness key removes delegation
(the zero-subagent rule is yours to keep), and nothing reads a hand-written scope
declaration — do **not** write that JSON file. Use the helper bundled with this
skill instead: `start` records the same scope, plus a real baseline. It needs Git
and Python 3, adds no third-party dependency and changes no permission. Replace
the example paths with the real scope, and resolve
`architecture.paths.docs_process_root` from config (normally `docs/process`).

```sh
python3 .claude/skills/kuraka-ahorro/scripts/cycle.py --project . start --docs-root docs/process --objective "Local task" --files src/component.ts tests/component.test.ts
```

Keep the returned cycle ID for every later call. The helper records the current
working files as the baseline; it never resets, checks out or stashes. Each
invocation reuses only that cycle, a new user task starts a new one, and two
cycles must not run in the same worktree: independent edits invalidate the scope
and check evidence.

```sh
python3 .claude/skills/kuraka-ahorro/scripts/cycle.py --project . check --cycle <id> -- npm test -- --run tests/component.test.ts
python3 .claude/skills/kuraka-ahorro/scripts/cycle.py --project . status --cycle <id>
```

`check` runs the argument vector in the project root and records its exit status
plus a file fingerprint. Use `-- sh -c 'command'` only when that exact command is
the appropriate and authorized one. Full output stays in the cycle log; read it
when the returned tail is not enough. Rerun any check whose evidence went stale
after an edit. A failing required check is never waived.

Baseline copies of the scope files live in `.claude/ultra-ahorro/<id>/baseline/`;
compare against them, not only against HEAD. The helper detects changes outside
the declared file list, but it cannot infer semantic risk, review quality,
delegation activity or ignored tool side effects — its success alone is not
proof that the task is done.

```sh
python3 .claude/skills/kuraka-ahorro/scripts/cycle.py --project . close --cycle <id> --summary "What changed and why" --confidence HIGH
```

Closure refuses out-of-scope changes, failed checks and stale check evidence. It
writes the RETRO and the telemetry file itself, so do not hand-write them on
these platforms. For a blocker, a scope expansion or an explicit cancellation use
`abort --cycle <id> --reason "reason"`; it keeps the state and every edit. Never
erase user work to satisfy the scope check.
