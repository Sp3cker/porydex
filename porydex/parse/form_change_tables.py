import functools
import pathlib
import re
from typing import Dict, List, Tuple, Any

from pycparser.c_ast import ArrayDecl, Decl
from yaspin import yaspin

from porydex.parse import load_table_set, extract_id, extract_int

_FORM_CHANGE_TABLE_PATTERN = re.compile(r's(.+)FormChangeTable')

def parse_form_change_table_decl(minimal: Decl, full: Decl) -> Tuple[str, List[List[Any]]]:
    """Parse a single form change table declaration."""
    name = full.name
    true_name = re.match(_FORM_CHANGE_TABLE_PATTERN, name)
    if not true_name:
        raise ValueError(f'form change table symbol does not match expected name pattern: {name}')

    true_name = true_name.group(1)
    
    result = []
    for minimal_expr, full_expr in zip(minimal.init.exprs, full.init.exprs):
        # Each form change entry is a struct initializer with multiple fields
        if hasattr(minimal_expr, 'exprs') and len(minimal_expr.exprs) >= 2:
            method_id = extract_id(minimal_expr.exprs[0])  # method type
            target_species_id = extract_id(minimal_expr.exprs[1])  # target species
            
            # Skip terminator entries
            if method_id == 'FORM_CHANGE_TERMINATOR':
                break
                
            # Extract parameters if available (param1, param2, etc.)
            parameters = []
            if len(minimal_expr.exprs) > 2:
                for param_expr in minimal_expr.exprs[2:]:
                    try:
                        # Try to extract as identifier first
                        param_value = extract_id(param_expr)
                        parameters.append(param_value)
                    except:
                        try:
                            # Try to extract as integer
                            param_value = extract_int(param_expr)
                            parameters.append(param_value)
                        except:
                            # If neither works, skip this parameter
                            continue
            
            # Create form change array: [method, parameterToMethod, targetSpecies]
            # Use first parameter as parameterToMethod, or None if no parameters
            parameter_to_method = parameters[0] if parameters else None
            
            form_change_entry = [method_id, parameter_to_method, target_species_id]
            result.append(form_change_entry)
    
    return true_name, result

def all_form_change_table_decls(minimal: List[Decl], full: List[Decl]) -> Dict[str, List[List[Any]]]:
    """Parse all form change table declarations from AST."""
    # Find where static const struct FormChange declarations start
    start = 0
    for i, decl in enumerate(full):
        if not isinstance(decl.type, ArrayDecl):
            start = i + 1
            break

    return functools.reduce(
        lambda d, t: d.update({ t[0]: t[1] }) or d,
        [
            parse_form_change_table_decl(min_entry, full_entry)
            for min_entry, full_entry in zip(minimal, full[start:])
            if _FORM_CHANGE_TABLE_PATTERN.match(full_entry.name)
        ],
        {}
    )

def parse_form_change_tables(fname: pathlib.Path) -> Dict[str, List[List[Any]]]:
    """
    Parse form change tables from form_change_tables.h file.
    
    Returns a dictionary mapping species names to form change requirement arrays.
    Each form change requirement is in format: [method, parameterToMethod, targetSpecies]
    
    Uses pycparser for proper C parsing and constant resolution.
    """
    minimal: List[Decl]
    full: List[Decl]
    with yaspin(text=f'Loading form change tables: {fname}', color='cyan') as spinner:
        minimal = load_table_set(fname, 
                                extra_includes=[
                                    r'-include', r'constants/form_change_types.h',
                                    r'-include', r'constants/species.h', 
                                    r'-include', r'constants/items.h',
                                    r'-include', r'constants/abilities.h',
                                    r'-include', r'constants/moves.h'
                                ], 
                                minimal_preprocess=True)
        full = load_table_set(fname, 
                             extra_includes=[
                                 r'-include', r'constants/form_change_types.h',
                                 r'-include', r'constants/species.h',
                                 r'-include', r'constants/items.h', 
                                 r'-include', r'constants/abilities.h',
                                 r'-include', r'constants/moves.h'
                             ], 
                             minimal_preprocess=False)
        spinner.ok("✅")

    return all_form_change_table_decls(minimal, full)
