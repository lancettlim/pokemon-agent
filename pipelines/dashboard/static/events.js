/* Events (docs/upgrade-plan-2027q1.md, C1) and the Overview's "Latest
 * event" card and "Copy and play" starter teams (C1, P5). Loaded after
 * app.js/teams.js and reuses window.DashboardApp.
 *
 *   #/events            every official event in the selected regulation,
 *                       then its Limitless online tournaments
 *                       (docs/upgrade-plan-2027q2.md, S1), which link out
 *                       to play.limitlesstcg.com rather than to an event
 *                       page of ours
 *   #/event/<event_id>  one event: header, top 8 with full sets, and the
 *                       Pokémon its field over- and under-used against the
 *                       regulation average
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
    setupOnlineEvents();
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

  function setupEvent() {
    overTable = performerTable(document.getElementById("event-over-table"), "Over-performers");
    underTable = performerTable(document.getElementById("event-under-table"), "Under-performers");
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
      (sources.length ? '<p class="sub">Sources: ' + sources.join(" · ") + "</p>" : "");

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
  App.registerTab("events", setupEvents, { extraMarts: ["online_event_summary"] });
  App.registerTab("event", setupEvent, {
    extraMarts: ["tournament_team_sheets", "pokemon_event_usage_vs_regulation", "mega_stone_usage", "team_mega_count"],
    onRoute: renderEvent,
  });
})();
