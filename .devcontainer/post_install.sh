#!/usr/bin/env bash
# openeuler-jenkins 依赖安装与测试（CLI 门禁子集范围）
# 原则：依赖安装 + 测试都在这里，保持 devcontainer.json 简洁；可重复执行
set -euo pipefail
cd /workspace

# 0) 兼容 bind mount 导致的 git dubious ownership（updateRemoteUserUID 之外的双保险）
git config --global --add safe.directory /workspace

# 1) 修正命名卷属主：命名卷首次挂载到镜像中不存在的目录时初始化为 root 属主，
#    vscode 无法写入（pip 缓存会被禁用、bash 历史写不进去）；
#    updateRemoteUserUID 只处理 workspace 不处理命名卷，故按当前 UID 运行时修正。
#    chown 幂等，脚本可重复执行。
sudo mkdir -p /commandhistory /home/vscode/.cache/pip
sudo chown -R "$(id -u):$(id -g)" /commandhistory /home/vscode/.cache/pip

# 2) 升级 pip 到用户级，避免系统 pip 过旧导致新版依赖安装失败
#    Python 3.9 已 EOL，pip 26.1 起不再支持 3.9，故固定上限
python3 -m pip install --user "pip<26.1"

# 3) 项目 Python 依赖（legacy Python，无 pyproject/锁文件）
#    内网源：设置 PIP_INDEX_URL 环境变量即可，此处不写死
python3 -m pip install --user -r src/requirements

# 4) 开发工具：版本与 .pre-commit-config.yaml 对齐（ruff v0.16.2）；
#    pre-commit 钉 4.1.0（4.2.0 起不再支持 Python 3.9）；hook 环境首次运行需联网拉取
python3 -m pip install --user "ruff==0.16.2" "pre-commit==4.1.0"

# 5) 离线单测（CLI 门禁子集）：
#    - 默认跑 test/ac/acl/package_yaml：离线全绿（39 用例，其中 29 个网络用例自动跳过）
#    - 其余模块已知不可离线运行：
#      * test/ac/acl/license：测试引用了源码中已不存在的 PkgLicense.load_config（仓库存量坏用例）
#      * test/ac/acl/openlibing：需要真实 openlibing/anti-poison 凭据与网络，属 CI 用例
#    如需全量执行：python3 -m unittest discover -s test -p 'test*.py' -t .
python3 -m unittest discover -s test/ac/acl/package_yaml -p 'test*.py' -t .

echo "依赖安装与单测完成。"
