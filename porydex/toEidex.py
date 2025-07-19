import json
import pathlib
import porydex.config
from porydex.move_descriptions import enrich_moves_with_descriptions
from porydex.parse.species_object import parse_all_generations_with_data

vanilla_data_dir = pathlib.Path("vanilla")
typeData = json.load(open(vanilla_data_dir / "typeData.json", "r", encoding="utf-8"))
type_name_to_id = {
    type_data["typeName"].lower(): type_data["typeID"]
    for type_data in typeData.values()
}

CATEGORY_LOOKUP = {
    "physical": 0,
    "special": 1,
    "status": 2,
    "": 3,  # for moves with no category
}


def eiDexSpecies(abilities, items, move_names, forms, form_changes, level_up_learnsets, teachable_learnsets, national_dex):
    """
    Export species data in the structured object format.
    This function parses all species data and exports it to species.json.
    
    Args:
        abilities: Pre-parsed list of ability names indexed by ID
        items: Pre-parsed list of item names indexed by ID
        move_names: Pre-parsed list of move names indexed by ID
        forms: Pre-parsed dictionary mapping form table names to form data
        form_changes: Pre-parsed dictionary mapping form change table names to form change data
        level_up_learnsets: Pre-parsed dictionary of level-up learnsets
        teachable_learnsets: Pre-parsed dictionary of teachable learnsets
        national_dex: Pre-parsed dictionary mapping species names to national dex numbers
    """
    try:
        print("Processing species data...")
        
        # Debug: Log form_changes data
        print(f"DEBUG: form_changes type: {type(form_changes)}")
        print(f"DEBUG: form_changes keys count: {len(form_changes) if form_changes else 0}")
        if form_changes:
            print("DEBUG: Sample form_changes keys:")
            sample_keys = list(form_changes.keys())[:5]  # Show first 5 keys
            for key in sample_keys:
                print(f"  - {key}: {form_changes[key]}")
            if len(form_changes) > 5:
                print(f"  ... and {len(form_changes) - 5} more keys")
        
        # Parse all species data using our new species object parser with pre-parsed data
        species_data = parse_all_generations_with_data(
            abilities, items, move_names, forms, form_changes, 
            level_up_learnsets, teachable_learnsets, national_dex
        )
        
        print(f"Successfully parsed {len(species_data)} species")
        
        # Write species data to output file
        output_path = porydex.config.output / "species.json"
        print(f"Writing {len(species_data)} species to {output_path}")
        
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w+", encoding="utf-8") as outf:
            json.dump(species_data, outf, indent=4, ensure_ascii=False)
        
        print(f"Successfully wrote species.json with {len(species_data)} entries")
        
        return species_data
        
    except Exception as e:
        print(f"Error in eiDexSpecies function: {e}")
        import traceback
        traceback.print_exc()
        return None


def eiDexSpeciesOnly(abilities, items, moves, forms, form_changes, level_up_learnsets, teachable_learnsets, national_dex):
    """
    Export only species data without moves.
    Convenience function for when you only want species data.
    
    Args:
        abilities: Pre-parsed list of ability names indexed by ID
        items: Pre-parsed list of item names indexed by ID
        moves: Pre-parsed list of move names indexed by ID
        forms: Pre-parsed dictionary mapping form table names to form data
        form_changes: Pre-parsed dictionary mapping form change table names to form change data
        level_up_learnsets: Pre-parsed dictionary of level-up learnsets
        teachable_learnsets: Pre-parsed dictionary of teachable learnsets
        national_dex: Pre-parsed dictionary mapping species names to national dex numbers
    
    Returns:
        dict: The species data dictionary, or None if an error occurred
    """
    return eiDexSpecies(abilities, items, moves, forms, form_changes, level_up_learnsets, teachable_learnsets, national_dex)


