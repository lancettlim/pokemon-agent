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
(`attachPokemonCombobox`), and `/` jumps to the Profile search.

- **Tier List** bands Pokémon by usage share in the selected regulation
  (S ≥ 4%, A 2–4%, B 1–2%, C 0.5–1%), each with a win-rate chip coloured
  only when the 95% Wilson interval sits clearly above or below 50%.
  Clicking a Pokémon opens its profile.
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

- **Overview** — the KPI cards plus a "Top 12" `.grid-6xn`, ranked by
  `usage_share`. (The old "Top 30" ranked list was removed — the Usage tab
  is the full leaderboard now.)
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
  `pipelines/dashboard/static/icons/types/`, bootstrapped once via
  `pipelines/render/assets.py`'s `ensure_type_icon()` and copied verbatim
  into `docs/dashboard/images/icons/types/` on every build. No network
  dependency — types never change.
- **Item icons** (open-ended, data-dependent): resolved for every distinct
  `item_name` in `pokemon_item_usage`, preferring `pipelines/render/
  bulbagarden_items.py`'s `ensure_item_icon_bulbagarden()` (Bulbagarden
  Archives held-item sprites, "File:Bag &lt;Item Name&gt; Sprite.png" and a
  couple of naming-variant fallbacks) and falling back per-item to
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
inlined into `index.html`. It no longer is: the marts are ~8MB and now live
only in the sibling `data.json`, which `app.js` fetches on first use of a
tab that needs it (see "Payload split" below). A browser refuses that fetch
over `file://` as a cross-origin request, so a directly-opened page renders
its header, KPI row and Overview tab — all of which read the inlined
critical payload — and then shows an explanatory empty state on the deeper
tabs naming this command. The published GitHub Pages site is unaffected.

## Payload split

`index.html` carries only the **critical payload** inline
(`_CRITICAL_PAYLOAD_KEYS` in `build.py`): KPIs, provenance, the
sprite/hero-art/type-icon/item-icon maps, type colors, display names and
reference teams — a few hundred KB. The marts go into `data.json` alone.

The reason is first paint. When everything was inlined, `index.html` was
**8.18 MB** and the browser had to parse all of it before rendering
anything; it is now **~140 KB**. `data.json` is still the *complete*
payload, not the leftovers — that preserves backlog #32's contract (the
data is scriptable via `curl | jq` or a notebook without re-running dbt or
scraping HTML) and costs only the few hundred KB of critical keys appearing
in both files, a rounding error against ~8MB of marts.

Client side, `app.js`'s `ensureData()` fetches `data.json` once, memoizes
the promise, and merges the loaded marts **into the existing `marts`
object** rather than reassigning it — `matchup.js` and `teams.js` hold a
reference to that same object through `window.DashboardApp.marts`. Tabs
registered with `{ needsMarts: false }` (only Overview today) skip the gate
entirely and render straight from the inline payload, so the landing view
never waits on a network round-trip. A failed fetch un-memoizes itself so
re-clicking the tab retries.

## Publishing (GitHub Pages)

Unlike other pipeline output in this repo (`data/normalized/`,
`data/marts/`, `data/staging/` are all gitignored regenerated build
output), **`docs/dashboard/index.html`, `docs/dashboard/app.js`,
`docs/dashboard/matchup.js`, `docs/dashboard/teams.js`,
`docs/dashboard/data.json`, and `docs/dashboard/images/` are committed to
git.** They can be rebuilt by hand (`make dashboard`, then commit the
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

**Regulation selector**: every regulation-sensitive mart is partitioned
by `regulation_scope` (each regulation plus `all`). The header's Regulation
dropdown chooses one scope for the whole page. It opens on the regulation
in force on the visitor's date (falling back to the newest one with data),
or whatever `?reg=` names, and changing it reloads the page with the new
`?reg=` so links are shareable. The open tab lives in the URL hash
(`#usage`). `static/app.js` narrows each scoped mart to the selected scope
once, as `data.json` loads (`applyRegulationScope`), so the tab code reads
`marts.<name>` exactly as before. KPIs are precomputed per scope
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
