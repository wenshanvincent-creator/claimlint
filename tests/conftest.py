import shutil
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def project(tmp_path):
    def create(name="drift"):
        destination = tmp_path / name
        shutil.copytree(FIXTURES / name, destination)
        return destination

    return create
