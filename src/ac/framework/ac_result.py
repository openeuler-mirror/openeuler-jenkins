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
# Create: 2020-09-23
# Description: access control list base class
# **********************************************************************************
"""


class ACResult(object):
    """
    Use this variables (FAILED, WARNING, SUCCESS， EXCLUDE) at most time,
    and don't new ACResult unless you have specific needs.
    """
    def __init__(self, val, details=None):
        self._val = val
        self._details = details or []

    def __add__(self, other):
        combined_details = list(self._details) + list(other._details)
        if self.val >= other.val:
            winner = ACResult(self.val, combined_details)
        else:
            winner = ACResult(other.val, combined_details)
        return winner

    def __eq__(self, other):
        if isinstance(other, ACResult):
            return self._val == other._val
        return NotImplemented

    def __hash__(self):
        return hash(self._val)

    def __ne__(self, other):
        if isinstance(other, ACResult):
            return self._val != other._val
        return NotImplemented

    def __str__(self):
        return self.hint

    def __repr__(self):
        return self.__str__()

    @classmethod
    def get_instance(cls, val):
        """
        
        :param val: 0/1/2/3/True/False/success/fail/warn
        :return: instance of ACResult
        """
        if isinstance(val, int):
            return {0: SUCCESS, 1: WARNING, 2: FAILED, 3: EXCLUDE}.get(val)
        if isinstance(val, bool):
            return {True: SUCCESS, False: FAILED}.get(val)

        try:
            val = int(val)
            return {0: SUCCESS, 1: WARNING, 2: FAILED, 3: EXCLUDE}.get(val)
        except ValueError:
            return {"success": SUCCESS, "fail": FAILED, "failed": FAILED, "failure": FAILED, "exclude": EXCLUDE,
                    "warn": WARNING, "warning": WARNING}.get(val.lower(), FAILED)

    @property
    def val(self):
        return self._val

    @property
    def hint(self):
        return ["SUCCESS", "WARNING", "FAILED", "EXCLUDE"][self.val]

    @property
    def emoji(self):
        return ["&#9989;", "&#9888;", "&#10060;", ":ballot_box_with_check:"][self.val]

    @property
    def details(self):
        """失败/警告的详细原因列表"""
        return self._details


EXCLUDE = ACResult(3)
FAILED = ACResult(2)
WARNING = ACResult(1)
SUCCESS = ACResult(0)
