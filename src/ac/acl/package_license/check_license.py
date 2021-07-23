# -*- encoding=utf-8 -*-
"""
# **********************************************************************************
# Copyright (c) Huawei Technologies Co., Ltd. 2020-2020. All rights reserved.
# [openeuler-jenkins] is licensed under the Mulan PSL v1.
# You can use this software according to the terms and conditions of the Mulan PSL v1.
# You may obtain a copy of Mulan PSL v1 at:
#     http://license.coscl.org.cn/MulanPSL
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY OR FIT FOR A PARTICULAR
# PURPOSE.
# See the Mulan PSL v1 for more details.
# Author: 
# Create: 2020-10-16
# Description: check spec file
# **********************************************************************************
"""

import logging
import time
import os
import yaml
import shutil

from src.proxy.git_proxy import GitProxy
from src.ac.framework.ac_result import FAILED, WARNING, SUCCESS
from src.ac.framework.ac_base import BaseCheck
from src.ac.common.rpm_spec_adapter import RPMSpecAdapter
from src.ac.common.gitee_repo import GiteeRepo
from src.ac.acl.package_license.package_license import PkgLicense

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

    def check_license_in_spec(self):
        """
        check whether the license in spec file is in white list
        :return
        """
        if self._spec is None:
            logger.error("spec file not find")
            return FAILED
        self._license_in_spec = self._gr.scan_license_in_spec(self._spec)
        self._license_in_spec = self._pkg_license.translate_license(self._license_in_spec)
        if self._pkg_license.check_license_safe(self._license_in_spec):
            return SUCCESS
        else:
            logger.error("licenses in spec are not in white list")
            return FAILED

    def check_license_in_src(self):
        """
        check whether the license in src file is in white list
        :return
        """
        self._license_in_src = self._pkg_license.scan_licenses_in_license(self._work_tar_dir)
        self._license_in_src = self._pkg_license.translate_license(self._license_in_src)
        if not self._license_in_src:
            logger.warning("cannot find licenses in src")
        if self._pkg_license.check_license_safe(self._license_in_src):
            return SUCCESS
        else:
            logger.error("licenses in src code are not in white list")
            return FAILED

    def check_license_is_same(self):
        """
        check whether the license in spec file and in src file is same
        :return
        """
        if self._pkg_license.check_licenses_is_same(self._license_in_spec, self._license_in_src, self._pkg_license._later_support_license):
            logger.info("licenses in src:{} and in spec:{} are same".format(self._license_in_src,
                                                                            self._license_in_spec))
            return SUCCESS
        else:
            logger.error("licenses in src:{} and in spec:{} are not same".format(self._license_in_src,
                                                                                   self._license_in_spec))
            return WARNING

    def __call__(self, *args, **kwargs):
        """
        入口函数
        :param args:
        :param kwargs:
        :return:
        """
        logger.info("check {} license ...".format(self._repo))

        _ = not os.path.exists(self._work_tar_dir) and os.mkdir(self._work_tar_dir)
        self._gr.decompress_all() # decompress all compressed file into work_tar_dir 
        self._pkg_license.load_config() # load license config into instance variable

        try:
            return self.start_check_with_order("license_in_spec", "license_in_src", "license_is_same")
        finally:
            shutil.rmtree(self._work_tar_dir)