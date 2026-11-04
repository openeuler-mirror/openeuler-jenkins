# -*- encoding=utf-8 -*-
"""
# **********************************************************************************
# Copyright (c) Huawei Technologies Co., Ltd. 2020-2020. All rights reserved.
# [openeuler-jenkins] is licensed under the Mulan PSL v2.
# You can use this software according to the terms and conditions of the Mulan PSL v2.
# You may obtain a copy of Mulan PSL v2 at:
#          http://license.coscl.org.cn/MulanPSL2
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND,
# EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT,
# MERCHANTABILITY OR FIT FOR A PARTICULAR PURPOSE.
# See the Mulan PSL v2 for more details.
# Description: wittyhub skill license 准入检查
# **********************************************************************************
"""

import hashlib
import logging
import os
import re
from pathlib import Path

import requests
import yaml

try:
    import chardet
except ImportError:  # pragma: no cover - chardet 是现有依赖，缺失时按 utf-8 解码
    chardet = None

logger = logging.getLogger("ac")

# compliance SIG 维护的 license 准入清单（AtomGit API raw 地址，无需登录）
DEFAULT_LICENSE_LIST_URL = (
    "https://api.atomgit.com/api/v5/repos/openeuler/compliance/raw/"
    "doc/rule/Licenses_Access_List.yaml?ref=master"
)

STATUS_ALLOWED = "allowed"
STATUS_BLACK = "black"
STATUS_RESTRICTED = "restricted"
STATUS_UNKNOWN = "unknown"
STATUS_MISSING = "missing"
STATUS_CONFLICT = "conflict"
STATUS_ERROR = "error"

# 多个分支组合时，取风险最高的状态用于展示
_STATUS_SEVERITY = {
    STATUS_ALLOWED: 0,
    STATUS_MISSING: 1,
    STATUS_UNKNOWN: 2,
    STATUS_RESTRICTED: 3,
    STATUS_BLACK: 4,
    STATUS_CONFLICT: 5,
    STATUS_ERROR: 6,
}

# 这些别名过于宽泛，不能用于 license 文件内容匹配
_GENERIC_ALIASES = frozenset(
    {
        "license",
        "licence",
        "licenses",
        "copyright",
        "notice",
        "multiple",
        "na",
        "unknown",
        "custom",
        "exceptions",
        "advertising",
        "additional permissions",
        "acknowledgement",
        "copyright only",
        "osi-approved",
        "open publication",
    }
)

_LICENSE_FILE_RE = re.compile(
    r"^(?:licen[cs]e|licence|copying|unlicense)(?:[-._].*)?$", re.IGNORECASE
)
_SPDX_HEADER_RE = re.compile(r"SPDX-License-Identifier\s*:\s*([^\r\n]+)", re.IGNORECASE)
_TOKEN_RE = re.compile(r"\(|\)|\bAND\b|\bOR\b|\bWITH\b|[^\s()]+", re.IGNORECASE)

