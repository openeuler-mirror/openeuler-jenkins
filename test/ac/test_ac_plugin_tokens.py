from unittest import mock

from src.ac.acl.repo_in_maintain.repo_in_maintain import CheckRepoInMaintain
from src.ac.acl.wittyhub_audit.check_wittyhub_audit import CheckWittyhubAudit
from src.ac.framework.ac_base import BaseCheck


def _get_attr(obj, name):
    """读取被测对象内部状态：测试需要，集中封装避免直接访问受保护成员。"""
    return getattr(obj, name)


def _set_attr(obj, name, value):
    """注入被测对象内部状态：测试需要，集中封装避免直接访问受保护成员。"""
    setattr(obj, name, value)


class _Check(BaseCheck):
    def __call__(self, *args, **kwargs):
        pass


def _fake_do_requests(calls, return_code=0):
    def fake(method, url, data=None):
        calls.append((method, url, data.headers if data else {}))
        return return_code

    return fake


def test_resolve_common_tokens_prefers_split_tokens():
    assert _Check.resolve_common_tokens({
        "read_token": "read-token",
        "write_token": "write-token",
        "access_token": "legacy-token",
    }) == ("read-token", "write-token")


def test_resolve_common_tokens_falls_back_to_access_token():
    assert _Check.resolve_common_tokens({"access_token": "legacy-token"}) == (
        "legacy-token",
        "legacy-token",
    )


def test_resolve_common_tokens_missing():
    assert _Check.resolve_common_tokens({}) == ("", "")


def test_get_pr_changed_files_uses_read_token():
    check = _Check("/tmp", "repo")
    _set_attr(check, "_kwargs", {"common_args": {
        "pr_num": "1", "owner": "owner",
        "read_token": "read-token", "write_token": "write-token",
    }})

    with mock.patch("src.proxy.atomgit_proxy.AtomgitProxy") as gp:
        gp.return_value.get_pr_files.return_value = [{"filename": "a"}, {"filename": ""}]
        assert check.get_pr_changed_files() == ["a"]

    gp.assert_called_once_with(
        "owner", "repo", read_token="read-token", write_token="write-token",
    )
    gp.return_value.get_pr_files.assert_called_once_with("1")


def test_get_pr_changed_files_falls_back_to_access_token():
    check = _Check("/tmp", "repo")
    _set_attr(check, "_kwargs", {"common_args": {
        "pr_num": "1", "owner": "owner", "access_token": "legacy-token",
    }})

    with mock.patch("src.proxy.atomgit_proxy.AtomgitProxy") as gp:
        gp.return_value.get_pr_files.return_value = []
        assert check.get_pr_changed_files() == []

    gp.assert_called_once_with(
        "owner", "repo", read_token="legacy-token", write_token="legacy-token",
    )


def test_get_pr_changed_files_without_token_returns_none():
    check = _Check("/tmp", "repo")
    _set_attr(check, "_kwargs", {"common_args": {"pr_num": "1", "owner": "owner"}})

    with mock.patch("src.proxy.atomgit_proxy.AtomgitProxy") as gp:
        assert check.get_pr_changed_files() is None

    gp.assert_not_called()


def _patch_repo_in_maintain_get(monkeypatch, captured):
    class _Response(object):
        status_code = 200
        text = ""
        content = b"packages: []\n"

    def fake_get(url, headers=None):
        captured["url"] = url
        captured["headers"] = headers or {}
        return _Response()

    monkeypatch.setattr(
        "src.ac.acl.repo_in_maintain.repo_in_maintain.requests.get", fake_get,
    )


def test_repo_in_maintain_uses_read_token(monkeypatch):
    captured = {}
    _patch_repo_in_maintain_get(monkeypatch, captured)
    check = CheckRepoInMaintain("/tmp", "repo")

    check(tbranch="master", common_args={"read_token": "read-token", "write_token": "write-token"})

    assert captured.get("headers", {}).get("Authorization") == "Bearer read-token"


