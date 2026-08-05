#!/bin/bash
# **********************************************************************************
# Copyright (c) Huawei Technologies Co., Ltd. 2020-2026. All rights reserved.
# [openeuler-jenkins] is licensed under the Mulan PSL v2.
# You can use this software according to the terms and conditions of the Mulan PSL v2.
# You may obtain a copy of Mulan PSL v2 at:
#          http://license.coscl.org.cn/MulanPSL2
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND,
# EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT,
# MERCHANTABILITY OR FIT FOR A PARTICULAR PURPOSE.
# See the Mulan PSL v2 for more details.
# **********************************************************************************
. ${shell_path}/src/lib/lib.sh
# 需要输入的参数
jenkins_api_host="https://ci.openeuler.openatom.cn/"
support_arch_prefix="${gitcodeRepoName}_${gitcodePullRequestId}_support_arch_"
repo_server_test_tail=""
token=${gitcodeToken}
user_passwd=${gitcodeUserPassword}

if [[ "${platform}" == "" ]]; then
    platform="gitcode"
fi

if [[ "${platform}" == "github" ]]; then
    repo_server_test_tail="-github"
    token=${GithubToken}
    user_passwd=${GithubUserPassword}
fi

# debug测试变量
function config_debug_variable() {
  if [[ "${repo_owner}" == "" ]]; then
    repo_owner="src-openeuler"
  elif [[ "${repo_owner}" != "src-openeuler" && "${repo_owner}" != "openeuler" ]]; then
    repo_server_test_tail="-test"
  fi
}
config_debug_variable

# 清理环境
function clearn_env() {
  remote_dir_reset_cmd=$(
    cat <<EOF
    rm -f /repo/soe${repo_server_test_tail}/support_arch/${support_arch_prefix}*
    rm -f /repo/soe${repo_server_test_tail}/support_arch/${gitcodeRepoName}_${gitcodePullRequestId}_spec_list
EOF
)
  ssh -i ${SaveBuildRPM2Repo} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR root@${repo_server} "$remote_dir_reset_cmd"
  log_info "***** Start to copy db file *****"
  scp -r -i ${SaveBuildRPM2Repo} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@${repo_server}:/repo/soe/sql/source_clean.db . || log_info "file source_clean not exist"

}
# 开始下载kernel代码
function download_kernel_repo() {
  log_info "***** Start to download kernel *****"
  if [ "x$repo" == "xkernel" ]; then
    kernel_tag=$(cat kernel/SOURCE)
    log_info "now clone kernel source of tag ${kernel_tag} to code/kernel"
    git clone -b $kernel_tag --depth 1 https://${gitcodeUserName}:${gitcodePassword}@gitcode.com/openeuler/kernel code/kernel
  fi
  log_info "***** End to download kernel *****"
}

# 开始执行静态检查（license，spec等）
function exec_check() {
  log_info "***** Start to exec static check *****"
  export PYTHONPATH=${shell_path}
  python3 ${shell_path}/src/ac/framework/ac.py \
    -w ${WORKSPACE} -r ${gitcodeRepoName} -o ${acfile} -t ${token}\
    -p ${gitcodePullRequestId} -b ${gitcodeTargetBranch} \
    -x ${prCreateTime} -l ${triggerLink} -z ${jobTriggerTime} -m "${comment}" \
    -i "${commentID}" -e ${gitcodeCommitter} --jenkins-base-url ${jenkins_api_host} \
    --jenkins-user ${jenkins_user} --jenkins-api-token ${jenkins_api_token} \
    -c ${gitcodeTargetNamespace} --platform "${platform}"
  log_info "***** End to exec static check *****"
}

# 执行额外操作，目前只有pkgship仓库需要额外操作
function extra_work() {
  log_info "***** Start to exec extra worker *****"
  # pkgship and ExclusiveArch,借用rpm repo存储
  remote_dir_create_cmd=$(
    cat <<EOF
if [[ ! -d "/repo/soe${repo_server_test_tail}/pkgship" ]]; then
	mkdir -p /repo/soe${repo_server_test_tail}/pkgship
fi
if [[ ! -d "/repo/soe${repo_server_test_tail}/support_arch" ]]; then
	mkdir -p /repo/soe${repo_server_test_tail}/support_arch
fi
EOF
  )
  ssh -i ${SaveBuildRPM2Repo} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR root@${repo_server} "$remote_dir_create_cmd"

  if [[ -e pkgship_notify ]]; then
    scp -r -i ${SaveBuildRPM2Repo} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null pkgship_notify root@${repo_server}:/repo/soe${repo_server_test_tail}/pkgship
  fi

  # 上传所有 per-spec support_arch 文件
  for f in support_arch_*; do
      if [[ -e "$f" ]]; then
          remote_name="${gitcodeRepoName}_${gitcodePullRequestId}_${f}"
          mv "$f" "${remote_name}"
          scp -r -i ${SaveBuildRPM2Repo} -o StrictHostKeyChecking=no \
              -o UserKnownHostsFile=/dev/null \
              "${remote_name}" root@${repo_server}:/repo/soe${repo_server_test_tail}/support_arch/
      fi
  done

  # 上传 spec_list 清单（PR 修改的全部 spec 名，用于识别无限制 spec）
  if [[ -e spec_list ]]; then
      remote_name="${gitcodeRepoName}_${gitcodePullRequestId}_spec_list"
      mv spec_list "${remote_name}"
      scp -r -i ${SaveBuildRPM2Repo} -o StrictHostKeyChecking=no \
          -o UserKnownHostsFile=/dev/null \
          "${remote_name}" root@${repo_server}:/repo/soe${repo_server_test_tail}/support_arch/
  fi
  log_info "***** End to exec extra worker *****"
}

# 执行入口
function main() {
  clearn_env
  download_kernel_repo
  exec_check
  extra_work
}
