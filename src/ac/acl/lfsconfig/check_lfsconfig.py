import configparser
import logging
import os

from src.ac.framework.ac_base import BaseCheck
from src.ac.framework.ac_result import EXCLUDE, FAILED, SUCCESS
from src.proxy.git_proxy import GitProxy

logger = logging.getLogger("ac")


class CheckLfsconfig(BaseCheck):
    """
    check .lfsconfig file in PR diff
    """

    def __init__(self, workspace, repo, conf=None):
        super(CheckLfsconfig, self).__init__(workspace, repo, conf)
        self._gp = GitProxy(self._work_dir)

    def __call__(self, *args, **kwargs):
        logger.info("check %s .lfsconfig ...", self._repo)

        diff_files = self._gp.diff_files_between_commits("HEAD~1", "HEAD~0")
        if ".lfsconfig" not in diff_files:
            logger.info(".lfsconfig not in PR diff, skip check")
            return EXCLUDE

        logger.info(".lfsconfig found in PR diff, checking url ...")
        return self.start_check_with_order("lfsconfig")

    def check_lfsconfig(self):
        lfsconfig_path = os.path.join(self._work_dir, ".lfsconfig")
        expected_url = "https://artlfs.openeuler.openatom.cn/src-openEuler/%s" % self._repo

        config = configparser.ConfigParser()
        try:
            config.read(lfsconfig_path)
            url = config.get("lfs", "url", fallback=None)
        except (configparser.Error, KeyError) as e:
            logger.error("parse .lfsconfig failed: %s", e)
            logger.error("expected url: %s", expected_url)
            return FAILED

        if not url:
            logger.error("lfs.url not found in .lfsconfig")
            logger.error("expected url: %s", expected_url)
            return FAILED

        url = url.strip()
        if url == expected_url:
            logger.info(".lfsconfig url is correct: %s", url)
            return SUCCESS

        logger.error(".lfsconfig url is incorrect: %s", url)
        logger.error("expected url: %s", expected_url)
        logger.info(
            "please refer to https://gitcode.com/openeuler/community/blob/master/zh/contributors/git-lfs.md for fix"
        )
        return FAILED