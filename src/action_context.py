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
# Create: 2026-08-26
# Description: Shared PR context and logging setup for GitCode Action entries
# ***********************************************************************************
"""
GitCode Action 入口公共模块

三个 Action 入口共用的 PR 上下文解析与日志初始化：
    - src/ac/gate_entry.py            （gate 门禁入口）
    - src/build/comment_entry.py      （build 门禁评论入口）
    - src/build/final_entry.py        （ci-final 最终汇总入口）

约定：ci.yml / build_entry.sh 只负责注入 ACTION_* 环境变量，
本模块统一完成读取、默认值、必填校验（缺失时抛 MissingActionEnvError，
由各入口 main 捕获后 exit 2）。
"""

import dataclasses
import logging
import os
import sys

logger = logging.getLogger("action_context")


class MissingActionEnvError(Exception):
    """
    缺少必要的 ACTION_* 环境变量（由各入口 main 捕获后 sys.exit(2)）
    """
    pass

# ActionContext 字段 → 环境变量名（token 例外：gate 入口用 ACTION_TOKEN，
# build/finalize 入口用 ACTION_GITCODE_TOKEN，由 load_action_context 的 token_env 指定）
_FIELD_ENV = {
    "pr_number": "ACTION_PR_NUMBER",
    "repo": "ACTION_REPO",
    "owner": "ACTION_OWNER",
    "target_branch": "ACTION_TARGET_BRANCH",
    "workspace": "ACTION_WORKSPACE",
    "pipeline_url": "ACTION_PIPELINE_URL",
    "run_number": "ACTION_RUN_NUMBER",
    "committer": "ACTION_COMMITTER",
    "arch": "ACTION_ARCH",
    "variant": "ACTION_VARIANT",
    "pr_url": "ACTION_PR_URL",
}


@dataclasses.dataclass
class ActionContext:
    """
    GitCode Action PR 上下文（ACTION_* 环境变量的解析结果）

    :param pr_number: PR 编号
    :param repo: 仓库名（如 openEuler-repos）
    :param owner: 仓库实际 owner（API 调用用，如 src-openeuler）
    :param token: GitCode API token
    :param target_branch: PR 目标分支
    :param workspace: 工作目录（产物所在）
    :param pipeline_url: 本 job 流水线链接（Build Details 跳转）
    :param run_number: Action 执行编号（链接显示 #N）
    :param committer: PR 提交者
    :param arch: 编译架构（x86_64 / aarch64，仅 build 入口使用）
    :param variant: 构建变体（如 64k，仅 build 入口使用）
    :param pr_url: PR 链接（仅 gate 入口使用）
    """

    pr_number: str
    repo: str
    owner: str
    token: str
    target_branch: str = ""
    workspace: str = ""
    pipeline_url: str = ""
    run_number: str = ""
    committer: str = ""
    arch: str = ""
    variant: str = ""
    pr_url: str = ""


def setup_action_logging(log_file):
    """
    初始化 Action 入口日志（stdout + log/<log_file>）

    显式装配 root logger：basicConfig 在业务模块已抢先配置过 root 时会静默失效
    （无 handler 时文件日志丢失），这里强制重置 handlers 保证一定落地。

    :param log_file: 日志文件名（写到 log/ 目录下，如 ac_action.log）
    """
    os.makedirs("log", exist_ok=True)
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()
    root.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s [%(levelname)7s] %(name)s: %(message)s")
    stream_handler = logging.StreamHandler(sys.stdout)
    file_handler = logging.FileHandler(os.path.join("log", log_file))
    for handler in (stream_handler, file_handler):
        handler.setFormatter(formatter)
        root.addHandler(handler)


def load_action_context(entry_name, required=(), token_env="ACTION_GITCODE_TOKEN"):
    """
    读取并校验 ACTION_* 环境变量，返回 PR 上下文。

    :param entry_name: 入口标识（用于日志，如 gate / build_comment / final）
    :param required: 必填字段名元组（ActionContext 字段名），缺失时抛 MissingActionEnvError
                     （由入口 main 捕获后 sys.exit(2)）
    :param token_env: token 对应的环境变量名（gate 入口为 ACTION_TOKEN，
                      build/finalize 入口为 ACTION_GITCODE_TOKEN）
    :return: ActionContext
    """
    # ACTION_OWNER 为正式环境变量名（装 PR 目标仓实际 owner，API 调用用）；
    # ACTION_COMMUNITY 为改名前的旧名，过渡期回退读取（三仓 ci.yml 全量切换后删除）
    owner = os.environ.get("ACTION_OWNER") or os.environ.get("ACTION_COMMUNITY", "")
    ctx = ActionContext(
        pr_number=os.environ.get("ACTION_PR_NUMBER", ""),
        repo=os.environ.get("ACTION_REPO", ""),
        owner=owner,
        token=os.environ.get(token_env, ""),
        target_branch=os.environ.get("ACTION_TARGET_BRANCH", ""),
        workspace=os.environ.get("ACTION_WORKSPACE", os.getcwd()),
        pipeline_url=os.environ.get("ACTION_PIPELINE_URL", ""),
        run_number=os.environ.get("ACTION_RUN_NUMBER", ""),
        committer=os.environ.get("ACTION_COMMITTER", ""),
        arch=os.environ.get("ACTION_ARCH", ""),
        variant=os.environ.get("ACTION_VARIANT", ""),
        pr_url=os.environ.get("ACTION_PR_URL", ""),
    )
    missing = [name for name in required if not getattr(ctx, name)]
    if missing:
        envs = ", ".join(token_env if name == "token" else _FIELD_ENV.get(name, name)
                         for name in missing)
        raise MissingActionEnvError("[%s] 缺少必要环境变量: %s" % (entry_name, envs))
    return ctx
