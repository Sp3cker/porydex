import json
import pathlib
import porydex.config
from porydex.common import name_key


def load_move_descriptions():
    """Load vanilla move descriptions and custom ability definitions."""
    vanilla_data_dir = pathlib.Path("vanilla")
    vanilla_moves = json.load(
        open(vanilla_data_dir / "moves.json", "r", encoding="utf-8")
    )
    
    if porydex.config.custom_ability_defs:
        custom_abilities = json.load(
            open(porydex.config.custom_ability_defs, "r", encoding="utf-8")
        )
    else:
        custom_abilities = {}
    
    return vanilla_moves, custom_abilities


def enrich_moves_with_descriptions(moves: dict):
    """Add desc and shortDesc to moves from vanilla data."""
    vanilla_moves, _ = load_move_descriptions()
    
    for key, vanilla in vanilla_moves.items():
        if (
            key.startswith("gmax")
            or (key.startswith("hiddenpower") and len(key) > 11)
            or vanilla.get("isNonstandard", "") == "CAP"
        ):
            continue

        if key in moves:
            moves[key]["desc"] = vanilla["desc"]
            moves[key]["shortDesc"] = vanilla["shortDesc"]
        else:
            print(f"Warning: Move {key} found in vanilla data but not in parsed moves")
    
    return moves
