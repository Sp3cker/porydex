"""Generic table extractor for C designated initializer arrays.

This module provides reusable utilities for parsing C data structures without
writing domain-specific parsers for each new data file.
"""

import pathlib
import re
from typing import Any

from pycparser.c_ast import ID, ArrayRef, Decl, InitList, NamedInitializer


def parse_enum_from_header(header_path: pathlib.Path, enum_name: str | None = None) -> dict[str, int]:
    """
    Parse C enum definitions from a header file.

    Handles both explicit values (ITEM_A = 5) and implicit auto-increment.

    Args:
        header_path: Path to header file containing enum
        enum_name: Optional enum name to filter (e.g., "Mugshots")

    Returns:
        Dictionary mapping enum constant names to their integer values
    """
    constants = {}

    with open(header_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find enum block(s)
    # Use a simpler pattern that works with any enum format
    if enum_name:
        # Specific enum: enum [attributes] Name { body }
        enum_pattern = rf'enum[^{{]*{enum_name}[^{{]*\{{([^}}]+)\}}'
    else:
        # Any enum: enum [anything] { body }
        enum_pattern = r'enum[^{]*\{([^}]+)\}'

    enum_matches = re.findall(enum_pattern, content, re.DOTALL)

    for enum_body in enum_matches:
        current_value = 0

        # Match: CONSTANT_NAME or CONSTANT_NAME = value
        entry_pattern = r'(\w+)(?:\s*=\s*(\d+))?'

        for match in re.finditer(entry_pattern, enum_body):
            const_name = match.group(1)
            explicit_value = match.group(2)

            # Skip COUNT constants used for array sizing
            if const_name.endswith('_COUNT'):
                continue

            if explicit_value:
                current_value = int(explicit_value)

            constants[const_name] = current_value
            current_value += 1

    return constants


def parse_define_constants(header_path: pathlib.Path, prefix: str = "") -> dict[str, int]:
    """
    Parse #define constants from a header file.

    Args:
        header_path: Path to header file
        prefix: Optional prefix filter (e.g., "ITEM_" to only get ITEM_* constants)

    Returns:
        Dictionary mapping constant names to values
    """
    constants = {}

    with open(header_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Pattern: #define CONSTANT_NAME 123
    pattern = rf'#define\s+({prefix}\w+)\s+(\d+)'

    for match in re.finditer(pattern, content):
        const_name = match.group(1)
        value = int(match.group(2))
        constants[const_name] = value

    return constants


def extract_struct_field(struct_init: NamedInitializer, field_name: str) -> Any:
    """
    Extract a specific field value from a C struct initializer.

    Args:
        struct_init: pycparser NamedInitializer node
        field_name: Name of field to extract

    Returns:
        The field's initializer expression, or None if not found
    """
    if not hasattr(struct_init, 'expr') or not hasattr(struct_init.expr, 'exprs'):
        return None

    for field_init in struct_init.expr.exprs:
        if hasattr(field_init, 'name') and field_init.name and field_init.name[0].name == field_name:
            return field_init.expr

    return None


def resolve_identifier(expr, symbol_table: dict[str, Any] | None = None) -> Any:
    """
    Resolve an identifier expression to its value.

    Args:
        expr: pycparser expression node
        symbol_table: Optional mapping of identifiers to values

    Returns:
        The resolved value, or the identifier name if unresolved
    """
    if isinstance(expr, ID):
        if symbol_table and expr.name in symbol_table:
            return symbol_table[expr.name]
        return expr.name

    # If it's already a literal, return its value
    if hasattr(expr, 'value'):
        return expr.value

    return expr


def extract_designated_init_table(
    table_decl: Decl,
    enum_mappings: list[dict[str, int]],
    symbol_table: dict[str, Any] | None = None
) -> dict:
    """
    Extract a multi-dimensional designated initializer array.

    This handles patterns like:
        static const struct Foo table[OUTER_COUNT][INNER_COUNT] = {
            [OUTER_A] = {
                [INNER_X] = { .field1 = value1, .field2 = value2 },
                [INNER_Y] = { .field1 = value3, .field2 = value4 },
            },
            [OUTER_B] = { ... },
        };

    Args:
        table_decl: pycparser Decl node for the table variable
        enum_mappings: List of enum constant dictionaries, one per dimension
            First dict maps outer indices, second maps inner indices, etc.
        symbol_table: Optional mapping of symbol names to values

    Returns:
        Nested dictionary structure with resolved enum names as keys
    """
    if not table_decl.init or not isinstance(table_decl.init, InitList):
        return {}

    # Create reverse mappings (value -> name) for pretty output
    reverse_enums = []
    for enum_dict in enum_mappings:
        reverse_enums.append({v: k for k, v in enum_dict.items()})

    result = {}

    # Process outer dimension
    for outer_init in table_decl.init.exprs:
        if not isinstance(outer_init, NamedInitializer):
            continue

        # Resolve outer index
        outer_designator = outer_init.name[0]
        if isinstance(outer_designator, ID):
            outer_key = outer_designator.name
        else:
            # It's a literal number, look up the enum name
            outer_idx = int(outer_designator.value) if hasattr(outer_designator, 'value') else 0
            outer_key = reverse_enums[0].get(outer_idx, f"INDEX_{outer_idx}")

        result[outer_key] = {}

        # Check if there's a second dimension
        if not isinstance(outer_init.expr, InitList):
            # Single-dimension table or single struct
            result[outer_key] = extract_struct_fields(outer_init.expr, symbol_table)
            continue

        # Process inner dimension
        for inner_init in outer_init.expr.exprs:
            if not isinstance(inner_init, NamedInitializer):
                continue

            # Resolve inner index
            inner_designator = inner_init.name[0]
            if isinstance(inner_designator, ID):
                inner_key = inner_designator.name
            else:
                inner_idx = int(inner_designator.value) if hasattr(inner_designator, 'value') else 0
                inner_key = reverse_enums[1].get(inner_idx, f"INDEX_{inner_idx}") if len(reverse_enums) > 1 else f"INDEX_{inner_idx}"

            # Extract struct fields
            result[outer_key][inner_key] = extract_struct_fields(inner_init.expr, symbol_table)

    return result


def extract_struct_fields(struct_expr, symbol_table: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Extract all fields from a struct initializer.

    Args:
        struct_expr: pycparser expression node (typically InitList)
        symbol_table: Optional mapping of symbol names to values

    Returns:
        Dictionary mapping field names to resolved values
    """
    fields = {}

    if not hasattr(struct_expr, 'exprs'):
        return fields

    for field_init in struct_expr.exprs:
        if not isinstance(field_init, NamedInitializer):
            continue

        field_name = field_init.name[0].name
        field_value = resolve_identifier(field_init.expr, symbol_table)
        fields[field_name] = field_value

    return fields


def find_variable_by_name(ast_nodes: list, var_name: str) -> Decl | None:
    """
    Find a variable declaration by name in a list of AST nodes.

    Args:
        ast_nodes: List of pycparser AST nodes
        var_name: Variable name to search for

    Returns:
        Decl node if found, None otherwise
    """
    for node in ast_nodes:
        if isinstance(node, Decl) and node.name == var_name:
            # Prefer declarations with initializers
            if node.init is not None:
                return node

    # Fallback: return first match even without initializer
    for node in ast_nodes:
        if isinstance(node, Decl) and node.name == var_name:
            return node

    return None
