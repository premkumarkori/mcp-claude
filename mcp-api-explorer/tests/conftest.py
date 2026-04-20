import json
from pathlib import Path

import pytest

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "openapi.json"


@pytest.fixture(scope="session")
def openapi_spec() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
