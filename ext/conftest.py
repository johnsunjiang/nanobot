"""Keep ``pytest ext/`` off the upstream nanobot fixtures.

The repository root ``conftest.py`` is still imported, but these overrides
replace its autouse fixtures so placeholder tests do not import nanobot.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_EXT_ROOT = str(Path(__file__).resolve().parent)
if _EXT_ROOT not in sys.path:
    sys.path.insert(0, _EXT_ROOT)


@pytest.fixture(autouse=True)
def _isolate_tokenizer_warmup() -> None:
    return None


@pytest.fixture(autouse=True)
def _isolate_tool_entry_points() -> None:
    return None


@pytest.fixture(autouse=True)
def _isolate_nanobot_log_activation() -> None:
    return None


@pytest.fixture(autouse=True)
def _isolate_runtime_stores() -> None:
    return None


@pytest.fixture(scope="session", autouse=True)
def _use_windows_system_ca_for_default_http_clients() -> None:
    return None
