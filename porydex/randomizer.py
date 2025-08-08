"""Utilities for working with the randomization metadata that is stored in the
pokeemerald-expansion source tree.

The vanilla game engine (and by extension pokeemerald-expansion) encodes, for
each species, a bit-mask named `randomizerMode` that dictates under which
randomisation modes that Pokémon is eligible to be selected.  The possible
modes are defined as macros in `include/config/randomizer.h` of the expansion
project:

    #define RANDOMIZER_MODE_WILD_ENCOUNTERS   0x01
    #define RANDOMIZER_MODE_TRAINER_POKEMON   0x02
    #define RANDOMIZER_MODE_GIFT_POKEMON      0x04
    ...

This helper module exposes functions to:

1. Parse the randomizer modes from the header file
2. Extract species randomization data with proper structure
3. Export randomization data to JSON format

The functions here *do not* try to guess a default path to the header – they
leverage ``porydex.config`` which already knows where the user's local checkout
of pokeemerald-expansion is located.
"""

from __future__ import annotations

from typing import Dict, List
import pathlib
import re
import json

from porydex import config
from pycparser.c_ast import NamedInitializer
from porydex.parse import load_truncated, extract_int

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_ENUM_PATTERN = re.compile(
    r"([A-Za-z0-9_]+),"
)

# Randomizer constants
MON_RANDOMIZER_INVALID = 3


def _base_stat_total_from_init(struct_init: NamedInitializer) -> int:
    total = 0
    fields = struct_init.expr.exprs
    for field_init in fields:
        fname = field_init.name[0].name
        if fname == "baseHP":
            total += extract_int(field_init.expr)
        elif fname == "baseAttack":
            total += extract_int(field_init.expr)
        elif fname == "baseDefense":
            total += extract_int(field_init.expr)
        elif fname == "baseSpAttack":
            total += extract_int(field_init.expr)
        elif fname == "baseSpDefense":
            total += extract_int(field_init.expr)
        elif fname == "baseSpeed":
            total += extract_int(field_init.expr)
    return total


def _is_randomizer_legendary(struct_init: NamedInitializer) -> bool:
    is_leg = False
    is_myth = False
    is_ub = False
    for field_init in struct_init.expr.exprs:
        fname = field_init.name[0].name
        if fname == "isLegendary":
            is_leg = extract_int(field_init.expr) == 1
        elif fname == "isMythical":
            is_myth = extract_int(field_init.expr) == 1
        elif fname == "isUltraBeast":
            is_ub = extract_int(field_init.expr) == 1
    return is_leg or is_myth or is_ub


def _extract_randomizer_mode(struct_init: NamedInitializer) -> int:
    """Return the randomizerMode value if present, else 0."""
    for field_init in struct_init.expr.exprs:
        fname = field_init.name[0].name
        if fname == "randomizerMode" or fname == "randomizerModes":
            return extract_int(field_init.expr)
    return 0


def _get_species_egg_id(expansion_root: pathlib.Path) -> int | None:
    """Parse include/constants/species.h to get SPECIES_EGG numeric ID."""
    header = expansion_root / "include" / "constants" / "species.h"
    try:
        text = header.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None
    # Match either '#define SPECIES_EGG 1234' or '#define SPECIES_EGG (1234)'
    m = re.search(r"#define\s+SPECIES_EGG\s*\(?\s*(\d+)\s*\)?", text)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            return None
    return None


def _collect_all_species_minimal(species_header: pathlib.Path, expansion_root: pathlib.Path) -> List[Dict]:
    # Minimal pre-processing; we only need constants resolution for numeric fields
    species_data = load_truncated(
        species_header,
        extra_includes=[
            r"-include",
            r"constants/moves.h",
        ],
    )

    egg_id = _get_species_egg_id(expansion_root)

    result: List[Dict] = []
    for struct_init in species_data:
        if not isinstance(struct_init, NamedInitializer):
            continue
        try:
            species_id = extract_int(struct_init.name[0])
            if egg_id is not None and species_id == egg_id:
                continue  # Exclude SPECIES_EGG explicitly
            base_total = _base_stat_total_from_init(struct_init)
            is_leg = _is_randomizer_legendary(struct_init)
            mode_val = _extract_randomizer_mode(struct_init)
            result.append({
                "ID": species_id,
                "baseStat": base_total,
                "isLegendary": is_leg,
                "mode": mode_val,
            })
        except Exception:
            # Skip malformed entries (if any)
            continue

    # Sort by ID, as requested
    result.sort(key=lambda s: s["ID"])
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_randomizer_modes(header_path: pathlib.Path | None = None) -> Dict[str, int]:
    """Parse *randomizer.h* and return a mapping of mode-name -> integer value."""

    if header_path is None:
        config.load()  # Ensure config is loaded
        header_path = (
            config.expansion / "include" / "config" / "randomizer.h"
        )

    modes: Dict[str, int] = {}

    try:
        with header_path.open("r", encoding="utf-8") as fp:
            content = fp.read()
            feature_match = re.search(r'enum RandomizerFeature\s*\{([^}]+)\}', content, re.DOTALL)
            if feature_match:
                enum_content = feature_match.group(1)
                enum_index = 0
                for line in enum_content.split('\n'):
                    line = line.strip()
                    if line and not line.startswith('//') and line != '{':
                        match = _ENUM_PATTERN.match(line)
                        if match:
                            name = match.group(1)
                            if name != 'MAX_MON_MODE':  # Skip the dummy end marker
                                modes[name] = enum_index
                                enum_index += 1
    except FileNotFoundError:
        pass

    return modes


def extract_randomizer_data():
    """Extract randomization data and export to randomize.json

    Output: a plain JSON array sorted by ID, each element:
    { "ID": number, "baseStat": number, "isLegendary": boolean, "mode": number }
    """
    config.load()
    config.output.mkdir(parents=True, exist_ok=True)

    expansion_data = config.expansion / "src" / "data"
    species_header = expansion_data / "pokemon" / "species_info.h"

    species_list = _collect_all_species_minimal(species_header, config.expansion)

    # Write array to randomize.json
    output_file = config.output / "randomize.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(species_list, f, indent=2, ensure_ascii=False)

    print(f"Randomization data exported to {output_file}")
    print(f"Processed {len(species_list)} species entries")
