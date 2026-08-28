# openeuler-jenkins devcontainer - openEuler 基础
#
# 判定结论：🟡 有条件
#   范围：只做 CLI 门禁子集（src/ac/framework/ac.py + src/ac/acl/*）+ test/ unittest，
#         不做 Kafka/ES/Jenkins 全栈，不启动中间件，不拉通门禁流水线。
#   资源要求：轻量（Python 门禁子集），无特权需求；完整门禁联调需要网络与真实凭据。
#
# 使用说明：
#   1. Python 依赖在 post_install.sh 中以 --user 安装（legacy Python，无 pyproject/锁文件）
#   2. 内网 pip 源不写死：通过 PIP_INDEX_URL 环境变量注入
#   3. 不加 --privileged / --gpus=all，无内核或硬件直通
#   4. 基础镜像可用 ARG OPENELER_IMAGE 覆盖（如内网镜像仓库）
#   5. pyrpm 必须用 openEuler 的 python3-pyrpm（dnf 包，提供 pyrpm.spec）；
#      PyPI 上的 pyrpm 是另一个包（只有 pyrpm.rpm），不要 pip 安装

ARG OPENELER_IMAGE=openeuler/openeuler:22.03-lts-sp1
FROM ${OPENELER_IMAGE}

ARG TZ=Asia/Shanghai
ENV TZ="${TZ}"

# 基础工具链 + 门禁子集运行依赖（openEuler dnf 包名）
# rpm-build 提供 rpmspec/rpmbuild；check_consistency 如需 spectool 另装 rpmdevtools（见 README.devcontainer.md）
RUN dnf update -y && dnf install -y \
    git \
    curl \
    wget \
    tar \
    unzip \
    xz \
    bzip2 \
    cpio \
    bsdtar \
    file \
    jq \
    vim \
    tmux \
    tzdata \
    zsh \
    sudo \
    gcc \
    gcc-c++ \
    make \
    cmake \
    pkgconf \
    python3 \
    python3-devel \
    python3-pip \
    python3-pyrpm \
    rpm-build \
    expect \
    openssh-clients \
    strace \
    && dnf clean all

# 创建开发用户（devcontainer remoteUser）
RUN useradd -m -s /bin/bash vscode && \
    echo 'vscode ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/vscode && \
    chmod 440 /etc/sudoers.d/vscode && \
    mkdir -p /workspace /commandhistory && \
    chown -R vscode:vscode /workspace /commandhistory

WORKDIR /workspace
USER vscode
ENV PATH="/home/vscode/.local/bin:/usr/local/bin:$PATH"
ENV SHELL=/bin/bash
ENV EDITOR=vim
