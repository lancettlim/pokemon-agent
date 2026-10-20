/* Team Builder + Top Teams tabs (docs/design-system.md's "Team card /
 * pokepaste component", "Top Teams tab"). Loaded after app.js/matchup.js
 * and reuses window.DashboardApp for data/helpers rather than duplicating
 * them.
 *
 * Team Builder and Top Teams share one addToTeam/team-state pipeline (a
 * pokepaste import or a Pro Team Gallery "Load into my builder" click both
 * need to push Pokémon into the same saved team, regardless of which tab
 * the visitor is on when they do it) — see ensureTeamBuilder() below for
 * how that stays correct even if Top Teams is visited before Team Builder
 * ever wires up its DOM (tabs otherwise init lazily, on first activation).
 *
 * Each roster slot is a real build, not just a species pick: item,
 * ability, and up to 4 moves are all user-selectable (defaulting to that
 * Pokémon's top recorded choices), drawn from real recorded usage data
 * (pokemon_item_usage/pokemon_ability_usage/pokemon_move_usage) — never
 * invented options. There is deliberately no stat/EV selector: no source
 * publishes real EV/IV data at all -- official tournament team sheets
 * carry ability, item, nature and moves and nothing more -- so building
 * one would mean presenting invented numbers as if they were sourced (see
 * docs/backlog.md item #25 and docs/data-sources.md's Victory Road entry).
 * Nature IS published (100% of Champions roster slots) but is not part of
 * this builder's model. */
