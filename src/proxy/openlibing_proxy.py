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
# Create: 2025-11-12
# Description: openlibing proxy
# **********************************************************************************

import logging
import time
import hmac
import hashlib
import base64

logger = logging.getLogger("common")


class OpenlibingProxy(object):
    def __init__(self, account_id, secret_key):
        self.accountid = account_id
        self.secretKey = secret_key
        self.timestamp = None
        self.sign = None

    def create_openlibing_api_sign(self):
        # generate a 13 bit timestamp as the timestamp
        self.timestamp = str(int(time.time()*1000))

        # combine the string for reception signature
        data = self.accountid + self.timestamp

        # calculate signatures using the HmacSHA256 algorithm
        key = self.secretKey.encode()
        msg = data.encode()
        sign = hmac.new(key, msg, hashlib.sha256).digest()

        # encode the signature using base64 encoding
        self.sign = base64.b64encode(sign).decode()

    def get_openlibing_api_headers(self):
        self.create_openlibing_api_sign()
        return {
            'Content-Type': 'application/json',
            'accountid': self.accountid,
            'timestamp': self.timestamp,
            'sign': self.sign
        }