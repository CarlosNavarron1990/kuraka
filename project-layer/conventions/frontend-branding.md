# Frontend branding and styling

## Context (auto-extracted from the project)

Everything below is **derived from the code**, because there is no design
source of truth to derive it from.

Confidence: **HIGH** on the code-derived facts; the absence of a design source
is itself a verified finding.

### `<TODO: confirm with team>` — there is NO design source of truth

Searched the whole workspace: **no `.pen` file, no Figma URL, no design
system package, no token file, no style guide document, no Storybook.** The
visual language exists only as ~71 hand-written per-component CSS files.

This has a concrete consequence for Kuraka cycles: **a UI story cannot cite a
design reference, so "matches the design" is not a verifiable acceptance
criterion here.** Until a source of truth exists, UI acceptance criteria must
either (a) cite an existing component in this codebase as the visual reference,
or (b) be approved from a screenshot at the gate.

Resolve one of:
1. Create a design file (Pencil `.pen` / Figma) and record its location here.
2. Declare an existing page the canonical reference and name it here.
3. Extract the repeated CSS custom properties into a real token layer (see
   anti-pattern 1) and treat that file as the source of truth.

## Rules

### Plain per-component CSS. No Tailwind, no CSS framework.

- **71 `.css` files, 2 `.scss`.** `angular.json` sets the `scss` schematic and
  `inlineStyleLanguage: "scss"`, but only the two globals are SCSS —
  `src/styles.scss` (20 lines) and `src/app/app.scss` (**0 bytes**). Every
  component style is plain `.css`.
- **Zero Tailwind.** No `tailwind` in `package.json`, `angular.json` or `src/`;
  no `postcss.config`; no utility classes. Class names are hand-written and
  BEM-ish: `.ps-form`, `.photo-row`, `.ps-btn ps-btn-secondary`.
- The unit of styling is the **`.ts` + `.html` + `.css` triplet** next to the
  component. `styleUrls: [...]` (array form) is used 69 times; the singular
  `styleUrl` never.
- Brand green is `#027e59` (`src/index.html:12`, `theme-color`).
- `@fullcalendar/common/main.css` is registered as a global style in
  `angular.json:34-36`.

### Fonts: Google Fonts, loaded in `index.html`

`src/index.html:16` loads, with `preconnect`:

- **Bricolage Grotesque** — weights 600/700/800, variable `opsz`
- **Inter** — weights 400/500/600

Caveat worth knowing: `src/styles.scss:17` sets `font-family: system-ui, …` on
`body`, so the loaded fonts apply **only where a component's own CSS asks for
them**. Do not assume a new component inherits Bricolage or Inter — set it
explicitly.

### Dark theme: a `body.dark-theme` class

- Toggled in exactly one place: `src/app/core/services/theme.service.ts:9-14`,
  an `effect()` that adds/removes the class on `<body>`.
- Persisted to `localStorage['petsuite_theme']`; initial value from
  `prefers-color-scheme`.
- **55 of 71 component CSS files carry their own `body.dark-theme .x { … }`
  overrides.**

**Rule: any new component with visible surface must ship its
`body.dark-theme` overrides in the same CSS file.** There is no automatic
inheritance and no token indirection to do it for you — a component without
overrides simply renders light-on-light in dark mode.

### There are no global design tokens

`src/styles.scss` is 20 lines: a reset, `box-sizing`, a `font-family`, and the
`body.dark-theme` rule. **There is no `:root` block anywhere in `src/`.**

Tokens *are* used — but each component re-declares them locally. The same
custom-property names are copy-pasted across 12+ separate `.css` files:

| Token | Files declaring it |
|---|---|
| `--white` | 17 |
| `--primary`, `--red`, `--gray-900/-700/-600/-500/-200/-100/-50` | 12 each |
| `--primary-dark`, `--transition` | 11 |
| `--green` | 8 |
| `--blue` | 7 |
| `--teal-500/-700/-900/-050` | 5 |
| `--muted`, `--purple` | fewer |

**Rule for now: reuse the existing token *names* so a future extraction is
mechanical.** Do not invent a new name for a colour that already has one. Do
not add a `:root` block for one component — that is the extraction story, not
a drive-by.

## Gotcha: `src/environments/*.ts` is dead code

This one has bitten people, so it is a rule, not a note.

