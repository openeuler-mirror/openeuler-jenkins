# 执行流程

#### ![](images/overview.png)

![](images/detail.png)

## 1. Trigger.sh脚本

此脚本主要分为三个步骤

1、下载kernel代码

2、执行静态检查（license，spec等）

3、执行额外操作，目前只有pkgship仓库需要额外操作

ac.py文件主要在第二步中执行

```shell
function exec_check() {
  log_info "***** Start to exec static check *****"
  export PYTHONPATH=${shell_path}
  python3 ${shell_path}/src/ac/framework/ac.py \
    -w ${WORKSPACE} -r ${giteeRepoName} -o acfile -t ${GiteeToken} \
    -p ${giteePullRequestIid} -b ${giteeTargetBranch} -a ${GiteeUserPassword} \
    -x ${prCreateTime} -l ${triggerLink} -z ${jobTriggerTime} -m "${comment}" \
    -i ${commentID} -e ${giteeCommitter} --jenkins-base-url ${jenkins_api_host} \
    --jenkins-user ${jenkins_user} --jenkins-api-token ${jenkins_api_token}
  log_info "***** End to exec static check *****"
}
```

## 说明

```python
self._ac_check_elements
```

```json
{
	'spec': {
		'hint': 'check_spec_file',
		'module': 'spec.check_spec',
		'entry': 'CheckSpec',
		'ignored': ['homepage']
	},
	'code': {
		'hint': 'check_code_style',
		'module': 'code.check_code_style',
		'entry': 'CheckCodeStyle',
		'exclude': True,
		'ignored': ['patch']
	},
	'package_yaml': {
		'hint': 'check_package_yaml_file',
		'module': 'package_yaml.check_yaml',
		'entry': 'CheckPackageYaml',
		'ignored': ['fields']
	},
	'package_license': {
		'hint': 'check_package_license',
		'module': 'package_license.check_license',
		'entry': 'CheckLicense'
	},
	'binary': {
		'hint': 'check_binary_file',
		'module': 'binary.check_binary_file',
		'entry': 'CheckBinaryFile'
	},
	'sca': {
		'exclude': True
	},
	'openlibing': {
		'exclude': True
	}
}

{
	'version_control': 'git',
	'src_repo': 'https://code.wireshark.org/review/gitweb?p=wireshark.git',
	'tag_prefix': '^v',
	'seperator': '.'
}
```



## 2 package yaml

函数调用关系图

![](images/check_yaml.png)

此文件夹中包含两个python文件

**1 check_yaml.py**

检查软件包中的yaml文件

| 类方法/属性            | 描述                   | 作用说明                                                     |
| ---------------------- | ---------------------- | ------------------------------------------------------------ |
| __init__               | 初始化                 | CheckPackageYaml实例化对象，初始设置一些参数值               |
| is_change_package_yaml | 判断是否更改了yaml文件 | 如果本次提交变更了yaml，则对yaml进行检查                     |
| check_fields           | 检查fileds             | 从具体的目标分{tbranch}支下载源码及关联仓库代码，编译软件包、比较软件包差异也需目标分支参数 |
| check_repo             | 检查repo               | 检查yaml的有效性,能否从上游社区获取版本信息                  |
| check_repo_domain      | 检查repo作用域         | 检查spec中source0域名是否包含yaml的version_control,仅做日志告警只返回SUCCESS(autoconf为特例) |
| check_repo_name        | 检查repo名称           | 检查spec中是否包含yaml中src_repo字段的软件名,仅做日志告警只返回SUCCESS |
| __call__               | ·                      | 使CheckPackageYaml的实例对象变为了可调用对象                 |

**2 check_repo.py**

获取上游社区的release tags

![](images/tags.png)

