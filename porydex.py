import argparse
import json
import pathlib
import os
import sys

import porydex.config
from porydex.toEidex import eiDex
from porydex.common import PICKLE_PATH, name_key
from porydex.parse.abilities import parse_abilities
from porydex.parse.encounters import parse_encounters
from porydex.parse.form_tables import parse_form_tables
from porydex.parse.form_change_tables import parse_form_change_tables
from porydex.parse.form_change_constants import export_form_change_constants
from porydex.parse.items import (
    parse_items,
    get_item_names_list,
    get_item_constants_dict,
)
from porydex.parse.learnsets import parse_level_up_learnsets, parse_teachable_learnsets
from porydex.parse.maps import parse_maps
from porydex.parse.moves import parse_moves
from porydex.parse.national_dex import parse_national_dex_enum
from porydex.parse.species import parse_species
from porydex.parse.trainer_parties import parse_trainer_parties
from porydex.parse.trainers import parse_trainers

MAX_SPECIES_EXPANSION = 1560 + 1


def prepend_file(f, s: str):
    f_data = f.read()
    f.seek(0, 0)
    f.write(s + f_data)


def config_show(_):
    porydex.config.load()
    print(f"compiler command:  {str(porydex.config.compiler)}")
    print(f"path to expansion: {str(porydex.config.expansion)}")
    print(f"output directory:  {str(porydex.config.output)}")
    print(f"output format:     {str(porydex.config.format)}")
    print(f"include mons file: {str(porydex.config.included_mons_file)}")
    print(f"custom abilities:  {str(porydex.config.custom_ability_defs)}")


def config_set(args):
    if args.expansion:
        assert (
            args.expansion.resolve().exists()
        ), f"specified expansion directory {args.expansion} does not exist"
        porydex.config.expansion = args.expansion.resolve()

    porydex.config.load()
    update = False

    if args.compiler:
        porydex.config.compiler = args.compiler
        update = True

    if args.output:
        porydex.config.output = args.output.resolve()
        update = True

    if args.format:
        porydex.config.format = args.format
        update = True

    if args.included_species_file:
        porydex.config.included_mons_file = args.included_species_file
        update = True

    if args.custom_ability_defs:
        porydex.config.custom_ability_defs = args.custom_ability_defs
        update = True

    if update:
        porydex.config.save()
    else:
        print("No config options given; nothing to do")


def config_clear(_):
    porydex.config.clear()


def extract(args: argparse.Namespace):
    """Extract all data from the expansion."""

    if args.reload:
        for f in PICKLE_PATH.glob("*"):
            os.remove(f)

    porydex.config.load()

    [
        path.mkdir(parents=True) if not path.exists() else ()
        for path in (PICKLE_PATH, porydex.config.output)
    ]

    expansion_data = porydex.config.expansion / "src" / "data"

    # Handle trainers subcommand
    if args.command == "trainers":
        parse_trainers(expansion_data)
        return
    # custom_headers = pathlib.Path("custom_headers")
    moves = parse_moves(expansion_data / "moves_info.h")
    # import pprint

    # pprint.pprint(moves)
    # import sys

    # sys.exit(0)
    # Create move_names array using the move IDs from constants, not sorted by num
    # This ensures move_names[move_id] corresponds to the correct move
    max_move_id = max(move.get("moveId", move["num"]) for move in moves.values())
    move_names = [""] * (max_move_id + 1)  # Initialize with empty strings
    for move in moves.values():
        move_id = move.get("moveId", move["num"])
        move_names[move_id] = move["name"]

    # Create a mapping from raw move IDs (from learnsets) to move_names array indices
    # This is needed because learnsets use raw move IDs, but move_names is indexed by moveId
    raw_move_id_to_move_names_index = {}
    for move in moves.values():
        raw_move_id = move["num"]  # This is the raw move ID from the moves data
        move_id = move.get("moveId", move["num"])  # This is the moveId (from constants)
        raw_move_id_to_move_names_index[raw_move_id] = move_id

    abilities = parse_abilities(expansion_data / "abilities.h")

    items_data = parse_items(expansion_data / "items.h")
    with open(porydex.config.output / "items.json", "w+", encoding="utf-8") as outf:
        json.dump(items_data, outf, indent=4, ensure_ascii=False)
    items = get_item_names_list(items_data)
    item_constants = get_item_constants_dict(items_data)

    forms = parse_form_tables(expansion_data / "pokemon" / "form_species_tables.h")

    # Parse form change tables
    form_changes = parse_form_change_tables(
        expansion_data / "pokemon" / "form_change_tables.h"
    )

    # Export form change constants as JSON maps
    export_form_change_constants(porydex.config.output)
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
        raw_move_id_to_move_names_index,
    )
    teach_learnsets = parse_teachable_learnsets(
        expansion_data / "pokemon" / "teachable_learnsets.h", move_names
    )
    national_dex = parse_national_dex_enum(
        porydex.config.expansion / "include" / "constants" / "pokedex.h"
    )

    included_mons = []
    if porydex.config.included_mons_file:
        with open(porydex.config.included_mons_file, "r", encoding="utf-8") as included:
            included_mons = list(
                filter(
                    lambda s: len(s) > 0, map(lambda s: s.strip(), included.readlines())
                )
            )

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
        included_mons,
    )

    # Parse trainer parties
    trainer_parties = parse_trainer_parties(expansion_data / "trainer_parties.h")

    # Convert trainer parties to consistent format with numeric IDs
    from porydex.parse.trainer_parties import convert_to_consistent_format

    # Create constant mappings for conversion
    species_constants = {}
    for species_data in species.values():
        species_name = f"SPECIES_{species_data['name'].upper()}"
        species_constants[species_name] = species_data["num"]

    move_constants = {}
    for i, move in enumerate(move_names):
        if move and move != "None":
            move_name = f"MOVE_{move.upper().replace(' ', '_').replace('-', '_')}"
            move_constants[move_name] = i

    ability_constants = {}
    if isinstance(abilities, dict):
        for ability_name, ability_data in abilities.items():
            if isinstance(ability_data, dict) and "id" in ability_data:
                ability_constants[ability_name] = ability_data["id"]
    elif isinstance(abilities, list):
        for i, ability in enumerate(abilities):
            if ability and ability != "None":
                ability_name = (
                    f"ABILITY_{ability.upper().replace(' ', '_').replace('-', '_')}"
                )
                ability_constants[ability_name] = i

    item_constants = {}
    if isinstance(items, dict):
        for item_name, item_data in items.items():
            if isinstance(item_data, dict) and "id" in item_data:
                item_constants[item_name] = item_data["id"]
    elif isinstance(items, list):
        for i, item in enumerate(items):
            if item and item != "None":
                item_name = f"ITEM_{item.upper().replace(' ', '_').replace('-', '_')}"
                item_constants[item_name] = i

    # Convert trainer parties to consistent format
    consistent_trainer_parties = convert_to_consistent_format(
        trainer_parties,
        species_constants,
        move_constants,
        ability_constants,
        item_constants,
        items,  # Pass the actual item names list
    )

    species_names = ["????????????"] * (MAX_SPECIES_EXPANSION + 1)
    for mon in species.values():
        if mon.get("cosmetic", False):
            species_names[mon["num"]] = mon["name"].split("-")[0]
        else:
            species_names[mon["num"]] = mon["name"]

    # cleanup cosmetic forms and missingno from species
    to_purge = ["missingno"]
    for key, mon in species.items():
        if mon.get("cosmetic", False):
            to_purge.append(key)
    for key in to_purge:
        del species[key]

    # species_names = [mon['name'] for mon in sorted(species.values(), key=lambda m: m['num'])]
    # encounters = parse_encounters(expansion_data / "wild_encounters.h", species_names)

    # Re-index num to nationalDex on the species before finishing up
    for _, mon in species.items():
        mon["num"] = mon["nationalDex"]
        del mon["nationalDex"]

    # Write trainer parties JSON regardless of format

    # Pass the export_species parameter based on command line args
    export_species = not args.no_species
    eiDex(
        moves,
        consistent_trainer_parties,
        export_species=export_species,
        abilities=abilities,
        items=items,
        move_names=move_names,
        forms=forms,
        form_changes=form_changes,
        level_up_learnsets=lvlup_learnsets,
        teachable_learnsets=teach_learnsets,
        national_dex=national_dex,
    )


