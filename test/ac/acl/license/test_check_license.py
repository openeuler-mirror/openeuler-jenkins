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

import unittest
from unittest import mock
import sys
import os
import types
import logging.config
import logging
import shutil
from src.ac.acl.package_license.package_license import PkgLicense

from src.ac.framework.ac_result import FAILED, WARNING, SUCCESS
from src.ac.acl.package_license.check_license import CheckLicense

logging.getLogger('test_logger')

class TestCheckPkgLicense(unittest.TestCase):
    DIR_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                            "license_test_sample")
    
    TEST_SAMPLE_DIR = {
        "no_spec": "no_spec",
        "spec_success": "pkgship",
        "spec_fail": "spec_fail",
        "no_src": "no_src",
        "src_success": "rubygem-mail",
        "src_fail": "perl-Date-Calc",
        "spec_src_same": "rubygem-mail",
        "spec_src_diff": "perl-Date-Calc"
    }

    def bind_func(self, check):
        def get_work_tar_dir(self):
            return self._work_tar_dir
        def load_license_config(self):
            self._pkg_license.load_config()
        def decompress(self):
            self._gr.decompress_all()
        check.get_work_tar_dir = types.MethodType(get_work_tar_dir, check)
        check.load_license_config = types.MethodType(load_license_config, check)
        check.decompress = types.MethodType(decompress, check)

    def _test_check_license_in_spec(self, dir_key, predict):
        os.chdir(os.path.join(self.DIR_PATH,
                              self.TEST_SAMPLE_DIR[dir_key]))
        cl = CheckLicense(self.DIR_PATH, 
                          self.TEST_SAMPLE_DIR[dir_key])
        self.bind_func(cl)
        cl.load_license_config()
        self.assertEqual(cl.check_license_in_spec(), predict)

    def test_check_license_in_spec_none(self):
        self._test_check_license_in_spec("no_spec", FAILED)
    
    def test_check_license_in_spec_succeed(self):
        self._test_check_license_in_spec("spec_success", SUCCESS)

    def test_check_license_in_spec_failed(self):
        self._test_check_license_in_spec("spec_fail", FAILED)

    def _test_check_license_in_src(self, dir_key, predict):
        os.chdir(os.path.join(self.DIR_PATH,
                              self.TEST_SAMPLE_DIR[dir_key]))
        cl = CheckLicense(self.DIR_PATH, 
                          self.TEST_SAMPLE_DIR[dir_key])
        self.bind_func(cl)
        _ = not os.path.exists(cl.get_work_tar_dir()) and os.mkdir(cl.get_work_tar_dir())
        try:
            cl.decompress()
            cl.load_license_config()
            self.assertEqual(cl.check_license_in_src(), predict)
        finally:
            shutil.rmtree(cl.get_work_tar_dir())

    def test_check_license_none(self):
        # 源码中不存在license由日志保存，不返回失败结果
        self._test_check_license_in_src("no_src", SUCCESS)

    def test_check_license_in_src_succeed(self):
        self._test_check_license_in_src("src_success", SUCCESS)

    def test_check_license_in_src_failed(self):
        self._test_check_license_in_src("src_fail", FAILED)

    def _test_check_license_same(self, dir_key, predict):
        os.chdir(os.path.join(self.DIR_PATH,
                              self.TEST_SAMPLE_DIR[dir_key]))
        cl = CheckLicense(self.DIR_PATH, 
                          self.TEST_SAMPLE_DIR[dir_key])
        self.bind_func(cl)
        _ = not os.path.exists(cl.get_work_tar_dir()) and os.mkdir(cl.get_work_tar_dir())
        try:
            cl.decompress()
            cl.load_license_config()
            cl.check_license_in_spec()
            cl.check_license_in_src()
            self.assertEqual(cl.check_license_is_same(), predict)
        finally:
            shutil.rmtree(cl.get_work_tar_dir())

    def test_check_license_same_succeed(self):
        self._test_check_license_same("spec_src_same", SUCCESS)

    def test_check_license_same_failed(self):
        self._test_check_license_same("spec_src_diff", WARNING)

    def test_check_license_same_later_version(self):
        cl = PkgLicense()
        cl.load_config()
        self.assertEqual(cl.check_licenses_is_same(["GPL-1.0-or-later"], ["GPL-3.0-only"], cl._later_support_license), True)


if __name__ == "__main__":
    work_dir = os.getcwd()
    _ = not os.path.exists("log") and os.mkdir("log")
    logger_conf_path = os.path.realpath(os.path.join(os.path.dirname(os.path.realpath(__file__)), "../../../../src/conf/logger.conf"))
    logging.config.fileConfig(logger_conf_path)
    logger = logging.getLogger("test_logger")
    # Test Package License
    suite = unittest.makeSuite(TestCheckPkgLicense)
    unittest.TextTestRunner().run(suite)
    os.chdir(work_dir)
    shutil.rmtree("log")
