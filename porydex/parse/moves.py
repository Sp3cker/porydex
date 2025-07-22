import pathlib
import re

from pycparser.c_ast import ExprList, NamedInitializer
from yaspin import yaspin

from porydex.common import name_key
from porydex.model import DAMAGE_TYPE, DAMAGE_CATEGORY, CONTEST_CATEGORY
from porydex.parse import extract_compound_str, load_truncated, extract_int, extract_u8_str

FLAGS_EXPANSION_TO_EI = {
    "bitingMove": "bite",
    "ballisticMove": "bullet",
    "ignoresSubstitute": "bypasssub",
    "cantUseTwice": "cantusetwice",
    "makesContact": "contact",
    "thawsUser": "defrost",
    "mirrorMoveBanned": "mirror",
    "powderMove": "powder",
    "ignoresProtect": "protect",
    "pulseMove": "pulse",
    "punchingMove": "punch",
    "magicCoatAffected": "reflectable",
    "slicingMove": "slicing",
    "snatchAffected": "snatch",
    "soundMove": "sound",
    "windMove": "wind",
}

DAMAGE_TYPE = {
    0: "None",
    1: "Normal",
    2: "Fighting",
    3: "Flying",
    4: "Poison",
    5: "Ground",
    6: "Rock",
    7: "Bug",
    8: "Ghost",
    9: "Steel",
    10: "Mystery",  # TYPE_MYSTERY
    11: "Fire",
    12: "Water",
    13: "Grass",
    14: "Electric",
    15: "Psychic",
    16: "Ice",
    17: "Dragon",
    18: "Dark",
    19: "Fairy",
    20: "Stellar",
}

DAMAGE_CATEGORY = {
    0: "Physical",
    1: "Special",
    2: "Status",
}

CONTEST_CATEGORY = {
    0: "Cool",
    1: "Beauty",
    2: "Cute",
    3: "Smart",
    4: "Tough",
}

