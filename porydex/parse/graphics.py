"""
Graphics extraction module for trainers, items, and pokemon.

Parses graphics header files to extract icon/sprite and palette mappings.
"""

import pathlib
import re
from typing import Dict, Any, Optional


def parse_trainer_graphics(expansion_path: pathlib.Path) -> Dict[str, Any]:
    """
    Parse trainer graphics from trainers.h and trainers.party.

    Returns dict mapping trainer IDs to their graphics info:
    {
        "TRAINER_SAWYER_1": {
            "trainerClass": "Hiker",
            "pic": "TRAINER_PIC_HIKER",
            "frontPic": "graphics/trainers/front_pics/hiker.4bpp.smol",
            "palette": "graphics/trainers/front_pics/hiker.gbapal"
        }
    }
    """
    trainers_h = expansion_path / "src/data/graphics/trainers.h"
    trainers_party = expansion_path / "src/data/trainers.party"

    # Step 1: Parse front pic and palette declarations from trainers.h
    pic_to_paths = {}  # Maps variable name -> file path
    palette_to_paths = {}

    with open(trainers_h, "r", encoding="utf-8") as f:
        content = f.read()

        # Match: const u32 gTrainerFrontPic_Hiker[] = INCBIN_U32("path/to/file.4bpp.smol");
        pic_pattern = (
            r'const\s+u32\s+gTrainerFrontPic_(\w+)\[\]\s*=\s*INCBIN_U32\("([^"]+)"\);'
        )
        for match in re.finditer(pic_pattern, content):
            name = match.group(1)
            path = match.group(2)
            pic_to_paths[f"gTrainerFrontPic_{name}"] = path

        # Match: const u16 gTrainerPalette_Hiker[] = INCBIN_U16("path/to/file.gbapal");
        palette_pattern = (
            r'const\s+u16\s+gTrainerPalette_(\w+)\[\]\s*=\s*INCBIN_U16\("([^"]+)"\);'
        )
        for match in re.finditer(palette_pattern, content):
            name = match.group(1)
            path = match.group(2)
            palette_to_paths[f"gTrainerPalette_{name}"] = path

    # Step 2: Parse gTrainerSprites array to map TRAINER_PIC constants to variables
    # TRAINER_SPRITE(TRAINER_PIC_HIKER, gTrainerFrontPic_Hiker, gTrainerPalette_Hiker)
    pic_id_to_vars = {}

    sprite_pattern = (
        r"TRAINER_SPRITE\(\s*(\w+)\s*,\s*(\w+)\s*,\s*(\w+)(?:\s*,\s*[^)]+)?\s*\)"
    )
    for match in re.finditer(sprite_pattern, content):
        pic_id = match.group(1)  # e.g., TRAINER_PIC_HIKER
        pic_var = match.group(2)  # e.g., gTrainerFrontPic_Hiker
        palette_var = match.group(3)  # e.g., gTrainerPalette_Hiker

        pic_id_to_vars[pic_id] = {
            "frontPic": pic_to_paths.get(pic_var),
            "palette": palette_to_paths.get(palette_var),
        }

    # Step 3: Parse trainers.party to map trainer IDs to their Pic field
    trainer_graphics = {}

    with open(trainers_party, "r", encoding="utf-8") as f:
        content = f.read()

        # Split into trainer blocks
        trainer_blocks = re.split(r"===\s+(\w+)\s+===", content)[
            1:
        ]  # Skip first empty element

        for i in range(0, len(trainer_blocks), 2):
            trainer_id = trainer_blocks[i].strip()
            block_content = trainer_blocks[i + 1] if i + 1 < len(trainer_blocks) else ""

            # Extract Pic field
            pic_match = re.search(r"^\s*Pic:\s*(.+)$", block_content, re.MULTILINE)
            if pic_match:
                trainer_class = pic_match.group(1).strip()

                # Convert trainer class name to TRAINER_PIC constant
                # "Bug Catcher" -> "TRAINER_PIC_BUG_CATCHER"
                pic_constant = "TRAINER_PIC_" + trainer_class.upper().replace(
                    " ", "_"
                ).replace("-", "_")

                # Look up graphics info
                graphics_info = pic_id_to_vars.get(pic_constant, {})

                trainer_graphics[trainer_id] = {
                    "trainerClass": trainer_class,
                    "pic": pic_constant,
                    "frontPic": graphics_info.get("frontPic"),
                    "palette": graphics_info.get("palette"),
                }

    return trainer_graphics


