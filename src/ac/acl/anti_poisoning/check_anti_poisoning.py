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
# Create: 2024-01-19
# Description: check anti_poisoning
# **********************************************************************************

import logging
import time

from src.ac.framework.ac_base import BaseCheck
from src.ac.framework.ac_result import FAILED, WARNING, SUCCESS
from src.proxy.requests_proxy import do_requests

logger = logging.getLogger("ac")


class CheckAntiPoisoning(BaseCheck):
    """
    code check
    """

    def __init__(self, workspace, repo, conf=None):
        """

        :param workspace:
        :param repo:
        :param conf:
        """
        super(CheckAntiPoisoning, self).__init__(workspace, repo, conf)

        # wait to initial
        self._community = None
        self._repo = repo
        self._access_token = None
        self._pr_number = None
        self._api_token = None
        self._antipoison_ip = 'https://majun.osinfra.cn'
        self._antipoison_prefix = '/api/http/majun-service-forwarding/ci-portal/poison/webhook'

    def __call__(self, *args, **kwargs):
        """
        入口函数
        :param args:
        :param kwargs:
        :return:
        """
        logger.info("check %s antipoisoning ...", self._repo)
        logger.debug("args: %s, kwargs: %s", args, kwargs)
        antipoisoning_conf = kwargs.get("antipoison", {})

        self._community = antipoisoning_conf.get("community", "")
        self._pr_number = antipoisoning_conf.get("pr_number", "")
        self._access_token = antipoisoning_conf.get("access_token", "")
        self._api_token = antipoisoning_conf.get('antipoison_api_token', "")

        return self.start_check()

    def get_poison_result(self):
        """
        通过api调用anti-poisoning
        """
        scan_response = {}
        # 创建anti-poisoning检查任务
        task_url = f'{self._antipoison_ip}{self._antipoison_prefix}/pr-scan'
        post_data = {
            "repoName": self._repo,
            "projectName": self._community,
            "pullNumber": self._pr_number,
            "accessToken": self._access_token,
            "apiToken": self._api_token
        }
        rs = do_requests("post", task_url, body=post_data, obj=scan_response)
        if rs == 0 or scan_response.get('code', '') == '200':
            logger.info('create anti_poison task success')
        else:
            logger.error('create anti_poison task failed: %s', scan_response.get("message"))

        scanid = scan_response.get('result').get('scanId')

        data = {
            "scanId": scanid,
            "apiToken": self._api_token
        }
        status_url = f'{self._antipoison_ip}{self._antipoison_prefix}/query-pr-results-status'
        current_time = 0
        logger.info("anti_poisoning probably need to 2min")

        # 定时2min
        while current_time < 120:
            time.sleep(10)
            response_content = {}
            # 检查auti_poisoning任务的执行状态

            rs = do_requests("post", status_url, body=data, obj=response_content)
            if rs == 0 and response_content.get('code') == 200 and not response_content.get('result'):
                current_time = current_time + 10
                continue
            else:
                break
        return rs, response_content

    def check_anti_poisoning(self):
        """
        开始进行anti_poisoning检查
        """
        # 等待计算结果
        rs, response_content = self.get_poison_result()

        # 判断是否计算完成
        if rs != 0:
            return FAILED

        result = response_content.get('result')
        if result:
            """
            # 返回结果 {
            "code": "200", 
            "message": "", 
            "result"{
            "isPass": "http://{ip}:{port}/increment/autipoisoning/{projectId}/openMajun/{repo}" 一个可以看到poison检查结果详情的地址
            "url": "pass(通过)/no pass(不通过)"
            }}
            """
            ispass = result.get('isPass')
            if not ispass:
                # 只有anti_poisoning完成且anti_poisoning检查的代码中存在bug，返回检查项失败的结果
                logger.warning("click %s view anti_poisoning check detail", result.get('url'))
                return FAILED
        else:
            logger.error("anti_poisoning check failed, info : %s", response_content.get('message'))
            return FAILED

        return SUCCESS

