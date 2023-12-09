. ${shell_path}/src/lib/lib.sh

function print_job(){
    job_name=`echo $JOB_NAME|sed -e 's#/#/job/#g'`
    job_path="https://openeulerjenkins.osinfra.cn/job/${job_name}/$BUILD_ID/console"
    body_str="热补丁构建入口：<a href=${job_path}>multiarch/src-openeuler/syscare-patch/trigger/Hotpatch_matedata</a>，当前构建号为 $BUILD_ID\n\
热补丁构建: <a href=https://openeulerjenkins.osinfra.cn/job/multiarch/job/src-openeuler/job/syscare-patch/job/aarch64/job/Hotpatch_matedata/>multiarch/src-openeuler/syscare-patch/aarch64/Hotpatch_matedata</a>,\
<a href=https://openeulerjenkins.osinfra.cn/job/multiarch/job/src-openeuler/job/syscare-patch/job/x86_64/job/Hotpatch_matedata/>multiarch/src-openeuler/syscare-patch/x86_64/Hotpatch_matedata</a>\n\
热补丁构建结果回显: <a href=https://openeulerjenkins.osinfra.cn/job/multiarch/job/src-openeuler/job/syscare-patch/job/comment/job/Hotpatch_matedata/>multiarch/src-openeuler/syscare-patch/comment/Hotpatch_matedata</a>"
    curl -X POST --header 'Content-Type: application/json;charset=UTF-8' 'https://gitee.com/api/v5/repos/'${giteeTargetNamespace}'/'${giteeTargetRepoName}'/pulls/'${giteePullRequestIid}'/comments' -d '{"access_token":"'"${token}"'","body":"'"${body_str}"'"}' || echo "comment source pr failed"
}

function get_pr_commit(){
    log_info "***********get pr commit**********"
    rm -rf ${giteeTargetRepoName}
    git clone https://gitee.com/${giteeTargetNamespace}/${giteeTargetRepoName}
    cd ${metadata_path}

    if [[ ${giteePullRequestIid} ]]; then
        git fetch origin pull/$giteePullRequestIid/head:pr_$giteePullRequestIid
        git checkout pr_$giteePullRequestIid
    fi

    check_whether_multiple_packages
    cd ${current_path}
}

