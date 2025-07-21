import pathlib
from typing import Dict, List, Any

from pycparser.c_ast import ExprList, NamedInitializer, ArrayDecl, InitList
from yaspin import yaspin

from porydex.parse import load_truncated, extract_int, extract_u8_str


def extract_trainer_mon(struct_init: NamedInitializer) -> Dict[str, Any]:
    """Extract a single TrainerMon struct into a dictionary."""
    mon_data = {}
    
    for field_init in struct_init.expr.exprs:
        field_name = field_init.name[0].name
        
        if field_name == 'iv':
            # Handle TRAINER_PARTY_IVS macro call
            if hasattr(field_init.expr, 'args') and field_init.expr.args:
                iv_values = [extract_int(arg) for arg in field_init.expr.args.exprs]
                mon_data['iv'] = {
                    'hp': iv_values[0],
                    'atk': iv_values[1], 
                    'def': iv_values[2],
                    'spa': iv_values[3],
                    'spd': iv_values[4],
                    'spe': iv_values[5]
                }
                # Also add a boolean flag for "perfect IVs"
                mon_data['iv_perfect'] = all(iv == 31 for iv in iv_values)
            else:
                iv_val = extract_int(field_init.expr)
                mon_data['iv'] = iv_val
                mon_data['iv_perfect'] = iv_val == 31
                
        elif field_name == 'ev':
            # Handle TRAINER_PARTY_EVS macro call or function name
            if hasattr(field_init.expr, 'name'):
                # Check for predefined EV spread macros
                if field_init.expr.name == 'TRAINER_PARTY_EVS_TIMID':
                    mon_data['ev'] = [6, 0, 0, 252, 0, 252]  # HP/SpA/Speed
                elif field_init.expr.name == 'TRAINER_PARTY_EVS_MODEST':
                    mon_data['ev'] = [6, 0, 0, 252, 0, 252]  # HP/SpA/Speed
                elif field_init.expr.name == 'TRAINER_PARTY_EVS_JOLLY':
                    mon_data['ev'] = [6, 252, 0, 0, 0, 252]  # HP/Atk/Speed
                elif field_init.expr.name == 'TRAINER_PARTY_EVS_ADAMANT':
                    mon_data['ev'] = [6, 252, 0, 0, 0, 252]  # HP/Atk/Speed
                elif field_init.expr.name == 'TRAINER_PARTY_EVS_BOLD':
                    mon_data['ev'] = [252, 0, 252, 6, 0, 0]  # HP/Def
                elif field_init.expr.name == 'TRAINER_PARTY_EVS_IMPISH':
                    mon_data['ev'] = [252, 6, 252, 0, 0, 0]  # HP/Def
                elif field_init.expr.name == 'TRAINER_PARTY_EVS_HASTY_OR_NAIVE_ATK':
                    mon_data['ev'] = [0, 252, 0, 6, 0, 252]  # Atk/Speed
                elif field_init.expr.name == 'TRAINER_PARTY_EVS_HASTY_OR_NAIVE_SP_ATK':
                    mon_data['ev'] = [0, 6, 0, 252, 0, 252]  # SpA/Speed
                elif field_init.expr.name == 'TRAINER_PARTY_EVS_MILD':
                    mon_data['ev'] = [0, 6, 0, 252, 0, 252]  # SpA/Speed
                elif field_init.expr.name == 'TRAINER_PARTY_EVS_QUIET':
                    mon_data['ev'] = [252, 6, 0, 252, 0, 0]  # HP/SpA
                elif field_init.expr.name == 'TRAINER_PARTY_EVS_CALM':
                    mon_data['ev'] = [252, 0, 0, 6, 252, 0]  # HP/SpD
                else:
                    # Unknown predefined macro, use default
                    mon_data['ev'] = [6, 252, 0, 0, 0, 252]  # Default
                    print(f"Warning: Unknown EV spread macro '{field_init.expr.name}', using default")
            elif hasattr(field_init.expr, 'args') and field_init.expr.args:
                # Direct TRAINER_PARTY_EVS(hp, atk, def, spatk, spdef, speed) call
                ev_values = [extract_int(arg) for arg in field_init.expr.args.exprs]
                if len(ev_values) == 6:
                    mon_data['ev'] = ev_values
                else:
                    print(f"Warning: Expected 6 EV values, got {len(ev_values)}")
                    mon_data['ev'] = ev_values + [0] * (6 - len(ev_values))  # Pad with zeros
            else:
                # Single EV value or NULL
                ev_val = extract_int(field_init.expr)
                if ev_val == 0:
                    mon_data['ev'] = [0, 0, 0, 0, 0, 0]  # No EVs
                else:
                    mon_data['ev'] = [ev_val] * 6  # Apply to all stats
                
        elif field_name == 'lvl':
            mon_data['lvl'] = extract_int(field_init.expr)
            
        elif field_name == 'species':
            # Extract species constant (e.g., SPECIES_GLAMEOW)
            if hasattr(field_init.expr, 'name'):
                mon_data['species'] = field_init.expr.name
            else:
                mon_data['species'] = extract_int(field_init.expr)
                
        elif field_name == 'moves':
            # Handle moves array
            moves = []
            if hasattr(field_init.expr, 'exprs'):
                for move_expr in field_init.expr.exprs:
                    if hasattr(move_expr, 'name'):
                        moves.append(move_expr.name)
                    else:
                        moves.append(extract_int(move_expr))
            mon_data['moves'] = moves
            
        elif field_name == 'ability':
            # Extract ability constant (e.g., ABILITY_OWN_TEMPO)
            if hasattr(field_init.expr, 'name'):
                mon_data['ability'] = field_init.expr.name
            else:
                mon_data['ability'] = extract_int(field_init.expr)
                
        elif field_name == 'nature':
            # Extract nature constant (e.g., NATURE_JOLLY)
            if hasattr(field_init.expr, 'name'):
                mon_data['nature'] = field_init.expr.name
            else:
                mon_data['nature'] = extract_int(field_init.expr)
                
        elif field_name == 'heldItem' or field_name == 'item':
            # Extract item constant (e.g., ITEM_SILK_SCARF)
            if hasattr(field_init.expr, 'name'):
                item_name = field_init.expr.name
                mon_data['item'] = item_name
            else:
                mon_data['item'] = extract_int(field_init.expr)
                
        elif field_name == 'nickname':
            # Extract nickname string
            if hasattr(field_init.expr, 'name'):
                mon_data['nickname'] = field_init.expr.name
            else:
                mon_data['nickname'] = extract_u8_str(field_init.expr)
                
        elif field_name == 'ball':
            # Extract ball constant
            if hasattr(field_init.expr, 'name'):
                mon_data['ball'] = field_init.expr.name
            else:
                mon_data['ball'] = extract_int(field_init.expr)
                
        elif field_name == 'friendship':
            mon_data['friendship'] = extract_int(field_init.expr)
            
        elif field_name == 'gender':
            # Extract gender constant
            if hasattr(field_init.expr, 'name'):
                mon_data['gender'] = field_init.expr.name
            else:
                mon_data['gender'] = extract_int(field_init.expr)
                
        elif field_name == 'isShiny':
            mon_data['isShiny'] = extract_int(field_init.expr)
            
        elif field_name == 'teraType':
            # Extract tera type constant
            if hasattr(field_init.expr, 'name'):
                mon_data['teraType'] = field_init.expr.name
            else:
                mon_data['teraType'] = extract_int(field_init.expr)
                
        elif field_name == 'gigantamaxFactor':
            mon_data['gigantamaxFactor'] = extract_int(field_init.expr)
            
        elif field_name == 'shouldUseDynamax':
            mon_data['shouldUseDynamax'] = extract_int(field_init.expr)
            
        elif field_name == 'dynamaxLevel':
            mon_data['dynamaxLevel'] = extract_int(field_init.expr)
    
    return mon_data


