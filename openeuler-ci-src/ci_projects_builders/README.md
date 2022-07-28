## openEuler代码仓门禁配置

目前 openEuler 企业下的所有制品仓（以 src-openeuler 开头的仓库）都配置了 Pull Request 的门禁，而代码仓（以 openeuler 开头的仓库）默认不配置 Pull Request 门禁。本文主要介绍如何给 openEuler 的代码仓配置 Pull Request 门禁。

### 账号授权
openEuler企业下所有制品仓和代码仓的门禁都托管在 Jenkins 上，Jenkins 地址为 https://openeulerjenkins.osinfra.cn 。访问Jenkins项目需要通过 authing 授权，点击`Sign in with authing` 并选择 Gitee 授权。如果您的 Gitee 绑定邮箱已在 authing 上注册并分入 openeuler-jenkins 的组（Gitee 的绑定邮箱通过往 https://gitee.com/openeuler/openeuler-jenkins 提交 Pull Request 进行 authing 配置），那么授权后您就能访问 Jenkins 项目。
当然，如果您需要查看或修改对应项目的配置，还需要一个 Jenkins 账号。账号的注册和项目的权限配置可联系作者。

### 提交Pull Request
现在，您可以通过提交一条 Pull Request 来实现在 Jenkins 自动创建 openEuler 代码仓的门禁工程。Pull Request 提交的仓库为 https://gitee.com/openeuler/openeuler-jenkins ，仓库内的路径为 openeuler-ci/{repo}.yaml ，即您需要在 openeuler-ci 目录下新建一个与仓库名同名的yaml文件，以 openeuler/website 为例，具体的内容如下

```
repo_name: website
container_level: l1
init_shell: "echo hello\necho $?"
users:
  - login_name: xxx
    name: xyz
    email: xxx@yyy.com
    gitee_id: xxx
```
配置文件的 repo_name 为需要配置项目的仓库名；container_level 为容器内存、磁盘的组合等级，l1为2核4G~4核8G，l2为4核6G以上； init_shell 是 x86-64 和 aarch64 工程users 是一个数组，每项为一个用户的配置。login_name 是 Jenkins 的登录账号，name 是账号在 Jenkins 的名称，email 为 authing 授权的 Gitee 绑定邮箱。
当 Pull Request 合入后，Gitee Webhook 会触发在 Jenkins 自动创建对应 openEuler 代码仓的工程。

### 门禁流程
一个代码仓的 Pull Request 门禁从触发、构建到评论需要分别在 `multiarch/openeuler/trigger/` `multiarch/openeuler/x86/` `multiarch/openeuler/aarch64/` `multiarch/openeuler/comment/` 四个目录下存在对应仓库名的工程。而上述 Pull Request 合入流程正好创建了这四个工程。

在 Jenkins 上存在一个 openEuler 代码仓的工程并完成对工程的配置后，在 openEuler 代码仓提交一条 Pull Request 或者在现有 Pull Request 下评论 `/retest` 都会触发 `multiarch/openeuler/trigger/` 目录下与仓库同名的工程；`multiarch/openeuler/trigger/` 下的工程结束运行后会触发`multiarch/openeuler/x86/` 和 `multiarch/openeuler/aarch64/` （或更多其他架构的工程）下对应的同名工程；`multiarch/openeuler/x86/` 和 `multiarch/openeuler/aarch64/` （或更多其他架构的工程）下两（多）个工程都结束运行后会触发 `multiarch/openeuler/comment/` 下对应的同名工程，最后 comment 调用 Gitee 的评论接口将门禁检查结果评论到PR下。

而实现门禁的定制，只需要自定义 `multiarch/openeuler/x86/` `multiarch/openeuler/aarch64/` 等不同架构下对应工程配置中的shell，但请避免在shell中使用**chroot**等指令。

### 支持其他架构
上述内容对大多项目的配置具有普适性。如果您有更加私人的定制，如需要工程在其他架构的容器中运行，您可以联系作者并提供对应的 Docker 镜像或 Dockerfile。
