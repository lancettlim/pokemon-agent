/* Global search (docs/upgrade-plan-2027q2.md, Q3): one box that finds
 * Pokémon, players and events, and opens the page for the one picked.
 * It opens from the header's search button from 1024px (the ⋯ menu's
 * "Search" below that, where the header has no room), "/" or Ctrl/⌘+K. On phones it is
 * a full-screen sheet with the keyboard up; from 768px a panel under the
 * header. With an empty box it lists recent picks, kept per browser.
 *
 * Pokémon are searchable at once, from the inline name map, in the page's
 * name language and in English (Q4). Players and events come from marts
 * the first open loads (player_index, the core tournament_event_summary);
 * until they arrive the box says so. Online events have no pages and are
 * not listed. */
(function () {
  "use strict";
  var App = window.DashboardApp;
  if (!App) return;

  var RECENT_KEY = "dashboard-recent-search";
  var MAX_RECENT = 6;
  var PER_GROUP = 6;
  var GROUPS = [
    { kind: "pokemon", label: "Pokémon" },
    { kind: "player", label: "Players" },
    { kind: "event", label: "Events" },
  ];

  var esc = App.escapeHtml;
  var norm = App.normalizeSearch;
  var sheet = document.getElementById("search-sheet");
  var input = document.getElementById("search-input");
  var list = document.getElementById("search-results");
  var status = document.getElementById("search-status");
  if (!sheet || !input || !list) return;

  var loaded = false;
  var loading = null;
  var results = [];
  var active = -1;
  var opener = null;

  // ---------- the index ----------

  function pokemonItems() {
    var keys = Object.keys(App.sprites || {});
    if (!keys.length) keys = Object.keys(App.pokemonNames || {});
    return keys.map(function (key) {
      return {
        kind: "pokemon",
        id: key,
        label: App.pokemonNames[key] || key,
        alt: (App.englishNames || {})[key] || "",
        href: App.pokemonHref(key),
      };
    });
  }

  function playerItems() {
    return (App.marts.player_index || []).map(function (r) {
      return {
        kind: "player",
        id: r.player_id,
        label: r.player_name,
        meta: [r.player_country, r.team_count === 1 ? "1 team" : (r.team_count || 0) + " teams"].filter(Boolean).join(" · "),
        href: App.routeHash("player", [r.player_id]),
      };
    });
  }

  function eventItems() {
    return (App.marts.tournament_event_summary || []).map(function (e) {
      return {
        kind: "event",
        id: e.event_id,
        label: App.shortEventName ? App.shortEventName(e.event_name) : e.event_name,
        alt: e.event_name,
        meta: [e.event_date, e.regulation_code ? "Reg " + e.regulation_code.toUpperCase() : ""].filter(Boolean).join(" · "),
        href: App.routeHash("event", [e.event_id]),
      };
    });
  }

  function index() {
    return pokemonItems().concat(loaded ? playerItems().concat(eventItems()) : []);
  }

  // Ranked by where the query falls: the start of the name, the start of a
  // word, anywhere. Ties keep the index order (Pokémon by usage-ish sprite
  // order, players alphabetically, events newest first as the mart has them).
  function score(item, query) {
    var best = 0;
    [item.label, item.alt].filter(Boolean).forEach(function (text) {
      var whole = norm(text);
      if (whole.indexOf(query) === 0) best = Math.max(best, 3);
      else if (String(text).split(/[\s\-–—()（）]+/).some(function (w) { return norm(w).indexOf(query) === 0; })) best = Math.max(best, 2);
      else if (whole.indexOf(query) > 0) best = Math.max(best, 1);
    });
    return best;
  }

  function search(text) {
    var query = norm(text);
    if (!query) return [];
    var scored = index()
      .map(function (item, order) { return { item: item, score: score(item, query), order: order }; })
      .filter(function (s) { return s.score > 0; })
      .sort(function (a, b) { return b.score - a.score || a.order - b.order; });
    var out = [];
    GROUPS.forEach(function (group) {
      out = out.concat(scored.filter(function (s) { return s.item.kind === group.kind; })
        .slice(0, PER_GROUP).map(function (s) { return s.item; }));
    });
    return out;
  }

  // ---------- recent picks ----------

  function readRecent() {
    try {
      var saved = JSON.parse(localStorage.getItem(RECENT_KEY) || "[]");
      return Array.isArray(saved) ? saved : [];
    } catch (e) {
      return [];
    }
  }

  function remember(item) {
    var recent = readRecent().filter(function (r) { return !(r.kind === item.kind && r.id === item.id); });
    recent.unshift({ kind: item.kind, id: item.id, label: item.label, meta: item.meta || "", href: item.href });
    try {
      localStorage.setItem(RECENT_KEY, JSON.stringify(recent.slice(0, MAX_RECENT)));
    } catch (e) {
      // Storage blocked: no recent list next time.
    }
  }

  function recentItems() {
    return readRecent().map(function (r) {
      // A Pokémon shows in the page's current name language.
      if (r.kind === "pokemon") r.label = App.pokemonNames[r.id] || r.label;
      return r;
    });
  }

  // ---------- rendering ----------

  function iconFor(item) {
    if (item.kind === "pokemon") return App.spriteImg(item.id, App.ICON_SIZES.sm) || '<span class="search-glyph">?</span>';
    if (item.kind === "player") return '<span class="search-glyph" aria-hidden="true">' + (App.countryFlag ? App.countryFlag((item.meta || "").slice(0, 2)) || "👤" : "👤") + "</span>";
    return '<span class="search-glyph" aria-hidden="true">🏆</span>';
  }

  function render() {
    var text = input.value;
    var recent = !norm(text);
    results = recent ? recentItems() : search(text);
    var html = recent && results.length ? '<li class="search-group" role="presentation">Recent</li>' : "";
    var lastKind = null;
    results.forEach(function (item, i) {
      if (!recent && item.kind !== lastKind) {
        lastKind = item.kind;
        var group = GROUPS.filter(function (g) { return g.kind === item.kind; })[0];
        html += '<li class="search-group" role="presentation">' + esc(group ? group.label : item.kind) + "</li>";
      }
      html += '<li role="option" id="search-option-' + i + '" data-index="' + i + '" aria-selected="false">' +
        '<a href="' + esc(item.href) + '" tabindex="-1">' + iconFor(item) +
        '<span class="search-text"><span class="search-label">' + esc(item.label) + "</span>" +
        (item.meta ? '<span class="search-meta">' + esc(item.meta) + "</span>" : "") +
        "</span></a></li>";
    });
    list.innerHTML = html;
    if (status) {
      status.textContent = recent
        ? (results.length ? "" : "Type a Pokémon, player or event.")
        : results.length
          ? results.length + (results.length === 1 ? " result" : " results")
          : "Nothing matches “" + text + "”." + (loaded ? "" : " Players and events are still loading.");
    }
    highlight(results.length ? 0 : -1);
  }

  function highlight(index) {
    active = index;
    Array.prototype.forEach.call(list.querySelectorAll('[role="option"]'), function (li) {
      var on = Number(li.getAttribute("data-index")) === index;
      li.setAttribute("aria-selected", on ? "true" : "false");
      if (on) li.scrollIntoView({ block: "nearest" });
    });
    if (index >= 0) input.setAttribute("aria-activedescendant", "search-option-" + index);
    else input.removeAttribute("aria-activedescendant");
  }

  function choose(index) {
    var item = results[index];
    if (!item) return;
    remember(item);
    close();
    App.navigate(item.href);
  }

  // ---------- open and close ----------

  function load() {
    if (loaded || loading) return;
    loading = App.ensureData(["player_index"]).then(function () {
      loaded = true;
      if (!sheet.hidden) render();
    }).catch(function () {
      loading = null;
    });
  }

  function open() {
    opener = document.activeElement;
    sheet.hidden = false;
    document.documentElement.classList.add("search-open");
    input.value = "";
    render();
    load();
    input.focus();
  }

  function close() {
    if (sheet.hidden) return;
    sheet.hidden = true;
    document.documentElement.classList.remove("search-open");
    // Hiding the box doesn't take focus from it at once in every browser,
    // and focusing the body (the usual opener) does nothing; until the box
    // lets go, the next "/" would count as typing in a field.
    if (sheet.contains(document.activeElement)) document.activeElement.blur();
    if (opener && opener !== document.body && opener.isConnected && opener.focus) opener.focus();
  }

  input.addEventListener("input", render);
  input.addEventListener("keydown", function (e) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      highlight(Math.min(active + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      highlight(Math.max(active - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      choose(active);
    } else if (e.key === "Escape") {
      e.preventDefault();
      close();
    }
  });
  list.addEventListener("click", function (e) {
    var li = e.target.closest && e.target.closest('[role="option"]');
    if (!li) return;
    e.preventDefault();
    choose(Number(li.getAttribute("data-index")));
  });
  sheet.addEventListener("click", function (e) {
    if (e.target === sheet || (e.target.closest && e.target.closest("[data-search-close]"))) close();
  });
  document.addEventListener("click", function (e) {
    var trigger = e.target.closest && e.target.closest("[data-search-open]");
    if (!trigger) return;
    e.preventDefault();
    var menu = document.getElementById("more-menu-panel");
    if (menu && !menu.hidden && menu.contains(trigger)) document.getElementById("more-menu-btn").click();
    open();
  });
  // "/" or Ctrl/⌘+K from anywhere outside a field.
  document.addEventListener("keydown", function (e) {
    var shortcut = (e.key === "k" || e.key === "K") && (e.metaKey || e.ctrlKey) && !e.altKey;
    var slash = e.key === "/" && !e.metaKey && !e.ctrlKey && !e.altKey;
    if (!shortcut && !slash) return;
    var focused = document.activeElement;
    var tag = (focused && focused.tagName) || "";
    var inField = (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") && !(sheet.hidden && sheet.contains(focused));
    if (slash && inField) return;
    e.preventDefault();
    if (sheet.hidden) open();
    else input.focus();
  });

  App.openSearch = open;
})();
