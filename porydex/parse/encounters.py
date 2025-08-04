import dataclasses
import json
import pathlib
import re

from pycparser.c_ast import ArrayDecl, Constant, Decl, ExprList, InitList, NamedInitializer, Struct, TypeDecl
from yaspin import yaspin

from porydex.common import name_key
from porydex.parse import extract_id, extract_int, load_data

def parse_species_constants(species_header_path: pathlib.Path) -> dict:
    """Parse species constants directly from the header file."""
    constants = {}
    aliases = {}
    
    try:
        with open(species_header_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # First pass: Find all SPECIES_* constant definitions with numeric values
        # Pattern: #define SPECIES_SOMETHING 123
        pattern = r'#define\s+(SPECIES_\w+)\s+(\d+)'
        matches = re.findall(pattern, content)
        
        for constant_name, value_str in matches:
            try:
                value = int(value_str)
                constants[constant_name] = value
            except ValueError:
                continue
        
        # Second pass: Find aliases (constants defined as other constants)
        # Pattern: #define SPECIES_SOMETHING SPECIES_SOMETHING_ELSE
        alias_pattern = r'#define\s+(SPECIES_\w+)\s+(SPECIES_\w+)'
        alias_matches = re.findall(alias_pattern, content)
        
        # Resolve aliases, handling multi-level aliases
        aliases = dict(alias_matches)
        
        # Keep resolving until all aliases are resolved (up to 10 levels to prevent infinite loops)
        for _ in range(10):
            resolved_any = False
            for alias_name, target_name in list(aliases.items()):
                if target_name in constants:
                    # Direct resolution
                    constants[alias_name] = constants[target_name]
                    del aliases[alias_name]
                    resolved_any = True
                elif target_name in aliases:
                    # Chain resolution: update the target to point deeper
                    aliases[alias_name] = aliases[target_name]
                    resolved_any = True
            
            if not resolved_any:
                break
    
    except FileNotFoundError:
        print(f"Warning: Could not find species header file: {species_header_path}")
    
    return constants

def camel_to_underscore(s: str) -> str:
    """Convert camelCase to underscore format."""
    import re
    # Add underscore before capital letters, but not at the start
    s = re.sub(r'(?<!^)(?=[A-Z])', '_', s)
    return s.upper()

def snake_to_pascal(s: str) -> str:
    return ''.join(x.capitalize() for x in s.lower().split('_'))

def snake_to_camel(s: str) -> str:
    pascal = snake_to_pascal(s)

    if not pascal:
        return ''
    return pascal[0].lower() + pascal[1:]

def split_words(s: str) -> str:
    return ' '.join(re.findall(r'[A-Z0-9]+[^A-Z0-9]*', s)).replace('_', ' -')

@dataclasses.dataclass
class Encounter:
    species: int  # Species ID (index)
    min_level: int
    max_level: int

    def to_json(self) -> dict:
        return {
            "min_level": self.min_level,
            "max_level": self.max_level,
            "species": self.species
        }

@dataclasses.dataclass
class EncounterInfo:
    base_rate: int
    enc_def_id: str

@dataclasses.dataclass
class EncounterRate:
    encounter_rate: int
    mons: list[Encounter]

    def to_json(self) -> dict:
        return {
            "encounter_rate": self.encounter_rate,
            "mons": [mon.to_json() for mon in self.mons]
        }

@dataclasses.dataclass
class MapEncounters:
    id: int | None
    name: str | None
    land: EncounterRate | None
    surf: EncounterRate | None
    rock: EncounterRate | None
    fish: EncounterRate | None

MAP_NAME_PATTERN = re.compile(r'g([A-Za-z0-9_]+?)_[A-Z]')

def parse_encounter_init(init: NamedInitializer,
                         info_sections: dict[str, EncounterInfo],
                         encounter_defs: dict[str, list[Encounter]]) -> tuple[str, EncounterRate] | None:
    if isinstance(init.expr, Constant):
        assert extract_int(init.expr) == 0, 'non-null constant for encounter info'
        return None

    id = extract_id(init.expr.expr)
    map_name_match = MAP_NAME_PATTERN.match(id)
    assert map_name_match, f'failed to match info ID: {id}'
    map_name = map_name_match.group(1)

    id_info = info_sections[id]
    id_encs = encounter_defs[id_info.enc_def_id]

    return map_name, EncounterRate(id_info.base_rate, id_encs)

def parse_encounter_header(header: InitList,
                           info_sections: dict[str, EncounterInfo],
                           encounter_defs: dict[str, list[Encounter]]) -> MapEncounters:
    field_inits = header.exprs
    encs = MapEncounters(None, None, None, None, None, None)
    for init in field_inits:
        result = None
        match init.name[0].name:
            case 'landMonsInfo':
                result = parse_encounter_init(init, info_sections, encounter_defs)
                if result:
                    encs.name, encs.land = result
            case 'waterMonsInfo':
                result = parse_encounter_init(init, info_sections, encounter_defs)
                if result:
                    encs.name, encs.surf = result
            case 'rockSmashMonsInfo':
                result = parse_encounter_init(init, info_sections, encounter_defs)
                if result:
                    encs.name, encs.rock = result
            case 'fishingMonsInfo':
                result = parse_encounter_init(init, info_sections, encounter_defs)
                if result:
                    encs.name, encs.fish = result

    return encs

def parse_encounter_def(entry: InitList, species_names: list[str]) -> Encounter:
    try:
        return Encounter(
            species=extract_int(entry.exprs[2]),  # Use species ID directly instead of name
            min_level=extract_int(entry.exprs[0]),
            max_level=extract_int(entry.exprs[1]),
        )
    except Exception as e:
        id = extract_int(entry.exprs[2])
        print(f'{id=}')
        print(f'{len(species_names)=}')
        raise e

def parse_encounters_simple(wild_encounters_json: dict, species_constants: dict) -> dict:
    """
    Parse encounters by using wild_encounters.json as source of truth,
    just converting species names to IDs.
    """
    # Use the species constants directly
    species_name_to_id = species_constants
    
    # Start with the structure from wild_encounters.json
    result = {
        "wild_encounter_groups": []
    }
    
    for group in wild_encounters_json.get("wild_encounter_groups", []):
        new_group = {
            "label": group.get("label", ""),
            "for_maps": group.get("for_maps", True),
            "fields": group.get("fields", []),
            "encounters": []
        }
        
        for encounter in group.get("encounters", []):
            new_encounter = {
                "map": encounter.get("map", ""),
                "base_label": encounter.get("base_label", "")
            }
            
            # Convert each encounter type
            for field_name in ["land_mons", "water_mons", "rock_smash_mons", "fishing_mons"]:
                if field_name in encounter:
                    # Map field names to output format
                    output_name = {
                        "land_mons": "land",
                        "water_mons": "water", 
                        "rock_smash_mons": "rock",
                        "fishing_mons": "fish"
                    }.get(field_name, field_name)
                    
                    field_data = encounter[field_name]
                    new_field = {
                        "encounter_rate": field_data.get("encounter_rate", 0),
                        "mons": []
                    }
                    
                    # Convert species names to IDs
                    for mon in field_data.get("mons", []):
                        species_name = mon.get("species", "")
                        species_id = species_name_to_id.get(species_name, 0)
                        
                        new_mon = {
                            "min_level": mon.get("min_level", 1),
                            "max_level": mon.get("max_level", 1),
                            "species": species_id
                        }
                        new_field["mons"].append(new_mon)
                    
                    new_encounter[output_name] = new_field
            
            new_group["encounters"].append(new_encounter)
        
        result["wild_encounter_groups"].append(new_group)
    
    return result

def parse_encounters_data(exts, jd: dict, species_names: list[str]) -> dict:
    headers = []
    info_sections = {}
    encounter_defs = {}
    for _, entry in enumerate(exts):
        if not isinstance(entry, Decl):
            continue

        if (isinstance(entry.type, TypeDecl)
                and isinstance(entry.type.type, Struct)
                and entry.type.type.name == 'WildPokemonInfo'):
            info_sections[entry.name] = EncounterInfo(
                base_rate=extract_int(entry.init.exprs[0]),
                enc_def_id=extract_id(entry.init.exprs[1]),
            )

        if (isinstance(entry.type, ArrayDecl)
                and isinstance(entry.type.type, TypeDecl)
                and isinstance(entry.type.type.type, Struct)):
            if entry.type.type.type.name == 'WildPokemon':
                encounter_defs[entry.name] = [
                    parse_encounter_def(enc_def, species_names)
                    for enc_def in entry.init.exprs
                ]
            if entry.type.type.type.name == 'WildPokemonHeader':
                headers = entry.init.exprs
                break

    # Start with the exact structure from wild_encounters.json
    wild_encounters = {
        "wild_encounter_groups": [
            {
                "label": "gWildMonHeaders",
                "for_maps": True,
                "fields": jd['wild_encounter_groups'][0]['fields'],  # Copy the global field definitions
                "encounters": []
            }
        ]
    }
    
    # Create a mapping from base_label to map constant from the JSON data
    map_constants = {}
    base_labels = {}
    global_group = jd['wild_encounter_groups'][0]
    for encounter in global_group.get('encounters', []):
        if 'base_label' in encounter and 'map' in encounter:
            map_constants[encounter['base_label']] = encounter['map']
            base_labels[encounter['base_label']] = encounter['base_label']

    # Process each parsed encounter header
    for header in headers:
        data = parse_encounter_header(header, info_sections, encounter_defs)
        if not data.name:
            continue

        # Convert the parsed name to the base_label format
        base_label = f"g{data.name.capitalize()}"
        
        # Get map constant and base_label (use defaults if not found)
        if base_label in map_constants:
            map_constant = map_constants[base_label]
            base_label_value = base_labels[base_label]
        else:
            # Convert camelCase to underscore format and add MAP_ prefix
            map_constant = f"MAP_{camel_to_underscore(data.name)}"
            base_label_value = base_label

        # Build encounter entry in wild_encounters.json format
        encounter_entry = {
            "map": map_constant,
            "base_label": base_label_value
        }
        
        # Add encounter types if they exist
        if data.land:
            encounter_entry["land"] = data.land.to_json()
        if data.surf:
            encounter_entry["water"] = data.surf.to_json()
        if data.rock:
            encounter_entry["rock"] = data.rock.to_json()
        if data.fish:
            encounter_entry["fish"] = data.fish.to_json()

        wild_encounters["wild_encounter_groups"][0]["encounters"].append(encounter_entry)

    return wild_encounters

def load_json(fname: pathlib.Path) -> dict:
    with open(fname, 'r', encoding='utf-8') as j:
        return json.load(j)

def parse_encounters(fname: pathlib.Path,
                     species_names: list[str]) -> dict:
    # Load the wild_encounters.json file directly
    json_path = fname.with_suffix('.json')
    with yaspin(text=f'Loading encounter tables: {json_path}', color='cyan') as spinner:
        wild_encounters_json = load_json(json_path)
        spinner.ok("✅")

    # Parse species constants from the header file
    species_header_path = fname.parent.parent.parent / "include" / "constants" / "species.h"
    species_constants = parse_species_constants(species_header_path)
    
    return parse_encounters_simple(wild_encounters_json, species_constants)

