import pytest

from src.action_context import MissingActionEnvError, load_action_context

TOKEN_ENVS = (
    "ACTION_BOT_TOKEN",
    "ACTION_SELF_TOKEN",
    "ACTION_GITCODE_TOKEN_READ",
    "ACTION_GITCODE_TOKEN_WRITE",
)


@pytest.fixture(autouse=True)
def clean_token_env(monkeypatch):
    """隔离宿主环境，避免真实 token 干扰用例。"""
    for name in TOKEN_ENVS:
        monkeypatch.delenv(name, raising=False)


def _tokens(ctx):
    return ctx.read_token, ctx.write_token, ctx.token


def test_gate_falls_back_to_action_self_token(monkeypatch):
    monkeypatch.setenv("ACTION_SELF_TOKEN", "gate-fallback")

    ctx = load_action_context("gate")

    assert _tokens(ctx) == ("gate-fallback", "gate-fallback", "gate-fallback")


def test_build_falls_back_to_action_self_token(monkeypatch):
    monkeypatch.setenv("ACTION_SELF_TOKEN", "build-fallback")

    ctx = load_action_context("build_entry")

    assert _tokens(ctx) == ("build-fallback", "build-fallback", "build-fallback")


def test_final_falls_back_to_action_self_token(monkeypatch):
    monkeypatch.setenv("ACTION_SELF_TOKEN", "final-fallback")

    ctx = load_action_context("final")

    assert _tokens(ctx) == ("final-fallback", "final-fallback", "final-fallback")


def test_build_comment_uses_write_token_only(monkeypatch):
    monkeypatch.setenv("ACTION_GITCODE_TOKEN_READ", "read-should-be-ignored")
    monkeypatch.setenv("ACTION_SELF_TOKEN", "platform-should-be-ignored")
    monkeypatch.setenv("ACTION_GITCODE_TOKEN_WRITE", "write-only")

    ctx = load_action_context("build_comment", write_only=True)

    assert _tokens(ctx) == ("", "write-only", "write-only")


def test_split_tokens_used_without_fallback(monkeypatch):
    monkeypatch.setenv("ACTION_GITCODE_TOKEN_READ", "read-token")
    monkeypatch.setenv("ACTION_GITCODE_TOKEN_WRITE", "write-token")

    ctx = load_action_context("build_entry")

    assert _tokens(ctx) == ("read-token", "write-token", "read-token")


def test_split_tokens_preferred_over_fallback(monkeypatch):
    monkeypatch.setenv("ACTION_SELF_TOKEN", "platform-token")
    monkeypatch.setenv("ACTION_GITCODE_TOKEN_READ", "read-token")
    monkeypatch.setenv("ACTION_GITCODE_TOKEN_WRITE", "write-token")

    ctx = load_action_context("gate")

    assert _tokens(ctx) == ("read-token", "write-token", "read-token")


def test_all_tokens_empty(monkeypatch):
    ctx = load_action_context("gate")

    assert _tokens(ctx) == ("", "", "")


def test_empty_split_token_falls_back(monkeypatch):
    monkeypatch.setenv("ACTION_GITCODE_TOKEN_READ", "")
    monkeypatch.setenv("ACTION_GITCODE_TOKEN_WRITE", "")
    monkeypatch.setenv("ACTION_SELF_TOKEN", "fallback")

    ctx = load_action_context("final")

    assert _tokens(ctx) == ("fallback", "fallback", "fallback")


def test_write_only_requires_write_token_without_fallback(monkeypatch):
    """反向测试：只有 READ / 平台 token 时，build-comment 必须 fail-fast。"""
    monkeypatch.setenv("ACTION_SELF_TOKEN", "platform-token")
    monkeypatch.setenv("ACTION_GITCODE_TOKEN_READ", "read-token")

    with pytest.raises(MissingActionEnvError) as excinfo:
        load_action_context("build_comment", required=("write_token",), write_only=True)

    assert "ACTION_GITCODE_TOKEN_WRITE" in str(excinfo.value)


def test_action_bot_token_is_ignored(monkeypatch):
    monkeypatch.setenv("ACTION_BOT_TOKEN", "legacy-bot-token")

    ctx = load_action_context("gate")

    assert _tokens(ctx) == ("", "", "")


def test_action_bot_token_does_not_override_split_tokens(monkeypatch):
    monkeypatch.setenv("ACTION_BOT_TOKEN", "legacy-bot-token")
    monkeypatch.setenv("ACTION_GITCODE_TOKEN_READ", "read-token")
    monkeypatch.setenv("ACTION_GITCODE_TOKEN_WRITE", "write-token")

    ctx = load_action_context("final")

    assert _tokens(ctx) == ("read-token", "write-token", "read-token")


def test_missing_required_token_reports_env_hint(monkeypatch):
    monkeypatch.setenv("ACTION_PR_NUMBER", "1")
    monkeypatch.setenv("ACTION_REPO", "ccb")
    monkeypatch.setenv("ACTION_OWNER", "src-openeuler")

    with pytest.raises(MissingActionEnvError) as excinfo:
        load_action_context(
            "gate", required=("pr_number", "repo", "owner", "token")
        )

    message = str(excinfo.value)
    assert "ACTION_GITCODE_TOKEN_READ" in message
    assert "ACTION_SELF_TOKEN" in message
