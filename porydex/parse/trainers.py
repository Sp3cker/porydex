import pathlib
from typing import Dict, List, Any

from pycparser.c_ast import ExprList, NamedInitializer, ArrayDecl, InitList
from yaspin import yaspin

from porydex.parse import load_truncated, extract_int, extract_u8_str

def parse_trainers(fname: pathlib.Path) -> Dict[str, Dict[str, Any]]:
    """Parse trainer party data from trainer_parties.h file."""

    with yaspin(text=f"Loading trainer parties data: {fname}", color="cyan") as spinner:
        from porydex.parse import load_table_set

        trainer_decls = load_table_set(
            fname,
            extra_includes=[
                r"-include",
                r"constants/species.h",
                r"-include",
                r"constants/moves.h",
                r"-include",
                r"constants/abilities.h",
                r"-include",
                r"constants/items.h",
                r"-include",
                r"constants/trainers.h",
            ],
        )
        spinner.ok("✅")

    # Parse all trainer parties
    all_parties = {}


