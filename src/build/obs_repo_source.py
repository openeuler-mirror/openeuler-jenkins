# -*- encoding=utf-8 -*-
"""
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
# Create: 2021-05-27
# Description: obs repo as dnf source
# **********************************************************************************
"""
import logging
import os
import re

from src.proxy.requests_proxy import do_requests
from src.utils.file_operator import FileOperator

logger = logging.getLogger("common")


class OBSRepoSource(object):
    """
    生成obs实时仓作为rpm源的配置
    """
    def __init__(self):
        """

        :param repo_host: obs仓库host
        """
        cur_path = os.path.abspath(os.path.dirname(__file__))
        config_file = os.path.join(cur_path, "../conf/project_host_mapping.yaml")
        self.project_host_map = FileOperator.filereader(config_file, "yaml")

    @staticmethod
    def repo_format(repo_id, repo_name, repo_baseurl, priority=None):
        """
        repo内容格式
        :param repo_id:
        :param repo_name:
        :param repo_baseurl:
        :param priority:
        :return:
        """
        if priority:
            return "[{}]\nname={}\nbaseurl={}\nenabled=1\ngpgcheck=0\npriority={}\n".format(repo_id, repo_name, repo_baseurl, priority)
        else:
            return "[{}]\nname={}\nbaseurl={}\nenabled=1\ngpgcheck=0\n".format(repo_id, repo_name,repo_baseurl)

    def generate_repo_info(self, branch, obs_branch_list, arch, repo_name_prefix):
        """
        不同的分支生成不同的repo
        :param branch:
        :param obs_branch_list:
        :param arch:
        :param repo_name_prefix:
        :return:
        """
        repo_config = ""
        priority = 1
        if not branch.startswith("Multi-Version"):
            obs_branch_list = self.remove_useless_repo(obs_branch_list)
        for obs_branch in obs_branch_list:
            host = ""
            for backend_name, backend_conf in self.project_host_map.items():
                if obs_branch in backend_conf.get("project_list"):
                    host = backend_conf.get("host")
                    break
            branch = obs_branch.replace(":", ":/")
            url = "{}/{}/standard_{}".format(host, branch, arch)
            if do_requests("GET", url) == 0:
                logger.debug("add openstack base repo: %s", url)
                repo_config += self.repo_format(obs_branch, repo_name_prefix + "_" + branch, url, priority)
                priority += 1

        return repo_config

    def remove_useless_repo(self, obs_branch_list):
        """
        删除多余的依赖repo
        :param obs_branch_list:
        :return:
        """
        with open("obs_project", "r") as f:
            obs_repos = f.read()
        obs_repo_suffix = obs_repos.split(":")[-1]
        if obs_repo_suffix == "Epol" and "openEuler:Factory" in obs_branch_list:
            obs_branch_list.remove("openEuler:Factory")
        elif obs_repo_suffix not in ["Factory", "Epol"]:
            pattern = re.compile(".*:Factory$|.*:Epol$")
            pattern_result = list(filter(None, [pattern.match(obs_branch) for obs_branch in obs_branch_list]))
            if pattern_result:
                for obs_branch in pattern_result:
                    obs_branch_list.remove(obs_branch.group(0))
        return obs_branch_list
