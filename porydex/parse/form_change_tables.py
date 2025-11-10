import pathlib
import re
from typing import Any, Dict, List, Tuple

from pycparser.c_ast import ArrayDecl, Decl
from yaspin import yaspin

from porydex.parse import extract_id, extract_int, load_table_set

_FORM_CHANGE_TABLE_PATTERN = re.compile(r's(.+)FormChangeTable')

def dump_ast_structure(decl: Decl, name: str):
    """Debug function to dump the AST structure of a declaration."""
    pass

def parse_form_change_table_decl(minimal: Decl, full: Decl) -> Tuple[str, List[List[Any]]]:
    """Parse a single form change table declaration."""
    name = full.name
    if name is None:
        raise ValueError('form change table declaration has no name')
    true_name = re.match(_FORM_CHANGE_TABLE_PATTERN, name)
    if not true_name:
        raise ValueError(f'form change table symbol does not match expected name pattern: {name}')

    true_name = true_name.group(1)

    # Check if init exists (can be None for some declarations)
    if minimal.init is None or full.init is None:
        raise ValueError(f'form change table {name} has no initializer')
    if not hasattr(minimal.init, 'exprs') or not hasattr(full.init, 'exprs'):
        raise ValueError(f'form change table {name} initializer has no exprs')

    result = []
    for i, (minimal_expr, full_expr) in enumerate(zip(minimal.init.exprs, full.init.exprs)):
        # print(f"DEBUG: Processing entry {i} in {name}")

        # Each form change entry is a struct initializer with multiple fields
        if hasattr(minimal_expr, 'exprs') and len(minimal_expr.exprs) >= 2:
            # print(f"DEBUG: Entry {i} has {len(minimal_expr.exprs)} expressions")

            # Use extract_int to get the numeric value of the form change method
            # pycparser will resolve the constant to its numeric value during preprocessing
            try:
                method_id = extract_int(minimal_expr.exprs[0])  # method type as numeric value
            except Exception as e:
                method_id = extract_id(minimal_expr.exprs[0])

            try:
                target_species_id = extract_int(minimal_expr.exprs[1])  # target species as numeric value
            except Exception as e:
                # Fallback to string if numeric extraction fails
                try:
                    target_species_id = extract_id(minimal_expr.exprs[1])
                except Exception as e2:
                    target_species_id = "UNKNOWN"

            # Skip terminator entries (FORM_CHANGE_TERMINATOR = 0)
            if method_id == 0:
                break

            # Extract parameters if available (param1, param2, etc.)
            parameters = []
            if len(minimal_expr.exprs) > 2:
                for j, param_expr in enumerate(minimal_expr.exprs[2:]):
                    try:
                        # Try to extract as integer first (preferred for numeric IDs)
                        param_value = extract_int(param_expr)
                        parameters.append(param_value)
                    except:
                        try:
                            # Fallback to identifier if integer extraction fails
                            param_value = extract_id(param_expr)
                            parameters.append(param_value)
                        except:
                            # If neither works, skip this parameter
                            pass
                            continue

            # Create form change array: [method, targetSpecies, paramToMethod]
            # Use first parameter as paramToMethod, or None if no parameters
            parameter_to_method = parameters[0] if parameters else None

            form_change_entry = [method_id, target_species_id, parameter_to_method]
            result.append(form_change_entry)
        else:
            pass

    return true_name, result

def all_form_change_table_decls(minimal: List[Decl], full: List[Decl]) -> Dict[str, List[List[Any]]]:
    """Parse all form change table declarations from AST."""

    # Find where static const struct FormChange declarations start
    start = 0
    for i, decl in enumerate(full):
        if not isinstance(decl.type, ArrayDecl):
            start = i + 1
            break

    result = {}
    for i, (min_entry, full_entry) in enumerate(zip(minimal, full[start:])):
        try:
            name, table_data = parse_form_change_table_decl(min_entry, full_entry)
            result[name] = table_data
        except ValueError as e:
            continue  # Skip entries that don't match the pattern instead of failing

    return result

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
                                    r'-include', r'constants/moves.h',
                                    r'-include', r'config/species_enabled.h'
                                ],
                                minimal_preprocess=True)

        full = load_table_set(fname,
                             extra_includes=[
                                 r'-include', r'constants/form_change_types.h',
                                 r'-include', r'constants/species.h',
                                 r'-include', r'constants/items.h',
                                 r'-include', r'constants/abilities.h',
                                 r'-include', r'constants/moves.h',
                                 r'-include', r'config/species_enabled.h'
                             ],
                             minimal_preprocess=True)  # Use minimal preprocessing for both
        spinner.ok("✅")

    result = all_form_change_table_decls(minimal, full)
    return result
