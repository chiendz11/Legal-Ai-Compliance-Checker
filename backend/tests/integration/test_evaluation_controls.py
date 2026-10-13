"""Independent synthetic assertions exercise gates, aggregation and numeric boundaries."""

import pytest
from devtools.evaluation_controls import controlled_cases, verify_control


@pytest.mark.parametrize("index", range(32))
def test_controlled_specification(knowledge, index):
    case = controlled_cases(knowledge)[index]
    assert case["input"]["payload"]["requirements"][0]["profile_snapshot_json"]["synthetic_spec"]
    verify_control(case, knowledge)
