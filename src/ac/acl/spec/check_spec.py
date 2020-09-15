# -*- encoding=utf-8 -*-
import logging
import time

import yaml

from src.proxy.git_proxy import GitProxy
from src.proxy.requests_proxy import do_requests
from src.ac.framework.ac_result import FAILED, SUCCESS
from src.ac.framework.ac_base import BaseCheck
from src.ac.common.rpm_spec_adapter import RPMSpecAdapter
from src.ac.common.gitee_repo import GiteeRepo

logger = logging.getLogger("ac")


class CheckSpec(BaseCheck):
    """
    check spec file
    """
    def __init__(self, workspace, repo, conf=None):
        super(CheckSpec, self).__init__(workspace, repo, conf)

        self._gp = GitProxy(self._work_dir)
        self._gr = GiteeRepo(self._repo, self._work_dir, None)  # don't care about decompress
        fp = self._gp.get_content_of_file_with_commit(self._gr.spec_file)
        self._spec = RPMSpecAdapter(fp)
        self._latest_commit = self._gp.commit_id_of_reverse_head_index(0)

    def _only_change_package_yaml(self):
        """
        如果本次提交只变更yaml，则无需检查version
        :return: boolean
        """
        diff_files = self._gp.diff_files_between_commits("HEAD~1", "HEAD~0")
        package_yaml = "{}.yaml".format(self._repo)     # package yaml file name

        if len(diff_files) == 1 and diff_files[0] == package_yaml:
            logger.debug("diff files: {}".format(diff_files))
            return True

        return False

    def check_version(self):
        """
        检查当前版本号是否比上一个commit新
        :return:
        """
        # need check version？
        if self._only_change_package_yaml():
            logger.debug("only change package yaml")
            return SUCCESS

        self._gp.checkout_to_commit("HEAD~1")
        try:
            gr = GiteeRepo(self._repo, self._work_dir, None)    # don't care about decompress
            fp = self._gp.get_content_of_file_with_commit(gr.spec_file)
            if fp is None:
                # last commit has no spec file 
                return SUCCESS
            spec_o = RPMSpecAdapter(fp)
        finally:
            self._gp.checkout_to_commit(self._latest_commit)   # recover whatever

        self._ex_pkgship(spec_o)

        if self._spec > spec_o:
            return SUCCESS
        elif self._spec < spec_o:
            if self._gp.is_revert_commit(depth=5):  # revert, version back, ignore
                logger.debug("revert commit")
                return SUCCESS

        logger.error("current version: {}-r{}, last version: {}-r{}".format(
            self._spec.version, self._spec.release, spec_o.version, spec_o.release))
        return FAILED

    def check_homepage(self, timeout=30, retrying=3, interval=1):
        """
        检查主页是否可访问
        :param timeout: 超时时间
        :param retrying: 重试次数
        :param interval: 重试间隔
        :return:
        """
        homepage = self._spec.url
        logger.debug("homepage: {}".format(homepage))
        if not homepage:
            return SUCCESS

        for _ in xrange(retrying):
            if 0 == do_requests("get", homepage, timeout=timeout):
                return SUCCESS
            time.sleep(interval)

        return FAILED

    def check_patches(self):
        """
        检查spec中的patch是否存在
        :return:
        """
        patches_spec = set(self._spec.patches)
        patches_file = set(self._gr.patch_files_not_recursive())
        logger.debug("spec patches: {}".format(patches_spec))
        logger.debug("file patches: {}".format(patches_file))
        
        result = SUCCESS
        for patch in patches_spec - patches_file:
            logger.error("patch {} lost".format(patch))
            result = FAILED
        for patch in patches_file - patches_spec:
            logger.warning("patch {} redundant".format(patch))

        return result

    def _ex_exclusive_arch(self):
        """
        保存spec中exclusive_arch信息
        :return:
        """
        aarch64 = self._spec.include_aarch64_arch()
        x86_64 = self._spec.include_x86_arch()

        content = None
        if aarch64 and not x86_64:  # only build aarch64
            content = "aarch64"
        elif not aarch64 and x86_64:  # only build x86_64
            content = "x86-64"

        if content is not None:
            logger.info("exclusive arch \"{}\"".format(content))
            try:
                with open("exclusive_arch", "w") as f:
                    f.write(content)
            except IOError:
                logger.exception("save exclusive arch exception")

    def _ex_pkgship(self, spec):
        """
        pkgship需求
        :param spec: 上一个版本spec对应的RPMSpecAdapter对象
        :return:
        """
        if not self._repo == "pkgship":
            return

        logger.debug("special repo \"pkgship\"")
        compare_version = RPMSpecAdapter.compare_version(self._spec.version, spec.version)
        compare_release = RPMSpecAdapter.compare_version(self._spec.release, spec.release)
        compare = self._spec.compare(spec)

        rs = {"repo": "pkgship", "curr_version": self._spec.version, "curr_release": self._spec.release,
              "last_version": spec.version, "last_release": spec.release,
              "compare_version": compare_version, "compare_release": compare_release, "compare": compare}

        logger.info("{}".format(rs))
        try:
            with open("pkgship_notify", "w") as f:
                yaml.safe_dump(rs, f)
        except IOError:
            logger.exception("save pkgship exception")

    def __call__(self, *args, **kwargs):
        logger.info("check {} spec ...".format(self._repo))
        self._ex_exclusive_arch()

        return self.start_check()
