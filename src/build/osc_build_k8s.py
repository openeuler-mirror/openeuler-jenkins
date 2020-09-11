# -*- encoding=utf-8 -*-
import os
import sys
import logging.config
import logging
import argparse
from xml.etree import ElementTree


class SinglePackageBuild(object):

    GITEEBRANCHPROJECTMAPPING = {
        "master": ["bringInRely", "openEuler:Extras", "openEuler:Factory", "openEuler:Mainline"],
        "openEuler-20.03-LTS": ["openEuler:20.03:LTS"],
        "openEuler-20.03-LTS-Next": ["openEuler:20.03:LTS:Next"],
        "openEuler-EPOL-LTS": ["bringInRely"],
        "openEuler-20.09": ["openEuler:20.09"],
        "mkopeneuler-20.03": ["openEuler:Extras"]
    }

    def __init__(self, package, arch, target_branch):
        self._package = package
        self._arch = arch
        self._branch = target_branch

    def get_need_build_obs_repos(self, project):
        """
        需要构建obs repo列表
        :return: list<dict>
        """
        return OBSProxy.list_repos_of_arch(project, self._package, self._arch)

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
            if not OBSProxy.build_package(project, self._package, repo["repo"], self._arch):
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
        if self._branch not in self.GITEEBRANCHPROJECTMAPPING:
            logger.error("branch \"{}\" not support yet".format(self._branch))
            sys.exit(1)

        for project in self.GITEEBRANCHPROJECTMAPPING.get(self._branch):
            logger.debug("start build project {}".format(project))

            obs_repos = self.get_need_build_obs_repos(project)
            if not obs_repos:
                logger.info("all repos ignored of project {}".format(project))
                continue

            logger.debug("build obs repos: {}".format(obs_repos))
            ret = self.build_obs_repos(project, obs_repos, work_dir, code_dir)
            if ret > 0:
                logger.debug("build run return {}".format(ret))
                logger.error("build {} {} {} ... {}".format(project, self._package, self._arch, "failed"))
                sys.exit(1)     # finish if any error
            else:
                logger.info("build {} {} {} ... {}".format(project, self._package, self._arch, "ok"))


if "__main__" == __name__:
    args = argparse.ArgumentParser()

    args.add_argument("-p", type=str, dest="package", help="obs package")
    args.add_argument("-a", type=str, dest="arch", help="build arch")
    args.add_argument("-b", type=str, dest="branch", help="target branch that merged to ")
    args.add_argument("-c", type=str, dest="code", help="code dir path")
    args.add_argument("-w", type=str, dest="workspace", default=os.getcwd(), help="obs workspace dir path")

    args = args.parse_args()

    _ = not os.path.exists("log") and os.mkdir("log")
    logger_conf_path = os.path.realpath(os.path.join(os.path.realpath(__file__), "../../conf/logger.conf"))
    logging.config.fileConfig(logger_conf_path)
    logger = logging.getLogger("build")

    from src.proxy.obs_proxy import OBSProxy
    from src.utils.shell_cmd import shell_cmd_live

    spb = SinglePackageBuild(args.package, args.arch, args.branch)
    spb.build(args.workspace, args.code)
