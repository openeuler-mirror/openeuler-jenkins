import json

import pytest

from src.proxy import github_proxy
from src.proxy.github_proxy import GithubProxy


class _Recorder(object):
    def __init__(self):
        self.calls = []

    def __call__(self, method, url, data=None):
        self.calls.append({"method": method, "url": url, "data": data})
        return 0


@pytest.fixture
def recorder(monkeypatch):
    rec = _Recorder()
    monkeypatch.setattr(github_proxy, "do_requests", rec)
    return rec


WRITE_CALLS = [
    ("comment_pr", (1, "comment body")),
    ("create_tags_of_pr", (1, "ci_processing")),
    ("replace_all_tags_of_pr", (1, "ci_successful")),
    ("delete_tag_of_pr", (1, "ci_failed")),
]


@pytest.mark.parametrize("method,args", WRITE_CALLS)
def test_write_methods_use_write_token(recorder, method, args):
    proxy = GithubProxy("owner", "repo", read_token="read-token", write_token="write-token")

    getattr(proxy, method)(*args)

    assert len(recorder.calls) == 1
    assert recorder.calls[0]["data"].headers == {
        "Authorization": "Bearer write-token",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
    }


def test_write_method_fails_fast_without_write_token(recorder):
    proxy = GithubProxy("owner", "repo", read_token="read-token")

    with pytest.raises(RuntimeError, match="write token not provided"):
        proxy.comment_pr(1, "comment body")

    assert recorder.calls == []


def test_legacy_positional_token_works_for_write(recorder):
    proxy = GithubProxy("owner", "repo", "legacy-token")

    proxy.comment_pr(1, "comment body")

    assert recorder.calls[0]["data"].headers["Authorization"] == "Bearer legacy-token"


def test_split_tokens_take_precedence_over_legacy_token(recorder):
    proxy = GithubProxy(
        "owner", "repo", "legacy-token", read_token="read-token", write_token="write-token"
    )

    proxy.comment_pr(1, "comment body")

    assert recorder.calls[0]["data"].headers["Authorization"] == "Bearer write-token"


def test_requests_do_not_carry_access_token(recorder):
    proxy = GithubProxy("owner", "repo", write_token="write-token")

    proxy.comment_pr(1, "comment body")
    proxy.create_tags_of_pr(1, "ci_processing")
    proxy.replace_all_tags_of_pr(1, "ci_successful")
    proxy.delete_tag_of_pr(1, "ci_failed")

    assert len(recorder.calls) == 4
    for call in recorder.calls:
        assert "access_token" not in call["url"]
        assert "access_token" not in json.dumps(call["data"].body, ensure_ascii=False)
