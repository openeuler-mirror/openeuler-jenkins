#!/usr/bin/python3
#******************************************************************************
# Copyright (c) Huawei Technologies Co., Ltd. 2020-2020. All rights reserved.
# licensed under the Mulan PSL v2.
# You can use this software according to the terms and conditions of the Mulan PSL v2.
# You may obtain a copy of Mulan PSL v2 at:
#     http://license.coscl.org.cn/MulanPSL2
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY OR FIT FOR A PARTICULAR
# PURPOSE.
# See the Mulan PSL v2 for more details.
# Author: wangchuangGG
# Create: 2020-07-20
# ******************************************************************************/

"""
(1) This script is used to check the ABI changes between the old
    and new versions of dynamic libraries.
    The merged result on difference is saved in the xxx_all_abidiff.out file in the working
    directory.
    default path: /var/tmp/xxx_all_abidiff.md

(2) This script depends on abidiff from libabigail package.

(3) Command parameters
    This script accept three kinds of command: compare_rpm or compare_so or compare_rpms
    Run it without any paramter prints out help message.
"""

import argparse
import subprocess
import sys
import os
import logging
import shutil
import tempfile
import re

class CheckAbi(object):
    """check abi functions"""

    def __init__(self, work_path="/var/tmp/", result_output_file=None, show_all_info=False,
                 verbose=False, input_rpms_path=None):
        self.work_path = work_path
        self.result_output_file = result_output_file
        self.show_all_info = show_all_info
        self.verbose = verbose
        self.input_rpms_path = input_rpms_path
        self.target_sos = set()
        self.changed_sos = set()
        self.diff_result_file = ""
			
    def list_so_files(self, path, add_global):
        """
        Generate a list of all .so files in the directory.
        """
        # known suffix of exception
        # we cannot rely on number suffix for some .so files use complex version scheme.
        exception_list = ["hmac", "debug", "socket"]
        so_files = set()
        for dirpath, _, files in os.walk(path):
            for filename in files:
                fp = os.path.join(dirpath, filename)
                if os.path.islink(fp):
                    continue
                if filename.split(".")[-1] in exception_list:
                    continue
                if ".so." in filename or filename.endswith(".so"):
                    logging.debug(".so file found:%s", fp)
                    so_files.add(fp)
                    if add_global:
                        self.target_sos.add(filename)
        return so_files

    def find_all_so_file(self, path1, path2):
        """
        Generate a map between previous and current so files
        """
        all_so_pair = {}
        previous_sos = self.list_so_files(path1, True)
        current_sos = self.list_so_files(path2, True)
        logging.debug("previous_so:%s", previous_sos)
        logging.debug("current_so:%s", current_sos)
        prev_matched = set()
        curr_matched = set()
        if previous_sos and current_sos:
            for so_file1 in previous_sos:
                for so_file2 in current_sos:
                    base_name1 = (os.path.basename(so_file1)).split('.so')[0]
                    base_name2 = (os.path.basename(so_file2)).split('.so')[0]
                    if base_name1 == base_name2:
                        all_so_pair[so_file1] = so_file2
                        prev_matched.add(so_file1)
                        curr_matched.add(so_file2)
        else:
            logging.info("Not found so files")
            return all_so_pair

        prev_left = previous_sos - prev_matched
        curr_left = current_sos - curr_matched

        if prev_left:
            logging.info("Unmatched .so file in previous version")
            logging.info("Usually means deleted .so in current version")
            logging.info("%s\n", prev_left)
            for so_name in prev_left:
                self.changed_sos.add(os.path.basename(so_name))
        if curr_left:
            logging.info("Unmatched .so file in current version")
            logging.info("Usually means newly added .so in current version")
            logging.info("%s\n", curr_left)
        logging.debug("mapping of .so files:%s\n", all_so_pair)
        return all_so_pair

    def make_abi_path(self, temp_path, abipath):
        """
        Get the path to put so file from rpm
        return the path.
        """
        fp = os.path.join(temp_path, abipath)
        if os.path.isdir(fp):
            shutil.rmtree(fp)
        os.makedirs(fp)
        return fp

    def get_rpm_path(self, rpm_url, dest):
        """Get the path of rpm package"""
        rpm_path = ""
        if os.path.isfile(rpm_url):
            rpm_path = os.path.abspath(rpm_url)
            logging.debug("rpm exists:%s", rpm_path)
        else:
            rpm_name = os.path.basename(rpm_url)
            rpm_path = os.path.join(dest, rpm_name)
            logging.info("downloading %s......", rpm_name)
            subprocess.run("wget -t 5 -c -P {} {}".format(dest, rpm_url), shell=True)
        return rpm_path

    def do_rpm2cpio(self, rpm2cpio_path, rpm_file):
        """
        Exec the rpm2cpio at rpm2cpio_path.
        """
        cur_dir = os.getcwd()
        os.chdir(rpm2cpio_path)
        logging.debug("\n----working in path:%s----", os.getcwd())
        logging.debug("rpm2cpio %s", rpm_file)
        subprocess.run("rpm2cpio {} | cpio -id > /dev/null 2>&1".format(rpm_file), shell=True)
        os.chdir(cur_dir)

    def merge_all_abidiff_files(self, all_abidiff_files, rpm_base_name):
        """
        Merge the all diff files to merged_file.
        return the merged_file.
        """
        merged_file = os.path.join(self.work_path, "{}_all_abidiff.out".format(rpm_base_name))
        if os.path.exists(merged_file):
            subprocess.run("rm -rf {}".format(merged_file), shell=True)

        ofile = open(merged_file, "a+")
        ofile.write("# Functions changed info\n")
        for diff_file in all_abidiff_files:
            diff_file_name = os.path.basename(diff_file)
            ofile.write("---------------diffs in {}:----------------\n".format(diff_file_name))
            for txt in open(diff_file, "r"):
                ofile.write(txt)
        ofile.close()
        return merged_file

    def do_abidiff(self, all_so_pair, base_name, debuginfo_path):
        """
        Exec the abidiff and write result to files.
        return the abidiff returncode.
        """
        if not all_so_pair:
            logging.info("There are no .so files to compare")
            return 0

        if debuginfo_path:
            logging.debug("old_debuginfo_path:%s\nnew_debuginfo_path:%s",
                          debuginfo_path[0], debuginfo_path[1])
            with_debuginfo = True
        else:
            with_debuginfo = False

        return_code = 0
        all_abidiff_files = []
        for old_so_file in all_so_pair:
            new_so_file = all_so_pair[old_so_file]
            logging.debug("begin abidiff between %s and %s", old_so_file, new_so_file)

            abidiff_file = os.path.join(self.work_path,
                                        "{}_{}_abidiff.out".format(base_name,
                                                                   os.path.basename(new_so_file)))

            so_options = "{} {}".format(old_so_file, new_so_file)

            if self.show_all_info:
                additional_options = "--harmless"
            else:
                additional_options = "--changed-fns --deleted-fns --added-fns"

            if with_debuginfo:
                debug_options = "--d1 {} --d2 {}".format(debuginfo_path[0], debuginfo_path[1])
            else:
                debug_options = ""

            abidiff_template = "abidiff {so_options} {debug_options} {additional_options} > {difffile}"
            abidiff_cmd = abidiff_template.format(so_options=so_options,
                                                  debug_options=debug_options,
                                                  additional_options=additional_options,
                                                  difffile=abidiff_file)

            ret = subprocess.run(abidiff_cmd, shell=True)

            all_abidiff_files.append(abidiff_file)
            logging.info("result write in: %s, returncode:%d", abidiff_file, ret.returncode)
            return_code |= ret.returncode
        if not return_code in [0, 1]:
            self.diff_result_file = self.merge_all_abidiff_files(all_abidiff_files, base_name)
            logging.info("abidiff all results writed in: %s", self.diff_result_file)
        return return_code

    def scan_target_functions_with_so(self, so_file, temp_path, rpm_require_functions, diff_functions):
        """
        Scan target functions witch the .so file require
        """
        require_func_file = os.path.join(temp_path, "calls_func_file.txt")
        subprocess.run("nm -D -C -u {} > {}".format(so_file, require_func_file), shell=True)
        with open(require_func_file, 'r') as fd:
            lines = fd.readlines()
            fd.close()

        for func_name in diff_functions:
            for line in lines:
                if func_name in re.split(r'[(<:\s]', line):
                    rpm_require_functions.add(func_name)
        
    def check_rpm_require_taget_functions(self, rpm_package, temp_path, rpm_require_functions, diff_functions):
        """
        Check whether the rpm package calls target functions
        """
        if not os.path.exists(rpm_package) or not rpm_package.endswith(".rpm"):
            logging.error("the rpm_package not exists:%s", rpm_package)
            return False
        logging.debug("\n----check the rpm whether calls diff_functions:%s----", rpm_package)

        rpm2cpio_path = os.path.join(temp_path, "other_rpm2cpio")
        if os.path.exists(rpm2cpio_path):
            shutil.rmtree(rpm2cpio_path)
        os.makedirs(rpm2cpio_path, exist_ok=True)

        self.do_rpm2cpio(rpm2cpio_path, rpm_package)
        so_files = self.list_so_files(rpm2cpio_path, False)

        for so_file in so_files:
            self.scan_target_functions_with_so(so_file, temp_path, rpm_require_functions, diff_functions)

        if rpm_require_functions:
            logging.debug("the rpm require target functions:%s", rpm_require_functions)
            return True
        logging.debug("the rpm not calls diff_functions")
        return False

    def scan_diff_functions(self):
        """
        Scan all diff functions
        """
        diff_functions = set()
        if len(self.diff_result_file) == 0:
            return diff_functions
        with open(self.diff_result_file, 'r') as fd:
            lines = fd.readlines()
            fd.close()
        for line in lines:
            if "(" in line and ("function " in line or "method " in line):
                func_name = line.split("(")[0].split()[-1].split("<")[0].split("::")[-1]
                if func_name != "void":
                    diff_functions.add(func_name)
            if "SONAME changed from" in line:
                old_so_name = line.split(" to ")[0].split()[-1].replace("'", "")
                self.changed_sos.add(old_so_name)
                logging.debug("------ changed_sos:%s ------", self.changed_sos)
        logging.debug("all_diff_functions:%s", diff_functions)
        return diff_functions

    def check_rpm_require_changed_sos(self, rpm_package, require_sos, rpm_base_name):
        """
        Check if the rpm require changed .so files
        """
        require_changed_sos = False
        write_name = os.path.basename(rpm_package) + " require these .so files witch version changed:"
        for so_name in self.changed_sos:
            base_name = so_name.split(".so")[0]
            if base_name in require_sos:
                logging.debug("this rpm require changed .so file:%s", base_name)
                require_changed_sos = True
                write_name += (" " + so_name)

        if require_changed_sos:
            effect_info_file = os.path.join(self.work_path, "{}_sos_changed_effect_rpms.out".format(rpm_base_name))
            if not os.path.exists(effect_info_file):
                f = open(effect_info_file, "a+", encoding="utf-8")
                f.write("# RPMS effected by .so version changed\n")
                f.close()
            else:
                f = open(effect_info_file, "a+", encoding="utf-8")
                f.write("{}\n".format(write_name))
                f.close()
            logging.info("sos changed effect rpms write at:%s", effect_info_file)
        return require_changed_sos

    def check_rpm_require_taget_sos(self, rpm_package, temp_path, base_name):
        """
        Check if the rpm require target .so files
        """
        if not os.path.exists(rpm_package) or not rpm_package.endswith(".rpm"):
            logging.error("the rpm_package not exists:%s", rpm_package)
            return False

        #logging.debug("\n---check if the rpm require target .so files:%s---", rpm_package)
        require_info_file = os.path.join(temp_path, "require_info_file.txt")
        subprocess.run("rpm -qpR {} > {}".format(rpm_package, require_info_file), shell=True, stderr=subprocess.PIPE)
        logging.debug("write require .sos info at:%s", require_info_file)

        with open(require_info_file, 'r') as fd:
            lines = fd.readlines()
            fd.close()
        require_sos = set()
        for line in lines:
            require_so_name = re.split(r'[(.><\s]', line)[0]
            require_sos.add(require_so_name)
        logging.debug("\n------%s this rpm require .so files:%s", rpm_package, require_sos)

        if self.check_rpm_require_changed_sos(rpm_package, require_sos, base_name):
            return True

        for so_name in self.target_sos:
            so_base_name = so_name.split(".so")[0]
            if so_base_name in require_sos:
                logging.debug("this rpm call target .so file:%s", so_base_name)
                return True
        logging.debug("this rpm not require target .so files")
        return False
    
    def validate_sos(self, sos, debuginfo_path):
        """
        Validate the command arguments
        """
        for so in sos:
            if not os.path.isfile(so) or ".so" not in so:
                logging.error("{so} not exists or not a .so file")
                sys.exit(0)

        if debuginfo_path:
            for d in debuginfo_path:
                if not os.path.exists(d):
                    logging.error("{d} not exists")
                    sys.exit(0)

    def check_result(self, returncode):
        """
        Check the result of abidiff
        """
        ABIDIFF_ERROR_BIT = 1
        if returncode == 0:
            logging.info("No ABI differences found.")
        elif returncode & ABIDIFF_ERROR_BIT:
            logging.info("An unexpected error happened to abidiff")
        else:
            logging.info("ABI differences found.")

    def find_target_rpms(self, rpms_path, temp_path, base_name):
        """
        Find target rpms witch requires target .so files
        """
        logging.debug("finding target rpms in all rpms, target sos:%s............", self.target_sos)
        target_rpms = set()
        for dirpath, dirnames, files in os.walk(rpms_path):
            file_number = len(files)
            count = 0
            for filename in files:
                count = count + 1
                logging.info("[%d/%d] check target rpms: %s", count, file_number, filename)
                fp = os.path.join(dirpath, filename)
                if fp.endswith(".rpm"):
                    if self.check_rpm_require_taget_sos(fp, temp_path, base_name):
                        target_rpms.add(fp)
        logging.debug("all rpms name whitch calls target .so files:%s", target_rpms)
        return target_rpms

    def find_effect_rpms(self, rpms_require_target_sos, temp_path, diff_functions):
        """
        Find rpms witch requires target functions
        """
        effect_rpms = set()
        rpm_number = len(rpms_require_target_sos)
        count = 0
        for rpm_package in rpms_require_target_sos:
            rpm_require_functions = set()
            count = count + 1
            logging.info("[%d/%d] check effect rpms: %s", count, rpm_number, os.path.basename(rpm_package))
            if self.check_rpm_require_taget_functions(rpm_package, temp_path,
                                    rpm_require_functions, diff_functions):
                write_name = os.path.basename(rpm_package) + ":"
                for func in rpm_require_functions:
                    write_name += (" " + func)
                effect_rpms.add(write_name)
        logging.debug("all effect rpms:%s", effect_rpms)
        return effect_rpms

    def scan_old_rpms(self, rpms_dir):
        """
        Scan all old rpms
        """
        files = os.listdir(rpms_dir)
        rpm_names = set()
        for file_name in files:
            if file_name.endswith(".rpm") and "-debuginfo-" not in file_name and "-help-" not in file_name:
                rpm_names.add(os.path.join(rpms_dir, file_name))
        logging.debug("all old rpms:%s", rpm_names)
        return rpm_names

    def find_new_rpm(self, old_rpm_name, rpms_dir):
        """
        Find new rpm by old rpm name
        """
        old_rpm_basename = os.path.basename(old_rpm_name)
        base_name1 = old_rpm_basename.rsplit("-", 2)[0]
        arch_name1 = old_rpm_basename.split(".oe1.")[-1]
        logging.info("\n------begin process rpm:%s------", old_rpm_basename)
        files = os.listdir(rpms_dir)
        for file_name in files:
            if file_name.endswith(".rpm") and "-debuginfo-" not in file_name and "-help-" not in file_name:
                base_name2 = file_name.rsplit("-", 2)[0]
                arch_name2 = file_name.split(".oe1.")[-1]
                if base_name1 == base_name2 and arch_name1 == arch_name2:
                    logging.debug("find new rpms:%s", file_name)
                    return os.path.join(rpms_dir, file_name)
        return None
    
    def find_debug_rpm(self, rpm_name, rpms_dir):
        """
        Find debuginfo rpm by rpm name
        """
        files = os.listdir(rpms_dir)
        for file_name in files:
            if file_name.endswith(".rpm") and "-debuginfo-" in file_name:
                file_basename = file_name.replace("-debuginfo-", "-")
                if file_basename == os.path.basename(rpm_name):
                    return os.path.join(rpms_dir, file_name)
        return None

    def write_result(self, result_file, merged_file):
        """
        Write content ro file
        """
        if os.path.exists(result_file):
            with open(result_file, "r") as fd:
                lines = fd.readlines()
                fd.close()
            ofile = open(merged_file, "a+")
            for line in lines:
                ofile.write(line)
                ofile.write("\n")
            ofile.close()
    
    def merge_all_result(self, base_name):
        """
        Merge all result files to a .md file
        """
        files_last_name = ["_sos_changed_effect_rpms.out", "_effect_rpms_list.out", "_all_abidiff.out"]
        result_files = [os.path.join(self.work_path, "{}{}".format(base_name, x)) for x in files_last_name]
        logging.debug("result_files:%s", result_files)

        merged_file = os.path.join(self.work_path, "{}_all_result.md".format(base_name))

        if self.result_output_file:
            merged_file = os.path.abspath(self.result_output_file)
        if os.path.exists(merged_file):
            subprocess.run("rm -rf {}".format(merged_file), shell=True)
        _ = [self.write_result(x, merged_file) for x in result_files]
        logging.info("-------------all result write at:%s", merged_file)

    def get_rpms_path(self, rpms_url, dest):
        """Get the path of rpm packages"""
        if type(rpms_url) is str and os.path.isdir(rpms_url):
            logging.debug("rpm exists:%s", rpms_url)
            return os.path.abspath(rpms_url)
        else:
            use_args = "-t 5 -r -c -np -nH -nd -R index.html"
            if type(rpms_url) is str:
                subprocess.run("wget {} -P {} {} > /dev/null 2>&1".format(use_args, dest, rpms_url), shell=True)
            else:
                count = 0
                need_download = len(rpms_url)
                for url in rpms_url:
                    count += 1
                    logging.info("[%d/%d] downloading %s", count, need_download, os.path.basename(url))
                    subprocess.run("wget {} -P {} {} > /dev/null 2>&1".format(use_args, dest, url),
                                    shell=True)
            return dest

    def process_effect_rpms(self, abs_dir, base_name):
        """
        Find the rpm packages in this path
        that calls the changed interfaces
        """
        logging.debug("-------process effect rpms, abs_dir:%s---------", abs_dir)
        diff_functions = self.scan_diff_functions()
        if len(diff_functions) == 0:
            logging.info("there has no diff functions found")
            return 0
        os.chdir(abs_dir)
        temp_path = tempfile.mkdtemp(dir=self.work_path)
        target_rpms_path = os.path.join(temp_path, "Target_rpms")
        rpms_path = self.get_rpms_path(self.input_rpms_path, target_rpms_path)

        if not os.path.isdir(rpms_path):
            logging.error("the rpms_path not exists:%s", rpms_path)
            return 0

        rpms_require_target_sos = self.find_target_rpms(rpms_path, temp_path, base_name)
        effect_rpms = self.find_effect_rpms(rpms_require_target_sos, temp_path, diff_functions)

        if len(effect_rpms) != 0:
            effect_rpms_file = os.path.join(self.work_path, "{}_effect_rpms_list.out".format(base_name))
            if os.path.exists(effect_rpms_file):
                os.remove(effect_rpms_file)

            f = open(effect_rpms_file, "a+", encoding="utf-8")
            f.write("# RPMS effected by function changed\n")
            for name in effect_rpms:
                f.write("{}\n".format(name))
            f.close()

            logging.info("\neffect rpms writed at:%s", effect_rpms_file)
        logging.debug("--- delete temp directory:%s ---", temp_path)
        self.diff_result_file = ""
        self.target_sos.clear()
        self.changed_sos.clear()
        shutil.rmtree(temp_path)

    def process_with_rpm(self, rpms, debuginfo_rpm=None):
        """
        Process the file with type of rpm.
        """
        abs_dir = os.path.abspath(os.path.dirname(__file__))
        temp_path = os.path.abspath(tempfile.mkdtemp(dir=self.work_path))

        abi_paths = [self.make_abi_path(temp_path, name) for name in ["previous_package", "current_package"]]
        logging.debug("abi_paths:%s\n", abi_paths)

        rpm_path = [self.get_rpm_path(x[0], x[1]) for x in zip(rpms, abi_paths)]
        logging.debug("rpm_path:%s\n", rpm_path)

        _ = [self.do_rpm2cpio(x[0], x[1]) for x in zip(abi_paths, rpm_path)]

        if debuginfo_rpm:
            debuginfo_rpm_path = [self.get_rpm_path(x[0], x[1])
                                  for x in zip(debuginfo_rpm, abi_paths)]

            logging.debug("debuginfo_rpm_path:%s\n", debuginfo_rpm_path)

            _ = [self.do_rpm2cpio(x[0], x[1]) for x in zip(abi_paths, debuginfo_rpm_path)]

        os.chdir(temp_path)
        logging.debug("\n----begin abidiff working in path:%s----", os.getcwd())

        #so_paths = [os.path.join(x, "usr/lib64") for x in abi_paths]

        all_so_pairs = self.find_all_so_file(abi_paths[0], abi_paths[1])
        if not all_so_pairs:
            os.chdir(abs_dir)
            shutil.rmtree(temp_path)
            return 0

        debuginfo_paths = [os.path.join(x, "usr/lib/debug") for x in abi_paths]

        rpm_base_name =  os.path.basename(rpm_path[0]).rsplit("-", 2)[0]

        returncode = self.do_abidiff(all_so_pairs, rpm_base_name, debuginfo_paths)
        logging.debug("\n--- delete temp directory:%s ---", temp_path)
        os.chdir(abs_dir)
        shutil.rmtree(temp_path)
        self.check_result(returncode)
        if self.input_rpms_path:
            self.process_effect_rpms(abs_dir, rpm_base_name)
        self.merge_all_result(rpm_base_name)
        return returncode

    def process_with_rpms(self, paths):
        """
        Process all rpms with two paths
        """
        rpms_paths = list(map(os.path.abspath, paths))
        old_rpms = self.scan_old_rpms(rpms_paths[0])
        return_code = 0
        ##################
        count = 0
        Length = len(old_rpms)
        ##################
        for old_rpm_name in old_rpms:
            #################
            count += 1
            logging.info("-----------------------------total rpms:%d  curr_count:%d----------------", Length, count)
            #################
            new_rpm_name = self.find_new_rpm(old_rpm_name, rpms_paths[1])
            if new_rpm_name:
                rpms_pair = [old_rpm_name, new_rpm_name]
                debug_rpms_pair = [self.find_debug_rpm(x[0], x[1]) for x in zip(rpms_pair, rpms_paths)]
                if not debug_rpms_pair[0] or not debug_rpms_pair[1]:
                    debuginfo_rpm = None
                    logging.debug("debuginfo not exist:%s", old_rpm_name)
                else:
                    debuginfo_rpm = debug_rpms_pair
                logging.debug("rpms:%s\ndebug_rpms:%s", rpms_pair, debuginfo_rpm)
                return_code |= self.process_with_rpm(rpms_pair, debuginfo_rpm)
        return return_code
        
    def process_with_so(self, sos, debuginfo_path=None):
        """
        Process the file with type of .so.
        """
        abs_dir = os.path.abspath(os.path.dirname(__file__))
        self.validate_sos(sos, debuginfo_path)
        all_so_pair = {}
        so_path = list(map(os.path.abspath, sos))
        all_so_pair[so_path[0]] = so_path[1]

        so_base_name = os.path.basename(so_path[0]).split('.')[0]
        _ = [self.target_sos.add(os.path.basename(x)) for x in so_path]
        if debuginfo_path:
            debuginfo_paths = list(map(os.path.abspath, debuginfo_path))
        else:
            debuginfo_paths = None
        os.chdir(self.work_path)
        logging.debug("\n----begin abidiff with .so working in path:%s----", os.getcwd())
        returncode = self.do_abidiff(all_so_pair, so_base_name, debuginfo_paths)
        self.check_result(returncode)
        if self.input_rpms_path:
            self.process_effect_rpms(abs_dir, so_base_name)
        self.merge_all_result(so_base_name)
        return returncode


