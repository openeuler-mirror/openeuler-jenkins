#!/usr/bin/env python
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
# Create: 2021-02-07
# Description: color log
# **********************************************************************************
"""

from colorlog import ColoredFormatter


class CusColoredFormatter(ColoredFormatter):
    def __init__(self, fmt=None, datefmt=None, style='%',
                 log_colors=None, reset=True,
                 secondary_log_colors=None):
        log_colors = {'DEBUG': 'reset',
            'INFO': 'reset',
            'WARNING': 'bold_yellow',
            'ERROR': 'bold_red',
            'CRITICAL': 'bold_red'}
        super(CusColoredFormatter, self).__init__(fmt, datefmt, style, log_colors, reset, secondary_log_colors)
