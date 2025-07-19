"""
Module for parsing species data into a structured object format.
This module provides functionality to convert parsed species data into
a standardized object format with numeric IDs for types, abilities, moves, etc.

Example usage:
    # Simple usage - parse all species from the expansion
    from porydex.parse.species_object import parse_all_generations
    
    species_data = parse_all_generations()
    bulbasaur = species_data["1"]  # Get Bulbasaur by species ID
    print(f"Species: {bulbasaur['speciesName']}")
    print(f"Types: {bulbasaur['types']}")  # [13, 4] for Grass/Poison
    print(f"Stats: {bulbasaur['stats']}")  # [HP, ATK, DEF, SPA, SPD, SPE]
    
    # Advanced usage - parse specific files with custom dependencies
    from porydex.parse.species_object import parse_species_to_object
    import pathlib
    
    species_file = pathlib.Path("src/data/pokemon/species_info/gen_1_families.h")
    # ... load dependencies (abilities, items, moves, etc.) ...
    species_data = parse_species_to_object(species_file, abilities, items, moves, ...)
"""
#Below is a reference target species object
#1. Ignore the order of the stats array. We have achieved proper parsing of that ✅
#2. The evolution parameters are [method, parameterForMethod, targetId] ✅ FIXED
#3. The current implementation does not parse `tmMoves` correctly. Note the full `tmMoves` array below. ✅ FIXED
#4. The siblings property is an array of ids for forms. We will handle this later. ✅ ADDED (placeholder)
#5. Missing baseForm property has been added ✅ ADDED
#6. speciesName should be base name (e.g., "Darumaka"), nameKey should be hyphenated form (e.g., "Darumaka-Galar") ✅ FIXED
#7. forms should contain species IDs, not names 🟡 MVP (form change parser added, falls back to legacy)
#  "989": {
#     "speciesId": 989,
#     "speciesName": "Darumaka",
#     "types": [16],
#     "stats": [70, 90, 45, 50, 15, 45],
#     "abilities": [55, 0, 39],
#     "heldItems": [0, 0],
#     "levelUpMoves": [
#       [181, 1],
#       [33, 1],
#       [269, 4],
#       [44, 8],
#       [419, 12],
#       [526, 16],
#       [423, 20],
#       [29, 24],
#       [8, 28],
#       [253, 32],
#       [187, 36],
#       [59, 40],
#       [37, 44],
#       [276, 48]
#     ],
#     "tmMoves": [
#       257, 428, 269, 58, 59, 91, 280, 53, 126, 317, 168, 315, 360, 157, 447,
#       369, 7, 8, 276, 526, 612, 423, 424, 241, 394, 264, 117, 218, 237, 102,
#       363, 182, 99, 216, 290, 164, 779, 92, 263, 156, 214
#     ],
#     "eggMoves": [172, 264, 573, 359, 510, 612, 36, 281],
#     "dexId": 554,
#     "evolutions": [[7, 990, 215]],
#     "forms": [["FORM_CHANGE_BATTLE_MEGA_EVOLUTION_ITEM", "ITEM_VENUSAURITE", "SPECIES_VENUSAUR_MEGA"]],
#     "formId": 1,
#     "nameKey": "Darumaka-Galar",
#     "siblings": [554],
#     "baseForm": 554
#   },
import pathlib
from collections import defaultdict
from typing import Dict, List, Any, Optional

from yaspin import yaspin
from pycparser.c_ast import ExprList

from porydex.common import name_key
from porydex.model import DAMAGE_TYPE
from porydex.parse import load_truncated, extract_int, extract_id, extract_u8_str
from porydex.parse.species import parse_mon


