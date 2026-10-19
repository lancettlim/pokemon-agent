# Next upgrade plan — "Current Meta" (2026 Q4)

Written 2026-10-18. This plan sets the next product cycle. It comes ahead of
`docs/roadmap.md` Phases 3–4 because the published dashboard has drifted out
of date with the live format. Items move into `docs/todo.md` once accepted,
per `docs/backlog.md`'s backlog → todo flow.

## Status

| Item | State |
|---|---|
| A1 regulation registry + drift test | Done (Sprint 1) |
| A2 `tournament_event.regulation_code` | Done (Sprint 1); `pokemon_usage_by_regulation` rebuilt as a true per-regulation slice (Sprint 2) |
| A3 regulation dimension on marts | Done (Sprint 2): `regulation_scope` on usage, win rate, items/abilities/moves, cores, synergy, placement, profile, speed tiers, build concentration, top teams. Head-to-head, triples, country and player marts still cover all regulations |
| A4 "what changed" mart | Done (Sprint 2): `pokemon_regulation_movers` plus the Overview panel. `pokemon_recent_window` was not needed: the regulation selector covers "the current regulation's events" |
| B3 global filter + URL state | Done (Sprint 2): header Regulation selector, `?reg=` and `#tab` links. Event-window filter and the type popover are not done |
| A5 M-C legality + new Megas | Done (Sprint 1). PokéAPI already models the Z Megas (`absol-mega-z`, `garchomp-mega-z`, `lucario-mega-z`), so they map like any other form and need no spec change |
| A6 refresh workflow + staleness banner | Done (Sprint 1) |
| B1 quick fixes | Done (Sprint 1) |
| A7 publish 0.4.0 | Deferred: needs re-extraction stamped 0.4.0 and adds ~55MB to git, so it's a separate decision |
| B2 five-section navigation | Done (Sprint 3), with the bottom nav on phones and the KPI strip on Meta only |
| B4 Pokémon hub | Done (Sprint 3): type-ahead search on every Pokémon picker, `/` shortcut, stat bars against the format median, most-common-set card with Showdown copy. A per-regulation trend sparkline is not done |
| B5 Meta landing | Done (Sprints 2–3): What changed panel and Tier List. Latest-event spotlight is not done |
| B7 performance | Done (Sprint 4): mart shards under `docs/dashboard/data/`. The default view is ~400KB compressed, down from ~2MB, and Overview needs no fetch |
| B8 theme + accessibility | Done (Sprint 4): dark theme (OS-following, with a header toggle), visible focus rings, reduced motion, combobox ARIA |
| B9 Team Builder | Done (Sprint 4): suggested partners by synergy lift in the selected regulation; the threat screen follows the selected regulation. Pokepaste import already existed |
| B6 shared table component | Not started. The views work and are consistent; this is a refactor with no visible change, so it's left for a later pass |

Two upstream breakages turned up during the Sprint 1 refresh, and both are
fixed: Bulbagarden renamed every sprite file from "Menu CP" to "Menu Champs"
(the extractor had been writing empty snapshots), and PokéBase redesigned
its page so legality arrives as `addedIn` rather than `regulationSets`.

## Why this, why now

An audit of the published dashboard (`docs/dashboard/data.json`) against the
live format found:

