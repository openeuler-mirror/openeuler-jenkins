# -*- coding: utf-8 -*-
"""
# **********************************************************************************
# Copyright (c) Huawei Technologies Co., Ltd. 2020-2020. All rights reserved.
# [openeuler-jenkins] is licensed under the Mulan PSL v1.
# You can use this software according to the terms and conditions of the Mulan PSL v1.
# You may obtain a copy of Mulan PSL v1 at:
#     http://license.coscl.org.cn/MulanPSL
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY OR FIT FOR A PARTICULAR
# PURPOSE.
# See the Mulan PSL v1 for more details.
# Author: 
# Create: 2020-09-23
# Description: cal package buddy with obs meta info
# **********************************************************************************
"""

import logging
import os
import re
import xml.etree.ElementTree as ET
import collections

logger = logging.getLogger("jobs")


class ObsMetaStrategy(object):
    """
    使用obs_meta仓库的策略
    """
    def __init__(self, obs_meta_path):
        """

        :param obs_meta_path: obs_meta路径
        """
        self._obs_meta_path = obs_meta_path
        self._package_repo = collections.defaultdict(set)
        self._repo_package = collections.defaultdict(set)

    def get_packages_of_repo(self, repo):
        """
        获取关联的obs package
        :param repo:
        :return:
        """
        return list(self._repo_package.get(repo, set()))

    def get_buddy_of_repo(self, repo):
        """
        获取兄弟仓库列表
        :param repo:
        :return:
        """
        packages = self.get_packages_of_repo(repo)

        buddy = set()
        for package in packages:
            buddy.update(self._package_repo.get(package, set()))

        return list(buddy)

    def __iter__(self):
        return iter(self._repo_package.keys())

    def algorithm(self, *repos):
        """
        仓库与package关联信息算法
        :param repos: 仓库列表
        :return:
        """
        index = 0
        for dirpath, dirnames, filenames in os.walk(self._obs_meta_path):
            # 忽略.osc目录
            if re.search("\.osc|\.git|\:Bak", dirpath):
                continue

            for filename in filenames:
                if filename == "_service":
                    _service = os.path.join(dirpath, filename)
                    try:
                        logger.debug("analysis %s", _service)
                        tree = ET.parse(_service)
                        elements = tree.findall(".//param[@name=\"url\"]")  # <param name=url>next/openEuler/zip</parm>
                    except:
                        logger.exception("invalid xml format, %s", _service)
                        continue

                    _repos = [element.text.strip("/").split("/")[-1] for element in elements]  # eg: next/openEuler/zip
                    logger.debug("get repos: %s", _repos)
                    if any([repo in repos for repo in _repos]):
                        package = dirpath.strip("/").split("/")[-1]  # eg: master/openEuler:Mainline/zip/_services
                        index += 1
                        logger.info("%s %s...ok", index, _service)
                        logger.info("package: %s, repos: %s", package, _repos)
                        for repo in _repos:
                            self._package_repo[package].add(repo)
                            self._repo_package[repo].add(package)
