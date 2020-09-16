# -*- coding: utf-8 -*-
import os
import sys
import logging.config
import logging
import json
import yaml
import argparse


class Comment(object):
    """
    comments process
    """
    def __init__(self, pr, jenkins_proxy, *check_abi_comment_files):
        """

        :param pr: pull request number
        """
        self._pr = pr
        self._check_abi_comment_files = check_abi_comment_files
        self._up_builds = []
        self._up_up_builds = []
        self._get_upstream_builds(jenkins_proxy)

    def comment_build(self, gitee_proxy):
        """
        构建结果
        :param jenkins_proxy:
        :param gitee_proxy:
        :return:
        """
        comments = self._comment_build_html_format()
        gitee_proxy.comment_pr(self._pr, "\n".join(comments))

    def comment_at(self, committer, gitee_proxy):
        """
        通知committer
        @committer
        :param committer:
        :param gitee_proxy:
        :return:
        """
        gitee_proxy.comment_pr(self._pr, "@{}".format(committer))

    def check_build_result(self):
        """
        build result check
        :return:
        """
        build_result = sum([ACResult.get_instance(build.get_status()) for build in self._up_builds], SUCCESS)
        return build_result

    def _get_upstream_builds(self, jenkins_proxy):
        """
        get upstream builds
        :param jenkins_proxy:
        :return:
        """
        base_job_name = os.environ.get("JOB_NAME")
        base_build_id = os.environ.get("BUILD_ID")
        base_build_id = int(base_build_id)
        logger.debug("base_job_name: {}, base_build_id: {}".format(base_job_name, base_build_id))
        base_build = jenkins_proxy.get_build(base_job_name, base_build_id)
        logger.debug("get base build")
        self._up_builds = jenkins_proxy.get_upstream_builds(base_build)
        if self._up_builds:
            logger.debug("get up_builds")
            self._up_up_builds = jenkins_proxy.get_upstream_builds(self._up_builds[0])

    def _comment_build_html_format(self):
        """
        组装构建信息，并评论pr
        :param jenkins_proxy: JenkinsProxy object
        :return:
        """
        comments = ["<table>", self._comment_html_table_th()]

        if self._up_up_builds:
            logger.debug("get up_up_builds")
            comments.extend(self._comment_of_ac(self._up_up_builds[0]))
        if self._up_builds:
            comments.extend(self._comment_of_build(self._up_builds))
            comments.extend(self._comment_of_check_abi(self._up_builds))

        comments.append("</table>")
        return comments

    def _comment_of_ac(self, build):
        """
        组装门禁检查结果
        :param build: Jenkins Build object，门禁检查jenkins构建对象
        :return:
        """
        if "ACL" not in os.environ:
            logger.debug("no ac check")
            return []

        try:
            acl = json.loads(os.environ["ACL"])
            logger.debug("ac result: {}".format(acl))
        except ValueError:
            logger.exception("invalid ac result format")
            return []

        comments = []
        try:
            for index, item in enumerate(acl):
                ac_result = ACResult.get_instance(item["result"])
                if index == 0:
                    build_url = build.get_build_url()
                    comments.append(self.__class__._comment_html_table_tr(
                        item["name"], ac_result.emoji, ac_result.hint, 
                        "{}{}".format(build_url, "console"), build.buildno, rowspan=len(acl)))
                else:
                    comments.append(self.__class__._comment_html_table_tr_rowspan(
                        item["name"], ac_result.emoji, ac_result.hint))
        except:
            # jenkins api maybe exception, who knows
            logger.exception("comment of ac result exception")

        logger.info("ac comment: {}".format(comments))

        return comments

    def _comment_of_build(self, builds):
        """
        组装编译任务的评论
        :return:
        """
        comments = []
        try:
            for build in builds:
                name = build.job._data["fullName"]
                status = build.get_status()
                ac_result = ACResult.get_instance(status)
                build_url = build.get_build_url()

                comments.append(self.__class__._comment_html_table_tr(
                    name, ac_result.emoji, ac_result.hint, "{}{}".format(build_url, "console"), build.buildno))
        except:
            # jenkins api maybe exception, who knows
            logger.exception("comment of build exception")

        logger.info("build comment: {}".format(comments))

        return comments

    def _comment_of_check_abi(self, builds):
        """
        check abi comment
        :param builds:
        :return:
        """
        comments = []

        def match(name, comment_file):
            if "aarch64" in name and "aarch64" in comment_file:
                return True
            if "x86-64" in name and "x86_64" in comment_file:
                return True
            return False

        try:
            for check_abi_comment_file in self._check_abi_comment_files:
                logger.debug("check abi comment file: {}".format(check_abi_comment_file))
                if os.path.exists(check_abi_comment_file):      # check abi评论文件存在
                    for build in builds:
                        name = build.job._data["fullName"]
                        logger.debug("check build {}".format(name))
                        if match(name, check_abi_comment_file):     # 找到匹配的jenkins build
                            logger.debug("build \"{}\" match".format(name))
                            status = build.get_status()
                            logger.debug("build state: {}".format(status))
                            if ACResult.get_instance(status) == SUCCESS:    # 保证build状态成功
                                with open(check_abi_comment_file, "r") as f:
                                    content = yaml.safe_load(f)
                                    logger.debug("comment: {}".format(content))
                                    for item in content:
                                        ac_result = ACResult.get_instance(item.get("result"))
                                        comments.append(self.__class__._comment_html_table_tr(
                                            item.get("name"), ac_result.emoji, ac_result.hint, item.get("link", ""),
                                            "markdown" if "link" in item else "", hashtag=False))
                            break
        except:
            # jenkins api or yaml maybe exception, who knows
            logger.exception("comment of build exception")

        logger.info("check abi comment: {}".format(comments))

        return comments

    @classmethod
    def _comment_html_table_th(cls):
        return "<tr><th>Check Name</th> <th>Build Result</th> <th>Build Details</th></tr>"

    @classmethod
    def _comment_html_table_tr(cls, name, icon, status, href, build_no, hashtag=True, rowspan=1):
        return "<tr><td>{}</td> <td>{}<strong>{}</strong></td> <td rowspan={}><a href={}>{}{}</a></td></tr>".format(
            name, icon, status, rowspan, href, "#" if hashtag else "", build_no)

    @classmethod
    def _comment_html_table_tr_rowspan(cls, name, icon, status):
        return "<tr><td>{}</td> <td>{}<strong>{}</strong></td></tr>".format(name, icon, status)


