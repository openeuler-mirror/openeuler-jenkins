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
# Create: 2020-12-30
# Description: elasticsearch proxy
# **********************************************************************************
"""

import logging
import elasticsearch 

logger = logging.getLogger("common")


class ESProxy(object):
    """
    es 代理
    """
    def __init__(self, username, password, hosts=None, timeout=30, **kwargs):
        """

        :param username:
        :param password:
        :param hosts: 参考Elasticsearch.__init__描述
        :param timeout:
        """

        self._timeout = timeout
        self._es = elasticsearch.Elasticsearch(hosts=hosts, http_auth=(username, password), timeout=timeout, **kwargs)

    def insert(self, index, body):
        """
        插入一条数据
        :param index:
        :param body:
        :return:
        """
        try:
            logger.debug("es insert: {}".format(body))
            rs = self._es.index(index, body=body)

            logger.debug("insert result: {}".format(rs))
            return rs["result"] == "created"
        except elasticsearch.RequestError:
            logger.exception("elastic search insert document exception")
            return False

    def search(self, index, body):
        """
        条件搜索
        :param index:
        :param body:
        :return:
        """
        logger.debug("es search: {}".format(body))
        rs = self._es.search(index=index, body=body)
        logger.debug("result: {}".format(rs))

        return rs['hits']['hits']

    def update_by_query(self, index, query, script):
        """
        更新一条数据，原数据不变
        eg:
        query = {
            "term": {"id": 567}
        }
        script = {
            "source": "ctx._source.tags = params.tags",
            "params": {
                "tags": tags
            },
            "lang":"painless"
        }
        :param index:
        :param query:
        :param script:
        :return:
        """
        try:
            body = {"query": query, "script": script}
            logger.debug("es update: {}".format(body))
            rs = self._es.update_by_query(index, body=body)
            logger.debug("update result: {}".format(rs))

            return True
        except elasticsearch.RequestError:
            logger.exception("elastic search update by query exception")
            return False
