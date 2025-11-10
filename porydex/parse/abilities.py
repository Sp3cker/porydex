import pathlib
import re

from pycparser.c_ast import ExprList, NamedInitializer
from yaspin import yaspin

from porydex.parse import extract_int, extract_u8_str, load_truncated


def parse_ability_constants(constants_file: pathlib.Path) -> dict:
    """Parse ability constants from the abilities.h enum file."""
    constants = {}

    with open(constants_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Pattern to match enum entries like "ABILITY_NAME = value,"
    pattern = r'(ABILITY_[A-Z_]+)\s*=\s*(\d+)'
    matches = re.findall(pattern, content)

    for constant_name, value_str in matches:
        try:
            constants[constant_name] = int(value_str)
        except ValueError:
            pass

    return constants

def get_ability_name(struct_init: NamedInitializer) -> str:
    for field_init in struct_init.expr.exprs:
        if field_init.name[0].name == 'name':
            return extract_u8_str(field_init.expr)

    print(struct_init.show())
    raise ValueError('no name for ability structure')

def all_ability_names(abilities_data, ability_constants: dict) -> list[str]:
    print(f"DEBUG: Processing {len(abilities_data)} ability entries")
    print(f"DEBUG: Ability constants loaded: {len(ability_constants)}")
    print(f"DEBUG: First entry type: {type(abilities_data[0]) if abilities_data else 'N/A'}")

    d_abilities = {}
    for i, init in enumerate(abilities_data):
        try:
            # Get the ability constant name (like "ABILITY_OVERGROW")
            ability_constant_name = init.name[0].name

            # Look up the constant's numeric value
            if ability_constant_name in ability_constants:
                ability_id = ability_constants[ability_constant_name]
            else:
                print(f"WARNING: Unknown ability constant: {ability_constant_name}")
                ability_id = 0

            ability_name = get_ability_name(init)
            d_abilities[ability_id] = ability_name

            if i < 3:  # Debug first 3
                print(f"DEBUG: Entry {i}: {ability_constant_name} -> ID={ability_id}, Name={ability_name}")
        except Exception as e:
            if i < 3:
                print(f"DEBUG: Entry {i}: Failed to parse - {e}")

    print(f"DEBUG: Parsed {len(d_abilities)} abilities")
    print(f"DEBUG: Sample abilities dict: {list(d_abilities.items())[:5]}")
    if d_abilities:
        print(f"DEBUG: Max ability ID: {max(d_abilities.keys())}")

        capacity = max(d_abilities.keys()) + 1
        l_abilities = [d_abilities[0]] * capacity
        for i, name in d_abilities.items():
            l_abilities[i] = name

        print(f"DEBUG: Created abilities list with {len(l_abilities)} entries")
        print(f"DEBUG: Ability at index 65 (OVERGROW): {l_abilities[65] if len(l_abilities) > 65 else 'N/A'}")
    else:
        l_abilities = []

    return l_abilities

def parse_abilities(fname: pathlib.Path) -> list[str]:
    abilities_data: ExprList
    with yaspin(text=f'Loading abilities data: {fname}', color='cyan') as spinner:
        # First, parse the ability constants from the header file
        import porydex.config
        constants_file = porydex.config.expansion / "include" / "constants" / "abilities.h"
        ability_constants = parse_ability_constants(constants_file)

        from porydex.parse import load_data
        full_data = load_data(fname, extra_includes=[r'-include', r'constants/abilities.h'])

        # Find ALL gAbilitiesInfo declarations and use the one with an initializer
        abilities_decl = None
        found_count = 0
        for decl in full_data:
            if hasattr(decl, 'name') and decl.name == 'gAbilitiesInfo':
                found_count += 1
                if decl.init is not None:
                    abilities_decl = decl

        if not abilities_decl:
            raise ValueError(f"Could not find gAbilitiesInfo declaration with initializer (found {found_count} total)")

        # Check if it's an InitList or something else
        if hasattr(abilities_decl.init, 'exprs'):
            abilities_data = abilities_decl.init.exprs
        else:
            abilities_data = []

        spinner.ok("✅")

    return all_ability_names(abilities_data, ability_constants)
