"""Run a person's reference stage, or validate JSON output from their implementation."""

import argparse
import json
from pathlib import Path

from devtools.parallel import FIXTURE_ROOT, SCENARIOS, FixturePack, json_text
from legal_checker.core.config import Settings
from legal_checker.modules.legal_knowledge.repository import Knowledge
from pydantic import ValidationError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--person", choices=["all", "1", "2", "3", "4", "5"], default="all")
    parser.add_argument("--scenario", choices=SCENARIOS, default="satisfied")
    parser.add_argument("--all-scenarios", action="store_true")
    parser.add_argument("--fixtures", type=Path, default=FIXTURE_ROOT)
    parser.add_argument("--knowledge", type=Path, default=Settings.from_env().knowledge_path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--verify-output", type=Path, help="JSON produced by your module")
    parser.add_argument(
        "--compare-reference",
        action="store_true",
        help="Also compare with the synthetic reference output",
    )
    args = parser.parse_args()
    if args.verify_output and (args.person == "all" or args.all_scenarios):
        parser.error("--verify-output needs one --person and one --scenario")
    if args.compare_reference and not args.verify_output:
        parser.error("--compare-reference needs --verify-output")
    people = range(1, 6) if args.person == "all" else [int(args.person)]
    scenarios = SCENARIOS if args.all_scenarios else [args.scenario]
    try:
        knowledge = Knowledge(args.knowledge)
        results = []
        for scenario in scenarios:
            pack = FixturePack.load(args.fixtures / scenario, knowledge)
            for person in people:
                if args.verify_output:
                    raw = json.loads(args.verify_output.read_text(encoding="utf-8"))
                    output = pack.validate_output(person, raw, knowledge)
                    if args.compare_reference and output != pack.reference_output(
                        person, knowledge
                    ):
                        raise ValueError(
                            "Valid contract, but output differs from the synthetic reference"
                        )
                    mode = "validate_external_output"
                else:
                    output = pack.reference_output(person, knowledge)
                    pack.validate_output(person, json.loads(json_text(output)), knowledge)
                    mode = (
                        "fixture_replay"
                        if person <= 3
                        else "deterministic_engines"
                        if person == 4
                        else "draft_report_builder"
                    )
                if args.output_dir:
                    target = args.output_dir / scenario / f"person_{person}"
                    target.mkdir(parents=True, exist_ok=True)
                    (target / "input.json").write_text(
                        json_text(pack.input_for(person)), encoding="utf-8"
                    )
                    (target / "output.json").write_text(json_text(output), encoding="utf-8")
                results.append(
                    {"person": person, "scenario": scenario, "status": "PASS", "mode": mode}
                )
        print(json_text({"fixture_only": True, "results": results}), end="")
    except (ValueError, ValidationError, OSError) as exc:
        parser.exit(1, f"Handoff check failed: {exc}\n")


if __name__ == "__main__":
    main()
