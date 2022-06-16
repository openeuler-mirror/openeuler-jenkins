

# Trigger阶段代码分析

## 一、trigger代码结构解析

整个ac检查的代码在：https://gitee.com/openeuler/openeuler-jenkins/tree/master/src/ac

### 如何加入检查项

1. 在ci_check/src/ac目录下新建文件夹放置检查项代码
2. 在ac_conf.yaml中增加配置项

### 配置文件说明

路径：src/ac/framework/ac.yaml

功能：用来指定每个检查项的路径，以及配置openeuler和src-openeuler需要进行的检查项

```yaml
示例=> 
spec:                       # ac项目名称
  hint: check_spec          # gitee中显示检查项名称，缺省使用check_+项目名称，会显示在pr评论下面
  module: spec.check_spec   # ac项目模块名称，缺省使用"项目名称+check_+项目名称"
  entry: Entry              # ac项目入口类名称，继承BaseCheck类，可自定义__callable__方法
  exclude: true             # 忽略该项检查
  ignored: []               # ac项目内忽略的检查项，就算失败也不影响最终ac项目结果
  allow_list: []            # 只有出现在allow_list的包才执行当前检查项
  deny_list:[]              # 出现在deny_list的包不执行当前检查项
```

### entry实现模板

```yaml
from src.ac.framework.ac_base import BaseCheck
from src.ac.framework.ac_result import FAILED, SUCCESS, WARNING


class Entry(BaseCheck):
    def __call__(self, *args, **kwargs):
        # do the work
        ...

    def check_case_a(self):
        # do the check

        return SUCCESS
```

### 检查结果

| 返回码 | 描述    | emoji              |
| ------ | ------- | ------------------ |
| 0      | SUCCESS | :white_check_mark: |
| 1      | WARNING | :bug:              |
| 2      | FAILED  | :x:                |

## 二、check_code_style分析

### 入口函数

```
def __call__(self, *args, **kwargs):
    """
    入口函数
    :param args:
    :param kwargs:
    :return:
    """
    logger.info("check %s repo ...", self._repo)

    _ = not os.path.exists(self._work_tar_dir) and os.mkdir(self._work_tar_dir)
    try:
        return self.start_check_with_order("compressed_file", "patch", "code_style")
    finally:
        shutil.rmtree(self._work_tar_dir)
```

### compressed_file：检查压缩包文件

```
def check_compressed_file(self):
    """
    解压缩包
    """
    return SUCCESS if 0 == self._gr.decompress_all() else FAILED
```

支持类型：".zip"，".tar.gz", ".tar.bz", ".tar.bz2", ".tar.xz", "tgz"

解压缩目标目录：self._work_tar_dir = os.path.join(workspace, "code") 

解压缩命令：zip：timeout 120s unzip -o -d {self._work_tar_dir} {file_path}

			其它：timeout 120s tar -C {self._work_tar_dir} -xavf {file_path}

返回值：0/全部成功，1/部分成功，-1/全部失败

### patch：检查补丁是否可以使用

```
def check_patch(self):
    """
    应用所有patch
    """
    patches = []
    if self._gr.spec_file:
        spec = RPMSpecAdapter(os.path.join(self._work_dir, self._gr.spec_file))
        patches = spec.patches

    rs = self._gr.apply_all_patches(*patches)

    if 0 == rs:
        return SUCCESS

    return WARNING if 1 == rs else FAILED
```

```
self._gr = GiteeRepo(self._repo, self._work_dir, self._work_tar_dir)
```

1.GiteeRepo类的init中会查找补丁文件self.find_file_path()

后缀名为".patch", ".diff"则认为补丁文件

2.从spec文件中读取patch信息

3.没有tar等压缩包则不应用补丁，直接退出

4.如果包中spec中的patch文件，则使用命令打补丁"cd {}; git apply --ignore-whitespace -p{} {}".format(patch_dir, leading, patch_path)

### code_style：执行linter工具

```
def check_code_style(self):
    """
    检查代码风格
    :return:
    """
    gp = GitProxy(self._work_dir)
    diff_files = gp.diff_files_between_commits("HEAD~1", "HEAD~0")
    logger.debug("diff files: %s", diff_files)

    diff_code_files = []                # 仓库中变更的代码文件
    diff_patch_code_files = []          # patch内的代码文件
    for diff_file in diff_files:
        if GiteeRepo.is_code_file(diff_file):
            diff_code_files.append(diff_file)
        elif GiteeRepo.is_patch_file(diff_file):
            patch_dir = self._gr.patch_dir_mapping.get(diff_file)
            logger.debug("diff patch %s apply at dir %s", diff_file, patch_dir)
            if patch_dir is not None:
                files_in_patch = gp.extract_files_path_of_patch(diff_file)
                patch_code_files = [os.path.join(patch_dir, file_in_patch) 
                        for file_in_patch in files_in_patch 
                        if GiteeRepo.is_code_file(file_in_patch)]
                # care about deleted file in patch, filter with "git patch --summary" maybe better
                diff_patch_code_files.extend([code_file 
                    for code_file in patch_code_files 
                    if os.path.exists(code_file)])

    logger.debug("diff code files: %s", diff_code_files)
    logger.debug("diff patch code files: %s", diff_patch_code_files)

    rs_1 = self.check_file_under_work_dir(diff_code_files)
    logger.debug("check_file_under_work_dir: %s", rs_1)
    rs_2 = self.check_files_inner_patch(diff_patch_code_files)
    logger.debug("check_files_inner_patch: %s", rs_2)
```

