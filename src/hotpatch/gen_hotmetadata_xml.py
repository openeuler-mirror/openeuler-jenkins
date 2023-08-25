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
# Create: 2023-07-18
# Description: Generate hot patch metadata files
# **********************************************************************************
"""
import argparse
import os
import re
import sys
import traceback
from xml.etree.ElementTree import Element
import xml.etree.ElementTree as ET
from xml.dom import minidom
from src.logger import logger
from src.proxy.gitee_proxy import GiteeProxy


def init_metadata_xml(filename):
    try:
        doc = minidom.Document()
        root = doc.createElement('hotpatchdoc')
        root.setAttribute('xmlns', meta_url)
        root.setAttribute('xmlns:cvrf', meta_url)
        doc.appendChild(root)
        with open(filename, 'w', encoding='utf-8') as xml_file:
            doc.writexml(xml_file, encoding="utf-8")
    except IOError:
        logger.error('init metadata.xml error: %s', traceback.format_exc())
        sys.exit(1)


def update_hotpatch(xml_root, hotpatch_issue):
    version, release = get_version(xml_root)
    hotpatch = Element('hotpatch')
    if mode == "ACC":
        hotpatch.attrib['version'] = version
        hotpatch.attrib['release'] = str(int(release) + 1)
    elif mode == "SGL":
        name = xml_root.find('.//hotpatch[@name="SGL-%s"]' % cve_issue_id)
        logger.warning("name=SGL-%s result:%s", cve_issue_id, name)
        if name:
            err_info = "修复issue：%s 的SGL补丁pr已经创建，请勿重复提交" % cve_issue_id
            comment_source_pr(err_info)
        hotpatch.attrib['name'] = "SGL-%s" % cve_issue_id
        hotpatch.attrib['version'] = "1"
        hotpatch.attrib['release'] = "1"

    hotpatch.attrib['type'] = patch_type
    hotpatch.attrib['inherit'] = "0"
    hotpatch.attrib['status'] = "unconfirmed"

    src_link = Element('SRC_RPM')
    src_link.text = src_url
    hotpatch.append(src_link)

    x86_debug_link = Element('Debug_RPM_X86_64')
    x86_debug_link.text = x86_url
    hotpatch.append(x86_debug_link)

    aarch64_debug_link = Element('Debug_RPM_Aarch64')
    aarch64_debug_link.text = arm_url
    hotpatch.append(aarch64_debug_link)

    for patch_file in args.patch.split(","):
        patch = Element('patch')
        patch.text = patch_file
        hotpatch.append(patch)

    issue_id = Element('issue')
    issue_id.attrib['id'] = cve_issue_id
    issue_id.attrib['issue_href'] = cve_issue_url
    hotpatch.append(issue_id)

    hotpatch_issue_link = Element('hotpatch_issue_link')
    hotpatch_issue_link.text = hotpatch_issue
    hotpatch.append(hotpatch_issue_link)

    p = xml_root.find('.//Package[@name="%s-%s"]' % (args.repo, repo_version))
    p.append(hotpatch)

    return xml_root


def new_metadata(xml_root, hotpatch_issue):
    logger.info("src_url=%s", src_url)
    logger.info("x86_url=%s", x86_url)
    logger.info("arm_url=%s", arm_url)

    DocumentTitle = Element('DocumentTitle')
    DocumentTitle.attrib['xml:lang'] = "en"
    DocumentTitle.attrib['type'] = mode

    DocumentTitle.text = "Managing Hot Patch Metadata"
    xml_root.append(DocumentTitle)

    HotPatchList = Element('HotPatchList')
    xml_root.append(HotPatchList)

    Package = Element('Package')
    Package.attrib['name'] = "%s-%s" % (args.repo, repo_version)
    HotPatchList.append(Package)

    hotpatch = Element('hotpatch')
    if mode == "SGL":
        hotpatch.attrib['name'] = "SGL-%s" % cve_issue_id

    hotpatch.attrib['version'] = "1"
    hotpatch.attrib['release'] = "1"
    hotpatch.attrib['type'] = patch_type
    hotpatch.attrib['inherit'] = "0"
    hotpatch.attrib['status'] = "unconfirmed"
    logger.info("patch_type=%s", patch_type)

    Package.append(hotpatch)

    src_link = Element('SRC_RPM')
    src_link.text = src_url
    hotpatch.append(src_link)

    x86_debug_link = Element('Debug_RPM_X86_64')
    x86_debug_link.text = x86_url
    hotpatch.append(x86_debug_link)

    aarch64_debug_link = Element('Debug_RPM_Aarch64')
    aarch64_debug_link.text = arm_url
    hotpatch.append(aarch64_debug_link)

    logger.info("patch=%s", args.patch)
    for patch_file in args.patch.split(","):
        patch = Element('patch')
        patch.text = patch_file
        logger.info("patch_file=%s", patch_file)
        hotpatch.append(patch)

    issue_id = Element('issue')
    issue_id.attrib['id'] = cve_issue_id
    issue_id.attrib['issue_href'] = cve_issue_url
    hotpatch.append(issue_id)
    logger.info("cve_issue_id=%s", cve_issue_id)
    logger.info("cve_issue_url=%s", cve_issue_url)

    hotpatch_issue_link = Element('hotpatch_issue_link')
    hotpatch_issue_link.text = hotpatch_issue
    hotpatch.append(hotpatch_issue_link)
    logger.info("hotpatch_issue_url=%s", hotpatch_issue)

    return xml_root


def get_version(xml_root):
    hotpatch = xml_root.iter('hotpatch')
    version = 0
    release = 0
    for child in hotpatch:
        version = child.attrib["version"]
        release = child.attrib["release"]

    logger.info("version: %s, release: %s", version, release)
    return version, release


def del_hotpatch(xml_root):
    hotpatch_issue_number = ''
    del_version, del_release = get_version(xml_root)
    Package = xml_root.find('.//Package[@name="%s-%s"]' % (args.repo, repo_version))
    if mode == "SGL":
        p = xml_root.find('.//hotpatch[@name="SGL-%s"][@version="%s"][@release="%s"]' % (
            cve_issue_id, del_version, del_release))
    else:
        p = xml_root.find('.//hotpatch[@version="%s"][@release="%s"]' % (del_version, del_release))

    issue_url = p.find('hotpatch_issue_link').text
    logger.info("hotpatch_issue_url exist: %s" % issue_url)
    Package.remove(p)
    if issue_url:
        hotpatch_issue_number = issue_url.split("/")[-1]
    return hotpatch_issue_number


def add_hotmetadata_xml():
    if os.path.exists(metadata_file):
        tree = ET.parse(metadata_file)
        root = tree.getroot()
        root = update_hotpatch(root, hotpatch_issue_url)
    else:
        init_metadata_xml(metadata_file)
        tree = ET.ElementTree(file=metadata_file)
        root = tree.getroot()
        root = new_metadata(root, hotpatch_issue_url)

    write_to_hotmetadata_xml(root)


def write_to_hotmetadata_xml(xml_root):
    """
    Convert the ElementTree into a formated string, and write it to the output path.
    """
    logger.info("---------------------")
    raw_text = ET.tostring(xml_root)
    dom = minidom.parseString(raw_text)
    pretty_text = dom.toprettyxml(indent='\t')
    new_pretty_text = re.sub('\n[\s|]*\n', '\n', pretty_text)
    with open(metadata_file, 'w') as meta_f:
        meta_f.write(new_pretty_text)


def get_issue_info(issue):
    enterprises = "open_euler"
    if patch_type not in ["cve", "bugfix", "feature"]:
        comment_source_pr("修复的问题类型%s不是支持的类型，可选类型[cve/bugfix/feature]，请重新指定\n" % patch_type)

    resp = gp.get_issue(issue, enterprises)
    html_url = resp.get("html_url")
    if not resp:
        err_info = "获取issue: %s 报错，请检查该issue是否存在" % issue
        comment_source_pr(err_info)

    if patch_type == "cve":
        issue_id = resp.get("title")
        if not issue_id.lower().startswith("cve-"):
            command_format = r"""makerhotpatch命令格式如下：
