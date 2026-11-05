#!/usr/bin/env python3
"""Check JSON files under deploy/.

Exits 0 when deploy/ has no JSON yet. Otherwise every JSON file must parse,
and any field whose name contains key, secret, token, or password must be
exactly ``${VAR}``. A file whose name contains ``config`` is also loaded with
nanobot. ``ConfigLoadError`` fails the check.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

_SECRET_NAME = re.compile(r"(?i)(key|secret|token|password)")
_ENV_VALUE = re.compile(r"^\$\{[A-Za-z_][A-Za-z0-9_]*\}$")
_ENV_REF = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEPLOY = _REPO_ROOT / "deploy"


def main() -> int:
    files = sorted(path for path in _DEPLOY.glob("**/*.json") if path.is_file())
    if not files:
        print("config_lint: no deploy JSON yet")
        return 0

    failed = False
    for path in files:
        if not _check_file(path):
            failed = True
    if failed:
        return 1
    print(f"config_lint: checked {len(files)} deploy JSON file(s)")
    return 0


def _check_file(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"config_lint: {path.relative_to(_REPO_ROOT)}: invalid JSON: {exc}")
        return False

    ok = True
    for location in _plaintext_secrets(data):
        print(f"config_lint: {path.relative_to(_REPO_ROOT)}: {location} must be exactly ${{VAR}}")
        ok = False
    if "config" in path.name.lower() and not _load_template(path, text):
        ok = False
    return ok


def _plaintext_secrets(value: object, location: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{location}.{key}" if location else str(key)
            if isinstance(key, str) and _SECRET_NAME.search(key) and not _is_env_placeholder(item):
                found.append(child)
            found.extend(_plaintext_secrets(item, child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(_plaintext_secrets(item, f"{location}[{index}]"))
    return found


def _is_env_placeholder(value: object) -> bool:
    return isinstance(value, str) and _ENV_VALUE.fullmatch(value) is not None


def _load_template(path: Path, text: str) -> bool:
    from nanobot.config.errors import ConfigLoadError
    from nanobot.config.loader import load_config, resolve_config_env_vars

    added = [name for name in _ENV_REF.findall(text) if name not in os.environ]
    for name in added:
        os.environ[name] = "family-lint-placeholder"
    try:
        config = load_config(path)
        resolve_config_env_vars(config, config_path=path)
    except ConfigLoadError as exc:
        print(exc)
        return False
    finally:
        for name in added:
            os.environ.pop(name, None)
    return True


if __name__ == "__main__":
    sys.exit(main())
