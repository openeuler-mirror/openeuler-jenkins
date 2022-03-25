# -*- encoding=utf-8 -*-
"""
# **********************************************************************************
# Copyright (c) Huawei Technologies Co., Ltd. 2020-2020. All rights reserved.
# [openeuler-jenkins] is licensed under the Mulan PSL v1.
# You can use this software according to the terms and conditions of the Mulan PSL v1.
# You may obtain a copy of Mulan PSL v1 at:
#     http://license.coscl.org.cn/MulanPSL
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY OR FIT FOR A PARTICULAR
# PURPOSE.
# See the Mulan PSL v1 for more details.
# Author: 
# Create: 2020-09-23
# Description: check spec file
# **********************************************************************************
"""
import calendar
import logging
import time
import re
from datetime import datetime, timezone
import yaml

from src.proxy.git_proxy import GitProxy
from src.proxy.requests_proxy import do_requests
from src.ac.framework.ac_result import FAILED, SUCCESS, WARNING
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
        self._tbranch = None

    def __call__(self, *args, **kwargs):
        logger.info("check %s spec ...", self._repo)
        self._ex_exclusive_arch()
        self._tbranch = kwargs.get("tbranch", None)
        # 因门禁系统限制外网访问权限，将涉及外网访问的检查功能check_homepage暂时关闭
        return self.start_check_with_order("version", "patches", "changelog")

    def _only_change_package_yaml(self):
        """
        如果本次提交只变更yaml，则无需检查version
        :return: boolean
        """
        diff_files = self._gp.diff_files_between_commits("HEAD~1", "HEAD~0")
        package_yaml = "{}.yaml".format(self._repo)  # package yaml file name

        if len(diff_files) == 1 and diff_files[0] == package_yaml:
            logger.debug("diff files: %s", diff_files)
            return True

        return False

    def _is_lts_branch(self):
        """
        检查分支是否是lts分支
        :return boolean
        """
        if self._tbranch:
            if "lts" in self._tbranch.lower():
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

        self._gp.checkout_to_commit_force("HEAD~1")
        try:
            gr = GiteeRepo(self._repo, self._work_dir, None)  # don't care about decompress
            logger.info("gr.spec_file:%s", gr.spec_file)
            fp = self._gp.get_content_of_file_with_commit(gr.spec_file)
            if fp is None:
                # last commit has no spec file
                return SUCCESS
            spec_o = RPMSpecAdapter(fp)
        finally:
            self._gp.checkout_to_commit_force(self._latest_commit)  # recover whatever

        self._ex_pkgship(spec_o)

        # if lts branch, version update is forbidden
        if self._is_lts_branch():
            logger.debug("lts branch %s", self._tbranch)
            if RPMSpecAdapter.compare_version(self._spec.version, spec_o.version) == 1:
                logger.error("version update of lts branch is forbidden")
                return FAILED
        if self._spec > spec_o:
            return SUCCESS
        elif self._spec < spec_o:
            if self._gp.is_revert_commit(depth=5):  # revert, version back, ignore
                logger.debug("revert commit")
                return SUCCESS

        logger.error("current version: %s-r%s, last version: %s-r%s",
                     self._spec.version, self._spec.release, spec_o.version, spec_o.release)
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
        logger.debug("homepage: %s", homepage)
        if not homepage:
            return SUCCESS

        for _ in range(retrying):
            if 0 == do_requests("get", homepage, timeout=timeout):
                return SUCCESS
            time.sleep(interval)

        return FAILED

    def check_changelog(self):
        """
        检查changelog中的日期错误
        :return:
        """
        ret = self._parse_spec()
        if not ret:
            return FAILED
        return SUCCESS

    def check_patches(self):
        """
        检查spec中的patch是否存在
        :return:
        """
        patches_spec = set(self._spec.patches)
        patches_file = set(self._gr.patch_files_not_recursive())
        logger.debug("spec patches: %s", patches_spec)
        logger.debug("file patches: %s", patches_file)

        result = SUCCESS
        for patch in patches_spec - patches_file:
            logger.error("patch %s lost", patch)
            result = FAILED
        for patch in patches_file - patches_spec:
            logger.warning("patch %s redundant", patch)
            result = WARNING
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
            logger.info("exclusive arch \"%s\"", content)
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

        logger.info("%s", rs)
        try:
            with open("pkgship_notify", "w") as f:
                yaml.safe_dump(rs, f)
        except IOError:
            logger.exception("save pkgship exception")

    def _parse_spec(self):
        """
        获取最新提交的spec文件
        :return:
        """
        weeks = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
        months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
        week = 0
        month = 1
        day = 2
        year = 3

        def judgment_date(date_obj):
            """
            检查日期合法性：年，月，日，周
            """
            if date_obj[week].upper() not in weeks:
                return False
            if date_obj[month].upper() not in months:
                return False
            # 日期，取1-当前月份最大天数
            if not 0 < int(date_obj[day]) <= calendar.monthrange(int(date_obj[year]),
                                                                 months.index(date_obj[month].upper()) + 1)[1]:
                return False
            # 年份要等于当前年份
            if int(date_obj[year]) != datetime.now(tz=timezone.utc).year:
                return False
            return True

        def bogus_date(date_obj):
            """
            匹配年月日对应的星期
            """
            try:
                week_num = calendar.weekday(int(date_obj[year]), months.index(date_obj[month].upper()) + 1,
                                            int(date_obj[day]))
            except (ValueError, IndexError) as error:
                logger.error(error)
                return False
            if weeks[week_num] != date_obj[week].upper():
                return False
            return True

        def release_and_version(changelog_con, version, release):
            """
            检查changelog中的版本号，release号是否和spec的版本号，release号一致
            """
            obj_s = re.search(r"(\d+(.\d+){0,9})-\d+", changelog_con)
            if not obj_s:
                logger.warning("%s Missing release or version!", changelog_con)
                return False
            version_num, release_num = obj_s.group(0).split("-")
            if version_num != version:
                logger.warning("version error in changelog: %s != %s", version_num, version)
                return False
            if release_num != release:
                logger.warning("release error in changelog: %s != %s", release_num, release)
                return False
            return True

        def every_changelog_should_start_with_star(changelog):
            """
            检查changelog中每条记录都应该以*开头
            """
            mail_obj = re.findall(r"[\w._-]+@[a-z0-9]+.[a-z]{2,4}", changelog)
            star_obj = re.findall(r"\* ", changelog)
            if len(mail_obj) != len(star_obj):
                return False
            return True

        if not every_changelog_should_start_with_star(self._spec.changelog):
            logger.error("Every changelog should start with * and contains a mailbox")
            return False
        changelog = self._spec.changelog.split("*")
        # 取最新一条changelog
        changelog_con = next(need_str for need_str in changelog if need_str)
        # date_obj是字符串列表，样例：['Tue', 'Mar', '21', '2022', 'xxx', '<xxx@xxx.com>', '-', '2.9.24-5-', 'test', '2.9.24-5']
        date_obj = [con for con in changelog_con.strip(" ").split(" ") if con]  # 列表中的空字符串已处理
        if len(date_obj) < 4:  # 列表中的字符串至少四个,包含年、月、日、星期 ['Tue', 'Mar', '21', '2022']
            logger.error("bad data in changelog:%s", changelog_con)
            return False
        if not judgment_date(date_obj) or not release_and_version(changelog_con, self._spec.version,
                                                                  self._spec.release):
            logger.error("bad date in changelog:%s", changelog_con)
            return False
        if not bogus_date(date_obj):
            logger.error("bogus date in changelog:%s", changelog_con)
            return False
        return True
