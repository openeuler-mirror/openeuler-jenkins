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
# Create: 2020-09-23
# Description: pkgship and check_abi
# **********************************************************************************
"""

import os
import argparse
import logging.config
import logging
import yaml

from src.proxy.obs_proxy import OBSProxy
from src.proxy.requests_proxy import do_requests
from src.constant import Constant
from src.build.obs_repo_source import OBSRepoSource
from src.build.build_rpm_package import BuildRPMPackage
from src.build.related_rpm_package import RelatedRpms
from src.utils.shell_cmd import shell_cmd_live
from src.utils.check_abi import CheckAbi
from src.utils.compare_package import ComparePackage
from src.utils.check_conf import CheckConfig


class ExtraWork(object):
    """
    pkgship
    check_abi
    """
    def __init__(self, package, rpmbuild_dir="/home/jenkins/agent/buildroot/home/abuild/rpmbuild"):
        """

        :param package: obs package
        :param rpmbuild_dir: rpmbuild 路径
        """
        self._repo = package
        self._rpm_package = BuildRPMPackage(package, rpmbuild_dir)

    def is_pkgship_need_notify(self, pkgship_meta_path):
        """
        是否需要发起notify
        :param pkgship_meta_path: 保存门禁中解析的pkgship spec版本元信息文件路径
        :return:
        """
        if self._repo == "pkgship":     # 只有pkgship包需要通知
            try:
                with open(pkgship_meta_path, "r") as f:
                    pkgship_meta = yaml.safe_load(f)
                    logger.debug("pkgship meta: %s", pkgship_meta)
                    if pkgship_meta.get("compare_version") == 1:     # version upgrade
                        logger.debug("pkgship: notify")
                        return True
            except IOError:
                # file not exist, bug
                logger.warning("pkgship meta file not exist!")
                return True

        return False

    def pkgship_notify(
            self, notify_url, notify_token, package_url, package_arch, notify_jenkins_user, notify_jenkins_password):
        """
        notify
        :param notify_url: notify url
        :param notify_token: notify token
        :param package_url: package addr
        :param package_arch: cpu arch
        :param notify_jenkins_user: 
        :param notify_jenkins_password: 
        :return:
        """
        package = self._rpm_package.last_main_package(package_arch, package_url)
        querystring = {"token": notify_token, "PACKAGE_URL": package, "arch": package_arch}
        ret = do_requests("get", notify_url, querystring=querystring,
                          auth={"user": notify_jenkins_user, "password": notify_jenkins_password}, timeout=1)
        if ret in [0, 2]:
            # send async, don't care about response, timeout will be ok
            logger.info("notify ...ok")
        else:
            logger.error("notify ...fail")

    def check_rpm_abi(self, package_url, package_arch, output, committer, comment_file, obs_addr,
                        branch_name="master", obs_repo_url=None):
        """
        对比两个版本rpm包之间的接口差异，根据差异找到受影响的rpm包
        :param package_arch:
        :param obs_repo_url:
        :return:
        """
        #get rpms
        curr_rpm = self._rpm_package.main_package_local()
        last_rpm = self._rpm_package.last_main_package(package_arch, package_url)
        logger.debug("curr_rpm: %s", curr_rpm)
        logger.debug("last_rpm: %s", last_rpm)
        if not curr_rpm or not last_rpm:
            logger.info("no rpms")
            return

        #check configs
        check_conf = CheckConfig(last_rpm, curr_rpm, output_file=output)
        check_conf.conf_check()
        rpms = [last_rpm, curr_rpm]

        #get debuginfos
        debuginfos = None
        curr_rpm_debug = self._rpm_package.debuginfo_package_local()
        last_rpm_debug = self._rpm_package.last_debuginfo_package(package_arch, package_url)
        logger.debug("curr_rpm_debug: %s", curr_rpm_debug)
        logger.debug("last_rpm_debug: %s", last_rpm_debug)
        if curr_rpm_debug and last_rpm_debug:
            debuginfos = [last_rpm_debug, curr_rpm_debug]

        #get related rpms url
        related_rpms_url = None
        if obs_repo_url:
            rp = RelatedRpms(obs_addr, obs_repo_url, branch_name, package_arch)
            related_rpms_url = rp.get_related_rpms_url(curr_rpm)

        #check abi
        check_abi = CheckAbi(result_output_file=output, input_rpms_path=related_rpms_url)
        ret = check_abi.process_with_rpm(rpms, debuginfos)
        if ret == 1:
            logger.error("check abi error: %s", ret)
        else:
            logger.debug("check abi ok: %s", ret)

        if os.path.exists(output):
            # change of abi
            comment = {"name": "check_abi/{}/{}".format(package_arch, self._repo), "result": "WARNING",
                       "link": self._rpm_package.checkabi_md_in_repo(committer, self._repo, package_arch,
                                os.path.basename(output), package_url)}
        else:
            comment = {"name": "check_abi/{}/{}".format(package_arch, self._repo), "result": "SUCCESS"}

        logger.debug("check abi comment: %s", comment)
        comments = []
        try:
            if os.path.exists(comment_file):
                with open(comment_file, "r") as f:  # one repo with multi build package
                    comments = yaml.safe_load(f)
                    logger.debug("check abi comments: %s", comments)
            comments.append(comment)
            with open(comment_file, "w") as f:
                yaml.safe_dump(comments, f)  # list
        except IOError:
            logger.exception("save check abi comment file exception")
        except yaml.MarkedYAMLError:
            logger.exception("save check abi comment file exception, yaml format error")

    def check_install_rpm(self, config):
        """
        检查生成的rpm是否可以安装
        :param config:
        :return:
        """
        logger.info("*** start check install start ***")

        # 1. prepare install root directory
        _ = not os.path.exists(config.install_root) and os.makedirs(config.install_root)
        logger.info("create install root directory: %s", config.install_root)

        # 2. prepare repo
        repo_source = OBSRepoSource()   # obs 实时构建repo地址
        obs_branch_list = Constant.GITEE_BRANCH_PROJECT_MAPPING.get(config.branch_name, [])
        repo_config = repo_source.generate_repo_info(config.branch_name, obs_branch_list, config.arch, "check_install")
        logger.info("repo source config:\n%s", repo_config)

        # write to /etc/yum.repos.d
        with open("obs_realtime.repo", "w+") as f:
            f.write(repo_config)

        # 3. dnf install using repo name start with "check_install"
        names = []
        packages = []
        for name, package in self._rpm_package.iter_all_rpm():
            # ignore debuginfo rpm
            if "debuginfo" in name or "debugsource" in name:
                logger.debug("ignore debug rpm: %s", name)
                continue
            names.append(name)
            packages.append(package)

        logger.info("install rpms: %s", names)
        if packages:
            check_install_cmd = "sudo dnf install -y --installroot={} --setopt=reposdir=. {}".format(
                    config.install_root, " ".join(packages))
            ret, _, err = shell_cmd_live(check_install_cmd, verbose=True)
            if ret:
                logger.error("install rpms error, %s, %s", ret, err)
                comment = {"name": "check_install", "result": "FAILED"}
            else:
                logger.info("install rpm success")
                comment = {"name": "check_install", "result": "SUCCESS"}

            logger.info("check install rpm comment: %s", comment)
            comments = []
            try:
                if os.path.exists(config.comment_file):
                    with open(config.comment_file, "r") as f:  # one repo with multi build package
                        comments = yaml.safe_load(f)
                comments.append(comment)
                with open(config.comment_file, "w") as f:
                    yaml.safe_dump(comments, f)  # list
            except IOError:
                logger.exception("save check install comment file exception")


def notify(config, extrawork):
    """
    notify, run after copy rpm to rpm repo
    :param config: args
    :param extrawork:
    :return:
    """
    if extrawork.is_pkgship_need_notify(config.pkgship_meta):
        extrawork.pkgship_notify(config.notify_url, config.token, config.rpm_repo_url,
                                 config.arch, config.notify_user, config.notify_password)


def checkabi(config, extrawork):
    """
    check abi, run before copy rpm to rpm repo
    :param config: args
    :param extrawork:
    :return:
    """
    extrawork.check_rpm_abi(config.rpm_repo_url, config.arch, config.output, config.committer, config.comment_file,
                            config.obs_addr, config.branch_name, config.obs_repo_url)


def comparepackage(config, extrawork):
    """
    对比两个版本rpm包之间的差异，根据差异找到受影响的rpm包
    :param config: args
    :return:
    """
    logger.info("compare package start")
    compare_package = ComparePackage(logger=logger)
    result = compare_package.output_result_to_console(config.json_path, config.pr_link, config.ignore, config.package,
                                                      config.check_result_file, config.pr_commit_json_file)
    logger.info("compare package result:%s", result)
    logger.info("compare package finish")


def checkinstall(config, extrawork):
    """
    check install
    :param config: args
    :param extrawork:
    :return:
    """
    extrawork.check_install_rpm(config)


def getrelatedrpm(config, extrawork):
    """
    get related rpm package
    :param config:
    :param extrawork:
    :return:
    """
    for project in Constant.GITEE_BRANCH_PROJECT_MAPPING.get(config.branch_name):
        logging.debug("find project %s, package: %s, aarch: %s", project, config.package, config.arch)
        result = OBSProxy.get_binaries(project, config.package, config.arch)
        if result:
            logging.info("get binaries: %s", result)
            break


if "__main__" == __name__:
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--package", type=str, default="src-openeuler", help="obs package")
    parser.add_argument("-d", "--rpmbuild_dir", type=str,
            default="/home/jenkins/agent/buildroot/home/abuild/rpmbuild", help="rpmbuild dir")
    subparsers = parser.add_subparsers(help='sub-command help')

    # 添加子命令 notify
    parser_notify = subparsers.add_parser('notify', help='add help')
    parser_notify.add_argument("-n", type=str, dest="notify_url", help="target branch that merged to ")
    parser_notify.add_argument("-t", type=str, dest="token", default=os.getcwd(), help="obs workspace dir path")
    parser_notify.add_argument("-l", type=str, dest="rpm_repo_url", help="rpm repo where rpm saved")
    parser_notify.add_argument("-a", type=str, dest="arch", help="build arch")
    parser_notify.add_argument("-u", type=str, dest="notify_user", default="trigger", help="notify trigger user")
    parser_notify.add_argument("-w", type=str, dest="notify_password", help="notify trigger password")
    parser_notify.set_defaults(func=notify)

    # 添加子命令 checkabi
    parser_checkabi = subparsers.add_parser('checkabi', help='add help')
    parser_checkabi.add_argument("-l", type=str, dest="rpm_repo_url", help="rpm repo where rpm saved")
    parser_checkabi.add_argument("-a", type=str, dest="arch", help="build arch")
    parser_checkabi.add_argument("-o", type=str, dest="output", help="checkabi result")
    parser_checkabi.add_argument("-c", type=str, dest="committer", help="committer")
    parser_checkabi.add_argument("-s", type=str, dest="obs_addr", help="obs address")
    parser_checkabi.add_argument("-r", type=str, dest="branch_name", help="obs project name")
    parser_checkabi.add_argument("-b", type=str, dest="obs_repo_url", help="obs repo where rpm saved")
    parser_checkabi.add_argument("-p", "--package", type=str, help="obs package")
    parser_checkabi.add_argument("-e", type=str, dest="comment_file", help="check abi result comment")
    parser_checkabi.set_defaults(func=checkabi)

    # 添加子命令 compare_package
    parser_comparepackage = subparsers.add_parser('comparepackage', help='add help')
    parser_comparepackage.add_argument("-f", type=str, dest="check_result_file",
                                       help="compare package check item result")
    parser_comparepackage.add_argument("-j", type=str, dest="json_path", help="compare package json path")
    parser_comparepackage.add_argument("-i", "--ignore", action="store_true", default=False, help="ignore or not")
    parser_comparepackage.add_argument("-pr", type=str, dest="pr_link", help="PR link")
    parser_comparepackage.add_argument("-pr_commit", type=str, dest="pr_commit_json_file",
                                       help="PR commit file difference")
    parser_comparepackage.add_argument("-p", "--package", type=str, help="obs package")
    parser_comparepackage.set_defaults(func=comparepackage)

    # 添加子命令 checkinstall
    parser_checkinstall = subparsers.add_parser('checkinstall', help='add help')
    parser_checkinstall.add_argument("-r", type=str, dest="branch_name", help="obs project name")
    parser_checkinstall.add_argument("-a", type=str, dest="arch", help="build arch")
    parser_checkinstall.add_argument("-e", type=str, dest="comment_file", help="check install result comment")
    parser_checkinstall.add_argument("--obs_rpm_host", type=str, dest="obs_rpm_host", default="", help="obs rpm host")
    parser_checkinstall.add_argument("--install-root", type=str, dest="install_root",
                                     help="check install root dir")
    parser_checkinstall.set_defaults(func=checkinstall)

    # 添加子命令 getrelatedrpm
    parser_getrelatedrpm = subparsers.add_parser('getrelatedrpm', help='add help')
    parser_getrelatedrpm.add_argument("-r", type=str, dest="branch_name", help="obs project name")
    parser_getrelatedrpm.add_argument("-a", type=str, dest="arch", help="build arch")
    parser_getrelatedrpm.add_argument("-p", "--package", type=str, help="obs package")
    parser_getrelatedrpm.set_defaults(func=getrelatedrpm)

    args = parser.parse_args()

    _ = not os.path.exists("log") and os.mkdir("log")
    logger_conf_path = os.path.realpath(os.path.join(os.path.realpath(__file__),
                                                     "../../conf/logger.conf"))
    logging.config.fileConfig(logger_conf_path)
    logger = logging.getLogger("build")

    ew = ExtraWork(args.package, args.rpmbuild_dir)
    args.func(args, ew)
