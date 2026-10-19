/* Plain vanilla JS — no bundler, no framework, no charting library. Reads
 * window.DASHBOARD_DATA (the critical payload baked into index.html by
 * pipelines/dashboard/build.py) and wires up the tabs/filters/tables/grids
 * declared in index.html.jinja. The marts themselves are not inlined —
 * they are fetched as shard files under data/ on the first activation of a
 * tab that needs them (see ensureData below).
 *
 * This file owns the core framework (tabs, tables, the shared .grid-6xn
 * component) plus the Overview/Usage/Pokémon Profile/Speed Tiers/Players &
 * Regions tabs, and
 * exposes shared state/helpers on window.DashboardApp so matchup.js
 * (Matchup tab) and teams.js (Team Builder + Top Teams tabs) — loaded
 * right after this file — can reuse them instead of duplicating. See
 * docs/design-system.md for the full component/token reference.
 *
 * Ranked/grid visuals (see renderGrid6xn/renderRankedList) are plain
 * DOM/CSS, not canvas charts — this dashboard has no Chart.js/CDN
 * dependency. */
(function () {
  "use strict";

  var DATA = window.DASHBOARD_DATA || {
    marts: {},
    kpis: {},
    sprites: {},
    hero_art: {},
    type_icons: {},
    type_colors: {},
    item_icons: {},
    reference_teams: [],
    pokemon_names: {},
  };
  // ---------- regulation scope ----------
  // Every regulation-sensitive mart carries a regulation_scope column with
  // one partition per regulation plus "all" (docs/upgrade-plan-2026q4.md,
  // A3). The page shows exactly one scope, chosen once at load from ?reg=
  // (so a link can point at "M-B"), else the regulation in force on the
  // viewer's date, else the build's default. Changing it reloads the page
  // (see setupRegulationSelector) rather than re-rendering live tabs.
  var SCOPE_PARAM = "reg";
  var ALL_SCOPE = "all";

  function resolveRegulationScope() {
    var byScope = DATA.kpis_by_scope || {};
    var requested = null;
    try {
      requested = new URLSearchParams(window.location.search).get(SCOPE_PARAM);
    } catch (e) {
      requested = null;
    }
    if (requested && byScope[requested]) return requested;
    var inForce = regulationInForce(DATA.regulations, new Date().toISOString().slice(0, 10));
    if (inForce && byScope[inForce.regulation_code]) return inForce.regulation_code;
    return DATA.default_scope || ALL_SCOPE;
  }

  var regulationScope = resolveRegulationScope();
  if (DATA.kpis_by_scope && DATA.kpis_by_scope[regulationScope]) {
    DATA.kpis = DATA.kpis_by_scope[regulationScope];
  }

  // Rows of a scoped mart narrowed to the page's scope; unscoped marts
  // (no regulation_scope column) pass through untouched.
  function applyRegulationScope(rows) {
    if (!rows || !rows.length || !("regulation_scope" in rows[0])) return rows;
    return rows.filter(function (r) {
      return r.regulation_scope === regulationScope;
    });
  }

  function scopeLabel(scope) {
    if (scope === ALL_SCOPE) return "All Champions regulations";
    var match = (DATA.regulations || []).filter(function (r) {
      return r.regulation_code === scope;
    })[0];
    return match ? match.regulation_name : scope;
  }

  var marts = DATA.marts || {};
  var sprites = DATA.sprites || {};
  var heroArt = DATA.hero_art || {};
  var typeIcons = DATA.type_icons || {};
  var typeColors = DATA.type_colors || {};
  var itemIcons = DATA.item_icons || {};
  var pokemonNames = DATA.pokemon_names || {};

  // Icon-size tokens (docs/design-system.md's "Icon size scale") — mirrors
  // the --icon-sm/md/lg/xl CSS custom properties in index.html.jinja.
  var ICON_SIZES = { sm: 40, md: 64, lg: 96, xl: 128 };

  var ALL_TYPES = [
    "normal", "fire", "water", "electric", "grass", "ice", "fighting",
    "poison", "ground", "flying", "psychic", "bug", "rock", "ghost",
    "dragon", "dark", "steel", "fairy",
  ];

  // ---------- generic helpers ----------

  function escapeHtml(value) {
    var map = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
    return String(value).replace(/[&<>"']/g, function (c) {
      return map[c];
    });
  }

  // Alphabetical distinct-values helper, used only for non-Pokémon selects
  // (e.g. tournament tier) where alphabetical is still the more findable
  // order — Pokémon pickers use distinctSortedByMetric instead (see below;
  // docs/design-system.md's ordering convention no longer has an
  // alphabetical exception for Pokémon-name dropdowns).
  function distinctSorted(rows, field) {
    var seen = {};
    var out = [];
    rows.forEach(function (row) {
      var value = row[field];
      if (value && !seen[value]) {
        seen[value] = true;
        out.push(value);
      }
    });
    out.sort();
    return out;
  }

  // Distinct pokemon_name values from rows, ordered by descending
  // usage_share (metricByKey: pokemon_key -> usage_share) rather than
  // alphabetically — every Pokémon-picker dropdown uses this now.
  function distinctSortedByMetric(rows, metricByKey) {
    var seen = {};
    var out = [];
    rows.forEach(function (row) {
      var name = row.pokemon_name;
      if (name && !seen[name]) {
        seen[name] = true;
        out.push({ name: name, key: row.pokemon_key });
      }
    });
    out.sort(function (a, b) {
      return (metricByKey[b.key] || 0) - (metricByKey[a.key] || 0);
    });
    return out.map(function (o) {
      return o.name;
    });
  }

  function usageShareByKey() {
    var lookup = {};
    (marts.pokemon_usage_summary || []).forEach(function (r) {
      if (!r.event_tier) lookup[r.pokemon_key] = r.usage_share || 0;
    });
    return lookup;
  }

  // pokemon_key -> its pokemon_champions_profile row (stats, type_1/type_2,
  // usage/win-rate) — the shared join point for the Usage/Speed
  // Tiers/Matchup tabs' type and stat-range filters.
  function championsProfileByKey() {
    var lookup = {};
    (marts.pokemon_champions_profile || []).forEach(function (r) {
      lookup[r.pokemon_key] = r;
    });
    return lookup;
  }

  // Rough physical/special/mixed role per Pokémon, derived from the
  // damage-category split of its own recorded moveset (pokemon_move_usage,
  // weighted by usage_count) — not a sourced attribute, a UX bucketing
  // convention like SPEED_TIERS below. Status-only moves don't count
  // toward either side.
  function roleByKey() {
    var counts = {};
    (marts.pokemon_move_usage || []).forEach(function (r) {
      if (r.category !== "physical" && r.category !== "special") return;
      var c = counts[r.pokemon_key] || (counts[r.pokemon_key] = { physical: 0, special: 0 });
      c[r.category] += r.usage_count || 1;
    });
    var roles = {};
    Object.keys(counts).forEach(function (key) {
      var c = counts[key];
      if (c.physical === 0 && c.special === 0) return;
      if (c.physical > c.special * 1.5) roles[key] = "physical";
      else if (c.special > c.physical * 1.5) roles[key] = "special";
      else roles[key] = "mixed";
    });
    return roles;
  }

  function fillSelect(select, options, allLabel) {
    select.innerHTML = "";
    var allOption = document.createElement("option");
    allOption.value = "";
    allOption.textContent = allLabel;
    select.appendChild(allOption);
    options.forEach(function (value) {
      var opt = document.createElement("option");
      opt.value = value;
      opt.textContent = value;
      select.appendChild(opt);
    });
  }

  function renderRows(tbody, rows, rowHtmlFn) {
    tbody.innerHTML = "";
    rows.forEach(function (row, index) {
      var tr = document.createElement("tr");
      tr.innerHTML = rowHtmlFn(row, index);
      tbody.appendChild(tr);
    });
  }

  // Numeric min/max <input type="number"> pair filter (docs/design-system.md's
  // "range-filter" component) — used for usage %/win rate/speed/stat
  // ranges. Empty min/max means unbounded on that side; a null/undefined
  // value fails the filter as soon as either bound is set.
  function inRange(value, minEl, maxEl) {
    var hasMin = minEl && minEl.value !== "";
    var hasMax = maxEl && maxEl.value !== "";
    if (!hasMin && !hasMax) return true;
    if (value === null || value === undefined) return false;
    if (hasMin && value < parseFloat(minEl.value)) return false;
    if (hasMax && value > parseFloat(maxEl.value)) return false;
    return true;
  }

  // Multi-select type filter, rendered as a row of toggle chips (one per
  // ALL_TYPES entry). `selected` is a plain {type_name: true} map the
  // caller owns; an empty map means "no filter, show everything".
  function renderTypeFilterChips(container, selected, onChange) {
    if (!container) return;
    container.innerHTML = "";
    ALL_TYPES.forEach(function (type) {
      var chip = document.createElement("button");
      chip.type = "button";
      chip.className = "toggle-chip";
      chip.setAttribute("aria-pressed", selected[type] ? "true" : "false");
      chip.innerHTML = typeIconImg(type, 14) + " " + type;
      chip.addEventListener("click", function () {
        if (selected[type]) {
          delete selected[type];
        } else {
          selected[type] = true;
        }
        chip.setAttribute("aria-pressed", selected[type] ? "true" : "false");
        onChange();
      });
      container.appendChild(chip);
    });
  }

  function hasAnySelectedType(selected) {
    for (var key in selected) {
      if (Object.prototype.hasOwnProperty.call(selected, key)) return true;
    }
    return false;
  }

  function passesTypeFilter(selected, type1, type2) {
    if (!hasAnySelectedType(selected)) return true;
    return !!(selected[type1] || (type2 && selected[type2]));
  }

  // A single select-driven drill-down: fills the select from the distinct
  // pokemon_name values across rows (ranked by usage relevance, not
  // alphabetically), defaults to the first option, and calls
  // render(selectedValue) on load and on every change.
  function setupDrilldown(opts) {
    var select = document.getElementById(opts.selectId);
    if (!select) return;
    var metricByKey = usageShareByKey();
    var options = distinctSortedByMetric(opts.rows, metricByKey);
    fillSelect(select, options, opts.allLabel || "Select a Pokémon…");
    select.addEventListener("change", function () {
      opts.render(select.value);
    });
    if (options.length) {
      select.value = options[0];
    }
    opts.render(select.value);
  }

  // ---------- sprite/icon cell rendering ----------

  function spriteImg(pokemonKey, sizePx) {
    var src = sprites[pokemonKey];
    if (!src) return "";
    var size = sizePx || ICON_SIZES.sm;
    return (
      '<img class="cell-icon" style="width:' + size + "px;height:" + size + 'px" src="' +
      src + '" width="' + size + '" height="' + size +
      '" loading="lazy" decoding="async" alt="">'
    );
  }

  // The hero-slot counterpart to spriteImg: a 256px downscale of the
  // Pokémon's 512x512 HOME render (pokemon_asset's home_render kind)
  // instead of its 128x128 menu sprite, for the --icon-lg/--icon-xl boxes
  // where a menu sprite is being upscaled and visibly blurs. Falls back to
  // the menu sprite when a Pokémon has no render, and to nothing at all
  // when it has neither — a Pokémon never renders as a broken image
  // (docs/design-system.md's "Representing Pokémon").
  function heroImg(pokemonKey, sizePx) {
    var src = heroArt[pokemonKey];
    if (!src) return spriteImg(pokemonKey, sizePx || ICON_SIZES.lg);
    var size = sizePx || ICON_SIZES.lg;
    return (
      '<img class="cell-icon hero-art" style="width:' + size + "px;height:" + size + 'px" src="' +
      src + '" width="' + size + '" height="' + size +
      '" loading="lazy" decoding="async" alt="">'
    );
  }

  function pokemonCell(pokemonKey, pokemonName) {
    return (
      '<div class="cell-with-icon">' + spriteImg(pokemonKey) + "<span>" +
      escapeHtml(pokemonName) + "</span></div>"
    );
  }

  // A team drawn as the six Pokémon it actually is. `pokemonKeys` is the
  // pipe-delimited, slot-ordered string the team marts publish
  // (top_tournament_teams.pokemon_keys, team_list_convergence.pokemon_keys).
  // Before this existed, a six-Pokémon team was rendered as its first
  // slot's sprite alone, which misrepresented the team rather than merely
  // under-illustrating it.
  function teamCompositionHtml(pokemonKeys, sizePx) {
    var keys = String(pokemonKeys || "")
      .split("|")
      .filter(Boolean);
    if (!keys.length) return "";
    var size = sizePx || ICON_SIZES.sm;
    return (
      '<div class="team-comp">' +
      keys
        .map(function (key) {
          var img = spriteImg(key, size);
          // Keep the slot even when its sprite is unresolvable, so the
          // composition still reads as six Pokémon rather than silently
          // shrinking to five.
          return (
            '<span class="team-comp-slot" title="' +
            escapeHtml(pokemonNames[key] || key) +
            '">' +
            (img || '<span class="team-comp-blank"></span>') +
            "</span>"
          );
        })
        .join("") +
      "</div>"
    );
  }

  // A `typeFn` for renderGrid6xn that resolves a row's types through
  // pokemon_champions_profile, so usage/win-rate grids (whose own marts
  // carry no type columns) can still take a type accent.
  function typeFnFromProfile() {
    var profiles = championsProfileByKey();
    return function (row) {
      return profiles[row.pokemon_key] || {};
    };
  }

  // A country's flag as a Unicode regional-indicator pair, derived from its
  // ISO 3166-1 alpha-2 code — no asset, no network, no lookup table.
  // Deliberately strict: anything that isn't exactly two ASCII letters
  // returns "" rather than a guess, because a *wrong* flag misattributes a
  // real player to a country they don't represent, which is worse than no
  // flag at all.
  function countryFlag(code) {
    var value = String(code || "").trim().toUpperCase();
    if (!/^[A-Z]{2}$/.test(value)) return "";
    return String.fromCodePoint(
      0x1f1e6 + value.charCodeAt(0) - 65,
      0x1f1e6 + value.charCodeAt(1) - 65
    );
  }

  // Country cell: flag glyph plus the code itself. The code always stays
  // visible — a flag emoji renders as tofu on some platforms, and two
  // letters are unambiguous where a small flag is not.
  function countryCell(code) {
    var flag = countryFlag(code);
    var label = escapeHtml(code || "—");
    return flag ? '<span class="country-flag" aria-hidden="true">' + flag + "</span> " + label : label;
  }

  // Per-type accent color (docs/design-system.md's "Type color accents"),
  // from the palette pipelines/render/template.py owns and build.py emits
  // into the payload. Unknown/absent types fall back to the neutral
  // --type-unknown rather than to a random hue.
  function typeColor(typeName) {
    if (!typeName) return "var(--type-unknown)";
    return typeColors[String(typeName).toLowerCase()] || "var(--type-unknown)";
  }

  // A left-edge accent bar built from a Pokémon's one or two types, as an
  // inline style value. Two types blend at the midpoint so a dual-type
  // Pokémon reads as both rather than as its primary only.
  function typeAccentGradient(type1, type2) {
    var c1 = typeColor(type1);
    var c2 = type2 ? typeColor(type2) : c1;
    return "linear-gradient(180deg, " + c1 + " 0%, " + c1 + " 50%, " + c2 + " 50%, " + c2 + " 100%)";
  }

  // The committed type-icon PNGs (static/icons/types/) are wide 200x40
  // "icon + type name" badges (a PokéAPI/sprites generation-ix asset), not
  // bare square icons — the symbol always sits in a fixed-width square on
  // the left edge, with the type name filling the rest. Squishing the
  // whole 5:1 image into a square (the old approach) stretched the text
  // into an illegible blob; instead this crops to just that left square
  // (an overflow:hidden window sized to `size`, holding a height:`size`
  // image scaled to its natural ~5:1 aspect so only the icon shows) —
  // a real icon-only emblem, not a squished text badge.
  function typeIconImg(typeName, sizePx) {
    var src = typeIcons[typeName];
    if (!src) return "";
    var size = sizePx || 18;
    return (
      '<span class="type-icon-crop" style="width:' + size + "px;height:" + size +
      'px" title="' + escapeHtml(typeName) + '">' +
      '<img src="' + src + '" alt="' + escapeHtml(typeName) + '" style="height:' + size + 'px">' +
      "</span>"
    );
  }

  // Renders a Pokémon's type_1/type_2 into `container` as a type-badge row
  // of icon-only emblems (no visible text label — the type name is exposed
  // via each pill's aria-label and the icon's title attribute instead).
  // large=true switches to the Profile header's --icon-xl dual-type
  // display (docs/design-system.md's "Larger type badge"); otherwise it's
  // the compact pill used in the Matchup tab's picker panels.
  function renderTypeBadgeRow(container, type1, type2, large) {
    if (!container) return;
    var types = [type1, type2].filter(Boolean);
    if (!types.length) {
      container.innerHTML = "";
      return;
    }
    if (large) {
      // A type-colored pill with a small icon and the type name. The
      // earlier 64px ringed emblems competed with the Pokémon's own art on
      // the Profile header, and the bare icons needed a hover to read.
      container.className = "type-badge-row type-badge-lg";
      container.innerHTML = types
        .map(function (t) {
          return '<span class="type-pill-lg" style="--pill-type-color:' + typeColor(t) + '">' +
            typeIconImg(t, 20) + "<span>" + escapeHtml(t) + "</span></span>";
        })
        .join("");
    } else {
      container.className = "type-badge-row";
      container.innerHTML = types
        .map(function (t) {
          return '<span class="type-pill" role="img" aria-label="' + escapeHtml(t) + ' type">' +
            typeIconImg(t, 18) + "</span>";
        })
        .join("");
    }
  }

  function formatPercent(value) {
    return value === null || value === undefined ? "—" : (value * 100).toFixed(1) + "%";
  }

  // Speed-tier bucketing (docs/design-system.md's "Speed-tier badge"
  // component) — thresholds are documented there and must stay in sync
  // with this function, the single source of truth for the bucketing
  // logic itself.
  var SPEED_TIERS = [
    { max: Infinity, min: 120, label: "Blazing", cls: "badge-speed-blazing" },
    { max: 119, min: 90, label: "Fast", cls: "badge-speed-fast" },
    { max: 89, min: 60, label: "Average", cls: "badge-speed-average" },
    { max: 59, min: -Infinity, label: "Slow", cls: "badge-speed-slow" },
  ];
  function speedTier(speed) {
    for (var i = 0; i < SPEED_TIERS.length; i++) {
      if (speed >= SPEED_TIERS[i].min) return SPEED_TIERS[i];
    }
    return SPEED_TIERS[SPEED_TIERS.length - 1];
  }
  function speedTierBadge(speed) {
    var tier = speedTier(speed);
    return '<span class="badge ' + tier.cls + '">' + tier.label + "</span>";
  }

  function itemCell(itemName) {
    if (!itemName) return "—";
    var src = itemIcons[itemName];
    var icon = src ? '<img class="cell-icon" src="' + src + '" alt="">' : "";
    return '<div class="cell-with-icon">' + icon + "<span>" + escapeHtml(itemName) + "</span></div>";
  }

  // ---------- 6-wide grid (docs/design-system.md's ".grid-6xn component") ----------

  // The dashboard's primary visual for any usage/win-rate metric,
  // replacing the old per-metric ranked-list bars (dashboard "replace
  // usage/win-rate bar charts with a 6xn grid just like overview" ask).
  // opts mirror renderRankedList's: keyFn/iconFn, labelFn, displayFn
  // (bolded headline value), subFn (optional second line — a description,
  // a secondary stat), showRank (default true).
  function renderGrid6xn(container, rows, opts) {
    if (!container) return;
    container.innerHTML = "";
    if (!rows.length) {
      container.innerHTML = '<p class="empty-state">No data yet.</p>';
      return;
    }
    // Type accent resolution, decided once per call rather than per row.
    // Any Pokémon-keyed grid gets it automatically — passing typeFn: false
    // opts out, and an explicit typeFn overrides the default lookup. Doing
    // it here rather than at each of the call sites is what makes
    // docs/design-system.md's "every Pokémon-keyed tile carries its type
    // accent" true by construction instead of by remembering.
    var typeFn = opts.typeFn;
    if (typeFn === undefined && opts.keyFn) typeFn = typeFnFromProfile();

    rows.forEach(function (row, i) {
      // Three ways to give a tile its visual, most specific first:
      //   iconHtmlFn -> arbitrary markup (a six-sprite team composition)
      //   iconFn     -> a direct src (a move-type or item icon)
      //   keyFn      -> a pokemon_key resolved against the sprite map
      var iconHtml = opts.iconHtmlFn ? opts.iconHtmlFn(row) : null;
      var iconSrc =
        iconHtml == null
          ? opts.iconFn
            ? opts.iconFn(row)
            : opts.keyFn
              ? sprites[opts.keyFn(row)]
              : null
          : null;
      var tile = document.createElement("div");
      tile.className = "grid-6xn-tile" + (i === 0 && opts.showLeader !== false ? " is-leader" : "");
      // Type accent: a left-edge bar in the Pokémon's own type colors, on
      // tiles whose row carries type data. Purely additive — a row without
      // types renders exactly as before.
      if (typeFn) {
        var types = typeFn(row) || {};
        if (types.type_1) {
          tile.classList.add("has-type-accent");
          tile.style.setProperty(
            "--tile-accent",
            typeAccentGradient(types.type_1, types.type_2)
          );
        }
      }
      tile.innerHTML =
        (opts.showRank !== false ? '<span class="badge badge-rank">#' + (i + 1) + "</span>" : "") +
        (iconHtml || (iconSrc ? '<img src="' + iconSrc + '" alt="" loading="lazy" decoding="async">' : "")) +
        '<div class="grid-6xn-label">' + escapeHtml(opts.labelFn(row)) + "</div>" +
        '<div class="grid-6xn-value">' + escapeHtml(opts.displayFn(row)) + "</div>" +
        (opts.subFn && opts.subFn(row) ? '<div class="grid-6xn-sub">' + escapeHtml(opts.subFn(row)) + "</div>" : "");
      container.appendChild(tile);
    });
  }

  // ---------- sortable table ----------

  // Wraps a <table> whose <th data-sort-key> headers should re-sort its
  // body on click (toggling asc/desc), replacing the previous fixed-sort-
  // only tables. Renders once immediately; call .setRows(newRows) when the
  // underlying data changes (e.g. a filter) to re-render with the current
  // sort state preserved.
  function makeSortableTable(table, initialRows, renderRowFn, opts) {
    opts = opts || {};
    var tbody = table.querySelector("tbody");
    var ths = table.querySelectorAll("th[data-sort-key]");
    var state = { key: opts.defaultKey || null, dir: opts.defaultDir || "desc" };
    var rows = initialRows;

    function sortedRows() {
      if (!state.key) return rows;
      return rows.slice().sort(function (a, b) {
        var av = a[state.key];
        var bv = b[state.key];
        av = av === null || av === undefined ? -Infinity : av;
        bv = bv === null || bv === undefined ? -Infinity : bv;
        var cmp = av < bv ? -1 : av > bv ? 1 : 0;
        return state.dir === "asc" ? cmp : -cmp;
      });
    }

    function render() {
      renderRows(tbody, sortedRows(), renderRowFn);
      ths.forEach(function (th) {
        var existing = th.querySelector(".sort-indicator");
        if (existing) existing.remove();
        if (th.getAttribute("data-sort-key") === state.key) {
          var span = document.createElement("span");
          span.className = "sort-indicator";
          span.textContent = state.dir === "asc" ? "▲" : "▼";
          th.appendChild(span);
        }
      });
    }

    ths.forEach(function (th) {
      th.addEventListener("click", function () {
        var key = th.getAttribute("data-sort-key");
        if (state.key === key) {
          state.dir = state.dir === "desc" ? "asc" : "desc";
        } else {
          state.key = key;
          state.dir = "desc";
        }
        render();
      });
    });

    render();
    return {
      setRows: function (newRows) {
        rows = newRows;
        render();
      },
    };
  }

  // ---------- tab switching ----------

  var tabInitializers = {};
  var activeTabId = null;
  var initialized = {};
  var tabNeedsMarts = {};

  // opts.needsMarts === false marks a tab that renders entirely from the
  // inline critical payload (kpis/sprites/names) and so must not wait on
  // the data.json fetch — Overview is the one such tab today, which is why
  // the landing view paints with no network at all.
  // opts.needsMarts === false: renders from the inline payload alone.
  // opts.extraMarts: on-demand marts (DATA.mart_files.on_demand) the tab
  // reads beyond the core and regulation files.
  var tabExtraMarts = {};
  function registerTab(tabId, initFn, opts) {
    tabInitializers[tabId] = initFn;
    tabNeedsMarts[tabId] = !(opts && opts.needsMarts === false);
    tabExtraMarts[tabId] = (opts && opts.extraMarts) || [];
    // A tab registered after the page already opened on it (a #matchup
    // link, with matchup.js loading after app.js) initialises now.
    if (activeTabId === tabId) initTab(tabId);
  }

  // ---------- lazy mart payload ----------

  // index.html inlines only the critical payload (KPIs, sprite/hero/type
  // icon maps, display names). The marts live in shard files indexed by
  // DATA.mart_files (pipelines/dashboard/build.py's _write_mart_shards):
  // a core file plus the selected regulation's file load on the first tab
  // that needs marts, and the largest marts (head-to-head, triple cores,
  // player signatures) load only when a tab that reads them opens
  // (registerTab's extraMarts). Each file is fetched at most once.
  var shardPromises = {};

  function fetchShard(path) {
    if (!shardPromises[path]) {
      shardPromises[path] = fetch(path)
        .then(function (response) {
          if (!response.ok) throw new Error("HTTP " + response.status + " for " + path);
          return response.json();
        })
        .then(function (loaded) {
          // Mutated in place, never reassigned: matchup.js and teams.js hold
          // a reference to this same object via window.DashboardApp.marts.
          Object.keys(loaded || {}).forEach(function (name) {
            marts[name] = applyRegulationScope(loaded[name]);
          });
          return marts;
        })
        .catch(function (error) {
          delete shardPromises[path];
          throw error;
        });
    }
    return shardPromises[path];
  }

  function ensureData(extraMarts) {
    var files = DATA.mart_files;
    if (!files) return Promise.resolve(marts);
    var paths = [files.core];
    var scopePath = files.scopes && (files.scopes[regulationScope] || files.scopes[ALL_SCOPE]);
    if (scopePath) paths.push(scopePath);
    (extraMarts || []).forEach(function (name) {
      if (files.on_demand && files.on_demand[name]) paths.push(files.on_demand[name]);
    });
    return Promise.all(paths.filter(Boolean).map(fetchShard)).then(function () {
      return marts;
    });
  }

  // fetch() against a file:// URL is blocked as a cross-origin request, so
  // a page opened by double-clicking index.html can load the inline
  // critical payload but never the marts. Say so, with the fix, rather
  // than leaving a permanently empty panel.
  function renderDataLoadError(tabId, error) {
    var panel = document.querySelector('.tab-panel[data-panel="' + tabId + '"]');
    if (!panel || panel.querySelector(".data-load-error")) return;
    var isFileProtocol = window.location.protocol === "file:";
    var message = isFileProtocol
      ? "This page loads its data from files under data/, which a browser will not fetch over file://. " +
        "Serve the directory instead: python -m http.server -d docs/dashboard"
      : "Could not load the dashboard data (" + String(error && error.message) + ").";
    var box = document.createElement("p");
    box.className = "empty-state data-load-error";
    box.textContent = message;
    panel.insertBefore(box, panel.firstChild);
  }

  // Two-level navigation (docs/upgrade-plan-2026q4.md, B2): five section
  // buttons, each owning a row of view buttons (.tab-btn[data-section]).
  // Only the active section's row shows, and only when it has more than
  // one view; the KPI strip shows on Meta only. The open view lives in the
  // URL hash (#usage), so a link opens the same view and the regulation
  // selector's reload keeps it. Each section remembers its last view.
  function setupTabs(onActivate) {
    var buttons = Array.prototype.slice.call(document.querySelectorAll(".tab-btn"));
    var panels = document.querySelectorAll(".tab-panel");
    var sectionButtons = Array.prototype.slice.call(document.querySelectorAll(".section-btn"));
    var tabRow = document.querySelector(".tabs");
    var kpiStrip = document.getElementById("kpi-strip");
    var lastTabBySection = {};

    function sectionOf(tabId) {
      var btn = buttons.filter(function (b) { return b.getAttribute("data-tab") === tabId; })[0];
      return btn ? btn.getAttribute("data-section") : null;
    }

    function activate(tabId) {
      var section = sectionOf(tabId);
      lastTabBySection[section] = tabId;
      var inSection = 0;
      buttons.forEach(function (btn) {
        var mine = btn.getAttribute("data-section") === section;
        btn.hidden = !mine;
        if (mine) inSection += 1;
        btn.setAttribute("aria-selected", btn.getAttribute("data-tab") === tabId ? "true" : "false");
      });
      if (tabRow) tabRow.hidden = inSection < 2;
      sectionButtons.forEach(function (btn) {
        if (btn.getAttribute("data-section") === section) btn.setAttribute("aria-current", "true");
        else btn.removeAttribute("aria-current");
      });
      if (kpiStrip) kpiStrip.hidden = section !== "meta";
      panels.forEach(function (panel) {
        panel.hidden = panel.getAttribute("data-panel") !== tabId;
      });
      if (onActivate) onActivate(tabId);
    }

    function go(tabId) {
      activate(tabId);
      if (window.history && window.history.replaceState) {
        window.history.replaceState(null, "", window.location.search + "#" + tabId);
      }
    }

    buttons.forEach(function (btn) {
      btn.addEventListener("click", function () {
        go(btn.getAttribute("data-tab"));
      });
    });
    sectionButtons.forEach(function (btn) {
      btn.addEventListener("click", function () {
        var section = btn.getAttribute("data-section");
        var first = buttons.filter(function (b) { return b.getAttribute("data-section") === section; })[0];
        var target = lastTabBySection[section] || (first && first.getAttribute("data-tab"));
        if (target) go(target);
        window.scrollTo(0, 0);
      });
    });
    var fromHash = window.location.hash.replace(/^#/, "");
    activate(sectionOf(fromHash) ? fromHash : "overview");
  }

  // ---------- sub-tabs ----------

  // A pill row nested inside one top-level tab/section (docs/design-
  // system.md's "Sub-tabs" component) — e.g. Usage's Usage-leaders/Win-
  // rate-leaders, Pokémon Profile's Items/Ability/Moves/Team Cores.
  // buttons/panels are NodeLists or arrays; buttons carry data-subtab,
  // panels carry data-subpanel, matched by that id. Defaults to the first
  // button. Distinct from setupTabs (the page's nine top-level tabs).
  function setupSubTabs(buttons, panels, onActivate) {
    buttons = Array.prototype.slice.call(buttons);
    panels = Array.prototype.slice.call(panels);
    function activate(id) {
      buttons.forEach(function (btn) {
        btn.setAttribute("aria-selected", btn.getAttribute("data-subtab") === id ? "true" : "false");
      });
      panels.forEach(function (panel) {
        panel.hidden = panel.getAttribute("data-subpanel") !== id;
      });
      if (onActivate) onActivate(id);
    }
    buttons.forEach(function (btn) {
      btn.addEventListener("click", function () {
        activate(btn.getAttribute("data-subtab"));
      });
    });
    if (buttons.length) activate(buttons[0].getAttribute("data-subtab"));
  }

  // ---------- per-tab setup (each called once, on first activation) ----------

  function moverListHtml(rows, showDelta) {
    if (!rows.length) return '<p class="empty-state">None.</p>';
    return "<ol class=\"mover-list\">" + rows.map(function (r) {
      var delta = r.usage_share_delta;
      var deltaHtml = "";
      if (showDelta && delta != null) {
        var sign = delta > 0 ? "+" : "";
        deltaHtml = '<span class="mover-delta ' + (delta > 0 ? "is-up" : "is-down") + '">' +
          sign + (delta * 100).toFixed(1) + " pts</span>";
      }
      return "<li>" + spriteImg(r.pokemon_key, ICON_SIZES.sm) +
        '<span class="mover-name">' + escapeHtml(r.pokemon_name || r.pokemon_key) + "</span>" +
        '<span class="mover-share">' + formatPercent(r.usage_share) + "</span>" + deltaHtml + "</li>";
    }).join("") + "</ol>";
  }

  // "What changed" (docs/upgrade-plan-2026q4.md, A4/B5): the selected
  // regulation against the one before it, from pokemon_regulation_movers
  // summarised server-side (summarize_movers). When either regulation has
  // too few teams for a delta to mean much, it shows the sample sizes and
  // new arrivals only.
  function renderMovers() {
    var panel = document.getElementById("movers-panel");
    var movers = DATA.kpis && DATA.kpis.movers;
    if (!panel || !movers) return;
    var title = "What changed in " + scopeLabel(movers.regulation_code) + " vs " +
      scopeLabel(movers.previous_regulation_code);
    var sample = movers.team_count.toLocaleString() + " teams this regulation · " +
      movers.previous_team_count.toLocaleString() + " in the previous one. " +
      "Shares are of all roster slots in each regulation's events.";
    var columns = [];
    if (movers.reliable) {
      columns.push('<div><h4>Rising</h4>' + moverListHtml(movers.risers, true) + "</div>");
      columns.push('<div><h4>Falling</h4>' + moverListHtml(movers.fallers, true) + "</div>");
    } else {
      sample += " Too few teams on one side to compare shares reliably, so only new arrivals are shown.";
    }
    columns.push('<div><h4>New this regulation</h4>' + moverListHtml(movers.new_arrivals, false) + "</div>");
    panel.innerHTML = "<h3>" + escapeHtml(title) + '</h3><p class="sub">' + escapeHtml(sample) +
      '</p><div class="mover-columns">' + columns.join("") + "</div>";
    panel.hidden = false;
  }

  function setupOverview() {
    var overviewSub = document.getElementById("overview-sub");
    if (overviewSub) {
      overviewSub.textContent = "Top 12 most-used Pokémon in " + scopeLabel(regulationScope) +
        ", ranked by share of roster slots.";
    }
    renderMovers();
    var top12 = (DATA.kpis && DATA.kpis.top_12_pokemon) || [];
    renderGrid6xn(document.getElementById("overview-top-12"), top12, {
      keyFn: function (r) {
        return r.pokemon_key;
      },
      // Read off the row itself, not through pokemon_champions_profile:
      // this tab renders before the marts are fetched, so the types are
      // joined into the KPI rows server-side (see compute_kpis).
      typeFn: function (r) {
        return { type_1: r.type_1, type_2: r.type_2 };
      },
      labelFn: function (r) {
        return r.pokemon_name;
      },
      displayFn: function (r) {
        return formatPercent(r.usage_share);
      },
      subFn: function (r) {
        return formatPercent(r.win_rate) + " win rate";
      },
    });
  }

  // Tier List (docs/upgrade-plan-2026q4.md, B5). Bands by usage share in
  // the selected regulation; the chip beside each Pokémon is its win rate,
  // coloured only when the 95% Wilson interval sits clearly above or below
  // 50%. Usage decides the band and win rate qualifies it, kept as two
  // signals rather than blended into one opaque score.
  var TIERS = [
    { id: "s", label: "S", min: 0.04 },
    { id: "a", label: "A", min: 0.02 },
    { id: "b", label: "B", min: 0.01 },
    { id: "c", label: "C", min: 0.005 },
  ];

  function setupTiers() {
    var body = document.getElementById("tiers-body");
    var method = document.getElementById("tiers-method");
    if (!body) return;
    var winByKey = {};
    (marts.pokemon_win_rate_summary || []).forEach(function (r) {
      winByKey[r.pokemon_key] = r;
    });
    var rows = (marts.pokemon_usage_summary || [])
      .filter(function (r) { return !r.event_tier; })
      .sort(function (a, b) { return a.usage_rank - b.usage_rank; });
    if (method) {
      method.textContent = "Bands by share of roster slots in " + scopeLabel(regulationScope) +
        ": S ≥ 4%, A 2–4%, B 1–2%, C 0.5–1%. The chip is win rate: green when its 95% Wilson lower bound " +
        "is above 50%, red when even its upper bound is below 50%, grey otherwise. Click a Pokémon for its profile.";
    }
    body.innerHTML = TIERS.map(function (tier, i) {
      var max = i === 0 ? Infinity : TIERS[i - 1].min;
      var members = rows.filter(function (r) {
        return r.usage_share >= tier.min && r.usage_share < max;
      });
      if (!members.length) return "";
      var chips = members.map(function (r) {
        var win = winByKey[r.pokemon_key];
        var wrHtml = "";
        if (win && win.win_rate != null) {
          // Upper bound mirrors the Wilson lower bound around the point
          // estimate; enough to flag "clearly losing" without a second mart.
          var upper = win.win_rate + (win.win_rate - (win.wilson_lower_bound || 0));
          var cls = win.wilson_lower_bound > 0.5 ? " is-strong" : upper < 0.5 ? " is-weak" : "";
          wrHtml = '<span class="tier-wr' + cls + '" title="' + win.record_count + ' recorded results">' +
            formatPercent(win.win_rate) + "</span>";
        }
        return '<button type="button" class="tier-chip" data-pokemon="' + escapeHtml(r.pokemon_name) + '">' +
          spriteImg(r.pokemon_key, ICON_SIZES.sm) + escapeHtml(r.pokemon_name) +
          ' <span class="set-share">' + formatPercent(r.usage_share) + "</span>" + wrHtml + "</button>";
      }).join("");
      return '<div class="tier-row"><div class="tier-label tier-' + tier.id + '">' + tier.label +
        "<small>" + members.length + "</small></div>" +
        '<div class="tier-members">' + chips + "</div></div>";
    }).join("") || '<p class="empty-state">No usage data for this regulation yet.</p>';
    body.addEventListener("click", function (e) {
      var chip = e.target.closest(".tier-chip");
      if (!chip) return;
      openProfile(chip.getAttribute("data-pokemon"));
    });
  }

  // Opens the Pokémon Profile on a given display name (the profile
  // select's option values), from any view.
  function openProfile(pokemonName) {
    var tab = document.querySelector('.tab-btn[data-tab="pokemon-profile"]');
    if (tab) tab.click();
    ensureData().then(function () {
      var select = document.getElementById("pokemon-profile-filter");
      if (!select) return;
      select.value = pokemonName;
      select.dispatchEvent(new Event("change", { bubbles: true }));
      window.scrollTo(0, 0);
    });
  }

  function setupUsage() {
    var usageRows = marts.pokemon_usage_summary || [];
    var profileByKey = championsProfileByKey();
    var roles = roleByKey();

    var tierSelect = document.getElementById("usage-tier-filter");
    var roleSelect = document.getElementById("usage-role-filter");
    var typeFilterEl = document.getElementById("usage-type-filter");
    var shareMin = document.getElementById("usage-share-min");
    var shareMax = document.getElementById("usage-share-max");
    var speedMin = document.getElementById("usage-speed-min");
    var speedMax = document.getElementById("usage-speed-max");
    var selectedTypes = {};

    // Rows are already scoped to the page's regulation (the header's
    // Regulation selector; see applyRegulationScope), so this tab only
    // filters by tier. It used to carry its own Regulation select, which
    // could only approximate a regulation by its legal pool.
    function filteredRows(tier) {
      return usageRows.filter(function (r) {
        if ((r.event_tier || "") !== tier) return false;
        var profile = profileByKey[r.pokemon_key];
        if (!passesTypeFilter(selectedTypes, profile && profile.type_1, profile && profile.type_2)) return false;
        if (roleSelect && roleSelect.value && roles[r.pokemon_key] !== roleSelect.value) return false;
        if (!inRange(r.usage_share != null ? r.usage_share * 100 : null, shareMin, shareMax)) return false;
        if (!inRange(profile ? profile.speed : null, speedMin, speedMax)) return false;
        return true;
      });
    }

    var grid = document.getElementById("usage-grid");
    var usageTable = document.getElementById("usage-leaders-table");
    var usageTableSortable = usageTable
      ? makeSortableTable(
          usageTable,
          [],
          function (r) {
            return (
              '<td><span class="badge badge-rank">#' + r.usage_rank + "</span></td>" +
              "<td>" + pokemonCell(r.pokemon_key, r.pokemon_name) + "</td>" +
              "<td>" + formatPercent(r.usage_share) + "</td>"
            );
          },
          {}
        )
      : null;

    function drawUsage() {
      var tier = tierSelect ? tierSelect.value : "";
      var rows = filteredRows(tier)
        .slice()
        .sort(function (a, b) {
          return a.usage_rank - b.usage_rank;
        });
      renderGrid6xn(grid, rows.slice(0, 18), {
        keyFn: function (r) {
          return r.pokemon_key;
        },
        labelFn: function (r) {
          return r.pokemon_name;
        },
        displayFn: function (r) {
          return formatPercent(r.usage_share);
        },
      });
      if (usageTableSortable) usageTableSortable.setRows(rows.slice(0, 30));
    }

    if (tierSelect) {
      var tiers = distinctSorted(usageRows, "event_tier");
      fillSelect(tierSelect, tiers, "Overall");
      tierSelect.addEventListener("change", drawUsage);
    }
    renderTypeFilterChips(typeFilterEl, selectedTypes, drawUsage);
    [roleSelect, shareMin, shareMax, speedMin, speedMax].forEach(function (el) {
      if (!el) return;
      el.addEventListener("input", drawUsage);
      el.addEventListener("change", drawUsage);
    });
    drawUsage();

    var winRows = marts.pokemon_win_rate_summary || [];
    var winGrid = document.getElementById("win-rate-grid");
    var winTable = document.getElementById("win-rate-table");
    var minRecordSelect = document.getElementById("win-rate-min-record-count-filter");
    var winSortable = winTable
      ? makeSortableTable(
          winTable,
          [],
          function (r, i) {
            return (
              '<td><span class="badge badge-rank">#' + (i + 1) + "</span></td>" +
              "<td>" + pokemonCell(r.pokemon_key, r.pokemon_name) + "</td>" +
              "<td>" + formatPercent(r.win_rate) + ' <span class="ranked-value">(n=' + r.record_count + ")</span></td>"
            );
          },
          { defaultKey: "win_rate" }
        )
      : null;
    function updateWinRows() {
      var floor = minRecordSelect ? parseInt(minRecordSelect.value, 10) : 5;
      var filtered = winRows
        .filter(function (r) {
          return r.record_count >= floor;
        })
        .slice()
        .sort(function (a, b) {
          return b.win_rate - a.win_rate;
        });
      renderGrid6xn(winGrid, filtered.slice(0, 18), {
        keyFn: function (r) {
          return r.pokemon_key;
        },
        labelFn: function (r) {
          return r.pokemon_name;
        },
        displayFn: function (r) {
          return formatPercent(r.win_rate);
        },
        subFn: function (r) {
          return "n=" + r.record_count;
        },
      });
      if (winSortable) winSortable.setRows(filtered.slice(0, 30));
    }
    if (minRecordSelect) minRecordSelect.addEventListener("change", updateWinRows);
    updateWinRows();

    setupUsageSuccess();
    setupUsageTrends();

    setupSubTabs(
      document.querySelectorAll('.tab-panel[data-panel="usage"] .subtab-btn'),
      document.querySelectorAll('.tab-panel[data-panel="usage"] .subtab-panel')
    );
  }

  // Success subtab (backlog #8's pokemon_placement_weighted_usage): the
  // "popular vs. successful" split. rank_movement is computed here rather
  // than in the mart because it compares two marts' ranks
  // (pokemon_usage_summary's overall usage_rank against this mart's own
  // rank under the selected weighting) — positive means the Pokémon
  // places better once results are weighted in than raw usage suggests.
  function rankMovementBadgeHtml(row) {
    if (row.rank_movement === null || row.rank_movement === undefined) return "—";
    if (row.rank_movement === 0) return '<span class="badge badge-rank">±0</span>';
    var cls = row.rank_movement > 0 ? "badge-positive" : "badge-negative";
    var arrow = row.rank_movement > 0 ? "▲ +" : "▼ ";
    return '<span class="badge ' + cls + '">' + arrow + row.rank_movement + "</span>";
  }

  function setupUsageSuccess() {
    var successRows = marts.pokemon_placement_weighted_usage || [];
    var metricSelect = document.getElementById("usage-success-metric");
    var grid = document.getElementById("usage-success-grid");
    var table = document.getElementById("usage-success-table");
    if (!grid && !table) return;

    var usageByKey = {};
    (marts.pokemon_usage_summary || []).forEach(function (r) {
      if (!r.event_tier) usageByKey[r.pokemon_key] = r;
    });

    var tableSortable = table
      ? makeSortableTable(
          table,
          [],
          function (r, i) {
            return (
              '<td><span class="badge badge-rank">#' + (i + 1) + "</span></td>" +
              "<td>" + pokemonCell(r.pokemon_key, r.pokemon_name) + "</td>" +
              "<td>" + formatPercent(r.weighted_usage_share) + "</td>" +
              "<td>" + formatPercent(r.top_cut_usage_share) + "</td>" +
              "<td>" + formatPercent(r.usage_share) + "</td>" +
              "<td>" + rankMovementBadgeHtml(r) + "</td>"
            );
          },
          { defaultKey: null }
        )
      : null;

    function rankedRows() {
      var byTopCut = metricSelect && metricSelect.value === "top_cut";
      var shareField = byTopCut ? "top_cut_usage_share" : "weighted_usage_share";
      var ranked = successRows
        .slice()
        .sort(function (a, b) {
          return (b[shareField] || 0) - (a[shareField] || 0);
        })
        .map(function (r, i) {
          var usage = usageByKey[r.pokemon_key];
          return {
            pokemon_key: r.pokemon_key,
            pokemon_name: r.pokemon_name,
            weighted_usage_share: r.weighted_usage_share,
            top_cut_usage_share: r.top_cut_usage_share,
            usage_share: usage ? usage.usage_share : null,
            success_share: r[shareField],
            rank_movement: usage ? usage.usage_rank - (i + 1) : null,
          };
        });
      return ranked;
    }

    function draw() {
      var rows = rankedRows();
      renderGrid6xn(grid, rows.slice(0, 18), {
        keyFn: function (r) {
          return r.pokemon_key;
        },
        labelFn: function (r) {
          return r.pokemon_name;
        },
        displayFn: function (r) {
          return formatPercent(r.success_share);
        },
        subFn: function (r) {
          if (r.rank_movement === null || r.rank_movement === undefined) return "";
          if (r.rank_movement === 0) return "±0 vs. usage rank";
          return (r.rank_movement > 0 ? "▲ +" : "▼ ") + r.rank_movement + " vs. usage rank";
        },
      });
      if (tableSortable) tableSortable.setRows(rows.slice(0, 30));
    }

    if (metricSelect) metricSelect.addEventListener("change", draw);
    draw();
  }

  // Usage-by-tournament-date subtab (backlog #6's data half; #29/#30's UI
  // half): a date filter (#30) plus a "vs. the previous tournament date"
  // delta per Pokémon (#29's dependency-free stand-in for a line chart —
  // this dashboard has no charting library, see the module docstring
  // above). event_date is a tournament date, not an extraction
  // snapshot_date, so this trend is real even with only one snapshot's
  // worth of staging history.
  function trendDeltaLabel(row) {
    if (row.is_new) return "NEW";
    if (row.usage_share_delta === null || row.usage_share_delta === undefined) return "";
    var points = row.usage_share_delta * 100;
    var arrow = points > 0 ? "▲" : points < 0 ? "▼" : "";
    var sign = points > 0 ? "+" : "";
    return arrow + " " + sign + points.toFixed(1) + "pp";
  }

  function trendDeltaBadgeHtml(row) {
    if (row.is_new) return '<span class="badge badge-new">NEW</span>';
    if (row.usage_share_delta === null || row.usage_share_delta === undefined) return "—";
    var points = row.usage_share_delta * 100;
    var cls = points > 0 ? "badge-positive" : points < 0 ? "badge-negative" : "badge-rank";
    return '<span class="badge ' + cls + '">' + escapeHtml(trendDeltaLabel(row)) + "</span>";
  }

  function setupUsageTrends() {
    var trendRows = marts.pokemon_usage_by_event_date || [];
    var dateSelect = document.getElementById("usage-trend-date-filter");
    var grid = document.getElementById("usage-trend-grid");
    var table = document.getElementById("usage-trend-table");
    var dates = distinctSorted(trendRows, "event_date").slice().reverse(); // most recent first

    var tableSortable = table
      ? makeSortableTable(
          table,
          [],
          function (r) {
            return (
              '<td><span class="badge badge-rank">#' + r.usage_rank + "</span></td>" +
              "<td>" + pokemonCell(r.pokemon_key, r.pokemon_name) + "</td>" +
              "<td>" + formatPercent(r.usage_share) + "</td>" +
              "<td>" + trendDeltaBadgeHtml(r) + "</td>"
            );
          },
          { defaultKey: "usage_rank", defaultDir: "asc" }
        )
      : null;

    function rowsForDate(date) {
      var dateIndex = dates.indexOf(date);
      var prevDate = dateIndex >= 0 && dateIndex < dates.length - 1 ? dates[dateIndex + 1] : null;
      var prevByKey = {};
      if (prevDate) {
        trendRows.forEach(function (r) {
          if (r.event_date === prevDate) prevByKey[r.pokemon_key] = r;
        });
      }
      // No prevDate at all (the earliest tournament date on record) means
      // there is nothing to compare against, full stop -- distinct from a
      // specific Pokémon genuinely being new as of `date`, which only
      // applies once a prevDate exists to have been absent from.
      return trendRows
        .filter(function (r) {
          return r.event_date === date;
        })
        .map(function (r) {
          var prev = prevByKey[r.pokemon_key];
          return {
            pokemon_key: r.pokemon_key,
            pokemon_name: r.pokemon_name,
            usage_rank: r.usage_rank,
            usage_share: r.usage_share,
            usage_share_delta: prev ? r.usage_share - prev.usage_share : null,
            is_new: !!prevDate && !prev,
          };
        })
        .sort(function (a, b) {
          return a.usage_rank - b.usage_rank;
        });
    }

    function drawTrend() {
      var date = dateSelect ? dateSelect.value : dates[0];
      var rows = rowsForDate(date);
      renderGrid6xn(grid, rows.slice(0, 18), {
        keyFn: function (r) {
          return r.pokemon_key;
        },
        labelFn: function (r) {
          return r.pokemon_name;
        },
        displayFn: function (r) {
          return formatPercent(r.usage_share);
        },
        subFn: trendDeltaLabel,
      });
      if (tableSortable) tableSortable.setRows(rows.slice(0, 30));
    }

    if (dateSelect) {
      dateSelect.innerHTML = "";
      dates.forEach(function (date) {
        var opt = document.createElement("option");
        opt.value = date;
        opt.textContent = date;
        dateSelect.appendChild(opt);
      });
      dateSelect.addEventListener("change", drawTrend);
    }
    drawTrend();
  }

  // Pokémon Profile: one Pokémon-centric view combining base stats + type,
  // then three separated Items/Ability/Moves sections (docs/design-system.md's
  // "Item / Ability / Move separation" — replaces the old single combined
  // build table), each capped and described, plus Team Cores.
  function setupPokemonProfile() {
    var profileRows = marts.pokemon_champions_profile || [];
    var itemRows = marts.pokemon_item_usage || [];
    var abilityRows = marts.pokemon_ability_usage || [];
    var moveRows = marts.pokemon_move_usage || [];
    var natureRows = marts.pokemon_nature_usage || [];
    var coreRows = marts.pokemon_team_core_usage || [];
    var synergyRows = marts.pokemon_team_synergy || [];
    var tripleRows = marts.pokemon_team_core_triple_usage || [];
    var concentrationByKey = {};
    (marts.pokemon_build_concentration || []).forEach(function (r) {
      concentrationByKey[r.pokemon_key] = r;
    });

    var select = document.getElementById("pokemon-profile-filter");
    if (!select) return;

    var sortedProfiles = profileRows.slice().sort(function (a, b) {
      return (b.usage_share || 0) - (a.usage_share || 0);
    });
    fillSelect(
      select,
      sortedProfiles.map(function (r) {
        return r.pokemon_name;
      }),
      "Select a Pokémon…"
    );

    var statsEl = document.getElementById("pokemon-profile-stats");
    var itemGrid = document.getElementById("profile-item-grid");
    var abilityGrid = document.getElementById("profile-ability-grid");
    var moveTable = document.getElementById("profile-move-table");
    var moveTableSortable = moveTable
      ? makeSortableTable(
          moveTable,
          [],
          function (r) {
            return (
              "<td>" + typeIconImg(r.move_type, 18) + " " + escapeHtml(r.move_name) + "</td>" +
              "<td>" + formatPercent(r.move_share) + "</td>" +
              "<td>" + escapeHtml(r.category || "—") + "</td>" +
              "<td>" + (r.power != null ? r.power : "—") + "</td>" +
              "<td>" + (r.accuracy != null ? r.accuracy + "%" : "—") + "</td>" +
              "<td>" + (r.pp != null ? r.pp : "—") + "</td>" +
              "<td>" + (r.priority || 0) + "</td>" +
              "<td>" + escapeHtml(r.short_effect || "") + "</td>"
            );
          },
          { defaultKey: "usage_rank", defaultDir: "asc" }
        )
      : null;
    var coreGrid = document.getElementById("profile-team-core-grid");
    var coreMetricSelect = document.getElementById("profile-team-core-metric");
    var coreSizeSelect = document.getElementById("profile-team-core-size");
    var itemConcentrationEl = document.getElementById("profile-item-concentration");
    var abilityConcentrationEl = document.getElementById("profile-ability-concentration");

    // Team Cores can be ranked two ways (backlog #9): raw co-occurrence
    // (pokemon_team_core_usage.partner_share) or synergy lift
    // (pokemon_team_synergy.lift, already floored at 5 shared teams and
    // capped per anchor in pipelines/dashboard/data.py). Lift's own tile
    // value is a multiplier, not a share, so it's formatted as "×N.N"
    // rather than run through formatPercent -- the one place in the
    // dashboard where the headline number isn't a percentage, because
    // there is no whole for it to be a share of.
    function coreRowsFor(pokemonKey) {
      if (coreSizeSelect && coreSizeSelect.value === "triples") {
        var metric = coreMetricSelect && coreMetricSelect.value === "synergy"
          ? "triple_lift"
          : "triple_team_count";
        return tripleRows
          .filter(function (r) {
            return r.triple_team_count >= 5 &&
              (r.pokemon_key_a === pokemonKey ||
                r.pokemon_key_b === pokemonKey ||
                r.pokemon_key_c === pokemonKey);
          })
          .sort(function (a, b) {
            return (b[metric] || 0) - (a[metric] || 0);
          })
          .slice(0, 12)
          .map(function (r) {
            var keys = [r.pokemon_key_a, r.pokemon_key_b, r.pokemon_key_c].filter(function (key) {
              return key !== pokemonKey;
            });
            return {
              partner_pokemon_key: keys[0],
              pokemon_keys: keys.join("|"),
              partner_pokemon_name: keys.map(function (key) {
                return pokemonNames[key] || key;
              }).join(" + "),
              display: metric === "triple_lift"
                ? "×" + (r.triple_lift || 0).toFixed(1)
                : formatPercent(r.triple_team_share),
              sub: r.triple_team_count + " teams · " + r.event_count + " events",
              is_triple: true,
            };
          });
      }
      if (coreMetricSelect && coreMetricSelect.value === "synergy") {
        return synergyRows
          .filter(function (r) {
            return r.pokemon_key === pokemonKey;
          })
          .sort(function (a, b) {
            return a.lift_rank - b.lift_rank;
          })
          .slice(0, 12)
          .map(function (r) {
            return {
              partner_pokemon_key: r.partner_pokemon_key,
              partner_pokemon_name: r.partner_pokemon_name,
              display: "×" + (r.lift || 0).toFixed(1),
              sub: r.pair_team_count + " shared teams",
            };
          });
      }
      return coreRows
        .filter(function (r) {
          return r.pokemon_key === pokemonKey;
        })
        .sort(function (a, b) {
          return a.usage_rank - b.usage_rank;
        })
        .slice(0, 15)
        .map(function (r) {
          return {
            partner_pokemon_key: r.partner_pokemon_key,
            partner_pokemon_name: r.partner_pokemon_name,
            display: formatPercent(r.partner_share),
            sub: "",
          };
        });
    }

    // Herfindahl-Hirschman index over a Pokémon's own item/ability shares
    // (backlog #14): near 1 means one locked-in build has crowded out the
    // alternatives, near 0 means the choice is genuinely contested. The
    // 0.5/0.25 cut points are a UX bucketing convention like SPEED_TIERS,
    // not a sourced threshold. An HHI of 1 across a single observed
    // option isn't a "locked-in" finding at all -- there was never a
    // choice to make -- so that case is labelled separately.
    function concentrationLabel(hhi, count) {
      if (hhi === null || hhi === undefined || !count) return "";
      if (count === 1) return '<span class="badge badge-rank">Only one recorded</span>';
      var label = hhi >= 0.5 ? "Locked in" : hhi >= 0.25 ? "Semi-contested" : "Contested";
      var cls = hhi >= 0.5 ? "badge-new" : hhi >= 0.25 ? "badge-rank" : "badge-positive";
      return (
        '<span class="badge ' + cls + '">' + label + "</span> " +
        '<span class="ranked-value">HHI ' + hhi.toFixed(2) + " across " + count + " recorded</span>"
      );
    }

    // Base stats as bars against the legal pool's median for each stat
    // (docs/upgrade-plan-2026q4.md, B4), so "Atk 130" reads as "well above
    // a typical Champions Pokémon" at a glance.
    var STAT_FIELDS = [
      ["hp", "HP"], ["attack", "Atk"], ["defense", "Def"],
      ["sp_attack", "SpA"], ["sp_defense", "SpD"], ["speed", "Spe"],
    ];
    var statMedians = {};
    STAT_FIELDS.forEach(function (field) {
      var values = profileRows
        .map(function (r) { return r[field[0]]; })
        .filter(function (v) { return v != null; })
        .sort(function (a, b) { return a - b; });
      statMedians[field[0]] = values.length ? values[Math.floor(values.length / 2)] : null;
    });
    var STAT_SCALE_MAX = 200;
    // Below this many team sheets, the most-common-set card says so.
    var MIN_SET_SAMPLE = 30;

    function statBarsHtml(profile) {
      return '<div class="stat-bars" role="list">' + STAT_FIELDS.map(function (field) {
        var value = profile[field[0]];
        var median = statMedians[field[0]];
        var width = Math.min(100, ((value || 0) / STAT_SCALE_MAX) * 100);
        var medianLeft = median != null ? Math.min(100, (median / STAT_SCALE_MAX) * 100) : null;
        var cls = median == null ? "" : value >= median * 1.15 ? " is-high" : value <= median * 0.85 ? " is-low" : "";
        return '<div class="stat-bar-row" role="listitem" aria-label="' + field[1] + " " + value +
          (median != null ? ", format median " + median : "") + '">' +
          '<span class="stat-label">' + field[1] + "</span>" +
          '<span class="stat-value">' + value + "</span>" +
          '<span class="stat-track"><span class="stat-fill' + cls + '" style="width:' + width + '%"></span>' +
          (medianLeft != null ? '<span class="stat-median" style="left:' + medianLeft + '%" title="Format median ' + median + '"></span>' : "") +
          "</span></div>";
      }).join("") + '<p class="stat-legend">Tick marks the median across the legal pool.</p></div>';
    }

    function topRow(rows, name) {
      return rows
        .filter(function (r) { return r.pokemon_name === name; })
        .sort(function (a, b) { return a.usage_rank - b.usage_rank; });
    }

    function showdownName(key) {
      return String(key).split("-").map(function (part) {
        return part.charAt(0).toUpperCase() + part.slice(1);
      }).join("-");
    }

    // The single most common choice in each slot (B4). These are separate
    // modes, not one observed team sheet: the top item and top nature may
    // never have appeared together. Labelled as such, and there is no EV
    // line because no source publishes spreads.
    function commonSetHtml(profile) {
      var item = topRow(itemRows, profile.pokemon_name)[0];
      var ability = topRow(abilityRows, profile.pokemon_name)[0];
      var nature = topRow(natureRows, profile.pokemon_name)[0];
      var moves = topRow(moveRows, profile.pokemon_name).slice(0, 4);
      if (!item && !ability && !moves.length) return "";
      var paste = [showdownName(profile.pokemon_key) + (item ? " @ " + item.item_name : "")];
      if (ability) paste.push("Ability: " + ability.ability);
      if (nature) paste.push(nature.nature + " Nature");
      moves.forEach(function (m) { paste.push("- " + m.move_name); });
      function line(label, value, share) {
        return "<dt>" + label + "</dt><dd>" + escapeHtml(value) +
          (share != null ? ' <span class="set-share">' + formatPercent(share) + "</span>" : "") + "</dd>";
      }
      var slots = item ? itemRows.filter(function (r) { return r.pokemon_name === profile.pokemon_name; })
        .reduce(function (sum, r) { return sum + (r.usage_count || 0); }, 0) : 0;
      var sampleNote = slots
        ? '<p class="set-sample' + (slots < MIN_SET_SAMPLE ? " is-thin" : "") + '">From ' + slots.toLocaleString() +
          " team sheet" + (slots === 1 ? "" : "s") + " in " + escapeHtml(scopeLabel(regulationScope)) +
          (slots < MIN_SET_SAMPLE ? ". Small sample: treat as anecdotal." : ".") + "</p>"
        : "";
      return '<div class="common-set">' +
        '<div class="common-set-head"><h3>Most common set</h3>' +
        '<button type="button" class="btn btn-sm" id="copy-common-set">Copy for Showdown</button></div>' +
        "<dl>" +
        (item ? line("Item", item.item_name, item.item_share) : "") +
        (ability ? line("Ability", ability.ability, ability.ability_share) : "") +
        (nature ? line("Nature", nature.nature, nature.nature_share) : "") +
        "</dl>" + sampleNote +
        '<ul class="set-moves">' + moves.map(function (m) {
          return "<li>" + typeIconImg(m.move_type, 18) + " " + escapeHtml(m.move_name) +
            ' <span class="set-share">' + formatPercent(m.move_share) + "</span></li>";
        }).join("") + "</ul>" +
        '<p class="stat-legend">Each line is the most common choice for that slot, counted separately. ' +
        "No EVs: tournament team sheets don't publish them.</p>" +
        '<textarea class="visually-hidden" id="common-set-paste" aria-hidden="true" tabindex="-1">' +
        escapeHtml(paste.join("\n")) + "</textarea></div>";
    }

    var setEl = document.getElementById("pokemon-profile-set");

    function render(chosenName) {
      var profile = sortedProfiles.filter(function (r) {
        return r.pokemon_name === chosenName;
      })[0];

      if (statsEl) {
        if (!profile) {
          statsEl.className = "empty-state";
          statsEl.textContent = "Select a Pokémon to see its profile.";
        } else {
          statsEl.className = "";
          // Hero slot: --icon-lg is where a 128px menu sprite was being
          // upscaled, so this reads the 256px HOME render instead.
          statsEl.style.setProperty(
            "--tile-accent",
            typeAccentGradient(profile.type_1, profile.type_2)
          );
          statsEl.classList.add("has-type-accent");
          statsEl.innerHTML =
            '<div class="cell-with-icon">' +
            // --icon-xl belongs to the Pokémon here: this is the one view
            // whose whole subject is a single Pokémon, and hero art is a
            // 256px render, so 128px is a downscale rather than the blurry
            // upscale a menu sprite would be at this size.
            heroImg(profile.pokemon_key, ICON_SIZES.xl) +
            "<div><strong>" + escapeHtml(profile.pokemon_name) + "</strong> " +
            speedTierBadge(profile.speed) +
            '<div class="type-badge-row type-badge-lg" id="profile-type-badge"></div>' +
            '<div class="profile-usage-line">' + formatPercent(profile.usage_share) + " usage · " +
            formatPercent(profile.win_rate) + " win rate in " + escapeHtml(scopeLabel(regulationScope)) +
            "</div>" + statBarsHtml(profile) + "</div></div>";
          renderTypeBadgeRow(document.getElementById("profile-type-badge"), profile.type_1, profile.type_2, true);
        }
      }
      if (setEl) {
        setEl.innerHTML = profile ? commonSetHtml(profile) : "";
        var copyBtn = document.getElementById("copy-common-set");
        if (copyBtn) {
          copyBtn.addEventListener("click", function () {
            var text = document.getElementById("common-set-paste").value;
            var done = function () {
              copyBtn.textContent = "Copied";
              setTimeout(function () { copyBtn.textContent = "Copy for Showdown"; }, 1500);
            };
            if (navigator.clipboard && navigator.clipboard.writeText) {
              navigator.clipboard.writeText(text).then(done, function () {});
            }
          });
        }
      }

      var items = chosenName
        ? itemRows
            .filter(function (r) {
              return r.pokemon_name === chosenName;
            })
            .sort(function (a, b) {
              return a.usage_rank - b.usage_rank;
            })
            .slice(0, 5)
        : [];
      renderGrid6xn(itemGrid, items, {
        iconFn: function (r) {
          return itemIcons[r.item_name];
        },
        labelFn: function (r) {
          return r.item_name;
        },
        displayFn: function (r) {
          return formatPercent(r.item_share);
        },
        subFn: function (r) {
          return r.short_effect;
        },
      });

      var abilities = chosenName
        ? abilityRows
            .filter(function (r) {
              return r.pokemon_name === chosenName;
            })
            .sort(function (a, b) {
              return a.usage_rank - b.usage_rank;
            })
            .slice(0, 5)
        : [];
      renderGrid6xn(abilityGrid, abilities, {
        labelFn: function (r) {
          return r.ability;
        },
        displayFn: function (r) {
          return formatPercent(r.ability_share);
        },
        subFn: function (r) {
          return r.short_effect;
        },
      });

      var moves = chosenName
        ? moveRows
            .filter(function (r) {
              return r.pokemon_name === chosenName;
            })
            .sort(function (a, b) {
              return a.usage_rank - b.usage_rank;
            })
            .slice(0, 15)
        : [];
      if (moveTableSortable) moveTableSortable.setRows(moves);

      var concentration = profile ? concentrationByKey[profile.pokemon_key] : null;
      if (itemConcentrationEl) {
        itemConcentrationEl.innerHTML = concentration
          ? concentrationLabel(concentration.item_hhi, concentration.item_count)
          : "";
      }
      if (abilityConcentrationEl) {
        abilityConcentrationEl.innerHTML = concentration
          ? concentrationLabel(concentration.ability_hhi, concentration.ability_count)
          : "";
      }

      var cores = profile ? coreRowsFor(profile.pokemon_key) : [];
      renderGrid6xn(coreGrid, cores, {
        iconHtmlFn: function (r) {
          return r.is_triple ? teamCompositionHtml(r.pokemon_keys, ICON_SIZES.sm) : null;
        },
        keyFn: function (r) {
          return r.partner_pokemon_key;
        },
        labelFn: function (r) {
          return r.partner_pokemon_name;
        },
        displayFn: function (r) {
          return r.display;
        },
        subFn: function (r) {
          return r.sub;
        },
      });
    }

    select.addEventListener("change", function () {
      render(select.value);
    });
    if (coreMetricSelect) {
      coreMetricSelect.addEventListener("change", function () {
        render(select.value);
      });
    }
    if (coreSizeSelect) {
      coreSizeSelect.addEventListener("change", function () {
        render(select.value);
      });
    }
    if (sortedProfiles.length) select.value = sortedProfiles[0].pokemon_name;
    render(select.value);

    setupSubTabs(
      document.querySelectorAll('.tab-panel[data-panel="pokemon-profile"] .subtab-btn'),
      document.querySelectorAll('.tab-panel[data-panel="pokemon-profile"] .subtab-panel')
    );
  }

  function setupDetectedArchetypes() {
    var rows = (marts.detected_archetype_summary || [])
      .slice()
      .sort(function (a, b) {
        return a.archetype_rank - b.archetype_rank;
      });
    renderGrid6xn(document.getElementById("detected-archetype-grid"), rows, {
      iconHtmlFn: function (r) {
        return teamCompositionHtml(
          [r.pokemon_key_a, r.pokemon_key_b, r.pokemon_key_c].join("|"),
          ICON_SIZES.sm
        );
      },
      labelFn: function (r) {
        return [r.pokemon_name_a, r.pokemon_name_b, r.pokemon_name_c].join(" / ");
      },
      displayFn: function (r) {
        return formatPercent(r.team_share);
      },
      subFn: function (r) {
        var extension = r.top_extension_pokemon_name
          ? " · + " + r.top_extension_pokemon_name + " on " + formatPercent(r.top_extension_share)
          : "";
        return r.team_count + " teams · " + r.player_count + " players · " +
          r.stability_label + extension;
      },
      showLeader: false,
      typeFn: false,
    });
  }

  // Speed Tiers now reads pokemon_speed_tiers (backlog #16) rather than
  // pokemon_champions_profile's flat base speed: base speed alone doesn't
  // decide who moves first, the modified bracket does. The scenario select
  // chooses which of that mart's columns the tab ranks, filters and
  // displays; the Speed/Outruns filters apply to that same column, so the
  // whole tab stays in one unit at a time.
  //
  // The tier badge stays pinned to base_speed on purpose: SPEED_TIERS'
  // Blazing/Fast/Average/Slow thresholds (docs/design-system.md) are
  // calibrated to the 0-200 base-stat scale, so scoring a x3 scarf-plus-
  // Tailwind number against them would read "Blazing" for every row and
  // mean nothing.
  function setupSpeedTiers() {
    var speedRows = marts.pokemon_speed_tiers || [];
    var minEl = document.getElementById("speed-tiers-min");
    var maxEl = document.getElementById("speed-tiers-max");
    var benchmarkEl = document.getElementById("speed-tiers-benchmark");
    var benchmarkNote = document.getElementById("speed-tiers-benchmark-note");
    var scenarioSelect = document.getElementById("speed-tiers-scenario");
    var typeFilterEl = document.getElementById("speed-tiers-type-filter");
    var selectedTypes = {};
    var grid = document.getElementById("speed-grid");
    var table = document.getElementById("speed-tiers-table");

    function scenarioField() {
      return scenarioSelect ? scenarioSelect.value : "max_investment_speed";
    }

    var tableSortable = table
      ? makeSortableTable(
          table,
          [],
          function (r, i) {
            return (
              '<td><span class="badge badge-rank">#' + (i + 1) + "</span></td>" +
              "<td>" + pokemonCell(r.pokemon_key, r.pokemon_name) + "</td>" +
              "<td>" + r.base_speed + "</td>" +
              "<td>" + r.max_investment_speed + "</td>" +
              "<td>" + r.plus_one_speed + "</td>" +
              "<td>" + r.plus_two_speed + "</td>" +
              "<td>" + r.scarf_tailwind_speed + "</td>" +
              "<td>" + speedTierBadge(r.base_speed) + "</td>" +
              "<td>" + formatPercent(r.usage_share) + "</td>" +
              "<td>" + formatPercent(r.win_rate) + "</td>"
            );
          },
          { defaultKey: "max_investment_speed" }
        )
      : null;

    function filtered() {
      var field = scenarioField();
      return speedRows
        .filter(function (r) {
          if (!passesTypeFilter(selectedTypes, r.type_1, r.type_2)) return false;
          if (!inRange(r[field], minEl, maxEl)) return false;
          return true;
        })
        .slice()
        .sort(function (a, b) {
          return b[field] - a[field];
        });
    }

    function draw() {
      var field = scenarioField();
      var f = filtered();
      renderGrid6xn(grid, f.slice(0, 18), {
        keyFn: function (r) {
          return r.pokemon_key;
        },
        labelFn: function (r) {
          return r.pokemon_name;
        },
        displayFn: function (r) {
          return String(r[field]);
        },
        subFn: function (r) {
          return speedTier(r.base_speed).label + " · base " + r.base_speed;
        },
      });
      if (tableSortable) tableSortable.setRows(f);

      // "Outruns": how much of the filtered pool this scenario beats a
      // given opposing Speed number by -- the actual question a speed tier
      // gets consulted for, answered against the same column the tab is
      // currently showing.
      if (benchmarkNote) {
        var benchmark = benchmarkEl && benchmarkEl.value !== "" ? parseFloat(benchmarkEl.value) : null;
        benchmarkNote.hidden = benchmark === null || isNaN(benchmark);
        if (!benchmarkNote.hidden) {
          var faster = f.filter(function (r) {
            return r[field] > benchmark;
          });
          benchmarkNote.textContent =
            faster.length + " of " + f.length + " shown Pokémon (" +
            (f.length ? Math.round((faster.length / f.length) * 100) : 0) +
            "%) outrun " + benchmark + " in this scenario.";
        }
      }
    }

    renderTypeFilterChips(typeFilterEl, selectedTypes, draw);
    [minEl, maxEl, benchmarkEl].forEach(function (el) {
      if (!el) return;
      el.addEventListener("input", draw);
    });
    if (scenarioSelect) scenarioSelect.addEventListener("change", draw);
    draw();
  }

  // Players & Regions (backlog #7's two marts): "which regions favour
  // what" from pokemon_usage_by_country, and "does this player have a
  // signature Pokémon" from player_signature_pokemon. Both are
  // whole-history views, not per-event ones. The player list is already
  // floored at 2 recorded teams in pipelines/dashboard/data.py — see
  // MART_SLICERS there for why that floor is analytical, not cosmetic.
  function setupPlayers() {
    setupPlayerRegions();
    setupPlayerSignatures();
    setupSubTabs(
      document.querySelectorAll('.tab-panel[data-panel="players"] .subtab-btn'),
      document.querySelectorAll('.tab-panel[data-panel="players"] .subtab-panel')
    );
  }

  function setupPlayerRegions() {
    var countryRows = marts.pokemon_usage_by_country || [];
    var select = document.getElementById("players-country-filter");
    var note = document.getElementById("players-country-note");
    var grid = document.getElementById("players-country-grid");
    var table = document.getElementById("players-country-table");
    if (!select) return;

    // Countries ordered by how much recorded data each has, not
    // alphabetically -- the ordering convention's "rank by the most
    // relevant metric" applied to a non-Pokémon dimension, where the
    // relevant metric is sample size.
    var appearancesByCountry = {};
    countryRows.forEach(function (r) {
      appearancesByCountry[r.player_country] =
        (appearancesByCountry[r.player_country] || 0) + (r.usage_count || 0);
    });
    var countries = Object.keys(appearancesByCountry).sort(function (a, b) {
      return appearancesByCountry[b] - appearancesByCountry[a];
    });

    select.innerHTML = "";
    countries.forEach(function (country) {
      var opt = document.createElement("option");
      opt.value = country;
      var countryFlagGlyph = countryFlag(country);
      opt.textContent =
        (countryFlagGlyph ? countryFlagGlyph + " " : "") + country +
        " (" + appearancesByCountry[country].toLocaleString() + " picks)";
      select.appendChild(opt);
    });

    var tableSortable = table
      ? makeSortableTable(
          table,
          [],
          function (r) {
            return (
              '<td><span class="badge badge-rank">#' + r.country_usage_rank + "</span></td>" +
              "<td>" + pokemonCell(r.pokemon_key, r.pokemon_name) + "</td>" +
              "<td>" + formatPercent(r.usage_share) + "</td>"
            );
          },
          { defaultKey: "country_usage_rank", defaultDir: "asc" }
        )
      : null;

    function draw() {
      var country = select.value;
      var rows = countryRows
        .filter(function (r) {
          return r.player_country === country;
        })
        .sort(function (a, b) {
          return a.country_usage_rank - b.country_usage_rank;
        });
      if (note) {
        note.textContent = rows.length
          ? country + " has " + appearancesByCountry[country].toLocaleString() +
            " recorded roster picks across " + rows.length + " distinct Pokémon."
          : "No recorded picks for this country.";
      }
      renderGrid6xn(grid, rows.slice(0, 18), {
        keyFn: function (r) {
          return r.pokemon_key;
        },
        labelFn: function (r) {
          return r.pokemon_name;
        },
        displayFn: function (r) {
          return formatPercent(r.usage_share);
        },
      });
      if (tableSortable) tableSortable.setRows(rows.slice(0, 30));
    }

    select.addEventListener("change", draw);
    if (countries.length) select.value = countries[0];
    draw();
  }

  function setupPlayerSignatures() {
    var signatureRows = marts.player_signature_pokemon || [];
    var select = document.getElementById("players-player-filter");
    var note = document.getElementById("players-player-note");
    var grid = document.getElementById("players-signature-grid");
    var table = document.getElementById("players-specialists-table");
    if (!select) return;

    // player_usage_share is a Pokémon's share of the player's total roster
    // *slots*, which is structurally capped at 1/6: a Pokémon can appear at
    // most once per team, and every team contributes six slots. So a player
    // who fielded the same Pokémon on every single one of their teams still
    // reads as 16.7%, tying with everyone else who did — ranking or
    // headlining on that share alone is degenerate. team_share (in how many
    // of the player's own teams the Pokémon appeared) is the metric that
    // actually separates them, and reaches a real 100%.
    var byPlayer = {};
    signatureRows.forEach(function (r) {
      var row = {};
      for (var k in r) {
        if (Object.prototype.hasOwnProperty.call(r, k)) row[k] = r[k];
      }
      row.team_share = r.player_team_count ? r.usage_count / r.player_team_count : null;
      (byPlayer[r.player_id] || (byPlayer[r.player_id] = [])).push(row);
    });
    var players = Object.keys(byPlayer).sort(function (a, b) {
      return byPlayer[b][0].player_team_count - byPlayer[a][0].player_team_count;
    });

    select.innerHTML = "";
    players.forEach(function (playerId) {
      var first = byPlayer[playerId][0];
      var opt = document.createElement("option");
      opt.value = playerId;
      // textContent, not innerHTML — a <select> option can hold the flag
      // glyph itself but not countryCell()'s markup.
      var flag = countryFlag(first.player_country);
      opt.textContent =
        first.player_name +
        (first.player_country ? " (" + (flag ? flag + " " : "") + first.player_country + ")" : "") +
        " — " + first.player_team_count + " teams";
      select.appendChild(opt);
    });

    var specialists = players
      .map(function (playerId) {
        return byPlayer[playerId]
          .slice()
          .sort(function (a, b) {
            return a.player_pokemon_rank - b.player_pokemon_rank;
          })[0];
      })
      .sort(function (a, b) {
        // Team share first, then sample size: a Pokémon fielded on all
        // three of a player's teams is a stronger signature than one
        // fielded on both of two.
        return (
          (b.team_share || 0) - (a.team_share || 0) ||
          b.player_team_count - a.player_team_count
        );
      })
      .slice(0, 30);

    if (table) {
      makeSortableTable(
        table,
        specialists,
        function (r, i) {
          return (
            '<td><span class="badge badge-rank">#' + (i + 1) + "</span></td>" +
            "<td>" + escapeHtml(r.player_name) + "</td>" +
            "<td>" + countryCell(r.player_country) + "</td>" +
            "<td>" + pokemonCell(r.pokemon_key, r.pokemon_name) + "</td>" +
            "<td>" + formatPercent(r.team_share) + "</td>" +
            "<td>" + r.usage_count + " of " + r.player_team_count + "</td>"
          );
        },
        { defaultKey: "team_share" }
      );
    }

    function draw() {
      var rows = (byPlayer[select.value] || []).slice().sort(function (a, b) {
        return a.player_pokemon_rank - b.player_pokemon_rank;
      });
      if (note) {
        note.textContent = rows.length
          ? rows[0].player_name + " has " + rows[0].player_team_count +
            " recorded teams; their top " + rows.length + " picks are below."
          : "No recorded picks for this player.";
      }
      renderGrid6xn(grid, rows, {
        keyFn: function (r) {
          return r.pokemon_key;
        },
        labelFn: function (r) {
          return r.pokemon_name;
        },
        displayFn: function (r) {
          return r.usage_count + " of " + r.player_team_count + " teams";
        },
        subFn: function (r) {
          return formatPercent(r.player_usage_share) + " of their picks";
        },
      });
    }

    select.addEventListener("change", draw);
    if (players.length) select.value = players[0];
    draw();
  }

  // ---------- Data & Sources ----------

  // The provenance surface. Feeds: reports/validation/extraction_summary.json
  // (committed) for per-source health, the validation report's gates (baked
  // into the payload at build time, since the report itself is gitignored),
  // build-time asset coverage, and the roster_source_agreement mart.
  function setupDataSources() {
    var prov = DATA.provenance || {};

    var sourcesTable = document.getElementById("ds-sources-table");
    if (sourcesTable) {
      makeSortableTable(sourcesTable, prov.sources || [], function (row) {
        return (
          "<td>" + escapeHtml(row.source_name || "—") + "</td>" +
          '<td class="wrap-cell"><code>' + escapeHtml(row.endpoint || "—") + "</code></td>" +
          "<td>" + escapeHtml(row.availability || "—") + "</td>" +
          "<td>" + formatPercent(row.request_success_rate) + "</td>" +
          "<td>" + (row.rows_written == null ? "—" : row.rows_written) + "</td>" +
          "<td>" + formatPercent(row.required_field_null_rate) + "</td>" +
          "<td>" + escapeHtml((row.checked_at_utc || "—").slice(0, 10)) + "</td>"
        );
      });
    }

    var statusEl = document.getElementById("ds-gates-status");
    if (statusEl) {
      if (!prov.validation_available) {
        statusEl.textContent =
          "Gate results are not available in this build — reports/validation/" +
          "validation_report.json is regenerated by `make validate` and is not committed.";
      } else {
        var blocking = prov.release_blocking_findings || [];
        statusEl.textContent = blocking.length
          ? blocking.length + " release-blocking finding(s): " + blocking.join("; ")
          : "All release gates passing — no blocking findings. Validated " +
            String(prov.validation_generated_at_utc || "").slice(0, 10) + ".";
      }
    }

    var gatesTable = document.getElementById("ds-gates-table");
    if (gatesTable) {
      makeSortableTable(gatesTable, prov.gates || [], function (row) {
        var status = String(row.status || "").toLowerCase();
        var badgeClass = status === "pass" ? "badge-positive" : "badge-negative";
        return (
          "<td>" + escapeHtml(row.category || "—") + "</td>" +
          "<td>" + escapeHtml(row.name || "—") + "</td>" +
          '<td class="wrap-cell">' + escapeHtml(row.description || "—") + "</td>" +
          "<td>" + escapeHtml(row.threshold || "—") + "</td>" +
          "<td>" + (row.metric_value == null ? "—" : row.metric_value) + "</td>" +
          '<td><span class="badge ' + badgeClass + '">' + escapeHtml(row.status || "—") +
          "</span></td>"
        );
      });
    }

    renderGrid6xn(document.getElementById("ds-assets-grid"), prov.asset_coverage || [], {
      showRank: false,
      showLeader: false,
      labelFn: function (r) {
        return r.asset;
      },
      displayFn: function (r) {
        return r.referenced ? formatPercent(r.resolved / r.referenced) : "—";
      },
      subFn: function (r) {
        return r.resolved + " of " + r.referenced + " resolved";
      },
    });

    var agreementTable = document.getElementById("ds-agreement-table");
    if (agreementTable) {
      makeSortableTable(
        agreementTable,
        marts.roster_source_agreement || [],
        function (row) {
          return (
            "<td>" + escapeHtml(row.event_name || row.event_id || "—") + "</td>" +
            "<td>" + (row.covered_players == null ? "—" : row.covered_players) + "</td>" +
            "<td>" + formatPercent(row.exact_agreement_rate) + "</td>" +
            "<td>" + formatPercent(row.slot_agreement_rate) + "</td>"
          );
        },
        { defaultKey: "covered_players", defaultDir: "desc" }
      );
    }

    // Snapshot/release history is intentionally compact metadata: raw
    // snapshots stay in the scheduled-extraction cache, while published
    // manifests are already committed. This makes the waiting period for
    // real longitudinal analytics visible instead of silent.
    var history = prov.snapshot_history || {};
    var historyStatus = document.getElementById("ds-history-status");
    if (historyStatus) {
      if (!history.snapshot_count) {
        historyStatus.textContent =
          "No retained extraction snapshots are present in this dashboard build. " +
          "The scheduled workflow stores them in its cache; run a refresh before expecting snapshot-over-snapshot trends.";
      } else if (history.has_multiple_snapshots) {
        historyStatus.textContent =
          history.snapshot_count + " distinct snapshot dates retained from " +
          history.first_snapshot_date + " through " + history.latest_snapshot_date + ".";
      } else {
        historyStatus.textContent =
          "One snapshot date is currently available (" + history.latest_snapshot_date + "). " +
          "Snapshot-over-snapshot trends need at least two dates.";
      }
    }

    var snapshotTable = document.getElementById("ds-snapshot-table");
    if (snapshotTable) {
      makeSortableTable(snapshotTable, history.sources || [], function (row) {
        return (
          "<td>" + escapeHtml(row.source_name || row.staging_subdir || "—") + "</td>" +
          "<td>" + (row.snapshot_count == null ? "—" : row.snapshot_count) + "</td>" +
          "<td>" + escapeHtml(row.first_snapshot_date || "—") + "</td>" +
          "<td>" + escapeHtml(row.latest_snapshot_date || "—") + "</td>" +
          "<td>" + (row.history_days == null ? "—" : row.history_days) + "</td>"
        );
      }, { defaultKey: "snapshot_count", defaultDir: "desc" });
    }

    var releaseTable = document.getElementById("ds-release-table");
    if (releaseTable) {
      makeSortableTable(releaseTable, prov.release_history || [], function (row) {
        var failures = row.quality_failure_count || 0;
        return (
          "<td>" + escapeHtml(row.dataset_version || "—") + "</td>" +
          "<td>" + escapeHtml(String(row.published_at_utc || "—").slice(0, 10)) + "</td>" +
          "<td>" + (row.table_count == null ? "—" : row.table_count) + "</td>" +
          "<td>" + (row.image_count == null ? "—" : row.image_count) + "</td>" +
          '<td><span class="badge ' + (failures ? "badge-negative" : "badge-positive") + '">' +
          failures + "</span></td>" +
          "<td>" + (row.known_limitation_count == null ? "—" : row.known_limitation_count) + "</td>"
        );
      }, { defaultKey: "published_at_utc", defaultDir: "desc" });
    }

    var subtabs = document.querySelectorAll('[data-panel="data-sources"] .subtab-btn');
    var subpanels = document.querySelectorAll('[data-panel="data-sources"] .subtab-panel');
    setupSubTabs(subtabs, subpanels);
  }

  // ---------- Pokémon search combobox ----------
  // Type-ahead search with sprites, layered over an existing Pokémon
  // <select> (docs/upgrade-plan-2026q4.md, B4). The select stays the source
  // of truth: picking a result sets select.value and dispatches "change",
  // so every listener the tabs already attach keeps working, and options
  // are read from the select on each open, so it can be attached before a
  // tab fills it. Option values are either pokemon_keys or display names
  // depending on the tab; both resolve to a sprite.
  var keyByName = {};
  Object.keys(pokemonNames).forEach(function (key) {
    keyByName[pokemonNames[key]] = key;
  });
  var MAX_COMBO_RESULTS = 12;
  var comboCount = 0;

  function normalizeSearch(text) {
    return String(text || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-z0-9]/g, "");
  }

  function attachPokemonCombobox(select) {
    if (!select || select.dataset.combobox) return;
    select.dataset.combobox = "1";
    comboCount += 1;
    var listId = "combo-list-" + comboCount;
    var wrap = document.createElement("div");
    wrap.className = "combo";
    var input = document.createElement("input");
    input.type = "search";
    input.className = "combo-input";
    input.setAttribute("role", "combobox");
    input.setAttribute("aria-autocomplete", "list");
    input.setAttribute("aria-expanded", "false");
    input.setAttribute("aria-controls", listId);
    input.setAttribute("autocomplete", "off");
    input.placeholder = "Search Pokémon…";
    var list = document.createElement("ul");
    list.className = "combo-list";
    list.id = listId;
    list.setAttribute("role", "listbox");
    list.hidden = true;
    wrap.appendChild(input);
    wrap.appendChild(list);
    select.parentNode.insertBefore(wrap, select);
    select.classList.add("combo-source");
    select.setAttribute("tabindex", "-1");
    select.setAttribute("aria-hidden", "true");

    var results = [];
    var active = -1;

    function selectedText() {
      var opt = select.options[select.selectedIndex];
      return opt && opt.value ? opt.textContent : "";
    }
    function syncInput() {
      if (document.activeElement !== input) input.value = selectedText();
    }
    function options() {
      return Array.prototype.filter.call(select.options, function (o) { return o.value; });
    }
    function spriteFor(opt) {
      return spriteImg(sprites[opt.value] ? opt.value : keyByName[opt.textContent], ICON_SIZES.sm);
    }
    function close() {
      list.hidden = true;
      input.setAttribute("aria-expanded", "false");
      input.removeAttribute("aria-activedescendant");
      active = -1;
    }
    function highlight(index) {
      active = index;
      Array.prototype.forEach.call(list.children, function (li, i) {
        li.setAttribute("aria-selected", i === index ? "true" : "false");
      });
      if (index >= 0 && list.children[index]) {
        input.setAttribute("aria-activedescendant", list.children[index].id);
        list.children[index].scrollIntoView({ block: "nearest" });
      }
    }
    function render() {
      var query = normalizeSearch(input.value);
      var all = options();
      // Prefix matches first, then substring matches; select order (which
      // is usage order on most tabs) breaks ties.
      var prefix = [];
      var inner = [];
      // A match at the start of any word counts as a prefix match, so
      // "salam" ranks Mega Salamence (by usage) alongside Salamence.
      all.forEach(function (opt) {
        var words = String(opt.textContent).split(/[\s-]+/).map(normalizeSearch);
        var text = normalizeSearch(opt.textContent);
        var wordStart = words.some(function (w) { return w.indexOf(query) === 0; });
        if (!query || wordStart || text.indexOf(query) === 0) prefix.push(opt);
        else if (text.indexOf(query) > 0) inner.push(opt);
      });
      results = prefix.concat(inner).slice(0, MAX_COMBO_RESULTS);
      list.innerHTML = results.length
        ? results.map(function (opt, i) {
            return '<li role="option" id="' + listId + "-" + i + '" data-index="' + i + '">' +
              spriteFor(opt) + "<span>" + escapeHtml(opt.textContent) + "</span></li>";
          }).join("")
        : '<li class="combo-empty" aria-disabled="true">No Pokémon match “' + escapeHtml(input.value) + "”</li>";
      list.hidden = false;
      input.setAttribute("aria-expanded", "true");
      highlight(results.length ? 0 : -1);
    }
    function choose(index) {
      var opt = results[index];
      if (!opt) return;
      select.value = opt.value;
      select.dispatchEvent(new Event("change", { bubbles: true }));
      close();
      input.value = opt.textContent;
      input.blur();
    }

    input.addEventListener("focus", function () {
      input.select();
      render();
    });
    input.addEventListener("input", render);
    input.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        if (list.hidden) render();
        else highlight(Math.min(active + 1, results.length - 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        highlight(Math.max(active - 1, 0));
      } else if (e.key === "Enter") {
        if (!list.hidden && active >= 0) {
          e.preventDefault();
          choose(active);
        }
      } else if (e.key === "Escape") {
        close();
        input.value = selectedText();
        input.blur();
      }
    });
    // mousedown, not click: it fires before the input's blur closes the list.
    list.addEventListener("mousedown", function (e) {
      var li = e.target.closest("li[data-index]");
      if (!li) return;
      e.preventDefault();
      choose(Number(li.getAttribute("data-index")));
    });
    input.addEventListener("blur", function () {
      close();
      input.value = selectedText();
    });
    select.addEventListener("change", syncInput);
    // Tabs fill and preselect their selects after setup; poll the label
    // cheaply until the first real selection appears.
    var tries = 0;
    var timer = setInterval(function () {
      syncInput();
      tries += 1;
      if (selectedText() || tries > 40) clearInterval(timer);
    }, 250);
  }

  [
    "pokemon-profile-filter",
    "compare-a",
    "compare-b",
    "core-anchor",
    "matchup-attacker-select",
    "matchup-defender-select",
  ].forEach(function (id) {
    attachPokemonCombobox(document.getElementById(id));
  });

  // "/" jumps to the Pokémon search from anywhere on the page.
  document.addEventListener("keydown", function (e) {
    if (e.key !== "/" || e.metaKey || e.ctrlKey || e.altKey) return;
    var tag = (document.activeElement && document.activeElement.tagName) || "";
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
    e.preventDefault();
    var profileTab = document.querySelector('.tab-btn[data-tab="pokemon-profile"]');
    if (profileTab) profileTab.click();
    setTimeout(function () {
      var input = document.querySelector('[data-panel="pokemon-profile"] .combo-input');
      if (input) input.focus();
    }, 50);
  });

  // ---------- staleness banner ----------
  // Evaluated against the viewer's clock, not the build time: a site that
  // stops being rebuilt is exactly the case this exists for (the published
  // dashboard once sat on Reg M-A data for four months after M-C began).
  var STALE_AFTER_DAYS = 21;

  function regulationInForce(regulations, todayIso) {
    var inForce = null;
    (regulations || []).forEach(function (r) {
      if (r.start_date <= todayIso && todayIso < r.end_date) inForce = r;
    });
    return inForce;
  }

  function renderStalenessBanner() {
    var banner = document.getElementById("staleness-banner");
    var latest = (DATA.kpis || {}).latest_event_date;
    if (!banner || !latest) return;
    var todayIso = new Date().toISOString().slice(0, 10);
    var ageDays = Math.floor((Date.parse(todayIso) - Date.parse(latest)) / 86400000);
    var current = regulationInForce(DATA.regulations, todayIso);
    var messages = [];
    if (current && latest < current.start_date) {
      messages.push(
        current.regulation_name + " began " + current.start_date +
        ", but the newest tournament here is from " + latest +
        ". These figures describe an earlier regulation."
      );
    } else if (ageDays > STALE_AFTER_DAYS) {
      messages.push(
        "The newest tournament here is from " + latest + " (" + ageDays +
        " days ago). Results from more recent events are not included yet."
      );
    }
    if (!messages.length) return;
    banner.textContent = messages.join(" ");
    banner.hidden = false;
  }
  renderStalenessBanner();

  // Header Regulation selector and the per-scope KPI rows the template
  // renders (one .kpi-row[data-scope] per scope; only the selected shows).
  function setupRegulationSelector() {
    document.querySelectorAll(".kpi-row[data-scope]").forEach(function (row) {
      row.hidden = row.getAttribute("data-scope") !== regulationScope;
    });
    var select = document.getElementById("regulation-scope");
    if (!select) return;
    select.value = regulationScope;
    select.addEventListener("change", function () {
      var params = new URLSearchParams(window.location.search);
      params.set(SCOPE_PARAM, select.value);
      window.location.assign("?" + params.toString() + window.location.hash);
    });
  }
  setupRegulationSelector();

  // Overview reads only DATA.kpis, which is inlined — it renders with no
  // network round-trip, so the landing view is never waiting on data.json.
  registerTab("overview", setupOverview, { needsMarts: false });
  registerTab("data-sources", setupDataSources);
  registerTab("tiers", setupTiers);
  registerTab("usage", setupUsage);
  registerTab("pokemon-profile", setupPokemonProfile, { extraMarts: ["pokemon_team_core_triple_usage"] });
  registerTab("archetypes", setupDetectedArchetypes);
  registerTab("speed-tiers", setupSpeedTiers);
  registerTab("players", setupPlayers, { extraMarts: ["player_signature_pokemon"] });

  function initTab(tabId) {
    if (initialized[tabId] || !tabInitializers[tabId]) return;
    initialized[tabId] = true;
    if (!tabNeedsMarts[tabId]) {
      tabInitializers[tabId]();
      return;
    }
    ensureData(tabExtraMarts[tabId]).then(
      function () {
        tabInitializers[tabId]();
      },
      function (error) {
        // Un-mark so a retry (re-clicking the tab) can try the fetch again
        // rather than silently doing nothing forever.
        initialized[tabId] = false;
        renderDataLoadError(tabId, error);
      }
    );
  }

  setupTabs(function (tabId) {
    activeTabId = tabId;
    initTab(tabId);
  });

  // Shared namespace for matchup.js/teams.js (loaded right after this
  // file) — avoids duplicating DATA access or any of the helpers above.
  window.DashboardApp = {
    DATA: DATA,
    marts: marts,
    sprites: sprites,
    typeIcons: typeIcons,
    itemIcons: itemIcons,
    pokemonNames: pokemonNames,
    ICON_SIZES: ICON_SIZES,
    ALL_TYPES: ALL_TYPES,
    escapeHtml: escapeHtml,
    distinctSorted: distinctSorted,
    distinctSortedByMetric: distinctSortedByMetric,
    usageShareByKey: usageShareByKey,
    championsProfileByKey: championsProfileByKey,
    roleByKey: roleByKey,
    fillSelect: fillSelect,
    renderRows: renderRows,
    inRange: inRange,
    renderTypeFilterChips: renderTypeFilterChips,
    hasAnySelectedType: hasAnySelectedType,
    passesTypeFilter: passesTypeFilter,
    setupDrilldown: setupDrilldown,
    spriteImg: spriteImg,
    heroImg: heroImg,
    teamCompositionHtml: teamCompositionHtml,
    typeColor: typeColor,
    typeAccentGradient: typeAccentGradient,
    typeFnFromProfile: typeFnFromProfile,
    countryFlag: countryFlag,
    countryCell: countryCell,
    pokemonCell: pokemonCell,
    itemCell: itemCell,
    typeIconImg: typeIconImg,
    renderTypeBadgeRow: renderTypeBadgeRow,
    formatPercent: formatPercent,
    SPEED_TIERS: SPEED_TIERS,
    speedTier: speedTier,
    speedTierBadge: speedTierBadge,
    renderGrid6xn: renderGrid6xn,
    makeSortableTable: makeSortableTable,
    registerTab: registerTab,
    setupSubTabs: setupSubTabs,
    ensureData: ensureData,
    regulationScope: regulationScope,
    scopeLabel: scopeLabel,
    attachPokemonCombobox: attachPokemonCombobox,
    openProfile: openProfile,
  };
})();
