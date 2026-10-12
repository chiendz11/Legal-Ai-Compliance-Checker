import pytest

from devtools.parallel import FIXTURE_ROOT, SCENARIOS, FixturePack


@pytest.fixture(scope="session")
def parallel_packs(knowledge):
    return {
        scenario: FixturePack.load(FIXTURE_ROOT / scenario, knowledge) for scenario in SCENARIOS
    }
