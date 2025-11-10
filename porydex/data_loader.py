
import pathlib
from typing import Dict, List, Optional, Tuple

from porydex.common import name_key
from porydex.parse.abilities import parse_abilities
from porydex.parse.form_change_tables import parse_form_change_tables
from porydex.parse.form_tables import parse_form_tables
from porydex.parse.items import get_item_names_list, parse_items
from porydex.parse.learnsets import parse_level_up_learnsets, parse_teachable_learnsets
from porydex.parse.maps import parse_maps
from porydex.parse.moves import parse_constants_from_header, parse_moves
from porydex.parse.national_dex import parse_national_dex_enum
from porydex.parse.species import parse_species
from porydex.parse.trainer_parties import (
    convert_to_consistent_format,
    parse_trainer_parties,
)


def load_all_data(
    expansion_path: pathlib.Path,
    include_trainer_parties: bool = False,
    included_mons: Optional[List[str]] = None
):

    """Load all data from the expansion in a single place.

    This is the centralized data loading function that all extraction modes should use
    to maintain consistency and avoid duplication.

    Parameters
    ----------
    expansion_path : pathlib.Path
        Path to the pokeemerald-expansion root directory
    include_trainer_parties : bool, default=False
        Whether to parse and include trainer party data
    included_mons : List[str], optional
        List of included Pokémon names for tier classification

    Returns
    -------
    Dict
        Dictionary containing all loaded data with keys:
        - 'species': Final species dictionary (dict[str, PokemonData])
        - 'learnsets': Learnset data
        - 'abilities': Ability names list
        - 'items': Item names list
        - 'moves': Moves dictionary
        - 'move_names': Move names list indexed by ID
        - 'forms': Form tables
        - 'form_changes': Form change tables
        - 'map_sections': Map section names
        - 'national_dex': National dex mapping
        - 'trainer_parties': Trainer party data (if requested)
        - 'species_constants': Species constants mapping
        - 'move_constants': Move constants mapping
        - 'ability_constants': Ability constants mapping
        - 'item_constants': Item constants mapping
        - 'species_names': Species names indexed by ID
    """

    expansion_data = expansion_path / "src" / "data"

    # Parse ability constants and set them globally for extract_int to use
    from porydex.parse import set_ability_constants
    from porydex.parse.abilities import parse_ability_constants
    ability_constants_file = expansion_path / "include" / "constants" / "abilities.h"
    ability_constants = parse_ability_constants(ability_constants_file)
    set_ability_constants(ability_constants)

    # Parse core data
    abilities = parse_abilities(expansion_data / "abilities.h")
    items_data = parse_items(expansion_data / "items.h")
    items = get_item_names_list(items_data)
    items_full = items_data  # Keep the full item data with prices and descriptions
    moves = parse_moves(expansion_data / "moves_info.h")

    # Build move names list
    max_move_id = max(move.get("moveId", move["num"]) for move in moves.values())
    move_names = [""] * (max_move_id + 1)
    for move in moves.values():
        move_id = move.get("moveId", move["num"])
        move_names[move_id] = move["name"]

    # Parse form and map data
    forms = parse_form_tables(expansion_data / "pokemon" / "form_species_tables.h")
    form_changes = parse_form_change_tables(
        expansion_data / "pokemon" / "form_change_tables.h"
    )
    map_sections = parse_maps(
        expansion_data / "region_map" / "region_map_entries.h"
    )

    # Parse move constants and learnsets
    move_constants = parse_constants_from_header(
        expansion_path / "include" / "constants" / "moves.h"
    )
    # Note: level_up_learnsets is now a directory with multiple generation files
    # Load all generation files, with hearth.h overriding others
    learnsets_dir = expansion_data / "pokemon" / "level_up_learnsets"
    gen_files = ["gen_1.h", "gen_2.h", "gen_3.h", "gen_4.h", "gen_5.h",
                 "gen_6.h", "gen_7.h", "gen_8.h", "gen_9.h"]

    lvlup_learnsets = {}
    # Load generation files in order (later gens override earlier ones)
    for gen_file in gen_files:
        gen_path = learnsets_dir / gen_file
        if gen_path.exists():
            gen_learnsets = parse_level_up_learnsets(
                gen_path,
                move_names,
                move_constants,
                {},  # raw_move_id_to_move_names_index - simplified
            )
            lvlup_learnsets.update(gen_learnsets)

    # hearth.h overrides all other generation files
    hearth_path = learnsets_dir / "hearth.h"
    if hearth_path.exists():
        hearth_learnsets = parse_level_up_learnsets(
            hearth_path,
            move_names,
            move_constants,
            {},  # raw_move_id_to_move_names_index - simplified
        )
        lvlup_learnsets.update(hearth_learnsets)
    teach_learnsets = parse_teachable_learnsets(
        expansion_data / "pokemon" / "teachable_learnsets.h", move_names
    )

    # Parse national dex
    national_dex = parse_national_dex_enum(
        expansion_path / "include" / "constants" / "pokedex.h"
    )

    # Parse species data
    included_mons_list = included_mons if included_mons is not None else []
    species, learnsets = parse_species(
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
        included_mons_list,
    )

    # Cleanup cosmetic forms and MissingNo
    to_purge = [name_key("MissingNo.")]
    for key, mon in list(species.items()):
        if mon.get("cosmetic", False):
            to_purge.append(key)
    for key in set(to_purge):
        species.pop(key, None)

    # Re-index num to nationalDex
    for mon in species.values():
        mon["num"] = mon.pop("nationalDex")

    # Build constants mappings
    species_constants = {f"SPECIES_{mon['name'].upper()}": mon['num'] for mon in species.values()}
    move_constants_map = {f"MOVE_{name.upper().replace(' ', '_').replace('-', '_')}": idx for idx, name in enumerate(move_names) if name and name != 'None'}

    # Handle abilities constants (handle both dict and list formats)
    if isinstance(abilities, dict):
        ability_constants = {f"ABILITY_{name.upper().replace(' ', '_').replace('-', '_')}": data['id'] for name, data in abilities.items() if isinstance(data, dict) and 'id' in data}
    else:
        ability_constants = {f"ABILITY_{ab.upper().replace(' ', '_').replace('-', '_')}": idx for idx, ab in enumerate(abilities) if ab and ab != 'None'}

    # Handle items constants (handle both dict and list formats)
    if isinstance(items, dict):
        item_constants = {f"ITEM_{name.upper().replace(' ', '_').replace('-', '_')}": data['id'] for name, data in items.items() if isinstance(data, dict) and 'id' in data}
    else:
        item_constants = {f"ITEM_{it.upper().replace(' ', '_').replace('-', '_')}": idx for idx, it in enumerate(items) if it and it != 'None'}

    # Build species names for encounters (up to MAX_SPECIES_EXPANSION)
    MAX_SPECIES_EXPANSION = 1560 + 1
    species_names = ['????????????'] * (MAX_SPECIES_EXPANSION + 1)
    for mon in species.values():
        species_names[mon['num']] = mon['name'].split('-')[0] if mon.get('cosmetic', False) else mon['name']

    # Prepare result dictionary
    result = {
        'species': species,
        'learnsets': learnsets,
        'abilities': abilities,
        'items': items,
        'items_full': items_full,  # Full item data with prices and descriptions
        'moves': moves,
        'move_names': move_names,
        'forms': forms,
        'form_changes': form_changes,
        'map_sections': map_sections,
        'national_dex': national_dex,
        'level_up_learnsets': lvlup_learnsets,  # Raw level-up learnsets for eiDex
        'teachable_learnsets': teach_learnsets,  # Raw teachable learnsets for eiDx
        'species_constants': species_constants,
        'move_constants': move_constants_map,
        'ability_constants': ability_constants,
        'item_constants': item_constants,
        'species_names': species_names,
    }

    # Parse trainer parties if requested
    if include_trainer_parties:
        trainer_parties = parse_trainer_parties(expansion_data / "trainer_parties.h")
        consistent_trainer_parties = convert_to_consistent_format(
            trainer_parties,
            species_constants,
            move_constants_map,
            ability_constants,
            item_constants,
            items,
        )
        result['trainer_parties'] = consistent_trainer_parties

    return result


def load_species_data(
    expansion_path: pathlib.Path,
    included_mons: Optional[List[str]] = None
) -> Tuple[Dict[str, dict], Dict]:
    """Load only species and learnset data (lighter version of load_all_data).

    Parameters
    ----------
    expansion_path : pathlib.Path
        Path to the pokeemerald-expansion root directory
    included_mons : List[str], optional
        List of included Pokémon names for tier classification

    Returns
    -------
    Tuple[Dict[str, dict], Dict]
        Tuple of (species_dict, learnsets_dict)
    """
    all_data = load_all_data(expansion_path, include_trainer_parties=False, included_mons=included_mons)
    return all_data['species'], all_data['learnsets']
