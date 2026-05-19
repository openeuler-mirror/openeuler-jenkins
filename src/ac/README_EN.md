# Gating Check

## How to Add Check Items

1. Create a folder in **ci_check/src/ac** to store the check item code.
2. Add configuration items to the **ac_conf.yaml** file.

### Configuration File Description

```yaml
Example =>
spec:                       # Name of the ac project
  hint: check_spec          # Name of the check item displayed on GitCode. The default value is "check_+project name".
  module: spec.check_spec   # Module name of the ac project. The default value is "project name+check_+project name".
  entry: Entry              # Entry class name of the ac project. It inherits the BaseCheck class and can customize the __callable__ method.
  exclude: true             # Ignore the check item.
  ignored: []               # Check items ignored in the ac project. Even if the check fails, it will not affect the final ac project result.
  allow_list: []            # The current check item is executed only for the packages in **allow_list**.
  deny_list:[]              # The current check item is not executed for the packages in **deny_list**.
```

### Entry Implementation Template

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

### Check Result

| Result Code| Description| emoji |
| --- | --- | --- |
| 0 | SUCCESS | :white_check_mark:|
| 1 | WARNING | :bug: |
| 2 | FAILED  | :x:|

## Supported Check Items

| Check Item| Directory| Description|
| --- | --- | --- |
| SPEC file| spec | Check whether the homepage can be accessed, whether the version number is monotonically increasing, and whether the patch file exists.|
| Code style| code | Check the compressed package, check whether the patch can be used, and run the linter tool.|
| YAML file| package_yaml | |
| License| package_license | |
| Code snippet| sca  | Currently, this is only for in-house projects.|
