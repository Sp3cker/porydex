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
                mon_data['ivs'] = {
                    'hp': iv_values[0],
                    'atk': iv_values[1], 
                    'def': iv_values[2],
                    'spa': iv_values[3],
                    'spd': iv_values[4],
                    'spe': iv_values[5]
                }
            else:
                mon_data['ivs'] = extract_int(field_init.expr)
                
        elif field_name == 'lvl':
            mon_data['level'] = extract_int(field_init.expr)
            
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
                
        elif field_name == 'heldItem':
            # Extract item constant (e.g., ITEM_SILK_SCARF)
            if hasattr(field_init.expr, 'name'):
                mon_data['heldItem'] = field_init.expr.name
            else:
                mon_data['heldItem'] = extract_int(field_init.expr)
    
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


def parse_trainer_parties(fname: pathlib.Path) -> Dict[str, Dict[str, Any]]:
    """Parse trainer party data from trainer_parties.h file."""
    parties_data: ExprList
    
    with yaspin(text=f'Loading trainer parties data: {fname}', color='cyan') as spinner:
        parties_data = load_truncated(fname, extra_includes=[
            r'-include', r'constants/species.h',
            r'-include', r'constants/moves.h', 
            r'-include', r'constants/abilities.h',
            r'-include', r'constants/items.h',
            r'-include', r'constants/trainers.h',
        ])
        spinner.ok("✅")
    
    # Parse all trainer parties
    all_parties = {}
    
    for init in parties_data:
        if isinstance(init, NamedInitializer):
            # Check if this is a trainer party array (starts with "sParty_")
            party_name = init.name[0].name
            if party_name.startswith('sParty_'):
                party_data = extract_trainer_party(init)
                all_parties[party_name] = party_data
    
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
