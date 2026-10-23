# Dashboard

M6's first-party analytics dashboard: a static site built from
`data/marts/*.csv` and published via GitHub Pages. This document covers
architecture and build/publish mechanics; see `docs/design-system.md` for
the dashboard's design tokens, component catalog, and Pokémon-
representation/naming/ordering conventions.

## Stack decision

`docs/prd.md`'s open question ("Which dashboard tool stack and hosting
model should be used for Phase 1?") is resolved as: a static
HTML/CSS/vanilla-JS page — Jinja2-rendered, no charting library, no
backend, no build tooling (no npm, no bundler). An earlier version of this
page used Chart.js (CDN-loaded) for its bar charts; the broadcast-redesign
pass replaced every chart with a dependency-free ranked-list component,
and the later competitive-UX redesign pass replaced *that* with a
dependency-free 6-wide grid (`docs/design-system.md`'s "6-wide grid"),
so there is no longer a charting-library dependency at all.

This was chosen because GitHub Pages only serves static files (no server),
which rules out a Python server-based dashboard (Streamlit, Dash, Flask)
for a zero-hosting-cost deployment, and because it's the lightest-weight
option that satisfies the PRD's KPI/trend/drill-down requirements. See
`docs/todo.md`'s M6 backlog item for a possible future dynamic
Python/Streamlit dashboard once the dataset has enough snapshots/trend data
to justify the added hosting complexity.

## Architecture

```
pipelines/dashboard/data.py       reads data/marts/*.csv, joins pokemon
                                   names, computes KPIs
pipelines/dashboard/sprites.py    copies Bulbagarden species sprites
                                   (keyed by pokemon_key) into output/images/
pipelines/dashboard/build.py      calls data.py + sprites.py, resolves
                                   type and item icons, copies
                                   pre-rendered Pro Team Gallery cards,
                                   renders templates/index.html.jinja with
                                   the payload baked in as inline JSON, and
                                   copies static/app.js + matchup.js +
                                   teams.js alongside it
pipelines/dashboard/templates/    the tabbed HTML/CSS template
pipelines/dashboard/static/       app.js (tab framework, .grid-6xn,
                                   Overview/Usage/Pokémon Profile/Speed
                                   Tiers/Players & Regions, shared helpers
                                   exported on
                                   window.DashboardApp), matchup.js
                                   (Matchup tab), teams.js (Team Builder +
                                   Top Teams tabs) — see
                                   docs/design-system.md's tab-registration
                                   note for how the three files share state
pipelines/dashboard/static/icons/ 18 committed move-type icon PNGs, also
                                   reused for the Pokémon-type badge/
                                   Matchup tab's type-effectiveness grid
data/reference_teams/             curated Pro Team Gallery specs + pre-
                                   rendered card PNGs (committed, see
                                   "Pro Team Gallery" below)
        ↓
docs/dashboard/index.html         generated output — committed to git
docs/dashboard/app.js
docs/dashboard/matchup.js
docs/dashboard/teams.js
docs/dashboard/images/            sprites + type/item icons + gallery
                                   cards — committed to git
```

Data is baked into `index.html` as `window.DASHBOARD_DATA = {...}` (an
inline `<script>` block) rather than fetched from a separate JSON file at
runtime. This is deliberate: `fetch()` of a local file is blocked by CORS
when `index.html` is opened directly via `file://` (no local server), and
inlining sidesteps that entirely while working identically once served
over `https://` by GitHub Pages.

Pokémon sprites, move-type icons, and item icons are copied/resolved into
`docs/dashboard/images/` as separate committed files rather than inlined as
base64 — the payload JSON is already large (hundreds of usage/build/move/
team-core rows), and base64 would add ~33% overhead across ~310 sprites,
bloating the one committed HTML file and making its diffs unreadable.
Separate PNGs keep diffs scoped to changed images and are browser-cacheable
across page loads, mirroring the `releases/data/<version>/images/` pattern
used by release packages.

The dashboard degrades gracefully in several ways:
- If `data/marts/*.csv` files don't exist yet (before `make dbt-build` has
  run), each mart loads as an empty list rather than erroring — the page
  still builds, just with empty sections.
