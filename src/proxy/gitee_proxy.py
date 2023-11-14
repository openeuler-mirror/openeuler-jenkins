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
# Description: gitee api proxy
# **********************************************************************************
import logging

import yaml

from src.proxy.requests_proxy import do_requests

logger = logging.getLogger("common")


class GiteeProxy(object):
    def __init__(self, owner, repo, token):
        self._owner = owner
        self._repo = repo
        self._token = token

    def comment_pr(self, pr, comment):
        """
        评论pull request
        :param pr: 本仓库PR的序数
        :param comment: 评论内容
        :return: 0成功，其它失败
        """
        logger.debug("comment pull request %s", pr)
        comment_pr_url = "https://gitee.com/api/v5/repos/{}/{}/pulls/{}/comments".format(self._owner, self._repo, pr)
        data = {"access_token": self._token, "body": comment}

        rs = do_requests("post", comment_pr_url, body=data, timeout=10)

        if rs != 0:
            logger.warning("comment pull request failed")
            return False

        return True

    def create_tags_of_pr(self, pr, *tags):
        """
        创建pr tag
        :param pr: 本仓库PR的序数
        :param tags: 标签
        :return: 0成功，其它失败
        """
        if not tags:
            logger.debug("create tags, but no tags")
            return True

        logger.debug("create tags %s of pull request %s", tags, pr)
        pr_tag_url = "https://gitee.com/api/v5/repos/{}/{}/pulls/{}/labels?access_token={}".format(
            self._owner, self._repo, pr, self._token)

        rs = do_requests("post", pr_tag_url, body=list(tags), timeout=10)

        if rs != 0:
            logger.warning("create tags:%s failed", tags)
            return False

        return True

    def replace_all_tags_of_pr(self, pr, *tags):
        """
        替换所有pr tag
        :param pr: 本仓库PR的序数
        :param tags: 标签
        :return: 0成功，其它失败
        """
        if not tags:
            logger.debug("replace tags, but no tags")
            return True

        logger.debug("replace all tags with %s of pull request %s", tags, pr)
        pr_tag_url = "https://gitee.com/api/v5/repos/{}/{}/pulls/{}/labels?access_token={}".format(
            self._owner, self._repo, pr, self._token)

        rs = do_requests("put", pr_tag_url, body=list(tags), timeout=10)
        if rs != 0:
            logger.warning("replace tags:%s failed", tags)
            return False

        return True

    def delete_tag_of_pr(self, pr, tag):
        """
        删除pr tag
        :param pr: 本仓库PR的序数
        :param tag: 标签
        :return: 0成功，其它失败
        """
        logger.debug("delete tag %s of pull request %s", tag, pr)
        pr_tag_url = "https://gitee.com/api/v5/repos/{}/{}/pulls/{}/labels/{}?access_token={}".format(
            self._owner, self._repo, pr, tag, self._token)

        rs = do_requests("delete", pr_tag_url, timeout=10)

        if rs != 0:
            logger.warning("delete tags:%s failed", tag)
            return False

        return True

    @staticmethod
    def load_community_repos(timeout=10):
        """
        获取社区repo
        :param timeout:
        :return:
        """
        repos = {}

        def analysis(response):
            """
            requests回调
            :param response: requests response object
            :return:
            """
            handler = yaml.safe_load(response.text)
            repos.update({item["name"]: item["type"] for item in handler["repositories"]})
            logger.info("repos from community: %s", len(repos))

        community_repo_url = "https://gitee.com/openeuler/community/raw/master/repository/src-openeuler.yaml"
        logger.info("requests repos from community, this will take multi seconds")
        do_requests("get", url=community_repo_url, timeout=timeout, obj=analysis)

        return repos

    def get_last_pr_committer(self, branch, state="merged"):
        """
        获取指定分支的最后一个pr的提交者
        :param branch: pr合入分支
        :param state: pr状态
        :return: str or None
        """
        logger.debug("get last pull request committer, branch: %s, state: %s", branch, state)
        pr_url = "https://gitee.com/api/v5/repos/{}/{}/pulls?access_token={}&state={}&base={}" \
                 "&page=1&per_page=1".format(self._owner, self._repo, self._token, state, branch)

        # python2 not have nonlocal
        committer = [None]

        def analysis(response):
            """
            requests回调，解析pr列表
            :param response: requests response object
            :return:
            """
            handler = response.json()

            if handler:
                try:
                    committer[0] = handler[0]["user"]["login"]
                    logger.debug("get last pr committer: %s", committer)
                except KeyError:
                    logger.exception("extract committer info from gitee exception")

        rs = do_requests("get", pr_url, timeout=10, obj=analysis)

        if rs != 0:
            logger.warning("get last pr committer failed")

        return committer[0]

    def get_issue(self, cve_issue, enterprises="open_euler"):
        resp = {}
        issue_url = "https://gitee.com/api/v5/enterprises/{}/issues/{}?access_token={}".format(
            enterprises, cve_issue, self._token)
        logging.info(issue_url)
        rs = do_requests("get", issue_url, timeout=10, obj=resp)

        if rs != 0:
            logging.warning("get issue failed")
        return resp

    @staticmethod
    def create_issue(owner, data):
        resp = {}
        issue_url = "https://gitee.com/api/v5/repos/{}/issues".format(owner)

        rs = do_requests("post", issue_url, body=data, timeout=10, obj=resp)
        if rs != 0:
            logging.warning("create issue failed")
        return resp

    @staticmethod
    def update_issue(owner, data, number):
        resp = {}
        issue_url = "https://gitee.com/api/v5/repos/{}/issues/{}".format(owner, number)

        rs = do_requests("patch", issue_url, body=data, timeout=10, obj=resp)
        if rs != 0:
            logging.warning("update issue failed")
        return resp

    def get_pr_info(self, pr_id):
        """
        获取指定pr的提交分支及其它信息
        :param pr_id: pr id
        :return: response dict.
        """
        logger.debug("get pull request branch and assignee, pr_id: %s", pr_id)
        pr_url = "https://gitee.com/api/v5/repos/{}/{}/pulls/{}?access_token={}".format(self._owner, self._repo, pr_id,
                                                                                        self._token)
        pr_info = {}
        rs = do_requests("get", pr_url, timeout=10, obj=pr_info)
        if rs != 0:
            logger.warning(f"get pr info {self._repo} {pr_id} failed")

        return pr_info

    def get_all_issues_data(self):
        """
        获取仓库下所有issue信息
        :return: issues response list
        """
        pr_url = f"https://gitee.com/api/v5/repos/{self._owner}/{self._repo}/issues?access_token={self._token}"
        issues_info = []

        rs = do_requests("get", pr_url, timeout=10, obj=issues_info)
        if rs != 0:
            logger.warning("get issue num info failed")

        return issues_info

    def get_milestone_id(self):
        """
        查询仓库对应分支的里程碑id
        :return: milestone id info list
        """
        pr_url = f"https://gitee.com/api/v5/repos/{self._owner}/{self._repo}/milestones"
        milestones_info = []
        rs = do_requests("get", pr_url, timeout=10, obj=milestones_info)
        if rs != 0:
            logger.warning("get milestone id info failed")

        return milestones_info
