# Subagent Hygiene (every pipeline agent)

Run-level contract that applies to every subagent, whatever its phase. Each item
exists because a cycle broke without it (origins in parentheses).

1. **You are a subagent.** Do not invoke the `kuraka` skill / `/kuraka`, do not
   spawn agents, do not run another phase. If you think more work is needed, say
   so in your report; the orchestrator decides. (guai-home: 9/11 project appends
   had to restate this.)
2. **Git is read-only for review / verify agents** (`code-reviewer`,
   `security-reviewer`, `architect-reviewer`, `migration-reviewer`,
   `deployment-verifier`, `e2e-tester`, `final-auditor`): only `git status`,
   `diff`, `log`, `show`, `blame`, `ls-files`, `rev-parse`, `merge-base`. Never
   `merge`, `rebase`, `reset`, `checkout`/`switch`, `stash`, `commit`, `push`,
   `clean` — a reviewer once started a real `git merge` in a consumer tree.
   Implementers mutate git only as their own agent definition allows.
3. **Scratch work goes to YOUR scratchpad** (the session scratchpad dir, or a
   per-agent subdir such as `$TMPDIR/kuraka-<agent>-<REQ>/`). Never create
   `scratchpad/`, `tmp/` or probe scripts in the repo root, and never reuse
   another agent's scratch file by name (editorial: one agent overwrote another's
   guard script; another left `scratchpad/` at the repo root).
4. **Leave `git status` as you found it** except for the files your task
   declares. Before reporting, run `git status --porcelain` and list any extra
   path you created; delete your own litter.
5. **Never finish with a background job running.** Wait for it (read its output
   file and exit code) or kill it and say so. A run that ends while its test
   suite still runs reports a result nobody measured.
6. **Never write text shaped like a system / task notification** ("task
   completed", `<task-notification>`, "Background command finished…"). While
   waiting on a background command, read its output file and exit code — do
   not narrate an invented completion (editorial LL-028).
7. **The declared output exists before you report it.** `test -s <path>` on
   every file your report names as produced; a missing/empty file means the run
   is NOT done.
8. **Numbers you report are measured, not remembered** — gate exit codes are
   literal (`MAKE_TEST_EXIT=<n>` or `GATE NO EJECUTADO`), and token/tool-use
   counts are never self-reported (`output-schemas.md` §Universal).
9. **Turn ceiling.** The harness caps a run's turns (`maxTurns`). Work in small
   batches, write your report file incrementally from the start, and when you
   are ~80% through the budget run the gate and hand in what remains as an
   explicit "pending" list — a run cut off at the limit returns nothing
   (editorial C06/C09, guai-home S4: 3 runs). See `kuraka-policies`
   §Turn ceiling.
10. **One test runner per host.** Do not start a suite / mutation / E2E run
    while another is running on the same host; a gate read under that load is
    void. See `rules/17` T7 (one runner per host).
