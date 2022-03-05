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
# Description: jenkins api proxy
# **********************************************************************************
"""

import logging
import re
import os

# not friendly when job in folders
import jenkins
from src.utils.dt_transform import convert_timestamp_to_naive

logger = logging.getLogger("common")


class JenkinsProxy(object):
    """
    Jenkins 代理，实现常见的jenkins操作
    """

    def __init__(self, base_url, username, token, timeout=10):
        """

        :param base_url:
        :param username: 用户名
        :param token:
        :param timeout:
        """
        self._username = username
        self._token = token
        self._timeout = timeout
        self._jenkins = jenkins.Jenkins(base_url, username=username, password=token, timeout=timeout)

    def create_job(self, job_path, config):
        """
        创建任务
        :param job_path: 任务路径
        :param config: 任务描述，xml
        :return: True / False
        """
        try:
            self._jenkins.create_job(job_path, config)
            return True
        except jenkins.JenkinsException as e:
            logger.exception("create job exception, %s", e)
            return False

    def update_job(self, job_path, config):
        """
        更新任务
        :param job_path: 任务路径
        :param config: 任务描述，xml
        :return: True / False
        """
        try:
            self._jenkins.reconfig_job(job_path, config)
            return True
        except jenkins.JenkinsException as e:
            logger.exception("update job exception, %s", e)
            return False

    def get_config(self, job_path):
        """
        获取任务描述，xml
        :param job_path: 任务路径
        :return: None if job_path not exist
        """
        try:
            return self._jenkins.get_job_config(job_path)
        except jenkins.JenkinsException as e:
            logger.exception("get config exception, %s", e)
            return None

    def get_jobs_list(self, job_path):
        """
        获取任务列表
        :return: list
        """
        try:
            jobs = self._jenkins.get_job_info(job_path)["jobs"]
            return [job["name"] for job in jobs]
        except jenkins.JenkinsException as e:
            logger.exception("update job exception, %s", e)
            return []

    def get_job_build_info(self, job_path, build_no):
        """
        get job and build info
        :param job_path:
        :param build_no:
        :return:
        """
        job_info = self.get_job_info(job_path)
        build_info = self.get_build_info(job_path, build_no)
        if not all([job_info, build_info]):
            return None, None, None

        build_dt = convert_timestamp_to_naive(build_info["timestamp"])
        cause_description, _, _ = self.get_build_trigger_reason(build_info)
        trigger_reason = cause_description if cause_description else "no upstream build"

        return job_info["url"], build_dt, trigger_reason

    def get_job_info(self, job_path):
        """
        获取任务信息
        :param job_path: job路径
        :return: None if job_path not exist
        """
        try:
            return self._jenkins.get_job_info(job_path)
        except jenkins.JenkinsException as e:
            logger.exception("get job exception, %s", e)
            return None

    def get_build_info(self, job_path, build_no):
        """
        获取任务构建信息
        :param job_path: job路径
        :param build_no: build编号
        :return: None if job_path or build_no not exist
        """
        try:
            return self._jenkins.get_build_info(job_path, build_no)
        except jenkins.JenkinsException as e:
            logger.exception("get job build exception, %s", e)
            return None

    @staticmethod
    def get_build_trigger_reason(build_info):
        """
        获取触发当前任务的上级job及build
        :param build_info: 当前任务构建信息
        :return: None if cause build not exist
        """
        causes = []
        for action in build_info["actions"]:
            if action["_class"] == "hudson.model.CauseAction":
                causes = action["causes"]
                break
        for cause in causes:
            if cause["_class"] == "hudson.model.Cause$UpstreamCause":
                cause_description = cause["shortDescription"]
                cause_job_path = cause["upstreamProject"]
                cause_build_no = int(cause["upstreamBuild"])
                return cause_description, cause_job_path, cause_build_no
        return None, None, None

    @classmethod
    def get_job_path_from_job_url(cls, job_url):
        """
        从url中解析job路径
        :param job_url: 当前工程url, for example https://domain/job/A/job/B/job/C
        :return: for example, A/B/C
        """
        jenkins_first_level_dir_index = 2
        jenkins_dir_interval_with_level = 2
        job_path = re.sub(r"/$", "", job_url)
        job_path = re.sub(r"http[s]?://", "", job_path)
        sp = job_path.split("/")[jenkins_first_level_dir_index::
                                 jenkins_dir_interval_with_level]
        sp = [item for item in sp if item != ""]
        job_path = "/".join(sp)
        return job_path

    @staticmethod
    def get_job_path_build_no_from_build_url(build_url):
        """
        从url中解析job路径
        :param build_url: 当前构建url, for example https://domain/job/A/job/B/job/C/number/
        :return: for example A/B/C/number
        """
        job_plus_build_no = re.sub(r"/$", "", build_url)
        job_url = os.path.dirname(job_plus_build_no)
        build_no = os.path.basename(job_plus_build_no)
        job_path = JenkinsProxy.get_job_path_from_job_url(job_url)
        return job_path, build_no

    @staticmethod
    def _get_upstream_jobs_path(job_info):
        """
        从job详情中解析上级job路径
        :param job_info: 当前任务详情
        :return:
        """
        upstream_job_path_list = []
        for project in job_info.get("upstreamProjects", []):
            job_url = JenkinsProxy.get_job_path_from_job_url(project["url"])
            upstream_job_path_list.append(job_url)
        return upstream_job_path_list

    def get_upstream_builds(self, build_info):
        """
        菱形任务工作流时，Jenkins提供的接口不支持多个upstream build
              A
            /   \
          B       C
            \   /
              D
        :param build_info:
        :return:
        """
        cause_description, cause_job_path, cause_build_no = self.get_build_trigger_reason(build_info)
        cause_build_info = self.get_build_info(cause_job_path, cause_build_no)
        cause_cause_description, cause_cause_job_path, cause_cause_build_no = self.get_build_trigger_reason(
            cause_build_info)
        logger.debug("cause_build_no: %s, cause_job_path: %s, cause_cause_build_no: %s, cause_cause_job_path: %s",
                     cause_build_no, cause_job_path, cause_cause_build_no, cause_cause_job_path)
        upstream_builds = [cause_build_info]
        if not all((cause_cause_description, cause_cause_job_path, cause_cause_build_no)):
            return upstream_builds

        cur_job_path, cur_build_no = JenkinsProxy.get_job_path_build_no_from_build_url(build_info["url"])
        cur_job_info = self.get_job_info(cur_job_path)
        upstream_jobs_path = JenkinsProxy._get_upstream_jobs_path(cur_job_info)
        for upstream_job_path in upstream_jobs_path:
            logger.debug("%s", upstream_job_path)
            upstream_jobs_path = self.get_job_info(upstream_job_path)
            upstream_builds_no = [item["number"] for item in upstream_jobs_path.get("builds", [])]
            for upstream_build_no in upstream_builds_no:
                logger.debug("try build id %s", upstream_build_no)
                if upstream_job_path == cause_job_path:
                    continue
                a_build_info = self.get_build_info(upstream_job_path, upstream_build_no)
                a_cause_description, a_cause_job_path, a_cause_build_no = JenkinsProxy.get_build_trigger_reason(
                    a_build_info)
                if all((a_cause_description, a_cause_job_path, a_cause_build_no)) \
                        and a_cause_job_path == cause_cause_job_path and a_cause_build_no == cause_cause_build_no:
                    logger.debug("build id %s match", a_cause_build_no)
                    upstream_builds.append(a_build_info)
                    break

        return upstream_builds
