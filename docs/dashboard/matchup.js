/* Matchup tab: real head-to-head records, type effectiveness, teammate
 * co-usage, and a stats/setup/
 * weather-aware damage calculator (docs/design-system.md's "Matchup tab
 * components"). Loaded after app.js and reuses window.DashboardApp for
 * data/helpers rather than duplicating them.
 *
 * The 18x18 type chart, weather-boost multipliers, the level-50 stat
 * formula, and the curated item/ability toggle list below are universal
 * Pokémon game mechanics, not per-record dataset facts — they're hardcoded
 * constants here (the same treatment app.js's SPEED_TIERS bucketing
 * already gets), not something requiring extraction/provenance. Pokémon
 * *type* and move *power/accuracy/category* are real sourced data
 * (pokemon.type_1/type_2, move_detail — see docs/dataset-spec.md),
 * fetched from PokéAPI.
 *
 * Scope, documented rather than silently approximated: this calculator
 * assumes a level-50, IV 31 / EV 252 "maximally invested" stat on
 * whichever offensive/defensive stat the chosen move uses (no source
 * publishes real EV/IV data at all, so an "actual spread" calculation is
 * not available to build; see docs/data-sources.md's Victory Road entry),
 * models STAB, type
 * effectiveness, stat stages, rain/sun weather boosts, sand/snow's
 * Rock-SpDef/Ice-Def boosts, and a curated set of common competitive
 * items/abilities as flat multipliers. It does NOT model status
 * conditions (e.g. burn), critical hits, multi-hit moves, or any
 * item/ability outside the curated toggle list below. */
