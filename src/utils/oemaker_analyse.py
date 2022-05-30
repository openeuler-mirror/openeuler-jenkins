# -*- coding: utf-8 -*-
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
# Create: 2022-04-28
# Description: analyse oemaker package list
# **********************************************************************************
"""
import argparse
import os
import re
import xml.etree.ElementTree as ET

from src.constant import Constant
from src.logger import logger
from src.utils.file_operator import FileOperator
from src.utils.shell_cmd import shell_cmd_live
from src.proxy.gitee_proxy import GiteeProxy


class OemakerAnalyse(object):
    """
    analyse oemaker package list
    """
    @staticmethod
    def load_normal_xml(file_path):
        """
        加载oemaker中的normal_x86_64.xml, normal_aarch64.xml, edge_normal_x86_64.xml, edge_normal_aarch64.xml
        :param file_path: xml文件路径
        :return: dict
        """
        group_list_dict = {}
        try:
            content = FileOperator.filereader(file_path)
        except IOError as e:
            logger.error(e)
            return {}
        root = ET.fromstring(content.encode("utf-8"))
        all_groups = root.findall("group")
        for group in all_groups:
            group_id = group.find("id")
            all_packagereqs = group.findall("packagelist/packagereq")
            pkg_list = []
            for one_packagereq in all_packagereqs:
                pkg_list.append(one_packagereq.text)
            group_list_dict[group_id.text] = pkg_list
        return group_list_dict

    @staticmethod
    def load_rpmlist_xml(file_path):
        """
        加载oemaker中的rpmlist.xml
        :param file_path: xml文件路径
        :return: dict
        """
        group_list_dict = {}
        try:
            content = FileOperator.filereader(file_path)
        except IOError as e:
            logger.error(e)
            return {}
        root = ET.fromstring(content.encode("utf-8"))
        all_packagelists = root.findall("packagelist")
        for one_packagelist in all_packagelists:
            packagelist_type = one_packagelist.get("type", "")
            all_packagereqs = one_packagelist.findall("packagereq")
            pkg_list = []
            for one_packagereq in all_packagereqs:
                pkg_list.append(one_packagereq.text)
            group_list_dict[packagelist_type] = pkg_list
        return group_list_dict

    @staticmethod
    def load_deny_delete_rpm_list(file_path, ignore_group):
        """
        过滤无效的列表，生成最终禁止删除的包列表组
        :param file_path: xml文件路径
        :param ignore_group: 需要忽略的组
        :return: dict
        """
        group_list_dict = OemakerAnalyse.load_normal_xml(file_path)
        deny_dict = {}
        for key, value in group_list_dict.items():
            if key not in ignore_group:
                deny_dict[key] = value
        return deny_dict

    @staticmethod
    def load_rpmlist(file_path, ignore_group, arch):
        """
        过滤无效的列表，生成最终禁止删除的包列表组
        :param file_path: xml文件路径
        :param ignore_group: 需要忽略的组
        :param arch: 架构
        :return: dict
        """
        group_list_dict = OemakerAnalyse.load_rpmlist_xml(file_path)
        deny_dict = {}
        for key, value in group_list_dict.items():
            if key not in ignore_group and (not any([item for item in Constant.SUPPORT_ARCH if key.endswith(item)])
                                            or arch in key):
                deny_dict[key] = value
        return deny_dict

    @staticmethod
    def get_deny_delete_list(branch, arch, gitee_token, oecp_json_path):
        """
        获取oecp删除包列表中被禁止删除的包列表
        :param branch: 分支
        :param arch: 架构
        :param gitee_token: gitee token
        :param oecp_json_path: oecp结果文件
        :return: list
        """
        try:
            oecp_dict = FileOperator.filereader(oecp_json_path, "json")
        except IOError as e:
            logger.error(e)
            return []

        try:
            need_check_delete_rpm_list = oecp_dict["compare_details"]["less"]["less_details"]
        except KeyError as e:
            logger.info("the json file does not have key:%s", e)
            return []

        if not need_check_delete_rpm_list:
            return []

        for index, value in enumerate(need_check_delete_rpm_list):
            match_result = re.match(r"^(.+)-.+-.+", value)
            need_check_delete_rpm_list[index] = match_result.group(1)
        logger.info("%s rpms to be deleted: %s", len(need_check_delete_rpm_list), need_check_delete_rpm_list)

        # download oemaker repo
        if os.path.exists('oemaker'):
            ret, out, _ = shell_cmd_live('rm -rf oemaker', cap_out=True, cmd_verbose=False)
            if ret:
                logger.error("delete oemaker failed, %s\n%s", ret, out)
                raise IOError("delete old oemaker project error")

        fetch_cmd = 'git clone -b {} --depth 1 https://{}@gitee.com/src-openeuler/oemaker'.format(branch, gitee_token)
        ret, out, _ = shell_cmd_live(fetch_cmd, cap_out=True, cmd_verbose=False)
        if ret:
            logger.error("git fetch failed, %s\n%s", ret, out)
            raise IOError("clone oemaker error")

        deny_dict_dict = {
            "rpmlist.xml": OemakerAnalyse.load_rpmlist("oemaker/rpmlist.xml", ["exclude", "src_exclude"], arch),
            "normal_{}.xml".format(arch): OemakerAnalyse.load_deny_delete_rpm_list(
                "oemaker/normal_{}.xml".format(arch), []),
            "edge_normal_{}.xml".format(arch): OemakerAnalyse.load_deny_delete_rpm_list(
                "oemaker/edge_normal_{}.xml".format(arch), [])
        }

        result_deny_list = []
        for xml_name, dict_content in deny_dict_dict.items():
            for key, value in dict_content.items():
                common_list = list(set(need_check_delete_rpm_list).intersection(set(value)))
                if common_list:
                    result_deny_list.extend(common_list)
                    logger.error("%s: delete %s, id or type is %s", xml_name, common_list, key)

        return list(set(result_deny_list))


if "__main__" == __name__:
    parser = argparse.ArgumentParser()
    parser.add_argument("--branch", type=str, dest="branch", help="branch")
    parser.add_argument("--arch", type=str, dest="arch", help="arch")
    parser.add_argument("--oecp_json_path", type=str, dest="oecp_json_path", help="oecp_json_path")
    parser.add_argument("--owner", type=str, dest="owner", help="owner")
    parser.add_argument("--repo", type=str, dest="repo", help="repo")
    parser.add_argument("--gitee_token", type=str, dest="gitee_token", help="gitee_token")
    parser.add_argument("--prid", type=str, dest="prid", help="prid")

    args = parser.parse_args()

    logger.info("check oemaker rpm-delete start")

    deny_delete_list = OemakerAnalyse.get_deny_delete_list(args.branch, args.arch,
                                                           args.gitee_token, args.oecp_json_path)
    if not deny_delete_list:
        logger.info("check oemaker rpm-delete pass")
    else:
        logger.info("check oemaker rpm-delete not pass")
        gp = GiteeProxy(args.owner, args.repo, args.gitee_token)
        gp.comment_pr(args.prid, "Forbidden delete rpm(s) {} in {}, which is/are list in oemaker. "
                                 "You should contact sig-release before merge this pull request.".format(
            ", ".join(deny_delete_list), args.arch))

