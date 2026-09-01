import os
import re
import threading
import time
from contextlib import ExitStack, contextmanager
from unittest import mock

from src.ac.acl.wittyhub_audit.check_wittyhub_audit import CheckWittyhubAudit
from src.ac.framework.ac_result import SUCCESS, WARNING


def _make_check(tmp_path, conf=None):
    return CheckWittyhubAudit(str(tmp_path), "openEuler-skills", conf=conf or {})


def _run(check, diff_files=None):
    if diff_files is not None:
        check.get_pr_changed_files = mock.Mock(return_value=diff_files)
    return check(common_args={"community": "openeuler", "pr_num": "1", "access_token": "at"})


def _skill_yaml(tmp_path, relative, content):
    path = tmp_path / "openEuler-skills" / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _mock_async_audit(mock_post, mock_get, result, build_number=42, poll_pending=0):
    """Mock 异步审计流程：POST 触发返回 build_number，GET 轮询 pending N 次后返回结果."""
    mock_post.return_value = mock.Mock(
        status_code=200,
        json=lambda: {"details": {"skillspector_build_number": build_number}},
    )
    polled = {"count": 0}

    def _get_side_effect(*args, **kwargs):
        if polled["count"] < poll_pending:
            polled["count"] += 1
            return mock.Mock(status_code=200, json=lambda: {"status": "pending", "build_number": build_number})
        return mock.Mock(status_code=200, json=lambda: result)

    mock_get.side_effect = _get_side_effect


@contextmanager
def _audit_ctx(check, discover=None):
    """组合门禁审计测试通用 mock：env + requests.post/get + GitcodeProxy + discover.

    discover=None 表示 _discover_repo_skills 返回 None（回退整仓库审计），传列表则
    展开逐 skill；返回 (mock_post, mock_get, mock_gp)。
    """
    with ExitStack() as stack:
        stack.enter_context(
            mock.patch.dict(os.environ, {"WITTYHUB_API_URL": "http://w:8080", "WITTYHUB_ADMIN_TOKEN": "t"})
        )
        mock_post = stack.enter_context(mock.patch("src.ac.acl.wittyhub_audit.check_wittyhub_audit.requests.post"))
        mock_get = stack.enter_context(mock.patch("src.ac.acl.wittyhub_audit.check_wittyhub_audit.requests.get"))
        mock_gp = stack.enter_context(mock.patch("src.proxy.gitcode_proxy.GitcodeProxy"))
        stack.enter_context(mock.patch.object(check, "_discover_repo_skills", return_value=discover))
        yield mock_post, mock_get, mock_gp


def _assert_payload(mock_post, payload):
    """断言门禁触发请求携带的 payload（repo_url/skill_url + async_mode）. """
    _, kwargs = mock_post.call_args
    assert kwargs["json"] == payload


def _assert_skill_url(urls, skill_url):
    """断言多次触发列表中包含指定 skill_url 的审计请求."""
    assert {"skill_url": skill_url, "async_mode": True} in urls


def _mock_pr_patch(mock_gp, filename, diff):
    # GitCode pulls/{pr}/files 的 patch 字段为 {"diff": "<unified diff>"}
    mock_gp.return_value.get_pr_files.return_value = [
        {"filename": filename, "patch": {"diff": diff}}
    ]


def test_no_skill_change_is_success(tmp_path):
    check = _make_check(tmp_path)
    with mock.patch.dict(os.environ, {"WITTYHUB_API_URL": "http://w:8080", "WITTYHUB_ADMIN_TOKEN": "t"}):
        result = _run(check, diff_files=["README.md"])
    assert result == SUCCESS


def test_repo_high_warns(tmp_path):
    """高风险不阻断，门禁返回 WARNING（评论提示「谨慎合入」，人工确认）."""
    _skill_yaml(tmp_path, "community/sig-x/skill.yaml", "skill_repos:\n- url: https://gitcode.com/openeuler/foo\n")
    check = _make_check(tmp_path)
    with _audit_ctx(check) as (mock_post, mock_get, _gp):
        _mock_async_audit(mock_post, mock_get, {"status": "done", "risk_level": "high", "risk_score": 65})
        result = _run(check, diff_files=["community/sig-x/skill.yaml"])
    assert result == WARNING
    assert any("high" in detail for detail in result.details)
    _assert_payload(mock_post, {"repo_url": "https://gitcode.com/openeuler/foo", "async_mode": True})
    mock_get.assert_called()


def test_skill_url_medium_warns(tmp_path):
    _skill_yaml(
        tmp_path,
        "enterprise/org/skill.yaml",
        "skills:\n- skill_name: x\n  skill_url: https://gitcode.com/openeuler/foo/blob/main/skills/x/SKILL.md\n",
    )
    check = _make_check(tmp_path)
    with _audit_ctx(check) as (mock_post, mock_get, _gp):
        _mock_async_audit(mock_post, mock_get, {"status": "done", "risk_level": "medium", "risk_score": 35})
        result = _run(check, diff_files=["enterprise/org/skill.yaml"])
    assert result == WARNING
    _assert_payload(mock_post, {
        "skill_url": "https://gitcode.com/openeuler/foo/blob/main/skills/x/SKILL.md", "async_mode": True,
    })


def test_uploaded_skill_md_uses_pr_head(tmp_path):
    check = _make_check(tmp_path)
    with _audit_ctx(check) as (mock_post, mock_get, mock_gp):
        mock_gp.return_value.get_pr_info.return_value = {
            "head": {"ref": "feature-x", "repo": {"html_url": "https://gitcode.com/forkowner/openEuler-skills"}}
        }
        _mock_async_audit(mock_post, mock_get, {"status": "done", "risk_level": "low", "risk_score": 10})
        result = _run(check, diff_files=["community/sig-x/my-skill/SKILL.md"])
    assert result == SUCCESS
    _assert_payload(mock_post, {
        "skill_url": "https://gitcode.com/forkowner/openEuler-skills/blob/feature-x/community/sig-x/my-skill/SKILL.md",
        "async_mode": True,
    })


