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

import logging
import time
import hmac
import hashlib
import base64

from src.ac.framework.ac_base import BaseCheck
from src.ac.framework.ac_result import FAILED, SUCCESS
from src.proxy.requests_proxy import do_requests

logger = logging.getLogger("ac")


class CheckSCA(BaseCheck):
    """
    check software composition analysis
    """
    def __init__(self, workspace, repo, conf):
        """

        :param workspace:
        :param repo:
        :param conf:
        """
        super(CheckSCA, self).__init__(workspace, repo, conf)
        # wait to initial
        self._pr_url = None
        self._dynamic_token = None
        self._static_key = None
        self._sca_app_id = None
        self._scanId = None
        self._report_url = None
        self._result = None
        self._sca_ip = 'https://sca.osinfra.cn'
        self._sca_prefix = '/gateway/dm-service/scan'

    def __call__(self, *args, **kwargs):
        """
        入口函数
        :param args:
        :param kwargs:
        :return:
        """
        logger.info("check %s sca ...", self._repo)

        logger.debug("args: %s, kwargs: %s", args, kwargs)
        scanoss_conf = kwargs.get("scanoss", {})
        self._pr_url = scanoss_conf.get("pr_url", "")
        self._sca_app_id = scanoss_conf.get('sca_app_id', "")
        self._static_key = scanoss_conf.get('sca_api_key', "")

        return self.start_check()

    def create_sign(self):
        # 生成13位时间戳作为timestamp
        timestamp = str(int(time.time()*1000))

        #  拼接待签名字符串
        data = self._sca_app_id + timestamp

        # 使用HmacSHA256算法计算签名
        key = self._static_key.encode()
        msg = data.encode()
        sign = hmac.new(key, msg, hashlib.sha256).digest()

        # 对签名进行base64编码
        sign = base64.b64encode(sign).decode()
        return timestamp, sign

    def get_create_task(self, headers):
        try:
            response_content = {}
            task_url = f'{self._sca_ip}{self._sca_prefix}/pr'
            post_data = {
                "prUrl": self._pr_url,
                "privateToken": ""
            }

            rs = do_requests("post", task_url, headers=headers, body=post_data, obj=response_content)
            if rs == 0 and response_content.get('code', "") == 200:
                self._scanId = response_content.get('data', '')
                logger.info('create sca task success')
            else:
                logger.error('create sca task failed: %s', response_content.get("message"))
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
        # get sca sign
        timestamp, sign = self.create_sign()

        headers = {
            'Content-Type': 'application/json',
            'appId': self._sca_app_id,
            'timestamp': timestamp,
            'sign': sign
        }

        # create sca task
        self.get_create_task(headers)

        status_url = f'{self._sca_ip}{self._sca_prefix}/result?scanId={self._scanId}'
        expire_time = 0
        logger.info("check sca probably need to 10min")
        while expire_time < 600:
            time.sleep(10)
            response_content = {}
            # 检查sca任务的执行状态
            rs = do_requests("get", status_url, headers=headers, obj=response_content)
            if rs == 0 and response_content.get('code') == 200:
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
                    expire_time = expire_time + 20
                    continue
                elif state == 'failure':
                    logger.error(f'sca check failed, info: %s ', response_content.get("message"))
                    break
            else:
                logger.error(f'sca check interface failed')
                break

    def check_scanoss(self):
        """
        Obtain scanoss logs and result
        """
        self.get_task_result()
        if not self._report_url or self._result is None:
            return FAILED
        if self._result == "no pass":
            logger.warning("click %s view sca check detail", self._report_url)
            return FAILED

        return SUCCESS
