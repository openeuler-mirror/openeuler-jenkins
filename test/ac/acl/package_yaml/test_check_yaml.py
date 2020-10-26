# -*- encoding=utf-8 -*-
"""
# ***********************************************************************************
# Copyright (c) Huawei Technologies Co., Ltd. 2020-2020. All rights reserved.
# [openeuler-jenkins] is licensed under the Mulan PSL v1.
# You can use this software according to the terms and conditions of the Mulan PSL v1.
# You may obtain a copy of Mulan PSL v1 at:
#     http://license.coscl.org.cn/MulanPSL
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY OR FIT FOR A PARTICULAR
# PURPOSE.
# See the Mulan PSL v1 for more details.
# Author: DisNight
# Create: 2020-09-17
# Description: test for check_yaml.py
# ***********************************************************************************/
"""

import unittest
import mock
import sys
import os
import types
import logging.config
import logging
import shutil

from src.ac.common.rpm_spec_adapter import RPMSpecAdapter
from src.proxy.git_proxy import GitProxy
from src.ac.common.gitee_repo import GiteeRepo
from src.ac.acl.package_yaml.check_yaml import CheckPackageYaml
from src.ac.framework.ac_result import FAILED, WARNING, SUCCESS
from src.ac.acl.package_yaml.check_repo import HgReleaseTags, GithubReleaseTags, GitReleaseTags, \
                                               GitlabReleaseTags, SvnReleaseTags, MetacpanReleaseTags, \
                                               PypiReleaseTags, RubygemReleaseTags, GiteeReleaseTags, \
                                               GnuftpReleaseTags

logging.getLogger('test_logger')

class TestCheckYamlField(unittest.TestCase):

    TEST_YAML_DIR = {
        "missing": os.path.join(os.path.dirname(os.path.realpath(__file__)), "fields_test_sample/missing.yaml"),
        "standard": os.path.join(os.path.dirname(os.path.realpath(__file__)), "fields_test_sample/standard.yaml")
    }

    def setUp(self):
        self.cy = CheckPackageYaml("", "", "")
        def set_yaml(self, file):
            self._gr.yaml_file = file
        self.cy.set_yaml = types.MethodType(set_yaml, self.cy, CheckPackageYaml) # python3该接口有变化 为实例动态绑定接口

    def test_none_file(self):
        self.cy.set_yaml(None)
        result = self.cy.check_fields()
        self.assertEqual(result, WARNING)
    
    def test_missing_fields(self):
        self.cy.set_yaml(self.TEST_YAML_DIR["missing"])
        result = self.cy.check_fields()
        self.assertEqual(result, WARNING)

    def test_standard_fields(self):
        self.cy.set_yaml(self.TEST_YAML_DIR["standard"])
        result = self.cy.check_fields()
        self.assertEqual(result, SUCCESS)


