. ${shell_path}/src/lib/lib.sh
function get_pr_commit(){
    log_info "********get hotmetadata pr commit**********"
    rm -rf ${metadata_path}
    git clone https://${GiteeCloneUserName}:${GiteeClonePassword}@gitee.com/openeuler/hotpatch_meta.git

    cd ${metadata_path}

    if [[ ${giteePullRequestIid} ]]; then
        git fetch origin pull/$giteePullRequestIid/head:pr_$giteePullRequestIid
        git checkout pr_$giteePullRequestIid
    fi
    
    log_info "get source branch repo version"
    hotmetadata_file=`git diff --name-status HEAD~1 HEAD~0 | grep "hotmetadata_" | awk -F ' ' '{print $2}'`
    if [[ ! ${hotmetadata_file} ]]; then
        patch_path=`git diff --name-status HEAD~1 HEAD~0 | grep ".patch" |head -n 1|awk -F ' ' '{print $2}'`
        repo_path=${patch_path%/*}
        hotmetadata_file=${repo_path}/hotmetadata.xml
    fi
    branch=`echo ${hotmetadata_file} | awk -F '/' '{print $1}'`
    src_repo=`echo ${hotmetadata_file} | awk -F '/' '{print $2}'`
    repo_version=`echo ${hotmetadata_file} | awk -F '/' '{print $3}'`

    hotmetadata_file_path=${metadata_path}/${hotmetadata_file}

    cd ${WORKSPACE}

}

function scp_file_server(){
    log_info "***********copy hotpatch from ci_file_server**********"
    ci_server_dir="/repo/openeuler/hotpatch/hotpatch_meta/${giteePullRequestIid}"
    rm -rf ${hotpatch_path}
    mkdir ${hotpatch_path}
    scp -r -i ${SaveBuildRPM2Repo} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@${repo_server}:$ci_server_dir/aarch64 root@${repo_server}:$ci_server_dir/x86_64 root@${repo_server}:$ci_server_dir/source ${hotpatch_path}
    ls -ls  ${hotpatch_path}
}

function create_repo(){
    log_info "**********begin create repo**********"
    remote_hotpatch=/repo/openeuler/hotpatch/${branch}
    dailybuild_path="http://${dailybuild_ip}/hotpatch/${branch}"
    arch=(source x86_64 aarch64)
    for ar in ${arch[@]}
    do
        log_info "${ar} create repo"
        ssh -i ${update_key} -o StrictHostKeyChecking=no root@${dailybuild_ip} "mkdir -p $remote_hotpatch/${ar}/Packages $remote_hotpatch/${ar}/hotpatch_xml"
        scp -i ${update_key} -o StrictHostKeyChecking=no -r ${hotpatch_path}/${ar}/Packages/* root@${dailybuild_ip}:${remote_hotpatch}/$ar/Packages || log_warn "copy hotpatch failed"
        scp -i ${update_key} -o StrictHostKeyChecking=no -r ${hotpatch_path}/${ar}/hotpatch_xml/* root@${dailybuild_ip}:${remote_hotpatch}/$ar/hotpatch_xml || log_warn "copy updateinfo.xml failed"
        ssh -i ${update_key} -o StrictHostKeyChecking=no root@${dailybuild_ip} "cd ${remote_hotpatch}/$ar/Packages && createrepo --update -d ${remote_hotpatch}/$ar"
    done

}

function comment_issue(){
    log_info "**********comment hotpatch link to hotpatch issue**********"
    hotpatch_issue=`cat ${hotmetadata_file_path} | grep hotpatch_issue_link | sed 's/^.*<hotpatch_issue_link>//g' | sed 's/<\/hotpatch_issue_link>//g'| awk -F ' ' 'END {print}' `

    owner=`echo ${hotpatch_issue}|awk -F '/' '{print $4}'`
    repo=`echo ${hotpatch_issue}|awk -F '/' '{print $5}'`
    issue_number=`echo ${hotpatch_issue}|awk -F '/' '{print $7}'`
    log_info "get hotpatch issue body"
    get_body=`curl -X GET --header 'Content-Type: application/json;charset=UTF-8' 'https://gitee.com/api/v5/enterprises/open_euler/issues/'${issue_number}'?access_token='${token}`
    body=`echo ${get_body} |jq -r '.body'`

    issue_desc=`echo ${body}| sed 's/热补丁路径.*$//g'`
    ques=`echo ${issue_desc} | sed 's/热补丁元数据.*$//g'`
    metadata=`echo ${issue_desc#${ques}}`

    hotpatch_str="热补丁路径："
    updateinfo_str="热补丁信息："
    arch=(source x86_64 aarch64)
    for ar in ${arch[@]}
    do
        arch_rpm=`ls ${hotpatch_path}/$ar/Packages/`
        if [[ ${arch_rpm} ]]; then
            patch_arch_rpm="${dailybuild_path}/$ar/Packages/${arch_rpm}"
            hotpatch_str="${hotpatch_str}${patch_arch_rpm}\n"
        fi
        arch_updateinfo=`ls ${hotpatch_path}/$ar/hotpatch_xml/`
        if [[ ${arch_updateinfo} ]]; then
            patch_arch_updateinfo="${dailybuild_path}/$ar/hotpatch_xml/${arch_updateinfo}"
            updateinfo_str="${updateinfo_str}${patch_arch_updateinfo}\n"
        fi
    done

    echo $hotpatch_str
    echo $updateinfo_str

    log_info "comment hotpatch issue"

    body="${ques}\n${metadata}\n${hotpatch_str}\n${updateinfo_str}"
    #curl -X PATCH --header 'Content-Type: application/json;charset=UTF-8' 'https://gitee.com/api/v5/repos/'${owner}'/issues/'${issue_number} -d '{"access_token":"'"${token}"'","repo":"'"${repo}"'","body":"'"${body}"'"}'
    curl -X PATCH --header 'Content-Type: application/json;charset=UTF-8' 'https://gitee.com/api/v5/enterprises/open_euler/issues/'${issue_number} -d '{"access_token":"'"${token}"'","repo":"'"${repo}"'","body":"'"${body}"'"}'

}

function main(){
    metadata_path=${WORKSPACE}/hotpatch_meta
    hotpatch_path=${WORKSPACE}/hotpatch_pr_${giteePullRequestIid}
    sudo yum install -y jq
    get_pr_commit
    scp_file_server
    create_repo
    comment_issue
    cd ${metadata_path}
    log_info "delete remote branch"
    set +e
    branch_name=${giteeSourceBranch}
    if [[ $giteeSourceNamespace == "wanghuan158" || $giteeSourceNamespace == "openeuler" ]]; then
        if [[ $(git branch -a | grep ${branch_name}) ]]; then
            git push origin --delete ${branch_name}
        fi
    fi
    set -e
}

set +x
set +e
main
set -e
set +x

