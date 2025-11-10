import pathlib
import re

from pycparser.c_ast import ID, ExprList, NamedInitializer
from yaspin import yaspin

from porydex.parse import load_truncated, extract_int, extract_u8_str, extract_compound_str

def parse_item_graphics_constants(graphics_file: pathlib.Path) -> dict:
    """
    Parse the graphics/items.h file to extract symbol-to-filepath mappings.

    Args:
        graphics_file: Path to src/data/graphics/items.h

    Returns:
        Dictionary mapping symbol names to file paths
        Example: {'gItemIcon_PokeBall': 'graphics/items/icons/poke_ball.4bpp.smol'}
    """
    graphics_map = {}

    try:
        with open(graphics_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Pattern to match: const u32 gItemIcon_PokeBall[] = INCBIN_U32("graphics/items/icons/poke_ball.4bpp.smol");
        # or: const u16 gItemIconPalette_PokeBall[] = INCBIN_U16("graphics/items/icons/poke_ball.gbapal");
        pattern = r'const\s+(?:u32|u16)\s+(\w+)\[\]\s+=\s+INCBIN_(?:U32|U16)\("([^"]+)"\);'

        matches = re.findall(pattern, content, re.MULTILINE)

        for symbol_name, file_path in matches:
            graphics_map[symbol_name] = file_path

        print(f"Parsed {len(graphics_map)} graphics symbol mappings from {graphics_file.name}")

    except Exception as e:
        print(f"Warning: Could not parse item graphics constants: {e}")

    return graphics_map

def parse_item_description_constants(fname: pathlib.Path) -> dict:
    """
    Parse description constants from the items.h file.
    
    Args:
        fname: Path to the items.h file
        
    Returns:
        Dictionary mapping description constant names to their string values
    """
    description_constants = {}
    
    try:
        with open(fname, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Pattern to match description constants like:
        # static const u8 sQuestionMarksDesc[] = _("?????");
        pattern = r'static const u8 (\w+)\[\] = _\(\s*"([^"]*)"\s*\);'
        
        matches = re.findall(pattern, content, re.MULTILINE | re.DOTALL)
        
        for match in matches:
            constant_name = match[0]
            description = match[1].strip()
            # Replace any escaped newlines with spaces
            description = description.replace("\\n", " ")
            description_constants[constant_name] = description
        
        # Also look for COMPOUND_STRING descriptions
        compound_pattern = r'static const u8 (\w+)\[\] = _\(\s*COMPOUND_STRING\(\s*"([^"]*)"\s*\);'
        compound_matches = re.findall(compound_pattern, content, re.MULTILINE | re.DOTALL)
        
        for match in compound_matches:
            constant_name = match[0]
            description = match[1].strip()
            # Replace any escaped newlines with spaces
            description = description.replace("\\n", " ")
            description_constants[constant_name] = description
            
    except Exception as e:
        print(f"Warning: Could not parse item description constants: {e}")
    
    return description_constants

def parse_item_constants_from_header(header_path: pathlib.Path) -> dict:
    """Parse item constants directly from the header file to get the correct constant names."""
    constants = {}
    
    try:
        with open(header_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find all ITEM_* constant definitions, but exclude ITEM_USE_* and ITEM_EFFECT_* constants
        # Pattern: #define ITEM_SOMETHING 123 (but not ITEM_USE_* or ITEM_EFFECT_*)
        pattern = r'#define\s+(ITEM_(?!USE_|EFFECT_)\w+)\s+(\d+)'
        matches = re.findall(pattern, content)
        
        for constant_name, value_str in matches:
            try:
                value = int(value_str)
                constants[value] = constant_name
            except ValueError:
                continue
                
        print(f"Parsed {len(constants)} item constants from header file")
        
    except Exception as e:
        print(f"Warning: Could not parse item constants from header: {e}")
    
    return constants

def get_item_name(struct_init: NamedInitializer) -> str:
    for field_init in struct_init.expr.exprs:
        if field_init.name[0].name == 'name':
            return extract_u8_str(field_init.expr)

    print(struct_init.show())
    raise ValueError('no name for item structure')

def get_item_price(struct_init: NamedInitializer) -> int:
    for field_init in struct_init.expr.exprs:
        if field_init.name[0].name == 'price':
            field_expr = field_init.expr
            
            # Handle conditional expressions like (I_PRICE >= GEN_7) ? 800 : 1200
            if hasattr(field_expr, 'cond') and hasattr(field_expr, 'iftrue') and hasattr(field_expr, 'iffalse'):
                # For conditional expressions, take the first value (iftrue)
                try:
                    return extract_int(field_expr.iftrue)
                except:
                    # Fallback to the second value if first fails
                    try:
                        return extract_int(field_expr.iffalse)
                    except:
                        return 0
            else:
                # Regular integer expression
                try:
                    return extract_int(field_expr)
                except:
                    return 0
    
    # Default price if not found
    return 0

def get_item_description(struct_init: NamedInitializer, description_constants: dict = None) -> str:
    for field_init in struct_init.expr.exprs:
        if field_init.name[0].name == 'description':
            field_expr = field_init.expr

            # Handle different types of description fields
            if hasattr(field_expr, "exprs"):
                # Compound string (multiple string literals concatenated)
                try:
                    return extract_compound_str(field_expr)
                except:
                    return str(field_expr)
            elif hasattr(field_expr, "value"):
                # String constant
                return field_expr.value.strip('"')
            elif hasattr(field_expr, "name"):
                # Identifier (e.g., sQuestionMarksDesc)
                constant_name = field_expr.name
                if description_constants and constant_name in description_constants:
                    # Resolve the constant to its actual string value
                    return description_constants[constant_name]
                else:
                    # Fallback to the constant name if we can't resolve it
                    return constant_name
            else:
                # Fallback - try to extract as compound string
                try:
                    return extract_compound_str(field_expr)
                except:
                    return str(field_expr)

    # Default description if not found
    return ""

def get_item_icon_pic(struct_init: NamedInitializer) -> str:
    """Extract iconPic symbol name from item struct."""
    for field_init in struct_init.expr.exprs:
        if field_init.name[0].name == 'iconPic':
            field_expr = field_init.expr
            if hasattr(field_expr, "name"):
                # It's an identifier like gItemIcon_PokeBall
                return field_expr.name
    return ""

def get_item_icon_palette(struct_init: NamedInitializer) -> str:
    """Extract iconPalette symbol name from item struct."""
    for field_init in struct_init.expr.exprs:
        if field_init.name[0].name == 'iconPalette':
            field_expr = field_init.expr
            if hasattr(field_expr, "name"):
                # It's an identifier like gItemIconPalette_PokeBall
                return field_expr.name
    return ""
def validate_item_name(item_name: str, item_id: int) -> list[str]:
    """Validate item name and return any warnings."""
    warnings = []
    
    # Check for potentially problematic patterns
    if item_name == "????????":
        return warnings  # Skip validation for placeholder items
    
    # Check for items that might be macro overwrites
    problematic_patterns = [
        ("ENERGYPOWDER", "Should be ENERGY_POWDER"),
        ("PARLYZ_HEAL", "Should be PARALYZE_HEAL"),
        ("ELIXER", "Should be ELIXIR"),
        ("MAX_ELIXER", "Should be MAX_ELIXIR"),
        ("RAGECANDYBAR", "Should be RAGE_CANDY_BAR"),
        ("TINYMUSHROOM", "Should be TINY_MUSHROOM"),
        ("BALMMUSHROOM", "Should be BALM_MUSHROOM"),
        ("THUNDERSTONE", "Should be THUNDER_STONE"),
        ("SILVERPOWDER", "Should be SILVER_POWDER"),
        ("BLACKGLASSES", "Should be BLACK_GLASSES"),
        ("BLACKBELT", "Should be BLACK_BELT"),
        ("TWISTEDSPOON", "Should be TWISTED_SPOON"),
        ("DEEPSEASCALE", "Should be DEEP_SEA_SCALE"),
        ("DEEPSEATOOTH", "Should be DEEP_SEA_TOOTH"),
        ("NEVERMELTICE", "Should be NEVER_MELT_ICE"),
        ("BRIGHTPOWDER", "Should be BRIGHT_POWDER"),
        ("X_DEFEND", "Should be X_DEFENSE"),
        ("X_SPECIAL", "Should be X_SP_ATK"),
        ("UP_GRADE", "Should be UPGRADE"),
        ("ITEMFINDER", "Should be DOWSING_MACHINE"),
        ("DOWSING_MCHN", "Should be DOWSING_MACHINE"),
        ("POKEMON_BOX", "Should be POKEMON_BOX_LINK"),
        ("DEVON_GOODS", "Should be DEVON_PARTS"),
        ("OAKS_PARCEL", "Should be PARCEL"),
        ("EXP_ALL", "Should be EXP_SHARE"),
        ("STICK", "Should be LEEK"),
    ]
    
    for pattern, suggestion in problematic_patterns:
        if pattern in item_name.upper():
            warnings.append(f"Item ID {item_id} '{item_name}' may need attention: {suggestion}")
    
    # Check for items with unusual characters or formatting
    if re.search(r'[A-Z]{3,}', item_name):
        warnings.append(f"Item ID {item_id} '{item_name}' has unusual capitalization pattern")
    
    # Check for items that might be missing spaces
    if re.search(r'[a-z][A-Z]', item_name):
        warnings.append(f"Item ID {item_id} '{item_name}' may be missing spaces between words")
    
    return warnings

def analyze_item_conflict(item_id: int, old_name: str, new_name: str) -> str:
    """Analyze the type of item name conflict and provide context."""
    
    # Check for common macro overwrite patterns
    if "BERRY" in old_name and "BERRY" in new_name:
        return f"Berry item conflict - likely macro definition overwrite"
    elif "WING" in old_name and "FEATHER" in new_name:
        return f"Wing/Feather item conflict - likely Gen VIII name update"
    elif "POWDER" in old_name and "POWDER" in new_name:
        return f"Powder item conflict - likely spacing/formatting change"
    elif "STONE" in old_name and "STONE" in new_name:
        return f"Stone item conflict - likely formatting change"
    elif "APRICORN" in old_name and "APRICORN" in new_name:
        return f"Apricorn item conflict - likely color name change"
    elif "KEY" in old_name and "KEY" in new_name:
        return f"Key item conflict - likely room number change"
    elif "HEAL" in old_name and "HEAL" in new_name:
        return f"Heal item conflict - likely spelling correction"
    elif "ELIXER" in old_name and "ELIXIR" in new_name:
        return f"Elixir item conflict - likely spelling correction"
    elif "MUSHROOM" in old_name and "MUSHROOM" in new_name:
        return f"Mushroom item conflict - likely spacing change"
    elif "SEA" in old_name and "SEA" in new_name:
        return f"Sea item conflict - likely spacing change"
    elif "GLASSES" in old_name and "GLASSES" in new_name:
        return f"Glasses item conflict - likely spacing change"
    elif "BELT" in old_name and "BELT" in new_name:
        return f"Belt item conflict - likely spacing change"
    elif "SPOON" in old_name and "SPOON" in new_name:
        return f"Spoon item conflict - likely spacing change"
    elif "MACHINE" in old_name and "MACHINE" in new_name:
        return f"Machine item conflict - likely name update"
    elif "PARCEL" in old_name and "PARCEL" in new_name:
        return f"Parcel item conflict - likely name change"
    elif "GOODS" in old_name and "PARTS" in new_name:
        return f"Devon item conflict - likely name update"
    elif "BOX" in old_name and "BOX" in new_name:
        return f"Box item conflict - likely name update"
    elif "FINDER" in old_name and "MACHINE" in new_name:
        return f"Finder/Machine item conflict - likely name update"
    elif "ALL" in old_name and "SHARE" in new_name:
        return f"Exp item conflict - likely name update"
    elif "STICK" in old_name and "LEEK" in new_name:
        return f"Stick/Leek item conflict - likely name update"
    elif "UP_GRADE" in old_name and "UPGRADE" in new_name:
        return f"Upgrade item conflict - likely formatting change"
    elif "NEVERMELTICE" in old_name and "NEVER_MELT_ICE" in new_name:
        return f"Nevermeltice item conflict - likely spacing change"
    elif "BRIGHTPOWDER" in old_name and "BRIGHT_POWDER" in new_name:
        return f"Bright powder item conflict - likely spacing change"
    elif "RAGECANDYBAR" in old_name and "RAGE_CANDY_BAR" in new_name:
        return f"Rage candy bar item conflict - likely spacing change"
    elif "TINYMUSHROOM" in old_name and "TINY_MUSHROOM" in new_name:
        return f"Tiny mushroom item conflict - likely spacing change"
    elif "BALMMUSHROOM" in old_name and "BALM_MUSHROOM" in new_name:
        return f"Balm mushroom item conflict - likely spacing change"
    elif "THUNDERSTONE" in old_name and "THUNDER_STONE" in new_name:
        return f"Thunder stone item conflict - likely spacing change"
    elif "SILVERPOWDER" in old_name and "SILVER_POWDER" in new_name:
        return f"Silver powder item conflict - likely spacing change"
    elif "BLACKGLASSES" in old_name and "BLACK_GLASSES" in new_name:
        return f"Black glasses item conflict - likely spacing change"
    elif "BLACKBELT" in old_name and "BLACK_BELT" in new_name:
        return f"Black belt item conflict - likely spacing change"
    elif "TWISTEDSPOON" in old_name and "TWISTED_SPOON" in new_name:
        return f"Twisted spoon item conflict - likely spacing change"
    elif "DEEPSEASCALE" in old_name and "DEEP_SEA_SCALE" in new_name:
        return f"Deep sea scale item conflict - likely spacing change"
    elif "DEEPSEATOOTH" in old_name and "DEEP_SEA_TOOTH" in new_name:
        return f"Deep sea tooth item conflict - likely spacing change"
    elif "PARLYZ_HEAL" in old_name and "PARALYZE_HEAL" in new_name:
        return f"Paralyze heal item conflict - likely spelling correction"
    elif "X_DEFEND" in old_name and "X_DEFENSE" in new_name:
        return f"X defend item conflict - likely name correction"
    elif "X_SPECIAL" in old_name and "X_SP_ATK" in new_name:
        return f"X special item conflict - likely name update"
    elif "PRETTY_WING" in old_name and "PRETTY_FEATHER" in new_name:
        return f"Pretty wing item conflict - likely name update"
    elif "ENERGYPOWDER" in old_name and "ENERGY_POWDER" in new_name:
        return f"Energy powder item conflict - likely spacing change"
    elif "ELIXER" in old_name and "ELIXIR" in new_name:
        return f"Elixir item conflict - likely spelling correction"
    elif "MAX_ELIXER" in old_name and "MAX_ELIXIR" in new_name:
        return f"Max elixir item conflict - likely spelling correction"
    else:
        return f"Unknown item name conflict pattern"

def all_item_names(items_data, description_constants: dict = None, graphics_map: dict = None) -> dict:
    d_items = {}
    duplicate_warnings = []
    conflict_analysis = {}
    validation_warnings = []
    
    print(f"Processing {len(items_data)} item declarations...")
    
    for i, item in enumerate(items_data):
        if isinstance(item.name[0], ID):
            continue

        item_id = extract_int(item.name[0])
        item_name = get_item_name(item)
        item_price = get_item_price(item)
        item_description = get_item_description(item, description_constants)
        item_icon_pic_symbol = get_item_icon_pic(item)
        item_icon_palette_symbol = get_item_icon_palette(item)

        # Resolve symbols to file paths using graphics_map
        if graphics_map:
            item_icon_pic = graphics_map.get(item_icon_pic_symbol, item_icon_pic_symbol)
            item_icon_palette = graphics_map.get(item_icon_palette_symbol, item_icon_palette_symbol)
        else:
            item_icon_pic = item_icon_pic_symbol
            item_icon_palette = item_icon_palette_symbol

        # Debug: Print first few items to see what we're getting
        if i < 10:
            print(f"  Item {i}: ID={item_id}, Name='{item_name}', Price={item_price}, IconPic='{item_icon_pic}', IconPalette='{item_icon_palette}'")

        # Validate item name
        item_warnings = validate_item_name(item_name, item_id)
        validation_warnings.extend(item_warnings)

        # Check for duplicate item IDs (caused by macro overwrites)
        if item_id in d_items:
            old_name = d_items[item_id]['name']
            if old_name != item_name:
                conflict_type = analyze_item_conflict(item_id, old_name, item_name)
                duplicate_warnings.append(f"Item ID {item_id}: '{old_name}' overwritten by '{item_name}'")
                conflict_analysis[item_id] = conflict_type
            # Keep the newer definition (usually the more descriptive one)
            d_items[item_id] = {
                'itemId': item_id,
                'id': '',  # Will be filled in by parse_items
                'name': item_name,
                'price': item_price,
                'description': item_description,
                'iconPic': item_icon_pic,
                'iconPalette': item_icon_palette
            }
        else:
            d_items[item_id] = {
                'itemId': item_id,
                'id': '',  # Will be filled in by parse_items
                'name': item_name,
                'price': item_price,
                'description': item_description,
                'iconPic': item_icon_pic,
                'iconPalette': item_icon_palette
            }
    
    print(f"Processed {len(d_items)} unique items")
    
    # Print warnings about overwritten items with analysis
    if duplicate_warnings:
        print("Warning: Detected item name overwrites (likely due to macro definitions):")
        for warning in duplicate_warnings:
            print(f"  {warning}")
        print(f"Total overwrites: {len(duplicate_warnings)}")
        
        # Print conflict analysis
        print("\nConflict analysis:")
        for item_id, conflict_type in conflict_analysis.items():
            print(f"  Item ID {item_id}: {conflict_type}")
    else:
        print("No item name conflicts detected")
    
    # Print validation warnings
    if validation_warnings:
        print("\nItem validation warnings:")
        for warning in validation_warnings[:20]:  # Limit to first 20 warnings
            print(f"  {warning}")
        if len(validation_warnings) > 20:
            print(f"  ... and {len(validation_warnings) - 20} more warnings")
    
    return d_items

def get_item_names_list(items_dict: dict) -> list[str]:
    """Convert items dict to list format for backward compatibility."""
    if not items_dict:
        return []
    
    capacity = max(items_dict.keys()) + 1
    l_items = [items_dict[0]['name']] * capacity  # Initialize with first item name
    
    for i, item_data in items_dict.items():
        l_items[i] = item_data['name']
    
    return l_items

def get_item_constants_dict(items_dict: dict) -> dict:
    """Extract constant names from items dict."""
    constants = {}
    for item_id, item_data in items_dict.items():
        if item_data['id']:
            constants[item_data['id']] = item_id
    return constants

def parse_items(fname: pathlib.Path) -> dict:
    items_data: ExprList
    with yaspin(text=f'Loading items data: {fname}', color='cyan') as spinner:
        items_data = load_truncated(fname, extra_includes=[
            r'-include', r'constants/items.h',
        ])
        spinner.ok("✅")

    # Parse constants directly from the header file
    header_path = fname.parent.parent.parent / "include" / "constants" / "items.h"
    header_constants = parse_item_constants_from_header(header_path)

    # Parse description constants from the items.h file
    description_constants = parse_item_description_constants(fname)

    # Parse graphics constants from the graphics/items.h file
    graphics_path = fname.parent / "graphics" / "items.h"
    graphics_map = parse_item_graphics_constants(graphics_path)

    # Parse the items data
    items_dict = all_item_names(items_data, description_constants, graphics_map)
    
    # Assign constants from the header file
    for item_id, item_data in items_dict.items():
        if item_id in header_constants:
            item_data['id'] = header_constants[item_id]
        else:
            # Generate a fallback constant name if not found in header
            item_name = item_data['name']
            if item_name and item_name != "????????":
                # Convert item name to constant format (e.g., "Poké Ball" -> "ITEM_POKE_BALL")
                constant_name = "ITEM_" + item_name.upper().replace(" ", "_").replace("-", "_").replace("'", "")
                # Remove any non-alphanumeric characters except underscores
                import re
                constant_name = re.sub(r"[^A-Z0-9_]", "", constant_name)
                item_data['id'] = constant_name
            else:
                item_data['id'] = f"ITEM_{item_id}"
    
    return items_dict

