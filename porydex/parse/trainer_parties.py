import pathlib
from typing import Dict, List, Any

from pycparser.c_ast import ExprList, NamedInitializer, ArrayDecl, InitList
from yaspin import yaspin

from porydex.parse import load_truncated, extract_int, extract_u8_str


def get_hidden_power_type(ivs: List[int]) -> str:
    """Calculate Hidden Power type from IVs using the same algorithm as the JavaScript function."""
    if not isinstance(ivs, list) or len(ivs) != 6:
        return "Normal"  # Default to Normal type

    # Get LSB for each IV
    hp = ivs[0] & 1
    atk = ivs[1] & 1
    def_iv = ivs[2] & 1
    spa = ivs[5] & 1
    spd = ivs[3] & 1
    spe = ivs[4] & 1

    value = hp + 2 * atk + 4 * def_iv + 8 * spe + 16 * spa + 32 * spd
    hp_type_num = (value * 15) // 63
    # Type order: Fighting, Flying, Poison, Ground, Rock, Bug, Ghost, Steel, Fire, Water, Grass, Electric, Psychic, Ice, Dragon, Dark
    type_names = [
        "Fighting",
        "Flying",
        "Poison",
        "Ground",
        "Rock",
        "Bug",
        "Ghost",
        "Steel",
        "Fire",
        "Water",
        "Grass",
        "Electric",
        "Psychic",
        "Ice",
        "Dragon",
        "Dark",
    ]
    return type_names[hp_type_num] if hp_type_num < len(type_names) else "Normal"


evMap = {
    "TRAINER_PARTY_EVS_TIMID": [6, 0, 0, 252, 0, 252],
    "TRAINER_PARTY_EVS_MODEST": [6, 0, 0, 252, 0, 252],
    "TRAINER_PARTY_EVS_JOLLY": [6, 252, 0, 0, 0, 252],
    "TRAINER_PARTY_EVS_ADAMANT": [6, 252, 0, 0, 0, 252],
    "TRAINER_PARTY_EVS_BOLD": [252, 0, 252, 6, 0, 0],
    "TRAINER_PARTY_EVS_IMPISH": [252, 6, 252, 0, 0, 0],
    "TRAINER_PARTY_EVS_HASTY_OR_NAIVE_ATK": [0, 252, 0, 6, 0, 252],
    "TRAINER_PARTY_EVS_HASTY_OR_NAIVE_SP_ATK": [0, 6, 0, 252, 0, 252],
    "TRAINER_PARTY_EVS_MILD": [0, 6, 0, 252, 0, 252],
    "TRAINER_PARTY_EVS_QUIET": [252, 6, 0, 252, 0, 0],
    "TRAINER_PARTY_EVS_CALM": [252, 0, 0, 6, 252, 0],
}


