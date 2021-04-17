# -*- encoding=utf-8 -*-
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
# Create: 2021-09-09
# Description: check sca (software composition analysis)
# **********************************************************************************

import os
import shutil
import logging

from src.proxy.git_proxy import GitProxy
from src.ac.framework.ac_base import BaseCheck
from src.ac.framework.ac_result import FAILED, WARNING, SUCCESS
from src.ac.common.scanoss import ScanOSS

logger = logging.getLogger("ac")


class CheckSCA(BaseCheck):
    """
    check software composition analysis
    """
    def __init__(self, workspace, repo, conf):
        """

        :param workspace:
        :param repo:
        :param conf:
        """
        super(CheckSCA, self).__init__(workspace, repo, conf)

        self._work_diff_dir = os.path.join(workspace, "diff")    # 目标目录，保存变更了的代码

    def copy_diff_files_to_dest(self, files):
        """
        拷贝所有diff文件到目标目录
        :param files: 文件列表
        :return:
        """
        for filepath in files:
            try:
                shutil.copy(os.path.join(self._work_dir, filepath), self._work_diff_dir)
            except IOError:
                logger.exception("copy {} to {} exception".format(filepath, self._work_diff_dir))

    def save_scanoss_result(self, html):
        """
        保存结果到本地
        :param html: scanoss 结果，html格式
        :return:
        """
        with open(self._scanoss_result_output, "w") as f:
            f.write(html)

    def check_scanoss(self):
        """
        scanoss工具检查代码片段引用
        https://osskb.org
        https://github.com/scanoss/scanner.py
        :return:
        """
        gp = GitProxy(self._work_dir)
        diff_files = gp.diff_files_between_commits("HEAD~1", "HEAD~0")
        logger.debug("diff files: {}".format(diff_files))

        self.copy_diff_files_to_dest(diff_files)

        blacklist_sbom = os.path.realpath(os.path.join(os.path.realpath(__file__), "../../../../conf/deny_list.sbom"))
        scan = ScanOSS(self._scanoss_api_key, self._scanoss_api_url, blacklist_sbom)
        result = scan.scan(self._work_diff_dir)

        # 保存详细结果到web server
        if not result:
            self.save_scanoss_result(scan.html)
            logger.warning("click to view scanoss detail: {}".format(self._scanoss_result_repo_path))

        return SUCCESS if result else FAILED

    def __call__(self, *args, **kwargs):
        """
        入口函数
        :param args:
        :param kwargs:
        :return:
        """
        logger.info("check {} sca ...".format(self._repo))

        logger.debug("args: {}, kwargs: {}".format(args, kwargs))
        scanoss_conf = kwargs.get("scanoss", {})
        self._scanoss_api_key = scanoss_conf.get("api_key", "")
        self._scanoss_api_url = scanoss_conf.get("api_url", "https://osskb.org/api/scan/direct")
        self._scanoss_result_output = scanoss_conf.get("output", "scanoss_result")    # 保存结果到本地文件
        self._scanoss_result_repo_path = scanoss_conf.get("repo_path", "-lost linker-")  # 保存结果到web server的路径

        _ = not os.path.exists(self._work_diff_dir) and os.mkdir(self._work_diff_dir)
        try:
            return self.start_check()
        finally:
            shutil.rmtree(self._work_diff_dir)
