#!/bin/bash
. /home/jenkins/ci_check/src/lib/lib.sh

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

# 启动ipv6 loopback
function config_ipv6() {
  log_info "***** Start to config ipv6 *****"
  sudo sysctl net.ipv6.conf.lo.disable_ipv6=0 &>/dev/null
  log_info "***** End to config ipv6 *****"
}

function save_build_result() {
  log_info "***** Start to save build result *****"
  committer_pr_x86_64_dir="/repo/openeuler/src-openeuler${repo_server_test_tail}/${giteeTargetBranch}/${giteeCommitter}/${giteeRepoName}/x86_64/${giteePullRequestIid}/"
  committer_pr_aarch64_dir="/repo/openeuler/src-openeuler${repo_server_test_tail}/${giteeTargetBranch}/${giteeCommitter}/${giteeRepoName}/aarch64/${giteePullRequestIid}/"
  global_x86_64_dir="/repo/openeuler/src-openeuler${repo_server_test_tail}/${giteeTargetBranch}/0X080480000XC0000000/${giteeRepoName}/x86_64/"
  global_aarch64_dir="/repo/openeuler/src-openeuler${repo_server_test_tail}/${giteeTargetBranch}/0X080480000XC0000000/${giteeRepoName}/aarch64/"

  log_info "***** Start to config remote shell *****"
  remote_place_cmd=$(
    cat <<EOF

if [[ -d "$committer_pr_x86_64_dir" && ("\$(ls -A $committer_pr_x86_64_dir | grep '\.rpm$')" || "\$(ls -A $committer_pr_x86_64_dir | grep '\.json$')") ]]; then
	if [[ ! -d "$global_x86_64_dir/report" ]]; then
		mkdir -p $global_x86_64_dir/report
	fi
	if [[ -d "$global_x86_64_dir" && "\$(ls -A $global_x86_64_dir | grep '\.rpm$')" ]]; then
		rm $global_x86_64_dir/*.rpm
	fi

    if [[ -d "$committer_pr_x86_64_dir" && "\$(ls -A $committer_pr_x86_64_dir | grep '\.rpm$')" ]]; then
		cp $committer_pr_x86_64_dir/*.rpm $global_x86_64_dir/
	fi
	if [[ -d "$committer_pr_x86_64_dir" && "\$(ls -A $committer_pr_x86_64_dir | grep '\.json$')" ]]; then
		cp $committer_pr_x86_64_dir/*.json $global_x86_64_dir/report/
	fi
fi
if [[ -d "$committer_pr_aarch64_dir" && ("\$(ls -A $committer_pr_aarch64_dir | grep '\.rpm$')" || "\$(ls -A $committer_pr_aarch64_dir | grep '\.json$')") ]]; then
	if [[ ! -d "$global_aarch64_dir/report" ]]; then
		mkdir -p $global_aarch64_dir/report
	fi
	if [[ -d "$global_aarch64_dir" && "\$(ls -A $global_aarch64_dir | grep '\.rpm$')" ]]; then
		rm $global_aarch64_dir/*.rpm
	fi

    if [[ -d "$committer_pr_aarch64_dir" && "\$(ls -A $committer_pr_aarch64_dir | grep '\.rpm$')" ]]; then
		cp $committer_pr_aarch64_dir/*.rpm $global_aarch64_dir/
	fi
	if [[ -d "$committer_pr_aarch64_dir" && "\$(ls -A $committer_pr_aarch64_dir | grep '\.json$')" ]]; then
		cp $committer_pr_aarch64_dir/*.json $global_aarch64_dir/report/
	fi
fi

EOF
  )
  echo "$remote_place_cmd"
  echo "https://gitee.com/src-openeuler/${giteeRepoName}/pulls/${giteePullRequestIid}"
  ssh -i ${SaveBuildRPM2Repo} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR root@${repo_server} "$remote_place_cmd"
  
  sed -i "s/dbhost=127.0.0.1/dbhost=${MysqldbHost}/g" ${JENKINS_HOME}/oecp/oecp/conf/oecp.conf
  sed -i "s/dbport=3306/dbport=${MysqldbPort}/g" ${JENKINS_HOME}/oecp/oecp/conf/oecp.conf
  python3 ${JENKINS_HOME}/oecp/cli.py -s ${giteeTargetBranch} --db-password ${MysqlUserPasswd:5} --pull-request-id ${giteeRepoName}-${giteePullRequestIid} --submit-symbol

  log_info "***** End to save build result *****"
}

# 执行入口
function main() {
  config_ipv6
  save_build_result
}
