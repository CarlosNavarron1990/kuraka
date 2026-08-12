# Kuraka — Evals Harness

> Tests of agent **behavior**, not structure. Complement to `tests/kuraka/`
> (the structural harness mounted into consumers), which only validates
> frontmatter, model routing, and reference integrity.

## Why this exists

Structural tests catch typos and missing fields. They cannot tell you whether
the `code-reviewer` actually flags a planted bug, whether the `po-analyst`
asks for clarification on an ambiguous requirement, or whether a refactor of
a prompt silently degrades detection rate.

This harness fills that gap by running each agent against fixtures with known
expected outputs and measuring detection rate, false-positive rate, tokens,
and latency.

## Status

**Skeleton only.** Populated incrementally during Fase 7 of the
adaptive-framework migration. See `../02-MIGRACION-FRAMEWORK.md`.

The directory is created in Fase 1 so a baseline can be captured before
Fase 3 (decoupling agents from sie_v2). Without a pre-refactor baseline,
regressions introduced during Fase 3 are invisible.

## Layout

```
evals/
├── README.md           # this file
├── runner.py           # (Fase 7) executes evals, emits report
├── fixtures/           # one subdir per scenario
│   └── {type}-{NNN}-{slug}/
└── reports/            # (Fase 7) timestamped JSON reports
```

## Fixture contract

Each fixture is a directory under `evals/fixtures/{scenario-id}/` with:

- `README.md` — what is planted, which agent should detect it, why it matters.
- `before/` — code/files in their original state.
- `after/` — code/files with the planted situation (bug, missing test,
  ambiguous requirement, etc.).
- `expected.json` — the structured findings the agent must produce, with
  severity, file:line, and a snippet of the description that must match
  (substring or regex).
- `agent.txt` — single-line agent name to invoke (e.g. `code-reviewer`).

The runner invokes the agent over `after/`, parses its output against the
agent's output schema, and compares findings against `expected.json`.

## Metrics per fixture

- `detection` — true if every expected finding matched.
- `false_positives` — count of findings not in `expected.json`.
- `total_tokens`
- `tool_uses`
- `duration_ms`

## Running (once `runner.py` exists)

```bash
python3 evals/runner.py                       # run all fixtures
python3 evals/runner.py plant-bug-001         # run one
python3 evals/runner.py --baseline            # write baseline report
python3 evals/runner.py --compare reports/baseline-2026-04-25.json
```

## Contributing a fixture

1. Pick the agent and the situation type.
2. Create `fixtures/{type}-{NNN}-{slug}/` with the files above.
3. Plant the situation in `after/` minimally — the smaller the diff, the
   sharper the signal.
4. Document `expected.json` with the literal strings the agent must emit.
5. Run the fixture; iterate until it passes consistently.

## `runs/` — reportes de `/kuraka-eval` (live-repo, no fixtures)

`runs/EVAL-<agente>-<slug>-<YYYYMMDD>.md` son las corridas del comando
`/kuraka-eval`: el agente ejecutado en sandbox contra un **proyecto real**
(no un fixture), sus afirmaciones verificadas por muestreo, y los gaps de
definición con id estable. Cada corrida se compara contra la anterior del
mismo par agente+target (CERRADO / REAPARECIDO / PERSISTENTE / NUEVO →
veredicto MEJORÓ/IGUAL/EMPEORÓ) — así se mide si un ajuste al repo central
realmente mejoró al agente antes de distribuirlo vía `kuraka update`/`mount`.
Frontmatter incluye `suite_version` para agrupar resultados por versión,
igual que los retros. Complementa a los fixtures: fixtures = señal nítida y
repetible; runs = realidad desordenada de un repo vivo.

## Out of scope

- LLM determinism is not assumed. The runner is expected to run each fixture
  N times and report detection rate, not pass/fail per single run.
- Performance regression alerts; we record timings but don't gate on them.
- Cross-agent end-to-end cycles. That's a future integration harness, not
  these unit-level evals.

## First fixtures (Fase 7 backlog)

| ID | Agent | Plants | Expects |
|---|---|---|---|
| `plant-bug-001` | `code-reviewer` | Cache invalidation that misses sub-keys (LL-002 pattern) | BLOCKER finding referencing the namespace |
| `plant-bug-002` | `security-reviewer` | Raw SQL with string interpolation | CRITICAL finding for SQL injection |
| `missing-test-001` | `test-engineer` | New endpoint without tests | New test file under `tests/` covering happy path + error |
| `ambiguous-req-001` | `po-analyst` | Requirement with vague scope | Clarification question, not a fabricated REQ |
| `wrong-layer-001` | `code-reviewer` or `architect-reviewer` | Business logic in HTTP endpoint | BLOCKER finding for layer violation |
