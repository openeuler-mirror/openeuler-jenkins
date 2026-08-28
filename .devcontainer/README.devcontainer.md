# openeuler-jenkins devcontainer

## 判定结论与范围边界

判定：🟡 **有条件**。依据 `devcontainer改造评估报告` 与决策矩阵，openeuler-jenkins 只做 **CLI 门禁子集 + unittest**：

| 能做 | 刻意不做 |
| --- | --- |
| 编辑/调试门禁代码（`src/ac/framework/ac.py`、`src/ac/acl/*`） | Kafka / Elasticsearch / Jenkins 全栈编排（compose 不引入） |
| 运行 `test/` 下离线 unittest（网络用例被 `ACCESS2INTERNET=False` 跳过） | 特权或 GPU 能力（`--privileged` / `--gpus=all`） |
| 本地运行门禁 CLI 的语法级检查与试跑 | 门禁流水线端到端联调（依赖内网 gitee/gitcode/OBS 与真实凭据） |
| ruff 检查、pre-commit（可选，见下文） | 生产部署/运行镜像（本配置只做开发环境） |

## 启动方式

- VS Code：打开仓库目录 → 命令面板 → "Reopen in Container"
- CLI：`devcontainer up --workspace-folder .`

首次启动会自动执行 `post_install.sh`：安装 `src/requirements` + `pyrpm` + 开发工具，并跑一遍单测。

## 环境构成

- 基础镜像：`openeuler/openeuler:22.03-lts-sp1`（Python 3.9，与门禁运行节点同系；可用 `ARG OPENEULER_IMAGE` 覆盖）
- 系统依赖：dnf 包名对齐 openEuler（git、cpio/bsdtar/xz/bzip2、file、rpm-build、expect、openssh-clients 等），
  其中 `python3-pyrpm` 提供 `pyrpm.spec`（`src/ac/**` 运行必需）
- Python 依赖：`--user` 安装，pip 缓存挂载到命名 volume，重建容器不重复下载
- 扩展：Python / Pylance / Ruff；解释器为系统 `/usr/bin/python3`

## 凭据注入

- devcontainer.json 的 `remoteEnv` 只放占位：`"GITEE_TOKEN": "${localEnv:GITEE_TOKEN:}"` 等。
  在宿主机设置同名环境变量即可注入，**不要把真实凭据写进配置或镜像**。
- 实际运行门禁 CLI 时仍以参数传入：`python3 src/ac/framework/ac.py -w <workspace> -r <repo> -b <branch> -p <pr> -t <token> ...`。
- 内网 pip 源：设置 `PIP_INDEX_URL`（或 `PIP_EXTRA_INDEX_URL`）环境变量即可，配置文件不写死。

## 测试与质量

- 单测（postCreate 默认执行）：`python3 -m unittest discover -s test/ac/acl/package_yaml -p 'test*.py' -t .`
  离线全绿（39 用例，其中 29 个需网络用例自动跳过）
- 全量套件（已知有失败，仅作参考）：
  `python3 -m unittest discover -s test -p 'test*.py' -t .`
  - `test/ac/acl/license`：测试引用了源码中已不存在的 `PkgLicense.load_config`（仓库存量坏用例，建议单独修复）
  - `test/ac/acl/openlibing`：需要真实 openlibing/anti-poison 凭据与网络（CI 用例）
- 额外：`src/apig_sdk/signer_test` 因测试与源码导入方式不匹配（测试用绝对导入 `import signer`，
  源码用相对导入）暂无法直接运行，属仓库存量问题，未纳入本容器验证范围
- Lint：`ruff check .`；pre-commit 需联网拉取 hook 环境后执行 `pre-commit run --files <file>`

## 已知限制

1. **`pyrpm` 不在 `src/requirements`**：代码 import 需要 `pyrpm.spec`，但 `src/requirements` 未声明；
   devcontainer 通过 dnf `python3-pyrpm` 提供。注意 PyPI 的 `pyrpm` 是另一个包（只含 `pyrpm.rpm`），
   不要用 pip 安装。建议后续在文档/依赖清单中补明对 `python3-pyrpm` 的依赖。
2. **网络用例跳过**：`test/` 中依赖外网/内网服务的用例被 `ACCESS2INTERNET=False` 跳过，属预期。
3. **完整门禁不可本地跑通**：CLI 会克隆 gitee/gitcode 仓库并调用 OBS/Jenkins/ES/Kafka/openlibing 等，容器只保证工具链一致，"容器化 ≠ 可运行"。
4. **spectool 未预装**：`check_consistency` 等检查需要 `spectool`，按需 `sudo dnf install -y rpmdevtools`。
5. **Python 版本**：22.03 自带 Python 3.9；如需更新版本（如 3.11），把基础镜像换成 24.03-lts 并重新验证依赖兼容性。
6. **存量坏测试**：`test/ac/acl/license` 与 `test/ac/acl/openlibing` 在干净环境必然失败
   （前者测试与源码脱节，后者需要真实凭据/网络），不属于 devcontainer 缺陷。
