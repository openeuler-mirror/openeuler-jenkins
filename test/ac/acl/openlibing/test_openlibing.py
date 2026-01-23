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
# Create: 2021-08-03
# Description: check spec file
# **********************************************************************************
"""


import unittest
import logging

from unittest import mock

from src.ac.framework.ac_result import FAILED, SUCCESS
from src.ac.acl.sca.check_sca import CheckSCA
from src.ac.acl.openlibing.check_code import CheckCode
from src.ac.acl.anti_poisoning.check_anti_poisoning import CheckAntiPoisoning

logging.getLogger('test_logger')


class TestCheckCode(unittest.TestCase):

    OPENLIBING_ARG = {"pr_url": "https://gitee.com/openeuler/iSulad/pulls/2624",
                "community": "openeuler", "pr_num": "2624",
                "accountid": "02657278-f08a-4169-b80f-1e6626b6b72d",
                "secretKey": "qCi6cHEgValRUA1oFpz8AnvnRUupWGJLyrQr135IP+A=",
                "access_token": "44c4948c0ed31fcc8b53c2f6f05bc2a4"}


    def _test_codecheck_api(self, return_value):
        mock_fun = mock.Mock(return_value=return_value)
        cc = CheckCode('./test', self.OPENLIBING_ARG.get("pr_url"))
        self.assertEqual(cc(common_args=self.OPENLIBING_ARG), mock_fun())

    def _test_anti_poison_api(self, return_value):
        mock_fun = mock.Mock(return_value=return_value)
        ap = CheckAntiPoisoning('./test', self.OPENLIBING_ARG.get("pr_url"))
        self.assertEqual(ap(common_args=self.OPENLIBING_ARG), mock_fun())

    def _test_sca_api(self, return_value):
        mock_fun = mock.Mock(return_value=return_value)
        cc = CheckSCA('./test', self.OPENLIBING_ARG.get("pr_url"))
        self.assertEqual(cc(common_args=self.OPENLIBING_ARG), mock_fun())

    def test_codecheck_api_success(self):
        return_value = SUCCESS
        self._test_codecheck_api(return_value)

    def test_codecheck_api_failed_no_pr_url(self):
        return_value = FAILED
        self.OPENLIBING_ARG['pr_url'] = ""
        self._test_codecheck_api(return_value)

    def test_anti_poison_api_success(self):
        return_value = SUCCESS
        self._test_anti_poison_api(return_value)

    def test_anti_poison_api_failed_no_pr_url(self):
        return_value = FAILED
        self.OPENLIBING_ARG['pr_url'] = ""
        self._test_anti_poison_api(return_value)

    def test_sca_api_success(self):
        return_value = SUCCESS
        self._test_anti_poison_api(return_value)

    def test_sca_api_failed_no_pr_url(self):
        return_value = FAILED
        self.OPENLIBING_ARG['pr_url'] = ""
        self._test_anti_poison_api(return_value)