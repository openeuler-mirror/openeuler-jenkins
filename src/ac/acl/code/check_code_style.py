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
# Author: 
# Create: 2020-09-23
# Description: check code style
# **********************************************************************************

import os
import shutil
import logging

from src.proxy.git_proxy import GitProxy
from src.ac.framework.ac_base import BaseCheck
from src.ac.framework.ac_result import FAILED, WARNING, SUCCESS
from src.ac.common.gitee_repo import GiteeRepo
from src.ac.common.linter import LinterCheck
from src.ac.common.rpm_spec_adapter import RPMSpecAdapter

logger = logging.getLogger("ac")


class CheckCodeStyle(BaseCheck):
    """
    check code style
    """
    def __init__(self, workspace, repo, conf):
        super(CheckCodeStyle, self).__init__(workspace, repo, conf)

        self._work_tar_dir = os.path.join(workspace, "code")    # 解压缩目标目录

        self._gr = GiteeRepo(self._repo, self._work_dir, self._work_tar_dir)

    def check_compressed_file(self):
        """
        解压缩包
        """
        return SUCCESS if 0 == self._gr.decompress_all() else FAILED

    def check_patch(self):
        """
        应用所有patch
        """
        patches = []
        if self._gr.spec_file:
            spec = RPMSpecAdapter(os.path.join(self._work_dir, self._gr.spec_file))
            patches = spec.patches

        rs = self._gr.apply_all_patches(*patches)

        if 0 == rs:
            return SUCCESS

        return WARNING if 1 == rs else FAILED

    def check_code_style(self):
        """
        检查代码风格
        :return:
        """
        gp = GitProxy(self._work_dir)
        diff_files = gp.diff_files_between_commits("HEAD~1", "HEAD~0")
        logger.debug("diff files: %s", diff_files)

        diff_code_files = []                # 仓库中变更的代码文件
        diff_patch_code_files = []          # patch内的代码文件
        for diff_file in diff_files:
            if GiteeRepo.is_code_file(diff_file):
                diff_code_files.append(diff_file)
            elif GiteeRepo.is_patch_file(diff_file):
                patch_dir = self._gr.patch_dir_mapping.get(diff_file)
                logger.debug("diff patch %s apply at dir %s", diff_file, patch_dir)
                if patch_dir is not None:
                    files_in_patch = gp.extract_files_path_of_patch(diff_file)
                    patch_code_files = [os.path.join(patch_dir, file_in_patch) 
                            for file_in_patch in files_in_patch 
                            if GiteeRepo.is_code_file(file_in_patch)]
                    # care about deleted file in patch, filter with "git patch --summary" maybe better
                    diff_patch_code_files.extend([code_file 
                        for code_file in patch_code_files 
                        if os.path.exists(code_file)])

        logger.debug("diff code files: %s", diff_code_files)
        logger.debug("diff patch code files: %s", diff_patch_code_files)

        rs_1 = self.check_file_under_work_dir(diff_code_files)
        logger.debug("check_file_under_work_dir: %s", rs_1)
        rs_2 = self.check_files_inner_patch(diff_patch_code_files)
        logger.debug("check_files_inner_patch: %s", rs_2)

        return rs_1 + rs_2

    def check_file_under_work_dir(self, diff_code_files):
        """
        检查仓库中变更的代码
        :return:
        """
        rs = [self.__class__.check_code_file(filename) for filename in set(diff_code_files)]

        return sum(rs, SUCCESS) if rs else SUCCESS

    def check_files_inner_patch(self, diff_patch_code_files):
        """
        检查仓库的patch内的代码
        :return:
        """
        rs = [self.__class__.check_code_file(os.path.join(self._work_tar_dir, filename)) 
                for filename in set(diff_patch_code_files)]

        return sum(rs, SUCCESS) if rs else SUCCESS

    @classmethod
    def check_code_file(cls, file_path):
        """
        检查代码风格
        :param file_path:
        :return:
        """
        if GiteeRepo.is_py_file(file_path):
            rs = LinterCheck.check_python(file_path)
        elif GiteeRepo.is_go_file(file_path):
            rs = LinterCheck.check_golang(file_path)
        elif GiteeRepo.is_c_cplusplus_file(file_path):
            rs = LinterCheck.check_c_cplusplus(file_path)
        else:
            logger.error("error when arrive here, unsupport file %s", file_path)
            return SUCCESS

        logger.info("Linter: %s %s", file_path, rs)
        if rs.get("F", 0) > 0:
            return FAILED

        if rs.get("W", 0) > 0 or rs.get("E", 0) > 0:
            return WARNING

        return SUCCESS

    def __call__(self, *args, **kwargs):
        """
        入口函数
        :param args:
        :param kwargs:
        :return:
        """
        logger.info("check %s repo ...", self._repo)

        _ = not os.path.exists(self._work_tar_dir) and os.mkdir(self._work_tar_dir)
        try:
            return self.start_check_with_order("compressed_file", "patch", "code_style")
        finally:
            shutil.rmtree(self._work_tar_dir)
