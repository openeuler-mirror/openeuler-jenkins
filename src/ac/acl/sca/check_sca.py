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
# Create: 2021-09-09
# Description: check sca (software composition analysis)
# **********************************************************************************

import os
import shutil
import logging
import json

from src.proxy.git_proxy import GitProxy
from src.ac.framework.ac_base import BaseCheck
from src.ac.framework.ac_result import FAILED, WARNING, SUCCESS
from src.ac.common.scanoss import ScanOSS

logger = logging.getLogger("ac")


class CheckSCA(BaseCheck):
    """
    check software composition analysis
    """
    def __init__(self, workspace, repo, conf):
        """

        :param workspace:
        :param repo:
        :param conf:
        """
        super(CheckSCA, self).__init__(workspace, repo, conf)

    def check_scanoss(self):
        """
        Obtain scanoss logs and result
        """
        # Describes the reportUrl result jenkinsJobName jenkinsBuildNum prNo repoUrl of scanoss
        try:
            with open(self._scanoss_result_output, 'r') as f:
                result_dirt = json.load(f)
        except IOError:
            logger.error("{} not found, make sure this file exists".format(self._scanoss_result_output))
            return FAILED
        
        result = result_dirt.get('result')
        
        # 保存详细结果到web server
        logger.warning("click {} view scanoss detail".format(result_dirt.get('reportUrl')))

        return SUCCESS if result else FAILED

    def __call__(self, *args, **kwargs):
        """
        入口函数
        :param args:
        :param kwargs:
        :return:
        """
        logger.info("check {} sca ...".format(self._repo))

        logger.debug("args: {}, kwargs: {}".format(args, kwargs))
        scanoss_conf = kwargs.get("scanoss", {})
        self._scanoss_result_output = scanoss_conf.get("output", "scanoss_result")
        
        return self.start_check()