# 常见 license 全文特征。license 文件全文通常不带 SPDX 头，需要按正文识别。
_TEXT_SIGNATURES = (
    ("AGPL-3.0-only", (r"GNU AFFERO GENERAL PUBLIC LICENSE", r"Version\s+3")),
    ("GPL-3.0-only", (r"GNU GENERAL PUBLIC LICENSE", r"Version\s+3")),
    ("GPL-2.0-only", (r"GNU GENERAL PUBLIC LICENSE", r"Version\s+2")),
    ("LGPL-3.0-only", (r"GNU LESSER GENERAL PUBLIC LICENSE", r"Version\s+3")),
    ("LGPL-2.1-only", (r"GNU LESSER GENERAL PUBLIC LICENSE", r"Version\s+2\.1")),
    ("Apache-2.0", (r"Apache License", r"Version\s+2\.0")),
    ("Apache-1.1", (r"Apache Software License", r"Version\s+1\.1")),
    ("MPL-2.0", (r"Mozilla Public License", r"Version\s+2\.0")),
    ("MulanPSL-2.0", (r"Mulan Permissive Software License", r"Version\s+2")),
    ("EPL-2.0", (r"Eclipse Public License", r"(?:v|Version)\s*2\.0")),
    ("CDDL-1.0", (r"COMMON DEVELOPMENT AND DISTRIBUTION LICENSE", r"Version\s+1\.0")),
    ("Artistic-2.0", (r"The Artistic License\s+2\.0",)),
    ("BSL-1.0", (r"Boost Software License", r"Version\s+1\.0")),
    ("OFL-1.1", (r"SIL OPEN FONT LICENSE", r"Version\s+1\.1")),
    ("OFL-1.0", (r"SIL OPEN FONT LICENSE", r"Version\s+1\.0")),
    ("CC0-1.0", (r"CC0\s+1\.0\s+Universal",)),
    ("Unlicense", (r"free and unencumbered software released into the public domain",)),
    ("WTFPL", (r"DO WHAT THE F\*?CK YOU WANT TO PUBLIC LICENSE",)),
    ("Zlib", (r"zlib License",)),
    ("ISC", (r"Permission to use, copy, modify, and/or distribute this software",)),
    ("MIT", (r"Permission is hereby granted, free of charge, to any person obtaining a copy",)),
    (
        "BSD-3-Clause",
        (
            r"Redistribution and use in source and binary forms",
            r"Neither the name",
        ),
    ),
    ("BSD-2-Clause", (r"Redistribution and use in source and binary forms",)),
)


class LicenseListError(Exception):
    """license 准入清单加载或解析失败。"""


class LicenseExpressionError(Exception):
    """SPDX license 表达式不合法。"""


def normalize_expression(value):
    """把 frontmatter/skill.yaml 中的 license 值归一化为 SPDX 表达式。

    列表按 AND 处理（保守），历史写法 ``MIT/Apache-2.0`` 按 OR 处理，
    逗号分隔按 AND 处理。
    """
    if isinstance(value, (list, tuple)):
        value = " AND ".join(str(item) for item in value if str(item).strip())
    text = str(value or "").strip()
    if not text:
        return ""
    text = re.sub(r"\s*/\s*", " OR ", text)
    text = re.sub(r"\s*,\s*", " AND ", text)
    return re.sub(r"\s+", " ", text).strip()


def _normalize_token(value):
    return re.sub(r"\s+", " ", str(value or "").strip().strip("'\"")).lower()


def _worse(statuses):
    """返回多个状态中最严重的一个。"""
    return max(
        statuses, key=lambda item: _STATUS_SEVERITY.get(item, _STATUS_SEVERITY[STATUS_UNKNOWN])
    )


class LicenseVerdict(object):
    """单个 skill 的 license 检查结论。"""

    def __init__(self, status, expression="", sources=None, reasons=None):
        self.status = status
        self.expression = expression
        self.sources = list(sources or [])
        self.reasons = list(reasons or [])

    def to_dict(self):
        return {
            "status": self.status,
            "expression": self.expression,
            "sources": list(self.sources),
            "reasons": list(self.reasons),
        }

    @classmethod
    def from_dict(cls, data):
        data = data or {}
        return cls(
            data.get("status") or STATUS_UNKNOWN,
            data.get("expression") or "",
            data.get("sources") or [],
            data.get("reasons") or [],
        )

    def __repr__(self):
        return "LicenseVerdict(status=%s, expression=%s)" % (self.status, self.expression)


