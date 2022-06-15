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
# Create: 2020-10-16
# Description: check spec file
# **********************************************************************************
"""

import logging
import os
import re
import json
import chardet

from src.proxy.requests_proxy import do_requests

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

    LICENSE_TARGET_PAT = re.compile(r"^(copying)|(copyright)|(copyrights)|(licenses)|(licen[cs]e)(\.(txt|xml))?")

    def __init__(self):
        self._license_translation = {}
        self._later_support_license = {}
        self.license_url = "https://compliance2.openeuler.org/sca?license={}&type={}"

    def check_license_safe(self, licenses):
        """
        Check if the license is in the blacklist
        """
        result = 0
        response_content = {}

        def analysis(response):
            """
            requests回调
            :param response: requests response object
            :return:
            """
            response_content.update(json.loads(response.text))

        if not isinstance(licenses, (set, list)):
            licenses = [licenses]
        for lic in licenses:
            rs = do_requests("get", url=self.license_url.format(lic, "reference"), obj=analysis)
            if rs != 0:
                result = 1
                logger.warning("Failed to obtain %s information through service", lic)
                continue
            res = response_content.get("pass")
            if res:
                logger.info("This license: %s is free", lic)
            else:
                notice_content = response_content.get("notice")
                black_reason = response_content.get("detail").get("is_white").get("blackReason")
                logger.warning("License: %s", notice_content)
                if black_reason:
                    logger.error("License: %s", black_reason)
                result = -1
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

    # 以下为从license文件中获取license
    def scan_licenses_in_license(self, srcdir):
        """
        Find LICENSE files and scan. 
        """
        licenses_in_file = set()
        if not os.path.exists(srcdir):
            logger.error("%s not exist.", srcdir)
            return licenses_in_file

        for root, _, filenames in os.walk(srcdir):
            for filename in filenames:
                if (filename.lower() in self.LICENSE_FILE_TARGET
                        or self.LICENSE_TARGET_PAT.search(filename.lower())):
                    logger.info("scan the license target file: %s", os.path.join(root, filename).replace(srcdir, ""))
                    licenses_in_file.update(
                        self.scan_licenses(
                            os.path.join(root, filename)))
        logger.info("all licenses from src: %s", ", ".join([data for data in licenses_in_file]))
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
        blank_pat = re.compile(r"\s+")
        data = blank_pat.sub(" ", data)
        if not data:
            return licenses_in_file
        for word in self._license_translation:
            try:
                if word in data:
                    pattern_str = r'(^{word}$)|(^{word}(\W+))|((\W+){word}$)|((\W+){word}(\W+))' \
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
    def check_licenses_is_same(licenses_for_spec, licenses_for_source_files, later_support_license):
        """
        Check if the licenses from SPEC is the same as the licenses from LICENSE file.
        if same, return True. if not same return False.
        """
        all_licenses_for_spec = set()
        for spec_license in licenses_for_spec:
            if "-or-later" in spec_license:
                [license_name, least_version] = spec_license.split("-or-later")[0].split("-", 1)
                if license_name not in later_support_license:
                    all_licenses_for_spec.add(spec_license)
                    continue
                for version in later_support_license[license_name]["versions"]:
                    if version >= least_version:
                        all_licenses_for_spec.add("{}-{}-or-later".format(license_name, version))
                        all_licenses_for_spec.add("{}-{}-only".format(license_name, version))
            else:
                all_licenses_for_spec.add(spec_license)
        return all_licenses_for_spec.issuperset(licenses_for_source_files)

    @property
    def later_support_license(self):
        return self._later_support_license
