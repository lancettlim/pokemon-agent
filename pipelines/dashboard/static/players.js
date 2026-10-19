/* Players (docs/upgrade-plan-2027q1.md, C3), for opponent prep: a search
 * on the Players tab and a page per player.
 *
 *   #/players            "Find a player" (search by name)
 *   #/player/<player_id> every event of theirs in the selected regulation,
 *                        with placement, record and the team they brought;
 *                        the Pokémon they bring most; and their team-level
 *                        record against detected archetypes
 *
 * Only what the source events published: names as the sources spell them,
 * nothing inferred or joined across sources. Loaded after app.js and
 * reuses window.DashboardApp. */
(function () {
  "use strict";

  var App = window.DashboardApp;
  if (!App) return;

  var marts = App.marts;
  var esc = App.escapeHtml;
  var MAX_RESULTS = 25;

  function normalize(text) {
    return String(text || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "")
      .replace(/[^a-z0-9 ]/g, "").trim();
  }

  function playerHref(id) {
    return App.routeHash("player", [id]);
  }

  function regulationsLabel(codes) {
    return String(codes || "").split("|").filter(Boolean).map(function (code) {
      return App.shortRegulation(code).replace("Reg ", "");
    }).join(", ");
  }

  // ---------- Find a player (the Players tab's first view) ----------
  // Called by app.js's setupPlayers once the player index has loaded.
  App.setupPlayerSearch = function () {
    var input = document.getElementById("player-search");
    var note = document.getElementById("player-search-note");
    var index = marts.player_index || [];
    var table = App.createDataTable(document.getElementById("player-search-table"), {
      caption: "Players",
      sort: null,
      limit: MAX_RESULTS,
      rowHref: function (r) { return playerHref(r.player_id); },
      empty: "No player on record matches that name.",
      columns: [
        {
          key: "player_name",
          label: "Player",
          main: true,
          sortable: true,
          render: function (r) { return '<a href="' + playerHref(r.player_id) + '">' + esc(r.player_name) + "</a>"; },
        },
        { key: "player_country", label: "Country", sortable: true, render: function (r) { return App.countryCell(r.player_country); } },
        { key: "team_count", label: "Teams", type: "int", main: true },
        {
          key: "best_placement",
          label: "Best finish",
          numeric: true,
          sortable: true,
          render: function (r) { return r.best_placement ? App.ordinal(r.best_placement) : "—"; },
        },
        { key: "latest_event_date", label: "Latest event", sortable: true, hideOnPhone: true },
        {
          key: "regulations",
          label: "Regulations",
          sortable: false,
          hideOnPhone: true,
          render: function (r) { return esc(regulationsLabel(r.regulations)); },
        },
      ],
    });

    function draw() {
      var query = normalize(input && input.value);
      var rows;
      if (!query) {
        // No query: the most decorated players in this regulation.
        rows = index.filter(function (r) {
          return App.regulationScope === App.ALL_SCOPE ||
            ("|" + r.regulations + "|").indexOf("|" + App.regulationScope + "|") !== -1;
        }).filter(function (r) { return r.best_placement && r.best_placement <= 8; })
          .sort(function (a, b) { return a.best_placement - b.best_placement || b.team_count - a.team_count; });
        if (note) {
          note.textContent = index.length.toLocaleString() + " players on record. Showing those with a top-8 finish in " +
            App.scopeLabel(App.regulationScope) + "; search to find anyone.";
        }
      } else {
        var starts = [];
        var contains = [];
        index.forEach(function (r) {
          var name = normalize(r.player_name);
          var words = name.split(" ");
          if (name.indexOf(query) === 0 || words.some(function (w) { return w.indexOf(query) === 0; })) starts.push(r);
          else if (name.indexOf(query) !== -1) contains.push(r);
        });
        rows = starts.concat(contains);
        if (note) note.textContent = rows.length.toLocaleString() + " match" + (rows.length === 1 ? "" : "es") + ".";
      }
      table.setRows(rows);
    }
    if (input) input.addEventListener("input", draw);
    draw();
  };

  // ---------- Player page ----------
  var pokemonTable = null;
  var archetypeTable = null;

  function setupPlayer() {
    pokemonTable = App.createDataTable(document.getElementById("player-pokemon-table"), {
      caption: "Most-brought Pokémon",
      sort: { key: "team_count", dir: "desc" },
      limit: 12,
      rowHref: App.pokemonRowHref,
      columns: [
        { key: "pokemon_name", label: "Pokémon", type: "pokemon", main: true, sortable: true },
        {
          key: "share",
          label: "Share of their teams",
          type: "share",
          main: true,
          title: function (r) { return "On " + r.team_count + " of their " + r.of + " teams"; },
        },
        { key: "team_count", label: "Teams", type: "int" },
      ],
    });
    archetypeTable = App.createDataTable(document.getElementById("player-archetype-table"), {
      caption: "Record against archetypes",
      sort: { key: "matches_played", dir: "desc" },
      empty: "No archetype faced at least twice in this regulation.",
      columns: [
        {
          key: "core",
          label: "Opponent archetype",
          main: true,
          sortable: false,
          render: function (r) {
            var keys = String(r.opponent_pokemon_keys || "").split("|").filter(Boolean);
            if (!keys.length) return esc(r.opponent_archetype_key);
            return App.teamCompositionHtml(keys.join("|"), 32) + '<span class="core-names">' +
              keys.map(function (k) {
                return '<a href="' + App.pokemonHref(k) + '">' + esc(App.pokemonNames[k] || k) + "</a>";
              }).join(" / ") + "</span>";
          },
        },
        {
          key: "wins",
          label: "Record",
          numeric: true,
          sortable: true,
          main: true,
          render: function (r) { return App.recordText(r.wins, r.losses); },
        },
        { key: "win_rate", label: "Win rate", type: "percent" },
        { key: "matches_played", label: "Matches", type: "int" },
      ],
    });
  }

  function renderPlayer(route) {
    var playerId = route.args[0];
    var header = document.getElementById("player-header");
    var teamsEl = document.getElementById("player-teams");
    var eventsNote = document.getElementById("player-events-note");
    var entry = (marts.player_index || []).filter(function (r) { return r.player_id === playerId; })[0];
    if (!entry) {
      header.innerHTML = '<p class="empty-state">No player with id “' + esc(playerId || "") + '” in this dataset. ' +
        '<a href="' + App.routeHash("players", []) + '">Search players</a>.</p>';
      teamsEl.innerHTML = "";
      eventsNote.textContent = "";
      pokemonTable.setRows([]);
      archetypeTable.setRows([]);
      return;
    }
    document.title = entry.player_name + " — Pokémon Champions Data";
    var events = App.eventsById();
    var allTeams = (marts.tournament_team_results || []).filter(function (t) {
      return t.player_id === playerId;
    }).map(function (t) {
      var e = events[t.event_id] || {};
      var team = {};
      for (var k in t) if (Object.prototype.hasOwnProperty.call(t, k)) team[k] = t[k];
      team.event_name = e.event_name;
      team.event_date = e.event_date;
      team.regulation_code = t.regulation_code || e.regulation_code;
      return team;
    }).sort(function (a, b) { return String(b.event_date).localeCompare(String(a.event_date)); });
    var inScope = allTeams.filter(function (t) {
      return App.regulationScope === App.ALL_SCOPE || t.regulation_code === App.regulationScope;
    });
    var best = allTeams.filter(function (t) { return t.placement; })
      .sort(function (a, b) { return a.placement - b.placement; })[0];

    header.innerHTML =
      '<p class="eyebrow"><a href="' + App.routeHash("players", []) + '">Players</a></p>' +
      '<h2 class="event-title">' + esc(entry.player_name) + " " + App.countryCell(entry.player_country) + "</h2>" +
      '<p class="event-meta">' + entry.team_count + " team" + (entry.team_count === 1 ? "" : "s") + " on record" +
      (best ? " · best finish " + App.ordinal(best.placement) + " at " + esc(App.shortEventName(best.event_name)) : "") +
      " · " + esc(regulationsLabel(entry.regulations)) + "</p>";

    var otherRegs = {};
    allTeams.forEach(function (t) {
      if (inScope.indexOf(t) === -1 && t.regulation_code) otherRegs[t.regulation_code] = (otherRegs[t.regulation_code] || 0) + 1;
    });
    var otherLinks = Object.keys(otherRegs).sort().map(function (code) {
      var params = new URLSearchParams(window.location.search);
      params.set("reg", code);
      return '<a href="?' + esc(params.toString()) + esc(playerHref(playerId)) + '">' +
        esc(App.shortRegulation(code)) + " (" + otherRegs[code] + ")</a>";
    });
    var scopeName = esc(App.shortRegulation(App.regulationScope));
    eventsNote.innerHTML = (inScope.length
      ? inScope.length + " event" + (inScope.length === 1 ? "" : "s") + " in " + scopeName + "."
      : "No events in " + scopeName + ".") +
      (otherLinks.length ? " Also on record in " + otherLinks.join(", ") + "." : "");
    teamsEl.innerHTML = inScope.map(function (t) {
      // Sheets exist for top-16 finishes only; otherwise the card shows the
      // six Pokémon without a copy or Builder action.
      return App.teamCardHtml(t, App.teamSheet(t.team_id) ? { hidePlayer: true } : { useHref: null, hidePlayer: true });
    }).join("");

    var source = inScope.length ? inScope : allTeams;
    var counts = {};
    source.forEach(function (t) {
      String(t.pokemon_keys || "").split("|").filter(Boolean).forEach(function (k) {
        counts[k] = (counts[k] || 0) + 1;
      });
    });
    pokemonTable.setRows(Object.keys(counts).map(function (k) {
      return {
        pokemon_key: k,
        pokemon_name: App.pokemonNames[k] || k,
        team_count: counts[k],
        of: source.length,
        share: counts[k] / source.length,
      };
    }));

    archetypeTable.setRows((marts.player_archetype_record || []).filter(function (r) {
      return r.player_id === playerId &&
        (App.regulationScope === App.ALL_SCOPE || r.regulation_code === App.regulationScope);
    }));
  }

  App.registerTab("player", setupPlayer, {
    extraMarts: ["player_index", "tournament_team_results", "tournament_team_sheets", "player_archetype_record"],
    onRoute: renderPlayer,
  });
})();
