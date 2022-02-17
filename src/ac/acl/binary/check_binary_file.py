# -*- encoding=utf-8 -*-
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
# Create: 2022-02-09
# Description: check binary file
# **********************************************************************************

import os
import shutil
import logging

from src.ac.framework.ac_base import BaseCheck
from src.ac.framework.ac_result import FAILED, SUCCESS
from src.ac.common.gitee_repo import GiteeRepo

logger = logging.getLogger("ac")


class CheckBinaryFile(BaseCheck):
    """
    check binary file
    """
    # 二进制文件后缀集
    BINARY_LIST = {"pyc", ".jar", ".o", ".ko"}

    def __init__(self, workspace, repo, conf):
        super(CheckBinaryFile, self).__init__(workspace, repo, conf)

        self._work_tar_dir = os.path.join(workspace, "code")  # 解压缩目标目录

        self._gr = GiteeRepo(self._repo, self._work_dir, self._work_tar_dir)

    def check_compressed_file(self):
        """
        解压缩包
        """
        return SUCCESS if 0 == self._gr.decompress_all() else FAILED

    def check_binary(self):
        """
        检查二进制文件
        """
        all_files = self._get_all_file(self._work_tar_dir)
        suffixes_list = self._get_file_suffixes(all_files)
        rs = suffixes_list & self.BINARY_LIST
        if rs:
            logger.error("binary file of type %s exists", rs)
            return FAILED
        else:
            return SUCCESS

    def _get_list_dir(self, path):
        """
        判断路径是否为文件全名
        """
        fl = []
        try:
            fl = os.listdir(path)
        except NotADirectoryError as error:
            pass
        finally:
            return fl

    def _get_all_file(self, path):
        """
        获取当前文件中所有文件名
        """
        all_file = []
        if not os.path.exists(path):
            return all_file

        files = self._get_list_dir(path)
        if len(files) != 0:
            files = list(map(lambda x: os.path.join(path, x), files))
            all_file = all_file + files
            for file in files:
                all_file = all_file + self._get_all_file(file)
        return all_file

    def _get_file_suffixes(self, file_list):
        """
        获取当前文件中所有文件名后缀
        """
        suffixes_list = set()
        for single_file in file_list:
            suffixes_list.add(os.path.splitext(single_file)[1].lower())
        logger.info("suffixes_list %s", suffixes_list)
        return suffixes_list

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
