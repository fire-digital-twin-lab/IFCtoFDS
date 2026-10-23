"""Generate an explicitly synthetic IFC4 MEP/PCCC model with swept geometry.

Run: python -m scripts.generate_mep_geometry_fixture --output examples/mep-fire-geometry.ifc
"""

import argparse
import json
from pathlib import Path

from tests.support.mep_geometry import create_mep_geometry_ifc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    expected = create_mep_geometry_ifc(args.output)
    args.output.with_suffix(".expected.json").write_text(
        json.dumps(expected, indent=2), encoding="utf-8"
    )
    print(
        f"Authored fixture: {args.output}; {len(expected['members'])} physical members"
    )


if __name__ == "__main__":
    main()
