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
# Create: 2021-08-03
# Description: check spec file
# **********************************************************************************
"""


import unittest
import os
import logging.config
import logging
import shutil

from unittest import mock
from src.ac.framework.ac_result import FAILED, WARNING, SUCCESS
from src.ac.acl.openlibing.check_code import CheckCode

logging.getLogger('test_logger')


class TestCheckCode(unittest.TestCase):

    CODECHECK = {
        "codecheck_api_url": "http://124.71.75.234:8384/api/openlibing/codecheck/start",
        "pr_url": "https://gitee.com/openeuler/pkgship/pulls/210",
        "pr_number": "210",
        "repo": "pkgship"
    }

    def _test_check_code(self, predict):
        cc = CheckCode('./test', self.CODECHECK.get("repo"))
        self.assertEqual(cc(codecheck=self.CODECHECK), mock.Mock(return_value=predict)())

    def _test_codecheck_api(self, return_value):
        mock_fun = mock.Mock(return_value=return_value)
        self.assertEqual(CheckCode.get_codecheck_result
                         (self.CODECHECK.get('pr_url'), self.CODECHECK.get("codecheck_api_url")), mock_fun())

    def test_check_code_success(self):
        self._test_check_code(SUCCESS)

    def test_codecheck_api_success(self):
        return_value = (0, {
            "code": "200",
            "msg": "success",
            "data": "http://124.71.75.234/inc/315fda2799c94eaf90fda86dfe1148c1/reports/" +
                    "90b92657bdc35b53481711ff6eac5f71/summary"
        })
        self._test_codecheck_api(return_value)

    def test_codecheck_api_success_no_pr_url(self):
        return_value = (0, {
            "code": "400",
            "msg": "pr_url is not null",
        })
        self.CODECHECK['pr_url'] = ""
        self._test_codecheck_api(return_value)

    def test_codecheck_api_success_no_fail(self):
        return_value = (0, {
            "code": "500",
            "msg": "codecheck is error",
        })
        self._test_codecheck_api(return_value)


if __name__ == "__main__":
    work_dir = os.getcwd()
    _ = not os.path.exists("log") and os.mkdir("log")
    logger_conf_path = os.path.realpath(os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                                     "../../../../src/conf/logger.conf"))
    logging.config.fileConfig(logger_conf_path)
    logger = logging.getLogger("test_logger")
    # Test Package License
    suite = unittest.makeSuite(TestCheckCode)
    unittest.TextTestRunner().run(suite)
    os.chdir(work_dir)
    shutil.rmtree("log")
