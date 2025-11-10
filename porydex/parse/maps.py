import pathlib
import re

from pycparser.c_ast import ID, BinaryOp, Constant, Decl, ExprList
from yaspin import yaspin

from porydex.parse import extract_id, extract_int, extract_u8_str, load_data

# Define constants to match the C code
WILD_AREA_LAND = 0
WILD_AREA_WATER = 1
WILD_AREA_ROCKS = 2
WILD_AREA_FISHING = 3

# Map encounter table keys to their area ID and number of slots
AREA_INFO = {
    "land_mons": (WILD_AREA_LAND, 12),
    "water_mons": (WILD_AREA_WATER, 5),
    "rock_smash_mons": (WILD_AREA_ROCKS, 5),
    "fishing_mons": (WILD_AREA_FISHING, 12),
}


def calculate_encounter_seed(map_group: int, map_num: int, area: int, slot: int) -> int:
    seed = (map_group & 0xFF) << 24
    seed |= (map_num & 0xFF) << 16
    seed |= (area & 0xFF) << 8
    seed |= slot & 0xFF
    return seed


def all_maps(existing: ExprList) -> list[str]:
    # Start by walking backward from -2 until we run out of map name symbols,
    # adding them to a tracking dictionary as we go
    map_name_defs = {}
    for entry in existing[-2::-1]:
        if not isinstance(entry, Decl):  # assume we are done
            break

        if (
            entry.name
            and isinstance(entry.name, str)
            and entry.name.startswith("sMapName_")
        ):
            map_name_defs[entry.name] = extract_u8_str(entry.init).title()
        else:
            break

    # Now map constants to names and store them in a name map
    map_names = {}
    for entry in existing[-1].init.exprs:
        try:
            key = extract_int(entry.name[0])
            id_value = extract_id(entry.expr.exprs[-1])
            map_names[key] = map_name_defs[id_value]
        except (TypeError, KeyError, AttributeError, IndexError) as e:
            # Skip entries that can't be processed
            continue

    # Zip the map down to a list
    return [map_name for _, map_name in sorted(map_names.items(), key=lambda e: e[0])]


def extract_map_constant_value(expr) -> tuple[int, int]:
    """
    Extract mapNum and mapGroup from a map constant expression.

    Args:
        expr: The AST expression representing (mapNum | (mapGroup << 8))

    Returns:
        Tuple of (mapNum, mapGroup)
    """
    if isinstance(expr, BinaryOp) and expr.op == "|":
        # Handle the format: (mapNum | (mapGroup << 8))
        left = expr.left
        right = expr.right

        # Extract mapNum from the left side
        if isinstance(left, Constant):
            map_num = int(left.value)
        else:
            # Handle cases where mapNum might be a reference
            map_num = extract_int(left)

        # Extract mapGroup from the right side: (mapGroup << 8)
        if isinstance(right, BinaryOp) and right.op == "<<":
            if isinstance(right.left, Constant):
                map_group = int(right.left.value)
            else:
                map_group = extract_int(right.left)
        else:
            # Fallback if the structure is different
            map_group = 0

        return map_num, map_group
    else:
        # Fallback for unexpected expression structure
        return 0, 0


def parse_map_constants(fname: pathlib.Path) -> dict:
    """
    Parse map constants from map_groups.h using pycparser and return a dictionary
    mapping map constant names to their mapNum and mapGroup values.
    Returns:
        Dictionary mapping map constant names to dicts with 'num' and 'group' keys
        Example: {'MAP_ROUTE101': {'num': 16, 'group': 0}}
    """
    map_constants = {}
    seeds_added = False

    try:
        with yaspin(text=f"Loading map constants: {fname}", color="cyan") as spinner:
            # Load the C header file using pycparser
            map_data = load_data(
                fname,
                extra_includes=[
                    r"-include",
                    r"constants/map_groups.h",
                ],
            )
            spinner.ok("✅")

        # Parse each declaration in the file
        for decl in map_data:
            if isinstance(decl, Decl) and decl.name and decl.name.startswith("MAP_"):
                try:
                    # Extract the constant name
                    map_name = decl.name

                    # Extract the value expression
                    if hasattr(decl, "init") and decl.init:
                        map_num, map_group = extract_map_constant_value(decl.init)

                        # Calculate seeds for this map
                        seeds = {
                            area_name: [
                                calculate_encounter_seed(map_group, map_num, area_id, slot)
                                for slot in range(slots)
                            ]
                            for area_name, (area_id, slots) in AREA_INFO.items()
                        }

                        map_constants[map_name] = {
                            "num": map_num,
                            "group": map_group,
                            "seeds": seeds,
                        }

                        # Mark that we successfully added seeds
                        seeds_added = True

                except Exception as e:
                    # Skip any declarations that can't be parsed
                    print(f"Warning: Could not parse map constant {decl.name}: {e}")
                    continue

        # If pycparser didn't find any constants, fall back to regex method
        if not map_constants:
            raise Exception("No map constants found")

        # Check if seeds were successfully added
        if not seeds_added:
            raise Exception("Failed to add seeds property to any map constants")

    except FileNotFoundError:
        print(f"Warning: Could not find map constants file {fname}")
        raise Exception(f"Map constants file not found: {fname}")
    except Exception as e:
        print(f"Warning: Could not parse map constants from {fname}: {e}")
        # Fall back to regex method
        return parse_map_constants_regex(fname)

    return map_constants


def parse_map_constants_regex(fname: pathlib.Path) -> dict:
    """
    Fallback method using regex to parse map constants from map_groups.h.
    """
    map_constants = {}
    seeds_added = False

    try:
        with open(fname, "r", encoding="utf-8") as f:
            content = f.read()

        # Pattern to match #define MAP_NAME (num | (group << 8))
        # This handles the format: #define MAP_ROUTE101 (16 | (0 << 8))
        pattern = (
            r"#define\s+(MAP_[A-Z_][A-Z0-9_]*)\s+\((\d+)\s*\|\s*\((\d+)\s*<<\s*8\)\)"
        )
        matches = re.findall(pattern, content)

        for map_name, map_num, map_group in matches:
            map_num_int = int(map_num)
            map_group_int = int(map_group)

            # Calculate seeds for this map
            seeds = {
                area_name: [
                    calculate_encounter_seed(map_group_int, map_num_int, area_id, slot)
                    for slot in range(slots)
                ]
                for area_name, (area_id, slots) in AREA_INFO.items()
            }

            map_constants[map_name] = {
                "num": map_num_int,
                "group": map_group_int,
                "seeds": seeds
            }
            seeds_added = True

        # Check if seeds were successfully added
        if not seeds_added:
            raise Exception("Failed to add seeds property to any map constants in regex fallback")

    except FileNotFoundError:
        print(f"Warning: Could not find map constants file {fname}")
        raise Exception(f"Map constants file not found: {fname}")
    except Exception as e:
        print(f"Warning: Could not parse map constants from {fname}: {e}")
        raise Exception(f"Failed to parse map constants: {e}")

    return map_constants


def parse_maps(fname: pathlib.Path) -> list[str]:
    maps_data: ExprList
    with yaspin(text=f"Loading map data: {fname}", color="cyan") as spinner:
        maps_data = load_data(
            fname,
            extra_includes=[
                r"-include",
                r"constants/abilities.h",
            ],
        )
        spinner.ok("✅")

    return all_maps(maps_data)
