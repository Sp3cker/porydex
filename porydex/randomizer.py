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

This helper module exposes two things:

1. ``parse_randomizer_modes`` – Parse the header and return a mapping of macro
   names to their integer values.
2. ``classify_species_by_mode`` – Given the Pokémon data already collected by
   the   rest of porydex and a *specific* mode value, return a dictionary that
   maps every Pokémon name to a boolean that is ``True`` when that Pokémon is
   available for that mode.

The functions here *do not* try to guess a default path to the header – they
leverage ``porydex.config`` which already knows where the user’s local checkout
of pokeemerald-expansion is located.
"""

from __future__ import annotations

from typing import Dict
import pathlib
import re

from porydex import config

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_ENUM_PATTERN = re.compile(
    r"([A-Za-z0-9_]+),"
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_randomizer_modes(header_path: pathlib.Path | None = None) -> Dict[str, int]:
    """Parse *randomizer.h* and return a mapping of mode-name -> integer value.

    Parameters
    ----------
    header_path
        Optional path to a *randomizer.h* file.  If *None* the helper will use
        ``porydex.config.expansion / 'include' / 'config' / 'randomizer.h'``.
    """

    if header_path is None:
        config.load()  # Ensure config is loaded
        header_path = (
            config.expansion / "include" / "config" / "randomizer.h"
        )

    modes: Dict[str, int] = {}

    try:
        with header_path.open("r", encoding="utf-8") as fp:
            content = fp.read()
            
            # Look for the RandomizerFeature enum
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
        # It is entirely possible that the user has not yet cloned the
        # expansion repo in the configured location.  Failing silently (with an
        # empty dict) is less intrusive than exploding – the caller can decide
        # what to do when the result is empty.
        pass

    return modes


def classify_species_by_mode(
    species_data: Dict[str, dict], mode_value: int
) -> Dict[str, bool]:
    """Return a *species-name -> is_randomizable* mapping for the given mode.

    The function expects that every Pokémon dictionary (i.e. the values of
    *species_data*) follows the structure produced by
    ``porydex.parse.species.parse_species`` – in particular it optionally
    contains the key ``'randomizerMode'`` which stores the bit-mask copied from
    the original C data.
    """

    result: Dict[str, bool] = {}
    
    for species_name, species_info in species_data.items():
        randomizer_mode = species_info.get("randomizerMode", 0)
        is_randomizable = (randomizer_mode & mode_value) != 0
        result[species_name] = is_randomizable

    return result
