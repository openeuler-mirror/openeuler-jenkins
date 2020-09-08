# 门禁检查

## 如何加入检查项
1. 在ci_check/src/ac目录下新建文件夹
2. 在ac_conf.yaml中增加配置项，可选

### 配置文件说明

```yaml
示例=> 
spec:                       # ac项目名称
  hint: check_spec          # gitee中显示名，缺省使用check_+项目名称
  module: spec.check_spec   # ac项目模块名称，缺省使用"项目名称+check_+项目名称"
  entry: Entry              # ac项目入口，入口属性具备callable，缺省使用"run"
  exclude: true             # 忽略该项检查
  ignored: []               # ac项目内忽略的检查项，就算失败也不影响最终ac项目结果
```

### entry实现模板

```yaml
class Entry(object):
    def __call__(self, *args, **kwargs):
        # do the work
        ...
```

### 检查结果

| 返回码 | 描述 | emoji |
| --- | --- | --- |
| 0 | SUCCESS | :white_check_mark:|
| 1 | WARNING | :bug: |
| 2 | FAILED  | :x:|
