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
# Description: GitCode Action entry for build gate comment
# ***********************************************************************************
"""
GitCode Action 编译门禁评论入口脚本

与 Jenkins 时代的独立 comment job（comment.sh + gitee_comment.py __main__）对应，
但从环境变量获取 PR 上下文，读取 build job 本地产物，直接评论 PR。

本脚本只做评论，不强加最终标签（ci_successful / ci_failed 由 ci-final job 统一汇总），
也不做 @committer（同样交给 ci-final，门禁全部完成后统一通知）。

环境变量约定（由 build_entry.sh / ci.yml 注入）：
    ACTION_PR_NUMBER:       PR 编号
    ACTION_REPO:            仓库名
    ACTION_OWNER:           仓库 owner（API 调用用，如 src-openeuler）
    ACTION_GITCODE_TOKEN:   GitCode API token
    ACTION_ARCH:            编译架构（x86_64 / aarch64）
    ACTION_VARIANT:         构建变体（可选，如 64k）
    ACTION_WORKSPACE:       工作目录（产物所在）
    ACTION_PIPELINE_URL:    本 build job 流水线链接（Build Details 跳转）
    ACTION_RUN_NUMBER:      Action 执行编号（链接显示 #N）
    ACTION_BUILD_RESULT:    build 成败（0 成功 / 非 0 失败），由 build_entry.sh 传入
    ACTION_TARGET_BRANCH:   目标分支（compare 差异评论用）
"""

import logging
import os
import sys

from src.action_context import MissingActionEnvError, load_action_context, setup_action_logging
from src.build.gitee_comment import Comment
from src.proxy.gitcode_proxy import GitcodeProxy

logger = logging.getLogger("build")


def _locate_artifacts(workspace, repo, pr_number, arch, variant):
    """
    定位 build 门禁本地产物。

    :param workspace: 工作目录
    :param repo: 仓库名
    :param pr_number: PR 编号
    :param arch: 编译架构
    :param variant: 构建变体（可为空）
    :return: (check_item_comment_file, compare_result_file)
    """
    variant_suffix = "_{}".format(variant) if variant else ""
    name_base = "{}_{}_{}{}".format(repo, pr_number, arch, variant_suffix)
    check_file = os.path.join(workspace, "records-course", "{}_comment".format(name_base))
    compare_file = os.path.join(workspace, "{}_compare_result".format(name_base))
    return check_file, compare_file


def main():
    """GitCode Action 编译门禁评论主入口"""
    setup_action_logging("build_action.log")

    # 从环境变量读取 PR 上下文（解析与校验见 src/action_context.py）
    try:
        ctx = load_action_context(
            entry_name="build_comment",
            required=("pr_number", "repo", "owner", "arch", "token"),
        )
    except MissingActionEnvError as e:
        logger.error("%s", e)
        sys.exit(2)
    pr_number = ctx.pr_number
    repo = ctx.repo
    owner = ctx.owner
    arch = ctx.arch
    variant = ctx.variant
    workspace = ctx.workspace
    pipeline_url = ctx.pipeline_url
    run_number = ctx.run_number
    target_branch = ctx.target_branch
    token = ctx.token
    build_rc = int(os.environ.get("ACTION_BUILD_RESULT", "0"))

    logger.info("==== GitCode Action build 门禁评论启动 ====")
    logger.info("PR #%s, repo=%s, owner=%s, arch=%s, build_rc=%s",
                pr_number, repo, owner, arch, build_rc)

    # 切到产物工作目录，使 Comment 内部读取 support_arch_* / spec_list 等相对文件可用
    os.chdir(workspace)

    # gitee_comment 模块内部的 logger 在 __main__ 分支才定义，import 时为 None，
    # 这里显式挂到模块全局，保证其实例方法可正常打日志。
    import src.build.gitee_comment as gitee_comment  # noqa: PLC0415 - 延迟赋值模块 logger
    gitee_comment.logger = logger

    gp = GitcodeProxy(owner, repo, token)

    # 定位本地产物（check 项评论文件 + compare 差异结果文件）
    check_file, compare_file = _locate_artifacts(workspace, repo, pr_number, arch, variant)
    logger.info("check comment file: %s, compare result file: %s", check_file, compare_file)

    # 构造单条 build 结果（仅评论自身架构，不动标签、不 @committer）
    # 64k 变体的架构名拼接为 aarch64_64k：gitee_comment 的 match 逻辑按此区分
    # 4k/64k（arch 无 64k 而产物文件名有 64k 时交叉校验不匹配，check 项会被误判 failed）
    build_result = "SUCCESS" if build_rc == 0 else "FAILURE"
    arch_name = "{}_{}".format(arch, variant) if variant else arch
    comment = Comment(pr_number, None, check_file)
    comment.set_compile_build(pipeline_url, run_number, build_result, arch_name)

    # check 项评论（check_build / check_install / check_license）
    try:
        comment.comment_build(gp)
        logger.info("build check 项已评论到 PR #%s", pr_number)
    except Exception as e:  # noqa: BLE001 - 评论失败不阻断脚本
        logger.error("评论 build check 项失败: %s", e)

    # compare 差异评论：仅当 build 成功且差异结果文件存在时评论，失败无 rpm 产物无意义
    if build_rc == 0 and os.path.exists(compare_file):
        try:
            comment.comment_compare_package_details(gp, compare_file, target_branch)
            logger.info("compare 差异已评论到 PR #%s", pr_number)
        except Exception as e:  # noqa: BLE001 - 评论失败不阻断脚本
            logger.error("评论 compare 差异失败: %s", e)

    logger.info("==== build 门禁评论结束 ====")


if __name__ == "__main__":
    main()
