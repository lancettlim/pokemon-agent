"""Card data loading: either from real ingested tournament data (by
team_id) or from a hand-authored ad-hoc build spec, into a common
CardModel shape consumed by pipelines/render/template.py.

The team_id path reads data/normalized/*.csv directly via csv.DictReader,
matching the rest of this codebase's convention of not requiring a dbt/
pandas runtime just to read already-normalized output. The ad-hoc path
exists for recreating a specific team (e.g. a broadcast graphic) that
isn't present in MunchStats's tournament coverage; it degrades gracefully
when a named Pokémon/item/sprite isn't resolvable against the ingested
dataset, since that's the entire point of not requiring ingestion.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path

from pipelines.dashboard.data import display_name as format_display_name

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_NORMALIZED_DIR = REPO_ROOT / "data" / "normalized"
DEFAULT_ASSET_CACHE_DIR = REPO_ROOT / "data" / "assets" / "bulbagarden"
MOVE_TYPES_SEED_PATH = REPO_ROOT / "dbt" / "seeds" / "pokeapi_move_types.csv"


class TeamNotFoundError(Exception):
    """Raised when a requested team_id has no rows in tournament_team_member."""


@dataclass
class CardSlot:
    slot_number: int
    pokemon_name: str
    form_name: str
    sprite_path: Path | None = None
    item_name: str | None = None
    item_icon_path: Path | None = None
    ability: str | None = None
    nature: str | None = None
    tera_type: str | None = None
    tera_icon_path: Path | None = None
    moves: list[str] = field(default_factory=list)
    move_types: list[str | None] = field(default_factory=list)


@dataclass
class CardModel:
    team_name: str
    subtitle: str | None = None
    player_name: str | None = None
    country: str | None = None
    slots: list[CardSlot] = field(default_factory=list)


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_move_types(seed_path: Path = MOVE_TYPES_SEED_PATH) -> dict[str, str]:
    """move_name (case-insensitive) -> move_type, from the pokeapi_move_types
    reference seed (dbt/seeds/pokeapi_move_types.csv, sourced from PokéAPI's
    moves.csv per docs/data-sources.md item 1)."""
    return {row["move_name"].lower(): row["move_type"] for row in _read_csv(seed_path)}


def _resolve_moves(
    raw_moves: list[str], move_types: dict[str, str]
) -> tuple[list[str], list[str | None]]:
    types = [move_types.get(move.strip().lower()) for move in raw_moves]
    return raw_moves, types


def _menu_sprite_assets_by_key(normalized_dir: Path) -> dict[str, dict]:
    """pokemon_key -> pokemon_asset row, restricted to menu_sprite rows.

    The filter is load-bearing, not defensive: pokemon_asset carries one row
    per Pokémon per image_kind (menu sprites from Bulbagarden, HOME renders
    from PokéAPI), so keying by pokemon_key alone would let whichever row
    came last win and point this renderer's sprite lookups at artwork
    filenames that don't exist under asset_cache_dir. The card wants the
    menu sprite specifically — it draws at 104px with pixelated rendering,
    which is what that asset is for.
    """
    return {
        row["pokemon_key"]: row
        for row in _read_csv(normalized_dir / "pokemon_asset.csv")
        if row.get("image_kind") == "menu_sprite"
    }


def _sprite_and_icon_lookup(
    pokemon_key: str | None,
    *,
    pokemon_assets: dict[str, dict],
    asset_cache_dir: Path,
) -> Path | None:
    if not pokemon_key:
        return None
    asset_row = pokemon_assets.get(pokemon_key)
    if not asset_row:
        return None
    local_cache_path = asset_row.get("local_cache_path")
    if not local_cache_path:
        return None
    candidate = asset_cache_dir / local_cache_path
    return candidate if candidate.exists() else None


def load_from_team_id(
    team_id: str,
    *,
    normalized_dir: Path = DEFAULT_NORMALIZED_DIR,
    asset_cache_dir: Path = DEFAULT_ASSET_CACHE_DIR,
    icon_cache_dir: Path | None = None,
) -> CardModel:
    """Build a CardModel from real ingested tournament_team /
    tournament_team_member rows, joined to pokemon (names) and
    pokemon_asset (sprites) via pokemon_key. Raises TeamNotFoundError if
    team_id resolves to zero roster members."""
    teams = {row["team_id"]: row for row in _read_csv(normalized_dir / "tournament_team.csv")}
    members = [
        row
        for row in _read_csv(normalized_dir / "tournament_team_member.csv")
        if row["team_id"] == team_id
    ]
    if not members:
        raise TeamNotFoundError(f"No tournament_team_member rows found for team_id={team_id!r}")
    members.sort(key=lambda row: int(row["slot_number"]))

    pokemon_by_key = {row["pokemon_key"]: row for row in _read_csv(normalized_dir / "pokemon.csv")}
    assets_by_key = _menu_sprite_assets_by_key(normalized_dir)
    move_types = load_move_types()

    slots = []
    for row in members:
        pokemon_key = row.get("pokemon_key")
        pokemon = pokemon_by_key.get(pokemon_key, {})
        sprite_path = _sprite_and_icon_lookup(
            pokemon_key, pokemon_assets=assets_by_key, asset_cache_dir=asset_cache_dir
        )
        raw_moves = [m for m in (row.get("moves") or "").split("|") if m]
        moves, types = _resolve_moves(raw_moves, move_types)
        display_name = (
            format_display_name(pokemon_key, pokemon.get("pokemon_name"))
            if pokemon_key
            else "Unknown"
        )
        slots.append(
            CardSlot(
                slot_number=int(row["slot_number"]),
                pokemon_name=display_name,
                form_name=pokemon.get("form_name", pokemon_key or ""),
                sprite_path=sprite_path,
                item_name=row.get("item_name") or None,
                ability=row.get("ability") or None,
                nature=row.get("nature") or None,
                tera_type=row.get("tera_type") or None,
                moves=moves,
                move_types=types,
            )
        )

    team = teams.get(team_id, {})
    placement = team.get("placement")
    return CardModel(
        team_name=team_id,
        subtitle=f"Placement: {placement}" if placement else None,
        player_name=team.get("player_name") or None,
        country=team.get("player_country") or None,
        slots=slots,
    )


def load_from_spec(
    spec_path: Path,
    *,
    normalized_dir: Path = DEFAULT_NORMALIZED_DIR,
    asset_cache_dir: Path = DEFAULT_ASSET_CACHE_DIR,
) -> CardModel:
    """Build a CardModel from a hand-authored ad-hoc JSON build spec:

    {"team_name": "...", "subtitle": "...", "player_name": "...", "country": "...",
     "slots": [{"pokemon_name": "...", "form_name": "...", "item_name": "...",
                "ability": "...", "nature": "...", "tera_type": "...",
                "moves": ["...", "..."]}]}

    player_name/country are optional, for recreating a real broadcast-style
    card (e.g. a Pro Team Gallery entry) that isn't in MunchStats's
    tournament coverage.

    Sprite/icon resolution is attempted against the ingested dataset (by
    matching form_name against pokemon.csv/pokemon_asset.csv) but degrades
    to a blank sprite when the spec's Pokémon isn't present there — that's
    the whole point of this path versus load_from_team_id.
    """
    spec = json.loads(spec_path.read_text(encoding="utf-8"))

    pokemon_by_form = {row["form_name"]: row for row in _read_csv(normalized_dir / "pokemon.csv")}
    assets_by_key = _menu_sprite_assets_by_key(normalized_dir)
    move_types = load_move_types()

    slots = []
    for slot_number, raw_slot in enumerate(spec.get("slots", []), start=1):
        form_name = raw_slot.get("form_name") or raw_slot.get("pokemon_name", "")
        pokemon = pokemon_by_form.get(form_name, {})
        pokemon_key = pokemon.get("pokemon_key")
        sprite_path = _sprite_and_icon_lookup(
            pokemon_key, pokemon_assets=assets_by_key, asset_cache_dir=asset_cache_dir
        )
        raw_moves = raw_slot.get("moves", [])
        moves, types = _resolve_moves(raw_moves, move_types)
        slots.append(
            CardSlot(
                slot_number=slot_number,
                pokemon_name=raw_slot.get("pokemon_name", form_name),
                form_name=form_name,
                sprite_path=sprite_path,
                item_name=raw_slot.get("item_name"),
                ability=raw_slot.get("ability"),
                nature=raw_slot.get("nature"),
                tera_type=raw_slot.get("tera_type"),
                moves=moves,
                move_types=types,
            )
        )

    return CardModel(
        team_name=spec.get("team_name", ""),
        subtitle=spec.get("subtitle"),
        player_name=spec.get("player_name"),
        country=spec.get("country"),
        slots=slots,
    )