**步骤：**

1.获取2次提交的差别的文件名列表

2.获取仓库中变更的代码文件列表：diff_code_files

   获取patch的代码文件列表：diff_patch_code_files

3.分别检查变更的代码文件列表和patch的代码文件列表的代码风格

**消息格式为:消息类型:行数:【对象:】消息**
**有5种消息类型:**

- (W)（warning，警告）：某些Python 特定的问题
- (E)（error，错误）：很可能是代码中的错误
- (R)（refactor，重构）：写得非常糟糕的代码。
- (C)（convention，规范）：违反编码风格标准
- (F)   致命,如果发生了阻止pylint执行的错误

#### 目前代码支持检查三种类型文件

**python**

后缀：".py" 

命令：pylint3 --disable=E0401 {filepath} 

检查结果："C", "R", "W", "E", "F"

**go**

后缀：".go"

命令：golint  {filepath} 

检查结果：所有都当作WARNING

**c++**

后缀：".c", ".cpp", ".cc", ".cxx", ".c++", ".h", ".hpp", "hxx"

命令：splint {filepath}

检查结果：检查结果不计入最终结果

**最终结果：如果有“F”类型则FAILD，如果有“W”或者“E”类型则WARNING**

## 三、check_package_license分析

### 入口函数

```
def __call__(self, *args, **kwargs):
    """
    入口函数
    :param args:
    :param kwargs:
    :return:
    """
    logger.info("check %s license ...", self._repo)

    _ = not os.path.exists(self._work_tar_dir) and os.mkdir(self._work_tar_dir)
    self._gr.decompress_all() # decompress all compressed file into work_tar_dir 

    try:
        return self.start_check_with_order("license_in_spec", "license_in_src", "license_is_same")
    finally:
        shutil.rmtree(self._work_tar_dir)
```

**1.解压全部的压缩包**


**license分为三种：**

Not Free Licenses -> black
Free Licenses -> white
Need Review Licenses -> need review

**最终结果：**

```
self._white_black_list = {license_id: tag, ... }
self._license_translation = {alias: license_id }
```

### license_in_spec：检查spec文件中的license是否在白名单中

```
def check_license_in_spec(self):
    """
    check whether the license in spec file is in white list
    :return
    """
    if self._spec is None:
        logger.error("spec file not find")
        return FAILED
    rs_code = self._pkg_license.check_license_safe(self._spec.license)
    if rs_code == 0:
        return SUCCESS
    elif rs_code == 1:
        return WARNING
    else:
        logger.error("licenses in spec are not in white list")
        return FAILED
```

1.获取spec中的license信息

2.通过指定接口 (https://compliance2.openeuler.org/sca) 获取相关license信息

3.从接口返回的信息license是否在白名单内

### license_in_src：检查src文件中的license是否在白名单中

```
def check_license_in_src(self):
    """
    check whether the license in src file is in white list
    :return
    """
    self._license_in_src = self._pkg_license.scan_licenses_in_license(self._work_tar_dir)
    self._license_in_src = self._pkg_license.translate_license(self._license_in_src)
    if not self._license_in_src:
        logger.warning("cannot find licenses in src")
    rs_code = self._pkg_license.check_license_safe(self._license_in_src)
    if rs_code == 0:
        return SUCCESS
    elif rs_code == 1:
        return WARNING
    else:
        logger.error("licenses in src are not in white list")
        return FAILED
```

1.获取代码中的license文件

2.通过指定接口 (https://compliance2.openeuler.org/sca) 获取相关license信息

3.从接口返回的信息license是否在白名单内

### license_is_same：检查spec文件和src文件中的license是否一致

```
def check_license_is_same(self):
    """
    check whether the license in spec file and in src file is same
    :return
    """
    if self._pkg_license.check_licenses_is_same(self._license_in_spec, 	   self._license_in_src,self._pkg_license._later_support_license):
        logger.info("licenses in src:%s and in spec:%s are same",
        self._license_in_src, self._license_in_spec)
        return SUCCESS
    else:
        logger.error("licenses in src:%s and in spec:%s are not same",self._license_in_src, self._license_in_spec)
        return WARNING
```

1.src中的license是否都被包含在spec的license里面