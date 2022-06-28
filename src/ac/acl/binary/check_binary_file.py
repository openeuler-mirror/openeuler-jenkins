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
# Create: 2022-02-09
# Description: check binary file
# **********************************************************************************

import os
import shutil
import logging

from src.ac.framework.ac_base import BaseCheck
from src.ac.framework.ac_result import FAILED, SUCCESS
from src.ac.common.gitee_repo import GiteeRepo
from pyrpm.spec import Spec, replace_macros

logger = logging.getLogger("ac")


class CheckBinaryFile(BaseCheck):
    """
    check binary file
    """
    # 二进制文件后缀集
    BINARY_LIST = {".pyc", ".jar", ".o", ".ko"}

    def __init__(self, workspace, repo, conf):
        super(CheckBinaryFile, self).__init__(workspace, repo, conf)
        self._work_tar_dir = os.path.join(workspace, "code")  # 解压缩目标目录
        self._gr = GiteeRepo(self._repo, self._work_dir, self._work_tar_dir)
        self._tarball_in_spec = set()
        self._upstream_community_tarball_in_spec()

    def __call__(self, *args, **kwargs):
        """
        入口函数
        :param args:
        :param kwargs:
        :return:
        """
        logger.info("check %s binary files ...", self._repo)

        _ = not os.path.exists(self._work_tar_dir) and os.mkdir(self._work_tar_dir)
        try:
            return self.start_check_with_order("compressed_file", "binary")
        finally:
            shutil.rmtree(self._work_tar_dir)

    def check_compressed_file(self):
        """
        解压缩包
        """
        need_compress_files = []
        for decompress_file in self._gr.get_compress_files():
            if decompress_file not in self._tarball_in_spec:
                need_compress_files.append(decompress_file)
        self._gr.set_compress_files(need_compress_files)
        return SUCCESS if 0 == self._gr.decompress_all() else FAILED

    def check_binary(self):
        """
        检查二进制文件
        """
        suffixes_list = self._get_all_file_suffixes(self._work_tar_dir)
        if suffixes_list:
            logger_con = ["%s: \n%s" % (key, value) for suffix_list in suffixes_list for key, value in
                          suffix_list.items()]
            logger.error("binary file of type exists:\n%s", "\n".join(logger_con))
            return FAILED
        else:
            return SUCCESS

    @staticmethod
    def _is_compress_tar_file(filename):
        """
        判断文件名是否是指定压缩文件
        filename：文件名
        返回值：bool
        """
        return filename.endswith((".tar.gz", ".tar.bz", ".tar.bz2", ".tar.xz", "tgz", ".zip"))

    def _upstream_community_tarball_in_spec(self):
        """
        spec指定的上游社区压缩包
        """
        if self._gr.spec_file is None:
            logger.error("spec file not find")
            return
        with open(os.path.join(self._work_dir, self._gr.spec_file), "r", encoding="utf-8") as fp:
            adapter = Spec.from_string(fp.read())
        for filename in adapter.__dict__.get("sources"):
            spec_src_name = replace_macros(filename, adapter)
            if "http" in spec_src_name and self._is_compress_tar_file(spec_src_name):
                self._tarball_in_spec.add(spec_src_name.split("/")[-1] if filename else "")
        info_msg = "spec指定的上游社区压缩包:%s" % self._tarball_in_spec if self._tarball_in_spec else "暂无spec指定的上游社区压缩包"
        logger.info(info_msg)
        return self._tarball_in_spec

    def _get_all_file_suffixes(self, path):
        """
        获取当前文件中所有文件名后缀,并判断
        """
        binary_list = []
        if not os.path.exists(path):
            return binary_list
        for root, _, files in os.walk(path):
            binary_file = []
            for single_file in files:
                file_suffixes = os.path.splitext(single_file)[1]
                if file_suffixes in self.BINARY_LIST:
                    binary_file.append(single_file)
            if binary_file:
                binary_list.append({root.split("code")[-1]: binary_file})
        return binary_list


