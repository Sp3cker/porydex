# Generic C Parser Infrastructure

## Summary

Created a **reusable generic parser** for C data structures that reduces code by ~70% compared to domain-specific parsers.

### Problem
Each new C data file required writing 200-400 lines of custom AST walking code with repeated patterns.

### Solution
Created `parse/generic_table.py` with reusable utilities that handle common C parsing patterns:
- Enum constant extraction
- Define macro extraction
- Multi-dimensional designated initializer arrays
- Struct field extraction
- Symbol resolution

### Results
✅ **Mugshots parser**: 104 lines (vs typical 200-400)
✅ **Fully functional**: Parses 133 mugshot entries across 146 types
✅ **Generates clean JSON**: Ready for consumption
✅ **Reusable**: Can be applied to other parsers

## Files Created

| File | Purpose | Lines |
|------|---------|-------|
| `parse/generic_table.py` | Reusable extraction utilities | 264 |
| `parse/mugshots.py` | Mugshots parser using generic utilities | 104 |
| `test_mugshots.py` | Demonstration script | 61 |
| `GENERIC_PARSER_DEMO.md` | Architecture explanation & comparison | - |
| `ADDING_NEW_PARSERS.md` | Templates & quick reference guide | - |

## Usage

### Quick Start
```bash
cd porydex
source .venv/bin/activate
python test_mugshots.py
```

### Output
```json
{
  "mugshots": {
    "MUGSHOT_OKADA": {
      "EMOTE_NORMAL": {
        "gfx": "graphics/field_mugshots/okada/normal.4bpp.smol",
        "pal": "gObjectEventPal_Npc_Cold"
      },
      "EMOTE_SEXY": {
        "gfx": "graphics/field_mugshots/okada/sexy.4bpp.smol",
        "pal": "gObjectEventPal_Npc_Cold"
      }
    }
  },
  "counts": {
    "mugshot_types": 146,
    "emote_types": 2,
    "entries": 133,
    "graphics_symbols": 137
  }
}
```

## Adding New Parsers

### Template
```python
from porydex.parse.generic_table import (
    extract_designated_init_table,
    find_variable_by_name,
    parse_enum_from_header,
)

def parse_feature(expansion: pathlib.Path) -> dict:
    # 1. Parse constants
    enums = parse_enum_from_header(header_file, "EnumName")

    # 2. Load AST
    ast = load_data(source_file)

    # 3. Find table
    table = find_variable_by_name(ast, "gTableName")

    # 4. Extract structure
    data = extract_designated_init_table(
        table,
        enum_mappings=[enums]
    )

    return {"data": data}
```

See `ADDING_NEW_PARSERS.md` for full guide with examples.

## Architecture

### Generic Utilities (`generic_table.py`)

| Function | Purpose |
|----------|---------|
| `parse_enum_from_header()` | Extract C enum constants with auto-increment |
| `parse_define_constants()` | Extract #define macros by prefix |
| `extract_designated_init_table()` | Parse multi-dimensional arrays with designated initializers |
| `extract_struct_fields()` | Extract all fields from struct initializer |
| `find_variable_by_name()` | Search AST for variable declaration |
| `resolve_identifier()` | Resolve ID to value using symbol table |

### Design Principles

- **Composition**: Small functions that combine
- **Reusability**: Works across different data structures
- **Separation of concerns**: Generic extraction vs domain logic
- **Simplicity**: Less code = fewer bugs

## Benefits

### 1. Dramatic Code Reduction
- Mugshots: **104 lines** (vs typical 200-400)
- **~70% less code** to write and maintain
- Future parsers benefit from same utilities

### 2. Consistency
- All parsers use same extraction patterns
- Bugs fixed once benefit all parsers
- Easier onboarding for new developers

### 3. Maintainability
- Clear separation: generic extraction vs domain logic
- Well-documented with examples
- Template-driven approach for new parsers

### 4. Future Applications
Can replace/simplify existing parsers:
- `form_tables.py` (169 lines → ~80 lines)
- `encounters.py` (418 lines → ~150 lines)
- `learnsets.py` (187 lines → ~100 lines)

## Alternative Approaches Considered

### Why Not LibClang?
- **Requires clang**: Project uses GCC
- **Overkill**: We only need struct extraction, not full semantic analysis
- **pycparser works**: Already handles our use cases

### Why Not Tree-sitter?
- **No preprocessing**: Still need GCC for macro expansion
- **Less semantic**: Syntax-only parsing
- **More complexity**: Another dependency

### Why Not Regex-Only?
- **Fragile**: Breaks on formatting changes
- **Limited**: Can't handle complex expressions
- **No constants**: Can't resolve enum values

### Our Approach (pycparser + Generic Utilities)
✅ Works with existing infrastructure
✅ Handles complex C patterns
✅ Resolves constants and symbols
✅ Minimal dependencies
✅ Dramatically reduces boilerplate

## Next Steps

### Immediate
- ✅ Demonstrated with mugshots parser
- Document in AGENTS.md (completed)
- Create templates for common patterns (completed)

### Future
- **Migrate existing parsers** to use generic utilities:
  - form_tables.py (save ~90 lines)
  - encounters.py (save ~270 lines)
  - learnsets.py (save ~90 lines)

- **Add more utilities**:
  - `extract_array_of_structs()` for simple 1D arrays
  - `extract_union_initializer()` for union types
  - `resolve_macro_constants()` for complex expressions

## Documentation

- **Overview**: This file
- **Demo**: `GENERIC_PARSER_DEMO.md` - Explanation & comparison
- **Guide**: `ADDING_NEW_PARSERS.md` - Step-by-step templates
- **Reference**: `AGENTS.md` - Updated with generic parser info
- **Example**: `parse/mugshots.py` - Working implementation
- **Test**: `test_mugshots.py` - Demonstration script

## Contact

Questions? Check the docs above or examine the working example in `parse/mugshots.py`.
