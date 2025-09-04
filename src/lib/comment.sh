#!/bin/bash
. ${shell_path}/src/lib/lib.sh

check_item_comment_aarch64=""
check_item_comment_x86=""
check_item_comment_riscv64=""
compare_package_result_aarch64=""
compare_package_result_x86=""
compare_package_result_riscv64=""
detail_result_file_aarch64=""
detail_result_file_x86_64=""
detail_result_file_riscv64=""

repo_server_test_tail=""
token=${giteetoken}
#需要输入的参数
jenkins_api_host="https://openeulerjenkins.osinfra.cn/"

if [[ $platform == "github" ]]; then
    repo_server_test_tail="-github"
    token=${GithubToken}
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
  log_info "***** Start to clearn env *****"
  # download compare package comment files
  check_item_comment_aarch64="${repo}_${prid}_aarch64_comment"
  check_item_comment_x86="${repo}_${prid}_x86_64_comment"
  check_item_comment_riscv64="${repo}_${prid}_riscv64_comment"
  #cat $compare_package_comment_x86
  compare_package_result_aarch64="${repo}_${prid}_aarch64_compare_result"
  compare_package_result_x86="${repo}_${prid}_x86_64_compare_result"
  compare_package_result_riscv64="${repo}_${prid}_riscv64_compare_result"
  build_num_file="${repo_owner}_${repo}_${prid}_build_num.yaml"


  if [[ -e check_item_comment_aarch64 ]]; then
    rm $check_item_comment_aarch64
  fi
  if [[ -e $check_item_comment_x86 ]]; then
    rm $check_item_comment_x86
  fi
  if [[ -e $check_item_comment_riscv64 ]]; then
    rm $check_item_comment_riscv64
  fi
  if [[ -e $compare_package_result_aarch64 ]]; then
    rm $compare_package_result_aarch64
  fi
  if [[ -e $compare_package_result_x86 ]]; then
    rm $compare_package_result_x86
  fi
  if [[ -e $compare_package_result_riscv64 ]]; then
    rm $compare_package_result_riscv64
  fi
  if [[ -e build_num_file ]]; then
    rm $build_num_file
  fi
  log_info "***** End to clearn env *****"
}

# 从文件服务器拷贝文件
function scp_comment_file() {
  log_info "***** Start to scp comment file *****"
  fileserver_tmpfile_path="/repo/soe${repo_server_test_tail}/check_item"
  detail_result_file_aarch64="${repo}_aarch64.json"
  detail_result_file_x86_64="${repo}_x86_64.json"
  detail_result_file_riscv64="${repo}_riscv64.json"
  scp -r -i ${SaveBuildRPM2Repo} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@${repo_server}:$fileserver_tmpfile_path/${check_item_comment_aarch64} . || log_info "file ${check_item_comment_aarch64} not exist"
  scp -r -i ${SaveBuildRPM2Repo} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@${repo_server}:$fileserver_tmpfile_path/${check_item_comment_x86} . || log_info "file ${check_item_comment_x86} not exist"
  scp -r -i ${SaveBuildRPM2Repo} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@${repo_server}:$fileserver_tmpfile_path/${check_item_comment_riscv64} . || log_info "file ${check_item_comment_riscv64} not exist"
  #ls $WORKSPACE/${comment}
  scp -r -i ${SaveBuildRPM2Repo} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@${repo_server}:"/repo/openeuler/src-openeuler${repo_server_test_tail}/${tbranch}/${committer}/${repo}/aarch64/${prid}/${repo}_*.json" ${detail_result_file_aarch64} || log_info "file ${detail_result_file_aarch64} not exist"
  scp -r -i ${SaveBuildRPM2Repo} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@${repo_server}:"/repo/openeuler/src-openeuler${repo_server_test_tail}/${tbranch}/${committer}/${repo}/x86_64/${prid}/${repo}_*.json" ${detail_result_file_x86_64} || log_info "file ${detail_result_file_x86_64} not exist"
  scp -r -i ${SaveBuildRPM2Repo} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@${repo_server}:"/repo/openeuler/src-openeuler${repo_server_test_tail}/${tbranch}/${committer}/${repo}/riscv64/${prid}/${repo}_*.json" ${detail_result_file_riscv64} || log_info "file ${detail_result_file_riscv64} not exist"
  scp -r -i ${SaveBuildRPM2Repo} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@${repo_server}:$fileserver_tmpfile_path/${compare_package_result_aarch64} . || log_info "file ${compare_package_result_aarch64} not exist"
  scp -r -i ${SaveBuildRPM2Repo} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@${repo_server}:$fileserver_tmpfile_path/${compare_package_result_x86} . || log_info "file ${compare_package_result_x86} not exist"
  scp -r -i ${SaveBuildRPM2Repo} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@${repo_server}:$fileserver_tmpfile_path/${compare_package_result_riscv64} . || log_info "file ${compare_package_result_riscv64} not exist"
  ls $WORKSPACE/${compare_result}
  scp -r -i ${SaveBuildRPM2Repo} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@${repo_server}:$fileserver_tmpfile_path/${build_num_file} . || log_info "file ${build_num_file} not exist"
  scp -r -i ${SaveBuildRPM2Repo} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@${repo_server}:/repo/soe${repo_server_test_tail}/support_arch/${repo}_${prid}_support_arch .
  if [[ -e ${repo}_${prid}_support_arch ]]; then
    mv ${repo}_${prid}_support_arch support_arch
  fi
  log_info "***** End to scp comment file *****"
}

# 执行评论功能
function exec_comment() {
  log_info "***** Start to exec comment *****"
  url_files_server="http://${repo_server}/src-openeuler${repo_server_test_tail}/${tbranch}/${committer}/${repo}/replace__arch/${prid}"
  export PYTHONPATH=${shell_path}
  python3 ${shell_path}/src/build/gitee_comment.py -o $repo_owner -r $repo -p $prid -c $committer -t ${token}\
   -b $jenkins_api_host -u $jenkins_user -j $jenkins_api_token -a ${check_item_comment_aarch64} ${check_item_comment_x86} ${check_item_comment_riscv64}\
    -f ${compare_package_result_x86},${compare_package_result_aarch64},${compare_package_result_riscv64} -m ${commentid} -l ${url_files_server} \
    -d ${detail_result_file_x86_64},${detail_result_file_aarch64},${detail_result_file_riscv64} -tb ${tbranch} --platform ${platform}
  log_info "***** End to exec comment *****"
  log_info "***** Start to exec comment to kafka*****"
  python3 ${shell_path}/src/build/comment_to_dashboard.py -r $repo -c $committer -m ${commentid} -g $jobtriggertime\
   -k "${prtitle}" -t $prcreatetime -b $tbranch -u $prurl -i $triggerbuildid -p $prid -o $repo_owner \
   --gitee_token ${token}
  log_info "***** End to exec comment to kafka*****"
}

# 执行入口
function main() {
  clearn_env
  scp_comment_file
  exec_comment
  log_info "save build num file"
  if [[ -e $build_num_file ]]; then
    scp -r -i ${SaveBuildRPM2Repo} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR ${build_num_file} root@${repo_server}:$fileserver_tmpfile_path/${build_num_file}
  fi
}
