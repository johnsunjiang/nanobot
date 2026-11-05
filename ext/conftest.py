"""Make ``ext/`` importable for pytest.

Run with ``--confcutdir=ext`` so the repository root ``conftest.py`` is not
loaded. Isolation that ext tests need later belongs in this directory.
"""

from __future__ import annotations

import sys
from pathlib import Path

_EXT_ROOT = str(Path(__file__).resolve().parent)
if _EXT_ROOT not in sys.path:
    sys.path.insert(0, _EXT_ROOT)
