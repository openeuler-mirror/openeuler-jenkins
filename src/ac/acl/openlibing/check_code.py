# -*- encoding=utf-8 -*-
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
# Description: check code static
# **********************************************************************************

import logging
import time

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

        # wait to initial
        self._pr_url = None
        self._pr_number = None
        self._dynamic_token = None
        self._static_key = None
        self._codecheck_ip = 'https://majun.osinfra.cn'
        self._codecheck_prefix = '/api/ci-backend/ci-portal/webhook/codecheck/v1'

    def __call__(self, *args, **kwargs):
        """
        入口函数
        :param args:
        :param kwargs:
        :return:
        """
        logger.info("check %s code ...", self._repo)
        logger.debug("args: %s, kwargs: %s", args, kwargs)
        codecheck_conf = kwargs.get("codecheck", {})

        self._pr_url = codecheck_conf.get("pr_url", "")
        self._pr_number = codecheck_conf.get("pr_number", "")
        self._static_key = codecheck_conf.get('codecheck_api_key', "")

        return self.start_check()

    def _get_dynamic_token(self):
        try:
            response_content = {}
            token_url = f'{self._codecheck_ip}{self._codecheck_prefix}/token'
            post_data = {
                "static_token": self._static_key
            }
            rs = do_requests("post", token_url, body=post_data, obj=response_content)
            if rs == 0 and response_content.get('code', "") == "200":
                self._dynamic_token = response_content.get('data', '')
                logger.info('get dynamic token success')
            else:
                logger.error('get dynamic token failed: %s', response_content.get("msg"))
        except Exception as error:
            logger.error('get dynamic token failed exception:%s', error)

    def get_codecheck_result(self, pr_url):
        """
        通过api调用codecheck
        """
        # get codecheck Api Token
        self._get_dynamic_token()

        response_content = {}
        # 创建codecheck检查任务
        task_url = f'{self._codecheck_ip}{self._codecheck_prefix}/task'
        post_data = {
            "pr_url": pr_url,
            "token": self._dynamic_token
        }
        rs = do_requests("post", task_url, body=post_data, obj=response_content)
        if rs != 0 or response_content.get('code', '') != '200':
            if response_content.get('msg').find("There is no proper set of languages") != -1:
                response_content.update(code="200", msg="success", state="pass")
                return 0, response_content
            logger.error("create codecheck task failed; %s", response_content.get('msg', ''))
            return 'false', {}

        uuid = response_content.get('uuid')
        task_id = response_content.get('task_id')
        data = {
            "uuid": uuid,
            "task_id": task_id,
            "token": self._dynamic_token
        }
        status_url = f'{self._codecheck_ip}{self._codecheck_prefix}/task/status'
        current_time = 0
        logger.info("codecheck probably need to 5min")

        # 定时5min
        while current_time < 300:
            time.sleep(10)
            response_content = {}
            # 检查codecheck任务的执行状态

            rs = do_requests("post", status_url, body=data, obj=response_content)
            if rs == 0 and response_content.get('code') == '100':
                current_time = current_time + 10
                continue
            else:
                break
        return rs, response_content

    def check_code(self):
        """
        开始进行codecheck检查
        """
        # 等待计算结果
        rs, response_content = self.get_codecheck_result(self._pr_url)

        # 判断是否计算完成
        if rs != 0:
            return FAILED

        if response_content.get('msg') == 'success':
            """
            # 返回结果 {
            "code": "200", 
            "msg": "success", 
            "data": "http://{ip}:{port}/inc/{projectId}/reports/{taskId}/detail" 一个可以看到codecheck检查结果详情的地址
            "state": "pass(通过)/no pass(不通过)"
            }
            """
            logger.warning("click %s view code check detail", response_content.get('data'))
            # 只有codecheck完成且codecheck检查的代码中存在bug，返回检查项失败的结果，以detail结尾，会显示具体的代码bug所在位置。
            if response_content.get("state") == "no pass":
                return FAILED
        else:
            logger.error("code check failed, info : %s", response_content.get('msg'))

        return SUCCESS
