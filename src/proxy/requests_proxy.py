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
# Create: 2020-09-23
# Description: requests api proxy
# **********************************************************************************

import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any

import requests
from requests.auth import HTTPBasicAuth
try:
    from urllib import urlencode
except ImportError:
    from urllib.parse import urlencode

logger = logging.getLogger("common")


@dataclass
class RequestData:
    """HTTP request data container"""
    querystring: Optional[Dict[str, Any]] = None
    body: Optional[Dict[str, Any]] = None
    headers: Optional[Dict[str, str]] = None
    auth: Optional[Dict[str, str]] = None
    timeout: int = 120
    obj: Optional[Any] = None


def do_requests(method, url, data: RequestData = None):
    """
    http request
    :param method: http method
    :param url: http[s] schema
    :param data: RequestData object containing querystring, body, headers, auth, timeout, obj
    :return:
    """
    if data is None:
        data = RequestData()

    try:
        logger.debug("http requests, %s %s %s", method, url, data.timeout)
        logger.debug("querystring: %s", data.querystring)
        logger.debug("body: %s", data.body)

        if method.lower() not in ["get", "post", "put", "delete", "patch"]:
            return -1

        if data.querystring:
            url = "{}?{}".format(url, urlencode(data.querystring))

        func = getattr(requests, method.lower())
        if data.body:
            if data.auth:
                if data.headers:
                    rs = func(url, 
                    json=data.body, 
                    timeout=data.timeout, 
                    auth=HTTPBasicAuth(data.auth["user"], data.auth["password"]),
                    headers=data.headers)
                else:
                    rs = func(url, 
                    json=data.body, 
                    timeout=data.timeout, 
                    auth=HTTPBasicAuth(data.auth["user"], data.auth["password"]))
            else:
                if data.headers:
                    rs = func(url, json=data.body, timeout=data.timeout, headers=data.headers)
                else:
                    rs = func(url, json=data.body, timeout=data.timeout)
        else:
            if data.auth:
                if data.headers:
                    rs = func(url, 
                    timeout=data.timeout, 
                    auth=HTTPBasicAuth(data.auth["user"], data.auth["password"]), 
                    headers=data.headers)
                else:
                    rs = func(url, 
                    timeout=data.timeout, 
                    auth=HTTPBasicAuth(data.auth["user"], data.auth["password"]))
            else:
                if data.headers:
                    rs = func(url, timeout=data.timeout, headers=data.headers)
                else:
                    rs = func(url, timeout=data.timeout)

        logger.debug("status_code %s", rs.status_code)
        if rs.status_code not in [requests.codes.ok, requests.codes.created, requests.codes.no_content]:
            logger.error("the response is {}".format(rs.json()))
            return 1

        # return response
        if data.obj is not None:
            if isinstance(data.obj, list):
                data.obj.extend(rs.json())
            elif isinstance(data.obj, dict):
                data.obj.update(rs.json())
            elif callable(data.obj):
                data.obj(rs)
            elif hasattr(data.obj, "cb"):
                getattr(data.obj, "cb")(rs.json())

        return 0
    except requests.exceptions.SSLError as e:
        logger.warning("requests %s ssl exception, %s", url, e)
        return -2
    except requests.exceptions.Timeout as e:
        logger.warning("requests timeout")
        return 2
    except requests.exceptions.RequestException as e:
        logger.warning("requests exception, %s", e)
        return 3
