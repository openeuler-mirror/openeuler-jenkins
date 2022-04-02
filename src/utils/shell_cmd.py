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
# Create: 2021-02-07
# Description: shell cmd
# **********************************************************************************
"""

import logging
import subprocess


logger = logging.getLogger("common")
no_fmt_logger = logging.getLogger("no_fmt")


def shell_cmd(cmd, inmsg=None):
    """
    创建子进程执行命令，返回执行结果
    :param cmd: 命令
    :param inmsg: 输入
    :return:
    """
    logger.debug("exec cmd -- [%s]", cmd)
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    if inmsg:
        p.stdin.write(inmsg)
    out, err = p.communicate()
    logger.debug("iret: %s, rs: %s, err: %s", p.returncode, out, err)

    return p.returncode, out, err


def shell_cmd_live(cmd, cap_in=None, cap_out=False, cap_err=False, verbose=False, cmd_verbose=True):
    """
    创建子进程执行命令，实时输出结果
    :param cmd: 命令
    :param cap_in: 输入
    :param cap_out: 是否捕捉输出结果
    :param cap_err: 是否捕捉错误结果
    :param verbose: show cmd output to console, default not
    :return:
    """
    if cmd_verbose:
        logger.debug("exec cmd -- %s", cmd)

    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    if cap_in:
        p.stdin.write(cap_in)

    out = []
    while True:
        if p.poll() is not None:
            break
        while True:
            line = p.stdout.readline()
            if line:
                line = line.decode("utf-8", errors="ignore")
                line = line.strip()
                _ = no_fmt_logger.info(line) if verbose else no_fmt_logger.debug(line)
                if cap_out and line and line != "\n":
                    out.append(line)
            else:
                break

    if cap_out:
        logger.debug("total %s lines output", len(out))

    ret = p.poll()

    err = None
    if ret:
        logger.debug("return code %s", ret)
        while True:
            line = p.stderr.readline()
            if not line:
                break
            err = line.decode("utf-8", errors="ignore").strip()
            _ = no_fmt_logger.error(err) if verbose else no_fmt_logger.debug(err)

    return ret, out, err if cap_err else None
