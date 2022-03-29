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
# Create: 2021-3-21
# Description: ci mistake report to database by kafka
# **********************************************************************************
"""
import os
import logging
import sys

from src.utils.color_log import CusColoredFormatter


def singleton(cls):
    instances = {}

    def _singleton(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]

    return _singleton


@singleton
class Logger:
    def __init__(self):
        self.logger = logging.getLogger('MyLogger')
        self.logger.setLevel(logging.DEBUG)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = CusColoredFormatter(fmt="%(log_color)s%(asctime)s [%(levelname)7s] : %(message)s")
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)

        file_handler = logging.FileHandler("{}/ci.log".format(os.path.dirname(__file__)))
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter("%(asctime)s %(filename)20s[line:%(lineno)3d] %(levelname)7s : %(message)s")
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)


logger = Logger().logger
