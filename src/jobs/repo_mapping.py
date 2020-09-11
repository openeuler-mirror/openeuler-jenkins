# -*- coding: utf-8 -*-
import logging.config
import logging
import os
import argparse
from abc import ABCMeta, abstractmethod

import yaml


class RepoMapping(object):
    __metaclass__ = ABCMeta

    def __init__(self, ignored_repos_path, ignored_repos_key, community_path, *repos):
        """
        :param ignored_repos_path: 忽略的repo配置文件
        :param key:
        :param repos: 用户输入的仓库
        """
        self._input_repos = repos
        self._repo_mapping = {}   # 保存结果
        self._ignored_repos = self._load_ignore_repo(ignored_repos_path, ignored_repos_key)
        logger.debug("ignored repos: {}".format(self._ignored_repos))
        self._community_repos = self._load_community_repo(community_path)    # 社区repos
        logger.debug("community repos: {}".format(self._community_repos))

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
            logger.warning("{} not exist".format(conf_file))
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
                logger.info("repos from community: {}".format(len(repos)))
                return repos
        except IOError as e:
            logger.warning("{} not exist".format(community_path))
            return []

    def _is_valid_repo(self, repo):
        """
        仓库是否需要创建门禁
        :param repo:
        :return:
        """
        if repo in self._community_repos and repo not in self._ignored_repos:
            return True

        return False

    @abstractmethod
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
    def __init__(self, ignored_repos_path, community_path, *repos):
        super(OERepoMapping, self).__init__(ignored_repos_path, "openeuler",
                                            os.path.join(community_path, "repository/openeuler.yaml"), *repos)

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
    def __init__(self, ignored_repos_path, community_path, *repos):
        super(SOERepoMapping, self).__init__(ignored_repos_path, "src-openeuler",
                                             os.path.join(community_path, "repository/src-openeuler.yaml"), *repos)

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
    args.add_argument("-j", type=str, dest="jobs", help="jobs name, split by dot")
    args.add_argument("-o", type=str, dest="mapping_file", help="output file to save buddy info")
    args.add_argument("-m", type=str, dest="obs_meta_path", help="obs meta path")
    args.add_argument("-c", type=str, dest="community_path", help="community repo path")
    args = args.parse_args()

    _ = not os.path.exists("log") and os.mkdir("log")
    logger_conf_path = os.path.realpath(os.path.join(os.path.dirname(os.path.realpath(__file__)), "../conf/logger.conf"))
    logging.config.fileConfig(logger_conf_path)
    logger = logging.getLogger("jobs")

    # import after log initial
    from src.jobs.obs_meta_strategy import ObsMetaStrategy

    ignore_repo_path = os.path.realpath(os.path.join(os.path.realpath(__file__), "../../conf/ignore_repo.yaml"))
    input_repos = [repo.strip() for repo in args.jobs.split(",")]

    if args.community == "src-openeuler":
        rm = SOERepoMapping(ignore_repo_path, args.community_path, *input_repos)
        rm.mapping(ObsMetaStrategy(args.obs_meta_path))
    else:
        rm = OERepoMapping(ignore_repo_path, args.community_path, *input_repos)
        rm.mapping(None)
    rm.save(args.mapping_file)
