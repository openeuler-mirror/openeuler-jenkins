# -*- encoding=utf-8 -*-
"""
# ***********************************************************************************
# Copyright (c) Huawei Technologies Co., Ltd. 2020-2020. All rights reserved.
# [openeuler-jenkins] is licensed under the Mulan PSL v2.
# You can use this software according to the terms and conditions of the Mulan PSL v2.
# You may obtain a copy of Mulan PSL v2 at:
#          http://license.coscl.org.cn/MulanPSL2
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND,
# EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT,
# MERCHANTABILITY OR FIT FOR A PARTICULAR PURPOSE.
# See the Mulan PSL v2 for more details.
# Author: DisNight
# Create: 2020-09-17
# Description: check yaml file in software package
# ***********************************************************************************/
"""

import logging
import os
import yaml

from src.proxy.git_proxy import GitProxy
from src.proxy.requests_proxy import do_requests
from src.ac.framework.ac_base import BaseCheck
from src.ac.framework.ac_result import FAILED, WARNING, SUCCESS
from src.ac.common.gitee_repo import GiteeRepo
from src.ac.acl.package_yaml.check_repo import ReleaseTagsFactory
from src.ac.common.rpm_spec_adapter import RPMSpecAdapter

logger = logging.getLogger("ac")


class CheckPackageYaml(BaseCheck):
    """
    check yaml file
    """

    NOT_FOUND = "NA"
    PACKAGE_YAML_NEEDED_KEY = [
        "version_control",
        "src_repo",
        "tag_prefix",
        "separator"]
    
    VERSION_CTRL_TRANS = {
        "gitlab.gnome": "gnome",
        "pypi": "pythonhosted"
    }

    def __init__(self, workspace, repo, conf):
        super(CheckPackageYaml, self).__init__(workspace, repo, conf)

        self._gp = GitProxy(self._work_dir)
        self._gr = GiteeRepo(self._repo, self._work_dir, None)  # don't care about decompress
        if self._gr.spec_file:
            self._spec = RPMSpecAdapter(os.path.join(self._work_dir, self._gr.spec_file))
        else:
            self._spec = None
        self._yaml_content = None
        self._yaml_changed = True
        self._is_standard = True

    def __call__(self, *args, **kwargs):
        logger.info("check %s yaml ...", self._repo)
        self._yaml_changed = self.is_change_package_yaml() # yaml文件变更 进行检查
        # 因门禁系统限制外网访问权限，将涉及外网访问的检查功能check_repo暂时关闭
        return self.start_check_with_order("fields", "repo_domain", "repo_name")

    def is_change_package_yaml(self, base="HEAD~1", head="HEAD~0"):
        """
        如果本次提交变更了yaml，则对yaml进行检查
        :param:
        base:作为对比的提交点
        head:此次提交点
        :return: boolean
        """
        diff_files = self._gp.diff_files_between_commits(base, head)
        package_yaml = "{}.yaml".format(self._repo)     # package yaml file name

        for change_file in diff_files:
            if change_file == package_yaml:
                logger.debug("diff files: %s", diff_files)
                return True
        return False

    def check_fields(self):
        """
        检查yaml规定字段的完整性
        :return:
        """
        if not self._yaml_changed:
            return SUCCESS
        yaml_path = self._gr.yaml_file
        if yaml_path is None:
            self._is_standard = False
            logger.warning("yaml file missing")
            return WARNING
        try:
            with open(os.path.join(self._work_dir, yaml_path), 'r') as yaml_data:    # load yaml data
                self._yaml_content = yaml.safe_load(yaml_data)
        except IOError as e:
            logging.warning("package yaml not exist. %s", str(e))
            return WARNING
        except yaml.YAMLError as exc:
            logging.warning("Error parsering YAML: %s", str(exc))
            return WARNING
        
        result = SUCCESS
        for keyword in self.PACKAGE_YAML_NEEDED_KEY:
            if keyword not in self._yaml_content:
                logger.error("yaml field %s missing", keyword)
                self._is_standard = True
                result = WARNING 
        return result

    def check_repo(self):
        """
        检查yaml的有效性,能否从上游社区获取版本信息
        :return:
        """
        if not self._yaml_changed:
            return SUCCESS
        if not self._is_standard:
            logger.warning("yaml does not comply with the rule")
            return SUCCESS
        # get value by key from yaml data
        vc = self._yaml_content[self.PACKAGE_YAML_NEEDED_KEY[0]] # value of version_control
        sr = self._yaml_content[self.PACKAGE_YAML_NEEDED_KEY[1]] # value of src_repo

        if vc == self.NOT_FOUND or sr == self.NOT_FOUND:
            logger.warning("no info for upsteam")
            return WARNING

        release_tags = ReleaseTagsFactory.get_release_tags(vc)
        tags = release_tags.get_tags(sr)
        
        if not tags:
            logger.warning("failed to get version by yaml, version_control: %s, src_repo: %s", vc, sr)
            return WARNING
        return SUCCESS

    def check_repo_domain(self):
        """
        检查spec中source0域名是否包含yaml的version_control,仅做日志告警只返回SUCCESS(autoconf为特例)
        :return:
        """
        if not self._yaml_changed:
            return SUCCESS
        if not self._is_standard:
            logger.warning("yaml does not comply with the rule")
            return SUCCESS
        if not self._spec:
            logger.warning("spec does not exist")
            return SUCCESS

        vc = self._yaml_content[self.PACKAGE_YAML_NEEDED_KEY[0]]
        if vc == self.NOT_FOUND:
            return SUCCESS
        src_url = self._spec.get_source("Source0")
        if not src_url:
            src_url = self._spec.get_source("Source")
        vc = self.VERSION_CTRL_TRANS.get(vc, vc) # 对特殊的版本控制对应的域名进行转换
        logger.debug("version control: %s source url: %s", vc, src_url)
        if vc not in src_url: # 通过判断版本控制字段是否在主页url中 判断一致性
            logger.warning("%s is not in url: %s", vc, src_url)
            return WARNING
        return SUCCESS

    def check_repo_name(self):
        """
        检查spec中是否包含yaml中src_repo字段的软件名,仅做日志告警只返回SUCCESS
        :return:
        """
        if not self._yaml_changed:
            return SUCCESS
        if not self._is_standard:
            logger.warning("yaml does not comply with the rule")
            return SUCCESS
        if not self._spec:
            logger.warning("spec does not exist")
            return SUCCESS

        sr = self._yaml_content[self.PACKAGE_YAML_NEEDED_KEY[1]]
        if sr == self.NOT_FOUND:
            return SUCCESS
        
        software_name_list = list(filter(None, sr.split("/")))

        def guess_real_pkgname(name_list):
            """
            解析yaml中src_repo字段对应的软件包名
            :return:
            """
            pkgname = name_list[-1]
            if len(name_list) > 1 and name_list[-1] == "svn":
                pkgname = name_list[-2]
            if pkgname.endswith(".git"):
                pkgname = os.path.splitext(pkgname)[0]
            return pkgname

        software_name = guess_real_pkgname(software_name_list)
        src_url = self._spec.get_source("Source0")
        if not src_url:
            src_url = self._spec.get_source("Source")
        logger.debug("software name: %s source url: %s", software_name, src_url)
        if software_name not in src_url:
            logger.warning("%s is not in source0: %s", software_name, src_url)
            return WARNING
        return SUCCESS


