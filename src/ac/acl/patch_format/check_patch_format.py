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
# Create: 2023-12-7
# Description: check patch format
# **********************************************************************************

import os
import re
import logging

from src.proxy.git_proxy import GitProxy
from src.ac.framework.ac_base import BaseCheck
from src.ac.framework.ac_result import FAILED, WARNING, SUCCESS

from src.ac.common.gitee_repo import GiteeRepo
from src.utils.shell_cmd import shell_cmd_unicode

logger = logging.getLogger("ac")

IGNORES_FOR_MAIN = [
    'CONFIG_DESCRIPTION',
    'FILE_PATH_CHANGES',
    'GERRIT_CHANGE_ID',
    'GIT_COMMIT_ID',
    'UNKNOWN_COMMIT_ID',
    'FROM_SIGN_OFF_MISMATCH',
    'REPEATED_WORD',
    'COMMIT_COMMENT_SYMBOL',
    'BLOCK_COMMENT_STYLE',
    'AVOID_EXTERNS',
    'AVOID_BUG'
]


class CheckPatchFormat(BaseCheck):
    """
    check code style
    """
    def __init__(self, workspace, repo, conf):
        super(CheckPatchFormat, self).__init__(workspace, repo, conf)

    @staticmethod
    def do_checkpatch(patch):
        ignore_str = ','.join(IGNORES_FOR_MAIN)

        cmd = f"./scripts/checkpatch.pl {patch} --show-types --no-tree --ignore {ignore_str}"
        ret, out = shell_cmd_unicode(cmd)

        _regex = 'total: .* checked'
        if re.search(_regex, out):
            description = re.search(_regex, out).group(0)
            if description.find(' 0 error') == -1:
                return 1, out
            elif description.find(' 0 warning') == -1:
                return 2, out
            else:
                return 0, out
        else:
            return 0, 'total: 0 errors, 0 warnings, 0 lines checked'

    def check_patch_format(self):
        """
        检查代码风格
        :return:
        """
        if self._tbranch != "openEuler-20.03-LTS-SP4":
            return SUCCESS
        gp = GitProxy(self._work_dir)
        diff_files = gp.diff_files_between_commits("HEAD~1", "HEAD~0")
        logger.info("diff files: %s", diff_files)

        patch_list = [diff_file for diff_file in diff_files if GiteeRepo.is_patch_file(diff_file)]
        if not patch_list:
            return SUCCESS

        os.chdir(self._repo)

        if not os.path.exists("scripts/checkpatch.pl"):
            return SUCCESS

        failed_num = 0
        warning_num = 0
        for patch in patch_list:
            logger.info(f"check {patch}")
            ret, description = self.do_checkpatch(patch)
            if ret == 1:
                logger.error(f"check {patch} failed")
                logger.error(description)
                failed_num = failed_num + 1
            elif ret == 2:
                logger.warning(f"check {patch} warning")
                logger.warning(description)
                warning_num += 1
            else:
                logger.info(f"check {patch} success")
                logger.info(description)

        if failed_num > 0:
            return FAILED
        elif warning_num > 0:
            return WARNING
        else:
            return SUCCESS

    def __call__(self, *args, **kwargs):
        """
        入口函数
        :param args:
        :param kwargs:
        :return:
        """
        logger.info("check %s patch format ...", self._repo)
        self._tbranch = kwargs.get("tbranch", None)
        return self.start_check_with_order("patch_format")