def parse_item_graphics(expansion_path: pathlib.Path) -> Dict[str, Any]:
    """
    Parse item graphics from items.h and graphics/items.h.

    Returns dict mapping item IDs to their graphics info:
    {
        "ITEM_POTION": {
            "icon": "graphics/items/icons/potion.4bpp.smol",
            "palette": "graphics/items/icon_palettes/potion.gbapal"
        }
    }
    """
    graphics_items_h = expansion_path / "src/data/graphics/items.h"
    items_h = expansion_path / "src/data/items.h"

    # Step 1: Parse icon and palette declarations from graphics/items.h
    icon_to_paths = {}
    palette_to_paths = {}

    with open(graphics_items_h, "r", encoding="utf-8") as f:
        content = f.read()

        # Match: const u32 gItemIcon_Potion[] = INCBIN_U32("path/to/file.4bpp.smol");
        icon_pattern = (
            r'const\s+u32\s+gItemIcon_(\w+)\[\]\s*=\s*INCBIN_U32\("([^"]+)"\)'
        )
        for match in re.finditer(icon_pattern, content):
            name = match.group(1)
            path = match.group(2)
            icon_to_paths[f"gItemIcon_{name}"] = path

        # Match: const u16 gItemIconPalette_Potion[] = INCBIN_U16("path/to/file.gbapal");
        palette_pattern = (
            r'const\s+u16\s+gItemIconPalette_(\w+)\[\]\s*=\s*INCBIN_U16\("([^"]+)"\)'
        )
        for match in re.finditer(palette_pattern, content):
            name = match.group(1)
            path = match.group(2)
            palette_to_paths[f"gItemIconPalette_{name}"] = path

    # Step 2: Parse items.h to map ITEM_* constants to icon/palette variables
    item_graphics = {}

    with open(items_h, "r", encoding="utf-8") as f:
        content = f.read()

        # Match item struct definitions: [ITEM_POTION] = { ... .iconPic = gItemIcon_Potion, .iconPalette = gItemIconPalette_Potion, ... }
        # Split into item blocks
        item_pattern = r"\[(\w+)\]\s*=\s*\{([^}]+)\}"

        for match in re.finditer(item_pattern, content, re.DOTALL):
            item_id = match.group(1)
            struct_content = match.group(2)

            # Extract iconPic and iconPalette from struct
            icon_match = re.search(r"\.iconPic\s*=\s*(\w+)", struct_content)
            palette_match = re.search(r"\.iconPalette\s*=\s*(\w+)", struct_content)

            if icon_match and palette_match:
                icon_var = icon_match.group(1)
                palette_var = palette_match.group(1)

                item_graphics[item_id] = {
                    "icon": icon_to_paths.get(icon_var),
                    "palette": palette_to_paths.get(palette_var),
                }

    return item_graphics


