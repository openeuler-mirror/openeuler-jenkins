#!/bin/bash
. ${shell_path}/src/lib/lib.sh

owner="src-openeuler"
jenkins_api_host="http://jenkins.jenkins"
check_item_comment_aarch64=""
check_item_comment_x86=""
compare_package_result_aarch64=""
compare_package_result_x86=""
#需要输入的参数
repo=$1
prid=$2
committer=$3
giteetoken=$4
jenkins_user=$5
jenkins_api_token=$6
WORKSPACE=$7
SaveBuildRPM2Repo=$8
repo_server=$9
compare_result=${10}
commentid=${11}
jenkins_api_host=${12}

# 清理环境
function clearn_env() {
  log_info "***** Start to clearn env *****"
  # download compare package comment files
  check_item_comment_aarch64="${repo}_aarch64_comment"
  check_item_comment_x86="${repo}_x86_64_comment"
  #cat $compare_package_comment_x86
  compare_package_result_aarch64="${repo}_aarch64_compare_result"
  compare_package_result_x86="${repo}_x86_64_compare_result"

  if [[ -e check_item_comment_aarch64 ]]; then
    rm $check_item_comment_aarch64
  fi
  if [[ -e $check_item_comment_x86 ]]; then
    rm $check_item_comment_x86
  fi
  if [[ -e $compare_package_result_aarch64 ]]; then
    rm $compare_package_result_aarch64
  fi
  if [[ -e $compare_package_result_x86 ]]; then
    rm $compare_package_result_x86
  fi
  log_info "***** End to clearn env *****"
}

# 从文件服务器拷贝文件
function scp_comment_file() {
  log_info "***** Start to scp comment file *****"
  fileserver_tmpfile_path="/repo/soe/check_item"
  #scp -r -i ${SaveBuildRPM2Repo} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@${repo_server}:$fileserver_tmpfile_path/${check_item_comment_aarch64} . || log_info "file ${check_item_comment_aarch64} not exist"
  #scp -r -i ${SaveBuildRPM2Repo} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@${repo_server}:$fileserver_tmpfile_path/${check_item_comment_x86} . || log_info "file ${check_item_comment_x86} not exist"
  #ls $WORKSPACE/${comment}
  scp -r -i ${SaveBuildRPM2Repo} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@${repo_server}:$fileserver_tmpfile_path/${compare_package_result_aarch64} . || log_info "file ${compare_package_result_aarch64} not exist"
  scp -r -i ${SaveBuildRPM2Repo} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@${repo_server}:$fileserver_tmpfile_path/${compare_package_result_x86} . || log_info "file ${compare_package_result_x86} not exist"
  ls $WORKSPACE/${compare_result}
  log_info "***** End to scp comment file *****"
}

# 执行评论功能
function exec_comment() {
  log_info "***** Start to exec comment *****"
  export PYTHONPATH=${shell_path}
  python3 ${shell_path}/src/build/gitee_comment.py -o $owner -r $repo -p $prid -c $committer -t ${giteetoken} -b $jenkins_api_host -u $jenkins_user -j $jenkins_api_token -a ${check_item_comment_aarch64} ${check_item_comment_x86} -f ${compare_package_result_x86},${compare_package_result_aarch64} -m ${commentid}
  log_info "***** End to exec comment *****"
}

# 执行入口
function main() {
  clearn_env
  scp_comment_file
  exec_comment
}
