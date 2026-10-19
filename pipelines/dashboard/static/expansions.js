/* Dashboard feature expansions: comparison mode, URL-shareable state,
 * and a searchable pair/triple core explorer. Kept dependency-free and
 * source-backed by the existing profile/core marts. */
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
    select.innerHTML = "";
    profileRows().forEach(function (row) {
      var option = document.createElement("option");
      option.value = row.pokemon_key;
      option.textContent = row.pokemon_name || displayName(row.pokemon_key);
      option.selected = row.pokemon_key === selected;
      select.appendChild(option);
    });
  }
  function shareState() {
    var params = new URLSearchParams(window.location.search);
    var tab = params.get("tab") || "overview";
    var a = params.get("a");
    var b = params.get("b");
    var core = params.get("core");
    var size = params.get("size") || "pair";
    return { tab: tab, a: a, b: b, core: core, size: size };
  }
  function writeState(state, replace) {
    var params = new URLSearchParams();
    if (state.tab && state.tab !== "overview") params.set("tab", state.tab);
    if (state.a) params.set("a", state.a);
    if (state.b) params.set("b", state.b);
    if (state.core) params.set("core", state.core);
    if (state.size && state.size !== "pair") params.set("size", state.size);
    var url = window.location.pathname + (params.toString() ? "?" + params.toString() : "") + window.location.hash;
    window.history[replace ? "replaceState" : "pushState"]({}, "", url);
  }
  function activateTab(tab) {
    var button = document.querySelector('.tab-btn[data-tab="' + tab + '"]');
    if (button) button.click();
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
      ["Recorded matches", metric(left.record_count), metric(right.record_count)],
      ["Base speed", metric(left.speed), metric(right.speed)],
      ["Attack", metric(left.attack), metric(right.attack)],
      ["Special attack", metric(left.special_attack), metric(right.special_attack)],
      ["Defense", metric(left.defense), metric(right.defense)],
      ["Special defense", metric(left.special_defense), metric(right.special_defense)]
    ];
    out.innerHTML = '<div class="compare-columns">' +
      '<article class="compare-card"><h3>' + esc(left.pokemon_name || displayName(left.pokemon_key)) +
      '</h3>' + (left.pokemon_key ? App.pokemonCell(left.pokemon_key) : "") + '</article>' +
      '<article class="compare-card"><h3>' + esc(right.pokemon_name || displayName(right.pokemon_key)) +
      '</h3>' + (right.pokemon_key ? App.pokemonCell(right.pokemon_key) : "") + '</article></div>' +
      '<div class="table-scroll"><table><thead><tr><th>Metric</th><th>' +
      esc(left.pokemon_name || displayName(left.pokemon_key)) + '</th><th>' +
      esc(right.pokemon_name || displayName(right.pokemon_key)) +
      '</th></tr></thead><tbody>' + metrics.map(function (m) {
        return '<tr><th>' + esc(m[0]) + '</th><td>' + esc(m[1]) +
          '</td><td>' + esc(m[2]) + '</td></tr>';
      }).join("") + '</tbody></table></div>' +
      '<p class="source-note">Comparison uses the current Champions profile mart. Win rate is the reported tournament win-rate proxy; sample size is shown to keep small samples visible.</p>';
    writeState({ tab: "compare", a: a.value, b: b.value }, true);
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
          return esc(displayName(k));
        }).join(" · ") + '</h3><p><strong>' + metric(r.triple_team_count) +
          '</strong> teams · ' + percent(r.triple_team_share) + ' share · ×' +
          Number(r.triple_lift || 0).toFixed(2) + ' lift</p><p class="source-note">' +
          metric(r.event_count) + ' events · ' + metric(r.player_count) + ' players</p></article>';
      }
      return '<article class="expansion-card"><h3>' + esc(displayName(r.partner_pokemon_key)) +
        '</h3><p><strong>' + metric(r.co_occurrence_count) + '</strong> shared teams · ' +
        percent(r.partner_share) + ' partner share</p><button class="link-button" type="button" data-compare="' +
        esc(r.partner_pokemon_key) + '">Compare with ' + esc(displayName(key)) + '</button></article>';
    }).join("");
    out.innerHTML = '<h3>' + esc(title) + '</h3><div class="expansion-grid">' + body + '</div>' +
      '<p class="source-note">Pair data is co-occurrence on tournament rosters. Triple data is restricted to supported, above-chance Champions cores; association is not proof of a strategic archetype.</p>';
    out.querySelectorAll("[data-compare]").forEach(function (button) {
      button.addEventListener("click", function () {
        var compare = document.querySelector('.tab-btn[data-tab="compare"]');
        if (compare) compare.click();
        var b = document.getElementById("compare-b");
        if (b) { b.value = button.getAttribute("data-compare"); b.dispatchEvent(new Event("change")); }
      });
    });
    writeState({ tab: "core-explorer", core: key, size: size.value }, true);
  }
  function setupCompare() {
    var state = shareState();
    var rows = profileRows();
    if (!rows.length) return;
    var defaultA = state.a || rows[0].pokemon_key;
    var defaultB = state.b || rows[1].pokemon_key;
    fillPokemonSelect(document.getElementById("compare-a"), defaultA);
    fillPokemonSelect(document.getElementById("compare-b"), defaultB);
    document.getElementById("compare-a").addEventListener("change", renderComparison);
    document.getElementById("compare-b").addEventListener("change", renderComparison);
    document.getElementById("compare-copy").addEventListener("click", function () {
      navigator.clipboard.writeText(window.location.href).then(function () {
        this.textContent = "Link copied";
      }.bind(this));
    });
    renderComparison();
  }
  function setupCoreExplorer() {
    var state = shareState();
    var rows = profileRows();
    fillPokemonSelect(document.getElementById("core-anchor"), state.core || (rows[0] && rows[0].pokemon_key));
    var size = document.getElementById("core-size");
    if (size) size.value = state.size || "pair";
    document.getElementById("core-anchor").addEventListener("change", renderCore);
    size.addEventListener("change", renderCore);
    renderCore();
  }
  App.registerTab("compare", setupCompare);
  App.registerTab("core-explorer", setupCoreExplorer, { extraMarts: ["pokemon_team_core_triple_usage"] });

  function initFromUrl() {
    var state = shareState();
    if (state.tab === "compare" || state.tab === "core-explorer") activateTab(state.tab);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initFromUrl);
  else initFromUrl();
})();