class LicenseAccessList(object):
    """compliance SIG license 准入清单。

    判定口径：
    - black=Y -> 禁止；
    - oeApproved=Y -> 允许；
    - lowRisk=Y 且 oeApproved=N -> oE 受限使用，不属于白名单；
    - 其余（含 Nonstandard、未收录）-> 无法识别，不属于白名单。
    """

    def __init__(self, source=None, timeout=10):
        self._source = source or DEFAULT_LICENSE_LIST_URL
        self._timeout = timeout
        self._entries = {}
        self._alias_index = {}
        self._content_aliases = []
        self._hash = ""
        self._loaded = False

    @property
    def hash(self):
        return self._hash

    def load(self, force=False):
        if self._loaded and not force:
            return self
        raw = self._read_source()
        try:
            content = yaml.safe_load(raw)
        except yaml.YAMLError as exc:
            raise LicenseListError("license 准入清单 YAML 解析失败: {}".format(exc)) from exc
        licenses = content.get("Software Licenses") if isinstance(content, dict) else None
        if not isinstance(licenses, dict):
            raise LicenseListError("license 准入清单缺少 Software Licenses 字段")

        entries = {}
        for group, items in licenses.items():
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                identifier = str(item.get("identifier") or "").strip()
                if not identifier or identifier in entries:
                    continue
                aliases = item.get("alias") or []
                if isinstance(aliases, str):
                    aliases = [aliases]
                entries[identifier] = {
                    "identifier": identifier,
                    "aliases": [str(alias).strip() for alias in aliases if str(alias).strip()],
                    "oeApproved": str(item.get("oeApproved") or "N").upper() == "Y",
                    "lowRisk": str(item.get("lowRisk") or "N").upper() == "Y",
                    "black": str(item.get("black") or "N").upper() == "Y",
                    "blackReason": str(item.get("blackReason") or "").strip(),
                    "exception": str(item.get("exception") or "N").upper() == "Y",
                    "group": group,
                }

        if not entries:
            raise LicenseListError("license 准入清单为空")

        self._entries = entries
        self._alias_index = self._build_alias_index(entries)
        self._content_aliases = self._build_content_aliases(entries)
        self._hash = hashlib.sha256(raw).hexdigest()[:12]
        self._loaded = True
        logger.info(
            "license access list loaded: %d entries, hash=%s",
            len(entries),
            self._hash,
        )
        return self

    def _read_source(self):
        source = self._source
        if os.path.isfile(source):
            with open(source, "rb") as stream:
                return stream.read()
        try:
            response = requests.get(source, timeout=self._timeout)
        except requests.RequestException as exc:
            raise LicenseListError("license 准入清单拉取失败: {}".format(exc)) from exc
        if response.status_code != 200:
            raise LicenseListError("license 准入清单拉取失败: HTTP {}".format(response.status_code))
        return response.content

    @staticmethod
    def _build_alias_index(entries):
        index = {}
        for identifier, entry in entries.items():
            for value in [identifier] + entry["aliases"]:
                key = _normalize_token(value)
                if key:
                    index.setdefault(key, set()).add(identifier)
        return index

    @staticmethod
    def _build_content_aliases(entries):
        pairs = []
        for identifier, entry in entries.items():
            if entry["group"] == "Nonstandard Licenses" or entry["exception"]:
                continue
            for alias in entry["aliases"]:
                key = _normalize_token(alias)
                if len(key) < 5 or key in _GENERIC_ALIASES or not re.search(r"[a-z]", key):
                    continue
                pairs.append((key, identifier))
        pairs.sort(key=lambda item: len(item[0]), reverse=True)
        return pairs[:200]

    def is_nonstandard(self, identifier):
        """是否为 Nonstandard Licenses 中的模糊名称（如 Apache、GPL）。"""
        entry = self._entries.get(identifier)
        return bool(entry and entry["group"] == "Nonstandard Licenses")

    def resolve(self, token):
        """把 license 名称/别名解析为清单中的 identifier。

        返回 ``(identifier, error)``；无法解析或存在冲突时 identifier 为 None。
        """
        key = _normalize_token(token)
        if not key:
            return None, "license 名称为空"
        candidates = self._alias_index.get(key)
        if not candidates:
            candidates = {identifier for identifier in self._entries if identifier.lower() == key}
        if not candidates:
            return None, "未在 license 准入清单中: {}".format(token)
        if len(candidates) == 1:
            return next(iter(candidates)), ""
        exact = [identifier for identifier in candidates if identifier.lower() == key]
        if len(exact) == 1:
            return exact[0], ""
        return None, "license 别名存在冲突，无法唯一确定: {} -> {}".format(
            token,
            "/".join(sorted(candidates)),
        )

    def classify(self, identifier):
        """返回 ``(status, reason)``。"""
        entry = self._entries.get(identifier)
        if entry is None:
            return STATUS_UNKNOWN, "未在 license 准入清单中: {}".format(identifier)
        if entry["black"]:
            return STATUS_BLACK, entry["blackReason"] or "禁止使用"
        if entry["oeApproved"]:
            return STATUS_ALLOWED, ""
        if entry["lowRisk"]:
            return STATUS_RESTRICTED, "oE 受限使用，需合规 SIG 评审"
        if entry["exception"]:
            return STATUS_UNKNOWN, "例外条款只能通过 WITH 与基础 license 搭配使用"
        return STATUS_UNKNOWN, "未获得 oE 认可"

    def evaluate(self, expression):
        """解析并判定 SPDX license 表达式。"""
        expression = normalize_expression(expression)
        if not expression:
            return LicenseVerdict(STATUS_MISSING, reasons=["未声明 license"])
        try:
            node = _ExpressionParser(expression).parse()
        except LicenseExpressionError as exc:
            return LicenseVerdict(
                STATUS_UNKNOWN,
                expression=expression,
                reasons=[str(exc)],
            )
        status, reasons = self._evaluate_node(node)
        return LicenseVerdict(status, expression=expression, reasons=reasons)

    def identifiers_in(self, expression):
        """提取表达式中出现的基础 license identifier（忽略 WITH 例外）。"""
        expression = normalize_expression(expression)
        if not expression:
            return []
        try:
            node = _ExpressionParser(expression).parse()
        except LicenseExpressionError:
            return []
        result = []

        def walk(current):
            kind = current[0]
            if kind == "license":
                identifier, _error = self.resolve(current[1])
                if identifier and identifier not in result:
                    result.append(identifier)
            elif kind == "with":
                walk(current[1])
            else:
                for child in current[1]:
                    walk(child)

        walk(node)
        return result

    def _evaluate_node(self, node):
        kind = node[0]
        if kind == "license":
            identifier, error = self.resolve(node[1])
            if identifier is None:
                return STATUS_UNKNOWN, [error]
            status, reason = self.classify(identifier)
            return status, [reason] if reason else []
        if kind == "with":
            base_status, base_reasons = self._evaluate_node(node[1])
            exception_token = node[2]
            exception_id, error = self.resolve(exception_token)
            if base_status != STATUS_ALLOWED:
                return base_status, base_reasons
            if exception_id is None:
                return STATUS_UNKNOWN, [error]
            exception_entry = self._entries[exception_id]
            if not exception_entry["exception"] or exception_entry["black"]:
                return STATUS_UNKNOWN, [
                    "不是有效的 license 例外条款: {}".format(exception_token),
                ]
            return STATUS_ALLOWED, []
        statuses = []
        reasons = []
        for child in node[1]:
            status, child_reasons = self._evaluate_node(child)
            statuses.append(status)
            reasons.extend(child_reasons)
        if kind == "and":
            if all(status == STATUS_ALLOWED for status in statuses):
                return STATUS_ALLOWED, []
            return _worse(statuses), reasons
        # OR：任一分支允许即可
        if STATUS_ALLOWED in statuses:
            return STATUS_ALLOWED, []
        return _worse(statuses), reasons

    def match_text(self, text):
        """从 license 文件正文中识别 license，返回 identifier 列表。"""
        normalized = re.sub(r"\s+", " ", (text or "").lower())
        if not normalized:
            return []
        matches = []
        for alias, identifier in self._content_aliases:
            if identifier in matches:
                continue
            if len(alias) < 8:
                pattern = r"(?<![a-z0-9]){}(?![a-z0-9])".format(re.escape(alias))
                if not re.search(pattern, normalized):
                    continue
            elif alias not in normalized:
                continue
            matches.append(identifier)
            if len(matches) >= 3:
                break
        return matches


