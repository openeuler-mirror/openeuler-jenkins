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
# Create: 2021-02-07
# Description: kafka proxy
# **********************************************************************************
"""

import logging
import json
import kafka
import kafka.errors as errors

logger = logging.getLogger("common")


class KafkaProducerProxy(object):
    """
    kafka 代理
    """
    def __init__(self, brokers, timeout=30):
        """

        :param brokers:
        :param timeout:
        """

        self._timeout = timeout
        self._kp = kafka.KafkaProducer(bootstrap_servers=brokers, 
                key_serializer=str.encode,
                value_serializer=lambda v:json.dumps(v).encode("utf-8"))

    def send(self, topic, key=None, value=None):
        """
        生产一条数据
        :param topic:
        :param key:
        :param value:
        :return:
        """
        try:
            logger.debug("kafka send: %s, %s", key, value)
            future = self._kp.send(topic, value=value, key=key)

            rs = future.get(timeout=self._timeout)

            logger.debug("kafka send result: %s", rs)
            return True
        except errors.KafkaTimeoutError:
            logger.exception("kafka send timeout exception")
            return False
        except errors.KafkaError:
            logger.exception("kafka send document exception")
            return False
