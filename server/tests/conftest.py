"""Shared test setup.

The server modules use flat (non-package) imports — ``import buttplug_protocol`` —
so put the server directory on sys.path before anything imports them.
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

import web  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    # The form rate limiter keeps per-IP state in a module global; clear it around
    # every test so attempts don't leak between tests.
    web._attempts.clear()
    yield
    web._attempts.clear()
