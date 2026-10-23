import csv

import requests

from pipelines.extract import http as extract_http
from pipelines.extract import pokeapi


class _FakeResponse:
    def __init__(self, payload, *, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            error = requests.exceptions.HTTPError(f"{self.status_code} error")
            error.response = self
            raise error

    def json(self):
        return self._payload


class _FakeSession:
    def __init__(
        self,
        payloads_by_name: dict[str, dict],
        list_names: list[str] | None = None,
        missing_names: set[str] | None = None,
        flaky_names: dict[str, int] | None = None,
    ) -> None:
        self._payloads_by_name = payloads_by_name
        self._list_names = list_names
        self._missing_names = missing_names or set()
        self._flaky_names = dict(flaky_names or {})
        self.requested_urls: list[str] = []

    def get(self, url: str, timeout: int):
        self.requested_urls.append(url)
        if url.startswith(f"{pokeapi.API_BASE_URL}/pokemon?"):
            return _FakeResponse({"results": [{"name": name} for name in self._list_names]})
        name = url.rstrip("/").rsplit("/", 1)[-1]
        if name in self._missing_names:
            return _FakeResponse(None, status_code=404)
        remaining_failures = self._flaky_names.get(name, 0)
        if remaining_failures > 0:
            self._flaky_names[name] = remaining_failures - 1
            return _FakeResponse(None, status_code=500)
        return _FakeResponse(self._payloads_by_name[name])


def _payload(
    resource_id: int,
    name: str,
    stats: dict[str, int],
    *,
    species_name: str,
    species_id: int,
    types: list[str] | None = None,
) -> dict:
    types = types if types is not None else ["normal"]
    return {
        "id": resource_id,
        "name": name,
        "species": {
            "name": species_name,
            "url": f"https://pokeapi.co/api/v2/pokemon-species/{species_id}/",
        },
        "stats": [
            {"base_stat": value, "stat": {"name": stat_name}} for stat_name, value in stats.items()
        ],
        "types": [
            {"slot": slot, "type": {"name": type_name}} for slot, type_name in enumerate(types, 1)
        ],
    }


def test_extract_writes_rows_with_stats_and_provenance(tmp_path):
    payloads = {
        "bulbasaur": _payload(
            1,
            "bulbasaur",
            {
                "hp": 45,
                "attack": 49,
                "defense": 49,
                "special-attack": 65,
                "special-defense": 65,
                "speed": 45,
            },
            species_name="bulbasaur",
            species_id=1,
            types=["grass", "poison"],
        ),
    }
    session = _FakeSession(payloads)
    output_path = tmp_path / "pokeapi.csv"

    pokeapi.extract(output_path, ["bulbasaur"], dataset_version="0.1.0", session=session)

    with output_path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    assert session.requested_urls == ["https://pokeapi.co/api/v2/pokemon/bulbasaur"]
    assert len(rows) == 1
    row = rows[0]
    assert row["pokemon_id"] == "1"
    assert row["pokemon_name"] == "bulbasaur"
    assert row["form_name"] == "bulbasaur"
    assert row["hp"] == "45"
    assert row["attack"] == "49"
    assert row["defense"] == "49"
    assert row["sp_attack"] == "65"
    assert row["sp_defense"] == "65"
    assert row["speed"] == "45"
    assert row["stat_total"] == "318"
    assert row["type_1"] == "grass"
    assert row["type_2"] == "poison"
    assert row["source_name"] == "PokéAPI"
    assert row["source_url"] == "https://pokeapi.co/api/v2/pokemon/bulbasaur"
    assert row["source_record_id"] == "1"
    assert row["dataset_version"] == "0.1.0"
    assert row["extracted_at_utc"]


def test_extract_uses_species_id_and_name_for_alt_forms(tmp_path):
    payloads = {
        "charizard-mega-x": _payload(
            10034,
            "charizard-mega-x",
            {
                "hp": 78,
                "attack": 130,
                "defense": 111,
                "special-attack": 130,
                "special-defense": 85,
                "speed": 100,
            },
            species_name="charizard",
            species_id=6,
        ),
    }
    session = _FakeSession(payloads)
    output_path = tmp_path / "pokeapi.csv"

    pokeapi.extract(output_path, ["charizard-mega-x"], session=session)

    with output_path.open(newline="", encoding="utf-8") as fh:
        row = next(csv.DictReader(fh))

    assert row["pokemon_id"] == "6"
    assert row["pokemon_name"] == "charizard"
    assert row["form_name"] == "charizard-mega-x"
    assert row["source_record_id"] == "10034"


def test_extract_preserves_requested_identifier_order(tmp_path):
    payloads = {
        "charmander": _payload(
            4,
            "charmander",
            {
                "hp": 39,
                "attack": 52,
                "defense": 43,
                "special-attack": 60,
                "special-defense": 50,
                "speed": 65,
            },
            species_name="charmander",
            species_id=4,
        ),
        "squirtle": _payload(
            7,
            "squirtle",
            {
                "hp": 44,
                "attack": 48,
                "defense": 65,
                "special-attack": 50,
                "special-defense": 64,
                "speed": 43,
            },
            species_name="squirtle",
            species_id=7,
        ),
    }
    session = _FakeSession(payloads)
    output_path = tmp_path / "pokeapi.csv"

    pokeapi.extract(output_path, ["squirtle", "charmander"], session=session)

    with output_path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    assert [row["pokemon_name"] for row in rows] == ["squirtle", "charmander"]


def test_extract_defaults_to_fetching_full_pokemon_list(tmp_path):
    payloads = {
        "bulbasaur": _payload(
            1,
            "bulbasaur",
            {
                "hp": 45,
                "attack": 49,
                "defense": 49,
                "special-attack": 65,
                "special-defense": 65,
                "speed": 45,
            },
            species_name="bulbasaur",
            species_id=1,
        )
    }
    session = _FakeSession(payloads, list_names=["bulbasaur"])
    output_path = tmp_path / "pokeapi.csv"

    pokeapi.extract(output_path, session=session)

    assert session.requested_urls[0].startswith(f"{pokeapi.API_BASE_URL}/pokemon?")
    with output_path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 1
    assert rows[0]["pokemon_name"] == "bulbasaur"


def test_extract_defaults_dataset_version_when_not_provided(tmp_path):
    payloads = {
        "bulbasaur": _payload(
            1,
            "bulbasaur",
            {
                "hp": 45,
                "attack": 49,
                "defense": 49,
                "special-attack": 65,
                "special-defense": 65,
                "speed": 45,
            },
            species_name="bulbasaur",
            species_id=1,
        )
    }
    session = _FakeSession(payloads)
    output_path = tmp_path / "pokeapi.csv"

    pokeapi.extract(output_path, ["bulbasaur"], session=session)

    with output_path.open(newline="", encoding="utf-8") as fh:
        row = next(csv.DictReader(fh))

    assert row["dataset_version"] == pokeapi.DEFAULT_DATASET_VERSION


def test_extract_writes_null_type_2_for_single_type_pokemon(tmp_path):
    payloads = {
        "pikachu": _payload(
            25,
            "pikachu",
            {
                "hp": 35,
                "attack": 55,
                "defense": 40,
                "special-attack": 50,
                "special-defense": 50,
                "speed": 90,
            },
            species_name="pikachu",
            species_id=25,
            types=["electric"],
        ),
    }
    session = _FakeSession(payloads)
    output_path = tmp_path / "pokeapi.csv"

    pokeapi.extract(output_path, ["pikachu"], session=session)

    with output_path.open(newline="", encoding="utf-8") as fh:
        row = next(csv.DictReader(fh))

    assert row["type_1"] == "electric"
    assert row["type_2"] == ""


def _move_payload(move_id: int, name: str, **overrides) -> dict:
    payload = {
        "id": move_id,
        "type": {"name": "electric"},
        "power": 90,
        "accuracy": 100,
        "damage_class": {"name": "special"},
        "priority": 0,
        "pp": 15,
        "effect_entries": [
            {"language": {"name": "en"}, "short_effect": "Has a 10% chance to paralyze."}
        ],
    }
    payload.update(overrides)
    return payload


def test_extract_moves_writes_move_detail_rows(tmp_path):
    payloads = {"thunderbolt": _move_payload(85, "thunderbolt")}
    session = _FakeSession(payloads)
    output_path = tmp_path / "pokeapi_move.csv"

    pokeapi.extract_moves(output_path, ["Thunderbolt"], dataset_version="0.1.0", session=session)

    with output_path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    assert session.requested_urls == ["https://pokeapi.co/api/v2/move/thunderbolt"]
    assert len(rows) == 1
    row = rows[0]
    assert row["move_name"] == "Thunderbolt"
    assert row["move_type"] == "electric"
    assert row["power"] == "90"
    assert row["accuracy"] == "100"
    assert row["category"] == "special"
    assert row["priority"] == "0"
    assert row["pp"] == "15"
    assert row["short_effect"] == "Has a 10% chance to paralyze."
    assert row["source_name"] == "PokéAPI"
    assert row["source_record_id"] == "85"
    assert row["dataset_version"] == "0.1.0"


def test_extract_moves_slugifies_multi_word_names(tmp_path):
    payloads = {"ice-punch": _move_payload(8, "ice-punch", type={"name": "ice"})}
    session = _FakeSession(payloads)
    output_path = tmp_path / "pokeapi_move.csv"

    pokeapi.extract_moves(output_path, ["Ice Punch"], session=session)

    assert session.requested_urls == ["https://pokeapi.co/api/v2/move/ice-punch"]


def test_extract_moves_slugifies_curly_apostrophe_like_straight_one(tmp_path):
    # Real roster text sometimes uses a Unicode curly apostrophe ('King’s
    # Shield') instead of a straight one ('King's Rock') — both must
    # resolve to the same PokéAPI slug PokéAPI itself uses (no apostrophe
    # at all), or the curly form 400s as an unrecognized percent-encoded
    # byte sequence.
    payloads = {"kings-shield": _move_payload(367, "kings-shield")}
    session = _FakeSession(payloads)
    output_path = tmp_path / "pokeapi_move.csv"

    pokeapi.extract_moves(output_path, ["King’s Shield"], session=session)

    assert session.requested_urls == ["https://pokeapi.co/api/v2/move/kings-shield"]
    with output_path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 1


def test_extract_abilities_writes_ability_detail_rows(tmp_path):
    payloads = {
        "intimidate": {
            "id": 22,
            "effect_entries": [
                {
                    "language": {"name": "en"},
                    "short_effect": "Lowers the foes' Attack stat by one stage on switch-in.",
                }
            ],
        }
    }
    session = _FakeSession(payloads)
    output_path = tmp_path / "pokeapi_ability.csv"

    pokeapi.extract_abilities(output_path, ["Intimidate"], dataset_version="0.1.0", session=session)

    with output_path.open(newline="", encoding="utf-8") as fh:
        row = next(csv.DictReader(fh))

    assert session.requested_urls == ["https://pokeapi.co/api/v2/ability/intimidate"]
    assert row["ability_name"] == "Intimidate"
    assert row["short_effect"] == "Lowers the foes' Attack stat by one stage on switch-in."
    assert row["source_record_id"] == "22"
    assert row["dataset_version"] == "0.1.0"


def test_extract_items_writes_item_detail_rows(tmp_path):
    payloads = {
        "choice-band": {
            "id": 220,
            "effect_entries": [
                {
                    "language": {"name": "en"},
                    "short_effect": "Boosts Attack by 50%, but restricts the holder to one move.",
                }
            ],
        }
    }
    session = _FakeSession(payloads)
    output_path = tmp_path / "pokeapi_item.csv"

    pokeapi.extract_items(output_path, ["Choice Band"], dataset_version="0.1.0", session=session)

    with output_path.open(newline="", encoding="utf-8") as fh:
        row = next(csv.DictReader(fh))

    assert session.requested_urls == ["https://pokeapi.co/api/v2/item/choice-band"]
    assert row["item_name"] == "Choice Band"
    assert row["short_effect"] == "Boosts Attack by 50%, but restricts the holder to one move."
    assert row["source_record_id"] == "220"
    assert row["dataset_version"] == "0.1.0"


def test_extract_moves_handles_no_english_effect_entry(tmp_path):
    payloads = {"splash": _move_payload(150, "splash", effect_entries=[])}
    session = _FakeSession(payloads)
    output_path = tmp_path / "pokeapi_move.csv"

    pokeapi.extract_moves(output_path, ["Splash"], session=session)

    with output_path.open(newline="", encoding="utf-8") as fh:
        row = next(csv.DictReader(fh))

    assert row["short_effect"] == ""


def test_extract_moves_skips_unresolvable_move_name(tmp_path):
    # Real tournament roster text can contain a genuinely malformed name
    # (e.g. a truncated "After Yo" instead of "After You") that 404s
    # against PokéAPI — this must be skipped, not crash the whole extract.
    payloads = {"thunderbolt": _move_payload(85, "thunderbolt")}
    session = _FakeSession(payloads, missing_names={"after-yo"})
    output_path = tmp_path / "pokeapi_move.csv"

    pokeapi.extract_moves(output_path, ["After Yo", "Thunderbolt"], session=session)

    with output_path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    assert len(rows) == 1
    assert rows[0]["move_name"] == "Thunderbolt"


def test_extract_abilities_skips_unresolvable_ability_name(tmp_path):
    payloads = {
        "intimidate": {
            "id": 22,
            "effect_entries": [{"language": {"name": "en"}, "short_effect": "Lowers Attack."}],
        }
    }
    session = _FakeSession(payloads, missing_names={"not-a-real-ability"})
    output_path = tmp_path / "pokeapi_ability.csv"

    pokeapi.extract_abilities(output_path, ["Not A Real Ability", "Intimidate"], session=session)

    with output_path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    assert len(rows) == 1
    assert rows[0]["ability_name"] == "Intimidate"


def test_extract_moves_retries_transient_error_then_succeeds(tmp_path, monkeypatch):
    monkeypatch.setattr(extract_http.time, "sleep", lambda seconds: None)
    payloads = {"thunderbolt": _move_payload(85, "thunderbolt")}
    session = _FakeSession(payloads, flaky_names={"thunderbolt": 2})
    output_path = tmp_path / "pokeapi_move.csv"

    pokeapi.extract_moves(output_path, ["Thunderbolt"], session=session)

    with output_path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    assert len(rows) == 1
    assert rows[0]["move_name"] == "Thunderbolt"


def test_extract_moves_gives_up_after_persistent_transient_error(tmp_path, monkeypatch):
    monkeypatch.setattr(extract_http.time, "sleep", lambda seconds: None)
    payloads = {"thunderbolt": _move_payload(85, "thunderbolt")}
    # Always fails (more failures than retry attempts) — should be skipped,
    # not crash the whole extraction.
    session = _FakeSession(payloads, flaky_names={"thunderbolt": 99})
    output_path = tmp_path / "pokeapi_move.csv"

    pokeapi.extract_moves(output_path, ["Thunderbolt"], session=session)

    with output_path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    assert rows == []


def test_extract_items_skips_unresolvable_item_name(tmp_path):
    payloads = {
        "choice-band": {
            "id": 220,
            "effect_entries": [{"language": {"name": "en"}, "short_effect": "Boosts Attack."}],
        }
    }
    session = _FakeSession(payloads, missing_names={"not-a-real-item"})
    output_path = tmp_path / "pokeapi_item.csv"

    pokeapi.extract_items(output_path, ["Not A Real Item", "Choice Band"], session=session)

    with output_path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    assert len(rows) == 1
    assert rows[0]["item_name"] == "Choice Band"


# --- localised names (docs/upgrade-plan-2027q2.md, Q4) ---

_NAME_CSVS = {
    "languages": "id,iso639,iso3166,identifier,official,order\n"
    "1,ja,jp,ja-hrkt,1,1\n5,fr,fr,fr,1,8\n6,de,de,de,1,9\n7,es,es,es,1,10\n9,en,us,en,1,7\n11,ja,jp,ja,1,2\n",
    "pokemon": "id,identifier,species_id,height,weight,base_experience,order,is_default\n"
    "6,charizard,6,17,905,267,7,1\n10035,charizard-mega-y,6,17,1005,285,9,0\n"
    "59,arcanine,59,19,1550,194,90,1\n10230,arcanine-hisui,59,20,1680,194,91,0\n"
    "414,mothim,414,9,233,148,500,1\n",
    "pokemon_forms": "id,identifier,form_identifier,pokemon_id,introduced_in_version_group_id,"
    "is_default,is_battle_only,is_mega,form_order,order\n"
    "6,charizard,,6,1,1,0,0,1,7\n10061,charizard-mega-y,mega-y,10035,15,1,1,1,3,9\n"
    "59,arcanine,,59,1,1,0,0,1,90\n10399,arcanine-hisui,hisui,10230,24,1,0,0,2,91\n"
    "491,mothim-plant,plant,414,8,1,0,0,1,500\n",
    "pokemon_species_names": "pokemon_species_id,local_language_id,name,genus\n"
    "6,11,リザードン,\n6,5,Dracaufeu,\n6,6,Glurak,\n6,7,Charizard,\n"
    "59,11,ウインディ,\n59,5,Arcanin,\n59,6,Arkani,\n59,7,Arcanine,\n"
    "414,11,ガーメイル,\n414,5,Papilord,\n414,6,Moterpel,\n414,7,Mothim,\n",
    "pokemon_form_names": "pokemon_form_id,local_language_id,form_name,pokemon_name\n"
    "10061,11,メガリザードンＹ,\n10061,5,Méga-Dracaufeu Y,Méga-Dracaufeu Y\n"
    "10399,11,ヒスイのすがた,\n491,9,Plant Cloak,\n",
}


class _CsvSession:
    def __init__(self):
        self.requested = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.requested.append(url)
        name = url.rsplit("/", 1)[-1].removesuffix(".csv")
        response = _FakeResponse(None)
        response.text = _NAME_CSVS[name]
        return response


def test_localised_name_composes_megas_regionals_and_labels():
    def name(language, species, **form):
        return pokeapi.localised_name(language, species, **form)[0]

    assert name("es", "Charizard", form_identifier="mega-y", is_mega=True) == "Mega-Charizard Y"
    assert name("de", "Glurak", form_identifier="mega-y", is_mega=True) == "Mega-Glurak Y"
    assert name("ja", "ライチュウ", form_identifier="mega-y", is_mega=True) == "メガライチュウY"
    assert name("fr", "Arcanin", form_identifier="hisui", is_mega=False) == "Arcanin de Hisui"
    assert name("de", "Arkani", form_identifier="hisui", is_mega=False) == "Hisui-Arkani"
    assert (
        name("ja", "ウインディ", form_identifier="hisui", is_mega=False, form_name="ヒスイのすがた")
        == "ウインディ（ヒスイのすがた）"
    )
    # A label that already holds the species name is the whole name.
    assert (
        name("es", "Rotom", form_identifier="wash", is_mega=False, form_name="Rotom Lavado")
        == "Rotom Lavado"
    )
    assert name("de", "Salmagnis", form_identifier="male", is_mega=False) == "Salmagnis ♂"
    assert name("es", "Maushold", form_identifier="family-of-three", is_mega=False) == (
        "Maushold (Family Of Three)"
    )


def test_extract_names_writes_each_form_in_four_languages(tmp_path):
    output = tmp_path / "names.csv"
    session = _CsvSession()

    pokeapi.extract_names(
        output,
        ["charizard", "charizard-mega-y", "arcanine-hisui", "mothim", "not-a-pokemon"],
        session=session,
        dataset_version="0.4.0",
    )

    assert len(session.requested) == 5
    with output.open(newline="", encoding="utf-8") as fh:
        rows = {(r["form_name"], r["language"]): r for r in csv.DictReader(fh)}
    assert rows[("charizard", "ja")]["localised_name"] == "リザードン"
    assert rows[("charizard-mega-y", "fr")]["localised_name"] == "Méga-Dracaufeu Y"
    assert rows[("charizard-mega-y", "fr")]["name_rule"] == "pokeapi_form"
    assert rows[("charizard-mega-y", "ja")]["localised_name"] == "メガリザードンＹ"
    assert rows[("charizard-mega-y", "de")]["localised_name"] == "Mega-Glurak Y"
    assert rows[("arcanine-hisui", "ja")]["localised_name"] == "ウインディ（ヒスイのすがた）"
    assert rows[("arcanine-hisui", "es")]["localised_name"] == "Arcanine de Hisui"
    # A single-form species' labelled default form is the species name.
    assert rows[("mothim", "fr")]["localised_name"] == "Papilord"
    assert not any(form == "not-a-pokemon" for form, _ in rows)
    assert {r["dataset_version"] for r in rows.values()} == {"0.4.0"}
    assert rows[("charizard", "de")]["source_record_id"] == "charizard:de"