def test_uploaded_skill_md_slash_branch_skipped(tmp_path):
    """PR 头分支含 '/' 时（如 feature/ai-skill），wittyhub 无法用 skill_url 精确审计
    上传的 SKILL.md；显式跳过并告警（WARNING），不静默、不拼出错误的审计 URL."""
    check = _make_check(tmp_path)
    with _audit_ctx(check) as (mock_post, _get, mock_gp):
        mock_gp.return_value.get_pr_info.return_value = {
            "head": {"ref": "feature/ai-skill", "repo": {"html_url": "https://gitcode.com/forkowner/openEuler-skills"}}
        }
        result = _run(check, diff_files=["community/sig-x/my-skill/SKILL.md"])
    assert result == WARNING
    mock_post.assert_not_called()  # 未触发任何审计
    assert any("审计失败" in d for d in result.details)


def test_trigger_one_slash_branch_isolation(tmp_path):
    """斜杠防护只作用于 pr_skill（PR 上传 SKILL.md + 斜杠 head_ref）场景；
    repo / skill 目标的斜杠分支审计不受影响，payload 正确构造."""
    check = _make_check(tmp_path)
    check._api_url = "http://w:8080"
    check._admin_token = "t"
    calls = []

    def _post(url, **kwargs):
        calls.append(kwargs.get("json"))
        return mock.Mock(status_code=200, json=lambda: {"details": {"skillspector_build_number": 7}})

    with mock.patch("src.ac.acl.wittyhub_audit.check_wittyhub_audit.requests.post", side_effect=_post):
        # 场景1: pr_skill + 斜杠 head_ref -> 防护触发，跳过且不发起审计
        t = {"type": "pr_skill", "url": "community/sig/x/SKILL.md",
             "head_url": "https://gitcode.com/o/r", "head_ref": "release/1.0"}
        assert check._trigger_one(t) is None
        assert len(calls) == 0

        # 场景2: pr_skill + 无斜杠 head_ref -> 正常审计，skill_url 拼接正确
        t = {"type": "pr_skill", "url": "community/sig/x/SKILL.md",
             "head_url": "https://gitcode.com/o/r", "head_ref": "master"}
        assert check._trigger_one(t) == 7
        assert calls[-1] == {
            "skill_url": "https://gitcode.com/o/r/blob/master/community/sig/x/SKILL.md",
            "async_mode": True,
        }

        # 场景3: repo + 斜杠 branch（skill_repos 斜杠分支回退整仓库）-> 不受 pr_skill 防护影响
        t = {"type": "repo", "url": "https://gitcode.com/openeuler/foo", "branch": "release/1.0"}
        assert check._trigger_one(t) == 7
        assert calls[-1] == {
            "repo_url": "https://gitcode.com/openeuler/foo",
            "branch": "release/1.0", "async_mode": True,
        }

        # 场景4: skill（skill.yaml 的 skill_url 带斜杠 ref）-> 原样透传
        t = {"type": "skill", "url": "https://gitcode.com/openeuler/foo/blob/release/1.0/skills/x/SKILL.md"}
        assert check._trigger_one(t) == 7
        assert calls[-1] == {
            "skill_url": "https://gitcode.com/openeuler/foo/blob/release/1.0/skills/x/SKILL.md",
            "async_mode": True,
        }


def test_audit_api_failure_warns(tmp_path):
    _skill_yaml(tmp_path, "community/sig-x/skill.yaml", "skill_repos:\n- url: https://gitcode.com/openeuler/foo\n")
    check = _make_check(tmp_path)
    with _audit_ctx(check) as (mock_post, _get, _gp):
        mock_post.return_value = mock.Mock(status_code=500, text="boom")
        result = _run(check, diff_files=["community/sig-x/skill.yaml"])
    assert result == WARNING
    assert any("审计失败" in detail for detail in result.details)


def test_unknown_risk_level_warns(tmp_path):
    """report 取不到时接口返回 risk_level=unknown，门禁不应静默放行，需告警."""
    _skill_yaml(tmp_path, "community/sig-x/skill.yaml", "skill_repos:\n- url: https://gitcode.com/openeuler/foo\n")
    check = _make_check(tmp_path)
    with _audit_ctx(check) as (mock_post, mock_get, _gp):
        _mock_async_audit(mock_post, mock_get, {"status": "done", "risk_level": "unknown", "risk_score": None})
        result = _run(check, diff_files=["community/sig-x/skill.yaml"])
    assert result == WARNING
    assert any("unknown" in detail for detail in result.details)


def test_polls_until_done(tmp_path):
    """轮询应持续到 status=done：先返回 pending，再返回最终结果."""
    _skill_yaml(tmp_path, "community/sig-x/skill.yaml", "skill_repos:\n- url: https://gitcode.com/openeuler/foo\n")
    check = _make_check(tmp_path, conf={"poll_interval": 0.01})
    with _audit_ctx(check) as (mock_post, mock_get, _gp):
        _mock_async_audit(
            mock_post, mock_get, {"status": "done", "risk_level": "high", "risk_score": 65}, poll_pending=2
        )
        result = _run(check, diff_files=["community/sig-x/skill.yaml"])
    assert result == WARNING
    assert mock_get.call_count >= 3  # 2 pending + 1 done


