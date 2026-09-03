# -*- encoding=utf-8 -*-
# ***********************************************************************************
# Copyright (c) Huawei Technologies Co., 2026. All rights reserved.
# [openeuler-jenkins] is licensed under the Mulan PSL v2.
# You can use this software according to the terms and conditions of the Mulan PSL v2.
# You may obtain a copy of Mulan PSL v2 at:
#          http://license.coscl.org.cn/MulanPSL2
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND,
# EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT,
# MERCHANTABILITY OR FIT FOR A PARTICULAR PURPOSE.
# See the Mulan PSL v2 for more details.
# Author:
# Create: 2026-07-06
# Description: GitCode Action entry for access control
# ***********************************************************************************
"""
GitCode Action 门禁入口脚本

与 Jenkins 入口（ac.py __main__）对应，但从环境变量获取 PR 上下文，
复用 AC 框架执行检查项，最后将结果以评论形式反馈到 PR。

环境变量约定（由 workflow 注入）：
    ACTION_PR_NUMBER:       PR 编号
    ACTION_REPO:            仓库名（如 openEuler-repos）
    ACTION_OWNER:           PR 目标仓实际 owner（API/clone 用；community 由映射表推导）
    ACTION_TARGET_BRANCH:   PR 目标分支
    ACTION_TOKEN:           GitCode API token
    ACTION_WORKSPACE:       工作目录（已 checkout 的仓库根目录）
    ACTION_PR_URL:          PR 链接（可选，用于评论展示）
    ACTION_COMMITTER:       PR 提交者（可选）
"""

import datetime
import glob
import logging
import os
import shutil
import sys
import warnings
from html import escape as html_escape

from src.ac.common.ai_summary import AISummarizer, load_ai_config
from src.ac.framework.ac import AC
from src.action_context import MissingActionEnvError, load_action_context, setup_action_logging
from src.proxy.git_proxy import GitProxy
from src.proxy.gitcode_proxy import GitcodeProxy
from src.proxy.llm_proxy import LLMProxy
from src.utils.dist_dataset import DistDataset

logger = logging.getLogger("ac")


def _build_pr_comment(ac_instance, pr_number, pipeline_url=None, run_number=None):
    """
    根据 AC 检查结果构造 PR 评论内容（HTML 表格形式，与 Jenkins 评论风格保持一致）
    """
    results = ac_instance._ac_check_result  # pylint: disable=protected-access
    if not results:
        return "门禁检查完成，未执行任何检查项。"

    # 状态值 → (emoji, hint) 与 ACResult 保持一致
    status_map = {
        0: ("&#9989;", "SUCCESS"),
        1: ("&#9888;", "WARNING"),
        2: ("&#10060;", "FAILED"),
        3: (":ballot_box_with_check:", "EXCLUDE"),
    }

    lines = [
        "<table>",
        "<tr><th colspan=2>Check Name</th> <th>Build Result</th> <th>详情</th> <th>Build Details</th></tr>",
    ]

    total = len(results)
    build_label = (
        "#{}".format(html_escape(str(run_number)))
        if run_number
        else "#{}".format(html_escape(str(pr_number)))
    )
    for index, item in enumerate(results):
        name = item.get("name", "")
        result_val = item.get("result", 2)
        emoji, hint = status_map.get(result_val, ("&#10060;", "FAILED"))

        # 详情列：WARNING/FAILED 展示 details；SUCCESS/EXCLUDE 留空
        detail_display = ""
        if result_val in (1, 2) and item.get("details"):
            detail_display = "<br/>".join(
                ["&#8226; " + html_escape(str(d)) for d in item["details"]]
            )

        if index == 0:
            # 第一行带 rowspan，Build Details 列放流水线链接
            if pipeline_url:
                build_details_cell = '<td rowspan={}><a href="{}">{}</a></td>'.format(
                    total, html_escape(pipeline_url), build_label
                )
            else:
                build_details_cell = "<td rowspan={}></td>".format(total)
            lines.append(
                "<tr><td colspan=2>{}</td> <td>{}<strong>{}</strong></td> <td>{}</td> {}</tr>".format(
                    html_escape(name), emoji, hint, detail_display, build_details_cell
                )
            )
        else:
            lines.append(
                "<tr><td colspan=2>{}</td> <td>{}<strong>{}</strong></td> <td>{}</td></tr>".format(
                    html_escape(name), emoji, hint, detail_display
                )
            )

    lines.append("</table>")

    return "\n".join(lines)


