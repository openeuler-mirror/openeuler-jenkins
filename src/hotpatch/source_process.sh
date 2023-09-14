release_path=/repo/openeuler/${giteeTargetBranch}
src_path=source/Packages
update_src_path=update/source/Packages
hotpatch_update_src_path=hotpatch_update/source/Packages
. ${shell_path}/src/lib/lib.sh

function ver_maintainer(){
    if [[ ! ${trustlist} =~ ${comment_user} ]];then
        check_result=`curl -X GET --header 'Content-Type: application/json;charset=UTF-8' 'https://gitee.com/api/v5/repos/'${giteeTargetNamespace}'/'${giteeRepoName}'/collaborators?access_token='${token}'&page=1&per_page=100'`
        maintainer_list=`echo ${check_result}|jq -r '.[].login'`
        echo $maintainer_list
        if [[ ! ${maintainer_list[@]} =~ ${comment_user} ]]; then
            comment_error_src_pr "你没有制作热补丁的权限，请联系sig maintianer。"
            log_error "You do not have the permission to make hotpatch. Only maintianer can make hotpatch."
        fi
    fi
}

function print_job(){
    job_name=`echo $JOB_NAME|sed -e 's#/#/job/#g'`
    job_path="https://openeulerjenkins.osinfra.cn/job/${job_name}/$BUILD_ID/console"
    body_str="热补丁制作流程已启动，正在创建热补丁issue和生成热补丁元数据并提交pr至hotpatch_meta仓库，请不要重复提交命令。\n点击链接查看工程进度：${job_path}\n热补丁issue及hotpatch_meta仓作用参考：https://gitee.com/openeuler/hotpatch_meta/blob/master/README.md"
    curl -X POST --header 'Content-Type: application/json;charset=UTF-8' 'https://gitee.com/api/v5/repos/'${giteeTargetNamespace}'/'${giteeRepoName}'/pulls/'${giteePullRequestIid}'/comments' -d '{"access_token":"'"${token}"'","body":"'"${body_str}"'"}' || echo "comment source pr failed"
}

