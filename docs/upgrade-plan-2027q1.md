# Next upgrade plan — "Built for players" (2026 Q4 → 2027 Q1)

Written 2026-10-19. This plan follows `docs/upgrade-plan-2026q4.md`, whose
Sprints 1–4 shipped. Items move into
`docs/todo.md` once accepted, per `docs/backlog.md`'s backlog → todo flow.

The Q4 plan made the data current and gave the site a usable shell. This
cycle makes it something players open every week and creators cite.

Constraints are unchanged: no EV/IV fields, team-vs-team grain stays
labelled everywhere it appears, and the site stays static with no backend.

## Status

| Item | State |
|---|---|
| U1–U4 Shell fixes | Not started |
| U5–U8 Data presentation | Not started |
| P1–P5 Player features | Not started |
| C1–C4 Event, team and player features | Not started |
| D1–D3 Data access and operations | Not started |

---

## What the 2026-10-19 UI review found

Screenshots of every view at 1440px and 390px, taken against the published
`docs/dashboard/` build.

### Working well (keep)

- Five-section nav, the bottom bar on phones, and the KPI strip on Meta only.
- The "What changed" panel: risers, fallers and new arrivals with sprites
  and point deltas is the right landing content.
- The Tier List: bands, win-rate chips coloured by the Wilson bound, and
  the method stated up top.
- The Pokémon profile layout: stat bars against the format median, plus a
  most-common-set card with Showdown copy.
- The Builder's empty state explains what each panel will do once you add
  Pokémon.

### Problems, ranked by impact

| # | Finding | Evidence |
|---|---|---|
| 1 | **The Back button doesn't move between views, and a Pokémon can't be linked.** | `setupTabs` writes the hash with `history.replaceState` and nothing listens for `hashchange`/`popstate`. Changing the hash on an open page does nothing, and the selected Pokémon, sub-tab and filters aren't in the URL. The Q4 plan's `#/pokemon/garchomp?reg=m-c` (B3) was only partly built. |
| 2 | **About 380px of chrome sits above the content on desktop.** | A 136px dark header with the title plus five pills (theme, regulation, dataset version, snapshot, gates), then ~140px of KPI cards, then the section and sub-tab rows. Each view then repeats its own sub-tab name as a black panel header ("Overview" under "OVERVIEW"). |
| 3 | **Ranked data is shown as tall card grids.** | Usage shows 12 Pokémon per desktop screen as 165px cards holding a name and one number. Each item card on the profile is ~270px tall because the PokéAPI effect text is inline. A table row would fit 3–4× as many. B6 (shared table) was deferred as "no visible change". It is the biggest density win left. |
| 4 | **The most common set can be a set nobody runs.** | The set card takes the modal item, ability, nature and each move slot independently. "Grassy Glide 24.8% / Fake Out 24.7% / Wood Hammer 22.6% / High Horsepower 16.6%" may describe no real team sheet. |
| 5 | **Jargon has no inline explanation.** | "HHI 0.57", "Locked in", "+3.6 pts", "95% Wilson lower bound", "synergy lift", "roster slots". |
| 6 | **The "What changed" baseline is thin and unlabelled.** | It compares 3,770 M-C teams with 395 M-B teams, almost all of them from one event (Worlds). An elite single-event field isn't a normal regulation baseline. |
| 7 | **Top Teams shows a bare win rate.** | Cards show "100.0%" in large type with no W–L record, no placement and no copy action. The mart has `record_wins`, `record_losses` and placement. |
| 8 | **The 18 type chips still dominate the filters.** | Usage and Builder each give about 140px to 18 chips. The type popover (Q4 B3) isn't done. |
| 9 | **The damage calculator starts blank.** | The attacker and defender start with no item or ability preset, and setup sliders sit at 0. The most common set is already known. |
| 10 | **Internal language leaks into the UI.** | The Matchup intro says *see docs/design-system.md's "Matchup tab"*. |
| 11 | **Mobile sub-tabs clip with no scroll cue.** | "Speed Ti…" is cut off at 390px. On Teams, the pokepaste import textarea sits above the Top Teams list, though import belongs to the Builder. |
| 12 | **A remembered regulation outranks the one in force.** | `resolveRegulationScope` checks `localStorage` before `regulationInForce`. Anyone who once picked M-C will still land on M-C after the next set starts on 2026-12-02. |
| 13 | **No test loads the page in a browser.** | `tests/unit/dashboard/` covers the Python build and the JS duplication check only, so a runtime JS error ships unnoticed. |

---

## Track U — UI shell and presentation (P0)

