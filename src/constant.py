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
# Create: 2021-12-22
# Description: class Constant
# **********************************************************************************
"""

class Constant(object):
    """
    class Constant
    """

    GITEE_BRANCH_PROJECT_MAPPING = {
        "master": ["bringInRely", "openEuler:Extras", "openEuler:Factory", "openEuler:Mainline", "openEuler:Epol"],
        "openEuler-20.03-LTS": ["openEuler:20.03:LTS"],
        "openEuler-20.03-LTS-Next": ["openEuler:20.03:LTS:Next", "openEuler:20.03:LTS:Next:Epol"],
        "openEuler-EPOL-LTS": ["bringInRely"],
        "openEuler-20.09": ["openEuler:20.09", "openEuler:20.09:Epol", "openEuler:20.09:Extras"],
        "mkopeneuler-20.03": ["openEuler:Extras"],
        "openEuler-20.03-LTS-SP1": ["openEuler:20.03:LTS:SP1", "openEuler:20.03:LTS:SP1:Epol",
            "openEuler:20.03:LTS:SP1:Extras"],
        "openEuler-20.03-LTS-SP2": ["openEuler:20.03:LTS:SP2", "openEuler:20.03:LTS:SP2:Epol",
            "openEuler:20.03:LTS:SP2:Extras"],
        "openEuler-21.03": ["openEuler:21.03", "openEuler:21.03:Epol", "openEuler:21.03:Extras"],
        "openEuler-21.09": ["openEuler:21.09", "openEuler:21.09:Epol", "openEuler:21.09:Extras"],
        "oepkg_openstack-common_oe-20.03-LTS-SP2": ["openEuler:20.03:LTS:SP2:oepkg:openstack:common"],
        "oepkg_openstack-queens_oe-20.03-LTS-SP2": ["openEuler:20.03:LTS:SP2:oepkg:openstack:queens"],
        "oepkg_openstack-rocky_oe-20.03-LTS-SP2": ["openEuler:20.03:LTS:SP2:oepkg:openstack:rocky"],
        "oepkg_openstack-common_oe-20.03-LTS-Next": ["openEuler:20.03:LTS:Next:oepkg:openstack:common"],
        "oepkg_openstack-queens_oe-20.03-LTS-Next": ["openEuler:20.03:LTS:Next:oepkg:openstack:queens"],
        "oepkg_openstack-rocky_oe-20.03-LTS-Next": ["openEuler:20.03:LTS:Next:oepkg:openstack:rocky"],
        "oepkg_openstack-common_oe-20.03-LTS-SP3": ["openEuler:20.03:LTS:SP3:oepkg:openstack:common"],
        "oepkg_openstack-queens_oe-20.03-LTS-SP3": ["openEuler:20.03:LTS:SP3:oepkg:openstack:queens"],
        "oepkg_openstack-rocky_oe-20.03-LTS-SP3": ["openEuler:20.03:LTS:SP3:oepkg:openstack:rocky"],
        "openEuler-20.03-LTS-SP3": ["openEuler:20.03:LTS:SP3", "openEuler:20.03:LTS:SP3:Epol"],
        "openEuler-22.03-LTS-Next": ["openEuler:22.03:LTS:Next", "openEuler:22.03:LTS:Next:Epol"],
        "Multi-Version_OpenStack-Train_openEuler-22.03-LTS-Next": ["openEuler:22.03:LTS:Next:Epol:Multi-Version:OpenStack:Train"],
        "Multi-Version_OpenStack-Wallaby_openEuler-22.03-LTS-Next": ["openEuler:22.03:LTS:Next:Epol:Multi-Version:OpenStack:Wallaby"]
    }

    COMPARE_PACKAGE_BLACKLIST = [
        r'^/etc/ima/digest_lists/0-metadata_list-compact*',
        r'^/etc/ima/digest_lists.tlv/0-metadata_list-compact_tlv*'
    ]
