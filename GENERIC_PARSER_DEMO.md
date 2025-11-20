# Generic Table Parser Demo

This demonstrates a **reusable approach** to parsing C data structures without writing domain-specific parsers for each file.

## Problem Statement

Previously, each new data file required:
- A new parser module (~200-400 lines)
- Custom AST walking code
- Manual handling of compiler-specific macro expansions
- Repeated boilerplate for common patterns

## Solution: Generic Table Extraction

Instead of domain-specific parsers, we created **generic utilities** that handle common C patterns:

### Architecture

```
porydex/parse/
├── generic_table.py       # Reusable extraction utilities
│   ├── parse_enum_from_header()          # Extract enum constants
│   ├── parse_define_constants()          # Extract #define macros
│   ├── extract_designated_init_table()   # Parse multi-dimensional arrays
│   ├── extract_struct_fields()           # Extract struct initializers
│   └── find_variable_by_name()           # AST search helper
│
└── mugshots.py            # Domain-specific parser (60 lines vs 200-400)
    ├── parse_incbin_graphics()   # Extract INCBIN declarations
    └── parse_mugshots()           # Main entry point
```

### Code Comparison

#### Old Approach (domain-specific)
```python
# Would require ~200-400 lines like existing parsers:
# - Custom enum parsing
# - Custom AST walking
# - Custom struct extraction
# - Manual index resolution
# - Hardcoded constant mappings
```

#### New Approach (generic)
```python
# mugshots.py - Only 104 lines including docstrings!

from porydex.parse.generic_table import (
    extract_designated_init_table,
    find_variable_by_name,
    parse_enum_from_header,
)

def parse_mugshots(expansion: pathlib.Path) -> dict:
    # 1. Parse enums (reusable)
    mugshot_enums = parse_enum_from_header(constants_file, "Mugshots")
    emote_enums = parse_enum_from_header(constants_file, "MugshotEmotes")

    # 2. Extract INCBIN graphics (domain-specific regex)
    graphics_map = parse_incbin_graphics(source_file)

    # 3. Load AST (existing infrastructure)
    ast_nodes = load_data(source_file, extra_includes=[...])

    # 4. Find table (reusable)
    table_decl = find_variable_by_name(ast_nodes, "sFieldMugshots")

    # 5. Extract structure (reusable)
    mugshots_table = extract_designated_init_table(
        table_decl,
        enum_mappings=[mugshot_enums, emote_enums],
        symbol_table=graphics_map
    )

    return {"mugshots": mugshots_table, ...}
```

## Demo Results

```bash
$ cd porydex && source .venv/bin/activate
$ python test_mugshots.py
```

### Output
```
============================================================
Generic Table Parser Demo: Field Mugshots
============================================================

Expansion path: /Users/spencer/dev/pokemon-hearth
Parsing mugshots...

✅ Loading mugshots data: field_mugshots.h

============================================================
Summary
============================================================
Mugshot types:     146
Emote types:       2
Total entries:     133
Graphics symbols:  137

============================================================
Full Structure Example: MUGSHOT_OKADA
============================================================
{
  "EMOTE_NORMAL": {
    "gfx": "graphics/field_mugshots/okada/normal.4bpp.smol",
    "pal": "gObjectEventPal_Npc_Cold"
  },
  "EMOTE_SEXY": {
    "gfx": "graphics/field_mugshots/okada/sexy.4bpp.smol",
    "pal": "gObjectEventPal_Npc_Cold"
  }
}

✅ Full output saved to: mugshots_demo.json
```

## Benefits

### 1. **Dramatic Code Reduction**
- **mugshots.py**: 104 lines (including docstrings)
- **Typical parser**: 200-400 lines
- **~70% reduction in code**

### 2. **Reusability**
Functions in `generic_table.py` work for:
- Multi-dimensional arrays (mugshots, forms, encounters)
- Single-dimensional arrays (abilities, items)
- Enum-indexed tables
- Define-indexed tables
- Mixed indexing

### 3. **Maintainability**
- Bug fixes in `generic_table.py` benefit ALL parsers
- Domain logic separated from extraction logic
- Clear entry points for new developers

### 4. **Future Applications**

This approach can handle:

| Data Structure | Current Parser | Generic Approach |
|----------------|---------------|------------------|
| Field Mugshots | ❌ None | ✅ 104 lines |
| Form Tables | ⚠️ 169 lines | ✅ ~80 lines |
| Encounters | ⚠️ 418 lines | ✅ ~150 lines |
| Learnsets | ⚠️ 187 lines | ✅ ~100 lines |

## Files Created

1. **`porydex/parse/generic_table.py`** - Reusable extraction utilities
2. **`porydex/parse/mugshots.py`** - Domain-specific mugshots parser
3. **`test_mugshots.py`** - Demonstration script
4. **`mugshots_demo.json`** - Generated output

## Next Steps

### Immediate
- ✅ Demonstrated feasibility with mugshots
- Integrate into `data_loader.py` if needed
- Add to `porydex.py extract` command

### Future Refactoring
- Migrate existing parsers to use generic utilities:
  - `form_tables.py` (169 lines → ~80 lines)
  - `encounters.py` (418 lines → ~150 lines)
  - `learnsets.py` (187 lines → ~100 lines)
- Add more generic helpers:
  - `extract_array_of_structs()` for simple 1D arrays
  - `extract_union_initializer()` for union types
  - `resolve_macro_constants()` for complex expressions

### Design Principles Applied
- **DRY**: Generic functions eliminate repetitive parsing code
- **Separation of Concerns**: Domain logic separate from AST traversal
- **Composition**: Small, focused functions that combine
- **Simplicity**: Less code = fewer bugs
