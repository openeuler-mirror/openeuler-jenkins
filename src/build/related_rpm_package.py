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
# Description: This module is used to find related rpms
# **********************************************************************************

"""
This module is used to find related rpms
"""
import os
import subprocess
import logging
import requests
import tempfile
import shutil
from src.proxy.obs_proxy import OBSProxy
from src.constant import Constant
logging.basicConfig(format='%(message)s', level=logging.INFO)


class RelatedRpms(object):
    """ 
    Found related rpms
    """
    GITEEBRANCHPROJECTMAPPING = {
        "master": ["bringInRely", "openEuler:Extras", "openEuler:Factory", "openEuler:Mainline"],
        "openEuler-20.03-LTS": ["openEuler:20.03:LTS"],
        "openEuler-20.03-LTS-Next": ["openEuler:20.03:LTS:Next"],
        "openEuler-EPOL-LTS": ["bringInRely"],
        "openEuler-20.09": ["openEuler:20.09"],
        "mkopeneuler-20.03": ["openEuler:Extras"],
        "openEuler-20.03-LTS-SP1": ["openEuler:20.03:LTS:SP1", "openEuler:20.03:LTS:SP1:Epol"],
        "openEuler-20.03-LTS-SP2": ["openEuler:20.03:LTS:SP2", "openEuler:20.03:LTS:SP2:Epol"],
        "openEuler-20.03-LTS-SP3": ["openEuler:20.03:LTS:SP3", "openEuler:20.03:LTS:SP3:Epol"],
        "openEuler-22.03-LTS-Next": ["openEuler:22.03:LTS:Next", "openEuler:22.03:LTS:Next:Epol"],
        "oepkg_openstack-common_oe-20.03-LTS-SP2": ["openEuler:20.03:LTS:SP2:oepkg:openstack:common"],
        "oepkg_openstack-rocky_oe-20.03-LTS-SP2": ["openEuler:20.03:LTS:SP2:oepkg:openstack:rocky"],
        "oepkg_openstack-queens_oe-20.03-LTS-SP2": ["openEuler:20.03:LTS:SP2:oepkg:openstack:queens"],
        "oepkg_openstack-common_oe-20.03-LTS-Next": ["openEuler:20.03:LTS:Next:oepkg:openstack:common"],
        "oepkg_openstack-rocky_oe-20.03-LTS-Next": ["openEuler:20.03:LTS:Next:oepkg:openstack:rocky"],
        "oepkg_openstack-queens_oe-20.03-LTS-Next": ["openEuler:20.03:LTS:Next:oepkg:openstack:queens"],
        "oepkg_openstack-common_oe-20.03-LTS-SP3": ["openEuler:20.03:LTS:SP3:oepkg:openstack:common"],
        "oepkg_openstack-rocky_oe-20.03-LTS-SP3": ["openEuler:20.03:LTS:SP3:oepkg:openstack:rocky"],
        "oepkg_openstack-queens_oe-20.03-LTS-SP3": ["openEuler:20.03:LTS:SP3:oepkg:openstack:queens"]
    }

    def __init__(self, obs_addr, obs_repo_url, branch_name, package_arch):
        """
        :param repo: obs address
        :param obs_repo_url: obs repo
        :param project_name: project name
        :param package_arch: aarch64/x86_64
        """
        self._obs_addr = obs_addr
        self._obs_repo_url = obs_repo_url
        self._project_name = "openEuler:Mainline"
        self._package_arch = package_arch
        self._arch_names = {}
        self._branch_name = branch_name      

    def get_src_name(self, temp_path, rpm_name):
        """
        Get src name by rpm_name
        """
        rpm_qi_info_file = os.path.join(temp_path, "rpmqi.txt")
        subprocess.run("rpm -qpi {} > {}".format(rpm_name, rpm_qi_info_file), shell=True, stderr=subprocess.PIPE)
        with open(rpm_qi_info_file, 'r') as fd:
            lines = fd.readlines()
            fd.close()
        for line in lines:
            if line.startswith("Source RPM  : "):
                src_name = line.split("Source RPM  : ")[-1].split("\n")[0]
                return src_name.rsplit("-", 2)[0]

    def get_requeset_by_name(self, temp_path, rpm_name, src_name):
        """
        Get requeset by name
        """
        if self._package_arch == "x86_64":
            self._arch_names["standard_x86_64/x86_64"] = os.path.join(temp_path, "x86_64.html")
            self._arch_names["standard_x86_64/noarch"] = os.path.join(temp_path, "x86_noarch.html")
        else:
            self._arch_names["standard_aarch64/aarch64"] = os.path.join(temp_path, "aarch64.html")
            self._arch_names["standard_aarch64/noarch"] =  os.path.join(temp_path, "noarch.html")
        download_project_name = self._project_name.replace(":", ":/")
        rpm_base_name = os.path.basename(rpm_name).rsplit("-", 2)[0]
        rpm_arch_name = os.path.basename(rpm_name).split(".oe1")[-1]
        rpm_final_name = ""
        has_found = False
        for name in  self._arch_names:
            download_req_addr = os.path.join(self._obs_repo_url, download_project_name, name)
            logging.info("downloading index of %s", download_req_addr)
            subprocess.run("wget -t 5 -c {} -O {} > /dev/null 2>&1".format(download_req_addr, self._arch_names[name]),
                            shell=True)
            if not has_found:
                with open(self._arch_names[name], "r") as fd:
                    lines = fd.readlines()
                    fd.close()
                for lin in lines:
                    if rpm_base_name in lin and rpm_arch_name in lin:
                        if "title=\"" in lin:
                            find_rpm_name = lin.split("title=\"")[-1].split("\"")[0]
                        else:
                            find_rpm_name = lin.split("href=\"")[-1].split("\"")[0]
                        if find_rpm_name.rsplit("-", 2)[0] == rpm_base_name:
                            if find_rpm_name.split(".oe1")[-1] == rpm_arch_name:
                                rpm_final_name = find_rpm_name
                                has_found = True
        logging.info("------------rpm_name:%s rpm_final_name:%s------------------", rpm_name, rpm_final_name)
        rpm_requeset_info = os.path.join(temp_path, "rpm_requeset.html")

        req_addr = os.path.join(self._obs_addr, "package/binary", self._project_name, src_name, 
                        "standard_" + self._package_arch, self._package_arch, os.path.basename(rpm_final_name))

        logging.info("find required_by info from: %s", req_addr)
        req = requests.get(req_addr)
        with open(rpm_requeset_info, "wb+") as fd:
            fd.write(req.content)
            fd.close()
        with open(rpm_requeset_info, "r") as fd:
            lines = fd.readlines()
            fd.close()

        required_by = set()
        has_found_required_by = False
        for line in lines:
            if "Required by" in line:
                has_found_required_by = True
                continue
            if has_found_required_by and "package/dependency/" in line:
                required_by_name = line.split("\">")[-1].split("<")[0]
                required_by.add(required_by_name)
                continue
            if has_found_required_by and "<th class=" in line:
                break
        return required_by

    def download_required_by_rpms(self, required_by_names):
        """
        Download rpms
        """
        logging.info("-------begin download_required_by_rpms------length:%d------", len(required_by_names))
        download_project_name = self._project_name.replace(":", ":/")
        related_rpms_url = set()
        for name in self._arch_names:
            with open(self._arch_names[name], "r") as fd:
                lines = fd.readlines()
                fd.close()
            for lin in lines:
                for req_name in required_by_names:
                    if ".rpm" in lin and req_name + "-" in lin and "-" + req_name + "-" not in lin and \
                        "-debuginfo-" not in lin and "-debugsource-" not in lin and \
                        "-help-" not in lin and "-devel-" not in lin:
                        if "title=\"" in lin:
                            rpm_name = lin.split("title=\"")[-1].split("\"")[0]
                        else:
                            rpm_name = lin.split("href=\"")[-1].split("\"")[0]
                        download_addr = os.path.join(self._obs_repo_url, download_project_name, name, rpm_name)
                        logging.debug("find related rpms url: %s", download_addr)
                        related_rpms_url.add(download_addr)
                        break
        return related_rpms_url

    def get_related_rpms_url(self, rpm_url):
        """
        Get related rpms url
        """
        logging.info("-------get_related_rpms_url rpm_name:%s---------", rpm_url)
        if os.path.exists(self._obs_repo_url):
            return self._obs_repo_url
        temp_path = os.path.abspath(tempfile.mkdtemp(dir="/var/tmp/"))
        if os.path.exists(rpm_url):
            rpm_path = rpm_url
        else:
            subprocess.run("wget -t 5 -c -P {} {}".format(temp_path, rpm_url), shell=True)
            rpm_path = os.path.join(temp_path, os.path.basename(rpm_url))
        
        for project in Constant.GITEE_BRANCH_PROJECT_MAPPING.get(self._branch_name):
            logging.debug("find project %s, rpm_name: %s, aarch: %s", project, 
                            os.path.basename(rpm_path), self._package_arch)
            if OBSProxy.list_repos_of_arch(project, os.path.basename(rpm_path), self._package_arch):
                self._project_name = project
                logging.info("get project name: %s", project)

        src_name = self.get_src_name(temp_path, rpm_path)
        logging.info("get_related_rpms_url src_name:%s", src_name)
        required_by_names = self.get_requeset_by_name(temp_path, rpm_path, src_name)
        related_rpms_url = set()
        if required_by_names:
            logging.debug("has found required_by_names:%s", required_by_names)
            related_rpms_url = self.download_required_by_rpms(required_by_names)
        else:
            logging.info("not found required_by_names")
        shutil.rmtree(temp_path)
        return related_rpms_url
