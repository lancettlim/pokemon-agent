/* Events (docs/upgrade-plan-2027q1.md, C1) and the Overview's "Latest
 * event" card and "Copy and play" starter teams (C1, P5). Loaded after
 * app.js/teams.js and reuses window.DashboardApp.
 *
 *   #/events            every official event in the selected regulation,
 *                       the upcoming Limitless online tournaments in the
 *                       visitor's time zone (list #31), then the past ones
 *                       (docs/upgrade-plan-2027q2.md, S1), which link out
 *                       to play.limitlesstcg.com rather than to an event
 *                       page of ours
 *   #/event/<event_id>  one event: header, top 8 with full sets, the
 *                       top-cut bracket with each player's path and Day 2
 *                       conversion (docs/upgrade-plan-2027q2.md, E1, E2),
 *                       and the Pokémon its field over- and under-used
 *                       against the regulation average
 *
 * Event pages work in any regulation scope: an event carries its own
 * regulation, and the marts they read (tournament_event_summary,
 * tournament_top_cut_teams, tournament_team_sheets,
 * pokemon_event_usage_vs_regulation) are not partitioned by scope. */
(function () {
  "use strict";

  var App = window.DashboardApp;
  if (!App) return;

  var marts = App.marts;
  var esc = App.escapeHtml;

  // Below this many teams, an event's over/under-performer deltas are
  // mostly noise and are withheld -- the same floor as the "What changed"
  // panel's regulation-to-regulation deltas (data.py's MIN_MOVER_TEAMS).
  var MIN_EVENT_DELTA_TEAMS = 100;
  var MAX_PERFORMERS = 8;
  // A Pokémon on this few teams in both the event and the regulation isn't
  // an over- or under-performer worth listing, whatever its delta (0.5% of
  // roster slots before team share became the unit).
  var MIN_PERFORMER_SHARE = 0.03;

  function regulationLink(code) {
    return code ? esc(App.shortRegulation(code)) : "";
  }

  // ---------- Overview: latest event + starter teams ----------
  function renderOverviewCards() {
    var row = document.getElementById("overview-row");
    var latestEl = document.getElementById("overview-latest-event");
    var startersEl = document.getElementById("overview-starters");
    var kpis = App.DATA.kpis || {};
    var latest = kpis.latest_event;
    // An online tournament ("LP-" id) has no event page to link to; the
    // build never puts one here (data.py's OFFICIAL_ONLY_KPIS), and this
    // keeps it that way.
    if (latest && String(latest.event_id || "").indexOf("LP-") === 0) latest = null;
    var starters = kpis.starter_teams || [];
    if (latestEl && latest) {
      latestEl.innerHTML =
        '<div class="latest-event">' +
        // Online events have no event pages: on an Online or All scope the
        // card is the regulation's latest official event, and says so.
        '<p class="eyebrow">' + (App.isOfficialScope ? "Latest event" : "Latest official event") + "</p>" +
        '<h3><a href="' + App.routeHash("event", [latest.event_id]) + '">' + esc(latest.event_name) + "</a></h3>" +
        '<p class="sub">' + esc(latest.event_date) + " · " + esc(latest.event_tier || "") + " · " +
        Number(latest.team_count || 0).toLocaleString() + " teams</p>" +
        (latest.winner_player_name
          ? '<p class="latest-event-winner">' + App.phaseChipHtml("Champion") + " " +
            App.playerLineHtml({
              player_name: latest.winner_player_name,
              player_country: latest.winner_player_country,
              record_wins: latest.winner_record_wins,
              record_losses: latest.winner_record_losses,
            }) + "</p>" +
            // The winner's sheet rides in the inline KPIs, so the strip
            // shows held items with no fetch (V3).
            App.teamStripHtml(
              (latest.winner_sets && latest.winner_sets.length)
                ? latest.winner_sets
                : String(latest.winner_pokemon_keys || "").split("|").filter(Boolean).map(function (k) {
                    return { pokemon_key: k };
                  }),
              { label: latest.winner_player_name + "'s winning team" }
            )
          : "") +
        '<p><a class="btn btn-sm" href="' + App.routeHash("event", [latest.event_id]) + '">Top 8 and sets</a> ' +
        '<a class="btn btn-sm" href="' + App.routeHash("events", []) + '">All events</a></p>' +
        "</div>";
    }
    if (startersEl && starters.length) {
      startersEl.innerHTML =
        '<p class="eyebrow">Copy and play</p>' +
        '<p class="sub">The top-placing fully reported teams in ' + esc(App.officialScopeName) +
        ", ready to paste into Showdown.</p>" +
        '<div class="starter-strip">' + starters.map(function (team) {
          return App.teamCardHtml(team);
        }).join("") + "</div>";
    }
    if (row) row.hidden = !(latest || starters.length);
  }

  // ---------- Events index ----------
  function setupEvents() {
    var table = App.createDataTable(document.getElementById("events-table"), {
      officialOnly: true,
      caption: "Champions events",
      sort: { key: "event_date", dir: "desc" },
      rowHref: function (r) { return App.routeHash("event", [r.event_id]); },
      empty: "No events in this regulation yet.",
      columns: [
        {
          key: "event_name",
          label: "Event",
          main: true,
          sortable: true,
          render: function (r) {
            return '<a href="' + App.routeHash("event", [r.event_id]) + '" title="' + esc(r.event_name) + '">' +
              esc(App.shortEventName(r.event_name)) + "</a>";
          },
        },
        { key: "event_date", label: "Date", main: true, sortable: true },
        { key: "event_tier", label: "Tier", sortable: true },
        {
          key: "regulation_code",
          label: "Reg",
          sortable: true,
          hideOnPhone: true,
          render: function (r) { return regulationLink(r.regulation_code); },
        },
        { key: "team_count", label: "Teams", type: "int", main: true },
        { key: "match_count", label: "Matches", type: "int", hideOnPhone: true },
        {
          key: "winner_player_name",
          label: "Winner",
          sortable: true,
          render: function (r) {
            return r.winner_player_name
              ? '<span class="winner-cell">' + App.teamCompositionHtml(r.winner_pokemon_keys, 24) +
                "<span>" + esc(r.winner_player_name) + "</span></span>"
              : "—";
          },
        },
      ],
    });
    table.setRows(App.eventsInScope());
    var note = document.getElementById("events-note");
    if (note) {
      var events = App.eventsInScope();
      var teams = events.reduce(function (sum, e) { return sum + (e.team_count || 0); }, 0);
      note.textContent = events.length + " official event" + (events.length === 1 ? "" : "s") + " · " +
        teams.toLocaleString() + " teams in " + App.scopeLabel(App.regulationCode) + ".";
    }
    setupUpcomingEvents();
    setupOnlineEvents();
  }

  // Upcoming online tournaments (docs/upgrade-plan-2027q2.md, list #31),
  // in the visitor's own time zone, grouped by their local day. The list is
  // as old as the last build, so anything that has started is dropped here.
  var UPCOMING_DAYS = 14;
  var UPCOMING_LIMIT = 24;

  function localDayKey(date) {
    return date.getFullYear() + "-" + (date.getMonth() + 1) + "-" + date.getDate();
  }

  function upcomingDayLabel(date, now) {
    var tomorrow = new Date(now.getTime());
    tomorrow.setDate(tomorrow.getDate() + 1);
    if (localDayKey(date) === localDayKey(now)) return "Today";
    if (localDayKey(date) === localDayKey(tomorrow)) return "Tomorrow";
    return date.toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "short" });
  }

  function setupUpcomingEvents() {
    var head = document.getElementById("upcoming-events-head");
    var note = document.getElementById("upcoming-events-note");
    var list = document.getElementById("upcoming-events-list");
    if (!head || !list) return;
    var now = new Date();
    var horizon = now.getTime() + UPCOMING_DAYS * 864e5;
    var rows = (marts.online_upcoming_events || []).filter(function (e) {
      var starts = Date.parse(e.starts_at_utc);
      return (App.regulationCode === App.ALL_SCOPE || e.regulation_code === App.regulationCode) &&
        starts > now.getTime() && starts <= horizon;
    }).sort(function (a, b) { return Date.parse(a.starts_at_utc) - Date.parse(b.starts_at_utc); });
    head.hidden = note.hidden = list.hidden = !rows.length;
    if (!rows.length) return;
    var zone = "";
    try { zone = Intl.DateTimeFormat().resolvedOptions().timeZone || ""; } catch (e) { zone = ""; }
    var read = rows[0].extracted_at_utc ? new Date(Date.parse(rows[0].extracted_at_utc)) : null;
    var shown = rows.slice(0, UPCOMING_LIMIT);
    note.innerHTML = rows.length.toLocaleString() + " Limitless online tournament" + (rows.length === 1 ? "" : "s") +
      " in the next " + UPCOMING_DAYS + " days, in your time zone" + (zone ? " (" + esc(zone) + ")" : "") + ". " +
      "Organiser-run events; registrations as of " +
      (read && !isNaN(read) ? esc(read.toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })) : "the last update") +
      ". " + (rows.length > shown.length ? "The next " + shown.length + " are below; " : "") +
      '<a href="https://play.limitlesstcg.com/tournaments/upcoming?game=VGC" target="_blank" rel="noopener">the full list is on Limitless</a>.';
    var html = "";
    var lastDay = null;
    shown.forEach(function (e) {
      var starts = new Date(Date.parse(e.starts_at_utc));
      var day = localDayKey(starts);
      if (day !== lastDay) {
        if (lastDay !== null) html += "</ol>";
        html += '<h4 class="upcoming-day">' + esc(upcomingDayLabel(starts, now)) + '</h4><ol class="upcoming-list">';
        lastDay = day;
      }
      var seats = e.registrations == null ? "" :
        e.registrations.toLocaleString() + (e.player_cap ? " / " + e.player_cap.toLocaleString() : "") + " registered";
      html += '<li class="upcoming-item">' +
        '<time class="upcoming-time" datetime="' + esc(e.starts_at_utc) + '">' +
        esc(starts.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })) + "</time>" +
        '<span class="upcoming-main"><a href="' + esc(e.source_url) + '" target="_blank" rel="noopener">' + esc(e.tournament_name) + "</a>" +
        '<span class="sub">' + [e.organizer_name, e.platform].filter(Boolean).map(esc).join(" · ") + "</span></span>" +
        '<span class="upcoming-seats">' + esc(seats) +
        '<span class="upcoming-reg' + (e.registration_open ? " is-open" : "") + '">' +
        (e.registration_open ? "Registration open" : "Not open yet") + "</span></span></li>";
    });
    list.innerHTML = html + "</ol>";
  }

  // Online tournaments (S1): their own list, never mixed into the official
  // one above. Handles are not legal names, so a winner is shown as the
  // platform spells them, with no player page.
  function setupOnlineEvents() {
    var rows = (marts.online_event_summary || []).filter(function (e) {
      return App.regulationCode === App.ALL_SCOPE || e.regulation_code === App.regulationCode;
    });
    var head = document.getElementById("online-events-head");
    var note = document.getElementById("online-events-note");
    var container = document.getElementById("online-events-table");
    if (!container || !rows.length) return;
    head.hidden = false;
    note.hidden = false;
    var teams = rows.reduce(function (sum, e) { return sum + (e.team_count || 0); }, 0);
    note.textContent = rows.length.toLocaleString() + " Limitless online tournament" + (rows.length === 1 ? "" : "s") +
      " with at least 16 players · " + teams.toLocaleString() + " published team sheets in " +
      App.scopeLabel(App.regulationCode) + ". Each links to its page on Limitless. " +
      "The Online scope (the Events select at the top) puts their usage figures beside the official ones.";
    App.createDataTable(container, {
      caption: "Online tournaments",
      // Cited as what it is, whichever scope the page shows.
      citation: function () {
        return {
          scope: "Limitless online tournaments, " + App.shortRegulation(App.regulationCode),
          sample: "n = " + teams.toLocaleString() + " teams",
        };
      },
      sort: { key: "event_date", dir: "desc" },
      limit: 50,
      empty: "No online tournament in this regulation yet.",
      columns: [
        {
          key: "event_name",
          label: "Tournament",
          main: true,
          sortable: true,
          render: function (r) {
            return '<a href="' + esc(r.source_url) + '" target="_blank" rel="noopener">' + esc(r.event_name) + "</a>";
          },
        },
        { key: "event_date", label: "Date", main: true, sortable: true },
        { key: "registered_player_count", label: "Players", type: "int", hideOnPhone: true },
        { key: "team_count", label: "Teams", type: "int", main: true },
        {
          key: "winner_player_name",
          label: "Winner",
          sortable: true,
          render: function (r) {
            if (r.winner_count > 1) return "Shared by " + r.winner_count;
            return r.winner_player_name
              ? '<span class="winner-cell">' + App.teamCompositionHtml(r.winner_pokemon_keys, 24) +
                "<span>" + esc(r.winner_player_name) + "</span></span>"
              : "—";
          },
        },
      ],
    }).setRows(rows);
  }

  // ---------- Event page ----------
  var currentEvent = null;
  function performerTable(container, caption) {
    return App.createDataTable(container, {
      caption: caption,
      sort: null,
      citation: function () {
        return currentEvent
          ? App.shortEventName(currentEvent.event_name) + ", n = " +
            Number(currentEvent.team_count || 0).toLocaleString() + " teams"
          : null;
      },
      rowHref: App.pokemonRowHref,
      columns: [
        { key: "pokemon_name", label: "Pokémon", type: "pokemon", main: true, sortable: true },
        {
          key: "event_team_share",
          label: "At this event",
          type: "share",
          main: true,
          title: function (r) {
            return r.usage_count.toLocaleString() + " of " + r.event_team_count.toLocaleString() + " teams · " +
              App.formatPercent(r.event_usage_share) + " of roster slots";
          },
        },
        { key: "regulation_team_share", label: "Regulation", type: "percent" },
        {
          key: "team_share_delta",
          label: "Difference",
          numeric: true,
          sortable: true,
          render: function (r) {
            var pts = (r.team_share_delta || 0) * 100;
            return '<span class="badge ' + (pts > 0 ? "badge-positive" : "badge-negative") + '">' +
              (pts > 0 ? "+" : "") + pts.toFixed(1) + " pts</span>";
          },
        },
        { key: "usage_count", label: "Teams", type: "int" },
      ],
    });
  }

  var overTable = null;
  var underTable = null;

  // The event's Top 12 cards (V8): every team there, and Day 2's.
  function eventCardsHtml(event) {
    var cards = (((App.DATA.share_cards || {}).top12 || {}).event || {})[event.event_id] || {};
    var short = App.shortEventName(event.event_name);
    var parts = [["all", "All players"], ["day2", "Day 2"]].filter(function (p) {
      return cards[p[0]] && Object.keys(cards[p[0]]).length;
    }).map(function (p) {
      return '<span class="event-card-pair"><span class="phase-chip">' + esc(p[1]) + "</span>" +
        App.shareCardControlsHtml(cards[p[0]], "Top 12 Pokémon · " + short + (p[0] === "day2" ? " · Day 2" : "")) + "</span>";
    });
    return parts.length ? '<p class="event-cards"><strong>Top 12 card</strong> ' + parts.join("") + "</p>" : "";
  }

  // ---------- Top-cut bracket and paths (E2) ----------
  // Team vs team: a match says which team beat which; no source names the
  // Pokémon brought to each game, and the page says so.
  var bracketState = { eventId: null, round: null, pathTeam: null };

  function byTable(a, b) {
    return (a.table_number || 0) - (b.table_number || 0);
  }

  // Each round's matches in bracket order: from the final backwards, the
  // two matches that fed a match sit together, side 1's first.
  function bracketRounds(rows) {
    var rounds = {};
    rows.forEach(function (r) { (rounds[r.bracket_round] = rounds[r.bracket_round] || []).push(r); });
    var order = Object.keys(rounds).map(Number).sort(function (a, b) { return a - b; });
    var ordered = {};
    ordered[order[order.length - 1]] = rounds[order[order.length - 1]].slice().sort(byTable);
    for (var i = order.length - 2; i >= 0; i--) {
      var pool = rounds[order[i]].slice();
      var list = [];
      ordered[order[i + 1]].forEach(function (m) {
        [m.team_id_1, m.team_id_2].forEach(function (team) {
          for (var k = 0; team && k < pool.length; k++) {
            if (pool[k].team_id_1 === team || pool[k].team_id_2 === team) {
              list.push(pool.splice(k, 1)[0]);
              return;
            }
          }
        });
      });
      ordered[order[i]] = list.concat(pool.sort(byTable));
    }
    return order.map(function (round) {
      return { round: round, label: ordered[round][0].round_label, matches: ordered[round] };
    });
  }

  function bracketSideHtml(m, n) {
    var team = m["team_id_" + n];
    var name = m["player_name_" + n];
    var won = !!(m.winner_team_id && team && m.winner_team_id === team);
    var player = name
      ? '<button type="button" class="bracket-player" data-path-team="' + esc(team) + '" aria-expanded="' +
        (bracketState.pathTeam === team) + '" aria-controls="event-path" title="Show ' + esc(name) + "'s path" + '">' +
        App.playerLineHtml({ player_name: name, player_country: m["player_country_" + n] }, { noLink: true }) +
        "</button>"
      : '<span class="bracket-player is-unknown">Player not on the roster</span>';
    return '<div class="bracket-side' + (won ? " is-winner" : "") + '">' + player +
      '<span class="sb-score" aria-label="' + (m.winner_team_id ? (won ? "won" : "lost") : "no result") + '">' +
      (m.winner_team_id ? (won ? "W" : "L") : "") + "</span>" +
      App.teamCompositionHtml(m["pokemon_keys_" + n], 24) + "</div>";
  }

  // A curated video of the match (featured_match_vods, S5 and E5), opening
  // on YouTube at the match.
  function vodLinkHtml(m) {
    if (!m.vod_url || !/^https:\/\/www\.youtube\.com\//.test(m.vod_url)) return "";
    var who = [m.player_name_1, m.player_name_2].filter(Boolean).join(" vs ");
    return '<a class="bracket-vod" href="' + esc(m.vod_url) + '" target="_blank" rel="noopener"' +
      (who ? ' aria-label="Watch ' + esc(who) + ' on YouTube"' : "") + '>' +
      '<span aria-hidden="true">▶</span> Watch on stream</a>';
  }

  function renderBracket(eventId) {
    var head = document.getElementById("event-bracket-head");
    var chip = document.getElementById("event-bracket-chip");
    var note = document.getElementById("event-bracket-note");
    var el = document.getElementById("event-bracket");
    var rows = (marts.tournament_top_cut_matches || []).filter(function (r) { return r.event_id === eventId; });
    if (bracketState.eventId !== eventId) {
      bracketState = { eventId: eventId, round: null, pathTeam: null };
      renderPath(eventId, null);
    }
    var show = rows.length > 0;
    head.hidden = note.hidden = el.hidden = !show;
    if (!show) return;
    var rounds = bracketRounds(rows);
    if (bracketState.round == null) bracketState.round = rounds[0].round;
    var players = rows[0].top_cut_size || rounds[0].matches.length * 2;
    var byes = rounds[0].matches.filter(function (m) { return m.outcome === "bye"; }).length;
    chip.textContent = players + " players";
    note.textContent = "From RK9 pairings" +
      (byes ? ": a " + (rows[0].bracket_size || rounds[0].matches.length * 2) + "-slot bracket, the top " + byes +
        " seed" + (byes === 1 ? "" : "s") + " on a bye" : "") +
      ". Team vs team: a W means that team won the match; no source names the Pokémon brought to each game. " +
      "Pick a player for their path through the event.";
    var tabs = App.segmentedHtml("Round", "data-bracket-round", rounds.map(function (r) {
      return { id: String(r.round), label: r.label };
    }), String(bracketState.round));
    el.innerHTML = '<div class="bracket-tabs">' + tabs + '</div><div class="bracket-rounds">' +
      rounds.map(function (r) {
        return '<div class="bracket-round' + (r.round === bracketState.round ? " is-active" : "") + '">' +
          '<p class="bracket-round-title">' + esc(r.label) + '</p><div class="bracket-matches">' +
          r.matches.map(function (m) {
            return '<div class="bracket-match' + (m.outcome === "bye" ? " is-bye" : "") + '">' +
              bracketSideHtml(m, 1) +
              (m.outcome === "bye" ? '<div class="bracket-side bracket-bye">Bye</div>' : bracketSideHtml(m, 2)) +
              vodLinkHtml(m) + "</div>";
          }).join("") + "</div></div>";
      }).join("") + "</div>";
  }

  function renderPath(eventId, teamId) {
    var panel = document.getElementById("event-path");
    if (!panel) return;
    var rows = teamId ? (marts.tournament_top_cut_paths || []).filter(function (r) {
      return r.event_id === eventId && r.team_id === teamId;
    }).sort(function (a, b) { return a.round_number - b.round_number; }) : [];
    if (!rows.length) {
      panel.hidden = true;
      panel.innerHTML = "";
      return;
    }
    var match = (marts.tournament_top_cut_matches || []).filter(function (m) {
      return m.event_id === eventId && (m.team_id_1 === teamId || m.team_id_2 === teamId);
    })[0] || {};
    var side = match.team_id_1 === teamId ? 1 : 2;
    var player = {
      player_name: match["player_name_" + side],
      player_country: match["player_country_" + side],
      player_id: match["player_id_" + side],
    };
    var wins = rows.filter(function (r) { return r.result === "W" || r.result === "Bye"; }).length;
    var losses = rows.filter(function (r) { return r.result === "L"; }).length;
    panel.innerHTML =
      '<div class="path-head"><h4>' + esc(player.player_name || "Player") + "'s path · " + App.recordText(wins, losses) + "</h4>" +
      '<button type="button" class="btn btn-sm" data-path-close>Close</button></div>' +
      '<p class="sub">Every round they played. Team vs team: no source names the Pokémon brought to each game.' +
      (player.player_id ? ' <a href="' + App.routeHash("player", [player.player_id]) + '">Player page &rarr;</a>' : "") + "</p>" +
      '<ol class="path-list">' + rows.map(function (r) {
        var result = r.result || "?";
        var opponent = r.opponent_player_name
          ? App.playerLineHtml({ player_name: r.opponent_player_name, player_country: r.opponent_player_country }, { noLink: true }) +
            App.teamCompositionHtml(r.opponent_pokemon_keys, 24)
          : '<span class="sub">' + (result === "Bye" ? "Bye" : "Opponent not on the roster") + "</span>";
        return '<li><span class="path-round">R' + r.round_number + "</span>" +
          '<span class="path-result is-' + result.toLowerCase() + '">' + esc(result) + "</span>" +
          '<span class="path-opponent">' + App.phaseChipHtml(r.phase) + opponent + "</span></li>";
      }).join("") + "</ol>";
    panel.hidden = false;
  }

  document.addEventListener("click", function (e) {
    var tab = e.target.closest && e.target.closest("[data-bracket-round]");
    var player = e.target.closest && e.target.closest("[data-path-team]");
    var close = e.target.closest && e.target.closest("[data-path-close]");
    if (!tab && !player && !close) return;
    var eventId = bracketState.eventId;
    if (tab) bracketState.round = Number(tab.getAttribute("data-bracket-round"));
    if (player) {
      var team = player.getAttribute("data-path-team");
      bracketState.pathTeam = bracketState.pathTeam === team ? null : team;
      renderPath(eventId, bracketState.pathTeam);
    }
    if (close) {
      bracketState.pathTeam = null;
      renderPath(eventId, null);
    }
    renderBracket(eventId);
    if (player && bracketState.pathTeam) {
      var panel = document.getElementById("event-path");
      if (panel && panel.scrollIntoView && window.innerWidth < 1024) panel.scrollIntoView({ block: "nearest" });
    }
  });

  // ---------- Day 2 conversion (E1) ----------
  var MAX_CONVERSION_ROWS = 20;
  var conversionTable = null;

  function renderConversion(event) {
    var head = document.getElementById("event-conversion-head");
    var note = document.getElementById("event-conversion-note");
    var rows = (marts.pokemon_event_phase_usage || []).filter(function (r) {
      return r.scope_kind === "event" && r.event_id === event.event_id && r.phase === "day2";
    });
    var show = rows.length > 0;
    head.hidden = note.hidden = !show;
    document.getElementById("event-conversion-table").hidden = !show;
    if (!show) {
      conversionTable.setRows([]);
      return;
    }
    var reliable = String(rows[0].is_reliable) === "true";
    note.innerHTML = Number(rows[0].phase_team_count).toLocaleString() + " of " +
      Number(rows[0].field_team_count).toLocaleString() + " teams reached Day 2, read off RK9's rounds. " +
      App.termHtml("conversion", "Conversion") + " is Day 2 share over field share" +
      (reliable ? "." : "; it is held back here because Day 2 had fewer than 100 teams.");
    conversionTable.setRows(rows.slice().sort(function (a, b) {
      return b.team_count - a.team_count || b.field_usage_count - a.field_usage_count;
    }).slice(0, MAX_CONVERSION_ROWS));
  }

  function setupEvent() {
    overTable = performerTable(document.getElementById("event-over-table"), "Over-performers");
    underTable = performerTable(document.getElementById("event-under-table"), "Under-performers");
    conversionTable = App.createDataTable(document.getElementById("event-conversion-table"), {
      caption: "Day 2 conversion",
      sort: null,
      rowHref: App.pokemonRowHref,
      citation: function () {
        return currentEvent ? App.shortEventName(currentEvent.event_name) + ", Day 2" : null;
      },
      columns: [
        { key: "pokemon_name", label: "Pokémon", type: "pokemon", main: true, sortable: true },
        {
          key: "field_team_share",
          label: "Field",
          type: "share",
          title: function (r) { return r.field_usage_count + " of " + r.field_team_count + " teams"; },
        },
        {
          key: "team_share",
          label: "Day 2",
          type: "share",
          main: true,
          title: function (r) { return r.team_count + " of " + r.phase_team_count + " Day 2 teams"; },
        },
        {
          key: "conversion",
          label: "Conversion",
          term: "conversion",
          numeric: true,
          sortable: true,
          main: true,
          render: function (r) {
            if (String(r.is_reliable) !== "true" || r.conversion == null) return "—";
            var cls = r.conversion >= 1.1 ? " is-up" : r.conversion <= 0.9 ? " is-down" : "";
            return '<span class="conversion' + cls + '">×' + Number(r.conversion).toFixed(2) + "</span>";
          },
        },
        { key: "team_count", label: "Day 2 teams", type: "int", hideOnPhone: true },
      ],
    });
  }

  function renderEvent(route) {
    var eventId = route.args[0];
    var event = App.eventsById()[eventId];
    var header = document.getElementById("event-header");
    var top8 = document.getElementById("event-top8");
    var perfNote = document.getElementById("event-performers-note");
    var perfBody = document.getElementById("event-performers");
    if (!event) {
      header.className = "";
      header.innerHTML = '<p class="empty-state">No event with id “' + esc(eventId || "") +
        '” in this dataset. <a href="' + App.routeHash("events", []) + '">See all events</a>.</p>';
      top8.innerHTML = "";
      perfBody.hidden = true;
      perfNote.textContent = "";
      return;
    }
    currentEvent = event;
    document.title = App.shortEventName(event.event_name) + " — Pokémon Champions Data";
    var sources = [];
    if (event.pairings_url) sources.push('<a href="' + esc(event.pairings_url) + '" rel="noopener">RK9 pairings</a>');
    if (event.source_url) sources.push('<a href="' + esc(event.source_url) + '" rel="noopener">' + esc(event.source_name || "Team sheets") + "</a>");
    header.className = "page-band broadcast-band";
    header.innerHTML =
      '<p class="eyebrow"><a href="' + App.routeHash("events", []) + '">Events</a></p>' +
      "<h2 class=\"event-title\">" + esc(event.event_name) + "</h2>" +
      (event.winner_player_name
        ? '<p class="event-winner">' + App.phaseChipHtml("Champion") + " " + App.playerLineHtml({
            player_name: event.winner_player_name,
            player_country: event.winner_player_country,
            record_wins: event.winner_record_wins,
            record_losses: event.winner_record_losses,
          }) + "</p>"
        : "") +
      '<p class="event-meta">' + [
        esc(event.event_date),
        esc(event.event_tier || ""),
        regulationLink(event.regulation_code),
        Number(event.player_count || 0).toLocaleString() + " players",
        Number(event.team_count || 0).toLocaleString() + " teams",
        event.match_count ? Number(event.match_count).toLocaleString() + " matches" : null,
      ].filter(Boolean).join(" · ") + "</p>" +
      (sources.length ? '<p class="sub">Sources: ' + sources.join(" · ") + "</p>" : "") +
      eventCardsHtml(event);

    var teams = (marts.tournament_top_cut_teams || [])
      .filter(function (t) { return t.event_id === eventId && t.placement <= 8; })
      .sort(function (a, b) { return a.placement - b.placement; })
      .map(function (t) {
        var team = {};
        for (var k in t) if (Object.prototype.hasOwnProperty.call(t, k)) team[k] = t[k];
        team.event_name = event.event_name;
        team.event_date = event.event_date;
        return team;
      });
    top8.innerHTML = teams.length
      ? teams.map(function (t) { return App.teamCardHtml(t, { hideEvent: true }); }).join("")
      : '<p class="empty-state">Standings for this event aren\'t published yet.</p>';

    var rows = (marts.pokemon_event_usage_vs_regulation || []).filter(function (r) {
      return r.event_id === eventId &&
        Math.max(r.event_team_share || 0, r.regulation_team_share || 0) >= MIN_PERFORMER_SHARE;
    });
    var thin = (event.team_count || 0) < MIN_EVENT_DELTA_TEAMS;
    perfBody.hidden = thin || !rows.length;
    perfNote.textContent = thin
      ? "Only " + (event.team_count || 0) + " teams: too few to compare this event's usage with the regulation's."
      : "Share of teams at this event against the whole of " + App.shortRegulation(event.regulation_code) +
        ", across " + Number(event.team_count).toLocaleString() + " teams.";
    renderBracket(eventId);
    renderConversion(event);
    App.renderMegaPanel(
      {
        note: document.getElementById("event-mega-note"),
        count: document.getElementById("event-mega-count"),
        table: document.getElementById("event-mega-table"),
      },
      { scope_kind: "event", event_id: eventId },
      "at this event"
    );
    if (!thin) {
      overTable.setRows(rows.filter(function (r) { return r.team_share_delta > 0; })
        .sort(function (a, b) { return b.team_share_delta - a.team_share_delta; })
        .slice(0, MAX_PERFORMERS));
      underTable.setRows(rows.filter(function (r) { return r.team_share_delta < 0; })
        .sort(function (a, b) { return a.team_share_delta - b.team_share_delta; })
        .slice(0, MAX_PERFORMERS));
    }
  }

  renderOverviewCards();
  App.registerTab("events", setupEvents, { extraMarts: ["online_event_summary", "online_upcoming_events"] });
  App.registerTab("event", setupEvent, {
    extraMarts: [
      "tournament_team_sheets",
      "pokemon_event_usage_vs_regulation",
      "mega_stone_usage",
      "team_mega_count",
      "pokemon_event_phase_usage",
      "tournament_top_cut_matches",
      "tournament_top_cut_paths",
    ],
    onRoute: renderEvent,
  });
})();
