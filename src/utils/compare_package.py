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
# Create: 2021-12-01
# Description: check compare package
# **********************************************************************************
"""
import os
import json
import logging
import re
import prettytable as pt
import yaml

from src.constant import Constant


class ComparePackage(object):
    """compare package functions"""

    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    MAX_SHOW_DATA_NUM = 5
    MIN_COLUMN_WIDTH = 16
    MAX_TABLE_WIDTH = 150

    all_check_item = ["rpm abi", "rpm kabi", "drive kabi", "rpm jabi", "rpm config", "rpm service",
                      "rpm kconfig", "rpm provides", "rpm requires", "rpm files", "rpm cmd", "rpm header", "rpm lib"]

    def __init__(self, logger):
        self.logger = logger

    def _get_dict(self, key_list, data):
        """
        获取字典value
        :param key_list: key列表
        :param data: 字典
        :return:
        """
        value = data
        for key in key_list:
            if value and isinstance(value, dict):
                value = value.get(key)
            else:
                return None
        return value

    def _rpm_name(self, rpm):
        """
        返回rpm包名称
        :param rpm:
        :return:
        """
        match_result = re.match(r"^(.+)-.+-.+", rpm)

        if match_result:
            return match_result.group(1)
        else:
            return rpm

    def _show_rpm_diff(self, compare_details):
        """
        输出rpm包差异
        :param compare_details:差异详情
        :return:
        """
        tb = pt.PrettyTable(hrules=True, min_width=self.MIN_COLUMN_WIDTH, max_table_width=self.MAX_TABLE_WIDTH)
        title = "Table of Changed Rpms"
        tb.field_names = ["added rpms", "deleted rpms", "changed rpms", "effected rpms"]
        diff_rpm = []

        for key in ["more", "less", "diff"]:
            key_list = [key, "%s_details" % key]
            details = self._get_dict(key_list, compare_details)
            if details:
                if key == "diff":
                    diff_rpm_name = []
                    effect_rpms = []
                    for rpm in details:
                        old_rpm_name = self._get_dict([rpm, "name", "old"], details)
                        effect_rpm = self._get_dict([rpm, "rpm symbol", "total_effect_other_rpm"], details)
                        diff_rpm_name.append(old_rpm_name)
                        if isinstance(effect_rpm, list):
                            effect_rpms.extend(effect_rpm)
                    diff_rpm.append("\n".join(diff_rpm_name))
                    diff_rpm.append("\n".join(effect_rpms))
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
            tb = pt.PrettyTable(hrules=True, min_width=self.MIN_COLUMN_WIDTH, max_table_width=self.MAX_TABLE_WIDTH)
            tb.field_names = ["rpm name", "added %s" % item_name, "deleted %s " % item_name, "changed %s" % item_name]
            for rpm in item_result:
                rpm_details = item_result.get(rpm)
                more_value = less_value = diff_values = ""

                for key, value in rpm_details.items():
                    if isinstance(value, list) and len(value) > self.MAX_SHOW_DATA_NUM:
                        value = value[:self.MAX_SHOW_DATA_NUM]
                        value.append("...")
                    if key == "more":
                        more_value = "\n".join(value)
                    elif key == "less":
                        less_value = "\n".join(value)
                    elif key in ["diff", "changed"]:
                        diff_value = value.get("old")
                        if len(diff_value) > self.MAX_SHOW_DATA_NUM:
                            diff_value = diff_value[:self.MAX_SHOW_DATA_NUM]
                            diff_value.append("...")
                        diff_values = "\n".join(diff_value)
                tb.add_row([rpm, more_value, less_value, diff_values])

            self.logger.info(" %s\n%s", title, tb)
            tb.clear()

    def output_result_to_console(self, json_file, pr_link, ignore, repo, check_result_file, pr_commit_json_file):
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
        if ignore:
            return self.SUCCESS

        status, all_data = self._read_json_file(json_file, dict)
        if not status:
            return self.FAILED
        # 写入pr link到json文件, 写入接口变更原因到文件
        self._write_compare_package_file(json_file, all_data, pr_link, pr_commit_json_file)

        compare_result = all_data.get("compare_result")
        compare_details = all_data.get("compare_details")
        if not all([compare_result, isinstance(compare_result, str),
                    compare_details, isinstance(compare_details, dict)]):
            self.logger.error("compare result format error")
            return self.FAILED

        # 生成各检查项的结果，输出到check_result_file文件中，后面comment时会用到
        result_dict = self._result_to_table(compare_details)
        try:
            with open(check_result_file, "w") as f:
                yaml.safe_dump(result_dict, f)  # list
                self.logger.info("output check result to comment file")
        except IOError:
            self.logger.exception("save compare package comment exception")

        self.logger.info("compare <%s> package %s" % (repo, compare_result))
        # 显示rpm包的变更
        self._show_rpm_diff(compare_details)
        # 显示有变更的rpm包的具体差异详情
        diff_details = self._get_dict(["diff", "diff_details"], compare_details)
        if diff_details:
            self._show_diff_details(diff_details)
            self._show_each_rpm_effect_other_rpm_details(diff_details)

        if compare_result == "pass":
            return self.SUCCESS
        else:
            return self.FAILED

    def _read_json_file(self, json_file, expect_result_type):
        """
        读取json文件并检查结果类型
        :param json_file: 结果文件json
        :param expect_result_type: 期待返回结果类型
        :return:
        """
        status = False
        all_data = {}
        if not os.path.exists(json_file):
            self.logger.error("%s not exists", os.path.basename(json_file))
            return status, all_data

        with open(json_file, "r") as data:
            try:
                all_data = json.load(data)
            except json.decode.JSONDecodeError:
                self.logger.error("%s is not an illegal json file", os.path.basename(json_file))
                return status, all_data
        try:
            if all_data and isinstance(all_data, expect_result_type):
                status = True
            else:
                self.logger.error("%s is not an illegal json file", os.path.basename(json_file))
        except TypeError:
            self.logger.error("%s is not an illegal type", expect_result_type)

        return status, all_data

    def _get_rule_data(self, data):
        """
        根据正则表达式过滤数据
        :param data:
        :return: data
        """
        remove_data = []
        for one_data in data:
            for rule in Constant.COMPARE_PACKAGE_BLACKLIST:
                pattern = re.compile(rule)
                match_result = pattern.match(one_data)
                if match_result:
                    remove_data.append(one_data)
                    break
        for one_data in remove_data:
            data.remove(one_data)
        return data

    def _get_new_json_data(self, all_data):
        """
        删除字典中的正则匹配到的数据
        :param all_data:
        :return: all_data
        """
        diff_details = self._get_dict(["compare_details", "diff", "diff_details"], all_data)
        if not diff_details:
            return all_data
        for rpm_key, rpm_details in diff_details.items():
            rpm_files = rpm_details.get("rpm files")
            if not rpm_files:
                continue
            rpm_files_dict = {}
            for item, data in rpm_files.items():
                new_data = self._get_rule_data(data)
                if new_data:
                    rpm_files_dict[item] = new_data
            diff_details[rpm_key]["rpm files"] = rpm_files_dict
        all_data["compare_details"]["diff"]["diff_details"] = diff_details
        return all_data

    def _write_compare_package_file(self, json_file, all_data, pr_link, pr_commit_json_file):
        """
        写接口变更检查结果文件，新增pr链接和接口变更检查原因
        :param json_file:
        :param all_data:
        :param pr_commit_json_file:
        :return:
        """
        self._get_new_json_data(all_data)

        with open(json_file, "w") as data:
            all_data["pr_link"] = pr_link
            all_data["pr_changelog"] = self._get_pr_changelog(pr_commit_json_file)
            json.dump(all_data, data)

    def _get_pr_changelog(self, pr_commit_json_file):
        """
        获取更新代码的changelog内容，应承载接口变更检查原因及影响
        :param: pr_commit_json_file: gitee PR提交对应的变更文件信息, json格式
        :return: 返回spec文件中新增的changelog内容
        """
        result = ""
        status, all_data = self._read_json_file(pr_commit_json_file, list)
        if not status:
            return result

        for item in all_data:
            filename = self._get_dict(["filename"], item)
            if filename and filename.endswith(".spec"):
                diff = self._get_dict(["patch", "diff"], item)
                if not diff or not isinstance(diff, str):
                    return result
                loc = diff.find("%changelog")
                if loc == -1:
                    logging.error("changelog not exists in spec file")
                    continue
                lines = diff[loc + 1:].split('\n')
                new_lines = [line[1:] for line in lines if line.startswith('+')]
                result += '\n'.join(new_lines)
        return result

    def _get_check_item_result(self, details):
        """
        获取compare package比较结果各子项的详细信息
        :param details:
        :return:
        {
        "rpm_files": [vala,xxx],
        "rpm_requires": [vala,xxx],
        "rpm_provides": [vala,xxx],
        "rpm_config": [vala,xxx],
        "rpm": [],
        "rpm_abi": [vala,xxx],
        "rpm_cmd": [vala,xxx],
        "rpm_lib": [vala,xxx],
        "rpm_symbol": [111,222,333],
        }
        """
        rpm_dict = {}
        for rpm_name, rpm_details in details.items():
            if not rpm_details and not isinstance(rpm_details, dict):
                self.logger.error("compare result format error")
                continue
            for check_item, item_details in rpm_details.items():
                if check_item == "name":
                    continue
                check_item = "_".join(check_item.split())
                rpm_list = rpm_dict.get(check_item) if rpm_dict.get(check_item) else []
                if item_details:
                    if check_item == "rpm_symbol":
                        rpm_list.extend(item_details.get("total_effect_other_rpm", []))
                    else:
                        rpm_list.append(rpm_name)
                rpm_dict[check_item] = rpm_list
        return rpm_dict

    def _result_to_table(self, compare_details):
        """
        获取compare package比较结果的详细信息
        :param compare_details:
        :return:
        """
        result_dict = {"add_rpms": [], "delete_rpms": []}
        for compare_item in ["more", "less", "diff", "changed"]:
            key_list = [compare_item, "%s_details" % compare_item]
            details = self._get_dict(key_list, compare_details)
            if details and isinstance(details, dict) and compare_item in ["diff", "changed"]:
                rpm_dict = self._get_check_item_result(details)
                result_dict.update(rpm_dict)
            elif details and isinstance(details, list):
                rpm_list = []
                for rpm in details:
                    rpm_list.append(self._rpm_name(rpm))
                if compare_item == "more":
                    result_dict["add_rpms"] = rpm_list
                elif compare_item == "less":
                    result_dict["delete_rpms"] = rpm_list
        return result_dict

    def _show_each_rpm_effect_other_rpm_details(self, diff_details):
        """
        显示每个rpm影响的其他软件包
        :param diff_details:
        "diff": {
            "diff_details": {
                "openssl": {
                    "name": {}
                    "rpm files": {}
                    "rpm requires": {}
                    "rpm symbol": {"total_effect_other_rpm": ["vala-0.42.2-2.oe1.aarch64.rpm"]}}}}
        :return:
        Table of Check rpm symbol Result
        +---------------+-----------------------------+
        |    rpm name   | effected_other_rpm          |
        +---------------+-----------------------------+
        |    openssl    |vala-0.42.2-2.oe1.aarch64.rpm|
        +---------------+-----------------------------+
        |     ...       |          ...                |
        +---------------+-----------------------------+
        """
        title = "Table of Check rpm symbol Result"
        tb = pt.PrettyTable(hrules=True, min_width=self.MIN_COLUMN_WIDTH, max_table_width=self.MAX_TABLE_WIDTH)
        tb.field_names = ["rpm name", "effected_other_rpm"]
        for rpm in diff_details:
            details = self._get_dict([rpm, "rpm symbol", "total_effect_other_rpm"], diff_details)
            value = "\n".join(details) if isinstance(details, list) else []
            tb.add_row([rpm, value]) if value else tb.add_row([rpm, ""])
        self.logger.info(" %s\n%s", title, tb)
        tb.clear()
