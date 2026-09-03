# -*- encoding=utf-8 -*-
# ***********************************************************************************
# Copyright (c) Huawei Technologies Co., 2026. All rights reserved.
# [openeuler-jenkins] is licensed under the Mulan PSL v2.
# You can use this software according to the terms and conditions of the Mulan PSL v2.
# You may obtain a copy of Mulan PSL v2 at:
#          http://license.coscl.org.cn/MulanPSL2/
# THIS SOFTWARE IS PROVIDED ON AN " IS" BASIS, WITHOUT WARRANTIES OF ANY KIND,
# EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT,
# MERCHANTABILITY OR FIT FOR A PARTICULAR PURPOSE.
# See the Mulan PSL v2 for more details.
# Author:
# Create: 2026-08-30
# Description: GitCode Action entry for build gate summary comment (multi-arch aggregated)
# ***********************************************************************************
"""
GitCode Action 编译门禁汇总评论入口脚本（build-comment job 入口）

matrix 化 build job 后，各架构实例不再直接评论 PR（原每架构 2 条评论 × N 架构，
评论多且分散），改为仅把结果文件随 artifact 上传；本脚本在 build-comment 汇总
job 中运行，download-artifact 拉取全部架构制品后：

1. 遍历各架构产物目录，读 {repo}_{pr}_{arch}[_{variant}]_build_rc 获知该架构成败；
2. 逐架构 set_compile_build() 注入 Comment（该类原生支持多架构同表渲染）；
3. 发评论①：build check 项汇总（build/install/license，所有架构一张表）；
4. 发评论②：oecp compare 差异汇总（compare 文件逗号拼接，多架构分组渲染）。

与 Jenkins 时代独立 comment job 的聚合形态一致（对应 ARCH_BUILD_INFO 多行注入），
对比逻辑不迁移：oecp 对比仍在各 build 实例内执行，本脚本只做渲染合并。

本脚本不发最终标签（ci-final job 职责）、不 @committer。

环境变量约定（由 ci.yml build-comment job 注入）：
    ACTION_PR_NUMBER:       PR 编号
    ACTION_REPO:            仓库名
    ACTION_OWNER:           仓库 owner（API 调用用，如 src-openeuler）
    ACTION_GITCODE_TOKEN:   GitCode API token
    ACTION_TARGET_BRANCH:   目标分支（compare 差异评论用）
    ACTION_ARTIFACT_DIR:    制品下载根目录（各架构制品子目录的父目录）
    ACTION_PIPELINE_URL:    本 run 流水线链接（各架构 Build Details 跳转）
    ACTION_RUN_NUMBER:      Action 执行编号（链接显示 #N）
"""

import glob
import logging
import os
import shutil
import sys

from src.action_context import MissingActionEnvError, load_action_context, setup_action_logging
from src.build.gitee_comment import Comment
from src.proxy.gitcode_proxy import GitcodeProxy

logger = logging.getLogger("build")

# artifact 内部产物文件的相对路径模式（与 build 侧落盘结构一致）：
#   records-course/{repo}_{pr}_{arch}[_{variant}]_build_rc    各架构成败
#   records-course/{repo}_{pr}_{arch}[_{variant}]_comment     check 项评论数据
#   {repo}_{pr}_{arch}[_{variant}]_compare_result             oecp 对比结果（workspace 根）
_RECORDS = "records-course"


