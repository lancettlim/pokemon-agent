/* The Showdown ladder lens (docs/upgrade-plan-2027q2.md, S2): Smogon's
 * monthly statistics for Pokémon Showdown's Champions ladder, a population
 * of its own (decision D2). Three views, each labelled as ladder data and
 * never added to a tournament figure:
 *   #/usage/ladder              ladder usage against official tournament
 *                               team share: a scatter on tablets and
 *                               desktops, two ranked lists everywhere
 *   #/pokemon/<key>/counters    checks and counters, from battle logs
 *   #/pokemon/<key>/spreads     the Stat Point spreads ladder players ran
 *                               (decision D3: ladder only)
 * Hooked into app.js's Usage tab and profile through App.extendTab. */
(function () {
  "use strict";
  var App = window.DashboardApp;
  if (!App) return;

  var esc = App.escapeHtml;
  var pct = App.formatPercent;

  // ---------- shared ----------

  // The regulation a ladder view shows: the page's own, or under "All
  // regulations" the newest one with ladder rows (the statistics are per
  // regulation).
  function ladderRegulation(rows) {
    var codes = {};
    rows.forEach(function (r) {
      codes[r.regulation_code] = true;
    });
    if (App.regulationCode !== App.ALL_SCOPE) {
      return { code: App.regulationCode, fallback: false, has: !!codes[App.regulationCode] };
    }
    var newest = (App.DATA.regulations || [])
      .filter(function (r) { return codes[r.regulation_code]; })
      .sort(function (a, b) { return String(a.start_date).localeCompare(String(b.start_date)); })
      .pop();
    return { code: newest ? newest.regulation_code : null, fallback: true, has: !!newest };
  }

  function regName(code) {
    return "Reg " + String(code).toUpperCase();
  }

  // "2026-09" -> "September 2026".
  function monthName(month) {
    var parts = String(month || "").split("-");
    var date = new Date(Date.UTC(Number(parts[0]), Number(parts[1]) - 1, 1));
    if (isNaN(date.getTime())) return String(month || "");
    return date.toLocaleDateString("en-GB", { month: "long", year: "numeric", timeZone: "UTC" });
  }

  function statsLink(month) {
    return '<a href="https://www.smogon.com/stats/' + esc(month) + '/" rel="noopener">Smogon, ' +
      esc(monthName(month)) + "</a>";
  }

  function fallbackText(reg) {
    return reg.fallback ? "Ladder statistics are per regulation, so this shows " + regName(reg.code) + ". " : "";
  }

  function nameOf(key) {
    return (App.pokemonNames || {})[key] || key;
  }

  function pts(gap) {
    var value = (gap * 100).toFixed(1);
    return (gap > 0 ? "+" : gap < 0 ? "−" : "±") + value.replace("-", "") + " pts";
  }

  // ---------- Usage tab: ladder vs tournament ----------

  var VARIANTS = [
    { id: "bo1", label: "Bo1" },
    { id: "bo3", label: "Bo3" },
  ];
  var CUTOFFS = [
    { id: "1760", label: "1760+" },
    { id: "0", label: "All ratings" },
  ];
  // Within EVEN_GAP of each other, a Pokémon reads as played the same.
  var EVEN_GAP = 0.02;
  // The scatter plots Pokémon on at least PLOT_FLOOR of teams on one side,
  // the lists those on LIST_FLOOR, LIST_LENGTH each.
  var PLOT_FLOOR = 0.005;
  var LIST_FLOOR = 0.02;
  var LIST_LENGTH = 10;
  // Named on the scatter: the LABELLED widest gaps each way.
  var LABELLED = 3;
  var view = { variant: "bo1", cutoff: "1760" };

  function gapClass(gap) {
    return gap >= EVEN_GAP ? "is-ladder" : gap <= -EVEN_GAP ? "is-tournament" : "is-even";
  }

  function pointTip(r) {
    return nameOf(r.pokemon_key) + ": ladder " + pct(r.ladder_usage) + " of teams, official tournaments " +
      pct(r.tournament_team_share) + " (" + pts(r.ladder_gap) + ")";
  }

  // Both axes share one square-root scale, so the many Pokémon under 5%
  // stay apart and the same share on both still falls on the diagonal.
  function scatterHtml(rows, reg) {
    var W = 640;
    var H = 420;
    var left = 54;
    var right = 18;
    var top = 14;
    var bottom = 46;
    var max = rows.reduce(function (m, r) {
      return Math.max(m, r.ladder_usage || 0, r.tournament_team_share || 0);
    }, 0);
    var domain = Math.min(1, Math.ceil(max * 10) / 10) || 0.1;
    function sx(v) { return left + Math.sqrt(Math.max(v, 0) / domain) * (W - left - right); }
    function sy(v) { return H - bottom - Math.sqrt(Math.max(v, 0) / domain) * (H - top - bottom); }
    var ticks = [0, 0.01, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1].filter(function (t) {
      return t <= domain + 1e-9;
    });
    var grid = ticks.map(function (t) {
      var x = sx(t).toFixed(1);
      var y = sy(t).toFixed(1);
      var label = Math.round(t * 100) + "%";
      return '<line x1="' + x + '" y1="' + top + '" x2="' + x + '" y2="' + (H - bottom) + '"/>' +
        '<line x1="' + left + '" y1="' + y + '" x2="' + (W - right) + '" y2="' + y + '"/>' +
        '<text x="' + x + '" y="' + (H - bottom + 16) + '" text-anchor="middle">' + label + "</text>" +
        '<text x="' + (left - 8) + '" y="' + (Number(y) + 4) + '" text-anchor="end">' + label + "</text>";
    }).join("");
    var plotted = rows.filter(function (r) {
      return Math.max(r.ladder_usage || 0, r.tournament_team_share || 0) >= PLOT_FLOOR;
    });
    // Even Pokémon first, so a coloured dot is never under a grey one.
    plotted.sort(function (a, b) { return Math.abs(a.ladder_gap) - Math.abs(b.ladder_gap); });
    var named = {};
    var listed = plotted.filter(function (r) {
      return Math.max(r.ladder_usage, r.tournament_team_share) >= LIST_FLOOR;
    });
    listed.slice().sort(function (a, b) { return b.ladder_gap - a.ladder_gap; }).slice(0, LABELLED)
      .concat(listed.slice().sort(function (a, b) { return a.ladder_gap - b.ladder_gap; }).slice(0, LABELLED))
      .forEach(function (r) { if (Math.abs(r.ladder_gap) >= EVEN_GAP) named[r.pokemon_key] = true; });
    var dots = plotted.map(function (r) {
      var x = sx(r.tournament_team_share);
      var y = sy(r.ladder_usage);
      return '<a href="' + esc(App.pokemonHref(r.pokemon_key)) + '" tabindex="-1" data-tip="' + esc(pointTip(r)) + '">' +
        '<circle class="hit" cx="' + x.toFixed(1) + '" cy="' + y.toFixed(1) + '" r="22"/>' +
        '<circle class="dot ' + gapClass(r.ladder_gap) + '" cx="' + x.toFixed(1) + '" cy="' + y.toFixed(1) + '" r="5"/></a>';
    }).join("");
    // Each name goes right of its dot, else left, else nudged up or down,
    // whichever first clears the names already placed and the plot edge.
    var placed = [];
    var labels = plotted.filter(function (r) { return named[r.pokemon_key]; }).map(function (r) {
      var x = sx(r.tournament_team_share);
      var y = sy(r.ladder_usage);
      var name = nameOf(r.pokemon_key);
      var width = name.length * 6.6 + 4;
      var spot = null;
      [0, -14, 14, -28, 28].some(function (dy) {
        return [1, -1].some(function (side) {
          var x1 = side > 0 ? x + 9 : x - 9 - width;
          var box = { x1: x1, x2: x1 + width, y1: y + dy - 10, y2: y + dy + 4 };
          var clear = box.x1 >= left && box.x2 <= W - right && !placed.some(function (b) {
            return box.x1 < b.x2 && box.x2 > b.x1 && box.y1 < b.y2 && box.y2 > b.y1;
          });
          if (clear) spot = { box: box, side: side, dy: dy };
          return clear;
        });
      });
      if (!spot) return "";
      placed.push(spot.box);
      return '<text class="dot-label" x="' + (spot.side > 0 ? x + 9 : x - 9).toFixed(1) + '" y="' +
        (y + 4 + spot.dy).toFixed(1) + '" text-anchor="' + (spot.side > 0 ? "start" : "end") + '">' + esc(name) + "</text>";
    }).join("");
    var summary = "Ladder usage against official tournament team share in " + regName(reg.code) + " for " +
      plotted.length + " Pokémon. The two lists below give the widest gaps.";
    return '<svg class="ladder-svg" viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="' + esc(summary) + '">' +
      '<g class="grid axis">' + grid + "</g>" +
      '<line class="diagonal" x1="' + sx(0) + '" y1="' + sy(0) + '" x2="' + sx(domain) + '" y2="' + sy(domain) + '"/>' +
      '<text class="region" x="' + (left + 10) + '" y="' + (top + 14) + '">More on the ladder</text>' +
      '<text class="region" x="' + (W - right - 6) + '" y="' + (H - bottom - 10) + '" text-anchor="end">More at tournaments</text>' +
      '<text class="axis-title" x="' + ((left + W - right) / 2) + '" y="' + (H - 8) + '" text-anchor="middle">Share of official tournament teams</text>' +
      '<text class="axis-title" transform="translate(14 ' + ((top + H - bottom) / 2) + ') rotate(-90)" text-anchor="middle">Share of ladder teams</text>' +
      dots + labels + "</svg>" +
      '<ul class="ladder-legend">' +
      '<li><span class="mega-swatch" style="background:var(--series-blue)"></span>Played more on the ladder</li>' +
      '<li><span class="mega-swatch" style="background:var(--muted)"></span>Within 2 pts</li>' +
      '<li><span class="mega-swatch" style="background:var(--series-red)"></span>Played more at tournaments</li>' +
      "<li>Dashed line: the same share on both. Square-root scale.</li></ul>";
  }

  function listHtml(title, rows) {
    return '<section><h3 class="eyebrow">' + esc(title) + '</h3><ol class="ladder-list">' + (rows.length
      ? rows.map(function (r) {
          return "<li>" + App.pokemonCell(r.pokemon_key, nameOf(r.pokemon_key)) +
            '<span class="ladder-gap">' + esc(pts(r.ladder_gap)) + "</span>" +
            '<span class="ladder-sub">Ladder ' + esc(pct(r.ladder_usage)) + " · Tournaments " +
            esc(pct(r.tournament_team_share)) + "</span></li>";
        }).join("")
      : '<li class="empty-state">None by more than 2 pts.</li>') + "</ol></section>";
  }

  function renderLadderView() {
    var noteEl = document.getElementById("ladder-note");
    var scatterEl = document.getElementById("ladder-scatter");
    var listsEl = document.getElementById("ladder-lists");
    if (!noteEl || !scatterEl || !listsEl) return;
    var all = App.marts.ladder_pokemon_usage || [];
    var reg = ladderRegulation(all);
    scatterEl.innerHTML = "";
    listsEl.innerHTML = "";
    if (!reg.has) {
      noteEl.textContent = all.length
        ? "Smogon hasn't published ladder statistics for " + regName(App.regulationCode) + " yet."
        : "No ladder statistics in this build.";
      return;
    }
    var rows = all.filter(function (r) {
      return r.regulation_code === reg.code && r.variant === view.variant && String(r.cutoff) === view.cutoff;
    });
    if (!rows.length) {
      noteEl.textContent = "Smogon published no " + (view.variant === "bo3" ? "Bo3" : "Bo1") + " " +
        (view.cutoff === "0" ? "all-ratings" : "1760+") + " file for " + regName(reg.code) + ".";
      return;
    }
    var compared = rows.filter(function (r) { return r.tournament_team_share != null; });
    var teams = ((App.DATA.kpis_by_scope || {})[reg.code] || {}).team_count;
    noteEl.innerHTML = esc(fallbackText(reg)) + rows[0].battles.toLocaleString() + " " +
      (view.variant === "bo3" ? "Bo3" : "Bo1") + " ladder battles" +
      (view.cutoff === "1760" ? ", weighted toward players rated 1760+," : "") + " in " + statsLink(rows[0].month) +
      ", against " + (teams ? teams.toLocaleString() + " " : "") + "official tournament teams in " +
      esc(regName(reg.code)) + "." + (App.isOfficialScope ? "" : " Tournament figures here are official events only.");
    scatterEl.innerHTML = scatterHtml(compared, reg);
    var eligible = compared.filter(function (r) {
      return Math.max(r.ladder_usage, r.tournament_team_share) >= LIST_FLOOR && Math.abs(r.ladder_gap) >= EVEN_GAP;
    });
    var more = eligible.filter(function (r) { return r.ladder_gap > 0; })
      .sort(function (a, b) { return b.ladder_gap - a.ladder_gap; }).slice(0, LIST_LENGTH);
    var less = eligible.filter(function (r) { return r.ladder_gap < 0; })
      .sort(function (a, b) { return a.ladder_gap - b.ladder_gap; }).slice(0, LIST_LENGTH);
    listsEl.innerHTML = listHtml("Played more on the ladder", more) + listHtml("Played more at tournaments", less);
  }

  function setupLadderView() {
    var controls = document.getElementById("ladder-controls");
    if (!controls) return;
    controls.innerHTML = App.segmentedHtml("Ladder", "data-ladder-variant", VARIANTS, view.variant) +
      App.segmentedHtml("Ratings", "data-ladder-cutoff", CUTOFFS, view.cutoff);
    controls.addEventListener("click", function (e) {
      var button = e.target.closest && e.target.closest("button");
      if (!button) return;
      if (button.hasAttribute("data-ladder-variant")) view.variant = button.getAttribute("data-ladder-variant");
      else if (button.hasAttribute("data-ladder-cutoff")) view.cutoff = button.getAttribute("data-ladder-cutoff");
      else return;
      Array.prototype.forEach.call(controls.querySelectorAll("button"), function (b) {
        var value = b.getAttribute("data-ladder-variant") || b.getAttribute("data-ladder-cutoff");
        b.setAttribute("aria-pressed", String(value === view.variant || value === view.cutoff));
      });
      renderLadderView();
    });
    renderLadderView();
  }

  App.extendTab("usage", setupLadderView);
  // The Builder's threat screen reads the same regulation choice (#23).
  App.ladderRegulation = ladderRegulation;

  // ---------- profile: checks and counters, Stat Point spreads ----------

  var COUNTERS_SHOWN = 6;
  var counterState = { key: null, expanded: false };

  function counterTip(r, pokemonName) {
    return "In " + r.encounters.toLocaleString() + " encounters with " + nameOf(r.counter_pokemon_key) + ", " +
      pokemonName + " was KO'd or switched out " + pct(r.ko_or_switch_rate) + " of the time.";
  }

  function drawCounters(profile) {
    var listEl = document.getElementById("profile-counters");
    var noteEl = document.getElementById("profile-counters-note");
    var moreEl = document.getElementById("profile-counters-more");
    if (!listEl || !noteEl) return;
    if (counterState.key !== profile.pokemon_key) counterState = { key: profile.pokemon_key, expanded: false };
    var all = App.marts.ladder_checks_counters || [];
    var reg = ladderRegulation(all);
    var inRegulation = all.filter(function (r) { return r.regulation_code === reg.code; });
    var rows = inRegulation.filter(function (r) { return r.pokemon_key === profile.pokemon_key; })
      .sort(function (a, b) { return a.counter_rank - b.counter_rank; });
    if (moreEl) moreEl.hidden = true;
    if (!reg.has) {
      listEl.innerHTML = "";
      noteEl.textContent = reg.code
        ? "Smogon published no checks and counters for " + regName(reg.code) + "'s ladder."
        : "No checks and counters in this build.";
      return;
    }
    var month = inRegulation[0].month;
    if (!rows.length) {
      listEl.innerHTML = "";
      noteEl.innerHTML = esc(fallbackText(reg) + profile.pokemon_name + " met no opponent 100 times on the Bo1 ladder in ") +
        statsLink(month) + ".";
      return;
    }
    noteEl.innerHTML = esc(fallbackText(reg)) + "Bo1 ladder, all ratings, " + esc(regName(reg.code)) + ": " +
      statsLink(month) + ". The rate is how often " + esc(profile.pokemon_name) + " was the one KO'd or switched out.";
    var shown = counterState.expanded ? rows : rows.slice(0, COUNTERS_SHOWN);
    listEl.innerHTML = shown.map(function (r) {
      return "<li>" + App.pokemonCell(r.counter_pokemon_key, nameOf(r.counter_pokemon_key)) +
        '<span class="counter-rate" data-tip="' + esc(counterTip(r, profile.pokemon_name)) + '" tabindex="0">' +
        esc(pct(r.ko_or_switch_rate)) + "</span>" +
        '<span class="counter-n">n=' + r.encounters.toLocaleString() + "</span></li>";
    }).join("");
    if (moreEl && rows.length > COUNTERS_SHOWN) {
      moreEl.hidden = false;
      moreEl.textContent = counterState.expanded ? "Show fewer" : "Show all " + rows.length;
      moreEl.onclick = function () {
        counterState.expanded = !counterState.expanded;
        drawCounters(profile);
      };
    }
  }

  var STATS = [
    ["sp_hp", "HP"], ["sp_atk", "Atk"], ["sp_def", "Def"],
    ["sp_spa", "SpA"], ["sp_spd", "SpD"], ["sp_spe", "Spe"],
  ];

  function spreadText(r) {
    return STATS.filter(function (s) { return r[s[0]] > 0; }).map(function (s) {
      return r[s[0]] + " " + s[1];
    }).join(" / ");
  }

  function drawSpreads(profile) {
    var listEl = document.getElementById("profile-spreads");
    var noteEl = document.getElementById("profile-spreads-note");
    if (!listEl || !noteEl) return;
    var all = App.marts.ladder_stat_point_spreads || [];
    var reg = ladderRegulation(all);
    var rows = all.filter(function (r) {
      return r.regulation_code === reg.code && r.pokemon_key === profile.pokemon_key;
    }).sort(function (a, b) { return a.spread_rank - b.spread_rank; });
    if (!rows.length) {
      listEl.innerHTML = "";
      noteEl.textContent = reg.has
        ? profile.pokemon_name + " doesn't appear in " + regName(reg.code) + "'s 1760+ Bo1 ladder statistics."
        : "No ladder statistics for " + regName(reg.code || App.regulationCode) + ".";
      return;
    }
    noteEl.innerHTML = esc(fallbackText(reg)) + "Share of the spreads 1760+ Bo1 ladder players ran on " +
      esc(profile.pokemon_name) + " in " + esc(regName(reg.code)) + ": " + statsLink(rows[0].month) +
      ". Smogon lists each with its nature, which Champions calls " + App.termHtml("alignment", "Stat Alignment") + ".";
    listEl.innerHTML = '<ol class="spread-list">' + rows.map(function (r) {
      return '<li><span class="spread-points"><span class="nature">' + esc(r.nature) + "</span>" +
        esc(spreadText(r)) + '</span><span class="spread-share">' + esc(pct(r.share)) + "</span>" +
        '<span class="spread-bar" aria-hidden="true"><span style="width:' + (r.share * 100).toFixed(1) + '%"></span></span></li>';
    }).join("") + "</ol>";
  }

  App.extendTab("profile", function (profile) {
    drawCounters(profile);
    drawSpreads(profile);
  });
})();