def convert_to_consistent_format(
    parties_data: Dict[str, Dict[str, Any]],
    species_constants: Dict[str, int],
    move_constants: Dict[str, int],
    ability_constants: Dict[str, int],
    item_constants: Dict[str, int],
    item_names: List[str] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """Convert trainer parties to consistent format with numeric IDs."""
    # Nature mapping from numeric values to lowercase strings
    nature_mapping = {
        0: "hardy",
        1: "lonely",
        2: "brave",
        3: "adamant",
        4: "naughty",
        5: "bold",
        6: "docile",
        7: "relaxed",
        8: "impish",
        9: "lax",
        10: "timid",
        11: "hasty",
        12: "serious",
        13: "jolly",
        14: "naive",
        15: "modest",
        16: "mild",
        17: "quiet",
        18: "bashful",
        19: "rash",
        20: "calm",
        21: "gentle",
        22: "sassy",
        23: "careful",
        24: "quirky",
    }
    consistent_parties = {}

    # Create reverse mapping from item IDs to item constant names
    item_id_to_name = {v: k for k, v in item_constants.items()}

    for party_name, party_data in parties_data.items():
        print(f"Processing party: {party_name}")
        party_list = []

        if "party" in party_data:
            for mon in party_data["party"]:
                consistent_mon = {}

                # Level is always included
                if "lvl" in mon:
                    consistent_mon["lvl"] = mon["lvl"]

                # Species ID mapping from constants
                if "species" in mon:
                    species_constant = mon["species"]
                    if (
                        isinstance(species_constant, str)
                        and species_constant in species_constants
                    ):
                        consistent_mon["id"] = species_constants[species_constant]
                    elif isinstance(species_constant, int):
                        consistent_mon["id"] = species_constant
                    else:
                        # Try to extract species number from constant name
                        # This is a fallback if the constant mapping doesn't work
                        consistent_mon["id"] = species_constant

                # Handle IVs - store the actual IV values as an array
                if "iv" in mon:
                    if isinstance(mon["iv"], list):
                        # Store the IV array directly
                        consistent_mon["iv"] = mon["iv"]
                    elif isinstance(mon["iv"], int) and mon["iv"] > 0:
                        # If it's a single IV value, convert to array format
                        consistent_mon["iv"] = [mon["iv"]] * 6
                    elif isinstance(mon["iv"], bool) and mon["iv"]:
                        # If it's just a boolean true, use perfect IVs
                        consistent_mon["iv"] = [31, 31, 31, 31, 31, 31]

                if "nature" in mon and mon["nature"] is not None:
                    nature_val = mon["nature"]
                    if isinstance(nature_val, str) and nature_val.startswith("NATURE_"):
                        # Convert NATURE_TIMID -> "timid"
                        consistent_mon["nature"] = nature_val.replace(
                            "NATURE_", ""
                        ).lower()
                    elif isinstance(nature_val, int):
                        # Convert numeric nature value to string using mapping
                        if nature_val in nature_mapping:
                            consistent_mon["nature"] = nature_mapping[nature_val]
                        else:
                            # Fallback to numeric if not in mapping
                            consistent_mon["nature"] = nature_val

                if "ability" in mon and mon["ability"]:
                    ability_val = mon["ability"]
                    if (
                        isinstance(ability_val, str)
                        and ability_val in ability_constants
                    ):
                        consistent_mon["ability"] = [ability_constants[ability_val]]
                    elif isinstance(ability_val, int):
                        consistent_mon["ability"] = [ability_val]

                if "item" in mon and mon["item"] is not None:
                    item_val = mon["item"]
                    if isinstance(item_val, str):
                        # Convert item constant to actual item name
                        if item_val != "ITEM_NONE" and item_constants and item_names:
                            if item_val in item_constants:
                                item_id = item_constants[item_val]
                                if 0 <= item_id < len(item_names):
                                    consistent_mon["item"] = item_names[item_id]
                                else:
                                    consistent_mon["item"] = (
                                        item_val  # Fallback to constant name
                                    )
                            else:
                                consistent_mon["item"] = (
                                    item_val  # Fallback to constant name
                                )
                    elif isinstance(item_val, int) and item_val != 0:
                        # Convert numeric item ID to actual item name
                        if item_names and 0 <= item_val < len(item_names):
                            consistent_mon["item"] = item_names[item_val]
                        elif item_val in item_id_to_name:
                            consistent_mon["item"] = item_id_to_name[item_val]
                        else:
                            # Fallback to numeric ID if we can't map it
                            consistent_mon["item"] = item_val

                if "moves" in mon and mon["moves"]:
                    move_ids = []
                    has_hidden_power = False
                    for move in mon["moves"]:
                        if isinstance(move, str) and move in move_constants:
                            move_id = move_constants[move]
                            if move_id != 0:  # Skip MOVE_NONE
                                move_ids.append(move_id)
                                # Check if this is Hidden Power
                                if move == "MOVE_HIDDEN_POWER" or move_id == 237:
                                    has_hidden_power = True
                        elif isinstance(move, int) and move != 0:
                            move_ids.append(move)
                            # Check if this is Hidden Power (move ID 237)
                            if move == 237:  # MOVE_HIDDEN_POWER
                                has_hidden_power = True
                    if move_ids:
                        consistent_mon["moves"] = move_ids

                        # Calculate Hidden Power type if the Pokémon has Hidden Power and IVs
                        if (
                            has_hidden_power
                            and "iv" in consistent_mon
                            and isinstance(consistent_mon["iv"], list)
                        ):
                            consistent_mon["hpType"] = get_hidden_power_type(
                                consistent_mon["iv"]
                            )

                if "ev" in mon and mon["ev"]:
                    if isinstance(mon["ev"], list):
                        consistent_mon["ev"] = mon["ev"]
                    elif isinstance(mon["ev"], int) and mon["ev"] > 0:
                        # If it's a single EV value, convert to array format
                        consistent_mon["ev"] = [mon["ev"]] * 6

                if "preStatus" in mon and mon["preStatus"] is not None:
                    consistent_mon["preStatus"] = mon["preStatus"]
                    print(f"Added preStatus to consistent_mon: {mon['preStatus']} for party {party_name}")
                elif "preStatus" in mon:
                    print(f"preStatus found but is None: {mon['preStatus']} for party {party_name}")
                else:
                    print(f"No preStatus found in mon for party {party_name}, available keys: {list(mon.keys())}")
        
                party_list.append(consistent_mon)

        consistent_parties[party_name] = party_list

    return consistent_parties


def parse_trainer_parties(fname: pathlib.Path) -> Dict[str, Dict[str, Any]]:
    """Parse trainer party data from trainer_parties.h file."""

    with yaspin(text=f"Loading trainer parties data: {fname}", color="cyan") as spinner:
        from porydex.parse import load_table_set

        parties_decls = load_table_set(
            fname,
            extra_includes=[
                r"-include",
                r"constants/species.h",
                r"-include",
                r"constants/moves.h",
                r"-include",
                r"constants/abilities.h",
                r"-include",
                r"constants/items.h",
                r"-include",
                r"constants/trainers.h",
                # r"-include",
                # r"constants/battle.h",
            ],
        )
        spinner.ok("✅")

    # Parse all trainer parties
    all_parties = {}

    for i, decl in enumerate(parties_decls):
        if hasattr(decl, "name") and decl.name and decl.name.startswith("sParty_"):
            if hasattr(decl, "init") and decl.init:
                party_data = {"name": decl.name, "party": []}

                # Parse the array initializer
                if hasattr(decl.init, "exprs"):
                    for mon_init in decl.init.exprs:
                        if hasattr(
                            mon_init, "exprs"
                        ):  # This should be a struct initializer
                            mon_data = {}

                            for field_init in mon_init.exprs:
                                if (
                                    hasattr(field_init, "name")
                                    and len(field_init.name) > 0
                                ):
                                    field_name = field_init.name[0].name
                                    # Debug: print field names to see what's being parsed
                                    if field_name in [
                                        "preStatus",
                                        "prestatus",
                                        "status",
                                    ]:
                                        print(
                                            f"Found status field: {field_name} in {decl.name}"
                                        )

                                    if field_name == "lvl":
                                        mon_data["lvl"] = extract_int(field_init.expr)
                                    elif field_name == "species":
                                        # Extract species constant and map to species ID
                                        if hasattr(field_init.expr, "name"):
                                            species_constant = field_init.expr.name
                                            # Map SPECIES_GEODUDE -> 74 using species constants
                                            # For now, just store the constant name
                                            mon_data["species"] = species_constant
                                        else:
                                            mon_data["species"] = extract_int(
                                                field_init.expr
                                            )
                                    elif field_name == "iv":
                                        # Handle TRAINER_PARTY_IVS macro call
                                        if (
                                            hasattr(field_init.expr, "args")
                                            and field_init.expr.args
                                        ):
                                            iv_values = [
                                                extract_int(arg)
                                                for arg in field_init.expr.args.exprs
                                            ]
                                            mon_data["iv"] = iv_values
                                            mon_data["iv_perfect"] = all(
                                                iv >= 31 for iv in iv_values
                                            )
                                        else:
                                            mon_data["iv"] = True
                                    elif field_name == "moves":
                                        moves = []
                                        if hasattr(field_init.expr, "exprs"):
                                            for move_expr in field_init.expr.exprs:
                                                if hasattr(move_expr, "name"):
                                                    moves.append(move_expr.name)
                                                else:
                                                    moves.append(extract_int(move_expr))
                                        mon_data["moves"] = moves
                                    elif field_name == "ability":
                                        if hasattr(field_init.expr, "name"):
                                            mon_data["ability"] = field_init.expr.name
                                        else:
                                            mon_data["ability"] = extract_int(
                                                field_init.expr
                                            )
                                    elif field_name == "nature":
                                        if hasattr(field_init.expr, "name"):
                                            mon_data["nature"] = field_init.expr.name
                                        else:
                                            mon_data["nature"] = extract_int(
                                                field_init.expr
                                            )
                                    elif (
                                        field_name == "heldItem" or field_name == "item"
                                    ):
                                        if hasattr(field_init.expr, "name"):
                                            item_name = field_init.expr.name
                                            mon_data["item"] = item_name
                                        else:
                                            mon_data["item"] = extract_int(
                                                field_init.expr
                                            )
                                    # Use a mapping for EV macros to EV spreads to reduce nesting

                                    elif field_name == "ev":
                                        # Handle EV parsing - use evMap or parse actual values
                                        if hasattr(field_init.expr, "name"):
                                            # Handle predefined EV spread macros
                                            macro_name = field_init.expr.name
                                            # Extract the actual name from the ID object if needed
                                            if hasattr(macro_name, "name"):
                                                macro_name = macro_name.name

                                            if macro_name in evMap:
                                                mon_data["ev"] = evMap[macro_name]
                                            elif (
                                                macro_name == "TRAINER_PARTY_EVS"
                                                and hasattr(field_init.expr, "args")
                                                and field_init.expr.args
                                            ):
                                                # This is a direct TRAINER_PARTY_EVS function call with EV values
                                                ev_values = [
                                                    extract_int(arg)
                                                    for arg in field_init.expr.args.exprs
                                                ]
                                                if len(ev_values) == 6:
                                                    mon_data["ev"] = ev_values
                                                else:
                                                    print(
                                                        f"Warning: Expected 6 EV values, got {len(ev_values)}"
                                                    )
                                                    mon_data["ev"] = ev_values + [0] * (
                                                        6 - len(ev_values)
                                                    )  # Pad with zeros
                                            else:
                                                # Unknown predefined macro, use default
                                                import pprint

                                                print(
                                                    f"Warning: Unknown EV spread macro '{macro_name}', using default"
                                                )
                                                print("AST for unknown EV macro:")
                                                pprint.pprint(field_init.expr, indent=2)
                                                mon_data["ev"] = [
                                                    6,
                                                    252,
                                                    0,
                                                    0,
                                                    0,
                                                    252,
                                                ]  # Default spread

                                        elif (
                                            hasattr(field_init.expr, "args")
                                            and field_init.expr.args
                                        ):
                                            # Direct TRAINER_PARTY_EVS(hp, atk, def, spatk, spdef, speed) call
                                            ev_values = [
                                                extract_int(arg)
                                                for arg in field_init.expr.args.exprs
                                            ]
                                            if len(ev_values) == 6:
                                                mon_data["ev"] = ev_values
                                            else:
                                                print(
                                                    f"Warning: Expected 6 EV values, got {len(ev_values)}"
                                                )
                                                mon_data["ev"] = ev_values + [0] * (
                                                    6 - len(ev_values)
                                                )  # Pad with zeros

                                        else:
                                            # Single EV value or NULL
                                            try:
                                                ev_val = extract_int(field_init.expr)
                                                if ev_val == 0:
                                                    mon_data["ev"] = [
                                                        0,
                                                        0,
                                                        0,
                                                        0,
                                                        0,
                                                        0,
                                                    ]  # No EVs
                                                else:
                                                    mon_data["ev"] = [
                                                        ev_val
                                                    ] * 6  # Apply to all stats
                                            except (AttributeError, ValueError):
                                                # Handle compound literals or other complex expressions
                                                print(
                                                    f"Warning: Complex EV expression in {decl.name}, using default"
                                                )
                                                mon_data["ev"] = [
                                                    0,
                                                    0,
                                                    0,
                                                    0,
                                                    0,
                                                    0,
                                                ]  # Default spread

                                    elif field_name == "preStatus":
                                        # Extract pre-status condition
                                        print(
                                            f"Processing preStatus field in {decl.name}"
                                        )
                                        if hasattr(field_init.expr, "name"):
                                            mon_data["preStatus"] = field_init.expr.name
                                            print(
                                                f"  -> Extracted constant: {mon_data['preStatus']}"
                                            )
                                        else:
                                            mon_data["preStatus"] = extract_int(
                                                field_init.expr
                                            )
                                            print(
                                                f"  -> Extracted int: {mon_data['preStatus']}"
                                            )
                                    elif field_name == "prestatus":
                                        # Alternative field name (lowercase)
                                        print(
                                            f"Processing prestatus field in {decl.name}"
                                        )
                                        if hasattr(field_init.expr, "name"):
                                            mon_data["preStatus"] = field_init.expr.name
                                            print(
                                                f"  -> Extracted constant: {mon_data['preStatus']}"
                                            )
                                        else:
                                            mon_data["preStatus"] = extract_int(
                                                field_init.expr
                                            )
                                            print(
                                                f"  -> Extracted int: {mon_data['preStatus']}"
                                            )
                                    elif field_name == "status":
                                        # Another possible field name
                                        print(
                                            f"Processing status field in {decl.name}"
                                        )
                                        if hasattr(field_init.expr, "name"):
                                            mon_data["preStatus"] = field_init.expr.name
                                            print(
                                                f"  -> Extracted constant: {mon_data['preStatus']}"
                                            )
                                        else:
                                            mon_data["preStatus"] = extract_int(
                                                field_init.expr
                                            )
                                            print(
                                                f"  -> Extracted int: {mon_data['preStatus']}"
                                            )

                party_data["party"].append(mon_data)

                all_parties[decl.name] = party_data

    return all_parties
