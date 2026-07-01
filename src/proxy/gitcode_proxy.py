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
# Create: 2025-11-18
# Description: gitcode api proxy
# **********************************************************************************
import logging

from src.proxy.requests_proxy import do_requests, RequestData

logger = logging.getLogger("common")

class GitcodeProxy(object):
    def __init__(self, owner, repo, token):
        self._owner = owner
        self._repo = repo
        self._token = token
        self._base_url = "https://api.gitcode.com"

    def comment_pr(self, pr, comment):
        """
        评论pull request
        :param pr: 本仓库PR的序数
        :param comment: 评论内容
        :return: True成功，False失败
        """
        url = "{burl}/api/v5/repos/{owner}/{repo}/pulls/{number}/comments?access_token={token}".format(
            burl=self._base_url,
            owner=self._owner,
            repo=self._repo,
            number=pr,
            token=self._token
        )
        data = {
            "body": comment
        }
        rs = do_requests("post", url, RequestData(body=data, timeout=10))
        if rs != 0:
            logger.warning("comment pull request failed")
            return False
        return True

    def handle_tags_of_pr(self, oper, pr, *tags):
        """
        处理pr tag
        :param oper: http请求操作，post/put/delete
        :param pr: 本仓库PR的序数
        :param tags: 标签
        :return: True成功，False失败
        """
        url = "{burl}/api/v5/repos/{owner}/{repo}/pulls/{number}/labels".format(
            burl=self._base_url,
            owner=self._owner,
            repo=self._repo,
            number=pr
        )
        if oper == "DELETE":
            url = url + "/{}?access_token={}".format(tags[0], self._token)
            rs = do_requests("delete", url, RequestData(timeout=10))
        else:
            url = url + "?access_token={}".format(self._token)
            rs = do_requests(oper.lower(), url, RequestData(body=list(tags), timeout=10))
        if rs != 0:
            logger.warning("{oper} tags:{tags} failed".format(oper=oper, tags=tags))
            return False
        return True

    def create_tags_of_pr(self, pr, *tags):
        """
        创建pr tag
        :param pr: 本仓库PR的序数
        :param tags: 标签
        :return: True成功，False失败
        """
        return self.handle_tags_of_pr("POST", pr, *tags)

    def replace_all_tags_of_pr(self, pr, *tags):
        """
        替换所有pr tag
        :param pr: 本仓库PR的序数
        :param tags: 标签
        :return: True成功，False失败
        """
        return self.handle_tags_of_pr("PUT", pr, *tags)

    def delete_tag_of_pr(self, pr, tag):
        """
        删除pr tag
        :param pr: 本仓库PR的序数
        :param tag: 标签
        :return: True成功，False失败
        """
        return self.handle_tags_of_pr("DELETE", pr, tag)

    def get_last_pr_committer(self, branch, state="merged"):
        """
        获取指定分支的最后一个pr的提交者
        :param branch: pr合入分支
        :param state: pr状态
        :return: str or None
        """
        url = "{burl}/api/v5/repos/{owner}/{repo}/pulls".format(
            burl=self._base_url,
            owner=self._owner,
            repo=self._repo,
        )
        querystring = {
            "access_token": self._token,
            "state": state,
            "base": branch
        }
        pr_list = []
        rs = do_requests("get", url, RequestData(querystring=querystring, timeout=10, obj=pr_list))
        if rs != 0:
            logger.warning("get last pr committer failed")
            return None
        if pr_list:
            try:
                committer = pr_list[0]["user"]["login"]
                logger.debug("get last pr committer: %s", committer)
                return committer
            except KeyError:
                logger.exception("extract committer info from gitcode exception")
        return None

    def get_issue(self, cve_issue, enterprises="open_euler"):
        """
        获取企业的某个issue信息
        :param cve_issue: issue编号
        :param enterprises: 企业名称
        :return: 请求response
        """
        resp = {}
        issue_url = "${}/api/v5/enterprises/{}/issues/{}?access_token={}".format(
            self._base_url, enterprises, cve_issue, self._token)

        rs = do_requests("get", issue_url, RequestData(timeout=10, obj=resp))
        if rs != 0:
            logging.warning("get issue failed")
        return resp

    @staticmethod
    def create_issue(owner, data):
        """
        创建issue
        :param owner: 仓库所属空间地址
        :param data: issue信息（字典格式），需包含如下信息
            {
            "title": issue标题,
            "repo": 仓库路径,
            "body": issue描述,
            "access_token": 用户token
            }
        :return: 请求response
        """
        resp = {}
        issue_url = "https://api.gitcode.com/api/v5/repos/{}/issues".format(owner)

        rs = do_requests("post", issue_url, RequestData(body=data, timeout=10, obj=resp))
        if rs != 0:
            logging.warning("create issue failed")
        return resp

    @staticmethod
    def update_issue(owner, data, number):
        """
        更新issue
        :param owner: 仓库所属空间地址
        :param data: issue信息（字典格式），需包含如下信息
            {
            "title": issue标题,
            "repo": 仓库路径,
            "body": issue描述,
            "access_token": 用户token
            }
        :param number: issue编号，不带#号
        :return: 请求response
        """
        resp = {}
        issue_url = "https://api.gitcode.com/api/v5/repos/{}/issues/{}".format(owner, number)

        rs = do_requests("patch", issue_url, RequestData(body=data, timeout=10, obj=resp))
        if rs != 0:
            logging.warning("update issue failed")
        return resp

    def get_all_issues_data(self):
        """
        获取仓库下所有issue信息
        :return: issues response list
        """
        pr_url = "{burl}/api/v5/repos/{owner}/{repo}/issues?access_token={token}".format(
            burl=self._base_url,
            owner=self._owner,
            repo=self._repo,
            token=self._token
        )
        issues_info = []

        rs = do_requests("get", pr_url, RequestData(timeout=10, obj=issues_info))
        if rs != 0:
            logger.warning("get issue num info failed")

        return issues_info

    def get_pr_info(self, pr_id):
        """
        获取指定pr的提交分支及其它信息
        :param pr_id: pr id
        :return: 请求response.
        """
        pr_url = "{burl}/api/v5/repos/{owner}/{repo}/pulls/{pr}?access_token={token}".format(
            burl=self._base_url,
            owner=self._owner,
            repo=self._repo,
            pr=pr_id,
            token=self._token
        )
        pr_info = {}
        rs = do_requests("get", pr_url, RequestData(timeout=10, obj=pr_info))
        if rs != 0:
            logger.warning(f"get pr info {self._repo} {pr_id} failed")

        return pr_info

    def get_pr_files(self, pr_id):
        """
        获取指定 PR 的所有变更文件列表
        :param pr_id: pr id
        :return: list of dict, 每个元素包含 filename、status 等字段
        """
        pr_url = "{burl}/api/v5/repos/{owner}/{repo}/pulls/{pr}/files?access_token={token}".format(
            burl=self._base_url,
            owner=self._owner,
            repo=self._repo,
            pr=pr_id,
            token=self._token
        )

        file_list = []
        rs = do_requests("get", pr_url, RequestData(timeout=10, obj=file_list))
        if rs != 0:
            logger.warning("get pr files %s %s failed", self._repo, pr_id)
            return None

        return file_list

    def get_milestone_id(self):
        """
        查询仓库所有里程碑
        :return: milestone id info list
        """
        pr_url = "{burl}/api/v5/repos/{owner}/{repo}/milestones?access_token={token}".format(
            burl=self._base_url,
            owner=self._owner,
            repo=self._repo,
            token=self._token
        )
        milestones_info = []
        rs = do_requests("get", pr_url, RequestData(timeout=10, obj=milestones_info))
        if rs != 0:
            logger.warning("get milestone id info failed")

        return milestones_info