def test_poll_error_warns(tmp_path):
    """轮询返回 status=error 时按审计失败告警."""
    _skill_yaml(tmp_path, "community/sig-x/skill.yaml", "skill_repos:\n- url: https://gitcode.com/openeuler/foo\n")
    check = _make_check(tmp_path)
    with _audit_ctx(check) as (mock_post, mock_get, _gp):
        _mock_async_audit(mock_post, mock_get, {"status": "error", "error": "report fetch failed"})
        result = _run(check, diff_files=["community/sig-x/skill.yaml"])
    assert result == WARNING
    assert any("审计失败" in detail for detail in result.details)


def test_comment_uses_table_with_report_link(tmp_path):
    """评论需用表格展示每个 skill：名称、风险等级、风险分数、report.md 详情链接."""
    _skill_yaml(tmp_path, "community/sig-x/skill.yaml", "skill_repos:\n- url: https://gitcode.com/openeuler/foo\n")
    check = _make_check(tmp_path)
    mock_result = {
        "status": "done",
        "risk_level": "high",
        "risk_score": 65,
        "risk_signals": [
            {"severity": "high", "name": "Skillspector PROMPT_INJECTION", "description": "prompt injection 风险"},
        ],
        "details": {"skillspector_report_md": "# Skillspector Report\n\n- high: prompt injection"},
    }
    with _audit_ctx(check) as (mock_post, mock_get, mock_gp):
        _mock_async_audit(mock_post, mock_get, mock_result)
        result = _run(check, diff_files=["community/sig-x/skill.yaml"])
    assert result == WARNING

    comment_pr = mock_gp.return_value.comment_pr
    comment_pr.assert_called_once()
    body = comment_pr.call_args.args[1]
    assert "| skill 名称 | 风险等级 | 风险分数 | 详情链接 |" in body
    assert "| --- | --- | --- | --- |" in body
    # 回退为整仓库审计时 name 取仓库 URL；风险等级与前端一致（score 65 -> 中风险），黑色字体 + 橙色背景
    assert "| https://gitcode.com/openeuler/foo | " in body
    assert '<span style="color:#000000;background-color:#FF9800;">中风险</span>' in body
    # report 链接文本与下载文件名均为「skill 名称 + 安全审计报告.md」
    assert "[https://gitcode.com/openeuler/foo安全审计报告.md]" in body
    filename_enc = (
        "&filename=https%3A%2F%2Fgitcode.com%2Fopeneuler%2Ffoo"
        "%E5%AE%89%E5%85%A8%E5%AE%A1%E8%AE%A1%E6%8A%A5%E5%91%8A.md"
    )
    assert filename_enc in body
    assert "**结论: 谨慎合入（存在高风险 skill）**" in body


def test_comment_conclusion_above_table_sorted_by_score(tmp_path):
    """评论结论放在表格上方；表格按风险分数降序（无分数排最后）."""
    check = _make_check(tmp_path)
    check._api_url = "http://w:8080"
    check._admin_token = "t"
    check._community = "openeuler"
    check._pr_num = "1"
    audits = [
        {"name": "low-skill", "desc": "low", "risk_level": "low", "risk_score": 10, "build_number": 1},
        {"name": "high-skill", "desc": "high", "risk_level": "high", "risk_score": 65, "build_number": 2},
        {"name": "unknown-skill", "desc": "unknown", "risk_level": "unknown", "risk_score": None, "build_number": 3},
        {"name": "crit-skill", "desc": "crit", "risk_level": "critical", "risk_score": 90, "build_number": 4},
    ]
    with _audit_ctx(check) as (_post, _get, mock_gp):
        check._comment_summary(audits, [], block_hit=True, warn_hit=True)
    body = mock_gp.return_value.comment_pr.call_args.args[1]
    lines = body.splitlines()
    # 结论在表格表头上方
    conclusion_idx = next(i for i, l in enumerate(lines) if l.startswith("**结论"))
    header_idx = next(i for i, l in enumerate(lines) if l.startswith("| skill 名称"))
    assert conclusion_idx < header_idx
    # 表格行（含 report 详情链接）按风险分数降序；无分数（unknown，分数显示 -）排最后
    rows = [l for l in lines if l.startswith("| ") and "安全审计报告.md]" in l]
    numeric = [int(l.split("|")[3].strip()) for l in rows if l.split("|")[3].strip() != "-"]
    assert numeric == sorted(numeric, reverse=True)
    assert rows[-1].startswith("| unknown-skill")


def test_risk_label_matches_frontend(tmp_path):
    """风险等级中文标签与前端 getSecurityLevel 一致（按分数分档）."""
    check = _make_check(tmp_path)
    assert check._risk_label(None) == "未检测"
    assert check._risk_label(0) == "安全"
    assert check._risk_label(20) == "安全"
    assert check._risk_label(21) == "低风险"
    assert check._risk_label(50) == "低风险"
    assert check._risk_label(51) == "中风险"
    assert check._risk_label(80) == "中风险"
    assert check._risk_label(81) == "高风险"
    assert check._risk_label(100) == "高风险"


def test_risk_level_style_mapping(tmp_path):
    """风险等级背景色映射：安全/低风险/中风险/高风险 = 绿/黄/橙/红，未检测=灰."""
    check = _make_check(tmp_path)
    assert check.RISK_LEVEL_STYLE["安全"] == "#67C23A"
    assert check.RISK_LEVEL_STYLE["低风险"] == "#F7BA2A"
    assert check.RISK_LEVEL_STYLE["中风险"] == "#FF9800"
    assert check.RISK_LEVEL_STYLE["高风险"] == "#F56C6C"
    assert check.RISK_LEVEL_STYLE["未检测"] == "#909399"