def _scan_builds(artifact_dir, repo, pr_number):
    """
    扫描制品目录，收集各架构构建信息。

    制品结构（download-artifact 落盘）：{artifact_dir}/{artifact_name}/{原路径}，
    artifact_name 即 build-result-{arch}。逐制品目录查找 _build_rc 文件，
    缺失视为该架构失败（fail-safe：写不出 rc 说明实例异常中断）。

    :param artifact_dir: 制品下载根目录
    :param repo: 仓库名
    :param pr_number: PR 编号
    :return: list[dict]，每项 {arch_name, build_rc, check_file, compare_file}
             arch_name 含变体后缀（如 aarch64_64k），与 Comment 渲染约定一致
    """
    builds = []
    if not os.path.isdir(artifact_dir):
        logger.error("artifact dir not found: %s", artifact_dir)
        return builds

    for artifact_name in sorted(os.listdir(artifact_dir)):
        artifact_path = os.path.join(artifact_dir, artifact_name)
        records_dir = os.path.join(artifact_path, _RECORDS)
        if os.path.isdir(records_dir):
            # 常规结构：records-course 目录层保留（upload 多 path 公共祖先=workspace）
            scan_dir = records_dir
        elif any(f.endswith("_build_rc") for f in os.listdir(artifact_path)):
            # 平铺结构兜底：build 失败时 compare/oecp.log 未生成，upload-artifact
            # 公共祖先坍缩，目录层被吞、文件平铺在制品根（build 侧的 build_entry.log
            # 锚点已根治该场景，此处兼容防御）
            scan_dir = artifact_path
            logger.warning("artifact %s has flat layout (no %s dir), scanning artifact root",
                           artifact_name, _RECORDS)
        else:
            logger.debug("skip non-build artifact: %s", artifact_name)
            continue

        # 在扫描目录下找本 PR 的 _build_rc 文件（架构与变体后缀从文件名解析）
        prefix = "{}_{}_".format(repo, pr_number)
        for fname in os.listdir(scan_dir):
            if not (fname.startswith(prefix) and fname.endswith("_build_rc")):
                continue
            # 文件名形如 {repo}_{pr}_{arch}[_{variant}]_build_rc
            arch_name = fname[len(prefix):-len("_build_rc")]
            rc_file = os.path.join(scan_dir, fname)
            try:
                with open(rc_file, "r") as fp:
                    build_rc = int(fp.read().strip())
            except (ValueError, OSError) as e:
                logger.warning("read build_rc %s failed: %s, treat as FAILURE", rc_file, e)
                build_rc = 1

            variant = ""
            if arch_name.endswith("_64k"):
                variant = "64k"
            # check 文件与 _build_rc 同目录；compare 文件在制品根（上传时位于 workspace 根）
            check_file = os.path.join(scan_dir, "{}{}_comment".format(prefix, arch_name))
            compare_file = os.path.join(artifact_path, "{}{}_compare_result".format(prefix, arch_name))
            builds.append({
                "arch_name": arch_name,
                "build_rc": build_rc,
                "check_file": check_file,
                "compare_file": compare_file,
            })
            logger.info("scanned build: arch=%s rc=%s", arch_name, build_rc)

    if not builds:
        logger.warning("no build_rc found under %s, nothing to comment", artifact_dir)
    return builds


def _restore_ac_spec_files(artifact_dir):
    """
    从 ac-result 制品还原 spec_list/support_arch_* 到当前工作目录。

    gitee_comment 渲染整架构 EXCLUDE 行依赖 cwd 下的 spec_list/support_arch_*
    （ExclusiveArch 全受限架构跳过构建时无 comment 文件，须据此判定排除语义，
    否则该架构 build_rc=0 会被误渲染为 SUCCESS）。download-artifact 落盘时
    保留原路径层级（upload path 公共祖先是 /tmp，实际位于 ac-result/ac-workspace/...），
    故递归 glob 动态定位，不假设固定子目录。

    :param artifact_dir: 制品下载根目录
    """
    spec_list_files = glob.glob(os.path.join(artifact_dir, "ac-result", "**", "spec_list"),
                                recursive=True)
    if not spec_list_files:
        logger.warning("no spec_list under %s/ac-result (AC 未生成或下载失败)，"
                       "EXCLUDE 渲染降级", artifact_dir)
        return
    spec_dir = os.path.dirname(spec_list_files[0])
    copied = []
    for path in [spec_list_files[0]] + sorted(glob.glob(os.path.join(spec_dir, "support_arch_*"))):
        dest = os.path.join(os.getcwd(), os.path.basename(path))
        shutil.copy(path, dest)
        copied.append(os.path.basename(path))
    logger.info("restored AC spec files to cwd: %s", copied)