class _ExpressionParser(object):
    """最小 SPDX 表达式解析器：license / AND / OR / WITH / 括号。"""

    MAX_TOKENS = 200

    def __init__(self, expression):
        self._tokens = _TOKEN_RE.findall(expression)
        if not self._tokens or len(self._tokens) > self.MAX_TOKENS:
            raise LicenseExpressionError("license 表达式为空或过长")
        self._pos = 0

    def parse(self):
        node = self._parse_or()
        if self._pos != len(self._tokens):
            raise LicenseExpressionError(
                "license 表达式存在无法解析的内容: {}".format(
                    " ".join(self._tokens[self._pos:]),
                )
            )
        return node

    def _peek(self):
        return self._tokens[self._pos].upper() if self._pos < len(self._tokens) else None

    def _take(self):
        token = self._tokens[self._pos]
        self._pos += 1
        return token

    def _parse_or(self):
        node = self._parse_and()
        children = [node]
        while self._peek() == "OR":
            self._take()
            children.append(self._parse_and())
        return ("or", children) if len(children) > 1 else node

    def _parse_and(self):
        node = self._parse_with()
        children = [node]
        while self._peek() == "AND":
            self._take()
            children.append(self._parse_with())
        return ("and", children) if len(children) > 1 else node

    def _parse_with(self):
        node = self._parse_atom()
        while self._peek() == "WITH":
            self._take()
            exception = self._parse_atom()
            if exception[0] != "license":
                raise LicenseExpressionError("WITH 后必须是 license 例外名称")
            node = ("with", node, exception[1])
        return node

    def _parse_atom(self):
        token = self._peek()
        if token is None:
            raise LicenseExpressionError("license 表达式不完整")
        if token == "(":
            self._take()
            node = self._parse_or()
            if self._peek() != ")":
                raise LicenseExpressionError("license 表达式括号不匹配")
            self._take()
            return node
        if token in ("AND", "OR", "WITH", ")"):
            raise LicenseExpressionError("license 表达式缺少 license 名称")
        return ("license", self._take())