def test_enterprise_and_personal_skill_yaml_collect_targets(tmp_path):
    """企业/个人渠道的 skill.yaml（organization/author 顶层字段 + github.com 域名）
    应能正确识别 skill_repos 与 skills 审计目标."""
    enterprise_yaml = (
        "organization: anthropics\n"
        "organization_info:\n"
        "  display_name: Anthropic\n"
        "  github_profile: https://github.com/anthropics\n"
        "author: []\n"
        "skill_repos:\n"
        "- url: https://github.com/anthropics/skills\n"
        "skills: []\n"
    )
    personal_yaml = (
        "author:\n"
        "  name: leon-wang2021\n"
        "skill_repos:\n"
        "- url: https://gitcode.com/leon-wang2021/aet\n"
        "skills:\n"
        "- skill_name: aet\n"
        "  skill_url: https://gitcode.com/leon-wang2021/aet/blob/main/skills/aet/SKILL.md\n"
    )
    _skill_yaml(tmp_path, "enterprise/anthropics/skill.yaml", enterprise_yaml)
    _skill_yaml(tmp_path, "personal/leon-wang2021/skill.yaml", personal_yaml)
    check = _make_check(tmp_path)
    with _audit_ctx(check) as (mock_post, mock_get, _gp):
        _mock_async_audit(mock_post, mock_get, {"status": "done", "risk_level": "low", "risk_score": 10})
        result = _run(check, diff_files=["enterprise/anthropics/skill.yaml", "personal/leon-wang2021/skill.yaml"])
    assert result == SUCCESS
    assert mock_post.call_count == 3  # enterprise repo + personal repo + personal skill
    urls = [call.kwargs["json"] for call in mock_post.call_args_list]
    assert {"repo_url": "https://github.com/anthropics/skills", "async_mode": True} in urls
    assert {"repo_url": "https://gitcode.com/leon-wang2021/aet", "async_mode": True} in urls
    _assert_skill_url(urls, "https://gitcode.com/leon-wang2021/aet/blob/main/skills/aet/SKILL.md")


def test_skill_url_only_change_scans_single_skill(tmp_path):
    """只改 skills[].skill_url 时，只扫单个 skill，不扫 skill_repos 对应整仓库."""
    _skill_yaml(
        tmp_path,
        "personal/leon-wang2021/skill.yaml",
        "author:\n"
        "  name: leon-wang2021\n"
        "skill_repos:\n"
        "- url: https://gitcode.com/leon-wang2021/aet\n"
        "skills:\n"
        "- skill_name: aet\n"
        "  skill_url: https://gitcode.com/leon-wang2021/aet/blob/main/skills/aet-analyzing-prd-innovation/SKILL.md\n",
    )
    check = _make_check(tmp_path)
    patch = (
        "@@ -6 +6 @@\n"
        "-  skill_url: https://gitcode.com/leon-wang2021/aet/blob/main/skills/aet/SKILL.md\n"
        "+  skill_url: https://gitcode.com/leon-wang2021/aet/blob/main/skills/aet-analyzing-prd-innovation/SKILL.md\n"
    )
    with _audit_ctx(check) as (mock_post, mock_get, mock_gp):
        _mock_pr_patch(mock_gp, "personal/leon-wang2021/skill.yaml", patch)
        _mock_async_audit(mock_post, mock_get, {"status": "done", "risk_level": "low", "risk_score": 10})
        result = _run(check, diff_files=["personal/leon-wang2021/skill.yaml"])
    assert result == SUCCESS
    assert mock_post.call_count == 1  # 只扫单个 skill
    _assert_payload(mock_post, {
        "skill_url": "https://gitcode.com/leon-wang2021/aet/blob/main/skills/aet-analyzing-prd-innovation/SKILL.md",
        "async_mode": True,
    })


def test_repo_url_only_change_scans_whole_repo(tmp_path):
    """只改 skill_repos[].url 时，只扫整仓库，不扫 skills[].skill_url."""
    _skill_yaml(
        tmp_path,
        "community/sig-x/skill.yaml",
        "skill_repos:\n"
        "- url: https://gitcode.com/openeuler/foo\n"
        "skills:\n"
        "- skill_name: x\n"
        "  skill_url: https://gitcode.com/openeuler/foo/blob/main/skills/x/SKILL.md\n",
    )
    check = _make_check(tmp_path)
    patch = (
        "@@ -3 +3 @@\n"
        "-- url: https://gitcode.com/openeuler/old\n"
        "+- url: https://gitcode.com/openeuler/foo\n"
    )
    with _audit_ctx(check) as (mock_post, mock_get, mock_gp):
        _mock_pr_patch(mock_gp, "community/sig-x/skill.yaml", patch)
        _mock_async_audit(mock_post, mock_get, {"status": "done", "risk_level": "low", "risk_score": 10})
        result = _run(check, diff_files=["community/sig-x/skill.yaml"])
    assert result == SUCCESS
    assert mock_post.call_count == 1  # 只扫整仓库
    _assert_payload(mock_post, {"repo_url": "https://gitcode.com/openeuler/foo", "async_mode": True})