def _comment_ai_summary(gitcode_proxy, ac_instance, pr_number, repo, target_branch):
    """
    AI 智能摘要：调用 LLM 对门禁结果生成自然语言分析，作为独立评论发布。
    仅在存在失败或告警项时触发；任何异常只记录 warning 日志，不影响门禁主流程。

    与 src/build/gitee_comment.py:_comment_ai_summary 保持一致（Action 入口版本）。

    :param gitcode_proxy: GitcodeProxy 实例
    :param ac_instance: AC 实例
    :param pr_number: PR 编号
    :param repo: 仓库名
    :param target_branch: 目标分支
    """
    try:
        acl = ac_instance._ac_check_result  # pylint: disable=protected-access
        if not acl:
            logger.info("[AI] acl is empty, skip ai summary")
            return

        # 有失败或警告项时才需要 AI 摘要（SUCCESS=0, EXCLUDE=3 视为通过）
        has_issues = any(item.get("result", 0) in (1, 2) for item in acl)
        if not has_issues:
            logger.info("[AI] all checks passed or excluded, skip ai summary")
            return

        logger.info("[AI] checks not all passed, preparing ai summary")

        config = load_ai_config()
        if not config.get("enabled"):
            logger.info("[AI] ai summary is disabled in config, skip")
            return

        llm = LLMProxy(**config["llm"])
        summarizer = AISummarizer(llm)

        pr_context = {
            "repo": repo,
            "branch": target_branch,
        }

        logger.info("[AI] calling LLM for ai summary")
        success, summary = summarizer.summarize(acl, pr_context)
        if success and summary:
            ai_comment = "**PR门禁 AI 智能分析（仅供参考）**\n\n" + summary
            logger.info("[AI] ai summary generated, posting comment")
            gitcode_proxy.comment_pr(pr_number, ai_comment)
        else:
            logger.warning("[AI] LLM call failed or returned empty, skip comment")

    except Exception as e:
        logger.warning("[AI] AI summary failed (non-critical): %s", e)


# 正式组织（src-openeuler / openeuler）直接命中；测试/fork 仓需在此登记映射，
# 未列出的 owner 一律归入 src-openeuler（与 Jenkins 时代 AC 类内置归一化行为一致）
# 当前字典的内容仅测试期间使用，后续可清空为空字典
_COMMUNITY_MAPPING = {
    "ComputingActionTest": {
        "iSulad": "openeuler",
        "default": "src-openeuler",
    },
}


def _normalize_community(owner, repo):
    """
    将仓库实际 owner 映射为 AC 框架的 community（检查项配置归属）。

    Jenkins 时代仓库直接位于 src-openeuler/openeuler 组织下，owner == community；
    Action 场景仓库可能 fork 到个人/测试组织，需按映射表归一化。

    :param owner: 仓库实际 owner（API 调用用）
    :param repo: 仓库名
    :return: community（src-openeuler / openeuler）
    """
    if owner in ("src-openeuler", "openeuler"):
        return owner
    owner_mapping = _COMMUNITY_MAPPING.get(owner)
    if isinstance(owner_mapping, dict):
        community = owner_mapping.get(repo) or owner_mapping.get("default", "src-openeuler")
    else:
        community = "src-openeuler"
    logger.info("owner %s mapped to community %s (repo=%s)", owner, community, repo)
    return community


