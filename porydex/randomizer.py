"""Utilities for working with the randomization metadata that is stored in the
pokeemerald-expansion source tree.

The vanilla game engine (and by extension pokeemerald-expansion) encodes, for
each species, a bit-mask named `randomizerMode` that dictates under which
randomisation modes that Pokémon is eligible to be selected.  The possible
modes are defined as macros in `include/config/randomizer.h` of the expansion
project:

    #define RANDOMIZER_MODE_WILD_ENCOUNTERS   0x01
    #define RANDOMIZER_MODE_TRAINER_POKEMON   0x02
    #define RANDOMIZER_MODE_GIFT_POKEMON      0x04
    ...

This helper module exposes functions to:

1. Parse the randomizer modes from the header file
2. Extract species randomization data with proper structure
3. Export randomization data to JSON format

The functions here *do not* try to guess a default path to the header – they
leverage ``porydex.config`` which already knows where the user's local checkout
of pokeemerald-expansion is located.
"""

from __future__ import annotations

from typing import Dict, List
import pathlib
import re
import json

from porydex import config

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_ENUM_PATTERN = re.compile(
    r"([A-Za-z0-9_]+),"
)

# Randomizer constants
MON_RANDOMIZER_INVALID = 3

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_randomizer_modes(header_path: pathlib.Path | None = None) -> Dict[str, int]:
    """Parse *randomizer.h* and return a mapping of mode-name -> integer value.

    Parameters
    ----------
    header_path
        Optional path to a *randomizer.h* file.  If *None* the helper will use
        ``porydex.config.expansion / 'include' / 'config' / 'randomizer.h'``.
    """

    if header_path is None:
        config.load()  # Ensure config is loaded
        header_path = (
            config.expansion / "include" / "config" / "randomizer.h"
        )

    modes: Dict[str, int] = {}

    try:
        with header_path.open("r", encoding="utf-8") as fp:
            content = fp.read()
            
            # Look for the RandomizerFeature enum
            feature_match = re.search(r'enum RandomizerFeature\s*\{([^}]+)\}', content, re.DOTALL)
            if feature_match:
                enum_content = feature_match.group(1)
                enum_index = 0
                for line in enum_content.split('\n'):
                    line = line.strip()
                    if line and not line.startswith('//') and line != '{':
                        match = _ENUM_PATTERN.match(line)
                        if match:
                            name = match.group(1)
                            if name != 'MAX_MON_MODE':  # Skip the dummy end marker
                                modes[name] = enum_index
                                enum_index += 1
    except FileNotFoundError:
        # It is entirely possible that the user has not yet cloned the
        # expansion repo in the configured location.  Failing silently (with an
        # empty dict) is less intrusive than exploding – the caller can decide
        # what to do when the result is empty.
        pass

    return modes


def get_species_randomization_data(species_data: Dict[str, dict]) -> List[Dict]:
    """Return array of species randomization data with proper structure.
    
    Each species object contains:
    - id: The species number (num field)
    - isLegendary: Boolean indicating if the species is legendary, mythical, or ultra beast
    - mode: The randomization mode value from the species data
    - baseStat: The total base stat (sum of all base stats)
    
    Parameters
    ----------
    species_data
        Dictionary of species data from parse_species function
        
    Returns
    -------
    List[Dict]
        Array of species randomization data objects
    """
    
    result = []
    
    for species_name, species_info in species_data.items():
        species_num = species_info.get("num", 0)
        is_legendary = species_info.get("isLegendary", False)
        is_mythical = species_info.get("isMythical", False)
        is_ultra_beast = species_info.get("isUltraBeast", False)
        randomizer_mode = species_info.get("randomizerMode", 0)
        
        # Calculate base stat total (BST) by summing all base stats
        base_stats = species_info.get("baseStats", {})
        base_stat_total = sum([
            base_stats.get("hp", 0),
            base_stats.get("atk", 0),
            base_stats.get("def", 0),
            base_stats.get("spa", 0),
            base_stats.get("spd", 0),
            base_stats.get("spe", 0)
        ])
        
        # Combine legendary, mythical, and ultra beast flags according to C logic:
        # return gSpeciesInfo[species].isLegendary || gSpeciesInfo[species].isMythical || gSpeciesInfo[species].isUltraBeast;
        is_randomizer_legendary = is_legendary or is_mythical or is_ultra_beast
        
        result.append({
            "id": species_num,
            "isLegendary": is_randomizer_legendary,
            "mode": randomizer_mode,
            "baseStat": base_stat_total
        })
    
    return result


