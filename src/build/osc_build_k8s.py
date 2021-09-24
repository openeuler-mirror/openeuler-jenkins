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
# Description: build single package using obs
# **********************************************************************************

import os
import sys
import logging.config
import logging
import argparse
import warnings
from xml.etree import ElementTree


class SinglePackageBuild(object):
    """
    build single package using obs
    """

    GITEE_BRANCH_PROJECT_MAPPING = {
        "master": ["bringInRely", "openEuler:Extras", "openEuler:Factory", "openEuler:Mainline", "openEuler:Epol"],
        "openEuler-20.03-LTS": ["openEuler:20.03:LTS"],
        "openEuler-20.03-LTS-Next": ["openEuler:20.03:LTS:Next", "openEuler:20.03:LTS:Next:Epol"],
        "openEuler-EPOL-LTS": ["bringInRely"],
        "openEuler-20.09": ["openEuler:20.09", "openEuler:20.09:Epol", "openEuler:20.09:Extras"],
        "mkopeneuler-20.03": ["openEuler:Extras"],
        "openEuler-20.03-LTS-SP1": ["openEuler:20.03:LTS:SP1", "openEuler:20.03:LTS:SP1:Epol", 
            "openEuler:20.03:LTS:SP1:Extras"],
        "openEuler-20.03-LTS-SP2": ["openEuler:20.03:LTS:SP2", "openEuler:20.03:LTS:SP2:Epol", 
            "openEuler:20.03:LTS:SP2:Extras"],
        "openEuler-21.03": ["openEuler:21.03", "openEuler:21.03:Epol", "openEuler:21.03:Extras"],
        "openEuler-21.09": ["openEuler:21.09", "openEuler:21.09:Epol", "openEuler:21.09:Extras"],
        "oepkg_openstack-common_oe-20.03-LTS-SP2": ["openEuler:20.03:LTS:SP2:oepkg:openstack:common"],
        "oepkg_openstack-queens_oe-20.03-LTS-SP2": ["openEuler:20.03:LTS:SP2:oepkg:openstack:queens"],
        "oepkg_openstack-rocky_oe-20.03-LTS-SP2": ["openEuler:20.03:LTS:SP2:oepkg:openstack:rocky"],
        "oepkg_openstack-common_oe-20.03-LTS-Next": ["openEuler:20.03:LTS:Next:oepkg:openstack:common"],
        "oepkg_openstack-queens_oe-20.03-LTS-Next": ["openEuler:20.03:LTS:Next:oepkg:openstack:queens"],
        "oepkg_openstack-rocky_oe-20.03-LTS-Next": ["openEuler:20.03:LTS:Next:oepkg:openstack:rocky"]
    }

    BUILD_IGNORED_GITEE_BRANCH = ["riscv"]

    def __init__(self, package, arch, target_branch):
        """
        
        :param package: package name
        :param arch: x86_64 or aarch64
        :param target_branch: branch pull request apply
        """
        self._package = package
        self._arch = arch
        self._branch = target_branch

    def get_need_build_obs_repos(self, project):
        """
        需要构建obs repo列表
        :return: list<dict>
        """
        return OBSProxy.list_repos_of_arch(project, self._package, self._arch, show_exclude=True)

    def build_obs_repos(self, project, repos, work_dir, code_dir):
        """
        build
        :param project: 项目名
        :param repos: obs repo
        :param code_dir: 码云代码在本地路径
        :param work_dir:
        :return:
        """
        # osc co
        if not OBSProxy.checkout_package(project, self._package):
            logger.error("checkout ... failed")
            return 1

        logger.info("checkout ... ok")

        # update package meta file "_service"
        self._handle_package_meta(project, work_dir, code_dir)
        logger.debug("prepare \"_service\" ... ok")

        # process_service.pl
        if not self._prepare_build_environ(project, work_dir):
            logger.error("prepare environ ... failed")
            return 2

        logger.info("prepare environ ... ok")

        # osc build
        for repo in repos:
            if repo["state"] == "excluded" and repo["mpac"] == "raspberrypi-kernel":
                logger.info("repo {}:{} excluded".format(repo["repo"], repo["mpac"]))
                continue
            root_build = repo["mpac"] == "iproute"
            if not OBSProxy.build_package(
                    project, self._package, repo["repo"], self._arch, repo["mpac"], root_build=root_build):
                logger.error("build {} ... failed".format(repo["repo"]))
                return 3

            logger.info("build {} ... ok".format(repo["repo"]))

        logger.debug("build all repos ... finished")

        return 0

    def _handle_package_meta(self, project, obs_work_dir, code_path):
        """
        _service文件重组

        <services>
            <service name="tar_scm_kernel_repo">
                <param name="scm">repo</param>
                <param name="url">next/openEuler/perl-Archive-Zip</param>
            </service>
        </services>

        :param project: obs项目
        :param obs_work_dir: obs工作目录
        :param code_path: 代码目录
        :return:
        """
        _service_file_path = os.path.join(obs_work_dir, project, self._package, "_service")
        tree = ElementTree.parse(_service_file_path)

        logger.info("before update meta------")
        ElementTree.dump(tree)
        sys.stdout.flush()

        services = tree.findall("service")

        for service in services:
            if service.get("name") == "tar_scm_repo_docker":
                service.set("name", "tar_local")
            elif service.get("name") == "tar_scm_repo":
                service.set("name", "tar_local")
            elif service.get("name") == "tar_scm_kernel_repo":
                service.set("name", "tar_local_kernel")
            elif service.get("name") == "tar_scm_kernels_repo":
                service.set("name", "tar_local_kernels")

            for param in service.findall("param"):
                if param.get("name") == "scm":
                    param.text = "local"
                elif param.get("name") == "tar_scm":
                    param.text = "tar_local"
                elif param.get("name") == "url":
                    if "openEuler_kernel" in param.text or "LTS_kernel" in param.text \
                            or "openEuler-kernel" in param.text \
                            or "openEuler-20.09_kernel" in param.text:
                        param.text = "{}/{}".format(code_path, "code")  # kernel special logical
                    else:
                        gitee_repo = param.text.split("/")[-1]
                        param.text = "{}/{}".format(code_path, gitee_repo)

        logger.info("after update meta------")

        ElementTree.dump(tree)
        sys.stdout.flush()
        tree.write(_service_file_path)

    def _prepare_build_environ(self, project, obs_work_dir):
        """
        准备obs build环境
        :param project: obs项目
        :param obs_work_dir: obs工作目录
        :return:
        """
        _process_perl_path = os.path.realpath(os.path.join(os.path.realpath(__file__), "../process_service.pl"))
        _service_file_path = os.path.join(obs_work_dir, project, self._package, "_service")
        _obs_package_path = os.path.join(obs_work_dir, project, self._package)

        cmd = "perl {} -f {} -p {} -m {} -w {}".format(
            _process_perl_path, _service_file_path, project, self._package, _obs_package_path)

        ret, _, _ = shell_cmd_live(cmd, verbose=True)

        if ret:
            logger.error("prepare build environ error, {}".format(ret))
            return False

        return True

    def build(self, work_dir, code_dir):
        """
        入口
        :param work_dir: obs工作目录
        :param code_dir: 代码目录
        :return:
        """
        if self._branch in self.BUILD_IGNORED_GITEE_BRANCH:
            logger.error("branch \"{}\" ignored".format(self._branch))
            return 0

        if self._branch not in self.GITEE_BRANCH_PROJECT_MAPPING:
            logger.error("branch \"{}\" not support yet".format(self._branch))
            return 1

        has_any_repo_build = False
        for project in self.GITEE_BRANCH_PROJECT_MAPPING.get(self._branch):
            logger.debug("start build project {}".format(project))

            obs_repos = self.get_need_build_obs_repos(project)
            if not obs_repos:
                logger.info("all repos ignored of project {}".format(project))
                continue

            logger.debug("build obs repos: {}".format(obs_repos))
            has_any_repo_build = True
            ret = self.build_obs_repos(project, obs_repos, work_dir, code_dir)
            if ret > 0:
                logger.debug("build run return {}".format(ret))
                logger.error("build {} {} {} ... {}".format(project, self._package, self._arch, "failed"))
                return 1     # finish if any error
            else:
                logger.info("build {} {} {} ... {}".format(project, self._package, self._arch, "ok"))

        # if no repo build, regard as fail
        if not has_any_repo_build:
            logger.error("package not in any obs projects, please add package into obs")
            return 1

        return 0


