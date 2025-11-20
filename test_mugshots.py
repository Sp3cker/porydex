#!/usr/bin/env python3
"""Test script for generic table parser demo."""

import json
import pathlib
import sys

# Add porydex to path
sys.path.insert(0, str(pathlib.Path(__file__).parent))

import porydex.config
from porydex.parse.mugshots import parse_mugshots


def main():
    """Run mugshots parser demo."""
    # Load config
    porydex.config.load()

    print(f"\n{'='*60}")
    print("Generic Table Parser Demo: Field Mugshots")
    print(f"{'='*60}\n")

    print(f"Expansion path: {porydex.config.expansion}")
    print(f"Parsing mugshots...\n")

    # Parse mugshots
    result = parse_mugshots(porydex.config.expansion)

    # Print summary
    print(f"\n{'='*60}")
    print("Summary")
    print(f"{'='*60}")
    print(f"Mugshot types:     {result['counts']['mugshot_types']}")
    print(f"Emote types:       {result['counts']['emote_types']}")
    print(f"Total entries:     {result['counts']['entries']}")
    print(f"Graphics symbols:  {result['counts']['graphics_symbols']}")
    print(f"Palette symbols:   {result['counts']['palette_symbols']}")

    # Show sample entries
    print(f"\n{'='*60}")
    print("Sample Entries")
    print(f"{'='*60}")

    mugshots = result['mugshots']
    for i, (mugshot_id, emotes) in enumerate(list(mugshots.items())[:5]):
        print(f"\n{i+1}. {mugshot_id}:")
        for emote_id, fields in emotes.items():
            print(f"   [{emote_id}]")
            for field_name, field_value in fields.items():
                # Truncate long paths
                if isinstance(field_value, str) and len(field_value) > 50:
                    field_value = "..." + field_value[-47:]
                print(f"     {field_name:12} = {field_value}")

    # Show full structure for one entry
    print(f"\n{'='*60}")
    print("Full Structure Example: MUGSHOT_OKADA")
    print(f"{'='*60}")
    if "MUGSHOT_OKADA" in mugshots:
        print(json.dumps(mugshots["MUGSHOT_OKADA"], indent=2))

    # Save JSON output
    output_file = pathlib.Path("mugshots_demo.json")
    with open(output_file, 'w') as f:
        json.dump(result, f, indent=2)

    print(f"\n{'='*60}")
    print(f"✅ Full output saved to: {output_file}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
