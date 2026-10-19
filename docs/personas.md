# Personas

Written 2026-10-19. These are the people the dashboard and dataset are built
for. Use them to decide what to build, what to show first and what to cut.
`docs/prd.md`'s "Target users" lists the same groups in one line each; this
document is the working version.

Each persona is a role, not a demographic. One person can be several of them
in the same week: a player who scouts opponents on Friday and builds a team on
Sunday is both the Scout and the Grinder.

Every persona works inside the same data limits. No source publishes EV/IV
spreads, and head-to-head results are team-vs-team, not Pokémon-vs-Pokémon
(see `CLAUDE.md`). A feature that only works by hiding one of those limits is
out of scope for every persona below.

## Summary

| Persona | Priority | One-line job | Lives in |
|---|---|---|---|
| **Grinder** (competitive player) | Primary | "Build a team that does well at my next event in the current regulation." | Pokémon, Builder, Meta → Tier List |
| **Creator** (content creator) | Primary | "Explain what changed this week, with numbers I can cite and images I can post." | Meta → Overview, event pages, share/copy |
| **Scout** (coach, captain, player prepping for opponents) | Secondary | "Know what a specific player or the top tables are likely to bring." | Teams → Players, Top Teams, Matchup |
| **Newcomer** (new to VGC/Champions) | Secondary | "Tell me what's good and give me a team I can copy and learn from." | Meta → Tier List, Top Teams, Pokémon |
| **Analyst** (data consumer) | Secondary | "Get clean, versioned tables with provenance I can query myself." | Data, `releases/`, JSON feed |
| **Maintainer** (runs this repo) | Internal | "Keep the site current and correct with little hands-on time." | CI, workflows, Data → Sources |

"Primary" means a design conflict is settled in that persona's favour. When the
Grinder and the Analyst want different things above the fold, the Grinder wins
and the Analyst's need moves to the Data section.

---

## Grinder — the competitive player

**Who:** plays Champions VGC seriously and attends Regionals or online
tournaments a few times a regulation. Knows the vocabulary (Fake Out,
Trick Room, Wilson interval maybe not). Builds teams on a laptop, then checks
things on a phone at the venue between rounds.

**Jobs to be done**

1. "When a new regulation drops, I want to see which Pokémon are winning
   and which are just popular, so I don't build around a trap."
2. "When I pick a Pokémon, I want the set people actually run, items,
   ability, nature and moves together, so I can copy it into Showdown."
3. "When I have four or five team members, I want to see what's missing:
   coverage holes, speed control, shared weaknesses, the top threats I can't
   touch."
4. "Between rounds, I want to look one Pokémon up on my phone in under ten
   seconds."

**Pain points today** (from the 2026-10-19 UI review, `docs/upgrade-plan-2027q1.md`)

- The most common set is built slot by slot, so it can show a combination of
  item, nature and moves that almost no one runs together.
- The Back button doesn't move between views, and a Pokémon page can't be
  linked or bookmarked.
- Ranked lists are card grids that show about 12 Pokémon a screen, with the
  18 type chips taking up the filter panel.
- The damage calculator starts from a blank set instead of the set people
  run.

**Success looks like:** from a cold start on a phone, the Grinder reaches a
Pokémon's page and copies its set in two taps and under ten seconds.
They come back each week of a regulation.

**Not for them:** EV spread suggestions (no source publishes EVs) and a
battle simulator (a PRD non-goal).

## Creator — the content creator

**Who:** makes YouTube videos, X/Bluesky threads, newsletters or stream
segments about the Champions meta, usually right after a big event. Needs to
be first and right, and needs visuals.

**Jobs to be done**

1. "After a Regional, I want a one-page recap: who won, the top-8 teams, and
   which Pokémon over- or under-performed against the regulation average."
2. "I want to quote a number with its sample size and source, so the
   comments don't tear it apart."
3. "I want an image or a link I can drop straight into a post, which opens
   on exactly the view I'm talking about."
4. "I want to see what changed since a particular event, not only since
   the regulation started."

**Pain points today**

- No per-event view. The "latest event spotlight" from the Q4 plan is not
  built.
- Links carry the regulation and the tab, but not the Pokémon, the
  sub-view or the filters.
- The "What changed" panel compares 3,770 M-C teams with 395 M-B teams, and
  nearly all of those come from Worlds. That baseline is easy to
  misquote.
- Nothing produces a shareable image, although `pipelines/render/` already
  renders team cards.

**Success looks like:** a recap post can be written from the site alone,
and each number in it links back to the view it came from.

**Not for them:** claims that "Pokémon X beats Pokémon Y". The data is
team-vs-team, and the site must keep saying so.

## Scout — the coach or opponent-prepper

