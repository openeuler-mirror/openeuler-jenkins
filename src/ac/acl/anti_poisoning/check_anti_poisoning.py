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
import json

from src.ac.framework.ac_base import BaseCheck
from src.ac.framework.ac_result import FAILED, WARNING, SUCCESS
from src.proxy.requests_proxy import do_requests
from src.proxy.openlibing_proxy import OpenlibingProxy

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
        self._pr_url = None
        self._accountid = None
        self._secretKey = None
        self._antipoison_ip = 'https://apig.openlibing.com'
        self._antipoison_prefix = '/openlibing-anti-poison'
        self.openlibing_proxy = None

    def __call__(self, *args, **kwargs):
        """
        入口函数
        :param args:
        :param kwargs:
        :return:
        """
        logger.info("check %s antipoisoning ...", self._repo)
        logger.debug("args: %s, kwargs: %s", args, kwargs)

        antipoisoning_conf = kwargs.get("common_args", {})

        self._community = antipoisoning_conf.get("community", "")
        self._pr_url = antipoisoning_conf.get("pr_url", "")
        self.anti_create_ak = antipoisoning_conf.get('anti_create_ak', "")
        self.anti_create_sk = antipoisoning_conf.get('anti_create_sk', "")
        self.anti_result_ak = antipoisoning_conf.get('anti_result_ak', "")
        self.anti_result_sk = antipoisoning_conf.get('anti_result_sk', "")

        return self.start_check()

    def create_poison_task(self):
        try:
            scan_response = {}
            # 创建anti-poisoning检查任务
            task_url = f'{self._antipoison_ip}{self._antipoison_prefix}/poison-pr/sca-pr'
            method = 'POST'
            headers = {"Content-Type": "application/json"}
            post_data = {
                "projectName": self._community,
                "prUrl": self._pr_url,
            }
            ol_proxy = OpenlibingProxy(self.anti_create_ak, self.anti_create_sk)
            request = ol_proxy.create_openlibing_api_request(method, task_url, headers, json.dumps(post_data))
            rs = do_requests(
                request.method,
                request.scheme + "://" + request.host + request.uri,
                headers=request.headers,
                body=json.loads(request.body),
                obj=scan_response)
            if rs != 0 or scan_response.get('code', '') != 200:
                logger.error('create anti_poison task failed: %s', scan_response.get("message"))
                return None
            else:
                logger.info('create anti_poison task success')
                return scan_response.get('result').get('scanId')
        except Exception as error:
            logger.error('create sca task failed exception:%s', error)

    def get_poison_result(self):
        scanid = self.create_poison_task()
        if not scanid:
            return FAILED, None
        status_url = f'{self._antipoison_ip}{self._antipoison_prefix}/poison-pr/query-pr-results-status'
        data = {
            "scanId": scanid
        }
        method = "POST"
        headers = {"Content-Type": "application/json"}
        ol_proxy = OpenlibingProxy(self.anti_result_ak, self.anti_result_sk)
        request = ol_proxy.create_openlibing_api_request(method, status_url, headers, json.dumps(data))
        current_time = 0
        total_expire = 120
        logger.info("codecheck probably need to {} seconds".format(total_expire))
        time_interval = 10
        while current_time < 120:
            time.sleep(time_interval)
            response_content = {}
            # 检查anti_poisoning任务的执行状态
            rs = do_requests(
                request.method,
                request.scheme + "://" + request.host + request.uri,
                headers=request.headers,
                body=json.loads(request.body),
                obj=response_content)
            if rs == 0 and response_content.get('code') == 200 and not response_content.get('result'):
                current_time = current_time + time_interval
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
            "message": "success", 
            "result"{
            "isPass": True
            "url": "http://{ip}:{port}/increment/autipoisoning/{projectId}/openMajun/{repo}" 一个可以看到poison检查结果详情的地址
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
        logger.info("click %s view anti_poisoning check detail", result.get('url'))
        return SUCCESS

