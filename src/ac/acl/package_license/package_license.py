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
# Create: 2020-10-16
# Description: check spec file
# **********************************************************************************
"""

import logging
import os
import re
import chardet
import yaml

from src.ac.common.pyrpm import Spec, replace_macros
from src.ac.common.rpm_spec_adapter import RPMSpecAdapter

logger = logging.getLogger("ac")

class PkgLicense(object):
    """
    解析获取软件包中源码、spec中的license
    进行白名单校验、一致性检查
    """

    LICENSE_FILE_TARGET = ["apache-2.0",
                           "artistic",
                           "artistic.txt",
                           "libcurllicense",
                           "gpl.txt",
                           "gpl2.txt",
                           "gplv2.txt",
                           "lgpl.txt",
                           "notice",
                           "about_bsd.txt",
                           "mit",
                           "pom.xml",
                           "meta.yml",
                           "meta.json",
                           "pkg-info"]
    
    LICENSE_TARGET_PAT  = re.compile(r"^(copying)|(copyright)|(copyrights)|(licenses)|(licen[cs]e)(\.(txt|xml))?$")

    LICENSE_YAML_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                   "config",
                                   "Licenses.yaml")

    def __init__(self):
        self._white_black_list = {}
        self._license_translation = {}

    def load_config(self):
        """
        load licenses' alias and id from Licenses.yaml
        Software License:
            Bad Licenses:
                - alias: []
                  identifier: str
                ...
            Good Licenses: []
            Need Review Licenses: []
        """
        if not os.path.exists(self.LICENSE_YAML_PATH):
            logger.warning("not found License config: %s", self.LICENSE_YAML_PATH)
            return
        data = {}
        with open(self.LICENSE_YAML_PATH, "r") as f:
            try:
                data = yaml.safe_load(f)
            except yaml.YAMLError as e:
                logger.exception("yaml load error: %s", str(e))
                return
        self._parse_tag_license(data["Software Licenses"]["Bad Licenses"], 
                                     "black")
        self._parse_tag_license(data["Software Licenses"]["Good Licenses"], 
                                     "white")
        self._parse_tag_license(data["Software Licenses"]["Need Review Licenses"], 
                                     "need review")

    def _parse_tag_license(self, licenses, tag):
        """
        add friendly list to self._white_black_list :
        {
            license_id: tag,
            ...
        }
        add license translation into self._license_translation
        {
            alias: license_id
        }
        """
        for lic in licenses:
            if lic["identifier"] not in self._white_black_list:
                self._white_black_list[lic["identifier"]] = tag
            for oname in lic["alias"]:
                if oname not in self._license_translation:
                    self._license_translation[oname] = lic["identifier"]

    def check_license_safe(self, licenses):
        """
        Check if the license is in the blacklist
        """
        result = True
        for lic in licenses:
            res = self._white_black_list.get(lic, "unknow")
            if res == "white":
                logger.info("This license: %s is safe", lic)
            elif res == "black":
                logger.error("This license: %s is not safe", lic)
                result = False
            else: 
                logger.warning("This license: %s need to be review", lic)
                result = False
        return result

    def translate_license(self, licenses):
        """
        Convert license to uniform format
        """
        result = set()
        for lic in licenses:
            real_license = self._license_translation.get(lic, lic)
            result.add(real_license)
        return result

    @staticmethod
    def split_license(licenses):
        """
        分割spec license字段的license 按() and -or- or / 进行全字匹配进行分割
        """
        license_set = re.split(r'\(|\)|\,|\s+[Aa][Nn][Dd]\s+|\s+-?or-?\s+|\s+/\s+', licenses)
        for index in range(len(license_set)): # 去除字符串首尾空格
            license_set[index] = license_set[index].strip()
        return set(filter(None, license_set)) # 去除list中空字符串

    # 以下为从license文件中获取license
    def scan_licenses_in_license(self, srcdir):
        """
        Find LICENSE files and scan. 
        """
        licenses_in_file = set()
        if not os.path.exists(srcdir):
            logger.error("%s not exist.", srcdir)
            return licenses_in_file

        for root, dirnames, filenames in os.walk(srcdir):
            for filename in filenames:  
                if (filename.lower() in self.LICENSE_FILE_TARGET 
                    or self.LICENSE_TARGET_PAT.search(filename.lower())):
                    logger.info("scan the license target file: %s", filename)
                    licenses_in_file.update(
                        self.scan_licenses(
                            os.path.join(root, filename)))
        logger.info("all licenses from src: %s", ", ".join([data.encode("utf-8") for data in licenses_in_file]))
        return licenses_in_file

    def scan_licenses(self, copying):
        """
        Scan licenses from copying file and add to licenses_for_source_files.
        if get contents failed or decode data failed, return nothing.
        """
        licenses_in_file = set()

        if not os.path.exists(copying):
            logger.warning("file: %s not exist", copying)
            return licenses_in_file

        for word in self._license_translation:
            if word in copying:
                licenses_in_file.add(word)

        with open(copying, "rb") as f:
            data = f.read()
        data = PkgLicense._auto_decode_str(data)
        if not data:
            return licenses_in_file
        for word in self._license_translation:
            try:
                if word in data:
                    pattern_str = r'(^{word}$)|(^{word}(\s+))|((\s+){word}$)|((\s+){word}(\s+))' \
                                  .format(word=word)
                    if re.search(pattern_str, data):
                        licenses_in_file.add(word)
            except UnicodeDecodeError as e:
                logger.exception("decode error: %s", str(e))
        return licenses_in_file

    @staticmethod
    def _decode_str(data, charset):
        """ 
        Decode the license string. return the license string or nothing.
        """
        if not charset:
            return ""
        try:
            return data.decode(charset)
        except UnicodeDecodeError as e:
            logger.exception("decode error: %s", str(e))
            return ""

    @staticmethod
    def _auto_decode_str(data):
        return PkgLicense._decode_str(data, chardet.detect(data)["encoding"])

    @staticmethod
    def check_licenses_is_same(licenses_for_spec, licenses_for_source_files):
        """
        Check if the licenses from SPEC is the same as the licenses from LICENSE file.
        if same, return True. if not same return False.
        """
        return licenses_for_spec.issuperset(licenses_for_source_files)