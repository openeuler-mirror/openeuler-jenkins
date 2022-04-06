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
# Description: jenkins patch
# **********************************************************************************

from urllib.parse import quote

from jenkinsapi.jenkinsbase import JenkinsBase

# hack, bug when if job under baseurl is not folder
# when use jenkins.jenkins src host
def resolve_job_folders(self, jobs):
    for job in list(jobs):
        if 'color' not in job.keys():
            jobs.remove(job)
            jobs += self.process_job_folder(job, self.baseurl)
        else:
            job["url"] = '%s/job/%s' % (self.baseurl, quote(job['name']))

    return jobs


old = JenkinsBase.resolve_job_folders
JenkinsBase.resolve_job_folders = resolve_job_folders
