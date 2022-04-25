# Check_binary_file分析

功能：检查仓库中是否存在二进制文件

代码：https://gitee.com/openeuler/openeuler-jenkins/blob/master/src/ac/acl/binary/check_binary_file.py

SUCCESS：不存在以.pyc、.jar、.ko、.o为后缀的文件（包括压缩包内，但不包括以链接形式给出的上游社区）

FAILED：存在以.pyc、.jar、.ko、.o为后缀的文件

## 入口函数

```python
def __call__(self, *args, **kwargs):
    """
    入口函数
    :param args:
    :param kwargs:
    :return:
    """
    logger.info("check %s binary files ...", self._repo)

    _ = not os.path.exists(self._work_tar_dir) and os.mkdir(self._work_tar_dir)
    try:
        return self.start_check_with_order("compressed_file", "binary")
    finally:
        shutil.rmtree(self._work_tar_dir)
```

## __init__初始化

```python
def __init__(self, workspace, repo, conf):
    super(CheckBinaryFile, self).__init__(workspace, repo, conf)
    self._work_tar_dir = os.path.join(workspace, "code")  # 解压缩目标目录
    self._gr = GiteeRepo(self._repo, self._work_dir, self._work_tar_dir)
    self._tarball_in_spec = set()
    self._upstream_community_tarball_in_spec()
```

self._upstream_community_tarball_in_spec()：拿到spec文件指定的上游社区的压缩包集合

## check_compressed_file检查压缩包

```python
def check_compressed_file(self):
    """
    解压缩包
    """
    need_compress_files = []
    for decompress_file in self._gr.get_compress_files():
        if decompress_file not in self._tarball_in_spec:
            need_compress_files.append(decompress_file)
    self._gr.set_compress_files(need_compress_files)
    return SUCCESS if 0 == self._gr.decompress_all() else FAILED
```

need_compress_files：需要进行二进制检查的压缩包，但不上游社区的压缩包

支持类型：".zip"，".tar.gz", ".tar.bz", ".tar.bz2", ".tar.xz", "tgz"

检查压缩包是否可以解压，返回值：0/全部成功，1/部分成功，-1/全部失败

## check_binary二进制检查

```python
def check_binary(self):
    """
    检查二进制文件
    """
    suffixes_list = self._get_all_file_suffixes(self._work_tar_dir)
    if suffixes_list:
        logger_con = ["%s: \n%s" % (key, value) for suffix_list in suffixes_list for key, value in
                      suffix_list.items()]
        logger.error("binary file of type exists:\n%s", "\n".join(logger_con))
        return FAILED
    else:
        return SUCCESS
```

suffixes_list：拿到所有以.pyc、.jar、.ko、.o为后缀的文件列表

如果suffixes_list不为空表示不存在二进制文件，返回FAILED