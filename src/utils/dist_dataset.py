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
# Create: 2020-09-23
# Description: gitee api proxy
# **********************************************************************************

import logging
from datetime import datetime

from src.utils.dot_json import MutableDotJson

logger = logging.getLogger("common")


class DistDataset(object):
    """
    分布式数据集，用来保存门禁各阶段性结果
    """
    def __init__(self):
        """
        初始化
        """
        self._json = MutableDotJson()

    def to_dict(self):
        """
        
        :return:
        """
        return self._json.to_dict()

    def set_attr(self, attr, value):
        """
        属性赋值
        :param attr: 属性
        :param value: 值
        :return:
        """
        self._json[attr] = value

    def set_attr_ctime(self, attr, ctime):
        """
        属性【开始时间】赋值
        :param attr:
        :param ctime: jenkins build time
        :return:
        """
        self._json[attr] = ctime.strftime("%Y-%m-%d %H:%M:%S")

        attrs = attr.split(".")
        # set pending
        attrs[-1] = "stime"
        try:
            stime_str = self._json[".".join(attrs)]
            stime = datetime.strptime(stime_str, "%Y-%m-%d %H:%M:%S")
            pending = (stime - ctime).total_seconds()  # seconds
            attrs[-1] = "pending"
            self._json[".".join(attrs)] = int(pending)
        except KeyError:
            logger.debug("no correspond stime")

    def set_attr_stime(self, attr):
        """
        属性【开始时间】赋值
        :param attr:
        :return:
        """
        now = datetime.now()
        self._json[attr] = now.strftime("%Y-%m-%d %H:%M:%S")

    def set_attr_etime(self, attr):
        """
        属性【结束时间】赋值
        :param attr:
        :return:
        """
        now = datetime.now()
        self._json[attr] = now.strftime("%Y-%m-%d %H:%M:%S")

        attrs = attr.split(".")
        # set elapse
        attrs[-1] = "stime"
        try:
            stime_str = self._json[".".join(attrs)]
            stime = datetime.strptime(stime_str, "%Y-%m-%d %H:%M:%S")
            elapse = (now - stime).total_seconds()   # seconds
            attrs[-1] = "elapse"
            self._json[".".join(attrs)] = int(elapse)
        except KeyError:
            logger.debug("no correspond stime")

        # set interval
        attrs[-1] = "ctime"
        try:
            ctime_str = self._json[".".join(attrs)]
            ctime = datetime.strptime(ctime_str, "%Y-%m-%d %H:%M:%S")
            elapse = (now - ctime).total_seconds()  # seconds
            attrs[-1] = "interval"
            self._json[".".join(attrs)] = int(elapse)
        except KeyError:
            logger.debug("no correspond ctime")