def classify_species_by_mode(
    species_data: Dict[str, dict], mode_value: int
) -> Dict[int, bool]:
    """Return a *species-number -> is_randomizable* mapping for the given mode.

    The function expects that every Pokémon dictionary (i.e. the values of
    *species_data*) follows the structure produced by
    ``porydex.parse.species.parse_species`` – in particular it optionally
    contains the key ``'randomizerMode'`` which stores the bit-mask copied from
    the original C data.
    
    A species can be randomized if:
    - Their randomizerMode is NOT MON_RANDOMIZER_INVALID (3)
    - AND their isLegendary property is NOT TRUE when using Normal Randomization
    """

    result: Dict[int, bool] = {}
    
    for species_name, species_info in species_data.items():
        species_num = species_info.get("num", 0)
        randomizer_mode = species_info.get("randomizerMode", 0)
        is_legendary = species_info.get("isLegendary", False)
        is_mythical = species_info.get("isMythical", False)
        is_ultra_beast = species_info.get("isUltraBeast", False)
        
        # Check if species can be randomized (not MON_RANDOMIZER_INVALID)
        can_randomize = randomizer_mode != MON_RANDOMIZER_INVALID
        
        # For normal randomization, legendary/mythical/ultra beast Pokémon are excluded
        if mode_value == 0:  # Assuming 0 is normal randomization mode
            is_randomizer_legendary = is_legendary or is_mythical or is_ultra_beast
            can_randomize = can_randomize and not is_randomizer_legendary
        
        result[species_num] = can_randomize

    return result


def extract_randomizer_data():
    """Extract randomization data and export to randomize.json
    
    This function parses the randomizer modes from the pokeemerald-expansion
    header file and creates a JSON file that contains species randomization data.
    The output file is saved as 'randomize.json' in the configured output directory.
    
    The output structure is:
    {
        "modes": {
            "RANDOMIZE_WILD_MON": 0,
            "RANDOMIZE_TRAINER_MON": 1,
            ...
        },
        "species": [
            {
                "id": 1,
                "isLegendary": false,
                "mode": 0,
                "baseStat": 318
            },
            ...
        ]
    }
    """
    
    config.load()
    
    # Ensure output directory exists
    config.output.mkdir(parents=True, exist_ok=True)
    
    # Parse the randomizer modes from the header
    modes = parse_randomizer_modes()
    
    if not modes:
        print("Warning: Could not parse randomizer modes from header file.")
        print("Make sure the expansion path is correctly configured and the randomizer.h file exists.")
        return
    
    # Parse species data to get the randomizerMode and isLegendary fields
    expansion_data = config.expansion / "src" / "data"
    
    # We need to parse the basic dependencies for species parsing
    from porydex.parse.abilities import parse_abilities
    from porydex.parse.items import parse_items, get_item_names_list
    from porydex.parse.moves import parse_moves
    from porydex.parse.form_tables import parse_form_tables
    from porydex.parse.form_change_tables import parse_form_change_tables
    from porydex.parse.maps import parse_maps
    from porydex.parse.learnsets import parse_level_up_learnsets, parse_teachable_learnsets
    from porydex.parse.national_dex import parse_national_dex_enum
    from porydex.parse.species import parse_species
    
    abilities = parse_abilities(expansion_data / "abilities.h")
    items_data = parse_items(expansion_data / "items.h")
    items = get_item_names_list(items_data)
    
    moves = parse_moves(expansion_data / "moves_info.h")
    max_move_id = max(move.get("moveId", move["num"]) for move in moves.values())
    move_names = [""] * (max_move_id + 1)
    for move in moves.values():
        move_id = move.get("moveId", move["num"])
        move_names[move_id] = move["name"]
    
    forms = parse_form_tables(expansion_data / "pokemon" / "form_species_tables.h")
    form_changes = parse_form_change_tables(
        expansion_data / "pokemon" / "form_change_tables.h"
    )
    map_sections = parse_maps(expansion_data / "region_map" / "region_map_entries.h")
    
    # Load move constants for learnset parsing
    from porydex.parse.moves import parse_constants_from_header
    move_constants = parse_constants_from_header(
        pathlib.Path("../include/constants/moves.h")
    )
    
    lvlup_learnsets = parse_level_up_learnsets(
        expansion_data / "pokemon" / "level_up_learnsets.h",
        move_names,
        move_constants,
        {},  # raw_move_id_to_move_names_index - simplified for randomizer
    )
    teach_learnsets = parse_teachable_learnsets(
        expansion_data / "pokemon" / "teachable_learnsets.h", move_names
    )
    national_dex = parse_national_dex_enum(
        config.expansion / "include" / "constants" / "pokedex.h"
    )
    
    # Parse species data
    species, _ = parse_species(
        expansion_data / "pokemon" / "species_info.h",
        abilities,
        items,
        move_names,
        forms,
        form_changes,
        map_sections,
        lvlup_learnsets,
        teach_learnsets,
        national_dex,
        [],  # included_mons - empty for randomizer
    )
    
    # Create the randomization data structure
    randomize_data = {
        "modes": modes,
        "species": get_species_randomization_data(species)
    }
    
    # Write to randomize.json
    output_file = config.output / "randomize.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(randomize_data, f, indent=2, ensure_ascii=False)
    
    print(f"Randomization data exported to {output_file}")
    print(f"Found {len(modes)} randomization modes:")
    for mode_name in modes.keys():
        print(f"  - {mode_name}")
    print(f"Processed {len(randomize_data['species'])} species")
