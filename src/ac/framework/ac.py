# -*- encoding=utf-8 -*-
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
# Description: access control list entrypoint
# **********************************************************************************

import argparse
import datetime
import importlib
import json
import logging.config
import os
import sys
import warnings

import yaml
from yaml.error import YAMLError

from src.proxy.git_proxy import GitProxy
from src.proxy.gitee_proxy import GiteeProxy
from src.proxy.jenkins_proxy import JenkinsProxy
from src.proxy.kafka_proxy import KafkaProducerProxy
from src.utils.dist_dataset import DistDataset


class AC(object):
    """
    ac entrypoint
    """
    def __init__(self, conf, community="src-openeuler"):
        """

        :param conf: 配置文件路径
        :param community: src-openeuler or openeuler
        :return:
        """
        self._ac_check_elements = {}       # 门禁项
        self._ac_check_result = []         # 门禁结果结果

        acl_path = os.path.realpath(os.path.join(os.path.dirname(__file__), "../acl"))
        self._acl_package = "src.ac.acl"  # take attention about import module
        self.load_check_elements_from_acl_directory(acl_path)
        if community != "src-openeuler" and community != "openeuler":
            self.load_check_elements_from_conf(conf, "src-openeuler")
        else:
            self.load_check_elements_from_conf(conf, community)

        logger.debug("check list: %s", self._ac_check_elements)

    @staticmethod
    def comment_jenkins_url(gp, jp, pr):
        """
        在pr评论中显示构建任务链接
        :param gp: gitee接口
        :param jp: jenkins接口
        :param pr: pr编号
        :return:
        """
        comments = ["门禁正在运行， 您可以通过以下链接查看实时门禁检查结果."]

        trigger_job_name = os.environ.get("JOB_NAME")
        trigger_build_id = os.environ.get("BUILD_ID")
        trigger_job_info = jp.get_job_info(trigger_job_name)
        trigger_job_url = trigger_job_info.get("url")
        comments.append("门禁入口及编码规范检查: <a href={}>{}</a>, 当前构建号为 {}".format(
            trigger_job_url, jp.get_job_path_from_job_url(trigger_job_url), trigger_build_id))

        down_projects = trigger_job_info.get("downstreamProjects", [])
        build_job_name_list = []
        build_job_link_list = []
        for project in down_projects:
            build_job_url = project.get("url", "")
            if build_job_url:
                build_job_name = jp.get_job_path_from_job_url(build_job_url)
                build_job_name_list.append(build_job_name)
                build_job_link_list.append("<a href={}>{}</a>".format(build_job_url, build_job_name))
        comments.append("构建及构建后检查: {}".format(", ".join(build_job_link_list)))

        if build_job_name_list:
            build_job_info = jp.get_job_info(build_job_name_list[0])
            down_down_projects = build_job_info.get("downstreamProjects", [])
            for project in down_down_projects:
                comment_job_url = project.get("url")
                comments.append("门禁结果回显: <a href={}>{}</a>".format(
                    comment_job_url, jp.get_job_path_from_job_url(comment_job_url)))
        comments.append("")
        comments.append("若您对门禁流程或功能不了解，对门禁结果存在疑问，遇到门禁问题难以解决，亦或是认为门禁误报希望反馈，"
                        "可参考<a href={门禁指导手册}>"
                        "{https://www.openeuler.org/zh/blog/zhengyaohui/2022-03-21-ci_guild.html}</a>。")
        gp.comment_pr(pr, "\n".join(comments))

    @staticmethod
    def is_repo_support_check(repo, check_element):
        """
        仓库是否支持检查
        不在allow_list或者在deny_list，则不支持检查
        :param repo:
        :param check_element:
        :return: 允许/True，否则False
        """
        allow_list = check_element.get("allow_list") or []
        deny_list = check_element.get("deny_list") or []

        return False if (allow_list and repo not in allow_list) or repo in deny_list else True

    def check_all(self, workspace, repo, dataset, **kwargs):
        """
        门禁检查
        :param workspace:
        :param repo:
        :return:
        """
        for element in self._ac_check_elements:
            check_element = self._ac_check_elements.get(element)
            logger.debug("check %s", element)

            # show in gitee, must starts with "check_"
            hint = check_element.get("hint", "check_{}".format(element))
            if not hint.startswith("check_"):
                hint = "check_{}".format(hint)

            if not self.__class__.is_repo_support_check(repo, check_element):
                logger.debug("%s not support check", repo)
                continue

            # import module
            module_path = check_element.get("module", "{}.check_{}".format(element, element))   # eg: spec.check_spec
            try:
                module = importlib.import_module("." + module_path, self._acl_package)
                logger.debug("load module %s succeed", module_path)
            except ImportError as exc:
                logger.exception("import module %s exception, %s", module_path, exc)
                continue

            # import entry
            entry_name = check_element.get("entry", "Check{}".format(element.capitalize()))
            try:
                entry = getattr(module, entry_name)
                logger.debug("load entry \"%s\" succeed", entry_name)
            except AttributeError as exc:
                logger.warning("entry \"%s\" not exist in module %s, %s", entry_name, module_path, exc)
                continue

            # new a instance
            if isinstance(entry, type):  # class object
                entry = entry(workspace, repo, check_element)       # new a instance

            if not callable(entry):      # check callable
                logger.warning("entry %s not callable", entry_name)
                continue

            # do ac check
            result = entry(**kwargs)
            logger.debug("check result %s %s", element, result)

            self._ac_check_result.append({"name": hint, "result": result.val})
            dataset.set_attr("access_control.build.acl.{}".format(element), result.hint)

        dataset.set_attr("access_control.build.content", self._ac_check_result)
        logger.debug("ac result: %s", self._ac_check_result)

    def load_check_elements_from_acl_directory(self, acl_dir):
        """
        加载当前目录下所有门禁项
        :return:
        """
        for filename in os.listdir(acl_dir):
            if filename != "__pycache__" and os.path.isdir(os.path.join(acl_dir, filename)):
                self._ac_check_elements[filename] = {}     # don't worry, using default when checking

    def load_check_elements_from_conf(self, conf_file, community):
        """
        加载门禁项目，只支持yaml格式
        :param conf_file: 配置文件路径
        :param community: src-openeuler or openeuler
        :return:
        """
        try:
            with open(conf_file, "r") as f:
                content = yaml.safe_load(f)
        except IOError:
            logger.exception("ac conf file %s not exist", conf_file)
            return
        except YAMLError:
            logger.exception("illegal conf file format")
            return

        elements = content.get(community, {})
        logger.debug("community \"%s\" conf: %s", community, elements)
        for name in elements:
            if name in self._ac_check_elements:
                if elements[name].get("exclude"):
                    logger.debug("exclude: %s", name)
                    self._ac_check_elements.pop(name)
                else:
                    self._ac_check_elements[name] = elements[name]

    def save(self, ac_file):
        """
        save result
        :param ac_file:
        :return:
        """
        logger.debug("save ac result to file %s", ac_file)
        with open(ac_file, "w") as f:
            f.write("ACL={}".format(json.dumps(self._ac_check_result)))