def test_repo_in_maintain_falls_back_to_access_token(monkeypatch):
    captured = {}
    _patch_repo_in_maintain_get(monkeypatch, captured)
    check = CheckRepoInMaintain("/tmp", "repo")

    check(tbranch="master", common_args={"access_token": "legacy-token"})

    assert captured.get("headers", {}).get("Authorization") == "Bearer legacy-token"


def test_repo_in_maintain_does_not_use_write_token(monkeypatch):
    captured = {}
    _patch_repo_in_maintain_get(monkeypatch, captured)
    check = CheckRepoInMaintain("/tmp", "repo")

    check(tbranch="master", common_args={"write_token": "write-token"})

    assert "Authorization" not in captured.get("headers", {})


def test_wittyhub_call_resolves_split_tokens(monkeypatch):
    monkeypatch.delenv("WITTYHUB_API_URL", raising=False)
    monkeypatch.delenv("WITTYHUB_ADMIN_TOKEN", raising=False)
    check = CheckWittyhubAudit("/tmp", "repo")

    check(common_args={
        "community": "community", "pr_num": "1",
        "read_token": "read-token", "write_token": "write-token",
    })

    assert (_get_attr(check, "_read_token"), _get_attr(check, "_write_token")) == (
        "read-token", "write-token",
    )


def test_wittyhub_call_falls_back_to_access_token(monkeypatch):
    monkeypatch.delenv("WITTYHUB_API_URL", raising=False)
    monkeypatch.delenv("WITTYHUB_ADMIN_TOKEN", raising=False)
    check = CheckWittyhubAudit("/tmp", "repo")

    check(common_args={"community": "community", "pr_num": "1", "access_token": "legacy-token"})

    assert (_get_attr(check, "_read_token"), _get_attr(check, "_write_token")) == (
        "legacy-token", "legacy-token",
    )


def test_wittyhub_read_uses_read_and_comment_uses_write(monkeypatch):
    check = CheckWittyhubAudit("/tmp", "repo")
    _set_attr(check, "_community", "community")
    _set_attr(check, "_repo", "repo")
    _set_attr(check, "_pr_num", "1")
    _set_attr(check, "_read_token", "read-token")
    _set_attr(check, "_write_token", "write-token")
    calls = []
    monkeypatch.setattr("src.proxy.atomgit_proxy.do_requests", _fake_do_requests(calls))

    _get_attr(check, "_pr_head")()
    _get_attr(check, "_post_comment")("hello")

    assert calls[0][0] == "get"
    assert calls[0][2]["Authorization"] == "Bearer read-token"
    assert calls[1][0] == "post"
    assert calls[1][2]["Authorization"] == "Bearer write-token"


def test_wittyhub_read_works_with_only_read_token(monkeypatch):
    check = CheckWittyhubAudit("/tmp", "repo")
    _set_attr(check, "_community", "community")
    _set_attr(check, "_repo", "repo")
    _set_attr(check, "_pr_num", "1")
    _set_attr(check, "_read_token", "read-token")
    _set_attr(check, "_write_token", "")
    calls = []
    monkeypatch.setattr("src.proxy.atomgit_proxy.do_requests", _fake_do_requests(calls))

    assert _get_attr(check, "_pr_head")() == ("https://atomgit.com/community/repo", "")
    _get_attr(check, "_skill_yaml_changed_fields")(["skill.yaml"])

    assert all(call[2]["Authorization"] == "Bearer read-token" for call in calls)


def test_wittyhub_comment_fails_with_only_read_token(monkeypatch, caplog):
    check = CheckWittyhubAudit("/tmp", "repo")
    _set_attr(check, "_community", "community")
    _set_attr(check, "_repo", "repo")
    _set_attr(check, "_pr_num", "1")
    _set_attr(check, "_read_token", "read-token")
    _set_attr(check, "_write_token", "")
    calls = []
    monkeypatch.setattr("src.proxy.atomgit_proxy.do_requests", _fake_do_requests(calls))

    with caplog.at_level("WARNING"):
        _get_attr(check, "_post_comment")("hello")

    assert calls == []
    assert any("comment pr failed" in record.getMessage() for record in caplog.records)
