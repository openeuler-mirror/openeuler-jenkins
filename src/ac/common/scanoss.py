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
# Create: 2021-04-15
# Description: sca with scanoss tools
# **********************************************************************************

import json
import logging

from src.utils.shell_cmd import shell_cmd_live, shell_cmd

logger = logging.getLogger("ac")


class ScanOSS(object):
    """
    scanoss 工具代理
    """
    def __init__(self, key, api_url, blacklist_sbom):
        """

        :param key:
        :param api_url:
        :param blacklist_sbom:
        """
        self._key = key
        self._api_url = api_url
        self._blacklist_sbom = blacklist_sbom

        self._html_content = "<table></table>"

    def result_analysis(self, result):
        """
        分析结果
        1.是否发生代码片段引用
        2.如果有则转换成html格式
        :param result:
        :return: True/没有代码引用，否则False
        """
        try:
            json_format = json.loads(result)
        except ValueError:
            logger.exception("illegal scanoss result, \"%s\"", result)
            return True

        snippets = 0
        files = 0
        detail_trs = []
        for filename, items in json_format.items():
            for item in items:
                if item["id"] == "none":
                    continue
                if item["id"] == "snippet":
                    snippets += 1
                elif item["id"] == "file":
                    files += 1

                detail_trs.append(self.__class__.detail_trs(filename, item))

        logger.debug("snippets: %s, files: %s", snippets, files)
        detail = "<table border=\"1\" cellspacing=\"0\" cellpadding=\"5\">{th}{trs}</table>".format(
            th=self.__class__.detail_th(), trs="\n".join(detail_trs))

        summary = "<table border=\"1\" cellspacing=\"0\" cellpadding=\"5\" style=\"margin-bottom:20px\" >" \
                  "{th}{trs}</table>".format(th=self.__class__.summary_th(),
                                             trs="".join(self.__class__.summary_trs(snippets, files)))

        self._html_content = "<html>{summary}{details}</html>".format(summary=summary, details=detail)

        return False if snippets or files else True

    @staticmethod
    def detail_th():
        """
        详细结果table header
        :return:
        """
        return "<tr>" \
               "<th style='1px solid black'>filename</th>" \
               "<th>id</th>" \
               "<th>lines</th>" \
               "<th>oss_lines</th>" \
               "<th>matched</th>" \
               "<th>vendor</th>" \
               "<th>component</th>" \
               "<th>version</th>" \
               "<th>url</th>" \
               "<th>file</th>" \
               "<th>file_id</th>" \
               "</tr>"

    @staticmethod
    def detail_trs(filename, item):
        """
        详细结果table rows
        :param filename: 文件名
        :param item:
        :return:
        """
        return "<tr>"\
               "<td>{filename}</td>" \
               "<td>{id}</td>" \
               "<td>{lines}</td>" \
               "<td>{oss_lines}</td>" \
               "<td>{matched}</td>" \
               "<td>{vendor}</td>" \
               "<td>{component}</td>" \
               "<td>{version}</td>" \
               "<td>{url}</td>" \
               "<td>{file}</td>" \
               "<td>{file_hash}</td>" \
               "</tr>".format(filename=filename, **item)

    @staticmethod
    def summary_th():
        """
        归纳结果table header
        :return:
        """
        return "<tr>" \
               "<td style='1px solid black'>snippet</td>" \
               "<td>file</td>" \
               "<td>total</td>" \
               "</tr>"

    @staticmethod
    def summary_trs(snippets, files):
        """
        归纳结果table rows
        :param snippets:
        :param files:
        :return:
        """
        return "<tr>" \
               "<td>{snippets}</td>" \
               "<td>{files}</td>" \
               "<td>{total}</td>" \
               "</tr>".format(snippets=snippets, files=files, total=snippets + files)

    @property
    def html(self):
        """
        内容
        :return:
        """
        return self._html_content

    def scan(self, directory):
        """
        执行扫描
        :param directory: 需要扫描的目录
        :return:
        """
        logger.debug("scan dir: %s", directory)
        #scanoss_cmd = "scanner.py --format {} {} --apiurl {} {}".format(
        #    "plain", "--key {}".format(self._key) if self._key else "", self._api_url, directory)
        scanoss_cmd = "scanner.py --blacklist {} --format {} {} --apiurl {} {}".format(
            self._blacklist_sbom, "plain", "--key {}".format(self._key) if self._key else "", self._api_url, directory)
        ret, out, err = shell_cmd(scanoss_cmd)

        if ret:
            logger.error("scanoss error, %s", ret)
            logger.error("%s", err)
            return True

        return self.result_analysis(out)
