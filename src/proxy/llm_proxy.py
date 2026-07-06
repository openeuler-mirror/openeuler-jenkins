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
# Description: LLM API proxy, supports OpenAI compatible interfaces
# ***********************************************************************************
"""

import logging
import requests

logger = logging.getLogger("common")


class LLMProxy:
    """
    OpenAI 兼容接口的 LLM 代理。
    支持所有实现了 /v1/chat/completions 接口的模型服务。
    """

    def __init__(self, api_url, api_key, model, timeout=20, max_tokens=1500):
        """
        :param api_url: LLM API 地址（完整 URL，如 https://api.openai.com/v1/chat/completions）
        :param api_key: API Key
        :param model: 模型名称（如 mimo-v2.5-pro, glm-4-flash, gpt-4o-mini）
        :param timeout: 请求超时秒数
        :param max_tokens: 最大输出 token 数
        """
        self._api_url = api_url
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._max_tokens = max_tokens

    def chat(self, system_prompt, user_prompt):
        """
        调用 LLM 进行对话。

        :param system_prompt: 系统提示词
        :param user_prompt: 用户提示词
        :return: (success: bool, content: str)
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer {}".format(self._api_key)
        }
        body = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.3,
            "max_tokens": self._max_tokens
        }
        try:
            resp = requests.post(
                self._api_url,
                json=body,
                headers=headers,
                timeout=self._timeout
            )
            if resp.status_code != 200:
                try:
                    err_msg = resp.json().get("error", {}).get("message", resp.text[:200])
                except Exception:
                    err_msg = resp.text[:200]
                logger.warning("LLM API returned status %s: %s", resp.status_code, err_msg)
                return False, ""

            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return True, content.strip()

        except requests.exceptions.Timeout:
            logger.warning("LLM API timeout (%ss)", self._timeout)
            return False, ""
        except (KeyError, IndexError, ValueError) as e:
            logger.warning("LLM API response parse error: %s", e)
            return False, ""
        except Exception as e:
            logger.warning("LLM API error: %s", e)
            return False, ""