def extract_trainer_party(party_init: NamedInitializer) -> Dict[str, Any]:
    """Extract a complete trainer party array."""
    party_name = party_init.name[0].name  # e.g., "sParty_GruntRusturfTunnel"
    
    party_data = {
        'name': party_name,
        'party': []
    }
    
    # Handle the array initializer
    if hasattr(party_init.expr, 'exprs'):
        for mon_init in party_init.expr.exprs:
            if isinstance(mon_init, NamedInitializer):
                mon_data = extract_trainer_mon(mon_init)
                party_data['party'].append(mon_data)
    
    return party_data


def convert_to_consistent_format(parties_data: Dict[str, Dict[str, Any]], 
                                species_constants: Dict[str, int], 
                                move_constants: Dict[str, int], 
                                ability_constants: Dict[str, int], 
                                item_constants: Dict[str, int],
                                item_names: List[str] = None) -> Dict[str, List[Dict[str, Any]]]:
    """Convert trainer parties to consistent format with numeric IDs."""
    # Nature mapping from numeric values to lowercase strings
    nature_mapping = {
        0: "hardy", 1: "lonely", 2: "brave", 3: "adamant", 4: "naughty",
        5: "bold", 6: "docile", 7: "relaxed", 8: "impish", 9: "lax",
        10: "timid", 11: "hasty", 12: "serious", 13: "jolly", 14: "naive",
        15: "modest", 16: "mild", 17: "quiet", 18: "bashful", 19: "rash",
        20: "calm", 21: "gentle", 22: "sassy", 23: "careful", 24: "quirky"
    }
    consistent_parties = {}
    
    # Create reverse mapping from item IDs to item constant names
    item_id_to_name = {v: k for k, v in item_constants.items()}
    
    for party_name, party_data in parties_data.items():
        party_list = []
        
        if 'party' in party_data:
            for mon in party_data['party']:
                consistent_mon = {}
                
                # Level is always included
                if 'lvl' in mon:
                    consistent_mon['lvl'] = mon['lvl']
                
                # Species ID mapping from constants
                if 'species' in mon:
                    species_constant = mon['species']
                    if isinstance(species_constant, str) and species_constant in species_constants:
                        consistent_mon['id'] = species_constants[species_constant]
                    elif isinstance(species_constant, int):
                        consistent_mon['id'] = species_constant
                    else:
                        # Try to extract species number from constant name
                        # This is a fallback if the constant mapping doesn't work
                        consistent_mon['id'] = species_constant
                
                # Only include other fields if they exist and are meaningful
                # Handle IVs - if any IVs are set (not all 0), mark as true
                if 'iv_perfect' in mon and mon['iv_perfect']:
                    consistent_mon['iv'] = True
                elif 'iv' in mon:
                    if isinstance(mon['iv'], list):
                        if any(iv != 0 for iv in mon['iv']):
                            consistent_mon['iv'] = True
                    elif isinstance(mon['iv'], int) and mon['iv'] > 0:
                        consistent_mon['iv'] = True
                
                if 'nature' in mon and mon['nature'] is not None:
                    nature_val = mon['nature']
                    if isinstance(nature_val, str) and nature_val.startswith('NATURE_'):
                        # Convert NATURE_TIMID -> "timid"
                        consistent_mon['nature'] = nature_val.replace('NATURE_', '').lower()
                    elif isinstance(nature_val, int):
                        # Convert numeric nature value to string using mapping
                        if nature_val in nature_mapping:
                            consistent_mon['nature'] = nature_mapping[nature_val]
                        else:
                            # Fallback to numeric if not in mapping
                            consistent_mon['nature'] = nature_val
                
                if 'ability' in mon and mon['ability']:
                    ability_val = mon['ability']
                    if isinstance(ability_val, str) and ability_val in ability_constants:
                        consistent_mon['ability'] = [ability_constants[ability_val]]
                    elif isinstance(ability_val, int):
                        consistent_mon['ability'] = [ability_val]
                
                if 'item' in mon and mon['item'] is not None:
                    item_val = mon['item']
                    if isinstance(item_val, str):
                        # Convert item constant to actual item name
                        if item_val != 'ITEM_NONE' and item_constants and item_names:
                            if item_val in item_constants:
                                item_id = item_constants[item_val]
                                if 0 <= item_id < len(item_names):
                                    consistent_mon['item'] = item_names[item_id]
                                else:
                                    consistent_mon['item'] = item_val  # Fallback to constant name
                            else:
                                consistent_mon['item'] = item_val  # Fallback to constant name
                    elif isinstance(item_val, int) and item_val != 0:
                        # Convert numeric item ID to actual item name
                        if item_names and 0 <= item_val < len(item_names):
                            consistent_mon['item'] = item_names[item_val]
                        elif item_val in item_id_to_name:
                            consistent_mon['item'] = item_id_to_name[item_val]
                        else:
                            # Fallback to numeric ID if we can't map it
                            consistent_mon['item'] = item_val
                
                if 'moves' in mon and mon['moves']:
                    move_ids = []
                    for move in mon['moves']:
                        if isinstance(move, str) and move in move_constants:
                            move_id = move_constants[move]
                            if move_id != 0:  # Skip MOVE_NONE
                                move_ids.append(move_id)
                        elif isinstance(move, int) and move != 0:
                            move_ids.append(move)
                    if move_ids:
                        consistent_mon['moves'] = move_ids
                
                if 'ev' in mon and mon['ev']:
                    if isinstance(mon['ev'], list):
                        consistent_mon['ev'] = mon['ev']
                    elif isinstance(mon['ev'], int) and mon['ev'] > 0:
                        # If it's a single EV value, convert to array format
                        consistent_mon['ev'] = [mon['ev']] * 6
                
                party_list.append(consistent_mon)
        
        consistent_parties[party_name] = party_list
    
    return consistent_parties