### U1. Real routing

- Move to `history.pushState`, and handle `popstate`/`hashchange` so Back,
  Forward and pasted links all route.
- Put the whole view state in the hash:
  `#/pokemon/garchomp/moves`, `#/compare/garchomp,kingambit`,
  `#/matchup/rillaboom/sneasler`, `#/teams/top?tier=regional`,
  `#/player/<player_id>`, `#/event/<event_id>`. Keep `?reg=` as the
  regulation.
- Every Pokémon name or sprite anywhere on the site becomes a real `<a href>`
  to its route, so middle-click and long-press work.
- Accept the old `#tab-id` links and redirect them, so shared links keep
  working.

Acceptance: a Playwright test opens a deep link, clicks to two more views,
presses Back twice and lands on the deep link's view with the same Pokémon.

### U2. Compact chrome

- Turn the header into one sticky 56px bar: the brand, the section nav, the
  regulation select and a ⋯ menu holding the theme toggle.
- Move the dataset version, snapshot and gate status into a one-line footer
  and the Data section. Only the staleness banner stays in the header area,
  and only when it fires.
- Drop the black panel header when it repeats the sub-tab label. Keep the
  method/intro line, collapsed to one sentence with a "How this is
  computed" disclosure.
- Replace the "Distinct Pokémon used" KPI with "Events · Teams in this
  regulation" (for example "5 events · 3,770 teams"). It tells every reader how
  much to trust the page.

Target: content starts within 200px of the top on desktop and 120px on
phones.

### U3. Regulation rollover behaviour

- Prefer the regulation in force over the remembered one. Keep the
  remembered choice only if it was made during the current regulation:
  store the regulation code with the date it was chosen.
- When the regulation in force has fewer than a minimum number of teams
  (start at 300), open on the previous regulation, with a banner: "Reg M-D
  started 2026-12-03. Not enough results yet; showing M-C. Switch to M-D →".
- Add a test with a fixture where today falls just after a regulation's
  `end_date` and the new regulation has zero events.

This must ship before 2026-12-02.

### U4. Copy pass

- Remove repo paths and internal names from user-facing text (finding 10).
- Add a glossary: one `<abbr>`/tooltip component for usage share, roster
  slot, Wilson bound, HHI ("how concentrated a Pokémon's item choice is"),
  "Locked in", synergy lift and pts, backed by a "How to read this page"
  entry in the Data section.
- Every percentage gets its denominator on hover/tap ("487 of 5,644 teams"),
  as the Q4 plan's B6 called for.

### U5. Shared table component (Q4 B6, carried and re-justified)

A sortable table with a sticky header, sprite + name cell, right-aligned
numbers, inline share bars, and row → Pokémon route. On phones it collapses
to two-line rows.

Adopt it in this order: Usage, Profile items/abilities/moves (effect text
moves into a tooltip), Speed Tiers, Core Explorer and Players. Keep card
grids only for top-N highlights (the Overview, the Tier List).

### U6. Type filter popover (Q4 B3, carried)

A "Type ▾" button that opens an 18-type multi-select and shows the selected
count. Use it in Usage and the Builder.

### U7. Mobile fixes

- Sub-tab rows get edge fades plus scroll-snap, and the active sub-tab
  scrolls into view.
- Move the pokepaste import into the Builder ("Import team"), and drop it
  from Teams.
- Raise tap targets to 44px in the bottom bar and the chips.

### U8. Browser smoke tests and a performance budget

- Add a pytest + Playwright test that builds the dashboard from fixture
  marts, opens every route at 1440px and 390px, and fails on any console
  error or empty main panel.
- Add a CI budget: the core payload stays under 500KB compressed and the
  default view makes no more than 3 data fetches.

---

## Track P — Player features

### P1. Real sets: `pokemon_set_variants` mart

The most-asked player question ("what set do people run?"), and the fix
for finding 4.

- New mart, regulation-scoped through `int_champions_roster_scoped`: one
  row per Pokémon × (item, ability, nature, sorted 4-move set), with
  `team_count`, `share_of_pokemon` and a Wilson-ranked `win_rate`. Add a
  looser "core set" level that groups on item + ability + the 3 most common
  moves, so near-identical sets still cluster.
- The profile's set card shows the top 3 real sets as tabs, each with its
  share and `n`, plus Copy for Showdown. Drop the per-slot modal card, or
  keep it labelled "Most common choice per slot".
- Tests: shares sum to ≤ 1 per Pokémon and scope, and every set listed
  appears verbatim on at least one team sheet.

### P2. Pokémon hub v2