| 类名                 | 方法                 | 描述                                        | 作用说明                                       |
| -------------------- | -------------------- | ------------------------------------------- | ---------------------------------------------- |
| AbsReleaseTags       |                      | 获取release tags的抽象类                    |                                                |
| DefaultReleaseTags   |                      | 获取release tags的基类                      |                                                |
|                      | url                  |                                             | 通过src_repo生成url                            |
|                      | get_tags             |                                             | 通过url获取上游社区的release tags              |
| HttpReleaseTagsMixin |                      | 通过web请求形式获取release tags             |                                                |
|                      | get_redirect_resp    |                                             | 获取重定向的url和cookie                        |
|                      | get_request_response |                                             | 获取url请求获取response                        |
| HgReleaseTags        |                      | 获取hg上游社区release tags                  |                                                |
| HgRawReleaseTags     |                      | 获取hg raw上游社区release tags              |                                                |
| MetacpanReleaseTags  |                      | 获取metacpan上游社区release tags            |                                                |
| PypiReleaseTags      |                      | 获取pypi上游社区release tags                |                                                |
| RubygemReleaseTags   |                      | 获取rubygem上游社区release tags             |                                                |
| GnuftpReleaseTags    |                      | 获取gnu-ftp上游社区release tags             |                                                |
| FtpReleaseTags       |                      | 获取ftp上游社区release tags                 |                                                |
| CmdReleaseTagsMixin  |                      | 通过shell命令获取上游社区的release tags     |                                                |
|                      | get_cmd_response     |                                             | 获取shell命令的response                        |
| SvnReleaseTags       |                      | 通过shell svn命令获取上游社区的release tags |                                                |
| GitReleaseTags       |                      | 通过shell git命令获取上游社区的release tags |                                                |
|                      | trans_reponse_tags   |                                             | 解析git命令返回值为纯数字形式的tag             |
| GithubReleaseTags    |                      | 获取github上游社区release tags              |                                                |
| GiteeReleaseTags     |                      | 获取gitee上游社区release tags               |                                                |
| GitlabReleaseTags    |                      | 获取gitlab.gnome上游社区release tags        |                                                |
| ReleaseTagsFactory   |                      | ReleaseTags及其子类的工厂类                 |                                                |
|                      | get_release_tags     |                                             | 通过version control返回对应的ReleaseTags的子类 |

## 3 spec

**check_spec.py**

![](images/check_spec.png)

检查软件包中的spec文件

![](images/check_spec_problem.png)

| 类方法/属性               | 描述                         | 作用说明                                  |
| ------------------------- | ---------------------------- | ----------------------------------------- |
| __init__                  | 初始化                       | CheckSpec实例化对象，初始设置一些参数值   |
| _only_change_package_yaml | 判断是否更改了yaml文件       | 如果本次提交只变更yaml，则无需检查version |
| _is_lts_branch            | 判断是否是lts分支            |                                           |
| check_version             | 检查版本信息                 | 检查当前版本号是否比上一个commit新        |
| check_homepage            | 检查spec文件中的主页url      | 检查主页是否可访问                        |
| check_patches             | 检查spec中的patch            | 检查spec中的patch是否存在                 |
| _ex_exclusive_arch        | 保存spec中exclusive_arch信息 |                                           |
| _ex_pkgship               | pkgship需求                  |                                           |
| __call__                  | ·                            | 使CheckSpec的实例对象变为了可调用对象     |



## 4 binary 

**check_binary_file.py**

![](images/check_binary.png)

检查压缩包中的二进制文件

| 类方法/属性                         | 描述                     | 作用说明                                      |
| ----------------------------------- | ------------------------ | --------------------------------------------- |
| __init__                            | 初始化                   | CheckBinaryFile实例化对象，初始设置一些参数值 |
| BINARY_LIST                         | 二进制文件后缀集         |                                               |
| check_compressed_file               | 解压缩包                 |                                               |
| check_binary                        | 检查二进制文件           |                                               |
| _upstream_community_tarball_in_spec | spec指定的上游社区压缩包 | 检查spec指定的上游社区压缩包                  |
| _get_all_file_suffixes              | 获取文件夹中文件后缀     | 获取当前文件中所有文件名后缀,并判断           |
| __call__                            | ·                        | 使CheckBinaryFile的实例对象变为了可调用对象   |

## 5 compare package

compare package在extra work中进行调用

| 类方法/属性                 | 描述                                                      | 作用说明                                     |
| --------------------------- | --------------------------------------------------------- | -------------------------------------------- |
| __init__                    | 初始化                                                    | ComparePackage实例化对象，初始设置一些参数值 |
| _get_dict                   | 获取字典值                                                |                                              |
| _rpm_name                   | 返回rpm包名称                                             |                                              |
| _show_rpm_diff              | 输出rpm包差异                                             |                                              |
| _get_check_item_dict        | 获取检查项详情字典                                        |                                              |
| _show_diff_details          | 显示有diff差异的rpm包的所有差异详情                       |                                              |
| output_result_to_console    | 解析结果文件并输出展示到jenkins上                         |                                              |
| _read_json_file             | 读取json文件并检查结果类型                                |                                              |
| _get_rule_data              | 根据正则表达式过滤数据                                    |                                              |
| _get_new_json_data          | 得到新的json数据                                          | 删除字典中的正则匹配到的数据                 |
| _write_compare_package_file | 写接口变更检查结果文件，新增pr链接和接口变更检查原因      |                                              |
| _get_pr_changelog           | 获取更新代码的changelog内容，应承载接口变更检查原因及影响 |                                              |
| _get_check_item_result      | 获取compare package比较结果各子项的详细信息               |                                              |
| _result_to_table            | 获取compare package比较结果的详细信息                     |                                              |