function check_whether_multiple_packages(){
    log_info "**********check whether multiple packages********"
    hotmetadata_list=`git diff --name-status HEAD~1 HEAD~0 | grep "hotmetadata_" | awk -F ' ' '{print $2}'`
    patch_list=`git diff --name-status HEAD~1 HEAD~0 | grep ".patch" |awk -F ' ' '{print $2}'`

    echo ${hotmetadata_list}
    echo ${patch_list}

    # 如果多个hotmetadata.xml有变更，报错不支持多软件包同时制作热补丁；
    if [[ ! ${hotmetadata_list} ]]; then
        repo_path_metadata=""
        log_warn "this pr not exist patch hotmetadata.xml."
    else
        if [[ ${#hotmetadata_list[@]} -gt 2 ]]; then
            comment_error_src_pr "不支持多个包同时制作热补丁"
            #log_error "Hotpatch cannot be created for multiple packages at the same time."
        else
            hotmetadata_path=${hotmetadata_list}
            log_info "only have one hotmetadata.xml."
            repo_path_metadata=${hotmetadata_path%/*}
            echo $repo_path_metadata
        fi
    fi

    # 如果有多个patch包，需要都是同一包同一版本的patch包，否则报错不支持多软件包同时制作热补丁
    if [[ ! ${patch_list} ]]; then
        repo_path_patch=""
        patch_list="null"
        log_warn "this pr not exist patch file."
    else
        patch_list=(${patch_list})
        if [[ ${#patch_list[@]} -gt 2 ]]; then
            repo_path_patch=${patch_list[0]%/*}
            echo $repo_path_patch
            for patch in ${patch_list[@]:1}
            do
                repo_path_tmp=${patch%/*}
                echo $repo_path_tmp
                if [[ $repo_path_patch != $repo_path_tmp ]]; then
                    comment_error_src_pr "不支持多个包同时制作热补丁"
                    #log_error "Hotpatch cannot be created for multiple packages at the same time."
                fi
            done
        else
            log_info "only have one patch."
            repo_path_patch=${patch_list%/*}
        fi
    fi

    # patch包需要和hotmetadata.xml包版本保持一致，否则认为是多个软件包同时制作热补丁
    if [[ $repo_path_metadata && $repo_path_patch ]]; then
        if [[ $repo_path_patch != $repo_path_metadata/patch ]]; then
            comment_error_src_pr "不支持多个包同时制作热补丁"
            #log_error "Hotpatch cannot be created for multiple packages at the same time."
        fi
    fi

    if [[ $repo_path_metadata ]]; then
        repo_path=$repo_path_metadata
    elif [[ $repo_path_patch ]]; then
        repo_path=$repo_path_patch
    else
        comment_error_src_pr "元数据文件和补丁文件没有变动，制作热补丁流程结束"
        exit 1
    fi

    comment_branch=`echo $repo_path | awk -F '/' '{print $1}'`
    repo=`echo $repo_path | awk -F '/' '{print $2}'`
    repo_version=`echo $repo_path | awk -F '/' '{print $3}'`

    echo ${comment_branch}
    echo ${repo}

    if [[ `echo ${hotmetadata_list} | grep "ACC"` ]]; then
        mode="ACC"
    else
        mode="SGL"
    fi

    hotmetadata_xml=${metadata_path}/${hotmetadata_list}
    repo_path=${metadata_path}/${repo_path}

    echo ${hotmetadata_xml}
    echo ${repo_path}
}

function check_laster_version_release(){
    if [[ -e ${modify_version_file} ]];then
        modify_list=`cat $modify_version_file`
        pre_version_release=`cat ${modify_version_file} | grep pre_version_release: | sed 's/^.*pre_version_release://g'`
        if [[ $pre_version_release ]]; then
            src_hotpatch_update_name=`ssh -i ${update_key} -o StrictHostKeyChecking=no -o LogLevel=ERROR root@${release_ip} "cd ${release_path}/${hotpatch_update_src_path} && ls | grep ${repo}-${repo_version} | grep ${pre_version_release}"`|| echo ""
            if [[ ! $src_hotpatch_update_name ]]; then
               src_url="https://repo.openeuler.org/${comment_branch}/${hotpatch_update_src_path}/${src_hotpatch_update_name}"
               comment_error_src_pr "上一个热补丁版本：${pre_version_release}未发布，不允许新增热补丁版本"
               #log_error "上一个热补丁版本未发布，不允许新增version"
            fi
        fi
    fi
}

function check_version_release(){
    release_path=/repo/openeuler/${comment_branch}
    hotpatch_update_src_path=hotpatch_update/source/Packages
    if [[ -e ${modify_version_file} ]];then
        modify_list=`cat ${modify_version_file} | grep modify_list: | sed 's/^.*modify_list://g'`
        echo $modify_list
        if [[ $modify_list ]]; then
            for ver in ${modify_list[@]}
            do
                src_hotpatch_update_name=`ssh -i ${update_key} -o StrictHostKeyChecking=no -o LogLevel=ERROR root@${release_ip} "cd ${release_path}/${hotpatch_update_src_path} && ls | grep ${repo}-${repo_version} | grep ${ver}"`|| echo ""
                if [[ $src_hotpatch_update_name ]]; then
                   src_url="https://repo.openeuler.org/${comment_branch}/${hotpatch_update_src_path}/${src_hotpatch_update_name}"
                   comment_error_src_pr "热补丁版本：${ver}已发布，不允许修改。发布路径为：$src_url"
                   #log_error "热补丁已发布，不允许修改，发布路径为：$src_url"
                fi
            done
        fi
    fi
}

function comment_error_src_pr(){
    log_info "**********comment hotmetadata pr link to pr********"
    body_str="热补丁制作流程已中止，$1 "
    curl -X POST --header 'Content-Type: application/json;charset=UTF-8' 'https://gitee.com/api/v5/repos/'${giteeTargetNamespace}'/'${giteeTargetRepoName}'/pulls/'${giteePullRequestIid}'/comments' -d '{"access_token":"'"${token}"'","body":"'"${body_str}"'"}' || echo "comment pr failed"
    log_info "create tag"
    curl -X DELETE --header 'Content-Type: application/json;charset=UTF-8' 'https://gitee.com/api/v5/repos/'${giteeTargetNamespace}'/'${giteeTargetRepoName}'/pulls/'${giteePullRequestIid}'/labels/ci_successful?access_token=0557ff54fd91c4170ecdd523ff1bba47'
    curl -X DELETE --header 'Content-Type: application/json;charset=UTF-8' 'https://gitee.com/api/v5/repos/'${giteeTargetNamespace}'/'${giteeTargetRepoName}'/pulls/'${giteePullRequestIid}'/labels/ci_processing?access_token=0557ff54fd91c4170ecdd523ff1bba47'
    curl -X POST --header 'Content-Type: application/json;charset=UTF-8' 'https://gitee.com/api/v5/repos/'${giteeTargetNamespace}'/'${giteeTargetRepoName}'/pulls/'${giteePullRequestIid}'/labels?access_token=0557ff54fd91c4170ecdd523ff1bba47' -d '"[\"ci_failed\"]"'
    log_error $1
}

function scp_file_server(){
    log_info "**********scp update_info to ci_file_server********"
    ci_server_dir="/repo/openeuler/hotpatch/hotpatch_meta/${giteePullRequestIid}"
    cat ${update_info_file}
    if [[ -e ${update_info_file} ]];then
        ssh -i ${SaveBuildRPM2Repo} -o StrictHostKeyChecking=no root@${repo_server} "mkdir -p $ci_server_dir/"
        scp -r -i ${SaveBuildRPM2Repo} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null  $update_info_file  root@${repo_server}:$ci_server_dir/ || log_error "copy hotpatch failed"
    fi
}

function main(){
    current_path=`pwd`
    metadata_path=${current_path}/hotpatch_meta
    update_info_file=${current_path}/update_info
    modify_version_file=${current_path}/modify_version

    echo ${giteeTargetRepoName}
    echo ${giteeTargetNamespace}
    echo ${giteeTargetBranch}
    echo ${giteePullRequestIid}

    # 打印当前工程链接
    print_job

    # 获取pr最新提交内容
    get_pr_commit

    # 解析metadata.xml获取信息
    export PYTHONPATH=${shell_path}
    python3 ${shell_path}/src/hotpatch/make_hotpatch.py -t ${token} -i ${hotmetadata_xml} -o ${update_info_file} -c ${giteeTargetNamespace} -r ${giteeTargetRepoName} -pr ${giteePullRequestIid} -p ${patch_list} -m ${mode}
    cat ${update_info_file}

    # 判断最近一次版本是否已被发布
    check_laster_version_release

    # 判断本次变更的版本是否已被发布
    check_version_release

    # 归档包至远程服务器
    scp_file_server

}
set -x
main
set +x

