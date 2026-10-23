/* Meta Graph (docs/plan-synergy-checks-graph.md, backlog #50): the whole
 * metagame of one regulation at once, as a graph. Loaded after app.js and
 * reuses window.DashboardApp.
 *
 *   #/graph/synergy   nodes are Pokémon, sized by team share and coloured
 *                     by synergy cluster; an edge is a pair that shares
 *                     teams more often than popularity predicts (lift)
 *   #/graph/checks    the same nodes; an arrow A -> B means teams with A
 *                     beat teams with B more often than the two teams'
 *                     overall records predict (pokemon_check_edges)
 *   ?focus=<key>      one Pokémon in the centre, with its partners, the
 *                     Pokémon its teams beat and the Pokémon whose teams
 *                     beat it in rings around it. The default on phones.
 *   ?min=<n>          minimum shared teams (synergy) or matches (checks)
 *   ?ev=all           checks: strong and suggestive edges. The default is
 *                     strong only, unless the regulation has no strong
 *                     edge at all (M-C, as of the 2026 data): then it
 *                     shows suggestive edges and says so
 *   ?hide=<n>         hide the n Pokémon with the highest team share
 *   ?mega=1           Megas only
 *
 * Positions and clusters are precomputed per regulation at build time
 * (pipelines/dashboard/graph.py), so this file only draws: plain SVG, no
 * charting or physics library, and the same picture on every load. Every
 * graph has a table twin below it with the same edges, for exact numbers
 * and for screen readers.
 *
 * Checks are team vs team: no source records which Pokémon were brought
 * to a match, so the caveat (CHECKS_CAVEAT) shows on every checks view. */