class TestCheckYamlRepo(unittest.TestCase):
    
    SUCCESS_TAG_LIST = ["0.0.0", "0.0.1"]
    FAILED_TAG_LIST = []
    TEST_YAML_DIR = {
        "na": os.path.join(os.path.dirname(os.path.realpath(__file__)), "repo_test_sample/na_test/na.yaml"),
        "hg": os.path.join(os.path.dirname(os.path.realpath(__file__)), "repo_test_sample/hg_test/hg_test.yaml"),
        "github": os.path.join(os.path.dirname(os.path.realpath(__file__)), "repo_test_sample/github_test/github_test.yaml"),
        "git": os.path.join(os.path.dirname(os.path.realpath(__file__)), "repo_test_sample/git_test/git_test.yaml"),
        "gitlab.gnome": os.path.join(os.path.dirname(os.path.realpath(__file__)), "repo_test_sample/gitlab_gnome_test/gitlab_gnome_test.yaml"),
        "svn": os.path.join(os.path.dirname(os.path.realpath(__file__)), "repo_test_sample/svn_test/svn_test.yaml"),
        "metacpan": os.path.join(os.path.dirname(os.path.realpath(__file__)), "repo_test_sample/metacpan_test/metacpan_test.yaml"),
        "pypi": os.path.join(os.path.dirname(os.path.realpath(__file__)), "repo_test_sample/pypi_test/pypi_test.yaml"),
        "rubygem": os.path.join(os.path.dirname(os.path.realpath(__file__)), "repo_test_sample/rubygem_test/rubygem_test.yaml"),
        "gitee": os.path.join(os.path.dirname(os.path.realpath(__file__)), "repo_test_sample/gitee_test/gitee_test.yaml"),
        "gnu-ftp": os.path.join(os.path.dirname(os.path.realpath(__file__)), "repo_test_sample/gnu_ftp_test/gnu_ftp_test.yaml")
    }

    TEST_SPEC_DIR = {
        "na": os.path.join(os.path.dirname(os.path.realpath(__file__)), "repo_test_sample/na_test/na.spec"),
        "hg": os.path.join(os.path.dirname(os.path.realpath(__file__)), "repo_test_sample/hg_test/hg_test.spec"),
        "github": os.path.join(os.path.dirname(os.path.realpath(__file__)), "repo_test_sample/github_test/github_test.spec"),
        "git": os.path.join(os.path.dirname(os.path.realpath(__file__)), "repo_test_sample/git_test/git_test.spec"),
        "gitlab.gnome": os.path.join(os.path.dirname(os.path.realpath(__file__)), "repo_test_sample/gitlab_gnome_test/gitlab_gnome_test.spec"),
        "svn": os.path.join(os.path.dirname(os.path.realpath(__file__)), "repo_test_sample/svn_test/svn_test.spec"),
        "metacpan": os.path.join(os.path.dirname(os.path.realpath(__file__)), "repo_test_sample/metacpan_test/metacpan_test.spec"),
        "pypi": os.path.join(os.path.dirname(os.path.realpath(__file__)), "repo_test_sample/pypi_test/pypi_test.spec"),
        "rubygem": os.path.join(os.path.dirname(os.path.realpath(__file__)), "repo_test_sample/rubygem_test/rubygem_test.spec"),
        "gitee": os.path.join(os.path.dirname(os.path.realpath(__file__)), "repo_test_sample/gitee_test/gitee_test.spec"),
        "gnu-ftp": os.path.join(os.path.dirname(os.path.realpath(__file__)), "repo_test_sample/gnu_ftp_test/gnu_ftp_test.spec")
    }

    def setUp(self):
        self.cy = CheckPackageYaml("", "", "")
        def set_yaml(self, file):
            self._gr.yaml_file = file
        def set_spec(self, file):
            self._spec = RPMSpecAdapter(file)
        self.cy.set_yaml = types.MethodType(set_yaml, self.cy, CheckPackageYaml) # python3该接口有变化 为实例动态绑定接口
        self.cy.set_spec = types.MethodType(set_spec, self.cy, CheckPackageYaml) # python3该接口有变化 为实例动态绑定接口

    def test_none_file(self):
        self.cy.set_yaml(None)
        self.cy.check_fields()
        result = self.cy.check_repo()
        self.assertEqual(result, SUCCESS)
    
    def test_NA_repo(self):
        self.cy.set_yaml(self.TEST_YAML_DIR["na"])
        self.cy.check_fields()
        result = self.cy.check_repo()
        self.assertEqual(result, WARNING)
    
    @mock.patch.object(HgReleaseTags, "get_tags")
    def test_hg_repo_success(self, mock_get_tags):
        self.cy.set_yaml(self.TEST_YAML_DIR["hg"])
        mock_get_tags.return_value = self.SUCCESS_TAG_LIST
        self.cy.check_fields()
        result = self.cy.check_repo()
        self.assertEqual(result, SUCCESS)

    @mock.patch.object(HgReleaseTags, "get_tags")
    def test_hg_repo_failed(self, mock_get_tags):
        self.cy.set_yaml(self.TEST_YAML_DIR["hg"])
        mock_get_tags.return_value = self.FAILED_TAG_LIST
        self.cy.check_fields()
        result = self.cy.check_repo()
        self.assertEqual(result, WARNING)

    @mock.patch.object(GithubReleaseTags, "get_tags")
    def test_github_repo_success(self, mock_get_tags):
        self.cy.set_yaml(self.TEST_YAML_DIR["github"])
        mock_get_tags.return_value = self.SUCCESS_TAG_LIST
        self.cy.check_fields()
        result = self.cy.check_repo()
        self.assertEqual(result, SUCCESS)

    @mock.patch.object(GithubReleaseTags, "get_tags")
    def test_github_repo_failed(self, mock_get_tags):
        self.cy.set_yaml(self.TEST_YAML_DIR["github"])
        mock_get_tags.return_value = self.FAILED_TAG_LIST
        self.cy.check_fields()
        result = self.cy.check_repo()
        self.assertEqual(result, WARNING)

    @mock.patch.object(GitReleaseTags, "get_tags")
    def test_git_repo_success(self, mock_get_tags):
        self.cy.set_yaml(self.TEST_YAML_DIR["git"])
        mock_get_tags.return_value = self.SUCCESS_TAG_LIST
        self.cy.check_fields()
        result = self.cy.check_repo()
        self.assertEqual(result, SUCCESS)

    @mock.patch.object(GitReleaseTags, "get_tags")
    def test_git_repo_failed(self, mock_get_tags):
        self.cy.set_yaml(self.TEST_YAML_DIR["git"])
        mock_get_tags.return_value = self.FAILED_TAG_LIST
        self.cy.check_fields()
        result = self.cy.check_repo()
        self.assertEqual(result, WARNING)

    @mock.patch.object(GitlabReleaseTags, "get_tags")
    def test_gitlab_gnome_repo_success(self, mock_get_tags):
        self.cy.set_yaml(self.TEST_YAML_DIR["gitlab.gnome"])
        mock_get_tags.return_value = self.SUCCESS_TAG_LIST
        self.cy.check_fields()
        result = self.cy.check_repo()
        self.assertEqual(result, SUCCESS)

    @mock.patch.object(GitlabReleaseTags, "get_tags")
    def test_gitlab_gnome_repo_failed(self, mock_get_tags):
        self.cy.set_yaml(self.TEST_YAML_DIR["gitlab.gnome"])
        mock_get_tags.return_value = self.FAILED_TAG_LIST
        self.cy.check_fields()
        result = self.cy.check_repo()
        self.assertEqual(result, WARNING)

    @mock.patch.object(SvnReleaseTags, "get_tags")
    def test_svn_repo_success(self, mock_get_tags):
        self.cy.set_yaml(self.TEST_YAML_DIR["svn"])
        mock_get_tags.return_value = self.SUCCESS_TAG_LIST
        self.cy.check_fields()
        result = self.cy.check_repo()
        self.assertEqual(result, SUCCESS)

    @mock.patch.object(SvnReleaseTags, "get_tags")
    def test_svn_repo_failed(self, mock_get_tags):
        self.cy.set_yaml(self.TEST_YAML_DIR["svn"])
        mock_get_tags.return_value = self.FAILED_TAG_LIST
        self.cy.check_fields()
        result = self.cy.check_repo()
        self.assertEqual(result, WARNING)

    @mock.patch.object(MetacpanReleaseTags, "get_tags")
    def test_metacpan_repoo_success(self, mock_get_tags):
        self.cy.set_yaml(self.TEST_YAML_DIR["metacpan"])
        mock_get_tags.return_value = self.SUCCESS_TAG_LIST
        self.cy.check_fields()
        result = self.cy.check_repo()
        self.assertEqual(result, SUCCESS)

    @mock.patch.object(MetacpanReleaseTags, "get_tags")
    def test_metacpan_repo_failed(self, mock_get_tags):
        self.cy.set_yaml(self.TEST_YAML_DIR["metacpan"])
        mock_get_tags.return_value = self.FAILED_TAG_LIST
        self.cy.check_fields()
        result = self.cy.check_repo()
        self.assertEqual(result, WARNING)

    @mock.patch.object(PypiReleaseTags, "get_tags")
    def test_pypi_repo_success(self, mock_get_tags):
        self.cy.set_yaml(self.TEST_YAML_DIR["pypi"])
        mock_get_tags.return_value = self.SUCCESS_TAG_LIST
        self.cy.check_fields()
        result = self.cy.check_repo()
        self.assertEqual(result, SUCCESS)

    @mock.patch.object(PypiReleaseTags, "get_tags")
    def test_pypi_repo_failed(self, mock_get_tags):
        self.cy.set_yaml(self.TEST_YAML_DIR["pypi"])
        mock_get_tags.return_value = self.FAILED_TAG_LIST
        self.cy.check_fields()
        result = self.cy.check_repo()
        self.assertEqual(result, WARNING)

    @mock.patch.object(RubygemReleaseTags, "get_tags")
    def test_rubygem_repo_success(self, mock_get_tags):
        self.cy.set_yaml(self.TEST_YAML_DIR["rubygem"])
        mock_get_tags.return_value = self.SUCCESS_TAG_LIST
        self.cy.check_fields()
        result = self.cy.check_repo()
        self.assertEqual(result, SUCCESS)

    @mock.patch.object(RubygemReleaseTags, "get_tags")
    def test_rubygem_repo_failed(self, mock_get_tags):
        self.cy.set_yaml(self.TEST_YAML_DIR["rubygem"])
        mock_get_tags.return_value = self.FAILED_TAG_LIST
        self.cy.check_fields()
        result = self.cy.check_repo()
        self.assertEqual(result, WARNING)

    @mock.patch.object(GiteeReleaseTags, "get_tags")
    def test_gitee_repo_success(self, mock_get_tags):
        self.cy.set_yaml(self.TEST_YAML_DIR["gitee"])
        mock_get_tags.return_value = self.SUCCESS_TAG_LIST
        self.cy.check_fields()
        result = self.cy.check_repo()
        self.assertEqual(result, SUCCESS)

    @mock.patch.object(GiteeReleaseTags, "get_tags")
    def test_gitee_repo_failed(self, mock_get_tags):
        self.cy.set_yaml(self.TEST_YAML_DIR["gitee"])
        mock_get_tags.return_value = self.FAILED_TAG_LIST
        self.cy.check_fields()
        result = self.cy.check_repo()
        self.assertEqual(result, WARNING)

    @mock.patch.object(GnuftpReleaseTags, "get_tags")
    def test_gnu_ftp_repo_success(self, mock_get_tags):
        self.cy.set_yaml(self.TEST_YAML_DIR["gnu-ftp"])
        mock_get_tags.return_value = self.SUCCESS_TAG_LIST
        self.cy.check_fields()
        result = self.cy.check_repo()
        self.assertEqual(result, SUCCESS)

    @mock.patch.object(GnuftpReleaseTags, "get_tags")
    def test_gnu_ftp_repo_failed(self, mock_get_tags):
        self.cy.set_yaml(self.TEST_YAML_DIR["gnu-ftp"])
        mock_get_tags.return_value = self.FAILED_TAG_LIST
        self.cy.check_fields()
        result = self.cy.check_repo()
        self.assertEqual(result, WARNING)


