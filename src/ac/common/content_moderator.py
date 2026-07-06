# -*- encoding=utf-8 -*-
"""
# **********************************************************************************
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
# Description: AI summary content safety moderation via LLM service
# **********************************************************************************
"""

import logging

logger = logging.getLogger("ac")

# 内容审核 System Prompt
# 要求 LLM 扮演内容审核员，判断文本是否包含公司名称/敏感内容
MODERATION_PROMPT = """\
你是一个内容安全审核员。你的任务是审核以下文本，判断是否适合在开源社区 PR 评论中公开发布。

审核标准：
1. 文本中是否涉及任何政治、宗教、人权、领土主权等敏感话题？
2. 文本中是否包含侮辱性、歧视性或其他不当言论？

如果文本违反了以上任何一条，请回复 "UNSAFE" 并简要说明原因。
如果文本完全合规，请只回复 "SAFE"。

你必须只回复 "SAFE" 或 "UNSAFE: 原因"，不要回复其他内容。"""


class ContentModerator:
    """
    通过 LLM 服务端审核确保 AI 摘要输出的合规性。

    使用 LLM-as-judge 模式：发送内容到 LLM 进行审核，
    由 LLM 判断是否包含政治敏感内容或不当言论。
    不在代码中硬编码任何敏感词列表。
    """

    def __init__(self, llm_proxy):
        """
        :param llm_proxy: LLMProxy 实例（复用同一个连接，或可独立配置审核模型）
        """
        self._llm = llm_proxy

    def moderate(self, text):
        """
        对 LLM 输出进行内容安全审核。

        :param text: 待审核文本
        :return: (is_safe: bool, reason: str)
            - is_safe=True: 内容安全，可发布
            - is_safe=False: 内容不安全，不应发布，reason 说明原因
        """
        if not text:
            return True, ""

        success, response = self._llm.chat(
            MODERATION_PROMPT,
            "请审核以下文本：\n\n{}".format(text)
        )

        if not success or not response:
            # 审核服务不可用时，默认拒绝（fail-closed，防止未审核内容发布）
            logger.error("[AI-Moderator] 内容审核服务调用失败，默认拒绝发布")
            return False, "审核服务不可用"

        response = response.strip().upper()
        if response.startswith("SAFE"):
            logger.info("[AI-Moderator] 内容审核通过")
            return True, ""

        # UNSAFE — 提取原因
        reason = response
        if response.startswith("UNSAFE"):
            # 格式: "UNSAFE: 原因" 或 "UNSAFE - 原因"
            for sep in [":", "：", "-"]:
                if sep in response:
                    reason = response.split(sep, 1)[1].strip()
                    break

        logger.warning("[AI-Moderator] 内容审核未通过: %s", reason)
        return False, reason