```text
/makehotpatch <version> <mode> <patch_name> <patch_type> <issue_id> <os_branch>
version:    源码包版本号，必填
mode:       热补丁包演进方式<ACC/SGL>， 必填
patch_name: 冷补丁包名，支持多patch包按顺序传入，以逗号隔开，src-openeuler下的仓库必填；kernel仓库不用填，门禁会自动打包patch文件
patch_type: 修复的问题类型<cve/bugfix/feature>，必填
issue_id:   修复问题的issue id，必填
os_branch:  本次热补丁基于哪个分支做，必填
```"""
            comment_source_pr("issue %s 不是cve类型，请重新指定\n %s" % (issue, command_format))
    else:
        issue_id = issue
    return issue_id, html_url


def comment_source_pr(err_info):
    body_str = "In response to this:\n > %s  \n\n命令执行结果：\n %s" % (args.comment, err_info)
    gp.comment_pr(args.prid, body_str)
    logger.error(err_info)
    sys.exit(1)


def create_update_issue(number=""):
    owner = "openeuler"
    title = "[hotpatch][{}-{}]fix {}".format(args.repo, repo_version, cve_issue)
    if mode == "SGL":
        hotpatch_metadata = "{}/blob/master/{}/{}/{}/hotmetadata_SGL.xml".format(
            meta_url, args.branch, args.repo, repo_version)
    else:
        hotpatch_metadata = "{}/blob/master/{}/{}/{}/hotmetadata_ACC.xml".format(
            meta_url, args.branch, args.repo, repo_version)

    body = "问题类别：{}\n热补丁元数据：{}\n".format(patch_type, hotpatch_metadata)
    if args.func == "add":
        data = {"access_token": args.token, "repo": "hotpatch_meta", "title": title, "issue_type": "hotpatch",
                "body": body}
        resp = gp.create_issue(owner, data)
        if not resp:
            err_info = "创建热补丁issue失败，请重试"
            comment_source_pr(err_info)
    elif args.func == "update":
        data = {"access_token": args.token, "repo": "hotpatch_meta", "title": title, "body": body}
        resp = gp.update_issue(owner, data, number)
        if not resp:
            err_info = "更新热补丁issue：%s 失败，请重试" % number
            comment_source_pr(err_info)

    resp_issue_number = resp.get("html_url")
    logger.info("issue_number=%s", resp_issue_number)

    return resp_issue_number


def get_patch_list(metadata):
    patch_list = []
    patch = []
    with open(metadata, "r") as xml_file:
        try:
            lines = xml_file.readlines()
            package = lines[4].strip()
            patch_list.append(package)
            for line in lines[5:-3]:
                line = line.strip()
                if line.startswith("<hotpatch "):
                    patch = []
                    patch.append(line)
                elif line.startswith("</hotpatch>"):
                    patch.append(line.strip())
                    patch_list.append("\n".join(patch))
                else:
                    patch.append(line)
        except IndexError:
            logger.error('metadata.xml format error: %s', traceback.format_exc())
            sys.exit(1)

    logger.info("patch_list: %s", patch_list)
    return patch_list


def init_args():
    """
    init args
    :return:
    """
    parser = argparse.ArgumentParser(description='generate hotmetadata.xml')
    parser.add_argument("-c", type=str, dest="community", default="src-openeuler",
                        help="src-openeuler or openeuler")
    parser.add_argument("-t", type=str, dest="token", help="gitee api token")
    parser.add_argument("-r", type=str, dest="repo", help="repo name")
    parser.add_argument("-o", type=str, dest="output", help="output file to save result")
    parser.add_argument("-m", type=str, dest="comment", help="trigger comment")
    parser.add_argument("-b", type=str, dest="branch", help="src branch")
    parser.add_argument("-pr", type=str, dest="prid", help="src prid")
    parser.add_argument("-p", type=str, dest="patch", help="patch_list")
    parser.add_argument("-f", type=str, dest="func", help="add or update")
    parser.add_argument("-i", type=str, dest="hotpatch_file", help="hotpatch issue file")
    parser.add_argument("-l", type=str, dest="download_link", help="src and debuginfo download link")
    return parser.parse_args()


if __name__ == '__main__':
    args = init_args()
    # makehotpatch 命令解析
    if len(args.comment.split()) == 6:
        _, repo_version, mode, patch_type, cve_issue, os_branch = args.comment.split()
    elif len(args.comment.split()) == 7:
        _, repo_version, mode, patch_name, patch_type, cve_issue, os_branch = args.comment.split()
    else:
        logger.error(
            "commond error, please keep it consistent: /makehotpatch <version> <mode> <patch_name> "
            "<patch_type> <cve_issue_id> <os_branch>")
        sys.exit(1)

    issue_number = ""
    metadata_path = args.output
    src_url, x86_url, arm_url = args.download_link.split(",")
    meta_url = "https://gitee.com/openeuler/hotpatch_meta"
    patch_path = os.path.join(metadata_path, args.branch, args.repo, repo_version, "patch")
    if not os.path.exists(patch_path):
        os.makedirs(patch_path)

    version_path = os.path.join(metadata_path, args.branch, args.repo, repo_version)
    if mode == "SGL":
        metadata_file = os.path.join(version_path, "hotmetadata_SGL.xml")
    else:
        metadata_file = os.path.join(version_path, "hotmetadata_ACC.xml")

    logger.info("new_metadata_patch: %s", metadata_file)

    gp = GiteeProxy(args.community, args.repo, args.token)

    # 获取需要修复的issue信息
    cve_issue_id, cve_issue_url = get_issue_info(cve_issue)

    # 删除最新version，在下面重新生成
    if args.func == "update" and os.path.exists(metadata_file):
        del_tree = ET.parse(metadata_file)
        del_root = del_tree.getroot()
        issue_number = del_hotpatch(del_root)
        write_to_hotmetadata_xml(del_root)

    # 创建热补丁issue，存在的话更新热补丁issue
    hotpatch_issue_url = create_update_issue(issue_number)
    with open(args.hotpatch_file, "w") as f:
        f.write(hotpatch_issue_url)

    # 生成元数据文件
    add_hotmetadata_xml()

    logger.info("success: hotmetadata.xml has been generated.")
    sys.exit(0)