def parse_description_constants(fname: pathlib.Path) -> dict:
    """
    Parse description constants from the moves_info.h file.
    
    Args:
        fname: Path to the moves_info.h file
        
    Returns:
        Dictionary mapping description constant names to their string values
    """
    description_constants = {}
    
    try:
        with open(fname, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Pattern to match description constants like:
        # static const u8 sMegaDrainDescription[] = _(
        #     "An attack that absorbs\n"
        #     "half the damage inflicted.");
        pattern = r'static const u8 (\w+)\[\] = _\(\s*"([^"]*)"\s*\n\s*"([^"]*)"\s*\);'
        
        matches = re.findall(pattern, content, re.MULTILINE | re.DOTALL)
        
        for match in matches:
            constant_name = match[0]
            line1 = match[1]
            line2 = match[2]
            description = f"{line1} {line2}".strip()
            # Replace any escaped newlines with spaces
            description = description.replace("\\n", " ")
            description_constants[constant_name] = description
        
        # Also try single-line pattern
        single_line_pattern = r'static const u8 (\w+)\[\] = _\(\s*"([^"]*)"\s*\);'
        single_matches = re.findall(single_line_pattern, content, re.MULTILINE | re.DOTALL)
        
        for match in single_matches:
            constant_name = match[0]
            description = match[1].strip()
            description_constants[constant_name] = description
        
    except Exception as e:
        print(f"Warning: Could not parse description constants from {fname}: {e}")
    
    return description_constants


def parse_constants_from_header(fname: pathlib.Path) -> dict:
    """
    Parse constants from a header file and return a dictionary mapping constant names to values.
    
    Args:
        fname: Path to the header file
        
    Returns:
        Dictionary mapping constant names to their values
    """
    constants = {}
    
    with open(fname, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Pattern to match #define CONSTANT_NAME value
    # This handles both simple values and references to other constants
    pattern = r'#define\s+([A-Z_][A-Z0-9_]*)\s+([^\s/]+)'
    matches = re.findall(pattern, content)
    
    for constant_name, value_str in matches:
        # Skip comments and preprocessor directives
        if value_str.startswith('//') or value_str.startswith('/*'):
            continue
            
        # Try to convert the value to an integer
        try:
            # Handle cases where the value references another constant
            if value_str.startswith('MOVE_') or value_str.startswith('ITEM_') or value_str.startswith('SPECIES_'):
                # For now, we'll store the reference as a string
                # In a full implementation, you might want to resolve these references
                constants[constant_name] = value_str
            else:
                # Try to parse as integer
                value = int(value_str)
                constants[constant_name] = value
        except ValueError:
            # If it's not a number, store as string
            constants[constant_name] = value_str
    
    return constants


def get_move_id_from_name(move_name: str, move_constants: dict) -> int:
    """
    Convert a move name to its constant name and get the move ID.
    
    Args:
        move_name: The move name (e.g., "High Horsepower")
        move_constants: Dictionary of move constants from the header file
        
    Returns:
        The move ID from the constants, or None if not found
    """
    # Convert move name to constant name format
    # "High Horsepower" -> "MOVE_HIGH_HORSEPOWER"
    constant_name = "MOVE_" + move_name.upper().replace(" ", "_")
    
    # Look up the constant value
    if constant_name in move_constants:
        value = move_constants[constant_name]
        # Ensure we return an integer
        if isinstance(value, int):
            return value
        elif isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                return None
    
    return None


def parse_move(struct_init: NamedInitializer, move_constants: dict = None, description_constants: dict = None) -> dict:
    init_list = struct_init.expr.exprs
    move = {}
    move["num"] = extract_int(struct_init.name[0])
    
    # We'll generate the constant name from the move name later
    # since the AST structure doesn't contain the actual constant names

    move["flags"] = {
        # ei format interprets these as "this move is affected by or can
        # be invoked by these effects"
        # expansion instead stores these as "this move ignores or cannot be
        # be invoked by these effects"
        "protect": 1,
        "mirror": 1,
    }
    
    # First pass: extract the move name
    for field_init in init_list:
        field_name = field_init.name[0].name
        field_expr = field_init.expr

        if field_name == "name":
            move["name"] = extract_compound_str(field_expr)
            break
    
    # Derive the moveId from the constant name if we have move constants
    if move_constants and "name" in move:
        move_id = get_move_id_from_name(move["name"], move_constants)
        if move_id is not None:
            move["moveId"] = move_id
        else:
            move["moveId"] = move["num"]  # Fallback to num if not found in constants
    else:
        move["moveId"] = move["num"]  # Fallback to num if no constants provided
    
    # Second pass: parse all other fields
    for field_init in init_list:
        field_name = field_init.name[0].name
        field_expr = field_init.expr

        match field_name:
            case "name":
                # Already handled above
                pass
            case "description":
                # Handle different types of description fields
                if hasattr(field_expr, "exprs"):
                    # Compound string (multiple string literals concatenated)
                    move["description"] = extract_compound_str(field_expr)
                elif hasattr(field_expr, "value"):
                    # String constant
                    move["description"] = field_expr.value.strip('"')
                elif hasattr(field_expr, "name"):
                    # Identifier (e.g., sMegaDrainDescription)
                    constant_name = field_expr.name
                    if description_constants and constant_name in description_constants:
                        # Resolve the constant to its actual string value
                        move["description"] = description_constants[constant_name]
                    else:
                        # Fallback to the constant name if we can't resolve it
                        move["description"] = constant_name
                else:
                    # Fallback - try to extract as compound string
                    try:
                        move["description"] = extract_compound_str(field_expr)
                    except:
                        move["description"] = str(field_expr)
            case "power":
                move["basePower"] = extract_int(field_expr)
            case "type":
                move["type"] = DAMAGE_TYPE[extract_int(field_expr)]
            case "accuracy":
                # expansion stores infinite accuracy as 0 accuracy
                # ei format represents infinite accuracy as boolean True
                acc = extract_int(field_expr)
                move["accuracy"] = acc  # if acc > 0 else True
            case "pp":
                move["pp"] = extract_int(field_expr)
            case "priority":
                move["priority"] = extract_int(field_expr)
            case "category":
                move["category"] = DAMAGE_CATEGORY[extract_int(field_expr)]
            case "criticalHitStage":
                # expansion stores this as an "additional" critical hit stage
                # ei format instead says all moves have an implicit critical hit
                # stage of 1
                move["critRatio"] = extract_int(field_expr) + 1
            case "contestCategory":
                move["contestType"] = CONTEST_CATEGORY[extract_int(field_expr)]
            case (
                "bitingMove"
                | "ballisticMove"
                | "ignoresSubstitute"
                | "cantUseTwice"
                | "makesContact"
                | "thawsUser"
                | "powderMove"
                | "pulseMove"
                | "punchingMove"
                | "magicCoatAffected"
                | "slicingMove"
                | "snatchAffected"
                | "soundMove"
                | "windMove"
            ):
                move["flags"][FLAGS_EXPANSION_TO_EI[field_name]] = 1
            case "ignoresProtect" | "mirrorMoveBanned":
                # ei format stores these as a flag for if they are affected by
                # or can be invoked by these effects
                del move["flags"][FLAGS_EXPANSION_TO_EI[field_name]]
            case _:
                pass

    # cleanup: expansion flags sound moves as both sound and ignores substitute
    # ei format only expects sound for these instances
    if "sound" in move["flags"] and "bypasssub" in move["flags"]:
        del move["flags"]["bypasssub"]

    return move


def parse_moves_data(moves_data: ExprList, move_constants: dict = None, description_constants: dict = None) -> dict:
    all_moves = {}
    for move_init in moves_data:
        try:
            move = parse_move(move_init, move_constants, description_constants)
            key = name_key(move["name"])
            all_moves[key] = move
        except Exception as err:
            print("error parsing move")
            print(move_init.show())
            raise err

    return all_moves


def parse_moves(fname: pathlib.Path) -> dict:
    moves_data: ExprList
    with yaspin(text=f"Loading moves data: {fname}", color="cyan") as spinner:
        moves_data = load_truncated(
            fname,
            extra_includes=[
                r"-include",
                r"constants/battle.h",
                r"-include",
                r"constants/moves.h",
            ],
        )
        spinner.ok("✅")

    # Load move constants to get proper move IDs
    expansion_path = fname.parent.parent.parent  # Go up to the expansion root
    move_constants = parse_move_constants(expansion_path)
    
    # Load description constants to resolve constant references
    description_constants = parse_description_constants(fname)

    return parse_moves_data(moves_data, move_constants, description_constants)

# used in toEidex?
def parse_move_constants(expansion_path: pathlib.Path) -> dict:
    """
    Parse move constants from the moves.h header file.
    
    Args:
        expansion_path: Path to the pokeemerald-expansion directory
        
    Returns:
        Dictionary mapping move constant names to their values
    """
    moves_header = expansion_path / "include" / "constants" / "moves.h"
    return parse_constants_from_header(moves_header)
