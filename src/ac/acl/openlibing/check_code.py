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
# Description: check code static
# **********************************************************************************
"""

import logging

from src.ac.framework.ac_base import BaseCheck
from src.ac.framework.ac_result import FAILED, WARNING, SUCCESS
from src.proxy.requests_proxy import do_requests

logger = logging.getLogger("ac")


class CheckCode(BaseCheck):
    """
    code check
    """

    def __init__(self, workspace, repo, conf=None):
        """

        :param workspace:
        :param repo:
        :param conf:
        """
        super(CheckCode, self).__init__(workspace, repo, conf)

    @staticmethod
    def get_codecheck_result(pr_url, codecheck_api_url):
        """
        通过api调用codecheck
        """
        data = {"pr_url": pr_url}
        response_content = {}
        logger.info("codecheck probably need to 3min")
        rs = do_requests("get", codecheck_api_url, querystring=data, timeout=180, obj=response_content)
        return rs, response_content

    def check_code(self):
        """
        开始进行codecheck检查
        """
        # 等待计算结果
        rs, response_content = self.get_codecheck_result(self._pr_url, self._codecheck_api_url)

        # 判断是否计算完成
        if rs != 0:
            return SUCCESS

        if response_content.get('msg') == 'success':
            """
            # 返回结果 {
            "code": "200", 
            "msg": "success", 
            "data": "http://{ip}:{port}/inc/{projectId}/reports/{taskId}/detail" 一个可以看到codecheck检查结果详情的地址
            "state": "pass(通过)/no pass(不通过)"
            }
            """
            # 只有codecheck完成且codecheck检查的代码中存在bug，返回检查项失败的结果，以detail结尾，会显示具体的代码bug所在位置。
            if response_content.get("state") == "no pass":
                logger.warning("click {} view code check detail".format(response_content.get('data')))
                return FAILED
        else:
            logger.error("code check failed, info :{}".format(response_content.get('msg')))

        return SUCCESS

    def __call__(self, *args, **kwargs):
        """
        入口函数
        :param args:
        :param kwargs:
        :return:
        """
        logger.info("check {} code ...".format(self._repo))
        logger.debug("args: {}, kwargs: {}".format(args, kwargs))
        codecheck_conf = kwargs.get("codecheck", {})

        self._pr_url = codecheck_conf.get("pr_url", "")
        self._pr_number = codecheck_conf.get("pr_number", "")
        self._codecheck_api_url = codecheck_conf.get("codecheck_api_url", "")

        return self.start_check()