def test_new_skill_yaml_scans_both_fields(tmp_path):
    """新登记 skill.yaml（全文件新增）时，两个字段都审计."""
    _skill_yaml(
        tmp_path,
        "personal/leon-wang2021/skill.yaml",
        "author:\n"
        "  name: leon-wang2021\n"
        "skill_repos:\n"
        "- url: https://gitcode.com/leon-wang2021/aet\n"
        "skills:\n"
        "- skill_name: aet\n"
        "  skill_url: https://gitcode.com/leon-wang2021/aet/blob/main/skills/aet/SKILL.md\n",
    )
    check = _make_check(tmp_path)
    patch = (
        "@@ -0,0 +1,7 @@\n"
        "+author:\n"
        "+  name: leon-wang2021\n"
        "+skill_repos:\n"
        "+- url: https://gitcode.com/leon-wang2021/aet\n"
        "+skills:\n"
        "+- skill_name: aet\n"
        "+  skill_url: https://gitcode.com/leon-wang2021/aet/blob/main/skills/aet/SKILL.md\n"
    )
    with _audit_ctx(check) as (mock_post, mock_get, mock_gp):
        _mock_pr_patch(mock_gp, "personal/leon-wang2021/skill.yaml", patch)
        _mock_async_audit(mock_post, mock_get, {"status": "done", "risk_level": "low", "risk_score": 10})
        result = _run(check, diff_files=["personal/leon-wang2021/skill.yaml"])
    assert result == SUCCESS
    assert mock_post.call_count == 2  # 整仓库 + 单个 skill
    urls = [call.kwargs["json"] for call in mock_post.call_args_list]
    assert {"repo_url": "https://gitcode.com/leon-wang2021/aet", "async_mode": True} in urls
    _assert_skill_url(urls, "https://gitcode.com/leon-wang2021/aet/blob/main/skills/aet/SKILL.md")


def test_enveloped_response_parsed(tmp_path):
    """兼容 wittyhub 的 {code, msg, data} 信封包装响应（trigger 与 poll 均需解包）."""
    _skill_yaml(tmp_path, "community/sig-x/skill.yaml", "skill_repos:\n- url: https://gitcode.com/openeuler/foo\n")
    check = _make_check(tmp_path)
    with _audit_ctx(check) as (mock_post, mock_get, _gp):
        mock_post.return_value = mock.Mock(
            status_code=200,
            json=lambda: {
                "code": 200, "msg": "ok",
                "data": {
                    "git_url": "https://gitcode.com/openeuler/foo", "ref": "main", "skill_path": "",
                    "risk_level": "unknown", "risk_score": None, "risk_signals": [],
                    "details": {"skillspector_build_number": 42, "skillspector_async": True},
                },
            },
        )
        mock_get.return_value = mock.Mock(
            status_code=200,
            json=lambda: {
                "code": 200, "msg": "ok",
                "data": {
                    "status": "done", "build_number": 42, "risk_level": "high",
                    "risk_score": 65, "risk_signals": [], "details": {},
                },
            },
        )
        result = _run(check, diff_files=["community/sig-x/skill.yaml"])
    assert result == WARNING
    assert any("high" in detail for detail in result.details)


def test_fields_changed_by_patch_only_skips_unrelated_lines():
    """_fields_changed_by_patch 只提取 skill_repos/url 与 skills/skill_url 的新增 URL.

    None 表示字段未被改动（不审计）；非空集合表示只审计这些具体 URL；
    空集合表示字段被改动但未定位到具体 URL（全量审计）。
    """
    check = CheckWittyhubAudit("", "openEuler-skills")
    assert check._fields_changed_by_patch(
        "@@ -1 +1 @@\n"
        "-  skill_url: https://old/SKILL.md\n"
        "+  skill_url: https://new/SKILL.md\n"
    ) == (None, {"https://new/SKILL.md"})
    assert check._fields_changed_by_patch(
        "@@ -1 +1 @@\n"
        "-- url: https://old\n"
        "+- url: https://new\n"
    ) == ({"https://new"}, None)
    assert check._fields_changed_by_patch(
        "@@ -1 +1 @@\n"
        "-  name: leon\n"
        "+  name: other\n"
    ) == (None, None)


def test_add_one_repo_url_only_scans_new_repo(tmp_path):
    """PR 只新增一个 skill_repos 条目时，只审计该新增仓库，不审计其他已有仓库."""
    _skill_yaml(
        tmp_path,
        "community/sig-intelligence/skill.yaml",
        "skill_repos:\n"
        "- url: https://gitcode.com/openeuler/witty-agents\n"
        "- url: https://gitcode.com/openeuler/wittyhub\n"
        "skills:\n"
        "- skill_name: witty-agents\n"
        "  skill_url: https://gitcode.com/openeuler/witty-agents/blob/master/skills/witty-agents/SKILL.md\n"
        "- skill_name: wittyhub\n"
        "  skill_url: https://gitcode.com/openeuler/wittyhub/blob/master/skills/wittyhub/SKILL.md\n",
    )
    check = _make_check(tmp_path)
    patch = (
        "@@ -10 +10 @@\n"
        "  - url: https://gitcode.com/openeuler/wittyhub\n"
        "+  - url: https://gitcode.com/openeuler/witty-agents\n"
    )
    with _audit_ctx(check) as (mock_post, mock_get, mock_gp):
        _mock_pr_patch(mock_gp, "community/sig-intelligence/skill.yaml", patch)
        _mock_async_audit(mock_post, mock_get, {"status": "done", "risk_level": "low", "risk_score": 10})
        result = _run(check, diff_files=["community/sig-intelligence/skill.yaml"])
    assert result == SUCCESS
    assert mock_post.call_count == 1  # 只扫新增的 witty-agents 仓库
    _assert_payload(mock_post, {"repo_url": "https://gitcode.com/openeuler/witty-agents", "async_mode": True})


def test_added_url_missing_in_content_still_audited(tmp_path):
    """patch 新增的 URL 在内容中匹配不到（格式不一致/内容为 base）时，
    仍应直接审计该 URL，避免静默漏扫."""
    _skill_yaml(
        tmp_path,
        "community/sig-x/skill.yaml",
        "skill_repos:\n"
        "- url: https://gitcode.com/openeuler/existing\n",
    )
    check = _make_check(tmp_path)
    patch = (
        "@@ -10 +10 @@\n"
        "  - url: https://gitcode.com/openeuler/existing\n"
        "+  - url: https://gitcode.com/openeuler/new-repo  # 新增登记\n"
    )
    with _audit_ctx(check) as (mock_post, mock_get, mock_gp):
        _mock_pr_patch(mock_gp, "community/sig-x/skill.yaml", patch)
        _mock_async_audit(mock_post, mock_get, {"status": "done", "risk_level": "low", "risk_score": 10})
        result = _run(check, diff_files=["community/sig-x/skill.yaml"])
    assert result == SUCCESS
    assert mock_post.call_count == 1
    _assert_payload(mock_post, {"repo_url": "https://gitcode.com/openeuler/new-repo", "async_mode": True})


