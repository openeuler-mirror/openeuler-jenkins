import os
from jenkinsapi import jenkins as jenkins_api


class JenkinsLib(jenkins_api.Jenkins):
    def __init__(self, *args, **kwargs):
        super(JenkinsLib, self).__init__(*args, **kwargs)

    def create_user(self, username, password, fullname, email):
        body = {
            "username": username,
            "$redact": ["password1", "password2"],
            "password1": password,
            "password2": password,
            "fullname": fullname,
            "email": email}
        baseurl = os.getenv('BASEURL', '')
        url = "%s/securityRealm/createAccountByAdmin" % self.baseurl
        valid = self.requester.VALID_STATUS_CODES + [302, ]
        resp = self.requester.post_and_confirm_status(url, data=body,
                                                      valid=valid)
        return resp


def add_user_permissions(server, users, project):
    users_permissions = ''
    for user in users:
        users_permissions += '      <permission>com.cloudbees.plugins.credentials.CredentialsProvider.Create:{}' \
                             '</permission>\n'.format(user)
    for user in users:
        users_permissions += '      <permission>com.cloudbees.plugins.credentials.CredentialsProvider.Delete:{}' \
                             '</permission>\n'.format(user)
    for user in users:
        users_permissions += '      <permission>com.cloudbees.plugins.credentials.CredentialsProvider.ManageDomains:{}' \
                             '</permission>\n'.format(user)
    for user in users:
        users_permissions += '      <permission>com.cloudbees.plugins.credentials.CredentialsProvider.Update:{}' \
                             '</permission>\n'.format(user)
    for user in users:
        users_permissions += '      <permission>com.cloudbees.plugins.credentials.CredentialsProvider.View:{}' \
                             '</permission>\n'.format(user)
    for user in users:
        users_permissions += '      <permission>hudson.model.Item.Build:{}</permission>\n'.format(user)
    for user in users:
        users_permissions += '      <permission>hudson.model.Item.Cancel:{}</permission>\n'.format(user)
    for user in users:
        users_permissions += '      <permission>hudson.model.Item.Configure:{}</permission>\n'.format(user)
    for user in users:
        users_permissions += '      <permission>hudson.model.Item.Delete:{}</permission>\n'.format(user)
    for user in users:
        users_permissions += '      <permission>hudson.model.Item.Discover:{}</permission>\n'.format(user)
    for user in users:
        users_permissions += '      <permission>hudson.model.Item.Move:{}</permission>\n'.format(user)
    for user in users:
        users_permissions += '      <permission>hudson.model.Item.Read:{}</permission>\n'.format(user)
    for user in users:
        users_permissions += '      <permission>hudson.model.Item.Workspace:{}</permission>\n'.format(user)
    for user in users:
        users_permissions += '      <permission>hudson.model.Run.Delete:{}</permission>\n'.format(user)
    for user in users:
        users_permissions += '      <permission>hudson.model.Run.Update:{}</permission>\n'.format(user)
    for user in users:
        users_permissions += '      <permission>hudson.scm.SCM.Tag:{}</permission>\n'.format(user)
    conf = server.get_job_config(project)  # e.g. multiarch/openeuler/trigger/kernel
    newconf = conf.replace(
        '<inheritanceStrategy class="org.jenkinsci.plugins.matrixauth.inheritance.InheritParentStrategy"/>\n',
        '<inheritanceStrategy class="org.jenkinsci.plugins.matrixauth.inheritance.InheritParentStrategy"/>\n'
        + users_permissions)
    server.reconfig_job(project, newconf)


def config_image_level(server, node, project):
    arch = project.split('/')[2]
    conf = server.get_job_config(project)
    newconf = None
    if arch == 'x86-64':
        newconf = conf.replace('<assignedNode>k8s-x86-openeuler-20.03-lts-sp1</assignedNode>\n',
                               '<assignedNode>{}</assignedNode>\n'.format(node))
    elif arch == 'aarch64':
        newconf = conf.replace('<assignedNode>k8s-aarch64-openeuler-20.09</assignedNode>\n',
                               '<assignedNode>{}</assignedNode>\n'.format(node))
    server.reconfig_job(project, newconf)


def config_init_shell(server, init_shell, project):
    conf = server.get_job_config(project)
    if '<command/>\n' in conf:
        newconf = conf.replace('<command/>\n', '<command>{}</command>\n'.format(init_shell))
    else:
        newconf = conf.replace('<command></command>\n', '<command>{}</command>\n'.format(init_shell))
    server.reconfig_job(project, newconf)
