# AGENT_CONTEXT — UnslothX-

_Updated: 2026-11-17 02:50 · UnslothX- @ d46130a · turn 7 (Argon) · shared index: `../CONTEXT.md`_

The authoritative Argon ledger for `UnslothX-`. Two Argon loops run under `C:/Projectas`; the root
`CONTEXT.md` is a shared index, this file is mine.

> **Naming:** not `CONTEXT.md`. This repo already tracks a different `Context.md` (45 KB, the webhook /
> Labs notes), and Windows paths are case-insensitive — writing `CONTEXT.md` silently overwrote it on
> 2026-11-17. It was restored from `HEAD` (`git restore Context.md`) before anything was committed.

## State — what is true right now

- **Goal:** Argon loop on UnslothX- (backend hardening/perf + frontend Council). No terminal state.
- **Active item:** Council round 1 — **2 of 3 reviewer slots still blocked** (see Council). Fix #1 shipped.
- **Working:** backend imports and serves; `studio/frontend` builds (`vite` 13–17 s, typecheck green);
  the served build is reachable at `http://127.0.0.1:5100` from `run.py` + `studio/frontend/dist`.
- **Broken / unknown:** the desktop-secret health poll still costs ~3 ms of SQLite on the memo path
  (KDF removed). One known pre-existing test failure: Windows symlink privilege in
  `test_account_lifecycle.py`. Frontend: 29 pre-existing failures in the 60 tests that read
  `index.css` (documented whole-suite baseline is 54).
- **Tests:** backend 77 passed (desktop/secret suites) + 170 passed (account lifecycle/network, 1
  pre-existing); frontend 60-file CSS set 823 pass / 30 fail (29 pre-existing + 3 new passing).
- **Build:** `npx vite build` 13 s after the CSS change, exit 0.

## Decisions

- 2026-11-17 — **The ledger is `AGENT_CONTEXT.md`**, because `Context.md` is already tracked and the
  filesystem is case-insensitive. Never write a file here whose name differs only by case.
- 2026-11-17 — **Root `CONTEXT.md` is a shared index** (peer decision, adopted): I write only this
  file and append one short section to the index.
- 2026-11-17 — **Route promotion rejected** as a perf fix: no signal (median 5.57 → 5.53 ms, p95
  24.72 → 24.82, interleaved 3 rounds); FastAPI 0.141 keeps hot routes behind lazy `_IncludedRouter`.
- 2026-11-17 — **Desktop-secret memo is bound to the stored hash**, not a TTL: rotation and clearing
  invalidate by construction; rejections are never cached so a guesser still pays the KDF.
- 2026-11-17 — Council evidence lives in `.council/round-<n>/` and is **gitignored**.

## Perf ledger

| case | commit | value | unit | command |
|---|---|---|---|---|
| API workload, 13 endpoints, 15 iterations, idle host | `ad49d11` | **10.58 median / 49.11 p95** | ms | `python studio/backend/tests/perf_harness/bench_api.py --iterations 15` |
| Desktop-secret `GET /api/health` poll | working tree | **28.38 → 11.04** | ms | cache cleared per poll vs warm, median of 15 |
| Wrong desktop secret (guesser pays KDF) | working tree | 15.05 | ms | same harness |
| Frontend build (vite only) | `d46130a` | 13 | s | `npx vite build` |
| Boot: LCP mobile / desktop chat | `d46130a` | 292–396 / 392 | ms | CDP `timings.json` |
| Boot: LCP + CLS, hub desktop | `d46130a` | 1128 ms / 0.064 | — | CDP `timings.json` — the one screen with a shift |
| Boot: requests / transferred | `d46130a` | 144–182 / 1.18–1.30 | req / MB | CDP `timings.json` |
| Bundle | `d46130a` | 45 MB dist, 98 modulepreloads, 2.57 MB `browser-*.js` | — | `.council/round-1/bundle.txt` |

## Security ledger

| id | surface | issue | severity | status | test |
|---|---|---|---|---|---|
| SEC-1 | `Host` header | DNS rebinding, middleware off by default | medium | fixed | `test_trusted_hosts.py` |
| SEC-2 | canvas `?link=` | capability carried no account binding | medium | fixed | `test_canvas_link_auth.py` |
| SEC-3 | keyless `full` scope | per-host, not per-user | medium | **open** (warning text) | `test_keyless_api_access.py` |
| SEC-4 | `X-Desktop-Secret` on `/api/health`, `POST /api/desktop/shutdown` | unauth 100k PBKDF2 per request | low | **fixed this turn**: budget before KDF + validated-once memo | `test_main_middleware_and_desktop_secret.py`, `test_desktop_secret_validation_cache.py` |
| SEC-5 | two middlewares | `scope["path"]` without `root_path` | low | fixed | `test_remote_access_settings.py`, `test_main_middleware_and_desktop_secret.py` |
| SEC-6 | sandbox `reveal` | directory form skipped owner check | low | fixed | `test_sandbox_files_and_storage_roots.py` |
| SEC-7 | HTTP error details | host paths in 503/422 | low | fixed | `test_rag_extract_text.py` |
| SEC-8 | library upload name | `.`/`..`/control chars in label | low | fixed | `test_library_routes.py` |
| SEC-9 | canvas routes | `?link=` never minted in production | low | open by design | `test_canvas_link_auth.py` |

Residual, recorded not fixed: `client_ip` honours `CF-Connecting-IP` on a loopback peer, so a *local*
process can rotate the desktop-secret throttle key. Impact is a self-DoS on the user's own machine.

