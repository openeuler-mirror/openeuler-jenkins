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
# Create: 2020-09-23
# Description: comment pr with build result 
# **********************************************************************************
"""

import os
import re
import stat
import sys
import logging.config
import json
import argparse
import warnings
import yaml

from yaml.error import YAMLError
from src.ac.framework.ac_result import ACResult, SUCCESS
from src.proxy.gitee_proxy import GiteeProxy
from src.proxy.kafka_proxy import KafkaProducerProxy
from src.proxy.jenkins_proxy import JenkinsProxy
from src.utils.dist_dataset import DistDataset


class Comment(object):
    """
    comments process
    """

    def __init__(self, pr, jenkins_proxy, *check_item_comment_files):
        """

        :param pr: pull request number
        """
        self._pr = pr
        self._check_item_comment_files = check_item_comment_files
        self._up_builds = []
        self._up_up_builds = []
        self._get_upstream_builds(jenkins_proxy)
        self.ac_result = {}
        self.compare_package_result = {}
        self.check_item_result = {}

    @staticmethod
    def _get_rpm_name(rpm):
        """
       返回rpm包名称
       :param rpm:
       :return:
       """
        rpm_name = re.match(r"^(.+)-.+-.+", rpm)

        if rpm_name:
            return rpm_name.group(1)
        else:
            logger.error(f"Prase rpm name error: {rpm}")
            return rpm

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

    def comment_build(self, gitee_proxy):
        """
        构建结果
        :param jenkins_proxy:
        :param gitee_proxy:
        :return:
        """
        comments = self._comment_build_html_format()
        gitee_proxy.comment_pr(self._pr, "\n".join(comments))

        return "\n".join(comments)

    def comment_compare_package_details(self, gitee_proxy, check_result_file):
        """
        compare package结果上报

        :param gitee_proxy:
        :param check_result_file:
        :return:
        """
        comments = self._comment_of_compare_package_details(check_result_file)
        gitee_proxy.comment_pr(self._pr, "\n".join(comments))

        return "\n".join(comments)

    def comment_at(self, committer, gitee_proxy):
        """
        通知committer
        @committer
        :param committer:
        :param gitee_proxy:
        :return:
        """
        gitee_proxy.comment_pr(self._pr, "@{}".format(committer))

    def check_build_result(self):
        """
        build result check
        :return:
        """
        build_result = sum([ACResult.get_instance(build["result"]) for build in self._up_builds], SUCCESS)
        return build_result

    def _get_upstream_builds(self, jenkins_proxy):
        """
        get upstream builds
        :param jenkins_proxy:
        :return:
        """
        base_job_name = os.environ.get("JOB_NAME")
        base_build_id = os.environ.get("BUILD_ID")
        base_build_id = int(base_build_id)
        logger.debug("base_job_name: %s, base_build_id: %s", base_job_name, base_build_id)
        base_build = jenkins_proxy.get_build_info(base_job_name, base_build_id)
        logger.debug("get base build")
        self._up_builds = jenkins_proxy.get_upstream_builds(base_build)
        if self._up_builds:
            logger.debug("get up_builds")
            self._up_up_builds = jenkins_proxy.get_upstream_builds(self._up_builds[0])

    def _comment_build_html_format(self):
        """
        组装构建信息，并评论pr
        :param jenkins_proxy: JenkinsProxy object
        :return:
        """
        comments = ["<table>", self.comment_html_table_th()]

        if self._up_up_builds:
            logger.debug("get up_up_builds")
            comments.extend(self._comment_of_ac(self._up_up_builds[0]))
        if self._up_builds:
            comments.extend(self._comment_of_check_item(self._up_builds))

        comments.append("</table>")
        return comments

    def _comment_of_ac(self, build):
        """
        组装门禁检查结果
        :param build: Jenkins Build object，门禁检查jenkins构建对象
        :return:
        """
        if "ACL" not in os.environ:
            logger.debug("no ac check")
            return []

        try:
            acl = json.loads(os.environ["ACL"])
            logger.debug("ac result: %s", acl)
        except ValueError:
            logger.exception("invalid ac result format")
            return []

        comments = []

        for index, item in enumerate(acl):
            ac_result = ACResult.get_instance(item["result"])
            if index == 0:
                build_url = build["url"]
                comments.append(self.__class__.comment_html_table_tr(
                    item["name"], ac_result.emoji, ac_result.hint,
                    "{}{}".format(build_url, "console"), build["number"], rowspan=len(acl)))
            else:
                comments.append(self.__class__.comment_html_table_tr_rowspan(
                    item["name"], ac_result.emoji, ac_result.hint))
            self.ac_result[item["name"]] = ac_result.hint
        logger.info("ac comment: %s", comments)

        return comments

    def _comment_of_compare_package_details(self, check_result_file):
        """
        compare package details
        :param:
        :return:
        """
        comments = []
        comments_title = ["<table> <tr><th>Arch Name</th> <th>Check Items</th> <th>Rpm Name</th> <th>Check Result</th> "
                          "<th>Build Details</th></tr>"]

        def match(name, comment_file):
            if "aarch64" in name and "aarch64" in comment_file:
                return True, "aarch64"
            if "x86-64" in name and "x86_64" in comment_file:
                return True, "x86_64"
            return False, ""

        for result_file in check_result_file.split(","):
            logger.info("check_result_file: %s", result_file)
            if not os.path.exists(result_file):
                logger.info("%s not exists", result_file)
                continue
            for build in self._up_builds:
                arch_cmp_result = "SUCCESS"
                name = JenkinsProxy.get_job_path_from_job_url(build["url"])
                logger.info("check build %s", name)
                arch_result, arch_name = match(name, result_file)
                if not arch_result:  # 找到匹配的jenkins build
                    continue
                logger.info("build \"%s\" match", name)

                status = build["result"]
                logger.info("build state: %s", status)
                content = {}
                if ACResult.get_instance(status) == SUCCESS:  # 保证build状态成功
                    with open(result_file, "r") as f:
                        try:
                            content = yaml.safe_load(f)
                        except YAMLError:  # yaml base exception
                            logger.exception("illegal yaml format of compare package comment file ")
                logger.info("comment: %s", content)
                for index, item in enumerate(content):
                    rpm_name = content.get(item)
                    check_item = item.replace(" ", "_")
                    result = "FAILED" if rpm_name else "SUCCESS"
                    if item == "delete_rpms" and rpm_name:
                        for single_result in rpm_name:
                            if single_result.get("RPM Level") in ["level3", "level4"] and single_result.get(
                                    "Obsoletes") == "yes" and single_result.get("Provides") == "yes":
                                result = "WARNING"
                            else:
                                result = "FAILED"
                        rpm_name = [self._get_rpm_name(single.get('Name', '')) for single in rpm_name]
                    if result == "FAILED":
                        arch_cmp_result = "FAILED"
                    compare_result = ACResult.get_instance(result)
                    if index == 0:
                        comments.append("<tr><td rowspan={}>compare_package({})</td> <td>{}</td> <td>{}</td> "
                                        "<td>{}<strong>{}</strong></td> <td rowspan={}><a href={}>{}{}</a></td></tr>"
                                        .format(len(content), arch_name, check_item, "<br>".join(rpm_name),
                                                compare_result.emoji, compare_result.hint, len(content),
                                                "{}{}".format(build["url"], "console"), "#", build["number"]))
                    else:
                        comments.append("<tr><td>{}</td> <td>{}</td> <td>{}<strong>{}</strong></td></tr>".format(
                            check_item, "<br>".join(rpm_name), compare_result.emoji, compare_result.hint))
                self.compare_package_result[arch_name] = arch_cmp_result
        if comments:
            comments = comments_title + comments
            comments.append("</table>")
        logger.info("compare package comment: %s", comments)

        return comments

    def _comment_of_check_item(self, builds):
        """
        check item comment
        :param builds:
        :return:
        """
        comments = []

        def match(name, comment_file):
            if "aarch64" in name and "aarch64" in comment_file:
                return True
            if "x86-64" in name and "x86_64" in comment_file:
                return True
            return False

        check_branches = None
        if os.path.exists('check_build.yaml'):
            with open('check_build.yaml', 'r') as f:
                check_branches = yaml.safe_load(f)
        tbranch = os.getenv('tbranch')
        if check_branches and tbranch not in check_branches.keys():
            return comments
        for build in builds:
            name, _ = JenkinsProxy.get_job_path_build_no_from_build_url(build["url"])
            status = build["result"]
            ac_result = ACResult.get_instance(status)

            if "x86-64" in name:
                arch = "x86_64"
            elif "aarch64" in name:
                arch = "aarch64"
            else:
                arch = name.split("/")[-2]
            if check_branches:
                arches = check_branches.get(tbranch)
                if arches:
                    if arch in arches.keys() and not arches.get(arch):
                        continue
            for check_item_comment_file in self._check_item_comment_files:
                if not os.path.exists(check_item_comment_file):
                    logger.info("%s not exists", check_item_comment_file)
                    continue
                if match(name, check_item_comment_file):
                    with open(check_item_comment_file, "r") as data:
                        try:
                            json_data = json.load(data)
                        except json.decoder.JSONDecodeError:
                            logger.error("%s is not an legal json file", os.path.basename(check_item_comment_file))
                            json_data = None
                            with open(check_item_comment_file, "r") as data:
                                try:
                                    yaml_data = yaml.safe_load(data)
                                except YAMLError:
                                    logger.error("%s is not an legal yaml file",
                                                 os.path.basename(check_item_comment_file))
                        else:
                            yaml_data = None
                comment = self._comment_of_combine_item(json_data, yaml_data, arch, build, ac_result)
                comments.extend(comment)
        return comments

    def _comment_of_combine_item(self, json_data, yaml_data, arch, build, ac_result):
        """
        check item combine comment
        :param json_data:
        :param yaml_data:
        :param arch:
        :param build:
        :return:
        """
        comments = []
        arch_dict = {}
        check_item_info = {}
        if json_data:
            single_build_result = self._get_dict(["single_build_check", "current_result"], json_data)
            check_item_info["check_install"] = self._get_dict(["single_install_check",
                                                               "current_result"], json_data)
        elif yaml_data:
            single_build_result = build["result"]
            check_item_info["check_install"] = yaml_data[0]["result"]
        else:
            single_build_result = build["result"]
        logger.info(f"single_build_result:{single_build_result}")
        logger.info(f"check_item_info:{check_item_info}")
        if os.path.exists("support_arch"):
            with open("support_arch", "r") as s_file:
                if arch not in s_file.readline():
                    ac_result = ACResult.get_instance("EXCLUDE")
                    item_num = 2
                else:
                    ac_result = ACResult.get_instance(single_build_result)
                    item_num = len(check_item_info) - list(check_item_info.values()).count(None) + 1
        else:
            ac_result = ACResult.get_instance(single_build_result)
            item_num = len(check_item_info) - list(check_item_info.values()).count(None) + 1

        comments.append("<tr><td rowspan={}>{}</td> <td>{}</td> <td>{}<strong>{}</strong></td> " \
                        "<td rowspan={}><a href={}>#{}</a></td></tr>".format(
            item_num, arch, "check_build", ac_result.emoji, ac_result.hint, item_num,
            "{}{}".format(build["url"], "console"), build["number"]))
        arch_dict["check_build"] = ac_result.hint

        if ac_result.hint == "EXCLUDE":
            comments.append("<tr><td>{}</td> <td>{}<strong>{}</strong></td>".format(
                "check_install", ac_result.emoji, ac_result.hint))
            arch_dict["check_install"] = ac_result.hint
        else:
            for check_item, check_result in check_item_info.items():
                if check_result:
                    check_result = ACResult.get_instance(check_result)
                    comments.append("<tr><td>{}</td> <td>{}<strong>{}</strong></td>".format(
                        check_item, check_result.emoji, check_result.hint))
                    arch_dict[check_item] = check_result.hint
        self.check_item_result[arch] = arch_dict
        logger.info("check item comment: %s", comments)

        return comments

    @classmethod
    def comment_html_table_th(cls):
        """
        table header
        """
        return "<tr><th colspan=2>Check Name</th> <th>Build Result</th> <th>Build Details</th></tr>"

    @classmethod
    def comment_html_table_tr(cls, name, icon, status, href, build_no, hashtag=True, rowspan=1):
        """
        one row or span row
        """
        return "<tr><td colspan=2>{}</td> <td>{}<strong>{}</strong></td> " \
               "<td rowspan={}><a href={}>{}{}</a></td></tr>".format(
            name, icon, status, rowspan, href, "#" if hashtag else "", build_no)

    @classmethod
    def comment_html_table_tr_rowspan(cls, name, icon, status):
        """
        span row
        """
        return "<tr><td colspan=2>{}</td> <td>{}<strong>{}</strong></td></tr>".format(name, icon, status)

    def _get_job_url(self, comment_url):
        """
        get_job_url
        :param url:
        :return:
        """
        build_urls = {"trigger": self._up_up_builds[0]["url"],
                      "comment": os.path.join(comment_url, os.environ.get("BUILD_ID"))
                      }
        for build in self._up_builds:
            arch = ""
            try:
                arch_index = 3
                list_step = 2
                if build["url"]:
                    job_path = re.sub(r"http[s]?://", "", build["url"])
                    arch = job_path.split("/")[::list_step][arch_index]
            except IndexError:
                logger.info("get arch from job failed, index error.")
            except KeyError:
                logger.info("not find build url key")
            if arch:
                build_urls[arch] = build["url"]

        return build_urls

    def _get_all_job_result(self, check_details):
        """
        get_all_job_result
        :return:
        """

        check_details["static_code"] = self.ac_result
        for arch, arch_result in self.check_item_result.items():
            if self.compare_package_result.get(arch):
                arch_result["compare_package"] = self.compare_package_result.get(arch)
            check_details[arch] = arch_result

        return check_details

    def get_all_result_to_kafka(self, comment_url):
        """
        名称            类型    必选  说明
        build_urls      字典    是    包含多个门禁工程链接和显示文本
        check_total     字符串  是    门禁整体结果
        check_details   字典    是    门禁各个检查项结果
        :return:
        """
        check_details = {}
        build_urls = self._get_job_url(comment_url)
        self._get_all_job_result(check_details)

        if self.check_build_result() == SUCCESS:
            check_total = 'SUCCESS'
        else:
            check_total = 'FAILED'

        all_dict = {"build_urls": build_urls,
                    "check_total": check_total,
                    "check_details": check_details
                    }
        logger.info("all_dict = %s", all_dict)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        modes = stat.S_IWUSR | stat.S_IRUSR
        try:
            with os.fdopen(os.open("build_result.yaml", flags, modes), "w") as f:
                yaml.safe_dump(all_dict, f)
        except IOError:
            logger.exception("save build result file exception")


def init_args():
    """
    init args
    :return:
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", type=int, dest="pr", help="pull request number")
    parser.add_argument("-m", type=str, dest="comment_id", help="uniq comment id")
    parser.add_argument("-c", type=str, dest="committer", help="commiter")
    parser.add_argument("-o", type=str, dest="owner", help="gitee owner")
    parser.add_argument("-r", type=str, dest="repo", help="repo name")
    parser.add_argument("-t", type=str, dest="gitee_token", help="gitee api token")

    parser.add_argument("-b", type=str, dest="jenkins_base_url", default="https://openeulerjenkins.osinfra.cn/",
                        help="jenkins base url")
    parser.add_argument("-u", type=str, dest="jenkins_user", help="repo name")
    parser.add_argument("-j", type=str, dest="jenkins_api_token", help="jenkins api token")
    parser.add_argument("-f", type=str, dest="check_result_file", default="", help="compare package check item result")
    parser.add_argument("-a", type=str, dest="check_item_comment_files", nargs="*", help="check item comment files")

    parser.add_argument("--disable", dest="enable", default=True, action="store_false", help="comment to gitee switch")

    return parser.parse_args()


