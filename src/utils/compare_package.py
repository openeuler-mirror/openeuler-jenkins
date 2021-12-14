# -*- encoding=utf-8 -*-
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
# Create: 2021-12-01
# Description: check compare package
# **********************************************************************************
"""
import os
import json
import logging
import prettytable as pt

class ComparePackage(object):
    """compare package functions"""
    
    SUCCESS="SUCCESS"
    FAILED="FAILED"
    all_check_item = ["rpm abi", "rpm kabi", "drive kabi", "rpm jabi", "rpm config",
                  "rpm kconfig", "rpm provides", "rpm requires", "rpm files"]

    def __init__(self, logger=logging):
        self.logger = logger

    def _get_dict(self, key_list, data):
        """
        获取字典value
        :param key_list: key列表
        :param data: 字典
        :return:
        """
        value = data
        try:
            for key in key_list:
                value = value.get(key)
        except (KeyError, TypeError): 
            value = None
        return value

    def _show_rpm_diff(self, compare_details):
        """
        输出rpm包差异
        :param compare_details:差异详情
        :return:
        """
        tb = pt.PrettyTable(hrules=True)
        title = "Table of Changed Rpms"
        tb.field_names = ["added rpms", "deleted rpms", "changed rpms"]
        diff_rpm = []

        for key in ["more", "less", "diff"]:
            key_list = [key, "%s_details" % key]
            details = self._get_dict(key_list, compare_details)
            if details:
                if key == "diff":
                    diff_rpm_name = []
                    for rpm in details:
                        old_rpm_name = self._get_dict([rpm, "name", "old"], details)
                        diff_rpm_name.append(old_rpm_name)
                    diff_rpm.append("\n".join(diff_rpm_name))
                else:
                    diff_rpm.append("\n".join(details))
            else:
                diff_rpm.append("")

        tb.add_row(diff_rpm)
        self.logger.info(" %s\n%s", title, tb)
        tb.clear()

    def _get_check_item_dict(self, all_item_dict, diff_details):
        """
        获取检查项详情字典
        :param all_item_dict:
        :param diff_details:
        :return:
        """
        rpm_name_list = diff_details.keys()

        for check_item in self.all_check_item:
            item_dict = all_item_dict.get(check_item) if all_item_dict.get(check_item) else {}
            for rpm_name in rpm_name_list:
                result = self._get_dict([rpm_name, check_item], diff_details)
                if result:
                    item_dict[rpm_name] = result
            if item_dict:
                all_item_dict[check_item] = item_dict

    def _show_diff_details(self, diff_details):
        """
        显示有diff差异的rpm包的所有差异详情
        :param diff_details:
        :return:
        """
        all_item_dict = {}
        self._get_check_item_dict(all_item_dict, diff_details)

        for item in self.all_check_item:
            item_result = all_item_dict.get(item)
            if not item_result:
                continue
            item_name = item.replace("rpm ", "")
            title = "Table of Check %s Result" % (item_name.capitalize())
            tb = pt.PrettyTable(hrules=True)
            tb.field_names = ["rpm name", "added %s" % item_name, "deleted %s " % item_name, "changed %s" % item_name]
            for rpm in item_result:
                rpm_details = item_result.get(rpm)
                more_value = less_value = diff_values = ""

                for key, value in rpm_details.items():
                    if key == "more":
                        more_value = "\n".join(value)
                    elif key == "less":
                        less_value = "\n".join(value)
                    elif key == "diff":
                        diff_value = value.get("old")
                        diff_values = "\n".join(diff_value)
                tb.add_row([rpm, more_value, less_value, diff_values])

            self.logger.info(" %s\n%s", title, tb)
            tb.clear()

    def output_result_to_console(self, json_file, ignore, repo):
        """
        解析结果文件并输出展示到jenkins上
        :param json_file: 结果文件json
        :param pr_link:
        :param ignore:
        :param repo:
        :param check_result_file:
        :param pr_commit_json_file:
        :return:
        """
        all_data = {}
        if ignore:
            return self.SUCCESS

        if not os.path.exists(json_file):
            self.logger.error("%s not exists", os.path.basename(json_file))
            return self.FAILED

        with open(json_file, "r") as data:
            try:
                all_data = json.load(data)
                compare_result = all_data.get("compare_result")
                compare_details = all_data.get("compare_details")
            except (json.decode.JSONDecodeError, KeyError):
                self.logger.error("%s is not an illegal json file", os.path.basename(json_file))
                return self.FAILED

        self.logger.info("compare <%s> package %s" % (repo, compare_result))

        # 显示rpm包的变更
        self._show_rpm_diff(compare_details)
        # 显示有变更的rpm包的具体差异详情
        diff_details = self._get_dict(["diff", "diff_details"], compare_details)
        if diff_details:
            self._show_diff_details(diff_details)

        if compare_result == "pass":
            return self.SUCCESS
        else:
            return self.FAILED
