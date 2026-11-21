import json
import pathlib
import subprocess
import sys

import pytest

from src.utils.sensitive_mask import MASK, _mask_json, _mask_text

MODULE_PATH = pathlib.Path(__file__).resolve().parents[2] / "src" / "utils" / "sensitive_mask.py"


def _run_cli(args, data):
    return subprocess.run(
        [sys.executable, str(MODULE_PATH)] + args,
        input=data,
        text=True,
        capture_output=True,
    )


def test_text_mode_masks_equals_and_colon():
    text = "token=abc password: xyz\n"

    assert _mask_text(text) == "token=***MASKED*** password: ***MASKED***\n"


def test_text_mode_preserves_non_sensitive():
    text = "repo=ccb n=1 branch: master auth=v\n"

    assert _mask_text(text) == text


def test_text_mode_masks_quoted_json_like_values():
    text = '"access_token": "x", "n": 1\n'

    assert _mask_text(text) == '"access_token": "***MASKED***", "n": 1\n'


def test_text_mode_masks_compound_and_case_insensitive_keys():
    text = "gitcodeToken=abc MysqlUserPasswd=user:pass OauthPassword=p\n"
    expected = "gitcodeToken=***MASKED*** MysqlUserPasswd=***MASKED*** OauthPassword=***MASKED***\n"

    assert _mask_text(text) == expected


def test_text_mode_leaves_empty_values():
    text = "token=\npassword:\n"

    assert _mask_text(text) == text


@pytest.mark.parametrize(
    "key",
    [
        "token",
        "password",
        "passwd",
        "secret",
        "access_key",
        "gitcodeToken",
        "MysqlUserPasswd",
        "OPENEULER_BOT_TOKEN_READ",
    ],
)
def test_sensitive_key_substring_match(key):
    assert _mask_text("%s=v\n" % key) == "%s=%s\n" % (key, MASK)


def test_json_mode_masks_sensitive_keys_only():
    payload = {"access_token": "x", "n": 1, "nested": {"password": "p"}}

    masked = _mask_json(payload)

    assert masked == {"access_token": MASK, "n": 1, "nested": {"password": MASK}}
    assert list(masked) == ["access_token", "n", "nested"]


def test_json_mode_preserves_empty_and_non_sensitive():
    payload = {"token": "", "repo": "ccb", "list": [{"secret": "s"}, {"ok": True}]}

    masked = _mask_json(payload)

    assert masked["token"] == ""
    assert masked["repo"] == "ccb"
    assert masked["list"][0]["secret"] == MASK
    assert masked["list"][1]["ok"] is True


def test_cli_text_mode():
    result = _run_cli([], "token=abc password=xyz\n")

    assert result.returncode == 0
    assert result.stdout == "token=***MASKED*** password=***MASKED***\n"
    assert result.stderr == ""


def test_cli_json_mode_outputs_valid_json():
    result = _run_cli(["--json"], '{"access_token":"x","n":1}\n')

    assert result.returncode == 0
    assert json.loads(result.stdout) == {"access_token": MASK, "n": 1}
    assert result.stdout.endswith("\n")


def test_cli_json_mode_invalid_json_exits_nonzero():
    result = _run_cli(["--json"], "not-json\n")

    assert result.returncode == 2
    assert result.stdout == ""
    assert "invalid JSON" in result.stderr