- `src/environments/environment.ts` and `environment.prod.ts` export
  `{ production, apiUrl, appName, version }`.
- `angular.json:39-44` even wires up the production `fileReplacements` for them.
- **Nothing in `src/` imports from `environments/environment`. Zero files.**

The real configuration is `src/app/core/config/app-settings.ts`, whose
`APP_CONFIG.API_BASE_URL` is provided as the `API_BASE_URL` injection token in
`app.config.ts:111-114` and consumed in ~79 places.

Worse: `environment.ts:3` says `http://demo.localhost:8080` while
`app-settings.ts:4` hardcodes `https://api.petsuite.pe`. **So the value that
looks like the dev config is inert, and local dev points at production unless
you edit `app-settings.ts`.**

Rules:
- **To point the app at a local backend, edit `app-settings.ts`** — and do not
  commit that edit.
- Never add a new setting to `src/environments/`; it will silently do nothing.
- Other centralised settings live in the same file: request timeout 30s,
  `WHATSAPP_SUPPORT`, and `TURNSTILE_SITE_KEY` (`app-settings.ts:12`) — a
  public Cloudflare Turnstile site key, correctly commented as such. It is not
  a secret.

## Examples (sampled from this codebase)

Component styling triplet, the pattern to follow:
`src/app/features/pets/ui/pet-form/pet-form.component.{ts,html,css}` — classes
`.ps-form`, `.photo-row`, `.ps-btn ps-btn-secondary`, with `body.dark-theme`
overrides in the CSS.

The single theme switch:

```ts
// src/app/core/services/theme.service.ts:10-13 — the ONLY .ts reference to 'dark-theme'
effect(() => {
  document.body.classList.toggle('dark-theme', this.isDark());
  localStorage.setItem('petsuite_theme', this.isDark() ? 'dark' : 'light');
});
```

## Anti-patterns detected in the codebase

Not blocking; flag for a future cleanup story.

1. **Design tokens re-declared in 12+ component CSS files** instead of a single
   `:root` block. This is the largest styling debt and the obvious first
   refactor: extracting them into `styles.scss` would also give the project the
   design source of truth it currently lacks.
2. **Giant stylesheets** — `register-wizard.page.css` 932 LOC,
   `medical-record-detail.page.css` 757, `layout.component.css` 700,
   `sales.page.css` 644, `payment-modal.component.css` 624,
   `login.component.css` 676, `staff-modal.component.css` 553. All well over
   `max_frontend_file_loc: 400`.
3. **Template control flow is split by vintage** — `*ngIf` 624 occurrences
   across 53/73 HTML files vs `@if` 139 across 19/73; `*ngFor` 95 vs `@for` 16.
   Newer features (superadmin, payments, cash-register, register-wizard,
   upgrade-plan) use the new syntax; older ones (pets, clients, staff,
   medical-records, sales) do not. Because of `*ngIf`, `CommonModule` is
   imported almost everywhere rather than the narrower `NgIf`/`NgFor`.
   **Use `@if`/`@for` in new templates.**
4. **Template-driven forms dominate** (`FormsModule` in 44 files vs
   `ReactiveFormsModule`/`FormBuilder` in 14), often with a bare
   `form: any = {…}` as the model (`pet-form.component.ts:20`).
5. **Native `alert()` for validation UX in 14 places** despite a real
   `ToastService` — e.g. `pet-form.component.ts:69,74`.
6. **Direct DOM access from components** —
   `document.querySelector('input[type="file"]')` in `removePhoto()`
   (`pet-form.component.ts:92`) instead of `viewChild`/`ElementRef`.
7. **Hardcoded external URLs** — `https://wa.me/` assembled in four separate
   pages (`account-blocked.page.ts:96`, `dashboard.page.ts:197`,
   `subscription-payment.page.ts:85`, `upgrade-plan.page.ts:93`), though the
   number itself is centralised as `WHATSAPP_SUPPORT`. Also the hostname check
   `window.location.hostname === 'admin.petsuite.pe'` in `app.config.ts:25` and
   the Turnstile script tag in `index.html:17`.
8. **`src/app/app.scss` is a 0-byte file** referenced by nothing, and
   `README.md` is unmodified Angular CLI output.
9. **Only 2 `TODO`/`FIXME` markers in the whole frontend** — debt here is
   undocumented rather than tracked.
