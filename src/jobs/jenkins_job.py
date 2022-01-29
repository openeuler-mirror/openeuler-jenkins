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
# Create: 2020-09-23
# Description: duplicate jenkins jobs configuration
# **********************************************************************************
"""
import sys

import gevent
from gevent import monkey

monkey.patch_all()

import abc
import os
import stat
import logging.config
import logging
import time
import re
import xml.etree.ElementTree as ET
import yaml
import argparse


class JenkinsJobs(object):
    """
    handle jenkins job with batch
    """

    __metaclass__ = abc.ABCMeta

    def __init__(self, template_jobs_dir, template_job, jenkins_proxy):
        """
        :param template_jobs_dir: 模板任务躲在的jenkins工程目录
        :param template_job: 考虑jenkins server的压力，客户端每次使用功能batch个协程发起请求
        :param jenkins_proxy: repo，buddy，package映射关系
        """
        self._template_job = template_job
        self._jenkins_proxy = jenkins_proxy
        self._template_job_config = jenkins_proxy.get_config(os.path.join(template_jobs_dir, template_job))

    def run(self, action, target_jobs_dir, jobs, exclude_jobs=None, concurrency=75, retry=3, interval=0):
        """
        启动
        :param action: 行为
        :param target_jobs_dir: 待更新/创建任务所在jenkins工程目录
        :param jobs: 任务列表
        :param exclude_jobs: 排除的任务列表
        :param concurrency: 并发量
        :param retry: 尝试次数
        :param interval: 每次batch请求后sleep时间（秒），
        :return:
        """
        logger.info("%s jobs %s", action, jobs)
        exclude_jobs_list = exclude_jobs if exclude_jobs else []
        real_jobs = self.get_real_target_jobs(target_jobs_dir, jobs, exclude_jobs_list, action)
        real_jobs = [os.path.join(target_jobs_dir, item) for item in real_jobs]
        logger.info("now %s %s jobs", action, len(real_jobs))

        def run_once(target_jobs):
            """
            run once for retry
            :param target_jobs: 目标任务列表
            :return:
            """
            batch = int((len(target_jobs) + concurrency - 1) / concurrency)
            _failed_jobs = []
            for index in range(batch):
                works = [gevent.spawn(self.dispatch, action, job, self._jenkins_proxy)
                         for job in target_jobs[index * concurrency: (index + 1) * concurrency]]
                logger.info("%s works, %s/%s ", len(works), index + 1, batch)
                gevent.joinall(works)
                for work in works:
                    if work.value["result"]:
                        logger.info("%s job %s ... ok", action, work.value["job"])
                    else:
                        _failed_jobs.append(work.value["job"])
                        logger.error("%s job %s ... failed", action, work.value["job"])

                time.sleep(interval)

            return _failed_jobs

        failed_jobs = run_once(real_jobs)

        for index in range(retry):
            if not failed_jobs:
                break
            logger.info("%s jobs failed, retrying %s/%s", len(failed_jobs), index + 1, retry)
            failed_jobs = run_once(failed_jobs)

        if failed_jobs:
            logger.warning("%s failed jobs", len(failed_jobs))
            logger.warning("%s%s", ",".join(failed_jobs[:100]), "..." if len(failed_jobs) > 100 else "")

    def dispatch(self, action, job, jenkins_proxy):
        """
        分发任务
        :param action: 更新或者创建
        :param job: 目标任务
        :param jenkins_proxy: 目标任务jenkins代理
        :return: dict
        """
        job_config = self.update_config(job.split("/")[-1])
        result = jenkins_proxy.create_job(job, job_config) if action == "create" \
            else jenkins_proxy.update_job(job, job_config)

        return {"job": job, "result": result}

    @abc.abstractmethod
    def get_real_target_jobs(self, target_jobs_dir, jobs, exclude_jobs, action):
        """
        真实有效的任务列表
        :param target_jobs_dir: 用户输入的目标任务目录
        :param jobs: 用户输入的任务列表
        :param exclude_jobs: 用户输入的exclude任务列表
        :param action: 用户输入的操作create/update
        :return: list<string>
        """
        exists_jobs_list = self._jenkins_proxy.get_jobs_list(target_jobs_dir)
        logger.info("%s exist %s jobs", target_jobs_dir, len(exists_jobs_list))
        if action == "update":
            return list(set(jobs).difference(set(exclude_jobs)).intersection(set(exists_jobs_list)))
        elif action == "create":
            return list(set(jobs).difference(set(exclude_jobs)).difference(set(exists_jobs_list)))
        else:
            logger.debug("illegal action: %s", action)
            return []

    @abc.abstractmethod
    def update_config(self, job):
        """
        implement in subclass
        :param job:
        :return:
        """
        raise NotImplementedError


class SrcOpenEulerJenkinsJobs(JenkinsJobs):
    """
    src-openEuler 仓库
    """

    def __init__(self, template_jobs_dir, template_job, jenkins_proxy, organization, gitee_token):
        super(SrcOpenEulerJenkinsJobs, self).__init__(template_jobs_dir, template_job, jenkins_proxy)

        self._all_community_jobs = self.get_all_repos(organization, gitee_token)
        logger.info("%s exist %s jobs", organization, len(self._all_community_jobs))
        self._config_table = self.load_exclusive_soe_config()

    @staticmethod
    def get_all_repos(organization, gitee_token):
        """
        Get all repositories belong openeuler or src-openeuler through file directories
        :param organization: openeuler/src-openeuler
        :param gitee_token:
        :return: A list of all repositories
        """
        # download community repo
        if os.path.exists('community'):
            os.system('rm -rf community')
        os.system('git clone -b master --depth 1 https://%s@gitee.com/openeuler/community' % gitee_token)

        sig_exception_list = ['README.md', 'sig-recycle', 'sig-template']
        sig_path = os.path.join('community', 'sig')
        repositories = []
        for i in os.listdir(sig_path):
            if i in sig_exception_list:
                continue
            if organization in os.listdir(os.path.join(sig_path, i)):
                for _, _, repos in os.walk(os.path.join(sig_path, i, organization)):
                    for repo in repos:
                        repositories.append(os.path.splitext(os.path.basename(repo))[0])
        return repositories

    def get_real_target_jobs(self, target_jobs_dir, jobs, exclude_jobs, action):
        """
        真实有效的任务列表
        :param target_jobs_dir: 用户输入的目标任务目录
        :param jobs: 用户输入的任务列表
        :param exclude_jobs: 用户输入的exclude任务列表
        :param action: 用户输入的操作create/update
        :return: list<string>
        """
        exists_jobs_list = self._jenkins_proxy.get_jobs_list(target_jobs_dir)
        logger.info("%s exist %s jobs", target_jobs_dir, len(exists_jobs_list))
        exclude_jobs_with_skipped = set(exclude_jobs).union(set(self._config_table.get("skipped_repo")))
        if "all" in jobs:
            jobs_in_community = list(set(self._all_community_jobs).difference(exclude_jobs_with_skipped))
        else:
            jobs_in_community = list(set(jobs).intersection(set(self._all_community_jobs)).difference(exclude_jobs_with_skipped))
        if action == "update":
            return list(set(jobs_in_community).intersection(set(exists_jobs_list)))
        elif action == "create":
            return list(set(jobs_in_community).difference(set(exists_jobs_list)))
        else:
            logger.debug("illegal action: %s", action)
            return []

    @staticmethod
    def load_exclusive_soe_config():
        """
        获取src-openeuler下所有已存在仓库的工程配置
        :return:
        """
        cur_path = os.path.abspath(os.path.dirname(__file__))
        try:
            with open(os.path.join(cur_path, "soe_exclusive_config.yaml"), "r") as f:
                config_table = yaml.safe_load(f)
        except OSError:
            logger.exception("soe_exclusive_config.yaml not exist")
            sys.exit(1)
        except yaml.MarkedYAMLError:
            logger.exception("soe_exclusive_config.yaml is not an illegal yaml format file")
            sys.exit(1)
        if not config_table:
            return {}
        # check yaml format and exception if not
        if not SrcOpenEulerJenkinsJobs.check_soe_exclusive_config_format(config_table):
            logger.exception("soe_exclusive_config.yaml is not an illegal yaml format file")
            sys.exit(1)
        return config_table

    @staticmethod
    def check_soe_exclusive_config_format(config_table):
        """
        检测配置文件格式
        :param config_table: 配置内容
        :return: True if config_table is an illegal format, or False
        """
        # expect config_table is a dict
        if not isinstance(config_table, dict):
            return False
        # expect config_table has repo/arch keys and the value is str
        skipped_repo = config_table.get("skipped_repo")
        exclusive_repo_config = config_table.get("repo_config")
        exclusive_arch_config = config_table.get("arch_config")
        if not all([skipped_repo, isinstance(skipped_repo, list),
                    exclusive_repo_config, isinstance(exclusive_repo_config, dict),
                    exclusive_arch_config, isinstance(exclusive_arch_config, dict)]):
            return False
        # expect exclusive_repo_config has repo/buddy/buddy keys and the value is str
        for _, value in exclusive_repo_config.items():
            repo_value = value.get("repo")
            buddy_value = value.get("buddy")
            package_value = value.get("packages")
            if not all([repo_value, buddy_value, package_value, isinstance(repo_value, str),
                        isinstance(buddy_value, str), isinstance(package_value, str)]):
                return False
        # expect exclusive_arch_config each value is str
        for _, value in exclusive_arch_config.items():
            if not all([value, isinstance(value, list)]):
                return False
        return True

    def update_config(self, job):
        """
        根据模板生成目标任务配置信息
        :param job: 目标任务
        :return: xml string
        """
        buddy = self._config_table.get("repo_config").get(job, {"repo": job, "buddy": job, "packages": job})
        root = ET.fromstring(self._template_job_config)

        ele = root.find("triggers//regexpFilterExpression")
        if ele is not None:
            ele.text = ele.text.replace(self._template_job, buddy["repo"])

        # parameterized trigger
        ele = root.find("publishers/hudson.plugins.parameterizedtrigger.BuildTrigger//projects")
        if ele is not None:
            arches = self._config_table.get("arch_config").get(job, ["x86_64", "aarch64"])
            project_template = ele.text.strip().split(",")[0].replace(self._template_job, buddy["repo"])
            projects = []
            for arch in arches:
                if arch == "x86_64":
                    arch = "x86-64"
                project = project_template.split("/")
                project[-2] = arch
                projects.append("/".join(project))
            ele.text = ",".join(projects)

        # join trigger
        ele = root.find("publishers/join.JoinTrigger//projects")
        if ele is not None:
            ele.text = ele.text.replace(self._template_job, buddy["repo"])

        # set repo defaultValue
        ele = root.find("properties//*[name=\"repo\"]/defaultValue")
        if ele is not None:
            ele.text = buddy["repo"]

        # set buddy defaultValue
        ele = root.find("properties//*[name=\"buddy\"]/defaultValue")
        if ele is not None:
            ele.text = buddy["buddy"]

        # set packages defaultValue
        ele = root.find("properties//*[name=\"package\"]/defaultValue")
        if ele is not None:
            ele.text = buddy["packages"]

        return ET.tostring(root).decode("utf-8")


class OpenEulerJenkinsJobs(SrcOpenEulerJenkinsJobs):
    """
    openEuler 仓库
    """

    @staticmethod
    def guess_build_script(job):
        """
        返回仓库对应的jenkins build脚本
        :param job:
        :return:
        """
        jenkinsfile_dir = os.path.realpath(os.path.join(__file__, "../../jenkinsfile"))

        script = job
        for filename in os.listdir(jenkinsfile_dir):
            if filename == script:
                break
            if re.match(r"{}\..*".format(job), filename):  # repo.{sufix}
                script = filename
                break

        script = os.path.realpath(os.path.join(jenkinsfile_dir, script))

        # helper chmod +x
        if os.path.exists(script):
            st = os.stat(script)
            os.chmod(script, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

        return script

    def update_config(self, job):
        """
        根据模板生成目标任务配置信息
        :param job: 目标任务
        :return: xml string
        """
        root = ET.fromstring(self._template_job_config.encode("utf-8"))

        buddy = self._all_community_jobs[job]  #

        # triggers
        ele = root.find("triggers//regexpFilterExpression")
        if ele is not None:
            ele.text = ele.text.replace(self._template_job, buddy["repo"])

        # parameterized trigger
        ele = root.find("publishers/hudson.plugins.parameterizedtrigger.BuildTrigger//projects")
        if ele is not None:
            arches = self._exclusive_arch.get(buddy["repo"])
            if arches:  # eg: [x86_64]
                projects = []
                for project in ele.text.split(","):
                    for arch in arches:
                        if arch in project:
                            projects.append(project)
                ele.text = ",".join(projects).replace(self._template_job, buddy["repo"])
            else:
                ele.text = ele.text.replace(self._template_job, buddy["repo"])

        # build
        script = self.guess_build_script(buddy["repo"])
        logger.debug("guess build script: %s", "script")
        ele = root.findall("buiders/hudson.task.Shell/command")
        if ele:
            # replace first command
            command = ele[0]
            command.text = script

        # join trigger
        ele = root.find("publishers/join.JoinTrigger//projects")
        if ele is not None:
            ele.text = ele.text.replace(self._template_job, buddy["repo"])

        # set repo defaultValue
        ele = root.find("properties//*[name=\"repo\"]/defaultValue")
        if ele is not None:
            ele.text = buddy["repo"]

        return ET.tostring(root)


if "__main__" == __name__:
    args = argparse.ArgumentParser()

    args.add_argument("-f", type=str, dest="organization", default="src-openeuler", help="src-openeuler or openeuler")

    args.add_argument("-a", type=str, dest="action", help="create or update")
    args.add_argument("-c", type=int, dest="concurrency", default=75, help="jobs send to jenkins server concurrency")
    args.add_argument("-r", type=int, dest="retry", default=3, help="retry times")
    args.add_argument("-i", type=int, dest="interval", default=0, help="retry interval")

    args.add_argument("-l", type=str, dest="exclude_jobs", nargs="*", help="jobs not to created")
    args.add_argument("-o", type=int, dest="jenkins_timeout", default=10, help="jenkins api timeout")

    args.add_argument("-u", type=str, dest="jenkins_user", help="jenkins user name")
    args.add_argument("-t", type=str, dest="jenkins_api_token", help="jenkins api token")

    args.add_argument("--gitee_token", type=str, dest="gitee_token", help="gitee token")
    args.add_argument("--jenkins_url", type=str, dest="jenkins_url", help="jenkins url")
    args.add_argument("-m", type=str, dest="template_job", help="template job name")
    args.add_argument("-s", type=str, dest="template_jobs_dir", help="jenkins dir of template job")
    args.add_argument("-j", type=str, dest="target_jobs", nargs="+", help="jobs to created")
    args.add_argument("-d", type=str, dest="target_jobs_dir", help="jenkins dir of target jobs")

    args = args.parse_args()

    # init logging
    _ = not os.path.exists("log") and os.mkdir("log")
    logger_conf_path = os.path.realpath(os.path.join(os.path.realpath(__file__), "../../conf/logger.conf"))
    logging.config.fileConfig(logger_conf_path)
    logger = logging.getLogger("jobs")

    from src.proxy.jenkins_proxy import JenkinsProxy

    jp = JenkinsProxy(args.jenkins_url, args.jenkins_user, args.jenkins_api_token,
                        args.jenkins_timeout)

    if args.organization == "src-openeuler":
        jenkins_jobs = SrcOpenEulerJenkinsJobs(args.template_jobs_dir,
            args.template_job, jp, args.organization, args.gitee_token)
    else:
        jenkins_jobs = OpenEulerJenkinsJobs(args.template_jobs_dir, args.template_job, jp, args.organization, args.gitee_token)

    jenkins_jobs.run(args.action, args.target_jobs_dir, args.target_jobs, exclude_jobs=args.exclude_jobs,
                     concurrency=args.concurrency, retry=args.retry, interval=args.interval)
