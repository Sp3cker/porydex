"""Parser for National Dex enum constants.

Now uses generic_table.py utilities instead of custom enum parsing.
"""

import pathlib

from porydex.parse.generic_table import parse_enum_from_header


def parse_national_dex_enum(fname: pathlib.Path) -> dict[str, int]:
    """
    Parse National Dex enum from header file.

    Args:
        fname: Path to header file containing enum NationalPokedexNum

    Returns:
        Dictionary mapping NATIONAL_DEX_* constants to integer values
    """
    # Use generic enum parser - no need for custom parsing logic
    return parse_enum_from_header(fname, enum_name=None)  # Parses all enums in file

