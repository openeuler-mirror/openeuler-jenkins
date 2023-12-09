import argparse
import re
import sys
import os
import xml.etree.ElementTree as ET

import logging
from src.proxy.gitee_proxy import GiteeProxy
from src.utils.shell_cmd import shell_cmd_live


def read_metadata_file(metadata_file):
    tree = ET.parse(metadata_file)
    root = tree.getroot()
    return root


def get_version_list(metadata):
    patch_list = []
    patch = []
    with open(metadata, "r") as file:
        lines = file.readlines()
        package = lines[4].strip()
        patch_list.append(package)
        for line in lines[5:-3]:
            line = line.strip()
            print(line)
            if line.startswith("<hotpatch "):
                patch.clear()
                patch.append(line)
            elif line.startswith("</hotpatch>"):
                patch.append(line.strip())
                patch_list.append("\n".join(patch))
            else:
                patch.append(line)

    logging.warning("patch_list: %s", patch_list)
    return patch_list


def get_version_release(patch_list):
    patch = patch_list.split("\n")[0].strip()
    version = patch.split(" ")[1].split("=")[1].strip('"')
    release = patch.split(" ")[2].split("=")[1].strip('"')
    logging.warning("%s-%s", version, release)
    return "%s-%s" % (version, release)


def get_sgl_version_release(name, patch_list):
    last_ver = ""
    for patch_i in patch_list:
        patch = patch_i.split("\n")[0].strip()
        old_name = patch.split(" ")[1].split("=")[1].strip('"')
        if name == old_name:
            version = patch.split(" ")[2].split("=")[1].strip('"')
            release = patch.split(" ")[3].split("=")[1].strip('"')
            last_ver = "%s-%s-%s" % (old_name.replace("-", "_"), version, release)
    return last_ver


def get_sgl_curr_ver(patch_list):
    patch = patch_list.split("\n")[0].strip()
    name = patch.split(" ")[1].split("=")[1].strip('"')
    version = patch.split(" ")[2].split("=")[1].strip('"')
    release = patch.split(" ")[3].split("=")[1].strip('"')
    logging.warning("name:%s, version:%s, release:%s", name, version, release)
    return name, version, release


def check_version(old_patch_list, new_patch_list):
    pre_version_release = ""
    if args.mode == "ACC":
        last_version_release = get_version_release(old_patch_list[-1])
        curr_version_release = get_version_release(new_patch_list[-1])
        if curr_version_release <= last_version_release:
            error_info = "新热补丁版本号%s小于已有热补丁%s，请重新指定热补丁版本和release" % (
                curr_version_release, last_version_release)
            comment_metadata_pr(error_info)
        pre_version_release = "ACC-%s" % last_version_release
    elif args.mode == "SGL":
        name, version, release = get_sgl_curr_ver(new_patch_list[-1])
        curr_ver = "%s-%s-%s" % (name.replace("-", "_"), version, release)
        last_ver = get_sgl_version_release(name, old_patch_list)
        if curr_ver <= last_ver:
            error_info = "新热补丁版本号%s小于已有热补丁%s，请重新指定热补丁版本和release" % (
                curr_ver, last_ver)
            comment_metadata_pr(error_info)
        pre_version_release = last_ver
    logging.warning("pre_version_release:%s", pre_version_release)
    return pre_version_release


def check_if_status_modify(version, old_field, new_field):
    # 检查status字段是否有变更
    old_field = old_field.strip().strip("<").strip(">").split()
    new_field = new_field.strip().strip("<").strip(">").split()

    old_status = old_field[-1].split("=")[-1].strip('"')
    new_status = new_field[-1].split("=")[-1].strip('"')

    if len(old_field) != len(new_field):
        if old_status == "confirmed":
            comment_metadata_pr("热补丁版本号%s已经confirmed, 如果需要更改的话请联系sig maintianer" % version)
    else:
        for i in range(len(old_field)):
            if old_field[i] != new_field[i]:
                if old_status == "confirmed":
                    comment_metadata_pr("热补丁版本号%s已经confirmed, 如果需要更改的话请联系sig maintianer" % version)

    return old_status, new_status


def check_modify_field(version, old_patch, new_patch, patch_file):
    # 检查同一个version下的字段变更
    old_patch = old_patch.split("\n")
    new_patch = new_patch.split("\n")
    old_status, new_status = check_if_status_modify(version, old_patch[0], new_patch[0])

    for i in range(1, len(old_patch)):
        field_name = old_patch[i].split(">")[0].split("<")[1]
        if old_status == "confirmed":
            if old_patch[i] != new_patch[i]:
                comment_metadata_pr("热补丁版本号%s已经confirmed, 如果需要更改的话请联系sig maintianer" % version)
            if field_name.lower() == "patch":
                patch_name = old_patch[i].split(">")[1].split("<")[0]
                logging.warning("patch_name:%s", patch_name)
                if patch_name in patch_file:
                    comment_metadata_pr("热补丁版本号%s已经confirmed, 如果需要更改的话请联系sig maintianer" % version)

    if old_status == "unconfirmed" and new_status == "confirmed":
        gp.delete_tag_of_pr(args.prid, "ci_processing")
        gp.create_tags_of_pr(args.prid, "ci_successful")
        logging.warning("%s only status is modify, don't need make hotpatch" % version)
        sys.exit(1)


