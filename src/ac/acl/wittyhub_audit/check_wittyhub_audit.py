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
from src.ac.framework.ac_result import FAILED, SUCCESS, WARNING, ACResult
from src.proxy.git_proxy import GitProxy

# git 可执行文件绝对路径（运行时解析，兼容不同镜像），避免依赖 PATH 查找
GIT_BIN = shutil.which("git") or "git"

logger = logging.getLogger("ac")


class CheckWittyhubAudit(BaseCheck):
    """对 openEuler-skills 仓库的 PR 执行 wittyhub 安全审计门禁。

    审计目标（调用 wittyhub audit-by-url，不要求 skill 已入库）：
    - skill.yaml 的 skill_repos[].url 变更 -> 克隆仓库逐 skill 审计；clone 失败时
      不触发整仓库审计，评论「无法识别仓库，请人工审核」并返回 WARNING
    - skill.yaml 的 skills[].skill_url 变更 -> 校验 URL 与远端内容后扫单个 skill；
      远端 clone 失败时未完成内容识别，返回 WARNING
    - 直接上传的 */SKILL.md -> 校验工作区文件后扫 PR 头分支中的该 skill
    识别标准与 wittyhub src/skills 扫描器一致：文件名 SKILL.md、非跳过目录、
    frontmatter 同时声明 name/description、正文不少于 100 字符；只有识别到 skill
    才发起审计。
    评论：表格展示每个 skill 的名称、风险等级、风险分数与 report.md 下载链接；
    有 skill 相关变更但一个合法 skill 都没识别到时，评论「没有识别到 skill」并
    返回 FAILED。
    汇总（ac.yaml 可用 block_levels/warn_levels 覆盖）：命中 block_levels（默认
    critical/high）-> WARNING（谨慎合入，不阻断）；命中 warn_levels（默认 medium）、
    结果 unknown 或审计失败 -> WARNING；其余 SUCCESS。
    """

    SKILL_YAML_NAME = "skill.yaml"
    SKILL_MD_NAME = "SKILL.md"
    DEFAULT_BLOCK_LEVELS = ("critical", "high")
    DEFAULT_WARN_LEVELS = ("medium",)
    # skill 识别标准与 wittyhub src/skills 扫描器保持一致：
    # frontmatter 必须同时声明 name/description，正文长度不低于阈值
    REQUIRED_SKILL_METADATA_FIELDS = ("name", "description")
    MIN_SKILL_CONTENT_LENGTH = 100
    # 与 wittyhub validate_git_url 白名单一致：仅允许公开代码托管域名，clone 前先校验防 SSRF
    ALLOWED_GIT_HOSTS = frozenset({
        "github.com", "gitlab.com", "bitbucket.org", "gitea.io",
        "gitee.com", "gitcode.com", "atomgit.com", "codeberg.org", "git.sr.ht",
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

        collected = self._collect_targets(diff_files)
        targets = collected["targets"]
        unrecognized = collected["unrecognized"]
        if not targets:
            # PR 有明确不合规的 skill 候选：判定失败
            if collected["rejected"]:
                logger.warning("wittyhub audit: no skill recognized in PR")
                self._comment_no_skill(collected["rejected"])
                details = ["没有识别到 skill，未执行安全审计"]
                details.extend(
                    "{}: {}".format(item.get("source", ""), item.get("reason", ""))
                    for item in collected["rejected"]
                )
                return ACResult(FAILED.val, details=details)
            # 仓库/远端 clone 失败：无法识别，告警并请人工审核
            if unrecognized:
                logger.warning("wittyhub audit: unable to recognize skill source")
                self._comment_unrecognized(unrecognized)
                details = ["无法识别仓库或 skill_url，未完成内容识别，请人工审核"]
                details.extend(
                    "{}: {}".format(item.get("source", ""), item.get("reason", ""))
                    for item in unrecognized
                )
                return ACResult(WARNING.val, details=details)
            # PR 没有任何 skill 相关变更（如只改 README）：无需审计
            return SUCCESS
        # 目标数上限保护：超过 MAX_TARGETS 个 skill 时不做自动化审计，评论提示人工审核
        if len(targets) > self.MAX_TARGETS:
            logger.warning("wittyhub audit skipped: %d targets exceed %d", len(targets), self.MAX_TARGETS)
            self._comment_skip(len(targets))
            return ACResult(WARNING.val, details=["超过 {} 个 skill，本次不做安全审计，请人工审核".format(self.MAX_TARGETS)])
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
        if unrecognized:
            warn_hit = True
        details.extend(failed_details)
        details.extend(
            "无法识别仓库或 skill_url: {} ({})".format(item.get("source", ""), item.get("reason", ""))
            for item in unrecognized
        )

        self._comment_summary(
            audits, failed_details, block_hit, warn_hit,
            collected["rejected"], unrecognized,
        )

        if block_hit:
            details.insert(0, "存在 {} 风险的 skill，请谨慎合入".format("/".join(self._block_levels)))
            return ACResult(WARNING.val, details=details)
        if warn_hit:
            details.insert(0, "安全审计有风险提示（medium、审计失败或未完成内容识别），请确认后合入")
            return ACResult(WARNING.val, details=details)
        return SUCCESS

    def _collect_targets(self, diff_files):
        """收集审计目标，并记录 skill 识别结果。

        返回 ``{"targets", "candidates", "rejected", "unrecognized"}``：

        - ``targets``: 识别为合法 skill、需要审计的目标
        - ``candidates``: PR 中与 skill 相关的变更（用于判断是否应失败）
        - ``rejected``: 明确未识别为 skill 的候选及原因
        - ``unrecognized``: 无法识别（仓库 clone/发现失败），WARNING，不触发整仓库审计
        """
        targets = []
        candidates = []
        rejected = []
        unrecognized = []
        skill_yamls = [
            f for f in diff_files
            if f == self.SKILL_YAML_NAME or f.endswith("/" + self.SKILL_YAML_NAME)
        ]
        # 条目粒度：按 skill.yaml 的行级 patch 提取本次新增的具体 URL 只审计这些目标
        # （skill_repos 的 url -> 整仓库，skills 的 skill_url -> 单个 skill）；无法定位到
        # 具体 URL（patch 缺失/解析失败）时回退为全量审计，宁多勿漏。
        changed = self._skill_yaml_changed_fields(skill_yamls)
        for yaml_file in skill_yamls:
            yaml_path = os.path.join(self._work_dir, yaml_file)
            # 已删除的 skill.yaml 不参与识别，避免删除类 PR 被误判为失败
            if not os.path.isfile(yaml_path):
                continue
            content = self._load_yaml(yaml_path)
            if not isinstance(content, dict):
                candidates.append(yaml_file)
                rejected.append({
                    "source": yaml_file,
                    "reason": "skill.yaml 解析失败或内容不是映射结构",
                })
                continue
            repo_urls, skill_urls = changed.get(yaml_file, ({}, {}))
            if repo_urls is not None:
                if repo_urls:
                    # 直接审计 patch 中新增的具体仓库 URL；内容中有对应条目时保留其 branch
                    entry_branches = {
                        entry.get("url"): entry.get("branch") or ""
                        for entry in content.get("skill_repos") or []
                        if isinstance(entry, dict) and entry.get("url")
                    }
                    for url in sorted(repo_urls):
                        candidates.append(url)
                        repo_targets, repo_rejected, repo_unrecognized = self._repo_targets(
                            url, entry_branches.get(url, ""),
                        )
                        targets.extend(repo_targets)
                        rejected.extend(repo_rejected)
                        unrecognized.extend(repo_unrecognized)
                else:
                    # 空集合：字段被改动但未定位到具体 URL -> 全量识别该字段
                    for repo_entry in content.get("skill_repos") or []:
                        if not isinstance(repo_entry, dict):
                            continue
                        url = repo_entry.get("url") or ""
                        if url:
                            candidates.append(url)
                            repo_targets, repo_rejected, repo_unrecognized = self._repo_targets(
                                url, repo_entry.get("branch") or "",
                            )
                            targets.extend(repo_targets)
                            rejected.extend(repo_rejected)
                            unrecognized.extend(repo_unrecognized)
            if skill_urls is not None:
                skill_entries = {
                    entry.get("skill_url"): entry
                    for entry in content.get("skills") or []
                    if isinstance(entry, dict) and entry.get("skill_url")
                }
                if skill_urls:
                    declared = [
                        {
                            "url": url,
                            "name": (skill_entries.get(url) or {}).get("skill_name"),
                            "entry_found": url in skill_entries,
                        }
                        for url in sorted(skill_urls)
                    ]
                else:
                    # 空集合：字段被改动但未定位到具体 URL -> 全量识别该字段
                    declared = [
                        {
                            "url": url,
                            "name": entry.get("skill_name"),
                            "entry_found": True,
                        }
                        for url, entry in skill_entries.items()
                    ]
                candidates.extend(item["url"] for item in declared)
                skill_targets, skill_rejected, skill_unrecognized = self._check_declared_skill_urls(declared)
                targets.extend(skill_targets)
                rejected.extend(skill_rejected)
                unrecognized.extend(skill_unrecognized)

        uploaded_skills = [
            f for f in diff_files
            if f == self.SKILL_MD_NAME or f.endswith("/" + self.SKILL_MD_NAME)
        ]
        head_url, head_ref = None, None
        for skill_file in uploaded_skills:
            local_path = os.path.join(self._work_dir, skill_file)
            # 已删除/重命名的旧路径不在工作区：不算 skill 变更
            if not os.path.isfile(local_path):
                continue
            # 样本/模板/文档目录下的 SKILL.md 不是 skill，直接忽略
            if self._should_skip_skill_path(skill_file):
                continue
            candidates.append(skill_file)
            try:
                text = Path(local_path).read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                rejected.append({
                    "source": skill_file,
                    "reason": "文件读取失败: {}".format(exc),
                })
                continue
            reason = self._recognize_skill_text(skill_file, text)
            if reason:
                rejected.append({"source": skill_file, "reason": reason})
                continue
            if head_url is None:
                head_url, head_ref = self._pr_head()
            targets.append({
                "type": "pr_skill",
                "url": skill_file,
                "name": self._skill_display_name_from_text(
                    text, self._skill_name_from_file_path(skill_file),
                ),
                "head_url": head_url,
                "head_ref": head_ref,
                "desc": "PR 上传 skill 文件: {}".format(skill_file),
            })
        return {
            "targets": targets,
            "candidates": candidates,
            "rejected": rejected,
            "unrecognized": unrecognized,
        }

    def _skill_target(self, url, name=None):
        """单个 skill 审计目标（desc 用于日志/评论展示）。"""
        display_name = name or self._skill_name_from_url(url)
        return {"type": "skill", "url": url, "name": display_name, "desc": "skill: {}".format(display_name)}

    def _repo_targets(self, repo_url, branch):
        """新增 skill 仓库展开为逐 skill 审计目标（与 skillcrawler 一致）。

        返回 ``(targets, rejected, unrecognized)``：

        - clone 成功且识别到合法 skill -> 逐 skill 目标
        - clone 成功但没有合法 skill -> rejected（门禁失败）
        - clone/发现失败 -> unrecognized（无法识别，WARNING，不触发整仓库审计）
        """
        discovered = self._discover_repo_skills(repo_url, branch)
        if discovered is None:
            return [], [], [{
                "source": repo_url,
                "reason": "克隆仓库或识别 skill 失败，未触发整仓库审计",
            }]
        if not discovered:
            return [], [{
                "source": repo_url,
                "reason": "仓库内未识别到符合标准的 skill",
            }], []
        return [
            {
                "type": "skill",
                "url": item["skill_url"],
                "name": item["name"],
                "desc": "skill: {}".format(item["name"] or item["skill_url"]),
            }
            for item in discovered
        ], [], []

    def _discover_repo_skills(self, repo_url, branch):
        """克隆仓库并按 skillcrawler 相同逻辑发现其中的合法 skill。

        返回 ``[{"name": str, "skill_url": str}]``；克隆/发现失败返回 None
        （由 ``_repo_targets`` 转成“无法识别仓库”告警，不触发整仓库审计）；
        克隆成功但没有任何合法 skill 时返回空列表（由上层判定为“没有识别到 skill”）。
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
                try:
                    text = skill_file.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                # 与 wittyhub 扫描器一致：frontmatter 缺 name/description、
                # 正文过短的 SKILL.md 不算 skill，不纳入审计
                if self._recognize_skill_text(relative, text):
                    continue
                skills.append({
                    "name": self._skill_display_name_from_text(
                        text, skill_file.parent.name or self.SKILL_MD_NAME,
                    ),
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
        """与 wittyhub should_skip_relative_path 一致：跳过样本/文档/测试目录。

        规则支持多级目录（用 '/' 连接），按连续目录段匹配。
        """
        parts = relative_path.lower().split("/")[:-1]
        for rule in cls.SKIP_SAMPLE_DIRS:
            rule_parts = rule.strip("/").lower().split("/")
            rule_length = len(rule_parts)
            if any(
                parts[index:index + rule_length] == rule_parts
                for index in range(len(parts) - rule_length + 1)
            ):
                return True
        return False

    @classmethod
    def _recognize_skill_text(cls, relative_path, text):
        """按 wittyhub src/skills 扫描口径识别 skill。

        返回 None 表示识别成功，否则返回未识别原因。
        """
        if not relative_path or Path(relative_path).name != cls.SKILL_MD_NAME:
            return "文件名必须为 {}".format(cls.SKILL_MD_NAME)
        if cls._should_skip_skill_path(relative_path):
            return "位于 template/example/demo/test/docs 等跳过目录"
        metadata, content = cls._parse_skill_frontmatter_text(text)
        missing = [
            field for field in cls.REQUIRED_SKILL_METADATA_FIELDS
            if not str(metadata.get(field) or "").strip()
        ]
        if missing:
            return "frontmatter 缺少必填字段: {}".format("/".join(missing))
        if len(content.strip()) < cls.MIN_SKILL_CONTENT_LENGTH:
            return "正文内容少于 {} 字符".format(cls.MIN_SKILL_CONTENT_LENGTH)
        return None

    @classmethod
    def _parse_skill_frontmatter_text(cls, text):
        """解析 SKILL.md frontmatter，行为与 wittyhub 扫描器保持一致。

        返回 ``(metadata, content)``；没有合法 frontmatter 时返回空元数据
        与去除首尾空白的正文。
        """
        stripped = (text or "").lstrip()
        if not stripped.startswith("---"):
            return {}, (text or "").strip()
        parts = stripped.split("---", maxsplit=2)
        if len(parts) < 3:
            return {}, (text or "").strip()

        raw_frontmatter = parts[1]
        content = parts[2].lstrip("\r\n")

        metadata = {}
        current_key = None
        block_scalar_indicator = None
        for line in raw_frontmatter.splitlines():
            stripped_line = line.strip()
            if not stripped_line or stripped_line.startswith("#"):
                continue

            # YAML 块标量（| 或 >）内，缩进行都属于当前值
            if block_scalar_indicator is not None:
                if line[:1] in (" ", "\t"):
                    if current_key is not None:
                        existing = metadata.get(current_key)
                        if isinstance(existing, str) and existing:
                            if block_scalar_indicator == "|":
                                metadata[current_key] = "{}\n{}".format(existing, stripped_line)
                            else:
                                metadata[current_key] = "{} {}".format(existing, stripped_line)
                        else:
                            metadata[current_key] = stripped_line
                    continue
                block_scalar_indicator = None

            if stripped_line.startswith("- ") and current_key is not None:
                existing = metadata.get(current_key)
                if not isinstance(existing, list):
                    existing = [existing] if isinstance(existing, str) and existing else []
                    metadata[current_key] = existing
                item = stripped_line[2:].strip()
                if item:
                    existing.append(item)
                continue

            if ":" not in line:
                if current_key is not None:
                    existing = metadata.get(current_key)
                    if isinstance(existing, str):
                        metadata[current_key] = "{} {}".format(existing, stripped_line).strip()
                continue

            key, value = line.split(":", 1)
            current_key = key.strip()
            value = value.strip()

            if value in ("|", ">", "|-", ">-", "|+", ">+"):
                block_scalar_indicator = value[0]
                metadata[current_key] = ""
                continue

            block_scalar_indicator = None
            metadata[current_key] = cls._parse_frontmatter_value(current_key, value)

        return metadata, content.strip()

    @staticmethod
    def _parse_frontmatter_value(key, value):
        if not value:
            return [] if key == "triggers" else ""
        if key == "triggers":
            stripped = value.strip("\"'")
            return [stripped] if stripped else []
        lowered = value.lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            if not inner:
                return []
            items = [item.strip().strip("\"'") for item in inner.split(",")]
            return [item for item in items if item] or []
        return value.strip("\"'")

    @classmethod
    def _skill_display_name_from_text(cls, text, fallback):
        """从 SKILL.md 文本提取 frontmatter name，缺失时使用 fallback。"""
        metadata, _content = cls._parse_skill_frontmatter_text(text)
        name = str(metadata.get("name") or "").strip()
        return name or fallback

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

    @classmethod
    def _parse_skill_url(cls, skill_url):
        """解析 skills[].skill_url -> ``(repo_url, ref, skill_path)``。

        与 wittyhub parse_skill_md_url 口径一致：必须是
        ``<repo>/blob/<ref>/<path>/SKILL.md``，且 ref 不含 '/'（无法消歧）。
        不合法时返回 None。
        """
        stripped = (skill_url or "").split("#", 1)[0].split("?", 1)[0].strip()
        if not stripped or "/blob/" not in stripped:
            return None
        repo_part, _, ref_path = stripped.partition("/blob/")
        ref, _, skill_path = ref_path.partition("/")
        if not ref or not skill_path or "/" in ref:
            return None
        if skill_path != cls.SKILL_MD_NAME and not skill_path.endswith("/" + cls.SKILL_MD_NAME):
            return None
        if not cls._normalize_repo_browse_url(repo_part):
            return None
        return repo_part, ref, skill_path

    @classmethod
    def _validate_skill_url_structure(cls, skill_url):
        """skill_url 纯字符串校验，返回 None 表示结构合法。"""
        parsed = cls._parse_skill_url(skill_url)
        if parsed is None:
            return "skill_url 必须为 <repo>/blob/<ref>/<path>/SKILL.md，且 ref 不能包含 '/'"
        repo_url, _ref, skill_path = parsed
        if cls._should_skip_skill_path(skill_path):
            return "skill_url 指向 template/example/demo/test/docs 等跳过目录"
        if not cls._validate_git_url(repo_url):
            return "skill_url 仓库地址不在公开托管域名白名单内"
        return None

    def _check_declared_skill_urls(self, declared):
        """校验 skill.yaml 的 skills[].skill_url，返回 ``(targets, rejected, unrecognized)``。

        先做纯字符串结构校验，再按仓库/ref 分组 clone 一次，读取远端
        SKILL.md 按 wittyhub 扫描口径校验内容：

        - 内容不合规 -> rejected（门禁失败）
        - clone 失败 -> unrecognized（无法完成内容识别，WARNING，不审计该目标）
        """
        targets = []
        rejected = []
        unrecognized = []
        groups = {}
        for item in declared:
            url = item.get("url") or ""
            error = self._validate_skill_url_structure(url)
            if error:
                rejected.append({"source": url, "reason": error})
                continue
            if item.get("entry_found") and not str(item.get("name") or "").strip():
                rejected.append({"source": url, "reason": "skills[] 缺少必填字段: skill_name"})
                continue
            repo_url, ref, skill_path = self._parse_skill_url(url)
            groups.setdefault((repo_url, ref), []).append(
                (url, skill_path, item.get("name")),
            )
        for (repo_url, ref), items in groups.items():
            results = self._remote_skill_errors(
                repo_url, ref, [skill_path for _url, skill_path, _name in items],
            )
            for (url, _skill_path, name), (status, reason) in zip(items, results):
                if status == "unavailable":
                    unrecognized.append({"source": url, "reason": reason})
                elif status == "invalid":
                    rejected.append({"source": url, "reason": reason})
                else:
                    targets.append(self._skill_target(url, name))
        return targets, rejected, unrecognized

    def _remote_skill_errors(self, repo_url, ref, skill_paths):
        """浅 clone 仓库并校验远端 SKILL.md 内容。

        返回与 ``skill_paths`` 等长的 ``(status, reason)`` 列表：

        - ``(None, None)``: 识别通过
        - ``("invalid", reason)``: 内容/文件不合规，门禁失败
        - ``("unavailable", reason)``: clone 失败，未完成内容识别，门禁告警

        clone 失败时不再回退为按声明 URL 审计。
        """
        if not self._validate_git_url(repo_url):
            return [("invalid", "仓库地址不在公开托管域名白名单内")] * len(skill_paths)
        env = dict(os.environ)
        env.update({
            "GIT_TERMINAL_PROMPT": "0",
            "GCM_INTERACTIVE": "Never",
            "GIT_LFS_SKIP_SMUDGE": "1",
        })
        tmpdir = None
        try:
            tmpdir = tempfile.mkdtemp(prefix="wittyhub-skill-")
            clone_url = repo_url if repo_url.endswith(".git") else repo_url + ".git"
            command = [GIT_BIN, "clone", "--depth", "1", "--branch", ref, clone_url, tmpdir]
            proc = subprocess.run(command, capture_output=True, text=True, env=env, timeout=120)
            if proc.returncode != 0:
                logger.warning(
                    "validate skill_url: clone %s@%s failed: %s",
                    repo_url, ref, (proc.stderr or "").strip()[-500:],
                )
                return [(
                    "unavailable",
                    "远端仓库 clone 失败，未完成 SKILL.md 内容识别",
                )] * len(skill_paths)
            repo_root = Path(tmpdir)
            return [
                self._recognize_remote_skill_file(repo_root / skill_path, skill_path)
                for skill_path in skill_paths
            ]
        except Exception as exc:
            logger.warning("validate skill_url %s@%s failed: %s", repo_url, ref, exc)
            return [(
                "unavailable",
                "远端仓库 clone 失败，未完成 SKILL.md 内容识别: {}".format(exc),
            )] * len(skill_paths)
        finally:
            if tmpdir:
                shutil.rmtree(tmpdir, ignore_errors=True)

    @classmethod
    def _recognize_remote_skill_file(cls, skill_file, relative_path):
        try:
            text = Path(skill_file).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return "invalid", "远端 SKILL.md 不存在或无法读取"
        reason = cls._recognize_skill_text(relative_path, text)
        return ("invalid", reason) if reason else (None, None)

    def _skill_yaml_changed_fields(self, skill_yamls):
        """解析 PR 中每个 skill.yaml 的行级 patch，返回 {yaml_file: (repo_urls, skill_urls)}。

        ``(repo_urls, skill_urls)`` 语义见 ``_fields_changed_by_patch``；无法获取
        patch 时对应文件回退为 ({}, {})（两字段全量审计，保守不漏）。
        """
        result = {}
        pr_files = []
        try:
            from src.proxy.atomgit_proxy import AtomgitProxy
            files = AtomgitProxy(self._community, self._repo, self._access_token).get_pr_files(self._pr_num) or []
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
                patch = raw_patch.get("diff") or ""  # AtomGit 返回 {"diff": "<unified diff>"}
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
        """获取 PR 头分支的仓库 URL 与 ref（AtomGit PR 信息）。"""
        try:
            from src.proxy.atomgit_proxy import AtomgitProxy
            info = AtomgitProxy(self._community, self._repo, self._access_token).get_pr_info(self._pr_num) or {}
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
                html_url = "https://atomgit.com/{}".format(full_name)
        if not html_url:
            html_url = "https://atomgit.com/{}/{}".format(self._community, self._repo)  # 同仓库 PR 时用目标仓库兜底
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
            from src.proxy.atomgit_proxy import AtomgitProxy
            atomgit_proxy = AtomgitProxy(self._community, self._repo, self._access_token)
        except Exception as exc:
            logger.warning("comment pr failed: %s", exc)
            return
        body = (
            "**SkillHub 安全审计门禁**\n\n"
            "本次 PR 涉及 {} 个 skill，超过单次审计目标上限（{} 个），"
            "本次不做安全审计，请人工审核。".format(count, self.MAX_TARGETS)
        )
        atomgit_proxy.comment_pr(self._pr_num, body)

    def _comment_no_skill(self, rejected):
        """PR 有 skill 相关变更但未识别到合法 skill 时评论失败原因。"""
        try:
            from src.proxy.atomgit_proxy import AtomgitProxy
            atomgit_proxy = AtomgitProxy(self._community, self._repo, self._access_token)
        except Exception as exc:
            logger.warning("comment pr failed: %s", exc)
            return
        lines = [
            "**SkillHub 安全审计门禁**",
            "",
            "**结论: 失败（没有识别到 skill）**",
            "",
            "本次 PR 包含 skill 相关变更，但未识别到符合标准的 skill，未执行安全审计。",
            "",
            "识别标准（与 WittyHub 扫描口径一致）：",
            "1. 文件名必须为 `SKILL.md`",
            "2. 不能位于 template/example/demo/test/fixture/docs/archive/legacy 目录",
            "3. frontmatter 必须同时声明非空的 `name` 和 `description`",
            "4. 正文内容不少于 {} 字符".format(self.MIN_SKILL_CONTENT_LENGTH),
        ]
        if rejected:
            lines.extend([
                "",
                "| 文件/来源 | 未识别原因 |",
                "| --- | --- |",
            ])
            for item in rejected:
                lines.append("| {} | {} |".format(
                    self._escape_table_cell(item.get("source", "")),
                    self._escape_table_cell(item.get("reason", "")),
                ))
        body = "\n".join(lines)
        if len(body) > self.MAX_COMMENT_CHARS:
            body = body[:self.MAX_COMMENT_CHARS] + "\n\n... (评论过长，已截断)"
        atomgit_proxy.comment_pr(self._pr_num, body)

    def _comment_unrecognized(self, unrecognized):
        """仓库 clone/发现失败或远端内容未完成识别时评论告警。"""
        try:
            from src.proxy.atomgit_proxy import AtomgitProxy
            atomgit_proxy = AtomgitProxy(self._community, self._repo, self._access_token)
        except Exception as exc:
            logger.warning("comment pr failed: %s", exc)
            return
        lines = [
            "**SkillHub 安全审计门禁**",
            "",
            "**结论: 警告（无法识别仓库，请人工审核）**",
            "",
            "以下仓库或 skill_url 无法完成识别，未执行安全审计。"
            "请人工审核，或评论 /retest 重试。",
        ]
        if unrecognized:
            lines.extend([
                "",
                "| 来源 | 失败原因 |",
                "| --- | --- |",
            ])
            for item in unrecognized:
                lines.append("| {} | {} |".format(
                    self._escape_table_cell(item.get("source", "")),
                    self._escape_table_cell(item.get("reason", "")),
                ))
        body = "\n".join(lines)
        if len(body) > self.MAX_COMMENT_CHARS:
            body = body[:self.MAX_COMMENT_CHARS] + "\n\n... (评论过长，已截断)"
        atomgit_proxy.comment_pr(self._pr_num, body)

    def _comment_summary(
        self, audits, failed_details, block_hit, warn_hit,
        rejected=None, unrecognized=None,
    ):
        try:
            from src.proxy.atomgit_proxy import AtomgitProxy
            atomgit_proxy = AtomgitProxy(self._community, self._repo, self._access_token)
        except Exception as exc:
            logger.warning("comment pr failed: %s", exc)
            return
        # 评论链接使用对外可访问的地址；未配置时回退到内部 API 地址
        report_base = (os.environ.get("WITTYHUB_PUBLIC_URL") or self._api_url).rstrip("/")

        # 结论放在表格上方，便于一眼看到门禁判定
        # 审计失败优先：失败目标无法拿到审计结果，需评论 /retest 触发重新审批
        if failed_details:
            conclusion = "**结论: 审计失败，请评论 /retest 重新审计**"
        elif block_hit:
            conclusion = "**结论: 谨慎合入（存在高风险 skill）**"
        elif warn_hit:
            conclusion = "**结论: 有风险提示（存在低风险、风险未知或未完成内容识别）**"
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
        if rejected:
            lines.extend([
                "",
                "**未识别到 skill（已跳过审计）**",
                "",
                "| 文件/来源 | 未识别原因 |",
                "| --- | --- |",
            ])
            for item in rejected:
                lines.append("| {} | {} |".format(
                    self._escape_table_cell(item.get("source", "")),
                    self._escape_table_cell(item.get("reason", "")),
                ))
        if unrecognized:
            lines.extend([
                "",
                "**无法识别仓库或 skill_url（未完成内容识别，请人工审核）**",
                "",
                "| 来源 | 失败原因 |",
                "| --- | --- |",
            ])
            for item in unrecognized:
                lines.append("| {} | {} |".format(
                    self._escape_table_cell(item.get("source", "")),
                    self._escape_table_cell(item.get("reason", "")),
                ))

        body = "\n".join(lines)
        if len(body) > self.MAX_COMMENT_CHARS:
            body = body[:self.MAX_COMMENT_CHARS] + "\n\n... (评论过长，已截断)"
        atomgit_proxy.comment_pr(self._pr_num, body)

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
