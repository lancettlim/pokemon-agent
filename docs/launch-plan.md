# Launch plan

Written 2026-11-01. Covers what must happen before a public launch of the
dashboard and dataset: blockers, UI cleanup, tech-debt removal, reliability
and the launch itself. Items move into `docs/todo.md` once accepted, per the
backlog → todo flow. One PR per phase.

## Evidence this plan rests on

- `pipelines/dashboard/static/app.js` is 5,610 lines (253KB),
  `pipelines/dashboard/data.py` 1,928 lines, and
  `templates/index.html.jinja` 3,058 lines with its CSS inlined into a 443KB
  `index.html`.
- `docs/dashboard/` is 66MB (44MB of data shards, 21MB of images) and the git
  pack is 65MB; regenerating the site on every build adds to it.
- No TODO/FIXME markers exist in code, so the debt is size and structure.
- Browser route tests run at 1440 and 390 only (`VIEWPORTS` in
  `tests/browser/test_dashboard_routes.py`); the one overflow assertion is at
  390 (`test_builder_and_views.py`). The 2027 Q2 plan's tablet finding
  (768px overflow) has no test proving it fixed.
- There is no `LICENSE`, the latest dataset release is 0.3.0, and Regulation
  M-D (starts 2026-12-03) has no row in `dbt/seeds/champions_regulations.csv`.

## Phase 0: Decisions (owner)

Defaults below apply until the owner says otherwise.

- [ ] License. Default: MIT for code; dataset under CC BY 4.0 with a note that
  sprites are Nintendo/Game Freak artwork sourced from Bulbagarden Archives
  and are not relicensed.
- [ ] Launch date and audience. Default: soft launch to the VGC community,
  after Phase 1 and 2 exit criteria.
- [ ] Cut dataset 0.4.0 with the launch. Default: yes.

## Phase 1: Launch blockers

- [ ] Add `LICENSE` and a data-terms note.
- [ ] Add the M-D row to `champions_regulations.csv`; rehearse the
  "Regulation rollover playbook" in `docs/dashboard.md`.
- [ ] Cut 0.4.0 via `cut-release.yml`; verify the zip and the manifest's
  sha256.
- [ ] Add `CONTRIBUTING.md`, issue templates and a data-correction path.
- [ ] Merge the README rewrite (PR 72).

Exit: `make check` is green on a clean checkout and the release asset
downloads and verifies.

## Phase 2: UI cleanup

- [ ] Add 360, 744, 768 and 1024px to the browser route matrix with a
  `scrollWidth <= viewport` assertion on every route; fix what it catches.
- [ ] Finish the per-tier layout checklist (`todo.md`, "Every new component
  built to its M3 per-tier layout") by testing each component.
- [ ] Accessibility pass: contrast, keyboard paths, touch targets, focus
  order.
- [ ] First-visit audit of Overview: Top 12 as the hero, loading and empty
  states.
- [ ] A one-screen "what this is / data limits" panel.

Exit: the matrix passes at 360, 390, 768, 1024 and 1440 with zero console
errors.

## Phase 3: Tech-debt removal

- [ ] Split `app.js` into modules (pure helpers, then table and tooltip
  components); keep the hash router and behavior unchanged.
- [ ] Move inline CSS out of `index.html.jinja` into a cacheable stylesheet.
- [ ] Split `data.py` by domain, following `graph.py`.
- [ ] Reduce site weight: audit the 44MB of shards and 21MB of images. Any
  git-history rewrite needs explicit owner approval.
- [ ] Meta Graph items with launch value: U1 regulation diff, U8 profile
  mini graph, and the ladder source switch (`todo.md`, "Step 4"). Defer the
  rest of Section 10.

Exit: behavior identical, browser tests unchanged and green, no source file
over about 2,000 lines.

## Phase 4: Reliability and ops

- [ ] Failure alerts on the scheduled-extraction, refresh-dashboard and
  event-weekend workflows.
- [ ] A visible "last updated" and freshness badge fed by the freshness gate.
- [ ] A rollback note for a bad Pages deploy.

Exit: a simulated source failure produces a visible alert.

## Phase 5: Launch

- [ ] Launch post and changelog entry.
- [ ] Check share-card and Open Graph previews on real platforms.
- [ ] Final Playwright run plus a manual phone check.
- [ ] Tag, publish, and monitor for 48 hours.

## Risks

- Splitting `app.js` is the riskiest step; any view the browser tests do not
  cover could regress silently. Keep it to small PRs.
- Pruning generated data in git touches published history. Do not do it
  without approval.
- M-D could land mid-launch; the seed row in Phase 1 removes that risk.
