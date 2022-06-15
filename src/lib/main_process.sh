#!/bin/bash
. ${shell_path}/src/lib/lib.sh
JENKINS_HOME=/home/jenkins
SCRIPT_PATCH=${shell_path}/src/build
BUILD_ROOT=${JENKINS_HOME}/agent/buildroot
RPM_PATH=${BUILD_ROOT}/home/abuild/rpmbuild/RPMS
support_arch_file=${repo}_${prid}_support_arch
comment_file=""

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

#配置osc
function config_osc() {
  log_info "***** Start to config osc *****"
  cat >${JENKINS_HOME}/.oscrc <<EOF
[general]
apiurl = http://117.78.1.88
no_verify = 1
build-root = ${BUILD_ROOT}

[http://117.78.1.88]
user = ${OBSUserName}
pass = ${OBSPassword}
trusted_prj = openEuler:22.03:LTS:LoongArch:selfbuild:BaseOS openEuler:22.03:LTS:selfbuild:BaseOS openEuler:22.03:LTS:Next:selfbuild:BaseOS openEuler:20.03:LTS:SP3:selfbuild:BaseOS openEuler:selfbuild:BaseOS openEuler:20.03:LTS:selfbuild:BaseOS openEuler:selfbuild:function openEuler:20.09:selfbuild:BaseOS openEuler:20.03:LTS:SP1:selfbuild:BaseOS openEuler:21.03:selfbuild:BaseOS openEuler:20.03:LTS:SP2:selfbuild:BaseOS openEuler:21.09:selfbuild:BaseOS openEuler:20.03:LTS:Next:selfbuild:BaseOS # 不用输0,1,2了
EOF
  log_info "***** End to config osc *****"
}

#配置华为云maven源，备用镜像源https://mirrors.huaweicloud.com/repository/maven/
#编译过程会将.m2文件内容复制到maven的配置文件中
function config_maven() {
  log_info "***** Start to config maven *****"
  cat >${JENKINS_HOME}/.m2 <<EOF
<settings>
    <mirrors>
        <mirror>
            <id>huaweimaven</id>
            <mirrorOf>*</mirrorOf>
      		  <name>huaweicloud maven</name>
      		  <url>https://repo.huaweicloud.com/repository/maven/</url>
        </mirror>
    </mirrors>
</settings>
EOF
  log_info "***** End to config maven *****"
}

#配置华为云gradle源
function config_gradle() {
  log_info "***** Start to config gradle *****"
  cat >${JENKINS_HOME}/.gradle <<EOF
allprojects {
    buildscript {
        repositories {
            maven { url "https://repo.huaweicloud.com/repository/maven/" }

        }
    }
    repositories {
        maven { url "https://repo.huaweicloud.com/repository/maven/" }

    }
}
EOF
  log_info "***** End to config gradle *****"
}

# 启动ipv6 loopback
function config_ipv6() {
  log_info "***** Start to config ipv6 *****"
  sudo sysctl net.ipv6.conf.lo.disable_ipv6=0 &>/dev/null
  sudo su - root <<FEOF
text=\$(cat /etc/resolv.conf)
echo "nameserver 100.125.1.250" > /etc/resolv.conf
for i in \$text; do
	echo \$i >> /etc/resolv.conf
done
FEOF
  log_info "***** End to config ipv6 *****"
}

# 从src-openeuler下载kernel代码
function download_kernel_repo_soe() {
  log_info "***** Start to download kernel of src-openeuler *****"
  git init kernel
  cd kernel
  git fetch --depth 4 https://gitee.com/${repo_owner}/kernel +refs/pull/${prid}/MERGE:pr_${prid}
  git checkout pr_${prid}
  cd ../
  log_info "***** End to download kernel of src-openeuler *****"
}

# 根据tag下载kernel代码
function download_kernel_repo_of_tag() {
    kernel_tag=$(cat kernel/SOURCE)
    log_info "now clone kernel source of tag ${kernel_tag} to code/kernel"
    git clone -b $kernel_tag --depth 1 https://${GiteeUserName}:${GiteePassword}@gitee.com/openeuler/kernel code/kernel
}

download_kernel_times=0 # 避免下载多次kernel
# 下载kernel代码
function download_kernel_repo() {
  log_info "***** Start to download kernel of openeuler *****"
  if [[ $download_kernel_times -gt 0 ]]; then
    log_info "already clone kernel source"
    return
  fi

  ((download_kernel_times += 1))

  if [[ -d code/kernel ]]; then
    rm -rf code/kernel
  fi

  if [ "x$repo" == "xkernel" ]; then
    download_kernel_repo_soe
    download_kernel_repo_of_tag
  elif [ "x$1" == "xkernel" ]; then
    log_info "***** Start to download the branch ${tbranch} of kernel in src-openeuler *****"
    git clone -b $tbranch --depth 1 https://gitee.com/${repo_owner}/kernel
    download_kernel_repo_of_tag
  else
    log_info "now clone kernel source of branch ${tbranch}"
    git clone -b $tbranch --depth 1 https://${GiteeUserName}:${GiteePassword}@gitee.com/openeuler/kernel code/kernel
  fi

  # 处理 "Installed (but unpackaged) file" 异常
  rm -rf $WORKSPACE/code/kernel/.git
  log_info "***** End to download kernel of openeuler *****"
}

# 下载关联仓库代码，某些仓库编译依赖其他仓库代码
function download_buddy_repo() {
  log_info "***** Start to download buddy rpm *****"
  # download buddy repo
  for item in $(echo ${buddy} | sed 's/,/ /g'); do
    #对kernel特殊处理
    if [[ "x$item" == "xkernel" ]]; then
      download_kernel_repo $item
    elif [[ "x$item" != "x$repo" ]]; then
      log_info "clone ${item} of branch $tbranch"
      git clone -b $tbranch --depth 1 https://${GiteeUserName}:${GiteePassword}@gitee.com/${repo_owner}/${item}
    fi
  done
  log_info "***** End to download buddy rpm *****"
}

# 防止复用pod，强制清除一些文件和目录
function drop_pod_cache() {
  log_info "***** Start to clean pod env *****"
  rm -rf /tmp/local_code/xdf/repo

  # 解挂buildroot目录
  set +e
  mount | grep buildroot | awk '{print $3}' | sudo xargs umount &>/dev/null
  set -e

  if [[ -d ${BUILD_ROOT} ]]; then
    sudo chmod -R 777 ${BUILD_ROOT} # buildroot mode is 444, owner and group is root
    rm -rf ${BUILD_ROOT}
  fi

  # check abi comment
  if [[ -e $WORKSPACE/${repo}_${prid}_${arch}_comment ]]; then
    rm $WORKSPACE/${repo}_${prid}_${arch}_comment
  fi
  if [[ -e $WORKSPACE/${repo}_${prid}_${arch}_compare_result ]]; then
    rm $WORKSPACE/${repo}_${prid}_${arch}_compare_result
  fi
  log_info "***** End to clean pod env *****"
}

# 编译软件包和执行install
function build_packages() {
  log_info "***** Start to build package *****"
  comment_file="${repo}_${prid}_${arch}_comment"
  export PYTHONPATH=${shell_path}
  for item in $(echo ${package} | sed 's/,/ /g'); do
    log_info "start build package $item"
    log_debug "params are [$repo, $branch, $prid, $committer, $arch, $package, $buddy, $WORKSPACE]"

    if [[ "x${item}" == "xkernel" ]]; then
      python3 ${SCRIPT_PATCH}/osc_build_k8s.py -o ${repo_owner} -p $item -a $arch -c $WORKSPACE -b $tbranch -r ${repo} -m ${commentid} --pr ${prid} -t ${GiteeUserPassword} --spec "kernel.spec"
    else
      python3 ${SCRIPT_PATCH}/osc_build_k8s.py -o ${repo_owner} -p $item -a $arch -c $WORKSPACE -b $tbranch -r ${repo} -m ${commentid} --pr ${prid} -t ${GiteeUserPassword}
    fi

    log_info "copy build package from root to home"
    sudo su - root <<FEOF
    if [[ -d ${BUILD_ROOT}/root/rpmbuild/ && "$(sudo ls -A ${BUILD_ROOT}/root/rpmbuild/)" ]]; then
      mkdir -p ${BUILD_ROOT}/home/abuild/rpmbuild/
      sudo cp -r ${BUILD_ROOT}/root/rpmbuild/* ${BUILD_ROOT}/home/abuild/rpmbuild/
    fi
FEOF
    log_debug "check install"
    python3 ${SCRIPT_PATCH}/extra_work.py checkinstall -a ${arch} -r $tbranch  --obs_rpm_host ${obs_rpm_host} --install-root=${WORKSPACE}/install_root/${commentid} -e $WORKSPACE/${comment_file} || echo "continue although run check install failed"

    log_debug "pkgship notify"
    if [[ "x$item" == "xpkgship" ]]; then
      scp -r -i ${SaveBuildRPM2Repo} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@${repo_server}:/repo/soe${repo_server_test_tail}/pkgship pkgship_notify
      python3 ${SCRIPT_PATCH}/extra_work.py notify -p ${repo} -a ${arch} -n ${pkgship_notify_url} -t ${pkgship_notify_token} -l "http://${repo_server}" -m pkgship_notify -u ${PkgShipUserName} -w ${PkgShipPassword} || echo "continue although run pkgship notify error"
    fi
  done
  log_info "***** End to build package *****"
}

# 比较软件包差异
function compare_package() {
  log_info "***** Start to compare package diff *****"
  old_dir="${WORKSPACE}/old_rpms/"
  new_dir="${WORKSPACE}/new_rpms/"
  result_dir="${WORKSPACE}/oecp_result"
  if [[ -d $old_dir ]]; then
    rm -rf $old_dir
  fi
  if [[ -d $new_dir ]]; then
    rm -rf $new_dir
  fi
  if [[ -d $result_dir ]]; then
    rm -rf $result_dir
  fi
  mkdir -p $old_dir
  mkdir -p $new_dir
  mkdir -p $result_dir

  if [[ -d ${RPM_PATH}/${arch} && "$(ls -A ${RPM_PATH}/${arch})" ]]; then
    cp ${RPM_PATH}/${arch}/*.rpm $new_dir
  fi

  if [[ -d ${RPM_PATH}/noarch && "$(ls -A ${RPM_PATH}/noarch)" ]]; then
    cp ${RPM_PATH}/noarch/*.rpm $new_dir
  fi
  if [[ $(ssh -i ${SaveBuildRPM2Repo} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR root@${repo_server} test -e "root@${repo_server}:/repo/openeuler/src-openeuler${repo_server_test_tail}/${tbranch}/0X080480000XC0000000/${repo}/${arch}/") ]]; then
    log_info "try download rpms from ci server"
    scp -r -i ${SaveBuildRPM2Repo} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR root@${repo_server}:/repo/openeuler/src-openeuler${repo_server_test_tail}/${tbranch}/0X080480000XC0000000/${repo}/${arch}/*.rpm $old_dir
  fi
  if [[ ! "$(ls -A $old_dir | grep '.rpm')" && "$(ls -A $new_dir | grep '.rpm')" ]]; then
    log_info "try download rpms from obs server"
    python3 ${SCRIPT_PATCH}/extra_work.py getrelatedrpm -r $tbranch -p ${item} -a ${arch} || echo "continue although run get related rpm failed"
    if [[ -d binaries && "$(ls -A binaries | grep '\.rpm$')" ]]; then
      cp binaries/*.rpm $old_dir
    fi
  fi

  if [[ "$(ls -A $new_dir | grep '.rpm')" ]]; then
    python3 ${JENKINS_HOME}/oecp/cli.py $old_dir $new_dir -o $result_dir -w $result_dir -n 2 -f json || echo "continue although run oecp failed"
  fi

  pr_link='https://gitee.com/${repo_owner}/'${repo}'/pulls/'${prid}
  pr_commit_json_file="${WORKSPACE}/pr_commit_json_file"
  curl https://gitee.com/api/v5/repos/${repo_owner}/${repo}/pulls/${prid}/files?access_token=$GiteeToken >$pr_commit_json_file
  compare_result="${repo}_${prid}_${arch}_compare_result"

  if [[ ! "$(ls -A $old_dir | grep '.rpm')" || ! "$(ls -A $new_dir | grep '.rpm')" ]]; then
    echo "this is first commit PR"
    python3 ${SCRIPT_PATCH}/extra_work.py comparepackage --ignore -p ${repo} -j $result_dir/report-$old_dir-$new_dir/osv.json -pr $pr_link -pr_commit $pr_commit_json_file -f $WORKSPACE/${compare_result} || echo "continue although run compare package failed"
  else
    python3 ${SCRIPT_PATCH}/extra_work.py comparepackage -p ${repo} -j $result_dir/report-$old_dir-$new_dir/osv.json -pr $pr_link -pr_commit $pr_commit_json_file -f $WORKSPACE/${compare_result} || echo "continue although run compare package failed"
  fi

  # run before save rpm, reset remote dir
  fileserver_user_path="/repo/openeuler/src-openeuler${repo_server_test_tail}/${tbranch}/${committer}/${repo}/${arch}/${prid}"
  fileserver_tmpfile_path="/repo/soe${repo_server_test_tail}/check_item"
  remote_dir_reset_cmd=$(
    cat <<EOF
if [[ ! -d "$fileserver_user_path" ]]; then
	mkdir -p $fileserver_user_path
fi
if [[ \$(ls -A "$fileserver_user_path" | grep ".rpm") ]]; then
	rm $fileserver_user_path/*.rpm
fi
if [[ \$(ls -A "$fileserver_user_path" | grep ".json") ]]; then
	rm $fileserver_user_path/*.json
fi
if [[ ! -d "$fileserver_tmpfile_path" ]]; then
	mkdir -p $fileserver_tmpfile_path
fi
if [[ -e "$fileserver_tmpfile_path/${compare_result}" ]]; then
	rm $fileserver_tmpfile_path/${compare_result}
fi
if [[ -e "$fileserver_tmpfile_path/${comment_file}" ]]; then
	rm $fileserver_tmpfile_path/${comment_file}
fi
EOF
  )
  #echo "$remote_dir_reset_cmd"
  ssh -i ${SaveBuildRPM2Repo} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR root@${repo_server} "$remote_dir_reset_cmd"

  log_info "save result"
  if [[ -e $result_dir/report-$old_dir-$new_dir/osv.json && "$(ls -A $old_dir | grep '.rpm')" && "$(ls -A $new_dir | grep '.rpm')" ]]; then
    old_any_rpm=$(ls $old_dir | head -n 1)
    old_version=$(rpm -q $old_dir/$old_any_rpm --queryformat '%{version}\n')
    old_release=$(rpm -q $old_dir/$old_any_rpm --queryformat '%{release}\n')
    old_release=${old_release%%\.oe1}
    new_any_rpm=$(ls $new_dir | head -n 1)
    new_version=$(rpm -q $new_dir/$new_any_rpm --queryformat '%{version}\n')
    new_release=$(rpm -q $new_dir/$new_any_rpm --queryformat '%{release}\n')
    new_release=${new_release%%\.oe1}

    new_json_name=${repo}_${old_version}-${old_release}_${new_version}-${new_release}.json
    scp -r -i ${SaveBuildRPM2Repo} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR $result_dir/report-$old_dir-$new_dir/osv.json root@${repo_server}:/repo/openeuler/src-openeuler${repo_server_test_tail}/${tbranch}/${committer}/${repo}/${arch}/${prid}/$new_json_name
  fi
  if [[ -d $new_dir && "$(ls -A $new_dir | grep '.rpm')" ]]; then
    scp -r -i ${SaveBuildRPM2Repo} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR $new_dir/* root@${repo_server}:/repo/openeuler/src-openeuler${repo_server_test_tail}/${tbranch}/${committer}/${repo}/${arch}/${prid}/
  fi
  if [[ -e $compare_result ]]; then
    scp -r -i ${SaveBuildRPM2Repo} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR ${compare_result} root@${repo_server}:$fileserver_tmpfile_path/${compare_result}
  fi
  if [[ -e $comment_file ]]; then
    scp -r -i ${SaveBuildRPM2Repo} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR ${comment_file} root@${repo_server}:$fileserver_tmpfile_path/${comment_file}
  fi

  python3 ${shell_path}/src/utils/oemaker_analyse.py --branch ${tbranch} --arch ${arch} \
	--oecp_json_path "$result_dir/report-$old_dir-$new_dir/osv.json" --owner "src-openeuler" \
	--repo ${repo} --gitee_token $GiteeToken --prid ${prid}
  log_info "***** End to compare package diff *****"
}

# 执行入口
function main() {
  config_osc
  config_ipv6
  config_maven
  config_gradle
  download_buddy_repo
  drop_pod_cache
  exclusive_arch=$arch
  scp -r -i ${SaveBuildRPM2Repo} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@${repo_server}:/repo/soe${repo_server_test_tail}/support_arch/${support_arch_file} . || echo "${support_arch_file}" not exist
  ls -l .
  if [[ -e ${support_arch_file} ]]; then
    support_arch=`cat ${support_arch_file}`
    if [[ $support_arch != *$arch* ]]
    then
      exclusive_arch=""
    fi
  fi
  if [[ $exclusive_arch ]]; then
    log_info "exclusive_arch not empty"
    build_packages
    compare_package
  fi
}
