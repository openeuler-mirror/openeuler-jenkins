#!/bin/bash
# ******************************************************************************
# GitCode Action 门禁归档入口脚本（PR merge 后触发）
# 对应 Jenkins 时代的 approve 流水线（src/lib/approve.sh 的 main 流程）。
# 由 workflow (.gitcode/workflows/approve.yml) 注入 ACTION_* 环境变量，
# 本脚本将其映射为 approve.sh 所需的 Jenkins 变量，source 后调用 main()。
#
# 不修改 approve.sh 本体（Jenkins 侧零影响），差异点均在本脚本内适配：
#   1. lib.sh 硬编码路径 /home/jenkins/ci_check/src/lib/lib.sh 用软链接兜底；
#   2. config_ipv6 以函数覆盖方式去 sudo（action 容器以 root 直跑，无 sudo；
#      后定义的函数覆盖 approve.sh 内同名定义，main 调用时生效）。
#
# 环境变量约定（由 workflow 注入）：
#   ACTION_REPO:              仓库名
#   ACTION_PR_NUMBER:         PR 编号
#   ACTION_TARGET_BRANCH:     PR 目标分支
#   ACTION_COMMITTER:         PR 提交者
#   ACTION_VARIANT:           构建变体（可选，如 64k）
#   ACTION_SHELL_PATHEOE:     openeuler-jenkins 仓库路径
#   ACTION_MYSQL_HOST/PORT/USER_PASSWD: MySQL 连接（oecp 基线更新用）
#   ACTION_SSH_KEY_CONTENT:   文件服务器 SSH 私钥内容（本脚本落盘+规范化）
#   ACTION_REPO_SERVER:       文件服务器地址
#   ACTION_WORKSPACE:         工作目录（key 落盘位置）
#   ACTION_JENKINS_HOME:      jenkins home（oecp cli.py 所在）
# ******************************************************************************

# 路径与基础环境
shell_pathoe=${ACTION_SHELL_PATHEOE:-/tmp/openeuler-jenkins}
export JENKINS_HOME=${ACTION_JENKINS_HOME:-/home/jenkins}
export ACTION_WORKSPACE=${ACTION_WORKSPACE:-/tmp/approve-workspace}
mkdir -p "${ACTION_WORKSPACE}"

# approve.sh 依赖的 gitcode* 变量（Jenkins ci_check 流水线命名，保持原样映射）
export gitcodeRepoName=${ACTION_REPO}
export gitcodePullRequestId=${ACTION_PR_NUMBER}
export gitcodeTargetBranch=${ACTION_TARGET_BRANCH}
export gitcodeCommitter=${ACTION_COMMITTER}
export variant=${ACTION_VARIANT:-}

# MySQL（config_oecp_db 依赖，MysqlUserPasswd 格式 "用户名:密码"）
export MysqldbHost=${ACTION_MYSQL_HOST}
export MysqldbPort=${ACTION_MYSQL_PORT}
export MysqlUserPasswd=${ACTION_MYSQL_USER_PASSWD}

# 文件服务器
export repo_server=${ACTION_REPO_SERVER}

# SSH key 落盘+规范化（与 build_entry.sh 模式一致，ci.yml 只注入内容不写文件）：
# 规范化 Secret 保存时的常见残留（字面 \n 转义、CRLF 行尾、行首尾多余空白），
# 用完即删（trap 清理，任何退出路径不留私钥）
if [[ -n "${ACTION_SSH_KEY_CONTENT}" ]]; then
    ssh_key_file="${ACTION_WORKSPACE}/.ci_ssh_key"
    key_content="${ACTION_SSH_KEY_CONTENT//\\n/$'\n'}"
    printf '%s\n' "${key_content}" | tr -d '\r' |
        sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' >"${ssh_key_file}"
    chmod 600 "${ssh_key_file}"
    trap 'rm -f "${ssh_key_file}"' EXIT
    export SaveBuildRPM2Repo="${ssh_key_file}"
fi

# approve.sh 顶部硬编码 source /home/jenkins/ci_check/src/lib/lib.sh（Jenkins 路径），
# action 环境不存在该路径；建软链接兜底，使 approve.sh 的 source 幂等指向真实 lib.sh
# （容器为一次性环境，链接无残留问题）
mkdir -p /home/jenkins/ci_check/src/lib
ln -sf "${shell_pathoe}/src/lib/lib.sh" /home/jenkins/ci_check/src/lib/lib.sh

# 先 source 真实 lib.sh（log_info/log_warn/config_oecp_db 等函数）
source "${shell_pathoe}/src/lib/lib.sh"

# source approve.sh（定义 main()，本体不自动执行，由调用方触发）
source "${shell_pathoe}/src/lib/approve.sh"

# 覆盖 config_ipv6：action 容器以 root 直跑（无 sudo），直接调用 sysctl
config_ipv6() {
    log_info "***** Start to config ipv6 *****"
    sysctl net.ipv6.conf.lo.disable_ipv6=0 &>/dev/null
    log_info "***** End to config ipv6 *****"
}

# 执行主流程：临时目录 rpm/json 归档到正式位置 + oecp 基线更新（submit-symbol）
# 归档失败（ssh 不通/rpm 缺失等）以非零退出码结束 job，Action 运行页可见红色状态
main
exit $?
