# -*- encoding=utf-8 -*-
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
# Description: wittyhub skill 安全审计门禁
# **********************************************************************************
import ipaddress
import logging
import os
import re
import shutil
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

import requests
import yaml

from src.ac.framework.ac_base import BaseCheck
from src.ac.framework.ac_result import SUCCESS, WARNING, ACResult
from src.proxy.git_proxy import GitProxy

# git 可执行文件绝对路径（运行时解析，兼容不同镜像），避免依赖 PATH 查找
GIT_BIN = shutil.which("git") or "git"

logger = logging.getLogger("ac")


class CheckWittyhubAudit(BaseCheck):
    """对 openEuler-skills 仓库的 PR 执行 wittyhub 安全审计门禁。

    审计目标（调用 wittyhub audit-by-url，不要求 skill 已入库）：
    - skill.yaml 的 skill_repos[].url 变更 -> 克隆仓库逐 SKILL.md 审计，发现失败回退整仓库
    - skill.yaml 的 skills[].skill_url 变更 -> 扫单个 skill
    - 直接上传的 */SKILL.md -> 扫 PR 头分支中的该 skill
    评论：表格展示每个 skill 的名称、风险等级、风险分数与 report.md 下载链接。
    汇总（ac.yaml 可用 block_levels/warn_levels 覆盖）：命中 block_levels（默认
    critical/high）-> WARNING（谨慎合入，不阻断）；命中 warn_levels（默认 medium）、
    结果 unknown 或审计失败 -> WARNING；其余 SUCCESS。
    """

    SKILL_YAML_NAME = "skill.yaml"
    SKILL_MD_NAME = "SKILL.md"
    DEFAULT_BLOCK_LEVELS = ("critical", "high")
    DEFAULT_WARN_LEVELS = ("medium",)
    # 与 wittyhub validate_git_url 白名单一致：仅允许公开代码托管域名，clone 前先校验防 SSRF
    ALLOWED_GIT_HOSTS = frozenset({
        "github.com", "gitlab.com", "bitbucket.org", "gitea.io",
        "gitee.com", "gitcode.com", "codeberg.org", "git.sr.ht",
    })
    # 与 skillcrawler.should_skip_relative_path 一致：跳过样本/模板/测试/文档目录
    SKIP_SAMPLE_DIRS = frozenset({
        "template", "templates", "example", "examples",
        "demo", "demos", "test", "tests",
        "fixture", "fixtures", "docs", "doc",
        "archive", "archives", "legacy",
    })
    MAX_COMMENT_CHARS = 60000      # 评论总长上限
    MAX_TARGETS = 100              # 单次 PR 审计目标上限，超过则跳过审计、评论提示人工审核
    POLL_TOTAL_TIMEOUT = 1200      # 轮询总超时（秒，20 分钟），可用 WITTYHUB_AUDIT_TIMEOUT 覆盖
    POLL_REQUEST_TIMEOUT = 10      # 单个 skill 单次查询请求超时（秒）
    POLL_INTERVAL = 10             # 两轮轮询之间的间隔（秒）
    MAX_TRIGGER_WORKERS = 20       # 触发阶段并发上限（Jenkins 多 executor 并行跑扫描）
    # 风险等级标签 -> 背景色（黑色字体），安全到高风险：绿/黄/橙/红；未检测用灰
    RISK_LEVEL_STYLE = {
        "安全": "#67C23A",
        "低风险": "#F7BA2A",
        "中风险": "#FF9800",
        "高风险": "#F56C6C",
        "未检测": "#909399",
    }

    def __init__(self, workspace, repo, conf=None):
        super(CheckWittyhubAudit, self).__init__(workspace, repo, conf)
        self._kwargs = {}
        self._community = None
        self._pr_url = None
        self._pr_num = None
        self._access_token = None
        self._platform = None
        self._api_url = ""
        self._admin_token = ""
        conf = conf or {}
        self._block_levels = tuple(conf.get("block_levels") or self.DEFAULT_BLOCK_LEVELS)
        self._warn_levels = tuple(conf.get("warn_levels") or self.DEFAULT_WARN_LEVELS)
        try:
            self._poll_timeout = float(
                conf.get("poll_timeout") or os.environ.get("WITTYHUB_AUDIT_TIMEOUT") or self.POLL_TOTAL_TIMEOUT
            )
        except (TypeError, ValueError):
            self._poll_timeout = self.POLL_TOTAL_TIMEOUT
        try:
            self._poll_interval = float(conf.get("poll_interval") or self.POLL_INTERVAL)
        except (TypeError, ValueError):
            self._poll_interval = self.POLL_INTERVAL

    def __call__(self, *args, **kwargs):
        logger.info("check %s wittyhub audit ...", self._repo)
        self._kwargs = kwargs
        common_args = kwargs.get("common_args", {})
        self._community = common_args.get("community", "")
        self._pr_url = common_args.get("pr_url", "")
        self._pr_num = common_args.get("pr_num", "")
        self._access_token = common_args.get("access_token", "")
        self._platform = common_args.get("platform", "gitcode")
        return self.start_check_with_order("audit")

    def check_audit(self):
        try:
            return self._do_check()
        except Exception as exc:  # 门禁自身异常不要静默通过，转为告警
            logger.exception("wittyhub audit internal error: %s", exc)
            return ACResult(WARNING.val, details=["WittyHub 审计检查内部错误: {}".format(str(exc)[:200])])

    def _do_check(self):
        if not all([self._community, self._pr_num]):
            logger.warning("wittyhub audit skipped: missing community/pr_num")
            return SUCCESS

        self._api_url = os.environ.get("WITTYHUB_API_URL", "").rstrip("/")
        self._admin_token = os.environ.get("WITTYHUB_ADMIN_TOKEN", "")
        if not self._api_url or not self._admin_token:
            logger.warning("wittyhub audit skipped: WITTYHUB_API_URL / WITTYHUB_ADMIN_TOKEN not configured")
            return SUCCESS

        diff_files = self.get_pr_changed_files()
        if diff_files is None:
            diff_files = GitProxy(self._work_dir).diff_files_between_commits("HEAD~1", "HEAD~0") or []
        if not diff_files:
            return SUCCESS

        targets = self._collect_targets(diff_files)
        if not targets:
            return SUCCESS
        # 目标数上限保护：超过 MAX_TARGETS 个 skill 时不做自动化审计，评论提示人工审核
        if len(targets) > self.MAX_TARGETS:
            logger.warning("wittyhub audit skipped: %d targets exceed %d", len(targets), self.MAX_TARGETS)
            self._comment_skip(len(targets))
            return SUCCESS
        logger.info("wittyhub audit targets: %s", targets)

        # 两阶段执行：先并发触发所有目标扫描（Jenkins 并行跑），再统一轮询
        pending = []  # [(build_number, target)]
        failed_details = []
        with ThreadPoolExecutor(max_workers=min(len(targets), self.MAX_TRIGGER_WORKERS)) as executor:
            # future->target 映射：即使某个触发抛异常，也能定位到是哪个目标失败
            future_to_target = {executor.submit(self._trigger_one, target): target for target in targets}
            for future in as_completed(future_to_target):
                target = future_to_target[future]
                try:
                    build_number = future.result()
                except Exception as exc:
                    logger.warning("wittyhub audit trigger exception: %s", exc)
                    build_number = None
                if build_number is None:
                    failed_details.append("审计失败: {}".format(target.get("desc", target.get("url", ""))))
                else:
                    pending.append((build_number, target))

        # 轮询阶段：串行轮询，逐个 skill 单次查询（请求超时 10s），查不到就换下一个，
        # 下一轮继续；总超时（默认 20 分钟）到点后未完成目标按审计失败告警
        audits = []
        deadline = time.monotonic() + self._poll_timeout
        pending_targets = pending
        while pending_targets and time.monotonic() < deadline:
            next_round = []
            for build_number, target in pending_targets:
                if time.monotonic() >= deadline:
                    break
                status, result = self._poll_once(build_number, target)
                if status == "done":
                    audits.append(result)
                elif status == "error":
                    failed_details.append("审计失败: {}".format(target.get("desc", target.get("url", ""))))
                else:
                    next_round.append((build_number, target))
            pending_targets = next_round
            if pending_targets and time.monotonic() < deadline:
                time.sleep(self._poll_interval)
        for build_number, target in pending_targets:
            failed_details.append("审计失败: {}".format(target.get("desc", target.get("url", ""))))

        details = []
        block_hit = False
        warn_hit = False
        for item in audits:
            level = (item.get("risk_level") or "unknown").lower()
            desc = item.get("desc", "")
            score = item.get("risk_score")
            details.append(
                "{}: risk_level={}{}".format(desc, level, ", score={}".format(score) if score is not None else "")
            )
            if level in self._block_levels:
                block_hit = True
            elif level in self._warn_levels or level == "unknown":
                warn_hit = True
        if failed_details:
            warn_hit = True
        details.extend(failed_details)

        self._comment_summary(audits, failed_details, block_hit, warn_hit)

        if block_hit:
            details.insert(0, "存在 {} 风险的 skill，请谨慎合入".format("/".join(self._block_levels)))
            return ACResult(WARNING.val, details=details)
        if warn_hit:
            details.insert(0, "安全审计有风险提示（medium 或审计失败），请确认后合入")
            return ACResult(WARNING.val, details=details)
        return SUCCESS

    def _collect_targets(self, diff_files):
        targets = []
        skill_yamls = [
            f for f in diff_files
            if f == self.SKILL_YAML_NAME or f.endswith("/" + self.SKILL_YAML_NAME)
        ]
        # 条目粒度：按 skill.yaml 的行级 patch 提取本次新增的具体 URL 只审计这些目标
        # （skill_repos 的 url -> 整仓库，skills 的 skill_url -> 单个 skill）；无法定位到
        # 具体 URL（patch 缺失/解析失败）时回退为全量审计，宁多勿漏。
        changed = self._skill_yaml_changed_fields(skill_yamls)
        for yaml_file in skill_yamls:
            content = self._load_yaml(os.path.join(self._work_dir, yaml_file))
            if not content:
                continue
            repo_urls, skill_urls = changed.get(yaml_file, ({}, {}))
            if repo_urls is not None:
                if repo_urls:
                    # 直接审计 patch 中新增的具体仓库 URL；内容中有对应条目时保留其 branch
                    entry_branches = {
                        (entry or {}).get("url"): (entry or {}).get("branch") or ""
                        for entry in content.get("skill_repos") or []
                        if (entry or {}).get("url")
                    }
                    for url in sorted(repo_urls):
                        targets.extend(self._repo_targets(url, entry_branches.get(url, "")))
                else:
                    # 空集合：字段被改动但未定位到具体 URL -> 全量审计该字段
                    for repo_entry in content.get("skill_repos") or []:
                        url = (repo_entry or {}).get("url") or ""
                        if url:
                            targets.extend(self._repo_targets(url, (repo_entry or {}).get("branch") or ""))
            if skill_urls is not None:
                if skill_urls:
                    for url in sorted(skill_urls):
                        targets.append(self._skill_target(url))
                else:
                    # 空集合：字段被改动但未定位到具体 URL -> 全量审计该字段
                    for skill_entry in content.get("skills") or []:
                        url = (skill_entry or {}).get("skill_url") or ""
                        if url:
                            targets.append(self._skill_target(url))

        uploaded_skills = [
            f for f in diff_files
            if f == self.SKILL_MD_NAME or f.endswith("/" + self.SKILL_MD_NAME)
        ]
        if uploaded_skills:
            head_url, head_ref = self._pr_head()
            for skill_file in uploaded_skills:
                targets.append({
                    "type": "pr_skill",
                    "url": skill_file,
                    "name": self._skill_name_from_file_path(skill_file),
                    "head_url": head_url,
                    "head_ref": head_ref,
                    "desc": "PR 上传 skill 文件: {}".format(skill_file),
                })
        return targets

    def _skill_target(self, url):
        """单个 skill 审计目标（desc 用于日志/评论展示）。"""
        name = self._skill_name_from_url(url)
        return {"type": "skill", "url": url, "name": name, "desc": "skill: {}".format(name)}

    def _repo_targets(self, repo_url, branch):
        """新增 skill 仓库展开为逐 skill 审计目标（与 skillcrawler 一致）；
        发现失败回退为整仓库审计（1 个目标），保证不静默通过。"""
        discovered = self._discover_repo_skills(repo_url, branch)
        if discovered:
            return [
                {
                    "type": "skill",
                    "url": item["skill_url"],
                    "name": item["name"],
                    "desc": "skill: {}".format(item["name"] or item["skill_url"]),
                }
                for item in discovered
            ]
        return [{
            "type": "repo",
            "url": repo_url,
            "branch": branch,
            "name": repo_url,
            "desc": "skill 仓库: {}".format(repo_url),
        }]

    def _discover_repo_skills(self, repo_url, branch):
        """克隆仓库并按 skillcrawler 相同逻辑发现其中的 SKILL.md。

        返回 ``[{"name": str, "skill_url": str}]``；克隆/发现失败返回 None
        （由 ``_repo_targets`` 回退为整仓库审计）。
        """
        # SSRF 防护：clone 前校验 URL 在白名单内，防止 PR 提交者探测内网/私网
        if not self._validate_git_url(repo_url):
            logger.warning("discover skills: rejected URL by SSRF guard: %s", repo_url)
            return None
        env = dict(os.environ)
        env.update({
            "GIT_TERMINAL_PROMPT": "0",
            "GCM_INTERACTIVE": "Never",
            "GIT_LFS_SKIP_SMUDGE": "1",  # 跳过 LFS 大文件，只取文件树
        })
        tmpdir = None
        try:
            tmpdir = tempfile.mkdtemp(prefix="wittyhub-scan-")
            clone_url = repo_url if (repo_url or "").endswith(".git") else "{}".format(repo_url) + ".git"
            command = [GIT_BIN, "clone", "--depth", "1"]
            if branch:
                command.extend(["--branch", branch])
            command.extend([clone_url, tmpdir])
            proc = subprocess.run(command, capture_output=True, text=True, env=env, timeout=120)
            if proc.returncode != 0:
                logger.warning("discover skills: clone %s failed: %s", repo_url, (proc.stderr or "").strip()[-500:])
                return None
            repo_root = Path(tmpdir)
            resolved_branch = branch or self._git_checked_out_branch(repo_root)
            base_url = self._normalize_repo_browse_url(repo_url)
            if not base_url or not resolved_branch:
                logger.warning("discover skills: cannot resolve base/branch for %s", repo_url)
                return None
            # wittyhub 的 skill_url 不支持 ref 含 '/'（如 release/2.0 会被拆错），逐 skill
            # 无法正确审计；回退整仓库审计（repo 模式把 branch 原样传 git 可处理斜杠分支）
            if "/" in resolved_branch:
                logger.warning(
                    "discover skills: branch %s contains '/', fall back to whole-repo audit for %s",
                    resolved_branch, repo_url,
                )
                return None
            skills = []
            for skill_file in sorted(repo_root.rglob(self.SKILL_MD_NAME)):
                if not skill_file.is_file():
                    continue
                relative = skill_file.relative_to(repo_root).as_posix()
                if self._should_skip_skill_path(relative):
                    continue
                skills.append({
                    "name": self._skill_display_name(skill_file),
                    "skill_url": "{}/blob/{}/{}".format(base_url, resolved_branch, relative),
                })
            return skills
        except Exception as exc:
            logger.warning("discover skills for %s failed: %s", repo_url, exc)
            return None
        finally:
            if tmpdir:
                shutil.rmtree(tmpdir, ignore_errors=True)

    @staticmethod
    def _git_checked_out_branch(repo_root):
        """clone 后 HEAD 所在分支名（即仓库默认分支）。"""
        try:
            proc = subprocess.run(
                [GIT_BIN, "-C", str(repo_root), "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True, text=True, timeout=30,
            )
        except (subprocess.SubprocessError, OSError):
            return None
        branch = proc.stdout.strip()
        return branch if branch and branch != "HEAD" else None

    @staticmethod
    def _normalize_repo_browse_url(repo_url):
        """把仓库 URL 规范化为浏览器地址（去 .git，ssh 转 https）。"""
        repo_url = (repo_url or "").strip()
        if not repo_url:
            return None
        m = re.match(r"git@([^:]+):(.+)", repo_url)
        if m:
            path = m.group(2).strip("/")
            return "https://{}/{}".format(m.group(1), path[:-4] if path.endswith(".git") else path)
        parsed = urlparse(repo_url)
        if not parsed.netloc:
            return None
        path = parsed.path.strip("/")
        if path.endswith(".git"):
            path = path[:-4]
        if not path:
            return None
        return "{}://{}/{}".format(parsed.scheme, parsed.netloc, path)

    @classmethod
    def _validate_git_url(cls, repo_url):
        """校验仓库 URL 是否为白名单公开托管地址，防止 SSRF 探测。

        与 wittyhub validate_git_url 对齐：仅白名单域名、标准端口、非私网 IP、无控制
        字符、无片段；http/https/git 拒凭据（ssh 仅拒密码）；路径先 unquote 再校验；
        ``git@``（scp-like ssh）先规范化为 https。
        """
        url = (repo_url or "").strip()
        if not url or len(url) > 2048:
            return False
        if any(ord(char) < 0x20 or ord(char) == 0x7f for char in url):
            return False
        m = re.match(r"git@([^:]+):(.+)", url)
        if m:
            url = "https://{}/{}".format(m.group(1), m.group(2).strip("/"))
        try:
            parsed = urlparse(url)
        except ValueError:
            return False
        scheme = parsed.scheme.lower()
        if scheme not in ("http", "https", "git", "ssh"):
            return False
        if parsed.fragment:
            return False
        if scheme in ("http", "https", "git") and (parsed.username or parsed.password):
            return False
        if scheme == "ssh" and parsed.password:
            return False
        try:
            hostname = (parsed.hostname or "").rstrip(".").encode("idna").decode("ascii").lower()
            port = parsed.port
        except ValueError:
            return False
        if not hostname:
            return False
        allowed_ports = {
            "http": {None, 80},
            "https": {None, 443},
            "git": {None, 9418},
            "ssh": {None, 22},
        }
        if port not in allowed_ports.get(scheme, set()):
            return False
        # 私网/环回地址直接拒绝（127.0.0.1、192.168.*、10.*）
        try:
            ip_obj = ipaddress.ip_address(hostname)
            if not ip_obj.is_global:
                return False
        except ValueError:
            pass  # 域名，走下面的白名单
        if hostname not in cls.ALLOWED_GIT_HOSTS:
            return False
        path = unquote(parsed.path).strip("/")
        if not path or path == "":
            return False
        if "\\" in path or any(part in (".", "..") for part in path.split("/")):
            return False
        return True

    @classmethod
    def _should_skip_skill_path(cls, relative_path):
        """与 skillcrawler.should_skip_relative_path 一致：跳过样本/文档/测试目录。"""
        parts = relative_path.lower().split("/")
        return any(part in cls.SKIP_SAMPLE_DIRS for part in parts[:-1])

    @staticmethod
    def _skill_display_name(skill_file):
        """skill 展示名：优先 SKILL.md frontmatter 的 name，否则取父目录名。"""
        try:
            text = skill_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        if text.lstrip().startswith("---") and text.count("---") >= 2:
            body = text.split("---", 2)[1]
            for line in body.splitlines():
                stripped = line.strip()
                if stripped.startswith("name:"):
                    name = stripped[len("name:"):].strip().strip("\"'")
                    if name:
                        return name
        return skill_file.parent.name or "SKILL.md"

    @staticmethod
    def _skill_name_from_url(skill_url):
        """从 SKILL.md blob URL 推导 skill 展示名（取 blob/<ref> 之后的目录段）。"""
        url = (skill_url or "").split("?", 1)[0].split("#", 1)[0].rstrip("/")
        parts = url.split("/")
        if parts and parts[-1] == "SKILL.md":
            parts = parts[:-1]
        if "blob" in parts:
            tail = parts[parts.index("blob") + 2:]
            if tail:
                return tail[-1]
        return skill_url

    @staticmethod
    def _skill_name_from_file_path(skill_file):
        """从 PR 上传的 SKILL.md 文件路径推导展示名（取父目录名）。"""
        parts = (skill_file or "").strip("/").split("/")
        if len(parts) >= 2:
            return parts[-2]
        return skill_file

    def _skill_yaml_changed_fields(self, skill_yamls):
        """解析 PR 中每个 skill.yaml 的行级 patch，返回 {yaml_file: (repo_urls, skill_urls)}。

        ``(repo_urls, skill_urls)`` 语义见 ``_fields_changed_by_patch``；无法获取
        patch 时对应文件回退为 ({}, {})（两字段全量审计，保守不漏）。
        """
        result = {}
        pr_files = []
        try:
            from src.proxy.gitcode_proxy import GitcodeProxy
            files = GitcodeProxy(self._community, self._repo, self._access_token).get_pr_files(self._pr_num) or []
            if isinstance(files, list):
                pr_files = files
        except Exception as exc:
            logger.warning("get skill.yaml patch failed, fallback to whole-file audit: %s", exc)

        patches = {}
        for f in pr_files:
            if not isinstance(f, dict):
                continue
            name = f.get("filename") or ""
            raw_patch = f.get("patch")
            if isinstance(raw_patch, dict):
                patch = raw_patch.get("diff") or ""  # GitCode 返回 {"diff": "<unified diff>"}
            elif isinstance(raw_patch, str):
                patch = raw_patch
            else:
                patch = ""
            if name and patch:
                patches[name] = patch

        for yaml_file in skill_yamls:
            patch = patches.get(yaml_file)
            if patch:
                try:
                    result[yaml_file] = self._fields_changed_by_patch(patch)
                except Exception as exc:
                    logger.warning("parse skill.yaml patch failed, fallback to whole-file audit: %s", exc)
                    result[yaml_file] = ({}, {})
            else:
                result[yaml_file] = ({}, {})
        return result

    # skill_repos 列表项形如 "- url: ..."，skills 元素形如 "  skill_url: ..."
    _REPO_URL_RE = re.compile(r"^- url:")
    _SKILL_URL_RE = re.compile(r"^skill_url:")

    @classmethod
    def _fields_changed_by_patch(cls, patch):
        """按 unified diff 的新增行（'+'）提取本次新增的具体审计目标 URL。

        - 新增 ``- url: <x>``（skill_repos 条目）-> 只审计仓库 x
        - 新增 ``skill_url: <y>``（skills 元素）-> 只审计 skill y
        - 仅新增 ``skill_repos:`` / ``skills:`` 段头而未定位到具体 URL 时，返回空集合表示该字段全量审计

        返回 ``(repo_urls, skill_urls)``：None 表示字段未被改动（不审计），空集合
        表示字段被改动但未定位到具体 URL（全量审计）。
        """
        repo_urls = None
        skill_urls = None
        for raw in patch.splitlines():
            if not raw.startswith("+"):
                continue
            stripped = raw[1:].strip()
            if stripped == "skill_repos:":
                if repo_urls is None:
                    repo_urls = set()
            elif stripped == "skills:":
                if skill_urls is None:
                    skill_urls = set()
            elif cls._REPO_URL_RE.match(stripped):
                if repo_urls is None:
                    repo_urls = set()
                url = cls._extract_url_value(stripped[len("- url:"):])
                if url:
                    repo_urls.add(url)
            elif cls._SKILL_URL_RE.match(stripped):
                if skill_urls is None:
                    skill_urls = set()
                url = cls._extract_url_value(stripped[len("skill_url:"):])
                if url:
                    skill_urls.add(url)
        return repo_urls, skill_urls

    @staticmethod
    def _extract_url_value(raw):
        """提取 URL 值：去首尾空白与引号，并按 '#' 截断行尾 YAML 注释。"""
        url = raw.strip().strip("'\"")
        if not url:
            return ""
        return url.split("#", 1)[0].rstrip()

    @staticmethod
    def _unwrap_response(body):
        """兼容 wittyhub 的 {code, msg, data} 信封包装，返回 data 内容（未包装原样返回）。"""
        if isinstance(body, dict) and isinstance(body.get("data"), dict):
            return body["data"]
        return body

    def _pr_head(self):
        """获取 PR 头分支的仓库 URL 与 ref（GitCode PR 信息）。"""
        try:
            from src.proxy.gitcode_proxy import GitcodeProxy
            info = GitcodeProxy(self._community, self._repo, self._access_token).get_pr_info(self._pr_num) or {}
        except Exception as exc:
            logger.warning("get pr info failed: %s", exc)
            return "", ""
        head = info.get("head") or {}
        ref = head.get("ref") or ""
        repo = head.get("repo") or {}
        html_url = repo.get("html_url") or ""
        if not html_url:
            full_name = repo.get("full_name") or ""
            if full_name:
                html_url = "https://gitcode.com/{}".format(full_name)
        if not html_url:
            html_url = "https://gitcode.com/{}/{}".format(self._community, self._repo)  # 同仓库 PR 时用目标仓库兜底
        return html_url, ref

    def _headers(self):
        """调用 wittyhub API 的鉴权头。"""
        return {"Authorization": "Bearer {}".format(self._admin_token), "Content-Type": "application/json"}

    def _audit_one(self, target):
        """兼容封装：触发并轮询单个目标直到出结果或总超时（供单目标场景直接使用）。"""
        build_number = self._trigger_one(target)
        if build_number is None:
            return None
        deadline = time.monotonic() + self._poll_timeout
        while time.monotonic() < deadline:
            status, result = self._poll_once(build_number, target)
            if status != "pending":
                return result
            time.sleep(self._poll_interval)
        logger.error("wittyhub audit build %s timed out after %.0fs", build_number, self._poll_timeout)
        return None

    def _trigger_one(self, target):
        """触发一次 audit-by-url 异步扫描，返回 Jenkins build_number；失败返回 None。

        触发是秒级返回，调用方应先把所有目标都触发完再统一轮询，让 Jenkins 的
        多 executor 并行跑各 skill 扫描。
        """
        ttype = target.get("type")
        if ttype == "repo":
            payload = {"repo_url": target["url"]}
            if target.get("branch"):
                payload["branch"] = target["branch"]
        elif ttype == "skill":
            payload = {"skill_url": target["url"]}
        elif ttype == "pr_skill":
            if not target.get("head_url") or not target.get("head_ref"):
                logger.warning("no PR head info for %s, skip", target.get("url"))
                return None
            # wittyhub 的 skill_url（.../blob/<ref>/<path>）不支持 ref 含 '/'（如
            # feature/ai-skill 会被拆错），也无法用 commit SHA 代替（git fetch <sha>
            # 需服务端允许未通告对象）；显式跳过并告警，保守不静默。
            if "/" in target["head_ref"]:
                logger.warning(
                    "PR head ref %s contains '/', cannot build a parseable skill_url; skip %s",
                    target["head_ref"], target.get("url"),
                )
                return None
            payload = {
                "skill_url": "{}/blob/{}/{}".format(
                    target["head_url"].rstrip("/"), target["head_ref"], target["url"].lstrip("/")
                )
            }
        else:
            return None

        # 异步触发：async_mode=true 立即返回 build_number，避免网关长连接超时（504）
        trigger_url = "{}/api/v1/skills/audit-by-url".format(self._api_url)
        trigger_payload = dict(payload)
        trigger_payload["async_mode"] = True
        try:
            # 触发很快，read 超时无需太长
            resp = requests.post(
                trigger_url, json=trigger_payload, headers=self._headers(), timeout=(30, 60)
            )
        except requests.RequestException as exc:
            logger.error("wittyhub audit trigger failed: %s", exc)
            return None
        if resp.status_code != 200:
            logger.error("wittyhub audit trigger returned %s: %s", resp.status_code, resp.text[:300])
            return None
        data = self._unwrap_response(resp.json())
        details = data.get("details") or {}
        build_number = details.get("skillspector_build_number")
        if not build_number:
            logger.error("wittyhub audit trigger missing build_number: %s", resp.text[:300])
            return None
        logger.info("wittyhub audit triggered: build_number=%s target=%s", build_number, target.get("desc", ""))
        return build_number

    def _poll_once(self, build_number, target):
        """单个 build 单次查询审计结果（请求超时 POLL_REQUEST_TIMEOUT=10s）。

        返回 (status, result)：
        - ("done", dict) 拿到审计结果
        - ("error", None) 审计失败（status=error）
        - ("pending", None) 尚无结果，调用方下一轮继续轮询
        """
        result_url = "{}/api/v1/skills/audit-by-url/result?build_number={}".format(self._api_url, build_number)
        try:
            resp = requests.get(result_url, headers=self._headers(), timeout=self.POLL_REQUEST_TIMEOUT)
        except requests.RequestException as exc:
            logger.error("wittyhub audit poll failed: %s", exc)
            return "pending", None
        if resp.status_code != 200:
            logger.error("wittyhub audit poll returned %s: %s", resp.status_code, resp.text[:300])
            return "pending", None
        rdata = self._unwrap_response(resp.json())
        status = rdata.get("status")
        if status == "done":
            rdetails = rdata.get("details") or {}
            signals = [
                {
                    "severity": (sig.get("severity") or "unknown").lower(),
                    "name": sig.get("name", ""),
                    "description": sig.get("description", ""),
                }
                for sig in rdata.get("risk_signals") or []
            ]
            return "done", {
                "name": target.get("name") or target.get("desc", ""),
                "desc": target.get("desc", ""),
                "risk_level": rdata.get("risk_level"),
                "risk_score": rdata.get("risk_score"),
                "risk_signals": signals,
                "report_md": rdetails.get("skillspector_report_md"),
                "build_number": build_number,
            }
        if status == "error":
            logger.error("wittyhub audit build %s error: %s", build_number, rdata.get("error", ""))
            return "error", None
        return "pending", None

    def _comment_skip(self, count):
        """目标数超过上限时评论：不做自动化安全审计，请人工审核。"""
        try:
            from src.proxy.gitcode_proxy import GitcodeProxy
            gitcode_proxy = GitcodeProxy(self._community, self._repo, self._access_token)
        except Exception as exc:
            logger.warning("comment pr failed: %s", exc)
            return
        body = (
            "**SkillHub 安全审计门禁**\n\n"
            "本次 PR 涉及 {} 个 skill，超过单次审计目标上限（{} 个），"
            "本次不做安全审计，请人工审核。".format(count, self.MAX_TARGETS)
        )
        gitcode_proxy.comment_pr(self._pr_num, body)

    def _comment_summary(self, audits, failed_details, block_hit, warn_hit):
        try:
            from src.proxy.gitcode_proxy import GitcodeProxy
            gitcode_proxy = GitcodeProxy(self._community, self._repo, self._access_token)
        except Exception as exc:
            logger.warning("comment pr failed: %s", exc)
            return
        # 评论链接使用对外可访问的地址；未配置时回退到内部 API 地址
        report_base = (os.environ.get("WITTYHUB_PUBLIC_URL") or self._api_url).rstrip("/")

        # 结论放在表格上方，便于一眼看到门禁判定
        if block_hit:
            conclusion = "**结论: 谨慎合入（存在高风险 skill）**"
        elif warn_hit:
            conclusion = "**结论: 有风险提示（medium 或审计失败），请关注**"
        else:
            conclusion = "**结论: 通过**"

        lines = [
            "**SkillHub 安全审计门禁**",
            "审计目标数: {}".format(len(audits) + len(failed_details)),
            "",
            conclusion,
            "",
            "| skill 名称 | 风险等级 | 风险分数 | 详情链接 |",
            "| --- | --- | --- | --- |",
        ]

        # 按风险分数降序展示：分数高的在前；无分数（unknown）视为最低排最后
        ordered = sorted(
            audits,
            key=lambda item: item.get("risk_score") if item.get("risk_score") is not None else -1,
            reverse=True,
        )
        for item in ordered:
            name = item.get("name") or item.get("desc") or ""
            # 与前端一致：按风险分数映射中文等级；黑色字体 + 背景色标签（绿/黄/橙/红，
            # 未检测为灰；平台不渲染内联 style 时降级为黑色纯文本）
            level = self._risk_label(item.get("risk_score"))
            bg = self.RISK_LEVEL_STYLE.get(level, "#909399")
            level_cell = '<span style="color:#000000;background-color:{};">{}</span>'.format(bg, level)
            score = item.get("risk_score")
            score_text = "{}".format(score) if score is not None else "-"
            build_number = item.get("build_number")
            link = "-"
            if build_number:
                # report 链接文本与下载文件名均为「skill 名称 + 安全审计报告.md」
                report_name = "{}安全审计报告.md".format(name or "skill")
                link = "[{}]({}/api/v1/skills/audit-by-url/report?build_number={}&filename={})".format(
                    self._escape_table_cell(report_name), report_base, build_number, quote(report_name, safe=""),
                )
            lines.append("| {} | {} | {} | {} |".format(self._escape_table_cell(name), level_cell, score_text, link))
        for detail in failed_details:
            lines.append("| {} | 审计失败 | - | - |".format(self._escape_table_cell(detail)))

        body = "\n".join(lines)
        if len(body) > self.MAX_COMMENT_CHARS:
            body = body[:self.MAX_COMMENT_CHARS] + "\n\n... (评论过长，已截断)"
        gitcode_proxy.comment_pr(self._pr_num, body)

    @staticmethod
    def _escape_table_cell(value):
        """转义表格单元格内容，避免破坏 Markdown 表格结构。"""
        return "{}".format(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")

    @staticmethod
    def _risk_label(score):
        """与前端 getSecurityLevel 一致：按风险分数映射中文风险等级。"""
        if score is None:
            return "未检测"
        if score <= 20:
            return "安全"
        if score <= 50:
            return "低风险"
        if score <= 80:
            return "中风险"
        return "高风险"

    @staticmethod
    def _load_yaml(path):
        try:
            with open(path, "r", encoding="utf-8") as yaml_file:
                return yaml.safe_load(yaml_file) or {}
        except Exception as exc:
            logger.warning("failed to load yaml %s: %s", path, exc)
            return None
