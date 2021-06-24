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
# Author: 
# Create: 2020-09-23
# Description: Gitee api proxy
# ***********************************************************************************/
"""

import os
import logging

from src.proxy.git_proxy import GitProxy
from src.utils.shell_cmd import shell_cmd_live
from src.ac.acl.package_license.package_license import PkgLicense

logger = logging.getLogger("ac")


class GiteeRepo(object):
    """
    analysis src-openeuler repo
    """
    def __init__(self, repo, work_dir, decompress_dir):
        self._repo = repo
        self._work_dir = work_dir
        self._decompress_dir = decompress_dir

        self._patch_files = []
        self._compress_files = []

        self.spec_file = None
        self.yaml_file = None
        self.patch_dir_mapping = {}

        self.find_file_path()

    def find_file_path(self):
        """
        compress file, patch file, diff file, spec file
        """
        spec_files = []
        for dirpath, dirnames, filenames in os.walk(self._work_dir):
            for filename in filenames:
                rel_file_path = os.path.join(dirpath, filename).replace(self._work_dir, "").lstrip("/")
                if self.is_compress_file(filename):
                    logger.debug("find compress file: {}".format(rel_file_path))
                    self._compress_files.append(rel_file_path)
                elif self.is_patch_file(filename):
                    logger.debug("find patch file: {}".format(rel_file_path))
                    self._patch_files.append(rel_file_path)
                elif self.is_spec_file(filename):
                    logger.debug("find spec file: {}".format(rel_file_path))
                    spec_files.append(filename)
                elif self.is_package_yaml_file(filename):
                    logger.debug("find yaml file: {}".format(rel_file_path))
                    self.yaml_file = rel_file_path

        def guess_real_spec_file():
            """
            maybe multi spec file of repo
            :return:
            """
            if not spec_files:      # closure
                logger.warning("no spec file")
                return None

            if len(spec_files) == 1:
                return spec_files[0]

            # file prefix
            for spec_file in spec_files:
                prefix = spec_file.split(".")[0]
                if prefix == self._repo:
                    return spec_file

            # will not happen
            logger.warning("no spec file")
            return None

        self.spec_file = guess_real_spec_file()

    def patch_files_not_recursive(self):
        """
        获取当前目录下patch文件
        """
        return [filename for filename in os.listdir(self._work_dir)
                if os.path.isfile(os.path.join(self._work_dir, filename)) and self.is_patch_file(filename)]

    def decompress_file(self, file_path):
        """
        解压缩文件
        :param file_path:
        :return:
        """
        if self._is_compress_zip_file(file_path):
            decompress_cmd = "cd {}; timeout 120s unzip -o -d {} {}".format(
                    self._work_dir, self._decompress_dir, file_path)
        elif self._is_compress_tar_file(file_path):
            decompress_cmd = "cd {}; timeout 120s tar -C {} -xavf {}".format(
                    self._work_dir, self._decompress_dir, file_path)
        else:
            logger.warning("unsupport compress file: {}".format(file_path))
            return False

        ret, _, _ = shell_cmd_live(decompress_cmd)
        if ret:
            logger.debug("decompress failed")
            return False

        return True

    def decompress_all(self):
        """
        解压缩所有文件
        :return: 0/全部成功，1/部分成功，-1/全部失败
        """
        if not self._compress_files:
            logger.warning("no compressed source file")
        rs = [self.decompress_file(filepath) for filepath in self._compress_files]

        return 0 if all(rs) else (1 if any(rs) else -1)

    def apply_patch(self, patch, max_leading=5):
        """
        尝试所有路径和leading
        :param patch: 补丁
        :param max_leading: leading path
        """
        logger.debug("apply patch {}".format(patch))
        for patch_dir in [filename for filename in os.listdir(self._decompress_dir) 
                if os.path.isdir(os.path.join(self._decompress_dir, filename))] + ["."]:
            if patch_dir.startswith(".git"):
                continue
            for leading in range(max_leading + 1):
                logger.debug("try dir {} -p{}".format(patch_dir, leading))
                if GitProxy.apply_patch_at_dir(os.path.join(self._decompress_dir, patch_dir), 
                        os.path.join(self._work_dir, patch), leading):
                    logger.debug("patch success")
                    self.patch_dir_mapping[patch] = os.path.join(self._decompress_dir, patch_dir)
                    return True

        logger.info("apply patch {} failed".format(patch))
        return False

    def apply_all_patches(self, *patches):
        """
        打补丁通常是有先后顺序的
        :param patches: 需要打的补丁
        """
        if not self._compress_files:
            logger.debug("no compress source file, not need apply patch")
            return 0

        rs = []
        for patch in patches:
            if patch in set(self._patch_files):
                rs.append(self.apply_patch(patch))
            else:
                logger.error("patch {} not exist".format(patch))
                rs.append(False)

        return 0 if all(rs) else (1 if any(rs) else -1)

    def scan_license_in_spec(self, spec):
        """
        Find spec file and scan. If no spec file or open file failed, the program will exit with an error. 
        """
        if not spec:
            return set()
        licenses = spec.license
        licenses_in_spec = PkgLicense.split_license(licenses)
        logger.info("all licenses from SPEC: %s", ", ".join(list(licenses_in_spec)))
        return licenses_in_spec

    @staticmethod
    def is_py_file(filename):
        """
        功能描述：判断文件是否是python文件
        参数：文件名
        返回值：bool
        """
        return filename.endswith((".py",))

    @staticmethod
    def is_go_file(filename):
        """
        功能描述：判断文件名是否是go文件
        参数：文件名
        返回值：bool
        """
        return filename.endswith((".go",))

    @staticmethod
    def is_c_cplusplus_file(filename):
        """
        功能描述：判断文件名是否是c++文件
        参数：文件名
        返回值：bool
        """
        return filename.endswith((".c", ".cpp", ".cc", ".cxx", ".c++", ".h", ".hpp", "hxx"))

    @staticmethod
    def is_code_file(filename):
        """
        功能描述：判断文件名是否是源码文件
        参数：文件名
        返回值：bool
        """
        return GiteeRepo.is_py_file(filename) \
               or GiteeRepo.is_go_file(filename) \
               or GiteeRepo.is_c_cplusplus_file(filename)

    @staticmethod
    def is_patch_file(filename):
        """
        功能描述：判断文件名是否是补丁文件
        参数：文件名
        返回值：bool
        """
        return filename.endswith((".patch", ".diff"))

    @staticmethod
    def is_compress_file(filename):
        """
        功能描述：判断文件名是否是压缩文件
        参数：文件名
        返回值：bool
        """
        return GiteeRepo._is_compress_tar_file(filename) or GiteeRepo._is_compress_zip_file(filename)

    @staticmethod
    def _is_compress_zip_file(filename):
        """
        功能描述：判断文件名是否是zip压缩文件
        参数：文件名
        返回值：bool
        """
        return filename.endswith((".zip",))

    @staticmethod
    def _is_compress_tar_file(filename):
        """
        功能描述：判断文件名是否是tar压缩文件
        参数：文件名
        返回值：bool
        """
        return filename.endswith((".tar.gz", ".tar.bz", ".tar.bz2", ".tar.xz", "tgz"))

    @staticmethod
    def is_spec_file(filename):
        """
        功能描述：判断文件名是否以.spec结尾
        参数：文件名
        返回值：bool
        """
        return filename.endswith((".spec",))

    @staticmethod
    def is_package_yaml_file(filename):
        """
        功能描述：判断文件名是否以.yaml结尾
        参数：文件名
        返回值：bool
        """
        return filename.endswith((".yaml",))
