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
# Create: 2022-8-26
# Description: check openeuler license file
# **********************************************************************************
"""

import logging
import os
import shutil

from src.ac.acl.package_license.package_license import PkgLicense
from src.ac.common.gitee_repo import GiteeRepo
from src.ac.common.rpm_spec_adapter import RPMSpecAdapter
from src.ac.framework.ac_base import BaseCheck
from src.ac.framework.ac_result import FAILED, WARNING, SUCCESS
from src.proxy.git_proxy import GitProxy

logger = logging.getLogger("ac")


class CheckOpeneulerLicense(BaseCheck):
    """
    check license and copyright in repo
    """

    def __init__(self, workspace, repo, conf=None):
        super(CheckOpeneulerLicense, self).__init__(workspace, repo, conf)

        self._work_tar_dir = os.path.join(workspace, "code")
        self._pkg_license = PkgLicense()

    def __call__(self, *args, **kwargs):
        """
        入口函数
        :param args:
        :param kwargs:
        :return:
        """
        logger.info("check %s license ...", self._repo)
        codecheck = kwargs.get("codecheck", {})
        pr_url = codecheck.get("pr_url", "")
        self.response_content = self._pkg_license.get_license_info(pr_url)

        try:
            return self.start_check_with_order("license_in_repo", "license_in_scope", "copyright_in_repo")
        finally:
            shutil.rmtree(self._work_tar_dir)

    def check_license_in_repo(self):
        """
        check whether the license in repo is in white list
        :return
        """
        repo_license_legal = self.response_content.get("repo_license_legal")
        if not repo_license_legal:
            return WARNING
        res = repo_license_legal.get("pass")
        if res:
            logger.info("the license in repo is free")
            return SUCCESS
        else:
            notice_content = repo_license_legal.get("notice")
            logger.warning("License notice: %s", notice_content)

            is_legal = repo_license_legal.get("is_legal")
            if is_legal:
                is_legal_pass = is_legal.get("pass")
                if not is_legal_pass:
                    detail = is_legal.get("detail")
                    if detail:
                        black_reason = detail.get("is_white").get("blackReason")
                        if black_reason:
                            logger.error("License black reason: %s", black_reason)

            return FAILED

    def check_license_in_scope(self):
        """
        check whether the license in src file is in white list
        :return
        """
        return self._pkg_license.check_license_in_scope()

    def check_copyright_in_repo(self):
        """
        check whether the copyright in src file
        :return
        """
        return self._pkg_license.check_repo_copyright_legal()

