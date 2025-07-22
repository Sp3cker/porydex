import json
import pathlib
import re
from typing import Dict, Any

from pycparser import parse_file

import porydex.config
from porydex.common import EXPANSION_INCLUDES, PREPROCESS_LIBC


def parse_form_change_constants(fname: pathlib.Path) -> Dict[str, Any]:
    """
    Parse form change constants from form_change_types.h file.
    
    Extracts method mappings, parameter descriptions, and related constants
    from the header file. Returns a structured dictionary with all the data.
    """
    # Set up include paths for the preprocessor
    include_dirs = [f"-I{porydex.config.expansion / dir}" for dir in EXPANSION_INCLUDES]

    # Parse the file to get the AST (we'll use this later if needed)
    ast = parse_file(
        str(fname),
        use_cpp=True,
        cpp_path=porydex.config.compiler,
        cpp_args=[
            *PREPROCESS_LIBC,
            *include_dirs,
            r"-DTRUE=1",
            r"-DFALSE=0",
        ],
    )

    # Read the raw file content for regex parsing
    with open(fname, "r") as f:
        file_content = f.read()

    # Parse form change methods and their descriptions
    method_map = {}
    method_info = {}
    
    # Regex to match form change constant definitions
    form_change_regex = re.compile(r"#define\s+(FORM_CHANGE_\w+)\s+(\d+)")

    # Process the file line by line to capture comments
    lines = file_content.split("\n")
    comment_buffer = []

    for line in lines:
        line = line.strip()
        
        # Collect comments
        if line.startswith("//"):
            comment_buffer.append(line[2:].strip())
        elif line.startswith("#define FORM_CHANGE_"):
            # Found a form change constant - extract it
            match = form_change_regex.match(line)
            if match:
                const_name = match.group(1)
                const_value = int(match.group(2))
                
                # Build description from accumulated comments
                desc = " ".join(comment_buffer).strip() if comment_buffer else ""
                
                method_map[const_value] = const_name
                method_info[const_value] = {
                    "name": const_name,
                    "value": const_value,
                    "description": desc,
                }
            
            # Reset comment buffer after processing
            comment_buffer = []
        elif line and not line.startswith("//"):
            # Non-comment, non-define line - clear the buffer
            comment_buffer = []

    # Extract various parameter constants
    param_constants = {}
    
    # HP-related constants
    hp_regex = re.compile(r"#define\s+(HP_\w+)\s+(\d+)")
    for match in hp_regex.finditer(file_content):
        name = match.group(1)
        value = int(match.group(2))
        param_constants[value] = name

    # Time-based constants
    time_regex = re.compile(r"#define\s+(DAY|NIGHT)\s+(\d+)")
    for match in time_regex.finditer(file_content):
        name = match.group(1)
        value = int(match.group(2))
        param_constants[value] = name

    # Move learning condition constants
    move_regex = re.compile(r"#define\s+(WHEN_\w+)\s+(\d+)")
    for match in move_regex.finditer(file_content):
        name = match.group(1)
        value = int(match.group(2))
        param_constants[value] = name

    return {
        "form_change_methods": method_map,
        "method_descriptions": method_info,
        "parameter_constants": param_constants,
        "metadata": {
            "source_file": str(fname),
            "total_methods": len(method_map),
            "total_parameters": len(param_constants),
        },
    }


def export_form_change_constants(
    output_dir: pathlib.Path, expansion_path: pathlib.Path = None
):
    """
    Export form change constants to JSON files.
    
    Creates three separate JSON files:
    - form_change_methods.json: Simple value -> name mapping
    - form_change_method_descriptions.json: Detailed method info with descriptions
    - form_change_parameters.json: Parameter constants mapping
    """
    if expansion_path is None:
        expansion_path = porydex.config.expansion

    # Parse the constants from the header file
    constants_file = expansion_path / "include" / "constants" / "form_change_types.h"
    parsed_data = parse_form_change_constants(constants_file)

    # Write the methods mapping
    methods_file = output_dir / "form_change_methods.json"
    with open(methods_file, "w", encoding="utf-8") as f:
        json.dump(parsed_data["form_change_methods"], f, indent=2, ensure_ascii=False)
    print(f"Wrote form change methods to {methods_file}")

    # Write detailed descriptions
    desc_file = output_dir / "form_change_method_descriptions.json"
    with open(desc_file, "w", encoding="utf-8") as f:
        json.dump(parsed_data["method_descriptions"], f, indent=2, ensure_ascii=False)
    print(f"Wrote method descriptions to {desc_file}")

    # Write parameter constants
    params_file = output_dir / "form_change_parameters.json"
    with open(params_file, "w", encoding="utf-8") as f:
        json.dump(parsed_data["parameter_constants"], f, indent=2, ensure_ascii=False)
    print(f"Wrote parameter constants to {params_file}")

    return parsed_data


__all__ = ["parse_form_change_constants", "export_form_change_constants"]