| Finding | Evidence |
|---|---|
| **The dashboard is 10 weeks stale.** | `generated_at_utc` is 2026-08-04. Its newest event is the 2026-06-12 NAIC. |
| **It shows the wrong regulation.** | Reg M-C has been live since **2026-09-09** and runs to 2026-12-02 ([Victory Road](https://victoryroad.pro/champions-regulations/)). The dashboard has only M-A/M-B legality and **M-A events only**. |
| **Worlds and every M-C event are silently dropped.** | The Champions format is hardcoded to Reg M-A in three places: `dbt/dbt_project.yml` (`champions_event_format: gen9championsvgc2026regma`), `pipelines/extract/rk9.py` (`CHAMPIONS_FORMAT`) and `pipelines/extract/limitless.py` (`CHAMPIONS_FORMAT = "m-a"`). The live MunchStats index already lists `gen9championsvgc2026regmb` (2026 Worlds, 395 players) and five `gen9championsvgc2026regmc` regionals: Baltimore, Frankfurt, Brisbane, Recife and Louisville (~3,770 players). The filter excludes all of them. |
| **Nothing refreshes the published site.** | `scheduled-extraction.yml` refreshes staging daily. `deploy-dashboard.yml` only runs when `docs/**` is pushed. No workflow chains extract → dbt → build-dashboard → deploy. |
| **Events carry no regulation.** | `pokemon_usage_by_regulation` admits it isn't a "usage during regulation X" slice. `tournament_event` has no `regulation_code`, so usage can't be scoped to the current format. |

As a result, every number on the site describes a format that ended four
months ago. M-C added 29 Pokémon and 6 new Megas: Mega Absol Z, Mega
Salamence, Mega Garchomp Z, Mega Lucario Z, Mega Golisopod and Mega
Baxcalibur. None of them appear.

The UI review (desktop 1440px and mobile 390px screenshots, 2026-10-18)
found:

- **Raw internal names leak into the UI**, e.g. `BasculegionMale` and
  `CharizardMegaY`. Long names break mid-word in the KPI cards
  ("Bascule / gionMal / e").
- **13 tabs in one horizontal strip.** It overflows and clips at desktop
  width ("Players & Regic…"), and on mobile only 2½ tabs are visible.
- **A literal `\n` sits in the tab bar markup**
  (`templates/index.html.jinja`, the Core Explorer / Data & Sources buttons,
  and the `@media` rule beside it). It is a leftover from a past edit.
- **About 300px of header and KPI cards repeat above every tab**, so the
  real content starts below the fold.
- **Filters are a loose grid.** Eighteen type chips dominate each filter
  panel, and labels and inputs don't line up.
- **The Pokémon Profile picker is a native `<select>` with ~300 options.**
  It has no search and no sprites. The profile's type icons render far
  larger than the `--icon-*` scale allows.
- **No shareable state.** URLs never change (no hash or query state outside
  `expansions.js`), so you can't link someone to "Garchomp in M-C".
- **The 7.9 MB `data.json` loads before anything renders.**

## Goals for this cycle

1. **Current by default.** The site opens on the regulation in force today,
   and its data is at most 7 days old.
2. **Regulation-aware everywhere.** Every usage, win-rate, build and
   matchup figure can be scoped to M-A, M-B, M-C or All Champions.
3. **Trend-first.** Lead with what changed in the current regulation, not
   with all-time aggregates.
4. **A UI players reach for.** Searchable, linkable, readable on a phone,
   and fast on first load.

Non-goals are unchanged: no EV/IV fields, no Pokémon-level battle
attribution (team-vs-team grain stays labelled), and no dynamic backend.

---

## Track A — Data currency (P0)

### A1. Regulation registry seed replaces the hardcoded format

Add `dbt/seeds/champions_regulations.csv` as the single source of truth:

| regulation_code | munchstats_format | limitless_slug | start_date | end_date |
|---|---|---|---|---|
| m-a | gen9championsvgc2026regma | m-a | 2026-04-08 | 2026-06-17 |
| m-b | gen9championsvgc2026regmb | m-b | 2026-06-17 | 2026-09-09 |
| m-c | gen9championsvgc2026regmc | m-c | 2026-09-09 | 2026-12-02 |

Changes:

- `rk9.py`, `limitless.py` and the MunchStats-index read take a *set* of
  Champions formats loaded from the seed, not one constant.
- `int_champions_roster.sql` filters `event_format in (select munchstats_format
  from champions_regulations)`, which retires the `champions_event_format`
  var.
- **Drift alarm:** an extractor warning plus a dbt singular test fail if the
  MunchStats index (or Limitless) lists a `gen9champions*` format or a
  Champions slug that isn't in the seed. That check would have caught this
  regression on 2026-06-17.
- Before A1 ships, confirm the Limitless slugs for M-B and M-C from the live
  page. The table above assumes the `m-a` naming pattern.

Acceptance: a refresh includes the 2026 Worlds event and all five M-C
regionals, and the drift test fails on a fixture that adds an unknown
format.

### A2. `regulation_code` on `tournament_event`

- Derive it from the registry by the event's `munchstats_format` (exact),
  with a fallback to the event-date range. Add it to `docs/dataset-spec.md`'s
  entity dictionary as a required field, with a null-rate gate.
- Propagate it to `team_list.regulation_set` cross-checks. Limitless already
  reports the set, so add an agreement test.
- Rebuild `pokemon_usage_by_regulation` as a true temporal slice: usage of
  Pokémon X *in events played under* regulation Y. That replaces today's
  "legal-pool membership" approximation.

### A3. Regulation as a mart dimension

Add a `regulation_code` partition, plus an `all` roll-up row, to these
marts:

- `pokemon_usage_summary`
- `pokemon_win_rate_summary`
- `pokemon_item_usage`, `pokemon_ability_usage`, `pokemon_move_usage`
- `pokemon_team_core_usage`, `pokemon_team_synergy`
- `pokemon_champions_profile`
- `top_tournament_teams`
- `pokemon_head_to_head`, `pokemon_matchup_summary`

This follows the pattern `event_tier` already uses in
`pokemon_usage_summary`. Mart tests (backlog #42) assert that each
partition ranks independently.

### A4. "What changed" marts (meta shift without snapshot history)

Backlog #18 was archived because it was blocked on *extraction* snapshot
history. A regulation-to-regulation comparison needs no snapshot history:
it compares event cohorts.

- `pokemon_regulation_movers`: usage share and Wilson win rate in M-B vs
  M-C, plus the delta, rank change and a `new_to_format` flag for the 29
  Pokémon M-C added.
- `pokemon_recent_window`: usage over the last N event dates (default: the
  current regulation's events), for a "hot right now" view.
- Show `n` (teams, events) next to every delta. M-C has 5 events today and
  will be thin until LAIC, so suppress deltas below a minimum team count
  rather than show noise.

### A5. M-C legality and new Mega forms

- Re-extract PokéBase and confirm `m-c` membership appears (expect +29 vs
  M-B).
- Extend the mapping seeds (`opgg_key_to_pokeapi_form`,
  `munchstats_name_to_pokeapi_form`, `pokebase_*`,
  `bulbagarden_title_to_pokeapi_form`) for the six new Megas. The "Z"
  Megas (Absol Z, Garchomp Z, Lucario Z) may have no PokéAPI form. Decide
  whether to model them as Champions-only `pokemon_key`s with a null
  `pokemon_id`, which is a spec decision, or leave them unmapped and
  reported. Record the decision in `dataset-spec.md`.
- Pull the new Mega sprites from Bulbagarden. The coverage gate must stay
  at or above 85%.

### A6. Automated refresh → deploy

- Add a `refresh-and-deploy.yml` workflow that runs weekly (Mon, after the
  PokéAPI run) and on demand. It restores the staging cache, then runs
  `make refresh` → `build-dashboard`. If validation passes, it opens or
  updates a bot PR with the regenerated `docs/dashboard/`. A bot PR keeps
  the review gate. Committing straight to `main` would trigger the existing
  Pages deploy without one.
- Add a **staleness banner** to the dashboard. It appears when the newest
  event is more than 21 days old, or when the current regulation (from the
  registry and today's date) has zero events. A silently stale site was
  the failure this cycle fixes, so make staleness visible.

### A7. Publish `dataset_version 0.4.0`

Publish after A1–A5: new entity field, new marts and M-C coverage. The
CHANGELOG should call out that pre-0.4.0 releases excluded M-B and M-C
events.

---

## Track B — UI overhaul

### B1. Quick fixes (ship with Track A)

- **Display names:** add one `display_name(pokemon_key)` formatter in
  `pipelines/dashboard/data.py`, fed by a small override seed:
  `charizard-mega-y` → "Mega Charizard Y", `basculegion-male` →
  "Basculegion ♂", `floette-mega` → "Mega Floette". Use it for every label.
  Never render the raw `pokemon_name` concatenation.
- Remove the literal `\n` characters from `index.html.jinja`.
- KPI cards: `overflow-wrap: normal`, a smaller name type size, and a
  sprite beside the text instead of stacked. Remove the empty space in the
  "Distinct Pokémon" card, or replace the card with something useful
  ("Events in M-C: 5 · Teams: 3,700").
- Profile type icons: apply `--icon-sm`, as `design-system.md` requires.

### B2. Information architecture: 13 tabs → 5 sections

| Section | Absorbs today's tabs |
|---|---|
| **Meta** | Overview, Usage, Speed Tiers, plus the new "What changed in M-C" |
| **Pokémon** | Pokémon Profile, Compare, Matchup |
| **Teams** | Top Teams, Archetypes, Core Explorer, Players & Regions |
| **Builder** | Team Builder |
| **Data** | Data & Sources |

- Use a compact sticky header (≈56px) with the brand, the section nav and
  the global filters (B3). Show the KPI strip only on Meta.
- Sub-views inside a section become a segmented control, not more tabs.
- Mobile gets a bottom navigation bar with the 5 sections, and filters move
  into a slide-up drawer.

### B3. Global filter bar + URL state

- Filters: **Regulation** (defaults to the current one from the registry;
  includes "All Champions"), **Event tier** and **Event window** (all
  events in the regulation / last N events). One filter state drives every
  section, replacing today's per-tab Tier/Regulation selects.
- Encode section, sub-view, filters and selected Pokémon in
  `location.hash`, e.g. `#/pokemon/garchomp?reg=m-c`. Back/forward work,
  and links are shareable.
- Collapse the 18 type chips behind a "Type ▾" multi-select popover that
  shows the selected count.

### B4. Pokémon page as the hub

- Replace the `<select>` with a **type-ahead combobox** (sprite + name +
  usage %), keyboard-navigable, reachable globally with `/`.
- Clicking any Pokémon anywhere on the site opens its page.
- Layout:
  1. Hero: art, types and base stats as horizontal bars against the
     format median.
  2. Usage and win-rate trend across regulations: a sparkline from A3/A4.
  3. **Most common set:** the modal item, ability, nature and 4 moves,
     rendered as a pokepaste-ready card with a copy button.
  4. Tables for items, abilities and moves, each row with an inline share
     bar.
  5. Teammates (by synergy lift) and matchups, keeping the existing
     team-vs-team caveat label.

### B5. Meta landing page

- **"What changed in M-C"** sits above the fold: risers and fallers, new
  arrivals, and the six new Megas with their usage. Data comes from A4.
- **Tier view:** S/A/B/C bands from usage share × Wilson lower bound,
  showing the method and `n`. The current top-12 cards grid becomes a
  ranked table with inline bars, sprites and sortable columns.
- Latest event spotlight: the winner and top-8 team sheets, using the
  existing team-card renderer images.

### B6. Data presentation

- Use one shared sortable table component (sticky header, numeric
  alignment, inline bars, row → profile link) in place of the many
  hand-rolled card grids. Keep card grids for top-N highlights only.
- Every percentage shows its denominator on hover ("487 of 5,644 teams").
- Charts: put Chart.js defaults into the design-token palette once, and
  use direct labels instead of legends where possible.

### B7. Performance

- Split `data.json` (7.9 MB) into a small `core.json` (KPIs, names,
  sprites, current-regulation usage) plus one lazily fetched shard per
  section and regulation. Head-to-head, at 16.7k rows, is the largest and
  loads only on the Matchup view.
- Targets: first meaningful paint under 1.5 s on a throttled 4G Lighthouse
  run, and a core payload under 500 KB.

### B8. Theme and accessibility

- Add a dark theme by mapping the existing `:root` tokens under
  `prefers-color-scheme` plus a toggle. Type colors already come from one
  palette.
- WCAG AA contrast pass, visible focus rings, combobox ARIA, and a
  reduced-motion setting.

### B9. Team Builder upgrades

- Import pokepaste text, the counterpart to the existing export.
- "Suggested partners" for the current picks from `pokemon_team_synergy`,
  scoped to the selected regulation.
- Point the threat screen at the current regulation's top 12, not
  all-time.

---

## Sequencing

| Sprint (≈1 wk) | Scope | Exit criteria |
|---|---|---|
| **1 — Get current** | A1, A2, A5, B1, and a manual refresh + redeploy | Site shows M-C legality, Worlds and the M-C regionals, with correct names. `make check` is green. |
| **2 — Regulation-aware** | A3, A4, A6, A7, B3 (filter bar + URL state) | Every view filters by regulation and defaults to M-C. Weekly bot PR is running. 0.4.0 is published. |
| **3 — New shell** | B2, B4, B5 | 5-section navigation, the Pokémon hub with search, and the "What changed" landing page. |
| **4 — Polish** | B6, B7, B8, B9 | Lighthouse targets met, dark mode, Builder import and suggestions. |

Sprint 1 alone fixes the "is this data relevant" problem. Ship it before
any redesign work starts.

## Calendar to plan around

- **M-C runs until 2026-12-02.** The regulation after it should be a
  one-row seed change once A1 lands. Add the row as soon as the next set
  is announced so the drift alarm stays quiet.
- **2027 Latin America International Championships** is the largest M-C
  event. Time Sprint 2's deploy so the movers view has LAIC data.

## Risks

| Risk | Mitigation |
|---|---|
| "Z" Megas have no PokéAPI form | A5 makes it an explicit spec decision. Don't guess mappings (precedent: Mega Meowstic left unmapped). |
| M-C sample is thin (5 events) | Show `n`, rank by Wilson, and suppress deltas below a minimum team count. |
| Bot-PR refresh churns `docs/dashboard/images` | Sprites are content-stable by key, so only `data*.json` should diff. Assert that in the workflow. |
| Limitless/RK9 slugs for M-B/M-C differ from the assumed pattern | The A1 drift alarm reports unknown slugs, and seed entries are verified against the live pages before merge. |
| Redesign regresses existing views | Keep the Playwright screenshot smoke tests per section and the JS duplication check (backlog #46). B2 moves views; it doesn't rewrite their logic. |

## Proposed `todo.md` entries (on acceptance)

- [ ] Add `champions_regulations` seed; make RK9/Limitless/MunchStats/dbt
  read it; add unknown-format drift test (A1)
- [ ] Add required `tournament_event.regulation_code`; rebuild
  `pokemon_usage_by_regulation` as a temporal slice (A2)
- [ ] Add a `regulation_code` partition to the regulation-sensitive marts (A3)
- [ ] Add `pokemon_regulation_movers` and `pokemon_recent_window` marts (A4)
- [ ] Map M-C additions and the six new Megas; record the Z-Mega key decision (A5)
- [ ] Add `refresh-and-deploy.yml` bot-PR workflow and a staleness banner (A6)
- [ ] Publish `dataset_version 0.4.0` (A7)
- [ ] Dashboard quick fixes: display names, stray `\n`, KPI wrapping, icon sizes (B1)
- [ ] 5-section IA, global regulation filter, hash routing (B2, B3)
- [ ] Pokémon hub with combobox + most-common-set card (B4)
- [ ] Meta landing page with "What changed" and tier view (B5)
- [ ] Shared table component, payload sharding, dark theme, a11y (B6–B8)
- [ ] Team Builder import + partner suggestions (B9)