- If a Pokémon referenced by a mart has no Bulbagarden sprite yet (or
  `data/assets/bulbagarden/` isn't populated at all), `sprites.py` skips it
  with a warning rather than raising — the dashboard falls back to
  text-only Pokémon names wherever a sprite is missing.
- Item icons (see "Icon sources" below) are resolved best-effort over the
  network; an unresolved or unreachable item icon degrades to a text-only
  item name, never a build failure.
- If `data/reference_teams/` doesn't exist yet, the Pro Team Gallery
  renders an empty-state message rather than erroring (see "Pro Team
  Gallery" below).

## The 2027 Q2 cycle ("Broadcast grade")

`docs/upgrade-plan-2027q2.md` made the site read like the official
competitive graphics and work on every screen. What changed, by sprint:

**Sprint 10 — the board, on every screen.**

- **Team share is the headline metric** (V1, decision D5). Every usage
  figure is the share of *teams* that brought a Pokémon (Rillaboom: 1,958
  of 3,770 M-C teams, 51.9%), the unit the official usage card,
  Pikalytics and Smogon report, instead of the share of roster slots
  (8.7%). The marts carry `team_share` beside `usage_share`; every
  tooltip still shows the slot share, and the Overview announces the
  change once. The Tier List's bands moved with it (S ≥ 24%, A 12–24%,
  B 6–12%, C 3–6% of teams: the old bands times six).
- **The Top 12 board** (V2) opens the Overview: six tiles, a title band
  and six more, as on the official card, with hero art breaking each
  tile's edge and the team share in gold display numerals. It reflows to
  band-on-top with 4 columns on tablets and 3 on phones, and has a
  Species / Forms toggle (Species folds each Mega into the Pokémon holding
  its stone, as the official card does). It renders from the inline KPIs
  (`top_12_boards`), so it needs no fetch; the KPI strip moved below it.
- **Responsive matrix** (M1, M2, Q1). `tests/browser/
  test_responsive_matrix.py` opens every route at 360, 390, 768, 1024 and
  1440px plus three spot checks and fails on horizontal scroll, sub-44px
  tap targets, sub-16px fields and oversized sticky chrome; CI uploads a
  screenshot of every route at every width. It caught both review
  findings: the profile 34px too wide on phones, and every route 39px too
  wide from 721px to 807px.
- **Stat Points** (Q2). Speed Tiers, the calculator and the glossary use
  Champions' terms: 32 Stat Points, Stat Alignment, IVs fixed at 31.
- **Broadcast tokens and a display font** (V7, D4). The board's palette
  is a set of design tokens with dark values, and `fonts/` serves one
  self-hosted display face, Oswald (OFL), as a 28KB Latin subset that
  `build.py` copies from `static/fonts/`. The footer says the site is an
  unofficial fan project.

**Sprint 11 — teams look like teams.**

- **Team strip** (V3). Every team is six square tiles with its held items
  and a Mega badge on the Mega holder; a tile opens its set. The
  Overview's winner strip reads the winner's sheet from the inline KPIs
  (`latest_event.winner_sets`), and the PNG team cards carry the same
  badges.
- **Player lines and scoreboard rows** (V4): "NAME [CC] [W–L]" chips on
  team cards, event headers and player pages.
- **Phase chips** (V5) on every team card and event section.
- **Square type badges** (V6) from our own glyphs
  (`pipelines/render/type_glyphs.py`), on the board and the PNG cards.
- **Mega usage panel** (E3): `mega_stone_usage` and `team_mega_count`
  (on-demand shards) behind the Usage tab's Megas view and a section on
  every event page. In M-C, 81.6% of teams carry two Mega Stones.
- Event and player pages open on a broadcast band.

**Sprint 12 — online events.**

- **Limitless online tournaments** (S1, `pipelines/extract/limitless_play.py`)
  are their own population: 13,418 published M-C sheets from 234
  tournaments in the first six weeks of M-C, against 3,770 official teams. They never blend
  into official figures by default.
- **Official / Online / All**: an Events select beside the regulation one.
  The scope is `regulation[:population]` (`?reg=m-c`, `?reg=m-c:online`,
  `?reg=m-c:combined`), the marts carry each scope as `regulation_scope`,
  and each ships as its own shard (`data/scope-m-c-online.json`). Official
  stays the default for every headline number and for "What changed".
- **Labels**: on an Online or All scope a blue population banner gives the
  sample and the way back; official-only views (event pages, players, Top
  Teams, head-to-head, archetypes, the event window, trends, triple cores)
  carry an "OFFICIAL" note and cite the official sample. The Top 12 board
  gains an Online switch on the official scope, beside "Official".
- **Rollover to Online**: when the regulation in force has under 300
  official teams but 300+ online ones, the page opens on its online events
  with the rollover banner saying so, instead of on the previous
  regulation. M-D will have data within days of 2026-12-03.
- **Events tab**: the online tournaments get their own list
  (`online_event_summary`), each linking to its page on Limitless; online
  events get no event pages and online handles no player pages.

**Sprint 13 — event weekend.**

- **Day 2 and the top cut** are read off RK9's round structure
  (`int_event_phases`): Day 2 starts at the first round with under half
  the tables of the one before, and the top cut is the trailing run of
  rounds where no loser plays again. The derived Day 2 fields match the
  players Limitless lists for Day 2 (Worlds 57 and 57, NAIC 156 and 156);
  `assert_day2_matches_limitless_lists` keeps checking. The top cut admits
  everyone with a qualifying record and pads its bracket with byes, so a
  16-slot bracket often holds 13 players.
- **Day 2 conversion** (E1, `pokemon_event_phase_usage`): each event page
  shows field share against Day 2 share, and the Top 12 board gains a Day
  2 switch. In M-C, Kingambit converts at ×1.30. The ratio is held back
  where either side has under 100 teams.
- **Bracket and paths** (E2, `tournament_top_cut_matches`,
  `tournament_top_cut_paths`): one column per round from 1024px, round
  tabs below it; picking a player opens every round they played, Day 1 to
  the final. Team vs team, and labelled so.
- **Top 12 cards** (V8): see "Share cards and link previews" below; the
  default regulation's 16:9 card is now the Open Graph image.
- **Sharing from a phone** (M4): "Share" hands the 4:5 and 9:16 cards to
  the system share sheet where the browser can share files; "Download
  card" saves the 16:9 one everywhere. Copying on a touch screen confirms
  with a toast.
- **Event weekends** (E4): see "Event-weekend refresh" below.
- **RK9 identity fix**: a name and country two entrants share is no longer
  resolved to one roster (both Noah Gardners at Indianapolis 2026 had been
  credited to the one in the top 16), and only Masters pairings resolve.

**Sprint 14 — the ladder lens.** Smogon's monthly Showdown ladder
statistics (S2, decisions D2 and D3), a population of their own:
`static/ladder.js`, hooked into the Usage tab and the profile through
`App.extendTab`, reading three on-demand marts. Every view carries a
"Showdown ladder" label and none adds a ladder figure to a tournament one.

- **Ladder vs tournament** (`#/usage/ladder`, `ladder_pokemon_usage`):
  ladder usage against the same regulation's official tournament team
  share. From 768px a scatter on one square-root scale (the dashed
  diagonal is the same share on both; blue is played more on the ladder,
  red more at tournaments, grey within 2 pts; each dot a 44px target that
  opens the profile), and at every width two ranked lists, "Played more on
  the ladder" and "Played more at tournaments", which are the scatter's
  text equivalent and all a phone shows. Bo1/Bo3 and 1760+/All ratings
  switches. In M-C, Mega Raichu Y is on 12.5% of 1760+ ladder teams
  against 25.9% of official ones; Basculegion runs the other way, 20.6%
  against 15.0%.
- **Checks and counters** (`#/pokemon/<key>/counters`,
  `ladder_checks_counters`): the six opponents that most often KO the
  Pokémon or force it out, with the rate and n, "Show all" for twelve.
  The only Pokémon-vs-Pokémon signal on the site, labelled "Showdown
  ladder, from battle logs". All ratings on the Bo1 ladder, since Smogon
  publishes almost no pairs for 1760+ (see `docs/data-sources.md` §10).
- **Stat Point spreads** (`#/pokemon/<key>/spreads`,
  `ladder_stat_point_spreads`): the six spreads 1760+ Bo1 ladder players
  ran most, labelled "Showdown ladder; tournament sheets don't publish
  spreads". They never reach a tournament view, a set card or the Builder.
- Under "All regulations", the ladder views show the newest regulation
  with ladder data and say so; a regulation Smogon has no file for says
  that instead of showing an empty panel.
- **Profile header on phones**: the stat bars need 260px, which never fit
  beside the 128px hero at 360–480px, so the header was clipped by the
  panel's edge; it now wraps.
- **S4, checked and parked**: MunchStats shows the game's ranked Battle
  Data only in its rendered pages, not its published JSON (see
  `docs/data-sources.md` §4).

**Sprint 15 — quality and shell.**

- **Global search** (Q3, `static/search.js`): one box for Pokémon, players
  and events, opened by `/`, Ctrl/⌘+K, the header's search button from
  1024px or the ⋯ menu's Search below that (the narrower headers have no
  52px to spare). A full-screen sheet on phones, a 640px panel under the
  header from 768px. Pokémon search at once from the inline names; players
  (`player_index`) and events (`tournament_event_summary`) arrive with the
  first open. With an empty box it lists the last six picks.
- **Pokémon names in five more languages** (Q4): the ⋯ menu's "Pokémon
  names" select (English, 日本語, Español, Português, Français, Deutsch),
  remembered per browser; changing it reloads the page. The build inlines
  `localised_names` (four maps, the 350 Pokémon the marts mention, 11 KB
  compressed), and app.js swaps them into the name map and the inline KPIs
  before anything renders; shard rows take theirs from the map as they
  load. Numbers and copy stay in English, Portuguese uses the English names
  (the Brazilian games do), the PNG share cards stay English, and search
  matches the English name too. Search now keeps letters of any script, so
  a Japanese query works.
