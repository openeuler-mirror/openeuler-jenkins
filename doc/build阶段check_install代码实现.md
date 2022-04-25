# Build阶段check_install代码分析

check_install的代码在：https://gitee.com/openeuler/openeuler-jenkins/src/build/extra_work.py

## 在extra_work中添加checkinstall方法

功能：用来检查在门禁中编译的rpm包是否可以进行安装

```python
    # 添加子命令 checkinstall
    parser_checkinstall = subparsers.add_parser('checkinstall', help='add help')
    parser_checkinstall.add_argument("-r", type=str, dest="branch_name", help="obs project name")
    parser_checkinstall.add_argument("-a", type=str, dest="arch", help="build arch")
    parser_checkinstall.add_argument("-e", type=str, dest="comment_file", help="check install result comment")
    parser_checkinstall.add_argument("--install-root", type=str, dest="install_root",
                                     help="check install root dir")
    parser_checkinstall.set_defaults(func=checkinstall)
```

## 调用checkinstall方法

```
check_install_rpm(self, branch_name, arch, install_root, comment_file):
```

#### **参数解析**

branch_name: 分支名
arch: cpu架构
install_root: 安装根路径
comment_file：用来保存check_install结果的文件路径，在后面comment上报时会用到

#### **准备install root directory**

```python
_ = not os.path.exists(install_root) and os.makedirs(install_root)
logger.info("create install root directory: %s", install_root)
```

#### **准备repo文件**

```python
repo_source = OBSRepoSource("http://119.3.219.20:82")   # obs 实时构建repo地址
obs_branch_list = Constant.GITEE_BRANCH_PROJECT_MAPPING.get(branch_name, [])
repo_config = repo_source.generate_repo_info(obs_branch_list, arch, "check_install")
logger.info("repo source config:\n%s", repo_config)

with open("obs_realtime.repo", "w+") as f:
    f.write(repo_config)
```

repo_source：repo地址为：http://119.3.219.20:82

obs_branch_list：根据分支映射表GITEE_BRANCH_PROJECT_MAPPING拿到分支对于obs上的分支名称列表

repo_config：根据上面拿到的分支名称解析出在repo上的路径

将上述生产的repo_config写入到obs_realtime.repo文件中，如下：

```bash
[bringInRely]
name=check_install_bringInRely
baseurl=http://119.3.219.20:82/bringInRely/standard_x86_64
enabled=1
gpgcheck=0
priority=1
[openEuler:Extras]
name=check_install_openEuler:/Extras
baseurl=http://119.3.219.20:82/openEuler:/Extras/standard_x86_64
enabled=1
gpgcheck=0
priority=2
[openEuler:Factory]
name=check_install_openEuler:/Factory
baseurl=http://119.3.219.20:82/openEuler:/Factory/standard_x86_64
enabled=1
gpgcheck=0
priority=3
[openEuler:Mainline]
name=check_install_openEuler:/Mainline
baseurl=http://119.3.219.20:82/openEuler:/Mainline/standard_x86_64
enabled=1
gpgcheck=0
priority=4
```

#### **获取需要进行安装的rpm包列表**

```python
names = []
packages = []
for name, package in self._rpm_package.iter_all_rpm():
    # ignore debuginfo rpm
    if "debuginfo" in name or "debugsource" in name:
        logger.debug("ignore debug rpm: %s", name)
        continue
    names.append(name)
    packages.append(package)
```

names：需要验证安装的rpm包名列表

packages：需要验证安装的rpm包全路径列表

#### **验证安装并将结果输出到comment文件中**

```python
if packages:
    check_install_cmd = "sudo dnf install -y --installroot={} --setopt=reposdir=. {}".format(install_root, " ".join(packages))
    ret, _, err = shell_cmd_live(check_install_cmd, verbose=True)
    if ret:
        logger.error("install rpms error, %s, %s", ret, err)
        comment = {"name": "check_install", "result": "FAILED"}
    else:
        logger.info("install rpm success")
        comment = {"name": "check_install", "result": "SUCCESS"}

    logger.info("check install rpm comment: %s", comment)
    comments = []
    try:
        if os.path.exists(comment_file):
            with open(comment_file, "r") as f:  # one repo with multi build package
                comments = yaml.safe_load(f)
        comments.append(comment)
        with open(comment_file, "w") as f:
            yaml.safe_dump(comments, f)  # list
    except IOError:
        logger.exception("save check install comment file exception")
```

**安装命令：sudo dnf install -y --installroot={1} --setopt=reposdir=. {2}**
	--installroot：安装的root路径
	--setopt=reposdir=.：表示使用当前路径下的repo，也就是obs_realtime.repo文件

**comment文件格式：**
失败：comment = {"name": "check_install", "result": "FAILED"}
成功：comment = {"name": "check_install", "result": "SUCCESS"}