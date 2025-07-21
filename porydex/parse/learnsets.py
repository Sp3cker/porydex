import collections
import pathlib
import re

import porydex.config

from pycparser.c_ast import Decl, ExprList
from yaspin import yaspin

from porydex.common import name_key
from porydex.parse import extract_int, load_data_and_start

def get_move_id_from_raw_id(raw_move_id: int, move_constants: dict) -> int:
    """
    Convert a raw move ID from the header file to the correct moveId from constants.
    
    Args:
        raw_move_id: The raw move ID from the header file
        move_constants: Dictionary of move constants from the header file
        
    Returns:
        The correct moveId from constants, or the raw_move_id if not found
    """
    # The raw_move_id should correspond to the constant value
    # We need to find which constant has this value
    for constant_name, constant_value in move_constants.items():
        if constant_value == raw_move_id:
            return raw_move_id  # For now, return the raw ID since that's what we're using
    
    return raw_move_id  # Fallback to raw ID if not found

def parse_level_up_learnset(decl: Decl,
                            move_names: list[str],
                            move_constants: dict = None,
                            raw_move_id_to_move_names_index: dict = None) -> dict[str, list[int]]:
    learnset = collections.defaultdict(list)
    entry_inits = decl.init.exprs
    

    
    for entry in entry_inits:
        raw_move_id = extract_int(entry.exprs[0].expr)
        if raw_move_id == 0xFFFF:
            break

        level = extract_int(entry.exprs[1].expr)
        
        # Convert raw move ID to the correct index in move_names array
        if raw_move_id_to_move_names_index and raw_move_id in raw_move_id_to_move_names_index:
            move_names_index = raw_move_id_to_move_names_index[raw_move_id]
        else:
            move_names_index = raw_move_id  # Fallback to raw ID if no mapping available
        


        if move_names_index < len(move_names) and move_names[move_names_index]:
            learnset[name_key(move_names[move_names_index])].append(level)
        else:
            print(f"WARNING: Move names index {move_names_index} (raw: {raw_move_id}) not found in move_names array")

    return learnset

def parse_teachable_learnset(decl: Decl,
                             move_names: list[str],
                             tm_moves: list[str]) -> dict[str, list[str]]:
    learnset = {
        'm': [],
        't': [],
    }
    entry_inits = decl.init.exprs
    for entry in entry_inits:
        move = extract_int(entry)
        if move == 0xFFFF:
            break

        move_name = move_names[move]
        if move_name in tm_moves:
            learnset['m'].append(name_key(move_name))
        else:
            learnset['t'].append(name_key(move_name))

    return learnset

def parse_level_up_learnsets_data(decls: list[Decl],
                                  move_names: list[str],
                                  move_constants: dict = None,
                                  raw_move_id_to_move_names_index: dict = None) -> dict[str, dict[str, list[int]]]:
    result = {}
    for decl in decls:
        try:
            learnset = parse_level_up_learnset(decl, move_names, move_constants, raw_move_id_to_move_names_index)
            result[decl.name] = learnset
        except Exception as e:
            raise e
    
    return result

def parse_teachable_learnsets_data(decls: list[Decl],
                                   move_names: list[str],
                                   tm_moves: list[str]) -> dict[str, dict[str, list[str]]]:
    return {
        decl.name: parse_teachable_learnset(decl, move_names, tm_moves)
        for decl in decls
    }

def parse_level_up_learnsets(fname: pathlib.Path,
                             move_names: list[str],
                             move_constants: dict = None,
                             raw_move_id_to_move_names_index: dict = None) -> dict[str, dict[str, list[int]]]:
    pattern = re.compile(r's(\w+)LevelUpLearnset')
    data: ExprList
    start: int

    with yaspin(text=f'Loading level-up learnsets: {fname}', color='cyan') as spinner:
        try:
            data, start = load_data_and_start(
                fname,
                pattern,
                extra_includes=[
                    rf'-I{porydex.config.expansion}/include',
                    r'-include', r'constants/moves.h',
                ]
            )
            spinner.ok("✅")
        except Exception as e:
            raise e

    result = parse_level_up_learnsets_data(data[start:], move_names, move_constants, raw_move_id_to_move_names_index)
    return result

def parse_teachable_learnsets(fname: pathlib.Path,
                              move_names: list[str]) -> dict[str, dict[str, list[str]]]:
    pattern = re.compile(r's(\w+)TeachableLearnset')
    data: ExprList
    start: int

    with yaspin(text=f'Loading teachable learnsets: {fname}', color='cyan') as spinner:
        data, start = load_data_and_start(
            fname,
            pattern,
            extra_includes=[
                rf'-I{porydex.config.expansion}/src',
                r'-include', r'constants/moves.h',
            ]
        )
        spinner.ok("✅")

    # Don't preprocess these files
    tm_moves = []
    tm_hm_list_file = porydex.config.expansion / 'include' / 'constants' / 'tms_hms.h'
    with yaspin(text=f'Loading TM/HM list: {tm_hm_list_file}', color='cyan') as spinner, open(tm_hm_list_file, 'r') as tm_hm_file:
        tm_moves = list({
            move.replace('_', ' ').title() for move in re.findall(r'F\((.*)\)', tm_hm_file.read())
        })
        spinner.ok("✅")

    return parse_teachable_learnsets_data(data[start:], move_names, tm_moves)

