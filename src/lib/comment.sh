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

# 64k variant support
variant="${variant:-""}"
if [[ -n "$variant" ]]; then
    variant_suffix="_${variant}"
else
    variant_suffix=""
fi

check_item_comment_aarch64=""
check_item_comment_x86=""
check_item_comment_riscv64=""
compare_package_result_aarch64=""
compare_package_result_x86=""
compare_package_result_riscv64=""
detail_result_file_aarch64=""
detail_result_file_x86_64=""
detail_result_file_riscv64=""
# variant (e.g. 64k) files
check_item_comment_aarch64_variant=""
compare_package_result_aarch64_variant=""
detail_result_file_aarch64_variant=""

repo_server_test_tail=""
token=${gitcodeToken}
#需要输入的参数
jenkins_api_host="https://ci.openeuler.openatom.cn/"

if [[ $platform == "github" ]]; then
    repo_server_test_tail="-github"
    token=${GithubToken}
fi

# debug测试变量
function config_debug_variable() {
  if [[ "${repo_owner}" == "" ]]; then
    repo_owner="src-openeuler"
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

  # variant files
  if [[ -n "${variant_suffix}" ]]; then
    check_item_comment_aarch64_variant="${repo}_${prid}_aarch64${variant_suffix}_comment"
    compare_package_result_aarch64_variant="${repo}_${prid}_aarch64${variant_suffix}_compare_result"
  fi

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
  # cleanup variant files
  if [[ -n "${variant_suffix}" ]]; then
    if [[ -e $check_item_comment_aarch64_variant ]]; then
      rm $check_item_comment_aarch64_variant
    fi
    if [[ -e $compare_package_result_aarch64_variant ]]; then
      rm $compare_package_result_aarch64_variant
    fi
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
  # 下载所有 per-spec support_arch 文件
  support_arch_prefix=${repo}_${prid}_support_arch_
  scp -r -i ${SaveBuildRPM2Repo} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    root@${repo_server}:/repo/soe${repo_server_test_tail}/support_arch/${support_arch_prefix}* . 2>/dev/null || true
  for f in ${support_arch_prefix}*; do
    if [[ -e "$f" ]]; then
      local_suffix="${f#${support_arch_prefix}}"
      mv "$f" "support_arch_${local_suffix}"
    fi
  done
  # 下载 spec_list 清单（PR 修改的全部 spec 名，用于识别无限制 spec）
  spec_list_remote=${repo}_${prid}_spec_list
  scp -r -i ${SaveBuildRPM2Repo} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    root@${repo_server}:/repo/soe${repo_server_test_tail}/support_arch/${spec_list_remote} . 2>/dev/null || true
  if [[ -e "$spec_list_remote" ]]; then
    mv "$spec_list_remote" "spec_list"
  fi
  # variant files
  if [[ -n "${variant_suffix}" ]]; then
    detail_result_file_aarch64_variant="${repo}_aarch64${variant_suffix}.json"
    scp -r -i ${SaveBuildRPM2Repo} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@${repo_server}:$fileserver_tmpfile_path/${check_item_comment_aarch64_variant} . || log_info "file ${check_item_comment_aarch64_variant} not exist"
    scp -r -i ${SaveBuildRPM2Repo} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@${repo_server}:"/repo/openeuler/src-openeuler${repo_server_test_tail}/${tbranch}/${committer}/${repo}/aarch64${variant_suffix}/${prid}/${repo}_*.json" ${detail_result_file_aarch64_variant} || log_info "file ${detail_result_file_aarch64_variant} not exist"
    scp -r -i ${SaveBuildRPM2Repo} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@${repo_server}:$fileserver_tmpfile_path/${compare_package_result_aarch64_variant} . || log_info "file ${compare_package_result_aarch64_variant} not exist"
  fi
  log_info "***** End to scp comment file *****"
}

# 执行评论功能
function exec_comment() {
  log_info "***** Start to exec comment *****"
  url_files_server="http://${repo_server}/src-openeuler${repo_server_test_tail}/${tbranch}/${committer}/${repo}/replace__arch/${prid}"
  export PYTHONPATH=${shell_path}

  # build -a args (space-separated)
  a_args="${check_item_comment_aarch64} ${check_item_comment_x86} ${check_item_comment_riscv64}"
  if [[ -n "${check_item_comment_aarch64_variant}" ]]; then
    a_args="${a_args} ${check_item_comment_aarch64_variant}"
  fi

  # build -f args (comma-separated)
  f_args="${compare_package_result_x86},${compare_package_result_aarch64},${compare_package_result_riscv64}"
  if [[ -n "${compare_package_result_aarch64_variant}" ]]; then
    f_args="${f_args},${compare_package_result_aarch64_variant}"
  fi

  # build -d args (comma-separated)
  d_args="${detail_result_file_x86_64},${detail_result_file_aarch64},${detail_result_file_riscv64}"
  if [[ -n "${detail_result_file_aarch64_variant}" ]]; then
    d_args="${d_args},${detail_result_file_aarch64_variant}"
  fi

  python3 ${shell_path}/src/build/gitee_comment.py -o $repo_owner -r $repo -p $prid -c $committer -t ${token}\
   -b $jenkins_api_host -u $jenkins_user -j $jenkins_api_token -a ${a_args}\
    -f ${f_args} -m ${commentid} -l ${url_files_server} \
    -d ${d_args} -tb ${tbranch} --platform ${platform}
  log_info "***** End to exec comment *****"
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
