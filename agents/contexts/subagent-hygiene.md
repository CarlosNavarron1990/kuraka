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
11. **Change text with an edit, never with a generator.** To change lines of an
    existing file use the edit tool (or one targeted replacement). Never
    regenerate the whole file to change a few lines, and never write a script
    that embeds the document's text to "apply" it — the script IS the rewrite,
    paid twice (estimator-v2 S04/S05: three agents wrote 46K–94K-char
    `apply_*.py` scripts to fill in answers or apply patches; one took 11 min
    to record 20 user answers).
12. **Your wall-clock is your output.** Measured: tool time is under 10% of a
    run; the rest is text you generate, ~100 tokens/s. Every document has a
    line budget set by the cycle size (`size:` in your prompt; your agent
    definition has the numbers) — say a thing once, in the artifact that owns
    it, and reference it by `§` elsewhere. Over budget = cut repetition, not
    rigour; if the content genuinely does not fit, say so in the report instead
    of silently exceeding it.
13. **Write in batches, gate once.** Create all the files of a batch first, then
    run lint + tests ONCE, then fix only what failed. Do not run the linter
    after each file, and do not write files through shell heredocs when a
    write tool exists (estimator-v2 S05: 38 turns to write 8 test files).
