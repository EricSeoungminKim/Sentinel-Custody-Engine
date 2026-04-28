import os

import pytest


def pytest_collection_modifyitems(config, items):
    if os.getenv("RUN_SEPOLIA_BROADCAST") == "1":
        return
    skip_broadcast = pytest.mark.skip(reason="set RUN_SEPOLIA_BROADCAST=1 to run Sepolia broadcast tests")
    for item in items:
        if "sepolia_broadcast" in item.keywords:
            item.add_marker(skip_broadcast)
