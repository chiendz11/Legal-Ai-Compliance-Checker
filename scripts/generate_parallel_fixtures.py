"""Regenerate synthetic, checksummed handoffs from the selected knowledge snapshot."""

import argparse
from pathlib import Path

from devtools.fixture_builder import write_fixtures
from devtools.parallel import FIXTURE_ROOT, SCENARIOS, FixturePack
from legal_checker.core.config import Settings
from legal_checker.modules.legal_knowledge.repository import Knowledge


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=FIXTURE_ROOT)
    parser.add_argument("--knowledge", type=Path, default=Settings.from_env().knowledge_path)
    args = parser.parse_args()
    knowledge = Knowledge(args.knowledge)
    write_fixtures(args.output, knowledge)
    for scenario in SCENARIOS:
        FixturePack.load(args.output / scenario, knowledge)
    print(f"Generated and validated {len(SCENARIOS)} synthetic scenarios in {args.output}")


if __name__ == "__main__":
    main()
