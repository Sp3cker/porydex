# Adding New Parsers: Quick Reference

## Overview

Use `generic_table.py` utilities to parse new C data files with minimal code.

## Step-by-Step Guide

### 1. Identify Data Structure Pattern

Ask:
- Is it an **array with designated initializers**? (like `table[INDEX] = {...}`)
- Does it use **enum constants** for indices?
- Are there **INCBIN** or other macro patterns?

### 2. Choose the Right Utilities

| Pattern | Use This Function |
|---------|------------------|
| C enum | `parse_enum_from_header()` |
| #define constants | `parse_define_constants()` |
| Array table | `extract_designated_init_table()` |
| Struct fields | `extract_struct_fields()` |
| Find variable | `find_variable_by_name()` |
| INCBIN graphics | Custom regex (see mugshots.py) |

### 3. Template for New Parser

```python
"""Parser for [FEATURE_NAME] data."""

import pathlib
import re

from yaspin import yaspin

from porydex.parse import load_data
from porydex.parse.generic_table import (
    extract_designated_init_table,
    find_variable_by_name,
    parse_enum_from_header,
    parse_define_constants,
)


def parse_[feature_name](expansion: pathlib.Path) -> dict:
    """
    Parse [FEATURE_NAME] data from pokeemerald-expansion.

    Args:
        expansion: Path to pokeemerald-expansion root

    Returns:
        Dictionary with parsed data
    """
    source_file = expansion / "src" / "data" / "[filename].h"
    constants_file = expansion / "include" / "constants" / "[constants].h"

    with yaspin(text=f"Loading [feature] data", color="cyan") as spinner:
        # Step 1: Parse constants (enums, defines, etc.)
        enum_constants = parse_enum_from_header(constants_file, "EnumName")

        # OR for #defines:
        # define_constants = parse_define_constants(constants_file, prefix="PREFIX_")

        # Step 2: Handle domain-specific patterns (INCBIN, macros, etc.)
        # Add custom regex/parsing here if needed

        # Step 3: Load AST
        ast_nodes = load_data(
            source_file,
            extra_includes=['-include', 'constants/[header].h']
        )

        # Step 4: Find the target variable/table
        table_decl = find_variable_by_name(ast_nodes, "g[TableName]")
        if not table_decl:
            raise ValueError("Could not find g[TableName] in source")

        # Step 5: Extract data structure
        # For 1D array:
        result = extract_struct_fields(table_decl.init)

        # For 2D array:
        # result = extract_designated_init_table(
        #     table_decl,
        #     enum_mappings=[outer_enum, inner_enum],
        #     symbol_table=optional_symbols
        # )

        spinner.ok("✅")

    return {
        "data": result,
        "counts": {
            "entries": len(result),
        }
    }
```

## Real-World Examples

### Example 1: Simple 1D Enum-Indexed Array

**C Code:**
```c
// include/constants/foo.h
enum FooType {
    FOO_NONE = 0,
    FOO_ALPHA,
    FOO_BETA,
    FOO_COUNT,
};

// src/data/foo.h
static const struct Foo gFooTable[FOO_COUNT] = {
    [FOO_ALPHA] = { .name = "Alpha", .value = 10 },
    [FOO_BETA] = { .name = "Beta", .value = 20 },
};
```

**Parser:**
```python
def parse_foo(expansion: pathlib.Path) -> dict:
    # Parse enum
    foo_enums = parse_enum_from_header(
        expansion / "include/constants/foo.h",
        "FooType"
    )

    # Load AST and find table
    ast = load_data(expansion / "src/data/foo.h")
    table = find_variable_by_name(ast, "gFooTable")

    # Extract (single dimension, so pass 1-element list)
    data = extract_designated_init_table(
        table,
        enum_mappings=[foo_enums]
    )

    return {"foos": data}
```

### Example 2: 2D Array (like mugshots)

**C Code:**
```c
enum Outer { OUTER_A, OUTER_B };
enum Inner { INNER_X, INNER_Y };

static const struct Bar gBarTable[2][2] = {
    [OUTER_A] = {
        [INNER_X] = { .field = "value" },
        [INNER_Y] = { .field = "value2" },
    },
};
```

**Parser:**
```python
def parse_bar(expansion: pathlib.Path) -> dict:
    outer_enums = parse_enum_from_header(header_file, "Outer")
    inner_enums = parse_enum_from_header(header_file, "Inner")

    ast = load_data(source_file)
    table = find_variable_by_name(ast, "gBarTable")

    # Pass BOTH enum mappings in order: [outer, inner]
    data = extract_designated_init_table(
        table,
        enum_mappings=[outer_enums, inner_enums]
    )

    return {"bars": data}
```

