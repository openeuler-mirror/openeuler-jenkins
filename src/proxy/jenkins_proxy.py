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

# not friendly when job in folders
import jenkinsapi.jenkins as jenkins
import src.proxy.jenkins_patch
from src.utils.dt_transform import convert_utc_to_naive

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

    def create_job(self, job, config):
        """
        创建任务
        :param job: 任务名
        :param config: 任务描述，xml
        :return: True / False
        """
        try:
            self._jenkins.create_job(job, config)
            return True
        except Exception as e:
            logger.exception("create job exception, %s", e)
            return False

    def update_job(self, job, config):
        """
        更新任务
        :param job: 任务名
        :param config: 任务描述，xml
        :return: True / False
        """
        try:
            jks_job = self._jenkins[job]
            jks_job.update_config(config)
            return True
        except Exception as e:
            logger.exception("update job exception, %s", e)
            return False

    def get_config(self, job):
        """
        获取任务描述，xml
        :param job: 任务名
        :return: None if job not exist
        """
        try:
            return self._jenkins[job].get_config()
        except Exception as e:
            logger.exception("get config exception, %s", e)
            return None

    def get_build(self, job, build_no):
        """
        获取任务build
        :param job: 任务名
        :param build_no: build编号
        :return: None if job not exist
        """
        try:
            return self._jenkins[job].get_build(build_no)
        except Exception as e:
            logger.exception("get job build exception, %s", e)
            return None

    @classmethod
    def get_grandpa_build(cls, build):
        """
        获取上游的上游job build
        :param build:
        :return:
        """
        try:
            parent_build = build.get_upstream_build()
            return parent_build.get_upstream_build() if parent_build else None
        except Exception as e:
            logger.exception("get grandpa build exception, %s", e)
            return None

    def _get_upstream_jobs(self, job):
        """
        获取upstream jobs
        jenkinsapi提供的接口不支持跨目录操作
        :param job: Jenkins Job object
        :return:
        """
        logger.debug("get upstream jobs of %s", job._data["fullName"])
        jobs = []
        for project in job._data["upstreamProjects"]:   # but is the only way of get upstream projects info
            url = project.get("url")
            name = project.get("name")
            logger.debug("upstream project: %s %s", url, name)

            m = re.match("(.*)/job/.*", url)    # remove last part of job url, greedy match
            base_url = m.group(1)
            logger.debug("base url %s", base_url)

            try:
                j = jenkins.Jenkins(base_url, self._username, self._token, timeout=self._timeout)
                jobs.append(j[name])
            except Exception as e:
                logger.exception("get job of %s exception", url)
                continue

        return jobs

    def get_upstream_builds(self, build):
        """
        菱形任务工作流时，Jenkins提供的接口不支持多个upstream build
              A
            /   \
          B       C
            \   /
              D
        :param build:
        :return:
        """
        upstream_jobs = self._get_upstream_jobs(build.job)

        cause_build_id = build.get_upstream_build_number()
        cause_job_name = build.get_upstream_job_name()
        
        cause_job = None        
        for upstream_job in upstream_jobs:
            if upstream_job._data["fullName"] == cause_job_name:
                cause_job = upstream_job
                break
        if cause_job is None:
            logger.error("get cause job failed")
            return []
            
        cause_build = cause_job.get_build(cause_build_id)
        cause_cause_build_id = cause_build.get_upstream_build_number()
        
        logger.debug("cause_build_id: %s, cause_job_name: %s, cause_cause_build_id: %s",
                     cause_build_id, cause_job_name, cause_cause_build_id)

        upstream_builds = []
        for upstream_job in upstream_jobs:
            logger.debug("%s", upstream_job._data["fullName"])
            for build_id in upstream_job.get_build_ids():
                logger.debug("try build id %s", build_id)
                a_build = upstream_job.get_build(build_id)
                if a_build.get_upstream_build_number() == cause_cause_build_id:
                    logger.debug("build id %s match", build_id)
                    upstream_builds.append(a_build)
                    break

        return upstream_builds

    def get_job_url(self, job):
        """
        获取任务url
        :param job:
        :return:
        """
        j = self._jenkins[job]

        return self._jenkins[job].url

    def get_build_datetime(self, job, build):
        """
        get job build tims
        :param job:
        :param build:
        :return:
        """
        return convert_utc_to_naive(self._jenkins[job].get_build(build).get_timestamp())

    def get_build_trigger_reason(self, job, build):
        """
        get job build tims
        :param job:
        :param build:
        :return:
        """
        causes = self._jenkins[job].get_build(build).get_causes()
        if not causes:
            return "N/A"

        return causes[0]["shortDescription"]

    def get_job_build_info(self, job, build):
        """
        get job and build info
        :param job:
        :param build:
        :return:
        """
        job = self._jenkins[job]
        build = job.get_build(build)

        build_dt = convert_utc_to_naive(build.get_timestamp())

        causes = build.get_causes()
        trigger_reason = causes[0]["shortDescription"] if causes else "N/A"

        return job.url, build_dt, trigger_reason
