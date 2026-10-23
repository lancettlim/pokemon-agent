# Data Sources

Catalog of external data sources with extraction notes. See "V1 scope" and
"Deferred sources" in `dataset-spec.md` for which of these are in scope for
the v1 build and why.

## 1. PokéAPI Raw CSV Backends
**Best for:** Raw, unmodified game data and canonical Pokédex information

PokéAPI maintains a complete, community-curated database of all official Pokémon game data in raw CSV format. This includes base stats, type matchups, generational information, move mechanics, physical attributes, and item catalogs. This is your canonical source for the standard game ruleset before any competitive modifications.

**Key assets:**
- Master Database (including csvs, sprites, cries): [pokeapi/data/v2/](https://github.com/PokeAPI/pokeapi/tree/master/data/v2)
- Master Species Base Stats: [pokemon_stats.csv](https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv/pokemon_stats.csv)
- Move Pool Master Index: [moves.csv](https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv/moves.csv)
- Items Master Index: [items.csv](https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv/items.csv)

**How to extract:**
1. Browse the full repository at [github.com/PokeAPI/pokeapi/tree/master/data/v2/csv](https://github.com/PokeAPI/pokeapi/tree/master/data/v2/csv)
2. Copy raw file URLs and import directly into Python (pd.read_csv), Google Sheets, or Excel
3. Link updates automatically if you reference the raw URL

## 2. OP.GG Pokémon Champions
**Best for:** Competitive legal pool, rebalanced base stats, and custom mechanics

OP.GG serves as the authoritative source for the Pokémon Champions tier—a curated competitive format featuring custom base stat rebalances, custom Mega Evolutions, and a restricted 317-entry legal Pokédex. Use this to align your competitive analysis with the exact rules and statistics that apply in tournaments.

**Key coverage:**
- Legally playable Pokémon (317-entry restricted pool)
- Custom base stats (modified from official values)
- Custom Mega Evolution forms and stats
- Tier-specific items and ability adjustments

**How to extract:**
1. GET [op.gg/pokemon-champions/pokedex](https://op.gg/pokemon-champions/pokedex) directly — no
   browser automation needed. The page is server-rendered by Next.js and ships its full Pokédex
   dataset embedded as a JSON-string-escaped array inside a React Server Components "Flight"
   script chunk (`self.__next_f.push([1, "..."])`), extractable with a plain HTTP client (see
   `pipelines/extract/opgg.py`'s docstring for the exact technique)
2. Join with PokéAPI canonical data via numeric ID (or the controlled name/form mapping for
   fabricated-id Mega/regional forms) to identify what was changed

## 3. PokéBase App
**Best for:** Competitive regulation rules, banned/restricted Pokémon, and official speed tiers

PokéBase aggregates competitive-specific ruleset information for Pokémon Champions, including which Pokémon are legal in each regulation, custom tier assignments, and critical speed tier breakpoints. This source reflects the actual competitive metagame restrictions that differ from the base game.

**Key coverage:**
- Legal Pokémon by regulation bracket
- Speed tier classifications
- Item restrictions and custom allowances
- Mega Evolution availability

**How to extract:**
1. GET [pokebase.app/pokemon-champions/pokemon](https://pokebase.app/pokemon-champions/pokemon)
   directly — no browser automation needed. Like OP.GG, the page is server-rendered by Next.js
   and ships its full paginated Pokémon list embedded the same way (a React Server Components
   "Flight" script chunk); each entry legal in the Champions pool carries a `regulationSets`
   array naming every regulation it's legal under (see `pipelines/extract/pokebase.py`'s
   docstring for the exact technique)
2. Join to canonical PokéAPI records via the embedded `nationalNumber` field (correct for
   Mega/regional/alternate forms too) or the controlled name/form mapping for the handful of
   form slugs that don't match PokéAPI's own naming directly

## 4. MunchStats
**Best for:** Live tournament results and player roster data

MunchStats bridges static Pokédex data with active competitive tournament metadata by scraping RK9.gg tournament pairings and results. Use this to track what Pokémon were actually used in recent competitions and which teams are meta-relevant.

**Key coverage:**
- Player rosters from recent tournaments
- Team compositions and move combinations
- Tournament standings and placement data
- Current metagame trends

**How to extract:**
1. Pull structured JSON from [github.com/PizzaTimeJoshua/munchstats](https://github.com/PizzaTimeJoshua/munchstats)
2. Use Python: `pd.read_json(url)` or [convert.town JSON-to-CSV](https://convert.town/json-to-csv)
3. Flatten nested team arrays into flat rows (one row per team member)

**In-game ranked usage (checked 2026-10-22, `docs/upgrade-plan-2027q2.md`,
S4): not published as data.** MunchStats' site shows the game's own Battle
Data ranks for each ranked season, but only in its rendered pages: the
repository's published JSON carries tournament rosters and no ranked-season
file. The plan's rule was to ingest the ranks only from published data and
never reverse-engineer an undocumented endpoint, so S4 is parked until
MunchStats publishes them.

## 5. Bulbagarden Archives
**Best for:** Pokémon sprite/menu-icon artwork for the newest Champions-format Pokémon

PokéAPI's own sprite bundle (see source 1's "Master Database" link) is stale for
the newest Pokémon relevant to the Champions format. Bulbagarden Archives' wiki
maintains a "Champions menu sprites" category with up-to-date artwork, and — unlike
sources 2-3 above — exposes it through a real MediaWiki JSON API rather than
needing HTML scraping.

**Key coverage:**
- Menu-sprite artwork, one image per Pokémon/form (359 images as of this writing)
- Image metadata: resolved CDN URL, dimensions, MIME type, SHA-1 checksum

**How to extract:**
1. `GET https://archives.bulbagarden.net/w/api.php?action=query&list=categorymembers&cmtitle=Category:Champions_menu_sprites&format=json`
   lists the category's files, paginated via the response's `continue.cmcontinue`
   token — no HTML parsing needed, unlike OP.GG/PokéBase (see
   `pipelines/extract/bulbagarden.py`'s docstring for the exact technique)
2. Batch-resolve each file title to its real CDN download URL + size/mime/sha1 via
   `action=query&titles=<pipe-joined titles>&prop=imageinfo&iiprop=url|size|mime|sha1`
3. Download the resolved URLs' bytes to a local cache and join to canonical PokéAPI
   records via the `bulbagarden_title_to_pokeapi_form` controlled mapping seed (see
   `dbt/seeds/schema.yml` for the reconciliation rules)

Type and item icons used only by team-card rendering (not part of the dataset
itself) come from a different source: PokéAPI's community sprites GitHub repo
([github.com/PokeAPI/sprites](https://github.com/PokeAPI/sprites)), fetched
directly by `pipelines/render/assets.py` as plain, deterministically-named raw
GitHub file URLs (no listing/discovery call needed).

## 6. Limitless VGC
**Best for:** Canonical shared team-list identity, and independent cross-validation of MunchStats rosters

Limitless publishes tournament standings and the team lists behind them. Its
distinguishing feature is not coverage but **identity**: a `/teams/<id>` is a
canonical team *composition*, reused across every player and event that
fielded it, where MunchStats mints a fresh team id per player per event. That
is what makes `team_list`/`team_list_member` possible, and it is the reason
this source is in scope.

**Two corrections to this entry's earlier description**, both established by
measurement (backlog.md #26):

- **No browser automation is needed.** limitlessvgc.com is server-rendered
  and every page below is a plain HTTP GET, with most fields on `data-`
  attributes. The previous "use a Table Capture extension to screenshot
  tables" recipe was never necessary.
- **It does not extend tournament history.** Only three Champions-format
  (`m-a`) events exist anywhere as of this writing, and MunchStats already
  has all three. Limitless' other tournaments are standard VGC (regulations
  F/H/I), which is out of v1 scope. It is in fact *narrower* per event:
  team lists are published for the day-2 cut only (156 of 1,096 players at
  NAIC 2026).

**Key coverage:**
- Canonical team-composition ids, shared across players and events
- Per-slot held item, ability, nature and moveset (100% populated for
  Champions events); no EV/IV spreads — see source 7
- Standings with placement, player and country, for the day-2 cut
- The event's regulation set, and its RK9 event id

**How to extract:**
1. `GET https://limitlessvgc.com/tournaments?time=all` — one `<tr>` per
   tournament carrying `data-date`/`data-country`/`data-name`/`data-format`/
   `data-players`/`data-winner` plus a `/tournaments/<id>` link.
   `data-format` is the regulation set, so Champions events are selectable
   without fetching them.
2. `GET /tournaments/<id>` — standings rows carrying `data-rank`/`data-name`/
   `data-country`, a `/players/<id>` link, and a `/teams/<id>` link where a
   list was published. This page also links out to the event on RK9, which
   yields `rk9_event_id` — a real join key to `tournament_event`, since
   MunchStats reuses RK9's ids (names and dates agree between the sources on
   neither).
3. `GET /teams/<id>` — the team list: six `div.pkmn[data-id]` blocks with
   item, ability, nature and moves. Fetch per distinct team id, not per
   player; teams are shared.
4. Join to canonical records via the `limitless_slug_to_pokeapi_form` seed,
   plus `limitless_mega_item_to_pokeapi_form` — Limitless publishes the base
   species holding its Mega Stone where MunchStats publishes the evolved
   form, so a Mega slot needs the item to resolve correctly (see
   `dbt/seeds/schema.yml`).

## 7. Victory Road — UNREACHABLE, and its unique value does not exist
**Previously listed for:** detailed EV spreads and verified movesets

**Status: not ingestible, and superseded.** This entry previously pointed at
`victory-road.com` and described exporting "Showdown Paste" format teams.
Both halves were wrong, and the correction is worth recording rather than
silently deleting (backlog.md #25):

1. **`victory-road.com` does not resolve at all** — it has no DNS record. The
   real site is `victoryroadvgc.com`.
2. **`victoryroadvgc.com` is unreachable from this project's egress.** It is
   permitted by network policy (a CONNECT tunnel is established, HTTP 200)
   but the origin resets the TLS handshake immediately after ClientHello.
   Reproduced across TLS 1.2 and 1.3, with and without ALPN, via curl and
   `openssl s_client`, while control hosts complete the handshake normally.
   This is not something the pipeline can work around.
3. **Most importantly, the EV spreads this source was wanted for are not
   published by anyone.** Official tournament team sheets — RK9's own, which
   both Limitless and MunchStats ultimately derive from — report Ability,
   Held Item, "Stat Alignment" (nature) and moves, and nothing else.
   Verified directly against `rk9.gg/teamlist/public/{event}/{team}` and
   `limitlessvgc.com/teams/{id}`: zero EV or IV data on either. Any EV
   spread published elsewhere is community-reconstructed, not sourced.

The other half of what this entry promised — verified movesets, items,
abilities and natures — is already fully covered by MunchStats and
Limitless at 100% for Champions events (source 6 below).

Treat EV/IV spreads as **structurally unavailable**, not merely deferred.
Reopen only if a source begins publishing them with real provenance.

## 8. RK9.gg
**Best for:** Round-by-round pairings and real head-to-head match outcomes

RK9 is the tournament software the events themselves run on — MunchStats
scrapes it for rosters, and Limitless links out to it. It publishes the
pairings for every round: who played whom, at which table, and who won. This
is the only source in this catalog that answers "what actually beats X",
and it closes backlog.md #27, which had been recorded as underivable on the
grounds that MunchStats reports only team-level records.

**Key coverage:**
- One row per played match, per round, per division (Masters/Senior/Junior)
- Winner/loser, ties, and byes
- Each player's running win/loss/tie record at that point in the event
- Player name and country, which resolve to this dataset's own team ids

**How to extract:**
1. `GET https://rk9.gg/pairings/{event_id}` — the shell. Its division tab
   strip (`<a id="P{pod}-tab" ...>Masters in Round 17</a>`) names every pod,
   its division label, and the highest round reached.
2. `GET https://rk9.gg/pairings/{event_id}?pod={pod}&rnd={n}` — one round's
   pairings as an HTML fragment. htmx lazy-loads these in the browser; a
   plain GET works identically. Enumerate rounds from the tab strip, **not**
   from the fragments' own `hx-get` attributes: the currently active round is
   rendered inline and has no `hx-get`, so reading only those silently drops
   the final round of every event.
3. Parse by cell: every cell carries
   `id="cell-{pod}-{round}-{index}-{slot}"`, slots 1 and 2 being the players
   and slot 3 the table number, with `winner`/`loser` on the player cell's
   class list. An empty second cell is a bye.
4. `event_id` needs no mapping: MunchStats reuses RK9's own event ids, so
   this joins straight to `tournament_event.event_id`. Players resolve to
   `team_id` on (name, country) — measured at 99.8% across 24,139 Masters
   pairing slots. A (name, country) two entrants share (it appears twice in
   one round, or twice on the roster) is left unresolved rather than
   guessed, and only Masters pairings resolve: MunchStats has no Junior or
   Senior rosters.
5. Day 2 and the top cut are not published as fields; `int_event_phases`
   reads them off the round structure (`docs/dashboard.md`, Sprint 13).

Note the grain honestly: an outcome is **team vs team**. RK9 publishes no
per-battle log naming which four of a team's six Pokémon were brought, or
which knocked out which. That remains genuinely unsourced.

## 9. Limitless online tournaments (play.limitlesstcg.com)
**Best for:** A large, fast sample: hundreds of grassroots online events per
regulation, with full sheets, records and pairings

Limitless runs an online tournament platform alongside limitlessvgc.com's
coverage of official events. Every Champions regulation sees hundreds of
events there, many with published team sheets: in the first six weeks of
M-C, 236 qualifying events and 13,457 published sheets, about 3.6 times
the official sample (3,770 teams), and the first results of a new regulation arrive
within days rather than weeks. Added 2026-10-21 (`docs/upgrade-plan-
2027q2.md`, S1, decision D1) as its own population, never blended into the
official figures by default.

**Key coverage:**
- Tournament name, date, format label (`M-C`), entrant count, organiser
- Per player: handle, display name, country, placing, W-L-T, drop round,
  and (when the organiser publishes lists) the six-Pokémon sheet with item,
  ability, nature and moves
- Every round's pairings and winner, Swiss and top cut (`phase`)

**How to extract:** a public JSON API
([docs](https://docs.limitlesstcg.com/developer.html)), no scraping:
1. `GET /api/tournaments?game=VGC&limit=500&page=N` — newest first; page
   until the listing passes the lookback date.
2. `GET /api/tournaments/{id}/standings` — players, placings, records and
   `decklist` (the sheet; absent when unpublished).
3. `GET /api/tournaments/{id}/pairings` — `round`, `phase`, `table`,
   `player1`, `player2` (absent for a bye) and `winner` (a handle, `0` for
   a tie, `-1` for no result).
4. Keep a tournament when its `format` is a registered
   `limitless_play_format` (`dbt/seeds/champions_regulations.csv`), it has
   at least 16 players, and its name isn't a Monotype event (house rules on
   top of the format would skew usage).
5. Resolve the regulation from the label, unless the tournament is dated
   after that regulation ended and fewer than 95% of its slots are legal
   under it: organisers keep the old label for weeks after a rollover (31
   "M-B" tournaments ran in September 2026, after M-C began; 29 had
   Rillaboom, legal only in M-C, on half their teams), so such a
   tournament takes the regulation in force on its date. The two that
   really were M-B (98–99% legal in it) keep their label.
   `assert_online_regulation_legality` fails the build if fewer than 95% of
   a regulation's online slots are legal in it.
6. Resolve species slugs with limitlessvgc.com's seeds
   (`limitless_slug_to_pokeapi_form`, then
   `limitless_mega_item_to_pokeapi_form` for a Mega Stone holder), falling
   back to the PokéAPI form of the same name.

**Limits and identity:** 50 requests per 5 minutes without a key
(`pipelines/extract/limitless_play.py` paces every call through one
sliding-window limiter and waits out a 429); a key for public-facing
projects raises it (`LIMITLESS_API_KEY`). Players are handles, not legal
names, so online teams never join RK9 or MunchStats identities and get no
player pages.

## 10. Smogon usage statistics (smogon.com/stats)
**Best for:** The Showdown ladder as its own population: usage, the only
Pokémon-vs-Pokémon battle signal any source publishes, and Stat Point
spreads

Smogon publishes, on the first of each month, usage statistics for every
Pokémon Showdown ladder, computed from every rated battle. September
2026's Champions Reg M-C file covers 1,631,943 Bo1 battles and 277
Pokémon at the 1760 cutoff. Added 2026-10-23 (`docs/upgrade-plan-2027q2.md`,
S2, decisions D2 and D3) as a separate `ladder` population, never blended
into tournament figures. Credit: Smogon University and Pokémon Showdown.

**Key coverage (per Pokémon, per file):**
- `usage`: weighted share of teams, the same unit as tournament team share
- `Checks and Counters`: per opponent, `n` (encounters where the pair met
  and one was KO'd or switched out), `p` (the share in which this Pokémon
  was the one) and `d` (its standard deviation). Smogon ranks by `p - 4d`
- `Spreads`: nature and Stat Points (`Adamant:32/32/0/0/2/0`, HP/Atk/Def/
  SpA/SpD/Spe), weighted. Every spread fits Champions' 66 points with at
  most 32 in one stat
- Abilities, items, moves and teammates, which tournament sheets already
  cover, are not extracted

**How to extract:** static files, no API:
1. `GET /stats/` lists the months; `GET /stats/<YYYY-MM>/chaos/` lists a
   month's files.
2. A file is `<metagame>[bo3]-<cutoff>.json`. The metagame is the
   regulation registry's `munchstats_format`
   (`gen9championsvgc2026regmc`), so nothing hardcodes a regulation.
   Cutoffs 0, 1500, 1630 and 1760 exist; 1760 (rating-weighted toward the
   strongest players) and 0 (every battle) are kept, Bo1 and Bo3.
3. For each regulation take the newest month it was in force for at least
   half of: August 2026 for M-B, which ended on 9 September, and
   September for M-C, which began on the 9th. A month never changes after
   publication, so a file the previous snapshot holds is reused.
4. Resolve names with `munchstats_name_to_pokeapi_form` (Showdown and
   MunchStats share names), then the slug rule that seed was built with,
   then `smogon_name_to_pokeapi_form` for the two names neither handles.
   All 333 names in the September 2026 files resolve.

**Checks and counters at 1760:** the rating-weighted files carry almost
none (13 pairs in September's M-C file, against 35,013 at cutoff 0).
Smogon lists a pair only above about 20 encounters (the smallest `n` in
either file is 21), a doubles battle rarely reaches the one-on-one moments
the statistic counts, and at 1760 each encounter is weighted by the chance
its players are rated that high, so almost no pair clears the bar. They are
read from the all-ratings files, and labelled so.

