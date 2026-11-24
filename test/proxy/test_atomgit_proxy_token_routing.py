import json

import pytest

from src.proxy import atomgit_proxy
from src.proxy.atomgit_proxy import AtomgitProxy


class _Recorder(object):
    def __init__(self):
        self.calls = []

    def __call__(self, method, url, data=None):
        self.calls.append({"method": method, "url": url, "data": data})
        return 0


@pytest.fixture
def recorder(monkeypatch):
    rec = _Recorder()
    monkeypatch.setattr(atomgit_proxy, "do_requests", rec)
    return rec


READ_CALLS = [
    ("get_labels_of_pr", (1,), {}),
    ("get_last_pr_committer", ("master",), {}),
    ("get_issue", (1,), {}),
    ("get_all_issues_data", (), {}),
    ("get_pr_info", (1,), {}),
    ("get_pr_files", (1,), {}),
    ("get_milestone_id", (), {}),
]

WRITE_CALLS = [
    ("comment_pr", (1, "comment body"), {}),
    ("handle_tags_of_pr", ("POST", 1, "ci_processing"), {}),
    ("create_tags_of_pr", (1, "ci_processing"), {}),
    ("replace_all_tags_of_pr", (1, "ci_successful"), {}),
    ("delete_tag_of_pr", (1, "ci_failed"), {}),
    ("create_issue", ("src-openeuler", {"title": "t", "repo": "r", "body": "b"}), {}),
    ("update_issue", ("src-openeuler", {"title": "t"}, 1), {}),
]


@pytest.mark.parametrize("method,args,kwargs", READ_CALLS)
def test_read_methods_use_read_token(recorder, method, args, kwargs):
    proxy = AtomgitProxy("owner", "repo", read_token="read-token", write_token="write-token")

    getattr(proxy, method)(*args, **kwargs)

    assert len(recorder.calls) == 1
    assert recorder.calls[0]["data"].headers == {"Authorization": "Bearer read-token"}


@pytest.mark.parametrize("method,args,kwargs", WRITE_CALLS)
def test_write_methods_use_write_token(recorder, method, args, kwargs):
    proxy = AtomgitProxy("owner", "repo", read_token="read-token", write_token="write-token")

    getattr(proxy, method)(*args, **kwargs)

    assert len(recorder.calls) == 1
    assert recorder.calls[0]["data"].headers == {"Authorization": "Bearer write-token"}


def test_read_method_fails_fast_without_read_token(recorder):
    proxy = AtomgitProxy("owner", "repo", write_token="write-token")

    with pytest.raises(RuntimeError, match="read token not provided"):
        proxy.get_pr_info(1)

    assert recorder.calls == []


@pytest.mark.parametrize("method,args,kwargs", READ_CALLS)
def test_read_only_proxy_keeps_read_available(recorder, method, args, kwargs):
    """反向测试：只有 READ token 时，全部读方法正常。"""
    proxy = AtomgitProxy("owner", "repo", read_token="read-token")

    getattr(proxy, method)(*args, **kwargs)

    assert recorder.calls[0]["data"].headers == {"Authorization": "Bearer read-token"}


@pytest.mark.parametrize("method,args,kwargs", WRITE_CALLS)
def test_read_only_proxy_fails_all_writes(recorder, method, args, kwargs):
    """反向测试：WRITE 缺失（等价于误用 READ）时，全部写方法 fail-fast。"""
    proxy = AtomgitProxy("owner", "repo", read_token="read-token")

    with pytest.raises(RuntimeError, match="write token not provided"):
        getattr(proxy, method)(*args, **kwargs)

    assert recorder.calls == []


def test_write_method_fails_fast_without_write_token(recorder):
    proxy = AtomgitProxy("owner", "repo", read_token="read-token")

    with pytest.raises(RuntimeError, match="write token not provided"):
        proxy.comment_pr(1, "comment body")

    assert recorder.calls == []


def test_legacy_positional_token_works_for_read_and_write(recorder):
    proxy = AtomgitProxy("owner", "repo", "legacy-token")

    proxy.get_pr_info(1)
    proxy.comment_pr(1, "comment body")

    assert [call["data"].headers for call in recorder.calls] == [
        {"Authorization": "Bearer legacy-token"},
        {"Authorization": "Bearer legacy-token"},
    ]


def test_split_tokens_take_precedence_over_legacy_token(recorder):
    proxy = AtomgitProxy(
        "owner", "repo", "legacy-token", read_token="read-token", write_token="write-token"
    )

    proxy.get_pr_info(1)
    proxy.comment_pr(1, "comment body")

    assert [call["data"].headers for call in recorder.calls] == [
        {"Authorization": "Bearer read-token"},
        {"Authorization": "Bearer write-token"},
    ]


def test_requests_do_not_carry_access_token(recorder):
    proxy = AtomgitProxy("owner", "repo", read_token="read-token", write_token="write-token")

    proxy.get_pr_files(1)
    proxy.comment_pr(1, "comment body")
    proxy.create_issue("src-openeuler", {"title": "t", "repo": "r", "body": "b"})
    proxy.update_issue("src-openeuler", {"title": "t"}, 1)

    assert len(recorder.calls) == 4
    for call in recorder.calls:
        assert "access_token" not in call["url"]
        assert "access_token" not in json.dumps(call["data"].body, ensure_ascii=False)
