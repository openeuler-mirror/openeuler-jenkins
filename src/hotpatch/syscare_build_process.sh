#!/bin/bash
shell_path=/home/jenkins/ci_check
. ${shell_path}/src/lib/lib.sh

function get_pr_commit(){
    log_info "***********get pr commit**********"
    rm -rf ${metadata_path}
    git clone https://gitee.com/${giteeTargetNamespace}/${giteeRepoName}
    cd ${metadata_path}

    if [[ ${giteePullRequestIid} ]]; then
        git fetch origin pull/$giteePullRequestIid/head:pr_$giteePullRequestIid
        git checkout pr_$giteePullRequestIid
    fi

    hotmetadata_path=`git diff --name-status HEAD~1 HEAD~0 | grep "hotmetadata_${mode}.xml" | awk -F ' ' '{print $2}'`
    patch_path=`git diff --name-status HEAD~1 HEAD~0 | grep ".patch" |head -n 1|awk -F ' ' '{print $2}'`

    echo ${hotmetadata_path}
    echo ${patch_path}

    if [[ ${hotmetadata_path} && ! ${patch_path} ]]; then
        log_warn "this pr not exist patch file."
        repo_path=${hotmetadata_path%/*}/patch
        echo ${repo_path}

    fi

    if [[ !${hotmetadata_path} && ${patch_path} ]]; then
        log_warn "this pr not exist patch hotmetadata.xml."
        repo_path=${patch_path%/*}
        hotmetadata_path=${repo_path%/*}/hotmetadata_${mode}.xml
    fi

    comment_branch=`echo $hotmetadata_path | awk -F '/' '{print $1}'`
    repo=`echo $hotmetadata_path | awk -F '/' '{print $2}'`
    repo_version=`echo $hotmetadata_path | awk -F '/' '{print $3}'`

    echo ${comment_branch}
    echo ${repo}

    hotmetadata_xml=${metadata_path}/${hotmetadata_path}
    repo_path=${metadata_path}/${repo_path}

    echo ${hotmetadata_xml}
    echo ${repo_path}

    cd ${root_path}

}

function gen_repo(){
    sudo sed -i "s/openEuler-22.03-LTS-SP1/${comment_branch}/g" /etc/yum.repo.d/openEuler.repo
    sudo cat /etc/yum.repo.d/openEuler.repo
}

function get_rpm_package(){
    # get src_url
    log_info "**********get rpm package from relase********"
    log_info "get source rpm"
    #src_url=`cat ${hotmetadata_xml} | grep SRC_RPM | sed 's/^.*<SRC_RPM>//g' | sed 's/<\/SRC_RPM>.*$//g'|awk -F " " 'END {print}' | sed -e 's#https://repo.openeuler.org#/repo/openeuler#'`
    #scp -i ${update_key} -o StrictHostKeyChecking=no root@${release_ip}:${src_url} . || log_error "get source rpm failed"
    src_url=`cat ${hotmetadata_xml} | grep SRC_RPM | sed 's/^.*<SRC_RPM>//g' | sed 's/<\/SRC_RPM>.*$//g'|awk -F " " 'END {print}'`
    wget ${src_url} || log_error "get source rpm failed"
    if [[ $arch == "x86_64" ]]; then
        log_info "get x86_64 debuginfo rpm"
        x86_debug_url=`cat ${hotmetadata_xml} | grep Debug_RPM_X86_64 | sed 's/^.*<Debug_RPM_X86_64>//g' | sed 's/<\/Debug_RPM_X86_64>.*$//g'|awk -F " " 'END {print}' | sed -e 's#https://repo.openeuler.org#/repo/openeuler#'`
        scp -i ${update_key} -o StrictHostKeyChecking=no root@${release_ip}:${x86_debug_url}  . || log_error "get x86 debuginfo failed"
    elif [[ $arch == "aarch64" ]]; then
        log_info "get aarch64 debuginfo rpm"
        aarch64_debug_url=`cat ${hotmetadata_xml} | grep Debug_RPM_Aarch64 | sed 's/^.*<Debug_RPM_Aarch64>//g' | sed 's/<\/Debug_RPM_Aarch64>.*$//g'|awk -F " " 'END {print}' | sed -e 's#https://repo.openeuler.org#/repo/openeuler#'`
        scp -i ${update_key} -o StrictHostKeyChecking=no root@${release_ip}:${aarch64_debug_url}  . || log_error "get aarch64 debuginfo failed"
    fi
}

function get_patch_package(){
    log_info "**********get patch file**********"
    rm -rf ${patch_dir}
    hotpatch=`cat ${update_info_file} | grep patch: | sed 's/^.*patch: //g'`
    echo ${hotpatch}
    mkdir ${patch_dir}
    
    all_patch=""
    log_info "copy patch to patch dir"
    for patch in ${hotpatch//,/ }
    do
    	echo $patch
    	cp $repo_path/$patch ${patch_dir}
	all_patch="$all_patch ${patch_dir}/$patch"
    done
    echo $all_patch
    ls -l ${patch_dir}

}

function install_build_require(){
    log_info "**********install buildrequire**********"
    #su - root
    rpm -ivh ${source_file}
    ls -l  /root/rpmbuild/SPECS
    dnf builddep -y  /root/rpmbuild/SPECS/*.spec
    if [[ ! $? ]];then
        log_error "install buildrequire failed!"
    fi
}

function syscare_build(){
    log_info "**********syscare build func*********"
    source_file=${src_url##*/}
    if [[ $arch == "x86_64" ]]; then
        debug_file=${x86_debug_url##*/}
    elif [[ $arch == "aarch64" ]]; then
        debug_file=${aarch64_debug_url##*/}
    fi
    # 安装spec依赖包
    install_build_require

    rm -rf ${hotpatch_dir}  ${hotpatch_src_dir}
    version=`cat ${update_info_file} | grep version: | sed 's/^.*version: //g'`
    log_info "pacth version:${version}"
    mkdir ${hotpatch_dir} ${hotpatch_src_dir}
    log_info "start syscare build------------"
    set -x

    echo $repo.spec>>/.build.command
    # 打包chroot环境
    #cp ${shell_path}/src/hotpatch/chroot_init_${arch}.sh /chroot_init.sh
    chmod 775 /chroot_init.sh
    ls -l /
    tar czf chroot_${arch}_pr${giteePullRequestIid}.tar.gz  --exclude=/etc/gpg-key/ --exclude=/bin/client --exclude=/proc/kcore --exclude=/chroot_${arch}_pr${giteePullRequestIid}.tar.gz /

    if [[ $mode == "ACC" ]]; then
        patch_name="ACC"
    else
    	patch_name=`echo ${patch_name}|sed 's/-/_/g'`
    fi
    syscare build --jobs 8 --patch-name ${patch_name} --patch-version ${curr_version} --patch-release ${curr_release} --source ${source_file} --debuginfo ${debug_file} --output ${hotpatch_dir} --patch ${all_patch}
    if [[ ! $? ]];then
        log_error "syscare build failed!"
    fi
    ls -l ${hotpatch_dir}

    hotpatch_src_filename=`ls ${hotpatch_dir}/*.src.rpm`
    mv ${hotpatch_src_filename} /${hotpatch_src_dir}

}

function generite_updateinfo(){
    log_info "**********generite updateinfo.xml**********"
    hotpatch_file=`ls ${hotpatch_dir}/patch*.rpm`
    updateinfo_path=${hotpatch_file%.*}.xml

    log_info "generite patch updateinfo--------"
    gen-updateinfo ${cve_type} "${issue_title}" ${issue_id} --reference-type ${type} --reference-id ${reference_id} --reference-href ${reference_href} --issued-date ${issued_date} --package-dir ${hotpatch_dir} --output-path ${updateinfo_path}
    cat ${updateinfo_path}

    if [[ $arch == "x86_64" ]]; then
        log_info "generite source updateinfo--------"
        updateinfo_src_path=${updateinfo_src_dir}/${hotpatch_src_filename%.*}.xml

        gen-updateinfo ${cve_type} "${issue_title}" ${issue_id} --reference-type ${type} --reference-id ${reference_id} --reference-href ${reference_href} --issued-date ${issued_date} --package-dir ${hotpatch_src_dir} --output-path ${updateinfo_src_path}
        cat ${updateinfo_src_path}
    fi
}


function scp_from_file_server(){
    log_info "**********scp update_info from ci_file_server********"
    ci_server_dir="/repo/openeuler/hotpatch/hotpatch_meta/${giteePullRequestIid}"
    scp -r -i ${SaveBuildRPM2Repo} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null  root@${repo_server}:$ci_server_dir/update_info $update_info_file || log_error "copy hotpatch updateinfo.xml failed"
    cat $update_info_file
}

function scp_to_file_server(){
    log_info "**********scp hotpatch to ci_file_server********"
    ci_server_dir="/repo/openeuler/hotpatch/hotpatch_meta/${giteePullRequestIid}"
    ssh -i ${SaveBuildRPM2Repo} -o StrictHostKeyChecking=no root@${repo_server} "mkdir -p $ci_server_dir/${arch}/Packages $ci_server_dir/${arch}/hotpatch_xml"
    #scp -i ${update_key} -o StrictHostKeyChecking=no -r hotpatch/patch*.rpm root@${dailybuild_ip}:${pkg_path}/$arch/Packages
    client --config /etc/gpg-key/signatrust.toml add --key-name openeuler-default-key --file-type rpm --key-type pgp ${hotpatch_dir}/patch*.rpm
    scp -r -i ${SaveBuildRPM2Repo} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null  ${hotpatch_dir}/patch*.rpm  root@${repo_server}:$ci_server_dir/${arch}/Packages || log_error "copy hotpatch failed"
    scp -r -i ${SaveBuildRPM2Repo} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null  ${updateinfo_path} root@${repo_server}:$ci_server_dir/${arch}/hotpatch_xml || log_error "copy hotpatch updateinfo.xml failed"
    if [[ $arch == "x86_64" ]]; then
      	ssh -i ${SaveBuildRPM2Repo} -o StrictHostKeyChecking=no root@${repo_server} "mkdir -p $ci_server_dir/source/Packages $ci_server_dir/source/hotpatch_xml"
        client --config /etc/gpg-key/signatrust.toml add --key-name openeuler-default-key --file-type rpm --key-type pgp ${hotpatch_src_dir}/*.src.rpm
        scp -r -i ${SaveBuildRPM2Repo} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null  ${hotpatch_src_dir}/*.src.rpm  root@${repo_server}:$ci_server_dir/source/Packages || log_error "copy source rpm failed"
        scp -r -i ${SaveBuildRPM2Repo} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null  ${updateinfo_src_path} root@${repo_server}:$ci_server_dir/source/hotpatch_xml || log_error "copy source updateinfo.xml failed"
    fi
    scp -r -i ${SaveBuildRPM2Repo} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null  chroot_${arch}_pr${giteePullRequestIid}.tar.gz root@${repo_server}:$ci_server_dir/ || log_error "copy chroot tar file failed"


}


function print_job(){
    job_name=`echo $JOB_NAME|sed -e 's#/#/job/#g'`
    job_path="https://openeulerjenkins.osinfra.cn/job/${job_name}/$BUILD_ID/console"
    body_str="${arch}架构热补丁构建，点击链接查看工程进度：${job_path}"
    curl -X POST --header 'Content-Type: application/json;charset=UTF-8' 'https://gitee.com/api/v5/repos/'${giteeTargetNamespace}'/'${giteeRepoName}'/pulls/'${giteePullRequestIid}'/comments' -d '{"access_token":"'"${token}"'","body":"'"${body_str}"'"}' || echo "comment source pr failed"
}


function get_para(){
    type=`cat ${update_info_file} | grep reference-type: | sed 's/^.*reference-type: //g'`
    cve_type=`cat ${update_info_file} | grep cve_type: | sed 's/^.*cve_type: //g'`
    issue_title=`cat ${update_info_file} | grep issue_title: | sed 's/^.*issue_title: //g'`
    issue_id=`cat ${update_info_file} | grep issue_id: | sed 's/^.*issue_id: //g'`
    reference_id=`cat ${update_info_file} | grep reference-id: | sed 's/^.*reference-id: //g'`
    reference_href=`cat ${update_info_file} | grep reference-href: | sed 's/^.*reference-href: //g'`
    issued_date=`cat ${update_info_file} | grep issued-date: | sed 's/^.*issued-date: //g'`
    mode=`cat ${update_info_file} | grep mode: | sed 's/^.*mode: //g'`
    curr_version=`cat ${update_info_file} | grep curr_version: | sed 's/^.*curr_version: //g'`
    curr_release=`cat ${update_info_file} | grep curr_release: | sed 's/^.*curr_release: //g'`
    patch_name=`cat ${update_info_file} | grep patch_name: | sed 's/^.*patch_name: //g'`

}

function main(){
    current_path=/hotpatch_cicd
    mkdir ${current_path}
    cd ${current_path}

    metadata_path=${current_path}/${giteeRepoName}
    update_info_file=${current_path}/update_info
    patch_dir=${current_path}/patch_dir
    hotpatch_dir=${current_path}/hotpatch_dir
    updateinfo_path=${current_path}/updateinfo_path
    hotpatch_src_dir=${current_path}/hotpatch_src_dir
    updateinfo_src_path=${current_path}/updateinfo_src_path
    modify_version_file=${current_path}/modify_version

    release_path=/repo/openeuler/${comment_branch}
    hotpatch_update_src_path=hotpatch_update/source/Packages

    update_key=/root/.ssh/id_rsa
    SaveBuildRPM2Repo=/root/.ssh/id_rsa

    rm -rf  ${hotpatch_src_dir}
    mkdir  ${hotpatch_src_dir}
    token=${GiteeeToken}

    echo ${giteeRepoName}
    echo ${giteeTargetNamespace}
    echo ${giteeTargetBranch}
    echo ${giteePullRequestIid}


    # 从远程服务器获取update_info
    scp_from_file_server
    cat ${update_info_file}
    
    # 解析update_info文件，获取需要的参数
    get_para

    # 获取pr最新提交内容
    get_pr_commit
    #gen_repo

    # 获取src、debuginfo包
    get_rpm_package

    # 获取本次制作热补丁需要的补丁包
    get_patch_package

    # 制作热补丁
    syscare_build

    # 生成updateinfo.xml
    generite_updateinfo

    # 归档包至远程服务器
    scp_to_file_server

}
set -x
main
set +x

