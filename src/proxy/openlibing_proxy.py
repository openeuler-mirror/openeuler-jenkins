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
from src.apig_sdk import signer

logger = logging.getLogger("common")


class OpenlibingProxy(object):
    def __init__(self, access_key, secret_access_key):
        self.ak = access_key
        self.sk = secret_access_key
        self.timestamp = None
        self.sign = None

    def create_openlibing_api_request(self, method, url, headers, body=""):
        request = signer.HttpRequest(method, url, headers, body)
        sig = signer.Signer()
        sig.Key = self.ak
        sig.Secret = self.sk
        sig.Sign(request)
        return request