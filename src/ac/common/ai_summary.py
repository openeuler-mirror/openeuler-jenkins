# -*- encoding=utf-8 -*-
"""
# ***********************************************************************************
# Copyright (c) Huawei Technologies Co., Ltd. 2026. All rights reserved.
# [openeuler-jenkins] is licensed under the Mulan PSL v2.
# You can use this software according to the terms and conditions of the Mulan PSL v2.
# You may obtain a copy of Mulan PSL v2 at:
#          http://license.coscl.org.cn/MulanPSL2
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND,
# EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT,
# MERCHANTABILITY OR FIT FOR A PARTICULAR PURPOSE.
# See the Mulan PSL v2 for more details.
# Author:
# Create: 2026-07-04
# Description: AI summary module, convert gate check results to LLM prompt
# ***********************************************************************************
"""

import logging
import os
import yaml

from src.ac.common.content_moderator import ContentModerator

logger = logging.getLogger("ac")

# 检查项名称到中文说明的映射
CHECK_ITEM_DESCRIPTIONS = {
    "check_lfsconfig": "Git LFS配置文件检查",
    "check_patch_format": "补丁格式检查",
    "check_spec_file": "spec文件格式检查",
    "check_package_yaml_file": "yaml文件格式检查",
    "check_binary_file": "二进制文件检查",
    "check_consistency": "源码包一致性检查",
    "check_repo_in_maintain": "仓库维护状态检查",
    "check_package_license": "license合法性检查",
    "check_sca": "软件成分分析(SCA)",
    "check_code": "代码静态分析(CodeCheck)",
    "check_commit_msg": "commit message规范检查",
    "check_anti_poisoning": "代码投毒检测",
}

SYSTEM_PROMPT = """\
你是openEuler社区门禁系统的AI助手。你的任务是分析PR门禁检查结果，为开发者提供清晰的问题诊断和修复建议。

输出要求：
1. 使用中文，简洁明了
2. 注意：result 值的含义是 0=通过(SUCCESS), 1=警告(WARNING), 2=失败(FAILED), 3=不适用/跳过(EXCLUDE)
3. EXCLUDE 表示该检查项被配置为跳过，不需要修复，属于正常状态
4. 只分析 result 为 1(警告) 或 2(失败) 的项，跳过 0(通过) 和 3(EXCLUDE) 的项
5. 如果所有项都是通过或EXCLUDE，说明门禁已全部通过
6. 分为"总结"、"问题分析"、"修复建议"三部分
7. 修复建议要具体可操作，尽量给出示例命令或链接
8. 如果提供了 details 信息，优先基于 details 分析原因
9. 不要编造具体的技术细节，只基于提供的数据进行分析
10. 严禁在回复中提及任何公司名称、品牌名称、产品名称（代码托管平台如GitHub/GitLab/Gitee/AtomGit/GitCode及openEuler等开源社区/项目名称除外），只使用技术术语
11. 严禁涉及任何政治、宗教、人权、领土主权等敏感话题
12. 使用markdown格式，不超过800字"""


class AISummarizer:
    """
    AI 智能摘要生成器。
    将结构化的门禁检查结果转换为 LLM prompt，调用 LLM 生成摘要。
    """

    def __init__(self, llm_proxy):
        """
        :param llm_proxy: LLMProxy 实例
        """
        self._llm = llm_proxy
        self._moderator = ContentModerator(llm_proxy)

    def summarize(self, check_results, pr_context=None):
        """
        生成门禁结果的 AI 摘要。

        :param check_results: [{"name": "check_spec_file", "result": 2, "details": [...]}, ...]
        :param pr_context: {"repo": "", "branch": "", "author": ""}
        :return: (success: bool, summary: str)
        """
        user_prompt = self._build_user_prompt(check_results, pr_context)
        success, raw_content = self._llm.chat(SYSTEM_PROMPT, user_prompt)
        if not success or not raw_content:
            return False, ""

        # 内容安全审核：通过 LLM 审核判断输出是否合规
        is_safe, reason = self._moderator.moderate(raw_content)
        if not is_safe:
            logger.warning("[AI] AI摘要内容审核未通过，跳过发布: %s", reason)
            return False, ""

        return True, raw_content

    @staticmethod
    def _build_user_prompt(check_results, pr_context):
        """
        构建用户 prompt，将结构化门禁结果转换为自然语言描述。
        """
        parts = []

        # PR 上下文
        if pr_context:
            if pr_context.get("repo"):
                parts.append("仓库: {}".format(pr_context["repo"]))
            if pr_context.get("branch"):
                parts.append("目标分支: {}".format(pr_context["branch"]))

        # 检查结果汇总
        total = len(check_results)
        failed = [r for r in check_results if r["result"] == 2]
        warned = [r for r in check_results if r["result"] == 1]
        passed = [r for r in check_results if r["result"] == 0]

        parts.append("\n门禁检查汇总: 共{}项, {}项通过, {}项警告, {}项失败".format(
            total, len(passed), len(warned), len(failed)))

        # 逐项列出失败/警告详情
        for item in failed + warned:
            name = item["name"]
            desc = CHECK_ITEM_DESCRIPTIONS.get(name, name)
            status = "FAILED" if item["result"] == 2 else "WARNING"
            parts.append("\n[{}] {} ({})".format(status, desc, name))
            if item.get("details"):
                for d in item["details"]:
                    parts.append("  - {}".format(d))

        return "\n".join(parts)


def load_ai_config():
    """
    加载 AI 配置文件。
    支持环境变量替换 API Key（格式: ${ENV_VAR_NAME}）。

    :return: {"enabled": bool, "llm": {"api_url": str, "api_key": str, "model": str, "timeout": int}}
    """
    conf_path = os.path.join(os.path.dirname(__file__), "../../conf/ai.yaml")
    try:
        with open(conf_path, "r") as f:
            config = yaml.safe_load(f)
    except (IOError, yaml.YAMLError) as e:
        logger.warning("[AI-Config] 加载配置文件 %s 失败: %s", conf_path, e)
        return {"enabled": False}

    ai_conf = config.get("ai_summary", {})
    if not ai_conf.get("enabled"):
        return {"enabled": False}

    llm_conf = ai_conf.get("llm", {})

    # 支持环境变量覆盖 API Key
    api_key = llm_conf.get("api_key", "")
    if api_key.startswith("${") and api_key.endswith("}"):
        env_var = api_key[2:-1]
        api_key = os.environ.get(env_var, "")

    if not api_key:
        logger.info("AI API key not configured, AI summary disabled")
        return {"enabled": False}

    return {
        "enabled": True,
        "llm": {
            "api_url": llm_conf.get("api_url", ""),
            "api_key": api_key,
            "model": llm_conf.get("model", "mimo-v2.5-pro"),
            "timeout": llm_conf.get("timeout", 20),
            "max_tokens": llm_conf.get("max_tokens", 1500)
        }
    }
