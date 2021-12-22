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
# Description: obs api proxy
# **********************************************************************************

import os
import shutil
import logging

from src.utils.shell_cmd import shell_cmd_live

logger = logging.getLogger("common")


class OBSProxy(object):
    @staticmethod
    def is_project_has_package(project, package):
        """
        包是否在项目中
        :param project:
        :param package:
        :return:
        """
        return not not OBSProxy.list_project(project, package)

    @staticmethod
    def list_project(project, package=""):
        """
        列出项目下包列表
        :param project:
        :param package:
        :return:
        """
        cmd = "osc ll {} {}".format(project, package)
        ret, rs, _ = shell_cmd_live(cmd, cap_out=True)
        if ret:
            logger.error("list project package error, %s", ret)
            return None

        return rs

    @staticmethod
    def list_repos_of_arch(project, package, arch, show_exclude=False):
        """
        获取包的repo列表
        :param project:
        :param package:
        :return:
        """
        cmd = "osc results {} {} {} -a {}".format(
                "--show-exclude" if show_exclude else "", project, package, arch)
        ret, out, _ = shell_cmd_live(cmd, cap_out=True)
        if ret:
            logger.debug("list obs repos of arch error, %s", ret)
            return []

        rs = []
        for line in out:
            try:
                repo, arch, state = line.split()
                mpac = package
            except ValueError:
                repo, arch, pac, state = line.split()
                mpac = pac.split(":")[-1]
            rs.append({"repo": repo, "mpac": mpac, "state": state})

        return rs

    @staticmethod
    def list_packages_of_state(project, state):
        """
        获取project下某个状态的包列表
        :param project: obs项目
        :param state: 状态
        :return: list<str>
        """
        cmd = "osc results {} --csv |grep {} | awk -F';' '{{print $1}}'".format(project, state)
        ret, out, _ = shell_cmd_live(cmd, cap_out=True)
        if ret:
            logger.debug("list package of state error, %s", ret)
            return []

        return out

    @staticmethod
    def checkout_package(project, package):
        """
        checkout
        :param project:
        :param package:
        :return: 成功返回True，失败返回False
        """
        # pod cache
        _ = os.path.isdir(project) and shutil.rmtree(project)

        cmd = "osc co {} {}".format(project, package)
        logger.info("osc co %s %s", project, package)
        ret, _, _ = shell_cmd_live(cmd, verbose=True)

        if ret:
            logger.error("checkout package error, %s", ret)
            return False

        return True

    @staticmethod
    def build_package(project, package, repo, arch, spec, mpac, debug=False, root_build=False, disable_cpio=False):
        """
        build
        :param project:
        :param package:
        :param repo:
        :param arch:
        :param spec:
        :param mpac: multibuild package
        :param debug:
        :return:
        """
        package_path = "{}/{}".format(project, package)
        root_opt = "--userootforbuild" if root_build else ""
        debuginfo_opt = "--disable-debuginfo" if not debug else ""
        disable_cpio_bulk = "--disable-cpio-bulk-download" if disable_cpio else ""
        cmd = "cd {}; osc build {} {} {} {} {} {} --no-verify --clean --noservice -M {}".format(
            package_path, repo, arch, spec, root_opt, debuginfo_opt, disable_cpio_bulk, mpac)

        logger.info("osc build %s %s %s %s %s %s --no-verify --clean --noservice -M %s",
            repo, arch, spec, root_opt, debuginfo_opt, disable_cpio_bulk, mpac)
        ret, _, _ = shell_cmd_live(cmd, verbose=True)

        if ret:
            logger.error("build package error, %s", ret)
            return False

        return True

    @staticmethod
    def build_history(project, package, repo, arch):
        """
        构建历史
        :param project:
        :param package:
        :param repo:
        :param arch:
        :return:
        """
        cmd = "osc api /build/{}/{}/{}/{}/_history".format(project, repo, arch, package)
        ret, out, _ = shell_cmd_live(cmd, cap_out=True)
        if ret:
            logger.debug("list build history of package error, %s", ret)
            return ""

        return "\n".join(out)

    @staticmethod
    def get_binaries(project, package, arch):
        """
        获取包的二进制编译结果
        :param project:
        :param package:
        :param arch:
        :return:
        """
        cmd = "osc getbinaries {} {} standard_{} {}".format(project, package, arch, arch)
        ret, out, _ = shell_cmd_live(cmd, cap_out=True)
        if ret:
            logger.debug("package get binaries error, %s", ret)
            return []

        return out
