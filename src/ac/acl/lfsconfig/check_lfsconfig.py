# -*- encoding=utf-8 -*-
"""
# ***********************************************************************************
# Copyright (c) Huawei Technologies Co., Ltd. 2026. All rights reserved.
# [openeuler-jenkins] is licensed under the Mulan PSL v2.
# You can use this software according to the terms and conditions of the Mulan PSL v2.
# You may obtain a copy of Mulan PSL v2 at:
#          http://license.coscl.org.cn/MulanPSL2
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND,
# EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT,
# MERCHANTABILITY OR FIT FOR A PARTICULAR PURPOSE.
# See the Mulan PSL v2 for more details.
# Author:
# Create: 2026-07-04
# Description: check .lfsconfig file in software package
# ***********************************************************************************/
"""

import configparser
import logging
import os

from src.ac.framework.ac_base import BaseCheck
from src.ac.framework.ac_result import EXCLUDE, FAILED, SUCCESS, ACResult
from src.proxy.git_proxy import GitProxy

logger = logging.getLogger("ac")


class CheckLfsconfig(BaseCheck):
    """
    check .lfsconfig file in PR diff
    """

    def __init__(self, workspace, repo, conf=None):
        super(CheckLfsconfig, self).__init__(workspace, repo, conf)
        self._gp = GitProxy(self._work_dir)

    def __call__(self, *args, **kwargs):
        logger.info("check %s .lfsconfig ...", self._repo)
        self._kwargs = kwargs

        diff_files = self.get_pr_changed_files()
        if diff_files is None:
            diff_files = self._gp.diff_files_between_commits("HEAD~1", "HEAD~0")
        if ".lfsconfig" not in diff_files:
            logger.info(".lfsconfig not in PR diff, skip check")
            return EXCLUDE

        logger.info(".lfsconfig found in PR diff, checking url ...")
        return self.start_check_with_order("lfsconfig")

    def check_lfsconfig(self):
        lfsconfig_path = os.path.join(self._work_dir, ".lfsconfig")
        expected_url = "https://artlfs.openeuler.openatom.cn/src-openEuler/%s" % self._repo

        config = configparser.ConfigParser()
        try:
            config.read(lfsconfig_path)
            url = config.get("lfs", "url", fallback=None)
        except (configparser.Error, KeyError) as e:
            logger.error("parse .lfsconfig failed: %s", e)
            logger.error("expected url: %s", expected_url)
            details = ["解析.lfsconfig文件失败: {}".format(e), "期望URL: {}".format(expected_url)]
            return ACResult(FAILED.val, details=details)

        if not url:
            logger.error("lfs.url not found in .lfsconfig")
            logger.error("expected url: %s", expected_url)
            details = [".lfsconfig中未找到lfs.url配置项", "期望URL: {}".format(expected_url)]
            return ACResult(FAILED.val, details=details)

        url = url.strip()
        if url == expected_url:
            logger.info(".lfsconfig url is correct: %s", url)
            return SUCCESS

        logger.error(".lfsconfig url is incorrect: %s", url)
        logger.error("expected url: %s", expected_url)
        logger.info(
            "please refer to https://gitcode.com/openeuler/community/blob/master/zh/contributors/git-lfs.md for fix"
        )
        details = [
            ".lfsconfig URL不正确: 实际值 '{}'，期望值 '{}'".format(url, expected_url),
            "请参考 https://gitcode.com/openeuler/community/blob/master/zh/contributors/git-lfs.md 进行修复"
        ]
        return ACResult(FAILED.val, details=details)