def _upload_support_arch(base_dir):
    """
    传递 check_spec 生成的 support_arch/spec_list 文件给 build 门禁。

    对应 Jenkins trigger.sh extra_work() 的上传职责（GitCode Action 版）：
    check_spec 解析 spec 时顺便提取 ExclusiveArch，生成 support_arch_{spec}
    与 spec_list 本地文件；build 门禁（A-guard ci-guard.sh）读取后用于构建
    决策（跳过不支持的架构）与构建结果修正。

    传递通道（唯一）：stage 到 ACTION_WORKSPACE，随 ci.yml 的 ac-result artifact
    上传；build job 下载制品还原到构建 workspace

    :param base_dir: 产物目录（入口启动时的进程 CWD；显式传入而非依赖当前 CWD，
                     规避检查项 os.chdir 未恢复导致的错位 glob）
    """
    workspace = os.environ.get("ACTION_WORKSPACE", "")
    if not workspace:
        logger.warning("[support_arch] ACTION_WORKSPACE 未配置, 跳过 artifact 通道 stage")

    # check_spec 产物以相对路径写在进程当前目录（base_dir），这里用绝对路径显式定位
    support_files = [f for f in glob.glob(os.path.join(base_dir, "support_arch_*")) if os.path.isfile(f)]
    has_spec_list = os.path.exists(os.path.join(base_dir, "spec_list"))
    if not support_files and not has_spec_list:
        logger.info("[support_arch] 未生成 support_arch/spec_list 文件, 跳过传递")
        return

    if workspace:
        try:
            stage_files = list(support_files)
            if has_spec_list:
                stage_files.append(os.path.join(base_dir, "spec_list"))
            for src in stage_files:
                shutil.copy2(src, os.path.join(workspace, os.path.basename(src)))
            logger.info(
                "[support_arch] 已 stage %d 个文件到 %s (随 ac-result artifact 上传)",
                len(stage_files),
                workspace,
            )
        except OSError as e:
            logger.warning("[support_arch] artifact 通道 stage 失败(不影响门禁结果): %s", e)


