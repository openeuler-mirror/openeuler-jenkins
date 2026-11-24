#!/usr/bin/env python3
# -*- encoding=utf-8 -*-
"""
# **********************************************************************************
# Copyright (c) Huawei Technologies Co., Ltd. 2020-2026. All rights reserved.
# [openeuler-jenkins] is licensed under the Mulan PSL v2.
# You can use this software according to the terms and conditions of the Mulan PSL v2.
# You may obtain a copy of Mulan PSL v2 at:
#          http://license.coscl.org.cn/MulanPSL2
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND,
# EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT,
# MERCHANTABILITY OR FIT FOR A PARTICULAR PURPOSE.
# See the Mulan PSL v2 for more details.
# Author:
# Create: 2026-11-23
# Description: Mask sensitive values in text / JSON read from stdin
# **********************************************************************************
"""

import argparse
import json
import logging
import re
import sys

MASK = "***MASKED***"

# 敏感 key 判定：文本与 JSON 模式共用，子串匹配、大小写不敏感
SENSITIVE_KEY_RE = re.compile(r"token|password|passwd|secret|access_key", re.IGNORECASE)

# 文本模式：key=value / key: value；key 可能是 JSON 风格的带引号形式
_KEY_BODY = r"[A-Za-z0-9_.\-]*(?:token|password|passwd|secret|access_key)[A-Za-z0-9_.\-]*"
_TEXT_RE = re.compile(
    r'(?P<key>"?' + _KEY_BODY + r'"?)(?P<sep>[ \t]*[=:][ \t]*)'
    r'(?P<value>"[^"]*"|\'[^\']*\'|\S+)',
    re.IGNORECASE,
)


def _mask_text(text):
    """只替换敏感 key 对应的 value，保留 key、分隔符与空白。"""
    def _replace(match):
        value = match.group("value")
        # 空值没有可泄露的内容，保持原样
        if value in ('""', "''"):
            return match.group(0)
        if len(value) >= 2 and value.startswith('"') and value.endswith('"'):
            masked = '"%s"' % MASK
        elif len(value) >= 2 and value.startswith("'") and value.endswith("'"):
            masked = "'%s'" % MASK
        else:
            masked = MASK
        return match.group("key") + match.group("sep") + masked

    return _TEXT_RE.sub(_replace, text)


def _mask_json(value):
    """递归替换 JSON 中敏感 key 的 value，保持 key 与结构。"""
    if isinstance(value, dict):
        masked = {}
        for key, item in value.items():
            if isinstance(key, str) and SENSITIVE_KEY_RE.search(key):
                # None / 空串没有可泄露的内容，保持原样
                masked[key] = item if item is None or item == "" else MASK
            else:
                masked[key] = _mask_json(item)
        return masked
    if isinstance(value, list):
        return [_mask_json(item) for item in value]
    return value


def _stream_logger(name, stream):
    """把输出流封装为 logger：保持 CLI 输出原样，同时用日志模块写流。"""
    stream_logger = logging.getLogger(name)
    stream_logger.handlers = []
    stream_logger.propagate = False
    stream_logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    # stdout 内容须与输入逐字节一致（换行由数据决定），不让 handler 追加换行
    handler.terminator = ""
    stream_logger.addHandler(handler)
    return stream_logger


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Mask sensitive values from stdin to stdout."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_mode",
        help="parse input as JSON and mask values of sensitive keys",
    )
    args = parser.parse_args(argv)

    try:
        sys.stdin.reconfigure(encoding="utf-8")
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    stdout_logger = _stream_logger("sensitive_mask.stdout", sys.stdout)
    stderr_logger = _stream_logger("sensitive_mask.stderr", sys.stderr)

    data = sys.stdin.read()
    if args.json_mode:
        try:
            payload = json.loads(data)
        except json.JSONDecodeError as exc:
            stderr_logger.error("sensitive_mask: invalid JSON: %s\n", exc)
            return 2
        suffix = "\n" if data.endswith("\n") else ""
        stdout_logger.info(json.dumps(_mask_json(payload), ensure_ascii=False) + suffix)
    else:
        stdout_logger.info(_mask_text(data))
    return 0


if __name__ == "__main__":
    sys.exit(main())