def init_args():
    """
    init args
    :return: 
    """
    parser = argparse.ArgumentParser()

    parser.add_argument("-p", type=str, dest="package", help="obs package")
    parser.add_argument("-a", type=str, dest="arch", help="build arch")
    parser.add_argument("-b", type=str, dest="branch", help="target branch that merged to ")
    parser.add_argument("-c", type=str, dest="code", help="code dir path")
    parser.add_argument("-w", type=str, dest="workspace", default=os.getcwd(), help="obs workspace dir path")

    parser.add_argument("-m", type=str, dest="comment_id", help="uniq comment id")
    parser.add_argument("-r", type=str, dest="repo", help="repo")
    parser.add_argument("--pr", type=str, dest="pr", help="pull request")
    parser.add_argument("-t", type=str, dest="account", help="gitee account")

    parser.add_argument("-o", type=str, dest="owner", default="src-openeuler", help="gitee owner")

    return parser.parse_args()


if "__main__" == __name__:
    args = init_args()

    _ = not os.path.exists("log") and os.mkdir("log")
    logger_conf_path = os.path.realpath(os.path.join(os.path.realpath(__file__), "../../conf/logger.conf"))
    logging.config.fileConfig(logger_conf_path)
    logger = logging.getLogger("build")

    logger.info("using credential {}".format(args.account.split(":")[0]))
    logger.info("cloning repository https://gitee.com/{}/{}.git ".format(args.owner, args.repo))
    logger.info("clone depth 1")
    logger.info("checking out pull request {}".format(args.pr))

    from src.utils.dist_dataset import DistDataset
    from src.proxy.git_proxy import GitProxy
    from src.proxy.obs_proxy import OBSProxy
    from src.proxy.es_proxy import ESProxy
    from src.proxy.kafka_proxy import KafkaProducerProxy
    from src.utils.shell_cmd import shell_cmd_live

    dd = DistDataset()
    dd.set_attr_stime("spb.job.stime")
    dd.set_attr("spb.job.link", os.environ["BUILD_URL"])
    dd.set_attr("spb.trigger.reason", os.environ["BUILD_CAUSE"])

    # suppress python warning
    warnings.filterwarnings("ignore")
    logging.getLogger("elasticsearch").setLevel(logging.WARNING)
    logging.getLogger("kafka").setLevel(logging.WARNING)

    kp = KafkaProducerProxy(brokers=os.environ["KAFKAURL"].split(","))

    # download repo
    dd.set_attr_stime("spb.scm.stime")
    gp = GitProxy.init_repository(args.repo, work_dir=args.workspace)
    repo_url = "https://{}@gitee.com/{}/{}.git".format(args.account, args.owner, args.repo)
    if not gp.fetch_pull_request(repo_url, args.pr, depth=1):
        logger.info("fetch finished -")

        dd.set_attr("spb.scm.result", "failed")
        dd.set_attr_etime("spb.scm.etime")
        dd.set_attr_etime("spb.job.etime")
        #dd.set_attr("spb.job.result", "failed")

        # upload to es
        query = {"term": {"id": args.comment_id}}
        script = {"lang": "painless", "source": "ctx._source.spb_{}=params.spb".format(args.arch),
                "params": dd.to_dict()}
        kp.send("openeuler_statewall_ci_ac", key=args.comment_id, value=dd.to_dict())
        sys.exit(-1)
    else:
        gp.checkout_to_commit_force("pull/{}/MERGE".format(args.pr))
        logger.info("fetch finished +")
        dd.set_attr("spb.scm.result", "successful")
        dd.set_attr_etime("spb.scm.etime")

    dd.set_attr_stime("spb.build.stime")
    spb = SinglePackageBuild(args.package, args.arch, args.branch)
    rs = spb.build(args.workspace, args.code)
    dd.set_attr("spb.build.result", "failed" if rs else "successful")
    dd.set_attr_etime("spb.build.etime")

    dd.set_attr_etime("spb.job.etime")

    # upload to es
    query = {"term": {"id": args.comment_id}}
    script = {"lang": "painless", "source": "ctx._source.spb_{}=params.spb".format(args.arch), "params": dd.to_dict()}
    kp.send("openeuler_statewall_ci_ac", key=args.comment_id, value=dd.to_dict())
    sys.exit(rs)
