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
# Create: 2020-12-22
# Description: one kind of json that support access value with continue dot attribute
# **********************************************************************************
"""

import collections


class DotJson(object):
    """
    one kind of json that support access value with continue dot attribute
    """
    def __init__(self, data=None):
        """
        初始化
        :param data: Mapping or Sequence
        """
        if isinstance(data, collections.Mapping):
            self._data = dict(data)
        elif isinstance(data, collections.MutableSequence):
            self._data = list(data)
        elif data is None:
            self._data = dict()
        else:
            raise Exception("init with type {} not support".format(type(data)))

    def to_dict(self):
        """
        dict格式
        :return:
        """
        return self._data

    def __str__(self):
        """

        :return:
        """
        return str(self._data)

    def __getitem__(self, item):
        """
        支持"."符号连接的嵌套属性取值
        :param item:
        :return:
        """
        if isinstance(item, int):
            return self.__class__.build(self._data[item])

        s = self
        for attr in item.split("."):        # eg: item = "a.0.b"
            s = s.get(attr)

        return s

    def get(self, item):
        """
        取值辅助函数
        :param item:
        :return:
        """
        if isinstance(self._data, collections.MutableSequence) and item.isdigit():    # 嵌套属性中的数字分量
            item = int(item)

        return self.__class__.build(self._data[item])

    def __getattr__(self, item):
        """
        获取属性
        :param item:
        :return:
        """
        try:
            return self[item]
        except (IndexError, KeyError, TypeError) as e:
            raise AttributeError(e)

    @classmethod
    def build(cls, obj):
        """
        自举
        :param obj:
        :return:
        """
        return cls(obj) if isinstance(obj, (collections.Mapping, collections.MutableSequence)) else obj


class MutableDotJson(DotJson):
    """
    可变
    """
    def __setitem__(self, key, value):
        """
        赋值
        :param key:
        :param value:
        :return:
        """
        s = self._data
        attrs = key.split(".")
        for attr in attrs[:-1]:
            if isinstance(s, collections.MutableMapping):
                if attr not in s:
                    s[attr] = {}
                s = s[attr]
            elif isinstance(s, collections.MutableSequence):
                if attr.isdigit():
                    s = s[int(attr)]
                else:
                    # set Sequence, but index is not digit
                    raise TypeError("list indices must be integers or slices, not str")
            else:
                # object is not Sequence or Mapping
                raise TypeError("set value for {} not support".format(type(s)))

        last_attr = attrs[-1]
        s[last_attr] = value
