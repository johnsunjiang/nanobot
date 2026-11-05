"""config-lint accepts typed non-secrets and still rejects plaintext secrets."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "family" / "config_lint.py"


def _lint() -> ModuleType:
    spec = importlib.util.spec_from_file_location("config_lint", _SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write(directory: Path, name: str, payload: object) -> None:
    (directory / name).write_text(json.dumps(payload), encoding="utf-8")


def test_secret_name_matches_credentials_not_typed_fields() -> None:
    lint = _lint()
    secret = (
        "apiKey",
        "api_key",
        "API_KEY",
        "token",
        "bot_token",
        "botToken",
        "password",
        "appPassword",
        "secret",
        "appSecret",
        "encryptKey",
        "encrypt_key",
        "webhookSecretToken",
    )
    plain = (
        "maxTokens",
        "contextWindowTokens",
        "inlineKeyboards",
        "allowedEnvKeys",
        "identityKey",
        "identity_key",
    )
    assert [name for name in secret if not lint._is_secret_name(name)] == []
    assert [name for name in plain if lint._is_secret_name(name)] == []


def test_typed_deploy_config_passes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    lint = _lint()
    _write(
        tmp_path,
        "config.template.json",
        {
            "agents": {
                "defaults": {
                    "maxTokens": 8192,
                    "contextWindowTokens": 200000,
                }
            },
            "channels": {
                "telegram": {
                    "inlineKeyboards": False,
                    "token": "${TELEGRAM_TOKEN}",
                },
                "feishu": {
                    "identityKey": "feishu:cli_example",
                    "appSecret": "${FEISHU_APP_SECRET}",
                    "encryptKey": "${FEISHU_ENCRYPT_KEY}",
                },
            },
            "providers": {"openai": {"apiKey": "${OPENAI_API_KEY}"}},
            "tools": {"exec": {"allowedEnvKeys": ["PATH"]}},
        },
    )

    assert lint.lint_deploy(tmp_path) == 0
    captured = capsys.readouterr()
    assert "checked 1 deploy JSON file" in captured.out
    assert captured.err == ""


def test_plaintext_string_secret_fails(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    lint = _lint()
    _write(
        tmp_path,
        "config.json",
        {"providers": {"openai": {"apiKey": "plaintext-not-for-use"}}},
    )

    assert lint.lint_deploy(tmp_path) == 1
    assert "providers.openai.apiKey must be exactly ${VAR}" in capsys.readouterr().out


def test_typed_env_placeholder_fails_schema(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    lint = _lint()
    _write(
        tmp_path,
        "config.json",
        {"agents": {"defaults": {"maxTokens": "${MAX_TOKENS}"}}},
    )

    assert lint.lint_deploy(tmp_path) == 1
    assert "Must be a valid integer" in capsys.readouterr().out


def test_non_string_values_are_not_secrets(tmp_path: Path) -> None:
    lint = _lint()
    _write(
        tmp_path,
        "notes.json",
        {
            "maxTokens": 8192,
            "contextWindowTokens": 200000,
            "inlineKeyboards": False,
            "apiKey": None,
        },
    )

    assert lint.lint_deploy(tmp_path) == 0


def test_no_json_exits_zero(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    lint = _lint()

    assert lint.lint_deploy(tmp_path) == 0
    assert capsys.readouterr().out.strip() == "config_lint: no deploy JSON yet"
