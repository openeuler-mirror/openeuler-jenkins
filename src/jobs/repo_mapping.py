# -*- coding: utf-8 -*-
"""
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
# Description: cal repo mapping info
# **********************************************************************************
"""

import logging.config
import logging
import os
import argparse
import abc

import yaml


class RepoMapping(object):
    __metaclass__ = abc.ABCMeta

    def __init__(self, ignored_repos_path, ignored_repos_key, community_path, *repos, **kwargs):
        """
        :param ignored_repos_path: 忽略的repo配置文件
        :param key:
        :param repos: 用户输入的仓库
        """
        self._input_repos = repos
        self._exclude_repos = kwargs.get("exclude_jobs") if kwargs.get("exclude_jobs") else []
        self._repo_mapping = {}   # 保存结果
        self._ignored_repos = self._load_ignore_repo(ignored_repos_path, ignored_repos_key)
        logger.debug("ignored repos: %s", self._ignored_repos)
        self._community_repos = self._load_community_repo(community_path)    # 社区repos
        logger.debug("community repos: %s", self._community_repos)

    @staticmethod
    def _load_ignore_repo(conf_file, ignored_repos_key):
        """
        加载不用触发门禁的任务
        :param conf_file:
        :param ignored_repos_key:
        :return:
        """
        try:
            with open(conf_file, "r") as f:
                handler = yaml.safe_load(f)
                return handler.get(ignored_repos_key, [])
        except IOError as e:
            logger.warning("%s not exist", conf_file)
            return []

    @staticmethod
    def _load_community_repo(community_path):
        """
        加载不用触发门禁的任务
        :param community_path:
        :return:
        """
        try:
            with open(community_path, "r") as f:
                handler = yaml.safe_load(f)
                repos = {item["name"]: item["type"] for item in handler["repositories"]}
                logger.info("repos from community: %s", len(repos))
                return repos
        except IOError as e:
            logger.warning("%s not exist", community_path)
            return []

    def _is_valid_repo(self, repo):
        """
        仓库是否需要创建门禁
        :param repo:
        :return:
        """
        if repo in self._community_repos and repo not in self._ignored_repos and repo not in self._exclude_repos:
            return True

        return False

    @abc.abstractmethod
    def mapping(self, strategy):
        """
        计算仓库关联的package及buddy
        :param strategy: 策略对象
        :return:
        """
        raise NotImplementedError

    def save(self, output):
        """
        保存结果
        :param output:
        :return:
        """
        with open(output, "w") as f:
            yaml.safe_dump(self._repo_mapping, f)


class OERepoMapping(RepoMapping):
    """
    openeuler
    """
    def __init__(self, ignored_repos_path, community_path, *repos, **kwargs):
        super(OERepoMapping, self).__init__(ignored_repos_path, "openeuler",
                                            os.path.join(community_path, "repository/openeuler.yaml"), *repos, **kwargs)

    def mapping(self, strategy):
        """

        :param strategy:
        :return:
        """
        repos = self._community_repos if "all" in self._input_repos else self._input_repos
        valid_repos = [repo for repo in repos if self._is_valid_repo(repo)]

        if valid_repos:
            self._repo_mapping = {repo: {"repo": repo} for repo in valid_repos}  # same structure with src-openeuler


class SOERepoMapping(RepoMapping):
    """
    src-openeuler
    """
    def __init__(self, ignored_repos_path, community_path, *repos, **kwargs):
        super(SOERepoMapping, self).__init__(ignored_repos_path, "src-openeuler", 
                os.path.join(community_path, "repository/src-openeuler.yaml"), *repos, **kwargs)

    def mapping(self, strategy):
        """
        计算仓库关联的package及buddy
        :param strategy: 策略对象
        :return:
        """
        repos = self._community_repos if "all" in self._input_repos else self._input_repos
        valid_repos = [repo for repo in repos if self._is_valid_repo(repo)]

        if valid_repos:
            strategy.algorithm(*valid_repos)

            self._repo_mapping = {repo: {"repo": repo, "packages": strategy.get_packages_of_repo(repo),
                                       "buddy": strategy.get_buddy_of_repo(repo)} for repo in strategy}


if "__main__" == __name__:
    args = argparse.ArgumentParser()
    args.add_argument("-f", type=str, dest="community", default="src-openeuler", help="src-openeuler or openeuler")
    #args.add_argument("-j", type=str, dest="jobs", help="jobs name, split by dot")
    args.add_argument("-j", type=str, dest="jobs", nargs="+", help="jobs name")
    args.add_argument("-e", type=str, dest="exclude_jobs", nargs="*", help="exclude jobs name")
    args.add_argument("-o", type=str, dest="mapping_file", help="output file to save buddy info")
    args.add_argument("-m", type=str, dest="obs_meta_path", help="obs meta path")
    args.add_argument("-c", type=str, dest="community_path", help="community repo path")
    args = args.parse_args()

    _ = not os.path.exists("log") and os.mkdir("log")
    logger_conf_path = os.path.realpath(os.path.join(os.path.realpath(__file__), "../../conf/logger.conf"))
    logging.config.fileConfig(logger_conf_path)
    logger = logging.getLogger("jobs")

    # import after log initial
    from src.jobs.obs_meta_strategy import ObsMetaStrategy

    ignore_repo_path = os.path.realpath(os.path.join(os.path.realpath(__file__), "../../conf/ignore_repo.yaml"))

    if args.community == "src-openeuler":
        rm = SOERepoMapping(ignore_repo_path, args.community_path, *args.jobs, exclude_jobs=args.exclude_jobs)
        rm.mapping(ObsMetaStrategy(args.obs_meta_path))
    else:
        rm = OERepoMapping(ignore_repo_path, args.community_path, *args.jobs, exclude_jobs=args.exclude_jobs)
        rm.mapping(None)
    rm.save(args.mapping_file)