- **Offline at the venue** (Q5, `sw.js`): pages, scripts and data shards
  network first, images cache first, other origins untouched. `build.py`
  writes the worker with its precache list (the page, scripts, font, core
  shard and default regulation's shard) and an id hashed from them, the
  inline payload counted without its timestamp, so an unchanged rebuild
  keeps visitors' caches. Offline, a banner says the figures are the saved
  ones and when they were built. Browser tests block service workers unless
  a test is about them, since a worker answers requests `page.route()`
  means to intercept.
- **Rank change on Usage** (list #19): a Rank column with ▲/▼ against the
  regulation before its newest event, or, in an event window, before the
  window. Official events only; online and combined scopes show "—".
- **Builder legality** (list #22): item clause and species clause warnings
  above the slots (`form_species` gives each form's species, so Charizard
  and Mega Charizard Y clash), and a notice when a saved team loses Pokémon
  to a regulation change.
- **Board tiles at 481–720px**: the large-phone tier's four tiles are about
  106px wide, too narrow for the number and two type badges side by side,
  which spilled into the next tile; the phone layout (number on its own
  line, badges in the corner) now applies up to 720px. The responsive
  matrix gains a 481px spot check.

**Sprint 16 — Builder and views.**

- **Team sheet image** (list #21): the Builder's "Download team sheet
  image" draws an Open Team Sheet (each Pokémon's ability, held item and
  moves; no Stat Points or Stat Alignment, as an open sheet shows) on a
  1200×760 canvas and saves it as a PNG, names in the page's language,
  long ones shrunk to fit.
- **Ladder checks in the threat screen** (list #23): a column naming the
  team members among each common threat's twelve strongest Showdown ladder
  checks, with each one's rate and n in the tooltip; the note says it is
  ladder data. The threat list itself was sorted on a `usage_rank` the
  profile rows don't carry, so it listed arbitrary Pokémon (Mega Absol Z
  first); it now takes the 12 highest team shares.
- **Speed line** (list #24): on Speed Tiers, your Builder team (outlined)
  above a number line and the 16 most-used Pokémon below, all at max Speed
  investment, sprites stacked into lanes where they would overlap.
  "Tailwind on your side" doubles your team; "Trick Room" flips which end
  moves first. Phones get the same as a list in move order, speed ties
  marked. Without a saved team the Tailwind toggle is off and the note
  says why.
- **Archetype matchups** (list #30, `archetype_matchups`): decided official
  matches between the primary teams of the listed archetypes, a heatmap of
  the top ten from 768px (blue where the row wins, red where it loses,
  uncoloured near even and under 20 matches; the number stays in ink) and
  a select-and-list below. Team vs team, and labelled so.
- **Compare tray** (list #34): "Pin to compare" on every profile; up to
  four pinned Pokémon follow the visitor in a tray (a bottom sheet over the
  phone's bottom bar, a card from 721px) that opens Compare on them.
  Compare now takes two to four Pokémon, adding and removing columns.

**Sprint 17 — sources and distribution.**

- **"Watch on stream" links** (S5, E5): `tournament_top_cut_matches.vod_url`
  from the curated `featured_match_vods` seed puts a "▶ Watch on stream"
  link under a bracket match with a video (opens YouTube in a new tab).
  Five finals so far, each a dedicated Play! Pokémon upload checked for its
  title and channel; a match inside a day-long stream gets a row once
  someone has its timestamp (`docs/data-sources.md` §12).
- **Upcoming online tournaments** (list #31, `online_upcoming_events`): on
  the Events tab above the past online list, the next 14 days of Limitless
  online tournaments in the visitor's own time zone (named in the note),
  grouped by local day ("Today", "Tomorrow", then the date), each with its
  time, organiser, platform, registrations and whether registration is
  open, linking to Limitless. The list is a day old by the time it is read,
  so tournaments that have started are dropped in the browser. A row per
  tournament on phones, the registrations under the name.
- **Embeddable Top 12** (list #33): `embed.html`, a page for an
  `<iframe>` (`templates/embed.html.jinja`, its own ~20KB inline payload
  from `build.py`'s `_embed_payload`, no shards or app scripts). Query
  parameters choose the regulation (`reg`), board (`board=all|day2|online`),
  grouping, `view=grid|list`, name language and theme. Every view carries
  its citation (team share, the sample, the update date, "an unofficial
  fan project") and links back to the dashboard. The Overview board's
  "Embed" button gives the snippet for what it shows, with Copy and
  Preview. Twelve tiles fit the snippet's 480px height from 320px wide;
  outside its red frame the page is transparent.
- **Which four do they bring?** (S3, list #27; `ladder_bring_rate`,
  `ladder_lead_pairs`): under the Ladder view, a table of how often each
  Pokémon is on Showdown ladder teams, brought, led, and its side's win
  rate brought versus benched, from sampled replays; then the ten most
  common lead pairs with their win rates. A Pokémon under 30 complete
  sides is left out. Every profile's Counters panel opens with the same
  four figures for that Pokémon (a Mega reads its base Pokémon's, and says
  so). Labelled "Showdown ladder replays" and "not tournament data". The
  first sample has 522 Reg M-C battles (365 complete): Rillaboom is on 36.9%
  of ladder teams and brought 62% of the time, its side winning 53.9% with
  it and 46.5% without; the sample grows with each daily run. Rows under
  the 30-side floor aren't shipped.

## Tabs

**Navigation since the 2026 Q4 upgrade** (`docs/upgrade-plan-2026q4.md`,
B2): the views are grouped into five sections, each with its own row of
views. **Meta** has Overview, Tier List, Usage and Speed Tiers. **Pokémon**
has Profile, Compare and Matchup. **Teams** has Top Teams, Archetypes, Core
Explorer and Players & Regions. **Builder** has Team Builder, and **Data**
has Data & Sources. The section bar sticks to the top of the page, and on
phones it becomes a bottom navigation bar. The KPI strip shows on Meta
only. View buttons keep the `.tab-btn[data-tab]` contract, so scripts that
click a tab still work. Every Pokémon picker (Profile, Compare, Core
Explorer, Matchup) carries a type-ahead search with sprites
(`attachPokemonCombobox`), and `/` or Ctrl/⌘+K opens the global search
(Pokémon, players and events; `static/search.js`, 2027 Q2 Q3).

- **Tier List** bands Pokémon by team share in the selected regulation
  (S ≥ 24%, A 12–24%, B 6–12%, C 3–6% of teams), each with a win-rate chip coloured
  only when the 95% Wilson interval sits clearly above or below 50%.
  Clicking a Pokémon opens its profile.
- **Team Builder** gains **Suggested partners**: Pokémon with a synergy
  lift above 1 alongside the current picks in the selected regulation,
  ranked by how many picks they pair with, then by average lift, each with
  an Add button.
- **Profile** now shows base stats as bars against the legal pool's median
  and a **Most common set** card: the modal item, ability and nature
  (`pokemon_nature_usage`) and top four moves, each counted separately,
  with the sample size, a small-sample warning under 30 team sheets, and a
  "Copy for Showdown" button.

The notes below describe each view's contents from earlier passes. Where
they mention the Usage tab's Regulation filter, that filter has been
replaced by the page-wide Regulation selector.

The page is a single scrolling KPI row plus eight tabs (client-side,
vanilla JS — no routing library, no page reload). The competitive-UX
redesign pass removed Archetypes and Regulations, added Matchup and Top
Teams, and restructured every remaining tab around
`docs/design-system.md`'s "3-tier tab layout convention"
(filters → `.grid-6xn` → optional detail table); a later
**mart-wiring pass** (see "Marts wired in the mart-wiring pass" below)
added Players & Regions and extended four of the existing tabs:

- **Overview** — the Top 12 board (2027 Q2, V2; see above), then "What
  changed", the latest event and starter teams, and the KPI cards. (The
  old "Top 30" ranked list and the Top 12 `.grid-6xn` were removed — the
  Usage tab is the full leaderboard now.)
- **Usage** — tier/regulation/type/role/usage-%/speed filters, a
  `.grid-6xn` of usage-share leaders, a full Usage leaders table, then the
  same grid+table pattern again for Win rate leaders (with a
  minimum-recorded-matches filter), plus two more subtabs. The
  **regulation** filter (backlog #12) swaps the leaderboard's source from
  `pokemon_usage_summary` to `pokemon_usage_by_regulation`, whose share and
  rank are recomputed inside that regulation's own legal pool; picking one
  *disables* the tier select rather than silently ignoring it, because no
  source reports which regulation an event was played under, so the two
  dimensions can't be combined (see that mart's header). The **Success**
  subtab (backlog #8, `pokemon_placement_weighted_usage`) is the
  popular-vs-successful split: rank by top-cut (placement 1–8) share or by
  a continuous 1/placement weighting, each row carrying a Movement badge
  for how many places the Pokémon gains or loses versus its raw usage
  rank. The **Trends** subtab (backlog #29/#30) has a tournament-date
  filter over `pokemon_usage_by_event_date` and a `.grid-6xn`/table showing
  each Pokémon's usage share *change* versus the previous tournament date
  (▲/▼ badge, or a `NEW` badge for a Pokémon absent from that previous
  date) — this dashboard's dependency-free stand-in for a usage-over-time
  line chart, since it has no charting library.
- **Pokémon Profile** — a single Pokémon picker (sorted by usage
  relevance, not alphabetically) driving: a profile header (base stats,
  speed-tier badge, and now a type badge), then three separate `.grid-6xn`
  sections — **Items** (top 5), **Ability** (top 5), **Moves** (top 15) —
  each tile showing a PokéAPI `short_effect` description, replacing the
  old single combined item×ability build table. The Items and Ability
  sections each carry a **build-concentration** badge (backlog #14,
  `pokemon_build_concentration`) — Locked in / Semi-contested / Contested,
  from that mart's Herfindahl-Hirschman index over the same shares the
  grid below shows. **Team Cores** (most-frequent partners) keeps its own
  `.grid-6xn` section below those, now rankable two ways: raw
  co-occurrence share (`pokemon_team_core_usage`) or **synergy lift**
  (backlog #9, `pokemon_team_synergy`) — how much more often a pair
  appears together than their individual popularity predicts, ×1.0 being
  exactly chance.
- **Speed Tiers** — who actually moves first, under a selectable
  **scenario** (backlog #16, `pokemon_speed_tiers`): base stat, max
  investment (Level 50 / 252 EVs / beneficial nature / 31 IV — the
  documented convention, since no source publishes real EV spreads),
  +1-stage-or-Choice-Scarf (×1.5), +2-stages-or-Tailwind (×2), or
  scarf-under-Tailwind (×3). The grid, the Speed range filter and the
  new **Outruns** benchmark ("N of M shown Pokémon outrun 180 in this
  scenario") all follow the selected scenario's column, and the table
  shows every bracket side by side. The Blazing/Fast/Average/Slow badge
  (`docs/design-system.md`'s "Speed-tier badge") stays pinned to *base*
  speed on purpose: its thresholds are calibrated to the base-stat scale,
  so scoring a ×3 number against them would read "Blazing" for every row.
- **Matchup** *(new)* — pick an attacker and defender Pokémon: a type-
  effectiveness grid, a stats/setup/weather damage calculator with a
  curated item/ability toggle list, the pair's real head-to-head record,
  a **Matchup profile** panel per side (`pokemon_matchup_summary`: overall
  record plus best and worst opponent, both Wilson-chosen over a
  10-match minimum — this answers something even when the two picked
  Pokémon have never met), and a co-usage `.grid-6xn` (a teammate-pairing
  proxy, explicitly not a real matchup-outcome signal). See
  `docs/design-system.md`'s "Matchup" section for the full scope note and
  what mechanics are/aren't modeled.
- **Team Builder** — a fully client-side roster builder: search/sort/
  type-filter the legal pool, add up to 6 Pokémon, see each slot's stats/
  top ability/top-4-move picker, their speed order, usage/win-rate/speed
  averages, a Team Analyst screen for type coverage/shared weaknesses/common
  threats, and an "Export as pokepaste text" button (see
  `docs/design-system.md`'s "Team Builder"); the team persists to
  `localStorage` only, never sent anywhere. The analyst is deliberately a
  screening tool based on selected recorded moves and type mechanics, not an
  EV/IV or full battle simulator.
- **Top Teams** *(new)* — a pokepaste (Showdown-export-text) paste-in box
  that loads a team into Team Builder, a `.grid-6xn` leaderboard fed by the
  new `top_tournament_teams` mart (real MunchStats team data, ranked by
  win_rate), and the **Pro Team Gallery** (see below), moved here from
  Team Builder.
- **Players & Regions** *(new, mart-wiring pass)* — backlog #7's two marts,
  as two subtabs. **By region** (`pokemon_usage_by_country`): a country
  picker ordered by how much recorded data each country has, driving a
  `.grid-6xn`/table of that country's own most-played Pokémon by share of
  its picks. **By player** (`player_signature_pokemon`): a player picker
  and a "Most committed specialists" table. Both views cover a player's or
  country's *entire* recorded Champions history, not one event. Two
  data-shape constraints are handled explicitly rather than papered over —
  see "Marts wired in the mart-wiring pass" below.

Usage leaders, Speed Tiers, Pokémon Profile, Matchup, and Team Builder's
picker all pull from `data/marts/pokemon_champions_profile.csv` — a mart
(one row per currently-legal Pokémon, joining `pokemon_stat_champions`
with `pokemon` for type, `pokemon_usage_summary`, and
`pokemon_win_rate_summary`) purpose-built so these views don't have to
join multiple marts client-side.

Each tab's setup function still runs lazily on that tab's first activation
(`App.registerTab(tabId, fn)` in `app.js`, called from all three JS files)
rather than eagerly on page load — see `docs/design-system.md`'s note on
how Team Builder and Top Teams coordinate shared team state despite that
laziness (`ensureTeamBuilder()`).

## Marts wired in the mart-wiring pass

`pipelines/dashboard/data.py`'s `MART_FIELDS` had drifted well behind the
mart layer: eight marts that `dbt build` produces on every run were read by
nothing, so `docs/local-queries.md` was the only way to see their output.
This pass wired them all into views — `pokemon_placement_weighted_usage`,
`pokemon_usage_by_regulation`, `pokemon_build_concentration`,
`pokemon_team_synergy`, `pokemon_speed_tiers`, `pokemon_matchup_summary`,
`pokemon_usage_by_country`, and `player_signature_pokemon` (see "Tabs"
above for where each one landed).

Three marts stay deliberately unwired, and none of them is an oversight:
`stat_change_leaderboard` (backlog #17 — permanently all-zero until a
Champions rebalance happens, and a section that always renders empty is
worse than no section), `pokemon_archetype_usage`/`archetype_summary` (the
Archetypes tab was removed by explicit request — see "Removed tabs" below),
and `roster_source_agreement` (a MunchStats-vs-Limitless data-quality
check, which belongs in `reports/validation/`, not in a competitive
analytics view).

### Payload slicing

The whole payload is inlined into the committed `docs/dashboard/index.html`
(see "Architecture" above), so two of the new marts are cut down to their
dashboard-relevant slice in `data.py` (`MART_SLICERS`) before they get
there: `pokemon_team_synergy` keeps pairs seen on at least 5 teams, at most
12 partners per anchor; `player_signature_pokemon` keeps players with at
least 2 recorded teams and each player's top 6 picks. Both floors are the
same ones each mart's own header calls for — lift is unstable at low
`pair_team_count`, and a signature claim from a single recorded team is
weak evidence — so this is the analytically honest cut, not only a size
cut. The marts themselves stay complete for `docs/local-queries.md`'s
ad-hoc querying. Net effect on the committed HTML: 6.97MB → 8.18MB
(+17%) for eight new marts. Unsliced, `player_signature_pokemon` alone
would have added several MB more.

### Two data-shape constraints worth knowing

Both were found by checking the built page against real data, and both
would have shipped a misleading view if taken at face value:

- **A "signature" share is structurally capped at 16.7%.**
  `player_signature_pokemon.player_usage_share` is a Pokémon's share of the
  player's roster *slots*, and a Pokémon can appear at most once on a
  six-slot team — so a player who brought the same Pokémon to every team
  they ever fielded still reads as 16.7%, tied with everyone else who did.
  The Most-committed-specialists table therefore ranks and displays on
  share of the player's *teams* (`usage_count / player_team_count`, "3 of
  3 teams", reaching a real 100%), not on that capped share.
- **Two recorded teams is the meaningful bar, not three.** Only three
  Champions events exist anywhere, so three teams is the ceiling: measured
  against the real mart, 2,329 players have one recorded team, 358 have
  two, and exactly one has three. A `>= 3` floor left the entire By-player
  view showing a single player.

## Cumulative legal pool

`legality_summary_by_regulation.cumulative_legal_pokemon_count` (used by
the "Legal Pool" KPI card — the dedicated Regulations tab that also showed
this was removed in the competitive-UX redesign pass, see "Removed
sections" below) is a **naive union**: regulation B's cumulative count
includes every Pokémon legal in regulation A too, assuming regulation
codes sort lexicographically in release order. PokéBase (the sole source
of `legality_snapshot`) never publishes a removal signal — a Pokémon's
absence from a later regulation's snapshot isn't distinguishable from "not
yet observed" vs. "actually banned." This means the cumulative count can
only grow; if a Pokémon were genuinely banned in a later regulation, this
count would keep including it anyway. Treat it as an upper bound, not a
confirmed current pool.

## Archetype Explorer (removed)

The Archetype Explorer tab was removed in the competitive-UX redesign
pass (see "Removed sections" below) — this section is kept for history.
`pokemon_archetype_usage`/`archetype_summary` (still dbt-built, just no
longer loaded by the dashboard) were built from `dbt/seeds/
archetype_pokemon_map.csv` — a **curated, editorial** seed (named
competitive strategies like "Rain," "Trick Room," "Sun" mapped to their
member Pokémon), not derived from any extractor. This was an explicit
exception to this repo's "provenance is mandatory" convention, made
because no in-scope source publishes team-composition/archetype labels at
all — see `dbt/seeds/schema.yml`'s entry for the seed's editable format if
a future pass wants to reintroduce archetype context elsewhere (e.g. as a
Team Builder tag).

## Pro Team Gallery

A grid of real tournament teams, rendered as broadcast-style cards via
`pipelines/render/` (the same tool `render-card` uses standalone) and
shown for reference/inspiration in the **Top Teams** tab (moved here from
Team Builder in the competitive-UX redesign pass, alongside the real
`top_tournament_teams` leaderboard and the pokepaste importer — see
"Tabs" above) — distinct from, and not part of, Team Builder's own
roster-planner feature.

Cards are **pre-rendered ahead of time**, not generated at dashboard-build
time or in the browser: there's no Playwright dependency in
`build-dashboard` itself, keeping it fast and network-optional (same
`--no-fetch-icons` offline story as item icons). The workflow to add a
gallery entry:

1. Write a build spec at `data/reference_teams/specs/<name>.json` (the
   same ad-hoc JSON format `render-card --spec` accepts — see
   `pipelines/render/data_source.py`'s `load_from_spec` docstring — with
   optional top-level `player_name`/`country`).
2. Render it: `python -m pipelines.cli render-card --spec
   data/reference_teams/specs/<name>.json --output
   data/reference_teams/cards/<name>.png`.
3. Add an entry to `data/reference_teams/reference_teams.json`: `{team_id,
   player_name, country, event_name, placement, archetype_key,
   pokemon_keys, card_image}` — `pokemon_keys` (the 6 `pokemon_key` slugs)
   drives the gallery card's "Load into my builder" button;
   `card_image` is the filename from step 2, relative to
   `data/reference_teams/cards/`.
4. Commit the spec, the PNG, and the updated `reference_teams.json` — like
   `docs/dashboard/`, this is generated-but-committed content
   (`pipelines/dashboard/build.py`'s `_load_reference_teams` just copies
   the already-rendered PNGs into the published site).

**Known gaps, not code bugs**: `nature` on a gallery card built from a
hand-authored spec (rather than a real `team_id`) is only as complete as
what you write into the spec. (An earlier note here claimed MunchStats
reports Nature for only ~17% of entries. That was a measurement artifact,
now corrected: 17.2% is the *Champions share* of a corpus that also
contained standard VGC events. Within Champions events nature coverage is
100% — and `tera_type` is 0%, because the format has no Tera mechanic.
Standard VGC is the exact reverse. See
`dbt/models/intermediate/int_champions_roster.sql`.) Country
codes are two-letter (e.g. "US", "GB") per MunchStats's own format,
rendered as plain text — no flag-emoji/ISO-lookup table exists yet.

## Icon sources

Four distinct assets, four distinct strategies:

- **Species menu sprites** (312 Pokémon, 128x128): copied from the
  gitignored `data/assets/bulbagarden/` cache (populated by
  `python -m pipelines.cli extract bulbagarden`) via `pipelines/dashboard/
  sprites.py`'s `copy_sprites`, keyed by `pokemon_key` so `app.js` can look
  them up the same way it looks up every other Pokémon-keyed field. Purely
  a local file copy — no network access at dashboard-build time. These are
  the asset for the small slots (`--icon-sm`/`--icon-md`).
- **Hero art** (312 Pokémon, 512x512 source): PokéAPI HOME renders from the
  gitignored `data/assets/pokeapi_artwork/` cache (populated by
  `python -m pipelines.cli extract pokeapi`), downscaled to 256px WebP into
  `images/hero/<pokemon_key>.webp` by `sprites.py`'s `copy_hero_art` — the
  one build step that needs Pillow. These are the asset for the hero slots
  (`--icon-lg`/`--icon-xl`), where a 128px menu sprite was being upscaled
  and visibly blurred. Both kinds come from the same `pokemon_asset` entity
  (one row per `pokemon_key` per `image_kind`); see
  `docs/design-system.md`'s "Hero art vs menu sprite" for which slot gets
  which.
- **Move-type icons** (18, fixed): bundled as committed static assets under
  `pipelines/dashboard/static/icons/types/`: Bulbagarden Archives' 128px
  round Sword/Shield emblems ("File:&lt;Type&gt; icon SwSh.png", symbol
  only, no baked-in name), downloaded once and copied verbatim
  into `docs/dashboard/images/icons/types/` on every build. No network
  dependency — types never change.
- **Item icons** (open-ended, data-dependent): resolved for every distinct
  `item_name` in `pokemon_item_usage`, preferring `pipelines/render/
  bulbagarden_items.py`'s `ensure_item_icon_bulbagarden()` (Bulbagarden
  Archives held-item art: the 160px "File:Bag &lt;Item Name&gt; ZA
  Sprite.png" render first, then the SV render and the Dream World art,
  and only then the 24px "Bag &lt;Item Name&gt; Sprite.png" pixel sprite,
  which looks blocky once a tile scales it up) and falling back per-item to
  `pipelines/render/assets.py`'s `ensure_item_icon()` (PokéAPI community
  sprites) on a Bulbagarden resolution miss, so an item that used to
  resolve via PokéAPI never regresses to no icon. This is the one part of
  a dashboard build that needs network access. Pass `--no-fetch-icons` to
  `build-dashboard` (or `fetch_icons=False` to
  `pipelines.dashboard.build.build`) for an offline build — item names
  render text-only in that case.
- **Pokémon type icons**: the Pokémon Profile type badge and the Matchup
  tab's type-effectiveness grid reuse the same 18 committed move-type
  icons above (types and move-types share one 18-value namespace) — no
  new icon assets were needed to add Pokémon type display.

## Team-core drill-down

`dbt/models/marts/pokemon_team_core_usage.sql` closes a gap named in
`docs/prd.md`'s original scope ("Drill-down by Pokémon, team core, move,
and item usage") but never built until this pass: it self-joins
`tournament_team_member` on `team_id` to count how often each pair of
Pokémon appears on the same tournament team, restricted to the current
legal pool, mirrored into both anchor directions so either Pokémon in a
pair can be the drill-down's selected anchor.

## Building and viewing locally

```
make dashboard                     # runs dbt-build, then builds the site
# or, if data/marts/*.csv is already current:
python -m pipelines.cli build-dashboard
# offline (skips fetching item icons over the network):
python -m pipelines.cli build-dashboard --no-fetch-icons
```

**Serve it — don't open the file directly:**

```
python -m http.server --directory docs/dashboard
```

This used to work over `file://` too, because the entire payload was
inlined into `index.html`. It no longer is: the marts live in shard files
under `data/`, which `app.js` fetches on first use of a tab that needs them
(see "Payload split" below). A browser refuses that fetch
over `file://` as a cross-origin request, so a directly-opened page renders
its header, KPI row and Overview tab — all of which read the inlined
critical payload — and then shows an explanatory empty state on the deeper
tabs naming this command. The published GitHub Pages site is unaffected.

## Payload split

`index.html` carries only the **critical payload** inline
(`_CRITICAL_PAYLOAD_KEYS` in `build.py`): KPIs per regulation, provenance,
the sprite/hero-art/type-icon/item-icon maps, type colors, display names
(and their four localised maps, Q4), each form's species, reference teams,
the regulation registry and `mart_files`, about 60 KB compressed. Overview renders from it with no fetch.

The marts are split into **shard files under `docs/dashboard/data/`**
(`_write_mart_shards`, docs/upgrade-plan-2026q4.md B7). Once the marts
gained a `regulation_scope` partition, one `data.json` holding everything
reached 22 MB:

| File | Holds | Loaded |
|---|---|---|
| `data/core.json` | unscoped marts the common tabs read | first tab that needs marts |
| `data/scope-<scope>.json` | the selected regulation's rows of every scoped mart | with core, for the page's regulation only |
| `data/pokemon_head_to_head.json`, `data/pokemon_team_core_triple_usage.json`, `data/player_signature_pokemon.json` | the three largest unscoped marts | only by the tabs that read them (`registerTab(..., { extraMarts: [...] })`: Matchup, Profile and Core Explorer, Players & Regions) |
| `data/ladder_pokemon_usage.json`, `data/ladder_checks_counters.json`, `data/ladder_stat_point_spreads.json` | the Showdown ladder marts (S2), sliced to what the views show (`data.py`'s `_slice_ladder_*`), about 190 KB compressed together | the Usage tab (usage) and the profile (counters, spreads) |
| `data/ladder_bring_rate.json`, `data/ladder_lead_pairs.json` | Showdown replay bring rates and lead pairs (S3), Bo1 and Bo3 pooled | the Usage tab (both) and the profile (bring rate) |
| `data/online_upcoming_events.json` | upcoming Limitless online tournaments (list #31) | the Events tab |

The default M-C view downloads about 400 KB compressed in total, against
roughly 2 MB for the old single file.

The profile's move, item and ability tables repeat each move's type,
power, accuracy and effect text on every Pokémon's row, which once took the
core payload past its 500 KB budget (`tests/browser/`). `build.py`'s
`DETAIL_SPLITS` strips those columns from the shards and writes one row
per move, item or ability into core as `pokemon_move_usage_details`,
`pokemon_item_usage_details` and `pokemon_ability_usage_details`;
`mart_files.detail_joins` lists each join, and `ensureData`'s
`restoreDetails()` puts the columns back as the marts load, so views read
the marts as before.

`data.json` remains backlog #32's JSON feed. It holds every non-mart key
plus `mart_files`, the index of the shard paths, and together they are the
complete payload, still scriptable with `curl`/`jq` or a notebook without
re-running dbt. Since 2026-10 it no longer inlines the marts themselves.

Client side, `app.js`'s `ensureData(extraMarts)` fetches each shard at
most once and merges the loaded marts **into the existing `marts` object**
rather than reassigning it, because `matchup.js` and `teams.js` hold a
reference to that same object through `window.DashboardApp.marts`. Scoped
marts are narrowed to the page's regulation as they load. Tabs registered
with `{ needsMarts: false }` (only Overview today) skip the gate entirely.
A failed fetch forgets itself, so re-clicking the tab retries. A tab
registered by a later script (`matchup.js`, `expansions.js`, `teams.js`)
initialises on registration if the page opened on it via a `#tab` link.

## Publishing (GitHub Pages)

Unlike other pipeline output in this repo (`data/normalized/`,
`data/marts/`, `data/staging/` are all gitignored regenerated build
output), **`docs/dashboard/index.html`, `docs/dashboard/app.js`,
`docs/dashboard/matchup.js`, `docs/dashboard/teams.js`,
`docs/dashboard/data.json`, `docs/dashboard/data/` and
`docs/dashboard/images/` are committed to git.** They can be rebuilt by hand (`make dashboard`, then commit the
regenerated files including `images/`), and since 2026-10 a weekly
workflow also rebuilds them.

**Weekly refresh** (`.github/workflows/refresh-dashboard.yml`): every
Monday, and on demand, it restores the staging cache that
`scheduled-extraction.yml` fills, re-extracts PokéAPI and Bulbagarden (the
two sources whose image bytes the site needs), runs `make validate`, builds
the dashboard, and opens or updates an `automation/dashboard-refresh` pull
request. Nothing reaches `main` without review, and a failed release gate
stops the run before any PR is opened. Before this workflow existed the
published site went four months without a rebuild while its data aged out
of the current regulation. The repo needs "Allow GitHub Actions to create
and approve pull requests" enabled (Settings → Actions → General).

**Event-weekend refresh** (`.github/workflows/event-weekend.yml`,
docs/upgrade-plan-2027q2.md E4): hourly from Friday to Monday UTC it
refreshes MunchStats and asks `python -m pipelines.cli live-events` whether
an event is running or just over (from the day before its date to three
days after). If one is, it re-extracts RK9 (a live event's pairings and
rosters are fetched again rather than reused from the cache), runs every
release gate, renders the share cards, rebuilds the site and deploys it
straight to Pages. It commits nothing: the weekly pull request is still
how data reaches `main`, and the next push to `docs/**` redeploys from
`main`. With no live event, a run stops after the check.

**Regulation selector**: every regulation-sensitive mart is partitioned
by `regulation_scope` (each regulation plus `all`). The header's Regulation
dropdown chooses one scope for the whole page. Changing it reloads the page
with the new `?reg=` so links are shareable. Which regulation the page
opens on is described under "Regulation rollover playbook" below. The open
view and its state live in the URL hash (`#/usage/win-rate`,
`#/pokemon/garchomp`; see "Routes"). `static/app.js` narrows each scoped mart to the selected scope
once, as its shard loads (`applyRegulationScope`), so the tab code reads
`marts.<name>` exactly as before. Since Sprint 12 the scope can carry a
population (`m-c:online`, `m-c:combined`), picked with the Events select;
a mart with no rows for it (player records are official-only) ships the
official scope's rows instead, listed in `mart_files.official_fallback`,
and `App.regulationCode` is the regulation part for views that only read
official events. KPIs are precomputed per scope
(`kpis_by_scope`) and the template renders one KPI row per scope. Marts
without the column (head-to-head, triple cores, country, players) still
cover all Champions regulations.

**What changed panel**: the top of Overview compares the selected
regulation with the one before it (`pokemon_regulation_movers`, summarised
server-side by `summarize_movers` into risers, fallers and new arrivals).
If either side has fewer than 100 teams it shows only new arrivals and the
sample sizes.

**Staleness banner**: the page compares the newest tournament date in its
data (`kpis.latest_event_date`) with the visitor's own clock and the
regulation registry (`payload.regulations`). It shows a warning strip under
the header if the newest event predates the regulation in force today, or
is more than 21 days old. The check runs in the browser, not at build time,
so a site that stops being rebuilt still reports that it's stale.

What *is* automated (`.github/workflows/deploy-dashboard.yml`) is
*publishing* what's committed: a push to `main` touching anything under
`docs/` triggers a GitHub Actions job that uploads the `docs/` folder as a
Pages artifact and deploys it via `actions/deploy-pages`, rather than
relying on GitHub Pages' own branch-polling deployment (which is what
caused stale/inconsistently-refreshed live-site content before this
workflow existed). It can also be run manually via the Actions tab
(`workflow_dispatch`).

`docs/.nojekyll` is committed alongside the dashboard files so the
published site serves plain static files, without Jekyll trying to process
the generated HTML or the repo's other `docs/*.md` narrative files.

**Pointing GitHub Pages at Actions-based deployment is a manual step that
can't be done via git**: in the repo's GitHub Settings → Pages, set the
source to "GitHub Actions" (not "Deploy from a branch" — that's the older
mode this workflow replaces). Once set, every push to `main` that touches
`docs/` redeploys via the workflow above, and the dashboard is reachable at
`https://<owner>.github.io/<repo>/dashboard/` — for this repo, that's
https://lancettlim.github.io/pokemon-agent/dashboard/.

`docs/index.html` is a static redirect stub (meta-refresh + JS
`location.replace`, so it works with JS disabled too) that sends
`https://<owner>.github.io/<repo>/` itself to `dashboard/` — the site root
would otherwise 404, since nothing else lives at `docs/`'s top level.

**claude.ai artifact mirror**: the dashboard is also mirrored to a private
claude.ai artifact (https://claude.ai/artifact/Lfb9NxbaAwRkshcGCQ11wR),
which Claude Code sessions republish whenever they change dashboard code,
before pushing it. An artifact version holds at most 511 files and the
full site has about a thousand, most of them images, so `python -m
pipelines.cli build-artifact-site --output-dir <fresh dir>`
(`pipelines/dashboard/artifact.py`) builds a lighter copy: every sprite,
type icon, script and data shard, hero art only for the Pokémon on a Top
12 board (the rest fall back to their sprite), no item icons (items show
as names) and no share cards (the share and download buttons don't
appear). It also writes `<dir>.plan.json`, the page plus the files in
publish-sized batches (255 files and 64MB each). The rules for keeping it
current are in `CLAUDE.md`'s "Dashboard artifact".

## Regulation rollover playbook

A new regulation set (M-D after M-C ends on 2026-12-02) needs one change:
a row in `dbt/seeds/champions_regulations.csv`. Everything else follows
from the seed (CLAUDE.md's "Regulation registry").

1. **Add the seed row** as soon as the set is announced:
   `regulation_code`, `regulation_name`, the MunchStats format
   (`gen9championsvgc2026regmd`), the Limitless format (`m-d`), and the
   start/end dates. Run `make refresh` and commit the seed.
2. **If you miss it, the drift alarm says so.** MunchStats is extracted
   unfiltered, so a new `gen9champions*` format reaches staging the day it
   is indexed, and `assert_champions_formats_registered` fails naming the
   unregistered format (it reports, for example,
   `gen9championsvgc2026regmc`). It is a referential-integrity gate, so a
   release and the weekly refresh both stop until the row is added.
3. **What the site shows in the first weeks.** The page opens on the
   regulation in force on the visitor's date only once it has at least
   300 teams on record (`MIN_DEFAULT_SCOPE_TEAMS` in `data.py`, carried to
   the page as `min_default_scope_teams`). Before that it opens on the
   previous regulation with a banner: "Reg M-D started 2026-12-02. Not
   enough results yet; showing Reg M-C." Once M-D has any results, the
   banner adds "Switch to Reg M-D →". A regulation a visitor picked by
   hand is remembered only while the regulation in force is the same one
   it was picked under, so the October choice of M-C doesn't pin anyone
   to M-C in December. `?reg=` always wins. This runs in the browser
   against the visitor's clock, so a site built before the rollover still
   behaves correctly after it.
4. **When to switch the "What changed" baseline.** The panel compares the
   selected regulation with the one before it, and shows deltas only when
   both sides have at least 100 teams; below that it shows sample sizes
   and new arrivals only. In a new set's first weeks the previous set is
   the useful comparison, which the rollover default already gives. Once
   the new set passes 300 teams the page opens on it and the panel
   compares it with the set before; nothing needs switching by hand.
5. **Legality** arrives separately: PokéBase usually publishes the new
   legal pool before the first event. Until it does, the legal-pool KPI for
   the new set reads "—".

**Dry run (2026-10-19).** A fixture `m-d` row (2026-12-02 to 2027-03-03)
was added to the seed and the pipeline run end to end against real data:

- `dbt build` passed all 259 nodes with no other change; the Limitless and
  MunchStats format lists picked up `m-d` from the seed.
- The payload built for 2026-12-03 kept scopes M-A/M-B/M-C/all (no M-D
  events), opened on M-C, and reported M-D as the regulation in force
  with no legal pool yet.
- In the browser, with the clock at 2026-12-03, the page opened on M-C
  with the rollover banner.
- The one finding: the staleness banner also fired and repeated the
  rollover banner's point ("M-D began…, these figures describe an earlier
  regulation"). It now defers to the rollover banner during a rollover.
- Removing the M-C row made `assert_champions_formats_registered` fail
  naming `gen9championsvgc2026regmc`, as step 2 describes.

The fixture row was then removed. `tests/browser/test_regulation_rollover.py`
and `tests/unit/dashboard/test_data.py` keep the rollover cases under test
with the same fixture registry.

## Share cards and link previews

`python -m pipelines.cli render-share-cards` (`pipelines/render/
share_cards.py`, docs/upgrade-plan-2027q1.md C4) renders, with Playwright:

- the newest event's top 8 as team-card PNGs
  (`images/cards/<event_id>-<placement>.png`), each offered as "Download
  card" on its team card;
- a 1200×630 "What changed" card per regulation
  (`images/cards/whats-changed-<scope>.png`), using the same comparison the
  Overview opens on, offered as "Download summary card";
- the Top 12 board as a card (docs/upgrade-plan-2027q2.md, V8):
  `images/cards/top12-<regulation|event>-<key>-<all|day2>-<landscape|portrait|story>.png`
  at 1920×1080, 1080×1350 and 1080×1920, the portrait two in the phone
  board's layout. The default regulation and its events (newest eight)
  get every format; other regulations get 16:9 only and older events
  none, which keeps a rebuild to about forty cards. Each is quantized to
  256 colours (about 175KB). The board and event pages offer them as
  "Share" (4:5 and 9:16, through the Web Share API) and "Download card"
  (16:9);
- `images/cards/og.png`, a copy of the default regulation's 16:9 Top 12
  card (else its "What changed" card), used as the Open Graph / Twitter
  image.

It writes `images/cards/manifest.json`, which `build-dashboard` reads, so it
runs first: `make dashboard` and the weekly refresh workflow both do. The
build also writes `og:`/`twitter:` title and description tags from the
default regulation's headline ("Reg M-C: Rillaboom is on 51.9% of 3,770
teams from 5 events…"), so a shared link unfurls with
the current state. Without the manifest the site simply has no download
buttons and no preview image. The cards add about 9MB to
`docs/dashboard/`, replaced on each refresh.

## Routes

Every view has a route in the hash, and the hash holds its state, so Back,
Forward and pasted links all work (docs/upgrade-plan-2027q1.md, U1):

| Route | View |
|---|---|
| `#/overview`, `#/tiers`, `#/speed` | Meta views |
| `#/usage[/win-rate\|success\|trends\|megas\|ladder]?window=last-<n>\|since-<event_id>` | Usage and its sub-views, optionally over an event window; `ladder` is Ladder vs tournament |
| `#/pokemon/<key>[/abilities\|moves\|cores\|teams\|pressure\|counters\|spreads]` | A Pokémon's profile; `counters` and `spreads` are Showdown ladder data |
| `#/compare/<a>,<b>[,<c>[,<d>]]`, `#/matchup/<attacker>/<defender\|meta>` | Comparisons of two to four Pokémon; `meta` is the calculator's "vs the meta" mode |
| `#/teams[/converged]?tier=regional&sort=win-rate` | Top Teams |
| `#/events`, `#/event/<event_id>` | Event index (with upcoming online tournaments) and event pages |
| `#/cores/<key>[/triple]`, `#/archetypes` | Cores and archetypes |
| `#/players[/regions\|signatures]`, `#/player/<player_id>` | Find a player, players by region and signature Pokémon; a player's page |
| `#/builder`, `#/builder/team/<team_id>`, `#/builder/list/<team_list_id>`, `#/builder/add/<key>.<set>`, `#/builder/<key>.<set>,...` | Team Builder, loading a real team, a converged list, one added Pokémon, or a shared team |
| `#/data[/how-to-read\|tables\|dictionary\|sources\|gates\|images\|agreement\|history\|caveats]` | Data & Sources: the glossary, table cards, the generated dictionary and the release gates |

Moving to another view pushes a history entry; refining the current one (a
filter, a sub-tab) replaces it. Links from before routing (`#usage`,
`?tab=compare&a=..&b=..`) are rewritten to their routes on load.
`?reg=` in the query string stays the scope: a regulation, or a regulation
and population (`?reg=m-c:online`).

`embed.html?reg=<code>&board=all|day2|online&group=forms|species&view=grid|list&lang=<ja|es|fr|de>&theme=auto|light|dark`
is the embeddable Top 12 widget (list #33), a separate page rather than a
route; every parameter is optional.

## Data section: table cards and dictionary

Data → Tables and Data → Dictionary (docs/upgrade-plan-2027q1.md, D2) are
generated by `pipelines/dashboard/dictionary.py` during `build-dashboard`,
so they can't drift from what they describe:

- **Release tables** come from the newest `releases/manifests/manifest-*.json`
  (by version number), described from `dbt/models/normalized/schema.yml`.
  From 0.4.0 the download is the release zip named in the manifest's
  `package` block; earlier releases link the committed CSV.
- **Site data** and the **Dictionary** cover every mart the page serves,
  with descriptions, grain (the model's uniqueness test) and fields from
  `dbt/models/marts/schema.yml`. Fields are the ones the JSON shards
  actually carry, so the display-name columns shards drop are not listed.
  Payload entries `data.py` derives (`tournament_top_cut_teams`,
  `player_index`) are described in `DERIVED_DESCRIPTIONS`.

Both ship in one on-demand file, `data/data_dictionary.json`, fetched only
when the Data section opens. schema.yml's maintainer pointers ("See
data/normalized/…schema.json", "Written to data/marts/….csv") are stripped
from the text.

## Triple cores and detected archetypes

Pokémon Profile's Team Cores sub-tab now has two independent controls:
pair/triple core size and co-occurrence/synergy ranking. Triple rows come
from `pokemon_team_core_triple_usage`, where every six-member Champions
roster produces 20 canonical combinations. The mart retains the full result;
the dashboard payload applies a five-team support floor before rendering.

The **Archetypes** tab is a new experimental, sourced alternative to the
removed curated Archetype Explorer. Its pipeline is deliberately
interpretable:

1. triples with at least five teams and above-chance triple/average-pair
   lift become candidates;
2. candidates sharing two members consolidate under the strongest one-hop
   neighbour;
3. teams receive one primary assignment and at most one secondary assignment
   within 90% of the primary score;
4. the dashboard displays the top 24 groups that span at least two events
   and ten teams.

The UI uses neutral three-member core names. Weather, balance, offense, and
similar labels remain editorial judgments, not facts that can be inferred
solely from co-occurrence. The existing curated seed and drift check remain
in place as a comparison surface until additional events establish stable
generated clusters.

## Data-reality caveats

As of this writing:
- **Regulation filtering**: `regulation_code` values (`m-a`, `m-b`) are
  populated (via PokéBase), so the "Legal Pool" KPI card's
  `legality_summary_by_regulation` data is real and non-degenerate, even
  though there's no longer a dedicated tab surfacing per-regulation detail.
- **Cumulative legal pool**: see "Cumulative legal pool" above — can only
  grow, never confirmed to reflect a real later-regulation ban.
- **Curated Archetype Explorer**: remains removed. The replacement
  **Detected Archetypes** tab uses sourced Champions rosters and neutral
  core names; the curated seed remains only as a validation comparison.
- **Matchup tab**: type effectiveness and the damage calculator's type/
  move-power inputs are real PokéAPI data; the co-usage panel is an
  explicitly-labeled teammate-pairing proxy, not real battle-outcome data
  (see `docs/design-system.md`'s "Matchup tab scope").
- **Date-range/trend views**: still not buildable — only one
  `snapshot_date` exists in the data so far (see "Removed sections"
  below).

## Removed sections (as of this pass)

The stat-change leaderboard and legal-pool-trend-by-regulation sections
were removed from the page (see `docs/todo.md`'s dashboard refinement
plan): both were structurally built but permanently showed an
empty-state banner, since today's dataset has zero nonzero stat deltas
(no Champions rebalance has occurred yet) and only one `snapshot_date`
(nothing to trend against). Rather than ship two sections that always
render as "not enough data yet," they were cut until the underlying data
exists. `pipelines/dashboard/data.py` no longer loads
`stat_change_leaderboard` or computes degenerate-data flags; re-adding
these views once a rebalance happens and multiple snapshots accumulate is
a small, self-contained addition (reintroduce the mart load, the two
template sections, and their `app.js` render functions — see git history
for the removed code).

By contrast, the "Tabs", "Icon sources", and "Team-core drill-down"
sections above are additive against this same original scope: they cover
a PRD-named drill-down (team core) and refinement-pass backlog items
(mobile layout, richer imagery) that had real, non-degenerate data
available, unlike the two removed sections.

The (also since-removed) **Regulations** tab was a different thing from
the removed legal-pool-trend section, worth distinguishing historically:
legal-pool trend would have compared the *same* regulation across
multiple `snapshot_date`s (still degenerate — only one snapshot exists),
while Regulation Comparison compared *different regulations* within one
snapshot (real, non-degenerate data, since `m-a`/`m-b` are both populated
today) — it just wasn't kept, unlike the permanently-empty sections above.

## Removed tabs (competitive-UX redesign pass)

Unlike the stat-change-leaderboard/legal-pool-trend removal above (cut
because the underlying data was permanently degenerate), the **Archetypes**
and **Regulations** tabs were removed by explicit request even though
their data was real and non-degenerate — a scope/UX decision, not a
data-availability one. `legality_summary_by_regulation` still loads (it
feeds the "Legal Pool" KPI card); `pokemon_archetype_usage`/
`archetype_summary` and the `archetype_pokemon_map` seed are untouched at
the data/dbt layer, just no longer read by `pipelines/dashboard/data.py`.
See `docs/design-system.md`'s "Removed tabs and components" for the full
rationale, and `docs/todo.md`'s M6 backlog for the redesign pass this was
part of.
