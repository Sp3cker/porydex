import json
import pathlib
import re
from typing import Dict, List, Any

from pycparser import parse_file
from pycparser.c_ast import Constant

import porydex.config
from porydex.common import EXPANSION_INCLUDES, PREPROCESS_LIBC


def parse_form_change_constants(fname: pathlib.Path) -> Dict[str, Any]:
    """
    Parse form change constants from form_change_types.h file.
    
    Returns a dictionary with form change method mappings and parameter descriptions.
    """
    print(f"DEBUG: Parsing form change constants from {fname}")
    
    include_dirs = [f'-I{porydex.config.expansion / dir}' for dir in EXPANSION_INCLUDES]
    
    # Parse the file to get the AST
    ast = parse_file(
        str(fname),
        use_cpp=True,
        cpp_path=porydex.config.compiler,
        cpp_args=[
            *PREPROCESS_LIBC,
            *include_dirs,
            r'-DTRUE=1',
            r'-DFALSE=0',
        ]
    )
    
    # Read the raw file to extract comments and descriptions
    with open(fname, 'r') as f:
        content = f.read()
    
    # Extract form change method constants and their descriptions
    methods = {}
    method_descriptions = {}
    
    # Pattern to match #define FORM_CHANGE_* constants
    define_pattern = re.compile(r'#define\s+(FORM_CHANGE_\w+)\s+(\d+)')
    
    # Pattern to extract comments before defines
    comment_pattern = re.compile(r'// (.*?)(?=\n#define\s+FORM_CHANGE_)', re.DOTALL)
    
    lines = content.split('\n')
    current_comment = []
    
    for i, line in enumerate(lines):
        # Collect comments
        if line.strip().startswith('//'):
            current_comment.append(line.strip()[2:].strip())
        elif line.strip().startswith('#define FORM_CHANGE_'):
            # Process the define
            match = define_pattern.match(line.strip())
            if match:
                constant_name = match.group(1)
                constant_value = int(match.group(2))
                
                # Join accumulated comments as description
                description = ' '.join(current_comment).strip() if current_comment else ""
                
                methods[constant_value] = constant_name
                method_descriptions[constant_value] = {
                    "name": constant_name,
                    "value": constant_value,
                    "description": description
                }
                
            # Clear comments after processing
            current_comment = []
        elif line.strip() and not line.strip().startswith('//'):
            # Non-comment, non-define line - clear accumulated comments
            current_comment = []
    
    # Extract parameter constants
    parameter_constants = {}
    
    # HP comparison constants
    hp_pattern = re.compile(r'#define\s+(HP_\w+)\s+(\d+)')
    for match in hp_pattern.finditer(content):
        name = match.group(1)
        value = int(match.group(2))
        parameter_constants[value] = name
    
    # Time constants
    time_pattern = re.compile(r'#define\s+(DAY|NIGHT)\s+(\d+)')
    for match in time_pattern.finditer(content):
        name = match.group(1)
        value = int(match.group(2))
        parameter_constants[value] = name
    
    # Move learning constants
    move_pattern = re.compile(r'#define\s+(WHEN_\w+)\s+(\d+)')
    for match in move_pattern.finditer(content):
        name = match.group(1)
        value = int(match.group(2))
        parameter_constants[value] = name
    
    return {
        "form_change_methods": methods,
        "method_descriptions": method_descriptions,
        "parameter_constants": parameter_constants,
        "metadata": {
            "source_file": str(fname),
            "total_methods": len(methods),
            "total_parameters": len(parameter_constants)
        }
    }


def export_form_change_constants(output_dir: pathlib.Path, expansion_path: pathlib.Path = None):
    """
    Export form change constants to JSON files in the output directory.
    """
    if expansion_path is None:
        expansion_path = porydex.config.expansion
    
    # Parse the constants
    constants_file = expansion_path / "include" / "constants" / "form_change_types.h"
    constants_data = parse_form_change_constants(constants_file)
    
    # Write form change methods map
    methods_file = output_dir / "form_change_methods.json"
    with open(methods_file, 'w', encoding='utf-8') as f:
        json.dump(constants_data["form_change_methods"], f, indent=2, ensure_ascii=False)
    
    print(f"Successfully wrote form change methods to {methods_file}")
    
    # Write detailed method descriptions
    descriptions_file = output_dir / "form_change_method_descriptions.json"
    with open(descriptions_file, 'w', encoding='utf-8') as f:
        json.dump(constants_data["method_descriptions"], f, indent=2, ensure_ascii=False)
    
    print(f"Successfully wrote method descriptions to {descriptions_file}")
    
    # Write parameter constants
    parameters_file = output_dir / "form_change_parameters.json"
    with open(parameters_file, 'w', encoding='utf-8') as f:
        json.dump(constants_data["parameter_constants"], f, indent=2, ensure_ascii=False)
    
    print(f"Successfully wrote parameter constants to {parameters_file}")
    
    return constants_data


__all__ = ["parse_form_change_constants", "export_form_change_constants"] 