def init_args():
    """
    init args
    :return:
    """
    parser = argparse.ArgumentParser()

    parser.add_argument("-c", type=str, dest="community", default="src-openeuler", help="src-openeuler or openeuler")
    parser.add_argument("-w", type=str, dest="workspace", help="workspace where to find source")
    parser.add_argument("-r", type=str, dest="repo", help="repo name")
    parser.add_argument("-b", type=str, dest="tbranch", help="branch merge to")
    parser.add_argument("-o", type=str, dest="output", help="output file to save result")
    parser.add_argument("-p", type=str, dest="pr", help="pull request number")
    parser.add_argument("-t", type=str, dest="token", help="gitee api token")
    parser.add_argument("-a", type=str, dest="account", help="gitee account")
    
    # dataset
    parser.add_argument("-m", type=str, dest="comment", help="trigger comment")
    parser.add_argument("-i", type=str, dest="comment_id", help="trigger comment id")
    parser.add_argument("-e", type=str, dest="committer", help="committer")
    parser.add_argument("-x", type=str, dest="pr_ctime", help="pr create time")
    parser.add_argument("-z", type=str, dest="trigger_time", help="job trigger time")
    parser.add_argument("-l", type=str, dest="trigger_link", help="job trigger link")

    # scanoss
    parser.add_argument("--scanoss-output", type=str, dest="scanoss_output", 
            default="scanoss_result", help="scanoss result output")

    parser.add_argument("--codecheck-api-key", type=str, dest="codecheck_api_key", help="codecheck api key")
    parser.add_argument("--codecheck-api-url", type=str, dest="codecheck_api_url",
                        default="https://majun.osinfra.cn:8384/api/openlibing/codecheck", help="codecheck api url")

    parser.add_argument("--jenkins-base-url", type=str, dest="jenkins_base_url",
                        default="https://openeulerjenkins.osinfra.cn/", help="jenkins base url")
    parser.add_argument("--jenkins-user", type=str, dest="jenkins_user", help="repo name")
    parser.add_argument("--jenkins-api-token", type=str, dest="jenkins_api_token", help="jenkins api token")

    return parser.parse_args()


