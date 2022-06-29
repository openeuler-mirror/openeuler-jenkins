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
# Create: 2021-4-22
# Description: generate scanoss sbom file
# **********************************************************************************
"""

import argparse
import os

from src.utils.file_operator import FileOperator


class ScanossSbomGenerator(object):
    """generate scanoss sbom file"""

    def __init__(self, organization, repo):
        """
        initial
        :param organization:
        :param repo:
        :return:
        """
        self.organization = organization
        self.repo = repo

    def get_final_config_dict(self, config_data):
        """
        check config yaml format and return final config data
        :param config_data: orign config dict data
        :return:
        """
        if not config_data or not isinstance(config_data, dict):
            raise KeyError("scanoss config error")
        organ_config_data = config_data.get(self.organization)
        if not organ_config_data or not isinstance(organ_config_data, dict):
            raise KeyError("scanoss config error")
        default_deny_list = organ_config_data.get("default_deny_list")
        extra_deny_list = organ_config_data.get("extra_deny_list")
        if not isinstance(default_deny_list, list) or not isinstance(extra_deny_list, dict):
            raise KeyError("scanoss config error")

        result_deny_list = []
        for default_deny_item in default_deny_list:
            if not default_deny_item or not isinstance(default_deny_item, str):
                raise KeyError("scanoss config error")
            result_deny_list.append({"publisher": default_deny_item, "name": self.repo})

        for extra_deny_item in extra_deny_list.get(self.repo, []):
            if not isinstance(extra_deny_item, dict) or not extra_deny_item \
                    or extra_deny_item.keys() - set(["publisher", "name"]):
                raise KeyError("scanoss config error")
            result_deny_list.append(extra_deny_item)
        return {"comment": "Component Denylist", "components": result_deny_list}

    def generator(self, target_path):
        """
        create ignore community or repository list file of scanoss
        :param target_path:
        :return:
        """
        cur_path = os.path.abspath(os.path.dirname(__file__))
        config_file = os.path.join(cur_path, "../conf/scanoss_deny_list.yaml")

        all_data = FileOperator.filereader(config_file, "yaml")
        final_config_dict = self.get_final_config_dict(all_data)
        FileOperator.filewriter(target_path, final_config_dict, "json")


if "__main__" == __name__:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=str, dest="repo", help="repo name")
    parser.add_argument("--organization", type=str, dest="organization", help="src-openeuler or openeuler")
    parser.add_argument("--target_path", type=str, dest="target_path", help="target sbom file path")
    args = parser.parse_args()

    ScanossSbomGenerator(args.organization, args.repo).generator(args.target_path)

