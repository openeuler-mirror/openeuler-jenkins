#!/usr/bin/python3
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
# Description: pkgship and check_abi
# **********************************************************************************
"""
import os
import sys
import argparse
import logging
import shutil
import tempfile
import subprocess

class CheckConfig(object):
    """check config file"""
    def __init__(self, old_rpm, new_rpm, work_path="/var/tmp", output_file="/var/tmp/config_change.md"):
        self._output_file = output_file
        self._old_rpm = old_rpm
        self._new_rpm = new_rpm
        self._remove_file = set()
        self._add_file = set()
        self._need_check_file = set()
        self._work_path = work_path
        self._add_configs = {}
        self._delete_configs = {}
        self._changed_configs = {}
        self._not_understand_configs = {}
        self._have_found_changed_info = False

    def do_check(self, name, config_files):
        """
        Check files
        """
        new_dict = {}
        old_dict = {}
        old_conf = open(config_files[0])
        understand_configs = ""
        for line in old_conf:  # 建立旧包字典
            if "=" in line and line.split()[0] != "#":
                a_b = line.split('=', 1)
                if len(a_b) == 2:
                    old_dict[a_b[0].strip()] = a_b[1].strip()
                elif len(a_b) != 1:
                    understand_configs = understand_configs + "in old file:" + line + "\n"
        old_conf.close()

        new_conf = open(config_files[1])
        for line in new_conf:  # 建立新包字典
            if "=" in line and line.split()[0] != "#":  # 忽略注释
                a_b = line.split('=', 1)
                if len(a_b) == 2:
                    new_dict[a_b[0].strip()] = a_b[1].strip()
                elif len(a_b) != 1:
                    understand_configs = understand_configs + " in new file:" + line + "\n"
        new_conf.close()
        if len(understand_configs):
            self._not_understand_configs[name] = understand_configs
            logging.debug("\n---not_understand_configs:%s----", self._not_understand_configs)

        changed_configs = ""
        add_configs = ""
        del_configs = ""
        for key in new_dict.keys():  # 修改的内容
            if old_dict.get(key) is not None:
                if old_dict[key] != new_dict[key]:
                    changed_configs = changed_configs + "Key:" + key + "  Old_value:" +\
                     old_dict[key] + "  New_value:" + new_dict[key] + "\n"
                old_dict.pop(key)
            else:
                add_configs = add_configs + "Key:" + key + "  Value:" + new_dict[key] + "\n"
        if len(changed_configs):
            self._changed_configs[name] = changed_configs
            logging.debug("\n---changed_configs:%s----", self._changed_configs)
        if len(add_configs):
            self._add_configs[name] = add_configs
            logging.debug("\n---add_configs:%s----", self._add_configs)
        for key in old_dict:  # 删除的内容
            del_configs = del_configs + "Key:" + key + "  Value:" + old_dict[key] + "\n"
        if len(del_configs):
            self._delete_configs[name] = del_configs
            logging.debug("\n---delete_configs:%s----", self._delete_configs)

    def _md5_check(self, old_rpm, new_rpm):
        """
        Check md5sum
        """
        old_md5 = subprocess.run(['md5sum', old_rpm], stdout=subprocess.PIPE, encoding='utf-8')
        new_md5 = subprocess.run(['md5sum', new_rpm], stdout=subprocess.PIPE, encoding='utf-8')
        return old_md5.stdout.split()[0] == new_md5.stdout.split()[0]

    def _check_diff(self, old_and_new_path):
        """
        Check diff file
        """
        for name in self._need_check_file:
            name = name.split("/", 1)[-1].split()[0]
            logging.debug("path:%s", old_and_new_path)
            if self._md5_check(os.path.join(old_and_new_path[0], name), os.path.join(old_and_new_path[1], name)):
                continue
            else:
                config_files = [os.path.join(x, name) for x in old_and_new_path]
                self.do_check(name, config_files)

    def _prepare(self, temp_path):
        """
        Prepare for rpm2cpio
        """
        old_and_new_path = [os.path.join(temp_path, x) for x in ["old", "new"]]
        _ = [os.makedirs(x) for x in old_and_new_path]
        rpms = [self._old_rpm, self._new_rpm]
        _ = [subprocess.run('cd {}; rpm2cpio {} | cpio -di > /dev/null 2>&1'.format(x[0], x[1]), 
            shell=True) for x in zip(old_and_new_path, rpms)]
        logging.debug("\n---old version path:%s   new version path:%s----", old_and_new_path[0], old_and_new_path[1])
        return old_and_new_path

    def _write_content(self, ofile, infos):
        """
        Write file
        """
        self._have_found_changed_info = True
        for name in infos:
            ofile.write("In " + name + ":\n")
            ofile.write(infos[name])
        ofile.write("\n")

    def _write_result(self):
        """
        Write result
        """
        ofile = open(self._output_file, "a+")
        if self._remove_file:
            ofile.write("# Delete config files:\n")
            ofile.writelines(self._remove_file)
        if self._add_file:
            ofile.write("# Add config files:\n")
            ofile.writelines(self._add_file)
        if self._add_configs:
            ofile.write("# Add configs:\n")
            self._write_content(ofile, self._add_configs)
        if self._delete_configs:
            ofile.write("# Delete configs:\n")
            self._write_content(ofile, self._delete_configs)
        if self._changed_configs:
            ofile.write("# Changed configs:\n")
            self._write_content(ofile, self._changed_configs)
        if self._not_understand_configs:
            ofile.write("# No understand configs:\n")
            self._write_content(ofile, self._not_understand_configs)
        if self._have_found_changed_info:
            logging.info("\n---Change infos write at:%s----", self._output_file)
        else:
            logging.info("\n---Configs are same----")
        ofile.close()
    
    def _get_rpms(self, rpm_url, dest):
        """
        Get rpm path
        """
        rpm_path = ""
        if os.path.isfile(rpm_url):
            rpm_path = os.path.abspath(rpm_url)
        else:
            rpm_name = os.path.basename(rpm_url)
            rpm_path = os.path.join(dest, rpm_name)
            logging.info("downloading %s ...", rpm_name)
            subprocess.run("wget -t 5 -c -P {} {}".format(dest, rpm_url), shell=True)
        return rpm_path

    def conf_check(self):
        """
        Begin check
        """
        temp_path = os.path.abspath(tempfile.mkdtemp(dir=self._work_path))
        self._old_rpm = self._get_rpms(self._old_rpm, temp_path)
        self._new_rpm = self._get_rpms(self._new_rpm, temp_path)
        try:
            if self._md5_check(self._old_rpm, self._new_rpm):
                logging.info("Same RPM")
                return
            old_config = subprocess.run(['rpm', '-qpc', self._old_rpm], stdout=subprocess.PIPE, encoding='utf-8')
            new_config = subprocess.run(['rpm', '-qpc', self._new_rpm], stdout=subprocess.PIPE, encoding='utf-8')
            for line in old_config.stdout.split():
                self._remove_file.add(line)
            for line in new_config.stdout.split():
                if line in self._remove_file:
                    self._remove_file.remove(line)
                    self._need_check_file.add(line)
                else:
                    self._add_file.add(line)

            if self._need_check_file:
                old_and_new_path = self._prepare(temp_path)
                self._check_diff(old_and_new_path)
            self._write_result()
        except FileNotFoundError:
            logging.error("file not found")
        shutil.rmtree(temp_path)


def parse_command_line():
    """Parse the command line args"""
    parser = argparse.ArgumentParser(prog="check_conf")

    parser.add_argument("-o", "--old_rpm", required=True, help="The old version rpm.")
    parser.add_argument("-n", "--new_rpm", required=True, help="The new version rpm.")
    parser.add_argument("-p", "--work_path", default="/var/tmp", nargs="?",
                        help="The work path to put rpm2cpio files and results")
    parser.add_argument("-v", "--verbose", action="store_true", default=False,
                        help="Show additional information")
    args = parser.parse_args()
    return args


def main():
    """
    Entry point for check_conf
    """
    args = parse_command_line()
    if args.verbose:
        logging.basicConfig(format='%(message)s', level=logging.DEBUG)
    else:
        logging.basicConfig(format='%(message)s', level=logging.INFO)
    work_path = os.path.abspath(args.work_path)
    check_conf = CheckConfig(args.old_rpm, args.new_rpm, work_path)
    check_conf.conf_check()

if __name__ == "__main__":
    main()
