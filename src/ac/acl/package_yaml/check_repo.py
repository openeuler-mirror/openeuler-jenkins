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
# Create: 2020-09-22
# Description: check yaml file in software package
# ***********************************************************************************/
"""
#  \   /  /|     /|   /|     /
#   \ /  /_|    / |  / |    /
#    /  /  |   /  | /  |   /
#   /  /   |  /   |/   |  /_____

import logging
import re
import urllib.parse as urlparse
import requests
import json
import subprocess
import tldextract
import abc

logging.getLogger("ac")


class AbsReleaseTags(object):
    """
    获取release tags的抽象类
    """

    __metaclass__ = abc.ABCMeta
    def __init__(self, version_control):
        self.version_control = version_control
    
    @abc.abstractmethod
    def url(self, repo):
        """
        抽象方法
        """
        pass
    
    @abc.abstractmethod
    def get_tags(self, repo):
        """
        抽象方法
        """
        pass


class DefaultReleaseTags(AbsReleaseTags):
    """
    获取release tags的基类
    """
    def url(self, repo):
        """
        通过src_repo生成url
        return: str
        """
        return ""
    
    def get_tags(self, repo):
        """
        通过url获取上游社区的release tags
        return: list
        """
        logging.info("unsupported version control: {}".format(self.version_control))
        return []


class HttpReleaseTagsMixin(object):
    """
    通过web请求形式获取release tags
    """
    DEFAULT_REQ_HEADER = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64)'
    }

    def get_redirect_resp(self, url, response):
        """
        获取重定向的url和cookie
        return: bool, str, list
        """
        cookie = set()
        href = ""
        need_redirect = False
        for line in response.text.splitlines():
            line = line.strip()
            if line.startswith("Redirecting"):
                logging.debug("Redirecting with document.cookie")
                need_redirect = True
            search_result = re.search(r"document\.cookie=\"(.*)\";", line)
            if search_result:
                cookie = cookie | set(search_result.group(1).split(';'))
            search_result = re.search(r"document\.location\.href=\"(.*)\";", line)
            if search_result:
                href = search_result.group(1)
        new_url = urlparse.urljoin(url, href)
        if "" in cookie:
            cookie.remove("")
        return need_redirect, new_url, list(cookie)

    def get_request_response(self, url, timeout=30, headers=None):
        """
        获取url请求获取response
        return: reponse
        """
        headers = self.DEFAULT_REQ_HEADER if headers is None else headers
        try:
            response = requests.get(url, headers=headers, timeout=timeout)
            need_redirect, new_url, cookies = self.get_redirect_resp(url, response)
            if tldextract.extract(url).domain != tldextract.extract(new_url).domain: # 判断域名是否一致 预防csrf攻击
                logging.warning("domain of redirection link is different: {}".format(new_url))
                return ""
            if need_redirect:
                cookie_dict = {}
                for cookie in cookies:
                    key, val = cookie.split("=")
                    cookie_dict[key] = val
                url = new_url
                response = requests.get(url, headers=headers, cookies=cookie_dict, timeout=timeout)
        except requests.exceptions.SSLError as e:
            logging.warning("requests {} ssl exception, {}".format(url, e))
            return ""
        except requests.exceptions.Timeout as e:
            logging.warning("requests timeout")
            return ""
        except requests.exceptions.RequestException as e:
            logging.warning("requests exception, {}".format(e))
            return ""
        return response


class HgReleaseTags(AbsReleaseTags, HttpReleaseTagsMixin):
    """
    获取hg上游社区release tags
    """
    def url(self, repo):
        """
        通过src_repo生成url
        return: str
        """
        return urlparse.urljoin(repo + "/", "json-tags") if repo else ""

    def get_tags(self, repo):
        """
        通过url获取上游社区的release tags
        return: list
        """
        url = self.url(repo)
        logging.debug("{repo} : get {vc} tags".format(repo=url, vc=self.version_control))
        if not url:
            logging.warning("illegal url: \"\"")
            return []
        response = self.get_request_response(url)
        if not response:
            logging.warning("unable to get response:")
            return []
        try:
            tags_json = json.loads(response.text)
            temp_tags = tags_json.get("tags")
            temp_tags.sort(reverse=True, key=lambda x: x["date"][0])
            release_tags = [tag["tag"] for tag in temp_tags]
        except Exception as e:
            logging.error("exception, {}".format(e))
            return []
        return release_tags


class HgRawReleaseTags(AbsReleaseTags, HttpReleaseTagsMixin):
    """
    获取hg raw上游社区release tags
    """
    def url(self, repo):
        """
        通过src_repo生成url
        return: str
        """
        return urlparse.urljoin(repo + "/", "raw-tags") if repo else ""

    def get_tags(self, repo):
        """
        通过url获取上游社区的release tags
        return: list
        """
        url = self.url(repo)
        logging.debug("{repo} : get {vc} tags".format(repo=url, vc=self.version_control))
        if not url:
            logging.warning("illegal url: \"\"")
            return []
        response = self.get_request_response(url)
        release_tags = []
        for line in response.text.splitlines():
            release_tags.append(line.split()[0])
        return release_tags


class MetacpanReleaseTags(AbsReleaseTags, HttpReleaseTagsMixin):
    """
    获取metacpan上游社区release tags
    """
    def url(self, repo):
        """
        通过src_repo生成url
        return: str
        """
        return urlparse.urljoin("https://metacpan.org/release/", repo) if repo else ""

    def get_tags(self, repo):
        """
        通过url获取上游社区的release tags
        return: list
        """
        url = self.url(repo)
        logging.debug("{repo} : get {vc} tags".format(repo=url, vc=self.version_control))
        if not url:
            logging.warning("illegal url: \"\"")
            return []
        response = self.get_request_response(url)
        if not response:
            return []
        resp_lines = response.text.splitlines()
        release_tags = []
        tag_condition = "value=\"/release"
        for index in range(len(resp_lines) - 1):
            if tag_condition in resp_lines[index]:
                tag = resp_lines[index + 1]
                index += 1
                if "DEV" in tag:
                    continue
                tag = tag.strip()
                release_tags.append(tag)
        return release_tags


class PypiReleaseTags(AbsReleaseTags, HttpReleaseTagsMixin):
    """
    获取pypi上游社区release tags
    """
    def url(self, repo):
        """
        通过src_repo生成url
        return: str
        """
        return urlparse.urljoin("https://pypi.org/pypi/", repo + "/json") if repo else ""

    def get_tags(self, repo):
        """
        通过url获取上游社区的release tags
        return: list
        """
        url = self.url(repo)
        logging.debug("{repo} : get {vc} tags".format(repo=url, vc=self.version_control))
        if not url:
            logging.warning("illegal url: \"\"")
            return []
        response = self.get_request_response(url)
        try:
            tags_json = response.json()
            release_tags = [tag for tag in tags_json.get("releases")]
        except Exception as e:
            logging.error("exception, {}".format(e))
            return []
        return release_tags


class RubygemReleaseTags(AbsReleaseTags, HttpReleaseTagsMixin):
    """
    获取rubygem上游社区release tags
    """
    def url(self, repo):
        """
        通过src_repo生成url
        return: str
        """
        return urlparse.urljoin("https://rubygems.org/api/v1/versions/", repo + ".json") if repo else ""

    def get_tags(self, repo):
        """
        通过url获取上游社区的release tags
        return: list
        """
        url = self.url(repo)
        logging.debug("{repo} : get {vc} tags".format(repo=url, vc=self.version_control))
        if not url:
            logging.warning("illegal url: \"\"")
            return []
        response = self.get_request_response(url)
        try:
            tags_json = response.json()
            release_tags = []
            for element in tags_json:
                if element.get("number"):
                    release_tags.append(element.get("number"))
        except Exception as e:
            logging.error("exception, {}".format(e))
            return []
        return release_tags


class GnuftpReleaseTags(AbsReleaseTags, HttpReleaseTagsMixin):
    """
    获取gnu-ftp上游社区release tags
    """
    def url(self, repo):
        """
        通过src_repo生成url
        return: str
        """
        return urlparse.urljoin("https://ftp.gnu.org/gnu/", repo) if repo else ""

    def get_tags(self, repo):
        """
        通过url获取上游社区的release tags
        return: list
        """
        url = self.url(repo)
        logging.debug("{repo} : get {vc} tags".format(repo=url, vc=self.version_control))
        if not url:
            logging.warning("illegal url: \"\"")
            return []
        response = self.get_request_response(url)
        pattern = re.compile("href=\"(.*)\">(.*)</a>")
        release_tags = []
        if not response:
            return []
        for line in response.text.splitlines():
            search_result = pattern.search(line)
            if search_result:
                release_tags.append(search_result.group(1)) # python2用法 python3不同
        return release_tags


class FtpReleaseTags(AbsReleaseTags, HttpReleaseTagsMixin):
    """
    获取ftp上游社区release tags
    """
    def url(self, repo):
        """
        通过src_repo生成url
        return: str
        """
        return urlparse.urljoin('ftp', repo + "/") if repo else ""

    def get_tags(self, repo):
        """
        通过url获取上游社区的release tags
        return: list
        """
        url = self.url(repo)
        logging.debug("{repo} : get {vc} tags".format(repo=url, vc=self.version_control))
        if not url:
            logging.warning("illegal url: \"\"")
            return []
        response = self.get_request_response(url)
        pattern = re.compile("href=\"(.*)\">(.*)</a>")
        release_tags = []
        for line in response.text.splitlines():
            search_result = pattern.search(line)
            if search_result:
                release_tags.append(search_result.group(1)) # python2用法 python3不同
        return release_tags


class CmdReleaseTagsMixin(object):
    """
    通过shell命令获取上游社区的release tags
    """
    def get_cmd_response(self, cmd_list):
        """
        获取shell命令的reponse
        return: reponse
        """
        sub_proc = subprocess.Popen(cmd_list, stdout=subprocess.PIPE)
        response = sub_proc.stdout.read().decode("utf-8")
        if sub_proc.wait():
            logging.warning("{cmd} > encount errors".format(cmd=" ".join(cmd_list)))
        return response


class SvnReleaseTags(AbsReleaseTags, CmdReleaseTagsMixin):
    """
    通过shell svn命令获取上游社区的release tags
    """
    def url(self, repo):
        """
        通过src_repo生成url
        return: str
        """
        return urlparse.urljoin(repo + "/", "tags") if repo else ""
    
    def get_response(self, url):
        """
        生成svn命令并获取reponse
        return: response
        """
        cmd_list = ["/usr/bin/svn", "ls", "-v", url]
        return self.get_cmd_response(cmd_list)

    def get_tags(self, repo):
        """
        通过shell cmd访问远端获取上游社区的release tags
        return: list
        """
        url = self.url(repo)
        logging.debug("{repo} : get svn tags".format(repo=url))
        if not url:
            logging.warning("illegal url: \"\"")
            return []
        response = self.get_response(url)
        release_tags = []
        for line in response.splitlines():
            for item in line.split():
                if item and item[-1] == "/":
                    release_tags.append(item[:-1])
                    break
        return release_tags


class GitReleaseTags(AbsReleaseTags, CmdReleaseTagsMixin):
    """
    通过shell git命令获取上游社区的release tags
    """
    def url(self, repo):
        """
        通过src_repo生成url
        return: str
        """
        return repo
    
    def get_response(self, url):
        """
        生成git命令并获取reponse
        return: response
        """
        cmd_list = ["git", "ls-remote", "--tags", url]
        return self.get_cmd_response(cmd_list)

    def trans_reponse_tags(self, reponse):
        """
        解析git命令返回值为纯数字形式的tag
        return: list
        """
        release_tags = []
        pattern = re.compile(r"^([^ \t]*)[ \t]*refs\/tags\/([^ \t]*)")
        for line in reponse.splitlines():
            match_result = pattern.match(line)
            if match_result:
                tag = match_result.group(2)
                if not tag.endswith("^{}"):
                    release_tags.append(tag)
        return release_tags

    def get_tags(self, repo):
        """
        通过shell cmd访问远端获取上游社区的release tags
        return: list
        """
        url = self.url(repo)
        logging.debug("{repo} : get {vc} tags".format(repo=url, vc=self.version_control))
        if not url:
            logging.warning("illegal url: \"\"")
            return []
        response = self.get_response(url)
        return self.trans_reponse_tags(response)


class GithubReleaseTags(GitReleaseTags):
    """
    获取github上游社区release tags
    """
    def url(self, repo):
        """
        通过src_repo生成url
        return: str
        """
        return urlparse.urljoin("https://github.com/", repo + ".git") if repo else ""


class GiteeReleaseTags(GitReleaseTags):
    """
    获取gitee上游社区release tags
    """
    def url(self, repo):
        """
        通过src_repo生成url
        return: str
        """
        return urlparse.urljoin("https://gitee.com/", repo) if repo else ""


class GitlabReleaseTags(GitReleaseTags):
    """
    获取gitlab.gnome上游社区release tags
    """
    def url(self, repo):
        """
        通过src_repo生成url
        return: str
        """
        if not repo:
            return ""
        src_repos = repo.split("/")
        if len(src_repos) == 1:
            return urlparse.urljoin("https://gitlab.gnome.org/GNOME/", repo + ".git")
        else:
            return urlparse.urljoin("https://gitlab.gnome.org/", repo + ".git")


class ReleaseTagsFactory(object):
    """
    ReleaseTags及其子类的工厂类
    """
    VERSION_CTRL_GETTER_MAPPING = {
        "hg": HgReleaseTags,
        "hg-raw": HgRawReleaseTags,
        "github": GithubReleaseTags,
        "git": GitReleaseTags,
        "gitlab.gnome": GitlabReleaseTags,
        "svn": SvnReleaseTags,
        "metacpan": MetacpanReleaseTags,
        "pypi": PypiReleaseTags,
        "rubygem": RubygemReleaseTags,
        "gitee": GiteeReleaseTags,
        "gnu-ftp": GnuftpReleaseTags,
        "ftp": FtpReleaseTags
    }
    
    @staticmethod
    def get_release_tags(version_control):
        """
        通过version control返回对应的ReleaseTags的子类
        return: class
        """
        release_tags = ReleaseTagsFactory.VERSION_CTRL_GETTER_MAPPING.get(version_control, DefaultReleaseTags)
        return release_tags(version_control)
