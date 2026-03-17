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
# Create: 2021-09-09
# Description: check sca (software composition analysis)
# **********************************************************************************
import json
import logging
import os
import time
import sys
import requests

from src.ac.framework.ac_base import BaseCheck
from src.ac.framework.ac_result import FAILED, SUCCESS, WARNING
from src.proxy.openlibing_proxy import OpenlibingProxy
from src.proxy.requests_proxy import do_requests

logger = logging.getLogger("ac")


class CheckSCA(BaseCheck):
    """
    check software composition analysis
    """
    def __init__(self, workspace, repo, conf=None):
        """

        :param workspace:
        :param repo:
        :param conf:
        """
        super(CheckSCA, self).__init__(workspace, repo, conf)
        # wait to initial
        self._community = None
        self._pr_url = None
        self._accountid = None
        self._secretKey = None
        self._report_url = None
        self._result = None
        self._sca_ip = 'https://apig.openlibing.com'
        self._sca_prefix = '/openlibing-sca'
        self.openlibing_proxy = None
        self._timeout = False

    def __call__(self, *args, **kwargs):
        """
        入口函数
        :param args:
        :param kwargs:
        :return:
        """
        logger.info("check %s sca ...", self._repo)

        logger.debug("args: %s, kwargs: %s", args, kwargs)
        scanoss_conf = kwargs.get("common_args", {})
        self._community = scanoss_conf.get("community", "")
        self._pr_url = scanoss_conf.get("pr_url", "")
        self.sca_create_ak = os.environ['sca_create_ak']
        self.sca_create_sk = os.environ['sca_create_sk']
        self.sca_result_ak = os.environ['sca_result_ak']
        self.sca_result_sk = os.environ['sca_result_sk']

        return self.start_check()

    def get_create_task(self):
        try:
            response_content = {}
            task_url = f'{self._sca_ip}{self._sca_prefix}/scan/pr'
            headers = {"Content-Type": "application/json"}
            post_data = {
                "projectName": self._community,
                "prUrl": self._pr_url
            }
            method = "POST"
            ol_proxy = OpenlibingProxy(self.sca_create_ak, self.sca_create_sk)
            request = ol_proxy.create_openlibing_api_request(method, task_url, headers, json.dumps(post_data))
            rs = do_requests(
                request.method,
                request.scheme + "://" + request.host + request.uri,
                headers=request.headers,
                body=json.loads(request.body),
                obj=response_content)
            if rs == 0 and response_content.get('code', "") == 200:
                logger.info('create sca task success')
                return response_content.get('data', '')
            else:
                logger.error('create sca task failed, the response is {}'.format(response_content))
        except Exception as error:
            logger.error('create sca task failed exception:%s', error)

    def get_task_result(self):
        """
        # 返回结果 {
        "code": "200",
        "message": "success",
        "data": {
            "prResult": link, 一个可以看到scacheck检查结果详情的地址
            “unconfirmedFileNum”: n,  未确认问题的个数
            "state": "success"
        }
        """
        # create sca task
        scan_id = self.get_create_task()
        if not scan_id:
            self._result = 'no pass'
            return
        status_url = f'{self._sca_ip}{self._sca_prefix}/scan/result?scanId=' + scan_id
        method = "GET"
        headers = {"host": "apig.openlibing.com"}
        ol_proxy = OpenlibingProxy(self.sca_result_ak, self.sca_result_sk)
        request = ol_proxy.create_openlibing_api_request(method, status_url, headers)
        expire_time = 0
        total_expire = 1200
        logger.info("check sca probably need to {} seconds".format(total_expire))
        query_interval = 10
        rs_error = 0
        max_rs_error = 3
        while expire_time < total_expire:
            time.sleep(query_interval)
            # 检查sca任务的执行状态
            rs = requests.request(method, status_url, headers=request.headers)
            response_content = rs.json()
            # 接口返回正常
            if response_content.get('code') == 200:
                rs_error = 0
                data = response_content.get('data')
                state = data.get('state')
                self._report_url = data.get('prResult')
                if state == 'success':
                    if data.get('unconfirmedFileNum') == 0:
                        self._result = 'pass'
                    elif data.get('unconfirmedFileNum') > 0:
                        self._result = 'no pass'
                    logger.info(f'sca check task success')
                    break
                elif state == 'scanning':
                    expire_time = expire_time + query_interval
                    continue
                elif state == 'failure':
                    logger.error(f'sca check failed, info: %s ', response_content.get("message"))
                    break
            # 接口返回异常
            else:
                # 检查状态的请求连续失败3次，则不再查询
                if rs_error >= max_rs_error:
                    logger.error(f"check sca status failed for {rs_error} times, "
                                 f"please contact openlibing, and the scan id is {scan_id}")
                    break
                else:
                    logger.warning(f"sca check interface failed: {rs}, retry")
                    expire_time = expire_time + query_interval
                    rs_error += 1
                    continue

        if expire_time >= total_expire:
            self._timeout = True

    def check_scanoss(self):
        """
        Obtain scanoss logs and result
        """
        self.get_task_result()
        if self._timeout:
            logger.error("check sca result timeout for 10min, click %s view sca check detail", self._report_url)
            return FAILED
        if not self._report_url:
            return FAILED
        if self._result == "no pass":
            logger.warning("click %s view sca check detail", self._report_url)
            return WARNING
        logger.info("click %s view sca check detail", self._report_url)
        return SUCCESS