def test_repo_expands_to_multiple_skills(tmp_path):
    """skill 仓库按 skillcrawler 逻辑展开为逐 skill 审计：每个 skill 一次审计、
    各自返回结果，评论表格每行一个 skill 并附 report.md 详情链接."""
    _skill_yaml(
        tmp_path,
        "community/sig-intelligence/skill.yaml",
        "skill_repos:\n"
        "- url: https://gitcode.com/openeuler/witty-agents\n",
    )
    check = _make_check(tmp_path)
    patch = (
        "@@ -3 +3 @@\n"
        "  - url: https://gitcode.com/openeuler/other\n"
        "+  - url: https://gitcode.com/openeuler/witty-agents\n"
    )
    discovered = [
        {
            "name": "witty-agents",
            "skill_url": "https://gitcode.com/openeuler/witty-agents/blob/master/skills/witty-agents/SKILL.md",
        },
        {
            "name": "wittyhub",
            "skill_url": "https://gitcode.com/openeuler/wittyhub/blob/master/skills/wittyhub/SKILL.md",
        },
    ]
    with _audit_ctx(check, discovered) as (mock_post, mock_get, mock_gp):
        _mock_pr_patch(mock_gp, "community/sig-intelligence/skill.yaml", patch)
        _mock_async_audit(mock_post, mock_get, {"status": "done", "risk_level": "low", "risk_score": 10})
        result = _run(check, diff_files=["community/sig-intelligence/skill.yaml"])
    assert result == SUCCESS
    assert mock_post.call_count == 2  # 1 个新增仓库发现出 2 个 skill -> 2 次独立审计
    urls = [call.kwargs["json"] for call in mock_post.call_args_list]
    _assert_skill_url(urls, "https://gitcode.com/openeuler/witty-agents/blob/master/skills/witty-agents/SKILL.md")
    _assert_skill_url(urls, "https://gitcode.com/openeuler/wittyhub/blob/master/skills/wittyhub/SKILL.md")

    comment_pr = mock_gp.return_value.comment_pr
    comment_pr.assert_called_once()
    body = comment_pr.call_args.args[1]
    # 表格中每个 skill 一行，含名称、风险等级（与前端一致，score 10 -> 安全，
    # 黑色字体 + 绿色背景标签）、风险分数、report 下载链接（skill 名 + 安全审计报告.md）
    assert "| skill 名称 | 风险等级 | 风险分数 | 详情链接 |" in body
    safe_span = '<span style="color:#000000;background-color:#67C23A;">安全</span>'
    assert "| witty-agents | " + safe_span + " | 10 |" in body
    assert "| wittyhub | " + safe_span + " | 10 |" in body
    assert body.count("[witty-agents安全审计报告.md]") == 1
    assert body.count("[wittyhub安全审计报告.md]") == 1
    assert body.count("/report?build_number=42&filename=") == 2


def test_repo_discover_failure_falls_back_to_whole_repo(tmp_path):
    """仓库 skill 发现失败（克隆/解析异常）时回退为整仓库审计，保证不静默通过."""
    _skill_yaml(tmp_path, "community/sig-x/skill.yaml", "skill_repos:\n- url: https://gitcode.com/openeuler/foo\n")
    check = _make_check(tmp_path)
    with _audit_ctx(check, None) as (mock_post, mock_get, _gp):
        _mock_async_audit(mock_post, mock_get, {"status": "done", "risk_level": "medium", "risk_score": 35})
        result = _run(check, diff_files=["community/sig-x/skill.yaml"])
    assert result == WARNING
    assert mock_post.call_count == 1  # 回退为 1 次整仓库审计
    _assert_payload(mock_post, {"repo_url": "https://gitcode.com/openeuler/foo", "async_mode": True})


def test_validate_git_url_allows_public_hosts(tmp_path):
    """URL 白名单校验：允许公开代码托管域名，拒绝内网/非白名单/带凭据/无路径地址."""
    check = _make_check(tmp_path)
    assert check._validate_git_url("https://gitcode.com/openeuler/witty-agents")
    assert check._validate_git_url("https://github.com/anthropics/skills.git")
    assert check._validate_git_url("git@github.com:anthropics/skills")
    assert check._validate_git_url("https://gitcode.com/openeuler/witty-agents/")
    # 无仓库路径
    assert not check._validate_git_url("https://gitcode.com")
    assert not check._validate_git_url("https://gitcode.com/")
    # 非白名单域名
    assert not check._validate_git_url("https://evil.example.com/org/repo")
    # 私网/环回地址（SSRF 防护）
    assert not check._validate_git_url("http://192.168.1.1/org/repo")
    assert not check._validate_git_url("http://127.0.0.1:8080/org/repo")
    assert not check._validate_git_url("http://10.0.0.1/org/repo")
    # 非标准端口
    assert not check._validate_git_url("https://github.com:8443/org/repo")
    # 携带凭据 / 片段
    assert not check._validate_git_url("https://user:pass@github.com/org/repo")
    assert not check._validate_git_url("https://github.com/org/repo#frag")
    # 非法协议
    assert not check._validate_git_url("file:///etc/passwd")
    assert not check._validate_git_url("ftp://github.com/org/repo")


