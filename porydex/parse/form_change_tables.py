import functools
import pathlib
import re
from typing import Dict, List, Tuple, Any

from pycparser.c_ast import ArrayDecl, Decl
from yaspin import yaspin

from porydex.parse import load_table_set, extract_id, extract_int

print("DEBUG: form_change_tables.py module loaded")

_FORM_CHANGE_TABLE_PATTERN = re.compile(r's(.+)FormChangeTable')

def dump_ast_structure(decl: Decl, name: str):
    """Debug function to dump the AST structure of a declaration."""
    print(f"DEBUG: AST structure for {name}:")
    print(f"  Type: {type(decl)}")
    print(f"  Name: {decl.name}")
    print(f"  Type type: {type(decl.type)}")
    
    if hasattr(decl, 'init') and decl.init:
        print(f"  Init type: {type(decl.init)}")
        if hasattr(decl.init, 'exprs'):
            print(f"  Init exprs count: {len(decl.init.exprs)}")
            for i, expr in enumerate(decl.init.exprs):
                print(f"    Expr {i}: {type(expr)}")
                if hasattr(expr, 'exprs'):
                    print(f"      Sub-exprs count: {len(expr.exprs)}")
                    for j, sub_expr in enumerate(expr.exprs):
                        print(f"        Sub-expr {j}: {type(sub_expr)} = {sub_expr}")
                else:
                    print(f"      Value: {expr}")

def parse_form_change_table_decl(minimal: Decl, full: Decl) -> Tuple[str, List[List[Any]]]:
    """Parse a single form change table declaration."""
    name = full.name
    true_name = re.match(_FORM_CHANGE_TABLE_PATTERN, name)
    if not true_name:
        raise ValueError(f'form change table symbol does not match expected name pattern: {name}')

    true_name = true_name.group(1)
    
    print(f"DEBUG: Parsing form change table '{name}' -> '{true_name}'")
    
    # Dump AST structure for debugging
    dump_ast_structure(minimal, f"minimal_{name}")
    dump_ast_structure(full, f"full_{name}")
    
    result = []
    for i, (minimal_expr, full_expr) in enumerate(zip(minimal.init.exprs, full.init.exprs)):
        print(f"DEBUG: Processing entry {i} in {name}")
        
        # Each form change entry is a struct initializer with multiple fields
        if hasattr(minimal_expr, 'exprs') and len(minimal_expr.exprs) >= 2:
            print(f"DEBUG: Entry {i} has {len(minimal_expr.exprs)} expressions")
            
            # Use extract_int to get the numeric value of the form change method
            # pycparser will resolve the constant to its numeric value during preprocessing
            try:
                method_id = extract_int(minimal_expr.exprs[0])  # method type as numeric value
                print(f"DEBUG: Entry {i} method_id (numeric): {method_id}")
            except Exception as e:
                print(f"DEBUG: Entry {i} failed to extract method_id as int: {e}")
                method_id = extract_id(minimal_expr.exprs[0])
                print(f"DEBUG: Entry {i} method_id (string): {method_id}")
            
            try:
                target_species_id = extract_int(minimal_expr.exprs[1])  # target species as numeric value
                print(f"DEBUG: Entry {i} target_species_id (numeric): {target_species_id}")
            except Exception as e:
                print(f"DEBUG: Entry {i} failed to extract target_species_id as int: {e}")
                # Fallback to string if numeric extraction fails
                try:
                    target_species_id = extract_id(minimal_expr.exprs[1])
                    print(f"DEBUG: Entry {i} target_species_id (string fallback): {target_species_id}")
                except Exception as e2:
                    print(f"DEBUG: Entry {i} failed to extract target_species_id entirely: {e2}")
                    target_species_id = "UNKNOWN"
            
            # Skip terminator entries (FORM_CHANGE_TERMINATOR = 0)
            if method_id == 0:
                print(f"DEBUG: Entry {i} is terminator, stopping")
                break
                
            # Extract parameters if available (param1, param2, etc.)
            parameters = []
            if len(minimal_expr.exprs) > 2:
                print(f"DEBUG: Entry {i} has {len(minimal_expr.exprs) - 2} parameters")
                for j, param_expr in enumerate(minimal_expr.exprs[2:]):
                    try:
                        # Try to extract as integer first (preferred for numeric IDs)
                        param_value = extract_int(param_expr)
                        parameters.append(param_value)
                        print(f"DEBUG: Entry {i} param {j} (int): {param_value}")
                    except:
                        try:
                            # Fallback to identifier if integer extraction fails
                            param_value = extract_id(param_expr)
                            parameters.append(param_value)
                            print(f"DEBUG: Entry {i} param {j} (id): {param_value}")
                        except:
                            # If neither works, skip this parameter
                            print(f"DEBUG: Entry {i} param {j} failed to extract")
                            continue
            
            # Create form change array: [method, targetSpecies, paramToMethod]
            # Use first parameter as paramToMethod, or None if no parameters
            parameter_to_method = parameters[0] if parameters else None
            
            form_change_entry = [method_id, target_species_id, parameter_to_method]
            result.append(form_change_entry)
            print(f"DEBUG: Entry {i} final form_change_entry: {form_change_entry}")
        else:
            print(f"DEBUG: Entry {i} has no expressions or insufficient expressions")
    
    print(f"DEBUG: Final result for {name}: {result}")
    return true_name, result