def parse_object_event_graphics(expansion_path: pathlib.Path) -> Dict[str, Any]:
    """
    Parse object event (overworld sprite) graphics.

    Returns dict mapping OBJ_EVENT_GFX constants to their graphics info:
    {
        "OBJ_EVENT_GFX_BRENDAN_NORMAL": {
            "sprites": ["graphics/object_events/pics/people/brendan/walking.4bpp", ...],
            "palette": "graphics/trainers/palettes/protagonist.gbapal"
        }
    }
    """
    object_event_graphics_h = expansion_path / "src/data/object_events/object_event_graphics.h"
    object_event_graphics_info_h = expansion_path / "src/data/object_events/object_event_graphics_info.h"
    object_event_pic_tables_h = expansion_path / "src/data/object_events/object_event_pic_tables.h"
    event_object_movement_c = expansion_path / "src/event_object_movement.c"

    # Step 1: Parse INCBIN declarations from object_event_graphics.h
    # Maps gObjectEventPic_* and gObjectEventPal_* to file paths
    pic_to_paths = {}
    pal_to_paths = {}

    with open(object_event_graphics_h, "r", encoding="utf-8") as f:
        content = f.read()

        # Match: const u32 gObjectEventPic_BrendanNormalRunning[] = INCBIN_U32("path1.4bpp", "path2.4bpp");
        # Note: Can have multiple paths comma-separated
        pic_pattern = r'const\s+u32\s+(gObjectEventPic_\w+)\[\]\s*=\s*INCBIN_U32\(([^)]+)\)'
        for match in re.finditer(pic_pattern, content):
            var_name = match.group(1)
            paths_str = match.group(2)
            # Extract all quoted strings
            paths = re.findall(r'"([^"]+)"', paths_str)
            pic_to_paths[var_name] = paths

        # Match: const u16 gObjectEventPal_Brendan[] = INCBIN_U16("path.gbapal");
        pal_pattern = r'const\s+u16\s+(gObjectEventPal_\w+)\[\]\s*=\s*INCBIN_U16\("([^"]+)"\)'
        for match in re.finditer(pal_pattern, content):
            var_name = match.group(1)
            path = match.group(2)
            pal_to_paths[var_name] = path

    # Step 2: Parse sPicTable_* from object_event_pic_tables.h
    # Maps sPicTable_* to list of gObjectEventPic_* symbols
    pic_table_to_pics = {}

    with open(object_event_pic_tables_h, "r", encoding="utf-8") as f:
        content = f.read()

        # Match: static const struct SpriteFrameImage sPicTable_BrendanNormal[] = {
        #            overworld_ascending_frames(gObjectEventPic_BrendanNormalRunning, 4, 4),
        #        };
        # We extract the sPicTable name and all gObjectEventPic references in that block
        table_pattern = r'static\s+const\s+struct\s+SpriteFrameImage\s+(sPicTable_\w+)\[\]\s*=\s*\{([^}]+)\}'
        for match in re.finditer(table_pattern, content):
            table_name = match.group(1)
            table_content = match.group(2)
            # Extract all gObjectEventPic_* references
            pic_refs = re.findall(r'(gObjectEventPic_\w+)', table_content)
            # Remove duplicates while preserving order
            unique_pics = list(dict.fromkeys(pic_refs))
            pic_table_to_pics[table_name] = unique_pics

    # Step 3: Parse sObjectEventSpritePalettes[] from event_object_movement.c
    # Maps OBJ_EVENT_PAL_TAG_* to gObjectEventPal_*
    pal_tag_to_pal = {}

    with open(event_object_movement_c, "r", encoding="utf-8") as f:
        content = f.read()

        # Find the sObjectEventSpritePalettes array
        # Match: {gObjectEventPal_Brendan, OBJ_EVENT_PAL_TAG_BRENDAN},
        pal_entry_pattern = r'\{(gObjectEventPal_\w+),\s*(OBJ_EVENT_PAL_TAG_\w+)\}'
        for match in re.finditer(pal_entry_pattern, content):
            pal_var = match.group(1)
            pal_tag = match.group(2)
            pal_tag_to_pal[pal_tag] = pal_var

    # Step 4: Parse gObjectEventGraphicsInfo structs from object_event_graphics_info.h
    # Extract .images and .paletteTag fields
    # Build temporary mapping from gObjectEventGraphicsInfo_* to graphics data
    info_to_graphics = {}

    with open(object_event_graphics_info_h, "r", encoding="utf-8") as f:
        content = f.read()

        # Match: const struct ObjectEventGraphicsInfo gObjectEventGraphicsInfo_BrendanNormal = {
        #            ... .images = sPicTable_BrendanNormal, ... .paletteTag = OBJ_EVENT_PAL_TAG_BRENDAN, ...
        #        };
        struct_pattern = r'const\s+struct\s+ObjectEventGraphicsInfo\s+(gObjectEventGraphicsInfo_\w+)\s*=\s*\{([^}]+)\}'
        for match in re.finditer(struct_pattern, content, re.DOTALL):
            info_name = match.group(1)
            struct_content = match.group(2)

            # Extract .images field
            images_match = re.search(r'\.images\s*=\s*(\w+)', struct_content)
            # Extract .paletteTag field
            palette_tag_match = re.search(r'\.paletteTag\s*=\s*(OBJ_EVENT_PAL_TAG_\w+)', struct_content)

            if images_match:
                pic_table = images_match.group(1)
                pal_tag = palette_tag_match.group(1) if palette_tag_match else None

                # Resolve pic table to gObjectEventPic_* symbols, then to file paths
                sprite_paths = []
                if pic_table in pic_table_to_pics:
                    for pic_symbol in pic_table_to_pics[pic_table]:
                        if pic_symbol in pic_to_paths:
                            sprite_paths.extend(pic_to_paths[pic_symbol])

                # Resolve palette tag to gObjectEventPal_* symbol, then to file path
                palette_path = None
                if pal_tag and pal_tag in pal_tag_to_pal:
                    pal_symbol = pal_tag_to_pal[pal_tag]
                    palette_path = pal_to_paths.get(pal_symbol)

                info_to_graphics[info_name] = {
                    "sprites": sprite_paths,
                    "palette": palette_path,
                }

    # Step 5: Parse object_event_graphics_info_pointers.h to map OBJ_EVENT_GFX_* to gObjectEventGraphicsInfo_*
    object_event_graphics_info_pointers_h = expansion_path / "src/data/object_events/object_event_graphics_info_pointers.h"
    object_event_graphics = {}

    with open(object_event_graphics_info_pointers_h, "r", encoding="utf-8") as f:
        content = f.read()

        # Match: [OBJ_EVENT_GFX_BRENDAN_NORMAL] = &gObjectEventGraphicsInfo_BrendanNormal,
        pointer_pattern = r'\[(OBJ_EVENT_GFX_\w+)\]\s*=\s*&(gObjectEventGraphicsInfo_\w+)'
        for match in re.finditer(pointer_pattern, content):
            gfx_constant = match.group(1)
            info_name = match.group(2)

            if info_name in info_to_graphics:
                object_event_graphics[gfx_constant] = info_to_graphics[info_name]

    return object_event_graphics
