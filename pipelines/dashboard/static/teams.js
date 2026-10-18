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
      resolvedSlots.push({
        key: key,
        item: itemPart || null,
        ability: ability,
        moves: moves.slice(0, MOVE_SLOT_COUNT),
      });
    });
    return { resolvedSlots: resolvedSlots, unresolvedNames: unresolvedNames };
  }

  // Emits each slot's actually-chosen item/ability/moves (not just that
  // Pokémon's top-recorded build), so the pokepaste export reflects real
  // edits made in the builder.
  function exportTeamAsPokepaste(teamSlots) {
    var byKey = {};
    (marts.pokemon_champions_profile || []).forEach(function (r) {
      byKey[r.pokemon_key] = r;
    });
    var blocks = teamSlots
      .map(function (slot) {
        if (!byKey[slot.key]) return null;
        var name = keyToShowdownName(slot.key);
        var lines = [name + (slot.item ? " @ " + slot.item : "")];
        if (slot.ability) lines.push("Ability: " + slot.ability);
        (slot.moves || []).forEach(function (m) {
          if (m) lines.push("- " + m);
        });
        return lines.join("\n");
      })
      .filter(Boolean);
    return blocks.join("\n\n");
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
    var movesByKey = groupByPokemonKey(marts.pokemon_move_usage);

    var STORAGE_KEY = "pokemonChampionsTeamBuilder";
    var MAX_TEAM_SIZE = 6;

    // Slot shape: {key, item, ability, moves: string[]} — item/ability
    // default to that Pokémon's top-recorded pick, moves default to its
    // top 4, all independently editable afterward (see makeDefaultSlot).
    function makeDefaultSlot(key) {
      var topItem = sortByUsageRank(itemsByKey[key])[0];
      var topAbility = sortByUsageRank(abilitiesByKey[key])[0];
      var topMoves = sortByUsageRank(movesByKey[key]).slice(0, MOVE_SLOT_COUNT);
      return {
        key: key,
        item: topItem ? topItem.item_name : null,
        ability: topAbility ? topAbility.ability : null,
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
      // render rather than the upscaled menu sprite, and carries its
      // Pokémon's type accent on the slot border.
      el.style.setProperty("--tile-accent", App.typeAccentGradient(r.type_1, r.type_2));
      el.classList.add("has-type-accent");
      el.innerHTML =
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

    function renderAll() {
      renderAvailable();
      renderSlots();
      renderSpeedOrder();
      renderSummary();
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

    return { addToTeam: addToTeam, loadTeam: loadTeam };
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

  // ---------- Top Teams tab: real leaderboard + pokepaste import + gallery ----------
  function setupTopTeams() {
    var teamRows = marts.top_tournament_teams || [];
    var grid = document.getElementById("top-teams-grid");
    if (grid) {
      var ranked = teamRows.slice().sort(function (a, b) {
        return a.team_rank - b.team_rank;
      });
      App.renderGrid6xn(grid, ranked.slice(0, 18), {
        // The whole roster, not just slot 1: a team is six Pokémon, and
        // drawing it as one sprite misrepresented which team a tile is.
        iconHtmlFn: function (r) {
          return App.teamCompositionHtml(r.pokemon_keys);
        },
        labelFn: function (r) {
          return (r.player_name || "Unknown") + (r.event_name ? " · " + r.event_name : "");
        },
        displayFn: function (r) {
          return App.formatPercent(r.win_rate);
        },
        subFn: function (r) {
          // The names stay as the sub-line: the sprite row above is
          // scannable, but a sprite alone doesn't name a Pokémon, and the
          // per-slot title attribute isn't reachable on touch.
          var names = (r.pokemon_keys || "")
            .split("|")
            .map(function (key) {
              return App.pokemonNames[key] || key;
            })
            .join(", ");
          return names;
        },
      });
    }

    // Converged lists: whole compositions multiple players independently
    // brought (Limitless team_list layer). Ranked by player_count, which
    // is the point of the view -- convergence, not placement.
    var convergedGrid = document.getElementById("converged-lists-grid");
    if (convergedGrid) {
      var converged = (marts.team_list_convergence || []).slice().sort(function (a, b) {
        return a.convergence_rank - b.convergence_rank;
      });
      App.renderGrid6xn(convergedGrid, converged.slice(0, 18), {
        iconHtmlFn: function (r) {
          return App.teamCompositionHtml(r.pokemon_keys);
        },
        labelFn: function (r) {
          return (r.pokemon_keys || "")
            .split("|")
            .map(function (key) {
              return App.pokemonNames[key] || key;
            })
            .join(", ");
        },
        displayFn: function (r) {
          var n = r.player_count || 0;
          return n + (n === 1 ? " player" : " players");
        },
        subFn: function (r) {
          var parts = [];
          if (r.best_placement) parts.push("best finish #" + r.best_placement);
          if (r.tournament_count) {
            parts.push(
              r.tournament_count + (r.tournament_count === 1 ? " event" : " events")
            );
          }
          if (r.first_seen_date) parts.push("first seen " + String(r.first_seen_date).slice(0, 10));
          return parts.join(" · ");
        },
      });
    }

    var ttSubtabs = document.querySelectorAll('[data-panel="top-teams"] .subtab-btn');
    var ttSubpanels = document.querySelectorAll('[data-panel="top-teams"] .subtab-panel');
    App.setupSubTabs(ttSubtabs, ttSubpanels);

    var input = document.getElementById("pokepaste-input");
    var loadBtn = document.getElementById("pokepaste-load");
    var statusEl = document.getElementById("pokepaste-status");
    if (loadBtn && input) {
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

    renderProTeamGallery();
  }

  App.registerTab("team-builder", function () {
    ensureTeamBuilder();
  });
  App.registerTab("top-teams", setupTopTeams);
})();
