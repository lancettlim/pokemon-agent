# Dashboard UX Design System

This is the design system for `pipelines/dashboard/` — the static
analytics dashboard described in `docs/dashboard.md`. It documents the
design tokens, component patterns, and Pokémon-representation/data
conventions the dashboard's HTML/CSS/JS (`templates/index.html.jinja`,
`static/app.js` + `static/matchup.js` + `static/teams.js`) implement, so
future additions stay visually and behaviorally consistent instead of
drifting per-tab. Where docs/dashboard.md
covers *architecture* (how the site is built and published), this document
covers *design*: what things look like, how Pokémon data is named and
ordered, and what a new component should reuse rather than reinvent.

This is a living document — when a new component or convention is added to
the dashboard, update this file in the same change.

## Design tokens

All tokens live as CSS custom properties on `:root` in
`templates/index.html.jinja`. Nothing in the stylesheet should hardcode a
color, spacing, or radius value that already has a token — add one instead.

### Color

| Token | Value | Use |
|---|---|---|
| `--navy` | `#16264d` | Primary text, borders |
| `--blue` | `#2b5cad` | Interactive accents (active tab, links, bars) |
| `--light-blue` | `#eaf1fb` | Subtle fills (empty states, table dividers, badge backgrounds) |
| `--muted` | `#5b6b8c` | Secondary text (labels, sub-text) |
| `--bg` | `#f4f6fb` | Page background |
| `--surface` | `#fff` | Card/section background |
| `--positive` / `--positive-bg` | `#1f8a4c` / `#e8f7ee` | Reserved for future positive-delta indicators (e.g. a stat gainer, once `stat_change_leaderboard` has real deltas — see "Removed sections" in `docs/dashboard.md`) |
| `--warning` / `--warning-bg` | `#a8710a` / `#fbf1e0` | Caution states; the Matchup tab's "not very effective" (0.5×) type-effectiveness tile |
| `--danger` / `--danger-bg` | `#b23434` / `#fbe9e9` | Destructive actions (Team Builder's remove button), Blazing speed tier, the Matchup tab's "4× weak" type-effectiveness tile |
| `--panel-dark` | `#12131a` | Broadcast color-block section/page header background (see "Broadcast color-block header" below) |
| `--accent-red` / `--accent-red-bg` | `#e3323c` / `#fce7e8` | Broadcast accent: active tab, `.grid-6xn` leader tile |
| `--accent-gold` | `#f4b942` | Broadcast accent: reserved for #1-rank/MVP highlighting |
| `--board-field` / `--board-field-ink` | `#ea0028` / `#84010c` | Broadcast (2027 Q2, V7): the Top 12 board's red field and the darker ink its CSS halftone and slashes are drawn in |
| `--board-surface` | `#fff` | The white board the tiles sit on |
| `--board-tile` / `--board-scrim` | `#7f2629` / `#572931` | A board tile's maroon, and the darker scrim under its number and name |
| `--board-gold` | `#ffc549` | The one number a board tile carries, and the band's regulation block |
| `--series-red`/`-blue`/`-green`/`-yellow` | `#e3323c` / `#2b6fd6` / `#2e9a4f` / `#f2c230` | A four-colour categorical palette (blue marks Online, green marks Ladder). A palette only: never drawn as the championship series' arc device |
| `--phase-chip` | `#111` | The phase chip's black |
| `--font-display` | Oswald (self-hosted) | The one display face (D4): board numerals and headlines only |
| `--type-<name>` (18) | see below | Per-type color, one per Pokémon type; fills the type pills only (see "Type colors") |
| `--type-unknown` | `#6B7280` | Fallback when a type is absent or unrecognized |

### Dark theme

Every color token above has a dark value, defined twice in
`templates/index.html.jinja`: under `@media (prefers-color-scheme: dark)`
for `:root:not([data-theme="light"])`, and under `:root[data-theme="dark"]`.
The header's Theme button cycles Auto → Light → Dark and stores the choice
in `localStorage` (`dashboard-theme`). A small inline script in `<head>`
applies it before first paint. `--navy` is the primary *text* token in
both themes (light text in dark mode), so text, borders and the stat-bar
median tick follow it automatically. Type colors are not redefined: they
are accents on borders and pills and read on both backgrounds. A new
component must use tokens for surfaces and text (`var(--surface)`, not
`#fff`) or it will glare in dark mode. White text on a colored fill (an
active pill, a primary button) is fine in both.

Keyboard focus always shows a 3px `--blue` ring (`:focus-visible`), and
`prefers-reduced-motion` turns off transitions and animations.

### Type colors

The 18 `--type-*` tokens are **not** authored in the stylesheet. They are
emitted into `:root` at build time from `pipelines/render/template.py`'s
`TYPE_COLORS` map — the same palette the team-card renderer already used —
via `build.py`'s `_type_colors()`, so the dashboard and the card renderer
are one palette rather than two that drift. To change a type's color, edit
`TYPE_COLORS`; do not add a literal hex here.

They fill the labelled type pills (the Pokémon Profile header's
`.type-pill-lg`) and nothing else. A color on its own never carries a type:
see "Type icons on Pokémon cards".

### Type icons on Pokémon cards

A card that stands for one Pokémon shows its type as one or two emblems
from `static/icons/types/`, primary type first, in the card's top-right
corner (docs/upgrade-plan-2027q1.md, U9). They replaced a 6px type-colour
bar down the left edge, which needed 18 colours memorised, was unreadable
to anyone who can't tell them apart, and confused close hues.

- Draw them with `typeIconsHtml(type_1, type_2)` in `app.js` (exported as
  `DashboardApp.typeIconsHtml`): a `.type-icons` span with
  `role="img"` and an `aria-label` such as "dragon / ground type", holding
  20px emblems that each keep a `title` for hover.
- Place them in the card's head row, in normal flow: `.grid-6xn-head`
  (the `#rank` badge left, emblems right) on `.grid-6xn-tile`, and
  `.slot-head` on Team Builder's filled slots. Never absolutely position
  them over the art.
- Every Pokémon-keyed `renderGrid6xn` grid gets them automatically, typed
  through `pokemon_champions_profile`; pass `typeFn` to read types off the
  row instead (the Overview, which renders before the marts load) or
  `typeFn: false` to opt out.
- A Pokémon with no type data shows no emblems; there is no placeholder.
- Where the types are already written out (the Profile header's pills),
  don't add emblems as well.

Speed-tier colors (`--speed-blazing`, `--speed-fast`, `--speed-average`,
`--speed-slow`, each with a `-bg` pair) are documented under "Speed-tier
badge" below rather than here, since they're paired directly with the
bucketing thresholds.

### Icon size scale

Four tokens (three plus one deliberate exception) replace what used to be
four ad-hoc pixel values scattered across the stylesheet/JS (40px KPI
sprite, 32px roster picker, 24px table cell, 22px chart axis):

| Token | Value | Use |
|---|---|---|
| `--icon-sm` | 40px | Table/list cells, `.grid-6xn` tiles, speed-order rows (`ICON_SIZES.sm` in `app.js`) |
| `--icon-md` | 64px | Roster picker rows, `.grid-6xn` tiles (`ICON_SIZES.md`) |
| `--icon-lg` | 96px | KPI hero sprite, team slot (`ICON_SIZES.lg`) |
| `--icon-xl` | 128px | Pokémon Profile's hero art only (`ICON_SIZES.xl`) |

**Every sprite/item/type image must use one of these tokens** (or the
matching `ICON_SIZES` constant in JS) — no other pixel value. `--icon-xl`
is a deliberate single-purpose exception, not a general-use size: it
belongs to the Pokémon Profile header's hero art, the one view whose whole
subject is a single Pokémon. Everywhere else still uses sm/md/lg.

It previously belonged to that header's *dual-type badge* instead. That was
wrong once real hero art existed: two 128px type emblems came out larger
than the Pokémon they described, so the subject of the page lost to its own
metadata. The badge dropped to `--icon-md` with a type-colored ring (see
"Type badge" below) and the token moved to the art.

**Sprites render at native resolution, smoothed, not pixelated.** Every
sprite-bearing element (`.kpi-sprite`, `.cell-icon`, `.grid-6xn-tile img`,
`.team-slot img`) used to force `image-rendering: pixelated` (a deliberate
"retro pixel art" look) — this was dropped, along with the tier bump
above, so the source art looks smooth rather than blocky.

### Hero art vs menu sprite

There are now **two** Pokémon image assets, and which one a slot gets is
decided by its size token, not by preference:

| Token | Asset | Helper |
|---|---|---|
| `--icon-sm` (40px), `--icon-md` (64px) | **Menu sprite** — Bulbagarden, 128×128, copied verbatim to `images/<pokemon_key>.png` | `spriteImg()` |
| `--icon-lg` (96px), `--icon-xl` (128px) | **Hero art** — PokéAPI HOME render, 512×512 downscaled to a 256px WebP at `images/hero/<pokemon_key>.webp` | `heroImg()` |

Both come from `pokemon_asset`, which carries one row per `pokemon_key`
**per `image_kind`** (`menu_sprite` / `home_render`) — see
`docs/dataset-spec.md`. This replaces the previous note here that no
higher-resolution source was wired up; one is now, as a gated dataset
entity with its own `>=95%` coverage gate, not a scraped extra.

The split is deliberate in both directions. Hero art exists because a
128px menu sprite upscaled into a 96px/128px box visibly blurs, and worse
on a HiDPI display where that box is 192–256 device px. Menu sprites stay
in the small slots because at 40px the 128px sprite is already
oversampled — swapping in a 256px render there would cost bytes for no
visible gain. **`heroImg()` falls back to `spriteImg()`** when a Pokémon
has no render, and to nothing when it has neither, so the
never-a-broken-image rule under "Representing Pokémon" still holds.

Every sprite/hero `<img>` carries intrinsic `width`/`height` plus
`loading="lazy"` and `decoding="async"` — with 300+ images on a page,
omitting the intrinsic size causes visible layout shift as they load.

### Spacing

A 4px base scale: `--space-1` (4px) through `--space-8` (32px). Prefer the
token nearest the ad-hoc pixel value you'd otherwise write.

### Radius

`--radius-sm` (6px, buttons/inputs/table containers), `--radius-md` (10px,
cards/sections/team slots), `--radius-pill` (999px, badges).

### Type scale

`--font-xs` (0.8rem, badges/sub-text) through `--font-2xl` (1.6rem, page
title). Body copy defaults to the browser's system font stack
(`-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`) — no
webfont, keeping the page dependency-free.

## Layout primitives

- **`header`** — page title + generation timestamp, centered, white text on
  a `--panel-dark` color-blocked background (the broadcast/esports theme's
  most visible landmark — see "Broadcast color-block header" below).
- **`main`** — centered content column, `max-width: 1100px`.
- **`.kpi-row`** — responsive grid of `.kpi-card`s (`auto-fit,
  minmax(200px, 1fr)`), always the first thing under the header.
- **`.tabs` / `.tab-btn` / `.tab-panel`** — client-side tab navigation
  (`app.js`'s `setupTabs`/`registerTab`). Every dashboard view beyond the
  KPI row lives in a tab, not a scrolling section — this was a deliberate
  M6 redesign decision (see `docs/todo.md`'s "Dashboard full redesign"
  entry) to keep the page scannable as views are added. Current tabs:
  Overview, Usage, Pokémon Profile, Speed Tiers, Matchup, Team Builder, Top
  Teams, Players & Regions, Data & Sources. Archetypes and Regulations were
  removed in the competitive-UX redesign pass (see "Removed tabs" below).
  Each tab's setup function is registered via `App.registerTab(tabId, fn)`
  and still runs lazily, on first activation — `app.js` owns the
  Overview/Usage/Pokémon Profile/Speed Tiers tabs directly, while
  `matchup.js` and `teams.js` (loaded right after `app.js`, sharing its
  helpers/data via `window.DashboardApp`) register Matchup and Team
  Builder/Top Teams respectively. Splitting the JS this way keeps any one
  file from growing unbounded as tabs are added.
- **`section` (`.tab-panel`)** — a bordered white card per tab, `h2` title
  rendered as a broadcast color-block header, optional `.controls` filter
  row, then content following the "3-tier tab layout convention" below.
- **`.subtabs` / `.subtab-btn` / `.subtab-panel`** — a compact pill row
  nested *inside* one top-level tab (`app.js`'s `setupSubTabs`), for
  several equally-important views that would otherwise stack vertically
  within one section. Deliberately lighter-weight than `.tabs` (a rounded
  pill row, not an underlined bar) so it reads as a sub-navigation, not
  another top-level tab strip — `.tabs` stays reserved for the page's
  nine main tabs. Three uses today: the **Usage** tab's Usage-leaders/
  Win-rate-leaders tables (previously two stacked `h2` sections), and the
  **Pokémon Profile** tab's Items/Ability/Moves/Team Cores (previously
  four stacked `.grid-6xn`s under separate `h3`s). Wired the same way as
  `.tabs`: buttons carry `data-subtab`, panels carry `data-subpanel`,
  matched by id, defaulting to the first button.

### 3-tier tab layout convention

Every tab panel (beyond the page-level KPI row, which is its own thing)
follows the same three tiers, top to bottom:

1. **Filters/mini-stats** — the `.controls` row: tier/type/role/range
   filters, a Pokémon picker, whatever inputs that tab needs. Not every
   tab needs this tier (Overview has none).
2. **`.grid-6xn`** — the primary visual, a 6-wide grid of ranked tiles.
   This is the tier that actually answers "what's the headline data here"
   at a glance.
3. **Detail table** *(optional)* — a full sortable `<table>` for raw
   drill-down beyond what the grid's top ~18 rows show. Only present where
   it adds something the grid doesn't: Usage keeps both a Usage-leaders and
   a Win-rate-leaders table, now as two `.subtabs` panels rather than two
   stacked sections (see "Sub-tabs" above); Overview has no table tier at
   all, since its job is the headline Top 12, not a full leaderboard
   (that's what the Usage tab is for) — this is also why Overview's old
   Top 30 ranked list was removed rather than converted to a grid.

Not every tab needs all three tiers — Pokémon Profile, Matchup, and Team
Builder are Pokémon/team-drill-down views built around a picker rather
than a leaderboard, so they use tier 2 (grids/tables) repeatedly without a
tier-3 table. Pokémon Profile's four tier-2 views (Items/Ability/Moves/
Team Cores) are sub-tabbed rather than stacked (see "Sub-tabs" above), so
only one is visible at a time.

## Component catalog

### KPI card

`.kpi-card`: a bordered white card with an optional `--icon-lg` (96px)
sprite, a `.label` (uppercase, muted, small), a `.value` (bold, large,
wraps rather than overflows for long names), and an optional `.sub`
(muted, small) for supporting detail like a percentage or date. Used only
in the top `.kpi-row` — don't reuse this class for in-tab summary stats;
use `.stat-summary-row .stat` instead (see Team Builder below), which is
denser and doesn't compete visually with the page-level KPIs.

### Leaderboard table

The recurring pattern for "top N Pokémon by some metric" (Usage leaders,
Win rate leaders, Speed Tiers): a
`<table>` inside `.table-scroll`, first column a `.badge.badge-rank`
(`#1`, `#2`, …), second column a `pokemonCell()`-rendered sprite+name,
remaining columns the metric(s). Columns with `<th class="sortable"
data-sort-key="...">` are click-to-sort (`makeSortableTable()` in
`app.js`, toggling ascending/descending, `▲`/`▼` indicator appended to the
active header) — every leaderboard table added since the broadcast
redesign uses this; a table's *default* order (before any header click)
is still descending by its primary relevance metric, per "Ordering
convention" below.

### Badge

`.badge`: a small pill (`--radius-pill`, `--font-xs`, bold). Two variants
today:
- `.badge-rank` — neutral blue-on-light-blue, used for leaderboard rank.
- `.badge-speed-*` — see "Speed-tier badge" below.

Add new badge variants as `.badge-<name>` with a token-backed color pair,
not one-off inline styles.

### Sprite / icon cell

`pokemonCell(pokemonKey, pokemonName)` (in `app.js`) is the canonical way
to render a Pokémon in a table cell: an `--icon-sm` (40px) sprite (from the
`sprites` map, keyed by `pokemon_key`) next to the display name, wrapped in
`.cell-with-icon`. `itemCell()` follows the same pattern for held items.
**Any new table or list that references a specific Pokémon should use
`pokemonCell()` (or `spriteImg()` directly for non-table contexts, as
Team Builder's roster list and team slots do) rather than rendering a bare
name** — see "Representing Pokémon" below.

### 6-wide grid (`.grid-6xn`)

`renderGrid6xn(container, rows, opts)` (in `app.js`) is the dashboard's
**only** data-visualization component, and the one every usage/win-rate
metric renders through — it replaced both Chart.js (removed in the
original broadcast redesign) and the ranked-list bar component that
redesign introduced (dashboard "replace usage/win-rate bar charts with a
6-wide grid just like Overview" ask; Overview's old Top-12 spotlight grid
became the template every other view now follows). Each `.grid-6xn-tile`
shows: an optional rank badge (`.badge-rank`, normal document flow and
left-aligned via `align-self: flex-start` — **not** absolutely positioned,
which would overlap the label whenever a tile has no icon), an optional
icon (`keyFn` → sprite lookup, or `iconFn` for a direct icon src like a
move-type or item icon), a label, a **bolded** headline value
(`.grid-6xn-value`, `font-weight: 800` — the "bold the percentage" ask),
and an optional `subFn` second line (a description, a sample-size note, a
secondary stat). The #1 tile gets `.is-leader` (`--accent-red` border/
text). Fixed 6 columns on desktop (`repeat(6, 1fr)`, not auto-fill/
auto-fit), with `minmax(0, 1fr)` tracks: 6 on desktop, 4 on tablets, 3
on large phones and 2 on phones (see "Responsive behavior").

Used by: Usage's usage-share and win-rate grids,
Pokémon Profile's Items/Ability/Moves/Team-Cores sections, Speed Tiers,
Matchup's co-usage panel, and Top Teams' leaderboard. Any new "top N by
metric" visual should use this — there is no other charting/ranking
component in the dashboard, and the old ranked-list component (`.ranked-
row`, `renderRankedList`) was deleted outright once nothing referenced it
anymore rather than kept "just in case." (`.ranked-value`, a small muted
inline-annotation style, survives on its own — the Win rate leaders
table's `(n=X)` sample-size note still uses it — but it's unrelated to the
deleted ranked-list row component now.)

### Team composition (`.team-comp`)

`teamCompositionHtml(pokemonKeys, sizePx)` in `app.js` renders a team as
the **six Pokémon it actually is** — a wrapping row of `--icon-sm` sprites
in `slot_number` order, each with the Pokémon's display name on a `title`
attribute. Fed the pipe-delimited, slot-ordered `pokemon_keys` string the
team marts publish (`top_tournament_teams`, `team_list_convergence`).

Reached through `renderGrid6xn`'s **`iconHtmlFn`** option, which supplies
arbitrary markup in place of the single `<img>` that `iconFn`/`keyFn`
produce. That option exists for this component.

This replaced rendering a team as its first slot's sprite alone, which was
a correctness problem rather than a cosmetic one — two teams sharing a lead
Pokémon were visually identical. A slot whose sprite doesn't resolve keeps
its place as a `.team-comp-blank` circle, so the composition still reads as
six. **Any new view that shows a team must use this** rather than picking
one representative Pokémon. The Pokémon *names* stay on the tile's
`subFn` line: sprites are scannable but don't name anything, and `title`
isn't reachable on touch.

### Broadcast color-block header

Section (`<h2>`) and page (`<header>`) titles are uppercase, `font-weight:
800`, `letter-spacing: 0.04em`, white text on a `--panel-dark` bar — this,
plus the `--accent-red`/`--accent-gold` accent tokens, is what gives the
dashboard its broadcast/esports look (dashboard "more Pokémon-like
features" ask). Deliberately **not** a webfont change — the effect comes
entirely from color-blocking and weight/case, preserving the
dependency-free-page convention "Type scale" above already established.

### Filter control

`.controls label` — a small-caps muted label wrapping a `<select>` or
`input[type=text]`. Selects default to `font-size: 16px` specifically to
prevent iOS Safari's auto-zoom-on-focus; keep that when adding new inputs
(see Team Builder's search box).

### Empty state

`.empty-state` — light-blue rounded box, muted text. Used for the
Overview tab's explanatory copy today; also the pattern to reach for if a
future view needs a "not enough data yet" message (see `docs/dashboard.md`'s
"Removed sections" — this is what the stat-change leaderboard and
legal-pool-trend sections would use if/when they're reintroduced).

### Buttons

`.btn` — bordered, `--radius-sm`, hover fills `--light-blue`. `.btn-primary`
is the solid-blue variant, used for a page's one clearly-primary action
(Top Teams' "Load into Team Builder" pokepaste-import button). `.btn-remove`
is a borderless text-only danger-colored button (Team Builder's per-slot
remove). `.btn-sm` is a compact size modifier (Team Builder's "Add"/
"Clear team"/"Export as pokepaste text" buttons).

### Speed-tier badge

Buckets a Pokémon's Champions-format base Speed stat
(`pokemon_champions_profile.speed`) into four bands, each rendered as a
`.badge-speed-*` pill. Thresholds live in `app.js`'s `SPEED_TIERS`
constant — **this table must stay in sync with that constant**:

| Tier | Speed range | Badge color |
|---|---|---|
| Blazing | ≥ 120 | danger red |
| Fast | 90–119 | warning amber |
| Average | 60–89 | blue |
| Slow | ≤ 59 | muted gray |

These bands are a display/UX bucketing of real Champions-format speed
data, not a separate data source — no new extraction or fabricated values
are involved. They're intentionally coarse (four bands) rather than
per-point tiers, since Champions' actual competitive speed-tier list
changes as the legal pool and rebalances change; the dashboard's job is to
make the real numbers scannable, not to assert a definitive competitive
tier list.

### Team slot / roster item

Two small, Team-Builder-specific patterns:
- `.team-slot` — a bordered card (filled, `--icon-lg` sprite) or dashed
  placeholder (`.empty`) representing one of the team's 6 roster
  positions. A filled slot's `.slot-detail` line shows its base stats,
  plus an item `<select>`, an ability `<select>`, and four move
  `<select>`s — a real build, not a read-only display — see "Team
  Builder" below for where that data comes from and how the selects are
  populated/capped.
- `.roster-item` — a horizontal row (`--icon-md` sprite, name,
  usage/win-rate/speed sub-text, Add button) in the scrollable "Legal
  pool" picker list, filterable by the type-filter chip row above it.

### Item / Ability / Move separation (Pokémon Profile)

The Pokémon Profile tab shows four separate views — one per `.subtabs`
panel (see "Sub-tabs" above), not stacked — instead of one combined
item×ability×move build table: **Items** (top 5, `pokemon_item_usage`,
`.grid-6xn`), **Ability** (top 5, `pokemon_ability_usage`, `.grid-6xn`),
**Moves** (top 15, `pokemon_move_usage`, a full sortable `<table>` — see
below), and **Team Cores** (`.grid-6xn`, teammate co-usage) — each capped
independently rather than sharing one table's row budget. The Items/
Ability grid tiles' `subFn` shows that item/ability's `short_effect`
description text (PokéAPI, joined in dbt — see `docs/dataset-spec.md`'s
`item_detail`/`ability_detail` entities).

**Moves is a table, not a grid** — real game mechanics need columns, not
tiles: Move (with its own type icon — `move_type`, real per-move data,
not a name-matched lookup, see "Removed: the move-types seed lookup"
below), Usage %, Category, Power, Accuracy, PP, Priority, and Effect
(`short_effect`), all joined from `move_detail` (PokéAPI) via
`pokemon_move_usage`, sortable via the same `makeSortableTable` every
other detail table uses. This replaced an earlier `.grid-6xn` tile
version that only surfaced name/usage-share/one line of effect text —
accuracy/PP/category/priority existed in the underlying data
(`move_detail`) all along but weren't selected into the mart or shown
anywhere.

**Removed: the move-types seed lookup.** Before this pass, a move's type
icon came from `dbt/seeds/pokeapi_move_types.csv` (a static name-matched
lookup, still used by `pipelines/render/`'s team-card renderer) via
`build.py`'s `_move_types_for()`/`payload["move_types"]`. Now that
`pokemon_move_usage` carries real `move_type` from `move_detail`
(PokéAPI, joined in dbt) for every move it lists, that duplicate lookup
path was deleted from the dashboard build entirely — `app.js` reads
`row.move_type` straight off the mart row.

### Default selection, not an empty state (Pokémon Profile)

The Pokémon Profile picker defaults to the highest-`usage_share` Pokémon on
tab open (`setupPokemonProfile()` in `app.js` sets `select.value` to
`sortedProfiles[0]` before its first `render()` call) rather than opening
on an empty "select a Pokémon" state. Decided, not an oversight
(backlog.md #34, which flagged this as an open call): every other tab in
this dashboard shows ranked content immediately on open — Overview's Top
12, Usage's leaderboard, Team Builder's legal-pool picker sorted by usage
— matching the "Ordering convention" section's descending-by-relevance
default throughout. A blank Profile panel on first load would be the one
tab that asks a visitor to act before showing them anything, breaking that
pattern for no real benefit. `.empty-state` still covers the case an
empty state actually serves: `render()` shows it if `chosenName` somehow
resolves to no matching profile row (e.g. a stale selection after the
underlying marts changed), not as the tab's default.

### Type badge

Pokémon type display (`pokemon.type_1`/`type_2`, sourced from PokéAPI —
previously nonexistent in this pipeline; see `docs/dataset-spec.md`'s
`pokemon` entity). `renderTypeBadgeRow(container, type1, type2, large)` in
`app.js` renders one of two variants, both reusing the 18 committed
move-type icons in `static/icons/types/` (the same icon set move types
already used — no new asset work). Both variants are **icon-only
emblems** — no visible type-name text — with the type name exposed via
`role="img"`/`aria-label` on the pill and a `title` attribute on the icon
itself, so the badge stays accessible/hoverable without a text label
cluttering it.

**The icons are square, text-free round emblems**: Bulbagarden Archives'
128px Sword/Shield set ("File:&lt;Type&gt; icon SwSh.png"), committed under
`static/icons/types/`. `typeIconImg()` is a plain `<img class="type-icon">`
at the requested size, with the type name on `alt`/`title`. The earlier
asset was PokéAPI's 200x40 "icon + type name" badge, which had to be
cropped to its left square and still showed the start of the baked-in
name at small sizes.
- **Compact** (`large=false`): `.type-pill`, an 18px type icon.
  Used in the Matchup tab's attacker/defender panels.
- **Large** (`large=true`): `.type-badge-lg .type-pill-lg`, an `--icon-md`
  (64px) icon in a 3px ring of that type's own `--type-*` color.
  Used once, in the Pokémon Profile header, beside the hero art. It was
  `--icon-xl` until hero art landed; see "Icon size scale" above for why it
  shrank and the token moved to the Pokémon.

The type-filter row (`renderTypeFilterChips`, Usage/Speed Tiers/Team
Builder) is **icon-only too**: one bare 32px emblem per
`.type-filter-chip` button, nine to a row, with the type name as the
button's `aria-label` and hover `title`. A picked type gets a navy ring;
once anything is picked, the row takes `.has-selection` and fades the
unpicked icons to 35% so the active filter reads at a glance. The
round, color-coded emblems are distinct enough to scan without a label,
and the text pills they replaced wrapped to five rows.

Not icon-only: the Matchup tab's type-effectiveness grid tiles keep their
visible type-name text. They are a lookup table, and every row must be
identifiable at a glance.

### Gallery card (Pro Team Gallery)

`.gallery-card`: a bordered card wrapping a pre-rendered team-card PNG
(`pipelines/render/`, see `docs/dashboard.md`'s "Pro Team Gallery"
section) plus a caption (player name, country, event, placement,
archetype tag) and a "Load into my builder" button that copies the
gallery team's Pokémon into Team Builder. Laid out in `.gallery-grid`
(`auto-fill, minmax(220px, 1fr)`). Moved to the **Top Teams** tab in the
competitive-UX redesign (previously lived inside the Team Builder tab) —
grouped there with the real `top_tournament_teams` leaderboard and the
pokepaste import box, since all three are "look at/import teams" features,
distinct from the roster-assembly tool Team Builder itself is. Still
visually and functionally distinct from Team Builder's own roster planner
and never itself called "Team Builder" — "Load into my builder" calls the
same `addToTeam`/`ensureTeamBuilder()` pipeline the pokepaste importer
uses (see "Team Builder" below).

### Routes and links (2027 Q1, U1)

Every view has a route, and the hash holds the whole view state:
`#/pokemon/<key>[/<view>]`, `#/compare/<a>,<b>`, `#/matchup/<a>/<b>`,
`#/teams[/<view>]`, `#/cores/<key>[/triple]`, `#/usage/<view>`,
`#/players/<view>`, `#/data/<view>`, plus the detail routes
`#/event/<event_id>` and `#/player/<player_id>`. `?reg=` in the query
string stays the regulation.

- Anything that names a Pokémon is a real `<a href>` to its profile:
  `pokemonCell()`, Pokémon-keyed `.grid-6xn` tiles, tier chips, mover rows
  and each slot of a `.team-comp`. Never attach a click handler that
  navigates where a link would do; middle-click and long-press must work.
- Moving to another view (a tab, a link, another Pokémon) adds a history
  entry. Refining the current view (a filter, a sub-tab) replaces it, so
  Back always means "the previous view".
- A sub-tab row passed `{route: {tab, argIndex}}` to `setupSubTabs` keeps
  its open sub-tab in the route; each button's `data-route` is its slug.
- A tab registers `onRoute(route)` with `registerTab`; it runs once the
  tab is ready and again on every Back/Forward while the tab is in view.

### Compact chrome (2027 Q1, U2)

One sticky 56px bar holds the brand, the five sections, the regulation
select and a ⋯ menu (theme, "How to read this page", Data). Provenance
(dataset version, snapshot, gate status) sits in a one-line footer. A
panel's own `<h2>` repeats its tab label, so it is `.panel-title`
(screen-reader only). Intros are one `.lead` sentence; the method goes in a
`<details class="method">` "How this is computed" disclosure. Content
starts within 200px of the top on desktop and 120px on phones.

### Data table (2027 Q1, U5)

`createDataTable(container, opts)` is the one component for ranked data,
replacing tall card grids wherever more than a top-N highlight is shown
(Usage, Profile items/abilities/moves, Speed Tiers, Core Explorer,
Players). Card grids remain for top-N highlights only (Overview, Tier
List).

- Columns are specs: `rank`, `pokemon` (sprite + name link), `share`
  (inline bar scaled to the column's maximum), `percent`, `int`, `text`,
  or a custom `render`. Numeric columns are right-aligned with tabular
  figures.
- Every percentage cell should pass `title(row)` with its denominator
  ("1,958 of 22,604 roster slots").
- The header is sticky under the bar and sorts on click or Enter; a row
  with `rowHref` opens what it describes when clicked anywhere but a link.
- On phones (≤600px) rows collapse to two lines: `main: true` columns on
  the first, the rest as labelled details on the second, with a Sort
  select in place of the header. `hideOnPhone` drops a column there.
- `limit` caps the first render with a "Show all N" button.

### Tooltip (2027 Q1, U4/U5)

Any element with `data-tip` shows that text in a bubble on hover, focus
and tap (a `title` never shows on a phone). `tipHtml(text)` renders a
small "i" button, used for item, ability and move effect text that used to
sit inline and make each row ~270px tall.

### Real-set card (2027 Q1, P1)

The profile's set card lists a Pokémon's top 3 real sets
(`pokemon_set_variants`) as tabs, each with its share and team count, and
an Exact/Core toggle: exact sets match item, ability, nature and all four
moves; core sets group item, ability and the three most common moves.
Moves are shown in the Pokémon's own move-usage order. Below 10 teams the
sample line says "Small sample". Copy for Showdown uses `setToShowdown()`
(no EV line: team sheets don't publish spreads).

### Type filter popover (2027 Q1, U6)

`renderTypeFilterChips()` renders one "Any type ▾" button that opens the
18-type multi-select and reads "Type · 2 selected" once types are picked.
It replaced an 18-icon row that took ~140px of each filter panel. Escape
or a click outside closes it.

### Scroll cues (2027 Q1, U7)

A horizontally scrolling tab row (`.tabs`, `.subtabs`) fades at whichever
edge has more to show, snaps to tabs, and centres the active tab without
scrolling the page. On phones every tab, sub-tab and chip is at least 44px
tall.

### Team card (2027 Q1, C1/C2/P5)

`teamCardHtml(team, opts)` draws a real team: placement and record as the
headline ("1st 15–2"), win rate secondary, the player (linked to their
page) and event (linked to its page), the six Pokémon as `.team-comp`
links, the sets behind a "Sets" disclosure, and actions: Copy for
Showdown, Use this team (`#/builder/team/<id>`) and, when a pre-rendered
image exists, Download card. Event pages pass `hideEvent`; converged lists
pass their own `headline` and `useHref`. Every team display on the site
(Top Teams, event top 8, starter strip, a profile's Teams, player pages)
uses it.

### Per-regulation trend (2027 Q1, P2)

The profile's "Usage across regulations" is a small inline SVG line of
usage share, one point per regulation with data, the selected regulation's
point in the accent red, with win rate and n under each. No charting
library: it's one `<polyline>` and labelled `<circle>`s with an
`aria-label` listing every value.

### Baseline toggle ("What changed", 2027 Q1, C4)

The Overview's "What changed" names its comparison with that baseline's
own size ("vs Reg M-B (1 event, 395 teams)") and offers "Early vs recent
events" within the selected regulation. A thin baseline (fewer than two
events, or under 300 teams) opens on early vs recent.

### Top 12 board (2027 Q2, V2)

The Overview's hero, after the official "Top 12 Pokémon" card
(docs/upgrade-plan-2027q2.md, R1). `renderBoard()` in `app.js` draws it
from the inline KPIs (`compute_kpis`' `top_12_boards`), so it paints with
no data fetch.

- **Layout.** A red `--board-field` with a CSS halftone frames a white
  board. On desktop, six tiles, a title band, then six more tiles. The
  band is first in the DOM (a screen reader hears the title and sample
  first) and placed on row 2 with `grid-row: 2`; the tiles flow around it.
  From 1023px down the band moves to the top, with 4 columns of tiles on
  tablets and large phones and 3 on phones. On phones the board is full
  bleed, so a tile is never narrower than 104px at 360px.
- **Tile.** Hero art (the 256px HOME render) breaks the tile's top edge;
  the team share sits in `--board-gold` display numerals on a darker
  scrim, the type emblems after it (top-right on phones) and the name
  under it. A form in parentheses shrinks, and on a phone moves to its own
  line; it is never cut off. Position is rank: the numeral is small and
  quiet, and the tile's `aria-label` says "1. Rillaboom, on 51.9% of teams
  (1,958 of 3,770 teams)". A tile links to the profile; the first six
  load eagerly, the rest lazily.
- **Band.** Three blocks: the title ("Top 12 Pokémon · by share of
  teams") on a `.broadcast-band`, the regulation and sample on gold, and
  the scope: a phase chip and the switches. The player-scope switch (All
  players / Day 2 / Online) shows only the scopes the build produced; the
  Species / Forms toggle folds each Mega into the Pokémon holding its
  stone (the official grouping) and is remembered per browser.
- **One number per tile.** Win rate, slot share and sample live in the
  tooltip, the profile and the Usage table, never on the tile.

### Team strip (2027 Q2, V3)

`teamStripHtml(slots, opts)` in `app.js` is every team on the site: Top
Teams, event top 8, player pages, Copy and play, the Overview's winner,
the Builder's preview, saved teams, and (as its own markup) the PNG team
cards. It replaced `teamCompositionHtml`, which drew sprites only and is
now a thin entry point onto the strip for cores and table cells.

- **Six square tiles**, the held item in a white circle at each tile's
  top-right corner: the item is the team, as in the game's battle UI and
  the broadcast (R2). There is no Mega badge; a Mega holder's name and
  sprite already say so.
- **A tile whose set is known opens it** on tap or click: a popover with
  the item, ability, Stat Alignment and moves, and a link to the profile.
  Without a set, the tile is a plain link to the profile.
- **One row of six**, up to 92px tiles on desktop, 76px on tablets and about
  45px on a 360px phone (team card grids bleed into the panel's padding
  there). A container query wraps the strip to 3 × 2 wherever a tile would
  fall under the 44px tap minimum.
- **Compact strips** (`opts.compact`, or `teamCompositionHtml` at 32px or
  less) draw 40-44px bordered tiles for table cells and saved-team rows,
  where the row is the tap target; they carry no badges. Every strip tile
  is bordered, compact or not.

### Type logo

A type is drawn one way everywhere: the round in-game emblem from
`static/icons/types/`, via `typeIconImg(type, size)` (`typeBadgeSquare` and
`typeIconsHtml(..., true)` now return the same emblem). The share-card and
team-card templates inline the same files through
`pipelines/render/type_glyphs.py`'s `square_badge_html`, so the site and its
PNG cards show one logo per type. The old square glyph badge is retired:
two logos for one type read as two different things.

Where a type is written out, use `typePillHtml(type)`: a pill in the type's
colour with the emblem (white ring) and the name, its text navy on a light
colour (electric, rock, fairy...) and white on a dark one. `TYPE_COLORS` is
sampled from the emblems themselves, so a pill, a tinted tile and a logo
are the same colour.

### Pokémon tile

A Pokémon's picture is never bare: `spriteImg()`, `heroImg()` and every
`pokemonCell()` draw it in a `.mon-tile`, a bordered rounded square on the
page's light fill, 25% larger than the size asked for so the art reads from
across the room. Items and abilities use the same shape (`thingTile()`),
so a picture slot is one shape throughout.

### Stat cards

`createCardGrid(container, cfg)` draws a grid of cards for a short list of
choices that each have a picture and a sentence of explanation: a Pokémon's
held items and abilities, and Mega Stones. A card holds the picture tile, the
name, the share as a big number and a bar, "N teams", and the description
in words. The most-picked card is outlined in gold; long lists show twelve
with a "Show all" button. Moves stay a table (several numbers per row), with
each move's description under its name.

### Population switch and banner (2027 Q2, S1) — retired from the dashboard

The dashboard shows official events only. `data.load_mart` drops every
mart row whose `regulation_scope` carries a population suffix
(`:online`, `:combined`) and returns nothing for `online_event_summary` and
`online_upcoming_events`, so the header's Official/Online/All select, the
population banner, the board's Online switch and the online event lists
never appear (the markup stays dormant, shown only when such data exists).
The marts and the release dataset still carry the Limitless online
tournaments; only the dashboard leaves them out.

### Top-cut bracket and path (2027 Q2, E2)

An event page's bracket (`.bracket`) is one column per round from 1024px
(`.bracket-round`, its title above evenly spaced matches) and round tabs
(a `.segmented` control) below it, one round at a time. A match
(`.bracket-match`) is two stacked sides, each a player button over the
team's compact strip, with W or L at the right; the winner's name is bold.
A top seed's bye is one side and an italic "Bye". The chip says how many
players made the cut ("13 PLAYERS"), the note how many seeds had byes.
Picking a player opens `.path-panel` under the bracket: every round they
played, as round number, a W/L/T/Bye badge, the phase chip and the
opponent's player line and strip. Both say "team vs team".

### Day 2 conversion (2027 Q2, E1)

A data table of field share, Day 2 share and conversion ("×1.30", green at
×1.10 and up, red at ×0.90 and down). The ratio shows "—" when either side
has under 100 teams, and the note says it is held back.

### Share controls and toast (2027 Q2, V8 and M4)

`App.shareCardControlsHtml(card, title)` renders "Share", only where the
browser can share files (it hands the 4:5 and 9:16 PNGs to the system
share sheet), and "Download card" (the 16:9 PNG) everywhere, both 44px
tall. The board puts them under its tiles, an event page in its header.
`App.showToast(message)` shows one line above the phone's bottom bar for
2.6s; a copy on a touch screen confirms with it, since there is no hover
feedback. It respects `prefers-reduced-motion`.

### Ladder lens (2027 Q2, S2)

Showdown ladder data is a population of its own, so every view of it opens
with a `.source-chip`, a blue pill naming the source ("Showdown ladder,
from battle logs"; "Showdown ladder; tournament sheets don't publish
spreads"). A ladder figure sits beside the tournament figure it compares
with and is never added to it.

- **Ladder vs tournament scatter** (`.ladder-svg`, 768px and up): ladder
  share of teams against official tournament share on one square-root
  scale, so the many Pokémon under 5% stay apart and equal shares stay on
  the dashed diagonal. One dot per Pokémon (r 5, a 2px surface ring),
  coloured by the gap: `--series-blue` played more on the ladder,
  `--series-red` more at tournaments, `--muted` within 2 pts (the pair
  passes the palette validator in light and dark). Each dot sits in a
  44px transparent target with a tooltip naming both shares, and links to
  the profile. The three widest gaps each way are named beside their dots,
  placed clear of each other. A legend sits under the plot.
- **Ladder lists** (`.ladder-list`, every width; all a phone shows): "Played
  more on the ladder" and "Played more at tournaments", ten each, among
  Pokémon on 2% of teams on either side. A row is the Pokémon link and
  the gap in pts, with "Ladder 20.6% · Tournaments 15.0%" under the name.
  They are the scatter's text equivalent.
- **Checks and counters** (`.counter-list`): rows of sprite and name, the
  KO-or-switch rate (tooltip: the encounter count and what the rate
  means) and n; two columns from 768px, one below. Six show, then "Show
  all".
- **Stat Point spreads** (`.spread-list`): nature in bold, the non-zero
  Stat Points ("32 HP / 32 Atk / 2 SpD"), the share, and a thin bar of the
  share under the row.

### Global search, name language, offline banner (2027 Q2, Q3–Q5)

- **Search sheet** (`.search-sheet`): an input over grouped results
  (Pokémon, Players, Events, six each), each row a sprite, flag or trophy,
  the name and a muted detail line; the active row is light blue. Arrow
  keys move, Enter opens, Escape closes and returns focus. Full screen on
  phones with the keyboard up; from 768px a 640px panel 64px from the top
  over a dimmed page. The empty state lists recent picks under "Recent".
- **Name language** is a labelled select in the ⋯ menu, never a flag.
  Localised names are names only: labels, numbers and copy stay English.
- **Offline banner** (`.offline-banner`) reuses the staleness banner and
  names the build date of the saved data.

### Builder warnings and rank change (2027 Q2, list #19 and #22)

`.builder-warnings` is an amber list above the Builder's slots, one ⚠ line
per broken rule (item clause, species clause), each naming the Pokémon.
Usage's Rank column reuses the rank-movement badge (▲ green, ▼ red, ±0)
with a "New" badge for a Pokémon absent before; its tooltip names the
baseline ("#5 before Louisville → #2 now").

### Speed line, matchup heatmap, compare tray (2027 Q2, list #24, #30, #34)

- **Speed line** (`.speed-line`, 768px and up): a navy axis with Speed
  ticks and a bold "Moves first" arrow at the end that moves first (it
  flips under Trick Room). Your team's 40px sprites sit above it with a
  blue ring, the most-used Pokémon below; a sprite that would overlap one
  already placed drops a 44px lane. Below 768px, `.speed-line-list`: rank,
  Pokémon link and Speed, with "Your team" and "Speed tie" chips on a
  second line.
- **Matchup heatmap** (`.archetype-heatmap`): rows and columns are
  archetypes as three 24px sprites; cells are the row's win rate in ink
  over a diverging tint (`--series-blue` above even, `--series-red` below,
  none within a couple of points or under 20 matches), the record in the
  tooltip. Phones get a select and a list. Always labelled team vs team.
- **Compare tray** (`.compare-tray`): pinned sprites with a small × to
  unpin, "Compare" (from two) and "Clear"; a full-width sheet over the
  bottom bar on phones, a 240px card bottom-right from 721px, and the page
  keeps room for it. The profile's "Pin to compare" is a toggle button.

### Segmented control (2027 Q2)

`.segmented` holds two to four mutually exclusive `<button
aria-pressed>`s (the board's scope and grouping, an event's round tabs).
Controls go inside a view's band, never in a new sticky row. On phones a
segmented control in a band fills its width and each button is 44px tall.

### Broadcast band (2027 Q2, V7)

`.broadcast-band` is a dark panel with a 115° slash in the field red and
gold and a white halftone, all drawn in CSS. It is our own pattern, not
the official key graphic, and heads the board's title block and the event
and player pages.

### Copy with citation (2027 Q1, C4)

Every data table has "Copy with citation": its rows in the current order
as tab-separated text, then "Source: Pokémon Champions Data Platform,
dataset X, Reg M-C, n = 3,770 teams, <url>" (an event page's tables cite
the event's own n).

### Removed tabs and components

The Archetype Explorer and Regulation Comparison tabs (and their
`.archetype-card`/`.archetype-grid` and regulation-comparison-table
markup) were removed outright in the competitive-UX redesign pass, per
explicit request — Archetypes were always curated editorial judgment
rather than sourced data (a documented exception to this repo's
"provenance is mandatory" convention), and Regulation Comparison's
cumulative-legal-pool caveat made it a lower-value tab than the rest.
`legality_summary_by_regulation` is still loaded (it feeds the page-level
"Legal Pool" KPI card), but has no dedicated tab anymore. `pokemon_
archetype_usage`/`archetype_summary` and the `archetype_pokemon_map` seed
are untouched at the data layer — only the dashboard's consumption of them
was removed — in case a future pass wants to reintroduce archetype context
elsewhere (e.g. as a Team Builder tag) without re-deriving the mapping.

## Representing Pokémon

Every dashboard view that names a specific Pokémon must show its sprite
alongside its name wherever there's room for one (table row, grid tile,
tooltip, team slot, roster picker row) — see "Sprite / icon cell" and
"6-wide grid" above. A name-only Pokémon reference should only appear where
space genuinely doesn't allow an image (e.g. a `<select>` option's text).
Sprites come from Bulbagarden Archives via `pokemon_asset.csv`
(`docs/dashboard.md`'s "Icon sources"); a Pokémon with no resolvable sprite
degrades to text-only, never a broken image.

### Pokémon name formatting: player-facing names

Display names are the names players use. They're derived from `pokemon_key`
(PokéAPI's form slug) by `pipelines/dashboard/data.py`'s `display_name()`:

```
charizard-mega-y          -> Mega Charizard Y
absol-mega-z              -> Mega Absol Z
basculegion-male          -> Basculegion ♂
ninetales-alola           -> Alolan Ninetales
tauros-paldea-aqua-breed  -> Paldean Tauros (Aqua)
landorus-therian          -> Landorus (Therian)
great-tusk                -> Great Tusk
farfetchd                 -> Farfetch’d
```

The rules: "Mega"/"Gigantamax" and regional adjectives go before the
species name; gender becomes ♂/♀; a Mega's X/Y/Z letter goes after it; any
other form descriptor goes in parentheses. A short override table handles
species whose slug drops punctuation (Mr. Mime, Porygon-Z, Flabébé).

This is computed once, server-side, when the payload is built
(`load_pokemon_names()`), so every consumer (KPI cards, every mart's
`pokemon_name` field, every `<select>` option) gets the same string.
`app.js` never reformats a name itself.

Two things worth calling out:

- The name comes from **`pokemon_key`/`form_name`, not the raw
  `pokemon_name` column** in `data/normalized/pokemon.csv`. That column is
  the species-only slug (`landorus` for both Landorus-Incarnate and
  Landorus-Therian), so using it directly would make a species' forms
  collide. `display_name()` uses it only to split species from form, which
  multi-word species (`great-tusk`) need.
- This **replaced the earlier PascalCase convention** (`CharizardMegaY`,
  `BasculegionMale`), as part of the 2026 Q4 upgrade
  (`docs/upgrade-plan-2026q4.md`, B1). Those names read as internal
  identifiers, and long ones broke mid-word in KPI cards.

### Ordering convention

Pokémon-keyed lists default to **descending order by their most relevant
ranking metric**, not alphabetical — usage share for usage-oriented views,
win rate for win-rate-oriented views, speed for the Speed Tiers view. This
applies to every Pokémon-keyed list in the dashboard: leaderboard tables,
ranked lists, Team Builder's "Legal pool" picker (sortable between Usage /
Win rate / Speed, all descending) — **and now every Pokémon-picker
`<select>` dropdown too** (Pokémon Profile's picker), via
`distinctSortedByMetric()` in `app.js`, which orders by descending
`usage_share`.

This supersedes an earlier version of this convention that kept plain
`<select>` dropdowns alphabetical for findability — the dashboard has no
alphabetical Pokémon lists anywhere now; the ranked order is treated as
more useful than alphabetical scanning even in a dropdown. Non-Pokémon
selects (tournament tier) are unaffected and keep `distinctSorted()`'s
natural/alphabetical order, since there's no usage-relevance ranking that
applies to a tier name.

### Percentages, not raw counts

**Usage is team share** (docs/upgrade-plan-2027q2.md, V1/D5): the share
of teams in scope that brought a Pokémon, `usage_count / scope_team_count`,
the unit the official usage card, Pikalytics and Smogon report. Every
usage tile, table, delta and share card leads with it (`team_share`,
`team_share_delta`, `event_team_share`, ...). The older share of roster
slots (`usage_share`, about one sixth of team share) stays in the marts
and in each figure's tooltip ("1,958 of 3,770 teams · 8.7% of roster
slots"), so a screenshot from before the change can still be reconciled.

The dashboard shows **percentages/shares, not raw counts**, wherever a
share metric exists (dashboard "focus on percentages" ask):
`pokemon_usage_summary.usage_share`, `pokemon_item_usage.item_share`,
`pokemon_ability_usage.ability_share`, `pokemon_move_usage.move_share`,
`pokemon_team_core_usage.partner_share` — all computed in dbt (a `sum(x)
over (partition by ...)` window function per mart), not client-side, so
shares stay internally consistent. `pokemon_item_usage`/
`pokemon_ability_usage` replaced the old combined `pokemon_build_usage`
mart (see "Item / Ability / Move separation" below) — same share-of-own-
total pattern, just split by dimension instead of one item×ability pair.
Raw `usage_count`, `total_wins`/`total_losses`, and `co_occurrence_count`
are no longer displayed anywhere in the UI (they still exist in the
underlying CSVs for ranking/testing purposes).

The one deliberate exception is **win rate's sample size**: hiding
`record_count` entirely risked a 100% win rate on a single recorded match
reading as more authoritative than a well-established Pokémon's 51% on
thousands of matches, so the Win rate leaders table and its `record_count`
filter (see below) keep a small `(n=X)` annotation next to the percentage
— a minimum-record-count filter, not a raw-count column. Base stats
(Speed, HP, Attack, etc. on the Pokémon Profile tab) aren't percentages
and are unaffected by this convention — they're numbers with no
"share of a whole" meaning to convert to.

### Filters beyond Pokémon/tier

Beyond the tournament-tier filter (Usage tab) and the **minimum recorded
matches** threshold (Win rate leaders table,
`#win-rate-min-record-count-filter`, options 5/10/20/50 — the same
`RECORD_COUNT_FLOOR` idea `compute_kpis()`'s KPI card already used, now
user-adjustable), the competitive-UX redesign pass added:

- **Type filter** (`.type-filter-row` + `renderTypeFilterChips()` in
  `app.js`): a row of 18 toggle chips, one per type, multi-select (a
  Pokémon matches if *either* of its types is selected — `App.
  passesTypeFilter()`). An empty selection means no filter. Present on
  Usage, Speed Tiers, and Team Builder's roster picker. Only possible
  because this pass added real Pokémon type data (`pokemon.type_1`/
  `type_2`) — see "Type badge" above.
- **Role filter** (Usage tab, `#usage-role-filter`): Physical / Special /
  Mixed, derived client-side from `App.roleByKey()` — a UX bucketing over
  each Pokémon's own recorded moveset's damage-category split
  (`pokemon_move_usage.category`, weighted by `usage_count`; status-only
  moves don't count toward either side), the same "derived bucketing, not
  a sourced attribute" treatment as `SPEED_TIERS`.
- **Range filters** (`.range-filter`, paired `<input type="number">` +
  `App.inRange(value, minEl, maxEl)`): usage % and Speed on Usage; Speed on
  Speed Tiers. An empty min or max on either side means unbounded on that
  side.
- **Tournament date filter** (Usage tab's Trends subtab,
  `#usage-trend-date-filter`, backlog #30): a plain `<select>` of every
  distinct `pokemon_usage_by_event_date.event_date`, most recent first and
  selected by default — not routed through `fillSelect()`'s usual "All"
  option, since an unfiltered/all-dates view doesn't make sense for a
  single-date usage snapshot.

The Archetype/Regulation-as-tabs pattern this section used to describe no
longer applies — both tabs were removed (see "Removed tabs and
components" above).

### Trend delta badge (Usage tab's Trends subtab)

Backlog #29's dependency-free stand-in for a line chart: rather than
reintroducing Chart.js (removed in the broadcast redesign, see "6-wide
grid" above), each Pokémon's row shows its `usage_share` change versus the
*previous* tournament date in `pokemon_usage_by_event_date` (not a fixed
time window) as a `.badge-positive`/`.badge-negative` pill (`▲ +2.1pp` /
`▼ -0.8pp`, reusing the existing `--positive`/`--danger` tokens — no new
color pair needed) or `.badge-new` (`--warning`-toned) when the Pokémon
has no row on the previous date at all. `.grid-6xn`'s `subFn` shows the
same label as plain text (escaped, so no colored badge there — grids only
support the two-line label/value/sub structure); the leaderboard table's
`Change` column renders the full colored badge. A Pokémon with no
*earlier* date to compare against (the very first tournament date on
record) shows neither — `usage_share_delta` and `is_new` are both
unset/false, which renders as `—`.

### Rank-movement badge (Usage tab's Success subtab)

The same two-token pattern as the trend delta badge, applied to a
different comparison: how many places a Pokémon moves between its raw
`pokemon_usage_summary.usage_rank` and its rank under
`pokemon_placement_weighted_usage`'s chosen weighting (`▲ +3` /
`▼ -2` / a neutral `.badge-rank` `±0`). Positive means results-weighting
*promotes* it — a quiet top-cut staple; negative means a crowd favourite
that underperforms. Computed client-side rather than in the mart, since it
compares two marts' ranks and the second one depends on which weighting
the user picked. As with the trend badge, `.grid-6xn`'s `subFn` shows the
plain-text version and the table column renders the colored pill.

### Build-concentration badge (Pokémon Profile)

Backlog #14's Herfindahl-Hirschman index (`pokemon_build_concentration`)
as a one-line label above the Items and Ability grids: **Locked in**
(HHI ≥ 0.5, `.badge-new`), **Semi-contested** (≥ 0.25, `.badge-rank`), or
**Contested** (`.badge-positive`), followed by the raw index and how many
distinct options were observed. The cut points are a UX bucketing
convention like `SPEED_TIERS`, not a sourced threshold. A Pokémon with
exactly one recorded option gets its own **Only one recorded** label
instead: an HHI of 1.0 across a single choice isn't a locked-in *finding*,
there was never a choice to make.

### Multiplier values, the one non-percentage headline

"Percentages, not raw counts" above has exactly one exception in a
`.grid-6xn` headline slot: Team Cores' synergy ranking shows lift as
`×1.9`, because lift is a ratio against chance with no whole to be a share
of — a percentage there would assert something false. The tile's `subFn`
carries the sample size (`74 shared teams`) for the same reason win rate
keeps its `(n=X)`: lift is noisy at low pair counts, which is also why the
dashboard only ever sees pairs at or above the floor documented in
`docs/dashboard.md`'s "Payload slicing".

### Scenario select (Speed Tiers)

A `<select>` that changes *which column* a whole tab reads, rather than
filtering rows: Speed Tiers' scenario picker swaps between
`pokemon_speed_tiers`' base/max-investment/×1.5/×2/×3 columns, and the
grid, the range filter and the Outruns benchmark all follow it so the tab
is never showing two units at once. Distinct from the range and chip
filters above, which narrow a fixed column. When adding one: keep any
derived badge pinned to the column it was calibrated for (the speed-tier
badge stays on base speed — see `docs/dashboard.md`'s Speed Tiers entry),
and say in the tab's `.sub` copy which unit is on screen.

## Team Builder

A fully client-side (no backend, nothing uploaded) roster-assembly tool
(`setupTeamBuilder()` in `static/teams.js`, moved out of `app.js` in the
competitive-UX redesign pass alongside Top Teams — both need the same
`addToTeam` pipeline, see "Cross-tab team state" below), built on
`pokemon_champions_profile` (one row per currently-legal Pokémon with
Champions-format stats, type, and usage/win-rate). A visitor searches/
sorts/type-filters the legal pool, adds up to 6 to a team, and sees:

- their picks as filled **team slots** (empty slots shown as dashed
  placeholders). Each filled slot shows a compact stats readout
  (HP/Atk/Def/SpA/SpD/Spe) plus a real build, not just a read-only
  display: an **item `<select>`** (top 8 recorded, `pokemon_item_usage`),
  an **ability `<select>`** (top 5 recorded, `pokemon_ability_usage`), and
  **four move `<select>`s** (top 15 recorded pool, `pokemon_move_usage`,
  each excluding whatever the slot's other three move selects already
  chose so the same move can't be picked twice) — the "Team Builder
  move/item/ability selector" ask. Every select defaults to that Pokémon's
  top-recorded choice but is independently editable; `buildChoiceSelect()`
  in `teams.js` always keeps the slot's current value present as an option
  even if it falls outside the top-N cap (e.g. a pasted build), so editing
  or importing a team never silently drops what was chosen. There is
  deliberately no stat/EV/nature selector alongside these — see "Pokepaste
  import/export" below for why.
- a **speed order** list — their own picks, fastest-first, each tagged
  with its Speed-tier badge (see above) — the practical payoff of Team
  Builder and Speed Tiers pulling from the same
  `pokemon_champions_profile` mart: a team's speed order is just that
  mart filtered to the selected keys.
- a **summary row** (`.stat-summary-row`) of the team's average
  speed/usage share/win rate.
- a **Team Analyst** panel (`#team-builder-analysis`) with four screening
  cards, defensive pressure points, and a common-threat table. Coverage is
  computed from the slot's selected recorded damaging moves against the
  standard type chart; exposure is computed from the threat's recorded move
  types. It is intentionally labeled as a screening tool, not a battle
  simulator or an EV/IV recommendation engine.
- an **"Export as pokepaste text"** button (`#team-builder-export`) —
  see "Pokepaste import/export" below.

The team selection persists to `localStorage` (key
`pokemonChampionsTeamBuilder`) purely so a reload doesn't lose it — it is
never sent to a server or embedded in the published HTML; this stays true
to the dashboard's "static site, no backend" architecture
(`docs/dashboard.md`'s "Stack decision").

### Cross-tab team state

Team Builder's team array, `addToTeam`/`removeFromTeam`/`loadTeam`, and
all of its rendering live inside `setupTeamBuilder()`'s closure — but two
other places need to push Pokémon into that same team: the Pro Team
Gallery's "Load into my builder" button and Top Teams' pokepaste importer
(both now live in the **Top Teams** tab, not Team Builder — see below).
Since tabs initialize lazily on first activation, a visitor could open Top
Teams and paste a team before ever opening Team Builder, at which point
`setupTeamBuilder()` wouldn't have run yet. `ensureTeamBuilder()` (module-
scoped in `teams.js`, not exported on `DashboardApp`, since only
`teams.js`'s own two tabs need it) handles this: it lazily calls
`setupTeamBuilder()` on first use from *either* tab and caches the
returned `{ addToTeam, loadTeam }` handle, so team state is correct
regardless of which of the two tabs a visitor opens first.

## Top Teams

A new tab (dashboard "include top teams" ask) with three sections:

1. **Top Teams leaderboard** — `.grid-6xn` fed by the new
   `top_tournament_teams` mart (real MunchStats data: one row per
   `tournament_team` with a reported win/loss record, ranked by win_rate,
   with its full roster). Distinct from the Pro Team Gallery below it:
   this is sourced tournament data, not curated/hand-authored.
2. **Pro Team Gallery** (see "Gallery card" above) — moved here from Team
   Builder.
3. **Pokepaste import** (`.pokepaste-box`, `#pokepaste-input`/
   `#pokepaste-load`/`#pokepaste-status`) — see "Pokepaste import/export"
   below.

### Pokepaste import/export

"Do it like vgcpastes/pokepaste": since this is a static site with no
backend, there's no way to fetch an arbitrary URL client-side (CORS), so
"paste a link" means paste the plain-text **Showdown export format** —
the same text a visitor would paste into pokepast.es itself to create a
paste, not a URL.

- **Import** (`parsePokepaste(text)` in `teams.js`): splits the pasted
  text on blank lines into per-Pokémon blocks, reads each block's first
  line (`Species [(Nickname)] [@ Item]`, tolerating a `(M)`/`(F)` gender
  marker) plus its `Ability: ...` line and `- Move` lines, and resolves
  the species name to a `pokemon_key` by normalizing both sides (strip
  spaces/hyphens/periods/apostrophes, lowercase) and matching against both
  each `pokemon_key` and its display name. For example, Showdown's
  "Charizard-Mega-Y" matches the key `charizard-mega-y`, and "Mega
  Charizard Y" matches the display name. The pasted item/
  ability/moves are carried into that slot as-is (not just the species),
  so an imported team keeps its actual build rather than falling back to
  that Pokémon's top-recorded one. Unresolved species names are reported
  (not silently dropped) in `#pokepaste-status`, alongside how many
  Pokémon loaded.
- **Export** (`exportTeamAsPokepaste(teamSlots)` in `teams.js`): the
  reverse direction, for Team Builder's export button. Since the
  dashboard's display names ("Landorus (Therian)") aren't real Showdown
  syntax, export re-derives a hyphenated Title Case name
  from `pokemon_key` instead (`keyToShowdownName()`: `landorus-therian` ->
  `Landorus-Therian`) — closer to real pokepaste convention, and a
  deliberately different transform from the dashboard's own display-name
  convention (see "Pokémon name formatting: player-facing names" above, which
  every other view uses). Each exported Pokémon uses that slot's
  actual chosen item/ability/moves (whatever its selects currently hold,
  defaulting to but not fixed at the top-recorded pick — see "Team
  Builder" above), not an EV spread. EVs are omitted because **no source
  publishes them**: official team sheets carry ability, item, nature and
  moves and nothing more (see `docs/data-sources.md`'s Victory Road entry).
  Nature is available — it is reported for 100% of Champions roster slots —
  but is left out of the export for the same reason the builder has no
  nature selector: it is a per-slot choice this UI doesn't model.

Neither direction is guaranteed to produce syntax that round-trips through
Pokémon Showdown itself byte-for-byte — this is a "pokepaste-style"
convenience for moving a team in and out of this dashboard's own Team
Builder, not a full Showdown-format implementation.

## Matchup

A new tab (dashboard "add matchup tab like Smogon" ask,
`static/matchup.js`) with three sections, all keyed off an
attacker/defender Pokémon pair (`<select>`s populated from
`pokemon_champions_profile`, ranked by usage per the ordering convention):

1. **Type effectiveness** (`.type-effect-grid`): all 18 attacking types'
   multiplier against the defender's type(s), color-coded tiles
   (`type-effect-4x/2x/1x/half/quarter/0x`).
2. **Damage calculator**: attacker/defender stat-stage sliders (-6..+6,
   Atk/SpA and Def/SpD), a weather `<select>`, and a curated row of
   item/ability toggle chips (`.toggle-chip`, reused from nowhere else —
   this is the first multi-select toggle-chip UI in the dashboard). Result
   shown in `.damage-result`, bolded per the "bold the percentage"
   convention.
3. **Co-usage** (`.grid-6xn`, `pokemon_team_core_usage` filtered to the
   defender): who the defender is most often teamed with in real
   tournament rosters — an explicitly-labeled **proxy**, not a real
   matchup-outcome signal (see the in-tab disclaimer copy and the scope
   note below).

### Matchup tab scope (read before extending)

The 18×18 type chart, weather-boost multipliers (rain/sun boost/halve
same-type moves; sandstorm boosts Rock's Sp. Def, snow boosts Ice's Def,
both by 1.5×), the stat-stage multiplier formula, and the curated item/
ability toggle list are **hardcoded game-mechanics constants** in
`matchup.js`, not dbt/staging data — they're universal Pokémon mechanics,
not per-record facts needing provenance, the same treatment `app.js`'s
`SPEED_TIERS` bucketing already gets. Pokémon *type* and move *power/
accuracy/category* **are** real sourced data (`pokemon.type_1`/`type_2`,
`move_detail` — PokéAPI, see `docs/dataset-spec.md`), which is what makes
a real (if simplified) calculator possible at all — see the "Still a real
gap" note in `dbt/models/marts/schema.yml` for why this was previously
listed as not-buildable.

Documented simplifications, not silent approximations:
- Stats are computed at **level 50, IV 31, EV 252** on whichever
  offensive/defensive stat the chosen move uses (`statAtLevel50()`/
  `hpAtLevel50()` in `matchup.js`) — a "maximally invested" baseline on
  both sides, not each Pokémon's actual real-tournament EV spread. EVs are
  not modeled because no source publishes them at all (see
  `docs/data-sources.md`'s Victory Road entry); nature is published, and
  reported for 100% of Champions roster slots, but is not modeled here
  either.
- Only the curated `TOGGLES` list (Choice Band/Specs, Life Orb, Expert
  Belt, Huge Power/Pure Power, Adaptability, Technician, Intimidate) is
  modeled; no other item or ability affects the calculation.
- Status conditions (e.g. burn), critical hits, multi-hit moves, and
  terrain are **not** modeled at all.
- Damage calc only offers moves the attacker actually has recorded usage
  for (`pokemon_move_usage`) — there's no full per-species movepool data
  in this pipeline, only what's been seen in real tournament rosters.

If a future pass wants deeper mechanics fidelity, extend `TOGGLES` and
`computeDamage()` in `matchup.js` rather than adding new dbt models —
none of this is data-layer work.

## Detected archetypes and triple cores

Triple-core tiles reuse the `.team-comp` visual with the selected Pokémon
omitted, so the two partners read as a unit instead of a misleading single
sprite. The existing percentage/multiplier convention still applies:
co-occurrence shows team share and synergy shows `×N.N` lift, always paired
with its real team/event sample.

Detected-archetype tiles show the representative three-Pokémon composition,
primary-assignment team share, sample size, stability label, and most common
extension. They intentionally do not use themed names or illustrations:
the visual language must make clear that these are measured composition
groups, not editorial claims about play style. Only cross-event groups enter
the dashboard, capped at 24; emerging and single-event groups remain in the
mart for analysis.

## Responsive behavior

Adopted from docs/upgrade-plan-2027q2.md (M2), and enforced by
`tests/browser/test_responsive_matrix.py` (M1), which opens every route
at 360, 390, 768, 1024 and 1440px, plus 430, 721 and an 844×390
landscape phone.

- **Four tiers**: phone ≤480px, large phone 481–720px, tablet
  721–1023px, desktop ≥1024px. There are no other breakpoints: the old
  600px (data tables) and 900px (Overview, event performers) breakpoints
  folded into 720px and 1023px.
- **No horizontal page scroll** at any width from 360px up
  (`scrollWidth <= innerWidth`). Only an element that scrolls itself may
  be wider than its box: `.table-scroll`, a tab row, or a data table's
  `.data-table-scroll` frame, which scrolls on tablets (with U7's edge
  fades) and gives way to two-line rows on phones.
- **Every grid has a column count per tier**, with `minmax(0, 1fr)`
  tracks, never a fixed `repeat(6, 1fr)` above 720px: `.grid-6xn` is
  6 / 4 / 3 / 2, the Top 12 board 6 / 4 / 4 / 3, team card grids and the
  starter strip 3 / 2 / 2 / 1.
- **Tap targets are at least 44px** on phones (nav items, sub-tabs,
  chips, segmented controls, board tiles, team-strip tiles, the ⋯ menu),
  and every hover affordance has a tap equivalent: a tooltip opens on tap,
  and a tile's detail is in its `aria-label` and its destination.
- **Fields are at least 16px** below 1024px, so iOS Safari doesn't zoom
  on focus (one rule outranks component fonts such as `.combo-input`).
- **The sticky chrome** is at most 120px tall on phones (the 56px top bar
  plus the bottom section bar) and 200px elsewhere. New controls go
  inside a view's band, never in a new sticky row.
- **The header fits from 721px**: on tablets the brand drops its suffix,
  the sections tighten and the regulation select shows only its code
  ("M-C"); "Reg" shows beside it on desktop.
- **A combobox's hidden `<select>`** is pinned to its host's corner
  (`.combo-host`); left at its static position it sat past a phone's
  right edge (the 2026-10-21 review's finding 1).
- **Bottom bars respect `env(safe-area-inset-bottom)`**; on landscape
  phones (`max-height: 500px`) nothing but the top bar sticks.
- **Images keep their intrinsic size.** Hero art is a 256px WebP of about
  16KB, right for a ~96px tile at 2–3× density, so phones need no smaller
  variant; below-the-fold board tiles lazy-load.
- **The display font** loads with `font-display: swap` and a size-adjusted
  local fallback, so the swap doesn't move the layout.

Each new component lists its layout per tier in docs/upgrade-plan-2027q2.md's
M3 table before it is built.

## Backlog: not yet buildable

One explicitly-requested capability still isn't in this pass because the
underlying data doesn't exist in this dataset yet — adding it as a
frontend-only feature would mean fabricating data, which this repo's
"provenance is mandatory" convention (`CLAUDE.md`) rules out:

- **Real head-to-head battle-outcome matchups** ("what beats Pokémon X X%
  of the time in practice"). The type-effectiveness half of this gap is
  now closed (see the "Matchup" section above) — Pokémon type and move
  power/accuracy/category are real PokéAPI data now. What's still missing
  is individual battle-outcome data: MunchStats reports team rosters and a
  team's aggregate win/loss record, not per-battle results against a named
  opponent, so the Matchup tab's co-usage panel is an explicitly-labeled
  teammate-pairing *proxy*, not a real matchup-outcome signal. Closing this
  for real needs a battle-log source — neither an in-scope nor a deferred
  source (Limitless VGC, Victory Road) is confirmed to provide one.
  Tracked in `docs/todo.md`'s M6 backlog.
- **Date-range filtering / trend charts.** Only one `snapshot_date` exists
  in the data so far, so a date-range control would have nothing to range
  over — see `docs/dashboard.md`'s "Removed sections" for the same
  degenerate-data reasoning applied to the earlier legal-pool-trend
  section. Tracked in `docs/todo.md`.

Sortable table columns and type-effectiveness (both previously listed
here as backlog) are now shipped — see "Leaderboard table" and "Matchup"
above.

See `docs/todo.md`'s M6 backlog section for the full, current list — this
document only calls out the items directly relevant to this pass's
design-system/Pokémon-representation scope.
