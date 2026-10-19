/* Dashboard feature expansions: comparison mode and a searchable
 * pair/triple core explorer. Kept dependency-free and source-backed by the
 * existing profile/core marts. Both views keep their state in the route
 * (docs/upgrade-plan-2027q1.md, U1):
 *   #/compare/<a>,<b>          #/cores/<anchor>[/triple]
 * Links from before routing (?tab=compare&a=..&b=..) are rewritten to these
 * by app.js's legacyQueryRoute. */
(function () {
  "use strict";
  var App = window.DashboardApp;
  if (!App) return;

  function esc(value) { return App.escapeHtml(value == null ? "" : value); }
  function displayName(key) {
    var names = App.pokemonNames || {};
    if (names[key]) return names[key];
    return String(key || "").replace(/(^|[-_])([a-z])/g, function (_, p, c) {
      return c.toUpperCase();
    }).replace(/-/g, " ");
  }
  function profileRows() {
    return (App.marts.pokemon_champions_profile || []).slice().sort(function (a, b) {
      return (b.usage_share || 0) - (a.usage_share || 0);
    });
  }
  function fillPokemonSelect(select, selected) {
    if (!select) return;
    App.fillSelectPairs(select, profileRows().map(function (row) {
      return { value: row.pokemon_key, label: row.pokemon_name || displayName(row.pokemon_key) };
    }));
    if (selected) select.value = selected;
  }
  function knownKey(key) {
    return profileRows().some(function (r) { return r.pokemon_key === key; });
  }
  function percent(value) {
    return value == null || isNaN(value) ? "—" : (Number(value) * 100).toFixed(1) + "%";
  }
  function metric(value) {
    return value == null || isNaN(value) ? "—" : Number(value).toLocaleString();
  }
  function renderComparison() {
    var a = document.getElementById("compare-a");
    var b = document.getElementById("compare-b");
    var out = document.getElementById("compare-results");
    if (!a || !b || !out) return;
    var rows = profileRows();
    var left = rows.find(function (r) { return r.pokemon_key === a.value; }) || {};
    var right = rows.find(function (r) { return r.pokemon_key === b.value; }) || {};
    var metrics = [
      ["Usage share", percent(left.usage_share), percent(right.usage_share)],
      ["Win rate", percent(left.win_rate), percent(right.win_rate)],
      ["Teams with a record", metric(left.record_count), metric(right.record_count)],
      ["Base speed", metric(left.speed), metric(right.speed)],
      ["Attack", metric(left.attack), metric(right.attack)],
      ["Special attack", metric(left.sp_attack), metric(right.sp_attack)],
      ["Defense", metric(left.defense), metric(right.defense)],
      ["Special defense", metric(left.sp_defense), metric(right.sp_defense)],
      ["HP", metric(left.hp), metric(right.hp)]
    ];
    out.innerHTML = '<div class="compare-columns">' +
      '<article class="compare-card"><h3>' + esc(left.pokemon_name || displayName(left.pokemon_key)) +
      '</h3>' + (left.pokemon_key ? App.pokemonCell(left.pokemon_key, left.pokemon_name) : "") + '</article>' +
      '<article class="compare-card"><h3>' + esc(right.pokemon_name || displayName(right.pokemon_key)) +
      '</h3>' + (right.pokemon_key ? App.pokemonCell(right.pokemon_key, right.pokemon_name) : "") + '</article></div>' +
      '<div class="table-scroll"><table><thead><tr><th>Metric</th><th>' +
      esc(left.pokemon_name || displayName(left.pokemon_key)) + '</th><th>' +
      esc(right.pokemon_name || displayName(right.pokemon_key)) +
      '</th></tr></thead><tbody>' + metrics.map(function (m) {
        return '<tr><th>' + esc(m[0]) + '</th><td>' + esc(m[1]) +
          '</td><td>' + esc(m[2]) + '</td></tr>';
      }).join("") + '</tbody></table></div>' +
      '<p class="source-note">Usage and win rate are for ' + esc(App.scopeLabel(App.regulationScope)) +
      '. Win rate is the combined W-L record of the teams that brought each Pokémon, with its sample size beside it.</p>';
  }
  function renderCore() {
    var anchor = document.getElementById("core-anchor");
    var size = document.getElementById("core-size");
    var out = document.getElementById("core-results");
    if (!anchor || !size || !out) return;
    var key = anchor.value;
    var pairRows = (App.marts.pokemon_team_core_usage || []).filter(function (r) {
      return r.pokemon_key === key;
    }).sort(function (x, y) { return (y.co_occurrence_count || 0) - (x.co_occurrence_count || 0); });
    var triples = (App.marts.pokemon_team_core_triple_usage || []).filter(function (r) {
      return [r.pokemon_key_a, r.pokemon_key_b, r.pokemon_key_c].indexOf(key) >= 0;
    }).sort(function (x, y) { return (y.triple_team_count || 0) - (x.triple_team_count || 0); });
    var rows = size.value === "triple" ? triples : pairRows;
    if (!rows.length) {
      out.innerHTML = '<p class="empty-state">No qualifying core data is available for this Pokémon.</p>';
      return;
    }
    var title = size.value === "triple" ? "Three-Pokémon cores containing " + displayName(key) :
      "Most common partners for " + displayName(key);
    var body = rows.slice(0, 24).map(function (r) {
      if (size.value === "triple") {
        var members = [r.pokemon_key_a, r.pokemon_key_b, r.pokemon_key_c];
        return '<article class="expansion-card"><h3>' + members.map(function (k) {
          return '<a href="' + App.pokemonHref(k) + '">' + esc(displayName(k)) + "</a>";
        }).join(" · ") + '</h3><p><strong>' + metric(r.triple_team_count) +
          '</strong> teams · ' + percent(r.triple_team_share) + ' share · ×' +
          Number(r.triple_lift || 0).toFixed(2) + ' lift</p><p class="source-note">' +
          metric(r.event_count) + ' events · ' + metric(r.player_count) + ' players</p></article>';
      }
      return '<article class="expansion-card"><h3><a href="' + App.pokemonHref(r.partner_pokemon_key) + '">' +
        esc(displayName(r.partner_pokemon_key)) +
        '</a></h3><p><strong>' + metric(r.co_occurrence_count) + '</strong> shared teams · ' +
        percent(r.partner_share) + ' partner share</p><a class="link-button" href="' +
        App.routeHash("compare", [key + "," + r.partner_pokemon_key]) + '">Compare with ' +
        esc(displayName(key)) + '</a></article>';
    }).join("");
    out.innerHTML = '<h3>' + esc(title) + '</h3><div class="expansion-grid">' + body + '</div>' +
      '<p class="source-note">Pair data is co-occurrence on tournament rosters. Triple data is restricted to supported, above-chance Champions cores; association is not proof of a strategic archetype.</p>';
  }

  var compareRoute = function () {};
  function setupCompare() {
    var rows = profileRows();
    if (!rows.length) return;
    var a = document.getElementById("compare-a");
    var b = document.getElementById("compare-b");
    fillPokemonSelect(a, rows[0].pokemon_key);
    fillPokemonSelect(b, rows[1] ? rows[1].pokemon_key : rows[0].pokemon_key);
    function record() {
      renderComparison();
      App.setRoute("compare", [a.value + "," + b.value], {}, { push: true });
    }
    a.addEventListener("change", record);
    b.addEventListener("change", record);
    var copy = document.getElementById("compare-copy");
    if (copy) {
      copy.addEventListener("click", function () {
        var done = function () { copy.textContent = "Link copied"; };
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(window.location.href).then(done, function () {
            copy.textContent = "Copy the address bar";
          });
        } else {
          copy.textContent = "Copy the address bar";
        }
      });
    }
    compareRoute = function (route) {
      var pair = String(route.args[0] || "").split(",");
      if (knownKey(pair[0])) { a.value = pair[0]; a.dispatchEvent(new Event("pokemon-sync")); }
      if (knownKey(pair[1])) { b.value = pair[1]; b.dispatchEvent(new Event("pokemon-sync")); }
      renderComparison();
    };
    renderComparison();
  }

  var coreRoute = function () {};
  function setupCoreExplorer() {
    var rows = profileRows();
    var anchor = document.getElementById("core-anchor");
    var size = document.getElementById("core-size");
    fillPokemonSelect(anchor, rows[0] && rows[0].pokemon_key);
    function record(push) {
      renderCore();
      App.setRoute(
        "core-explorer",
        [anchor.value, size.value === "triple" ? "triple" : ""],
        {},
        { push: push }
      );
    }
    anchor.addEventListener("change", function () { record(true); });
    size.addEventListener("change", function () { record(false); });
    coreRoute = function (route) {
      if (knownKey(route.args[0])) {
        anchor.value = route.args[0];
        anchor.dispatchEvent(new Event("pokemon-sync"));
      }
      size.value = route.args[1] === "triple" ? "triple" : "pair";
      renderCore();
    };
    renderCore();
  }
  App.registerTab("compare", setupCompare, {
    onRoute: function (route) { compareRoute(route); },
  });
  App.registerTab("core-explorer", setupCoreExplorer, {
    extraMarts: ["pokemon_team_core_triple_usage"],
    onRoute: function (route) { coreRoute(route); },
  });
})();
