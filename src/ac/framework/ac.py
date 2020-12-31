# -*- encoding=utf-8 -*-
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
# Create: 2020-09-23
# Description: access control list entrypoint
# **********************************************************************************

import os
import sys
import yaml
import logging.config
import logging
import json
import argparse
import importlib
import datetime

from yaml.error import YAMLError


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
        self.load_check_elements_from_conf(conf, community)

        logger.debug("check list: {}".format(self._ac_check_elements))

    def check_all(self, workspace, repo, dataset, **kwargs):
        """
        门禁检查
        :param workspace:
        :param repo:
        :return:
        """
        for element in self._ac_check_elements:
            check_element = self._ac_check_elements[element]
            logger.debug("check {}".format(element))

            # import module
            module_path = check_element.get("module", "{}.check_{}".format(element, element))   # eg: spec.check_spec
            try:
                module = importlib.import_module("." + module_path, self._acl_package)
                logger.debug("load module {} succeed".format(module_path))
            except ImportError as exc:
                logger.exception("import module {} exception, {}".format(module_path, exc))
                continue

            # import entry
            entry_name = check_element.get("entry", "Check{}".format(element.capitalize()))
            try:
                entry = getattr(module, entry_name)
                logger.debug("load entry \"{}\" succeed".format(entry_name))
            except AttributeError as exc:
                logger.warning("entry \"{}\" not exist in module {}, {}".format(entry_name, module_path, exc))
                continue

            # new a instance
            if isinstance(entry, type):  # class object
                try:
                    entry = entry(workspace, repo, check_element)       # new a instance
                except Exception as exc:
                    logger.exception("new a instance of class {} exception, {}".format(entry_name, exc))
                    continue

            if not callable(entry):      # check callable
                logger.warning("entry {} not callable".format(entry_name))
                continue

            # do ac check
            try:
                result = entry(**kwargs)
                logger.debug("check result {} {}".format(element, result))
            except Exception as exc:
                logger.exception("check exception, {} {}".format(element, exc))
                continue

            # show in gitee, must starts with "check_"
            hint = check_element.get("hint", "check_{}".format(element))
            if not hint.startswith("check_"):
                hint = "check_{}".format(hint)
            self._ac_check_result.append({"name": hint, "result": result.val})
            dataset.set_attr("access_control.build.acl.{}".format(element), result.hint)

        dataset.set_attr("access_control.build.content", self._ac_check_result)
        logger.debug("ac result: {}".format(self._ac_check_result))

    def load_check_elements_from_acl_directory(self, acl_dir):
        """
        加载当前目录下所有门禁项
        :return:
        """
        for filename in os.listdir(acl_dir):
            if os.path.isdir(os.path.join(acl_dir, filename)):
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
            logger.exception("ac conf file {} not exist".format(conf_file))
            return
        except YAMLError:
            logger.exception("illegal conf file format")
            return

        elements = content.get(community, {})
        logger.debug("community \"{}\" conf: {}".format(community, elements))
        for name in elements:
            if name in self._ac_check_elements:
                if elements[name].get("exclude"):
                    logger.debug("exclude: {}".format(name))
                    self._ac_check_elements.pop(name)
                else:
                    self._ac_check_elements[name] = elements[name]

    def save(self, ac_file):
        """
        save result
        :param ac_file:
        :return:
        """
        logger.debug("save ac result to file {}".format(ac_file))
        with open(ac_file, "w") as f:
            f.write("ACL={}".format(json.dumps(self._ac_check_result)))


def init_args():
    """
    init args
    :return:
    """
    args = argparse.ArgumentParser()
    args.add_argument("-c", type=str, dest="community", default="src-openeuler", help="src-openeuler or openeuler")
    args.add_argument("-w", type=str, dest="workspace", help="workspace where to find source")
    args.add_argument("-r", type=str, dest="repo", help="repo name")
    args.add_argument("-b", type=str, dest="tbranch", help="branch merge to")
    args.add_argument("-o", type=str, dest="output", help="output file to save result")
    args.add_argument("-p", type=str, dest="pr", help="pull request number")
    args.add_argument("-t", type=str, dest="token", help="gitee api token")
    args.add_argument("-a", type=str, dest="account", help="gitee account")
    
    # dataset
    args.add_argument("-m", type=str, dest="comment", help="trigger comment")
    args.add_argument("-i", type=str, dest="comment_id", help="trigger comment id")
    args.add_argument("-e", type=str, dest="committer", help="committer")
    args.add_argument("-x", type=str, dest="pr_ctime", help="pr create time")
    args.add_argument("-z", type=str, dest="trigger_time", help="job trigger time")
    args.add_argument("-l", type=str, dest="trigger_link", help="job trigger link")

    return args.parse_args()


if "__main__" == __name__:
    args = init_args()

    # init logging
    _ = not os.path.exists("log") and os.mkdir("log")
    logger_conf_path = os.path.realpath(os.path.join(os.path.dirname(os.path.realpath(__file__)), "../../conf/logger.conf"))
    logging.config.fileConfig(logger_conf_path)
    logger = logging.getLogger("ac")

    logger.info("------------------AC START--------------")

    # notify gitee
    from src.proxy.gitee_proxy import GiteeProxy
    from src.proxy.git_proxy import GitProxy
    from src.proxy.es_proxy import ESProxy
    from src.utils.dist_dataset import DistDataset

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

    ep = ESProxy(os.environ["ESUSERNAME"], os.environ["ESPASSWD"], os.environ["ESURL"], verify_certs=False)

    # download repo
    dd.set_attr_stime("access_control.scm.stime")
    gp = GitProxy.init_repository(args.repo, work_dir=args.workspace)
    repo_url = "https://{}@gitee.com/{}/{}.git".format(args.account, args.community, args.repo)
    if not gp.fetch_pull_request(repo_url, args.pr, depth=4):
        dd.set_attr("access_control.scm.result", "failed")
        dd.set_attr_etime("access_control.scm.etime")

        dd.set_attr_etime("access_control.job.etime")
        dd.set_attr("access_control.job.result", "successful")
        ep.insert(index="openeuler_statewall_ac", body=dd.to_dict())
        sys.exit(-1)
    else:
        gp.checkout_to_commit_force("pull/{}/MERGE".format(args.pr))
        dd.set_attr("access_control.scm.result", "successful")
        dd.set_attr_etime("access_control.scm.etime") 

    # build start
    dd.set_attr_stime("access_control.build.stime")

    # gitee pr tag
    gp = GiteeProxy(args.community, args.repo, args.token)
    gp.delete_tag_of_pr(args.pr, "ci_successful")
    gp.delete_tag_of_pr(args.pr, "ci_failed")
    gp.create_tags_of_pr(args.pr, "ci_processing")

    # build
    ac = AC(os.path.join(os.path.dirname(os.path.realpath(__file__)), "ac.yaml"), args.community)
    ac.check_all(workspace=args.workspace, repo=args.repo, dataset=dd, tbranch=args.tbranch)
    dd.set_attr_etime("access_control.build.etime")
    ac.save(args.output)

    dd.set_attr_etime("access_control.job.etime")
    dd.set_attr("access_control.job.result", "successful")
    ep.insert(index="openeuler_statewall_ac", body=dd.to_dict())