(function () {
  "use strict";

  var App = window.DashboardApp;
  if (!App) return;

  var marts = App.marts;
  var esc = App.escapeHtml;
  var SVG_NS = "http://www.w3.org/2000/svg";

  var CHECKS_CAVEAT =
    "Team vs team: teams with A beat teams with B more often than their overall records predict. " +
    "No source records which Pokémon were brought, so this is not a battle log.";
  var SYNERGY_MINS = [5, 10, 20, 40];
  var CHECK_MINS = [20, 40, 80];
  var HIDE_TOPS = [0, 5, 10, 20];
  // Labels on the full graph: only the most-used, or it turns to noise.
  var LABELLED_NODES = 18;
  // Focus rings hold at most this many Pokémon each.
  var MAX_RING = 12;
  var PHONE_PX = 720;
  // Neutral cluster palette, readable on both themes as a halo behind the
  // sprite. Cluster 0 ("unclustered") is grey.
  var CLUSTER_COLORS = [
    "#8a94a6", "#3b82f6", "#e4572e", "#2bb673", "#a35bd6", "#f2a541",
    "#17a2b8", "#d6457a", "#7a8b2e", "#5c6bc0", "#b7793f", "#2f9e9e", "#c0392b",
  ];

  var state = {
    layer: "synergy", focus: "", min: 0, ev: "strong", evExplicit: false,
    hide: 0, mega: false, selected: "", showFull: false,
  };
  var els = {};
  var graph = null;
  var nodesByKey = {};
  var table = null;
  var tableMode = "";

  function clusterColor(c) {
    return CLUSTER_COLORS[c % CLUSTER_COLORS.length] || CLUSTER_COLORS[0];
  }

  function nameOf(key) {
    return App.pokemonNames[key] || key;
  }

  function isPhone() {
    return window.innerWidth < PHONE_PX;
  }

  function currentGraph() {
    var rows = marts.pokemon_graph || [];
    return rows.filter(function (g) { return g.regulation_scope === App.regulationScope; })[0] || rows[0] || null;
  }

  function defaultMin() {
    return state.layer === "checks" ? CHECK_MINS[0] : SYNERGY_MINS[0];
  }

  // ---------- which nodes and edges are shown ----------

  function hiddenKeys() {
    var hidden = {};
    if (!graph) return hidden;
    if (state.hide) {
      graph.nodes.slice().sort(function (a, b) { return b.teams - a.teams; })
        .slice(0, state.hide).forEach(function (n) { hidden[n.k] = true; });
    }
    if (state.mega) {
      graph.nodes.forEach(function (n) {
        if (!/-mega(-|$)/.test(n.k)) hidden[n.k] = true;
      });
    }
    return hidden;
  }

  function synergyEdges() {
    var min = state.min || SYNERGY_MINS[0];
    var hidden = hiddenKeys();
    return (graph ? graph.synergy : []).filter(function (e) {
      return e[2] >= min && !hidden[e[0]] && !hidden[e[1]];
    }).map(function (e) {
      return { a: e[0], b: e[1], teams: e[2], lift: e[3], z: e[4] };
    });
  }

  function hasStrongEdges() {
    return !!graph && graph.checks.some(function (e) { return e[8] === "strong"; });
  }

  // "Strong only" on a regulation with no strong edge would be an empty
  // page; unless the viewer picked it, show suggestive edges instead.
  function effectiveEv() {
    return state.ev === "strong" && !state.evExplicit && !hasStrongEdges() ? "all" : state.ev;
  }

  function checkEdges() {
    var min = state.min || CHECK_MINS[0];
    var hidden = hiddenKeys();
    var ev = effectiveEv();
    return (graph ? graph.checks : []).filter(function (e) {
      return e[2] >= min && (ev === "all" || e[8] === "strong") && !hidden[e[0]] && !hidden[e[1]];
    }).map(function (e) {
      return {
        a: e[0], b: e[1], matches: e[2], wins: e[3], observed: e[4], expected: e[5],
        z: e[6], q: e[7], evidence: e[8],
      };
    });
  }

  function layerEdges() {
    return state.layer === "checks" ? checkEdges() : synergyEdges();
  }

  // The selected scope's full synergy rows (top 12 partners per Pokémon by
  // lift, floored at 5 shared teams in data.py), for a focus view's
  // partner ring: richer than the graph's per-node cap.
  function partnersOf(key) {
    var min = state.layer === "synergy" ? state.min || SYNERGY_MINS[0] : SYNERGY_MINS[0];
    var hidden = hiddenKeys();
    return (marts.pokemon_team_synergy || []).filter(function (r) {
      return r.pokemon_key === key && r.pair_team_count >= min && r.lift > 1 && !hidden[r.partner_pokemon_key];
    }).sort(function (a, b) {
      return (b.synergy_z || 0) - (a.synergy_z || 0) || b.lift - a.lift;
    }).slice(0, MAX_RING).map(function (r) {
      return { a: key, b: r.partner_pokemon_key, teams: r.pair_team_count, lift: r.lift, z: r.synergy_z };
    });
  }

  function checksOf(key) {
    var edges = checkEdges();
    return {
      beats: edges.filter(function (e) { return e.a === key; }).slice(0, MAX_RING),
      beatenBy: edges.filter(function (e) { return e.b === key; }).slice(0, MAX_RING),
    };
  }

  // ---------- SVG ----------

  function svgEl(tag, attrs) {
    var node = document.createElementNS(SVG_NS, tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (attrs[k] !== null && attrs[k] !== undefined) node.setAttribute(k, attrs[k]);
    });
    return node;
  }

  function nodeRadius(n, maxShare) {
    return 10 + 22 * Math.sqrt((n.share || 0) / (maxShare || 1));
  }

  var profiles = null;
  function typeRing(key) {
    if (!profiles) profiles = App.championsProfileByKey();
    var profile = profiles[key];
    return profile && profile.type_1 ? App.typeColor(profile.type_1) : "var(--border)";
  }

  // One node: halo in its cluster colour, a ring in its first type's
  // colour, the sprite, and an invisible hit circle of at least 22px
  // radius (44px across) so it is a fair touch target.
  function drawNode(parent, key, x, y, r, opts) {
    opts = opts || {};
    var n = nodesByKey[key] || { k: key, c: 0, share: 0, teams: 0 };
    var g = svgEl("g", {
      class: "graph-node" + (opts.cls ? " " + opts.cls : ""),
      transform: "translate(" + x + "," + y + ")",
      "data-key": key,
      tabindex: "-1",
      role: "button",
      "aria-label": nameOf(key) + ", " + App.formatPercent(n.share) + " of teams" +
        (n.c ? ", cluster " + n.c : ""),
    });
    var title = svgEl("title");
    title.textContent = nameOf(key) + " · " + App.formatPercent(n.share) + " of teams";
    g.appendChild(title);
    g.appendChild(svgEl("circle", { class: "graph-hit", r: Math.max(r, 22) }));
    g.appendChild(svgEl("circle", {
      class: "graph-halo", r: r, fill: clusterColor(n.c), stroke: typeRing(key),
    }));
    var src = App.sprites[key];
    if (src) {
      g.appendChild(svgEl("image", {
        href: src, x: -r * 0.9, y: -r * 0.9, width: r * 1.8, height: r * 1.8,
        preserveAspectRatio: "xMidYMid meet",
      }));
    }
    if (opts.label) {
      var text = svgEl("text", { class: "graph-label", y: r + 13, "text-anchor": "middle" });
      text.textContent = nameOf(key);
      g.appendChild(text);
    }
    parent.appendChild(g);
    return g;
  }

  function drawEdge(parent, edge, pa, pb, rb) {
    var line;
    if (state.layer === "checks") {
      // Stop the arrow at the target's rim so its head stays visible.
      var dx = pb.x - pa.x;
      var dy = pb.y - pa.y;
      var len = Math.sqrt(dx * dx + dy * dy) || 1;
      var trim = (rb || 16) + 4;
      line = svgEl("line", {
        x1: pa.x, y1: pa.y, x2: pb.x - (dx / len) * trim, y2: pb.y - (dy / len) * trim,
        class: "graph-edge graph-edge-check" + (edge.evidence === "suggestive" ? " is-suggestive" : ""),
        // Strong edges carry the weight; suggestive ones stay thin, so a
        // regulation with only suggestive edges doesn't read as a dense
        // web of findings.
        "stroke-width": edge.evidence === "suggestive"
          ? "1.2"
          : (2 + Math.min(3, Math.abs(edge.observed - edge.expected) * 15)).toFixed(1),
        "marker-end": "url(#graph-arrow)",
      });
    } else {
      line = svgEl("line", {
        x1: pa.x, y1: pa.y, x2: pb.x, y2: pb.y,
        class: "graph-edge graph-edge-synergy",
        "stroke-width": (1 + Math.min(5, Math.log(Math.max(edge.lift, 1)) * 2.5)).toFixed(1),
        "stroke-opacity": (0.25 + 0.6 * Math.min(1, edge.teams / 50)).toFixed(2),
      });
    }
    line.setAttribute("data-a", edge.a);
    line.setAttribute("data-b", edge.b);
    parent.appendChild(line);
  }

  function newSvg(width, height, label) {
    var svg = svgEl("svg", {
      viewBox: "0 0 " + width + " " + height,
      class: "graph-svg",
      role: "group",
      "aria-label": label,
      "aria-describedby": "graph-table",
    });
    var defs = svgEl("defs");
    var marker = svgEl("marker", {
      id: "graph-arrow", viewBox: "0 0 10 10", refX: "8", refY: "5",
      markerUnits: "userSpaceOnUse", markerWidth: "11", markerHeight: "11", orient: "auto-start-reverse",
    });
    marker.appendChild(svgEl("path", { d: "M0,0 L10,5 L0,10 z", class: "graph-arrow-head" }));
    defs.appendChild(marker);
    svg.appendChild(defs);
    return svg;
  }

  // When a filter or the checks layer leaves only part of the graph, zoom
  // to the Pokémon still shown: positions keep their arrangement (they are
  // the same precomputed ones, scaled about the shown nodes' bounding box)
  // while sprites keep their size. Zoom is capped, so three nodes don't
  // spread across the whole frame.
  var MAX_ZOOM = 2.5;
  var ZOOM_PAD = 50;
  function projection(nodes) {
    if (!nodes.length) return function (n) { return n; };
    var x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    nodes.forEach(function (n) {
      x0 = Math.min(x0, n.x); y0 = Math.min(y0, n.y);
      x1 = Math.max(x1, n.x); y1 = Math.max(y1, n.y);
    });
    var w = graph.width - 2 * ZOOM_PAD;
    var h = graph.height - 2 * ZOOM_PAD;
    var zoom = Math.min(MAX_ZOOM, w / Math.max(x1 - x0, 1), h / Math.max(y1 - y0, 1));
    var cx = (x0 + x1) / 2;
    var cy = (y0 + y1) / 2;
    return function (n) {
      return { x: graph.width / 2 + (n.x - cx) * zoom, y: graph.height / 2 + (n.y - cy) * zoom };
    };
  }

  function drawFull() {
    var edges = layerEdges();
    var hidden = hiddenKeys();
    var shown = {};
    edges.forEach(function (e) { shown[e.a] = true; shown[e.b] = true; });
    // Synergy keeps every node with any edge in the graph; checks show
    // only the Pokémon a drawn arrow touches, so the picture isn't a sea
    // of unconnected sprites.
    var nodes = graph.nodes.filter(function (n) {
      return !hidden[n.k] && (state.layer === "checks" ? shown[n.k] : true);
    });
    var maxShare = nodes.reduce(function (m, n) { return Math.max(m, n.share || 0); }, 0);
    var svg = newSvg(graph.width, graph.height,
      (state.layer === "checks" ? "Checks graph" : "Synergy graph") + " for " + App.scopeLabel(App.regulationScope));
    var edgeLayer = svgEl("g", { class: "graph-edges" });
    var nodeLayer = svgEl("g", { class: "graph-nodes" });
    svg.appendChild(edgeLayer);
    svg.appendChild(nodeLayer);
    var radius = {};
    nodes.forEach(function (n) { radius[n.k] = nodeRadius(n, maxShare); });
    var at = projection(nodes);
    edges.forEach(function (e) {
      var a = nodesByKey[e.a];
      var b = nodesByKey[e.b];
      if (a && b) drawEdge(edgeLayer, e, at(a), at(b), radius[e.b]);
    });
    var labelled = {};
    nodes.slice().sort(function (a, b) { return b.teams - a.teams; }).slice(0, LABELLED_NODES)
      .forEach(function (n) { labelled[n.k] = true; });
    nodes.forEach(function (n) {
      var p = at(n);
      drawNode(nodeLayer, n.k, p.x, p.y, radius[n.k], { label: labelled[n.k] });
    });
    return { svg: svg, nodes: nodes, edges: edges };
  }

  // Focus: the Pokémon in the centre, then up to three rings: partners
  // (synergy), "its teams beat" and "teams that beat its teams" (checks).
  // An empty ring is skipped, so the others close in.
  function drawFocus(key) {
    // A phone draws the same rings in a smaller frame, so sprites read at
    // about the size of a table row's; ring labels are left to the side
    // panel and table, where they don't collide.
    var phone = isPhone();
    var width = phone ? 440 : 700;
    var height = width;
    var cx = width / 2;
    var cy = height / 2;
    var partners = partnersOf(key);
    var checks = checksOf(key);
    var rings = [
      { kind: "partner", label: "Partners", edges: partners, other: function (e) { return e.b; } },
      { kind: "beats", label: "Its teams beat", edges: checks.beats, other: function (e) { return e.b; } },
      { kind: "beaten", label: "Teams that beat its teams", edges: checks.beatenBy, other: function (e) { return e.a; } },
    ].filter(function (ring) { return ring.edges.length; });
    var svg = newSvg(width, height, "Graph focused on " + nameOf(key));
    var edgeLayer = svgEl("g", { class: "graph-edges" });
    var nodeLayer = svgEl("g", { class: "graph-nodes" });
    svg.appendChild(edgeLayer);
    svg.appendChild(nodeLayer);
    // Ring radii between INNER_RING and OUTER_RING, which leaves room for
    // a sprite and its label inside the 700px frame.
    var INNER_RING = phone ? 90 : 120;
    var OUTER_RING = phone ? 195 : 290;
    function ringRadius(i) {
      if (rings.length === 1) return (INNER_RING + OUTER_RING) / 2;
      return INNER_RING + ((OUTER_RING - INNER_RING) * i) / (rings.length - 1);
    }
    var placed = {};
    var nodeKeys = [key];
    var edges = [];
    rings.forEach(function (ring, i) {
      var r = ringRadius(i);
      edgeLayer.appendChild(svgEl("circle", { cx: cx, cy: cy, r: r, class: "graph-ring graph-ring-" + ring.kind }));
      var count = ring.edges.length;
      // Rings start at a different angle each, so sprites in neighbouring
      // rings don't line up on the same spoke.
      var offset = -Math.PI / 2 + i * 0.35;
      ring.edges.forEach(function (e, j) {
        var other = ring.other(e);
        var angle = offset + (2 * Math.PI * j) / count;
        var p = { x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle) };
        // A Pokémon in two rings is drawn in the first and linked from both.
        if (!placed[other]) {
          placed[other] = p;
          nodeKeys.push(other);
        }
        var from = ring.kind === "beaten" ? placed[other] : { x: cx, y: cy };
        var to = ring.kind === "beaten" ? { x: cx, y: cy } : placed[other];
        var saved = state.layer;
        state.layer = ring.kind === "partner" ? "synergy" : "checks";
        drawEdge(edgeLayer, e, from, to, ring.kind === "beaten" ? (phone ? 30 : 34) : (phone ? 20 : 18));
        state.layer = saved;
        edges.push({ ring: ring.kind, edge: e });
      });
    });
    nodeKeys.slice(1).forEach(function (k) {
      drawNode(nodeLayer, k, placed[k].x, placed[k].y, phone ? 20 : 18, { label: !phone });
    });
    drawNode(nodeLayer, key, cx, cy, phone ? 30 : 34, { label: true, cls: "is-focus" });
    var legend = rings.map(function (ring) {
      return '<span class="graph-key graph-key-' + ring.kind + '">' + esc(ring.label) + " (" + ring.edges.length + ")</span>";
    }).join("");
    return { svg: svg, rings: rings, edges: edges, legend: legend, nodeKeys: nodeKeys };
  }

  // ---------- interaction ----------

  function neighbourMap(edges) {
    var map = {};
    edges.forEach(function (e) {
      (map[e.a] = map[e.a] || {})[e.b] = true;
      (map[e.b] = map[e.b] || {})[e.a] = true;
    });
    return map;
  }

  function highlight(svg, key, neighbours) {
    svg.classList.toggle("has-selection", !!key);
    svg.querySelectorAll(".graph-node").forEach(function (g) {
      var k = g.getAttribute("data-key");
      var on = !key || k === key || (neighbours[key] && neighbours[key][k]);
      g.classList.toggle("is-dim", !on);
      g.classList.toggle("is-selected", k === key);
    });
    svg.querySelectorAll(".graph-edge").forEach(function (line) {
      var on = !key || line.getAttribute("data-a") === key || line.getAttribute("data-b") === key;
      line.classList.toggle("is-dim", !on);
    });
  }

  function setFocus(key) {
    state.focus = key || "";
    state.selected = "";
    syncRoute(true);
    render();
  }

  // Arrow keys move to the neighbour that lies most in that direction
  // (or, with no neighbours, the nearest node that way); Enter focuses;
  // Escape clears the selection, then the focus.
  function moveSelection(svg, from, dir, neighbours) {
    var nodes = Array.prototype.slice.call(svg.querySelectorAll(".graph-node"));
    var pos = {};
    nodes.forEach(function (g) {
      var m = /translate\(([-\d.]+),([-\d.]+)\)/.exec(g.getAttribute("transform"));
      pos[g.getAttribute("data-key")] = { x: +m[1], y: +m[2], g: g };
    });
    var origin = pos[from];
    if (!origin) return nodes[0];
    var vec = { ArrowRight: [1, 0], ArrowLeft: [-1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }[dir];
    var pool = Object.keys((neighbours[from]) || {}).filter(function (k) { return pos[k]; });
    if (!pool.length) pool = Object.keys(pos).filter(function (k) { return k !== from; });
    var best = null;
    var bestScore = Infinity;
    pool.forEach(function (k) {
      var dx = pos[k].x - origin.x;
      var dy = pos[k].y - origin.y;
      var along = dx * vec[0] + dy * vec[1];
      if (along <= 0) return;
      var across = Math.abs(dx * vec[1] - dy * vec[0]);
      var score = along + 2 * across;
      if (score < bestScore) {
        bestScore = score;
        best = k;
      }
    });
    return best ? pos[best].g : null;
  }

  function wireSvg(svg, edges) {
    var neighbours = neighbourMap(edges);
    var nodes = svg.querySelectorAll(".graph-node");
    if (nodes.length) {
      var start = svg.querySelector('.graph-node[data-key="' + (state.selected || state.focus) + '"]') || nodes[0];
      start.setAttribute("tabindex", "0");
    }
    function select(g, moveFocus) {
      var key = g.getAttribute("data-key");
      state.selected = key;
      nodes.forEach(function (n) { n.setAttribute("tabindex", n === g ? "0" : "-1"); });
      if (moveFocus) g.focus();
      highlight(svg, key, neighbours);
      renderSide(key);
    }
    svg.addEventListener("click", function (e) {
      var g = e.target.closest(".graph-node");
      if (!g) {
        state.selected = "";
        highlight(svg, "", neighbours);
        renderSide("");
        return;
      }
      var key = g.getAttribute("data-key");
      // First tap selects; a second tap on the same node focuses it. The
      // centre of a focus view opens the profile instead.
      if (state.focus && key === state.focus) App.navigate(App.pokemonHref(key));
      else if (state.selected === key) setFocus(key);
      else select(g, false);
    });
    svg.addEventListener("mouseover", function (e) {
      var g = e.target.closest(".graph-node");
      if (g && !state.selected) highlight(svg, g.getAttribute("data-key"), neighbours);
    });
    svg.addEventListener("mouseleave", function () {
      highlight(svg, state.selected, neighbours);
    });
    svg.addEventListener("keydown", function (e) {
      var g = e.target.closest(".graph-node");
      if (!g) return;
      var key = g.getAttribute("data-key");
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        if (state.focus && key === state.focus) App.navigate(App.pokemonHref(key));
        else setFocus(key);
      } else if (e.key === "Escape") {
        e.preventDefault();
        if (state.selected && state.selected !== state.focus) {
          state.selected = "";
          highlight(svg, "", neighbours);
          renderSide("");
        } else if (state.focus) {
          setFocus("");
        }
      } else if (/^Arrow/.test(e.key)) {
        e.preventDefault();
        var next = moveSelection(svg, key, e.key, neighbours);
        if (next) select(next, true);
      }
    });
    // Keyboard focus selects, like a first tap. A pointer press also
    // focuses the node, so it is skipped here: the click handler decides
    // whether that tap selects or focuses.
    var pointerDown = false;
    svg.addEventListener("pointerdown", function () { pointerDown = true; });
    svg.addEventListener("focusin", function (e) {
      var g = e.target.closest(".graph-node");
      if (g && !pointerDown && state.selected !== g.getAttribute("data-key")) select(g, false);
      pointerDown = false;
    });
    if (state.selected) highlight(svg, state.selected, neighbours);
  }

  // ---------- side panel ----------

  function liftText(v) {
    return v == null ? "—" : "×" + Number(v).toFixed(1);
  }

  function pokemonLink(key) {
    return '<a href="' + esc(App.routeHash("graph", [state.layer], routeQuery({ focus: key }))) + '">' +
      App.spriteImg(key, 24) + esc(nameOf(key)) + "</a>";
  }

  function renderSide(key) {
    if (!els.side) return;
    if (!key) {
      els.side.innerHTML = '<p class="sub">' + (isPhone() ? "Tap" : "Hover or tap") +
        " a Pokémon to see its links. Tap it again to put it in the centre.</p>";
      return;
    }
    var n = nodesByKey[key] || { share: 0, teams: 0, c: 0 };
    var partners = partnersOf(key).slice(0, 5);
    var checks = checksOf(key);
    var cluster = (graph.clusters || []).filter(function (c) { return c.cluster === n.c; })[0];
    // Core partners inherit the same check edges (plan section 9): say so
    // when the top partner shares most of this Pokémon's teams.
    var overlapNote = "";
    if (partners[0] && n.teams && partners[0].teams / n.teams >= 0.5) {
      overlapNote = '<p class="sub">Often on the same team as ' + esc(nameOf(partners[0].b)) +
        " (" + App.formatPercent(partners[0].teams / n.teams) + " of its teams), so their check edges overlap.</p>";
    }
    function list(title, edges, other, fmt) {
      if (!edges.length) return "";
      return "<h4>" + esc(title) + '</h4><ul class="graph-side-list">' + edges.slice(0, 5).map(function (e) {
        return "<li>" + pokemonLink(other(e)) + ' <span class="sub">' + fmt(e) + "</span></li>";
      }).join("") + "</ul>";
    }
    function checkFmt(e) {
      return App.formatPercent(e.observed) + " vs " + App.formatPercent(e.expected) + " expected, n=" +
        e.matches + (e.evidence === "suggestive" ? " · suggestive" : "");
    }
    els.side.innerHTML =
      '<h3 class="graph-side-title">' + App.spriteImg(key, 40) + esc(nameOf(key)) + "</h3>" +
      '<p class="sub">' + App.formatPercent(n.share) + " of teams (" + Number(n.teams || 0).toLocaleString() + ")" +
      (cluster ? ' · <span class="graph-swatch" style="background:' + clusterColor(n.c) + '"></span>' + esc(cluster.label) : "") +
      "</p>" +
      '<p><a class="btn btn-sm" href="' + esc(App.pokemonHref(key)) + '">Profile</a> ' +
      (state.focus === key ? "" : '<button type="button" class="btn btn-sm" data-graph-focus="' + esc(key) + '">Focus</button>') +
      "</p>" +
      list("Partners", partners, function (e) { return e.b; }, function (e) {
        return liftText(e.lift) + ", " + e.teams + " teams";
      }) +
      list("Its teams beat", checks.beats, function (e) { return e.b; }, checkFmt) +
      list("Teams that beat its teams", checks.beatenBy, function (e) { return e.a; }, checkFmt) +
      overlapNote;
  }

  // ---------- table twin ----------

  function buildTable(mode) {
    if (tableMode === mode && table) return;
    tableMode = mode;
    if (mode === "checks") {
      table = App.createDataTable(els.table, {
        caption: "Check edges",
        sort: { key: "z", dir: "desc" },
        limit: 25,
        empty: "No check edge clears this evidence level and match floor.",
        citation: function () { return null; },
        columns: [
          { key: "a_name", label: "Teams with", type: "pokemon", keyField: "a", main: true, sortable: true },
          { key: "b_name", label: "beat teams with", type: "pokemon", keyField: "b", main: true, sortable: true },
          { key: "observed", label: "Win rate", type: "percent", main: true,
            title: function (r) { return r.wins + "–" + (r.matches - r.wins) + " in " + r.matches + " matches"; } },
          { key: "expected", label: "Expected", type: "percent" },
          { key: "matches", label: "Matches", type: "int" },
          { key: "z", label: "z", numeric: true, sortable: true, hideOnPhone: true,
            render: function (r) { return Number(r.z).toFixed(1); } },
          { key: "q", label: "q", numeric: true, sortable: true, hideOnPhone: true,
            render: function (r) { return Number(r.q).toFixed(3); } },
          { key: "evidence", label: "Evidence", sortable: true },
        ],
      });
    } else {
      table = App.createDataTable(els.table, {
        caption: "Synergy edges",
        sort: { key: "z", dir: "desc" },
        limit: 25,
        empty: "No pair clears this many shared teams.",
        columns: [
          { key: "a_name", label: "Pokémon", type: "pokemon", keyField: "a", main: true, sortable: true },
          { key: "b_name", label: "Partner", type: "pokemon", keyField: "b", main: true, sortable: true },
          { key: "lift", label: "Lift", term: "lift", numeric: true, sortable: true, main: true,
            render: function (r) { return liftText(r.lift); } },
          { key: "teams", label: "Teams together", type: "int" },
          { key: "z", label: "Confidence (z)", numeric: true, sortable: true, hideOnPhone: true,
            render: function (r) { return r.z == null ? "—" : Number(r.z).toFixed(1); } },
        ],
      });
    }
  }

  function setTableRows(edges) {
    buildTable(state.layer);
    table.setRows(edges.map(function (e) {
      var row = { a_name: nameOf(e.a), b_name: nameOf(e.b) };
      Object.keys(e).forEach(function (k) { row[k] = e[k]; });
      return row;
    }));
  }

  // ---------- render ----------

  function routeQuery(extra) {
    var q = {
      focus: state.focus || null,
      min: state.min && state.min !== defaultMin() ? state.min : null,
      ev: state.layer === "checks" && state.evExplicit ? state.ev : null,
      hide: state.hide || null,
      mega: state.mega ? 1 : null,
    };
    Object.keys(extra || {}).forEach(function (k) { q[k] = extra[k]; });
    return q;
  }

  function syncRoute(push) {
    App.setRoute("graph", [state.layer], routeQuery(), { push: !!push });
  }

  function fillMinSelect() {
    var values = state.layer === "checks" ? CHECK_MINS : SYNERGY_MINS;
    if (values.indexOf(state.min) === -1) state.min = values[0];
    App.fillSelectPairs(els.min, values.map(function (v) {
      return { value: String(v), label: v + (state.layer === "checks" ? " matches" : " teams") };
    }));
    els.min.value = String(state.min);
    els.minLabel.firstChild.textContent = state.layer === "checks" ? "Minimum matches " : "Minimum shared teams ";
  }

  function renderControls() {
    els.layerButtons.forEach(function (btn) {
      btn.setAttribute("aria-pressed", btn.getAttribute("data-graph-layer") === state.layer ? "true" : "false");
    });
    fillMinSelect();
    els.evLabel.hidden = state.layer !== "checks";
    els.ev.value = effectiveEv();
    els.hide.value = String(state.hide);
    els.mega.checked = state.mega;
    els.caveat.hidden = state.layer !== "checks" && !state.focus;
    els.clear.hidden = !state.focus;
    if (els.focusSelect.value !== state.focus) {
      els.focusSelect.value = state.focus;
      els.focusSelect.dispatchEvent(new Event("pokemon-sync"));
    }
  }

  function renderLegend(focusView) {
    if (focusView) {
      els.legend.innerHTML = focusView.legend +
        '<span class="graph-key graph-key-dashed">Dashed: suggestive (|z| ≥ 2, not significant after correction)</span>';
      return;
    }
    if (state.layer === "checks") {
      els.legend.innerHTML =
        '<span class="graph-key graph-key-beats">Arrow A → B: teams with A beat teams with B more than expected</span>' +
        '<span class="graph-key graph-key-dashed">Dashed: suggestive (|z| ≥ 2, not significant after correction)</span>' +
        "<span class=\"graph-key\">Thicker: strong, and further from expected</span>";
      return;
    }
    var clusters = (graph.clusters || []).slice(0, 10);
    els.legend.innerHTML =
      "<span class=\"graph-key\">Size: team share · Line: lift (thicker) and shared teams (darker) · Ring: type</span>" +
      clusters.map(function (c) {
        var core = c.members.slice(0, 3).map(nameOf).join(", ");
        return '<button type="button" class="graph-cluster-chip" data-graph-cluster="' + c.cluster + '">' +
          '<span class="graph-swatch" style="background:' + clusterColor(c.cluster) + '"></span>' +
          esc(c.label) + ': <span class="sub">' + esc(core) + (c.members.length > 3 ? "…" : "") + "</span></button>";
      }).join("");
  }

  function renderNotice() {
    var teams = graph ? graph.total_teams : 0;
    var thin = graph && teams < (App.DATA.min_default_scope_teams || 300);
    var parts = [];
    if (thin) {
      parts.push("Thin data: " + App.shortRegulation(App.regulationScope) + " has " + Number(teams).toLocaleString() +
        " teams on record, so expect fewer edges and wider error.");
    }
    if (state.layer === "checks" && graph && !graph.checks.length) {
      parts.push("No check edge in this regulation clears " + CHECK_MINS[0] +
        " matches with |z| ≥ 2. Tournament pairings are sparse once split by regulation.");
    } else if (state.layer === "checks" && graph && !hasStrongEdges() && !state.evExplicit) {
      parts.push("No pair in " + App.shortRegulation(App.regulationScope) +
        " survives the false-discovery correction, so these are suggestive edges only (|z| ≥ 2): " +
        "expect some to be chance.");
    }
    els.notice.hidden = !parts.length;
    els.notice.textContent = parts.join(" ");
  }

  function renderPhoneHome() {
    // Phones open on chips for the most-used Pokémon and the table twin;
    // the full graph is behind a button (plan section 5).
    var top = graph.nodes.slice().sort(function (a, b) { return b.teams - a.teams; }).slice(0, 5);
    els.canvas.innerHTML =
      '<p class="sub">Pick a Pokémon to see its partners and checks.</p>' +
      '<div class="graph-chips">' + top.map(function (n) {
        return '<button type="button" class="tier-chip" data-graph-focus="' + esc(n.k) + '">' +
          App.spriteImg(n.k, 32) + esc(nameOf(n.k)) + "</button>";
      }).join("") + "</div>" +
      '<p><button type="button" class="btn btn-sm" data-graph-full>Full graph</button></p>';
  }

  function render() {
    graph = currentGraph();
    nodesByKey = {};
    if (graph) graph.nodes.forEach(function (n) { nodesByKey[n.k] = n; });
    renderControls();
    renderNotice();
    if (!graph || !graph.nodes.length) {
      els.canvas.innerHTML = '<p class="empty-state">No graph for ' + esc(App.scopeLabel(App.regulationScope)) +
        ": no pair of Pokémon shares " + SYNERGY_MINS[0] + " teams yet.</p>";
      els.legend.innerHTML = "";
      els.side.innerHTML = "";
      setTableRows([]);
      return;
    }
    if (state.focus && !nodesByKey[state.focus] && !partnersOf(state.focus).length) {
      els.notice.hidden = false;
      els.notice.textContent = nameOf(state.focus) + " has no edges in " +
        App.shortRegulation(App.regulationScope) + ". Showing the full graph.";
      state.focus = "";
    }
    els.title.textContent = state.focus
      ? nameOf(state.focus) + " on the graph"
      : (state.layer === "checks" ? "Checks" : "Synergy") + " graph · " + App.shortRegulation(App.regulationScope);

    if (state.focus) {
      var view = drawFocus(state.focus);
      els.canvas.innerHTML = "";
      els.canvas.appendChild(view.svg);
      wireSvg(view.svg, view.edges.map(function (x) { return x.edge; }));
      renderLegend(view);
      setTableRows(state.layer === "checks"
        ? checkEdges().filter(function (e) { return e.a === state.focus || e.b === state.focus; })
        : partnersOf(state.focus));
      renderSide(state.selected || state.focus);
      return;
    }
    var edges = layerEdges();
    renderLegend(null);
    if (isPhone() && !state.showFull) {
      renderPhoneHome();
    } else {
      var full = drawFull();
      els.canvas.innerHTML = "";
      els.canvas.appendChild(full.svg);
      wireSvg(full.svg, full.edges);
    }
    setTableRows(edges);
    renderSide(state.selected);
  }

  // ---------- setup ----------

  function fromRoute(route) {
    if (!route) return;
    var layer = route.args[0] === "checks" ? "checks" : "synergy";
    var q = route.query || {};
    state.layer = layer;
    state.focus = q.focus || "";
    state.min = parseInt(q.min, 10) || defaultMin();
    state.ev = q.ev === "all" ? "all" : "strong";
    state.evExplicit = q.ev === "all" || q.ev === "strong";
    state.hide = HIDE_TOPS.indexOf(parseInt(q.hide, 10)) >= 0 ? parseInt(q.hide, 10) : 0;
    state.mega = q.mega === "1";
    if (els.canvas) render();
  }

  function setupGraph(route) {
    els = {
      panel: document.querySelector('.tab-panel[data-panel="graph"]'),
      canvas: document.getElementById("graph-canvas"),
      side: document.getElementById("graph-side"),
      legend: document.getElementById("graph-legend"),
      table: document.getElementById("graph-table"),
      title: document.getElementById("graph-title"),
      notice: document.getElementById("graph-notice"),
      caveat: document.getElementById("graph-caveat"),
      min: document.getElementById("graph-min"),
      minLabel: document.getElementById("graph-min-label"),
      ev: document.getElementById("graph-evidence"),
      evLabel: document.getElementById("graph-evidence-label"),
      hide: document.getElementById("graph-hide"),
      mega: document.getElementById("graph-mega"),
      focusSelect: document.getElementById("graph-focus"),
      clear: document.getElementById("graph-clear"),
      layerButtons: Array.prototype.slice.call(document.querySelectorAll("[data-graph-layer]")),
    };
    if (!els.canvas) return;
    els.caveat.textContent = CHECKS_CAVEAT;

    var g = currentGraph();
    var keys = g ? g.nodes.map(function (n) { return n.k; }) : [];
    App.fillSelectPairs(els.focusSelect, keys.map(function (k) {
      return { value: k, label: nameOf(k) };
    }).sort(function (a, b) { return a.label.localeCompare(b.label); }), "Whole graph");
    App.attachPokemonCombobox(els.focusSelect);
    App.fillSelectPairs(els.hide, HIDE_TOPS.map(function (v) {
      return { value: String(v), label: v ? "Top " + v : "None" };
    }));

    els.layerButtons.forEach(function (btn) {
      btn.addEventListener("click", function () {
        state.layer = btn.getAttribute("data-graph-layer");
        state.min = defaultMin();
        state.selected = "";
        syncRoute(false);
        render();
      });
    });
    els.min.addEventListener("change", function () {
      state.min = parseInt(els.min.value, 10) || defaultMin();
      syncRoute(false);
      render();
    });
    els.ev.addEventListener("change", function () {
      state.ev = els.ev.value;
      state.evExplicit = true;
      syncRoute(false);
      render();
    });
    els.hide.addEventListener("change", function () {
      state.hide = parseInt(els.hide.value, 10) || 0;
      syncRoute(false);
      render();
    });
    els.mega.addEventListener("change", function () {
      state.mega = els.mega.checked;
      syncRoute(false);
      render();
    });
    els.focusSelect.addEventListener("change", function () {
      if (els.focusSelect.value !== state.focus) setFocus(els.focusSelect.value);
    });
    els.clear.addEventListener("click", function () { setFocus(""); });
    els.panel.addEventListener("click", function (e) {
      var focusBtn = e.target.closest("[data-graph-focus]");
      if (focusBtn) {
        setFocus(focusBtn.getAttribute("data-graph-focus"));
        return;
      }
      if (e.target.closest("[data-graph-full]")) {
        state.showFull = true;
        render();
        return;
      }
      var chip = e.target.closest("[data-graph-cluster]");
      if (chip) {
        var svg = els.canvas.querySelector("svg");
        var c = parseInt(chip.getAttribute("data-graph-cluster"), 10);
        var pressed = chip.getAttribute("aria-pressed") === "true";
        els.legend.querySelectorAll("[data-graph-cluster]").forEach(function (b) { b.setAttribute("aria-pressed", "false"); });
        if (!svg) return;
        svg.classList.toggle("has-selection", !pressed);
        svg.querySelectorAll(".graph-node").forEach(function (node) {
          var n = nodesByKey[node.getAttribute("data-key")];
          node.classList.toggle("is-dim", !pressed && (!n || n.c !== c));
        });
        svg.querySelectorAll(".graph-edge").forEach(function (line) {
          var a = nodesByKey[line.getAttribute("data-a")];
          var b = nodesByKey[line.getAttribute("data-b")];
          line.classList.toggle("is-dim", !pressed && !(a && b && a.c === c && b.c === c));
        });
        chip.setAttribute("aria-pressed", pressed ? "false" : "true");
      }
    });
    fromRoute(route || App.currentRoute());
  }

  App.registerTab("graph", setupGraph, {
    extraMarts: ["pokemon_graph"],
    onRoute: fromRoute,
  });
})();
