# Next upgrade plan — "Broadcast grade" (2026 Q4 → 2027 Q2)

Written 2026-10-21. This plan follows `docs/upgrade-plan-2027q1.md`, whose
Sprints 5–9 all shipped. Items move into `docs/todo.md` once accepted, per
`docs/backlog.md`'s backlog → todo flow.

The 2027 Q1 cycle made the site something players use for prep. This cycle
does three things:

1. It makes the site *look and read* like the official competitive
   graphics players already know, starting with the "Top 12 Pokémon"
   card.
2. It brings in better data: online tournaments for sample size and
   freshness, and the Showdown ladder for the first real Pokémon-vs-Pokémon
   battle signal.
3. It turns event weekends into the site's best moments.

Constraints carry over: no EV/IV fields (see decision D3 for Stat Points),
team-vs-team grain stays labelled wherever it appears, and the site stays
static with no backend. Two constraints are new:

- **Borrow the official design grammar, never the official marks.** That
  rules out logos, wordmarks, the Champions 2D art set and "Play! Pokémon"
  branding. The site must never be mistaken for an official product.
- **Every component ships with its phone and tablet layout.** The official
  graphics are 16:9 TV frames, while players read this site on a phone at
  the venue. Track M defines how each new piece reflows, and no item is
  done until it passes the responsive test matrix (M1) at every width.

## Status

| Item | State |
|---|---|
| M1–M4 Mobile and responsive | M1, M2 done (Sprint 10); M3 applied to each component as it ships; M4 done (Sprint 13) |
| Q1–Q5 Quality and shell | Q1, Q2 done (Sprint 10); Q3–Q5 done (Sprint 15) |
| V1–V8 Broadcast-grade visuals | V1, V2, V7 done (Sprint 10); V3–V6 done (Sprint 11); V8 done (Sprint 13) |
| E1–E5 Event weekend | E3 done (Sprint 11); E1, E2, E4 done (Sprint 13); E5 proposed |
| S1–S5 Data sources | S1 done (Sprint 12); S2 done, S4 checked and parked: the ranks aren't in MunchStats' published data (Sprint 14); S3, S5 proposed |
| D1–D5 Decisions | Taken as recommended, 2026-10-21 (see section 6) |

---

## 1. What the 2026-10-21 review found

### 1a. The current UI

These are screenshots of the published `docs/dashboard/` build at 1440px,
768px and 390px, plus a scripted horizontal-overflow check
(`document.documentElement.scrollWidth` against the viewport) of 19 routes
at 360, 390, 430, 721–1024 and 1440px.

| # | Finding | Evidence |
|---|---|---|
| 1 | **The Pokémon profile is wider than a phone.** | `#/pokemon/<key>` is 34px too wide at every phone width: `scrollWidth` 394 at 360px, 424 at 390px and 464 at 430px. The stat bars, the per-regulation trend and the Real sets Exact/Core toggle are cut off, and the page scrolls sideways. The culprit is `select.combo-source` and the rows beside it. Every other route fits at phone widths. `tests/browser/` runs only at 1440 and 390 (`VIEWPORTS` in `test_dashboard_routes.py`) and fails on console errors and empty panels, but never checks width, so nothing caught it. |
| 2 | **Every route is too wide on a tablet.** | At 768px all 19 routes measure `scrollWidth` 807, and Overview measures 807 at every width checked from 721px to 800px (it fits from 820px). The header's regulation select and ⋯ menu run off the right edge, so at 768px the ⋯ menu, and the theme toggle inside it, is cut off. Above 720px the phone header and bottom bar switch off, but the desktop header doesn't fit until about 808px. This range covers iPad mini (744) and iPad (768) in portrait and many Android phones held landscape. At 768px two content problems sit outside any scroll container as well: the fixed six-column `.grid-6xn` on Overview and Matchup (tiles reach 809px and 822px), and the `data-table` on Events (878px) and Players (778px). No test runs between 390 and 1440. |
| 3 | **The Top 12 is the last thing on Overview.** | On desktop it starts about 1,200px down, after the KPI strip, "What changed", the latest event and Copy and play. The official card (reference R1 below) makes the Top 12 the hero. |
| 4 | **Our usage headline is about 6× smaller than every number players compare it with.** | The site leads with *share of roster slots*: Rillaboom 8.7%. The official card, Pikalytics and Smogon all report *share of teams*. Rillaboom is on 1,958 of 3,770 M-C teams, which is 51.9%. A player who sees "8.7%" here and "52%" elsewhere concludes one of them is wrong. |
| 5 | **Teams are six bare sprites.** | Held items and Mega Stones sit behind a "Sets" disclosure. The game's own battle UI and the broadcast (R2) put the held item on every slot, because the item *is* the team: a Mega Stone, Choice Scarf or Focus Sash changes how the team plays. |
| 6 | **Speed Tiers talks about EVs, which Champions doesn't have.** | `index.html.jinja` line 1548 reads "level 50 (252 EVs, a beneficial nature, a 31 IV)". Champions uses Stat Points: 66 in total, at most 32 per stat, with IVs fixed at 31. Its formula, (Base + SP + 20) × nature, gives the same Level 50 numbers as the old one, so **the figures are right and only the wording is wrong**. ([Bulbapedia: Stat point](https://bulbapedia.bulbagarden.net/wiki/Stat_point)) |
| 7 | **Baselines are thin exactly when they matter most.** | M-B is 395 teams from a single event (Worlds). After M-D starts on 2026-12-03, U3's fallback will show M-C until the first regional reports. Online events (S1) fill both gaps within days. |
| 8 | **Event pages have no bracket.** | Event pages list the top 8, but the round-by-round RK9 pairings already in `tournament_match` never appear as a bracket or as a "path to the title". |

