# -*- encoding=utf-8 -*-
"""
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
# Description: check spec file
# **********************************************************************************
"""
import os
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
from pyrpm.spec import Spec
from src.constant import Constant

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
        self._ex_support_arch()
        self._tbranch = kwargs.get("tbranch", None)
        # 因门禁系统限制外网访问权限，将涉及外网访问的检查功能check_homepage暂时关闭
        return self.start_check_with_order("patches", "changelog", "version_pr_changelog")

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
        检查lts分支是否是告警分支
        :return boolean
        """
        if self._tbranch:
            if self._tbranch.lower() in Constant.ALARM_LTS_BRANCH:
                return True
        return False

    def check_version_pr_changelog(self):
        """
        检查当前版本号是否比上一个commit新，每次提交pr的changelog
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

        # if lts branch is in MAINTENANCE_LTS_BRANCH, version update is allowed
        if self._is_lts_branch():
            logger.debug("lts branch %s", self._tbranch)
            if RPMSpecAdapter.compare_version(self._spec.version, spec_o.version) == 1:
                logger.error("version update of lts branch is forbidden")
                return FAILED

        def every_pr_changelog(changelog):
            """
            提取最新的一次changelog
            """
            return next(need_str for need_str in changelog.split("*") if need_str)

        try:
            changelog_new = every_pr_changelog(self._spec.changelog)
            changelog_old = every_pr_changelog(spec_o.changelog)
        except StopIteration as error:
            logger.error("new spec.changelog: %s, old spec.changelog: %s", self._spec.changelog, spec_o.changelog)
            return FAILED
        if changelog_new == changelog_old:
            logger.error("Every pr commit requires a changelog!")
            return FAILED
        if self._spec > spec_o:
            return SUCCESS
        elif self._spec < spec_o:
            if self._gp.is_revert_commit(depth=5):  # revert, version back, ignore
                logger.debug("revert commit")
                return SUCCESS

        logger.warning("current version: %s-r%s, last version: %s-r%s",
                       self._spec.version, self._spec.release, spec_o.version, spec_o.release)
        return WARNING

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
        检查spec中的patch是否存在，及patch的使用情况
        :return:
        """
        patches_spec = set(self._spec.patches)
        patches_file = set(self._gr.patch_files_not_recursive())
        logger.debug("spec patches: %s", patches_spec)
        logger.debug("file patches: %s", patches_file)

        result = SUCCESS

        def equivalent_patch_number(patch_con):
            """
            处理spec文件中patch序号
            :param patch_con:spec文件中patch内容
            :return:
            """
            patch_number = re.search(r"\d+", patch_con)
            new_patch_number = "patch" + str(int(patch_number.group()))
            return new_patch_number

        def rpm_new_standard_distinguishe_patch(patch_con):
            """
            匹配rpm新规则patch号
            :param patch_con:spec文件中patch内容
            :return:
            """
            prep_patches = []
            not_used_patches = []
            if re.findall(r"#\s*%patch\w+", patch_con):
                not_used_patches = re.findall(r"#\s*%patch\w+", patch_con)
            if re.findall(r"#\s*%patch \d+", patch_con):
                not_used_patches.extend(re.findall(r"#\s*%patch \d+", patch_con))
            if re.findall(r"#\s*%(-p\d+) (-p\d+)", patch_con):
                not_used_patches.extend(con[1] for con in re.findall(r"#\s*%(-p\d+) (-p\d+)", patch_con))
            format_not_used_patches = [equivalent_patch_number(single_prep_patch) for single_prep_patch in
                                       not_used_patches]

            if re.findall(r"patch\d+", patch_con):
                prep_patches = re.findall(r"patch\d+", patch_con)
            if re.findall(r"patch \d+", patch_con):
                prep_patches.extend(re.findall(r"patch \d+", patch_con))
            if re.findall(r"(-p\d+) (-p\d+)", patch_con):
                prep_patches.extend(con[1] for con in re.findall(r"(-p\d+) (-p\d+)", patch_con))
            all_patches = [equivalent_patch_number(single_prep_patch) for single_prep_patch in prep_patches]

            return list(set(all_patches) - set(format_not_used_patches))

        def patch_adaptation(spec_con, patches_dict):
            """
            检查spec文件中patch在prep阶段的使用情况
            :param spec_con:spec文件内容
            :param patches_dict:spec文件中补丁具体信息
            :return:
            """
            if not patches_dict:
                return True
            miss_patches_dict = {}
            prep_obj = re.search(r"%prep[\s\S]*%changelog", spec_con, re.I)
            if not prep_obj:
                logger.error("%prep part lost")
                return False
            prep_str = prep_obj.group().lower()
            if prep_str.find("autosetup") != -1 or \
                    prep_str.find("autopatch") != -1:
                return True
            prep_patch = rpm_new_standard_distinguishe_patch(prep_str)
            for single_key, single_patch in patches_dict.items():
                single_number = equivalent_patch_number(single_key)
                if single_number not in prep_patch:
                    miss_patches_dict[single_key] = single_patch
            if miss_patches_dict:
                logger_con = ["%s: %s" % (key, value) for key, value in miss_patches_dict.items()]
                logger.error("The following patches in the spec file are not used: \n%s", "\n".join(logger_con))
                logger.error(
                    "%patch is used to apply patches on top of the just unpacked pristine sources.Historically it \n"
                    "supported multiple strange syntaxes and buggy behaviors, which are no longer maintained. To apply\n"
                    "patch number 1, the following are recognized:\n"
                    "1 %patch 1 (since rpm >= 4.18)\n"
                    "2 %patch -P1 (all rpm versions)\n"
                    "3 %patch1 (deprecated, do not use)")
                return False
            return True

        for patch in patches_spec - patches_file:
            logger.error("patch %s lost", patch)
            result = FAILED
        for patch in patches_file - patches_spec:
            logger.warning("patch %s redundant", patch)
            result = WARNING
        with open(os.path.join(self._work_dir, self._gr.spec_file), "r", encoding="utf-8") as fp:
            all_str = fp.read()
            adapter = Spec.from_string(all_str)
            patch_dict = adapter.__dict__.get("patches_dict")
            if not patch_adaptation(all_str, patch_dict):
                result = FAILED
        return result

    def _ex_support_arch(self):
        """
        保存spec中exclusivearch字段信息
        :return:
        """
        exclusive_arch = self._spec.get_exclusivearch()
        if exclusive_arch:
            obj_s = list(set(exclusive_arch).intersection(("x86_64", "aarch64", "noarch")))
            logger.info("support arch:%s", " ".join(obj_s))
            if obj_s and "noarch" not in obj_s:
                content = " ".join(obj_s)
                try:
                    with open("support_arch", "w") as f:
                        f.write(content)
                except IOError:
                    logger.exception("save support arch exception")

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
            检查日期合法性
            """
            if date_obj[week].upper() not in weeks:
                return False
            if date_obj[month].upper() not in months:
                return False
            # 日期，取1-当前月份最大天数
            if not 0 < int(date_obj[day]) <= calendar.monthrange(int(date_obj[year]),
                                                                 months.index(date_obj[month].upper()) + 1)[1]:
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
            # 排除名字、邮箱格式中“-”的影响
            new_str = re.sub(r".*<[\w._-]+@[\w\-_]+[.a-zA-Z]+>", "", changelog_con)
            if self._spec.epoch:  # 检查spec文件中是否存在epoch字段
                obj_s = re.search(r"\w+:(\w+(.\w+){0,9})-[\w.]+", new_str)
                if not obj_s:
                    logger.error(
                        "There is an non-standard format in %s, please keep it consistent: Epoch:version-release \n"
                        "e.g: 1:1.0.0-1", changelog_con)
                    return False
                version = "".join([self._spec.epoch, ":", version])
            else:
                obj_s = re.search(r"(\w+(.\w+){0,9})-[\w.]+", new_str)
                if not obj_s:
                    logger.error("%s release or version incorrect format,please keep it consistent: version-release \n"
                                 "e.g: 1.0.0-1", changelog_con)
                    return False
            try:
                version_num, release_num = obj_s.group(0).split("-")
            except (ValueError, IOError, KeyError, IndexError) as e:
                logger.error("%s release or version incorrect format,please keep it consistent: version-release \n"
                             "e.g: 1.0.0-1", changelog_con)
                return False
            if version_num != version:
                logger.error("version error in changelog: %s is different from %s", version_num, version)
                return False
            if release_num != release:
                logger.error("release error in changelog: %s is different from %s", release_num, release)
                return False
            return True

        def check_mailbox(changelog):
            """
            检查changelog中邮箱格式
            """
            if "<" in changelog or ">" in changelog:
                mail_obj = re.findall(r"<[\w._-]+@[\w\-_]+[.a-zA-Z]+>", changelog)
            else:
                mail_obj = re.findall(r"[\w._-]+@[\w\-_]+[.a-zA-Z]+", changelog)
            if not mail_obj:
                return False
            return True

        def check_changelog_entries_start(changelog):
            """
            %changelog 条目必须以 * 开头
            """
            changelog_entries_obj = re.match(r"\*", changelog)
            if not changelog_entries_obj:
                return False
            return True

        def get_date_data(date_con):
            """
            年、月、日、星期
            """
            date_list = []
            date_data = [con for con in date_con.strip(" ").split(" ") if con]  # 列表中的空字符串已处理
            if len(date_data) < 4:  # 列表中的字符串至少四个,包含年、月、日、星期 ['Tue', 'Mar', '21', '2022']
                logger.error("bad data in changelog:%s", date_con)
                return False
            for index, con in enumerate(date_data[:4]):
                if index < 2:
                    date_list.append(con[:3])
                else:
                    date_list.append(con)
            return date_list

        if not check_changelog_entries_start(self._spec.changelog):
            logger.error("%changelog entries must start with *")
            return False
        changelog = self._spec.changelog.split("*")
        # 取最新一条changelog
        changelog_con = next(need_str for need_str in changelog if need_str)
        # 检查changelog中邮箱格式
        if not check_mailbox(changelog_con):
            logger.error("bad mailbox in changelog:%s", changelog_con)
            return False
        # date_obj是字符串列表，样例：['Tue', 'Mar', '21', '2022', 'xxx', '<xxx@xxx.com>', '-', '2.9.24-5-', 'test', '2.9.24-5']
        date_obj = get_date_data(changelog_con)  # 列表中的空字符串已处理
        if not date_obj:
            return False
        if not judgment_date(date_obj):
            logger.error("bad date in changelog:%s", changelog_con)
            return False
        if not release_and_version(changelog_con, self._spec.version, self._spec.release):
            return False
        if not bogus_date(date_obj):
            logger.error("bogus date in changelog:%s", changelog_con)
            return False
        return True
