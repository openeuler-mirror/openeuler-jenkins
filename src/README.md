# 基于K8s集群的打包方案

## 单包构建任务

### 设计逻辑

- 部署x86-64和aarch64架构下的k8s集群
- 将集群配置为**Jenkins slave**
- **Jenkins master** 运行在x86-64架构k8s集群内

### 流水线任务

> 相同任务只运行一个实例

#### trigger

- 码云触发
- 并行跑门禁任务，cpu架构不限，失败则中止任务并对pr评论
- 成功传递参数给下游 **job**
  - 项目名(**repo**)
  - 分支(**branch**)
  - pull request id(**prid**)
  - 发起者(**committer**)

#### multiarch

- 支持x86_64和aarch64架构
- trigger成功后触发
- 执行[**python osc_build_k8s.py $repo $arch $WORKSPACE**](https://gitee.com/src-openeuler/ci_check/blob/k8s/private_build/build/osc_build_k8s.py)进行构建

#### comment

- 收集门禁、build结果
- 调用接口[**提交Pull Request评论**](https://gitee.com/wuyu15255872976/gitee-python-client/blob/master/docs/PullRequestsApi.md#post_v5_repos_owner_repo_pulls)反馈结果给码云
- cpu架构不限

## 制作jenkins/obs镜像

### 机制

- k8s集群中部署docker service 服务，对外提供的内部服务地址为tcp://docker.jenkins:2376
- jenkins安装docker插件，并配置连接到k8s集群docker service服务
- jenkins中配置制作镜像流水线任务obs-image
- 触发方式：代码仓库ci_check打tag后手动触发，jenkins需安装build with parameterrs插件支持

### 流水线任务obs-image

> 运行该任务的K8s agent需带docker client

#### 任务：_trigger

- 检查Dockerfile文件【optional】
- 设置参数 【环境变量?】
  - name 【jenkins/obs】
  - version 【取自tag】

#### 任务：build-image-aarch64 & build-image-x86-64

- 构建过程选择 **Build/Publish Docker Image**
- 配置推送镜像的 **Registry Credentials**

#### 任务：manifest

多arch支持
> docker manifest push时Registry Credentials?

## 目录结构
| 目录 | 描述 |
| --- | --- |
|ac/framework | 门禁框架 |
|ac/acl | 门禁任务，每个门禁项对应一个目录 |
|ac/common | 门禁通用代码 |
|build| 单包构建|
|jobs| jenkins任务管理|
|conf|配置|
|proxy|第三方接口代理|
|utils|通用代码，日志等|
