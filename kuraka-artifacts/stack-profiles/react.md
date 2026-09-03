# Stack Profile — TypeScript / React (Vite)

**Profile version**: 1
**Covers**: React 18–19 + Vite 5, TypeScript 5.x, package manager npm/pnpm
(often in an npm-workspaces monorepo). State via hooks / Zustand / Redux Toolkit.
**Status**: draft (seeded from kuraka-control retros — expand as cycles run)

---

## When this profile applies

The agent loads this profile when `stack.frontend.framework` in
`kuraka.config.yaml` equals `react` (or `react-vite`).

## Implementation order

1. Types / API client types.
2. API client / data hooks (`use{Resource}`).
3. State store (if any).
4. Components (presentational → container).
5. Routing wiring.

## Idiomatic file paths

Relative to `architecture.paths.frontend_root`.

| Artifact | Path |
|---|---|
| Component | `src/components/{Name}.tsx` |
| Feature | `src/features/{feature}/` |
| Hook | `src/hooks/use{Name}.ts` |
| API client | `src/api/{resource}.ts` |
| Types | `src/types/{name}.ts` |
| Design tokens | `src/styles/tokens.css` (or theme file) |

## Architecture invariants

- **Named type-imports, never framework-namespace types** — use
  `import type { KeyboardEvent, ReactNode } from 'react'`, not `React.KeyboardEvent`
  / `React.ReactNode`. A mechanical review-check (`grep 'React\.[A-Z]' changed .tsx`
  in type position → MINOR) killed this recurrence on first deploy in kuraka-control.
- **Every referenced `var(--x)` must be defined in the design tokens** — a
  component using an undefined custom property (e.g. `--gold`) renders wrong
  silently. Grep referenced tokens against definitions.
- **Render external date strings verbatim** — never `new Date(x)` to display a
  backend `YYYY-MM-DD` string (TZ off-by-one). Treat external `date` as `string`.
- **"Green" includes typecheck** — vitest transpiles per-file; require
  `tsc --noEmit` / `vue-tsc`-equivalent before declaring done.
- **One submit path per form** + an in-flight disabled state (no double-submit).

## Test patterns

- **Unit/component tests**: `vitest` + `@testing-library/react`; query by role/label.
- **E2E**: Playwright (see `e2e-tester`) — full-page snapshots for modal/overlay state;
  disambiguate empty-state from broken-state before closing.
- **File location**: `*.test.tsx` next to source.
- **Naming**: `should {action} when {condition}`.

## Naming and typing conventions

- Components `PascalCase`; hooks `useCamelCase`.
- Distinguish `prop?: T` (optional) from `prop: T | null` (nullable) in props types.
- No `any` in component props or API return types.

## Reference command surface

| Purpose | Typical command |
|---|---|
| Lint | `eslint .` (flat `eslint.config.js` for ESLint v9) |
| Format | `prettier --write .` |
| Typecheck | `tsc --noEmit` |
| Test | `vitest run` |
| Dev (smoke) | `vite` |

## Common pitfalls

- `React.X` namespace types instead of named `import type`.
- Undefined design tokens referenced in `var(--x)`.
- `new Date(externalDateString)` for display.
- Closing on green vitest without a graph typecheck.
- Vite dev-server port collisions across sibling projects — pin the port in dev docs.

## Anti-patterns flagged by reviewers

- Business logic in components instead of hooks.
- Effects without correct dependency arrays (stale closures).
- Fetch logic inline in components instead of an API client / data hook.
- Uncontrolled re-renders from new object/array literals in props.


## SPA navigation (RETRO-S12 Patch C, completed in RETRO-S9)
- Internal routes: use `<Link to=...>` / router-aware nav from `react-router-dom`.
  NEVER a raw `<a href>` for an in-app route — it forces a full page reload and
  drops client-side state. Raw `<a>` is only for true external links.

## Keyboard & dialog contracts (RETRO-S9, Phase 5 findings)
- A keyboard handler on a NESTED interactive element must `stopPropagation()`
  for every key an ancestor also handles — otherwise one keypress fires both
  (S9: ArrowUp nudged the node AND panned the canvas; the focused node moved
  the wrong way). `preventDefault()` alone does not stop the ancestor.
- `role="dialog"` is a contract, not a label: `aria-modal="true"`, move focus
  into the dialog on open, close on `Escape`, and keep the page behind
  non-tabbable. Cover Escape-close with a test.
