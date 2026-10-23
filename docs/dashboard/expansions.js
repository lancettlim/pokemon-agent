/* Dashboard feature expansions: comparison mode and a searchable
 * pair/triple core explorer. Kept dependency-free and source-backed by the
 * existing profile/core marts. Both views keep their state in the route
 * (docs/upgrade-plan-2027q1.md, U1):
 *   #/compare/<a>,<b>          #/cores/<anchor>[/triple]
 * Links from before routing (?tab=compare&a=..&b=..) are rewritten to these
 * by app.js's legacyQueryRoute. Compare takes two to four Pokémon
 * (#/compare/<a>,<b>,<c>,<d>), and the compare tray (docs/upgrade-plan-
 * 2027q2.md, list #34) collects them from any profile. */
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
  var MAX_COMPARE = 4;
  function compareSelects() {
    return Array.prototype.slice.call(document.querySelectorAll("[data-compare-select]"));
  }
  function compareKeys() {
    return compareSelects().map(function (select) { return select.value; }).filter(Boolean);
  }
  function renderComparison() {
    var out = document.getElementById("compare-results");
    if (!out) return;
    var rows = profileRows();
    var picked = compareKeys().map(function (key) {
      return rows.find(function (r) { return r.pokemon_key === key; }) || { pokemon_key: key };
    });
    var metrics = [
      ["Team share", function (r) { return percent(r.team_share); }],
      ["Win rate", function (r) { return percent(r.win_rate); }],
      ["Teams with a record", function (r) { return metric(r.record_count); }],
      ["Base speed", function (r) { return metric(r.speed); }],
      ["Attack", function (r) { return metric(r.attack); }],
      ["Special attack", function (r) { return metric(r.sp_attack); }],
      ["Defense", function (r) { return metric(r.defense); }],
      ["Special defense", function (r) { return metric(r.sp_defense); }],
      ["HP", function (r) { return metric(r.hp); }],
    ];
    function name(r) { return r.pokemon_name || displayName(r.pokemon_key); }
    out.innerHTML = '<div class="compare-columns compare-columns-' + picked.length + '">' + picked.map(function (r) {
      return '<article class="compare-card"><h3>' + esc(name(r)) + "</h3>" +
        (r.pokemon_key ? App.pokemonCell(r.pokemon_key, r.pokemon_name) : "") + "</article>";
    }).join("") + "</div>" +
      '<div class="table-scroll"><table><thead><tr><th>Metric</th>' + picked.map(function (r) {
        return "<th>" + esc(name(r)) + "</th>";
      }).join("") + "</tr></thead><tbody>" + metrics.map(function (m) {
        return "<tr><th>" + esc(m[0]) + "</th>" + picked.map(function (r) {
          return "<td>" + esc(m[1](r)) + "</td>";
        }).join("") + "</tr>";
      }).join("") + "</tbody></table></div>" +
      '<p class="source-note">Usage and win rate are for ' + esc(App.scopeLabel(App.regulationScope)) +
      ". Win rate is the combined W-L record of the teams that brought each Pokémon, with its sample size beside it.</p>";
  }
  // Pairs and triples on the shared table (docs/upgrade-plan-2027q1.md,
  // U5), one table per core size.
  var pairTable = null;
  var tripleTable = null;
  function setupCoreTables() {
    pairTable = App.createDataTable(document.getElementById("core-pair-table"), {
      caption: "Most common partners",
      sort: { key: "co_occurrence_count", dir: "desc" },
      limit: 24,
      rowHref: function (r) { return App.pokemonHref(r.partner_pokemon_key); },
      empty: "No qualifying pair data for this Pokémon.",
      columns: [
        { key: "pokemon_name", label: "Partner", type: "pokemon", keyField: "partner_pokemon_key", main: true, sortable: true },
        { key: "co_occurrence_count", label: "Shared teams", type: "int", main: true },
        { key: "partner_share", label: "Partner share", type: "share",
          title: function (r) { return "On " + percent(r.partner_share) + " of this Pokémon's teams"; } },
        {
          key: "compare",
          label: "",
          sortable: false,
          hideOnPhone: true,
          render: function (r) {
            return '<a href="' + App.routeHash("compare", [r.anchor + "," + r.partner_pokemon_key]) + '">Compare</a>';
          },
        },
      ],
    });
    tripleTable = App.createDataTable(document.getElementById("core-triple-table"), {
      officialOnly: true,
      caption: "Three-Pokémon cores",
      sort: { key: "triple_team_count", dir: "desc" },
      limit: 24,
      empty: "No qualifying three-Pokémon cores for this Pokémon.",
      columns: [
        {
          key: "core",
          label: "Core",
          main: true,
          sortable: false,
          render: function (r) {
            return App.teamCompositionHtml([r.pokemon_key_a, r.pokemon_key_b, r.pokemon_key_c].join("|"), 32) +
              '<span class="core-names">' + [r.pokemon_key_a, r.pokemon_key_b, r.pokemon_key_c].map(function (k) {
                return '<a href="' + App.pokemonHref(k) + '">' + esc(displayName(k)) + "</a>";
              }).join(" · ") + "</span>";
          },
        },
        { key: "triple_team_count", label: "Teams", type: "int", main: true },
        { key: "triple_team_share", label: "Share", type: "share" },
        {
          key: "triple_lift",
          label: "Lift",
          numeric: true,
          sortable: true,
          render: function (r) { return "×" + Number(r.triple_lift || 0).toFixed(2); },
          title: function () { return "How much more often the three appear together than chance predicts"; },
        },
        { key: "event_count", label: "Events", type: "int", hideOnPhone: true },
        { key: "player_count", label: "Players", type: "int", hideOnPhone: true },
      ],
    });
  }
  function renderCore() {
    var anchor = document.getElementById("core-anchor");
    var size = document.getElementById("core-size");
    var title = document.getElementById("core-title");
    if (!anchor || !size || !pairTable) return;
    var key = anchor.value;
    var triple = size.value === "triple";
    document.getElementById("core-pair-table").hidden = triple;
    document.getElementById("core-triple-table").hidden = !triple;
    if (title) {
      title.textContent = triple
        ? "Three-Pokémon cores containing " + displayName(key)
        : "Most common partners for " + displayName(key);
    }
    if (triple) {
      tripleTable.setRows((App.marts.pokemon_team_core_triple_usage || []).filter(function (r) {
        return [r.pokemon_key_a, r.pokemon_key_b, r.pokemon_key_c].indexOf(key) >= 0;
      }));
    } else {
      pairTable.setRows((App.marts.pokemon_team_core_usage || []).filter(function (r) {
        return r.pokemon_key === key;
      }).map(function (r) {
        return {
          anchor: key,
          partner_pokemon_key: r.partner_pokemon_key,
          pokemon_name: r.partner_pokemon_name,
          co_occurrence_count: r.co_occurrence_count,
          partner_share: r.partner_share,
        };
      }));
    }
  }

  var compareRoute = function () {};
  function setupCompare() {
    var rows = profileRows();
    if (!rows.length) return;
    var a = document.getElementById("compare-a");
    var b = document.getElementById("compare-b");
    var extra = document.getElementById("compare-extra");
    var addButton = document.getElementById("compare-add");
    fillPokemonSelect(a, rows[0].pokemon_key);
    fillPokemonSelect(b, rows[1] ? rows[1].pokemon_key : rows[0].pokemon_key);
    function record() {
      renderComparison();
      syncAdd();
      App.setRoute("compare", [compareKeys().join(",")], {}, { push: true });
    }
    // A third or fourth column: its own picker and a remove button.
    function addColumn(key) {
      if (!extra || compareSelects().length >= MAX_COMPARE) return null;
      var label = document.createElement("label");
      label.className = "compare-extra-field";
      label.textContent = "Pokémon " + "ABCD".charAt(compareSelects().length) + " ";
      var select = document.createElement("select");
      select.setAttribute("data-compare-select", "");
      label.appendChild(select);
      var remove = document.createElement("button");
      remove.type = "button";
      remove.className = "btn btn-sm compare-remove";
      remove.textContent = "Remove";
      remove.addEventListener("click", function (e) {
        e.preventDefault();
        label.remove();
        relabel();
        record();
      });
      label.appendChild(remove);
      extra.appendChild(label);
      fillPokemonSelect(select, key || rows[compareSelects().length - 1] && rows[compareSelects().length - 1].pokemon_key);
      App.attachPokemonCombobox(select);
      select.addEventListener("change", record);
      return select;
    }
    function relabel() {
      Array.prototype.forEach.call(extra.querySelectorAll(".compare-extra-field"), function (label, i) {
        label.firstChild.textContent = "Pokémon " + "CD".charAt(i) + " ";
      });
    }
    function syncAdd() {
      if (addButton) addButton.hidden = compareSelects().length >= MAX_COMPARE;
    }
    a.addEventListener("change", record);
    b.addEventListener("change", record);
    if (addButton) {
      addButton.addEventListener("click", function () {
        var used = compareKeys();
        var next = rows.find(function (r) { return used.indexOf(r.pokemon_key) === -1; });
        if (addColumn(next && next.pokemon_key)) record();
      });
    }
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
      var keys = String(route.args[0] || "").split(",").filter(knownKey).slice(0, MAX_COMPARE);
      if (keys[0]) { a.value = keys[0]; a.dispatchEvent(new Event("pokemon-sync")); }
      if (keys[1]) { b.value = keys[1]; b.dispatchEvent(new Event("pokemon-sync")); }
      if (extra) extra.innerHTML = "";
      keys.slice(2).forEach(function (key) {
        var select = addColumn(key);
        if (select) { select.value = key; select.dispatchEvent(new Event("pokemon-sync")); }
      });
      syncAdd();
      renderComparison();
    };
    syncAdd();
    renderComparison();
  }

  // ---------- compare tray (docs/upgrade-plan-2027q2.md, list #34) ----------
  // Pin up to four Pokémon from their profiles; the tray follows the
  // visitor across pages (a bottom sheet over the phone's bottom bar, a
  // side card from 721px) and opens Compare on them. Kept per browser.
  var TRAY_KEY = "dashboard-compare-tray";
  var tray = document.getElementById("compare-tray");
  function readTray() {
    try {
      var saved = JSON.parse(localStorage.getItem(TRAY_KEY) || "[]");
      return Array.isArray(saved) ? saved.filter(function (k) { return typeof k === "string"; }).slice(0, MAX_COMPARE) : [];
    } catch (e) {
      return [];
    }
  }
  function writeTray(keys) {
    try {
      localStorage.setItem(TRAY_KEY, JSON.stringify(keys.slice(0, MAX_COMPARE)));
    } catch (e) {
      // Storage blocked: the tray lasts this page only.
    }
    trayKeys = keys.slice(0, MAX_COMPARE);
    renderTray();
    syncPin();
  }
  var trayKeys = readTray();
  function renderTray() {
    if (!tray) return;
    tray.hidden = !trayKeys.length;
    // The page keeps room for the tray so it never covers the last row.
    document.documentElement.classList.toggle("has-compare-tray", trayKeys.length > 0);
    if (!trayKeys.length) return;
    tray.innerHTML = '<p class="compare-tray-title">Compare <span>' + trayKeys.length + "/" + MAX_COMPARE + "</span></p>" +
      '<ul class="compare-tray-list">' + trayKeys.map(function (key) {
        return '<li><a href="' + App.pokemonHref(key) + '" title="' + esc(displayName(key)) + '">' +
          App.spriteImg(key, App.ICON_SIZES.sm) + '<span class="visually-hidden">' + esc(displayName(key)) + "</span></a>" +
          '<button type="button" class="compare-tray-remove" data-tray-remove="' + esc(key) + '" aria-label="Unpin ' +
          esc(displayName(key)) + '">×</button></li>';
      }).join("") + "</ul>" +
      '<div class="compare-tray-actions">' +
      (trayKeys.length >= 2
        ? '<a class="btn btn-sm btn-primary" href="' + App.routeHash("compare", [trayKeys.join(",")]) + '">Compare</a>'
        : '<span class="compare-tray-hint">Pin one more</span>') +
      '<button type="button" class="btn btn-sm" data-tray-clear>Clear</button></div>';
  }
  if (tray) {
    tray.addEventListener("click", function (e) {
      var remove = e.target.closest && e.target.closest("[data-tray-remove]");
      if (remove) {
        writeTray(trayKeys.filter(function (k) { return k !== remove.getAttribute("data-tray-remove"); }));
      } else if (e.target.closest && e.target.closest("[data-tray-clear]")) {
        writeTray([]);
      }
    });
  }
  // The profile's pin button, refreshed on every profile render.
  var pinnedProfile = null;
  function syncPin() {
    var button = document.getElementById("profile-pin");
    if (!button || !pinnedProfile) return;
    var pinned = trayKeys.indexOf(pinnedProfile) !== -1;
    button.setAttribute("aria-pressed", String(pinned));
    button.textContent = pinned ? "Pinned to compare" : "Pin to compare";
    button.disabled = !pinned && trayKeys.length >= MAX_COMPARE;
    button.title = button.disabled ? "The tray holds " + MAX_COMPARE + " Pokémon" : "";
  }
  if (App.extendTab) {
    App.extendTab("profile", function (profile) {
      pinnedProfile = profile.pokemon_key;
      var host = document.querySelector(".profile-controls");
      var button = document.getElementById("profile-pin");
      if (host && !button) {
        button = document.createElement("button");
        button.type = "button";
        button.id = "profile-pin";
        button.className = "btn btn-sm profile-pin";
        button.addEventListener("click", function () {
          if (!pinnedProfile) return;
          var pinned = trayKeys.indexOf(pinnedProfile) !== -1;
          writeTray(pinned ? trayKeys.filter(function (k) { return k !== pinnedProfile; }) : trayKeys.concat([pinnedProfile]));
        });
        host.appendChild(button);
      }
      syncPin();
    });
  }
  renderTray();

  var coreRoute = function () {};
  function setupCoreExplorer() {
    var rows = profileRows();
    var anchor = document.getElementById("core-anchor");
    var size = document.getElementById("core-size");
    setupCoreTables();
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
