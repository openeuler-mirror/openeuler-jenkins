import tempfile
from types import SimpleNamespace

import pytest

pytest.importorskip("jenkins")

from src.build import comment_entry, final_entry, summary_entry


class _FakeProxy(object):
    instances = []

    def __init__(self, owner, repo, **kwargs):
        self.owner = owner
        self.repo = repo
        self.kwargs = kwargs
        self.calls = []
        _FakeProxy.instances.append(self)

    def comment_pr(self, *args):
        self.calls.append(("comment_pr", args))
        return True

    def create_tags_of_pr(self, *args):
        self.calls.append(("create_tags_of_pr", args))
        return True

    def delete_tag_of_pr(self, *args):
        self.calls.append(("delete_tag_of_pr", args))
        return True

    def get_labels_of_pr(self, *args):
        self.calls.append(("get_labels_of_pr", args))
        return []


class _FakeComment(object):
    def __init__(self, *args, **kwargs):
        self.check_license_result = True

    def set_compile_build(self, *args, **kwargs):
        pass

    def comment_build(self, gp):
        pass

    def comment_compare_package_details(self, *args, **kwargs):
        pass


def _ctx(**overrides):
    values = dict(
        pr_number="1",
        repo="repo",
        owner="src-openeuler",
        arch="x86_64",
        variant="",
        workspace=tempfile.gettempdir(),
        pipeline_url="https://example.com/run/1",
        run_number="1",
        target_branch="master",
        read_token="read-token",
        write_token="write-token",
        committer="alice",
    )
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.fixture
def captured(monkeypatch):
    calls = {}

    def fake_load_action_context(entry_name, required=(), write_only=False):
        calls["entry_name"] = entry_name
        calls["required"] = required
        calls["write_only"] = write_only
        return _ctx()

    monkeypatch.setattr(summary_entry, "setup_action_logging", lambda *a, **k: None)
    monkeypatch.setattr(comment_entry, "setup_action_logging", lambda *a, **k: None)
    monkeypatch.setattr(final_entry, "setup_action_logging", lambda *a, **k: None)
    for module in (summary_entry, comment_entry, final_entry):
        monkeypatch.setattr(module, "load_action_context", fake_load_action_context)
        monkeypatch.setattr(module, "AtomgitProxy", _FakeProxy)
    monkeypatch.setattr(summary_entry, "Comment", _FakeComment)
    monkeypatch.setattr(comment_entry, "Comment", _FakeComment)
    _FakeProxy.instances = []
    return calls


def test_summary_entry_uses_write_only(monkeypatch, captured):
    monkeypatch.setenv("ACTION_ARTIFACT_DIR", "")
    monkeypatch.setattr(summary_entry, "_scan_builds", lambda *a, **k: [])
    summary_entry.main()

    assert captured["entry_name"] == "build_summary"
    assert captured["write_only"] is True
    assert "write_token" in captured["required"]
    assert "token" not in captured["required"]


def test_summary_entry_proxy_has_write_token_only(monkeypatch, captured):
    monkeypatch.setenv("ACTION_ARTIFACT_DIR", "")
    monkeypatch.setattr(
        summary_entry,
        "_scan_builds",
        lambda *a, **k: [
            {
                "arch_name": "x86_64",
                "build_rc": 0,
                "check_file": "/nonexistent/check",
                "compare_file": "/nonexistent/compare",
            }
        ],
    )
    summary_entry.main()

    assert _FakeProxy.instances[-1].kwargs == {"write_token": "write-token"}


def test_comment_entry_uses_write_only(monkeypatch, captured, tmp_path):
    monkeypatch.setenv("ACTION_BUILD_RESULT", "0")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        comment_entry,
        "_locate_artifacts",
        lambda *a, **k: ("/nonexistent/check", "/nonexistent/compare"),
    )
    comment_entry.main()

    assert captured["entry_name"] == "build_comment"
    assert captured["write_only"] is True
    assert "write_token" in captured["required"]
    assert "token" not in captured["required"]
    assert _FakeProxy.instances[-1].kwargs == {"write_token": "write-token"}


def test_final_entry_uses_read_and_write(monkeypatch, captured):
    monkeypatch.setenv("ACTION_GATE_RESULT", "success")
    monkeypatch.setenv("ACTION_BUILD_RESULT", "success")
    final_entry.main()

    assert captured["entry_name"] == "final"
    assert captured["write_only"] is False
    assert "read_token" in captured["required"]
    assert "write_token" in captured["required"]
    assert "token" not in captured["required"]

    proxy = _FakeProxy.instances[-1]
    assert proxy.kwargs == {"read_token": "read-token", "write_token": "write-token"}
    assert ("get_labels_of_pr", ("1",)) in proxy.calls
    assert ("create_tags_of_pr", ("1", "ci_successful")) in proxy.calls
    assert ("comment_pr", ("1", "@alice")) in proxy.calls
