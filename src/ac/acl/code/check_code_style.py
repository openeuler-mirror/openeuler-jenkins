# -*- encoding=utf-8 -*-
import os
import shutil
import logging

from src.proxy.git_proxy import GitProxy
from src.ac.framework.ac_base import BaseCheck
from src.ac.framework.ac_result import FAILED, WARNING, SUCCESS
from src.ac.common.gitee_repo import GiteeRepo
from src.ac.common.linter import LinterCheck
from src.ac.common.rpm_spec_adapter import RPMSpecAdapter

logger = logging.getLogger("ac")


class CheckCodeStyle(BaseCheck):
    def __init__(self, workspace, repo, conf):
        super(CheckCodeStyle, self).__init__(workspace, repo, conf)

        self._work_tar_dir = os.path.join(workspace, "code")    # 解压缩目标目录

        self._gr = GiteeRepo(self._work_dir, self._work_tar_dir)

    def check_compressed_file(self):
        """
        解压缩包
        """
        return SUCCESS if 0 == self._gr.decompress_all() else FAILED

    def check_patch(self):
        """
        应用所有patch
        """
        patches = []
        if self._gr.spec_file:
            spec = RPMSpecAdapter(os.path.join(self._work_dir, self._gr.spec_file))
            patches = spec.patches

        rs = self._gr.apply_all_patches(*patches)

        if 0 == rs:
            return SUCCESS

        return WARNING if 1 == rs else FAILED

    def check_code_style(self):
        """
        检查代码风格
        :return:
        """
        gp = GitProxy(self._work_dir)
        diff_files = gp.diff_files_between_commits("HEAD~1", "HEAD~0")
        logger.debug("diff files: {}".format(diff_files))

        diff_code_files = []                # 仓库中变更的代码文件
        diff_patch_code_files = []          # patch内的代码文件
        for diff_file in diff_files:
            if GiteeRepo.is_code_file(diff_file):
                diff_code_files.append(diff_file)
            elif GiteeRepo.is_patch_file(diff_file):
                patch_dir = self._gr.patch_dir_mapping.get(diff_file)
                logger.debug("diff patch {} apply at dir {}".format(diff_file, patch_dir))
                if patch_dir is not None:
                    files_in_patch = gp.extract_files_path_of_patch(diff_file)
                    diff_patch_code_files.extend([os.path.join(patch_dir, file_in_patch) 
                        for file_in_patch in files_in_patch if GiteeRepo.is_code_file(file_in_patch)])
        logger.debug("diff code files: {}".format(diff_code_files))
        logger.debug("diff patch code files: {}".format(diff_patch_code_files))

        rs_1 = self.check_file_under_work_dir(diff_code_files)
        logger.debug("check_file_under_work_dir: {}".format(rs_1))
        rs_2 = self.check_files_inner_patch(diff_patch_code_files)
        logger.debug("check_files_inner_patch: {}".format(rs_2))

        return rs_1 + rs_2

    def check_file_under_work_dir(self, diff_code_files):
        """
        检查仓库中变更的代码
        :return:
        """
        rs = [self.__class__.check_code_file(filename) for filename in set(diff_code_files)]

        return sum(rs, SUCCESS) if rs else SUCCESS

    def check_files_inner_patch(self, diff_patch_code_files):
        """
        检查仓库的patch内的代码
        :return:
        """
        rs = [self.__class__.check_code_file(os.path.join(self._work_tar_dir, filename)) for filename in set(diff_patch_code_files)]

        return sum(rs, SUCCESS) if rs else SUCCESS

    @classmethod
    def check_code_file(cls, file_path):
        """
        检查代码风格
        :param file_path:
        :return:
        """
        if GiteeRepo.is_py_file(file_path):
            rs = LinterCheck.check_python(file_path)
        elif GiteeRepo.is_go_file(file_path):
            rs = LinterCheck.check_golang(file_path)
        elif GiteeRepo.is_c_cplusplus_file(file_path):
            rs = LinterCheck.check_c_cplusplus(file_path)
        else:
            logger.error("error when arrive here, unsupport file {}".format(file_path))
            return SUCCESS

        logger.info("Linter: {:<40} {}".format(file_path, rs))
        if rs.get("F", 0) > 0:
            return FAILED

        if rs.get("W", 0) > 0 or rs.get("E", 0) > 0:
            return WARNING

        return SUCCESS

    def __call__(self, *args, **kwargs):
        """
        入口函数
        :param args:
        :param kwargs:
        :return:
        """
        logger.info("check {} repo ...".format(self._repo))

        not os.path.exists(self._work_tar_dir) and os.mkdir(self._work_tar_dir)
        try:
            return self.start_check_with_order("compressed_file", "patch", "code_style")
        finally:
            shutil.rmtree(self._work_tar_dir)
