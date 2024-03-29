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
# Create: 2020-09-29
# Description: report obs package build info
# **********************************************************************************
"""

import logging.config
import logging
import argparse
import os

import yaml


class ObsPackageBuildReport(object):
    """
    obs包构建状态上报
    """
    GITEE_OWNER = "src-openeuler"

    def __init__(self,  project, state, real_name_mapping_file):
        """

        :param project: obs项目名
        :param state: 构建状态
        :param real_name_mapping_file: 码云账号真实姓名映射文件
        """
        self._project = project
        self._state = state
        self._real_name_mapping = self._load_real_name_of_gitee_id(real_name_mapping_file)

        self._package_last_committer = {}

    @staticmethod
    def _load_real_name_of_gitee_id(real_name_mapping_file):
        """
        加载用户名和码云账号映射表
        :param real_name_mapping_file:
        :return:
        """
        try:
            with open(real_name_mapping_file, "r") as f:
                return yaml.safe_load(f)
        except IOError:
            logger.exception("real name mapping file not exist")
        except yaml.YAMLError:
            logger.exception("load real name mapping file exception")

        return {}

    def get_last_committer(self, gitee_api_token):
        """
        计算最后的pr提交人
        :param gitee_api_token: 码云api token
        :return:
        """
        branch = "master"

        # get packages in project of state
        packages = OBSProxy.list_packages_of_state(self._project, self._state)
        logger.info("project %s state %s, find %s packages", self._project, self._state, len(packages))

        # get last pr committer
        for index, package in enumerate(packages):
            logger.info("%s: %s", index, package)
            gp = GiteeProxy(self.GITEE_OWNER, package, gitee_api_token)
            committer = gp.get_last_pr_committer(branch)
            real_name = self._real_name_mapping.get(committer, "N/A")
            self._package_last_committer[package] = {"committer": committer, "real_name": real_name}

    def dump(self):
        """
        导出
        :return:
        """
        print("{:<25}{:<25}{:<15}{:<20}{:<20}".format("project", "package", "state", "gitee", "charger"))
        for package in self._package_last_committer:
            committer = self._package_last_committer[package]["committer"]
            real_name = self._package_last_committer[package]["real_name"].encode("utf-8")
            print("{:<25}{:<25}{:<15}{:<20}{:<20}".format(self._project, package, self._state, committer, real_name))


if "__main__" == __name__:
    args = argparse.ArgumentParser()

    args.add_argument("-p", type=str, dest="project", nargs="+", help="obs project")
    args.add_argument("-s", type=str, dest="state", nargs="+", help="package build state")
    args.add_argument("-c", type=str, dest="real_name_mapping_file", help="gitee real name mapping")
    args.add_argument("-t", type=str, dest="token", help="gitee api token")

    args = args.parse_args()

    not os.path.exists("log") and os.mkdir("log")
    logger_conf_path = os.path.realpath(os.path.join(os.path.realpath(__file__), "../../conf/logger.conf"))
    logging.config.fileConfig(logger_conf_path)
    logger = logging.getLogger("build")

    from src.proxy.obs_proxy import OBSProxy
    from src.proxy.gitee_proxy import GiteeProxy

    for prj in args.project:
        for states in args.state:
            report = ObsPackageBuildReport(prj, states, args.real_name_mapping_file)
            report.get_last_committer(args.token)
            report.dump()