- A per-regulation trend line: usage share and win rate across M-A, M-B and
  M-C, with `n`. This is the sparkline the Q4 plan left undone.
- "Teams featuring X": the top-placing teams in the regulation that include
  this Pokémon, linking to their team views.
- "Common teammates" ranked by synergy lift (the mart already exists), as a
  table with sprites.
- "Pressure from the meta": type-chart weaknesses weighted by the usage of
  the attacking types in the current regulation. That's computed from data
  already loaded, and labelled as type-based, not battle results.
- A recently viewed strip, stored per browser, for the venue use case.

### P3. Calculator presets

- Load the attacker and defender with their #1 real set from P1, including
  item and ability. Keep the item/ability toggles, but pre-select them.
- Add a "vs the meta" mode: one attacker and one move against the top 12 of
  the regulation, each row showing a damage range and "OHKO / 2HKO / —".
  Label it as an estimate using base stats and no EVs.

### P4. Builder: start from a real team, save and share

- "Use this team" on any Top Teams or Converged list card loads the six
  Pokémon and their real sets into the Builder.
- Up to 5 saved teams in `localStorage`, named and kept per browser.
- A share link: the six keys plus their set indices in the hash
  (`#/builder/rillaboom.1,sneasler.0,...`). No server needed.

### P5. Starter teams for new players

A "Copy and play" strip on Meta → Overview: the three top-placing,
fully-reported teams of the current regulation, each with player, event,
placement and record, plus one-click Showdown copy and "Open in Builder".
It reuses P4 and C2's data.

---

## Track C — Events, teams and players

### C1. Event pages (`#/event/<id>`)

Carries the Q4 plan's "latest event spotlight" and goes further.

- The header gives the event name, date, tier, regulation, player count and
  source links.
- Show the top 8 teams with player, placement, W–L record, full sets and
  copy buttons.
- Add "Over- and under-performers at this event": usage at the event against
  the regulation average, with `n`. That needs a new
  `pokemon_event_usage_vs_regulation` mart.
- The Overview gets a "Latest event" card linking to the newest event page.
- An event index under Teams lists every event, sortable by date and size.

### C2. Top Teams that make sense

- Show the record and placement ("1st · 9–0") as the headline, with the win
  rate secondary.
- Rank by placement within event tier by default, and offer win rate (with
  its record) as a sort option.
- Add Copy for Showdown and Use this team (P4) on every card.

### C3. Player pages (`#/player/<player_id>`), for opponent prep

- Search by player name (the same combobox as Pokémon search).
- Show every event in the selected regulation, with placement, record and
  the team they brought. Signature Pokémon come from the existing
  `player_signature_pokemon` mart.
- Show team-level results against archetypes where there's a sample,
  labelled team-vs-team.
- Show only what the source events published. Names appear as the sources
  spell them, and nothing is inferred beyond tournament data.

### C4. Shareable outputs

- Event windows: an "Event window" filter (whole regulation, since event X,
  last N events), so a reader can ask "what changed since Frankfurt". It
  was planned in Q4 B3 and not built. It needs per-event-date marts already
  partly present in `pokemon_usage_by_event_date`.
- Pre-rendered images: at build time, render team-card PNGs for each new
  event's top 8 with the existing `pipelines/render/`, and a "What changed"
  summary card. Each image gets a download button.
- An Open Graph image and description for the site, refreshed on each build,
  so links unfurl with the current regulation's headline.
- "Copy with citation" on tables: copies the rows as text with
  "Source: Pokémon Champions Data Platform, dataset X, n = Y teams, <url>".
- A "What changed" baseline label (finding 6): show the comparison
  regulation's team and event count beside the heading. Below a threshold,
  offer "early vs recent events in this regulation" as the default
  comparison instead.

---

## Track D — Data access and operations

### D1. Publish 0.4.0 without growing git (Q4 A7, unblocked)