class LicenseScanner(object):
    """扫描 skill 目录及仓库根目录下的 license 信息。"""

    MAX_FILES = 20
    MAX_FILE_SIZE = 1024 * 1024
    MAX_HEADER_CHARS = 8192

    def __init__(self, access):
        self._access = access

    def scan(self, repo_root, skill_dir, declared=None):
        repo_root = Path(repo_root).resolve()
        skill_dir = Path(skill_dir).resolve()
        declared_expression = normalize_expression(declared)

        files = self._find_license_files(repo_root, skill_dir)
        sources = [self._relative(path, repo_root) for path in files]
        detected = {}
        for path in files:
            text = self._read_text(path)
            if not text:
                continue
            relative = self._relative(path, repo_root)
            for identifier in self._detect(path, text):
                detected.setdefault(identifier, []).append(relative)

        if declared_expression:
            verdict = self._access.evaluate(declared_expression)
            verdict.sources = sources or ["SKILL.md frontmatter"]
            conflict = self._conflict_reason(declared_expression, detected)
            if conflict and verdict.status == STATUS_ALLOWED:
                return LicenseVerdict(
                    STATUS_CONFLICT,
                    expression=declared_expression,
                    sources=sources,
                    reasons=[conflict],
                )
            if conflict:
                verdict.reasons.append(conflict)
            return verdict

        if not detected:
            if files:
                return LicenseVerdict(
                    STATUS_UNKNOWN,
                    sources=sources,
                    reasons=[
                        "无法从 license 文件识别具体 license，请在 SKILL.md 中声明 SPDX license"
                    ],
                )
            return LicenseVerdict(
                STATUS_MISSING,
                sources=sources,
                reasons=["未在 SKILL.md frontmatter 或 license 文件中找到 license 声明"],
            )

        # 多个 license 文件无法判断是 AND 还是 OR，按 AND 保守处理
        expression = " AND ".join(sorted(detected))
        verdict = self._access.evaluate(expression)
        verdict.sources = sources
        return verdict

    def _conflict_reason(self, declared_expression, detected):
        declared_ids = set(self._access.identifiers_in(declared_expression))
        if not declared_ids or not detected:
            return ""
        detected_ids = set(detected)
        if not declared_ids & detected_ids:
            return "SKILL.md 声明的 license '{}' 与 license 文件检测结果 '{}' 不一致".format(
                declared_expression,
                "/".join(sorted(detected_ids)),
            )
        extra = detected_ids - declared_ids
        for identifier in sorted(extra):
            status, _reason = self._access.classify(identifier)
            if status != STATUS_ALLOWED:
                return "license 文件包含声明之外的 {}（{}），存在合规风险".format(
                    identifier,
                    status,
                )
        return ""

    def _find_license_files(self, repo_root, skill_dir):
        # 从 skill 目录向上逐级查找，兼容仓库根目录或一级子目录放 LICENSE 的常见布局
        current = skill_dir
        while True:
            files = self._license_files_in(current, repo_root)
            if files:
                return files[: self.MAX_FILES]
            if current == repo_root:
                break
            try:
                current.relative_to(repo_root)
            except ValueError:
                break
            if current.parent == current:
                break
            current = current.parent
        return []

    def _license_files_in(self, directory, repo_root):
        if not directory.is_dir():
            return []
        candidates = []
        for path in sorted(directory.iterdir()):
            if path.is_file() and _LICENSE_FILE_RE.match(path.name):
                candidates.append(path)
        licenses_dir = directory / "LICENSES"
        if licenses_dir.is_dir():
            for path in sorted(licenses_dir.iterdir()):
                if path.is_file():
                    candidates.append(path)
        result = []
        for path in candidates:
            if path.is_symlink():
                try:
                    path.resolve().relative_to(repo_root)
                except ValueError:
                    continue
            if path.stat().st_size > self.MAX_FILE_SIZE:
                logger.warning("license file too large, skip: %s", path)
                continue
            result.append(path)
        return result

    @staticmethod
    def _relative(path, repo_root):
        try:
            return path.relative_to(repo_root).as_posix()
        except ValueError:
            return str(path)

    @staticmethod
    def _read_text(path):
        try:
            data = path.read_bytes()[: LicenseScanner.MAX_FILE_SIZE]
        except OSError as exc:
            logger.warning("read license file %s failed: %s", path, exc)
            return ""
        if data.startswith((b"\xff\xfe", b"\xfe\xff")):
            return data.decode("utf-16", errors="replace")
        encoding = "utf-8"
        if chardet is not None:
            detected = chardet.detect(data).get("encoding")
            if detected:
                encoding = detected
        try:
            return data.decode(encoding, errors="replace")
        except (LookupError, UnicodeDecodeError):
            return data.decode("utf-8", errors="replace")

    def _detect(self, path, text):
        identifiers = []

        # REUSE：LICENSES/<SPDX>.txt 文件名即 license identifier
        if path.parent.name.lower() == "licenses":
            identifier, _error = self._access.resolve(path.stem)
            if identifier and not self._access.is_nonstandard(identifier):
                identifiers.append(identifier)

        filename_token = self._filename_token(path)
        if filename_token:
            identifier, _error = self._access.resolve(filename_token)
            # LICENSE-APACHE / LICENSE-GPL 这类文件名过于宽泛，交给正文识别具体版本
            if identifier and not self._access.is_nonstandard(identifier) and identifier not in identifiers:
                identifiers.append(identifier)

        header = text[: self.MAX_HEADER_CHARS]
        for match in _SPDX_HEADER_RE.findall(header):
            for identifier in self._access.identifiers_in(match):
                if identifier not in identifiers:
                    identifiers.append(identifier)

        normalized = re.sub(r"\s+", " ", text[: self.MAX_HEADER_CHARS])
        for identifier, patterns in _TEXT_SIGNATURES:
            if all(re.search(pattern, normalized, re.IGNORECASE) for pattern in patterns):
                if identifier not in identifiers:
                    identifiers.append(identifier)
                break

        if not identifiers:
            identifiers = self._access.match_text(header)
        return identifiers

    @staticmethod
    def _filename_token(path):
        name = path.stem
        if path.parent.name.lower() == "licenses":
            return name
        lowered = name.lower()
        for prefix in ("license", "licence", "copying", "unlicense"):
            if lowered.startswith(prefix):
                name = name[len(prefix):]
                break
        lowered = name.lower()
        for suffix in ("license", "licence", "copying", "unlicense"):
            if lowered.endswith(suffix):
                name = name[:-len(suffix)]
                break
        return re.sub(r"^[-._\s]+|[-._\s]+$", "", name)
