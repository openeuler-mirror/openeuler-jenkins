#!/bin/bash
. /home/jenkins/ci_check/src/lib/lib.sh
# 需要输入的参数
repo=$1
SaveBuildRPM2Repo=$2
repo_server=$3
giteeRepoName=$4
giteeTargetBranch=$5
GiteeUserName=$6
GiteePassword=$7
GiteeToken=$8
GiteeUserPassword=$9
giteePullRequestIid=${10}
prCreateTime=${11}
giteeCommitter=${12}
commentID=${13}
comment=${14}
jobTriggerTime=${15}
triggerLink=${16}

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
  export PYTHONPATH=/home/jenkins/ci_check
  python3 /home/jenkins/ci_check/src/ac/framework/ac.py -w ${WORKSPACE} -r ${giteeRepoName} -o acfile -t ${GiteeToken} -p ${giteePullRequestIid} -b ${giteeTargetBranch} -a ${GiteeUserPassword} -x ${prCreateTime} -l ${triggerLink} -z ${jobTriggerTime} -m "${comment}" -i ${commentID} -e ${giteeCommitter}
  log_info "***** End to exec static check *****"
}

# 执行额外操作，目前只有pkgship仓库需要额外操作
function extra_work() {
  log_info "***** Start to exec extra worker *****"
  # pkgship and ExclusiveArch,借用rpm repo存储
  if [[ -e pkgship_notify ]]; then
    scp -r -i ${SaveBuildRPM2Repo} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null pkgship_notify root@${repo_server}:/repo/soe/pkgship
  fi

  if [[ -e exclusive_arch ]]; then
    scp -r -i ${SaveBuildRPM2Repo} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null exclusive_arch root@${repo_server}:/repo/soe/exclusive_arch/${giteeRepoName}
  fi
  log_info "***** End to exec extra worker *****"
}

# 执行入口
function main() {
  download_kernel_repo
  exec_check
  extra_work
}