## Council — round 1 (evidence `.council/round-1/`)

Target chosen by "most recent edits": `studio/frontend`. Evidence captured from the **served build**
at 1440x900 and 390x844: 5 desktop screens + chat/library/hub mobile + d-chat/d-hub, `timings.json`,
`bundle.txt`, `consistency.md`, `a11y.json`, `notes.md`. `automated_axe: not installed` → a11y is
measured by computed styles + real Tab events; contrast sampled on 30 text elements (0 failures).

| reviewer | model | C | Load | Hier | States | A11y | Total |
|---|---|---|---|---|---|---|---|
| 2 | `deepseek-v4.1-flash` | 6 | 7 | 7 | 7 | 5 | **32/50** |
| 1 | `mimo-2.6-flash` | — | — | — | — | — | **not obtained** (provider `fetch failed` ×2) |
| 3 | `glm-5.3-flash` | — | — | — | — | — | **not obtained** (2-subagent cap, 3 attempts) |

**Provisional median = 32/50 — not a valid council median (1 of 3).** Do not record it as the round
score. Minimum dimension 5 (A11y).

Citations I verified myself (council step 5):
- ✅ `.sidebar-nav-btn` had `outline: none` and no shadow on focus (CDP, 12 rows) → **fixed, re-measured**.
- ✅ Blanket `button:focus, a:focus, summary:focus, [role=button]:focus { outline: none !important }`
  at `index.css:3778`.
- ✅ `--x-space-*` and `--x-icon-*` tokens have **0 uses** in `src` (dead layer from UI_AUDIT Task 1).
- ✅ `DownloadApprovalDialog` is a static import at `src/app/routes/__root.tsx:26`; `dist/index.html`
  emits **98** modulepreloads and 3 references to the 2.57 MB `browser-*.js`.
- ✅ `--x-focus-ring` used exactly once (inputs, `index.css:6705`).
- ⚠️ The reviewer's "11 of 14 tab stops show no ring" is partly a probe artifact: composer buttons do
  get a 1 px `--ring` shadow. The real, narrower defect is the nav rows + the missing outline fallback.

### Round 1 fixes

| # | Fix | Status | Evidence |
|---|---|---|---|
| 1 | Sidebar nav rows get the one keyboard ring (`--x-focus-ring`) + pointer-modality exemption | **shipped `d46130a`** | CDP: computed shadow `none` → `color(srgb 0.3458…) 0 0 0 1px, oklab(…)…`; 3 new tests fail without the rule; 60-file set 823/30 vs 821/32 stashed |
| 2 | Lazy-load `DownloadApprovalDialog` so the 2.45 MB browser chunk leaves the boot graph | queued | `__root.tsx:26`, `dist/index.html` 98 preloads |
| 3 | Give the Compute-backend select a placeholder instead of an empty box | queued | `features/settings/components/llama-backend-section.tsx:917`, `05-settings-dark.png` |
| 4 | Collapse arbitrary radii onto the declared scale (56×10px, 37×14px, …) | queued | `consistency.md`, `index.css:242-247` |
| 5 | One selected-pill treatment for Train's sub-nav (white pill vs Hub's accent) | queued | `studio-navigation.tsx:44`, `index.css:6862-6892` |

## Open threads

- [ ] **Council round 1 is incomplete**: reviewers 1 and 3 never returned. Re-dispatch both when a
  subagent slot frees, then aggregate the median properly.
- [ ] Fixes 2–5 above (fix 2 is +1 load point and is cheap: one `lazy()` + Suspense).
- [ ] SEC-3 warning text ("any local user").
- [ ] `--x-space-*` / `--x-icon-*` are dead tokens: adopt at call sites or delete. The panel named it;
  a dead token layer is worse than none because UI_AUDIT claims it exists.

## Next best action

1. Re-dispatch reviewers 1 and 3 (`mimo-2.6-flash`, `glm-5.3-flash`) and complete the round-1 median.
2. Ship fix #2 (lazy browser chunk) and re-measure LCP / modulepreload count.
3. Re-capture evidence into `.council/round-2/` and re-convene.

## Log — append only, newest last

### 2026-11-17 · turn 7
- Baselines: API workload 10.58 ms median / 49.11 p95 on an idle host (the 2026-11-13 "median miss"
  was host load). Route-promotion dead end measured and reverted.
- SEC-4: throttle was already in the tree while the audit said "skipped" → ledger corrected; added the
  validated-once memo (28.38 → 11.04 ms per desktop-secret health poll, wrong secret still 15.05 ms).
  `test_desktop_auth.py`'s missing `routes.telemetry` stub fixed (2 pre-existing failures cleared).
- Council round 1: evidence captured from the served build (`run.py` on 5100; note `run.py` moves port
  when 5099 is taken — the first capture photographed a stale uvicorn's 404 page, caught because
  `encodedBodySize: 22` and 7 DOM nodes is not this app).
- One reviewer returned 32/50; two dispatches failed on provider fetch / the account's 2-child cap.
  Shipped its top fix (nav focus ring) and verified it by CDP rather than trusting the score.
- Incident: wrote `CONTEXT.md` over the tracked `Context.md` (case-insensitive filesystem). Restored
  from `HEAD` before committing; ledger moved to this file.
- Commits: `a44b8f2` (SEC-4 + tests), `d46130a` (focus ring + tests).
