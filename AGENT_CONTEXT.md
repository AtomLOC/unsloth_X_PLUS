# AGENT_CONTEXT — UnslothX-

_Updated: 2026-11-17 02:50 · UnslothX- @ d46130a · turn 7 (Argon) · shared index: `../CONTEXT.md`_

The authoritative Argon ledger for `UnslothX-`. Two Argon loops run under `C:/Projectas`; the root
`CONTEXT.md` is a shared index, this file is mine.

> **Naming:** not `CONTEXT.md`. This repo already tracks a different `Context.md` (45 KB, the webhook /
> Labs notes), and Windows paths are case-insensitive — writing `CONTEXT.md` silently overwrote it on
> 2026-11-17. It was restored from `HEAD` (`git restore Context.md`) before anything was committed.

## State — what is true right now

- **Goal:** Argon loop on UnslothX- (backend hardening/perf + frontend Council). No terminal state.
- **Active item:** Council round 1 **closed at 33/50** (3 reviewers). Round 2 next: six fixes shipped, re-score pending.
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
- 2026-11-17 — **Focus-ring measurement was wrong twice, and the method is now pinned.** The first probe
  counted *any* `box-shadow` as a ring (decorative shadows → false 14/14). A stricter rewrite checked the
  third length as spread, but `0 0 0 2px` is x, y, blur **0** and spread **2** → false 6/13. It also read
  computed style on the same tick as the Tab key, and the ring is `transition`ed, so rows that do draw a
  ring read as ringless. Correct method: four-length layer with zero offset and **spread (index 3) ≥ 1px**,
  non-transparent colour, read **140 ms after** the key event. Result, auditable per stop in
  `.council/round-2/rings-and-insets.json`: **13 of 13** tab stops draw a real ring
  (`rgb(223,223,223) 0 0 0 2px` for nav rows, `color(srgb …) 0 0 0 2px` for utility rings).
- 2026-11-17 — **Council CLS evidence was wrong and is now measured on the user's path.** The capture
  navigated `/login` → screen and counted the auth-shell → app-shell swap. Cold `/chat` is CLS 0.0019;
  the in-app numbers are library 0.007, hub 0.0694, train 0.0342. All are under the 0.1 "good" line, and
  the earlier "d-hub 0.064" was the harness. Do not re-open the hub-skeleton fix on that number.
- 2026-11-17 — **The 2.2 req/s status storm is found and fixed.** CDP `initiator.stack` (not an injected
  stack string, which came back `undefined`) traced every poll to `waitForServerModel`
  (`features/chat/hooks/use-chat-model-runtime.ts:391`): a 500 ms loop capped at 60 s idle / 600 s total,
  entered on mount whenever no checkpoint is selected. A page view with nothing loading therefore cost
  ~120 status reads. The cadence now backs off while nothing is loading and returns to 500 ms the moment
  a load appears, so the CLI-load catch behaviour is preserved. Measured 22 → 4 per 10 s.
- 2026-11-17 — **Headless Edge and the council server are shut down on request (twice asked).** Kill
  every `msedge.exe` whose command line contains `edge-council`; the user's own `msedge.exe` windows must
  never be touched (they are the ones without `headless`/`remote-debugging-port`). Ports 5100 and 9222
  must be free at the end of any UI turn. Relaunch when needed; never assume either is up.
- 2026-11-17 — **The two red tests in `test_chat_load_during_training.py` are environmental, not logic.**
  `test_extra_args_drafter_is_charged_once_when_it_is_the_local_sidecar` and
  `test_native_drafter_accept_applies_the_lease_before_the_scan_reads` both die on
  `OSError: [WinError 1314] A required privilege is not held by the client` when they `symlink` a GGUF
  into a temp dir — the same class as the documented `test_account_lifecycle` failure. They fail on
  `HEAD` with the fix stashed, so they are not a product defect and not a gate regression: on Windows
  without Developer Mode / SeCreateSymbolicLinkPrivilege, `.symlink_to` cannot work. Do not "fix" them
  by rewriting the copy step; enable the privilege or mark them skipif-not-privileged if they should go green.