(function () {
  "use strict";

  var App = window.DashboardApp;
  if (!App) return;

  var marts = App.marts;
  var sprites = App.sprites;

  // ---------- type chart (standard Gen 6+ Pokémon type effectiveness) ----------
  // TYPE_CHART[attackType][defendType] = multiplier; unlisted pairs are 1x.
  var TYPE_CHART = {
    normal: { rock: 0.5, ghost: 0, steel: 0.5 },
    fire: { fire: 0.5, water: 0.5, grass: 2, ice: 2, bug: 2, rock: 0.5, dragon: 0.5, steel: 2 },
    water: { fire: 2, water: 0.5, grass: 0.5, ground: 2, rock: 2, dragon: 0.5 },
    electric: { water: 2, electric: 0.5, grass: 0.5, ground: 0, flying: 2, dragon: 0.5 },
    grass: { fire: 0.5, water: 2, grass: 0.5, poison: 0.5, ground: 2, flying: 0.5, bug: 0.5, rock: 2, dragon: 0.5, steel: 0.5 },
    ice: { fire: 0.5, water: 0.5, grass: 2, ice: 0.5, ground: 2, flying: 2, dragon: 2, steel: 0.5 },
    fighting: { normal: 2, ice: 2, poison: 0.5, flying: 0.5, psychic: 0.5, bug: 0.5, rock: 2, ghost: 0, dark: 2, steel: 2, fairy: 0.5 },
    poison: { grass: 2, poison: 0.5, ground: 0.5, rock: 0.5, ghost: 0.5, steel: 0, fairy: 2 },
    ground: { fire: 2, electric: 2, grass: 0.5, poison: 2, flying: 0, bug: 0.5, rock: 2, steel: 2 },
    flying: { electric: 0.5, grass: 2, fighting: 2, bug: 2, rock: 0.5, steel: 0.5 },
    psychic: { fighting: 2, poison: 2, psychic: 0.5, dark: 0, steel: 0.5 },
    bug: { fire: 0.5, grass: 2, fighting: 0.5, poison: 0.5, flying: 0.5, psychic: 2, ghost: 0.5, dark: 2, steel: 0.5, fairy: 0.5 },
    rock: { fire: 2, ice: 2, fighting: 0.5, ground: 0.5, flying: 2, bug: 2, steel: 0.5 },
    ghost: { normal: 0, psychic: 2, ghost: 2, dark: 0.5 },
    dragon: { dragon: 2, steel: 0.5, fairy: 0 },
    dark: { fighting: 0.5, psychic: 2, ghost: 2, dark: 0.5, fairy: 0.5 },
    steel: { fire: 0.5, water: 0.5, electric: 0.5, ice: 2, rock: 2, steel: 0.5, fairy: 2 },
    fairy: { fire: 0.5, fighting: 2, poison: 0.5, dragon: 2, dark: 2, steel: 0.5 },
  };

  function typeEffectiveness(attackType, defendTypes) {
    var chart = TYPE_CHART[attackType] || {};
    var multiplier = 1;
    defendTypes.filter(Boolean).forEach(function (t) {
      multiplier *= chart[t] === undefined ? 1 : chart[t];
    });
    return multiplier;
  }

  // Shared by Team Builder's Team Analyst. Keeping one chart implementation
  // prevents the dashboard's matchup and team-coverage screens from drifting.
  App.typeEffectiveness = typeEffectiveness;

  function effectClass(m) {
    if (m === 0) return "type-effect-0x";
    if (m === 0.25) return "type-effect-quarter";
    if (m === 0.5) return "type-effect-half";
    if (m === 1) return "type-effect-1x";
    if (m === 2) return "type-effect-2x";
    return "type-effect-4x";
  }

  // ---------- curated item/ability toggle list ----------
  var TOGGLES = [
    { id: "choice-band", label: "Choice Band" },
    { id: "choice-specs", label: "Choice Specs" },
    { id: "life-orb", label: "Life Orb" },
    { id: "expert-belt", label: "Expert Belt" },
    { id: "huge-power", label: "Huge Power / Pure Power" },
    { id: "adaptability", label: "Adaptability" },
    { id: "technician", label: "Technician" },
    { id: "intimidate", label: "Intimidate (on defender)" },
  ];

  // Presets (docs/upgrade-plan-2027q1.md, P3): the calculator starts each
  // side on its #1 real set (pokemon_set_variants), pre-selecting whichever
  // toggles that set's item and ability correspond to. The toggles stay
  // editable; picking another Pokémon re-applies its preset.
  var ITEM_TOGGLES = {
    "Choice Band": "choice-band",
    "Choice Specs": "choice-specs",
    "Life Orb": "life-orb",
    "Expert Belt": "expert-belt",
  };
  var ATTACKER_ABILITY_TOGGLES = {
    "Huge Power": "huge-power",
    "Pure Power": "huge-power",
    Adaptability: "adaptability",
    Technician: "technician",
  };

  function koVerdict(result) {
    if (result.lowPct >= 100) return "OHKO";
    if (result.highPct >= 100) return "Possible OHKO";
    if (result.lowPct >= 50) return "2HKO";
    if (result.highPct >= 50) return "Possible 2HKO";
    if (result.lowPct >= 100 / 3) return "3HKO";
    return "—";
  }

  // ---------- level-50 stat formula (IV 31 / EV 252 "maxed" baseline —
  // see the file-header scope note) ----------
  function statAtLevel50(base) {
    return Math.floor(Math.floor((2 * base + 31 + Math.floor(252 / 4)) * 50 / 100) + 5);
  }
  function hpAtLevel50(base) {
    return Math.floor((2 * base + 31 + Math.floor(252 / 4)) * 50 / 100) + 50 + 10;
  }
  function stageMultiplier(stage) {
    stage = Math.max(-6, Math.min(6, stage || 0));
    return stage >= 0 ? (2 + stage) / 2 : 2 / (2 - stage);
  }

  function computeDamage(params) {
    var move = params.move;
    if (!move || !move.power) return null;
    var category = move.category === "special" ? "special" : "physical";
    var atkBase = category === "special" ? params.attacker.sp_attack : params.attacker.attack;
    var defBase = category === "special" ? params.defender.sp_defense : params.defender.defense;

    var atkStage = category === "special" ? params.attackerStages.spa : params.attackerStages.atk;
    var defStage = category === "special" ? params.defenderStages.spd : params.defenderStages.def;
    if (params.toggles["intimidate"] && category === "physical") atkStage -= 1;

    var atkStat = statAtLevel50(atkBase) * stageMultiplier(atkStage);
    if (params.toggles["huge-power"] && category === "physical") atkStat *= 2;

    var defStat = statAtLevel50(defBase) * stageMultiplier(defStage);
    var defenderTypes = [params.defender.type_1, params.defender.type_2].filter(Boolean);
    if (params.weather === "sand" && category === "special" && defenderTypes.indexOf("rock") !== -1) defStat *= 1.5;
    if (params.weather === "snow" && category === "physical" && defenderTypes.indexOf("ice") !== -1) defStat *= 1.5;

    var base = (2 * 50 / 5 + 2) * move.power * (atkStat / defStat) / 50 + 2;

    var attackerTypes = [params.attacker.type_1, params.attacker.type_2].filter(Boolean);
    var stab = attackerTypes.indexOf(move.move_type) !== -1 ? (params.toggles["adaptability"] ? 2 : 1.5) : 1;
    var effectiveness = typeEffectiveness(move.move_type, defenderTypes);

    var weatherMod = 1;
    if (params.weather === "rain") {
      if (move.move_type === "water") weatherMod = 1.5;
      if (move.move_type === "fire") weatherMod = 0.5;
    } else if (params.weather === "sun") {
      if (move.move_type === "fire") weatherMod = 1.5;
      if (move.move_type === "water") weatherMod = 0.5;
    }

    var itemMod = 1;
    if (params.toggles["choice-band"] && category === "physical") itemMod *= 1.5;
    if (params.toggles["choice-specs"] && category === "special") itemMod *= 1.5;
    if (params.toggles["life-orb"]) itemMod *= 1.3;
    if (params.toggles["expert-belt"] && effectiveness > 1) itemMod *= 1.2;
    if (params.toggles["technician"] && move.power <= 60) itemMod *= 1.5;

    var multiplier = stab * effectiveness * weatherMod * itemMod;
    var low = Math.floor(base * multiplier * 0.85);
    var high = Math.floor(base * multiplier);
    var defenderHp = hpAtLevel50(params.defender.hp);

    return {
      low: low,
      high: high,
      lowPct: (low / defenderHp) * 100,
      highPct: (high / defenderHp) * 100,
      effectiveness: effectiveness,
      stab: stab,
      category: category,
    };
  }

  // Visible HP/Atk/Def/SpA/SpD/Spe stat line for a matchup-side panel —
  // the damage calculator already uses these stats (level-50 formula,
  // hpAtLevel50() for the %-of-HP result) but previously didn't surface
  // them anywhere in the UI, only the derived percentage.
  function statLine(pokemon) {
    if (!pokemon) return "";
    return (
      "HP " + pokemon.hp + " Atk " + pokemon.attack + " Def " + pokemon.defense +
      " SpA " + pokemon.sp_attack + " SpD " + pokemon.sp_defense + " Spe " + pokemon.speed
    );
  }

  // ---------- tab wiring ----------
  function setupMatchup() {
    var profileRows = marts.pokemon_champions_profile || [];
    var moveRows = marts.pokemon_move_usage || [];
    var coreRows = marts.pokemon_team_core_usage || [];
    var h2hRows = marts.pokemon_head_to_head || [];
    var summaryByKey = {};
    (marts.pokemon_matchup_summary || []).forEach(function (r) {
      summaryByKey[r.pokemon_key] = r;
    });
    var byKey = {};
    profileRows.forEach(function (r) {
      byKey[r.pokemon_key] = r;
    });

    var attackerSelect = document.getElementById("matchup-attacker-select");
    var defenderSelect = document.getElementById("matchup-defender-select");
    var moveSelect = document.getElementById("matchup-move-select");
    var weatherSelect = document.getElementById("matchup-weather");
    var attackerTypeEl = document.getElementById("matchup-attacker-type");
    var defenderTypeEl = document.getElementById("matchup-defender-type");
    var attackerStatsEl = document.getElementById("matchup-attacker-stats");
    var defenderStatsEl = document.getElementById("matchup-defender-stats");
    var moveDescEl = document.getElementById("matchup-move-desc");
    var attackerStagesEl = document.getElementById("matchup-attacker-stages");
    var defenderStagesEl = document.getElementById("matchup-defender-stages");
    var toggleRowEl = document.getElementById("matchup-toggle-row");
    var resultEl = document.getElementById("matchup-damage-result");
    var typeGridEl = document.getElementById("matchup-type-grid");
    var coUsageGridEl = document.getElementById("matchup-co-usage-grid");
    var h2hGridEl = document.getElementById("matchup-h2h-grid");
    var h2hHeadlineEl = document.getElementById("matchup-h2h-headline");
    var summaryEl = document.getElementById("matchup-summary");
    if (!attackerSelect || !defenderSelect) return;

    var sortedProfiles = profileRows.slice().sort(function (a, b) {
      return (b.usage_share || 0) - (a.usage_share || 0);
    });
    // Values are pokemon_keys, the ids #/matchup/<attacker>/<defender> carries.
    var pairs = sortedProfiles.map(function (r) {
      return { value: r.pokemon_key, label: r.pokemon_name };
    });
    App.fillSelectPairs(attackerSelect, pairs);
    App.fillSelectPairs(defenderSelect, pairs);
    if (pairs.length) {
      attackerSelect.value = pairs[0].value;
      defenderSelect.value = pairs[Math.min(1, pairs.length - 1)].value;
    }

    var attackerStages = { atk: 0, spa: 0 };
    var defenderStages = { def: 0, spd: 0 };
    var toggles = {};
    var toggleChips = {};
    var topSetByKey = {};
    (marts.pokemon_set_variants || []).forEach(function (r) {
      if (r.set_level === "full" && r.set_rank === 1) topSetByKey[r.pokemon_key] = r;
    });
    var presetNoteEl = document.getElementById("matchup-preset-note");
    var metaEl = document.getElementById("matchup-meta");
    var defenderSideEl = document.getElementById("matchup-defender-side");
    var mode = "single";

    function syncToggleChips() {
      Object.keys(toggleChips).forEach(function (id) {
        toggleChips[id].setAttribute("aria-pressed", toggles[id] ? "true" : "false");
      });
    }

    function setSummary(pokemon) {
      var set = topSetByKey[pokemon.pokemon_key];
      return set
        ? App.escapeHtml(pokemon.pokemon_name) + " @ " + App.escapeHtml(set.item_name || "no item") +
          " (" + App.escapeHtml(set.ability || "—") + ")"
        : App.escapeHtml(pokemon.pokemon_name) + " (no complete set on record)";
    }

    function applyPresets() {
      var attacker = byKey[attackerSelect.value];
      var defender = byKey[defenderSelect.value];
      toggles = {};
      var attackerSet = attacker && topSetByKey[attacker.pokemon_key];
      if (attackerSet) {
        if (ITEM_TOGGLES[attackerSet.item_name]) toggles[ITEM_TOGGLES[attackerSet.item_name]] = true;
        if (ATTACKER_ABILITY_TOGGLES[attackerSet.ability]) toggles[ATTACKER_ABILITY_TOGGLES[attackerSet.ability]] = true;
      }
      var defenderSet = defender && topSetByKey[defender.pokemon_key];
      if (mode === "single" && defenderSet && defenderSet.ability === "Intimidate") toggles.intimidate = true;
      syncToggleChips();
      if (presetNoteEl) {
        presetNoteEl.innerHTML = attacker
          ? "Preset from each side's most common real set: " + setSummary(attacker) +
            (mode === "single" && defender ? "; " + setSummary(defender) : "") + ". Toggle anything to override."
          : "";
      }
    }

    function renderStageSliders(container, stages, keys) {
      container.innerHTML = "";
      keys.forEach(function (spec) {
        var row = document.createElement("div");
        row.className = "stage-row";
        var valueSpan = document.createElement("span");
        valueSpan.className = "stage-value";
        valueSpan.textContent = (stages[spec.key] > 0 ? "+" : "") + stages[spec.key];
        var label = document.createElement("label");
        label.textContent = spec.label;
        var input = document.createElement("input");
        input.type = "range";
        input.min = "-6";
        input.max = "6";
        input.value = String(stages[spec.key]);
        input.addEventListener("input", function () {
          stages[spec.key] = parseInt(input.value, 10);
          valueSpan.textContent = (stages[spec.key] > 0 ? "+" : "") + stages[spec.key];
          updateAll();
        });
        row.appendChild(label);
        row.appendChild(input);
        row.appendChild(valueSpan);
        container.appendChild(row);
      });
    }
    renderStageSliders(attackerStagesEl, attackerStages, [
      { key: "atk", label: "Atk" },
      { key: "spa", label: "SpA" },
    ]);
    renderStageSliders(defenderStagesEl, defenderStages, [
      { key: "def", label: "Def" },
      { key: "spd", label: "SpD" },
    ]);

    if (toggleRowEl) {
      toggleRowEl.innerHTML = "";
      TOGGLES.forEach(function (toggle) {
        var chip = document.createElement("button");
        chip.type = "button";
        chip.className = "toggle-chip";
        chip.setAttribute("aria-pressed", "false");
        chip.textContent = toggle.label;
        chip.addEventListener("click", function () {
          if (toggles[toggle.id]) {
            delete toggles[toggle.id];
          } else {
            toggles[toggle.id] = true;
          }
          chip.setAttribute("aria-pressed", toggles[toggle.id] ? "true" : "false");
          updateAll();
        });
        toggleChips[toggle.id] = chip;
        toggleRowEl.appendChild(chip);
      });
    }

    function refreshMoveOptions() {
      var attacker = byKey[attackerSelect.value];
      var moves = attacker
        ? moveRows
            .filter(function (r) {
              return r.pokemon_key === attacker.pokemon_key && r.category && r.category !== "status";
            })
            .sort(function (a, b) {
              return a.usage_rank - b.usage_rank;
            })
        : [];
      App.fillSelect(
        moveSelect,
        moves.map(function (r) {
          return r.move_name;
        }),
        "Select a move…"
      );
      moveSelect.removeChild(moveSelect.firstChild);
      if (moves.length) moveSelect.value = moves[0].move_name;
      return moves;
    }

    function drawTypeGrid(defender) {
      if (!typeGridEl) return;
      typeGridEl.innerHTML = "";
      if (!defender) return;
      var defenderTypes = [defender.type_1, defender.type_2].filter(Boolean);
      App.ALL_TYPES.forEach(function (attackType) {
        var multiplier = typeEffectiveness(attackType, defenderTypes);
        var tile = document.createElement("div");
        tile.className = "type-effect-tile " + effectClass(multiplier);
        tile.innerHTML = App.typeIconImg(attackType, 16) + " " + attackType + "<br>" + multiplier + "×";
        typeGridEl.appendChild(tile);
      });
    }

    // Minimum recorded matches before a head-to-head pair is shown. Below
    // this, win rate is noise: a single match reads as 100% or 0%. Matches
    // pokemon_matchup_summary's own threshold so the mart and the UI agree.
    var H2H_MIN_MATCHES = 10;

    function h2hRow(attacker, defender) {
      if (!attacker || !defender) return null;
      for (var i = 0; i < h2hRows.length; i++) {
        if (
          h2hRows[i].pokemon_key === attacker.pokemon_key &&
          h2hRows[i].opponent_pokemon_key === defender.pokemon_key
        ) {
          return h2hRows[i];
        }
      }
      return null;
    }

    function drawHeadToHead(attacker, defender) {
      if (h2hHeadlineEl) {
        var row = h2hRow(attacker, defender);
        if (!attacker || !defender) {
          h2hHeadlineEl.innerHTML =
            '<div class="damage-sub">Pick an attacker and a defender to see their recorded head-to-head.</div>';
        } else if (!row) {
          h2hHeadlineEl.innerHTML =
            '<div class="damage-sub">No recorded matches between teams fielding ' +
            App.escapeHtml(attacker.pokemon_name) + " and " +
            App.escapeHtml(defender.pokemon_name) + ".</div>";
        } else {
          h2hHeadlineEl.innerHTML =
            '<div class="damage-headline">' + App.formatPercent(row.win_rate) + "</div>" +
            '<div class="damage-sub">Teams with ' + App.escapeHtml(attacker.pokemon_name) +
            " beat teams with " + App.escapeHtml(defender.pokemon_name) + " in " +
            row.wins + " of " + row.matches_played + " recorded matches." +
            (row.matches_played < H2H_MIN_MATCHES
              ? " Small sample — treat with caution."
              : "") +
            "</div>";
        }
      }
      if (!h2hGridEl) return;
      // The defender's toughest opponents: rows where the DEFENDER is the
      // opponent, ranked by how reliably the other side wins.
      var rows = defender
        ? h2hRows
            .filter(function (r) {
              return (
                r.opponent_pokemon_key === defender.pokemon_key &&
                r.matches_played >= H2H_MIN_MATCHES
              );
            })
            .sort(function (a, b) {
              return b.wilson_lower_bound - a.wilson_lower_bound;
            })
            .slice(0, 12)
        : [];
      App.renderGrid6xn(h2hGridEl, rows, {
        keyFn: function (r) {
          return r.pokemon_key;
        },
        labelFn: function (r) {
          return r.pokemon_name;
        },
        displayFn: function (r) {
          return App.formatPercent(r.win_rate) + " (n=" + r.matches_played + ")";
        },
      });
    }

    // Matchup profile (pokemon_matchup_summary): each side's whole-dataset
    // record plus its single best and worst opponent. Complements the
    // pair-specific headline above, which says nothing when the two picked
    // Pokémon have never met. Inherits pokemon_head_to_head's team-vs-team
    // caveat exactly — "best matchup" means the opponent whose teams this
    // Pokémon's teams beat most reliably, not a claim about the two
    // Pokémon fighting each other.
    function summaryCardHtml(role, pokemon) {
      if (!pokemon) return "";
      var row = summaryByKey[pokemon.pokemon_key];
      var body;
      if (!row) {
        body = '<div class="damage-sub">No recorded matches for ' +
          App.escapeHtml(pokemon.pokemon_name) + "'s teams.</div>";
      } else {
        // total_matchup_appearances is sum(matches_played) across every
        // opponent pair, so one real match contributes once per opposing
        // Pokémon (up to six) — calling it a match count would overstate
        // the sample by roughly 6x. Labelled as pairings for that reason.
        body =
          '<div class="damage-headline">' + App.formatPercent(row.overall_win_rate) + "</div>" +
          '<div class="damage-sub">across ' + row.total_matchup_appearances.toLocaleString() +
          " opponent pairings (one match counts once per opposing Pokémon) vs. " +
          row.distinct_opponents + " distinct Pokémon</div>" +
          '<div class="desc-text">Best: ' +
          (row.best_matchup_pokemon_key
            ? App.escapeHtml(row.best_matchup_pokemon_name) + " " +
              App.formatPercent(row.best_matchup_win_rate) +
              " (n=" + row.best_matchup_matches + ")"
            : "—") +
          "</div>" +
          '<div class="desc-text">Worst: ' +
          (row.worst_matchup_pokemon_key
            ? App.escapeHtml(row.worst_matchup_pokemon_name) + " " +
              App.formatPercent(row.worst_matchup_win_rate) +
              " (n=" + row.worst_matchup_matches + ")"
            : "—") +
          "</div>";
      }
      return (
        '<div class="matchup-side"><h4>' + role + " · " +
        App.escapeHtml(pokemon.pokemon_name) + "</h4>" + body + "</div>"
      );
    }

    function drawMatchupSummary(attacker, defender) {
      if (!summaryEl) return;
      var html = summaryCardHtml("Attacker", attacker) + summaryCardHtml("Defender", defender);
      summaryEl.innerHTML =
        html || '<p class="empty-state">Pick an attacker and a defender.</p>';
    }

    function drawCoUsage(defender) {
      if (!coUsageGridEl) return;
      var rows = defender
        ? coreRows
            .filter(function (r) {
              return r.pokemon_key === defender.pokemon_key;
            })
            .sort(function (a, b) {
              return a.usage_rank - b.usage_rank;
            })
            .slice(0, 15)
        : [];
      App.renderGrid6xn(coUsageGridEl, rows, {
        keyFn: function (r) {
          return r.partner_pokemon_key;
        },
        labelFn: function (r) {
          return r.partner_pokemon_name;
        },
        displayFn: function (r) {
          return App.formatPercent(r.partner_share);
        },
      });
    }

    function updateAll() {
      var attacker = byKey[attackerSelect.value];
      var defender = byKey[defenderSelect.value];
      App.renderTypeBadgeRow(attackerTypeEl, attacker && attacker.type_1, attacker && attacker.type_2, false);
      App.renderTypeBadgeRow(defenderTypeEl, defender && defender.type_1, defender && defender.type_2, false);
      if (attackerStatsEl) attackerStatsEl.textContent = statLine(attacker);
      if (defenderStatsEl) defenderStatsEl.textContent = statLine(defender);
      drawTypeGrid(defender);
      drawHeadToHead(attacker, defender);
      drawMatchupSummary(attacker, defender);
      drawCoUsage(defender);

      var moveName = moveSelect.value;
      var move = moveName
        ? moveRows.filter(function (r) {
            return attacker && r.pokemon_key === attacker.pokemon_key && r.move_name === moveName;
          })[0]
        : null;
      if (moveDescEl) moveDescEl.textContent = move ? move.short_effect || "" : "";

      if (mode === "meta") {
        drawMeta(attacker, move);
        return;
      }
      if (!resultEl) return;
      if (!attacker || !defender || !move) {
        resultEl.innerHTML = '<div class="damage-sub">Pick an attacker, a move, and a defender to see estimated damage.</div>';
        return;
      }
      if (!move.power) {
        resultEl.innerHTML = '<div class="damage-sub">' + App.escapeHtml(move.move_name) + " is a status move — no direct damage to calculate.</div>";
        return;
      }
      var result = computeDamage({
        attacker: attacker,
        defender: defender,
        move: move,
        attackerStages: attackerStages,
        defenderStages: defenderStages,
        weather: weatherSelect ? weatherSelect.value : "",
        toggles: toggles,
      });
      if (!result) {
        resultEl.innerHTML = '<div class="damage-sub">Unable to calculate damage for this move.</div>';
        return;
      }
      resultEl.innerHTML =
        '<div class="damage-range">' + result.low + "–" + result.high + " dmg</div>" +
        '<div class="damage-sub">' + result.lowPct.toFixed(1) + "%–" + result.highPct.toFixed(1) + "% of " +
        App.escapeHtml(defender.pokemon_name) + "'s HP · " + result.effectiveness + "× effective · " +
        (result.stab > 1 ? result.stab + "× STAB" : "no STAB") + "</div>";
    }

    // "vs the meta" (P3): the attacker's move against the regulation's 12
    // most-used Pokémon, each defender with its own #1 set's Intimidate.
    var META_SIZE = 12;
    var metaTable = App.createDataTable(document.getElementById("matchup-meta-table"), {
      caption: "Damage against the top 12",
      sort: { key: "usage_rank", dir: "asc" },
      rowHref: function (r) {
        return App.routeHash("matchup", [attackerSelect.value, r.pokemon_key]);
      },
      empty: "Pick an attacker and a damaging move.",
      columns: [
        { key: "usage_rank", label: "#", type: "rank", main: true },
        { key: "pokemon_name", label: "Defender", type: "pokemon", main: true, sortable: true },
        {
          key: "high_pct",
          label: "Damage",
          numeric: true,
          sortable: true,
          main: true,
          render: function (r) { return r.low_pct.toFixed(1) + "–" + r.high_pct.toFixed(1) + "%"; },
          title: function (r) { return r.low + "–" + r.high + " HP"; },
        },
        {
          key: "ko_rank",
          label: "KO",
          numeric: true,
          sortable: true,
          render: function (r) { return '<span class="ko-badge">' + r.ko + "</span>"; },
        },
        {
          key: "effectiveness",
          label: "Type",
          numeric: true,
          sortable: true,
          render: function (r) { return r.effectiveness + "×"; },
        },
        {
          key: "intimidate",
          label: "Intimidate",
          sortable: false,
          hideOnPhone: true,
          render: function (r) { return r.intimidate ? "Yes" : ""; },
        },
      ],
    });
    var KO_ORDER = { OHKO: 0, "Possible OHKO": 1, "2HKO": 2, "Possible 2HKO": 3, "3HKO": 4, "—": 5 };

    function drawMeta(attacker, move) {
      if (!attacker || !move || !move.power) {
        metaTable.setRows([]);
        return;
      }
      var top = sortedProfiles.slice(0, META_SIZE);
      metaTable.setRows(top.map(function (defender, i) {
        var defenderSet = topSetByKey[defender.pokemon_key];
        var sideToggles = {};
        Object.keys(toggles).forEach(function (id) {
          if (id !== "intimidate") sideToggles[id] = true;
        });
        var intimidate = !!(defenderSet && defenderSet.ability === "Intimidate");
        if (intimidate) sideToggles.intimidate = true;
        var result = computeDamage({
          attacker: attacker,
          defender: defender,
          move: move,
          attackerStages: attackerStages,
          defenderStages: { def: 0, spd: 0 },
          weather: weatherSelect ? weatherSelect.value : "",
          toggles: sideToggles,
        });
        var ko = result ? koVerdict(result) : "—";
        return {
          usage_rank: i + 1,
          pokemon_key: defender.pokemon_key,
          pokemon_name: defender.pokemon_name,
          low: result ? result.low : 0,
          high: result ? result.high : 0,
          low_pct: result ? result.lowPct : 0,
          high_pct: result ? result.highPct : 0,
          effectiveness: result ? result.effectiveness : 1,
          ko: ko,
          ko_rank: -KO_ORDER[ko],
          intimidate: intimidate,
        };
      }));
    }

    function setMode(next) {
      mode = next;
      document.querySelectorAll("[data-calc-mode]").forEach(function (btn) {
        btn.setAttribute("aria-pressed", btn.getAttribute("data-calc-mode") === mode ? "true" : "false");
      });
      if (metaEl) metaEl.hidden = mode !== "meta";
      if (resultEl) resultEl.hidden = mode === "meta";
      if (defenderSideEl) defenderSideEl.hidden = mode === "meta";
      applyPresets();
      updateAll();
    }

    function recordRoute(push) {
      App.setRoute(
        "matchup",
        [attackerSelect.value, mode === "meta" ? "meta" : defenderSelect.value],
        {},
        { push: push !== false }
      );
    }
    document.querySelectorAll("[data-calc-mode]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        setMode(btn.getAttribute("data-calc-mode"));
        recordRoute(false);
      });
    });
    attackerSelect.addEventListener("change", function () {
      refreshMoveOptions();
      applyPresets();
      updateAll();
      recordRoute();
    });
    defenderSelect.addEventListener("change", function () {
      applyPresets();
      updateAll();
      recordRoute();
    });
    moveSelect.addEventListener("change", updateAll);
    if (weatherSelect) weatherSelect.addEventListener("change", updateAll);

    refreshMoveOptions();
    applyPresets();
    updateAll();

    // #/matchup/<attacker>/<defender>, or #/matchup/<attacker>/meta for the
    // top-12 mode; either side may be omitted.
    matchupRoute = function (route) {
      var attacker = route.args[0];
      var defender = route.args[1];
      var changed = false;
      var nextMode = defender === "meta" ? "meta" : "single";
      if (nextMode !== mode) {
        mode = nextMode;
        changed = true;
      }
      if (attacker && byKey[attacker] && attacker !== attackerSelect.value) {
        attackerSelect.value = attacker;
        attackerSelect.dispatchEvent(new Event("pokemon-sync"));
        refreshMoveOptions();
        changed = true;
      }
      if (defender && byKey[defender] && defender !== defenderSelect.value) {
        defenderSelect.value = defender;
        defenderSelect.dispatchEvent(new Event("pokemon-sync"));
        changed = true;
      }
      if (changed) setMode(mode);
    };
  }

  var matchupRoute = function () {};

  App.registerTab("matchup", setupMatchup, {
    extraMarts: ["pokemon_head_to_head"],
    onRoute: function (route) {
      matchupRoute(route);
    },
  });
})();
