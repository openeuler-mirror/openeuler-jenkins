import pytest

from src.ac.framework.ac import resolve_jenkins_api_token, resolve_tokens


@pytest.fixture
def clean_env(monkeypatch):
    for name in ("GITCODE_TOKEN_READ", "GITCODE_TOKEN_WRITE", "GITHUB_TOKEN"):
        monkeypatch.delenv(name, raising=False)


def test_atomgit_reads_split_env(clean_env, monkeypatch):
    monkeypatch.setenv("GITCODE_TOKEN_READ", "read-token")
    monkeypatch.setenv("GITCODE_TOKEN_WRITE", "write-token")

    assert resolve_tokens("atomgit") == ("read-token", "write-token")


@pytest.mark.parametrize(
    "env,expected",
    [
        ({"GITCODE_TOKEN_READ": "read-token"}, ("read-token", "")),
        ({"GITCODE_TOKEN_WRITE": "write-token"}, ("", "write-token")),
        ({}, ("", "")),
    ],
)
def test_atomgit_env_combinations(clean_env, monkeypatch, env, expected):
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    assert resolve_tokens("atomgit") == expected


def test_cli_token_wins_for_local_debug(clean_env, monkeypatch):
    monkeypatch.setenv("GITCODE_TOKEN_READ", "read-token")
    monkeypatch.setenv("GITCODE_TOKEN_WRITE", "write-token")

    assert resolve_tokens("atomgit", "legacy-token") == ("legacy-token", "legacy-token")


def test_github_uses_github_token_for_both(clean_env, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "github-token")

    assert resolve_tokens("github") == ("github-token", "github-token")


def test_github_cli_token_wins_for_local_debug(clean_env, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "github-token")

    assert resolve_tokens("github", "legacy-token") == ("legacy-token", "legacy-token")


def test_jenkins_api_token_prefers_env(monkeypatch):
    monkeypatch.setenv("JENKINS_API_TOKEN", "env-token")

    assert resolve_jenkins_api_token("cli-token") == "env-token"


def test_jenkins_api_token_falls_back_to_cli(monkeypatch):
    monkeypatch.delenv("JENKINS_API_TOKEN", raising=False)

    assert resolve_jenkins_api_token("cli-token") == "cli-token"


def test_jenkins_api_token_missing(monkeypatch):
    monkeypatch.delenv("JENKINS_API_TOKEN", raising=False)

    assert resolve_jenkins_api_token(None) == ""