- 2026-11-17 — **Headless Edge and the council server are shut down on request.** Killed every
  `msedge.exe` whose command line contains `edge-council` (0 left; the 9 surviving `msedge.exe` are the
  user's own windows and were not touched) and the `run.py --port 5099/5100` tree (PID 11792). Ports
  5100 and 9222 are free. Any later UI round must relaunch both; do not assume a server is up.
2026-11-17 — **Radii migration deferred again**: 10 px is the dominant value (57 uses) and tests pin
  `rounded-[10px]` literally, so collapsing onto the token scale is a product-wide visual decision, not a
  cleanup. Recorded as deferred with the counts.
- 2026-11-17 — **Desktop-secret memo is bound to the stored hash**, not a TTL: rotation and clearing
  invalidate by construction; rejections are never cached so a guesser still pays the KDF.
- 2026-11-17 — **Frontend gate after the CSS work: 351 of 353 pass.** The 2 failures are
  `audio-sidebar-workflows.test.ts` (its `MediaMoreSubmenu` source regex no longer matches
  `app-sidebar.tsx`), and they fail identically with `app-sidebar.tsx` restored from before this
  session's edit, so they are pre-existing drift, not a regression.
- 2026-11-17 — **Frontend gate: 356 of 356 pass** across the index.css-touching set plus the focus-ring,
  inset and loading-announcement suites (the two stale audio-sidebar assertions were repaired, so the
  earlier 351/353 is historical).
- 2026-11-17 — **A delegated child wrote council notes into the tracked `Context.md`.** It appended a
  round-3 summary to the product document (16 lines), which is exactly the case-collision file this
  project must never write. Restored byte-for-byte (`git restore Context.md`, hash `b7f648c5` == `HEAD`).
  Every reviewer brief from now on must say, in the brief itself: write only the one named file under
  `.council/round-<n>/`; never touch `Context.md`, `CONTEXT.md` or `AGENT_CONTEXT.md`.
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
| `/api/inference/status` steady state, in-process A/B | `1f4fcc4` | **56.06 / 49.16 → 23.53 / 21.82** | ms | two arms, alternating order, 25 requests each: `_path_binary` forced to `shutil.which` vs memoised |
| `/api/inference/status` before vs after (same run) | `1f4fcc4` | 39.13 → 22.7 (floor 5.86 / 8.59) | ms | 30 requests, warm; the floor moved with host load, the A/B above is the evidence |
| Cold boot `/chat`: LCP / CLS | `1f4fcc4` | **292–336 / 0.0019** | ms / — | `.council/round-2/timings.json`, direct load with the token already stored |
| In-app route change: CLS | `1f4fcc4` | library 0.007 · hub 0.0694 · train 0.0342 | — | same file, CLS reset immediately before a sidebar click |
| Hub requests on arrival | `1f4fcc4` | 217 total: **119 js**, `/api/inference/status` ×17 per 10 s | — | `.council/requests.mjs`, `.council/poll_rate.mjs` |
| Backend `import main` (launch) | measured | **2.93 s** total: `routes` 1.12, `routes.systemone` 0.66, `fastmcp` 0.39, `routes.training` 0.35, `mcp` 0.25 | s | `python -X importtime -c "import main"`, top cumulative. Taken while two reviewers ran, so treat the absolute as an upper bound; the *shares* are the useful part. The MCP server is built at import (`main.py:1152-1156`) because `combine_lifespans` needs it, so lazifying it is a boot-structure change, not an import tweak — not attempted. |
| Idle `/api/inference/status` polling on /hub, 10 s window | `57f2073` | **22 → 4 requests**, median gap **524 → 4047 ms** | requests | `.council/round-2/pollers.mjs` (CDP `initiator.stack`), before/after on the served build. Idle backend cost 2.2×39 → 0.4×23 ≈ **86 → 9 ms/s** |
| Unnamed focusables / visible focus rings on /chat | `57f2073` | **7 → 0** unnamed; focus rings **3 → 10** of 14 tab stops | count | `.council/round-2/a11y.json` (`.json` before/after), real Tab key events, computed styles |
| Post-fix cold desktop load | `57f2073` | LCP chat 404 / settings 320, CLS 0.0019 | ms | `.council/round-2/timings-postfix.json`; the hub row in that file is auth-swap contaminated and not quotable |

## Security ledger

| id | surface | issue | severity | status | test |
|---|---|---|---|---|---|
| SEC-1 | `Host` header | DNS rebinding, middleware off by default | medium | fixed | `test_trusted_hosts.py` |
| SEC-2 | canvas `?link=` | capability carried no account binding | medium | fixed | `test_canvas_link_auth.py` |
| SEC-3 | keyless `full` scope | per-host, not per-user | medium | **fixed this turn**: the setting now states the per-machine boundary in the confirmation *and* the always-visible row (the boundary itself is unchanged and stays host-wide) | `keyless-full-scope-warning.test.ts` (3) |
| SEC-4 | `X-Desktop-Secret` on `/api/health`, `POST /api/desktop/shutdown` | unauth 100k PBKDF2 per request | low | **fixed this turn**: budget before KDF + validated-once memo | `test_main_middleware_and_desktop_secret.py`, `test_desktop_secret_validation_cache.py` |
| SEC-5 | two middlewares | `scope["path"]` without `root_path` | low | fixed; regression-pinned this turn (raw ASGI scope, `TestClient` cannot express it) | `test_security_header_root_path_and_error_redaction.py` |
| SEC-6 | sandbox `reveal` | directory form skipped owner check | low | fixed | `test_sandbox_files_and_storage_roots.py` |
| SEC-7 | HTTP error details | host paths in 503/422 | low | fixed; redaction pinned this turn (POSIX + Windows reasons) | `test_security_header_root_path_and_error_redaction.py` |
| SEC-8 | library upload name | `.`/`..`/control chars in label | low | fixed | `test_library_routes.py` |
| SEC-9 | canvas routes | `?link=` never minted in production | low | open by design | `test_canvas_link_auth.py` |

All nine entries were re-verified against `HEAD` on 2026-11-17; seven were already fixed in code. Corrected the stale `SECURITY_AUDIT.md` in place (the document had SEC-1, 2, 5, 6, 7, 8 written as open). SEC-9 stays open by decision: the mint is dead code and exposing it would widen the surface SEC-2 is about.

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
| 3 | `glm-5.3-flash` | 6 | 7 | 7 | 7 | 7 | **34/50** |
| 1 | `mimo-2.6-flash` | 6 | 6 | 7 | 7 | 7 | **33/50** |

**Round 1 closed: median of three = 33/50** (32 / 33 / 34). Per-dimension medians are C6 · L7 · H7 ·
S7 · A7 — note those sum to 34 while the median *total* is 33, so quote the total, not the sum of
medians. Minimum single dimension: 5 (A11y, reviewer 2); its round-1 finding is now measured away
(rings 3 → 10 → **14 of 14**, unnamed focusables 7 → **0**). Reviewer 1's full scorecard is
`.council/round-2/reviewer-1-mimo.md`.

Two of reviewer 1's three load-bearing load claims do **not** survive measurement, so L=6 is
recorded but not acted on: (a) the "2.45 MB eager `browser-*.js`" is the **shared vendor chunk** —
45 chunks import it and it contains `react-dom` and `radix`, so it is not a lazy-loadable feature
(checked: `grep -l 'Gdb9V1jr' dist/assets/*.js | wc -l` = 45); (b) its `d-hub 1672 ms / CLS 0.0122`
comes from the **contaminated** `timings.json`, captured while two reviewers were running.

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

### Round 3 — closed at median **39/50** (round 2 was 37)

| reviewer | model | C | Load | Hier | States | A11y | Total |
|---|---|---|---|---|---|---|---|
| 1 | `mimo-2.6-flash` | 8 | 7 | 8 | 8 | 8 | **39/50** |
| 2 | `deepseek-v4.1-flash` | 7 | 9 | 8 | 7 | 7 | **38/50** |
| 3 | `glm-5.3-flash` | 9 | 9 | 8 | 8 | 9 | **43/50** |

Median total **39**; per-dimension medians C8 · L9 · H8 · S8 · A8. Best-of-panel 43. Scored changes:
the sidebar inset (912 -> 888), loading announcements, the profile-row subtitle fix, two non-visual test
repairs. Consistency moved 7 -> 9 at best and Load held at 9, so the remaining distance to 47 is spread
thinly across H/S/A rather than concentrated anywhere.

Reviewer 3's one open criticism — "no round-3 screenshot shows the corrected profile row" — is now
answered: `.council/round-3/screenshots/profile-row-fixed.png` shows the avatar plus a single title and
the cog, and the DOM reads back `lines: ["X", "X-"]` with `duplicate label: false` (was "X-" bold over
"X-" faint). The row is 243x44 at (19, 835) in a 1440x900 viewport.

Reviewer claims from round 3 and what happened:
- ✅ "footer identity renders `x-` over a faint `x-`" — **real**: the subtitle was a hard-coded "X-"
  while the owner's title is also "X-". Fixed (`23a2d43`), 3 tests.
- ❌ "drop the `.dark` prefix so light mode gets the inset too" — rejected: the glass shell is
  documented `.dark`-only on purpose ("Light mode and every palette keep exactly what they had",
  `index.css:6624-6630`). Not a defect.
- ⚠️ "a hard failure is silent (`states-failure.json` alerts [])" — that file came from a **void**
  probe (the Hub renders a bundled catalogue with every `/api/hub/*` blocked), so it proves nothing
  either way. The inline "Unsloth isn't running — please relaunch it." message IS present.
- ⚠️ "responsive unproven, all measurements 1440x900" — the round-1 mobile captures (390x844) exist at
  `.council/round-1/screenshots/06-08_*`; the reviewer was handed an evidence list that omitted them.
- ❌ Reviewer 1's Hub `min-height` suggestion targets the wrong node. Attributed with a layout-shift
  observer over two in-app visits (`.council/round-3/hub-cls.json`): run 1 CLS 0.0647, of which 0.0487
  is `div.page-title-halo` / the page title collapsing 70 -> 32 px, plus 0.0211 from a fixed overlay;
  run 2 CLS 0.0289, 0.0278 of it the content container's own reflow. The route root
  `div.relative.flex` is **not** the source, and both runs are inside the "good" band (<0.1).

### Round 2 (closed) — median 37/50

| reviewer | model | C | Load | Hier | States | A11y | Total |
|---|---|---|---|---|---|---|---|
| 1 | `mimo-2.6-flash` | 7 | 7 | 7 | 8 | 8 | **37/50** |
| 2 | `deepseek-v4.1-flash` | 7 | 7 | 8 | 7 | 7 | **36/50** |
| 3 | `glm-5.3-flash` | 8 | 9 | 8 | 8 | 9 | **42/50** |

### Round 1 fixes### Round 1 fixes### Round 1 fixes

| # | Fix | Status | Evidence |
|---|---|---|---|
| 1 | Sidebar nav rows get a keyboard ring matching the rows beside them | **shipped `d46130a`, corrected `b98b6d3`** | First version used `--x-focus-ring`; reviewer 3 cited `app-sidebar.tsx:797` (`focus-visible:ring-2 ring-ring`) on the nav's own submenu rows, so the first version created a second look. Now `0 0 0 2px var(--ring)`; CDP on the served build: `rgb(223,223,223) 0 0 0 2px`. 3 tests fail without the rule; 60-file CSS set 823/30 (29 pre-existing). |
| 2 | Lazy-load the browser feature off the boot graph (2.57 MB, 98 preloads) | **rejected as scoped** — see below | `__root.tsx:26` is 1 of **12** eager importers of `@/features/browser` (app-sidebar, chat-page, markdown-text, shared-composer, artifact-card, rag/*, settings tabs); lazying the dialog alone left `dist/index.html` at **98 preloads** with `browser-*.js` still referenced 3×. Reverted. The real fix is deep imports at those call sites, tracked below. |
| 3 | Give the Compute-backend select a placeholder instead of an empty box | **shipped `9c53572`** | `llama-backend-section.tsx:920`: the trigger had an item for `unknown` only when the stored marker was explicitly null, so `value = "unknown"` rendered nothing. Now renders the value we hold, labelled **Unknown** and disabled. Verified in `.council/round-2/screenshots/05-settings-dark.png` (read back: row reads "Unknown", not an empty box). |
| 4 | Give every slider thumb an accessible name | **shipped `5e82bf9`** | The thumb *is* the `role="slider"` element; the visible row label beside it is not a name. Fixed `chat-settings-sheet.tsx` (2, beside an input that already had `ariaLabel={label}`), `params-section-controls.tsx`, `params-section.tsx`, `markdown-note-dialog.tsx`. Verified: the unnamed-focusable probe on /chat returns **`[]`**, was 7. |
| 6 | Give the last four ringless tab stops a focus indicator | **shipped `205b19a`** | Reviewer 1 named the home anchor as its cheapest fix; a real 14-Tab walk showed **four**: Dictate, the brand anchor, "Show workflows", the section triggers. The shell strips every focus outline, `.sidebar-row-action` added its own `outline-none` and stayed at opacity 0 until hovered. Fixed in `index.css` (row actions) + `app-sidebar.tsx` (anchor, 4 triggers) + `thread.tsx` (Dictate); a fifth trigger with different classes was caught by the new test, not by the walk. Measured **14 of 14** ring-visible, unnamed 0, contrast 0/30. 5 tests. |
| 5 | Collapse arbitrary radii onto the declared scale (56×10px, 37×14px, …) | deferred, with reason | `consistency.md`, `index.css:242-247`. 10 px is dominant (57 uses) and tests pin `rounded-[10px]` literally, so this is a product-wide visual decision, not a cleanup. |
| 7 | One selected-pill treatment for Train's sub-nav (white pill vs Hub's accent) | queued | `studio-navigation.tsx:44`, `index.css` `.train-segment-active` — `background: var(--foreground)` with `text-background` ink. The comment in `index.css` defends the *track*, not the white fill. |

## Open threads

- [x] **Sidebar inset claim was real, and is fixed.** Both review panels said the sidebar runs past the
  content panel's bottom inset. Measured: `[data-sidebar="sidebar"]` bottom **912** on a 900 viewport vs the
  content panel's **888** — the sidebar carried shadcn's `size-full`, and a utilities-layer utility outranks
  the components-layer `height: calc(100% - 24px)`, so it was full height PLUS a 12px top margin. `!important`
  on the two length declarations makes it 888/888. Committed `6d98260`, pinned by
  `tests/sidebar-panel-inset.test.ts`.

- [x] **The Hub's failure path cannot be observed by blocking requests: its catalogue is bundled.**
  With every `/api/hub/*` call blocked on a cache-cleared, storage-cleared load, the Hub still renders the
  full model list plus "Unsloth isn't running -- please relaunch it." and a "0 Cache 0 Local" chip
  (`.council/round-2/screenshots/hub-all-hub-api-blocked.png`, `states-failure.json`). So the earlier
  "silent failure" reading was a probe artifact, not a defect, and `states.mjs` blocking
  `/api/hub/unsloth-models` proved nothing. Loading skeletons are real: 10 on /library, 36 on /hub mid-load.

- [ ] **219 requests / 119 JS chunks on the Hub** — chunk fragmentation, measured. A manual chunking pass
  (shared vendor chunk) would cut requests; unmeasured benefit, so not started.
- [ ] **Why `/api/inference/status` is polled 17× per 10 s** on the Hub is still unknown: the endpoint is
  now cheap (23 ms), but 1.7 req/s is more than a status read needs. Find the poll driver before changing
  an interval that may be intentional.
- [ ] SEC-3 warning text ("any local user").
- [ ] `--x-space-*` / `--x-icon-*` are dead tokens: adopt at call sites or delete. The panel named it;
  a dead token layer is worse than none because UI_AUDIT claims it exists.

## Next best action

1. **Round 3**: the shipped set since round 2 is sidebar inset + stale-test repair + formatting, so re-score
   only after one more behavioural fix. Best candidates, in order of evidence: (a) announce loading regions
   (`aria-live`) on the hub/library skeletons — reviewer 3's only unfixed States item; (b) the hub detail
   table, *after* checking in the DOM whether it scrolls; (c) the Train pill row height, *after* measuring
   real CLS attribution (`PerformanceObserver` + `LayoutShift.sources`), never from `timings.json`.
2. Dispatch reviewers **one or two at a time** (account caps at 2 children); always pass `target`
   explicitly — omitting it inherits the parent model and silently duplicates a reviewer, which happened
   once and had to be cancelled.
3. Re-measure the API workload (`bench_api.py`) **only on an idle host**: the 15-reviewer-session earlier
   showed reviewer children move the median by ~2x. Say so if a number was taken while a child ran.

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
- Fix #2 did not survive contact: `@/features/browser` has 12 eager importers, so the one `lazy()` the
  reviewer proposed left the preload count at 98 and the chunk still referenced. Reverted the edit
  rather than keeping a comment that claims a win it did not produce; the real fix (deep imports at
  the call sites) is tracked as an open thread.
- Fix #3 shipped and verified visually: the Compute-backend select now reads "Unknown" instead of an
  empty box (round-2 screenshot read back).
- Round-2 evidence captured (`.council/round-2/`, 10 screens + a11y + timings). **Caveat: captured while
  two reviewers were running**, so its LCP numbers are contaminated (d-chat 528 vs 392, d-hub 1672 vs
  1128). The a11y comparison is unaffected: `focus_ring_seen` 3 → 7 of 14 tab stops. Re-measure timings
  on an idle host before quoting round 2.
- Reviewer 3 (34/50) mis-attributed my fix to `app-sidebar.tsx:797`, but the citation was useful: it
  showed the sidebar already had a 2px `ring-ring` convention, so I corrected my own rule to match it
  (`b98b6d3`). That is the loop working — the score was not trusted, the citation was checked.
- Reviewer 3's own top fix (dedupe cpp/wasm chunks) **rejected on measurement**: neither is referenced
  by `dist/index.html` (`grep -cE 'cpp-|wasm-'` = 0), so both are on-demand grammar chunks and fixing
  the duplication buys 0 boot time. Recorded instead of done.
- Cleared the 7 unnamed focusables reviewer 3 kept A11y at 7 for: every one traced to a slider thumb
  (`data-slot="slider-thumb"`, the `role="slider"` element) whose visible row label was never passed
  as a name. The chat panel's number input already did it correctly beside the slider that did not.
  Probe on the served build: 7 → **0**.
- Found and fixed the measurement pipeline: the CLS/LCP evidence navigated `/login` → screen, so it
  counted the auth-shell swap. Rebuilt the harness around the user's two real paths (cold load with a
  stored token; in-app sidebar click with CLS reset before it). Cold `/chat` is LCP 292–336 ms / CLS
  0.0019; in-app CLS is library 0.007, hub 0.0694, train 0.0342. That kills the "fix d-hub CLS 0.064"
  item that both reviewers ranked: the 0.064 was the harness.
- Hub arrival makes **219 requests, 119 of them JS**, and polls `/api/inference/status` **17× per 10 s**.
  Profiled that endpoint: `shutil.which("llama-server")` walked the whole PATH twice per request, 28.6 ms
  of 39.1 ms. Memoised the PATH fallback for 5 s with misses cached: in-process A/B 56.06/49.16 →
  23.53/21.82 ms (alternating order), 5 new tests, 412 related tests pass (2 failures reproduce on
  `HEAD` with the change stashed).
- Commits: `a44b8f2` (SEC-4 + tests), `d46130a` (focus ring + tests), `b1422c8` (round-1 ledger),
  `9c53572` (backend select label), `b98b6d3` (ring matches the sidebar's own convention), `5e82bf9`
  (slider accessible names), `1f4fcc4` (PATH memo).
