import argparse
import json
import os
import pathlib
import sys

import porydex.config
from porydex.common import PICKLE_PATH, name_key
from porydex.parse.abilities import parse_abilities
from porydex.parse.encounters import parse_encounters
from porydex.randomizer import extract_randomizer_data
from porydex.data_loader import load_all_data
from porydex.toEidex import eiDex

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

    # Use shared data loader to get all data in one place (DRY principle)
    include_trainer_parties = args.command != 'randomizer'  # Only load trainer parties when needed
    all_data = load_all_data(
        expansion_path=porydex.config.expansion,
        include_trainer_parties=include_trainer_parties,
        included_mons=[]  # no included species filtering
    )

    # Extract commonly used data
    species = all_data['species']
    moves = all_data['moves']
    species_names = all_data['species_names']

    # Handle randomizer subcommand
    if args.command == 'randomizer':
        extract_randomizer_data()
        return

    # Handle encounters subcommand
    if args.command == 'encounters':
        expansion_data = porydex.config.expansion / "src" / "data"
        encounters = parse_encounters(expansion_data / 'wild_encounters.h', species_names)
        output_file = porydex.config.output / 'encounters.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(encounters, f, indent=2, ensure_ascii=False)
        print(f"Encounter data exported to {output_file}")
        return

    # Default (eiDex) extraction
    export_species = not args.no_species
    eiDex(
        moves,
        all_data['trainer_parties'],
        export_species=export_species,
        abilities=all_data['abilities'],
        items=all_data['items'],
        move_names=all_data['move_names'],
        forms=all_data['forms'],
        form_changes=all_data['form_changes'],
        level_up_learnsets=all_data['learnsets'],  # Note: this might need adjustment based on eiDx function signature
        teachable_learnsets=all_data['learnsets'],  # Note: this might need adjustment
        national_dex=all_data['national_dex'],
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

    # Add encounters subcommand
    encounters_p = extract_subp.add_parser("encounters", help="extract encounter data only")
    encounters_p.add_argument(
        "--reload",
        action="store_true",
        help="if specified, flush the cache of parsed data and reload from expansion",
    )
    encounters_p.set_defaults(func=extract)

    # Add trainers subcommand
    trainers_p = extract_subp.add_parser("trainers", help="extract trainer data only")
    trainers_p.add_argument(
        "--reload",
        action="store_true",
        help="if specified, flush the cache of parsed data and reload from expansion",
    )
    trainers_p.set_defaults(func=extract)

    # Add randomizer subcommand
    randomizer_p = extract_subp.add_parser("randomizer", help="extract randomization data only")
    randomizer_p.add_argument(
        "--reload",
        action="store_true",
        help="if specified, flush the cache of parsed data and reload from expansion",
    )
    randomizer_p.set_defaults(func=extract)

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
