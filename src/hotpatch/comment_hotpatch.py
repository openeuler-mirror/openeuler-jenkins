import argparse
import os
from src.proxy.gitee_proxy import GiteeProxy
from src.proxy.jenkins_proxy import JenkinsProxy
from src.ac.framework.ac_result import ACResult, SUCCESS


def comment_tag(up_builds):
    build_result = sum([ACResult.get_instance(build["result"]) for build in up_builds], SUCCESS)
    if build_result == SUCCESS:
        gitee_proxy.delete_tag_of_pr(args.prid, "ci_failed")
        gitee_proxy.create_tags_of_pr(args.prid, "ci_successful")
    else:
        gitee_proxy.delete_tag_of_pr(args.prid, "ci_successful")
        gitee_proxy.create_tags_of_pr(args.prid, "ci_failed")
        

def comment_of_check_item(jp):
    """
    check item comment
    :param builds:
    :return:
    """
    comments = ["<table><tr><th>Arch name</th> <th>Result</th> <th>Details</th><th>Download link</th> </tr>"]
    base_job_name = os.environ.get("JOB_NAME")
    base_build_id = os.environ.get("BUILD_ID")
    base_build_id = int(base_build_id)
    print("base_job_name: %s, base_build_id: %s" % (base_job_name, base_build_id))
    base_build = jp.get_build_info(base_job_name, base_build_id)
    up_builds = jp.get_upstream_builds(base_build)
    for build in up_builds:
        name, _ = jp.get_job_path_build_no_from_build_url(build["url"])
        print(name)
        status = build["result"]
        ac_result = ACResult.get_instance(status)
        build_url = build["url"]
        arch = name.split("/")[-2]
        if ACResult.get_instance(status) == SUCCESS:
            hotpath_path = "http://{}/hotpatch/hotpatch_meta/{}/{}".format(args.repo_server, args.prid, arch)
            comments.append("<tr><td>{}</td> <td>{}<strong>{}</strong></td> <td><a href={}>#{}</a></td> <td>{}</td>".format(
            arch, ac_result.emoji, ac_result.hint, "{}{}".format(build_url, "console"), build["number"], hotpath_path))
        else:
            comments.append("<tr><td>{}</td> <td>{}<strong>{}</strong></td> <td><a href={}>#{}</a></td> <td>{}</td>".format(
            arch, ac_result.emoji, ac_result.hint, "{}{}".format(build_url, "console"), build["number"], ""))

    comments.append("</table>")
    comment_tag(up_builds)

    return comments


def comment_chroot_info():
    """
    check item comment
    :param builds:
    :return:
    """
    chroot_x86 = "http://{}/hotpatch/hotpatch_meta/{}/chroot_x86_64_pr{}.tar.gz".format(args.repo_server, args.prid, args.prid)
    chroot_aarch64 = "http://{}/hotpatch/hotpatch_meta/{}/chroot_aarch64_pr{}.tar.gz".format(args.repo_server, args.prid, args.prid)

    comment = "chroot环境路径如下：\n {}\n{}\n " \
              "使用方法：\n" \
              "1. 下载对应架构chroot环境的tar包到本地环境，使用tar xzvf [tar包] -C [chroot_path]命令解压chroot环境；\n" \
              "2. 进入chroot_path目录，执行chroot_init.sh文件，用来安装编译需要的syscare包并mount chroot环境和本地环境，执行chroot .进入chroot环境；\n" \
              "3. 制作热补丁需要的source包和debuginfo包在chroot_path下的root目录中，patch在chroot_path下的/hotpatch_cicd/patch_dir/目录中，参考如下命令进行热补丁制作:\n" \
              "syscare build --patch-name [ACC/SGL_xxx] --patch-version [patch_version] --patch-release [patch_release] --source [source_package] \
              --debuginfo [debuginfo_package] --output [hotpatch_ouput_path] [patches]".format(chroot_x86, chroot_aarch64)
    gitee_proxy.comment_pr(args.prid, comment)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='generate hotmetadata.xml')
    parser.add_argument("-c", type=str, dest="community", default="src-openeuler",
                        help="src-openeuler or openeuler")
    parser.add_argument("-t", type=str, dest="token", help="gitee api token")
    parser.add_argument("-r", type=str, dest="repo", help="repo name")
    parser.add_argument("-pr", type=str, dest="prid", help="src prid")
    parser.add_argument("--jenkins-base-url", type=str, dest="jenkins_base_url",
                        default="https://openeulerjenkins.osinfra.cn/", help="jenkins base url")
    parser.add_argument("--jenkins-user", type=str, dest="jenkins_user", help="repo name")
    parser.add_argument("--jenkins-api-token", type=str, dest="jenkins_api_token", help="jenkins api token")
    parser.add_argument("--repo-server", type=str, dest="repo_server", help="repo server")

    args = parser.parse_args()

    gitee_proxy = GiteeProxy(args.community, args.repo, args.token)
    gitee_proxy.delete_tag_of_pr(args.prid, "ci_processing")

    jenkins_proxy_inst = JenkinsProxy(args.jenkins_base_url, args.jenkins_user, args.jenkins_api_token)
    comments = comment_of_check_item(jenkins_proxy_inst)
    gitee_proxy.comment_pr(args.prid, "\n".join(comments))
    comment_chroot_info()