def main():
    argp = argparse.ArgumentParser(
        prog="porydex",
        description="generate data exports from pokeemerald-expansion for ei format",
    )
    subp = argp.add_subparsers(required=True)

    config_p = subp.add_parser("config", help="configuration options for porydex")
    config_subp = config_p.add_subparsers(required=True)

    config_show_p = config_subp.add_parser(
        "show", help="show configured options for porydex"
    )
    config_show_p.set_defaults(func=config_show)

    config_set_p = config_subp.add_parser(
        "set", help="set configurable options for porydex"
    )
    config_set_p.add_argument(
        "-e",
        "--expansion",
        action="store",
        help="path to the root of your pokeemerald-expansion repository; default: ../pokeemerald-expansion",
        type=pathlib.Path,
    )
    config_set_p.add_argument(
        "-c",
        "--compiler",
        action="store",
        help="command for or path to the compiler to be used for pre-processing; default: gcc",
        type=pathlib.Path,
    )
    config_set_p.add_argument(
        "-o",
        "--output",
        action="store",
        help="path to output directory for extracted data files; default: ./out",
        type=pathlib.Path,
    )
    config_set_p.add_argument(
        "-f",
        "--format",
        help="format for output files",
        type=porydex.config.OutputFormat.argparse,
        choices=list(porydex.config.OutputFormat),
    )
    # config_set_p.add_argument(
    #     "-i",
    #     "--included-species-file",
    #     help="text file describing species to be included in the pokedex",
    #     type=pathlib.Path,
    # )
    # config_set_p.add_argument(
    #     "-a",
    #     "--custom-ability-defs",
    #     help="JSON file describing custom ability definitions and descriptions",
    #     type=pathlib.Path,
    # )
    config_set_p.set_defaults(func=config_set)

    config_clear_p = config_subp.add_parser("clear", help="clear configured options")
    config_clear_p.set_defaults(func=config_clear)

    extract_p = subp.add_parser("extract", help="run data extraction")
    extract_subp = extract_p.add_subparsers(
        dest="command", help="extraction subcommands"
    )

    # Add trainers subcommand
    trainers_p = extract_subp.add_parser("trainers", help="extract trainer data only")
    trainers_p.add_argument(
        "--reload",
        action="store_true",
        help="if specified, flush the cache of parsed data and reload from expansion",
    )
    trainers_p.set_defaults(func=extract)

    # Add default extract subcommand (for when no subcommand is specified)
    extract_p.add_argument(
        "--reload",
        action="store_true",
        help="if specified, flush the cache of parsed data and reload from expansion",
    )
    extract_p.add_argument(
        "--no-species",
        action="store_true",
        help="if specified, skip species data export (for ei format only)",
    )
    extract_p.set_defaults(func=extract, command=None)

    args = argp.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
