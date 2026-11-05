"""Trivial check so ``pytest ext/`` collects and passes."""

from __future__ import annotations

import family_tools


def test_family_tools_package_imports() -> None:
    assert family_tools.__name__ == "family_tools"
