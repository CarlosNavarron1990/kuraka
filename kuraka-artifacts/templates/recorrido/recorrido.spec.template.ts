// Recorrido <REQ> — generated from the RECORRIDO table of TEST-PLAN-<ticket>.md.
// One test.step per table row: action -> UI assertion -> backend re-fetch.
// Kuraka skill: recorrido-e2e. Never weaken an assertion to get green; a FAIL
// goes back to Phase 4 and THIS spec is re-run unchanged.
import { test, expect, type APIRequestContext, type Page } from '@playwright/test';

test.use({ trace: 'on', screenshot: 'on', video: 'retain-on-failure' });

const REQ = '<REQ>';
const API = process.env.RECORRIDO_API_URL ?? '<backend base url of the isolated stack>';

/** Re-fetch the backend effect of a step. Use the API, or a read-only DB helper. */
async function backend(request: APIRequestContext, path: string, token?: string) {
  const res = await request.get(`${API}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  return { status: res.status(), body: await res.json().catch(() => null) };
}

/** Route provenance: the URL actually hit must be the one the REQ names. */
function expectRoute(page: Page, expected: RegExp) {
  expect(page.url(), 'route provenance').toMatch(expected);
}

test(`recorrido ${REQ}`, async ({ page, request }, testInfo) => {
  await test.step('#1 AC-1 — <user action>', async () => {
    // action
    // await page.goto('/<route>');
    // await page.getByRole('button', { name: '<label>' }).click();
    // UI
    // await expect(page.getByText('<expected UI>')).toBeVisible();
    // expectRoute(page, /\/<route>$/);
    // backend effect (exact, per table)
    // const r = await backend(request, '/api/<endpoint>?<query>');
    // expect(r.status).toBe(200);
    // expect(r.body.<field>).toBe(<value>);
    // testInfo.annotations.push({ type: 'step-1', description: JSON.stringify(r.body) });
  });

  // ...one test.step per row. The LAST step proves the REQ outcome sentence.
});