def test_validate_git_url_aligned_with_wittyhub(tmp_path):
    """URL 白名单校验与 wittyhub validate_git_url 对齐：
    控制字符拒绝、路径先 unquote 再校验、ssh 仅拒密码（用户名允许）."""
    check = _make_check(tmp_path)
    # ssh:// 形式允许用户名（与 wittyhub 一致），仅拒绝密码
    assert check._validate_git_url("ssh://git@github.com/org/repo")
    assert not check._validate_git_url("ssh://git:pass@github.com/org/repo")
    # http/https/git 拒绝任何凭据
    assert not check._validate_git_url("https://user@github.com/org/repo")
    assert not check._validate_git_url("git://git@github.com/org/repo")
    # 控制字符拒绝（防止日志/命令污染）
    assert not check._validate_git_url("https://gitcode.com/openeuler/foo\nbar")
    # 路径先 unquote 再校验：%2e%2e（..）与 .. 均拒绝
    assert not check._validate_git_url("https://gitcode.com/openeuler/%2e%2e/foo")
    assert not check._validate_git_url("https://gitcode.com/openeuler/../foo")


def test_discover_slash_branch_falls_back_to_whole_repo(tmp_path):
    """分支名含 '/'（如 release/2.0）时，wittyhub 无法解析逐 skill blob URL
    （owner/repo/blob/<ref>/<path>，ref 含 / 会被拆错），应回退整仓库审计；
    整仓库审计把 branch 原样传 git，可正确处理斜杠分支."""
    check = _make_check(tmp_path)
    with (
        mock.patch("src.ac.acl.wittyhub_audit.check_wittyhub_audit.subprocess.run") as mock_run,
        mock.patch.object(check, "_git_checked_out_branch", return_value="release/2.0"),
    ):
        mock_run.return_value = mock.Mock(returncode=0, stderr="")
        discovered = check._discover_repo_skills("https://gitcode.com/openeuler/foo", "")
    assert discovered is None  # 回退信号：_repo_targets 将转整仓库审计
    mock_run.assert_called_once()  # 只发生了一次 clone


def test_discover_rejects_non_whitelisted_url(tmp_path):
    """内网/非白名单 URL 不应被 git clone（SSRF 防护），门禁回退整仓库审计."""
    _skill_yaml(tmp_path, "community/sig-x/skill.yaml", "skill_repos:\n- url: http://192.168.1.1/repo\n")
    check = _make_check(tmp_path)
    with (
        mock.patch.dict(os.environ, {"WITTYHUB_API_URL": "http://w:8080", "WITTYHUB_ADMIN_TOKEN": "t"}),
        mock.patch("src.ac.acl.wittyhub_audit.check_wittyhub_audit.requests.post") as mock_post,
        mock.patch("src.ac.acl.wittyhub_audit.check_wittyhub_audit.requests.get") as mock_get,
        mock.patch("src.ac.acl.wittyhub_audit.check_wittyhub_audit.subprocess.run") as mock_run,
        mock.patch("src.proxy.gitcode_proxy.GitcodeProxy"),
    ):
        _mock_async_audit(mock_post, mock_get, {"status": "done", "risk_level": "low", "risk_score": 10})
        result = _run(check, diff_files=["community/sig-x/skill.yaml"])
    assert mock_run.call_count == 0  # 未触发 git clone（SSRF 拦截），回退为 1 次整仓库审计
    assert mock_post.call_count == 1
    _assert_payload(mock_post, {"repo_url": "http://192.168.1.1/repo", "async_mode": True})


def test_two_phase_triggers_all_before_polling(tmp_path):
    """两阶段执行：所有目标先触发（POST）完毕，才开始轮询（GET），
    让 Jenkins 多 executor 并行跑各 skill 扫描."""
    _skill_yaml(
        tmp_path,
        "community/sig-x/skill.yaml",
        "skill_repos:\n"
        "- url: https://gitcode.com/openeuler/foo\n"
        "- url: https://gitcode.com/openeuler/bar\n",
    )
    check = _make_check(tmp_path, conf={"poll_interval": 0.01})
    order = []

    def _post_side_effect(*args, **kwargs):
        order.append("post")
        return mock.Mock(status_code=200, json=lambda: {"details": {"skillspector_build_number": 42}})

    def _get_side_effect(*args, **kwargs):
        order.append("get")
        return mock.Mock(status_code=200, json=lambda: {"status": "done", "risk_level": "low", "risk_score": 10})

    with _audit_ctx(check) as (mock_post, mock_get, _gp):
        mock_post.side_effect = _post_side_effect
        mock_get.side_effect = _get_side_effect
        result = _run(check, diff_files=["community/sig-x/skill.yaml"])
    assert result == SUCCESS
    # 2 个仓库目标：先 2 次 POST 触发，再 2 次 GET 轮询，顺序为 post,post,get,get
    first_get = order.index("get")
    assert order[:first_get] == ["post", "post"]
    assert order[first_get:] == ["get", "get"]


def test_trigger_phase_runs_in_parallel(tmp_path):
    """触发阶段真正并行：多个目标的 audit-by-url POST 应同时并发发出，
    而不是串行逐个等待（Jenkins 队列解析 build_number 是慢操作）."""
    _skill_yaml(
        tmp_path,
        "community/sig-x/skill.yaml",
        "skill_repos:\n"
        "- url: https://gitcode.com/openeuler/foo\n"
        "- url: https://gitcode.com/openeuler/bar\n"
        "- url: https://gitcode.com/openeuler/baz\n",
    )
    check = _make_check(tmp_path, conf={"poll_interval": 0.01})
    state = {"in_flight": 0, "max_in_flight": 0}
    lock = threading.Lock()

    def _post_side_effect(*args, **kwargs):
        # 模拟触发耗时：让并发窗口可见，统计同一时刻在途的 POST 数
        with lock:
            state["in_flight"] += 1
            state["max_in_flight"] = max(state["max_in_flight"], state["in_flight"])
        time.sleep(0.05)
        with lock:
            state["in_flight"] -= 1
        return mock.Mock(status_code=200, json=lambda: {"details": {"skillspector_build_number": 42}})

    def _get_side_effect(*args, **kwargs):
        return mock.Mock(status_code=200, json=lambda: {"status": "done", "risk_level": "low", "risk_score": 10})

    with _audit_ctx(check) as (mock_post, mock_get, _gp):
        mock_post.side_effect = _post_side_effect
        mock_get.side_effect = _get_side_effect
        result = _run(check, diff_files=["community/sig-x/skill.yaml"])
    assert result == SUCCESS
    assert state["max_in_flight"] >= 2  # 3 个仓库目标并发触发，在途 POST 数应 >= 2