def main():
    """
    GitCode Action 门禁主入口
    """
    setup_action_logging("ac_action.log")

    # 从环境变量读取 PR 上下文（解析与校验见 src/action_context.py）
    try:
        ctx = load_action_context(
            entry_name="gate",
            required=("pr_number", "repo", "owner", "token"),
            token_env="ACTION_TOKEN",
        )
    except MissingActionEnvError as e:
        logger.error("%s", e)
        sys.exit(2)
    pr_number = ctx.pr_number
    repo = ctx.repo
    owner = ctx.owner  # 仓库实际 owner（API 调用用）
    target_branch = ctx.target_branch
    token = ctx.token
    workspace = ctx.workspace
    pr_url = ctx.pr_url
    pipeline_url = ctx.pipeline_url
    run_number = ctx.run_number
    committer = ctx.committer

    logger.info("==== GitCode Action 门禁启动 ====")
    logger.info(
        "PR #%s, repo=%s, owner=%s, target_branch=%s", pr_number, repo, owner, target_branch
    )

    base_dir = os.getcwd()

    # 规范化 community（用于 AC 框架加载检查项配置）
    #   - owner: 仓库实际 owner，用于 API 调用和 clone URL
    #   - community: 检查项配置归属（src-openeuler/openeuler），用于 AC 框架
    community = _normalize_community(owner, repo)

    # 抑制无关告警
    warnings.filterwarnings("ignore")
    logging.getLogger("elasticsearch").setLevel(logging.WARNING)
    logging.getLogger("kafka").setLevel(logging.WARNING)

    # 构造 dataset（与 Jenkins 入口保持兼容）
    dd = DistDataset()
    dd.set_attr_stime("access_control.job.stime")
    dd.set_attr("id", "action-{}".format(pr_number))
    dd.set_attr("pull_request.package", repo)
    dd.set_attr("pull_request.number", pr_number)
    dd.set_attr("pull_request.author", committer)
    dd.set_attr("pull_request.target_branch", target_branch)
    now = datetime.datetime.now(datetime.timezone.utc).astimezone().strftime("%Y-%m-%dT%H:%M:%S")
    dd.set_attr("pull_request.ctime", now)
    dd.set_attr("access_control.trigger.link", pr_url)
    dd.set_attr("access_control.trigger.reason", "gitcode_action")
    # dist_dataset 内部 stime/ctime 运算基于 naive datetime，此处须剥离 tzinfo
    dd.set_attr_ctime("access_control.job.ctime",
                      datetime.datetime.now(datetime.timezone.utc).astimezone().replace(tzinfo=None))

    # GitCode proxy（用于评论和标签）——用仓库实际 owner，不是 community
    gp = GitcodeProxy(owner, repo, token)

    # 标记门禁进行中
    try:
        gp.delete_tag_of_pr(pr_number, "ci_successful")
        gp.delete_tag_of_pr(pr_number, "ci_failed")
        gp.create_tags_of_pr(pr_number, "ci_processing")
    except Exception as e:
        logger.warning("设置 ci_processing 标签失败: %s", e)

    code_url = "https://gitcode.com"
    pull_tag = "pull"
    common_args = {
        "pr_url": "{}/{}/{}/{}/{}".format(code_url, owner, repo, pull_tag, pr_number),
        "owner": owner,
        "community": community,
        "pr_num": pr_number,
        "access_token": token,
        "platform": "gitcode",
    }

    # 下载被检查仓库的 PR 代码（与 Jenkins 入口 ac.py __main__ 保持一致）
    # workflow 不做 checkout，由门禁代码自己 fetch PR ref，避免与 GitProxy 逻辑冲突
    repo_url = "{}/{}/{}.git".format(code_url, owner, repo)
    logger.info("cloning repository %s, depth 4", repo_url)
    logger.info("checking out pull request %s", pr_number)

    dd.set_attr_stime("access_control.scm.stime")
    git_proxy = GitProxy.init_repository(repo, work_dir=workspace)
    if not git_proxy or not git_proxy.fetch_pull_request(
        repo_url, pr_number, depth=4, platform="gitcode"
    ):
        dd.set_attr("access_control.scm.result", "failed")
        dd.set_attr_etime("access_control.scm.etime")
        logger.error("fetch PR %s failed", pr_number)
        sys.exit(3)
    git_proxy.checkout_to_commit_force("pull/{}/MERGE".format(pr_number))
    dd.set_attr("access_control.scm.result", "successful")
    dd.set_attr_etime("access_control.scm.etime")
    logger.info("fetch finished +")

    logger.info("--------------------AC START---------------------")
    dd.set_attr_stime("access_control.build.stime")

    # 初始化并执行检查
    ac_yaml_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "framework", "ac.yaml")
    ac = AC(ac_yaml_path, community)
    ac.check_all(
        workspace=workspace, repo=repo, dataset=dd, tbranch=target_branch, common_args=common_args
    )

    dd.set_attr_etime("access_control.build.etime")

    # 上传 check_spec 生成的 support_arch/spec_list 供 build 门禁使用
    _upload_support_arch(base_dir)

    # 保存结果
    result_file = os.path.join(workspace, "ac_result.txt")
    ac.save(result_file)
    logger.info("门禁结果已保存到 %s", result_file)

    # 构造并发布 PR 评论
    comment = _build_pr_comment(ac, pr_number, pipeline_url, run_number)
    try:
        gp.comment_pr(pr_number, comment)
        logger.info("门禁结果已评论到 PR #%s", pr_number)
    except Exception as e:
        logger.error("评论 PR 失败: %s", e)

    # AI 智能摘要：失败或告警时调用 LLM 生成自然语言分析（独立评论，失败不影响主流程）
    _comment_ai_summary(gp, ac, pr_number, repo, target_branch)

    overall_failed = any(item.get("result") == 2 for item in ac._ac_check_result)  # pylint: disable=protected-access

    # lfsconfig 标签（与 Jenkins 入口保持一致）
    lfsconfig_result = ac.get_check_result("check_lfsconfig")
    try:
        if lfsconfig_result == 0:
            gp.delete_tag_of_pr(pr_number, "check_lfs_failed")
            gp.create_tags_of_pr(pr_number, "check_lfs_success")
        elif lfsconfig_result == 2:
            gp.delete_tag_of_pr(pr_number, "check_lfs_success")
            gp.create_tags_of_pr(pr_number, "check_lfs_failed")
    except Exception as e:
        logger.warning("更新 lfsconfig 标签失败: %s", e)

    dd.set_attr_etime("access_control.job.etime")
    logger.info("==== 门禁结束 ====")

    # 门禁失败时以非零退出码结束，Action 会标记为失败
    if overall_failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