def parse_species_to_object(fname: pathlib.Path,
                           abilities: List[str],
                           items: List[str],
                           move_names: List[str],
                           forms: Dict[str, Dict[int, str]],
                           form_changes: Dict[str, List[List[Any]]],
                           level_up_learnsets: Dict[str, Dict[str, List[int]]],
                           teachable_learnsets: Dict[str, Dict[str, List[str]]],
                           national_dex: Dict[str, int],
                           tm_moves: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    Parse species data and return it in a structured object format.
    
    Args:
        fname: Path to the species data file
        abilities: List of ability names indexed by ID
        items: List of item names indexed by ID
        move_names: List of move names indexed by ID (e.g., move_names[1] = "Pound")
        forms: Dictionary mapping form table names to form data
        form_changes: Dictionary mapping form change table names to form change data
        level_up_learnsets: Dictionary of level-up learnsets
        teachable_learnsets: Dictionary of teachable learnsets
        national_dex: Dictionary mapping species names to national dex numbers
        tm_moves: List of TM move names
        
    Returns:
        Dictionary with species ID as key and species object as value
    """
    
    # Load the species data
    with yaspin(text=f'Loading species data for object parsing: {fname}', color='cyan') as spinner:
        species_data = load_truncated(fname, extra_includes=[
            r'-include', r'constants/moves.h',
        ])
        spinner.ok("✅")
    
    result = {}
    
    for species_init in species_data:
        try:
            # Parse the basic species data using existing function
            mon, evos, lvlup_learnset, teach_learnset = parse_mon(
                species_init, abilities, items, forms, form_changes, 
                level_up_learnsets, teachable_learnsets, national_dex
            )
            
            # Skip if no name
            if 'name' not in mon or not mon['name']:
                continue
                
            # Create the object in the desired format
            species_obj = create_species_object(
                mon, evos, lvlup_learnset, teach_learnset, 
                abilities, items, move_names, forms, form_changes, tm_moves
            )
            
            if species_obj:
                result[str(mon['num'])] = species_obj
                
        except Exception as err:
            print(f'Error parsing species {species_init.name if hasattr(species_init, "name") else "unknown"}')
            print(species_init.show() if hasattr(species_init, "show") else str(species_init))
            raise err
    
    return result


def create_species_object(mon: Dict[str, Any],
                         evos: List[Any],
                         lvlup_learnset: Dict[str, List[int]],
                         teach_learnset: Dict[str, List[str]],
                         abilities: List[str],
                         items: List[str],
                         move_names: List[str],
                         forms: Dict[str, Dict[int, str]],
                         form_changes: Dict[str, List[List[Any]]],
                         tm_moves: List[str]) -> Optional[Dict[str, Any]]:
    """
    Create a species object in the desired format.
    
    Args:
        mon: Parsed species data
        evos: Evolution data
        lvlup_learnset: Level-up moves data
        teach_learnset: Teachable moves data
        abilities: List of ability names
        items: List of item names
        move_names: List of move names indexed by ID
        forms: Form data
        form_changes: Form change data
        tm_moves: List of TM move names
        
    Returns:
        Species object dictionary or None if invalid
    """
    
    # Get types as numeric IDs
    types = []
    if 'types' in mon:
        for type_name in mon['types']:
            try:
                type_id = DAMAGE_TYPE.index(type_name)
                types.append(type_id)
            except ValueError:
                print(f"Warning: Unknown type '{type_name}' for {mon.get('name', 'unknown')}")
    
    # Get stats in the correct order [HP, ATTACK, DEFENSE, SPATTACK, SPDEFENSE, SPEED]
    stats = []
    if 'baseStats' in mon:
        base_stats = mon['baseStats']
        stats = [
            base_stats.get('hp', 0),
            base_stats.get('atk', 0),
            base_stats.get('def', 0),
            base_stats.get('spa', 0),
            base_stats.get('spd', 0),
            base_stats.get('spe', 0)
        ]
    
    # Get abilities as numeric IDs
    abilities_list = [0, 0, 0]  # [ability1, ability2, hiddenAbility]
    if 'abilities' in mon:
        # The mon['abilities'] contains ability names mapped to slots
        # We need to find the numeric IDs
        ability_data = mon['abilities']
        
        # Regular abilities
        if '0' in ability_data:
            ability_name = ability_data['0']
            try:
                abilities_list[0] = abilities.index(ability_name) if ability_name != 'None' else 0
            except (ValueError, TypeError):
                abilities_list[0] = 0
                
        if '1' in ability_data:
            ability_name = ability_data['1']
            try:
                abilities_list[1] = abilities.index(ability_name) if ability_name != 'None' else 0
            except (ValueError, TypeError):
                abilities_list[1] = 0
                
        # Hidden ability
        if 'H' in ability_data:
            ability_name = ability_data['H']
            try:
                abilities_list[2] = abilities.index(ability_name) if ability_name != 'None' else 0
            except (ValueError, TypeError):
                abilities_list[2] = 0
    
    # Get held items as numeric IDs
    held_items = [0, 0]  # [uncommon, rare]
    if 'items' in mon:
        item_data = mon['items']
        if 'U' in item_data:
            item_name = item_data['U']
            try:
                held_items[0] = items.index(item_name) if item_name != 'None' else 0
            except (ValueError, TypeError):
                held_items[0] = 0
        if 'R' in item_data:
            item_name = item_data['R']
            try:
                held_items[1] = items.index(item_name) if item_name != 'None' else 0
            except (ValueError, TypeError):
                held_items[1] = 0
    
    # Create reverse mapping from name_key format to move ID
    # The move_names parameter is a list of move names indexed by ID
    # The learnsets use name_key() format for move names
    move_name_to_id = {}
    for move_id, move_name in enumerate(move_names):
        if move_name and move_name != 'None':
            move_name_to_id[name_key(move_name)] = move_id
    
    # Parse level-up moves
    level_up_moves = []
    for move_name_key, levels in lvlup_learnset.items():
        if move_name_key in move_name_to_id:
            move_id = move_name_to_id[move_name_key]
            for level in levels:
                if move_id > 0:  # Only add valid moves
                    level_up_moves.append([move_id, level])
        else:
            print(f"Warning: Unknown move '{move_name_key}' in level-up learnset for {mon.get('name', 'unknown')}")
    
    # Sort level-up moves by level
    level_up_moves.sort(key=lambda x: x[1])
    
    # Parse TM moves and egg moves
    tm_move_ids = []
    egg_move_ids = []
    
    # Create a set of TM move name keys for faster lookup
    tm_move_name_keys = set()
    for tm_name in tm_moves:
        if tm_name and tm_name != 'None':
            tm_move_name_keys.add(name_key(tm_name))
    
    # In the teachable learnsets:
    # 'm' = TM/Machine moves 
    # 't' = Other teachable moves (egg moves)
    if 'm' in teach_learnset:  # TM/Machine moves
        for move_name_key in teach_learnset['m']:
            if move_name_key in move_name_to_id:
                move_id = move_name_to_id[move_name_key]
                if move_id > 0:  # Only add valid moves
                    tm_move_ids.append(move_id)
            else:
                print(f"Warning: Unknown TM move '{move_name_key}' for {mon.get('name', 'unknown')}")
    
    if 't' in teach_learnset:  # Egg moves (other teachable moves)
        for move_name_key in teach_learnset['t']:
            if move_name_key in move_name_to_id:
                move_id = move_name_to_id[move_name_key]
                if move_id > 0:  # Only add valid moves
                    egg_move_ids.append(move_id)
            else:
                print(f"Warning: Unknown egg move '{move_name_key}' for {mon.get('name', 'unknown')}")
    
    # Remove duplicates and sort
    tm_move_ids = sorted(list(set(tm_move_ids)))
    egg_move_ids = sorted(list(set(egg_move_ids)))
    
    # Parse evolutions
    evolution_data = []
    for evo in evos:
        if len(evo) >= 3:
            # evo format: [method, param, target_species]
            method = evo[0]
            param = evo[1]
            target_species = evo[2]
            
            # Extract method ID properly
            if hasattr(method, 'value'):
                method_id = method.value
            elif hasattr(method, 'name'):
                # Handle enum names
                method_id = int(method.name.split('_')[-1]) if method.name.split('_')[-1].isdigit() else 4  # Default to EVO_LEVEL
            else:
                method_id = int(method) if isinstance(method, (int, str)) else 4
            
            # Evolution format should be [method, parameterForMethod, targetId]
            evolution_data.append([method_id, param, target_species])
    
    # Handle forms and name parsing
    forms_list = None
    form_id = 0
    siblings = []
    base_form = mon['num']  # Default to self
    
    # Extract base species name and form name
    species_full_name = mon['name']
    base_species_name = species_full_name
    form_name = None
    name_key_value = species_full_name
    
    # Check if this is a form variant (contains hyphen)
    if '-' in species_full_name:
        parts = species_full_name.split('-', 1)
        base_species_name = parts[0]  # e.g., "Darumaka" from "Darumaka-Galar"
        form_name = parts[1]          # e.g., "Galar" from "Darumaka-Galar"
        name_key_value = species_full_name  # Keep the hyphenated form for nameKey
    
    # Convert forms from names to form change requirements if available
    forms_list = None
    
    # For MVP: Only use form change data if it's available and not empty
    if form_changes:
        # Look for form change table for this species
        species_name = mon.get('name', '')
        form_change_table_name = None
        
        # Try different possible form change table names
        possible_names = [
            base_species_name,
            species_name,
            species_full_name
        ]
        
        for name in possible_names:
            if name in form_changes:
                form_change_table_name = name
                break
        
        if form_change_table_name and form_changes[form_change_table_name]:
            # Convert form change entries to the required format: [method, parameterToMethod, targetSpecies]
            forms_list = form_changes[form_change_table_name]
    
    # Fallback to legacy behavior if no form change data available
    if forms_list is None:
        if 'formeOrder' in mon and len(mon['formeOrder']) > 1:
            # Fallback: use forme order as simple array (legacy behavior)
            forms_list = mon['formeOrder']
        elif 'otherFormes' in mon:
            # Fallback: use other formes (legacy behavior)
            forms_list = [mon['name']] + mon['otherFormes']
    
    # Create the final object
    species_object = {
        "speciesId": mon['num'],
        "speciesName": base_species_name,  # Use base species name, not full form name
        "types": types,
        "stats": stats,
        "abilities": abilities_list,
        "heldItems": held_items,
        "levelUpMoves": level_up_moves,
        "tmMoves": tm_move_ids,
        "eggMoves": egg_move_ids if egg_move_ids else None,
        "dexId": mon.get('nationalDex', 0),
        "evolutions": evolution_data if evolution_data else None,
        "forms": forms_list,  # Now contains form change requirement arrays
        "formId": form_id,
        "nameKey": name_key_value,  # Use hyphenated form name for nameKey
        "siblings": siblings if siblings else None,
        "baseForm": base_form
    }
    
    return species_object


def parse_all_generations_with_data(abilities: List[str],
                                   items: List[str], 
                                   move_names: List[str],
                                   forms: Dict[str, Dict[int, str]],
                                   form_changes: Dict[str, List[List[Any]]],
                                   level_up_learnsets: Dict[str, Dict[str, List[int]]],
                                   teachable_learnsets: Dict[str, Dict[str, List[str]]],
                                   national_dex: Dict[str, int],
                                   expansion_path: Optional[pathlib.Path] = None) -> Dict[str, Dict[str, Any]]:
    """
    Parse all generation species files using pre-parsed dependency data.
    This is more efficient than parse_all_generations() as it reuses already-parsed data.
    
    Args:
        abilities: Pre-parsed list of ability names indexed by ID
        items: Pre-parsed list of item names indexed by ID
        move_names: Pre-parsed list of move names indexed by ID
        forms: Pre-parsed dictionary mapping form table names to form data
        form_changes: Pre-parsed dictionary mapping form change table names to form change data
        level_up_learnsets: Pre-parsed dictionary of level-up learnsets
        teachable_learnsets: Pre-parsed dictionary of teachable learnsets
        national_dex: Pre-parsed dictionary mapping species names to national dex numbers
        expansion_path: Path to the pokeemerald-expansion directory.
                       If None, attempts to use porydex.config.expansion
        
    Returns:
        Complete dictionary with all species data in object format
    """
    
    # Import here to avoid circular imports
    import porydex.config
    
    if expansion_path is None:
        expansion_path = porydex.config.expansion
    
    # Parse the main species_info.h file which includes all generations
    species_info_file = expansion_path / "src" / "data" / "pokemon" / "species_info.h"
    
    # Get TM moves (simplified - you may need to adjust this)
    tm_moves = [move for move in move_names if 'TM' in move]# or 'TR' in move]
    
    # Parse the main species file using the pre-parsed data
    return parse_species_to_object(
        species_info_file, abilities, items, move_names, forms, form_changes,
        level_up_learnsets, teachable_learnsets, national_dex, tm_moves
    )


def parse_all_generations(expansion_path: Optional[pathlib.Path] = None) -> Dict[str, Dict[str, Any]]:
    """
    Convenience function to parse all generation species files from the expansion.
    
    This function automatically discovers and parses all species files, loads required
    dependencies, and returns the complete species data in object format.
    
    Args:
        expansion_path: Path to the pokeemerald-expansion directory.
                       If None, attempts to use porydex.config.expansion
        
    Returns:
        Complete dictionary with all species data in object format
        
    Example:
        >>> species_data = parse_all_generations()
        >>> bulbasaur = species_data["1"]  # Get Bulbasaur's data
        >>> print(bulbasaur["speciesName"])  # "Bulbasaur"
    """
    
    # Import here to avoid circular imports
    import porydex.config
    from porydex.parse.abilities import parse_abilities
    from porydex.parse.items import parse_items
    from porydex.parse.moves import parse_moves
    from porydex.parse.learnsets import parse_level_up_learnsets, parse_teachable_learnsets
    from porydex.parse.form_tables import parse_form_tables
    from porydex.parse.form_change_tables import parse_form_change_tables
    from porydex.parse.national_dex import parse_national_dex_enum
    
    if expansion_path is None:
        expansion_path = porydex.config.expansion
    
    # Parse the main species_info.h file which includes all generations
    species_info_file = expansion_path / "src" / "data" / "pokemon" / "species_info.h"
    
    # Load required data
    with yaspin(text='Loading dependencies...', color='yellow') as spinner:
        # Load abilities
        abilities_file = expansion_path / "src" / "data" / "text" / "abilities.h"
        abilities = parse_abilities(abilities_file)
        
        # Load items
        items_file = expansion_path / "src" / "data" / "text" / "items.h"
        items = parse_items(items_file)
        
        # Load moves
        moves_file = expansion_path / "src" / "data" / "text" / "moves.h"
        moves = parse_moves(moves_file)
        move_names = [
            move["name"] for move in sorted(moves.values(), key=lambda m: m["num"])
        ]
        
        # Load form tables
        form_tables_file = expansion_path / "src" / "data" / "pokemon" / "form_species_tables.h"
        forms = parse_form_tables(form_tables_file) if form_tables_file.exists() else {}
        
        # Load form change tables  
        form_change_tables_file = expansion_path / "src" / "data" / "pokemon" / "form_change_tables.h"
        form_changes = parse_form_change_tables(form_change_tables_file) if form_change_tables_file.exists() else {}
        
        # Load learnsets
        learnsets_file = expansion_path / "src" / "data" / "pokemon" / "learnsets.h"
        level_up_learnsets = parse_level_up_learnsets(learnsets_file, move_names)
        teachable_learnsets = parse_teachable_learnsets(learnsets_file, move_names)
        
        # Load national dex
        natdex_file = expansion_path / "include" / "constants" / "pokedex.h"
        national_dex = parse_national_dex_enum(natdex_file) if natdex_file.exists() else {}
        
        # Get TM moves (simplified - you may need to adjust this)
        tm_moves = [move for move in move_names if 'TM' in move or 'TR' in move]
        
        spinner.ok("✅")
    
    # Parse the main species file
    return parse_species_to_object(
        species_info_file, abilities, items, move_names, forms, form_changes,
        level_up_learnsets, teachable_learnsets, national_dex, tm_moves
    )


__all__ = [
    "parse_species_to_object", 
    "parse_all_generations", 
    "parse_all_generations_with_data", 
    "create_species_object"
]
