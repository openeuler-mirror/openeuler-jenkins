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
# Create: 2020-09-23
# Description: access control list base class
# **********************************************************************************
"""

class ACResult(object):
    """
    Use this variables (FAILED, WARNING, SUCCESS) at most time,
    and don't new ACResult unless you have specific needs.
    """
    def __init__(self, val):
        self._val = val

    def __add__(self, other):
        return self if self.val >= other.val else other

    def __str__(self):
        return self.hint

    def __repr__(self):
        return self.__str__()

    @classmethod
    def get_instance(cls, val):
        """
        
        :param val: 0/1/2/True/False/success/fail/warn
        :return: instance of ACResult
        """
        if isinstance(val, int):
            return {0: SUCCESS, 1: WARNING, 2: FAILED}.get(val)
        if isinstance(val, bool):
            return {True: SUCCESS, False: FAILED}.get(val)

        try:
            val = int(val)
            return {0: SUCCESS, 1: WARNING, 2: FAILED}.get(val)
        except ValueError:
            return {"success": SUCCESS, "fail": FAILED, "failed": FAILED, "failure": FAILED,
                    "warn": WARNING, "warning": WARNING}.get(val.lower(), FAILED)

    @property
    def val(self):
        return self._val

    @property
    def hint(self):
        return ["SUCCESS", "WARNING", "FAILED"][self.val]

    @property
    def emoji(self):
        return [":white_check_mark:", ":bug:", ":x:"][self.val]


FAILED = ACResult(2)
WARNING = ACResult(1)
SUCCESS = ACResult(0)
