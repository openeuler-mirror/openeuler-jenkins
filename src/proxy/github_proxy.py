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

from src.proxy.requests_proxy import do_requests

logger = logging.getLogger("common")


class GithubProxy(object):
    def __init__(self, owner, repo, token):
        self._owner = owner
        self._repo = repo
        self._token = token
        self._headers = {"Authorization": "Bearer %s" % self._token, "Accept": "application/vnd.github+json", 
                "Content-Type": "application/json"}

    def comment_pr(self, pr, comment):
        """
        评论pull request
        :param pr: 本仓库PR的序数
        :param comment: 评论内容
        :return: 0成功，其它失败
        """
        logger.debug("comment pull request %s", pr)
        comment_pr_url = "https://api.github.com/repos/{}/{}/issues/{}/comments".format(self._owner, self._repo, pr)
        data = {"auth": self._token, "body": comment}

        rs = do_requests("post", comment_pr_url, body=data, timeout=10, headers=self._headers)

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
        pr_tag_url = "https://api.github.com/repos/{}/{}/issues/{}/labels".format(
                self._owner, self._repo, pr)

        rs = do_requests("post", pr_tag_url, body=list(tags), timeout=10, headers=self._headers)

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
        pr_tag_url = "https://api.github.com/repos/{}/{}/issues/{}/label".format(
                self._owner, self._repo, pr)

        rs = do_requests("put", pr_tag_url, body=list(tags), timeout=10, headers=self._headers)
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
        pr_tag_url = "https://api.github.com/repos/{}/{}/issues/{}/labels/{}".format(
                self._owner, self._repo, pr, tag)

        rs = do_requests("delete", pr_tag_url, timeout=10, headers=self._headers)

        if rs != 0:
            logger.warning("delete tags:%s failed", tag)
            return False

        return True