### Example 3: With Symbol Resolution

**C Code:**
```c
const u32 gGraphic_A[] = INCBIN_U32("path/to/a.bin");
const u32 gGraphic_B[] = INCBIN_U32("path/to/b.bin");

static const struct Item gItems[] = {
    [ITEM_A] = { .gfx = gGraphic_A },
    [ITEM_B] = { .gfx = gGraphic_B },
};
```

**Parser:**
```python
def parse_items_with_graphics(expansion: pathlib.Path) -> dict:
    # First, extract INCBIN symbols
    with open(source_file) as f:
        content = f.read()

    graphics = {}
    pattern = r'const u32 (\w+)\[\] = INCBIN_U32\("([^"]+)"\)'
    for symbol, path in re.findall(pattern, content):
        graphics[symbol] = path

    # Then parse table with symbol resolution
    item_enums = parse_enum_from_header(constants_file, "ItemId")
    ast = load_data(source_file)
    table = find_variable_by_name(ast, "gItems")

    data = extract_designated_init_table(
        table,
        enum_mappings=[item_enums],
        symbol_table=graphics  # Resolves gGraphic_A → "path/to/a.bin"
    )

    return {"items": data, "graphics": graphics}
```

## Common Patterns

### Pattern: INCBIN Extraction

```python
def extract_incbin_declarations(source_file: pathlib.Path) -> dict[str, str]:
    """Extract INCBIN_U32/U16 symbol mappings."""
    with open(source_file) as f:
        content = f.read()

    pattern = r'const\s+(?:u32|u16)\s+(\w+)\[\]\s+=\s+INCBIN_(?:U32|U16)\("([^"]+)"\)'
    return {sym: path for sym, path in re.findall(pattern, content)}
```

### Pattern: Parse Multiple Enums

```python
def parse_all_enums(header_file: pathlib.Path) -> dict[str, dict]:
    """Parse all enums from a header file."""
    enums = {}

    # List all enum names you want
    for enum_name in ["TypeA", "TypeB", "TypeC"]:
        enums[enum_name] = parse_enum_from_header(header_file, enum_name)

    return enums
```

### Pattern: Post-Process Extracted Data

```python
def parse_feature(expansion: pathlib.Path) -> dict:
    # ... extract data ...

    # Post-process: resolve references, compute derived values, etc.
    for entry_id, entry_data in data.items():
        if 'raw_value' in entry_data:
            entry_data['computed'] = entry_data['raw_value'] * 2

        if 'symbol_ref' in entry_data and entry_data['symbol_ref'] in symbols:
            entry_data['resolved_path'] = symbols[entry_data['symbol_ref']]

    return {"data": data}
```

## Tips

### 1. **Start Simple**
- Get enum parsing working first
- Then add AST loading
- Then extraction
- Finally post-processing

### 2. **Debug with test_mugshots.py Pattern**
Create a standalone test script:
```python
#!/usr/bin/env python3
import porydex.config
from porydex.parse.your_parser import parse_your_feature

porydex.config.load()
result = parse_your_feature(porydex.config.expansion)
print(json.dumps(result, indent=2))
```

### 3. **Check AST Structure**
If extraction fails, inspect the AST:
```python
table_decl = find_variable_by_name(ast_nodes, "gYourTable")
print(table_decl.show())  # Shows AST structure
```

### 4. **Handle Missing Entries**
Some C arrays have gaps:
```c
[INDEX_1] = { ... },
[INDEX_5] = { ... },  // Indices 2-4 missing
```

This is fine - `extract_designated_init_table()` only returns initialized entries.

## Integration

Once your parser works:

1. **Add to data_loader.py** if it's needed for other parsers
2. **Add to porydex.py** if it should be exported:
   ```python
   # In extract() function:
   from porydex.parse.your_parser import parse_your_feature

   your_data = parse_your_feature(porydex.config.expansion)
   # ... save to JSON ...
   ```

3. **Update AGENTS.md** with the new dataset

## Questions?

Refer to:
- **Working example**: `porydex/parse/mugshots.py`
- **Test script**: `test_mugshots.py`
- **Generic utilities**: `porydex/parse/generic_table.py`
- **Existing patterns**: `porydex/parse/abilities.py` (simpler 1D example)
