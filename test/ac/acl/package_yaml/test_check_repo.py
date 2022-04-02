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
# Description: test for check_repo.py
# ***********************************************************************************/
"""

import unittest
from unittest import mock
import os
import yaml
import logging.config
import logging
import shutil
from time import sleep

from src.ac.acl.package_yaml.check_repo import ReleaseTagsFactory

logging.getLogger('test_logger')

ACCESS2INTERNET = False

class TestGetReleaseTags(unittest.TestCase):
    TEST_YAML_DIR = {
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

    def _load_yaml(self, filepath):
        result = {}
        try:
            with open(filepath, 'r') as yaml_data:    # load yaml data
                result = yaml.safe_load(yaml_data)
        except IOError as e:
            logging.warning("package yaml not exist. %s", str(e))
        except yaml.YAMLError as exc:
            logging.warning("Error parsering YAML: %s", str(exc))
        finally:
            return result

    def _get_test_tags(self, version):
        sleep(2)
        yaml_content = self._load_yaml(self.TEST_YAML_DIR[version])
        vc = yaml_content.get("version_control", "")
        sr = yaml_content.get("src_repo", "")
        release_tags = ReleaseTagsFactory.get_release_tags(vc)
        return release_tags.get_tags(sr)

    @unittest.skipIf((not ACCESS2INTERNET), "skip testcase need to access internet")
    def test_get_hg_release_tags(self):
        release_tags = self._get_test_tags("hg")
        self.assertEqual(len(release_tags) > 0, True)

    # 当前测试用例中网址无法访问，待后续更新，暂时关闭该单测
    # def test_get_github_release_tags(self):
    #     release_tags = self._get_test_tags("github")
    #     self.assertEqual(len(release_tags) > 0, True)

    @unittest.skipIf((not ACCESS2INTERNET), "skip testcase need to access internet")
    def test_get_git_release_tags(self):
        release_tags = self._get_test_tags("git")
        self.assertEqual(len(release_tags) > 0, True)

    @unittest.skipIf((not ACCESS2INTERNET), "skip testcase need to access internet")
    def test_get_gitlab_gnome_release_tags(self):
        release_tags = self._get_test_tags("gitlab.gnome")
        self.assertEqual(len(release_tags) > 0, True)

    @unittest.skipIf((not ACCESS2INTERNET), "skip testcase need to access internet")
    def test_get_svn_release_tags(self):
        release_tags = self._get_test_tags("svn")
        self.assertEqual(len(release_tags) > 0, True)

    # 当前测试用例中网址无法访问，待后续更新，暂时关闭该单测
    # def test_get_metacpan_release_tags(self):
    #     release_tags = self._get_test_tags("metacpan")
    #     self.assertEqual(len(release_tags) > 0, True)

    @unittest.skipIf((not ACCESS2INTERNET), "skip testcase need to access internet")
    def test_get_pypi_release_tags(self):
        release_tags = self._get_test_tags("pypi")
        self.assertEqual(len(release_tags) > 0, True)

    @unittest.skipIf((not ACCESS2INTERNET), "skip testcase need to access internet")
    def test_get_rubygem_release_tags(self):
        release_tags = self._get_test_tags("rubygem")
        self.assertEqual(len(release_tags) > 0, True)

    @unittest.skipIf((not ACCESS2INTERNET), "skip testcase need to access internet")
    def test_get_gitee_release_tags(self):
        release_tags = self._get_test_tags("gitee")
        self.assertEqual(len(release_tags) > 0, True)

    # 当前测试用例中网址无法访问，待后续更新，暂时关闭该单测
    # def test_get_gnu_ftp_release_tags(self):
    #     release_tags = self._get_test_tags("gnu-ftp")
    #     self.assertEqual(len(release_tags) > 0, True)

if __name__ == '__main__':
    work_dir = os.getcwd()
    _ = not os.path.exists("log") and os.mkdir("log")
    logger_conf_path = os.path.realpath(os.path.join(os.path.dirname(os.path.realpath(__file__)), "../../../../src/conf/logger.conf"))
    logging.config.fileConfig(logger_conf_path)
    logger = logging.getLogger("test_logger")
    # Test get release tags
    suite = unittest.makeSuite(TestGetReleaseTags)
    unittest.TextTestRunner().run(suite)
    os.chdir(work_dir)
    shutil.rmtree("log")



