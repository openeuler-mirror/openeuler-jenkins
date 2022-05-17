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
# Create: 2021-4-22
# Description: common file read and write class
# **********************************************************************************
"""
import os
import stat
import json
import yaml


class FileOperator(object):
    """file operator"""

    config_table = {
        "reader": {
            "yaml": {"function": yaml.safe_load, "exception": yaml.MarkedYAMLError},
            "json": {"function": json.load, "exception": json.JSONDecodeError},
            "default": {"function": lambda f: f.read(), "exception": IOError}
        },
        "writer": {
            "yaml": {"function": yaml.safe_dump, "exception": IOError},
            "json": {"function": json.dump, "exception": IOError},
            "default": {"function": lambda f, data: f.write(data), "exception": IOError}
        },
    }

    @staticmethod
    def filereader(filepath, file_format=None):
        if file_format:
            reader_config = FileOperator.config_table.get("reader").get(file_format)
        else:
            reader_config = FileOperator.config_table.get("reader").get("default")
        if not reader_config:
            raise IOError("filereader don't support {} file".format(file_format))
        if not os.path.exists(filepath):
            raise IOError("{} not exists".format(os.path.basename(filepath)))

        with open(filepath, "r", encoding='utf-8') as data:
            try:
                all_data = reader_config.get("function")(data)
            except reader_config.get("exception") as error:
                raise IOError("{} is not an illegal {} file".format(
                    os.path.basename(filepath), file_format)) from error
        return all_data

    @staticmethod
    def filewriter(filepath, all_data, file_format=None):
        if file_format:
            writer_config = FileOperator.config_table.get("writer").get(file_format)
        else:
            writer_config = FileOperator.config_table.get("writer").get("default")
        if not writer_config:
            raise IOError("filewriter don't support {} file".format(file_format))
        try:
            with os.fdopen(os.open(filepath, os.O_WRONLY | os.O_CREAT,
                                   stat.S_IWUSR | stat.S_IRUSR), "w") as f:
                writer_config.get("function")(all_data, f)
        except writer_config.get("exception") as error:
            raise IOError("save {} file exception".format(os.path.basename(filepath))) from error


