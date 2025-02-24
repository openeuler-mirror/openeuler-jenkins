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
# Create: 2025-2-6
# Description: check repo branch whether in maintain
# **********************************************************************************

import logging
import requests
import yaml

from src.ac.framework.ac_base import BaseCheck
from src.ac.framework.ac_result import FAILED, SUCCESS

logger = logging.getLogger("ac")


class CheckRepoInMaintain(BaseCheck):

    def __init__(self, workspace, repo, conf=None):
        super(CheckRepoInMaintain, self).__init__(workspace, repo, conf)

    def __call__(self, *args, **kwargs):
        logger.info("check %s branch whether in maintain...", self._repo)
        antipoisoning_conf = kwargs.get("antipoison", {})

        self._branch = kwargs.get("tbranch")
        self._token = antipoisoning_conf.get("access_token", "")

        return self.start_check_with_order("repo_in_maintain")

    def load_yml(self):
        base_url = "https://gitee.com/api/v5/repos/openeuler/release-management/raw"
        url = f"{base_url}/{self._branch}/delete/pckg-mgmt.yaml?access_token={self._token}"

        response = requests.get(url)
        if response.status_code != 200:
            logger.info(f"request package management failure: {response.text}")
            return {}

        dct = yaml.safe_load(response.content)
        return dct

    def check_repo_in_maintain(self):
        yml = self.load_yml()

        del_repos = [x.get("name") for x in yml.get("packages")] if yml else []

        if self._repo in del_repos:
            return FAILED
        return SUCCESS