if "__main__" == __name__:
    args = argparse.ArgumentParser()
    args.add_argument("-p", type=int, dest="pr", help="pull request number")
    args.add_argument("-c", type=str, dest="committer", help="commiter")
    args.add_argument("-o", type=str, dest="owner", help="gitee owner")
    args.add_argument("-r", type=str, dest="repo", help="repo name")
    args.add_argument("-t", type=str, dest="gitee_token", help="gitee api token")

    args.add_argument("-b", type=str, dest="jenkins_base_url", help="jenkins base url")
    args.add_argument("-u", type=str, dest="jenkins_user", help="repo name")
    args.add_argument("-j", type=str, dest="jenkins_api_token", help="jenkins api token")

    args.add_argument("-a", type=str, dest="check_abi_comment_files", nargs="*", help="check abi comment files")

    args.add_argument("--disable", dest="enable", default=True, action="store_false", help="comment to gitee switch")

    args = args.parse_args()

    if not args.enable:
        sys.exit(0)

    _ = not os.path.exists("log") and os.mkdir("log")
    logger_conf_path = os.path.realpath(os.path.join(os.path.realpath(__file__), "../../conf/logger.conf"))
    logging.config.fileConfig(logger_conf_path)
    logger = logging.getLogger("build")

    from src.ac.framework.ac_result import ACResult, SUCCESS
    from src.proxy.gitee_proxy import GiteeProxy
    from src.proxy.jenkins_proxy import JenkinsProxy

    # gitee notify
    gp = GiteeProxy(args.owner, args.repo, args.gitee_token)
    gp.delete_tag_of_pr(args.pr, "ci_processing")


    jp = JenkinsProxy(args.jenkins_base_url, args.jenkins_user, args.jenkins_api_token)

    if args.check_abi_comment_files:
        comment = Comment(args.pr, jp, *args.check_abi_comment_files)
    else:
        comment = Comment(args.pr, jp)
    logger.info("comment: build result......")
    comment.comment_build(gp)
    
    if comment.check_build_result() == SUCCESS:
        gp.create_tags_of_pr(args.pr, "ci_success")
    else:
        gp.create_tags_of_pr(args.pr, "ci_fail")
    logger.info("comment: at committer......")
    comment.comment_at(args.committer, gp)