def main():
    """GitCode Action build 门禁汇总评论主入口"""
    setup_action_logging("build_action.log")

    try:
        ctx = load_action_context(
            entry_name="build_summary",
            required=("pr_number", "repo", "owner", "token"),
        )
    except MissingActionEnvError as e:
        logger.error("%s", e)
        sys.exit(2)
    pr_number = ctx.pr_number
    repo = ctx.repo
    owner = ctx.owner
    target_branch = ctx.target_branch
    token = ctx.token
    pipeline_url = ctx.pipeline_url
    run_number = ctx.run_number
    artifact_dir = os.environ.get("ACTION_ARTIFACT_DIR", "")

    logger.info("==== GitCode Action build 汇总评论启动 ====")
    logger.info("PR #%s, repo=%s, owner=%s, artifact_dir=%s", pr_number, repo, owner, artifact_dir)

    # 还原 AC spec 清单到 cwd（EXCLUDE 渲染数据源），失败不阻断汇总评论
    if artifact_dir:
        try:
            _restore_ac_spec_files(artifact_dir)
        except OSError as e:
            logger.warning("restore ac spec files failed: %s, EXCLUDE 渲染降级", e)

    builds = _scan_builds(artifact_dir, repo, pr_number)
    if not builds:
        logger.warning("no build artifacts to comment, skip")
        return

    # gitee_comment 模块 logger 挂载（与 comment_entry.py 一致）
    import src.build.gitee_comment as gitee_comment  # noqa: PLC0415 - 延迟赋值模块 logger
    gitee_comment.logger = logger

    gp = GitcodeProxy(owner, repo, token)

    # 收集各架构产物文件，构造单实例 Comment 一次成型：
    # check_item_comment_files（构造参数）供 _comment_of_check_item 渲染，
    # set_compile_build 逐架构 append 供同表渲染（Comment 原生多架构聚合）
    check_files = []
    compare_files = []
    for build in builds:
        arch_name = build["arch_name"]
        build_result = "SUCCESS" if build["build_rc"] == 0 else "FAILURE"

        if os.path.exists(build["check_file"]):
            check_files.append(build["check_file"])
        else:
            logger.warning("check comment file missing: %s", build["check_file"])

        # compare 文件存在即有效：其生成前提就是 build 成功（ci-guard.sh main 短路逻辑
        # 保证 build 失败不会跑 compare），install 失败场景下比较结果对提交者仍有参考价值
        if os.path.exists(build["compare_file"]):
            compare_files.append(build["compare_file"])
        else:
            logger.info("compare file skip (build failed or not generated): %s", build["compare_file"])

    comment = Comment(pr_number, None, *check_files)
    for build in builds:
        build_result = "SUCCESS" if build["build_rc"] == 0 else "FAILURE"
        comment.set_compile_build(pipeline_url, run_number, build_result, build["arch_name"])

    # check 项汇总评论（所有架构一张表：build/install/license）
    if check_files:
        try:
            comment.comment_build(gp)
            logger.info("build check 汇总已评论到 PR #%s", pr_number)
        except Exception as e:  # noqa: BLE001 - 评论失败不阻断脚本
            logger.error("评论 build check 汇总失败: %s", e)

    # oecp compare 汇总评论（多架构分组渲染，comment_compare_package_details
    # 原生支持逗号分隔多文件；仅收集到至少一个文件时才评论）
    if compare_files:
        try:
            comment.comment_compare_package_details(gp, ",".join(compare_files), target_branch)
            logger.info("compare 汇总已评论到 PR #%s", pr_number)
        except Exception as e:  # noqa: BLE001 - 评论失败不阻断脚本
            logger.error("评论 compare 汇总失败: %s", e)

    logger.info("==== build 汇总评论结束 ====")


if __name__ == "__main__":
    main()
