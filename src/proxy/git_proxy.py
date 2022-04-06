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
# Author: 
# Create: 2020-09-23
# Description: git api proxy
# **********************************************************************************
"""

import os
import logging
from io import StringIO
import retrying

from src.utils.shell_cmd import shell_cmd_live

logger = logging.getLogger("common")


class GitProxy(object):
    """
    git 代理，实现常见的git操作
    """
    def __init__(self, repo_dir):
        """
        :param repo_dir: 仓库目录
        """
        self._repo_dir = repo_dir

    @classmethod
    def init_repository(cls, sub_dir, work_dir=None):
        """
        初始化git仓库
        :param sub_dir: 仓库子目录
        :param work_dir: 仓库根目录
        :return: GitProxy() or None
        """
        repo_dir = os.path.join(work_dir, sub_dir) if work_dir else sub_dir

        init_cmd = "git init {}".format(repo_dir)
        ret, _, _ = shell_cmd_live(init_cmd)

        if ret:
            logger.warning("init repository failed, %s", ret)
            return None

        return cls(repo_dir)

    @retrying.retry(retry_on_result=lambda result: result is False, 
            stop_max_attempt_number=3, wait_fixed=2)
    def fetch_pull_request(self, url, pull_request, depth=1, progress=False):
        """
        fetch pr
        :param url: 仓库地址
        :param pull_request: pr编号
        :param depth: 深度
        :param progress: 展示进度
        :return:
        """
        fetch_cmd = "cd {}; git fetch {} --depth {} {} +refs/pull/{}/MERGE:refs/pull/{}/MERGE".format(
            self._repo_dir, "--progress" if progress else "", depth, url, pull_request, pull_request)
        ret, out, _ = shell_cmd_live(fetch_cmd, cap_out=True, cmd_verbose=False)
        if ret:
            logger.error("git fetch failed, %s", ret)
            logger.error("%s", out)
            return False

        return True
      
    def get_content_of_file_with_commit(self, file_path, commit="HEAD~0"):
        """
        获取单个commit文件内容
        :param commit: HEAD~{} or SHA
        :param file_path: 文件完整路径
        :return: StringIO
        """
        get_content_cmd = "cd {}; git show {}:{}".format(self._repo_dir, commit, file_path)
        ret, out, _ = shell_cmd_live(get_content_cmd, cap_out=True)
        if ret:
            logger.warning("get file content of commit failed, %s", ret)
            return None

        f = StringIO()
        f.write("\n".join(out))
        f.seek(0)

        return f

    def diff_files_between_commits(self, base, head):
        """
        获取2次提交的差别的文件名列表
        :param base: 被比较的版本
        :param head: 比较的版本
        :return: list&lt;string&gt;
        """
        diff_files_cmd = "cd {}; git diff --name-only --diff-filter=ACM {} {}".format(self._repo_dir, base, head)
        ret, out, _ = shell_cmd_live(diff_files_cmd, cap_out=True)

        if ret:
            logger.error("get diff files of commits failed, %s", ret)
            return []

        return out

    def extract_files_path_of_patch(self, patch_path):
        """
        获取patch内diff的文件路径
        :param patch_path: patch完整路径
        :return: list&lt;string&gt;
        """
        extract_file_cmd = "cd {}; git apply --numstat {}".format(self._repo_dir, patch_path)
        ret, out, _ = shell_cmd_live(extract_file_cmd, cap_out=True)

        if ret:
            logger.error("extract diff files of patch failed, %s", ret)
            return []

        return [line.split()[-1] for line in out]

    def apply_patch(self, patch_path, leading=0):
        """
        打补丁
        :param patch_path: patch完整路径
        :param leading: Remove &lt;n&gt; leading path components
        :return: boolean
        """
        apply_patch_cmd = "cd {}; git apply -p{} {}".format(self._repo_dir, leading, patch_path)
        ret, _, _ = shell_cmd_live(apply_patch_cmd)

        if ret:
            #logger.error("apply patch failed, %s", ret)
            return False

        return True

    @classmethod
    def apply_patch_at_dir(cls, patch_dir, patch_path, leading=0):
        """
        到指定目录下打补丁
        :param patch_path: patch完整路径
        :param patch_dir: patch使用路径
        :param leading: Remove &lt;n&gt; leading path components
        :return: boolean
        """
        #apply_patch_cmd = "cd {}; patch -l -t -p{} < {}".format(patch_dir, leading, patch_path)
        apply_patch_cmd = "cd {}; git apply --ignore-whitespace -p{} {}".format(patch_dir, leading, patch_path)
        ret, _, _ = shell_cmd_live(apply_patch_cmd)

        if ret:
            #logger.error("apply patch failed, %s", ret)
            return False

        return True

    def commit_id_of_reverse_head_index(self, index=0):
        """
        对应的commit hash
        :param index: HEAD~index
        :return: hash string
        """
        get_commit_cmd = "cd {}; git rev-parse {}".format(self._repo_dir, "HEAD~{}".format(index))
        ret, out, _ = shell_cmd_live(get_commit_cmd, cap_out=True)

        if ret:
            logger.error("get commit id of index failed, %s", ret)
            return None

        return out[0]

    def checkout_to_commit(self, commit):
        """
        git checkout
        :param commit: HEAD~{} or SHA
        :return: boolean
        """
        checkout_cmd = "cd {}; git checkout {}".format(self._repo_dir, commit)
        ret, _, _ = shell_cmd_live(checkout_cmd)

        if ret:
            logger.warning("checkout failed, %s", ret)
            return False

        return True

    def checkout_to_commit_force(self, commit):
        """
        git checkout
        :param commit: HEAD~{} or SHA
        :return: boolean
        """
        checkout_cmd = "cd {}; git checkout -f {}".format(self._repo_dir, commit)
        ret, _, _ = shell_cmd_live(checkout_cmd)

        if ret:
            logger.warning("checkout failed, %s", ret)
            return False

        return True

    def get_tree_hashes(self, commit, number=0, with_merges=True):
        """
        获取tree对象hash值
        :param commit: HEAD~{} or SHA
        :param number: hash numbers
        :return: hash string
        """
        if 0 == number:
            tree_hashes_cmd = "cd {}; git log --format=%T {}".format(self._repo_dir, commit)
        else:
            tree_hashes_cmd = "cd {}; git log --format=%T -n{} {}".format(self._repo_dir, number, commit)

        if not with_merges:
            tree_hashes_cmd = "{} --no-merges".format(tree_hashes_cmd)

        ret, out, _ = shell_cmd_live(tree_hashes_cmd, cap_out=True)

        if ret:
            logger.error("get tree hashes failed, %s", ret)
            return None

        return out

    def fetch_commit_with_depth(self, depth):
        """
        git fetch
        :param depth: fetch 提交深度，0表示全部提交
        :return: boolean
        """
        if 0 == depth:
            fetch_cmd = "cd {}; git fetch --unshallow".format(self._repo_dir)
        else:
            fetch_cmd = "cd {}; git fetch --depth {}".format(self._repo_dir, depth)

        ret, _, _ = shell_cmd_live(fetch_cmd)

        if ret:
            logger.error("fetch failed, %s", ret)
            return False

        return True

    def is_revert_commit(self, commit="HEAD~0", depth=0):
        """
        判断是否revert commit
        :param commit: HEAD~{} or SHA
        :param depth: 往前检查的深度，如果是0则表示检查全部
        :return:
        """
        self.fetch_commit_with_depth(depth)

        tree_hashes = self.get_tree_hashes(commit, with_merges=False)

        if tree_hashes:
            curr = tree_hashes[0]
            for tree_hash in tree_hashes[1:]:
                if curr == tree_hash:
                    return True

        return False