def test_trigger_exception_preserves_target(tmp_path):
    """触发阶段某目标抛异常时，failed_details 应保留该目标信息（不丢失目标名），
    且不影响其他目标的正常审计."""
    _skill_yaml(
        tmp_path,
        "community/sig-x/skill.yaml",
        "skill_repos:\n"
        "- url: https://gitcode.com/openeuler/foo\n"
        "- url: https://gitcode.com/openeuler/bar\n",
    )
    check = _make_check(tmp_path, conf={"poll_interval": 0.01})
    real_trigger = check._trigger_one

    def _fake_trigger(target):
        if target.get("url") == "https://gitcode.com/openeuler/foo":
            raise RuntimeError("boom")
        return real_trigger(target)

    with _audit_ctx(check) as (mock_post, mock_get, _gp):
        with mock.patch.object(check, "_trigger_one", side_effect=_fake_trigger):
            _mock_async_audit(mock_post, mock_get, {"status": "done", "risk_level": "low", "risk_score": 10})
            result = _run(check, diff_files=["community/sig-x/skill.yaml"])
    assert result == WARNING
    # foo 触发异常 -> failed_details 保留目标描述（含 foo 的仓库名）
    assert any("foo" in d and "审计失败" in d for d in result.details)
    # bar 仍正常触发并审计
    assert mock_post.call_count == 1
    _assert_payload(mock_post, {"repo_url": "https://gitcode.com/openeuler/bar", "async_mode": True})


def test_trigger_concurrency_keeps_build_target_binding(tmp_path):
    """并发触发下 build_number 与 target 的绑定不丢失：每个审计结果的风险数据
    来自其自身 build_number，不会串到别的 skill（结果顺序打乱但归属正确）."""
    _skill_yaml(
        tmp_path,
        "community/sig-x/skill.yaml",
        "skill_repos:\n"
        "- url: https://gitcode.com/openeuler/foo\n"
        "- url: https://gitcode.com/openeuler/bar\n",
    )
    check = _make_check(tmp_path, conf={"poll_interval": 0.01})

    def _post_side_effect(url, **kwargs):
        # foo -> build 10（high），bar -> build 20（low）
        repo_url = kwargs["json"].get("repo_url", "")
        bn = 10 if repo_url.endswith("/foo") else 20
        return mock.Mock(status_code=200, json=lambda: {"details": {"skillspector_build_number": bn}})

    def _get_side_effect(url, **kwargs):
        bn = int(re.search(r"build_number=(\d+)", url).group(1))
        if bn == 10:
            return mock.Mock(status_code=200, json=lambda: {"status": "done", "risk_level": "high", "risk_score": 65})
        return mock.Mock(status_code=200, json=lambda: {"status": "done", "risk_level": "low", "risk_score": 10})

    with _audit_ctx(check) as (mock_post, mock_get, _gp):
        mock_post.side_effect = _post_side_effect
        mock_get.side_effect = _get_side_effect
        result = _run(check, diff_files=["community/sig-x/skill.yaml"])
    assert result == WARNING
    # 各自结果与自身 build/target 绑定：foo 行 high，bar 行 low（不串）
    foo_line = next(d for d in result.details if "foo" in d)
    bar_line = next(d for d in result.details if "bar" in d)
    assert "risk_level=high" in foo_line
    assert "risk_level=low" in bar_line


def test_exceed_max_targets_skips_audit(tmp_path):
    """目标数超过 MAX_TARGETS（100）时，跳过自动化审计，评论提示人工审核，门禁 WARNING 不触发审计."""
    repos = "".join("- url: https://gitcode.com/openeuler/repo{}\n".format(i) for i in range(101))
    _skill_yaml(tmp_path, "community/sig-x/skill.yaml", "skill_repos:\n" + repos)
    check = _make_check(tmp_path)
    with _audit_ctx(check) as (mock_post, _get, mock_gp):
        result = _run(check, diff_files=["community/sig-x/skill.yaml"])
    assert result == WARNING
    mock_post.assert_not_called()  # 未触发任何审计
    body = mock_gp.return_value.comment_pr.call_args.args[1]
    assert "SkillHub 安全审计门禁" in body
    assert "不做安全审计" in body
    assert "人工审核" in body


def test_poll_total_timeout_marks_pending_failed(tmp_path):
    """轮询总超时（默认 20 分钟）到点后，仍为 pending 的目标按审计失败告警."""
    _skill_yaml(tmp_path, "community/sig-x/skill.yaml", "skill_repos:\n- url: https://gitcode.com/openeuler/foo\n")
    check = _make_check(tmp_path, conf={"poll_timeout": 0.2, "poll_interval": 0.01})
    with _audit_ctx(check) as (mock_post, mock_get, _gp):
        _mock_async_audit(mock_post, mock_get, {"status": "pending", "build_number": 42})
        result = _run(check, diff_files=["community/sig-x/skill.yaml"])
    assert result == WARNING
    assert any("审计失败" in d for d in result.details)
