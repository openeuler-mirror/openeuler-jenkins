"""
Avoid incomplete downloads due to redirection, use Gitee V5 API to get raw file.
"""
import base64
import os
import requests
import subprocess
import sys
from urllib.parse import urlparse


def repo_branches(owner, repo, access_token):
    request_url = 'https://gitee.com/api/v5/repos/{}/{}/branches'.format(owner, repo)
    params = {
        'access_token': access_token
    }
    r = requests.get(request_url, params=params)
    if r.status_code != 200:
        print('ERROR! Unexpected Error: {}'.format(r.content))
        sys.exit(1)
    return [x['name'] for x in r.json()]


def repo_file_content(owner, repo, branch, access_token, filepath):
    request_url = 'https://gitee.com/api/v5/repos/{}/{}/contents/{}'.format(owner, repo, filepath)
    params = {
        'ref': branch,
        'access_token': access_token
    }
    r = requests.get(request_url, params=params)
    if r.status_code == 404:
        return ''
    elif r.status_code != 200:
        print('ERROR! Unexpected Error: {}'.format(r.content))
        sys.exit(1)
    return r.json()['content']


def main():
    if len(sys.argv) < 3:
        print('ERROR! Lost of required source url and access token.')
        sys.exit(1)
    url = sys.argv[1]
    access_token = sys.argv[2]
    urlparse_res = urlparse(url)
    if urlparse_res.netloc != 'gitee.com':
        cmd = 'wget {}'.format(url)
        res = subprocess.call(cmd, shell=True)
        sys.exit(res)
    urlparse_path = urlparse_res.path
    if len(urlparse_path.split('/')) < 6:
        print('ERROR! You must apply a file address instead of a repo address.')
        sys.exit(1)
    _, owner, repo, fmt, branch_filepath = urlparse_path.split('/', 4)
    filename = branch_filepath.split('/')[-1]
    if fmt != 'raw':
        print('ERROR! Source file must be raw format.')
        sys.exit(1)
    branches = repo_branches(owner, repo, access_token)
    for branch in branches:
        if branch_filepath.startswith(branch) and len(branch_filepath.split(branch)) == 2:
            filepath = branch_filepath.split(branch + '/')[1]
            content_b64 = repo_file_content(owner, repo, branch, access_token, filepath)
            if not content_b64:
                continue
            content = base64.b64decode(content_b64)
            with open(filename, 'wb') as f:
                f.write(content)
            print('Download {} successfully.'.format(filename))
            break
    if not os.path.exists(filename):
        print('Download {} failed.'.format(filename))
        sys.exit(1)


if __name__ == '__main__':
    main()