def parse_trainer_parties(fname: pathlib.Path) -> Dict[str, Dict[str, Any]]:
    """Parse trainer party data from trainer_parties.h file."""
    
    with yaspin(text=f'Loading trainer parties data: {fname}', color='cyan') as spinner:
        from porydex.parse import load_table_set
        parties_decls = load_table_set(fname, extra_includes=[
            r'-include', r'constants/species.h',
            r'-include', r'constants/moves.h', 
            r'-include', r'constants/abilities.h',
            r'-include', r'constants/items.h',
            r'-include', r'constants/trainers.h',
        ])
        spinner.ok("✅")
    
    # Parse all trainer parties
    all_parties = {}
    
    for i, decl in enumerate(parties_decls):
        if hasattr(decl, 'name') and decl.name and decl.name.startswith('sParty_'):
            if hasattr(decl, 'init') and decl.init:
                party_data = {
                    'name': decl.name,
                    'party': []
                }
                
                # Parse the array initializer
                if hasattr(decl.init, 'exprs'):
                    for mon_init in decl.init.exprs:
                        if hasattr(mon_init, 'exprs'):  # This should be a struct initializer
                            mon_data = {}
                            
                            for field_init in mon_init.exprs:
                                if hasattr(field_init, 'name') and len(field_init.name) > 0:
                                    field_name = field_init.name[0].name
                                    
                                    if field_name == 'lvl':
                                        mon_data['lvl'] = extract_int(field_init.expr)
                                    elif field_name == 'species':
                                        # Extract species constant and map to species ID
                                        if hasattr(field_init.expr, 'name'):
                                            species_constant = field_init.expr.name
                                            # Map SPECIES_GEODUDE -> 74 using species constants
                                            # For now, just store the constant name
                                            mon_data['species'] = species_constant
                                        else:
                                            mon_data['species'] = extract_int(field_init.expr)
                                    elif field_name == 'iv':
                                        # Handle TRAINER_PARTY_IVS macro call
                                        if hasattr(field_init.expr, 'args') and field_init.expr.args:
                                            iv_values = [extract_int(arg) for arg in field_init.expr.args.exprs]
                                            mon_data['iv_perfect'] = all(iv >= 31 for iv in iv_values)
                                            if not mon_data['iv_perfect']:
                                                mon_data['iv'] = iv_values
                                        else:
                                            mon_data['iv'] = True
                                    elif field_name == 'moves':
                                        moves = []
                                        if hasattr(field_init.expr, 'exprs'):
                                            for move_expr in field_init.expr.exprs:
                                                if hasattr(move_expr, 'name'):
                                                    moves.append(move_expr.name)
                                                else:
                                                    moves.append(extract_int(move_expr))
                                        mon_data['moves'] = moves
                                    elif field_name == 'ability':
                                        if hasattr(field_init.expr, 'name'):
                                            mon_data['ability'] = field_init.expr.name
                                        else:
                                            mon_data['ability'] = extract_int(field_init.expr)
                                    elif field_name == 'nature':
                                        if hasattr(field_init.expr, 'name'):
                                            mon_data['nature'] = field_init.expr.name
                                        else:
                                            mon_data['nature'] = extract_int(field_init.expr)
                                    elif field_name == 'heldItem' or field_name == 'item':
                                        if hasattr(field_init.expr, 'name'):
                                            item_name = field_init.expr.name
                                            mon_data['item'] = item_name
                                        else:
                                                                                        mon_data['item'] = extract_int(field_init.expr)
                                    elif field_name == 'ev':
                                        # Handle TRAINER_PARTY_EVS macro call or function name
                                        if hasattr(field_init.expr, 'name'):
                                            # Check for predefined EV spread macros
                                            macro_name = field_init.expr.name
                                            # Extract the actual name from the ID object
                                            if hasattr(macro_name, 'name'):
                                                macro_name = macro_name.name
                                        if macro_name == 'TRAINER_PARTY_EVS_TIMID':
                                            mon_data['ev'] = [6, 0, 0, 252, 0, 252]  # HP/SpA/Speed
                                        elif macro_name == 'TRAINER_PARTY_EVS_MODEST':
                                            mon_data['ev'] = [6, 0, 0, 252, 0, 252]  # HP/SpA/Speed
                                        elif macro_name == 'TRAINER_PARTY_EVS_JOLLY':
                                            mon_data['ev'] = [6, 252, 0, 0, 0, 252]  # HP/Atk/Speed
                                        elif macro_name == 'TRAINER_PARTY_EVS_ADAMANT':
                                            mon_data['ev'] = [6, 252, 0, 0, 0, 252]  # HP/Atk/Speed
                                        elif macro_name == 'TRAINER_PARTY_EVS_BOLD':
                                            mon_data['ev'] = [252, 0, 252, 6, 0, 0]  # HP/Def
                                        elif macro_name == 'TRAINER_PARTY_EVS_IMPISH':
                                            mon_data['ev'] = [252, 6, 252, 0, 0, 0]  # HP/Def
                                        elif macro_name == 'TRAINER_PARTY_EVS_HASTY_OR_NAIVE_ATK':
                                            mon_data['ev'] = [0, 252, 0, 6, 0, 252]  # Atk/Speed
                                        elif macro_name == 'TRAINER_PARTY_EVS_HASTY_OR_NAIVE_SP_ATK':
                                            mon_data['ev'] = [0, 6, 0, 252, 0, 252]  # SpA/Speed
                                        elif macro_name == 'TRAINER_PARTY_EVS_MILD':
                                            mon_data['ev'] = [0, 6, 0, 252, 0, 252]  # SpA/Speed
                                        elif macro_name == 'TRAINER_PARTY_EVS_QUIET':
                                            mon_data['ev'] = [252, 6, 0, 252, 0, 0]  # HP/SpA
                                        elif macro_name == 'TRAINER_PARTY_EVS_CALM':
                                            mon_data['ev'] = [252, 0, 0, 6, 252, 0]  # HP/SpD
                                        else:
                                            # Unknown predefined macro, use default
                                            mon_data['ev'] = [6, 252, 0, 0, 0, 252]  # Default
                                            print(f"Warning: Unknown EV spread macro '{macro_name}', using default")
                                    elif hasattr(field_init.expr, 'args') and field_init.expr.args:
                                        # Direct TRAINER_PARTY_EVS(hp, atk, def, spatk, spdef, speed) call
                                        ev_values = [extract_int(arg) for arg in field_init.expr.args.exprs]
                                        if len(ev_values) == 6:
                                            mon_data['ev'] = ev_values
                                        else:
                                            print(f"Warning: Expected 6 EV values, got {len(ev_values)}")
                                            mon_data['ev'] = ev_values + [0] * (6 - len(ev_values))  # Pad with zeros
                                    else:
                                        # Single EV value or NULL
                                        try:
                                            ev_val = extract_int(field_init.expr)
                                            if ev_val == 0:
                                                mon_data['ev'] = [0, 0, 0, 0, 0, 0]  # No EVs
                                            else:
                                                mon_data['ev'] = [ev_val] * 6  # Apply to all stats
                                        except (AttributeError, ValueError):
                                            # Handle compound literals or other complex expressions
                                            print(f"Warning: Complex EV expression in {decl.name}, using default")
                                            mon_data['ev'] = [6, 252, 0, 0, 0, 252]  # Default
                
                            party_data['party'].append(mon_data)
                
                all_parties[decl.name] = party_data
    
    return all_parties


def get_trainer_party_by_name(parties: Dict[str, Dict[str, Any]], trainer_name: str) -> Dict[str, Any]:
    """Get a specific trainer party by name."""
    party_key = f"sParty_{trainer_name}"
    return parties.get(party_key)


def get_all_species_used(parties: Dict[str, Dict[str, Any]]) -> List[str]:
    """Get a list of all species used across all trainer parties."""
    species_set = set()
    
    for party_data in parties.values():
        for mon in party_data['party']:
            species_set.add(mon['species'])
    
    return sorted(list(species_set))
