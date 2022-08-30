import logging
import jenkins
import os
import random
import requests
import subprocess
import sys
import time
import yaml
from django.http import JsonResponse
from multiprocessing import Process
from rest_framework.generics import GenericAPIView
from projects_builders.permissions import HookPermission
from utils.authing import get_token, search_member, create_authing_user, add_member
from utils.jenkins import JenkinsLib, add_user_permissions, config_image_level, config_init_shell
from utils.send_login_info import sendmail


logger = logging.getLogger('log')
BASEURL = os.getenv('BASEURL', '')
JENKINS_URL = os.getenv('JENKINS_URL', '')
JENKINS_USERNAME = os.getenv('JENKINS_USERNAME', '')
JENKINS_PASSWORD = os.getenv('JENKINS_PASSWORD', '')
AUTHING_USERID = os.getenv('AUTHING_USERID', '')
AUTHING_SECRET = os.getenv('AUTHING_SECRET', '')
if not (JENKINS_URL and JENKINS_USERNAME and JENKINS_PASSWORD and AUTHING_USERID and AUTHING_SECRET and BASEURL):
    logger.error('Please check environment variables, exit...')
    sys.exit(1)


def get_diff_files(organization, repo, number):
    url = 'https://gitee.com/{}/{}/pulls/{}.diff'.format(organization, repo, number)
    r = requests.get(url)
    if r.status_code != 200:
        logger.error('Error! Cannot locate difference file of Pull Request. status code: {}'.format(r.status_code))
        sys.exit(1)
    diff_files = [x.split(' ')[0][2:] for x in r.text.split('diff --git ')[1:]]
    return diff_files


def conn_jenkins(url, username, password):
    """
    Connect to jenkins server
    :return: jenkins server
    """
    server = jenkins.Jenkins(url=url, username=username, password=password, timeout=120)
    return server


def base_log(pr_url, hook_name, action):
    logger.info('URL of Pull Request: {}'.format(pr_url))
    logger.info('Hook Name: {}'.format(hook_name))
    logger.info('Action: {}'.format(action))


def pull_code(owner, repo):
    if repo in os.listdir():
        subprocess.call('rm -rf {}'.format(repo), shell=True)
    subprocess.call('git clone https://gitee.com/{}/{}.git'.format(owner, repo), shell=True)


def run(owner, repo, number):
    logger.info('Step 1: Get list of repos ready to build projects')
    # 获取更变文件名列表
    diff_files = get_diff_files(owner, repo, number)

    # 获取doc/openeuler-ci/下新增yaml文件的路径
    waiting_repos = []
    for diff_file in diff_files:
        file_path = os.path.join(repo, diff_file)
        if len(diff_file.split('/')) == 2 and \
                diff_file.split('/')[0] == 'openeuler-ci' and \
                diff_file.split('/')[-1].endswith('.yaml'):
            waiting_repos.append(file_path)
    if not waiting_repos:
        logger.info('Notice there is no repo needs to build jenkins projects, exit...')
        return

    logger.info('Step 2: Pull code')
    # 拉取目标仓库代码
    pull_code(owner, repo)

    logger.info('Step 3: Build Jenkins projects')
    # 连接Jenkins server
    server = conn_jenkins(JENKINS_URL, JENKINS_USERNAME, JENKINS_PASSWORD)

    for waiting_repo in waiting_repos:
        # 获取yaml文件的关键字段
        f = open(waiting_repo, 'r')
        ci_config = yaml.safe_load(f)
        f.close()
        repo_name = ci_config.get('repo_name')
        init_shell = ci_config.get('init_shell')
        container_level = ci_config.get('container_level')
        users = ci_config.get('users')
        parameters = {
            'action': 'create',
            'template': 'openeuler-jenkins',
            'jobs': repo_name,
            'repo_server': 'repo-service.dailybuild'
        }
        # 新增jenkins工程
        server.build_job(name='multiarch/openeuler/jobs-crud/_entry', parameters=parameters)
        logger.info('Build Jenkins projects for openeuler/{}'.format(repo_name))

        # 查看工程是否创建成功
        x86_project = 'multiarch/openeuler/x86-64/{}'.format(repo_name)
        aarch64_project = 'multiarch/openeuler/aarch64/{}'.format(repo_name)
        projects_created = False
        retest = 5
        while retest > 0:
            time.sleep(60)
            if server.get_job_name(x86_project) == repo_name and server.get_job_name(aarch64_project) == repo_name:
                logger.info('Notice projects x86-64 & aarch64 for {} had been created.'.format(repo_name))
                projects_created = True
                break
            retest -= 1
        if not projects_created:
            logger.info('Fail to create all projects for repo {}'.format(repo_name))
            continue

        if not users:
            logger.info('Notice no users need to create and config, continue...')
            continue
        if not isinstance(users, list):
            logger.error('ERROR! The field `users` must be a List Type, continue...')
            continue
        for user in users:
            if not isinstance(user, dict):
                logger.error('ERROR! The user must be a Dict Type, which content is :\n{}'.format(user))
                continue
            try:
                login_name = user['login_name']
                name = user.get('name')
                email_addr = user['email']
            except KeyError:
                logger.error('ERROR! A user must declare its username and email_address.')
                continue
            # Authing授权、分组
            logger.info('Create Authing users and add users to group')
            authing_token = get_token(AUTHING_USERID, AUTHING_SECRET)
            member_id = create_authing_user(authing_token, AUTHING_USERID, email_addr)
            add_member(authing_token, AUTHING_USERID, 'openeuler-jenkins', member_id)
            # 创建Jenkins用户、发送邮件并添加权限
            logger.info('Create and config Jenkins users.')
            login_password = str(random.randint(100000, 999999))
            jenkinslib = JenkinsLib(BASEURL, JENKINS_USERNAME, JENKINS_PASSWORD, useCrumb=True, timeout=180)
            res = jenkinslib.create_user(login_name, login_password, name, email_addr)
            if res.status_code == 200:
                sendmail(login_name, login_password, email_addr)
        # 配置users权限
        user_list = [user['login_name'] for user in users]
        add_user_permissions(server, user_list, x86_project)
        add_user_permissions(server, user_list, aarch64_project)
        # 修改x86-64和aarch64的指定node
        logger.info('Config container level')
        with open('utils/container_level_mapping.yaml', 'r') as f:
            container_level_mapping = yaml.safe_load(f)
        x86_node = container_level_mapping.get('x86').get(container_level)
        aarch64_node = container_level_mapping.get('aarch64').get(container_level)
        config_image_level(server, x86_node, x86_project)
        config_image_level(server, aarch64_node, aarch64_project)
        # 修改x86-64和aarch64的初始脚本
        logger.info('Config init shell')
        config_init_shell(server, init_shell, x86_project)
        config_init_shell(server, init_shell, aarch64_project)
    logger.info('Finish dealing with the Merge Hook, waiting next Merge Hook.')


class HookView(GenericAPIView):
    permission_classes = (HookPermission,)

    def post(self, request, *args, **kwargs):
        data = self.request.data
        hook_name = data['hook_name']
        action = data['action']
        pr_url = data['pull_request']['html_url']
        base_log(pr_url, hook_name, action)
        owner = pr_url.split('/')[-4]
        repo = pr_url.split('/')[-3]
        number = pr_url.split('/')[-1]
        p1 = Process(target=run, args=(owner, repo, number))
        p1.start()
        return JsonResponse({'code': 200, 'msg': 'OK'})

