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
# Description: comment pr with build result to dashboard
# **********************************************************************************
"""

import os
import argparse
import stat
import time
from datetime import datetime

import yaml

from src.proxy.kafka_proxy import KafkaProducerProxy
from src.logger import logger


class CommentToDashboard(object):
    """
    comments process
    """

    @staticmethod
    def output_build_num(args_list):
        """
        output_build_num
        :param args_list:
        :return:
        """
        build_num_list = []
        build_num_file = "{}_{}_{}_build_num.yaml".format(args_list.owner, args_list.repo, args_list.prid)
        try:
            if os.path.exists(build_num_file):
                with open(build_num_file, "r") as f:
                    build_num_list = yaml.safe_load(f)
        except yaml.MarkedYAMLError:
            logger.exception("Read trigger build number file exception, yaml format error")
        if args_list.trigger_build_id not in build_num_list:
            build_num_list.append(args_list.trigger_build_id)
        logger.info("build_num_list = %s", build_num_list)
        flags = os.O_WRONLY | os.O_CREAT
        modes = stat.S_IWUSR | stat.S_IRUSR
        try:
            with os.fdopen(os.open(build_num_file, flags, modes), "w") as f:
                yaml.safe_dump(build_num_list, f)
        except IOError:
            logger.exception("save build number file exception")

    def get_all_result_to_kafka(self, args_list):
        """
        名称            类型   必选  说明
        pr_url          字符串  是   需要进行上报的pr地址，(pr_url, build_no)共同确定一次门禁结果
        pr_title        字符串  是   pr标题
        pr_create_at    数值    是   pr创建时间戳
        pr_committer    字符串  是   pr提交人
        pr_branch       字符串  是   pr目标分支
        build_no        数值    是   门禁评论工程构建编号，区分同一个pr的多次门禁结果
        build_at        数值    是   门禁触发时间戳
        update_at       数值    是   当前时间对应的时间戳
        build_exception 布尔    是   门禁执行是否异常，异常情况部分字段可以为空
        build_urls      字典    是   包含多个门禁工程链接和显示文本
        build_time      数值    是   整体构建时间(单位秒) trigger触发时间~comment时间
        check_total     字符串  是   门禁整体结果
        check_details   字典    是   门禁各个检查项结果
        :return:
        """
        pr_create_time = round(datetime.timestamp(datetime.strptime(args_list.pr_create_time,
                                                                    '%Y-%m-%dT%H:%M:%S%z')), 1)
        trigger_time = round(datetime.timestamp(datetime.strptime(args_list.trigger_time, '%Y-%m-%dT%H:%M:%S%z')), 1)
        current_time = round(time.time(), 1)

        base_dict = {"pr_title": args_list.pr_title,
                    "pr_url": args_list.pr_url,
                    "pr_create_at": pr_create_time,
                    "pr_committer": args_list.committer,
                    "pr_branch": args_list.tbranch,
                    "build_at": trigger_time,
                    "update_at": current_time,
                    "build_no": args_list.trigger_build_id
                     }
        build_time = round(current_time - trigger_time, 1)
        base_dict["build_time"] = build_time

        self.output_build_num(args_list)
        build_file = "build_result.yaml"
        try:
            if os.path.exists(build_file):
                base_dict["build_exception"] = False
                with open(build_file, "r") as f:
                    comments = yaml.safe_load(f)
                    base_dict.update(comments)
            else:
                base_dict["build_exception"] = True
        except yaml.MarkedYAMLError:
            logger.exception("Read build result file exception, yaml format error")

        logger.info("base_dict = %s", base_dict)
        # upload to es
        kp = KafkaProducerProxy(brokers=os.environ["KAFKAURL"].split(","))
        kp.send("openeuler_statewall_ci_result", key=args_list.comment_id, value=base_dict)


def init_args():
    """
    init args
    :return:
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("-r", type=str, dest="repo", help="repo name")
    parser.add_argument("-c", type=str, dest="committer", help="commiter")
    parser.add_argument("-m", type=str, dest="comment_id", help="uniq comment id")
    parser.add_argument("-g", type=str, dest="trigger_time", help="job trigger time")
    parser.add_argument("-k", type=str, dest="pr_title", help="pull request title")
    parser.add_argument("-t", type=str, dest="pr_create_time", help="pull request create time")
    parser.add_argument("-b", type=str, dest="tbranch", help="target branch")
    parser.add_argument("-u", type=str, dest="pr_url", help="pull request url")
    parser.add_argument("-p", type=str, dest="prid", help="pull request id")
    parser.add_argument("-o", type=str, dest="owner", help="gitee owner")
    parser.add_argument("-i", type=int, dest="trigger_build_id", help="trigger build id")

    return parser.parse_args()


if "__main__" == __name__:
    args = init_args()
    comment = CommentToDashboard()
    comment.get_all_result_to_kafka(args)