def all_form_change_table_decls(minimal: List[Decl], full: List[Decl]) -> Dict[str, List[List[Any]]]:
    """Parse all form change table declarations from AST."""
    print(f"DEBUG: all_form_change_table_decls - minimal count: {len(minimal)}, full count: {len(full)}")
    
    # Debug: Show some sample declarations
    print(f"DEBUG: Sample minimal declarations:")
    for i in range(min(5, len(minimal))):
        print(f"  {i}: {minimal[i].name if hasattr(minimal[i], 'name') else 'no name'}")
    
    print(f"DEBUG: Sample full declarations:")
    for i in range(min(10, len(full))):
        print(f"  {i}: {full[i].name if hasattr(full[i], 'name') else 'no name'}")
    
    # Find where static const struct FormChange declarations start
    start = 0
    for i, decl in enumerate(full):
        if not isinstance(decl.type, ArrayDecl):
            start = i + 1
            break
    
    print(f"DEBUG: Found start index: {start}")
    print(f"DEBUG: Checking {len(minimal)} minimal declarations against {len(full) - start} full declarations")
    
    result = {}
    for i, (min_entry, full_entry) in enumerate(zip(minimal, full[start:])):
        print(f"DEBUG: Processing entry {i}: {full_entry.name}")
        
        try:
            name, table_data = parse_form_change_table_decl(min_entry, full_entry)
            result[name] = table_data
            print(f"DEBUG: Successfully parsed form change table: {name}")
        except ValueError as e:
            print(f"DEBUG: Skipping entry {i}: {e}")
            continue  # Skip entries that don't match the pattern instead of failing
    
    print(f"DEBUG: Successfully parsed {len(result)} form change tables")
    return result

def parse_form_change_tables(fname: pathlib.Path) -> Dict[str, List[List[Any]]]:
    """
    Parse form change tables from form_change_tables.h file.
    
    Returns a dictionary mapping species names to form change requirement arrays.
    Each form change requirement is in format: [method, parameterToMethod, targetSpecies]
    
    Uses pycparser for proper C parsing and constant resolution.
    """
    print(f"DEBUG: parse_form_change_tables called with fname: {fname}")
    print(f"DEBUG: File exists: {fname.exists()}")
    
    minimal: List[Decl]
    full: List[Decl]
    with yaspin(text=f'Loading form change tables: {fname}', color='cyan') as spinner:
        print(f"DEBUG: About to call load_table_set for minimal preprocessing")
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
        print(f"DEBUG: Minimal preprocessing complete, got {len(minimal)} declarations")
        
        print(f"DEBUG: About to call load_table_set for full preprocessing")
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
        print(f"DEBUG: Full preprocessing complete, got {len(full)} declarations")
        spinner.ok("✅")

    print(f"DEBUG: About to call all_form_change_table_decls")
    result = all_form_change_table_decls(minimal, full)
    print(f"DEBUG: all_form_change_table_decls returned {len(result)} tables")
    return result
