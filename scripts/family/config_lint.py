#!/usr/bin/env python3
"""Check JSON files under deploy/.

Exits 0 when deploy/ has no JSON yet. Otherwise every JSON file must parse.
A string field is a secret only when its name ends in a secret component
(apiKey, key, secret, token, or password, in snake_case or camelCase).
Those values must be exactly ``${VAR}``. Integers, booleans, and null are
never secrets, so typed settings such as ``maxTokens`` stay literals.
``identityKey`` is a public id and is not a secret. A file whose name
contains ``config`` is also loaded with nanobot. ``ConfigLoadError`` fails
the check.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

# End of the field name, so plurals such as maxTokens and inlineKeyboards
# do not match. The case-insensitive branch covers snake_case and ALL_CAPS.
# The second branch covers camelCase components (encryptKey, botToken).
_SECRET_NAME = re.compile(
    r"(?i:(?:^|[_-])(?:api[_-]?key|key|secret|token|password)$)"
    r"|(?:^|[a-z0-9])(?:Key|Secret|Token|Password)$"
)
# Feishu identityKey is a public instance id (for example "feishu:cli_..."),
# not a credential. It still ends in Key, so it is named here explicitly.
_NON_SECRET_FIELDS = frozenset({"identitykey", "identity_key"})
_ENV_VALUE = re.compile(r"^\$\{[A-Za-z_][A-Za-z0-9_]*\}$")
_ENV_REF = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEPLOY = _REPO_ROOT / "deploy"


def main() -> int:
    return lint_deploy(_DEPLOY)


def lint_deploy(root: Path) -> int:
    files = sorted(path for path in root.glob("**/*.json") if path.is_file())
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
        print(f"config_lint: {_display(path)}: invalid JSON: {exc}")
        return False

    ok = True
    for location in _plaintext_secrets(data):
        print(f"config_lint: {_display(path)}: {location} must be exactly ${{VAR}}")
        ok = False
    if "config" in path.name.lower() and not _load_template(path, text):
        ok = False
    return ok


def _plaintext_secrets(value: object, location: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{location}.{key}" if location else str(key)
            if (
                isinstance(key, str)
                and isinstance(item, str)
                and _is_secret_name(key)
                and not _is_env_placeholder(item)
            ):
                found.append(child)
            found.extend(_plaintext_secrets(item, child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(_plaintext_secrets(item, f"{location}[{index}]"))
    return found


def _is_secret_name(key: str) -> bool:
    if key.lower() in _NON_SECRET_FIELDS:
        return False
    return _SECRET_NAME.search(key) is not None


def _is_env_placeholder(value: object) -> bool:
    return isinstance(value, str) and _ENV_VALUE.fullmatch(value) is not None


def _display(path: Path) -> str:
    try:
        return str(path.relative_to(_REPO_ROOT))
    except ValueError:
        return str(path)


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
