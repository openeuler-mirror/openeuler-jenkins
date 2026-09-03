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
# Create: 2026-08-14
# Description: GitCode Action entry for final gate summary (result label + committer notify)
# ***********************************************************************************
"""
GitCode Action 门禁最终汇总脚本（ci-final job 入口）

职责：在所有门禁 job（gate / build 双架构 matrix）结束后统一：
1. 汇总各 job 结果，判定最终标签 ci_successful / ci_failed；
2. 清理旧标签（ci_processing / ci_successful / ci_failed）并设置最终标签；
3. @committer 通知 PR 提交者。

判定规则：ci_successful 要求 AC（gate）与各架构 build / install / license 全部通过，
即 gate.result / build.result 均为 success（matrix job 任一架构实例失败即 failure；
job 退出码即聚合结果，compare 不纳入统计；AC 的 warning/exclude 不计失败）。
否则判定 ci_failed。

本脚本只做最终标签与 @committer，故从 ci-final 的 needs.<job>.result 读取各 job 结果。
"""

import logging
import os
import sys

from src.action_context import MissingActionEnvError, load_action_context, setup_action_logging
from src.proxy.gitcode_proxy import GitcodeProxy

logger = logging.getLogger("build.final")


def main():
    """GitCode Action 门禁最终标签汇总主入口"""
    setup_action_logging("finalize_action.log")

    # 从环境变量读取 PR 上下文（解析与校验见 src/action_context.py）
    try:
        ctx = load_action_context(
            entry_name="final",
            required=("pr_number", "repo", "owner", "token"),
        )
    except MissingActionEnvError as e:
        logger.error("%s", e)
        sys.exit(2)
    pr_number = ctx.pr_number
    owner = ctx.owner
    repo = ctx.repo
    token = ctx.token
    committer = ctx.committer
    gate_result = os.environ.get("ACTION_GATE_RESULT", "")
    build_result = os.environ.get("ACTION_BUILD_RESULT", "")

    logger.info("==== GitCode Action 门禁最终汇总启动 ====")
    logger.info("PR #%s, repo=%s, gate=%s, build=%s",
                pr_number, repo, gate_result, build_result)

    gp = GitcodeProxy(owner, repo, token)

    if gate_result == "success" and build_result == "success":
        final_state = "ci_successful"
    else:
        final_state = "ci_failed"
    logger.info("final state: %s", final_state)

    # 清理旧标签，保持 ci_processing / ci_successful / ci_failed 三者一致。
    for old_tag in ("ci_processing", "ci_successful", "ci_failed"):
        if old_tag == final_state:
            continue
        try:
            gp.delete_tag_of_pr(pr_number, old_tag)
        except Exception as e:
            logger.warning("删除标签 %s 失败: %s", old_tag, e)

    try:
        gp.create_tags_of_pr(pr_number, final_state)
        logger.info("已设置标签 %s 到 PR #%s", final_state, pr_number)
    except Exception as e:
        logger.warning("设置标签 %s 失败(可能已存在): %s", final_state, e)

    # 门禁全部完成后 @committer 通知 PR 提交者
    if committer:
        try:
            gp.comment_pr(pr_number, "@{}".format(committer))
            logger.info("已 @committer %s 到 PR #%s", committer, pr_number)
        except Exception as e:
            logger.error("@committer 失败: %s", e)

    logger.info("==== 门禁最终汇总结束 ====")

    # 门禁失败时以非零退出码结束本 job，使流水线运行状态与 ci_failed 标签一致，
    # 并让 ci-final 进入"失败 job"集合（页面"重新运行失败 job"可重新汇总）。
    if final_state == "ci_failed":
        sys.exit(1)


if __name__ == "__main__":
    main()