def compare_modify_version(metadata_file, patch_file):
    # 比较xml中两个相同版本
    modify_list = []
    old_patch_list = []
    new_patch_list = []
    patch_file_list = []
    if patch_file != "null":
        patch_file_list = list(map(lambda x: x.split("/")[-1], patch_file.split()))
    logging.error("patch_file_list:%s", patch_file_list)

    # 获取本次提交的元数据信息
    if os.path.exists(metadata_file):
        new_patch_list = get_version_list(metadata_file)

    get_content_cmd = "cd hotpatch_meta; git checkout master; cd .."
    ret, out, _ = shell_cmd_live(get_content_cmd, cap_out=True)
    if ret:
        logging.warning("get checkout master failed, %s", ret)
        return None
    # 获取本次提交之前的元数据信息
    if os.path.exists(metadata_file):
        old_patch_list = get_version_list(metadata_file)

    if old_patch_list and new_patch_list:
        # Package name 有变更
        if old_patch_list[0] != new_patch_list[0]:
            logging.error("package or package version is modify")
        old_patch_list = old_patch_list[1:]
        new_patch_list = new_patch_list[1:]

        if len(old_patch_list) < 1:
            return None

        # 判断新增热补丁的版本是否大于上个版本
        if len(old_patch_list) != len(new_patch_list):
            pre_version_release = check_version(old_patch_list, new_patch_list)
            with open("modify_version", "w") as file:
                file.write("pre_version_release:%s\n" % pre_version_release)

        # 判断其它patch字段是否有变更
        for i in range(len(old_patch_list)):
            if args.mode == "ACC":
                version_release = get_version_release(old_patch_list[i])
                version_release = "ACC-" + version_release
            elif args.mode == "SGL":
                name, version, release = get_sgl_curr_ver(new_patch_list[-1])
                version_release = "%s-%s-%s" % (name.replace("-", "_"), version, release)

            logging.warning("compare %s", version_release)
            check_modify_field(version_release, old_patch_list[i], new_patch_list[i], patch_file_list)
            if old_patch_list[i] != new_patch_list[i]:
                logging.warning("version %s is modify", version_release)
                modify_list.append(version_release)

    # 变更的patch字段是否发布，已发布的不允许修改
    if modify_list:
        logging.warning("modify_list = %s", modify_list)
        with open("modify_version", "w") as file:
            file.write("modify_version:%s\n" % " ".join(modify_list))


def get_patch_list(hotpatch):
    patch_list = []
    logging.warning(hotpatch)
    version = 0
    release = 0
    for child in hotpatch:
        patch_list = []
        version = child.attrib["version"]
        release = child.attrib["release"]
        patch = child.findall('patch')
        for patch_name in patch:
            patch_list.append(patch_name.text)
    logging.warning("version:%s, release:%s, patch_list:%s", version, release, patch_list)
    return version, release, patch_list


def verifying_field(version, release):
    hotpatch_dict = {}
    issue_id_list = []
    reference_href_list = []
    logging.info("verifying field")
    root = read_metadata_file(args.input)
    hotpatchs = root.iter('hotpatch')
    try:
        for child in hotpatchs:
            issue_id_list = []
            reference_href_list = []
            logging.warning("version: %s, release: %s, type: %s, status: %s", child.attrib["version"],
                         child.attrib["release"], child.attrib["type"], child.attrib["status"])
            if child.attrib["version"] == version and child.attrib["release"] == release:
                logging.warning("version: %s, release: %s", version, release)
                cve_type = child.attrib["type"]
                issue_list = child.findall('issue')
                hotpatch_dict["patch_name"] = "ACC"
                if cve_type not in ["cve", "bugfix", "feature"]:
                    comment_metadata_pr("修复的问题类型%s不是支持的类型，可选类型[cve/bugfix/feature]，请重新指定\n" % cve_type)
                for issue in issue_list:
                    issue_id = issue.attrib["id"]
                    issue_id_list.append(issue_id)
                    reference_href = issue.attrib["issue_href"]
                    reference_href_list.append(reference_href)
                if args.mode == "SGL":
                    name = child.attrib["name"]
                    hotpatch_dict["patch_name"] = name
                    ver_name = "SGL-%s" % ("-".join(issue_id_list))
                    if name != ver_name:
                        error_info = "热补丁name字段与issue id字段不匹配，当前为：%s， 应该为：%s" % (name, ver_name)
                        comment_metadata_pr(error_info)
                src_url = child.find('SRC_RPM').text
                x86_debug = child.find('Debug_RPM_X86_64').text
                aarch64_debug = child.find('Debug_RPM_Aarch64').text
                hotpatch_issue = child.find('hotpatch_issue_link').text
                verify_str = "verifying field success.\n type: %s\n issue id: %s\n SRC_RPM:%s\n Debug_RPM_X86_64:%s\n\
                Debug_RPM_Aarch64: %s\n  issue_href: %s\n hotpatch_issue: %s\n" % (
                    cve_type, " ".join(issue_id_list),src_url, x86_debug, aarch64_debug, " ".join(reference_href_list),
                    hotpatch_issue)
                logging.warning(verify_str)
                hotpatch_dict["cve_type"] = cve_type
                hotpatch_dict["hotpatch_issue"] = hotpatch_issue
        hotpatch_dict["issue_id"] = issue_id_list
        hotpatch_dict["reference_href"] = reference_href_list
    except KeyError as error:
        logging.error("hotmatedata.xml keyerror: %s", error)
    except Exception as error:
        logging.error("hotmatedata.xml error: %s", error)

    return hotpatch_dict


