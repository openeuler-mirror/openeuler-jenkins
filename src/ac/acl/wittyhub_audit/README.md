# WittyHub 安全审计门禁（wittyhub_audit）

该检查项**仅用于 `openEuler-skills` 仓库**：当有人向该仓库提交 PR 时，调用
[wittyhub](https://atomgit.com/openeuler/wittyhub) 的
`POST /api/v1/skills/audit-by-url` 接口对 skill 内容做安全审计并评分，
结果评论到 PR 上，作为合入门禁之一。

## 功能说明

审计目标（通过 audit-by-url 接口，不要求 skill 已入库）：

- PR 变更涉及 `skill.yaml` 的 `skill_repos[].url`（skill 仓库 URL）→ 克隆该仓库，按
  与 skillcrawler **一致的发现逻辑**枚举其中的 SKILL.md（跳过 template/example/test/
  docs 等样本目录），**每个合法 skill 一次独立审计、各自返回结果**；仓库无合法
  skill 时门禁失败并评论「没有识别到 skill」。仓库 clone/发现失败时无法识别其中的
  skill，**不触发整仓库审计**，门禁返回 FAILED 并评论无法识别原因
- PR 变更涉及 `skill.yaml` 的 `skills[].skill_url`（SKILL.md URL）→ 先校验 URL
  结构，再按仓库/ref 分组浅 clone 读取远端 SKILL.md，内容符合识别标准后扫描
  单个 skill；结构或内容不合规时门禁失败；远端 clone 失败时未完成内容识别，
  门禁同样返回 FAILED
- PR 变更涉及直接上传的 `*/SKILL.md` → 从 PR 工作区读取文件，按识别标准校验后
  扫描 PR 头分支中的该 skill；位于跳过目录的 SKILL.md 不审计，但会在评论中提示
  “已忽略的 SKILL.md 变更”
- `skill.yaml` 结构异常（`skill_repos`/`skills` 不是列表、条目不是映射结构、
  条目缺 `url`/`skill_url`/`skill_name`）→ 记为未识别，门禁 `FAILED`

按**条目粒度**判断：门禁会解析 skill.yaml 的行级 diff（`pulls/{pr}/files` 的
`patch` 字段），提取本次**新增的具体 URL 条目**，只审计这些目标——例如某 PR 只在
`skill_repos` 中新增一行 `- url: <repo>`，则仅克隆并逐 skill 审计该新增仓库，不审计
该文件里其他未改动的 `skill_repos` / `skills` 条目。只新增/修改 `skills[].skill_url`
时仅扫单个 skill。获取不到 patch 或无法定位到具体 URL 时回退为全量审计（该字段所有
条目都审，宁多勿漏）。

另外几点健壮性说明：

- **SSRF 防护**：门禁在 `git clone` 前校验仓库 URL 是否在白名单内的公开代码托管
  域名（与 wittyhub `validate_git_url` 一致：仅允许 github.com / gitcode.com / atomgit.com 等
  公开域名、标准端口、非私网 IP，拒绝携带凭据/控制字符/编码路径穿越的 URL），
  防止 PR 提交者通过 skill.yaml 填入内网地址探测网络。
- **斜杠分支回退整仓库审计**：仓库默认分支或 `skill_repos[].branch` 含 `/`（如
  `release/2.0`）时，wittyhub 的 `.../blob/<ref>/<path>` 逐 skill URL 无法正确
  解析 ref，门禁改为对整个仓库发起审计（`repo_url` + `branch`），不丢弃审计目标。
- **目标数上限**：单次 PR 审计目标（skill / 仓库）超过 `MAX_TARGETS`（默认 100）时，
  不做自动化安全审计，仅在 PR 评论提示「本次不做安全审计，请人工审核」，门禁
  WARNING 提示（不阻断合入）。

## Skill 识别标准

与 [wittyhub src/skills](https://atomgit.com/openeuler/wittyhub) 扫描器保持一致，
只有同时满足以下条件的 `SKILL.md` 才被识别为 skill 并进入安全审计：

1. 文件名必须精确为 `SKILL.md`（`_cannbot_SKILL.md` 等不算）；
2. 路径不能位于 `template/templates/example/examples/demo/demos/test/tests/
   fixture/fixtures/docs/doc/archive/archives/legacy` 目录（按连续目录段匹配）；
3. frontmatter 必须同时声明非空的 `name` 和 `description`；
4. frontmatter 之后的正文内容（strip 后）不少于 100 字符。

判定行为：

- PR 没有任何 skill 相关变更（如只改 README）→ `SUCCESS`，不审计；
- 有 skill 相关变更且至少识别到 1 个合法 skill → 审计合法 skill；若同时存在
  未识别项（结构/内容不合规），整体仍为 `FAILED`，未识别项在评论中单独列出；
- 有 skill 相关变更但一个合法 skill 都没识别到 → `FAILED`，评论
  `**结论: 失败（没有识别到 skill）**` 并附未识别原因；
- `skill.yaml` 结构异常 → `FAILED`，评论具体结构错误；
- 仓库 clone/发现失败、远端 `skill_url` clone 失败 → `FAILED`，评论
  `**结论: 失败（无法识别仓库或 skill_url，未完成内容识别）**`，明确
  “未完成内容识别”，不触发整仓库审计；即使其他 skill 审计通过也会失败；
- 删除 `SKILL.md`、跳过目录下的 `SKILL.md` 变更不视为 skill 提交：
  - 删除：不审计、不评论；
  - 跳过目录：不审计，`SUCCESS` + 评论“已忽略的 SKILL.md 变更（不属于 skill）”。

## 判定规则

| 审计结果 risk_level | 门禁结果 | 说明 |
| --- | --- | --- |
| critical / high | WARNING | 不阻断合入，评论提示「谨慎合入」，人工确认 |
| medium / unknown / 审计调用失败 | WARNING | 告警，人工确认 |
| low | SUCCESS | 通过 |
| 未识别到 skill | FAILED | 有 skill 相关变更但没有任何合法 skill，评论未识别原因 |
| skill.yaml 结构异常 | FAILED | 字段/条目结构不合法，评论具体错误 |
| 无法识别仓库 | FAILED | 仓库 clone/发现失败或远端 skill_url clone 失败，未完成内容识别，评论未识别原因 |
| 跳过目录 SKILL.md 变更 | SUCCESS | 不属于 skill 变更，不审计，评论提示已忽略 |

默认判定可在 `src/ac/framework/ac.yaml` 中用 `block_levels` / `warn_levels`
覆盖（默认 `block_levels: [critical, high]`，`warn_levels: [medium]`）。

## License 合规检查

`license_check: true` 时，门禁在安全审计之外增加 license 白名单检查：

- **数据来源**：优先读取 `SKILL.md` frontmatter 的 `license` 字段（SPDX 表达式，
  如 `Apache-2.0`、`MIT OR Apache-2.0`）；其次扫描 skill 目录的
  `LICENSE`/`LICENCE`/`COPYING`/`UNLICENSES` 及 `LICENSES/<SPDX>.txt`；skill
  目录没有时回退到仓库根目录。
- **准入清单**：compliance SIG 维护的
  `Licenses_Access_List.yaml`，默认运行时从
  `https://api.atomgit.com/api/v5/repos/openeuler/compliance/raw/doc/rule/Licenses_Access_List.yaml?ref=master`
  拉取并缓存，可用 `license_list_url` 或环境变量 `WITTYHUB_LICENSE_LIST_URL` 覆盖。
- **判定口径**：`black: Y` 禁止（评论展示 `blackReason`）；`oeApproved: Y` 允许；
  `lowRisk: Y`（oE 受限使用）、未收录、未声明均不属于白名单。SPDX 表达式中
  `AND` 要求全部分支允许，`OR` 任一分支允许即可，`WITH` 的例外条款需在清单中
  标记为 `exception: Y`。
- **门禁结果**：非白名单默认 `FAILED`；`license_missing` / `license_restricted` /
  `license_unknown` 可分别配置为 `failed`、`warning`、`success`。清单拉取失败时
  降级 `WARNING`（评论提示未执行 license 检查），不阻断 PR。
- **检测限制**：只检查 skill 自身，不扫描依赖、lock 文件或 vendor 目录；无法
  自动识别的 license 会按“无法识别”处理，建议在 SKILL.md 中显式声明 SPDX。

## 部署配置

### 1. openeuler-jenkins 侧

检查项已注册在 `src/ac/framework/ac.yaml` 的 `openeuler` 段，通过
`allow_list: ["openEuler-skills"]` 限制仅对 `openEuler-skills` 生效；
`src-openeuler` 段已 `exclude: True`，不影响其他社区仓库。

**必须配置以下环境变量**（配置在 openEuler-skills 的 AC Jenkins 任务环境中，
否则门禁直接 SUCCESS 跳过）：

| 环境变量 | 说明 | 示例 |
| --- | --- | --- |
| `WITTYHUB_API_URL` | wittyhub 服务地址（不含末尾斜杠） | `https://skillhub.openeuler.org` |
| `WITTYHUB_ADMIN_TOKEN` | wittyhub 管理 token（audit-by-url 需要，Bearer 认证） | `xxx` |
| `WITTYHUB_AUDIT_TIMEOUT` | 可选：单个目标轮询审计结果的总超时（秒），默认 600 | `900` |
| `WITTYHUB_PUBLIC_URL` | 可选：PR 评论中 report.md 下载链接的对外地址；不配置则用 `WITTYHUB_API_URL` | `https://skillhub.openeuler.org` |

### 2. wittyhub 侧

- 服务的 `security.enable_audit` 必须为 `true`，否则接口返回 503，门禁按审计失败告警。
- 服务需配置 skillspector（Jenkins）凭据，见 wittyhub 的 `config.yaml`：
  `security.skillspector_jenkins_url` / `security.skillspector_jenkins_user` /
  `security.skillspector_jenkins_token`。
- 服务需开放管理 token 鉴权：`require_admin_token`（`WITTYHUB_ADMIN_TOKEN` 需与服务端
  管理 token 一致）。

## 异步调用与超时行为

门禁**异步触发 + 轮询**，避免网关长连接超时（此前同步调用会 504）：

1. `POST /api/v1/skills/audit-by-url` 带 `async_mode=true` → wittyhub 立即触发
   Jenkins 构建并返回 `details.skillspector_build_number`（不阻塞，秒级返回）。
   多目标时触发阶段用**线程池并发**发出全部 POST（并发度上限 `MAX_TRIGGER_WORKERS`，
   默认 20），避免串行逐个等待 Jenkins 队列解析 build_number；Jenkins 侧由多
   executor 并行跑各 skill 扫描。
2. 门禁**串行轮询**：逐个 skill 单次查询
   `GET /api/v1/skills/audit-by-url/result?build_number=<n>`，单个查询请求超时
   `POLL_REQUEST_TIMEOUT`（默认 10 秒），查不到结果就换查下一个 skill，下一轮
   继续轮询，直到 `status == "done"`（拿到结果）或 `status == "error"`（按审计失败告警）。
3. 轮询**总超时**：门禁 `WITTYHUB_AUDIT_TIMEOUT`（默认 20 分钟）。总超时到点后
   仍未完成的目标按审计失败告警（WARNING，不阻断、不重试），不影响其他目标。

wittyhub 侧 `security.skillspector_timeout`（默认 600 秒/10 分钟，可用
`SECURITY__SKILLSPECTOR_TIMEOUT` 覆盖）为 Jenkins 构建等待上限，应 ≥ 门禁轮询超时。
整仓库级扫描耗时较长时可在两侧调大对应值。

## 评论格式示例

评论以**表格**展示每个 skill 的名称、风险等级、风险分数与安全审计报告下载链接，
每个 skill 一行、一个独立审计报告；表格按风险分数降序（分数高的在前，无分数的排最后），
**结论行置于表格上方**。风险等级为中文（按风险分数分档：安全/低风险/中风险/高风险/
未检测），黑色字体 + 背景色标签（安全=绿、低风险=黄、中风险=橙、高风险=红、未检测=灰，
与前端配色一致；平台若不渲染内联 style 则降级为黑色纯文本）。详情链接指向 wittyhub 的
`GET /api/v1/skills/audit-by-url/report?build_number=<n>&filename=<skill名>安全审计报告.md`，
链接文本与下载文件名均为「skill 名称 + 安全审计报告.md」：

```markdown
**SkillHub 安全审计门禁**
审计目标数: 2

**结论: 谨慎合入（存在高风险 skill）**

| skill 名称 | 风险等级 | 风险分数 | 详情链接 |
| --- | --- | --- | --- |
| witty-agents | <span style="color:#000000;background-color:#FF9800;">中风险</span> | 65 | [witty-agents安全审计报告.md](https://skillhub.openeuler.org/api/v1/skills/audit-by-url/report?build_number=101&filename=witty-agents%E5%AE%89%E5%85%A8%E5%AE%A1%E8%AE%A1%E6%8A%A5%E5%91%8A.md) |
| wittyhub | <span style="color:#000000;background-color:#67C23A;">安全</span> | 10 | [wittyhub安全审计报告.md](https://skillhub.openeuler.org/api/v1/skills/audit-by-url/report?build_number=102&filename=wittyhub%E5%AE%89%E5%85%A8%E5%AE%A1%E8%AE%A1%E6%8A%A5%E5%91%8A.md) |
```

- 评论链接默认使用 `WITTYHUB_API_URL`；如需对外可访问的域名，可配置
  `WITTYHUB_PUBLIC_URL`（例如 `https://skillhub.openeuler.org`）覆盖。
- 报告来源：wittyhub 的 audit-by-url 构建产物 `reports/skillspector/report.md`，
  由 report 端点按需从 Jenkins 获取，保证链接始终是最新报告。
- 结论判定：存在审计失败（触发/轮询 error/超时）时，结论为
  `**结论: 审计失败，请评论 /retest 重新审计**`，失败目标在表格中显示为「审计失败」行；
  仅命中高风险时结论为「谨慎合入」，仅 medium/unknown 时结论为「有风险提示」。
