# -*- encoding=utf-8 -*-
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
