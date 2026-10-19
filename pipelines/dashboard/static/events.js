/* Events (docs/upgrade-plan-2027q1.md, C1) and the Overview's "Latest
 * event" card and "Copy and play" starter teams (C1, P5). Loaded after
 * app.js/teams.js and reuses window.DashboardApp.
 *
 *   #/events            every event in the selected regulation
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
  // A Pokémon this rare in both the event and the regulation isn't an
  // over- or under-performer worth listing, whatever its delta.
  var MIN_PERFORMER_SHARE = 0.005;

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
    var starters = kpis.starter_teams || [];
    if (latestEl && latest) {
      latestEl.innerHTML =
        '<div class="latest-event">' +
        '<p class="eyebrow">Latest event</p>' +
        '<h3><a href="' + App.routeHash("event", [latest.event_id]) + '">' + esc(latest.event_name) + "</a></h3>" +
        '<p class="sub">' + esc(latest.event_date) + " · " + esc(latest.event_tier || "") + " · " +
        Number(latest.team_count || 0).toLocaleString() + " teams</p>" +
        (latest.winner_player_name
          ? '<p class="latest-event-winner">Won by <strong>' + esc(latest.winner_player_name) + "</strong> " +
            App.countryCell(latest.winner_player_country) +
            (latest.winner_record_wins != null
              ? " · " + App.recordText(latest.winner_record_wins, latest.winner_record_losses)
              : "") + "</p>" +
            App.teamCompositionHtml(latest.winner_pokemon_keys, 40)
          : "") +
        '<p><a class="btn btn-sm" href="' + App.routeHash("event", [latest.event_id]) + '">Top 8 and sets</a> ' +
        '<a class="btn btn-sm" href="' + App.routeHash("events", []) + '">All events</a></p>' +
        "</div>";
    }
    if (startersEl && starters.length) {
      startersEl.innerHTML =
        '<p class="eyebrow">Copy and play</p>' +
        '<p class="sub">The top-placing fully reported teams in ' + esc(App.scopeLabel(App.regulationScope)) +
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
      note.textContent = events.length + " event" + (events.length === 1 ? "" : "s") + " · " +
        teams.toLocaleString() + " teams in " + App.scopeLabel(App.regulationScope) + ".";
    }
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
          key: "event_usage_share",
          label: "At this event",
          type: "share",
          main: true,
          title: function (r) {
            return r.usage_count.toLocaleString() + " of " + r.event_slot_count.toLocaleString() + " roster slots";
          },
        },
        { key: "regulation_usage_share", label: "Regulation", type: "percent" },
        {
          key: "usage_share_delta",
          label: "Difference",
          numeric: true,
          sortable: true,
          render: function (r) {
            var pts = (r.usage_share_delta || 0) * 100;
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
    header.innerHTML =
      '<p class="eyebrow"><a href="' + App.routeHash("events", []) + '">Events</a></p>' +
      "<h2 class=\"event-title\">" + esc(event.event_name) + "</h2>" +
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
        Math.max(r.event_usage_share || 0, r.regulation_usage_share || 0) >= MIN_PERFORMER_SHARE;
    });
    var thin = (event.team_count || 0) < MIN_EVENT_DELTA_TEAMS;
    perfBody.hidden = thin || !rows.length;
    perfNote.textContent = thin
      ? "Only " + (event.team_count || 0) + " teams: too few to compare this event's usage with the regulation's."
      : "Share of roster slots at this event against the whole of " + App.shortRegulation(event.regulation_code) +
        ", across " + Number(event.team_count).toLocaleString() + " teams.";
    if (!thin) {
      overTable.setRows(rows.filter(function (r) { return r.usage_share_delta > 0; })
        .sort(function (a, b) { return b.usage_share_delta - a.usage_share_delta; })
        .slice(0, MAX_PERFORMERS));
      underTable.setRows(rows.filter(function (r) { return r.usage_share_delta < 0; })
        .sort(function (a, b) { return a.usage_share_delta - b.usage_share_delta; })
        .slice(0, MAX_PERFORMERS));
    }
  }

  renderOverviewCards();
  App.registerTab("events", setupEvents);
  App.registerTab("event", setupEvent, {
    extraMarts: ["tournament_team_sheets", "pokemon_event_usage_vs_regulation"],
    onRoute: renderEvent,
  });
})();
