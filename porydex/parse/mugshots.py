"""Parser for field mugshots data.

Demonstrates the generic table extraction approach - this entire parser
is ~60 lines vs the typical 200-400 lines of domain-specific code.
"""

import pathlib
import re

from yaspin import yaspin

from porydex.parse import load_data
from porydex.parse.generic_table import (
    extract_designated_init_table,
    find_variable_by_name,
    parse_enum_from_header,
)


def parse_incbin_graphics(source_file: pathlib.Path) -> dict[str, str]:
    """
    Extract INCBIN_U32/INCBIN_U16 declarations to map symbols to file paths.

    Args:
        source_file: Path to C source file with INCBIN declarations

    Returns:
        Dictionary mapping symbol names to graphics file paths
    """
    graphics_map = {}

    with open(source_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Pattern: const u32 symbolName[] = INCBIN_U32("path/to/file.ext");
    pattern = r'const\s+(?:u32|u16)\s+(\w+)\[\]\s+=\s+INCBIN_(?:U32|U16)\("([^"]+)"\)'

    for match in re.finditer(pattern, content):
        symbol_name = match.group(1)
        file_path = match.group(2)
        graphics_map[symbol_name] = file_path

    return graphics_map


def parse_mugshots(expansion: pathlib.Path) -> dict:
    """
    Parse field mugshots data from pokeemerald-expansion.

    Args:
        expansion: Path to pokeemerald-expansion root

    Returns:
        Dictionary with structure:
        {
            "mugshots": {
                "MUGSHOT_HARIKO": {
                    "EMOTE_NORMAL": {
                        "gfx": "graphics/field_mugshots/hariko/normal.4bpp.smol",
                        "pal": "graphics/object_events/palettes/pal_cold.gbapal"
                    }
                },
                ...
            },
            "graphics": { ... gfx symbol mappings ... },
            "palettes": { ... pal symbol mappings ... }
        }
    """
    source_file = expansion / "src" / "data" / "field_mugshots.h"
    constants_file = expansion / "include" / "constants" / "field_mugshots.h"
    palettes_file = expansion / "src" / "data" / "object_events" / "object_event_graphics.h"

    with yaspin(text=f"Loading mugshots data: {source_file.name}", color="cyan") as spinner:
        # Step 1: Parse enum constants
        mugshot_enums = parse_enum_from_header(constants_file, "Mugshots")
        emote_enums = parse_enum_from_header(constants_file, "MugshotEmotes")

        # Step 2: Parse INCBIN graphics declarations from mugshots file
        graphics_map = parse_incbin_graphics(source_file)

        # Step 3: Parse INCBIN palette declarations from object events file
        palettes_map = parse_incbin_graphics(palettes_file)

        # Step 4: Load and parse the AST
        ast_nodes = load_data(
            source_file,
            extra_includes=['-include', 'constants/field_mugshots.h']
        )

        # Step 5: Find the table declaration
        table_decl = find_variable_by_name(ast_nodes, "sFieldMugshots")
        if not table_decl:
            raise ValueError("Could not find sFieldMugshots table in source file")

        # Step 6: Extract the table structure with both graphics and palettes as symbols
        all_symbols = {**graphics_map, **palettes_map}
        mugshots_table = extract_designated_init_table(
            table_decl,
            enum_mappings=[mugshot_enums, emote_enums],
            symbol_table=all_symbols
        )

        spinner.ok("✅")

    # Post-process: resolve gfx and pal symbol references to actual file paths
    for mugshot_id, emotes in mugshots_table.items():
        for emote_id, fields in emotes.items():
            # Resolve graphics path
            if 'gfx' in fields:
                gfx_symbol = fields['gfx']
                if gfx_symbol in graphics_map:
                    fields['gfx'] = graphics_map[gfx_symbol]
                    fields['gfx_symbol'] = gfx_symbol

            # Resolve palette path
            if 'pal' in fields:
                pal_symbol = fields['pal']
                if pal_symbol in palettes_map:
                    fields['pal'] = palettes_map[pal_symbol]
                    fields['pal_symbol'] = pal_symbol

    return {
        "mugshots": mugshots_table,
        "graphics": graphics_map,
        "palettes": palettes_map,
        "counts": {
            "mugshot_types": len(mugshot_enums),
            "emote_types": len(emote_enums),
            "entries": sum(len(emotes) for emotes in mugshots_table.values()),
            "graphics_symbols": len(graphics_map),
            "palette_symbols": len(palettes_map),
        }
    }
