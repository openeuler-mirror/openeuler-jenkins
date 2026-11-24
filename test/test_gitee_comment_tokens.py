import pytest

pytest.importorskip("jenkins")

from src.build import gitee_comment

TOKEN_ENVS = (
    "GITCODE_TOKEN_READ",
    "GITCODE_TOKEN_WRITE",
    "GITHUB_TOKEN",
    "JENKINS_API_TOKEN",
)


def _get_attr(obj, name):
    """读取被测对象内部状态：测试需要，集中封装避免直接访问受保护成员。"""
    return getattr(obj, name)


@pytest.fixture(autouse=True)
def clean_token_env(monkeypatch):
    """隔离宿主环境，避免真实 token 干扰用例。"""
    for name in TOKEN_ENVS:
        monkeypatch.delenv(name, raising=False)


def _fake_do_requests(calls, return_code=0):
    def fake(method, url, data=None):
        calls.append((method, url, data.headers if data else {}))
        return return_code

    return fake


def test_atomgit_proxy_uses_split_env(monkeypatch):
    monkeypatch.setenv("GITCODE_TOKEN_READ", "read-token")
    monkeypatch.setenv("GITCODE_TOKEN_WRITE", "write-token")

    gp = gitee_comment.build_code_proxy("gitcode", "owner", "repo")

    assert (_get_attr(gp, "_read_token"), _get_attr(gp, "_write_token")) == (
        "read-token", "write-token",
    )


def test_cli_token_stays_dual_for_local_debug(monkeypatch):
    monkeypatch.setenv("GITCODE_TOKEN_READ", "read-token")
    monkeypatch.setenv("GITCODE_TOKEN_WRITE", "write-token")

    gp = gitee_comment.build_code_proxy("gitcode", "owner", "repo", "cli-token")

    assert (_get_attr(gp, "_read_token"), _get_attr(gp, "_write_token")) == (
        "cli-token", "cli-token",
    )


def test_github_uses_github_token(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "github-token")

    gp = gitee_comment.build_code_proxy("github", "owner", "repo")

    assert (_get_attr(gp, "_read_token"), _get_attr(gp, "_write_token")) == (
        "github-token", "github-token",
    )


def test_gitee_keeps_single_token(monkeypatch):
    monkeypatch.setenv("GITCODE_TOKEN_READ", "read-token")
    monkeypatch.setenv("GITCODE_TOKEN_WRITE", "write-token")

    gp = gitee_comment.build_code_proxy("gitee", "owner", "repo")

    assert _get_attr(gp, "_token") == "write-token"


def test_write_only_proxy_can_comment_and_tag(monkeypatch):
    monkeypatch.setenv("GITCODE_TOKEN_WRITE", "write-token")
    calls = []
    monkeypatch.setattr("src.proxy.atomgit_proxy.do_requests", _fake_do_requests(calls))
    gp = gitee_comment.build_code_proxy("gitcode", "owner", "repo")

    assert gp.comment_pr("1", "body") is True
    assert gp.create_tags_of_pr("1", "ci_successful") is True

    assert calls
    assert all(call[2]["Authorization"] == "Bearer write-token" for call in calls)


def test_read_only_proxy_fails_write_ops(monkeypatch):
    monkeypatch.setenv("GITCODE_TOKEN_READ", "read-token")
    gp = gitee_comment.build_code_proxy("gitcode", "owner", "repo")

    with pytest.raises(RuntimeError):
        gp.comment_pr("1", "body")
    with pytest.raises(RuntimeError):
        gp.create_tags_of_pr("1", "ci_successful")


def test_jenkins_token_env_wins(monkeypatch):
    monkeypatch.setenv("JENKINS_API_TOKEN", "env-token")

    jp = gitee_comment.build_jenkins_proxy("https://ci.example.com/", "user", "cli-token")

    assert _get_attr(jp, "_token") == "env-token"


def test_jenkins_token_falls_back_to_cli(monkeypatch):
    jp = gitee_comment.build_jenkins_proxy("https://ci.example.com/", "user", "cli-token")

    assert _get_attr(jp, "_token") == "cli-token"
