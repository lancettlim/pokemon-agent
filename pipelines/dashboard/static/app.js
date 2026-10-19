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
  // A3). The page shows exactly one scope, chosen once at load. Changing it
  // reloads the page (see setupRegulationSelector) rather than re-rendering
  // live tabs.
  //
  // The order (docs/upgrade-plan-2027q1.md, U3):
  //   1. ?reg= in the link.
  //   2. The viewer's last choice, but only if it was made while the same
  //      regulation was in force as today. A choice of M-C made in October
  //      must not keep someone on M-C after M-D starts.
  //   3. The regulation in force, once it has MIN_DEFAULT_SCOPE_TEAMS teams.
  //      Before that (the first week of a new set), the previous regulation,
  //      with a banner saying so (renderRolloverBanner).
  //   4. The newest regulation with data, then the build's default.
  var SCOPE_PARAM = "reg";
  var SCOPE_STORAGE_KEY = "dashboard-regulation";
  var ALL_SCOPE = "all";
  var MIN_DEFAULT_SCOPE_TEAMS = DATA.min_default_scope_teams || 300;
  var TODAY_ISO = new Date().toISOString().slice(0, 10);
  var rolloverNotice = null;

  function regulationsWithData() {
    var byScope = DATA.kpis_by_scope || {};
    return (DATA.regulations || []).filter(function (r) {
      return byScope[r.regulation_code];
    });
  }

  function readRememberedScope() {
    try {
      var saved = JSON.parse(localStorage.getItem(SCOPE_STORAGE_KEY) || "null");
      return saved && typeof saved === "object" && saved.code ? saved : null;
    } catch (e) {
      // A bare string from before U3 can't say when it was chosen, so it
      // is ignored rather than trusted.
      return null;
    }
  }

  function resolveRegulationScope() {
    var byScope = DATA.kpis_by_scope || {};
    var inForce = regulationInForce(DATA.regulations, TODAY_ISO);
    var requested = null;
    try {
      requested = new URLSearchParams(window.location.search).get(SCOPE_PARAM);
    } catch (e) {
      requested = null;
    }
    if (requested && byScope[requested]) return requested;
    // Hosts that don't pass the query string through (a Claude artifact
    // frame) fall back to the viewer's last choice in this browser.
    var remembered = readRememberedScope();
    if (
      remembered && byScope[remembered.code] && inForce &&
      remembered.in_force === inForce.regulation_code
    ) {
      return remembered.code;
    }
    var withData = regulationsWithData();
    if (inForce) {
      var kpis = byScope[inForce.regulation_code];
      if (kpis && (kpis.team_count || 0) >= MIN_DEFAULT_SCOPE_TEAMS) return inForce.regulation_code;
      var earlier = withData.filter(function (r) {
        return r.start_date < inForce.start_date;
      });
      if (earlier.length) {
        var shown = earlier[earlier.length - 1];
        rolloverNotice = {
          in_force: inForce,
          shown: shown,
          team_count: kpis ? kpis.team_count || 0 : 0,
          has_data: !!kpis,
        };
        return shown.regulation_code;
      }
      if (kpis) return inForce.regulation_code;
    }
    if (withData.length) return withData[withData.length - 1].regulation_code;
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

  // fillSelect for options whose value differs from their label (a
  // pokemon_key value with a display-name label). pairs: [{value, label}].
  function fillSelectPairs(select, pairs, allLabel) {
    select.innerHTML = "";
    if (allLabel) {
      var allOption = document.createElement("option");
      allOption.value = "";
      allOption.textContent = allLabel;
      select.appendChild(allOption);
    }
    pairs.forEach(function (pair) {
      var opt = document.createElement("option");
      opt.value = pair.value;
      opt.textContent = pair.label;
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

  // Multi-select type filter (docs/upgrade-plan-2027q1.md, U6): a "Type ▾"
  // button showing how many types are picked, opening an 18-type popover.
  // It replaced a row of 18 icon chips that took ~140px of every filter
  // panel. `selected` is a plain {type_name: true} map the caller owns; an
  // empty map means "no filter, show everything".
  var typePopoverCount = 0;
  function renderTypeFilterChips(container, selected, onChange) {
    if (!container) return;
    typePopoverCount += 1;
    var panelId = "type-popover-" + typePopoverCount;
    container.innerHTML = "";
    container.classList.add("type-popover");
    var toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "type-popover-btn";
    toggle.setAttribute("aria-haspopup", "true");
    toggle.setAttribute("aria-expanded", "false");
    toggle.setAttribute("aria-controls", panelId);
    var panel = document.createElement("div");
    panel.className = "type-popover-panel";
    panel.id = panelId;
    panel.hidden = true;
    panel.setAttribute("role", "group");
    panel.setAttribute("aria-label", "Filter by type");
    container.appendChild(toggle);
    container.appendChild(panel);

    function count() {
      return Object.keys(selected).filter(function (k) { return selected[k]; }).length;
    }
    function syncToggle() {
      var n = count();
      toggle.innerHTML = (n ? "Type · " + n + " selected" : "Any type") + ' <span aria-hidden="true">▾</span>';
      toggle.classList.toggle("is-active", n > 0);
      panel.classList.toggle("has-selection", n > 0);
    }
    function setOpen(open) {
      panel.hidden = !open;
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    }
    ALL_TYPES.forEach(function (type) {
      var chip = document.createElement("button");
      chip.type = "button";
      chip.className = "type-filter-chip";
      chip.setAttribute("aria-pressed", selected[type] ? "true" : "false");
      chip.setAttribute("aria-label", type);
      chip.title = type;
      chip.innerHTML = typeIconImg(type, 32) + '<span class="type-chip-name">' + escapeHtml(type) + "</span>";
      chip.addEventListener("click", function () {
        if (selected[type]) delete selected[type];
        else selected[type] = true;
        chip.setAttribute("aria-pressed", selected[type] ? "true" : "false");
        syncToggle();
        onChange();
      });
      panel.appendChild(chip);
    });
    var clear = document.createElement("button");
    clear.type = "button";
    clear.className = "btn btn-sm type-popover-clear";
    clear.textContent = "Clear";
    clear.addEventListener("click", function () {
      Object.keys(selected).forEach(function (k) { delete selected[k]; });
      panel.querySelectorAll(".type-filter-chip").forEach(function (chip) {
        chip.setAttribute("aria-pressed", "false");
      });
      syncToggle();
      onChange();
    });
    panel.appendChild(clear);

    toggle.addEventListener("click", function (e) {
      e.stopPropagation();
      setOpen(panel.hidden);
    });
    document.addEventListener("click", function (e) {
      if (!panel.hidden && !container.contains(e.target)) setOpen(false);
    });
    container.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && !panel.hidden) {
        setOpen(false);
        toggle.focus();
      }
    });
    syncToggle();
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

  // A Pokémon's sprite and name as one link to its profile (U1), so
  // middle-click and long-press work everywhere a Pokémon appears.
  function pokemonCell(pokemonKey, pokemonName, sizePx) {
    return (
      '<a class="cell-with-icon pokemon-link" href="' + pokemonHref(pokemonKey) + '">' +
      spriteImg(pokemonKey, sizePx) + "<span>" +
      escapeHtml(pokemonName || pokemonNames[pokemonKey] || pokemonKey) + "</span></a>"
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
            '<a class="team-comp-slot" href="' + pokemonHref(key) + '" title="' +
            escapeHtml(pokemonNames[key] || key) +
            '">' +
            (img || '<span class="team-comp-blank"></span>') +
            "</a>"
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

  // The committed type icons (static/icons/types/) are square, text-free
  // round emblems (Bulbagarden's Sword/Shield set, 128px), so one plain
  // <img> at any size is the whole icon. The name rides on alt/title.
  function typeIconImg(typeName, sizePx) {
    var src = typeIcons[typeName];
    if (!src) return "";
    var size = sizePx || 18;
    return (
      '<img class="type-icon" src="' + src + '" alt="' + escapeHtml(typeName) +
      '" title="' + escapeHtml(typeName) + '" width="' + size + '" height="' + size + '">'
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

  // ---------- tooltips ----------
  // Any element with data-tip shows that text in a bubble on hover, on
  // keyboard focus and on tap (a title attribute never shows on a phone).
  // tipHtml makes a small "i" button for long text that used to sit inline
  // (an item's effect), and the glossary terms use the same handler.
  function tipHtml(text, label) {
    if (!text) return "";
    return '<button type="button" class="tip" data-tip="' + escapeHtml(text) + '" aria-label="' +
      escapeHtml(label || "More about this") + ": " + escapeHtml(text) + '">i</button>';
  }

  var tipBubble = null;
  var tipOwner = null;
  function showTip(owner) {
    if (!tipBubble) {
      tipBubble = document.createElement("div");
      tipBubble.className = "tip-bubble";
      tipBubble.setAttribute("role", "tooltip");
      tipBubble.id = "tip-bubble";
      document.body.appendChild(tipBubble);
    }
    tipOwner = owner;
    tipBubble.textContent = owner.getAttribute("data-tip");
    tipBubble.hidden = false;
    owner.setAttribute("aria-describedby", "tip-bubble");
    var rect = owner.getBoundingClientRect();
    var width = Math.min(320, window.innerWidth - 24);
    tipBubble.style.maxWidth = width + "px";
    var left = Math.min(Math.max(12, rect.left + rect.width / 2 - width / 2), window.innerWidth - width - 12);
    tipBubble.style.left = left + window.scrollX + "px";
    var below = rect.bottom + 8;
    tipBubble.style.top = below + window.scrollY + "px";
  }
  function hideTip() {
    if (tipBubble) tipBubble.hidden = true;
    if (tipOwner) tipOwner.removeAttribute("aria-describedby");
    tipOwner = null;
  }
  document.addEventListener("mouseover", function (e) {
    var owner = e.target.closest && e.target.closest("[data-tip]");
    if (owner) showTip(owner);
    else if (tipOwner && !(e.target.closest && e.target.closest(".tip-bubble"))) hideTip();
  });
  document.addEventListener("focusin", function (e) {
    var owner = e.target.closest && e.target.closest("[data-tip]");
    if (owner) showTip(owner);
  });
  document.addEventListener("focusout", function (e) {
    if (tipOwner && e.target === tipOwner) hideTip();
  });
  document.addEventListener("click", function (e) {
    var owner = e.target.closest && e.target.closest("[data-tip]");
    if (owner) {
      if (tipOwner === owner && !tipBubble.hidden && owner.tagName !== "BUTTON") hideTip();
      else showTip(owner);
    } else if (tipOwner) {
      hideTip();
    }
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") hideTip();
  });
  window.addEventListener("scroll", hideTip, { passive: true });

  // ---------- Showdown export and copying ----------

  // A pokemon_key in Showdown's spelling: charizard-mega-y -> Charizard-Mega-Y.
  function showdownName(key) {
    return String(key).split("-").map(function (part) {
      return part.charAt(0).toUpperCase() + part.slice(1);
    }).join("-");
  }

  function splitMoves(moves) {
    if (Array.isArray(moves)) return moves.filter(Boolean);
    return String(moves || "").split("|").map(function (m) { return m.trim(); }).filter(Boolean);
  }

  // One Pokémon's set as Showdown text. set: {pokemon_key, item_name,
  // ability, nature, moves (array or pipe-delimited)}. No EV line: team
  // sheets don't publish spreads.
  function setToShowdown(set) {
    var lines = [showdownName(set.pokemon_key) + (set.item_name ? " @ " + set.item_name : "")];
    if (set.ability) lines.push("Ability: " + set.ability);
    lines.push("Level: 50");
    if (set.nature) lines.push(set.nature + " Nature");
    splitMoves(set.moves).forEach(function (move) {
      lines.push("- " + move);
    });
    return lines.join("\n");
  }

  function teamToShowdown(sets) {
    return sets.map(setToShowdown).join("\n\n");
  }

  // Copies text, confirming on the button. Some hosts refuse clipboard
  // writes; then the text appears selected next to the button so the
  // reader can copy it by hand.
  function copyWithFallback(button, text, doneLabel) {
    var label = button.textContent;
    function done() {
      button.textContent = doneLabel || "Copied";
      setTimeout(function () { button.textContent = label; }, 1500);
    }
    function fallback() {
      var box = button.parentNode.querySelector("textarea.copy-fallback");
      if (!box) {
        box = document.createElement("textarea");
        box.className = "copy-fallback";
        box.readOnly = true;
        button.parentNode.appendChild(box);
      }
      box.value = text;
      box.rows = Math.min(14, text.split("\n").length + 1);
      box.focus();
      box.select();
      button.textContent = "Select and copy";
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done, fallback);
    } else {
      fallback();
    }
  }

  // Any [data-copy] button copies the text stored for it in copyPayloads
  // (a click delegate, so views can render buttons as plain HTML).
  var copyPayloads = {};
  var copyCounter = 0;
  function copyButtonHtml(text, label, cls) {
    copyCounter += 1;
    var id = "copy-" + copyCounter;
    copyPayloads[id] = text;
    return '<button type="button" class="btn btn-sm' + (cls ? " " + cls : "") + '" data-copy="' + id + '">' +
      escapeHtml(label || "Copy for Showdown") + "</button>";
  }
  document.addEventListener("click", function (e) {
    var button = e.target.closest && e.target.closest("[data-copy]");
    if (!button) return;
    var text = copyPayloads[button.getAttribute("data-copy")];
    if (text != null) copyWithFallback(button, text);
  });

  // ---------- events and team cards (docs/upgrade-plan-2027q1.md, C1/C2/P5) ----------

  // "2027 Louisville Pokémon VGC Regional Championships" -> "Louisville
  // Regional". Mirrors data.py's short_event_name.
  var EVENT_NAME_NOISE = /^\d{4}\s+|\bPok[ée]mon\b|\bVGC\b|\bChampionships?\b|\bChampions\b/gi;
  function shortEventName(name) {
    if (!name) return "";
    var short = String(name).replace(EVENT_NAME_NOISE, " ").replace(/\s+/g, " ").trim();
    if (short.toLowerCase() === "world") return "World Championships";
    return short || name;
  }

  function ordinal(n) {
    if (n == null) return "—";
    var mod100 = n % 100;
    var suffix = mod100 >= 11 && mod100 <= 13 ? "th" : { 1: "st", 2: "nd", 3: "rd" }[n % 10] || "th";
    return n + suffix;
  }

  function recordText(wins, losses) {
    return wins == null || losses == null ? "" : wins + "–" + losses;
  }

  // Event tiers, most prestigious first, for "placement within tier"
  // ranking. Mirrors data.py's EVENT_TIER_ORDER.
  var EVENT_TIER_ORDER = ["Worlds", "International", "Special", "Regional"];
  function tierRank(tier) {
    var i = EVENT_TIER_ORDER.indexOf(tier);
    return i === -1 ? EVENT_TIER_ORDER.length : i;
  }

  function eventsById() {
    var out = {};
    (marts.tournament_event_summary || []).forEach(function (e) {
      out[e.event_id] = e;
    });
    return out;
  }

  // Events in the page's regulation (every event for "all").
  function eventsInScope() {
    return (marts.tournament_event_summary || []).filter(function (e) {
      return regulationScope === ALL_SCOPE || e.regulation_code === regulationScope;
    });
  }

  // team_id -> its sheet's slots, from the on-demand tournament_team_sheets
  // (or team_list_sheets for a Limitless list, keyed by team_list_id).
  var sheetIndexes = {};
  function sheetsFor(martName, idField, id) {
    if (!sheetIndexes[martName] || sheetIndexes[martName].size !== (marts[martName] || []).length) {
      var index = {};
      (marts[martName] || []).forEach(function (row) {
        (index[row[idField]] = index[row[idField]] || []).push(row);
      });
      Object.keys(index).forEach(function (k) {
        index[k].sort(function (a, b) { return (a.slot_number || 0) - (b.slot_number || 0); });
      });
      sheetIndexes[martName] = { size: (marts[martName] || []).length, index: index };
    }
    return sheetIndexes[martName].index[id] || null;
  }
  function teamSheet(teamId) {
    return sheetsFor("tournament_team_sheets", "team_id", teamId);
  }
  function teamListSheet(teamListId) {
    return sheetsFor("team_list_sheets", "team_list_id", teamListId);
  }

  function compactSetHtml(set) {
    return '<li><a href="' + pokemonHref(set.pokemon_key) + '">' +
      escapeHtml(pokemonNames[set.pokemon_key] || set.pokemon_key) + "</a>" +
      (set.item_name ? ' <span class="set-share">@ ' + escapeHtml(set.item_name) + "</span>" : "") +
      '<span class="team-card-set-detail">' +
      escapeHtml([set.ability, set.nature ? set.nature + " Nature" : null].filter(Boolean).join(" · ")) +
      (splitMoves(set.moves).length ? " · " + escapeHtml(splitMoves(set.moves).join(" / ")) : "") +
      "</span></li>";
  }

  // A real team as a card: placement and record as the headline (C2),
  // win rate secondary, who brought it where, its six Pokémon, and -- when
  // its sheet is known -- the sets, Copy for Showdown and Use this team.
  // team: {team_id | team_list_id, placement, record_wins, record_losses,
  // win_rate, player_id, player_name, player_country, event_id, event_name,
  // event_date, event_team_count, pokemon_keys, sets?}. opts.headline
  // overrides the placement line (a converged list has none);
  // opts.useHref is where "Use this team" goes (null for no button);
  // opts.hideEvent drops the event link on the event's own page.
  function teamCardHtml(team, opts) {
    opts = opts || {};
    var sets = team.sets || (team.team_id ? teamSheet(team.team_id) : null);
    var placement = team.placement != null
      ? '<span class="team-card-place" title="' + escapeHtml(
          team.event_team_count ? ordinal(team.placement) + " of " + team.event_team_count.toLocaleString() + " teams" : ""
        ) + '">' + ordinal(team.placement) + "</span>"
      : "";
    var record = recordText(team.record_wins, team.record_losses);
    var headline = opts.headline != null
      ? opts.headline
      : placement + (record ? ' <span class="team-card-record">' + record + "</span>" : "");
    var winRate = team.win_rate != null
      ? '<span class="team-card-wr">' + formatPercent(team.win_rate) + " win rate</span>"
      : "";
    var who = [];
    if (team.player_name) {
      who.push(
        (team.player_id ? '<a href="' + routeHash("player", [team.player_id]) + '">' : "<span>") +
        escapeHtml(team.player_name) + (team.player_id ? "</a>" : "</span>") +
        (team.player_country ? " " + countryCell(team.player_country) : "")
      );
    }
    if (team.event_id && !opts.hideEvent) {
      who.push('<a href="' + routeHash("event", [team.event_id]) + '" title="' + escapeHtml(team.event_name || "") + '">' +
        escapeHtml(shortEventName(team.event_name)) + "</a>" +
        (team.event_date ? ' <span class="set-share">' + escapeHtml(String(team.event_date).slice(0, 10)) + "</span>" : ""));
    }
    if (opts.meta) who.push(opts.meta);
    var actions = [];
    if (sets && sets.length) actions.push(copyButtonHtml(teamToShowdown(sets), "Copy for Showdown"));
    if (opts.useHref !== null) {
      var useHref = opts.useHref || (team.team_id ? routeHash("team-builder", ["team", team.team_id]) : null);
      if (useHref) actions.push('<a class="btn btn-sm" href="' + useHref + '">Use this team</a>');
    }
    // A pre-rendered PNG of the team (render-share-cards, C4), when the
    // build has one: the newest event's top 8.
    var card = team.team_id && ((DATA.share_cards || {}).teams || {})[team.team_id];
    if (card) {
      actions.push('<a class="btn btn-sm" href="' + escapeHtml(card) + '" download>Download card</a>');
    }
    return '<article class="team-card">' +
      '<header class="team-card-head"><span class="team-card-headline">' + headline + "</span>" + winRate + "</header>" +
      (who.length ? '<div class="team-card-who">' + who.join(" · ") + "</div>" : "") +
      teamCompositionHtml(team.pokemon_keys, 40) +
      (sets && sets.length
        ? '<details class="team-card-sets"><summary>Sets</summary><ul>' + sets.map(compactSetHtml).join("") + "</ul></details>"
        : "") +
      (actions.length ? '<div class="team-card-actions">' + actions.join(" ") + "</div>" : "") +
      "</article>";
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
      // A Pokémon-keyed tile is a link to that Pokémon (U1) unless it holds
      // its own links (a team composition) or opts.hrefFn says otherwise.
      var href = opts.hrefFn
        ? opts.hrefFn(row)
        : opts.keyFn && iconHtml == null && opts.link !== false
          ? pokemonHref(opts.keyFn(row))
          : null;
      var tile = document.createElement(href ? "a" : "div");
      if (href) tile.href = href;
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

  // ---------- shared data table (docs/upgrade-plan-2027q1.md, U5) ----------
  // The one component for ranked data: a sortable table with a sticky
  // header, sprite + name cells, right-aligned numbers, inline share bars
  // and rows that open the Pokémon (or event, or player) they describe. On
  // phones it collapses to two-line rows: the "main" columns on the first
  // line, the rest as labelled details on the second, with a Sort select in
  // place of the header.
  //
  // opts.columns: [{
  //   key,            the row field the column shows and sorts by
  //   label,          header text
  //   type,           "rank" | "pokemon" | "share" | "percent" | "int" | "text"
  //   render(row),    custom cell HTML (overrides type)
  //   title(row),     hover/tap text for the cell (a percentage's denominator)
  //   main: true,     on the first line of a phone row
  //   sortable,       defaults to true for numeric types
  //   sortKey,        sort by another field than key
  //   numeric: true,  right-aligned (default for numeric types)
  //   hideOnPhone,    dropped from the phone layout
  // }]
  // opts.sort: {key, dir}; opts.rowHref(row): where a row click goes;
  // opts.limit: rows shown before "Show all"; opts.empty: empty-state text;
  // opts.caption: accessible table caption.
  var NUMERIC_TYPES = { rank: 1, share: 1, percent: 1, int: 1 };
  // Table rows use a 32px sprite: dense enough for ~20 rows a screen.
  var TABLE_SPRITE_PX = 32;
  var tableCount = 0;

  function cellHtml(col, row, maxByKey) {
    if (col.render) return col.render(row);
    var value = row[col.key];
    switch (col.type) {
      case "rank":
        return value == null ? "—" : '<span class="badge badge-rank">#' + value + "</span>";
      case "pokemon":
        return pokemonCell(row[col.keyField || "pokemon_key"], value, TABLE_SPRITE_PX);
      case "share": {
        if (value == null) return "—";
        var max = maxByKey[col.key] || 1;
        return '<span class="share-cell"><span class="share-bar" style="width:' +
          Math.max(2, Math.round((value / max) * 100)) + '%"></span><span class="share-value">' +
          formatPercent(value) + "</span></span>";
      }
      case "percent":
        return formatPercent(value);
      case "int":
        return value == null ? "—" : Number(value).toLocaleString();
      default:
        return value == null || value === "" ? "—" : escapeHtml(value);
    }
  }

  function createDataTable(container, opts) {
    if (!container) return { setRows: function () {} };
    tableCount += 1;
    var tableId = "data-table-" + tableCount;
    var columns = opts.columns;
    var state = {
      key: opts.sort ? opts.sort.key : null,
      dir: opts.sort ? opts.sort.dir || "desc" : "desc",
      expanded: false,
    };
    var rows = [];

    function sortField(col) {
      return col.sortKey || col.key;
    }
    function isSortable(col) {
      return col.sortable !== undefined ? col.sortable : !!NUMERIC_TYPES[col.type];
    }
    function isNumeric(col) {
      return col.numeric !== undefined ? col.numeric : !!NUMERIC_TYPES[col.type];
    }

    container.classList.add("data-table-host");
    container.innerHTML =
      '<div class="data-table-tools">' +
      '<label class="data-table-sort">Sort <select aria-controls="' + tableId + '"></select></label>' +
      '<button type="button" class="btn btn-sm data-table-cite">Copy with citation</button></div>' +
      '<table class="data-table" id="' + tableId + '">' +
      (opts.caption ? '<caption class="visually-hidden">' + escapeHtml(opts.caption) + "</caption>" : "") +
      "<thead><tr></tr></thead><tbody></tbody></table>" +
      '<p class="data-table-empty empty-state" hidden></p>' +
      '<button type="button" class="btn btn-sm data-table-more" hidden></button>';
    var table = container.querySelector("table");
    var headRow = table.querySelector("thead tr");
    var tbody = table.querySelector("tbody");
    var sortSelect = container.querySelector(".data-table-sort select");
    var emptyEl = container.querySelector(".data-table-empty");
    var moreBtn = container.querySelector(".data-table-more");

    columns.forEach(function (col) {
      var th = document.createElement("th");
      th.scope = "col";
      th.textContent = col.label;
      if (isNumeric(col)) th.classList.add("num");
      if (isSortable(col)) {
        th.classList.add("sortable");
        th.tabIndex = 0;
        th.setAttribute("data-sort-key", sortField(col));
        var go = function () {
          var key = sortField(col);
          if (state.key === key) state.dir = state.dir === "desc" ? "asc" : "desc";
          else {
            state.key = key;
            state.dir = col.type === "rank" ? "asc" : "desc";
          }
          render();
        };
        th.addEventListener("click", go);
        th.addEventListener("keydown", function (e) {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            go();
          }
        });
        var opt = document.createElement("option");
        opt.value = sortField(col);
        opt.textContent = col.label;
        sortSelect.appendChild(opt);
      }
      headRow.appendChild(th);
    });
    if (!sortSelect.options.length) container.querySelector(".data-table-sort").hidden = true;
    sortSelect.addEventListener("change", function () {
      state.key = sortSelect.value;
      var col = columns.filter(function (c) { return sortField(c) === state.key; })[0];
      state.dir = col && col.type === "rank" ? "asc" : "desc";
      render();
    });

    function sorted() {
      if (!state.key) return rows;
      return rows.slice().sort(function (a, b) {
        var av = a[state.key];
        var bv = b[state.key];
        var aMissing = av === null || av === undefined || av === "";
        var bMissing = bv === null || bv === undefined || bv === "";
        if (aMissing || bMissing) return aMissing === bMissing ? 0 : aMissing ? 1 : -1;
        var cmp = typeof av === "string" ? av.localeCompare(bv) : av < bv ? -1 : av > bv ? 1 : 0;
        return state.dir === "asc" ? cmp : -cmp;
      });
    }

    function render() {
      var ordered = sorted();
      var limit = opts.limit && !state.expanded ? opts.limit : Infinity;
      var shown = ordered.slice(0, limit);
      var maxByKey = {};
      columns.forEach(function (col) {
        if (col.type === "share") {
          maxByKey[col.key] = rows.reduce(function (m, r) { return Math.max(m, r[col.key] || 0); }, 0);
        }
      });
      tbody.innerHTML = shown.map(function (row) {
        var href = opts.rowHref ? opts.rowHref(row) : null;
        return "<tr" + (href ? ' class="row-link" data-href="' + escapeHtml(href) + '"' : "") + ">" +
          columns.map(function (col) {
            var cls = [];
            if (isNumeric(col)) cls.push("num");
            cls.push(col.main ? "col-main" : "col-detail");
            if (col.hideOnPhone) cls.push("col-phone-hide");
            var title = col.title ? col.title(row) : "";
            return '<td class="' + cls.join(" ") + '" data-label="' + escapeHtml(col.label) + '"' +
              (title ? ' title="' + escapeHtml(title) + '"' : "") + ">" + cellHtml(col, row, maxByKey) + "</td>";
          }).join("") + "</tr>";
      }).join("");
      table.hidden = !rows.length;
      emptyEl.hidden = !!rows.length;
      emptyEl.textContent = opts.empty || "No rows match.";
      moreBtn.hidden = ordered.length <= limit;
      moreBtn.textContent = "Show all " + ordered.length.toLocaleString();
      headRow.querySelectorAll("th").forEach(function (th) {
        var active = th.getAttribute("data-sort-key") === state.key;
        if (active) th.setAttribute("aria-sort", state.dir === "asc" ? "ascending" : "descending");
        else th.removeAttribute("aria-sort");
      });
      if (state.key) sortSelect.value = state.key;
    }

    moreBtn.addEventListener("click", function () {
      state.expanded = true;
      render();
    });
    // "Copy with citation" (C4): every row in the current order as
    // tab-separated text, then a source line a reader can paste under it.
    var citeBtn = container.querySelector(".data-table-cite");
    citeBtn.addEventListener("click", function () {
      var scratch = document.createElement("div");
      function text(html) {
        scratch.innerHTML = html;
        return scratch.textContent.replace(/\s+/g, " ").trim();
      }
      var maxByKey = {};
      var cols = columns.filter(function (c) { return c.label; });
      var lines = [cols.map(function (c) { return c.label; }).join("\t")];
      sorted().forEach(function (row) {
        lines.push(cols.map(function (c) { return text(cellHtml(c, row, maxByKey)); }).join("\t"));
      });
      lines.push("");
      lines.push(citationLine(opts.citation ? opts.citation() : null));
      copyWithFallback(citeBtn, lines.join("\n"));
    });
    // A row click anywhere but a link or button opens what the row is about.
    tbody.addEventListener("click", function (e) {
      if (e.target.closest("a, button, select, input")) return;
      var tr = e.target.closest("tr[data-href]");
      if (tr) navigate(tr.getAttribute("data-href"));
    });

    return {
      setRows: function (newRows) {
        rows = newRows || [];
        state.expanded = false;
        render();
      },
      rows: function () {
        return sorted();
      },
      setSort: function (key, dir) {
        state.key = key;
        state.dir = dir || "desc";
        render();
      },
    };
  }

  // "Source: Pokémon Champions Data Platform, dataset 0.3.0, Reg M-C,
  // n = 3,770 teams, <url>". sample overrides the n clause (an event
  // page's own team count).
  function citationLine(sample) {
    var parts = ["Source: Pokémon Champions Data Platform"];
    var version = DATA.provenance && DATA.provenance.dataset_version;
    if (version) parts.push("dataset " + version);
    parts.push(shortRegulation(regulationScope));
    var teams = DATA.kpis && DATA.kpis.team_count;
    parts.push(sample || (teams ? "n = " + Number(teams).toLocaleString() + " teams" : null));
    parts.push(window.location.href);
    return parts.filter(Boolean).join(", ");
  }

  function pokemonRowHref(row) {
    return row.pokemon_key ? pokemonHref(row.pokemon_key) : null;
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
  // opts.onRoute(route): called once the tab is ready, and again on every
  // later route change while it is in view (Back/Forward, a pasted link),
  // so the tab can show the Pokémon/event/sub-tab the route names.
  var tabExtraMarts = {};
  var tabReady = {};
  function registerTab(tabId, initFn, opts) {
    tabInitializers[tabId] = initFn;
    tabNeedsMarts[tabId] = !(opts && opts.needsMarts === false);
    tabExtraMarts[tabId] = (opts && opts.extraMarts) || [];
    if (opts && opts.onRoute) routeHandlers[tabId] = opts.onRoute;
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

  // The shard files omit display-name columns (build.py's
  // _write_mart_shards); each row gets them back from the inline
  // pokemon_key -> name map, so every view can keep reading
  // row.pokemon_name.
  function restoreNames(rows) {
    var pairs = (DATA.mart_files && DATA.mart_files.name_fields) || [];
    (rows || []).forEach(function (row) {
      pairs.forEach(function (pair) {
        var key = row[pair[0]];
        if (key && row[pair[1]] === undefined) row[pair[1]] = pokemonNames[key] || key;
      });
    });
    return rows;
  }

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
            marts[name] = restoreNames(applyRegulationScope(loaded[name]));
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

  // ---------- scroll cues (docs/upgrade-plan-2027q1.md, U7) ----------
  // A horizontally scrolling row of tabs fades at whichever edge has more
  // to show, so "Speed Ti…" reads as cut off on purpose. centerInRow
  // brings the active tab into view without scrolling the page.
  function updateScrollCues(row) {
    var max = row.scrollWidth - row.clientWidth;
    row.classList.toggle("can-scroll-left", row.scrollLeft > 2);
    row.classList.toggle("can-scroll-right", max > 2 && row.scrollLeft < max - 2);
  }
  function setupScrollCues(row) {
    if (!row || row.dataset.scrollCues) return;
    row.dataset.scrollCues = "1";
    row.classList.add("scroll-cues");
    row.addEventListener("scroll", function () { updateScrollCues(row); }, { passive: true });
    if (window.ResizeObserver) new ResizeObserver(function () { updateScrollCues(row); }).observe(row);
    updateScrollCues(row);
  }
  function centerInRow(row, item) {
    if (!row || !item || row.scrollWidth <= row.clientWidth) return;
    row.scrollLeft = item.offsetLeft - row.offsetLeft - (row.clientWidth - item.offsetWidth) / 2;
    updateScrollCues(row);
  }

  // ---------- routing (docs/upgrade-plan-2027q1.md, U1) ----------
  // The whole view state lives in the hash, so Back, Forward and pasted
  // links all route:
  //   #/pokemon/garchomp/moves   #/compare/garchomp,kingambit
  //   #/matchup/rillaboom/sneasler   #/teams/top?tier=regional
  //   #/event/<event_id>   #/player/<player_id>   #/builder/<team>
  // ?reg= in the query string stays the regulation. A route is
  // {tab, args, query}: the tab is the panel shown, args are its path
  // segments after the head. Navigating between views pushes a history
  // entry; a tab refining its own view (a filter, a sub-tab) replaces the
  // current one, so Back always means "the previous view".
  var ROUTE_HEADS = {
    overview: "overview",
    tiers: "tiers",
    usage: "usage",
    "speed-tiers": "speed",
    "pokemon-profile": "pokemon",
    compare: "compare",
    matchup: "matchup",
    "top-teams": "teams",
    events: "events",
    event: "event",
    archetypes: "archetypes",
    "core-explorer": "cores",
    players: "players",
    player: "player",
    "team-builder": "builder",
    "data-sources": "data",
  };
  var TAB_BY_HEAD = {};
  Object.keys(ROUTE_HEADS).forEach(function (tab) {
    TAB_BY_HEAD[ROUTE_HEADS[tab]] = tab;
  });
  var DEFAULT_TAB = "overview";

  // Commas and dots are part of route segments (#/compare/a,b and the
  // Builder's #/builder/rillaboom.1,...), so they stay readable.
  function encodeSegment(value) {
    return encodeURIComponent(String(value)).replace(/%2C/gi, ",");
  }

  function parseRoute(hash) {
    var raw = String(hash || "").replace(/^#/, "");
    var query = {};
    var queryIndex = raw.indexOf("?");
    if (queryIndex >= 0) {
      new URLSearchParams(raw.slice(queryIndex + 1)).forEach(function (value, key) {
        query[key] = value;
      });
      raw = raw.slice(0, queryIndex);
    }
    if (raw.charAt(0) !== "/") {
      // Pre-routing links were bare tab ids (#usage); they still open.
      if (raw && ROUTE_HEADS[raw]) return { tab: raw, args: [], query: query, legacy: true };
      return null;
    }
    var segments = raw.slice(1).split("/").filter(Boolean).map(function (part) {
      try {
        return decodeURIComponent(part);
      } catch (e) {
        return part;
      }
    });
    var tab = TAB_BY_HEAD[segments[0]];
    if (!tab) return null;
    return { tab: tab, args: segments.slice(1), query: query };
  }

  function routeHash(tab, args, query) {
    var parts = (args || []).filter(function (a) {
      return a !== null && a !== undefined && a !== "";
    });
    var hash = "#/" + (ROUTE_HEADS[tab] || ROUTE_HEADS[DEFAULT_TAB]) +
      (parts.length ? "/" + parts.map(encodeSegment).join("/") : "");
    var keys = Object.keys(query || {}).filter(function (k) {
      return query[k] !== null && query[k] !== undefined && query[k] !== "";
    });
    if (keys.length) {
      hash += "?" + keys.map(function (k) {
        return encodeURIComponent(k) + "=" + encodeSegment(query[k]);
      }).join("&");
    }
    return hash;
  }

  function pokemonHref(key) {
    return routeHash("pokemon-profile", [key]);
  }

  // Before routing, Compare and the Core Explorer kept their state in the
  // query string (?tab=compare&a=..&b=..). Those links are rewritten to
  // their routes once, at load; ?reg= is kept.
  function legacyQueryRoute() {
    var params;
    try {
      params = new URLSearchParams(window.location.search);
    } catch (e) {
      return null;
    }
    var tab = params.get("tab");
    if (!tab) return null;
    var route = null;
    if (tab === "compare") {
      route = routeHash("compare", [params.get("a") && params.get("b") ? params.get("a") + "," + params.get("b") : ""]);
    } else if (tab === "core-explorer") {
      route = routeHash("core-explorer", [params.get("core"), params.get("size")]);
    } else if (ROUTE_HEADS[tab]) {
      route = routeHash(tab, []);
    }
    ["tab", "a", "b", "core", "size"].forEach(function (k) {
      params.delete(k);
    });
    var search = params.toString();
    return { search: search ? "?" + search : "", hash: route };
  }

  // History URLs are always absolute paths: a fragment-only URL ("#/x")
  // would silently keep whatever query string the page has.
  function urlWithHash(search, hash) {
    return window.location.pathname + search + hash;
  }

  var currentRoute = { tab: DEFAULT_TAB, args: [], query: {} };
  var appliedHash = null;
  var lastHashByTab = {};
  var routeHandlers = {};

  function sameArgs(a, b) {
    return JSON.stringify(a || []) === JSON.stringify(b || []);
  }

  // Five sections, each owning a row of view buttons (.tab-btn[data-section]).
  // Only the active section's row shows, and only when it has more than one
  // view; the KPI strip shows on Meta only. Detail views (an event, a
  // player) carry their section on the panel itself (data-section).
  var tabButtons = Array.prototype.slice.call(document.querySelectorAll(".tab-btn"));
  var tabPanels = Array.prototype.slice.call(document.querySelectorAll(".tab-panel"));
  var sectionButtons = Array.prototype.slice.call(document.querySelectorAll(".section-btn"));
  var lastTabBySection = {};
  var onTabActivate = null;

  function sectionOf(tabId) {
    var panel = tabPanels.filter(function (p) { return p.getAttribute("data-panel") === tabId; })[0];
    if (panel && panel.getAttribute("data-section")) return panel.getAttribute("data-section");
    var btn = tabButtons.filter(function (b) { return b.getAttribute("data-tab") === tabId; })[0];
    return btn ? btn.getAttribute("data-section") : null;
  }

  // A detail view highlights the list it belongs to in the tab row.
  var DETAIL_PARENT = { event: "events", player: "players" };

  function showTab(tabId) {
    var section = sectionOf(tabId);
    var hasButton = tabButtons.some(function (b) { return b.getAttribute("data-tab") === tabId; });
    if (hasButton) lastTabBySection[section] = tabId;
    var highlighted = DETAIL_PARENT[tabId] || tabId;
    var inSection = 0;
    var tabRow = document.querySelector(".tabs");
    tabButtons.forEach(function (btn) {
      var mine = btn.getAttribute("data-section") === section;
      btn.hidden = !mine;
      if (mine) inSection += 1;
      btn.setAttribute("aria-selected", btn.getAttribute("data-tab") === highlighted ? "true" : "false");
    });
    if (tabRow) {
      tabRow.hidden = inSection < 2;
      setupScrollCues(tabRow);
      centerInRow(tabRow, tabRow.querySelector('.tab-btn[aria-selected="true"]'));
    }
    sectionButtons.forEach(function (btn) {
      if (btn.getAttribute("data-section") === section) btn.setAttribute("aria-current", "true");
      else btn.removeAttribute("aria-current");
    });
    var kpiStrip = document.getElementById("kpi-strip");
    if (kpiStrip) kpiStrip.hidden = tabId !== "overview";
    tabPanels.forEach(function (panel) {
      panel.hidden = panel.getAttribute("data-panel") !== tabId;
    });
    if (onTabActivate) onTabActivate(tabId);
  }

  // Hands a route to its tab once the tab is initialised (initTab), and
  // again on every later route change while it stays in view.
  function dispatchRoute(route) {
    var handler = routeHandlers[route.tab];
    if (!handler || !initialized[route.tab] || !tabReady[route.tab]) return;
    handler(route);
  }

  var DEFAULT_TITLE = document.title;
  function applyRoute(route) {
    var tabChanged = route.tab !== currentRoute.tab;
    // An event or player page titles the tab after itself; everything else
    // keeps the site's title.
    if (tabChanged) document.title = DEFAULT_TITLE;
    currentRoute = route;
    lastHashByTab[route.tab] = routeHash(route.tab, route.args, route.query);
    showTab(route.tab);
    if (!tabChanged || initialized[route.tab]) dispatchRoute(route);
  }

  function onLocationChange() {
    if (window.location.hash === appliedHash) return;
    var route = parseRoute(window.location.hash);
    if (!route || route.legacy) {
      // An unknown hash opens the default view; a legacy #tab link becomes
      // its route, replacing (not adding) the history entry.
      route = route || { tab: DEFAULT_TAB, args: [], query: {} };
      var canonical = routeHash(route.tab, route.args, route.query);
      if (window.location.hash && window.history.replaceState) {
        window.history.replaceState(window.history.state, "", urlWithHash(window.location.search, canonical));
      }
    }
    appliedHash = window.location.hash;
    applyRoute(route);
  }

  // Navigates to a view (a history entry). opts.replace rewrites the current
  // entry instead.
  function navigate(hash, opts) {
    opts = opts || {};
    if (hash === window.location.hash) {
      onLocationChange();
      return;
    }
    var url = urlWithHash(window.location.search, hash);
    if (window.history && window.history.pushState) {
      if (opts.replace) window.history.replaceState(null, "", url);
      else window.history.pushState(null, "", url);
      onLocationChange();
    } else {
      window.location.hash = hash;
    }
    if (!opts.keepScroll && !opts.replace) window.scrollTo(0, 0);
  }

  // For a tab recording a change it has already rendered (a new Pokémon
  // picked, a filter): updates the address bar without re-dispatching.
  // opts.push adds a history entry, for changes a reader would expect Back
  // to undo (another Pokémon); filters and sub-tabs replace.
  function setRoute(tab, args, query, opts) {
    opts = opts || {};
    if (tab !== currentRoute.tab) return;
    var hash = routeHash(tab, args, query);
    lastHashByTab[tab] = hash;
    if (hash === window.location.hash) return;
    currentRoute = parseRoute(hash);
    appliedHash = hash;
    var url = urlWithHash(window.location.search, hash);
    if (window.history && window.history.pushState) {
      if (opts.push) window.history.pushState(null, "", url);
      else window.history.replaceState(null, "", url);
    }
  }

  function openTab(tabId) {
    navigate(lastHashByTab[tabId] || routeHash(tabId, []));
  }

  function setupNavigation(onActivate) {
    onTabActivate = onActivate;
    tabButtons.forEach(function (btn) {
      btn.addEventListener("click", function () {
        openTab(btn.getAttribute("data-tab"));
      });
    });
    sectionButtons.forEach(function (btn) {
      btn.addEventListener("click", function () {
        var section = btn.getAttribute("data-section");
        var first = tabButtons.filter(function (b) { return b.getAttribute("data-section") === section; })[0];
        var target = lastTabBySection[section] || (first && first.getAttribute("data-tab"));
        if (target) openTab(target);
      });
    });
    window.addEventListener("popstate", onLocationChange);
    window.addEventListener("hashchange", onLocationChange);
    var legacy = legacyQueryRoute();
    if (legacy && window.history.replaceState) {
      window.history.replaceState(null, "", urlWithHash(legacy.search, legacy.hash || window.location.hash));
    }
    onLocationChange();
  }

  // ---------- sub-tabs ----------

  // A pill row nested inside one top-level tab/section (docs/design-
  // system.md's "Sub-tabs" component) — e.g. Usage's Usage-leaders/Win-
  // rate-leaders, Pokémon Profile's Items/Ability/Moves/Team Cores.
  // buttons/panels are NodeLists or arrays; buttons carry data-subtab,
  // panels carry data-subpanel, matched by that id. Defaults to the first
  // button.
  //
  // opts.route = {tab, argIndex} puts the open sub-tab in the URL: each
  // button's data-route (or its data-subtab id) becomes route arg
  // argIndex, a click replaces the current history entry, and the returned
  // object's fromRoute(route) opens whichever sub-tab a route names.
  function setupSubTabs(buttons, panels, onActivate, opts) {
    buttons = Array.prototype.slice.call(buttons);
    panels = Array.prototype.slice.call(panels);
    opts = opts || {};
    var activeId = null;
    function slugOf(btn) {
      return btn.getAttribute("data-route") || btn.getAttribute("data-subtab");
    }
    var row = buttons.length ? buttons[0].parentNode : null;
    setupScrollCues(row);
    function activate(id) {
      activeId = id;
      buttons.forEach(function (btn) {
        var on = btn.getAttribute("data-subtab") === id;
        btn.setAttribute("aria-selected", on ? "true" : "false");
        if (on) centerInRow(row, btn);
      });
      panels.forEach(function (panel) {
        panel.hidden = panel.getAttribute("data-subpanel") !== id;
      });
      if (onActivate) onActivate(id);
    }
    function idForSlug(slug) {
      var match = buttons.filter(function (btn) { return slugOf(btn) === slug; })[0];
      return match ? match.getAttribute("data-subtab") : null;
    }
    buttons.forEach(function (btn) {
      btn.addEventListener("click", function () {
        activate(btn.getAttribute("data-subtab"));
        if (opts.route && currentRoute.tab === opts.route.tab) {
          var args = currentRoute.args.slice();
          while (args.length < opts.route.argIndex) args.push(opts.route.fill ? opts.route.fill(args.length) : "");
          args[opts.route.argIndex] = btn === buttons[0] ? "" : slugOf(btn);
          setRoute(opts.route.tab, args, currentRoute.query);
        }
      });
    });
    var initial = opts.route && currentRoute.tab === opts.route.tab
      ? idForSlug(currentRoute.args[opts.route.argIndex])
      : null;
    if (buttons.length) activate(initial || buttons[0].getAttribute("data-subtab"));
    return {
      fromRoute: function (route) {
        var id = idForSlug(route.args[opts.route.argIndex]) ||
          (buttons[0] && buttons[0].getAttribute("data-subtab"));
        if (id && id !== activeId) activate(id);
      },
      active: function () {
        return activeId;
      },
    };
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
      return '<li><a class="mover-link" href="' + pokemonHref(r.pokemon_key) + '">' +
        spriteImg(r.pokemon_key, ICON_SIZES.sm) +
        '<span class="mover-name">' + escapeHtml(r.pokemon_name || r.pokemon_key) + "</span>" +
        '<span class="mover-share">' + formatPercent(r.usage_share) + "</span>" + deltaHtml + "</a></li>";
    }).join("") + "</ol>";
  }

  // "What changed" (docs/upgrade-plan-2026q4.md, A4/B5): the selected
  // regulation against a baseline, summarised server-side. The baseline is
  // labelled with its own event and team count (2027q1 C4, finding 6), and
  // there are two: the previous regulation (pokemon_regulation_movers) or
  // the selected regulation's own early vs recent events
  // (summarize_event_window_movers). When the previous regulation is thin
  // (fewer than two events, or under 300 teams -- M-B is one Worlds field)
  // the panel opens on early vs recent. When either side has too few teams
  // for a delta to mean much, it shows the sample sizes and arrivals only.
  var moversMode = null;
  function plural(n, word) {
    return Number(n || 0).toLocaleString() + " " + word + (n === 1 ? "" : "s");
  }

  function renderMovers() {
    var panel = document.getElementById("movers-panel");
    var movers = DATA.kpis && DATA.kpis.movers;
    var windowed = DATA.kpis && DATA.kpis.window_movers;
    if (!panel || (!movers && !windowed)) return;
    if (!moversMode) moversMode = (movers && movers.baseline_thin && windowed) || !movers ? "window" : "previous";
    var summary = moversMode === "window" ? windowed : movers;
    var toggle = "";
    if (movers && windowed) {
      toggle = '<div class="movers-toggle" role="group" aria-label="Compare with">' +
        '<button type="button" data-movers="previous" aria-pressed="' + (moversMode === "previous") + '">vs ' +
        escapeHtml(shortRegulation(movers.previous_regulation_code)) + " (" + plural(movers.previous_event_count, "event") +
        ", " + plural(movers.previous_team_count, "team") + ")</button>" +
        '<button type="button" data-movers="window" aria-pressed="' + (moversMode === "window") + '">Early vs recent events</button>' +
        "</div>";
    }
    var title;
    var sample;
    if (moversMode === "window") {
      title = "What changed within " + shortRegulation(regulationScope);
      sample = windowed.recent_events.join(", ") + " (" + plural(windowed.team_count, "team") + ") against " +
        windowed.early_events.join(", ") + " (" + plural(windowed.previous_team_count, "team") + ").";
    } else {
      title = "What changed in " + shortRegulation(movers.regulation_code) + " vs " +
        shortRegulation(movers.previous_regulation_code);
      sample = plural(movers.team_count, "team") + " from " + plural(movers.event_count, "event") + " this regulation · " +
        plural(movers.previous_team_count, "team") + " from " + plural(movers.previous_event_count, "event") + " in the previous one.";
      if (movers.baseline_thin) sample += " A thin baseline: compare early and recent events instead.";
    }
    sample += " Shares are of roster slots.";
    var columns = [];
    if (summary.reliable) {
      columns.push('<div><h4>Rising</h4>' + moverListHtml(summary.risers, true) + "</div>");
      columns.push('<div><h4>Falling</h4>' + moverListHtml(summary.fallers, true) + "</div>");
    } else {
      sample += " Too few teams on one side to compare shares reliably, so only new arrivals are shown.";
    }
    if (moversMode === "previous") {
      columns.push('<div><h4>New this regulation</h4>' + moverListHtml(movers.new_arrivals, false) + "</div>");
    }
    var shareCard = ((DATA.share_cards || {}).whats_changed || {})[regulationScope];
    panel.innerHTML = '<div class="movers-head"><h3>' + escapeHtml(title) + "</h3>" + toggle + "</div>" +
      '<p class="sub">' + escapeHtml(sample) + '</p><div class="mover-columns">' + columns.join("") + "</div>" +
      (shareCard
        ? '<p class="movers-share"><a class="btn btn-sm" href="' + escapeHtml(shareCard) +
          '" download>Download summary card</a></p>'
        : "");
    panel.hidden = false;
  }

  document.addEventListener("click", function (e) {
    var btn = e.target.closest && e.target.closest("[data-movers]");
    if (!btn) return;
    moversMode = btn.getAttribute("data-movers");
    renderMovers();
  });

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
        return '<a class="tier-chip" href="' + pokemonHref(r.pokemon_key) + '">' +
          spriteImg(r.pokemon_key, ICON_SIZES.sm) + escapeHtml(r.pokemon_name) +
          ' <span class="set-share">' + formatPercent(r.usage_share) + "</span>" + wrHtml + "</a>";
      }).join("");
      return '<div class="tier-row"><div class="tier-label tier-' + tier.id + '">' + tier.label +
        "<small>" + members.length + "</small></div>" +
        '<div class="tier-members">' + chips + "</div></div>";
    }).join("") || '<p class="empty-state">No usage data for this regulation yet.</p>';
  }

  // Opens a Pokémon's profile from any view (a history entry, like a link).
  function openProfile(pokemonKey) {
    navigate(pokemonHref(pokemonKey));
  }

  // Usage (docs/upgrade-plan-2027q1.md, U5): four ranked tables on the
  // shared component, replacing the 18-tile grids that showed 12 Pokémon
  // per screen. Every percentage carries its denominator on hover/tap.
  function slotsTitle(count, total) {
    if (count == null || !total) return "";
    return Number(count).toLocaleString() + " of " + Number(total).toLocaleString() + " roster slots";
  }

  function recordTitle(row) {
    if (row.total_wins == null) return row.record_count != null ? row.record_count + " teams with a record" : "";
    return row.total_wins.toLocaleString() + "–" + row.total_losses.toLocaleString() + " across " +
      (row.record_count || 0).toLocaleString() + " teams";
  }

  function setupUsage() {
    var usageRows = marts.pokemon_usage_summary || [];
    var profileByKey = championsProfileByKey();
    var roles = roleByKey();
    var winByKey = {};
    (marts.pokemon_win_rate_summary || []).forEach(function (r) {
      winByKey[r.pokemon_key] = r;
    });

    var tierSelect = document.getElementById("usage-tier-filter");
    var roleSelect = document.getElementById("usage-role-filter");
    var typeFilterEl = document.getElementById("usage-type-filter");
    var shareMin = document.getElementById("usage-share-min");
    var shareMax = document.getElementById("usage-share-max");
    var speedMin = document.getElementById("usage-speed-min");
    var speedMax = document.getElementById("usage-speed-max");
    var noteEl = document.getElementById("usage-table-note");
    var selectedTypes = {};

    // Rows are already scoped to the page's regulation (the header's
    // Regulation selector; see applyRegulationScope), so this tab only
    // filters by tier, type, role and ranges.
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

    var slotTotals = {};
    usageRows.forEach(function (r) {
      var tier = r.event_tier || "";
      slotTotals[tier] = (slotTotals[tier] || 0) + (r.usage_count || 0);
    });

    var usageTable = createDataTable(document.getElementById("usage-table"), {
      caption: "Usage by Pokémon",
      sort: { key: "usage_rank", dir: "asc" },
      limit: 50,
      rowHref: pokemonRowHref,
      empty: "No Pokémon match these filters.",
      columns: [
        { key: "usage_rank", label: "#", type: "rank", main: true },
        { key: "pokemon_name", label: "Pokémon", type: "pokemon", main: true, sortable: true },
        {
          key: "types",
          label: "Type",
          sortable: false,
          hideOnPhone: true,
          render: function (r) {
            return [r.type_1, r.type_2].filter(Boolean).map(function (t) {
              return typeIconImg(t, 20);
            }).join(" ");
          },
        },
        {
          key: "usage_share",
          label: "Usage",
          type: "share",
          main: true,
          title: function (r) { return slotsTitle(r.usage_count, slotTotals[r.event_tier || ""]); },
        },
        {
          key: "win_rate",
          label: "Win rate",
          type: "percent",
          title: recordTitle,
        },
        { key: "usage_count", label: "Teams", type: "int" },
      ],
    });

    // Event window (C4): usage over a run of events -- the last N, or every
    // event since a given one -- from pokemon_event_usage_vs_regulation,
    // with each Pokémon's change against the events before the window.
    // Shares are of roster slots, like everything else here. Tier doesn't
    // apply inside a window, so the tier filter is disabled while one is on.
    var windowSelect = document.getElementById("usage-window-filter");
    var windowEvents = eventsInScope().slice().sort(function (a, b) {
      return String(b.event_date).localeCompare(String(a.event_date)) || String(a.event_id).localeCompare(String(b.event_id));
    });
    if (windowSelect) {
      [1, 2, 3].forEach(function (n) {
        if (windowEvents.length > n) {
          var opt = document.createElement("option");
          opt.value = "last-" + n;
          opt.textContent = n === 1 ? "Latest event" : "Last " + n + " events";
          windowSelect.appendChild(opt);
        }
      });
      windowEvents.slice(1).forEach(function (e) {
        var opt = document.createElement("option");
        opt.value = "since-" + e.event_id;
        opt.textContent = "Since " + shortEventName(e.event_name);
        windowSelect.appendChild(opt);
      });
      windowSelect.disabled = windowEvents.length < 2;
    }

    function windowEventIds(value) {
      if (!value) return null;
      if (value.indexOf("last-") === 0) {
        return windowEvents.slice(0, parseInt(value.slice(5), 10)).map(function (e) { return e.event_id; });
      }
      if (value.indexOf("since-") === 0) {
        var id = value.slice(6);
        var index = windowEvents.map(function (e) { return e.event_id; }).indexOf(id);
        return index === -1 ? null : windowEvents.slice(0, index + 1).map(function (e) { return e.event_id; });
      }
      return null;
    }

    var windowTable = createDataTable(document.getElementById("usage-window-table"), {
      caption: "Usage in the selected events",
      sort: { key: "usage_share", dir: "desc" },
      limit: 50,
      rowHref: pokemonRowHref,
      empty: "No Pokémon match these filters.",
      columns: [
        { key: "pokemon_name", label: "Pokémon", type: "pokemon", main: true, sortable: true },
        {
          key: "usage_share",
          label: "Usage",
          type: "share",
          main: true,
          title: function (r) { return slotsTitle(r.usage_count, r.slot_total); },
        },
        {
          key: "usage_share_delta",
          label: "vs before",
          numeric: true,
          sortable: true,
          render: function (r) {
            if (r.usage_share_delta == null) return "—";
            var pts = r.usage_share_delta * 100;
            var cls = pts > 0.05 ? "badge-positive" : pts < -0.05 ? "badge-negative" : "badge-rank";
            return '<span class="badge ' + cls + '">' + (pts > 0 ? "+" : "") + pts.toFixed(1) + " pts</span>";
          },
          title: function (r) {
            return r.previous_usage_share != null ? "Was " + formatPercent(r.previous_usage_share) + " before" : "";
          },
        },
        { key: "win_rate", label: "Win rate", type: "percent", title: recordTitle },
        { key: "usage_count", label: "Teams", type: "int" },
      ],
    });

    function windowRows(ids) {
      var inWindow = {};
      ids.forEach(function (id) { inWindow[id] = true; });
      var current = {};
      var before = {};
      var slots = { now: {}, before: {} };
      var inScope = {};
      windowEvents.forEach(function (e) { inScope[e.event_id] = true; });
      (marts.pokemon_event_usage_vs_regulation || []).forEach(function (r) {
        if (!inScope[r.event_id]) return;
        var side = inWindow[r.event_id] ? "now" : "before";
        var bucket = side === "now" ? current : before;
        var b = bucket[r.pokemon_key] || (bucket[r.pokemon_key] = { usage: 0, wins: 0, losses: 0 });
        b.usage += r.usage_count || 0;
        b.wins += r.total_wins || 0;
        b.losses += r.total_losses || 0;
        slots[side][r.event_id] = r.event_slot_count || 0;
      });
      function total(map) {
        return Object.keys(map).reduce(function (sum, k) { return sum + map[k]; }, 0);
      }
      var nowSlots = total(slots.now);
      var beforeSlots = total(slots.before);
      return Object.keys(current).filter(function (key) {
        return current[key].usage > 0;
      }).map(function (key) {
        var c = current[key];
        var b = before[key];
        var share = nowSlots ? c.usage / nowSlots : null;
        var prev = beforeSlots ? (b ? b.usage : 0) / beforeSlots : null;
        return {
          pokemon_key: key,
          pokemon_name: pokemonNames[key] || key,
          usage_share: share,
          usage_count: c.usage,
          slot_total: nowSlots,
          previous_usage_share: prev,
          usage_share_delta: prev == null ? null : share - prev,
          win_rate: c.wins + c.losses ? c.wins / (c.wins + c.losses) : null,
          total_wins: c.wins,
          total_losses: c.losses,
          record_count: null,
        };
      });
    }

    function drawUsage() {
      var tier = tierSelect ? tierSelect.value : "";
      var ids = windowEventIds(windowSelect ? windowSelect.value : "");
      var windowed = !!ids;
      document.getElementById("usage-table").hidden = windowed;
      document.getElementById("usage-window-table").hidden = !windowed;
      if (tierSelect) tierSelect.disabled = windowed;
      if (windowed) {
        var wrows = windowRows(ids).filter(function (r) {
          var profile = profileByKey[r.pokemon_key];
          if (!passesTypeFilter(selectedTypes, profile && profile.type_1, profile && profile.type_2)) return false;
          if (roleSelect && roleSelect.value && roles[r.pokemon_key] !== roleSelect.value) return false;
          if (!inRange(r.usage_share != null ? r.usage_share * 100 : null, shareMin, shareMax)) return false;
          if (!inRange(profile ? profile.speed : null, speedMin, speedMax)) return false;
          return true;
        });
        windowTable.setRows(wrows);
        if (noteEl) {
          var names = windowEvents.filter(function (e) { return ids.indexOf(e.event_id) !== -1; })
            .map(function (e) { return shortEventName(e.event_name); });
          var teams = windowEvents.filter(function (e) { return ids.indexOf(e.event_id) !== -1; })
            .reduce(function (sum, e) { return sum + (e.team_count || 0); }, 0);
          noteEl.textContent = "Usage at " + names.join(", ") + " (" + teams.toLocaleString() +
            " teams), against the regulation's earlier events" +
            (ids.length === windowEvents.length ? " (none: this is every event)" : "") + ".";
        }
        return;
      }
      var rows = filteredRows(tier).map(function (r) {
        var profile = profileByKey[r.pokemon_key] || {};
        var win = winByKey[r.pokemon_key] || {};
        return {
          pokemon_key: r.pokemon_key,
          pokemon_name: r.pokemon_name,
          event_tier: r.event_tier,
          usage_rank: r.usage_rank,
          usage_share: r.usage_share,
          usage_count: r.usage_count,
          type_1: profile.type_1,
          type_2: profile.type_2,
          win_rate: win.win_rate,
          total_wins: win.total_wins,
          total_losses: win.total_losses,
          record_count: win.record_count,
        };
      });
      usageTable.setRows(rows);
      if (noteEl) {
        noteEl.textContent = rows.length.toLocaleString() + " Pokémon · shares are of " +
          (slotTotals[tier] || 0).toLocaleString() + " roster slots in " + shortRegulation(regulationScope) +
          (tier ? " " + tier + " events" : "") + ".";
      }
    }

    if (tierSelect) {
      var tiers = distinctSorted(usageRows, "event_tier");
      fillSelect(tierSelect, tiers, "Overall");
      tierSelect.addEventListener("change", drawUsage);
    }
    if (windowSelect) {
      windowSelect.addEventListener("change", function () {
        drawUsage();
        var route = currentRoute;
        var query = {};
        Object.keys(route.query || {}).forEach(function (k) { query[k] = route.query[k]; });
        query.window = windowSelect.value;
        setRoute("usage", route.args, query);
      });
    }
    usageWindowRoute = function (route) {
      var value = (route.query && route.query.window) || "";
      if (windowSelect && windowSelect.value !== value &&
        (!value || windowSelect.querySelector('option[value="' + value + '"]'))) {
        windowSelect.value = value;
        drawUsage();
      }
    };
    renderTypeFilterChips(typeFilterEl, selectedTypes, drawUsage);
    [roleSelect, shareMin, shareMax, speedMin, speedMax].forEach(function (el) {
      if (!el) return;
      el.addEventListener("input", drawUsage);
      el.addEventListener("change", drawUsage);
    });
    drawUsage();

    var winRows = marts.pokemon_win_rate_summary || [];
    var minRecordSelect = document.getElementById("win-rate-min-record-count-filter");
    var winTable = createDataTable(document.getElementById("win-rate-table"), {
      caption: "Win rate by Pokémon",
      sort: { key: "wilson_lower_bound", dir: "desc" },
      limit: 50,
      rowHref: pokemonRowHref,
      columns: [
        { key: "rank", label: "#", type: "rank", main: true },
        { key: "pokemon_name", label: "Pokémon", type: "pokemon", main: true, sortable: true },
        { key: "win_rate", label: "Win rate", type: "percent", main: true, title: recordTitle },
        {
          key: "wilson_lower_bound",
          label: "Wilson bound",
          type: "percent",
          title: function () { return "95% confidence: the true win rate is at least this"; },
        },
        { key: "record_count", label: "Teams", type: "int" },
      ],
    });
    function updateWinRows() {
      var floor = minRecordSelect ? parseInt(minRecordSelect.value, 10) : 20;
      var filtered = winRows
        .filter(function (r) {
          return r.record_count >= floor;
        })
        .slice()
        .sort(function (a, b) {
          return (b.wilson_lower_bound || 0) - (a.wilson_lower_bound || 0);
        })
        .map(function (r, i) {
          var row = {};
          for (var k in r) if (Object.prototype.hasOwnProperty.call(r, k)) row[k] = r[k];
          row.rank = i + 1;
          return row;
        });
      winTable.setRows(filtered);
    }
    if (minRecordSelect) minRecordSelect.addEventListener("change", updateWinRows);
    updateWinRows();

    setupUsageSuccess();
    setupUsageTrends();

    usageSubTabs = setupSubTabs(
      document.querySelectorAll('.tab-panel[data-panel="usage"] .subtab-btn'),
      document.querySelectorAll('.tab-panel[data-panel="usage"] .subtab-panel'),
      null,
      { route: { tab: "usage", argIndex: 0 } }
    );
  }
  var usageSubTabs = null;
  var usageWindowRoute = function () {};

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
    var usageByKey = {};
    (marts.pokemon_usage_summary || []).forEach(function (r) {
      if (!r.event_tier) usageByKey[r.pokemon_key] = r;
    });

    var table = createDataTable(document.getElementById("usage-success-table"), {
      caption: "Placement-weighted usage",
      sort: { key: "rank", dir: "asc" },
      limit: 50,
      rowHref: pokemonRowHref,
      columns: [
        { key: "rank", label: "#", type: "rank", main: true },
        { key: "pokemon_name", label: "Pokémon", type: "pokemon", main: true, sortable: true },
        { key: "weighted_usage_share", label: "Weighted", type: "share", main: true },
        {
          key: "top_cut_usage_share",
          label: "Top cut",
          type: "percent",
          title: function (r) {
            return r.top_cut_usage_count != null ? r.top_cut_usage_count + " top-8 roster slots" : "";
          },
        },
        { key: "usage_share", label: "Raw usage", type: "percent" },
        {
          key: "rank_movement",
          label: "Movement",
          numeric: true,
          sortable: true,
          render: rankMovementBadgeHtml,
        },
      ],
    });

    function draw() {
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
            rank: i + 1,
            pokemon_key: r.pokemon_key,
            pokemon_name: r.pokemon_name,
            weighted_usage_share: r[shareField],
            top_cut_usage_share: r.top_cut_usage_share,
            top_cut_usage_count: r.top_cut_usage_count,
            usage_share: usage ? usage.usage_share : null,
            rank_movement: usage ? usage.usage_rank - (i + 1) : null,
          };
        });
      table.setRows(ranked);
    }

    if (metricSelect) metricSelect.addEventListener("change", draw);
    draw();
  }

  // Usage-by-tournament-date subtab (backlog #6's data half; #29/#30's UI
  // half): a date filter (#30) plus a "vs. the previous tournament date"
  // delta per Pokémon (#29's dependency-free stand-in for a line chart).
  // event_date is a tournament date, not an extraction snapshot_date, so
  // this trend is real even with only one snapshot's worth of staging
  // history.
  function trendDeltaLabel(row) {
    if (row.is_new) return "NEW";
    if (row.usage_share_delta === null || row.usage_share_delta === undefined) return "";
    var points = row.usage_share_delta * 100;
    var arrow = points > 0 ? "▲" : points < 0 ? "▼" : "";
    var sign = points > 0 ? "+" : "";
    return arrow + " " + sign + points.toFixed(1) + " pts";
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
    var dates = distinctSorted(trendRows, "event_date").slice().reverse(); // most recent first

    var table = createDataTable(document.getElementById("usage-trend-table"), {
      caption: "Usage by tournament date",
      sort: { key: "usage_rank", dir: "asc" },
      limit: 50,
      rowHref: pokemonRowHref,
      columns: [
        { key: "usage_rank", label: "#", type: "rank", main: true },
        { key: "pokemon_name", label: "Pokémon", type: "pokemon", main: true, sortable: true },
        { key: "usage_share", label: "Usage", type: "share", main: true },
        {
          key: "usage_share_delta",
          label: "Change",
          numeric: true,
          sortable: true,
          render: trendDeltaBadgeHtml,
          title: function (r) {
            return r.previous_usage_share != null ? "Was " + formatPercent(r.previous_usage_share) : "";
          },
        },
      ],
    });

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
            previous_usage_share: prev ? prev.usage_share : null,
            usage_share_delta: prev ? r.usage_share - prev.usage_share : null,
            is_new: !!prevDate && !prev,
          };
        });
    }

    function drawTrend() {
      table.setRows(rowsForDate(dateSelect ? dateSelect.value : dates[0]));
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
    var profileKeys = {};
    sortedProfiles.forEach(function (r) {
      profileKeys[r.pokemon_key] = true;
    });
    // Option values are pokemon_keys, the same id the route carries
    // (#/pokemon/<key>); the label is the display name.
    fillSelectPairs(
      select,
      sortedProfiles.map(function (r) {
        return { value: r.pokemon_key, label: r.pokemon_name };
      }),
      "Select a Pokémon…"
    );

    var statsEl = document.getElementById("pokemon-profile-stats");
    // Items, abilities and moves on the shared table (U5); effect text sits
    // behind an "i" tooltip instead of making every row ~270px tall.
    function nameWithTip(name, effect, iconHtml) {
      return '<span class="cell-with-icon">' + (iconHtml || "") + "<span>" + escapeHtml(name) + "</span>" +
        tipHtml(effect, name) + "</span>";
    }
    function shareOfTitle(r) {
      return r.total ? r.usage_count.toLocaleString() + " of " + r.total.toLocaleString() + " team sheets" : "";
    }
    var itemTable = createDataTable(document.getElementById("profile-item-table"), {
      caption: "Held items",
      sort: { key: "usage_rank", dir: "asc" },
      limit: 10,
      empty: "No recorded held items.",
      columns: [
        { key: "usage_rank", label: "#", type: "rank", main: true },
        {
          key: "item_name",
          label: "Item",
          main: true,
          sortable: true,
          render: function (r) {
            var src = itemIcons[r.item_name];
            return nameWithTip(r.item_name, r.short_effect, src ? '<img class="cell-icon" src="' + src + '" alt="">' : "");
          },
        },
        { key: "item_share", label: "Share", type: "share", main: true, title: shareOfTitle },
        { key: "usage_count", label: "Teams", type: "int" },
      ],
    });
    var abilityTable = createDataTable(document.getElementById("profile-ability-table"), {
      caption: "Abilities",
      sort: { key: "usage_rank", dir: "asc" },
      empty: "No recorded abilities.",
      columns: [
        { key: "usage_rank", label: "#", type: "rank", main: true },
        {
          key: "ability",
          label: "Ability",
          main: true,
          sortable: true,
          render: function (r) { return nameWithTip(r.ability, r.short_effect); },
        },
        { key: "ability_share", label: "Share", type: "share", main: true, title: shareOfTitle },
        { key: "usage_count", label: "Teams", type: "int" },
      ],
    });
    var moveTable = createDataTable(document.getElementById("profile-move-table"), {
      caption: "Moves",
      sort: { key: "usage_rank", dir: "asc" },
      limit: 15,
      empty: "No recorded moves.",
      columns: [
        { key: "usage_rank", label: "#", type: "rank", main: true },
        {
          key: "move_name",
          label: "Move",
          main: true,
          sortable: true,
          render: function (r) { return nameWithTip(r.move_name, r.short_effect, typeIconImg(r.move_type, 18)); },
        },
        {
          key: "move_share",
          label: "Usage",
          type: "share",
          main: true,
          title: function (r) { return r.usage_count != null ? r.usage_count.toLocaleString() + " team sheets" : ""; },
        },
        { key: "category", label: "Category", sortable: true },
        { key: "power", label: "Power", type: "int" },
        {
          key: "accuracy",
          label: "Acc.",
          type: "int",
          render: function (r) { return r.accuracy != null ? r.accuracy + "%" : "—"; },
        },
        { key: "pp", label: "PP", type: "int", hideOnPhone: true },
        { key: "priority", label: "Priority", type: "int", hideOnPhone: true },
      ],
    });
    var coreMetricSelect = document.getElementById("profile-team-core-metric");
    var coreSizeSelect = document.getElementById("profile-team-core-size");
    var itemConcentrationEl = document.getElementById("profile-item-concentration");
    var abilityConcentrationEl = document.getElementById("profile-ability-concentration");

    // Teammates (docs/upgrade-plan-2027q1.md, P2): one table per core size.
    // A pair row joins raw co-occurrence (pokemon_team_core_usage) with
    // synergy lift (pokemon_team_synergy, floored at 5 shared teams in
    // data.py), and "Ranked by" picks the sort. Lift is a multiplier
    // ("×1.8"), the one headline number that isn't a percentage: there is
    // no whole for it to be a share of.
    function liftCell(value) {
      return value == null ? "—" : "×" + Number(value).toFixed(1);
    }
    var LIFT_TITLE = "How much more often the two appear together than their popularity alone predicts";
    var pairTable = createDataTable(document.getElementById("profile-pair-table"), {
      caption: "Teammates",
      sort: { key: "lift", dir: "desc" },
      limit: 15,
      rowHref: function (r) { return pokemonHref(r.partner_pokemon_key); },
      empty: "No recorded teammates.",
      columns: [
        { key: "pokemon_name", label: "Teammate", type: "pokemon", keyField: "partner_pokemon_key", main: true, sortable: true },
        { key: "lift", label: "Lift", numeric: true, sortable: true, main: true,
          render: function (r) { return liftCell(r.lift); }, title: function () { return LIFT_TITLE; } },
        { key: "partner_share", label: "Partner share", type: "share",
          title: function (r) { return r.co_occurrence_count != null ? "On " + r.co_occurrence_count.toLocaleString() + " teams together" : ""; } },
        { key: "co_occurrence_count", label: "Teams together", type: "int" },
      ],
    });
    var tripleTable = createDataTable(document.getElementById("profile-triple-table"), {
      caption: "Three-Pokémon cores",
      sort: { key: "triple_lift", dir: "desc" },
      limit: 12,
      empty: "No three-Pokémon core with this Pokémon reaches five teams.",
      columns: [
        {
          key: "core",
          label: "With",
          main: true,
          sortable: false,
          render: function (r) {
            return teamCompositionHtml(r.pokemon_keys, 32) + '<span class="core-names">' +
              r.pokemon_keys.split("|").map(function (k) {
                return '<a href="' + pokemonHref(k) + '">' + escapeHtml(pokemonNames[k] || k) + "</a>";
              }).join(" + ") + "</span>";
          },
        },
        { key: "triple_lift", label: "Lift", numeric: true, sortable: true, main: true,
          render: function (r) { return liftCell(r.triple_lift); } },
        { key: "triple_team_count", label: "Teams", type: "int" },
        { key: "event_count", label: "Events", type: "int", hideOnPhone: true },
      ],
    });

    function drawTeammates(pokemonKey) {
      var triples = coreSizeSelect && coreSizeSelect.value === "triples";
      var bySynergy = !coreMetricSelect || coreMetricSelect.value === "synergy";
      document.getElementById("profile-pair-table").hidden = triples;
      document.getElementById("profile-triple-table").hidden = !triples;
      pairTable.setSort(bySynergy ? "lift" : "co_occurrence_count");
      tripleTable.setSort(bySynergy ? "triple_lift" : "triple_team_count");
      if (triples) {
        tripleTable.setRows(tripleRows.filter(function (r) {
          return r.triple_team_count >= 5 &&
            (r.pokemon_key_a === pokemonKey || r.pokemon_key_b === pokemonKey || r.pokemon_key_c === pokemonKey);
        }).map(function (r) {
          var others = [r.pokemon_key_a, r.pokemon_key_b, r.pokemon_key_c].filter(function (k) { return k !== pokemonKey; });
          return {
            pokemon_keys: others.join("|"),
            triple_lift: r.triple_lift,
            triple_team_count: r.triple_team_count,
            event_count: r.event_count,
          };
        }));
        return;
      }
      var liftByPartner = {};
      synergyRows.forEach(function (r) {
        if (r.pokemon_key === pokemonKey) liftByPartner[r.partner_pokemon_key] = r.lift;
      });
      pairTable.setRows(coreRows.filter(function (r) {
        return r.pokemon_key === pokemonKey;
      }).map(function (r) {
        return {
          partner_pokemon_key: r.partner_pokemon_key,
          pokemon_name: r.partner_pokemon_name,
          partner_share: r.partner_share,
          co_occurrence_count: r.co_occurrence_count,
          lift: liftByPartner[r.partner_pokemon_key] != null ? liftByPartner[r.partner_pokemon_key] : null,
        };
      }));
    }

    // Per-regulation trend (P2): usage share across every regulation with
    // data, as a small line, with win rate and sample size under each point.
    function trendHtml(pokemonKey) {
      var byCode = {};
      (marts.pokemon_usage_by_regulation || []).forEach(function (r) {
        if (r.pokemon_key === pokemonKey) byCode[r.regulation_code] = r;
      });
      var points = (DATA.regulations || []).filter(function (reg) {
        return (DATA.kpis_by_scope || {})[reg.regulation_code];
      }).map(function (reg) {
        return { code: reg.regulation_code, row: byCode[reg.regulation_code] || null };
      });
      if (points.length < 2) return "";
      var width = 280;
      var height = 64;
      var pad = 22;
      var max = points.reduce(function (m, p) { return Math.max(m, p.row ? p.row.usage_share || 0 : 0); }, 0) || 0.01;
      var step = (width - pad * 2) / (points.length - 1);
      var coords = points.map(function (p, i) {
        var value = p.row ? p.row.usage_share || 0 : 0;
        return { x: pad + i * step, y: height - 14 - (value / max) * (height - 30), value: value, p: p };
      });
      var line = coords.map(function (c) { return c.x.toFixed(1) + "," + c.y.toFixed(1); }).join(" ");
      var svg = '<svg class="trend-svg" viewBox="0 0 ' + width + " " + height + '" role="img" aria-label="Usage share by regulation: ' +
        coords.map(function (c) { return shortRegulation(c.p.code) + " " + formatPercent(c.value); }).join(", ") + '">' +
        '<polyline points="' + line + '" fill="none" stroke="var(--blue)" stroke-width="2"/>' +
        coords.map(function (c) {
          var current = c.p.code === regulationScope;
          return '<circle cx="' + c.x.toFixed(1) + '" cy="' + c.y.toFixed(1) + '" r="' + (current ? 5 : 3.5) +
            '" fill="' + (current ? "var(--accent-red)" : "var(--blue)") + '"/>' +
            '<text x="' + c.x.toFixed(1) + '" y="' + (c.y - 8).toFixed(1) + '" text-anchor="middle" class="trend-label">' +
            formatPercent(c.value) + "</text>";
        }).join("") + "</svg>";
      var legend = '<div class="trend-legend" style="grid-template-columns: repeat(' + points.length + ', 1fr)">' +
        points.map(function (p) {
          var r = p.row;
          return '<div' + (p.code === regulationScope ? ' class="is-current"' : "") + "><strong>" +
            escapeHtml(shortRegulation(p.code).replace("Reg ", "")) + "</strong>" +
            (r && r.win_rate != null
              ? '<span title="' + escapeHtml(recordTitle(r)) + '">' + formatPercent(r.win_rate) + " WR</span>" +
                "<span>n=" + (r.record_count || 0).toLocaleString() + "</span>"
              : "<span>" + (r && r.usage_count ? r.usage_count.toLocaleString() + " teams" : "not used") + "</span>") +
            "</div>";
        }).join("") + "</div>";
      return '<div class="trend"><p class="trend-title">Usage across regulations</p>' + svg + legend + "</div>";
    }

    // Recently viewed (P2): the last few profiles opened in this browser,
    // for checking a handful of Pokémon at a venue without searching each.
    var RECENT_KEY = "dashboard-recent-pokemon";
    var MAX_RECENT = 8;
    var recentEl = document.getElementById("profile-recent");
    function readRecent() {
      try {
        var list = JSON.parse(localStorage.getItem(RECENT_KEY) || "[]");
        return Array.isArray(list) ? list : [];
      } catch (e) {
        return [];
      }
    }
    function rememberRecent(key) {
      var list = readRecent().filter(function (k) { return k !== key; });
      list.unshift(key);
      list = list.slice(0, MAX_RECENT);
      try {
        localStorage.setItem(RECENT_KEY, JSON.stringify(list));
      } catch (e) {
        // Storage blocked: the strip just shows this visit's Pokémon.
      }
      return list;
    }
    function drawRecent(currentKey) {
      if (!recentEl) return;
      var list = rememberRecent(currentKey).filter(function (k) {
        return k !== currentKey && profileKeys[k];
      });
      recentEl.hidden = !list.length;
      recentEl.innerHTML = '<span class="recent-label">Recently viewed</span>' + list.map(function (k) {
        return '<a class="recent-chip" href="' + pokemonHref(k) + '" title="' + escapeHtml(pokemonNames[k] || k) + '">' +
          spriteImg(k, 32) + '<span class="visually-hidden">' + escapeHtml(pokemonNames[k] || k) + "</span></a>";
      }).join("");
    }

    // Teams featuring this Pokémon (P2): its top-placing top-cut teams in
    // the selected regulation, as team cards.
    var MAX_FEATURING = 6;
    var teamsEl = document.getElementById("profile-teams");
    function drawFeaturing(profile) {
      if (!teamsEl) return;
      var events = eventsById();
      var inScope = {};
      eventsInScope().forEach(function (e) { inScope[e.event_id] = true; });
      var teams = (marts.tournament_top_cut_teams || []).filter(function (t) {
        return inScope[t.event_id] && ("|" + t.pokemon_keys + "|").indexOf("|" + profile.pokemon_key + "|") !== -1;
      }).map(function (t) {
        var e = events[t.event_id] || {};
        var team = {};
        for (var k in t) if (Object.prototype.hasOwnProperty.call(t, k)) team[k] = t[k];
        team.event_name = e.event_name;
        team.event_date = e.event_date;
        team.event_tier = e.event_tier;
        team.event_size = e.team_count || 0;
        return team;
      }).sort(function (a, b) {
        return a.placement - b.placement || tierRank(a.event_tier) - tierRank(b.event_tier) || b.event_size - a.event_size;
      });
      teamsEl.innerHTML = teams.length
        ? teams.slice(0, MAX_FEATURING).map(function (t) { return teamCardHtml(t); }).join("")
        : '<p class="empty-state">No top-16 team in ' + escapeHtml(shortRegulation(regulationScope)) +
          " brought " + escapeHtml(profile.pokemon_name) + ".</p>";
      var note = document.getElementById("profile-teams-note");
      if (note) {
        note.textContent = teams.length
          ? teams.length + " top-16 team" + (teams.length === 1 ? "" : "s") + " in " +
            shortRegulation(regulationScope) + " brought " + profile.pokemon_name + "; the best-placed are below."
          : "";
      }
    }

    // Pressure from the meta (P2): type-chart weaknesses weighted by how
    // often the regulation's teams use each attacking type. Type-based,
    // not battle results -- labelled as such in the view.
    var attackTypeWeights = null;
    function metaAttackWeights() {
      if (attackTypeWeights) return attackTypeWeights;
      var usage = usageShareByKey();
      var weights = {};
      var total = 0;
      moveRows.forEach(function (m) {
        if (!m.move_type || m.category === "status" || !(m.power > 0)) return;
        var w = (usage[m.pokemon_key] || 0) * (m.move_share || 0);
        weights[m.move_type] = (weights[m.move_type] || 0) + w;
        total += w;
      });
      Object.keys(weights).forEach(function (t) { weights[t] = total ? weights[t] / total : 0; });
      attackTypeWeights = weights;
      return weights;
    }
    var pressureTable = createDataTable(document.getElementById("profile-pressure-table"), {
      caption: "Pressure by attacking type",
      sort: { key: "pressure", dir: "desc" },
      columns: [
        {
          key: "type",
          label: "Attacking type",
          main: true,
          sortable: true,
          render: function (r) {
            return '<span class="cell-with-icon">' + typeIconImg(r.type, 22) + "<span class=\"type-name\">" + escapeHtml(r.type) + "</span></span>";
          },
        },
        {
          key: "multiplier",
          label: "Against it",
          numeric: true,
          sortable: true,
          main: true,
          render: function (r) {
            var cls = r.multiplier > 1 ? "badge-negative" : r.multiplier < 1 ? "badge-positive" : "badge-rank";
            return '<span class="badge ' + cls + '">' + r.multiplier + "×</span>";
          },
        },
        {
          key: "weight",
          label: "Share of meta attacks",
          type: "share",
          title: function () { return "Usage-weighted share of the regulation's damaging moves"; },
        },
        {
          key: "pressure",
          label: "Pressure",
          numeric: true,
          sortable: true,
          render: function (r) {
            var pts = r.pressure * 100;
            return (pts > 0 ? "+" : "") + pts.toFixed(1);
          },
          title: function () {
            return "Share of meta attacks × (multiplier − 1), in points: how much this type pushes the average above neutral";
          },
        },
      ],
    });
    function drawPressure(profile) {
      var summary = document.getElementById("profile-pressure-summary");
      // The type chart lives in matchup.js, which publishes it on the shared
      // namespace once loaded (before any tab initialises).
      var effectiveness = window.DashboardApp && window.DashboardApp.typeEffectiveness;
      if (!effectiveness) return;
      var weights = metaAttackWeights();
      var types = [profile.type_1, profile.type_2].filter(Boolean);
      var expected = 0;
      var rows = ALL_TYPES.map(function (t) {
        var m = effectiveness(t, types);
        var w = weights[t] || 0;
        expected += w * m;
        return { type: t, multiplier: m, weight: w, pressure: w * (m - 1) };
      });
      pressureTable.setRows(rows);
      if (summary) {
        var weak = rows.filter(function (r) { return r.multiplier > 1; })
          .sort(function (a, b) { return b.pressure - a.pressure; });
        summary.innerHTML = "A typical attack in " + escapeHtml(shortRegulation(regulationScope)) + " hits " +
          escapeHtml(profile.pokemon_name) + " for <strong>" + expected.toFixed(2) + "×</strong> on average" +
          (weak.length
            ? ". Its biggest exposure is " + weak.slice(0, 2).map(function (r) {
                return escapeHtml(r.type) + " (" + formatPercent(r.weight) + " of attacks, " + r.multiplier + "×)";
              }).join(" and ") + "."
            : ", and nothing common hits it super-effectively.");
      }
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

    function topRow(rows, key) {
      return rows
        .filter(function (r) { return r.pokemon_key === key; })
        .sort(function (a, b) { return a.usage_rank - b.usage_rank; });
    }

    // Real sets (docs/upgrade-plan-2027q1.md, P1): an item, ability, nature
    // and four moves that appeared together on real team sheets, from
    // pokemon_set_variants. "Exact" sets match all of it; "core" sets group
    // on item, ability and the three most common moves, so near-identical
    // sets differing in one flex move cluster. This replaced a card built
    // from each slot's most common choice, which could describe a set
    // nobody ran.
    var setRows = marts.pokemon_set_variants || [];
    var setsByKey = {};
    setRows.forEach(function (r) {
      var byLevel = setsByKey[r.pokemon_key] || (setsByKey[r.pokemon_key] = { full: [], core: [] });
      (byLevel[r.set_level] || (byLevel[r.set_level] = [])).push(r);
    });
    Object.keys(setsByKey).forEach(function (key) {
      ["full", "core"].forEach(function (level) {
        setsByKey[key][level].sort(function (a, b) { return a.set_rank - b.set_rank; });
      });
    });
    var setState = { level: "full", index: 0 };
    // Below this many teams, a set's card says the sample is thin.
    var MIN_SET_TEAMS = 10;

    // A set's moves in the Pokémon's own move-usage order, not the mart's
    // alphabetical order, so the headline move comes first.
    function orderedMoves(key, moves) {
      var rank = {};
      topRow(moveRows, key).forEach(function (m, i) { rank[m.move_name] = i; });
      return splitMoves(moves).sort(function (a, b) {
        return (rank[a] === undefined ? 99 : rank[a]) - (rank[b] === undefined ? 99 : rank[b]);
      });
    }

    function moveTypeOf(key, moveName) {
      var row = moveRows.filter(function (m) { return m.pokemon_key === key && m.move_name === moveName; })[0];
      return row ? row.move_type : null;
    }

    function setBodyHtml(profile, set) {
      var moves = orderedMoves(profile.pokemon_key, set.moves);
      var exportSet = {
        pokemon_key: profile.pokemon_key,
        item_name: set.item_name,
        ability: set.ability,
        nature: set.nature,
        moves: moves,
      };
      var thin = set.team_count < MIN_SET_TEAMS;
      var winLine = set.win_rate != null
        ? ' · <span title="95% Wilson lower bound ' + formatPercent(set.wilson_lower_bound) + '">' +
          formatPercent(set.win_rate) + " win rate</span>"
        : "";
      return "<dl>" +
        "<dt>Item</dt><dd>" + itemCell(set.item_name) + "</dd>" +
        "<dt>Ability</dt><dd>" + escapeHtml(set.ability || "—") + "</dd>" +
        (set.nature ? "<dt>Nature</dt><dd>" + escapeHtml(set.nature) + "</dd>" : "") +
        "</dl>" +
        '<ul class="set-moves">' + moves.map(function (m) {
          return "<li>" + typeIconImg(moveTypeOf(profile.pokemon_key, m), 18) + " " + escapeHtml(m) + "</li>";
        }).join("") + (set.set_level === "core" ? '<li class="set-flex">+ 1 flex move</li>' : "") + "</ul>" +
        '<p class="set-sample' + (thin ? " is-thin" : "") + '">' +
        '<span title="' + set.team_count.toLocaleString() + " of " + set.pokemon_slot_count.toLocaleString() +
        " " + escapeHtml(profile.pokemon_name) + ' teams">Run by ' + set.team_count.toLocaleString() + " of " +
        set.pokemon_slot_count.toLocaleString() + " teams (" + formatPercent(set.share_of_pokemon) + ")</span>" +
        winLine + " in " + escapeHtml(shortRegulation(regulationScope)) +
        (thin ? ". Small sample: treat as anecdotal." : ".") + "</p>" +
        '<div class="set-actions">' + copyButtonHtml(setToShowdown(exportSet), "Copy for Showdown") +
        (set.set_level === "full"
          ? ' <a class="btn btn-sm" href="' + routeHash("team-builder", ["add", profile.pokemon_key + "." + setState.index]) +
            '">Add to Builder</a>'
          : "") +
        "</div>";
    }

    function setCardHtml(profile) {
      var sets = setsByKey[profile.pokemon_key];
      var list = sets ? sets[setState.level] : [];
      if (!sets || (!sets.full.length && !sets.core.length)) {
        return '<div class="set-card"><h3>Real sets</h3><p class="empty-state">No complete team sheet for ' +
          escapeHtml(profile.pokemon_name) + " in " + escapeHtml(shortRegulation(regulationScope)) +
          " yet: a set needs an item, ability, nature and four moves.</p></div>";
      }
      if (!list.length) {
        setState.level = sets.full.length ? "full" : "core";
        list = sets[setState.level];
      }
      if (setState.index >= list.length) setState.index = 0;
      var set = list[setState.index];
      return '<div class="set-card">' +
        '<div class="set-card-head"><h3>Real sets</h3>' +
        '<div class="set-level" role="group" aria-label="Set grouping">' +
        '<button type="button" class="set-level-btn" data-set-level="full" aria-pressed="' + (setState.level === "full") + '">Exact</button>' +
        '<button type="button" class="set-level-btn" data-set-level="core" aria-pressed="' + (setState.level === "core") + '">Core</button>' +
        "</div></div>" +
        '<div class="set-tabs" role="tablist" aria-label="Most common sets">' + list.map(function (r, i) {
          return '<button type="button" role="tab" class="set-tab" data-set-index="' + i + '" aria-selected="' +
            (i === setState.index) + '">Set ' + (i + 1) + ' <span class="set-share">' + formatPercent(r.share_of_pokemon) +
            "</span></button>";
        }).join("") + "</div>" +
        '<div class="set-body" role="tabpanel">' + setBodyHtml(profile, set) + "</div>" +
        '<p class="stat-legend">' + (setState.level === "full"
          ? "Each set appeared exactly like this on real team sheets."
          : "Core sets group by item, ability and the three most common moves; the fourth move varies.") +
        " No EVs: team sheets don't publish them.</p></div>";
    }

    var setEl = document.getElementById("pokemon-profile-set");
    if (setEl) {
      setEl.addEventListener("click", function (e) {
        var levelBtn = e.target.closest("[data-set-level]");
        var tabBtn = e.target.closest("[data-set-index]");
        if (!levelBtn && !tabBtn) return;
        if (levelBtn) setState = { level: levelBtn.getAttribute("data-set-level"), index: 0 };
        if (tabBtn) setState.index = Number(tabBtn.getAttribute("data-set-index"));
        var profile = sortedProfiles.filter(function (r) { return r.pokemon_key === select.value; })[0];
        if (profile) setEl.innerHTML = setCardHtml(profile);
      });
    }

    function render(chosenKey) {
      var profile = sortedProfiles.filter(function (r) {
        return r.pokemon_key === chosenKey;
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
            "</div>" + statBarsHtml(profile) + trendHtml(profile.pokemon_key) + "</div></div>";
          renderTypeBadgeRow(document.getElementById("profile-type-badge"), profile.type_1, profile.type_2, true);
        }
      }
      if (setEl) {
        if (profile && profile.pokemon_key !== setEl.getAttribute("data-key")) {
          setState = { level: "full", index: 0 };
          setEl.setAttribute("data-key", profile.pokemon_key);
        }
        setEl.innerHTML = profile ? setCardHtml(profile) : "";
      }

      var items = chosenKey
        ? itemRows.filter(function (r) {
            return r.pokemon_key === chosenKey;
          })
        : [];
      var itemTotal = items.reduce(function (sum, r) { return sum + (r.usage_count || 0); }, 0);
      itemTable.setRows(items.map(function (r) {
        return { item_name: r.item_name, item_share: r.item_share, usage_count: r.usage_count,
          usage_rank: r.usage_rank, short_effect: r.short_effect, total: itemTotal };
      }));

      var abilities = chosenKey
        ? abilityRows.filter(function (r) {
            return r.pokemon_key === chosenKey;
          })
        : [];
      var abilityTotal = abilities.reduce(function (sum, r) { return sum + (r.usage_count || 0); }, 0);
      abilityTable.setRows(abilities.map(function (r) {
        return { ability: r.ability, ability_share: r.ability_share, usage_count: r.usage_count,
          usage_rank: r.usage_rank, short_effect: r.short_effect, total: abilityTotal };
      }));

      var moves = chosenKey
        ? moveRows.filter(function (r) {
            return r.pokemon_key === chosenKey;
          })
        : [];
      moveTable.setRows(moves);

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

      if (profile) {
        drawTeammates(profile.pokemon_key);
        drawFeaturing(profile);
        drawPressure(profile);
        drawRecent(profile.pokemon_key);
      }
    }

    var subTabs = setupSubTabs(
      document.querySelectorAll('.tab-panel[data-panel="pokemon-profile"] .subtab-btn'),
      document.querySelectorAll('.tab-panel[data-panel="pokemon-profile"] .subtab-panel'),
      null,
      {
        route: {
          tab: "pokemon-profile",
          argIndex: 1,
          fill: function () { return select.value; },
        },
      }
    );

    // Picking another Pokémon is a navigation (Back returns to the last one).
    select.addEventListener("change", function () {
      render(select.value);
      setRoute("pokemon-profile", [select.value], {}, { push: true });
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

    profileRoute = function (route) {
      var key = route.args[0];
      if (!key || !profileKeys[key]) key = sortedProfiles.length ? sortedProfiles[0].pokemon_key : "";
      if (key !== select.value || !statsEl.innerHTML) {
        select.value = key;
        select.dispatchEvent(new Event("pokemon-sync"));
        render(key);
      }
      subTabs.fromRoute(route);
    };
  }

  var profileRoute = function () {};

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
    var SCENARIO_LABELS = {
      max_investment_speed: "Max",
      base_speed: "Base",
      plus_one_speed: "+1 / Scarf",
      plus_two_speed: "+2 / Tailwind",
      scarf_tailwind_speed: "Scarf + TW",
    };

    function scenarioField() {
      return scenarioSelect ? scenarioSelect.value : "max_investment_speed";
    }

    var table = createDataTable(document.getElementById("speed-tiers-table"), {
      caption: "Speed tiers",
      sort: { key: "scenario_speed", dir: "desc" },
      limit: 60,
      rowHref: pokemonRowHref,
      columns: [
        { key: "rank", label: "#", type: "rank", main: true },
        { key: "pokemon_name", label: "Pokémon", type: "pokemon", main: true, sortable: true },
        {
          key: "scenario_speed",
          label: "Speed",
          type: "int",
          main: true,
          render: function (r) { return "<strong>" + r.scenario_speed + "</strong>"; },
          title: function () { return SCENARIO_LABELS[scenarioField()] + " scenario"; },
        },
        { key: "base_speed", label: "Base", type: "int" },
        {
          key: "tier",
          label: "Tier",
          sortable: false,
          hideOnPhone: true,
          render: function (r) { return speedTierBadge(r.base_speed); },
        },
        { key: "usage_share", label: "Usage", type: "percent" },
        { key: "win_rate", label: "Win rate", type: "percent", hideOnPhone: true },
      ],
    });

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
        })
        .map(function (r, i) {
          var row = {};
          for (var k in r) if (Object.prototype.hasOwnProperty.call(r, k)) row[k] = r[k];
          row.rank = i + 1;
          row.scenario_speed = r[field];
          return row;
        });
    }

    function draw() {
      var field = scenarioField();
      var f = filtered();
      table.setRows(f);

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
    playersSubTabs = setupSubTabs(
      document.querySelectorAll('.tab-panel[data-panel="players"] .subtab-btn'),
      document.querySelectorAll('.tab-panel[data-panel="players"] .subtab-panel'),
      null,
      { route: { tab: "players", argIndex: 0 } }
    );
  }
  var playersSubTabs = null;

  function setupPlayerRegions() {
    var countryRows = marts.pokemon_usage_by_country || [];
    var select = document.getElementById("players-country-filter");
    var note = document.getElementById("players-country-note");
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

    var table = createDataTable(document.getElementById("players-country-table"), {
      caption: "Usage by country",
      sort: { key: "country_usage_rank", dir: "asc" },
      limit: 30,
      rowHref: pokemonRowHref,
      columns: [
        { key: "country_usage_rank", label: "#", type: "rank", main: true },
        { key: "pokemon_name", label: "Pokémon", type: "pokemon", main: true, sortable: true },
        {
          key: "usage_share",
          label: "Share of picks",
          type: "share",
          main: true,
          title: function (r) {
            return r.usage_count + " of " + (appearancesByCountry[r.player_country] || 0).toLocaleString() + " picks";
          },
        },
        { key: "usage_count", label: "Picks", type: "int" },
      ],
    });

    function draw() {
      var country = select.value;
      var rows = countryRows.filter(function (r) {
        return r.player_country === country;
      });
      if (note) {
        note.textContent = rows.length
          ? country + " has " + appearancesByCountry[country].toLocaleString() +
            " recorded roster picks across " + rows.length + " distinct Pokémon."
          : "No recorded picks for this country.";
      }
      table.setRows(rows);
    }

    select.addEventListener("change", draw);
    if (countries.length) select.value = countries[0];
    draw();
  }

  function setupPlayerSignatures() {
    var signatureRows = marts.player_signature_pokemon || [];
    var select = document.getElementById("players-player-filter");
    var note = document.getElementById("players-player-note");
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

    createDataTable(document.getElementById("players-specialists-table"), {
      caption: "Most committed specialists",
      sort: { key: "team_share", dir: "desc" },
      limit: 30,
      rowHref: function (r) { return routeHash("player", [r.player_id]); },
      columns: [
        {
          key: "player_name",
          label: "Player",
          main: true,
          sortable: true,
          render: function (r) {
            return '<a href="' + routeHash("player", [r.player_id]) + '">' + escapeHtml(r.player_name) + "</a>";
          },
        },
        { key: "player_country", label: "Country", sortable: true, render: function (r) { return countryCell(r.player_country); } },
        { key: "pokemon_name", label: "Signature Pokémon", type: "pokemon", main: true, sortable: true },
        {
          key: "team_share",
          label: "Share of their teams",
          type: "share",
          main: true,
          title: function (r) { return "On " + r.usage_count + " of their " + r.player_team_count + " teams"; },
        },
        { key: "player_team_count", label: "Teams", type: "int" },
      ],
    }).setRows(specialists);

    var signatureTable = createDataTable(document.getElementById("players-signature-table"), {
      caption: "A player's most-fielded Pokémon",
      sort: { key: "player_pokemon_rank", dir: "asc" },
      rowHref: pokemonRowHref,
      columns: [
        { key: "player_pokemon_rank", label: "#", type: "rank", main: true },
        { key: "pokemon_name", label: "Pokémon", type: "pokemon", main: true, sortable: true },
        {
          key: "team_share",
          label: "Share of their teams",
          type: "share",
          main: true,
          title: function (r) { return "On " + r.usage_count + " of their " + r.player_team_count + " teams"; },
        },
        { key: "player_usage_share", label: "Share of picks", type: "percent" },
      ],
    });

    function draw() {
      var rows = byPlayer[select.value] || [];
      if (note) {
        note.innerHTML = rows.length
          ? '<a href="' + routeHash("player", [select.value]) + '">' + escapeHtml(rows[0].player_name) + "</a> has " +
            rows[0].player_team_count + " recorded teams; their top " + rows.length + " picks are below."
          : "No recorded picks for this player.";
      }
      signatureTable.setRows(rows);
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
    dataSubTabs = setupSubTabs(subtabs, subpanels, null, { route: { tab: "data-sources", argIndex: 0 } });
  }
  var dataSubTabs = null;

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
    // A route sets the select without a "change" (which would record a new
    // history entry); "pokemon-sync" just refreshes the label.
    select.addEventListener("pokemon-sync", syncInput);
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
    if (currentRoute.tab !== "pokemon-profile") openTab("pokemon-profile");
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

  // The regulation whose [start_date, end_date) holds todayIso; past every
  // registered set, the latest one that has started (the next set hasn't
  // been added to the registry yet). Mirrors data.py's regulation_in_force.
  function regulationInForce(regulations, todayIso) {
    var inForce = null;
    var started = null;
    (regulations || []).forEach(function (r) {
      if (r.start_date <= todayIso && todayIso < r.end_date) inForce = r;
      if (r.start_date <= todayIso) started = r;
    });
    return inForce || started;
  }

  function shortRegulation(code) {
    return code === ALL_SCOPE ? "All regulations" : "Reg " + String(code || "").toUpperCase();
  }

  // "Reg M-D started 2026-12-02. Not enough results yet; showing M-C.
  // Switch to M-D →" (docs/upgrade-plan-2027q1.md, U3).
  function renderRolloverBanner() {
    var banner = document.getElementById("rollover-banner");
    if (!banner || !rolloverNotice) return;
    var inForce = rolloverNotice.in_force;
    var html = escapeHtml(shortRegulation(inForce.regulation_code)) + " started " +
      escapeHtml(inForce.start_date) + ". Not enough results yet" +
      (rolloverNotice.has_data ? " (" + rolloverNotice.team_count.toLocaleString() + " teams)" : "") +
      "; showing " + escapeHtml(shortRegulation(rolloverNotice.shown.regulation_code)) + ".";
    if (rolloverNotice.has_data) {
      var params = new URLSearchParams(window.location.search);
      params.set(SCOPE_PARAM, inForce.regulation_code);
      html += ' <a href="?' + escapeHtml(params.toString()) + escapeHtml(window.location.hash) + '">Switch to ' +
        escapeHtml(shortRegulation(inForce.regulation_code)) + " &rarr;</a>";
    }
    banner.innerHTML = html;
    banner.hidden = false;
  }

  function renderStalenessBanner() {
    var banner = document.getElementById("staleness-banner");
    var latest = (DATA.kpis || {}).latest_event_date;
    if (!banner || !latest) return;
    var todayIso = new Date().toISOString().slice(0, 10);
    var ageDays = Math.floor((Date.parse(todayIso) - Date.parse(latest)) / 86400000);
    var current = regulationInForce(DATA.regulations, todayIso);
    var messages = [];
    // During a rollover the rollover banner already says the new set has
    // no results yet and which regulation is shown; repeating it here was
    // the one finding of the M-D dry run (docs/dashboard.md's rollover
    // playbook). Only the data's age is still worth a warning then.
    if (current && latest < current.start_date && !rolloverNotice) {
      messages.push(
        current.regulation_name + " began " + current.start_date +
        ", but the newest tournament here is from " + latest +
        ". These figures describe an earlier regulation."
      );
    } else if (ageDays > STALE_AFTER_DAYS && (!rolloverNotice || latest < rolloverNotice.in_force.start_date)) {
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
  renderRolloverBanner();

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
      var inForce = regulationInForce(DATA.regulations, TODAY_ISO);
      try {
        // Remembered with the regulation in force when it was made, so the
        // next set's arrival overrides it (resolveRegulationScope, step 2).
        localStorage.setItem(
          SCOPE_STORAGE_KEY,
          JSON.stringify({
            code: select.value,
            in_force: inForce ? inForce.regulation_code : null,
            chosen_on: TODAY_ISO,
          })
        );
      } catch (e) {
        // Storage blocked: the ?reg= link below still carries the choice.
      }
      var params = new URLSearchParams(window.location.search);
      params.set(SCOPE_PARAM, select.value);
      window.location.assign("?" + params.toString() + window.location.hash);
    });
  }
  setupRegulationSelector();

  // Theme toggle: Auto (follow the OS) -> Light -> Dark. The choice is a
  // per-browser convenience in localStorage; the inline script in <head>
  // applies it before first paint.
  function setupThemeToggle() {
    var button = document.getElementById("theme-toggle");
    if (!button) return;
    var order = ["auto", "light", "dark"];
    var labels = { auto: "Theme: Auto", light: "Theme: Light", dark: "Theme: Dark" };
    var current = document.documentElement.getAttribute("data-theme") || "auto";
    function apply(theme) {
      current = theme;
      if (theme === "auto") document.documentElement.removeAttribute("data-theme");
      else document.documentElement.setAttribute("data-theme", theme);
      button.textContent = labels[theme];
      try {
        localStorage.setItem("dashboard-theme", theme);
      } catch (e) {
        // Storage blocked (private mode): the choice lasts for this page only.
      }
    }
    button.textContent = labels[current];
    button.addEventListener("click", function () {
      apply(order[(order.indexOf(current) + 1) % order.length]);
    });
  }
  setupThemeToggle();

  // The header's ⋯ menu (U2): the theme toggle and the Data links.
  function setupMoreMenu() {
    var button = document.getElementById("more-menu-btn");
    var panel = document.getElementById("more-menu-panel");
    if (!button || !panel) return;
    function setOpen(open) {
      panel.hidden = !open;
      button.setAttribute("aria-expanded", open ? "true" : "false");
    }
    button.addEventListener("click", function (e) {
      e.stopPropagation();
      setOpen(panel.hidden);
    });
    panel.addEventListener("click", function (e) {
      if (e.target.closest("a")) setOpen(false);
    });
    document.addEventListener("click", function (e) {
      if (!panel.hidden && !e.target.closest(".more-menu")) setOpen(false);
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && !panel.hidden) {
        setOpen(false);
        button.focus();
      }
    });
  }
  setupMoreMenu();

  // Overview reads only DATA.kpis, which is inlined — it renders with no
  // network round-trip, so the landing view is never waiting on data.json.
  registerTab("overview", setupOverview, { needsMarts: false });
  registerTab("data-sources", setupDataSources, {
    onRoute: function (route) {
      if (dataSubTabs) dataSubTabs.fromRoute(route);
    },
  });
  registerTab("tiers", setupTiers);
  registerTab("usage", setupUsage, {
    extraMarts: ["pokemon_event_usage_vs_regulation"],
    onRoute: function (route) {
      if (usageSubTabs) usageSubTabs.fromRoute(route);
      usageWindowRoute(route);
    },
  });
  registerTab("pokemon-profile", setupPokemonProfile, {
    extraMarts: ["pokemon_team_core_triple_usage", "tournament_team_sheets"],
    onRoute: function (route) {
      profileRoute(route);
    },
  });
  registerTab("archetypes", setupDetectedArchetypes);
  registerTab("speed-tiers", setupSpeedTiers);
  registerTab("players", setupPlayers, {
    extraMarts: ["player_signature_pokemon"],
    onRoute: function (route) {
      if (playersSubTabs) playersSubTabs.fromRoute(route);
    },
  });

  function runInitializer(tabId) {
    tabInitializers[tabId](currentRoute.tab === tabId ? currentRoute : null);
    tabReady[tabId] = true;
    if (currentRoute.tab === tabId) dispatchRoute(currentRoute);
  }

  function initTab(tabId) {
    if (initialized[tabId] || !tabInitializers[tabId]) return;
    initialized[tabId] = true;
    if (!tabNeedsMarts[tabId]) {
      runInitializer(tabId);
      return;
    }
    ensureData(tabExtraMarts[tabId]).then(
      function () {
        runInitializer(tabId);
      },
      function (error) {
        // Un-mark so a retry (re-clicking the tab) can try the fetch again
        // rather than silently doing nothing forever.
        initialized[tabId] = false;
        renderDataLoadError(tabId, error);
      }
    );
  }

  setupNavigation(function (tabId) {
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
    createDataTable: createDataTable,
    pokemonRowHref: pokemonRowHref,
    registerTab: registerTab,
    setupSubTabs: setupSubTabs,
    ensureData: ensureData,
    regulationScope: regulationScope,
    scopeLabel: scopeLabel,
    attachPokemonCombobox: attachPokemonCombobox,
    openProfile: openProfile,
    fillSelectPairs: fillSelectPairs,
    showdownName: showdownName,
    setToShowdown: setToShowdown,
    teamToShowdown: teamToShowdown,
    copyButtonHtml: copyButtonHtml,
    shortEventName: shortEventName,
    ordinal: ordinal,
    recordText: recordText,
    tierRank: tierRank,
    eventsById: eventsById,
    eventsInScope: eventsInScope,
    teamSheet: teamSheet,
    teamListSheet: teamListSheet,
    teamCardHtml: teamCardHtml,
    tipHtml: tipHtml,
    citationLine: citationLine,
    ALL_SCOPE: ALL_SCOPE,
    copyWithFallback: copyWithFallback,
    // Routing (U1): navigate() adds a history entry, setRoute() records a
    // tab's own state change, routeHash() builds a link.
    navigate: navigate,
    setRoute: setRoute,
    routeHash: routeHash,
    pokemonHref: pokemonHref,
    openTab: openTab,
    currentRoute: function () {
      return currentRoute;
    },
    shortRegulation: shortRegulation,
  };
})();
