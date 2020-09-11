# -*- encoding=utf-8 -*-
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
        logger.debug("comment pull request {}".format(pr))
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

        logger.debug("create tags {} of pull request {}".format(tags, pr))
        pr_tag_url = "https://gitee.com/api/v5/repos/{}/{}/pulls/{}/labels?access_token={}".format(
                self._owner, self._repo, pr, self._token)

        rs = do_requests("post", pr_tag_url, body=list(tags), timeout=10)

        if rs != 0:
            logger.warning("create tags failed")
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

        logger.debug("replace all tags with {} of pull request {}".format(tag, pr))
        pr_tag_url = "https://gitee.com/api/v5/repos/{}/{}/pulls/{}/labels?access_token={}".format(
                self._owner, self._repo, pr, self._token)

        rs = do_requests("put", pr_tag_url, body=list(tags), timeout=10)
        if rs != 0:
            logger.warning("replace tags failed")
            return False

        return True

    def delete_tag_of_pr(self, pr, tag):
        """
        删除pr tag
        :param pr: 本仓库PR的序数
        :param tag: 标签
        :return: 0成功，其它失败
        """
        logger.debug("delete tag {} of pull request {}".format(tag, pr))
        pr_tag_url = "https://gitee.com/api/v5/repos/{}/{}/pulls/{}/labels/{}?access_token={}".format(
                self._owner, self._repo, pr, tag, self._token)

        rs = do_requests("delete", pr_tag_url, timeout=10)

        if rs != 0:
            logger.warning("delete tags failed")
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
            logger.info("repos from community: {}".format(len(repos)))
        
        community_repo_url = "https://gitee.com/openeuler/community/raw/master/repository/src-openeuler.yaml"
        logger.info("requests repos from community, this will take multi seconds")
        do_requests("get", url=community_repo_url, timeout=timeout, obj=analysis)
        
        return repos