if "__main__" == __name__:
    args = init_args()
    if not args.enable:
        sys.exit(0)

    _ = not os.path.exists("log") and os.mkdir("log")
    logger_conf_path = os.path.realpath(os.path.join(os.path.realpath(__file__), "../../conf/logger.conf"))
    logging.config.fileConfig(logger_conf_path)
    logger = logging.getLogger("build")

    dd = DistDataset()
    dd.set_attr_stime("comment.job.stime")

    # gitee pr tag
    gp = GiteeProxy(args.owner, args.repo, args.gitee_token)
    gp.delete_tag_of_pr(args.pr, "ci_processing")

    jp = JenkinsProxy(args.jenkins_base_url, args.jenkins_user, args.jenkins_api_token)
    url, build_time, reason = jp.get_job_build_info(os.environ.get("JOB_NAME"), int(os.environ.get("BUILD_ID")))
    dd.set_attr_ctime("comment.job.ctime", build_time)
    dd.set_attr("comment.job.link", url)
    dd.set_attr("comment.trigger.reason", reason)

    dd.set_attr_stime("comment.build.stime")

    comment = Comment(args.pr, jp, *args.check_item_comment_files) \
        if args.check_item_comment_files else Comment(args.pr, jp)
    logger.info("comment: build result......")
    comment_content = comment.comment_build(gp)
    dd.set_attr_etime("comment.build.etime")
    dd.set_attr("comment.build.content.html", comment_content)

    if comment.check_build_result() == SUCCESS:
        gp.delete_tag_of_pr(args.pr, "ci_failed")
        gp.create_tags_of_pr(args.pr, "ci_successful")
        dd.set_attr("comment.build.tags", ["ci_successful"])
        dd.set_attr("comment.build.result", "successful")
        if args.check_result_file:
            comment.comment_compare_package_details(gp, args.check_result_file)
    else:
        gp.delete_tag_of_pr(args.pr, "ci_successful")
        gp.create_tags_of_pr(args.pr, "ci_failed")
        dd.set_attr("comment.build.tags", ["ci_failed"])
        dd.set_attr("comment.build.result", "failed")
    if args.owner != "openeuler":
        comment.get_all_result_to_kafka(url)

    logger.info("comment: at committer......")
    comment.comment_at(args.committer, gp)

    dd.set_attr_etime("comment.job.etime")

    # suppress python warning
    warnings.filterwarnings("ignore")
    logging.getLogger("elasticsearch").setLevel(logging.WARNING)
    logging.getLogger("kafka").setLevel(logging.WARNING)

    # upload to es
    kp = KafkaProducerProxy(brokers=os.environ["KAFKAURL"].split(","))
    query = {"term": {"id": args.comment_id}}
    script = {"lang": "painless", "source": "ctx._source.comment = params.comment", "params": dd.to_dict()}
    kp.send("openeuler_statewall_ci_ac", key=args.comment_id, value=dd.to_dict())
