from types import SimpleNamespace

import pytest

from src.ac import gate_entry


class _FakeProxy(object):
    instances = []

    def __init__(self, owner, repo, **kwargs):
        self.owner = owner
        self.repo = repo
        self.kwargs = kwargs
        self.calls = []
        _FakeProxy.instances.append(self)

    def delete_tag_of_pr(self, *args):
        self.calls.append(("delete_tag_of_pr", args))

    def create_tags_of_pr(self, *args):
        self.calls.append(("create_tags_of_pr", args))

    def comment_pr(self, *args):
        self.calls.append(("comment_pr", args))


class _FakeAC(object):
    last_common_args = None

    def __init__(self, ac_yaml_path, community):
        self._ac_check_result = []

    def check_all(self, workspace, repo, dataset, tbranch, common_args):
        _FakeAC.last_common_args = common_args

    def save(self, path):
        self.saved_path = path

    def get_check_result(self, name):
        return None


class _FakeGit(object):
    def fetch_pull_request(self, *args, **kwargs):
        return True

    def checkout_to_commit_force(self, *args, **kwargs):
        pass


class _FakeGitProxy(object):
    @staticmethod
    def init_repository(*args, **kwargs):
        return _FakeGit()


@pytest.fixture
def gate_env(monkeypatch):
    captured = {}

    ctx = SimpleNamespace(
        pr_number="1",
        repo="repo",
        owner="src-openeuler",
        target_branch="master",
        read_token="read-token",
        write_token="write-token",
        workspace="/tmp/workspace",
        pr_url="https://atomgit.com/src-openeuler/repo/pull/1",
        pipeline_url="",
        run_number="",
        committer="committer",
    )

    def fake_load_action_context(entry_name, required=(), write_only=False):
        captured["entry_name"] = entry_name
        captured["required"] = required
        captured["write_only"] = write_only
        return ctx

    monkeypatch.setattr(gate_entry, "setup_action_logging", lambda *a, **k: None)
    monkeypatch.setattr(gate_entry, "load_action_context", fake_load_action_context)
    monkeypatch.setattr(gate_entry, "AtomgitProxy", _FakeProxy)
    monkeypatch.setattr(gate_entry, "AC", _FakeAC)
    monkeypatch.setattr(gate_entry, "GitProxy", _FakeGitProxy)
    monkeypatch.setattr(gate_entry, "_upload_support_arch", lambda *a, **k: None)
    monkeypatch.setattr(gate_entry, "_build_pr_comment", lambda *a, **k: "comment body")
    monkeypatch.setattr(gate_entry, "_comment_ai_summary", lambda *a, **k: None)

    _FakeProxy.instances = []
    return captured


def test_gate_requires_read_and_write_tokens(gate_env):
    gate_entry.main()

    assert gate_env["required"] == (
        "pr_number", "repo", "owner", "read_token", "write_token",
    )
    assert "token" not in gate_env["required"]


def test_gate_constructs_proxy_with_split_tokens(gate_env):
    gate_entry.main()

    proxy = _FakeProxy.instances[0]
    assert proxy.owner == "src-openeuler"
    assert proxy.repo == "repo"
    assert proxy.kwargs == {"read_token": "read-token", "write_token": "write-token"}


def test_gate_tags_and_comment_use_write_methods(gate_env):
    gate_entry.main()

    proxy = _FakeProxy.instances[0]
    method_names = [name for name, _ in proxy.calls]
    assert method_names == [
        "delete_tag_of_pr",
        "delete_tag_of_pr",
        "create_tags_of_pr",
        "comment_pr",
        "delete_tag_of_pr",
        "delete_tag_of_pr",
    ]
    assert "comment_pr" in method_names


def test_gate_common_args_carries_split_tokens(gate_env):
    gate_entry.main()

    common_args = _FakeAC.last_common_args
    assert common_args["read_token"] == "read-token"
    assert common_args["write_token"] == "write-token"
    assert common_args["access_token"] == "write-token"


def test_gate_common_args_access_token_falls_back_to_read(monkeypatch):
    captured = {}

    ctx = SimpleNamespace(
        pr_number="1",
        repo="repo",
        owner="src-openeuler",
        target_branch="master",
        read_token="read-token",
        write_token="",
        workspace="/tmp/workspace",
        pr_url="",
        pipeline_url="",
        run_number="",
        committer="committer",
    )

    def fake_load_action_context(entry_name, required=(), write_only=False):
        captured["required"] = required
        return ctx

    monkeypatch.setattr(gate_entry, "setup_action_logging", lambda *a, **k: None)
    monkeypatch.setattr(gate_entry, "load_action_context", fake_load_action_context)
    monkeypatch.setattr(gate_entry, "AtomgitProxy", _FakeProxy)
    monkeypatch.setattr(gate_entry, "AC", _FakeAC)
    monkeypatch.setattr(gate_entry, "GitProxy", _FakeGitProxy)
    monkeypatch.setattr(gate_entry, "_upload_support_arch", lambda *a, **k: None)
    monkeypatch.setattr(gate_entry, "_build_pr_comment", lambda *a, **k: "comment body")
    monkeypatch.setattr(gate_entry, "_comment_ai_summary", lambda *a, **k: None)

    _FakeProxy.instances = []
    gate_entry.main()

    assert _FakeAC.last_common_args["access_token"] == "read-token"
