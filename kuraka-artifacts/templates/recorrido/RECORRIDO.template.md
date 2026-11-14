# RECORRIDO — <REQ>

- **Outcome sentence:** <the sentence declared in the solution outline>
- **Stack:** isolated `vp<id>` (validar-pr `stack.sh`, providers mocked) | dev stack from Phase 3.9 (`baseline_git_head` <sha>)
- **Spec:** `<e2e_root>/recorridos/<REQ>.spec.ts`
- **Command:** `npx playwright test <spec> --reporter=line,json > recorrido.log 2>&1; echo $? > recorrido.exit`
- **Exit code:** <n>
- **Run:** <n> (1 = first run; re-runs after Phase 4 fixes keep the SAME spec — list relaxed assertions vs run 1: none | …)

| # | AC | Action | UI assertion | Backend effect observed (literal) | Result | Evidence |
|---|----|--------|--------------|-----------------------------------|--------|----------|
| 1 | AC-1 | | | | PASS / FAIL / SKIPPED / UI-ONLY | `test-results/recorridos/<REQ>/…png`, trace.zip |

**Not exercised** (each with its reason): —

## Verdict: PASS — n/n pasos | PASS PARCIAL — n/m pasos | FAIL — paso #k