function ver_comment(){
    comment_array=(${comment})
    if [[ ${#comment_array[@]} -eq 7 || ${#comment_array[@]} -eq 6 ]]; then
        version=${comment_array[1]}
        mode=${comment_array[2]}
        if [[ ${#comment_array[@]} -eq 7 ]]; then
            patch_name=${comment_array[3]}
            cve_issue=${comment_array[5]}
            commet_branch=${comment_array[6]}
        elif [[ ${#comment_array[@]} -eq 6 ]]; then
            cve_issue=${comment_array[4]}
            commet_branch=${comment_array[5]}
        fi
    else
        body_str="makehotpatch命令格式错误，请参考如下格式：\n\
  \`\`\`text
  /makehotpatch <version> <mode> <patch_name> <patch_type> <issue_id> <os_branch>\n
  version:    源码包版本号，必填\n\
  mode:       热补丁包演进方式<ACC/SGL>， 必填\n\
  patch_name: 冷补丁包名，支持多个patch包，按顺序传入，以逗号隔开，src-openeuler下的仓库必填；kernel仓库不用填，门禁会自动打包patch文件\n\
  patch_type: 修复的问题类型<cve/bugfix/feature>，必填\n\
  issue_id:   修复问题的issue id，必填\n\
  os_branch:  本次热补丁基于哪个分支做，必填\n\`\`\`"
        comment_error_src_pr ${body_str}
        log_error "makehotpatch命令格式错误，请参考如下格式：/makehotpatch <version> <mode> <patch_name> <patch_type> <cve_issue_id> <os_branch>"
    fi
    echo ${cve_issue}
    echo ${mode}
    echo ${commet_branch}
    echo ${patch_name}
    echo ${version}

    release_path=/repo/openeuler/${commet_branch}
}

function get_src_rpm(){
    # get src_url
    log_info "**********get source rpm in release**********"
    if [[ mode == "ACC" ]]; then
        src_hotpatch_update_name=`ssh -i ${update_key} -o StrictHostKeyChecking=no -o LogLevel=ERROR root@${release_ip} "cd ${release_path}/${hotpatch_update_src_path} && ls | grep ${giteeRepoName}-${version} | tail -n 1"`|| echo ""
    else
        src_hotpatch_update_name=""
    fi

    if [[ $src_hotpatch_update_name ]]; then
        src_url="https://repo.openeuler.org/${commet_branch}/${hotpatch_update_src_path}/${src_hotpatch_update_name}"
    else
        src_update_name=`ssh -i ${update_key} -o StrictHostKeyChecking=no -o LogLevel=ERROR root@${release_ip} "cd ${release_path}/${update_src_path} && ls | grep ${giteeRepoName}-${version}"`|| echo ""
        if [[ $src_update_name ]]; then
            src_url="https://repo.openeuler.org/${commet_branch}/${update_src_path}/${src_update_name}"
        else
            src_name=`ssh -i ${update_key} -o StrictHostKeyChecking=no root@${release_ip} "cd ${release_path}/${src_path} && ls | grep ${giteeRepoName}-${version}"`|| echo ""
            if [[ $src_name ]]; then
                src_url="https://repo.openeuler.org/${commet_branch}/${src_path}/${src_name}"
            else
                comment_error_src_pr "没有找到${giteeRepoName}包${version}版本源码包"
                log_error "${giteeRepoName} not found ${version} source rpm"
            fi
        fi
    fi
    echo ${src_url}
}

function get_debuginfo_url(){
    arch=$1
    log_info "***********get ${arch} debuginfo rpm in release**********"
    debuginfo_path=debuginfo/${arch}/Packages
    update_debuginfo_path=update/${arch}/Packages
    debug_name=`ssh -i ${update_key} -o StrictHostKeyChecking=no root@${release_ip} "cd ${release_path}/${debuginfo_path} && ls | grep ${giteeRepoName}-debuginfo-${version}"`|| echo ""
    if [[ $debug_name ]]; then
        debug_url="https://repo.openeuler.org/${commet_branch}/${debuginfo_path}/${debug_name}"
    else
        debug_name=`ssh -i ${update_key} -o StrictHostKeyChecking=no root@${release_ip} "cd ${release_path}/${update_debuginfo_path} && ls | grep ${giteeRepoName}-debuginfo-${version}"`|| echo ""
        if [[ $debug_name ]];then
             debug_url="https://repo.openeuler.org/${commet_branch}/${update_debuginfo_path}/${debug_name}"
        else
            comment_error_src_pr "没有找到${giteeRepoName}包${version}版本${arch}架构debuginfo包"
            log_error "${giteeRepoName} not found ${version} ${arch} debuginfo rpm"
        fi
    fi
}

function get_debuginfo_rpm(){
    # get debug_url
    get_debuginfo_url "x86_64"
    x86_debug_url=$debug_url
    echo ${x86_debug_url}

    get_debuginfo_url "aarch64"
    aarch64_debug_url=$debug_url
    echo ${aarch64_debug_url}
}

function get_patch(){
    rm -rf $giteeRepoName
    git clone -b $giteeTargetBranch --depth 1  https://gitee.com/$giteeTargetNamespace/$giteeRepoName
    cd $giteeRepoName
    if [[ ${openeuler_support} =~ ${giteeRepoName} ]]; then
        log_info "***********get openeuler pr patch file*********"
        wget https://gitee.com/$giteeTargetNamespace/kernel/pulls/$giteePullRequestIid.patch
        patch_list="$giteePullRequestIid.patch"
    else
        echo
        log_info "**********get src-openeuler ${giteeRepoName} patch file**********"
        git fetch origin pull/$giteePullRequestIid/head:pr_$giteePullRequestIid
        git checkout pr_$giteePullRequestIid
        patch_list=`echo ${patch_name}|sed -e 's/,/ /g'`
        changed_patch=`git diff --name-status HEAD~1 HEAD~0 | grep ".patch" | awk -F ' ' '{print $2}'`
        if [[ $changed_patch ]]; then
            for patch in ${patch_list[@]}
            do
                if [[ ! `echo $changed_patch | grep $patch` ]]; then
                    comment_error_src_pr "补丁文件：${patch}不存在"
                    log_error "补丁文件：${patch}不存在"
                fi
            done
        fi
    fi

    patch_path=`pwd`
    cd ..
}

function judge_laster_version_release(){
    log_info "**********judge laster version release**********"
    curr_version=`cat ${hotmetadata_xml} | grep "<hotpatch version="| sed 's/<hotpatch version=//g' | sed 's/ type=.*$//g'|awk -F " " 'END {print}'|sed 's/\"//g'`
    curr_release=`cat ${hotmetadata_xml} | grep "release="| sed 's/.*release=//g' | sed 's/ type=.*$//g'|awk -F " " 'END {print}'|sed 's/\"//g'`

    echo "curr_version:$curr_version"
    echo "curr_release:$curr_release"

    curr_version=$((10#${curr_version}))
    curr_release=$((10#${curr_release}))

    if [[ func == "update" ]];then
        last_release=$curr_release-1
    else
        last_release=$curr_release
    fi
    echo $last_release

    if [[ $last_release -ge 1 ]];then
        src_hotpatch_update_name=`ssh -i ${update_key} -o StrictHostKeyChecking=no -o LogLevel=ERROR root@${release_ip} "cd ${release_path}/${hotpatch_update_src_path} && ls | grep ${repo}-${repo_version} | grep ACC-${curr_version}-${last_release}"`|| echo ""
        echo $src_hotpatch_update_name
        if [[ ! $src_hotpatch_update_name ]]; then
           src_url="https://repo.openeuler.org/${comment_branch}/${hotpatch_update_src_path}/${src_hotpatch_update_name}"
           comment_error_src_pr "上一个热补丁版本：${curr_version}-${last_release}未发布，不允许新增version"
           log_error "上一个热补丁版本未发布，不允许新增version"
        fi
    fi
}

function get_pr_patch_file(){
    if [[ $open_pr_result ]];then
        open_pr_id=${open_pr_result##*/}
        if [[ ${open_pr_id} ]]; then
            git fetch origin pull/${open_pr_id}/head:pr_${open_pr_id}
            git checkout pr_${open_pr_id}
            pr_patch_list=`git diff --name-status HEAD~1 HEAD~0 | grep ".patch"| awk -F ' ' '{print $2}'`
            echo ${pr_patch_list}
        fi
    fi
}

function gen_hot_patch_metadata(){
    log_info "************genarate hotpatch metadata**********"
    # 生成远程临时分支，用来提交pr
    create_remote_branch

    export PYTHONPATH=${shell_path}
    # 生成hotmetadata.xml文件
    python3 ${shell_path}/src/hotpatch/gen_hotmetadata_xml.py -f ${func} -c ${giteeTargetNamespace} -t ${token} -p `echo ${patch_list}|sed -e 's/ /,/g'` -b ${commet_branch} -r ${giteeRepoName} -pr ${giteePullRequestIid} -o ${metadata_path} -i ${hotpatch_issue_file} -m "${comment}" -l  "${src_url},${x86_debug_url},${aarch64_debug_url}"
    if [ $? -ne 0 ];then
        # 报错后删除临时分支
        if [[ $(git branch -a | grep ${branch_name}) && !${open_pr_result} ]]; then
            git push origin --delete ${branch_name}
        fi
    else
        # 获取pr提交的patch文件列表，用来删除上次提交的文件
        get_pr_patch_file
        git checkout ${branch_name}
        # 删除源分支已打开pr提交的文件
        pr_patch_list=(${pr_patch_list})
        echo ${pr_patch_list}
        for patch in ${pr_patch_list[@]}
        do
            rm -f $patch
        done

        log_info "copy patch file to hotmetadata"
        for patch in ${patch_list[@]}
        do
            cp ${patch_path}/${patch} ${metadata_path}/${commet_branch}/${giteeRepoName}/${version}/patch/
        done

        ls -l ${metadata_path}/${commet_branch}/${giteeRepoName}/${version}
        cat ${hotmetadata_xml}

        set +e
        log_info "git push"
        git add .
        git commit -m "Hotpatch repair"
        git push
        set -e
        # 向hotpatch_meta仓库提交pr
        create_pr
    fi
}

function create_remote_branch(){
    log_info "**********create remote branch for pr**********"
    branch_name="hotpatch_${commet_branch}_${giteeRepoName}_${version}_${giteePullRequestIid}"
    echo $branch_name
    branch_result=`curl -X POST --header 'Content-Type: application/json;charset=UTF-8' 'https://gitee.com/api/v5/repos/openeuler/hotpatch_meta/branches' -d '{"access_token":"'"${CicdToken}"'","refs":"master","branch_name":"'"${branch_name}"'"}'`
    if [[ `echo ${branch_result} | grep "分支名已存在"` ]]; then
        branch_exist=`curl -X GET --header 'Content-Type: application/json;charset=UTF-8' 'https://gitee.com/api/v5/repos/openeuler/hotpatch_meta/branches/'${branch_name}'?access_token='${CicdToken}`
        branch_creater=`echo ${branch_exist} | jq -r '.commit.commit.author.name'`
        echo ${branch_creater}
        if [[ ${branch_creater} != ${GiteeCloneUserName} ]]; then
            comment_error_src_pr "私人分支${branch_name}已存在，不能创建分支"
        fi
        func="update"
        # 查看源分支是否有打开的pr
        pr_result=`curl -X GET --header 'Content-Type: application/json;charset=UTF-8' 'https://gitee.com/api/v5/repos/openeuler/hotpatch_meta/pulls?access_token='${CicdToken}'&state=open&head='${branch_name}'&sort=created&direction=desc&page=1&per_page=20'` || echo "get source branch open pr failed"
        open_pr_result=`echo ${pr_result} | jq -r '.[].html_url'`
        echo ${open_pr_result}
        if [[ !{open_pr_result} ]]; then
                func="add"
        fi
    else
        func="add"
    fi
    echo ${func}

    rm -rf hotpatch_meta
    git clone https://${GiteeCloneUserName}:${GiteeClonePassword}@gitee.com/openeuler/hotpatch_meta.git
    cd hotpatch_meta

    # 切换到临时的远程分支
    git branch --track  ${branch_name} remotes/origin/${branch_name}
    git checkout ${branch_name}

    # 判断上个版本的version是否已发布，未发布不能新增version
    metadata_path=`pwd`
    if [[ $mode == "SGL" ]]; then
        hotmetadata_xml=${metadata_path}/${commet_branch}/${giteeRepoName}/${version}/hotmetadata_SGL.xml
    else
        hotmetadata_xml=${metadata_path}/${commet_branch}/${giteeRepoName}/${version}/hotmetadata_ACC.xml
    fi

    if [[ -e $hotmetadata_xml && $mode == "ACC" ]];then
        judge_laster_version_release
    fi
}

function create_pr(){
    log_info "**********create pr to commit hotmetadata**********"
    title="[hotpatch]fix ${cve_issue}"
    head=${branch_name}
    base="master"

    log_info "**********create pr**********"
    pr_result=`curl -X POST --header 'Content-Type: application/json;charset=UTF-8' 'https://gitee.com/api/v5/repos/openeuler/hotpatch_meta/pulls' -d '{"access_token":"'"${CicdToken}"'","title":"'"${title}"'","base":"master","head":"'"${branch_name}"'"}'`
    if [[ $(echo ${pr_result}|grep "已存在相同源分支、目标分支的 Pull Request") ]]; then
        pr_url=`echo ${pr_result}|jq -r '.message'| sed 's/^.*<a href=//g' | sed 's/>.*$//g'| sed 's/\"//g'`
        pr_link="https://gitee.com/${pr_url}"
    else
        pr_link=`echo ${pr_result}|jq -r '.html_url'`
    fi
    echo ${pr_link}
    # 元数据pr链接返回给源码仓pr
    comment_src_pr
}

function comment_src_pr(){
    log_info "**********comment hotmetadata pr link to source pr********"
    hotpatch_issue=`cat ${hotpatch_issue_file}`
    echo ${hotpatch_issue}
    body_str="In response to this:\n > ${comment}  \n\n命令执行结果：\n热补丁issue链接：${hotpatch_issue} \n后续热补丁流程请在hotpatch_meta仓库pr跟踪，链接如下: ${pr_link}"
    curl -X POST --header 'Content-Type: application/json;charset=UTF-8' 'https://gitee.com/api/v5/repos/'${giteeTargetNamespace}'/'${giteeRepoName}'/pulls/'${giteePullRequestIid}'/comments' -d '{"access_token":"'"${token}"'","body":"'"${body_str}"'"}' || echo "comment source pr failed"
}

function comment_error_src_pr(){
    log_info "**********comment hotmetadata pr link to source pr********"
    body_str="In response to this:\n > ${comment}  \n\n命令执行结果：\n $1 "
    curl -X POST --header 'Content-Type: application/json;charset=UTF-8' 'https://gitee.com/api/v5/repos/'${giteeTargetNamespace}'/'${giteeRepoName}'/pulls/'${giteePullRequestIid}'/comments' -d '{"access_token":"'"${token}"'","body":"'"${body_str}"'"}' || echo "comment source pr failed"
    log_error $1
}

function main(){
    echo ${giteeRepoName}
    echo ${giteeTargetNamespace}
    echo ${giteeTargetBranch}
    curr_path=`pwd`
    hotpatch_issue_file=$curr_path/hotpatch_issue

    # 校验是否为maintainer评论
    ver_maintainer

    # 打印工程链接
    print_job

    # 校验参数
    ver_comment

    # 获取source包地址
    get_src_rpm
    # 获取debuginfo包地址
    get_debuginfo_rpm

    # 获取本次的patch包
    get_patch

    sudo yum install -y python3-pip
    pip3 install -i https://repo.huaweicloud.com/repository/pypi/simple -r  ${shell_path}/src/requirements

    # hotpatch_meta仓库代码生成并提交pr
    gen_hot_patch_metadata

}

set -x
main
set +x
