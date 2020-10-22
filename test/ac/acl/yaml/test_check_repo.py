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
# Description: test for check_repo.py
# ***********************************************************************************/
"""

import unittest
import mock
import os
import yaml
import logging.config
import logging
import shutil

from src.ac.acl.yaml.check_repo import ReleaseTagsFactory

logging.getLogger('test_logger')

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
            logging.warning("package yaml not exist. {}".format(str(e)))
        except yaml.YAMLError as exc:
            logging.warning("Error parsering YAML: {}".format(str(exc)))
        finally:
            return result

    def _get_test_tags(self, version):
        yaml_content = self._load_yaml(self.TEST_YAML_DIR[version])
        vc = yaml_content.get("version_control", "")
        sr = yaml_content.get("src_repo", "")
        release_tags = ReleaseTagsFactory.get_release_tags(vc)
        return release_tags.get_tags(sr)

    def test_get_hg_release_tags(self):
        release_tags = self._get_test_tags("hg")
        self.assertEqual(len(release_tags) > 0, True)

    def test_get_github_release_tags(self):
        release_tags = self._get_test_tags("github")
        self.assertEqual(len(release_tags) > 0, True)

    def test_get_git_release_tags(self):
        release_tags = self._get_test_tags("git")
        self.assertEqual(len(release_tags) > 0, True)

    def test_get_gitlab_gnome_release_tags(self):
        release_tags = self._get_test_tags("gitlab.gnome")
        self.assertEqual(len(release_tags) > 0, True)
    
    def test_get_svn_release_tags(self):
        release_tags = self._get_test_tags("svn")
        self.assertEqual(len(release_tags) > 0, True)

    def test_get_metacpan_release_tags(self):
        release_tags = self._get_test_tags("metacpan")
        self.assertEqual(len(release_tags) > 0, True)

    def test_get_pypi_release_tags(self):
        release_tags = self._get_test_tags("pypi")
        self.assertEqual(len(release_tags) > 0, True)

    def test_get_rubygem_release_tags(self):
        release_tags = self._get_test_tags("rubygem")
        self.assertEqual(len(release_tags) > 0, True)

    def test_get_gitee_release_tags(self):
        release_tags = self._get_test_tags("gitee")
        self.assertEqual(len(release_tags) > 0, True)

    def test_get_gnu_ftp_release_tags(self):
        release_tags = self._get_test_tags("gnu-ftp")
        self.assertEqual(len(release_tags) > 0, True)

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



