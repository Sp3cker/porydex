"""
Parse trainer party data from trainers.party file using the trainerproc tool.
"""

import json
import pathlib
import subprocess
import tempfile
from typing import Dict, List, Optional, Any


def parse_trainers_party(expansion_path: pathlib.Path) -> List[Dict[str, Any]]:
    """
    Parse trainers.party file using the trainerproc tool with JSON output.

    Returns a list of trainer dictionaries with complete party information.
    Each trainer includes all properties and each Pokemon includes all stats.
    """
    trainers_party_file = expansion_path / "src/data/trainers.party"
    trainerproc_path = expansion_path / "tools/trainerproc/trainerproc"

    if not trainers_party_file.exists():
        raise FileNotFoundError(f"trainers.party not found at {trainers_party_file}")

    if not trainerproc_path.exists():
        raise FileNotFoundError(f"trainerproc tool not found at {trainerproc_path}")

    # Step 1: Preprocess the .party file with cpp
    # This removes comments and processes any C preprocessor directives
    cpp_result = subprocess.run(
        [
            "cpp",
            "-nostdinc",
            f"-I{expansion_path / 'include'}",
            "-undef",
            "-P",
            str(trainers_party_file)
        ],
        capture_output=True,
        text=True,
        check=True
    )

    preprocessed_content = cpp_result.stdout

    # Step 2: Run trainerproc with -j flag to get JSON output
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as output_file:
        output_path = output_file.name

    try:
        proc_result = subprocess.run(
            [str(trainerproc_path), "-j", "-o", output_path, "-"],
            input=preprocessed_content,
            capture_output=True,
            text=True,
            check=True
        )

        # Step 3: Load and return the JSON
        with open(output_path, 'r', encoding='utf-8') as f:
            trainers = json.load(f)

        return trainers

    finally:
        # Clean up temp file
        pathlib.Path(output_path).unlink(missing_ok=True)
