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

#function add_nameserver()
#{
#    grep -w "nameserver" /etc/resolv.conf | grep -v "#"
#    if [ "$?" != "0" ]; then
#        echo "search huawei.com">>/etc/resolv.conf
#        echo "nameserver 10.72.255.100">>/etc/resolv.conf
#        echo "nameserver 10.72.55.82">>/etc/resolv.conf
#        echo "nameserver 10.98.48.39">>/etc/resolv.conf
#    fi
#    set +e
#    ping -c 2 code.huawei.com
#    if [ "$?" != "0" ]; then
#        sleep 60
#        ping -c 6 code.huawei.com
#        if [ "$?" != "0" ]; then
#            sleep 120
#            ping -c 6 code.huawei.com
#            if [ "$?" != "0" ]; then
#                echo "can't connet to code.huawei.com"
#                exit 1
#            fi
#        fi
#    fi
#    set -e
#}

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
#    cat >id_rsa <<L_EOF
#-----BEGIN RSA PRIVATE KEY-----
#MIIEpAIBAAKCAQEA1P4eZu/VaHOCs8n/WzWq3W0GLkonJznOBEb+bQLWToAGcFfb
#ODOCe/vmcboBT1HGybPZyB8JYQTVUsVnIJ6ew5XxM8rLr+9nSMKxKG3RFIiKSr/R
#rhzVryUTNJbUVSJTtT+IlAMKj12ggjDhAESi96lTVZrmTNVHIBjiwcatlf5qiXX/
#Etb2E7u5TscIUh0iS8c4WmDVYjioj64zGlUZInjiyy4qo2ROKYF4DN25ftobkfRm
#pqNmVkwiydmPlHnpOLXxzL807q1xWBFQowSX3emKSeecIeh6ol7HeW4sjNmzRAhk
#g50RpOdqi4eN0UfgS8QdbKAqaFCz/0+dhukElwIDAQABAoIBAFtc5g2hsxkq81XL
#wA2P58sziQMyK7lXwldzXI/GN8dUg26NQSvKbJ5iX2dJMmaj3XGIBFMjfRJw0FDA
#/IuxfsjG+MAOrXC6cMN1QCjnclgseaW2wmq9U6vda2+Tg2FBaEbHCf7zjwQQVVmD
#PgCvcHhr2aNO3pr2oZvTEPGuF6fOwa/Jd7MdDnNwRrRz1/8XxuURzAycIsIrXvPM
#5b1h4DmB5CiR//p/mbrJAdUWr2w21DfgmIj6cN6uwea1AwJT/3bqXhSe+NXwkoVI
#rqY/yvw0b78ecrTLnXtUDPU2NkxmyjB9VL0M9JWLek76S/q+EbLdKvVFHitJmkRR
#pFN7KgECgYEA9X8uuRtj7z0o7Ihv/SL6XVZOCz71JlPwW4SpRB+6irF7h+hkIeNO
#cpo6N6HCu9xn3yzqV6HVgQ+h9X7Lwqx5+xbnOlp7RxxE6Gr1YFL0yE+UyvQ2MDSU
#Lmxv5dVzRdgItwvey2lYbUyawCusCEkukQOygX2Pdrvdj8M4K/+gkEcCgYEA3hru
#w3KrsN5z9tb/8hizGz5kL06iLrT7y/UzngUrssNwMK63mQcxNhehnkS1P8HccwuI
#q7U5MGAqiS6UMhpZYB44mNuiqLbI6cPrPPZSrVost0noVcAtOoRz+nitbZp4e8nx
#TyL+sI+qf+EzIo2wlOtEMBdsm+udMvg7NSkp4TECgYEA0dAn04ZIS7B+qGEXLUZW
#qazYOJ5PELnOg7kGnTVszZpQVGBWK+xEIIgVV3SFpN8DW2bcxZaHja0Zo2IBrViR
#S/pQFrw7/hN4BRdcrT1Y/VWeejJrmZlmR6Lfo5Ng2IGBOUgI2tom/Arre3AXsGEz
#TjbVufvgv/5hpruW52urA4MCgYEArc4bq9zPWGAsFSzYK0aC2j3vvkllhvFf3ZJr
#KyxWrtRbtezzhY/oRbEmayjPQS5eabTL5bqyHxYSEzndBHw0FpBvr8aoOiiXfr8v
#FYyY1Ektlt0CMCBsBE/kRkwrQwrPX+d+q3PyJI64WMwM7Ow+E7srqAqclkNBx8IS
#6x3kRPECgYBRCR23MOCKJ0wbdJaOyPVwYOT/2Roz+vcsb4ufVRVq4X2rACq7aaVg
#kW5Nkoovsw/UyY5lg8RalWPxKJ/vQ2pMwhbKZNVFgzBLJv+esjlUGrl55KatFrGI
#ZAIAY2MnglnEhNvkV7UDJfFJoKzgVGnvSsqyICeGKLNtZz9wAS+bug==
#-----END RSA PRIVATE KEY-----
#L_EOF
#
#cat >id_rsa.pub <<L_EOF
#ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDU/h5m79Voc4Kzyf9bNardbQYuSicnOc4ERv5tAtZOgAZwV9s4M4J7++ZxugFPUcbJs9nIHwlhBNVSxWcgnp7DlfEzysuv72dIwrEobdEUiIpKv9GuHNWvJRM0ltRVIlO1P4iUAwqPXaCCMOEARKL3qVNVmuZM1UcgGOLBxq2V/mqJdf8S1vYTu7lOxwhSHSJLxzhaYNViOKiPrjMaVRkieOLLLiqjZE4pgXgM3bl+2huR9Gamo2ZWTCLJ2Y+Ueek4tfHMvzTurXFYEVCjBJfd6YpJ55wh6HqiXsd5biyM2bNECGSDnRGk52qLh43RR+BLxB1soCpoULP/T52G6QSX eulerosci@huawei.com
#L_EOF
#    key_dir=/root/.ssh
#    rm -rf ${key_dir}/
#    mkdir -p ${key_dir}
#    chmod 700 ${key_dir}
#    cp id_rsa ${key_dir}/
#    chmod 600  ${key_dir}/id_rsa
#    cp id_rsa.pub ${key_dir}/
#    chmod 644  ${key_dir}/id_rsa.pub
    
    #add_nameserver
    
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