class TestCheckConsistency(unittest.TestCase):
    DIR_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                            "repo_test_sample")
    TEST_SAMPLE_DIR = {
        "na": "na_test",
        "hg": "hg_test",
        "github": "github_test",
        "git": "git_test",
        "gitlab.gnome": "gitlab_gnome_test",
        "svn": "svn_test",
        "metacpan": "metacpan_test",
        "pypi": "pypi_test",
        "rubygem": "rubygem_test",
        "gitee": "gitee_test",
        "gnu-ftp": "gnu_ftp_test",
        "reponame": "repo_name_test"
    }

    def _test_repo_domain(self, dir_key, predict):
        self.cy = CheckPackageYaml(TestCheckConsistency.DIR_PATH, 
                                   TestCheckConsistency.TEST_SAMPLE_DIR[dir_key],
                                   None)
        self.cy.check_fields()
        result = self.cy.check_repo_domain()
        self.assertEqual(result, predict)

    def test_common_repo_domain_success(self):
        self._test_repo_domain("gitee", SUCCESS)

    def test_common_repo_domain_failed(self):
        self._test_repo_domain("svn", WARNING)

    def test_gnome_repo_domain(self):
        self._test_repo_domain("gitlab.gnome", SUCCESS)

    def test_pypi_repo_domain(self):
        self._test_repo_domain("pypi", SUCCESS)

    def _test_repo_name(self, dir_key, predict):
        self.cy = CheckPackageYaml(TestCheckConsistency.DIR_PATH, 
                                   TestCheckConsistency.TEST_SAMPLE_DIR[dir_key],
                                   None)
        self.cy.check_fields()
        result = self.cy.check_repo_name()
        self.assertEqual(result, predict)

    def test_common_repo_name_success(self):
        self._test_repo_name("gitlab.gnome", SUCCESS)

    def test_common_repo_name_failed(self):
        self._test_repo_name("reponame", WARNING)

    def test_svn_repo_name(self):
        self._test_repo_name("svn", SUCCESS)

if __name__ == '__main__':
    _ = not os.path.exists("log") and os.mkdir("log")
    logger_conf_path = os.path.realpath(os.path.join(os.path.dirname(os.path.realpath(__file__)), "../../../../src/conf/logger.conf"))
    logging.config.fileConfig(logger_conf_path)
    logger = logging.getLogger("test_logger")
    # Test check yaml fields
    suite = unittest.makeSuite(TestCheckYamlField)
    unittest.TextTestRunner().run(suite)
    # Test check yaml repo
    suite = unittest.makeSuite(TestCheckYamlRepo)
    unittest.TextTestRunner().run(suite)
    # Test check repo name and repo domain
    suite = unittest.makeSuite(TestCheckConsistency)
    unittest.TextTestRunner().run(suite)
    shutil.rmtree("log")