### 1b. Iconography: what the official VGC graphics do

The four references below were studied directly. They are linked, not
copied: official images must not be committed to this repository.

- **R1 — "Top 12 Pokémon · Phase Two", 2026 NAIC.** The usage card in
  pokemon.com's
  [2026 Worlds VGC roundtable](https://www.pokemon.com/us/features/2026-pokemon-world-championships-preview-vgc-roundtable)
  (`…/previews/vgc/inline/02.png`, alt text "2026 North America VGC
  International Championships Top 12 Pokémon by usage").
- **R2 — NAIC 2026 Masters Top 8 broadcast frame.** In the same article
  (`…/inline/03.png`).
- **R3 — 2026 Worlds identity.** The logo and the key graphic, from
  Bulbagarden Archives:
  [2026 Pokémon World Championships logo.png](https://archives.bulbagarden.net/wiki/File:2026_Pok%C3%A9mon_World_Championships_logo.png)
  and
  [Champs Worlds 2026 logo.jpg](https://archives.bulbagarden.net/wiki/File:Champs_Worlds_2026_logo.jpg).
- **R4 — Official team presentation.**
  [2026 Worlds VGC Masters page](https://www.pokemon.com/us/play-pokemon/worlds/2026/vgc-masters).

#### R1, anatomy of the "Top 12 Pokémon" card

| Element | What the official card does | What we take |
|---|---|---|
| Canvas | 16:9, 1920×1080. A white rounded board on a red field (`#EA0028`) patterned with darker red (`#84010C`) Pokémon line art | A 16:9 board for the share card; a full-width board on Overview |
| Grid | 6 columns × 3 rows. Ranks 1–6 fill the top row and 7–12 the bottom row. The middle row is three 2-column blocks: the title ("Top 12 Pokémon"), the event mark on gold (`#FFC549`), and the phase ("Phase Two") | The same 6+band+6 layout. Our band holds the title, the regulation and sample ("Reg M-C · 3,770 teams · 5 events") and the scope ("All players" / "Day 2") |
| Rank | **No rank numerals.** Position is the rank, read like text | Keep a small rank in the corner for screen readers and the table view, visually quiet |
| Tile | Deep maroon (`#7F2629`), rounded. The art is large and **breaks the tile's top edge**, and a darker scrim (`#572931`–`#6B272D`) sits under the label | Hero art (the 256px HOME render we already ship) instead of 64px menu sprites, allowed to overflow the tile |
| Hero number | Usage % in heavy **gold numerals** (`#FEC449`), left of the type badges, on one line | Team share in `--accent-gold` (a token already reserved for "#1/MVP"), with type badges inline after it |
| Name | White, bold, under the number. Long forms use a condensed cut: "Floette (Eternal Flower)", "Basculegion (Male)", "Lycanroc (Dusk Form)" | Names stay one line; forms in parentheses shrink rather than wrap |
| Types | Small **square** badges with rounded corners: the type colour filled, with a white glyph (the in-game Champions style) | A square badge variant of `typeIconsHtml` for broadcast components |
| Grouping | Species level: "Charizard", not "Mega Charizard Y" | A Species / Forms toggle. Forms stays the default (Pikalytics and Smogon also split Megas), and Species matches the official card |
| Metric | Share of **teams** (Kingambit 70.7%) | Finding 4: team share becomes the headline everywhere |

#### R2, anatomy of the broadcast frame

- **Scoreboard bar** (top centre, red): `PLAYER NAME` in white caps, then a
  country chip (`JP`), a W/L/T record chip (`12/1/0`) and the game score in
  a white box (`1`). The event mark sits in the centre, and below it a black
  italic phase chip: `MASTERS TOP 8A`.
- **Team rails** (the game's own UI, down each side of the screen): six
  **square tiles**, each with the **held-item icon in a white circle at the
  top-right corner**, and a **Mega badge** on the Mega holder. The two
  active Pokémon are lit (cream), and benched or fainted ones are dimmed.
- **Timers**: per-player time and total time.

#### R3, the 2026 Worlds identity

- **Logo**: a Poké Ball under four coloured arcs (red, blue, green and
  yellow, the championship series' four-colour system). The wordmark is
  chunky geometric caps, white with a black outline and a grey keyline,
  like a sticker.
- **Key graphic**: a red field tiled with a tone-on-tone Poké Ball pattern,
  45° parallelogram slashes in yellow, orange, blue and white, halftone dot
  gradients, and a thick yellow frame.

#### R4, how official channels present a team

The official team presentation has the player, country and placement label,
then six sprites, then a "Show details" disclosure. Each Pokémon lists its
moves, **Stat Alignment** (the nature), held item and ability. **There are
no Stat Points, no item icons and no record.** This matches what RK9
publishes (`docs/data-sources.md`, source 7) and confirms that official
sheets carry no spreads.

#### The design grammar, as rules for this site

1. **The Pokémon is the hero.** Big art first, the number second, the name
   third.
2. **One number per tile, in gold.** Context (the sample, the phase, the
   regulation) appears once, in the title band, not on every tile.
3. **Position is rank.** Rank numerals stay small or hidden.
4. **A team is six squares, each carrying its held item.** A Mega gets a
   badge.
5. **A player is name · country · record**, in chips and in that order.
6. **Every view says its phase**: "Day 2", "Top 8", "Swiss R9", "All
   players".
7. **Square type badges** on broadcast components. Circular emblems stay
   in dense tables.

#### The grammar on a phone

The references are 16:9 TV frames; a phone is a 9:19.5 portrait screen read
with one thumb. The rules above hold, and they adapt like this:

- **The band moves to the top.** On a phone the title band (title, sample,
  scope) becomes the board's header instead of its middle row, followed by
  the twelve tiles in reading order. Rank stays positional.
- **Fewer columns, never smaller tiles.** The board drops from 6 columns
  to 4 on a tablet and 3 on a phone. A tile never gets narrower than
  104px, which is 3 columns at 360px with 16px gutters and 8px gaps.
- **One idea per line.** The gold number gets its own line on a phone. The
  type badges move to the tile's top-right corner, where U9 already puts
  them, rather than sharing the number's line.
- **Names wrap, they don't truncate.** A long form such as "Floette
  (Eternal Flower)" puts the form on a second, smaller line. An ellipsis
  that hides the form would make two Pokémon look the same.
- **A team stays one row of six.** At 360px with 4px gaps a tile is about
  51px, or about 47px inside a card with 14px padding. Wherever a tile
  would fall below 44px, the team wraps to 3×2 rather than shrinking past
  the tap minimum.
- **Tap, not hover.** Anything a desktop shows on hover (a held item's
  name, a set, a denominator) opens on tap as a popover. The design system
  already notes that `title` isn't reachable on touch.
- **Trees become steps.** A bracket or a path becomes a list of rounds
  with round tabs; a scatter becomes a ranked list. Nothing relies on
  horizontal page scrolling.

What we will not copy: the Worlds and International Championship logos and
wordmarks, the Pokémon wordmark, the Champions 2D art set, the official
key-graphic patterns, and the four-colour arcs *as a mark*. The four colours
may appear as a palette, not as the arc device. Our patterns are drawn in
CSS, and the footer keeps saying the site is unofficial.

---

## 2. Data sources: what's better out there

Each candidate below was evaluated on 2026-10-21. "Verified" means the
endpoint was called from this project's egress and the fields inspected,
not taken from a description.

| Source | What it adds | Verified | Population | Access | Verdict |
|---|---|---|---|---|---|
| **Limitless online tournaments** (`play.limitlesstcg.com/api`) | Hundreds of online Champions events, each with full team sheets (item, ability, nature, moves), W–L–T records, drops and round-by-round pairings | Yes. The 500 newest VGC events (2026-08-29 to 2026-10-20) included **280 M-C events with 11,970 entries since 2026-09-12** and 118 M-B events | Online grassroots players, identified by handle | No key needed; rate limit 50 requests per 5 minutes; keys with higher limits go to public-facing projects ([docs](https://docs.limitlesstcg.com/developer.html)) | **Adopt (S1)**, as a separately labelled `online` tier |
| **Smogon monthly usage stats** (`smogon.com/stats/<month>/chaos/gen9championsvgc2026regmc-<cutoff>.json`) | Ladder usage, plus per-Pokémon abilities, items, moves, teammates, **Stat Point spreads** and **Checks and Counters** (KO or forced-switch rates per pair, derived from battle logs) | Yes. September 2026 Reg M-C: **1,631,943 battles, 277 Pokémon**. Bo3 and four rating cutoffs (0/1500/1630/1760) exist for M-B and M-C | Pokémon Showdown ladder | Public files, monthly; credit Smogon / Pokémon Showdown | **Adopt (S2)**, as a separate `ladder` population that is never blended with tournaments |
| **Pokémon Showdown replays** (`replay.pokemonshowdown.com/search.json?format=…`, then `/<id>.json`) | Battle logs: the six at team preview, **which four were brought**, leads, switches, KOs and turn count | Yes. The search returns current `gen9championsvgc2026regmc` and `…regmcbo3` replays with players and rating | Showdown ladder and some tournaments | Public JSON; volume needs pacing; player handles stay unpublished | **Discovery (S3)**, the `docs/roadmap.md` Phase 4 path |
| **In-game Battle Data** (Battle → Battle Data, per ranked season) | The game's own ranked usage by season | Indirectly. [MunchStats](https://www.munchstats.com/about/) reads the in-game screens nightly ("235 ranked Pokémon in both formats") as **ranks, not percentages**; Pokémon Zone mirrors the seasons | Official in-game ranked | No documented public API | **Check S4**: if MunchStats (already in scope) publishes it, ingest it from there. Don't reverse-engineer undocumented endpoints |
| Official pokemon.com / championships.pokemon.com | Official standings and team sheets | Blocked: Imperva "Error 15" from this egress | Official events | Not reachable | Park. Same fields as RK9 anyway (R4) |
| Liquipedia (VGC events and players) | Player identity across events, aliases, earnings | Blocked: 403 to our fetcher; the LPDB API needs a key; CC-BY-SA | Notable players | Key application | Park, unless player identity across sources becomes a goal |
| Pikalytics `/ai/` pages and `llms-full.txt` | Aggregates (team compositions, usage, 30-day rank change) | Yes ([team usage](https://www.pikalytics.com/ai/team-usage/championstournaments): 10,940 source teams, data date 2026-05) | Derived from others | Unclear licence | **Cross-validation only.** Never a primary source: its figures are derived |
| Official stream VODs (YouTube) | "Watch this match" links for featured tables | Not built; a curated seed of event, round and table → URL and timestamp | Featured matches | Manual seed, or a YouTube Data API key | **Small add (S5)** |

The landscape we compete with, and what each competitor does that we don't:

| Site | Distinctive UI | Gap it shows |
|---|---|---|
| [Pikalytics](https://www.pikalytics.com/worlds-2026) | Event hub pages; meta table with a 30-day rank change; ranked team compositions with records; team image export; Labs quizzes | Rank-change column, team images |
| Pokémon Zone | Ranked season pages (singles and doubles); "Most common Stat Points"; builds ranked by placement vs raw usage | Seasons, Stat Points |
| [Champions Lab](https://championslab.xyz/meta) | Rising/Falling grids; "560 community tournaments with 28,123 teams"; type distribution with win rates | Online-event volume (S1) |
| [MetaVGC](https://metavgc.com/tournaments/worlds-2026) | Event hub with a time-zone schedule, a top-cut bracket and a competitor grid | Bracket (E2), schedule |

Where we're ahead, which every feature below should keep: provenance on
every row, real team-vs-team results from RK9 pairings, regulation scoping,
versioned releases, and citation-ready numbers.

---

## 3. Tracks

### Track M — Mobile and responsive (P0, gates every track)

**M1. A responsive test matrix.** `tests/browser/` grows from two
viewports (1440 and 390) to the widths people actually use:

- **Full sweep of every route** at 360×780 (the floor), 390×844, 768×1024,
  1024×768 and 1440×900.
- **Spot checks** at 430×932, at 721×1024 (the first tablet pixel, where
  finding 2 starts) and on a landscape phone at 844×390.

The checks:

1. `scrollWidth <= innerWidth` on every route. This catches findings 1
   and 2.
2. On phones, every nav item, sub-tab, chip, segmented control, board
   tile and team-strip tile is at least 44×44px. U7 set that target; this
   enforces it.
3. Every input and select computes to at least 16px, so iOS Safari
   doesn't zoom on focus.
4. The sticky chrome is at most 120px tall on phones and 200px on
   desktop. These are U2's targets, now enforced.
5. CI uploads a screenshot of every route at every width as an artifact,
   so reviewers can see the phone layout on every PR.

**M2. Responsive rules.** These become the "Responsive behavior" section
of `docs/design-system.md` on acceptance.

- **Four tiers**: phone ≤480px, large phone 481–720px, tablet 721–1023px,
  desktop ≥1024px. The stylesheet's stray 600px and 900px breakpoints fold
  into these.
- **No horizontal page scroll** at any width from 360px up. Only an
  explicit `.table-scroll` may scroll sideways, and it carries U7's edge
  fades.
- **Every grid gets a column count per tier.** No fixed `repeat(6, 1fr)`
  above 720px, which is what breaks finding 2. Tracks use
  `minmax(0, 1fr)`, the fix U9 found for the Builder.
- **Tap targets are at least 44px**, and every hover affordance has a tap
  equivalent.
- **New controls go inside a view's band**, never in a new sticky row:
  the scope switch, the Species/Forms toggle, the round tabs.
- **Bottom sheets respect `env(safe-area-inset-bottom)`**, as the bottom
  bar already does. On landscape phones (`max-height: 500px`) the sub-tab
  row stops sticking, which gives the content back its height.
- **Images keep their intrinsic size** (the existing rule). Board rows
  below the first screen lazy-load. Hero art is a 256px WebP of about
  16KB (347 files, 5.6MB), the right size for a ~96px tile at 2–3× pixel
  density, so phones need no smaller variant. Twelve of them come to about
  195KB, of which a phone loads the first six eagerly.
- **The display font (D4)** loads with `font-display: swap` and a
  size-adjusted fallback, so the swap doesn't move the layout.

**M3. Every new component's layout, per tier.**

| Component | Phone (≤480) | Large phone (481–720) | Tablet (721–1023) | Desktop (≥1024) |
|---|---|---|---|---|
| Header | Brand mark, regulation select, search, ⋯; sections in the bottom bar (as today) | The same, with the wordmark | Brand mark, five sections, a compact regulation select ("M-C ▾"), search, ⋯. It must fit at 721px (finding 2) | As today, plus search |
| Top 12 board (V2) | Band on top, then 3 columns × 4 rows of 104–114px tiles; 88px art; number on its own line; type badges top-right | Band on top, 4 × 3 | Band on top, 4 × 3 | 6 + band + 6, as R1 |
| Team strip (V3) | One row of six 47–51px tiles; 18px item badge top-right, Mega badge stacked under it; tap opens the set; wraps to 3×2 below 44px | 56px tiles | 56px tiles | 64px tiles |
| Team card grids (Top Teams, Copy and play, event top 8) | 1 column | 2 columns | 2 columns | 3 columns |
| Scoreboard row (V4) | Two stacked lines, player A over player B. Each line has the name (ellipsis, full name on tap), country chip and record chip; the result sits at the right and the winner is bold | One line: A, score, B | One line | One line |
| Phase chips (V5) | Wrap onto a second line, never truncated | Wrap | One line | One line |
| Scope switch, Species/Forms | Full-width segmented controls inside the band, 44px tall | Inline in the band | Inline | Inline |
| Day 2 conversion, Mega panel (E1, E3) | U5's two-line rows: name and conversion, then "All 34.1% → Day 2 41.0% · n" | Two-line rows | Full table | Full table |
| Bracket (E2) | Round tabs (Top 16 · QF · SF · Final) over a vertical list of match rows; a player's path is a vertical timeline | Round tabs | Quarterfinals → Final tree in 3 columns | Full tree |
| Ladder vs tournament (S2) | Two ranked lists, "Over-rated on ladder" and "Under-rated on ladder" | Two lists | Scatter with 44px hit areas | Scatter |
| Checks and counters (S2) | List rows (sprite, KO-or-switch %, n), top 6 with "Show all" | List rows | Two-column list | Two-column list |
| Global search (Q3) | Full-screen sheet with the keyboard up and recent searches | Full-screen sheet | Dropdown under the header | Dropdown |
| Speed line (list #24) | Vertical: fastest at the top, sticky scenario chips | Vertical | Horizontal number line | Horizontal |
| Share cards (V8, M4) | "Share" opens the system share sheet with the 4:5 and 9:16 cards | Share sheet | Download; 16:9 default | Download |
| Compare tray (list #34) | Bottom sheet above the bottom bar | Bottom sheet | Side panel | Side panel |

**M4. Sharing from a phone.** The share buttons use the Web Share API
(`navigator.canShare({files})`), which hands the PNG straight to the
system share sheet, and fall back to a download where that isn't
available. V8 adds a 9:16 (1080×1920) story card to its 16:9 and 4:5
cards. "Copy for Showdown" confirms with a toast on touch devices, where
there is no hover feedback.

### Track Q — Quality and shell (P0)

**Q1. Overflow fixes on phones and tablets.** Fix `#/pokemon/<key>` at
every phone width (finding 1), and the header, `.grid-6xn` and table
overflow between 721px and 807px (finding 2). M1's matrix keeps both
fixed.

**Q2. Stat Points copy.** Speed Tiers says "32 Stat Points (66 total),
beneficial Stat Alignment, IVs fixed at 31" instead of 252 EVs (finding 6).
The glossary gains entries for "Stat Points" and "Stat Alignment", the terms
the game and the official team sheets use.

**Q3. Global search (`/` or ⌘K).** One box finds Pokémon, players and
events. The Pokémon and player comboboxes already exist; this merges them.

**Q4. Localised Pokémon names (JP / ES / PT / DE / FR).** PokéAPI carries
localised species names, and Japan and Brazil are two of the biggest
audiences. This changes names only; numbers and copy stay in English.

**Q5. Offline at the venue.** A service worker caches the core payload and
the last regulation shard. The calculator and the Builder then work on bad
convention Wi-Fi.

### Track V — Broadcast-grade visuals (P0/P1)

**V1. Team share becomes the headline metric** (finding 4). It is the
number of teams carrying a Pokémon divided by the teams in scope. Every
usage tile, table and share card leads with it. Share of roster slots
moves to the tooltip and the dictionary. Add a `team_share` column to the
usage marts (`usage_count / teams in scope`) rather than computing it
client-side, so releases carry it too. Note it in the changelog: every
usage number on the site gets about 6× bigger.

**V2. The Top 12 board** (R1). Overview opens with it, above "What
changed".

- Six tiles, then a title band, then six more tiles. The band says "Top 12
  Pokémon · Reg M-C · 3,770 teams · 5 events", plus a scope switch: All
  players / Day 2 (needs E1) / Online (needs S1).
- Each tile shows hero art overflowing its top edge, team share in gold
  numerals, square type badges and the name. A tap opens the profile.
- It reflows per M3: 6 + band + 6 on desktop, the band on top with 4
  columns on tablets and large phones, and 3 columns on phones.
- A Species / Forms toggle (R1's grouping).
- The board and the existing table share one data path, so this is a new
  view of the mart, not a new mart.

**V3. Team strip v2** (R2, rule 4). Every team on the site uses one
component: six square tiles, each with the held-item icon in a white circle
at the top-right corner and a Mega badge on the Mega holder.

- It is used by Top Teams, event top 8, player pages, Copy and play, the
  Builder slots and the PNG cards.
- Item icons already resolve for the profile (`docs/dashboard.md`, "Icon
  sources"), and team sheets carry the item.
- It replaces `teamCompositionHtml`, which draws sprites only.

**V4. Scoreboard rows** (R2, rule 5). A match or player line reads `NAME
[CC] [W-L-T] [score]` with chips. It is used in head-to-head records, event
pairings and the bracket (E2).

**V5. Phase chips** (rule 6). Small black italic chips such as "MASTERS ·
TOP 8", "DAY 2", "SWISS R9" and "ALL PLAYERS" sit on every event-scoped
view and every card.

**V6. Square type badges** (rule 7). Add a `square` variant to
`typeIconsHtml`: a fill from `--type-<name>` with a white glyph. Use it on
broadcast components (V2, V3, share cards). The circular emblems stay in
tables. This needs white glyph art: our own SVGs, or PokéAPI's sprite set
if a suitable one exists. Never the official icons.

**V7. Broadcast tokens.** Promote the palette from R1/R3 into the design
system as `--board-field`, `--board-tile`, `--board-scrim` and
`--accent-gold` (already reserved), plus a four-colour accent set (red,
blue, green and yellow) for categorical highlights. Add a CSS-drawn diagonal
slash/halftone band for page headers. Dark-mode values come with them, per
`docs/design-system.md`.

**V8. Top 12 share card** (R1). Add 16:9 (1920×1080), 4:5 (1080×1350) and
9:16 (1080×1920) PNGs per regulation and per event ("All players" and "Day
2") through `pipelines/render/share_cards.py`. The two portrait formats use
the phone board layout (band on top, 3 columns), not a squeezed 16:9. They carry the citation line and the
site URL. The Overview's Open Graph image becomes this card.

### Track E — Event weekend (P1)

**E1. Day 2 conversion.** VGC's classic stat is usage across the whole
field against usage among players who reached Day 2, and the ratio between
them. R1's "Phase Two" board is exactly this.

- Derive Day 2 membership from RK9's round structure (players with a
  pairing after the day-1 cut). Cross-check it against Limitless, which
  publishes team lists for the Day 2 cut only (`docs/data-sources.md`,
  source 6).
- The new mart is `pokemon_event_phase_usage`: (event, phase, Pokémon) →
  teams, team share, and conversion (Day 2 share ÷ all-player share), with
  `n` on every row.
- Hide the conversion for small fields, using the same minimum-teams rule
  as the movers mart.

**E2. Top-cut bracket.** Event pages draw the single-elimination bracket
from `tournament_match` with scoreboard rows (V4) and team strips (V3).
Clicking a player shows their **path**: each round's opponent, their team
and the result. Label it team-vs-team, as every match view is.

**E3. Mega usage panel.** Event pages and regulation views get a "which
Mega Stones are teams carrying" table: each Mega's share of teams, and the
share of teams with zero, one or two Mega Stones. Every competitor recap
publishes one, and the item data already exists.

**E4. Event-weekend refresh cadence.** While an event is live, the
scheduled extraction runs hourly for RK9 pairings and rebuilds the event
page. Swiss standings and Day 1 usage then appear while people are still
watching. It is static output on a faster schedule, with no backend.

**E5. "Watch on stream" links (S5).** Featured-table matches link to the
VOD timestamp from a curated seed.

### Track S — Sources (P1, gated on decisions)

**S1. Limitless online events (decision D1).**

- A new extractor, `pipelines/extract/limitless_play.py`, pages
  `/api/tournaments?game=VGC`, keeps formats in the regulation registry
  (`dbt/seeds/champions_regulations.csv`; never a hardcoded `M-C`), and
  fetches `/standings` and `/pairings` per event.
- Rows land as `tournament_event` with `event_tier = 'online'`. Teams and
  members go through the existing tables, and matches through
  `tournament_match`. Provenance fields follow the usual contract.
- Pace requests to the 50-per-5-minutes limit. The first backfill of about
  560 calls takes about an hour; after that it's incremental. Apply for an
  API key as a public-facing project.
- **Scope rule:** every regulation-scoped view gets an Official / Online /
  All switch. **Official** stays the default for headline numbers and
  "What changed".
- U3's thin-regulation fallback learns one more step: when Official has
  fewer than 300 teams in the regulation in force, show Online with a
  banner instead of falling back to the previous regulation. M-D then has
  data within days of 2026-12-03.
- Handles are not legal names. Online players get no player pages and
  never join RK9 identities.
- Update `docs/dataset-spec.md` (the entity contract and `event_tier`
  values) and `docs/data-sources.md` in the same change.

**S2. The Smogon ladder lens (decision D2).**

- Monthly extraction of `chaos/gen9championsvgc2026reg<x>-1760.json` and
  `-0.json` for each registered regulation (the format slug is built from
  the registry), plus the Bo3 variant.
- New marts: `ladder_pokemon_usage` and `ladder_checks_counters`.
- UI:
  - "Ladder vs tournament": a scatter of tournament team share against
    ladder usage, which shows what is over- and under-rated on ladder.
  - A **Checks and counters** panel on the profile, labelled "Showdown
    ladder, from battle logs".
  - This is the first Pokémon-vs-Pokémon battle signal on the site. It is
    never presented as tournament data.
- **Stat Point spreads** from the same file wait on D3.

**S3. Replay discovery (roadmap Phase 4).** Follow `docs/roadmap.md`'s
seven steps against Showdown replays. Confirm the terms, write a contract
and a fixture, and measure coverage. Then define `battle`, `battle_side`
and `battle_pokemon` and build bring rate, lead pairs, and win rate when
brought versus benched. Aggregate only: no player handles on the site.

**S4. Official ranked seasons via MunchStats.** If MunchStats' published
JSON includes its nightly in-game Battle Data ranks, add a `ranked_season`
staging source and an "Official ranked (rank only)" column on Usage. If it
doesn't, park this item.

**S5. A VOD seed** (`dbt/seeds/featured_match_vods.csv`): event_id, round,
table, url and t. It feeds E5.

---

## 4. The laundry list: top UI features

The ranked list, with the top ten in bold. Sizes: S ≤ 1 day, M 2–4 days,
L 1 week or more. "Data" says whether the feature needs nothing new (✓),
a new mart (mart) or a new source (S1–S5).

| # | Feature | Why | Data | Size | Item |
|---|---|---|---|---|---|
| 1 | **Fix the phone (profile) and tablet (every route) overflow; responsive test matrix from 360 to 1440** | Broken on phones and tablets today, and untested between 390 and 1440 | ✓ | M | Q1, M1, M2 |
| 2 | **Team share as the headline metric** | Our numbers read 6× lower than the official ones | mart column | M | V1 |
| 3 | **The Top 12 board as the Overview hero, 6/4/3 columns by tier** | The single most recognisable VGC graphic | ✓ | M | V2, M3 |
| 4 | **Team strip with held-item and Mega badges everywhere** | The item is the team; matches the game and broadcast UI | ✓ | M | V3 |
| 5 | **Online events scope (Official / Online / All)** | 3× the M-C sample; M-D data within days | S1 | L | S1 |
| 6 | **Day 2 conversion board and table** | VGC's classic "who converts" stat; R1's Phase Two | mart | M | E1 |
| 7 | **Top-cut bracket with each player's path (round tabs on phones)** | Every event hub has one; we hold the pairings already | ✓ | M | E2 |
| 8 | **Top 12 share card (16:9, 4:5, 9:16), shared through the phone's share sheet** | The image people post; links unfurl with it | ✓ | M | V8, M4 |
| 9 | **Checks and counters on the profile (ladder)** | The first real "what beats X" signal | S2 | M | S2 |
| 10 | **Stat Points copy and glossary** | Wrong game terminology on the site | ✓ | S | Q2 |
| 11 | Scoreboard rows for matches and players | A broadcast-native way to read a result | ✓ | S | V4 |
| 12 | Phase chips on event-scoped views | Every view says what it covers | ✓ | S | V5 |
| 13 | Mega usage panel | Every recap publishes one | ✓ | S | E3 |
| 14 | Ladder vs tournament scatter (two ranked lists on phones) | Shows over- and under-rated picks | S2 | M | S2 |
| 15 | Species / Forms toggle | Matches the official grouping when wanted | ✓ | S | V2 |
| 16 | Square type badges on broadcast components | The in-game style; reads faster at size | art | S | V6 |
| 17 | Broadcast tokens and header band | One visual identity across site and cards | ✓ | S | V7 |
| 18 | Global search (Pokémon, players, events), as a full-screen sheet on phones | One entry point | ✓ | M | Q3 |
| 19 | Rank-change column on Usage (vs the previous event window) | Pikalytics' most-read column | ✓ | S | — |
| 20 | Event-weekend hourly refresh | Live Swiss standings and Day 1 usage | ✓ | M | E4 |
| 21 | Open Team Sheet image export from the Builder | Players share sheets as images | ✓ | M | — |
| 22 | Builder legality warnings (regulation legal pool, item clause) | Prevents illegal teams | ✓ | S | — |
| 23 | Builder threat list upgraded with checks and counters | Turns the screen into prep | S2 | M | — |
| 24 | Speed line: a number line of sprites (vertical on phones), with Tailwind and Trick Room toggles | The standard speed-tier visual | ✓ | M | — |
| 25 | Localised Pokémon names | Japan and Brazil audiences | ✓ | M | Q4 |
| 26 | Offline at the venue (service worker) | Convention Wi-Fi | ✓ | S | Q5 |
| 27 | Bring rate and lead pairs | "Which four did they bring" | S3 | L | S3 |
| 28 | Official ranked season rank column | The game's own numbers | S4 | S | S4 |
| 29 | "Watch on stream" links | Context for featured matches | S5 | S | E5 |
| 30 | Archetype matchup heatmap (team-vs-team, labelled) | Archetype-level prep | ✓ | M | — |
| 31 | Upcoming online events with local times | Players pick events | S1 | S | — |
| 32 | Stat Point spreads (ladder) | The #1 thing competitors show that we don't | S2 | M | D3 |
| 33 | Embeddable Top 12 / usage widget with a citation for creators | Distribution | ✓ | M | — |
| 34 | Compare tray: pin up to 4 Pokémon across pages (a bottom sheet on phones) | Fewer round trips to Compare | ✓ | M | — |

---

## 5. Sequencing

| Sprint (≈1 wk) | Scope | Exit criteria |
|---|---|---|
| **10 — Broadcast board, every screen** | M1, M2, Q1, Q2, V1, V2, V7 | The M1 matrix passes: no route overflows at any width from 360 to 1440, including 721–807. Overview opens on the Top 12 board in team share, in 6, 4 or 3 columns by tier. The Speed Tiers copy says Stat Points. |
| **11 — Teams look like teams** | V3, V4, V5, V6, E3 | Every team on the site shows item and Mega badges. Matches read as scoreboard rows. |
| **12 — Online events** (before 2026-12-03) | S1 (after D1) | 300+ M-C online teams in the dataset, gated and labelled. The scope switch works. A rollover fixture shows Online when Official is thin. |
| **13 — Event weekend** | E1, E2, V8, E4 | Day 2 conversion and the bracket on every event page with RK9 pairings. The Top 12 card renders per event. |
| **14 — Ladder lens** | S2 (after D2/D3), S4 check | Checks and counters on profiles, labelled ladder. The ladder vs tournament view. |
| later | S3, S5, E5, Q3–Q5, list items 19–34 | Per `docs/roadmap.md` Phase 4 for S3 |

Sprint 12 is pinned before 2026-12-03 for the same reason U3 was: online
events report the new regulation within days, and official events take
weeks.

M1 lands in Sprint 10 so that every later sprint is built against it. From
Sprint 11 on, each sprint's exit criteria also include the M1 matrix
passing, and the PR shows its changed views at 360px and 768px.

## 6. Decisions needed

All five were taken as recommended on 2026-10-21, when the cycle was
built: Online and Ladder are separate, labelled scopes (D1, D2); Stat Point
spreads appear only as a ladder mart (D3, with CLAUDE.md's rule reworded);
Oswald is the one self-hosted display font (D4); and team share is the
headline metric (D5).

| # | Decision | Recommendation |
|---|---|---|
| D1 | Bring Limitless online events into the dataset as `event_tier = 'online'`? | **Yes.** It's a separate scope with Official as the default; it fixes thin baselines and gives day-one data for a new regulation. |
| D2 | Add the Showdown ladder as a second, never-blended population? | **Yes.** Checks and counters is the only battle-derived matchup signal available today. |
| D3 | Show Stat Point spreads from the ladder? CLAUDE.md says "Don't add an EV field", and official sheets carry none. | **Yes, but only as a ladder mart** (`ladder_stat_point_spreads`), labelled "Showdown ladder; tournament sheets don't publish spreads". It never enters tournament entities or the Builder's sets. Reword CLAUDE.md's rule to say tournament data has no spreads and ladder data may show them. If you'd rather keep the rule absolute, drop item 32. |
| D4 | Allow one self-hosted display font? The design system says no webfonts. | **Yes, one.** An OFL condensed variable font, subset to Latin and numerals (about 30KB), self-hosted, used only for board numerals and headlines. The condensed names and gold numerals in R1 depend on it. |
| D5 | Change the headline metric to team share (V1)? | **Yes.** Keep roster-slot share in tooltips and the dictionary, and call the change out in the changelog. |

## 7. Risks

| Risk | Mitigation |
|---|---|
| Online results get read as official ones | Official is the default scope; every Online view carries a phase-style "ONLINE" chip; release CSVs keep `event_tier` |
| Ladder numbers get cited as tournament numbers | Separate marts, a "LADDER" chip and a different accent colour; ladder figures never appear in the Top 12 board |
| The site starts to look official | No marks or official art (section 1b); the unofficial footer stays; our own CSS patterns |
| Limitless changes or limits its API | Retry/backoff and incremental extraction already exist (backlog #43/#44); apply for a key; the source is optional per scope |
| Team share changes every number and breaks shared screenshots | A changelog entry, a one-time banner on Overview, and roster share still in tooltips |
| The hourly event-weekend refresh burns Actions minutes | Only while an event in `tournament_event` is live; RK9 pairings only |
| Hero art makes the board heavier | 256px WebP already ships (about 16KB each); a phone loads the first six eagerly and the rest lazily; the U8 budget test covers the payload |
| Broadcast layouts are 16:9 and break in portrait | Each component has a per-tier layout in M3 before it's built, and the M1 matrix fails any route that overflows from 360px up |
| The matrix slows CI | About 100 page loads per run (19 routes at five widths, plus spot checks); run the full sweep in CI and a three-route smoke locally, and share one built site across the sweep |

## Proposed `todo.md` entries (on acceptance)

- [ ] Responsive test matrix: every route at 360/390/768/1024/1440, spot checks at 430/721/landscape; width, tap-target, input-size and chrome-height assertions; screenshots as a CI artifact (M1)
- [ ] Responsive rules in `docs/design-system.md`: four tiers, per-tier column counts, no page scroll, 44px targets, controls inside bands (M2)
- [ ] Fix `#/pokemon/<key>` overflow at every phone width, and the header, `.grid-6xn` and table overflow at 721–807px (Q1)
- [ ] Every new component built to its M3 per-tier layout (V2–V8, E1–E3, S2, Q3)
- [ ] Phone sharing through the Web Share API, and a 9:16 story card (M4)
- [ ] Speed Tiers and glossary: Stat Points and Stat Alignment instead of EVs (Q2)
- [ ] `team_share` on the usage marts; team share as the headline metric site-wide (V1)
- [ ] Top 12 board on Overview: 6+band+6, hero art, gold numerals, Species/Forms toggle, scope switch (V2)
- [ ] Broadcast tokens and header band in the design system (V7)
- [ ] Team strip v2 with item and Mega badges, replacing `teamCompositionHtml` everywhere, PNG cards included (V3)
- [ ] Scoreboard rows (V4), phase chips (V5), square type badges (V6)
- [ ] Mega usage panel on event and regulation views (E3)
- [ ] `limitless_play` extractor, `event_tier = 'online'`, Official/Online/All scope, rollover fallback to Online (S1, after D1)
- [ ] `pokemon_event_phase_usage` mart and the Day 2 conversion board (E1)
- [ ] Top-cut bracket and player path on event pages (E2)
- [ ] Top 12 share cards, 16:9 and 4:5, per regulation and event; becomes the OG image (V8)
- [ ] Event-weekend hourly refresh of RK9 pairings (E4)
- [ ] Smogon ladder extractor; `ladder_pokemon_usage`, `ladder_checks_counters`; profile panel and ladder-vs-tournament view (S2, after D2)
- [ ] Check MunchStats for published in-game Battle Data ranks (S4)