**Who:** a team captain, coach, or a player the night before Day 2 who knows
their pairings. Thinks in players and tables, not in Pokémon.

**Jobs to be done**

1. "Given a player's name, show me what they've brought at past events and
   how they placed."
2. "Show me what the top tables of the last event brought, so I can test
   against them."
3. "Which archetypes does my team lose to at the team level, and how big is
   that sample?"

**Pain points today**

- Players & Regions → By player is a list of signature Pokémon. There's no
  player page with event history and the actual teams.
- Top Teams shows a win rate without the record or placement next to it.

**Success looks like:** typing a player's name brings up every team they've
registered in the selected regulation, with placements, in under three
interactions.

**Ground rules:** show only what the source events published. No
cross-referencing beyond tournament data, and no inferred personal data.

## Newcomer — new to VGC or to Champions

**Who:** a Pokémon fan who played the games, maybe the anime-to-Showdown
pipeline, and wants into competitive. Doesn't know what "roster share",
"HHI" or "synergy lift" mean.

**Jobs to be done**

1. "Tell me which Pokémon are strong right now, in plain words."
2. "Give me a complete team that did well that I can copy and play."
3. "Explain the jargon when I hit it, without making me leave the page."

**Pain points today**

- The UI shows "HHI 0.57", "Locked in", "+3.6 pts", "Wilson lower bound" and
  "synergy lift" with no inline explanation.
- Top Teams has no one-click "copy this team" for Showdown.
- The Matchup intro tells readers to see `docs/design-system.md`, an
  internal file path.

**Success looks like:** a Newcomer can go from the landing page to a copied,
tournament-proven team without hitting an unexplained term.

## Analyst — the data consumer

**Who:** writes SQL or pandas, builds their own charts or models, and cares
about provenance, versioning and method more than layout. Includes other
tool-builders who want a stable feed.

**Jobs to be done**

1. "Download a versioned release with a manifest and changelog, and trust
   that the keys join."
2. "Know exactly how each dashboard number was computed."
3. "Pull a stable JSON or CSV feed into my own tool without scraping the
   page."

**Pain points today**

- The newest published release is 0.3.0, which predates M-B and M-C.
  0.4.0 is deferred over the ~55MB git cost (Q4 plan A7).
- The method explanations are scattered across tab intros. There's no
  single "how to read this" or data dictionary page on the site.
- The header gives prime space to pills like "dataset 0.3.0", "snapshot"
  and "all gates passing". They matter to the Analyst and to nobody else.

**Success looks like:** a release exists for the current regulation, and
each mart on the site links to its definition.

## Maintainer — runs the pipeline

**Who:** the repository owner, or a contributor working through
`.claude/loop.md`. Wants the weekly refresh to just work and wants to hear
quickly when it doesn't.

**Jobs to be done**

1. "When a new regulation is announced, add one seed row and have
   everything else follow."
2. "Know that the site is stale or broken before users do."
3. "Change the UI without silently breaking a view."

**Pain points today**

- M-C ends 2026-12-02 and the registry has no next row yet. The site's
  "current regulation" logic hasn't been exercised across a rollover.
- A regulation remembered in `localStorage` outranks the regulation in
  force. A returning visitor who once picked M-C will stay on M-C after
  the next set starts.
- No test loads the built page in a browser. `tests/unit/dashboard/` checks
  the Python build and JS duplication only, so a view that throws at
  runtime ships unnoticed. There's no performance budget either.

**Success looks like:** the next regulation goes live on the site the week
it starts, from one seed row, with no hand edits.

---

## Persona × surface map

P = primary audience for the surface, S = secondary, blank = not designed for
them.

| Surface | Grinder | Creator | Scout | Newcomer | Analyst |
|---|---|---|---|---|---|
| Meta → Overview ("What changed") | S | P | | S | |
| Meta → Tier List | P | S | | P | |
| Meta → Usage / Speed Tiers | P | S | | | S |
| Pokémon hub (profile, compare) | P | S | | P | |
| Pokémon → Matchup | P | | S | | |
| Teams → Top Teams / Archetypes | S | S | P | P | |
| Teams → Players (player pages) | | S | P | | |
| Event pages (planned) | S | P | P | | |
| Builder | P | | S | S | |
| Data & Sources | | S | | | P |
| Releases / JSON feed | | | | | P |

## Anti-personas

The site is not built for these, and it should not be changed to suit them:

- **Someone looking for EV spreads or exact damage benchmarks for a specific
  spread.** No source publishes EVs. The calculator stays a stat-and-setup
  estimate.
- **Someone who wants real-time help during a live battle.** The data is
  weekly tournament data, and in-battle assistance is out of scope.
- **Someone who wants individual Pokémon-vs-Pokémon win rates.** The source
  grain is team-vs-team, and inventing finer attribution would be wrong.