(function () {
  "use strict";

  var App = window.DashboardApp;
  if (!App) return;

  var marts = App.marts;
  var sprites = App.sprites;

  var ITEM_OPTION_CAP = 8;
  var ABILITY_OPTION_CAP = 5;
  var MOVE_OPTION_CAP = 15;
  var MOVE_SLOT_COUNT = 4;

  function groupByPokemonKey(rows) {
    var out = {};
    (rows || []).forEach(function (r) {
      (out[r.pokemon_key] = out[r.pokemon_key] || []).push(r);
    });
    return out;
  }

  function sortByUsageRank(rows) {
    return (rows || []).slice().sort(function (a, b) {
      return a.usage_rank - b.usage_rank;
    });
  }

  // ---------- pokepaste (Showdown-export-text) import/export ----------
  // "Do it like vgcpastes/pokepaste": accepts the same plain-text format
  // pokepast.es itself accepts (species [@ item] / Ability: .../ moves),
  // parsed client-side — there's no live URL fetch (static site, no
  // backend/CORS-proxy), so "paste a link" means paste the export text
  // you'd otherwise paste into pokepast.es to create one.
  function keyToShowdownName(key) {
    return key
      .split("-")
      .map(function (part) {
        return part.charAt(0).toUpperCase() + part.slice(1);
      })
      .join("-");
  }

  function normalizeSpeciesName(name) {
    return name.replace(/[-\s.'\u2019]/g, "").toLowerCase();
  }

  // Indexes every Pokémon under both its normalized pokemon_key (which is
  // what Showdown's hyphenated names normalize to: "Charizard-Mega-Y" ->
  // "charizardmegay") and its normalized display name ("Mega Charizard Y"
  // -> "megacharizardy"), so either spelling resolves.
  function buildNameLookup() {
    var lookup = {};
    Object.keys(App.pokemonNames).forEach(function (key) {
      lookup[normalizeSpeciesName(App.pokemonNames[key])] = key;
    });
    Object.keys(App.pokemonNames).forEach(function (key) {
      lookup[normalizeSpeciesName(key)] = key;
    });
    return lookup;
  }

  // Parses a Showdown-format team export into per-slot {key, item, ability,
  // moves} objects, so a pasted team round-trips through Team Builder with
  // its actual item/ability/moveset intact rather than falling back to
  // that Pokémon's top-recorded build.
  function parsePokepaste(text) {
    var lookup = buildNameLookup();
    var blocks = text
      .split(/\n\s*\n/)
      .map(function (b) {
        return b.trim();
      })
      .filter(Boolean);
    var resolvedSlots = [];
    var unresolvedNames = [];
    blocks.forEach(function (block) {
      var lines = block.split("\n").map(function (l) {
        return l.trim();
      });
      var firstLine = lines[0];
      var atIndex = firstLine.indexOf(" @ ");
      var namePart = atIndex !== -1 ? firstLine.slice(0, atIndex) : firstLine;
      var itemPart = atIndex !== -1 ? firstLine.slice(atIndex + 3).trim() : "";
      var parenMatch = namePart.match(/\(([^)]+)\)/);
      var species = parenMatch ? parenMatch[1] : namePart;
      species = species.replace(/\s*\((M|F)\)/g, "").trim();
      var key = lookup[normalizeSpeciesName(species)];
      if (!key) {
        if (species) unresolvedNames.push(species);
        return;
      }
      var ability = null;
      var moves = [];
      lines.slice(1).forEach(function (line) {
        if (/^Ability:\s*/i.test(line)) {
          ability = line.replace(/^Ability:\s*/i, "").trim();
        } else if (line.charAt(0) === "-") {
          var move = line.slice(1).trim();
          if (move) moves.push(move);
        }
      });
      var nature = null;
      lines.slice(1).forEach(function (line) {
        var match = line.match(/^(\w+)\s+Nature$/i);
        if (match) nature = match[1];
      });
      resolvedSlots.push({
        key: key,
        item: itemPart || null,
        ability: ability,
        nature: nature,
        moves: moves.slice(0, MOVE_SLOT_COUNT),
      });
    });
    return { resolvedSlots: resolvedSlots, unresolvedNames: unresolvedNames };
  }

  // Emits each slot's actually-chosen item/ability/moves (not just that
  // Pokémon's top-recorded build), so the pokepaste export reflects real
  // edits made in the builder.
  function exportTeamAsPokepaste(teamSlots) {
    return App.teamToShowdown(teamSlots.map(slotToSet));
  }

  // The Builder's slot shape -> the {pokemon_key, item_name, ...} set shape
  // App.setToShowdown and the share link use.
  function slotToSet(slot) {
    return {
      pokemon_key: slot.key,
      item_name: slot.item,
      ability: slot.ability,
      nature: slot.nature,
      moves: (slot.moves || []).filter(Boolean),
    };
  }

  // A team sheet row (tournament_team_sheets / team_list_sheets) -> a slot.
  function sheetToSlot(row) {
    return {
      key: row.pokemon_key,
      item: row.item_name || null,
      ability: row.ability || null,
      nature: row.nature || null,
      moves: String(row.moves || "").split("|").map(function (m) { return m.trim(); }).filter(Boolean),
    };
  }

  // ---------- Team Builder (fully client-side; localStorage only) ----------
  var teamBuilderState = null;

  function setupTeamBuilder() {
    var rows = marts.pokemon_champions_profile || [];
    var byKey = {};
    rows.forEach(function (r) {
      byKey[r.pokemon_key] = r;
    });
    var itemsByKey = groupByPokemonKey(marts.pokemon_item_usage);
    var abilitiesByKey = groupByPokemonKey(marts.pokemon_ability_usage);
    var naturesByKey = groupByPokemonKey(marts.pokemon_nature_usage);
    var movesByKey = groupByPokemonKey(marts.pokemon_move_usage);

    var STORAGE_KEY = "pokemonChampionsTeamBuilder";
    var MAX_TEAM_SIZE = 6;

    // Slot shape: {key, item, ability, moves: string[]} — item/ability
    // default to that Pokémon's top-recorded pick, moves default to its
    // top 4, all independently editable afterward (see makeDefaultSlot).
    // A new pick starts on its #1 real set (pokemon_set_variants, P1) when
    // it has one, otherwise on each slot's most common choice.
    var setsByKey = {};
    (marts.pokemon_set_variants || []).forEach(function (r) {
      if (r.set_level !== "full") return;
      (setsByKey[r.pokemon_key] = setsByKey[r.pokemon_key] || []).push(r);
    });
    Object.keys(setsByKey).forEach(function (key) {
      setsByKey[key].sort(function (a, b) { return a.set_rank - b.set_rank; });
    });

    function slotFromSet(key, set) {
      return {
        key: key,
        item: set.item_name || null,
        ability: set.ability || null,
        nature: set.nature || null,
        moves: String(set.moves || "").split("|").filter(Boolean),
      };
    }

    function makeDefaultSlot(key, setIndex) {
      var sets = setsByKey[key] || [];
      var set = sets[setIndex || 0] || sets[0];
      if (set) return slotFromSet(key, set);
      var topItem = sortByUsageRank(itemsByKey[key])[0];
      var topAbility = sortByUsageRank(abilitiesByKey[key])[0];
      var topNature = sortByUsageRank(naturesByKey[key])[0];
      var topMoves = sortByUsageRank(movesByKey[key]).slice(0, MOVE_SLOT_COUNT);
      return {
        key: key,
        item: topItem ? topItem.item_name : null,
        ability: topAbility ? topAbility.ability : null,
        nature: topNature ? topNature.nature : null,
        moves: topMoves.map(function (m) {
          return m.move_name;
        }),
      };
    }

    // Accepts either a bare pokemon_key (old localStorage format, or a
    // gallery/pokepaste caller that only has a species) or an already-built
    // slot object, and returns a valid slot or null if the key isn't
    // (or is no longer) in the legal pool.
    function normalizeEntry(entry) {
      if (typeof entry === "string") {
        return byKey[entry] ? makeDefaultSlot(entry) : null;
      }
      if (!entry || !byKey[entry.key]) return null;
      return {
        key: entry.key,
        item: entry.item || null,
        ability: entry.ability || null,
        nature: entry.nature || null,
        moves: (entry.moves || []).slice(0, MOVE_SLOT_COUNT),
      };
    }

    var team = [];
    try {
      var saved = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || "[]");
      team = saved.map(normalizeEntry).filter(Boolean).slice(0, MAX_TEAM_SIZE);
    } catch (e) {
      team = [];
    }

    var searchInput = document.getElementById("team-builder-search");
    var sortSelect = document.getElementById("team-builder-sort");
    var typeFilterEl = document.getElementById("team-builder-type-filter");
    var availableList = document.getElementById("team-builder-available");
    var slotsEl = document.getElementById("team-builder-slots");
    var countEl = document.getElementById("team-builder-count");
    var speedOrderEl = document.getElementById("team-builder-speed-order");
    var summaryEl = document.getElementById("team-builder-summary");
    var clearBtn = document.getElementById("team-builder-clear");
    var exportBtn = document.getElementById("team-builder-export");
    var exportOutput = document.getElementById("team-builder-export-output");
    var shareBtnEl = document.getElementById("team-builder-share");
    var analysisSummaryEl = document.getElementById("team-analysis-summary");
    var analysisDefenseTable = document.getElementById("team-analysis-defense-table");
    var analysisThreatTable = document.getElementById("team-analysis-threat-table");
    var analysisNoteEl = document.getElementById("team-analysis-note");
    var selectedTypes = {};

    function typeMultiplier(attackType, defendTypes) {
      return App.typeEffectiveness
        ? App.typeEffectiveness(attackType, defendTypes)
        : 1;
    }

    function offensiveMoves(slot) {
      var selected = (slot.moves || []).filter(Boolean);
      return (movesByKey[slot.key] || []).filter(function (move, index, rowsForPokemon) {
        return (
          selected.indexOf(move.move_name) !== -1 &&
          move.category !== "status" &&
          Number(move.power || 0) > 0 &&
          rowsForPokemon.findIndex(function (candidate) {
            return candidate.move_name === move.move_name;
          }) === index
        );
      });
    }

    function teamMembers() {
      return team.map(function (slot) {
        return { slot: slot, profile: byKey[slot.key], moves: offensiveMoves(slot) };
      }).filter(function (member) {
        return member.profile;
      });
    }

    function typeLabel(type) {
      return type ? type.charAt(0).toUpperCase() + type.slice(1) : "—";
    }

    function renderAnalysis() {
      if (!analysisSummaryEl) return;
      var members = teamMembers();
      if (!members.length) {
        analysisSummaryEl.innerHTML = '<p class="empty-state">Add Pokémon to see coverage, weakness, and threat checks.</p>';
        if (analysisDefenseTable) analysisDefenseTable.querySelector("tbody").innerHTML = "";
        if (analysisThreatTable) analysisThreatTable.querySelector("tbody").innerHTML = "";
        if (analysisNoteEl) analysisNoteEl.textContent = "";
        return;
      }

      var coveredTypes = App.ALL_TYPES.filter(function (defendType) {
        return members.some(function (member) {
          return member.moves.some(function (move) {
            return typeMultiplier(move.move_type, [defendType]) > 1;
          });
        });
      });
      var defensiveRows = App.ALL_TYPES.map(function (attackType) {
        var weak = 0;
        var resistOrImmune = 0;
        members.forEach(function (member) {
          var multiplier = typeMultiplier(attackType, [member.profile.type_1, member.profile.type_2]);
          if (multiplier > 1) weak += 1;
          if (multiplier < 1) resistOrImmune += 1;
        });
        return { type: attackType, weak: weak, resistOrImmune: resistOrImmune };
      }).filter(function (row) {
        return row.weak > 0;
      }).sort(function (a, b) {
        return b.weak - a.weak || a.resistOrImmune - b.resistOrImmune;
      });
      var speeds = members.map(function (member) { return Number(member.profile.speed || 0); });
      var fastest = Math.max.apply(null, speeds);
      var slowest = Math.min.apply(null, speeds);
      var speedTools = {};
      members.forEach(function (member) {
        (movesByKey[member.slot.key] || []).forEach(function (move) {
          var effect = String(move.short_effect || "").toLowerCase();
          if (Number(move.priority || 0) > 0 || /speed|tailwind|trick room|priority/.test(effect)) {
            speedTools[move.move_name] = true;
          }
        });
      });

      var threatRows = sortByUsageRank(rows).slice(0, 12).map(function (threat) {
        var threatTypes = [threat.type_1, threat.type_2].filter(Boolean);
        var threatMoveTypes = (movesByKey[threat.pokemon_key] || []).filter(function (move) {
          return move.category !== "status" && Number(move.power || 0) > 0 && move.move_type;
        });
        var answers = members.filter(function (member) {
          return member.moves.some(function (move) {
            return typeMultiplier(move.move_type, threatTypes) > 1;
          });
        }).length;
        var exposed = members.filter(function (member) {
          return threatMoveTypes.some(function (move) {
            return typeMultiplier(move.move_type, [member.profile.type_1, member.profile.type_2]) > 1;
          });
        }).length;
        return { threat: threat, answers: answers, exposed: exposed };
      });

      analysisSummaryEl.innerHTML =
        '<div class="analysis-card"><strong>' + coveredTypes.length + "/" + App.ALL_TYPES.length +
        '</strong><span>defending types hit super-effectively</span></div>' +
        '<div class="analysis-card"><strong>' + (defensiveRows[0] ? defensiveRows[0].weak + "/" + members.length : "0") +
        '</strong><span>members exposed to the biggest shared weakness</span></div>' +
        '<div class="analysis-card"><strong>' + fastest + "–" + slowest +
        '</strong><span>base Speed range</span></div>' +
        '<div class="analysis-card"><strong>' + Object.keys(speedTools).length +
        '</strong><span>recorded speed / priority tools</span></div>';

      if (analysisDefenseTable) {
        var defenseBody = analysisDefenseTable.querySelector("tbody");
        defenseBody.innerHTML = defensiveRows.slice(0, 8).map(function (row) {
          var cls = row.weak >= Math.max(2, Math.ceil(members.length / 2)) ? "status-warn" : "";
          return '<tr><td>' + App.escapeHtml(typeLabel(row.type)) + "</td><td class=\"" + cls + "\">" +
            row.weak + " / " + members.length + "</td><td>" + row.resistOrImmune + " / " + members.length + "</td></tr>";
        }).join("") || '<tr><td colspan="3">No shared weaknesses detected.</td></tr>';
      }
      if (analysisThreatTable) {
        var threatBody = analysisThreatTable.querySelector("tbody");
        threatBody.innerHTML = threatRows.map(function (row) {
          var cls = row.answers === 0 || row.exposed >= Math.max(2, Math.ceil(members.length / 2)) ? "status-warn" : "status-good";
          return '<tr><td>' + App.escapeHtml(row.threat.pokemon_name) + "</td><td class=\"" + cls + "\">" +
            row.answers + " / " + members.length + "</td><td>" + row.exposed + " / " + members.length + "</td></tr>";
        }).join("");
      }
      if (analysisNoteEl) {
        analysisNoteEl.textContent =
          "Coverage checks selected recorded damaging moves against single defending types. Threat exposure uses the threat Pokémon's recorded damaging move types; it is a screening heuristic, not a full moveset or battle simulation.";
      }
    }

    function persist() {
      try {
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify(team));
      } catch (e) {
        // localStorage unavailable (private browsing, etc.) — the team
        // just won't survive a reload; not fatal.
      }
    }

    function addSlot(slot) {
      var normalized = normalizeEntry(slot);
      if (!normalized) {
        showNotice((App.pokemonNames[slot.key] || slot.key) + " isn't legal in " +
          App.shortRegulation(App.regulationScope) + ".", false);
        return;
      }
      var existing = team.map(function (s) { return s.key; }).indexOf(normalized.key);
      if (existing !== -1) {
        team[existing] = normalized;
      } else if (team.length >= MAX_TEAM_SIZE) {
        showNotice("Your team is full. Remove a Pokémon to add " + App.pokemonNames[normalized.key] + ".", false);
        return;
      } else {
        team.push(normalized);
      }
      persist();
      renderAll();
      showNotice("Added " + App.pokemonNames[normalized.key] + " with its set.", false);
    }

    function addToTeam(key) {
      if (team.length >= MAX_TEAM_SIZE || team.some(function (s) { return s.key === key; }) || !byKey[key]) return;
      team.push(makeDefaultSlot(key));
      persist();
      renderAll();
    }

    function removeFromTeam(key) {
      team = team.filter(function (s) {
        return s.key !== key;
      });
      persist();
      renderAll();
    }

    function loadTeam(entries) {
      team = entries.map(normalizeEntry).filter(Boolean).slice(0, MAX_TEAM_SIZE);
      persist();
      renderAll();
    }

    // Replaces the team from a link (a real team, a converged list, a
    // shared team), saying what was loaded and offering to undo it. Slots
    // outside this regulation's legal pool are skipped and counted.
    var noticeEl = document.getElementById("team-builder-notice");
    var previousTeam = null;
    function replaceTeam(entries, message) {
      previousTeam = team.slice();
      var kept = entries.map(normalizeEntry).filter(Boolean).slice(0, MAX_TEAM_SIZE);
      var skipped = entries.length - kept.length;
      team = kept;
      persist();
      renderAll();
      showNotice(
        message + (skipped ? " " + skipped + " Pokémon not legal in " +
          App.shortRegulation(App.regulationScope) + " were skipped." : ""),
        previousTeam.length > 0
      );
    }
    function showNotice(message, undoable) {
      if (!noticeEl) return;
      noticeEl.innerHTML = App.escapeHtml(message) +
        (undoable ? ' <button type="button" class="btn btn-sm" data-undo-load>Undo</button>' : "");
      noticeEl.hidden = false;
    }
    if (noticeEl) {
      noticeEl.addEventListener("click", function (e) {
        if (!e.target.closest("[data-undo-load]") || !previousTeam) return;
        team = previousTeam;
        previousTeam = null;
        persist();
        renderAll();
        noticeEl.textContent = "Restored your previous team.";
      });
    }

    function renderAvailable() {
      if (!availableList) return;
      var query = ((searchInput && searchInput.value) || "").trim().toLowerCase();
      var sortBy = sortSelect ? sortSelect.value : "usage";
      var teamKeys = team.map(function (s) {
        return s.key;
      });
      var candidates = rows.filter(function (r) {
        if (teamKeys.indexOf(r.pokemon_key) !== -1) return false;
        if (r.pokemon_name.toLowerCase().indexOf(query) === -1) return false;
        if (!App.passesTypeFilter(selectedTypes, r.type_1, r.type_2)) return false;
        return true;
      });
      candidates.sort(function (a, b) {
        if (sortBy === "win_rate") return (b.win_rate || 0) - (a.win_rate || 0);
        if (sortBy === "speed") return (b.speed || 0) - (a.speed || 0);
        return (b.usage_count || 0) - (a.usage_count || 0);
      });
      var full = team.length >= MAX_TEAM_SIZE;
      availableList.innerHTML = "";
      candidates.slice(0, 50).forEach(function (r) {
        var li = document.createElement("li");
        li.className = "roster-item";
        li.innerHTML =
          App.spriteImg(r.pokemon_key, App.ICON_SIZES.md) +
          '<div class="roster-info"><div class="roster-name">' + App.escapeHtml(r.pokemon_name) + "</div>" +
          '<div class="roster-sub">' + App.formatPercent(r.usage_share) + " usage · " +
          App.formatPercent(r.win_rate) + " win rate · " + (r.speed != null ? r.speed : "—") + " speed</div></div>" +
          '<button class="btn btn-sm" type="button"' + (full ? " disabled" : "") + ">Add</button>";
        li.querySelector("button").addEventListener("click", function () {
          addToTeam(r.pokemon_key);
        });
        availableList.appendChild(li);
      });
      if (!candidates.length) {
        var empty = document.createElement("li");
        empty.className = "roster-item";
        empty.textContent = "No Pokémon match your search/filters.";
        availableList.appendChild(empty);
      }
    }

    // Builds a <select> whose options are `values`, always including
    // `current` even if it falls outside that list (e.g. a pasted
    // move/item outside the top-N recorded cap) so an edited/imported
    // build never silently loses its chosen value. Fires onChange(value)
    // (null for the blank option) on change.
    function buildChoiceSelect(values, current, blankLabel, emptyLabel, onChange) {
      var select = document.createElement("select");
      var effectiveValues = values.slice();
      if (current && effectiveValues.indexOf(current) === -1) effectiveValues.unshift(current);
      if (!effectiveValues.length) {
        select.disabled = true;
        var placeholder = document.createElement("option");
        placeholder.textContent = emptyLabel;
        select.appendChild(placeholder);
        return select;
      }
      var blank = document.createElement("option");
      blank.value = "";
      blank.textContent = blankLabel;
      select.appendChild(blank);
      effectiveValues.forEach(function (v) {
        var opt = document.createElement("option");
        opt.value = v;
        opt.textContent = v;
        select.appendChild(opt);
      });
      select.value = current || "";
      select.addEventListener("change", function () {
        onChange(select.value || null);
      });
      return select;
    }

    // A named helper (rather than inline logic in renderSlots' for loop)
    // so each slot's remove handler closes over its own `key` — a `var`
    // declared inside a for-loop body is function-scoped, not
    // block-scoped, so handlers built directly in the loop would all end
    // up capturing the loop's final value instead of their own slot's.
    function buildSlotElement(slot) {
      var el = document.createElement("div");
      if (!slot || !byKey[slot.key]) {
        el.className = "team-slot empty";
        el.textContent = "Empty slot";
        return el;
      }
      var key = slot.key;
      var r = byKey[key];
      el.className = "team-slot";
      // A filled slot is an --icon-lg hero box, so it takes the HOME
      // render rather than the upscaled menu sprite. Its type emblems sit
      // top-right, so the team's type spread reads across the slots.
      var emblems = App.typeIconsHtml(r.type_1, r.type_2);
      el.innerHTML =
        (emblems ? '<div class="slot-head">' + emblems + "</div>" : "") +
        App.heroImg(key, App.ICON_SIZES.lg) +
        '<div class="slot-name">' + App.escapeHtml(r.pokemon_name) + "</div>" +
        '<div class="slot-detail">HP ' + r.hp + " Atk " + r.attack + " Def " + r.defense +
        " SpA " + r.sp_attack + " SpD " + r.sp_defense + " Spe " + r.speed + "</div>";

      var itemOptions = sortByUsageRank(itemsByKey[key])
        .slice(0, ITEM_OPTION_CAP)
        .map(function (it) {
          return it.item_name;
        });
      var itemSelect = buildChoiceSelect(
        itemOptions,
        slot.item,
        "No item",
        "No recorded items",
        function (value) {
          slot.item = value;
          persist();
        }
      );
      itemSelect.setAttribute("aria-label", "Held item");
      el.appendChild(itemSelect);

      var abilityOptions = sortByUsageRank(abilitiesByKey[key])
        .slice(0, ABILITY_OPTION_CAP)
        .map(function (ab) {
          return ab.ability;
        });
      var abilitySelect = buildChoiceSelect(
        abilityOptions,
        slot.ability,
        "No ability",
        "No recorded ability",
        function (value) {
          slot.ability = value;
          persist();
        }
      );
      abilitySelect.setAttribute("aria-label", "Ability");
      el.appendChild(abilitySelect);

      var natureOptions = sortByUsageRank(naturesByKey[key])
        .slice(0, ABILITY_OPTION_CAP)
        .map(function (n) {
          return n.nature;
        });
      var natureSelect = buildChoiceSelect(
        natureOptions,
        slot.nature,
        "No nature",
        "No recorded nature",
        function (value) {
          slot.nature = value;
          persist();
        }
      );
      natureSelect.setAttribute("aria-label", "Nature");
      el.appendChild(natureSelect);

      var movePool = sortByUsageRank(movesByKey[key])
        .slice(0, MOVE_OPTION_CAP)
        .map(function (m) {
          return m.move_name;
        });
      if (movePool.length || slot.moves.some(Boolean)) {
        var moveContainer = document.createElement("div");
        moveContainer.className = "slot-move-selects";
        for (var i = 0; i < MOVE_SLOT_COUNT; i++) {
          (function (moveIndex) {
            var current = slot.moves[moveIndex] || "";
            // Exclude moves already picked in this slot's other move
            // selects, so the same move can't be chosen twice — real
            // Pokémon Champions movesets can't repeat a move either.
            var chosenElsewhere = slot.moves.filter(function (m, idx) {
              return idx !== moveIndex && m;
            });
            var available = movePool.filter(function (m) {
              return chosenElsewhere.indexOf(m) === -1;
            });
            var moveSelect = buildChoiceSelect(
              available,
              current,
              "— Move " + (moveIndex + 1) + " —",
              "No recorded moves",
                function (value) {
                  slot.moves[moveIndex] = value || "";
                  persist();
                  renderSlots();
                  renderAnalysis();
                }
            );
            moveSelect.setAttribute("aria-label", "Move " + (moveIndex + 1));
            moveContainer.appendChild(moveSelect);
          })(i);
        }
        el.appendChild(moveContainer);
      } else {
        var noMoves = document.createElement("div");
        noMoves.className = "slot-detail";
        noMoves.textContent = "No recorded moves";
        el.appendChild(noMoves);
      }

      var removeBtn = document.createElement("button");
      removeBtn.className = "btn-remove";
      removeBtn.type = "button";
      removeBtn.setAttribute("aria-label", "Remove " + r.pokemon_name);
      removeBtn.textContent = "Remove";
      removeBtn.addEventListener("click", function () {
        removeFromTeam(key);
      });
      el.appendChild(removeBtn);

      return el;
    }

    function renderSlots() {
      if (!slotsEl) return;
      slotsEl.innerHTML = "";
      for (var i = 0; i < MAX_TEAM_SIZE; i++) {
        slotsEl.appendChild(buildSlotElement(team[i]));
      }
      if (countEl) countEl.textContent = String(team.length);
      if (clearBtn) clearBtn.disabled = team.length === 0;
      if (exportBtn) exportBtn.disabled = team.length === 0;
      if (shareBtnEl) shareBtnEl.disabled = team.length === 0;
    }

    function renderSpeedOrder() {
      if (!speedOrderEl) return;
      var members = team
        .map(function (slot) {
          return byKey[slot.key];
        })
        .filter(Boolean)
        .sort(function (a, b) {
          return (b.speed || 0) - (a.speed || 0);
        });
      speedOrderEl.innerHTML = "";
      if (!members.length) {
        var li = document.createElement("li");
        li.textContent = "Add Pokémon to your team to see their speed order.";
        speedOrderEl.appendChild(li);
        return;
      }
      members.forEach(function (r) {
        var row = document.createElement("li");
        row.innerHTML =
          App.spriteImg(r.pokemon_key, App.ICON_SIZES.sm) +
          "<span>" + App.escapeHtml(r.pokemon_name) + "</span>" +
          App.speedTierBadge(r.speed) +
          '<span class="speed-value">' + r.speed + "</span>";
        speedOrderEl.appendChild(row);
      });
    }

    function renderSummary() {
      if (!summaryEl) return;
      var members = team
        .map(function (slot) {
          return byKey[slot.key];
        })
        .filter(Boolean);
      function avg(field) {
        var values = members
          .map(function (r) {
            return r[field];
          })
          .filter(function (v) {
            return v !== null && v !== undefined;
          });
        if (!values.length) return null;
        return (
          values.reduce(function (sum, v) {
            return sum + v;
          }, 0) / values.length
        );
      }
      var avgSpeed = avg("speed");
      summaryEl.innerHTML =
        '<div class="stat"><strong>' + (avgSpeed !== null ? Math.round(avgSpeed) : "—") + "</strong>Avg. speed</div>" +
        '<div class="stat"><strong>' + App.formatPercent(avg("usage_share")) + "</strong>Avg. usage share</div>" +
        '<div class="stat"><strong>' + App.formatPercent(avg("win_rate")) + "</strong>Avg. win rate</div>";
    }

    // Suggested partners (docs/upgrade-plan-2026q4.md, B9): candidates
    // ranked by how many current picks they have a synergy row with
    // (pokemon_team_synergy, already floored at a minimum pair count and
    // scoped to the page's regulation), then by average lift with them.
    // Lift, not raw co-occurrence, so the list isn't just "the most popular
    // Pokémon" again.
    var synergyByKey = {};
    (marts.pokemon_team_synergy || []).forEach(function (r) {
      (synergyByKey[r.pokemon_key] = synergyByKey[r.pokemon_key] || []).push(r);
    });
    var suggestionsEl = document.getElementById("team-builder-suggestions");
    var MAX_SUGGESTIONS = 6;

    function renderSuggestions() {
      if (!suggestionsEl) return;
      if (!team.length) {
        suggestionsEl.innerHTML = '<p class="empty-state">Add a Pokémon to see who pairs well with it.</p>';
        return;
      }
      if (team.length >= MAX_TEAM_SIZE) {
        suggestionsEl.innerHTML = '<p class="empty-state">Your team is full.</p>';
        return;
      }
      var onTeam = {};
      team.forEach(function (slot) { onTeam[slot.key] = true; });
      var candidates = {};
      team.forEach(function (slot) {
        (synergyByKey[slot.key] || []).forEach(function (r) {
          var key = r.partner_pokemon_key;
          if (onTeam[key] || !byKey[key] || !(r.lift > 1)) return;
          var c = candidates[key] || (candidates[key] = { key: key, lifts: [], with: [] });
          c.lifts.push(r.lift);
          c.with.push(slot.key);
        });
      });
      var ranked = Object.keys(candidates).map(function (key) {
        var c = candidates[key];
        c.avgLift = c.lifts.reduce(function (a, b) { return a + b; }, 0) / c.lifts.length;
        return c;
      }).sort(function (a, b) {
        return b.with.length - a.with.length || b.avgLift - a.avgLift;
      }).slice(0, MAX_SUGGESTIONS);
      if (!ranked.length) {
        suggestionsEl.innerHTML = '<p class="empty-state">Not enough recorded teams with these picks to suggest partners.</p>';
        return;
      }
      suggestionsEl.innerHTML = ranked.map(function (c) {
        var withNames = c.with.map(function (k) { return App.pokemonNames[k] || k; }).join(", ");
        return '<div class="suggestion">' + App.spriteImg(c.key, App.ICON_SIZES.sm) +
          '<div class="suggestion-body"><strong>' + App.escapeHtml(App.pokemonNames[c.key] || c.key) + "</strong>" +
          "<small>With " + App.escapeHtml(withNames) + " · lift " + c.avgLift.toFixed(1) + "×</small></div>" +
          '<button type="button" class="btn btn-sm" data-suggest="' + App.escapeHtml(c.key) + '">Add</button></div>';
      }).join("");
    }

    if (suggestionsEl) {
      suggestionsEl.addEventListener("click", function (e) {
        var btn = e.target.closest("[data-suggest]");
        if (btn) addToTeam(btn.getAttribute("data-suggest"));
      });
    }

    function renderAll() {
      if (typeof renderSaved === "function") renderSaved();
      renderAvailable();
      renderSlots();
      renderSpeedOrder();
      renderSummary();
      renderSuggestions();
      renderAnalysis();
      if (exportOutput) exportOutput.style.display = "none";
    }

    if (searchInput) searchInput.addEventListener("input", renderAvailable);
    if (sortSelect) sortSelect.addEventListener("change", renderAvailable);
    App.renderTypeFilterChips(typeFilterEl, selectedTypes, renderAvailable);
    if (clearBtn) {
      clearBtn.addEventListener("click", function () {
        team = [];
        persist();
        renderAll();
      });
    }
    if (exportBtn && exportOutput) {
      exportBtn.addEventListener("click", function () {
        exportOutput.value = exportTeamAsPokepaste(team);
        exportOutput.style.display = team.length ? "block" : "none";
        if (team.length) exportOutput.select();
      });
    }

    renderAll();

    // ---------- share links and saved teams (P4) ----------
    // A share link is #/builder/<key>.<set>,<key>.<set>,... with each set an
    // index into the Pokémon's real sets (pokemon_set_variants, exact level)
    // in the link's ?reg= regulation. A slot edited away from every real set
    // is shared as its key alone and opens on that Pokémon's #1 set.
    function sameSet(slot, set) {
      var a = (slot.moves || []).filter(Boolean).slice().sort().join("|");
      var b = String(set.moves || "").split("|").filter(Boolean).sort().join("|");
      return (slot.item || null) === (set.item_name || null) &&
        (slot.ability || null) === (set.ability || null) &&
        (slot.nature || null) === (set.nature || null) && a === b;
    }
    function shareToken(slot) {
      var sets = setsByKey[slot.key] || [];
      for (var i = 0; i < sets.length; i++) {
        if (sameSet(slot, sets[i])) return slot.key + "." + i;
      }
      return slot.key;
    }
    function shareUrl() {
      var params = new URLSearchParams(window.location.search);
      params.set("reg", App.regulationScope);
      return window.location.origin + window.location.pathname + "?" + params.toString() +
        App.routeHash("team-builder", [team.map(shareToken).join(",")]);
    }
    function slotsFromShareArg(arg) {
      return String(arg || "").split(",").filter(Boolean).map(function (token) {
        var dot = token.lastIndexOf(".");
        var key = dot > 0 ? token.slice(0, dot) : token;
        var index = dot > 0 ? parseInt(token.slice(dot + 1), 10) : 0;
        return byKey[key] ? makeDefaultSlot(key, isNaN(index) ? 0 : index) : { key: key };
      });
    }

    var shareBtn = document.getElementById("team-builder-share");
    if (shareBtn) {
      shareBtn.addEventListener("click", function () {
        if (!team.length) return;
        App.copyWithFallback(shareBtn, shareUrl(), "Link copied");
      });
    }

    var SAVED_KEY = "pokemonChampionsSavedTeams";
    var MAX_SAVED = 5;
    var savedList = document.getElementById("team-builder-saved");
    var savedNote = document.getElementById("team-builder-saved-note");
    var saveName = document.getElementById("team-builder-save-name");
    var saveBtn = document.getElementById("team-builder-save");
    function readSaved() {
      try {
        var list = JSON.parse(window.localStorage.getItem(SAVED_KEY) || "[]");
        return Array.isArray(list) ? list : [];
      } catch (e) {
        return [];
      }
    }
    function writeSaved(list) {
      try {
        window.localStorage.setItem(SAVED_KEY, JSON.stringify(list));
        return true;
      } catch (e) {
        return false;
      }
    }
    function renderSaved() {
      if (!savedList) return;
      var list = readSaved();
      savedList.innerHTML = list.map(function (entry, i) {
        return '<li><span class="saved-name">' + App.escapeHtml(entry.name) +
          '<span class="saved-meta">' + App.escapeHtml(App.shortRegulation(entry.reg || App.regulationScope)) + " · " +
          App.escapeHtml(String(entry.saved_on || "")) + "</span></span>" +
          App.teamCompositionHtml((entry.team || []).map(function (s) { return s.key; }).join("|"), 32) +
          '<button type="button" class="btn btn-sm" data-saved-load="' + i + '">Load</button>' +
          '<button type="button" class="btn-remove" data-saved-delete="' + i + '" aria-label="Delete ' +
          App.escapeHtml(entry.name) + '">Delete</button></li>';
      }).join("");
      if (saveBtn) saveBtn.disabled = !team.length;
    }
    if (saveBtn) {
      saveBtn.addEventListener("click", function () {
        var list = readSaved();
        if (!team.length) return;
        if (list.length >= MAX_SAVED) {
          if (savedNote) savedNote.textContent = "You have " + MAX_SAVED + " saved teams. Delete one to save another.";
          return;
        }
        var name = (saveName && saveName.value.trim()) || "Team " + (list.length + 1);
        list.push({
          name: name,
          reg: App.regulationScope,
          saved_on: new Date().toISOString().slice(0, 10),
          team: team.map(function (slot) {
            return { key: slot.key, item: slot.item, ability: slot.ability, nature: slot.nature, moves: slot.moves };
          }),
        });
        if (savedNote) {
          savedNote.textContent = writeSaved(list)
            ? "Saved “" + name + "”."
            : "This browser won't store teams (private mode?), so it wasn't saved.";
        }
        if (saveName) saveName.value = "";
        renderSaved();
      });
    }
    if (savedList) {
      savedList.addEventListener("click", function (e) {
        var load = e.target.closest("[data-saved-load]");
        var del = e.target.closest("[data-saved-delete]");
        var list = readSaved();
        if (load) {
          var entry = list[Number(load.getAttribute("data-saved-load"))];
          if (entry) replaceTeam(entry.team || [], "Loaded “" + entry.name + "”.");
        } else if (del) {
          var removed = list.splice(Number(del.getAttribute("data-saved-delete")), 1)[0];
          writeSaved(list);
          if (savedNote && removed) savedNote.textContent = "Deleted “" + removed.name + "”.";
          renderSaved();
        }
      });
    }
    renderSaved();

    return {
      addToTeam: addToTeam,
      loadTeam: loadTeam,
      replaceTeam: replaceTeam,
      slotsFromShareArg: slotsFromShareArg,
      addSlot: addSlot,
      renderSaved: renderSaved,
      showNotice: showNotice,
      makeDefaultSlot: makeDefaultSlot,
      team: function () { return team; },
    };
  }

  // Team Builder normally initializes lazily (on first tab activation,
  // like every other tab) — but a Top Teams pokepaste import or gallery
  // "Load into my builder" click can happen before that, so both paths
  // call this instead of the raw team-builder state, forcing init on
  // first use rather than assuming the tab was already visited.
  function ensureTeamBuilder() {
    if (!teamBuilderState) teamBuilderState = setupTeamBuilder();
    return teamBuilderState;
  }

  // ---------- Pro Team Gallery (curated real-team reference cards) ----------
  function renderProTeamGallery() {
    var container = document.getElementById("pro-team-gallery");
    if (!container) return;
    var teams = App.DATA.reference_teams || [];
    container.innerHTML = "";
    if (!teams.length) {
      container.innerHTML = '<p class="empty-state">No reference teams curated yet.</p>';
      return;
    }
    teams.forEach(function (team) {
      var card = document.createElement("div");
      card.className = "gallery-card";
      var img = team.card_image
        ? '<img class="gallery-card-image" src="' + team.card_image + '" alt="">'
        : "";
      var keys = team.pokemon_keys || [];
      card.innerHTML =
        img +
        '<div class="gallery-card-body">' +
        '<div class="gallery-card-player">' + App.escapeHtml(team.player_name || "Unknown player") +
        (team.country ? " (" + App.escapeHtml(team.country) + ")" : "") + "</div>" +
        '<div class="gallery-card-meta">' + App.escapeHtml(team.event_name || "") +
        (team.placement ? " · #" + team.placement : "") +
        (team.archetype_key ? " · " + App.escapeHtml(team.archetype_key) : "") + "</div>" +
        '<button class="btn btn-sm" type="button"' + (keys.length ? "" : " disabled") +
        ">Load into my builder</button></div>";
      var btn = card.querySelector("button");
      if (btn && keys.length) {
        btn.addEventListener("click", function () {
          var state = ensureTeamBuilder();
          keys.forEach(function (key) {
            state.addToTeam(key);
          });
        });
      }
      container.appendChild(card);
    });
  }

  // ---------- Top Teams (docs/upgrade-plan-2027q1.md, C2) ----------
  // Real top-cut teams as team cards: "1st · 9–2" is the headline and win
  // rate is secondary, ranked by placement within event tier by default
  // (a Worlds 1st above a regional 1st), with win rate as a sort option.
  // ?tier= in the route filters to one event tier. Every card has Copy for
  // Showdown and Use this team.
  var TOP_TEAMS_PAGE = 18;

  function setupTopTeams() {
    var events = App.eventsById();
    var tierSelect = document.getElementById("top-teams-tier");
    var sortSelect = document.getElementById("top-teams-sort");
    var grid = document.getElementById("top-teams-grid");
    var moreBtn = document.getElementById("top-teams-more");
    var note = document.getElementById("top-teams-note");
    var shown = TOP_TEAMS_PAGE;
    var inScope = {};
    App.eventsInScope().forEach(function (e) { inScope[e.event_id] = true; });

    var teams = (marts.tournament_top_cut_teams || [])
      .filter(function (t) { return inScope[t.event_id]; })
      .map(function (t) {
        var event = events[t.event_id] || {};
        var team = {};
        for (var k in t) if (Object.prototype.hasOwnProperty.call(t, k)) team[k] = t[k];
        team.event_name = event.event_name;
        team.event_date = event.event_date;
        team.event_tier = event.event_tier;
        team.event_size = event.team_count || 0;
        return team;
      });

    var tiers = [];
    teams.forEach(function (t) {
      if (t.event_tier && tiers.indexOf(t.event_tier) === -1) tiers.push(t.event_tier);
    });
    tiers.sort(function (a, b) { return App.tierRank(a) - App.tierRank(b); });
    tiers.forEach(function (tier) {
      var opt = document.createElement("option");
      opt.value = tier.toLowerCase();
      opt.textContent = tier;
      tierSelect.appendChild(opt);
    });

    function ranked() {
      var tier = tierSelect.value;
      var list = teams.filter(function (t) {
        return !tier || String(t.event_tier || "").toLowerCase() === tier;
      });
      if (sortSelect.value === "win_rate") {
        return list.sort(function (a, b) {
          return (b.win_rate || 0) - (a.win_rate || 0) || (b.record_wins || 0) - (a.record_wins || 0) ||
            a.placement - b.placement;
        });
      }
      return list.sort(function (a, b) {
        return a.placement - b.placement ||
          App.tierRank(a.event_tier) - App.tierRank(b.event_tier) ||
          b.event_size - a.event_size ||
          String(b.event_date || "").localeCompare(String(a.event_date || ""));
      });
    }

    function draw() {
      var list = ranked();
      grid.innerHTML = list.length
        ? list.slice(0, shown).map(function (t) { return App.teamCardHtml(t); }).join("")
        : '<p class="empty-state">No top-cut teams in this regulation yet.</p>';
      moreBtn.hidden = list.length <= shown;
      moreBtn.textContent = "Show " + Math.min(TOP_TEAMS_PAGE, list.length - shown) + " more";
      if (note) {
        note.textContent = list.length + " top-16 teams from " +
          Object.keys(list.reduce(function (acc, t) { acc[t.event_id] = 1; return acc; }, {})).length +
          " events in " + App.shortRegulation(App.regulationScope) + ".";
      }
    }

    function recordRoute() {
      var route = App.currentRoute();
      App.setRoute("top-teams", route.args, {
        tier: tierSelect.value,
        sort: sortSelect.value === "win_rate" ? "win-rate" : "",
      });
    }
    tierSelect.addEventListener("change", function () { shown = TOP_TEAMS_PAGE; draw(); recordRoute(); });
    sortSelect.addEventListener("change", function () { shown = TOP_TEAMS_PAGE; draw(); recordRoute(); });
    moreBtn.addEventListener("click", function () { shown += TOP_TEAMS_PAGE; draw(); });

    topTeamsRoute = function (route) {
      var tier = String(route.query.tier || "").toLowerCase();
      var sort = route.query.sort === "win-rate" ? "win_rate" : "placement";
      var changed = false;
      if (tierSelect.value !== tier && (!tier || tierSelect.querySelector('option[value="' + tier + '"]'))) {
        tierSelect.value = tier;
        changed = true;
      }
      if (sortSelect.value !== sort) {
        sortSelect.value = sort;
        changed = true;
      }
      if (changed || !grid.innerHTML) draw();
      if (topTeamsSubTabs) topTeamsSubTabs.fromRoute(route);
    };
    draw();

    // Converged lists: whole compositions several players independently
    // brought (Limitless team_list layer), ranked by player_count -- the
    // point of the view is convergence, not placement.
    var convergedGrid = document.getElementById("converged-lists-grid");
    if (convergedGrid) {
      var converged = (marts.team_list_convergence || []).slice().sort(function (a, b) {
        return a.convergence_rank - b.convergence_rank;
      }).slice(0, TOP_TEAMS_PAGE);
      convergedGrid.innerHTML = converged.map(function (r) {
        var n = r.player_count || 0;
        var meta = [];
        if (r.best_placement) meta.push("best finish " + App.ordinal(r.best_placement));
        if (r.tournament_count) meta.push(r.tournament_count + (r.tournament_count === 1 ? " event" : " events"));
        if (r.first_seen_date) meta.push("first seen " + String(r.first_seen_date).slice(0, 10));
        return App.teamCardHtml(
          {
            pokemon_keys: r.pokemon_keys,
            sets: App.teamListSheet(r.team_list_id),
          },
          {
            headline: n + (n === 1 ? " player" : " players"),
            meta: meta.join(" · "),
            useHref: App.routeHash("team-builder", ["list", r.team_list_id]),
          }
        );
      }).join("") || '<p class="empty-state">No converged lists on record.</p>';
    }

    var ttSubtabs = document.querySelectorAll('[data-panel="top-teams"] .subtab-btn');
    var ttSubpanels = document.querySelectorAll('[data-panel="top-teams"] .subtab-panel');
    topTeamsSubTabs = App.setupSubTabs(ttSubtabs, ttSubpanels, null, {
      route: { tab: "top-teams", argIndex: 0 },
    });

    renderProTeamGallery();
  }
  var topTeamsSubTabs = null;
  var topTeamsRoute = function () {};

  // The pokepaste import sits in the Builder (docs/upgrade-plan-2027q1.md,
  // U7): importing a team is building one, not browsing Top Teams.
  function setupPokepasteImport() {
    var input = document.getElementById("pokepaste-input");
    var loadBtn = document.getElementById("pokepaste-load");
    var statusEl = document.getElementById("pokepaste-status");
    if (!loadBtn || !input) return;
    loadBtn.addEventListener("click", function () {
      var parsed = parsePokepaste(input.value || "");
      if (!parsed.resolvedSlots.length) {
        if (statusEl) statusEl.textContent = "No recognizable Pokémon found in that paste.";
        return;
      }
      ensureTeamBuilder().loadTeam(parsed.resolvedSlots);
      if (statusEl) {
        statusEl.textContent =
          "Loaded " + parsed.resolvedSlots.length + " Pokémon into Team Builder" +
          (parsed.unresolvedNames.length
            ? " (" + parsed.unresolvedNames.length + " not recognized: " + parsed.unresolvedNames.join(", ") + ")"
            : ".");
      }
    });
  }

  // #/builder/team/<team_id> and #/builder/list/<team_list_id> load a real
  // tournament team or a converged Limitless list, with the sets as
  // published (docs/upgrade-plan-2027q1.md, C2/P4). Once loaded, the
  // address goes back to #/builder, so a reload doesn't overwrite edits.
  function loadFromRoute(route) {
    var kind = route.args[0];
    var id = route.args[1];
    if (kind === "add" && id) {
      // #/builder/add/<key>.<set>: a profile's "Open in Builder" adds that
      // real set to the current team (replacing the Pokémon if it's
      // already on it) rather than replacing the team.
      var adder = ensureTeamBuilder();
      App.setRoute("team-builder", [], {});
      var slot = adder.slotsFromShareArg(id)[0];
      if (slot) adder.addSlot(slot);
      return;
    }
    if (kind && kind !== "team" && kind !== "list") {
      // A share link: #/builder/<key>.<set>,... (P4).
      var shared = ensureTeamBuilder();
      App.setRoute("team-builder", [], {});
      shared.replaceTeam(shared.slotsFromShareArg(kind), "Loaded a shared team.");
      return;
    }
    if (!kind || !id) return;
    var mart = kind === "team" ? "tournament_team_sheets" : "team_list_sheets";
    App.ensureData([mart]).then(function () {
      var state = ensureTeamBuilder();
      var sheet = kind === "team" ? App.teamSheet(id) : App.teamListSheet(id);
      App.setRoute("team-builder", [], {});
      if (!sheet) {
        state.showNotice("That team's sheet isn't in this dataset.", false);
        return;
      }
      var label = "Loaded a converged team list.";
      if (kind === "team") {
        var team = (marts.tournament_top_cut_teams || []).filter(function (t) { return t.team_id === id; })[0];
        var event = team ? App.eventsById()[team.event_id] : null;
        label = team
          ? "Loaded " + team.player_name + "'s team (" + App.ordinal(team.placement) +
            (event ? ", " + App.shortEventName(event.event_name) : "") + ")."
          : "Loaded a tournament team.";
      }
      state.replaceTeam(sheet.map(sheetToSlot), label);
    });
  }

  App.registerTab(
    "team-builder",
    function () {
      ensureTeamBuilder();
      setupPokepasteImport();
    },
    { onRoute: loadFromRoute }
  );
  App.registerTab("top-teams", setupTopTeams, {
    extraMarts: ["tournament_team_sheets", "team_list_sheets"],
    onRoute: function (route) {
      topTeamsRoute(route);
    },
  });
})();
