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
# Create: 2020-10-16
# Description: check spec file
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


class CheckLicense(BaseCheck):
    """
    check license in spec and src-code
    """

    def __init__(self, workspace, repo, conf=None):
        super(CheckLicense, self).__init__(workspace, repo, conf)

        self._gp = GitProxy(self._work_dir)
        self._work_tar_dir = os.path.join(workspace, "code")
        self._gr = GiteeRepo(self._repo, self._work_dir, self._work_tar_dir)
        if self._gr.spec_file:
            self._spec = RPMSpecAdapter(os.path.join(self._work_dir, self._gr.spec_file))
        else:
            self._spec = None

        self._pkg_license = PkgLicense()
        self._license_in_spec = set()
        self._license_in_src = set()

    def __call__(self, *args, **kwargs):
        """
        入口函数
        :param args:
        :param kwargs:
        :return:
        """
        logger.info("check %s license ...", self._repo)

        if not os.path.exists(self._work_tar_dir):
            os.mkdir(self._work_tar_dir)
        self._gr.decompress_all()  # decompress all compressed file into work_tar_dir
        codecheck = kwargs.get("codecheck", {})
        pr_url = codecheck.get("pr_url", "")
        self.response_content = self._pkg_license.get_license_info(pr_url)

        try:
            return self.start_check_with_order("license_in_spec", "license_in_src", "license_is_same",
                                               "copyright_in_repo")
        finally:
            shutil.rmtree(self._work_tar_dir)

    def check_license_in_spec(self):
        """
        check whether the license in spec file is in white list
        :return
        """
        if self._spec is None:
            logger.error("spec file not find")
            return FAILED
        spec_license_legal = self.response_content.get("spec_license_legal")

        if not spec_license_legal:
            logger.warning("No spec license data is obtained")
            return WARNING

        res = spec_license_legal.get("pass")
        if res:
            logger.info("the license in spec is free")
            return SUCCESS
        else:
            notice_content = spec_license_legal.get("notice")
            logger.warning("License notice: %s", notice_content)
            black_reason = spec_license_legal.get("detail").get("is_white").get("blackReason")
            if black_reason:
                logger.error("License black reason: %s", black_reason)
            return FAILED

    def check_license_in_src(self):
        """
        check whether the license in src file is in white list
        :return
        """
        return self._pkg_license.check_license_in_scope()

    def check_license_is_same(self):
        """
        check whether the license in spec file and in src file is same
        :return
        """
        self._license_in_spec = self._spec.license
        self._license_in_src = self._pkg_license.scan_licenses_in_license(self._work_tar_dir)
        self._license_in_src = self._pkg_license.translate_license(self._license_in_src)
        if self._pkg_license.check_licenses_is_same(self._license_in_spec, self._license_in_src,
                                                    self._pkg_license.later_support_license):
            logger.info("licenses in src:%s and in spec:%s are same", self._license_in_src,
                                                                            self._license_in_spec)
            return SUCCESS
        else:
            logger.error("licenses in src:%s and in spec:%s are not same", self._license_in_src,
                                                                                   self._license_in_spec)
            return WARNING

    def check_copyright_in_repo(self):
        """
        check whether the copyright in src file
        :return
        """
        return self._pkg_license.check_repo_copyright_legal()
