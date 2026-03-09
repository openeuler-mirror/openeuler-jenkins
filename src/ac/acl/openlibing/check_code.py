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
import os
import time
import json

from src.ac.framework.ac_base import BaseCheck
from src.ac.framework.ac_result import FAILED, SUCCESS
from src.proxy.requests_proxy import do_requests
from src.proxy.openlibing_proxy import OpenlibingProxy

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
        self._community = None
        self._pr_url = None
        self._accountid = None
        self._secretKey = None
        self._codecheck_ip = 'https://apig.openlibing.com'
        self._codecheck_prefix = '/openlibing-codecheck'
        self.openlibing_proxy = None

    def __call__(self, *args, **kwargs):
        """
        入口函数
        :param args:
        :param kwargs:
        :return:
        """
        logger.info("check %s code ...", self._repo)
        logger.debug("args: %s, kwargs: %s", args, kwargs)
        codecheck_conf = kwargs.get("common_args", {})

        self._community = codecheck_conf.get("community", "")
        self._pr_url = codecheck_conf.get("pr_url", "")
        self.code_create_ak = os.environ["code_create_ak"]
        self.code_create_sk = os.environ["code_create_sk"]
        self.code_result_ak = os.environ["code_result_ak"]
        self.code_result_sk = os.environ["code_result_sk"]

        if codecheck_conf.get("platform", "") == "gitcode":
            self._pr_url = self._pr_url.replace("/pull/", "/merge_requests/")

        return self.start_check()

    def get_codecheck_result(self):
        """
        通过api调用codecheck
        """
        response_content = {}
        # 创建codecheck检查任务
        task_url = f'{self._codecheck_ip}{self._codecheck_prefix}/ci-portal/webhook/codecheck/v1/task'
        headers = {"Content-Type": "application/json"}
        post_data = {
            "pr_url": self._pr_url,
            "projectName": self._community
        }
        method = 'POST'
        ol_proxy = OpenlibingProxy(self.code_create_ak, self.code_create_sk)
        request = ol_proxy.create_openlibing_api_request(method, task_url, headers, json.dumps(post_data))
        rs = do_requests(
            request.method,
            request.scheme + "://" + request.host + request.uri,
            headers=request.headers,
            body=json.loads(request.body),
            obj=response_content)
        if rs != 0 or response_content.get('code', '') != '200':
            if response_content.get('msg') and response_content.get('msg').find("There is no proper set of languages") != -1:
                response_content.update(code="200", msg="success", state="pass")
                return 0, response_content
            logger.error("create codecheck task failed:{}".format(response_content))
            return 'false', {}

        uuid = response_content.get('uuid')
        task_id = response_content.get('task_id')
        status_url = f'{self._codecheck_ip}{self._codecheck_prefix}/ci-portal/webhook/codecheck/v1/task/status'
        headers = {"Content-Type": "application/json"}
        data = {
            "uuid": uuid,
            "task_id": task_id,
        }
        method = 'POST'
        ol_proxy = OpenlibingProxy(self.code_result_ak, self.code_result_sk)
        request = ol_proxy.create_openlibing_api_request(method, status_url, headers, json.dumps(data))
        current_time = 0
        total_expire = 1200
        logger.info("codecheck probably need to {} seconds".format(total_expire))
        time_interval = 10
        # 定时10min
        while current_time < total_expire:
            time.sleep(time_interval)
            response_content = {}
            # 检查codecheck任务的执行状态
            rs = do_requests(
                request.method,
                request.scheme + "://" + request.host + request.uri,
                headers=request.headers,
                body=json.loads(request.body),
                obj=response_content)
            if rs == 0 and response_content.get('code') == '100':
                current_time = current_time + time_interval
                continue
            else:
                break
        return rs, response_content

    def check_code(self):
        """
        开始进行codecheck检查
        """
        # 等待计算结果
        rs, response_content = self.get_codecheck_result()

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
        elif response_content.get('code') == '500':
            logger.error("response content detail : %s", response_content)
            logger.error("Maybe an unpredictable error has occurred. Please contact the CI administrator.")
            return FAILED
        else:
            logger.error("code check failed, info : %s", response_content.get('msg'))

        return SUCCESS
