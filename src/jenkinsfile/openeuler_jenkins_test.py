# -*- encoding=utf-8 -*-
"""
# ***********************************************************************************
# Copyright (c) Huawei Technologies Co., Ltd. 2020-2020. All rights reserved.
# licensed under the Mulan PSL v1.
# You can use this software according to the terms and conditions of the Mulan PSL v1.
# You may obtain a copy of Mulan PSL v1 at:
#     http://license.coscl.org.cn/MulanPSL
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY OR FIT FOR A PARTICULAR
# PURPOSE.
# See the Mulan PSL v1 for more details.
# Author: DisNight
# Create: 2020-09-21
# Description: run all test cases in test/
# ***********************************************************************************/
"""

import os
import unittest
import logging.config
import logging
import mock
import shutil

PATTERN_STR = 'test*.py' # 测试用例文件必须以test_开头
TEST_DIR = os.path.realpath(os.path.join(os.path.realpath(__file__), '..', '..', '..', 'test'))
LOG_FILE = os.path.realpath(os.path.join(os.path.realpath(__file__), '..', 'test.log'))

if __name__ == '__main__':
    # mock所有logger为测试使用logger,输出为该文件同目录下的test.log
    wordk_dir = os.getcwd()
    _ = not os.path.exists("log") and os.mkdir("log")
    logger_conf_path = os.path.realpath(os.path.join(os.path.dirname(os.path.realpath(__file__)), "../conf/logger.conf"))
    logging.config.fileConfig(logger_conf_path)
    logger = logging.getLogger("test_logger")

    # 递归获取test目录下所有module的所有测试用例(需包含__init__.py)
    discover_sets = unittest.defaultTestLoader.discover(start_dir=TEST_DIR, pattern=PATTERN_STR, top_level_dir=None)
    suite = unittest.TestSuite()
    suite.addTest(discover_sets)
    # 运行所有测试用例
    test_runner = unittest.TextTestRunner()
    test_runner.run(suite)
    os.chdir(wordk_dir)
    shutil.rmtree("log")