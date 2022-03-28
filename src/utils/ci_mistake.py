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
# Create: 2021-3-21
# Description: ci mistake report to database by kafka
# **********************************************************************************
"""
import os
import re
import datetime
import argparse
import time
import yaml

from src.proxy.gitee_proxy import GiteeProxy
from src.proxy.kafka_proxy import KafkaProducerProxy
from src.logger import logger


class CiMistake(object):
    """ci mistake functions"""

    support_check_stage = ["check_binary_file", "check_package_license", "check_package_yaml_file",
                           "check_spec_file", "check_build", "check_install", "compare_package",
                           "build_exception"]

    support_mistake_type = ["ci", "obs", "infra"]

    def __init__(self, pr_url, gitee_token, committer, commit_at, comment_id):
        """
        initial
        :param pr_url: pr link
        :param gitee_token: gitee comment token
        :param committer: ci mistake comment committer
        :param commit_at: ci mistake comment date
        :param comment_id: gitee comment id
        :return:
        """
        self.pr_url = pr_url
        self.gitee_token = gitee_token
        self.committer = committer
        self.comment_id = comment_id
        self.commit_at = round(datetime.datetime.strptime(commit_at, "%Y-%m-%dT%H:%M:%S%z").timestamp(), 1)
        self.owner, self.repo, self.pr_id = CiMistake.get_owner_repo_id(pr_url)

    @staticmethod
    def load_build_no_list(filepath):
        """
        load build number list
        :param filepath:
        :return: a number list
        """
        if not os.path.exists(filepath):
            logger.error("%s not exists", os.path.basename(filepath))
            return []

        with open(filepath, "r") as data:
            try:
                all_data = yaml.safe_load(data)
            except yaml.MarkedYAMLError:
                logger.error("%s is not an illegal yaml file", os.path.basename(filepath))
                return []

        if isinstance(all_data, list):
            build_no_list = []
            for value in all_data:
                try:
                    build_no_list.append(int(value))
                except ValueError as e:
                    return []
            return build_no_list
        else:
            logger.error("%s content is not a list", os.path.basename(filepath))
            return []

    @staticmethod
    def get_owner_repo_id(pr_url):
        """
        get owner, repo and pr id from pull request link
        :param pr_url:
        :return:
        """
        res = re.search(r"https://gitee.com/.*/.*/.*/.*", pr_url)
        if not res:
            raise ValueError("{} format error".format(pr_url))
        sp = re.sub("https://gitee.com/", "", pr_url).split("/")
        owner_index = 0
        repo_index = 1
        pr_id_index = 3
        return sp[owner_index], sp[repo_index], sp[pr_id_index]

    @staticmethod
    def check_command_format(mistake_comment):
        """
        analyse ci mistake comment format
        :param mistake_comment:
        :return:
        """
        sp = re.split(r"\s+", mistake_comment.strip())
        command_index = 0
        build_no_index = 1
        ci_type_stage_index = 2

        command = sp[command_index]
        if any([all([command != "/ci_unmistake", command != "/ci_mistake"]),
                all([command == "/ci_unmistake", len(sp) != build_no_index + 1]),
                all([command == "/ci_mistake", len(sp) < build_no_index + 1])]):
            raise ValueError("command type or numbers of parameter error")

        try:
            build_no = int(sp[build_no_index])
        except ValueError:
            raise ValueError("build_no is not a number")

        ci_mistake_type_stage = sp[ci_type_stage_index:]

        return command, build_no, ci_mistake_type_stage

    def comment_to_pr(self, comment_content):
        """
        comment message to pull request
        :param comment_content: comment content
        :return:
        """
        gp = GiteeProxy(self.owner, self.repo, self.gitee_token)
        gp.comment_pr(self.pr_id, comment_content)

    def send_ci_mistake_data(self, command, build_no, ci_mistake_type, ci_mistake_stage):
        """
        send message to datebase by kafka
        :param command:
        :param build_no:
        :param ci_mistake_type:
        :param ci_mistake_stage:
        :return:
        """
        message = {
            "pr_url": self.pr_url,
            "build_no": build_no,
            "committer": self.committer,
            "commit_at": self.commit_at,
            "update_at": round(time.time(), 1)
        }
        if ci_mistake_type:
            message["ci_mistake_type"] = ci_mistake_type
        if ci_mistake_stage:
            message["ci_mistake_stage"] = ci_mistake_stage

        if command == "/ci_unmistake":
            message["ci_mistake_status"] = False
        else:
            message["ci_mistake_status"] = True
        kp = KafkaProducerProxy(brokers=os.environ["KAFKAURL"].split(","))
        kp.send("openeuler_statewall_ci_mistake", key=self.comment_id, value=message)
        self.comment_to_pr("Thanks for your commit.")
        logger.info("ci mistake finished. kafka message: %s.", message)

    def process(self, mistake_comment, build_no_filepath):
        """
        process to analyse ci mistake content and save to datebase
        :param mistake_comment: ci mistake comment
        mistake_comment format: /ci_unmistake build_no, /ci_mistake build_no <mistake_type> <ci_mistake_stage>
        1. build_no must be set, and in history trigger build number of same pr
        2. You can set zero or one <mistake_type> parameter, but all of them should be in support_mistake_type
        3. You can set any number of <mistake_stage> parameters, but all of them should be in support_mistake_stage
        4. <mistake_type> and <mistake_stage> can be out of order
        :param build_no_filepath: build number filepath
        :return:
        """
        build_no_list = CiMistake.load_build_no_list(build_no_filepath)

        try:
            command, build_no, ci_mistake_type_stage = CiMistake.check_command_format(mistake_comment)
        except ValueError:
            command_error_tips = "comment format error."
            logger.error(command_error_tips)
            self.comment_to_pr(command_error_tips)
            return

        if build_no not in build_no_list:
            build_no_error_tips = "***{}*** is not an illegal build number. You should select one from " \
                                  "***{}***.".format(build_no, ", ".join([str(item) for item in build_no_list]))
            logger.error(build_no_error_tips)
            self.comment_to_pr(build_no_error_tips)
            return

        ci_mistake_type_list = list(set(ci_mistake_type_stage).intersection(set(self.support_mistake_type)))
        ci_mistake_stage = list(set(ci_mistake_type_stage).intersection(set(self.support_check_stage)))
        ci_mistake_others = list(set(ci_mistake_type_stage).difference(
            set(self.support_mistake_type)).difference(set(self.support_check_stage)))
        if ci_mistake_others:
            mistake_type_stage_error_tips = "***{}*** is not an illegal mistake type or check item. " \
                                            "If you want to express mistake type, you can select one from ***{}***. " \
                                            "If you want to express check item, you can select one or more from " \
                                            "***{}***.".format(", ".join(ci_mistake_others),
                                                               ", ".join(self.support_mistake_type),
                                                               ", ".join(self.support_check_stage))
            logger.error(mistake_type_stage_error_tips)
            self.comment_to_pr(mistake_type_stage_error_tips)
            return

        if len(ci_mistake_type_list) > 1:
            ci_mistake_type_tips = "You should only select one mistake type, now are ***{}***. ".format(
                ", ".join(ci_mistake_type_list))
            logger.error(ci_mistake_type_tips)
            self.comment_to_pr(ci_mistake_type_tips)
            return
        ci_mistake_type = ci_mistake_type_list[0] if ci_mistake_type_list else ""

        self.send_ci_mistake_data(command, build_no, ci_mistake_type, ci_mistake_stage)


def init_args():
    """
    init args
    :return:
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--pr_url", type=str, dest="pr_url", help="pull request")
    parser.add_argument("--mistake_comment", type=str, dest="mistake_comment",
                        help="gitee comment for mask ci mistake")
    parser.add_argument("--committer", type=str, dest="committer", help="committer")
    parser.add_argument("--commit_at", type=str, dest="commit_at", help="commit time")
    parser.add_argument("--comment_id", type=str, dest="comment_id", help="comment id")
    parser.add_argument("--build_no_filepath", type=str, dest="build_no_filepath",
                        help="path of a file which record history build numbers")
    parser.add_argument("--gitee_token", type=str, dest="gitee_token", help="gitee api token")

    return parser.parse_args()


if "__main__" == __name__:
    args = init_args()

    ci_mistake = CiMistake(args.pr_url, args.gitee_token, args.committer, args.commit_at, args.comment_id)
    ci_mistake.process(args.mistake_comment, args.build_no_filepath)