def eiDex(moves: dict, trainer_parties: dict, export_species: bool = True, 
          abilities=None, items=None, move_names=None, forms=None, form_changes=None, 
          level_up_learnsets=None, teachable_learnsets=None, national_dex=None):
    """
    Export moves and optionally species data to EiDex format.
    
    Args:
        moves: Dictionary of move data
        trainer_parties: Dictionary of trainer party data
        export_species: Whether to also export species data (default: True)
        abilities: Pre-parsed list of ability names (required if export_species=True)
        items: Pre-parsed list of item names (required if export_species=True)
        move_names: Pre-parsed list of move names (required if export_species=True)
        forms: Pre-parsed form data (required if export_species=True)
        level_up_learnsets: Pre-parsed learnset data (required if export_species=True)
        teachable_learnsets: Pre-parsed learnset data (required if export_species=True)
        national_dex: Pre-parsed national dex data (required if export_species=True)
    """
    try:
        # Debug: Log form_changes data at entry point
        print(f"DEBUG: eiDex entry - form_changes type: {type(form_changes)}")
        print(f"DEBUG: eiDex entry - form_changes is None: {form_changes is None}")
        if form_changes:
            print(f"DEBUG: eiDex entry - form_changes keys count: {len(form_changes)}")
            print("DEBUG: eiDex entry - Sample form_changes entries:")
            sample_items = list(form_changes.items())[:3]  # Show first 3 entries
            for key, value in sample_items:
                print(f"  {key}: {value}")
            if len(form_changes) > 3:
                print(f"  ... and {len(form_changes) - 3} more entries")
        
        # Export species data if requested
        if export_species:
            print("=== Exporting Species Data ===")
            if any(x is None for x in [abilities, items, move_names, forms, form_changes, level_up_learnsets, teachable_learnsets, national_dex]):
                print("Error: Missing required pre-parsed data for species export")
                print("Required: abilities, items, move_names, forms, form_changes, level_up_learnsets, teachable_learnsets, national_dex")
                return
            
            eiDexSpecies(abilities, items, move_names, forms, form_changes, level_up_learnsets, teachable_learnsets, national_dex)
            print("=== Species Export Complete ===\n")
        
        print("=== Exporting Moves Data ===")
        # Enrich moves with descriptions first
        moves = enrich_moves_with_descriptions(moves)

        print(f"Processing {len(moves)} moves...")

        transformed = []
        move_constants = []
        for idx, (move_id, m) in enumerate(moves.items(), start=1):
            try:
                # Debug type assignment
                move_type = m.get("type", "").lower()
                type_id = type_name_to_id.get(move_type)

                if type_id is None:
                    print(
                        f"Warning: No type mapping found for '{move_type}' in move '{m.get('name', move_id)}'"
                    )
                    type_id = 0  # Default to first type if not found

                # Use shortDesc if available, fallback to desc, then empty string
                description = m.get("description", m.get("shortDesc", ""))

                move_num = m.get("num", idx)
                
                # Generate constant name from move name
                move_name = m.get("name", "")
                if move_name:
                    # Convert name to constant format (e.g., "Karate Chop" -> "MOVE_KARATE_CHOP")
                    constant_name = "MOVE_" + move_name.upper().replace(" ", "_").replace("-", "_").replace("'", "")
                    # Remove any non-alphanumeric characters except underscores
                    import re
                    constant_name = re.sub(r'[^A-Z0-9_]', '', constant_name)
                else:
                    constant_name = f"MOVE_{move_num}"
                
                move_constant = m.get("constant", constant_name)

                transformed.append(
                    {
                        "id": move_num,
                        "name": m["name"],
                        "type": type_id,
                        "desc": description,
                        "power": int(m.get("basePower", 0) or 0),
                        "acc": int(m.get("accuracy", 0) or 0),
                        "cat": CATEGORY_LOOKUP.get(m.get("category", "").lower(), 3),
                        "properties": list(m.get("flags", {}).keys()),
                    }
                )

                # Add to move constants list
                move_constants.append(
                    {
                        "constName": move_constant,
                        "id": move_num,
                    }
                )
            except Exception as e:
                print(f"Error processing move {move_id}: {e}")
                print(f"Move data: {m}")
                continue

        output_path = porydex.config.output / "moves.json"
        print(f"Writing {len(transformed)} moves to {output_path}")

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w+", encoding="utf-8") as outf:
            json.dump(transformed, outf, indent=4, ensure_ascii=False)

        print(f"Successfully wrote moves.json with {len(transformed)} entries")

        # Write move constants file
        constants_path = porydex.config.output / "move_constants.json"
        print(f"Writing {len(move_constants)} move constants to {constants_path}")

        with open(constants_path, "w+", encoding="utf-8") as outf:
            json.dump(move_constants, outf, indent=4, ensure_ascii=False)

        print(f"Successfully wrote move_constants.json with {len(move_constants)} entries")
        print("=== Moves Export Complete ===")

    except Exception as e:
        print(f"Error in eiDex function: {e}")
        import traceback
        traceback.print_exc()


__all__ = ["eiDex", "eiDexSpecies", "eiDexSpeciesOnly"]
