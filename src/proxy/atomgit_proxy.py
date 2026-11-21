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
# Description: atomgit api proxy
# **********************************************************************************
import logging
import time

from src.proxy.requests_proxy import do_requests, RequestData

logger = logging.getLogger("common")


class AtomgitProxy(object):
    def __init__(self, owner, repo, token):
        self._owner = owner
        self._repo = repo
        self._token = token
        self._base_url = "https://api.atomgit.com"

    def _auth_headers(self):
        return {"Authorization": "Bearer {}".format(self._token)}

    def comment_pr(self, pr, comment):
        """
        评论pull request
        :param pr: 本仓库PR的序数
        :param comment: 评论内容
        :return: True成功，False失败
        """
        url = "{burl}/api/v5/repos/{owner}/{repo}/pulls/{number}/comments".format(
            burl=self._base_url,
            owner=self._owner,
            repo=self._repo,
            number=pr
        )
        data = {
            "body": comment
        }
        rs = do_requests("post", url, RequestData(body=data, timeout=10, headers=self._auth_headers()))
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
            url = url + "/{}".format(tags[0])
            rs = do_requests("delete", url, RequestData(timeout=10, headers=self._auth_headers()))
        else:
            rs = do_requests(oper.lower(), url,
                             RequestData(body=list(tags), timeout=10, headers=self._auth_headers()))
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

    def get_labels_of_pr(self, pr, retries=3):
        """
        获取PR当前标签名列表
        :param pr: 本仓库PR的序数
        :param retries: 请求失败时的最大尝试次数（网络抖动需重试，避免把失败误判为空标签）
        :return: list[str]；重试后仍失败返回 None（调用方应跳过标签增删，以区别于"无标签"）
        """
        url = "{burl}/api/v5/repos/{owner}/{repo}/pulls/{number}/labels".format(
            burl=self._base_url,
            owner=self._owner,
            repo=self._repo,
            number=pr
        )
        for attempt in range(1, retries + 1):
            labels = []
            rs = do_requests(
                "get", url,
                RequestData(timeout=10, obj=labels, headers=self._auth_headers())
            )
            if rs == 0:
                names = []
                for item in labels:
                    if isinstance(item, dict):
                        name = item.get("name") or item.get("title")
                    else:
                        name = item
                    if name:
                        names.append(name)
                return names
            logger.warning("get labels of pr %s failed (attempt %s/%s)", pr, attempt, retries)
            if attempt < retries:
                time.sleep(2)
        return None

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
            "state": state,
            "base": branch
        }
        pr_list = []
        rs = do_requests("get", url, RequestData(querystring=querystring, timeout=10, obj=pr_list,
                                                 headers=self._auth_headers()))
        if rs != 0:
            logger.warning("get last pr committer failed")
            return None
        if pr_list:
            try:
                committer = pr_list[0]["user"]["login"]
                logger.debug("get last pr committer: %s", committer)
                return committer
            except KeyError:
                logger.exception("extract committer info from atomgit exception")
        return None

    def get_issue(self, cve_issue, enterprises="open_euler"):
        """
        获取issue信息；数字编号为仓库级 issue（atomgit 新建），字母编号为企业级（gitee 遗留）
        :param cve_issue: issue编号
        :param enterprises: 企业名称
        :return: 请求response
        """
        resp = {}
        if str(cve_issue).isdigit():
            issue_url = "{}/api/v5/repos/{}/{}/issues/{}".format(
                self._base_url, self._owner, self._repo, cve_issue)
        else:
            issue_url = "{}/api/v5/enterprises/{}/issues/{}".format(
                self._base_url, enterprises, cve_issue)

        rs = do_requests("get", issue_url, RequestData(timeout=10, obj=resp, headers=self._auth_headers()))
        if rs != 0:
            logging.warning("get issue failed")
        return resp

    def create_issue(self, owner, data):
        """
        创建issue
        :param owner: 仓库所属空间地址
        :param data: issue信息（字典格式），需包含 title/repo/body 等字段
        :return: 请求response
        """
        resp = {}
        issue_url = "https://api.atomgit.com/api/v5/repos/{}/issues".format(owner)

        rs = do_requests("post", issue_url, RequestData(body=data, timeout=10, obj=resp,
                                                        headers=self._auth_headers()))
        if rs != 0:
            logging.warning("create issue failed")
        return resp

    def update_issue(self, owner, data, number):
        """
        更新issue
        :param owner: 仓库所属空间地址
        :param data: issue信息（字典格式），需包含 title/repo/body 等字段
        :param number: issue编号，不带#号
        :return: 请求response
        """
        resp = {}
        issue_url = "https://api.atomgit.com/api/v5/repos/{}/issues/{}".format(owner, number)

        rs = do_requests("patch", issue_url, RequestData(body=data, timeout=10, obj=resp,
                                                         headers=self._auth_headers()))
        if rs != 0:
            logging.warning("update issue failed")
        return resp

    def get_all_issues_data(self):
        """
        获取仓库下所有issue信息
        :return: issues response list
        """
        pr_url = "{burl}/api/v5/repos/{owner}/{repo}/issues".format(
            burl=self._base_url,
            owner=self._owner,
            repo=self._repo
        )
        issues_info = []

        rs = do_requests("get", pr_url, RequestData(timeout=10, obj=issues_info, headers=self._auth_headers()))
        if rs != 0:
            logger.warning("get issue num info failed")

        return issues_info

    def get_pr_info(self, pr_id):
        """
        获取指定pr的提交分支及其它信息
        :param pr_id: pr id
        :return: 请求response.
        """
        pr_url = "{burl}/api/v5/repos/{owner}/{repo}/pulls/{pr}".format(
            burl=self._base_url,
            owner=self._owner,
            repo=self._repo,
            pr=pr_id
        )
        pr_info = {}
        rs = do_requests("get", pr_url, RequestData(timeout=10, obj=pr_info, headers=self._auth_headers()))
        if rs != 0:
            logger.warning(f"get pr info {self._repo} {pr_id} failed")

        return pr_info

    def get_pr_files(self, pr_id):
        """
        获取指定 PR 的所有变更文件列表
        :param pr_id: pr id
        :return: list of dict, 每个元素包含 filename、status 等字段
        """
        pr_url = "{burl}/api/v5/repos/{owner}/{repo}/pulls/{pr}/files".format(
            burl=self._base_url,
            owner=self._owner,
            repo=self._repo,
            pr=pr_id
        )

        file_list = []
        rs = do_requests("get", pr_url, RequestData(timeout=10, obj=file_list, headers=self._auth_headers()))
        if rs != 0:
            logger.warning("get pr files %s %s failed", self._repo, pr_id)
            return None

        return file_list

    def get_milestone_id(self):
        """
        查询仓库所有里程碑
        :return: milestone id info list
        """
        pr_url = "{burl}/api/v5/repos/{owner}/{repo}/milestones".format(
            burl=self._base_url,
            owner=self._owner,
            repo=self._repo
        )
        milestones_info = []
        rs = do_requests("get", pr_url, RequestData(timeout=10, obj=milestones_info,
                                                    headers=self._auth_headers()))
        if rs != 0:
            logger.warning("get milestone id info failed")

        return milestones_info
