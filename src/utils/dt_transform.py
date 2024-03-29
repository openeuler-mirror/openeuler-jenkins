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
# Create: 2020-09-23
# Description: gitee api proxy
# **********************************************************************************
"""

from datetime import datetime
import calendar

SECOND_TO_MILLISECOND_RATE = 1000
MILLISECOND_TO_MICROSECOND_RATE = 1000


def convert_utc_to_naive(utc_dt):
    """
    utc datetime to local datetime
    :param utc_dt: utc datetime
    :return:
    """
    ts = calendar.timegm(utc_dt.timetuple())
    naive_dt = datetime.fromtimestamp(ts)

    return naive_dt.replace(microsecond=utc_dt.microsecond)


def convert_timestamp_to_naive(timestamp):
    """
    timestamp to local datetime
    :param timestamp: 13位时间戳
    :return:
    """
    naive_dt = datetime.fromtimestamp(timestamp / SECOND_TO_MILLISECOND_RATE)
    return naive_dt.replace(microsecond=((timestamp % SECOND_TO_MILLISECOND_RATE) * MILLISECOND_TO_MICROSECOND_RATE))