Publish the release CSVs and images only as a GitHub Release asset (backlog
#33 already packages releases), and commit just the manifest and changelog
under `releases/`. Record that change to the release contract in
`docs/dataset-spec.md`. The changelog says pre-0.4.0 releases exclude M-B
and M-C events.

### D2. Data section for data consumers

- A per-table card: a description, row count, primary key, download link to
  the release asset, and the JSON shard path.
- A rendered data dictionary for the marts the site uses, generated from
  `dbt/models/marts/schema.yml` at build time so it can't drift.
- "How to read this page" (U4) lives here.

### D3. Regulation rollover playbook

A short section in `docs/dashboard.md` covering how to add the seed row,
what the drift alarm reports, what the site shows during the first week of
a new set (U3), and when to switch the "What changed" baseline. Do a dry
run before 2026-12-02 with a fixture M-D row.

---

## Sequencing

| Sprint (≈1 wk) | Scope | Exit criteria |
|---|---|---|
| **5 — Routable shell** | U1, U2, U3, U4 (copy cleanup), U8 (smoke test) | Back/forward and deep links work for every route. Content starts within 200px. The rollover fixture test passes. A browser smoke test runs in CI. |
| **6 — Real sets** | P1, U5 (Usage + Profile), U6, U7 | The profile shows real sets with copy. Usage is a sortable table. No 18-chip filter remains. |
| **7 — Events and teams** | C1, C2, P5, D3 dry run | Every event has a page. Top Teams leads with the record. Starter teams sit on Meta. |
| **8 — Build and share** | P2, P3, P4, C4 | Calculator presets, saved and shared teams, event-window filter, pre-rendered cards. |
| **9 — Players and data** | C3, D1, D2, U4 (glossary) | Player pages, 0.4.0 published, and the data dictionary on the site. |

Sprint 5 lands before 2026-12-02 because U3 has to be in place when M-C
ends. Sprint 7 should land before the next major event so its event page is
the first one people see.

## How we'll know it worked

The site is static and has no analytics, so measure what we can and decide
whether to add more:

| Area | Signal | How to measure |
|---|---|---|
| Sets | A Pokémon set is copied within two interactions on a phone | Playwright task script in CI (U8) |
| Citations | Every number on an event page has `n` and a deep link | Lint test over rendered HTML: percentages carry a `title` or `data-n` |
| Copy | No unexplained jargon | Test that each glossary term in rendered text is wrapped in the tooltip component |
| Releases | A release exists for the current regulation | `releases/manifests/` has a manifest whose newest event falls in the regulation in force |
| Rollover | Rollover needs only a seed row | U3 fixture test plus the D3 dry run |

**Open decision:** whether to add privacy-respecting, cookie-free page
analytics (e.g. GoatCounter) to measure real use. It's not needed for any
item above. Without it, the "3 recurring downstream consumers" metric in
`docs/prd.md` stays unmeasured.

## Risks

| Risk | Mitigation |
|---|---|
| The P1 full-set mart fragments into thousands of one-off sets | Rank by team count with a minimum `n`, and add the looser "core set" grouping. Show the top 3 only. |
| The routing rewrite (U1) breaks existing shared links | Redirect old `#tab` hashes, and cover both forms in the smoke test. |
| Player pages (C3) surface people's names more prominently | Show only fields the public sources publish, link each row to its source, and add no cross-source enrichment. |
| Event pages for small events have tiny samples | Show `n` everywhere, and hide over-/under-performer deltas below a minimum team count, the same rule as the movers mart. |
| The next regulation adds forms PokéAPI doesn't model | Same as the Z-Mega precedent: an explicit mapping-seed decision, never a guess. |

## Proposed `todo.md` entries (on acceptance)

- [ ] Routing: pushState + popstate, full view state in the hash, legacy `#tab` redirects (U1)
- [ ] Compact sticky header; status pills to footer; drop duplicate panel headers; events/teams KPI (U2)
- [ ] Regulation-in-force beats a stale remembered choice; thin-new-regulation fallback; rollover fixture test (U3)
- [ ] Copy pass, glossary tooltips, denominators on every percentage (U4)
- [ ] Shared sortable table component, adopted in Usage, Profile, Speed Tiers, Cores, Players (U5)
- [ ] Type filter popover (U6); mobile sub-tab scroll cues, import moved to Builder (U7)
- [ ] Playwright route smoke test + payload budget in CI (U8)
- [ ] `pokemon_set_variants` mart and real-set tabs on the profile (P1)
- [ ] Pokémon hub v2: per-regulation trend, featuring teams, teammates, meta pressure (P2)
- [ ] Calculator presets from real sets; "vs the meta" mode (P3)
- [ ] Builder: use a real team, saved teams, share link (P4); starter teams strip (P5)
- [ ] Event pages and `pokemon_event_usage_vs_regulation` mart (C1)
- [ ] Top Teams: record/placement headline, placement ranking, copy actions (C2)
- [ ] Player pages (C3)
- [ ] Event-window filter, pre-rendered share cards, OG image, copy-with-citation, labelled baseline (C4)
- [ ] Publish 0.4.0 as a Release asset; update the release contract (D1)
- [ ] Data section table cards and a generated data dictionary (D2)
- [ ] Regulation rollover playbook and M-D dry run (D3)
