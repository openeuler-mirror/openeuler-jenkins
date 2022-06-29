#!/bin/bash
. ${shell_path}/src/lib/lib.sh
# 需要输入的参数
jenkins_api_host="https://openeulerjenkins.osinfra.cn/"
support_arch_file=${giteeRepoName}_${giteePullRequestIid}_support_arch

# debug测试变量
function config_debug_variable() {
  if [[ "${repo_owner}" == "" ]]; then
    repo_owner="src-openeuler"
    repo_server_test_tail=""
  elif [[ "${repo_owner}" != "src-openeuler" && "${repo_owner}" != "openeuler" ]]; then
    repo_server_test_tail="-test"
  fi
}
config_debug_variable

# 清理环境
function clearn_env() {
  fileserver_tmpfile_path="/repo/soe${repo_server_test_tail}/support_arch/${support_arch_file}"
  remote_dir_reset_cmd=$(
    cat <<EOF
    if [[ -e $fileserver_tmpfile_path ]]; then
	    rm -f $fileserver_tmpfile_path
    fi
EOF
)
  ssh -i ${SaveBuildRPM2Repo} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR root@${repo_server} "$remote_dir_reset_cmd"

}
# 开始下载kernel代码
function download_kernel_repo() {
  log_info "***** Start to download kernel *****"
  if [ "x$repo" == "xkernel" ]; then
    kernel_tag=$(cat kernel/SOURCE)
    log_info "now clone kernel source of tag ${kernel_tag} to code/kernel"
    git clone -b $kernel_tag --depth 1 https://${GiteeUserName}:${GiteePassword}@gitee.com/openeuler/kernel code/kernel
  fi
  log_info "***** End to download kernel *****"
}

# 开始执行静态检查（license，spec等）
function exec_check() {
  log_info "***** Start to exec static check *****"
  export PYTHONPATH=${shell_path}
  python3 ${shell_path}/src/ac/framework/ac.py \
    -w ${WORKSPACE} -r ${giteeRepoName} -o acfile -t ${GiteeToken} \
    -p ${giteePullRequestIid} -b ${giteeTargetBranch} -a ${GiteeUserPassword} \
    -x ${prCreateTime} -l ${triggerLink} -z ${jobTriggerTime} -m "${comment}" \
    -i ${commentID} -e ${giteeCommitter} --jenkins-base-url ${jenkins_api_host} \
    --jenkins-user ${jenkins_user} --jenkins-api-token ${jenkins_api_token} \
    -c ${repo_owner}
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

  if [[ -e support_arch ]]; then
    mv support_arch ${support_arch_file}
    scp -r -i ${SaveBuildRPM2Repo} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null ${support_arch_file} root@${repo_server}:/repo/soe${repo_server_test_tail}/support_arch/
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