def parse_command_line():
    """Parse the command line arguments."""
    parser = argparse.ArgumentParser(prog="check_abi")

    parser.add_argument("-d", "--work_path", default="/var/tmp", nargs="?",
                        help="The work path to put rpm2cpio files and results"
                        " (e.g. /home/tmp_abidiff default: /var/tmp/)")
    parser.add_argument("-o", "--result_output_file", default="", nargs="?",
                        help="The result file"
                        " (e.g. /home/result.md)")
    parser.add_argument("-a", "--show_all_info", action="store_true", default=False,
                        help="show all infos includ changes in member name")
    parser.add_argument("-v", "--verbose", action="store_true", default=False,
                        help="Show additional information")
    parser.add_argument("-i", "--input_rpms_path", default="", nargs="?",
                        help="Find the rpm packages in this path or this list of url that calls this change interfaces"
                        " (e.g. /home/rpms)")

    subparser = parser.add_subparsers(dest='command_name',
                                      help="Compare between two RPMs or two .so files or two RPMs paths")

    rpm_parser = subparser.add_parser('compare_rpm', help="Compare between two RPMs")
    rpm_parser.add_argument("-r", "--rpms", required=True, nargs=2,
                            metavar=('old_rpm', 'new_rpm'),
                            help="Path or URL of both the old and new RPMs")
    rpm_parser.add_argument("-d", "--debuginfo_rpm", nargs=2,
                            metavar=('old_debuginfo_rpm', 'new_debuginfo_rpm'),
                            required=False,
                            help="Path or URL of both the old and new debuginfo RPMs,"
                            "corresponding to compared RPMs.")
    rpm_parser.set_defaults(func=process_with_rpm)

    so_parser = subparser.add_parser('compare_so', help="Compare between two .so files")
    so_parser.add_argument("-s", "--sos", required=True, nargs=2,
                           metavar=('old_so', 'new_so'),
                           help="Path or URL of both the old and new .so files")
    so_parser.add_argument("-f", "--debuginfo_path", nargs=2, required=False,
                           metavar=('old_debuginfo_path', 'new_debuginfo_path'),
                           help="Path or URL of both the old and new debuginfo files,"
                           "corresponding to compared .so files.")
    so_parser.set_defaults(func=process_with_so)

    rpms_parser = subparser.add_parser('compare_rpms', help="Compare between two RPMs paths")
    rpms_parser.add_argument("-p", "--paths", required=True, nargs=2,
                            metavar=('old_path', 'new_path'),
                            help="Path of both the old RPMs and new RPMs")
    rpms_parser.set_defaults(func=process_with_rpms)

    config = parser.parse_args()

    if config.command_name is None:
        parser.print_help()
        sys.exit(0)
    else:
        return config


def process_with_rpm(config, check_abi_process):
    """
    Process the file with type of rpm.
    """
    return check_abi_process.process_with_rpm(config.rpms, config.debuginfo_rpm)


def process_with_so(config, check_abi_process):
    """
    Process the file with type of .so.
    """
    return check_abi_process.process_with_so(config.sos, config.debuginfo_path)


def process_with_rpms(config, check_abi_process):
    """
    Process all rpms with two paths
    """
    return check_abi_process.process_with_rpms(config.paths)


def main():
    """Entry point for check_abi"""
    config = parse_command_line()
    if config.verbose:
        logging.basicConfig(format='%(message)s', level=logging.DEBUG)
    else:
        logging.basicConfig(format='%(message)s', level=logging.INFO)
    config.work_path = os.path.abspath(config.work_path)
    check_abi_process = CheckAbi(config.work_path, config.result_output_file, config.show_all_info,
                                  config.verbose, config.input_rpms_path)
    ret = config.func(config, check_abi_process)
    sys.exit(ret)


if __name__ == "__main__":
    main()