if "__main__" == __name__:
    args = init_args()

    # init logging
    _ = not os.path.exists("log") and os.mkdir("log")
    logger_conf_path = os.path.realpath(os.path.join(
        os.path.dirname(os.path.realpath(__file__)), "../../conf/logger.conf"))
    logging.config.fileConfig(logger_conf_path)
    logger = logging.getLogger("ac")

    logger.info("using credential %s", args.account.split(":")[0])
    logger.info("cloning repository https://gitee.com/%s/%s.git ", args.community, args.repo)
    logger.info("clone depth 4")
    logger.info("checking out pull request %s", args.pr)

    dd = DistDataset()
    dd.set_attr_stime("access_control.job.stime")

    # info from args
    dd.set_attr("id", args.comment_id)
    dd.set_attr("pull_request.package", args.repo)
    dd.set_attr("pull_request.number", args.pr)
    dd.set_attr("pull_request.author", args.committer)
    dd.set_attr("pull_request.target_branch", args.tbranch)
    dd.set_attr("pull_request.ctime", args.pr_ctime)
    dd.set_attr("access_control.trigger.link", args.trigger_link)
    dd.set_attr("access_control.trigger.reason", args.comment)
    ctime = datetime.datetime.strptime(args.trigger_time.split("+")[0], "%Y-%m-%dT%H:%M:%S")
    dd.set_attr_ctime("access_control.job.ctime", ctime)

    # suppress python warning
    warnings.filterwarnings("ignore")
    logging.getLogger("elasticsearch").setLevel(logging.WARNING)
    logging.getLogger("kafka").setLevel(logging.WARNING)

    kp = KafkaProducerProxy(brokers=os.environ["KAFKAURL"].split(","))

    # download repo
    dd.set_attr_stime("access_control.scm.stime")
    git_proxy = GitProxy.init_repository(args.repo, work_dir=args.workspace)
    repo_url = "https://{}@gitee.com/{}/{}.git".format(args.account, args.community, args.repo)
    if not git_proxy.fetch_pull_request(repo_url, args.pr, depth=4):
        dd.set_attr("access_control.scm.result", "failed")
        dd.set_attr_etime("access_control.scm.etime")

        dd.set_attr_etime("access_control.job.etime")
        kp.send("openeuler_statewall_ci_ac", key=args.comment_id, value=dd.to_dict())
        logger.info("fetch finished -")
        sys.exit(-1)
    else:
        git_proxy.checkout_to_commit_force("pull/{}/MERGE".format(args.pr))
        logger.info("fetch finished +")
        dd.set_attr("access_control.scm.result", "successful")
        dd.set_attr_etime("access_control.scm.etime") 

    logger.info("--------------------AC START---------------------")

    # build start
    dd.set_attr_stime("access_control.build.stime")

    # gitee comment jenkins url
    gitee_proxy_inst = GiteeProxy(args.community, args.repo, args.token)
    if all([args.jenkins_base_url, args.jenkins_user, args.jenkins_api_token]):
        jenkins_proxy_inst = JenkinsProxy(args.jenkins_base_url, args.jenkins_user, args.jenkins_api_token)
        AC.comment_jenkins_url(gitee_proxy_inst, jenkins_proxy_inst, args.pr)

    # gitee pr tag
    gitee_proxy_inst.delete_tag_of_pr(args.pr, "ci_successful")
    gitee_proxy_inst.delete_tag_of_pr(args.pr, "ci_failed")
    gitee_proxy_inst.create_tags_of_pr(args.pr, "ci_processing")

    # scanoss conf
    scanoss = {"output": args.scanoss_output}

    codecheck = {"pr_url": "https://gitee.com/{}/{}/pulls/{}".format(args.community, args.repo, args.pr),
        "pr_number": args.pr, "codecheck_api_url": args.codecheck_api_url, "codecheck_api_key": args.codecheck_api_key
    }

    # build
    ac = AC(os.path.join(os.path.dirname(os.path.realpath(__file__)), "ac.yaml"), args.community)
    ac.check_all(workspace=args.workspace, repo=args.repo, dataset=dd, tbranch=args.tbranch, scanoss=scanoss,
                 codecheck=codecheck)
    dd.set_attr_etime("access_control.build.etime")
    ac.save(args.output)

    dd.set_attr_etime("access_control.job.etime")
    kp.send("openeuler_statewall_ci_ac", key=args.comment_id, value=dd.to_dict())