def get_update_info(args):
    date_pattern = r"\d{4}[-/]\d{2}[-/]\d{2}"
    type_dict = {
        "cve": "security",
        "bugfix": "bugfix",
        "feature": "enhancement"
    }

    root = read_metadata_file(args.input)
    hotpatch = root.iter('hotpatch')

    version, release, patch_list = get_patch_list(hotpatch)
    hotpatch_dict = verifying_field(version, release)

    hotpatch_issue = hotpatch_dict.get("hotpatch_issue")
    #hotpatch_issue_resp = gp.get_repo_issue(hotpatch_issue.split("/")[-1], "wanghuan158", "hot-patch_metadata")
    hotpatch_issue_resp = gp.get_issue(hotpatch_issue.split("/")[-1])

    logging.warning(hotpatch_issue_resp)
    if not hotpatch_issue_resp:
        comment_metadata_pr("获取热补丁issue失败")

    state = hotpatch_issue_resp.get("state")
    if state in ["closed", "rejected"]:
        comment_metadata_pr("请确认热补丁issue未处于已完成/已关闭状态")

    issue_title = hotpatch_issue_resp.get("title")
    reference_date = hotpatch_issue_resp.get("created_at")
    logging.warning("issue_title: %s" % issue_title)
    logging.warning("reference_date: %s" % reference_date)
    dates = re.findall(date_pattern, reference_date)

    with open(args.output, "w") as file:
        file.write("patch: " + ",".join(patch_list) + "\n")
        file.write("cve_type: %s\n" % type_dict.get(hotpatch_dict.get("cve_type"), ""))
        file.write("issue_title: %s\n" % issue_title)
        file.write("issue_id: %s\n" % ",".join(hotpatch_dict.get("issue_id")))
        file.write("reference-type: %s\n" % hotpatch_dict.get("cve_type"))
        file.write("reference-id: %s\n" % " ".join(hotpatch_dict.get("issue_id")))
        file.write("reference-href: %s\n" % " ".join(hotpatch_dict.get("reference_href")))
        file.write("issued-date: %s\n" % dates[0])
        file.write("curr_version: %s\n" % version)
        file.write("curr_release: %s\n" % release)
        file.write("mode: %s\n" % args.mode)
        file.write("patch_name: %s\n" % hotpatch_dict.get("patch_name"))

    logging.warning("output path: %s", args.output)

    compare_modify_version(args.input, args.patch)


def comment_metadata_pr(err_info):
    body_str = "热补丁制作流程已中止，错误信息：%s" % err_info
    gp.comment_pr(args.prid, body_str)
    logging.error(err_info)
    gp.delete_tag_of_pr(args.prid, "ci_processing")
    gp.create_tags_of_pr(args.prid, "ci_failed")
    sys.exit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Parsing hotmetadata.xml')
    parser.add_argument("-t", type=str, dest="token", help="gitee api token")
    parser.add_argument("-i", type=str, dest="input", help="input file")
    parser.add_argument("-o", type=str, dest="output", help="output file")
    parser.add_argument("-c", type=str, dest="community", default="src-openeuler",
                        help="src-openeuler or openeuler")
    parser.add_argument("-r", type=str, dest="repo", help="repo name")
    parser.add_argument("-pr", type=str, dest="prid", help="pr id")
    parser.add_argument("-p", type=str, dest="patch", help="modify patch file")
    parser.add_argument("-m", type=str, dest="mode", help="hotpatch mode")

    args = parser.parse_args()

    gp = GiteeProxy(args.community, args.repo, args.token)
    gp.delete_tag_of_pr(args.prid, "ci_successful")
    gp.delete_tag_of_pr(args.prid, "ci_failed")
    gp.create_tags_of_pr(args.prid, "ci_processing")

    get_update_info(args)
    sys.exit(0)
