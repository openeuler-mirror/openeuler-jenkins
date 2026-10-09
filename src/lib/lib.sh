#!/bin/echo Warning: this library should be sourced!

function log_info()
{
    echo "[`date +%Y-%m-%d\ %T`] [  INFO ] $@"
}

function log_warn()
{
    echo -e "\033[33m"[`date +%Y-%m-%d\ %T`] [WARNING] $@" \033[0m"
}

function log_error()
{
    echo -e "\033[31m"[`date +%Y-%m-%d\ %T`] [ ERROR ] $@" \033[0m"
    exit 1
}


function log_debug()
{
    [ "$DEBUG" == "yes" ] && echo "[`date +%Y-%m-%d\ %T`] [ DEBUG ] $@"
    echo -n ""
}

function clean_and_exit()
{
    
    if [ $1 -ne 0 ]; then
        echo "=========error start========="
        cat $ERROR_LOG
        echo "=========error end========="
    fi
    exit $1
}

function run_srcipt()
{
    script=$1
    shift
    args="$@"
    log_info "Start run $script $args at `date`"
    bash $script $args
    if [ $? -ne 0 ]; then
        log_error "Run $script $args failed at `date`"
    fi
    log_info "Finished run $script $args at `date`"
}

function config_oecp_db()
{
    # 配置 oecp 的数据库连接（dbhost/dbport/dbuser）
    # 依赖环境变量：MysqldbHost / MysqldbPort / MysqlUserPasswd / JENKINS_HOME
    # MysqlUserPasswd 格式为 "用户名:密码"，动态替换 oecp.conf 的 dbuser（不假设固定 root）
    # 格式守卫：缺分隔冒号时 ${MysqlUserPasswd%%:*} 与 ${MysqlUserPasswd#*:} 均退化为整串，
    # 会把用户名当密码用（连接失败且报错指向模糊）。此处告警并跳过配置，
    # oecp 连接失败已被调用侧容忍（|| echo continue），不影响构建主流程
    if [[ -z "${MysqlUserPasswd:-}" ]]; then
        log_warn "MysqlUserPasswd is empty, skip oecp db config"
        return 1
    fi
    if [[ "${MysqlUserPasswd}" != *:* ]]; then
        log_warn "MysqlUserPasswd format error (expect \"user:passwd\"), skip oecp db config"
        return 1
    fi
    sed -i "s/dbhost=127.0.0.1/dbhost=${MysqldbHost}/g" ${JENKINS_HOME}/oecp/oecp/conf/oecp.conf
    sed -i "s/dbport=3306/dbport=${MysqldbPort}/g" ${JENKINS_HOME}/oecp/oecp/conf/oecp.conf
    sed -i "s/^dbuser=.*/dbuser=${MysqlUserPasswd%%:*}/g" ${JENKINS_HOME}/oecp/oecp/conf/oecp.conf
}

function git_clone()
{
    url=$1
    #add_nameserver
    expect -c "
	set timeout -1
        spawn git clone $url
        expect {
                \"?(yes/no)*?\" {
                        send \"yes\r\"
                        exp_continue
                }
        }
"
}

function git_fetch()
{
    #add_nameserver
    expect -c "
        set timeout -1
        spawn git fetch
        expect {
                \"?(yes/no)*?\" {
                        send \"yes\r\"
                        exp_continue
                }
        }
"
}

function git_pull()
{
    #add_nameserver
    git reset --hard
    git clean -df
    expect -c "
        set timeout -1
        spawn git pull
        expect {
                \"?(yes/no)*?\" {
                        send \"yes\r\"
                        exp_continue
                }
        }
"
}

function git_checkout()
{
    br=$1
    expect -c "
        set timeout -1
        spawn git checkout $br
        expect { 
            \"?(yes/no)*?\" { send \"yes\r\"; exp_continue }
            eof { catch wait result; exit [lindex \$result 3] }
        }
        expect {
            eof { catch wait result; exit [lindex \$result 3] }
        }
"
}

function git_update()
{
    git_dir=/usr1/source_cache
    mkdir -p "${git_dir}"
    git_url="${1}"
    git_branch="${2}"
    git_name=${git_url##*/}
    git_name=${git_name%.git}
    old_pwd=`pwd`
    if [ -d "${git_dir}/${git_name}" ]; then
        cd "${git_dir}/${git_name}"
        if git branch -a | grep "remotes/origin/$git_branch"; then
            git_checkout "${git_branch}"
            git_pull
        elif git tag -l | grep "$git_branch"; then
            git reset --hard "$git_branch"
            echo "$git_branch already checkout"
        else
            git_fetch
            git_checkout "${git_branch}"
        fi
        cd $old_pwd &> /dev/null
    else
        cd "${git_dir}"
        git_clone "${git_url}"
        cd "${git_name}"
        git_checkout "${git_branch}"
        cd $old_pwd &> /dev/null
    fi
}
