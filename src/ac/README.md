# 门禁检查

## 如何加入检查项
1. 在ci_check/src/ac目录下新建文件夹放置检查项代码
2. 在ac_conf.yaml中增加配置项

### 配置文件说明

```yaml
示例=> 
spec:                       # ac项目名称
  hint: check_spec          # gitee中显示检查项名称，缺省使用check_+项目名称
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

| 返回码 | 描述 | emoji |
| --- | --- | --- |
| 0 | SUCCESS | :white_check_mark:|
| 1 | WARNING | :bug: |
| 2 | FAILED  | :x:|

## 支持的检查项
| 检查项 | 目录 | 描述 |
| --- | --- | --- |
| spec文件 | spec | 检查homepage是否可以访问、版本号单调递增、检查补丁文件是否存在|
| 代码风格 | code | 检查压缩包文件、检查补丁是否可以使用、执行linter工具 |
| yaml文件 | package_yaml | |
| license检查 | package_license | |
| 代码片段检查 | sca  | 目前只针对自研项目 |