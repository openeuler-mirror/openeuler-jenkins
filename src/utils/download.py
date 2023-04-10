"""
Avoid incomplete downloads due to redirection, use Gitee V5 API to get raw file.
"""
import base64
import requests
import subprocess
import sys
from urllib.parse import urlparse


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
_, owner, repo, fmt, branch, filepath = urlparse_path.split('/', 5)
if fmt != 'raw':
    print('ERROR! Source file must be raw format.')
    sys.exit(1)
request_url = 'https://gitee.com/api/v5/repos/{}/{}/contents/{}'.format(owner, repo, filepath)
params = {
    'branch': branch,
    'access_token': access_token
}
r = requests.get(request_url, params=params)
if r.status_code != 200:
    print('ERROR! Unexpected Error: {}'.format(r.content))
    sys.exit(1)
content_b64 = r.json()['content']
content = base64.b64decode(content_b64)
filename = filepath.split('/')[-1]
with open(filename, 'wb') as f:
    f.write(content)
print('Downlaod {} successfully.'.format(filename))
