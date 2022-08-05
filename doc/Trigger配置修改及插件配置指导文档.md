# 门禁工程tirgger部分Jenkins工程中的配置

## 一、背景：

当前Jenkins工程trigger部分存在无法在保存当前页面修改的问题，需使用其他Jenkins工程来辅助更改trigger部分配置。

## 二、分析

## 2.1、trigger流程

triiger部分详细配置流程见

## 2.2、流程详解

### 2.2.1、在指定位置创建自己的工程

https://openeulerjenkins.osinfra.cn/job/test_directory_temporary/

在上述目录下创建工程文件夹，然后按自己需求再创建指定工程

![](images/update_trigger_con_pj.png)

指定工程创建完成进行下面进一步处理。

### 2.2.2、获取要修改的包配置

![](images/view_config.png)

![](images/view_config_rs.png)

https://openeulerjenkins.osinfra.cn/job/test_directory_temporary/job/zhengyaohui-ci/job/jenkins_config_function/job/view_config/，在此工程下，如上图操作，将

结果复制，进行下一步操作

### 2.2.3、配置自己创建的工程

![](images/config_trigger_personal.png)

进入自己创建的工程，在构建部分，填入获取到的包的配置内容。

举例如下：

```html
cat > new_config.xml << "EOF"
<?xml version="1.0" encoding="UTF-8"?><project>
  <actions/>
  <description/>
  <keepDependencies>false</keepDependencies>
  <properties>
    <hudson.security.AuthorizationMatrixProperty>
      <inheritanceStrategy class="org.jenkinsci.plugins.matrixauth.inheritance.InheritParentStrategy"/>
    </hudson.security.AuthorizationMatrixProperty>
    <com.sonyericsson.jenkins.plugins.bfa.model.ScannerJobProperty plugin="build-failure-analyzer@1.27.1">
      <doNotScan>false</doNotScan>
    </com.sonyericsson.jenkins.plugins.bfa.model.ScannerJobProperty>
    <com.gitee.jenkins.connection.GiteeConnectionProperty plugin="gitee@1.1.12">
      <giteeConnection>Gitee</giteeConnection>
    </com.gitee.jenkins.connection.GiteeConnectionProperty>
    <com.chikli.hudson.plugin.naginator.NaginatorOptOutProperty plugin="naginator@1.18.1">
      <optOut>false</optOut>
    </com.chikli.hudson.plugin.naginator.NaginatorOptOutProperty>
    <com.sonyericsson.rebuild.RebuildSettings plugin="rebuild@1.31">
      <autoRebuild>false</autoRebuild>
      <rebuildDisabled>false</rebuildDisabled>
    </com.sonyericsson.rebuild.RebuildSettings>
  </properties>
  <scm class="hudson.plugins.git.GitSCM" plugin="git@3.11.0">
    <configVersion>2</configVersion>
    <userRemoteConfigs>
      <hudson.plugins.git.UserRemoteConfig>
        <name>origin</name>
        <refspec>+refs/pull/${giteePullRequestIid}/MERGE:refs/pull/${giteePullRequestIid}/MERGE</refspec>
        <url>https://gitee.com/openeuler/${giteeRepoName}.git</url>
        <credentialsId>openeuler_ci_bot</credentialsId>
      </hudson.plugins.git.UserRemoteConfig>
    </userRemoteConfigs>
    <branches>
      <hudson.plugins.git.BranchSpec>
        <name>pull/${giteePullRequestIid}/MERGE</name>
      </hudson.plugins.git.BranchSpec>
    </branches>
    <doGenerateSubmoduleConfigurations>false</doGenerateSubmoduleConfigurations>
    <submoduleCfg class="list"/>
    <extensions>
      <hudson.plugins.git.extensions.impl.CleanBeforeCheckout/>
      <hudson.plugins.git.extensions.impl.CloneOption>
        <shallow>true</shallow>
        <noTags>true</noTags>
        <reference/>
        <depth>2</depth>
        <honorRefspec>true</honorRefspec>
      </hudson.plugins.git.extensions.impl.CloneOption>
      <hudson.plugins.git.extensions.impl.RelativeTargetDirectory>
        <relativeTargetDir>${giteeRepoName}</relativeTargetDir>
      </hudson.plugins.git.extensions.impl.RelativeTargetDirectory>
    </extensions>
  </scm>
  <assignedNode>k8s-x86-oe</assignedNode>
  <canRoam>false</canRoam>
  <disabled>false</disabled>
  <blockBuildWhenDownstreamBuilding>false</blockBuildWhenDownstreamBuilding>
  <blockBuildWhenUpstreamBuilding>false</blockBuildWhenUpstreamBuilding>
  <triggers>
    <org.jenkinsci.plugins.gwt.GenericTrigger plugin="generic-webhook-trigger@1.67">
      <spec/>
      <genericVariables>
        <org.jenkinsci.plugins.gwt.GenericVariable>
          <expressionType>JSONPath</expressionType>
          <key>giteeRepoName</key>
          <value>repository.name</value>
          <regexpFilter/>
          <defaultValue/>
        </org.jenkinsci.plugins.gwt.GenericVariable>
        <org.jenkinsci.plugins.gwt.GenericVariable>
          <expressionType>JSONPath</expressionType>
          <key>giteePullRequestIid</key>
          <value>pull_request.number</value>
          <regexpFilter/>
          <defaultValue/>
        </org.jenkinsci.plugins.gwt.GenericVariable>
        <org.jenkinsci.plugins.gwt.GenericVariable>
          <expressionType>JSONPath</expressionType>
          <key>giteeSourceBranch</key>
          <value>pull_request.head.ref</value>
          <regexpFilter/>
          <defaultValue/>
        </org.jenkinsci.plugins.gwt.GenericVariable>
        <org.jenkinsci.plugins.gwt.GenericVariable>
          <expressionType>JSONPath</expressionType>
          <key>giteeTargetBranch</key>
          <value>pull_request.base.ref</value>
          <regexpFilter/>
          <defaultValue/>
        </org.jenkinsci.plugins.gwt.GenericVariable>
        <org.jenkinsci.plugins.gwt.GenericVariable>
          <expressionType>JSONPath</expressionType>
          <key>giteeSourceNamespace</key>
          <value>pull_request.head.repo.namespace</value>
          <regexpFilter/>
          <defaultValue/>
        </org.jenkinsci.plugins.gwt.GenericVariable>
        <org.jenkinsci.plugins.gwt.GenericVariable>
          <expressionType>JSONPath</expressionType>
          <key>giteeTargetNamespace</key>
          <value>pull_request.base.repo.namespace</value>
          <regexpFilter/>
          <defaultValue/>
        </org.jenkinsci.plugins.gwt.GenericVariable>
        <org.jenkinsci.plugins.gwt.GenericVariable>
          <expressionType>JSONPath</expressionType>
          <key>giteeCommitter</key>
          <value>pull_request.user.login</value>
          <regexpFilter/>
          <defaultValue/>
        </org.jenkinsci.plugins.gwt.GenericVariable>
        <org.jenkinsci.plugins.gwt.GenericVariable>
          <expressionType>JSONPath</expressionType>
          <key>comment</key>
          <value>comment.body</value>
          <regexpFilter/>
          <defaultValue/>
        </org.jenkinsci.plugins.gwt.GenericVariable>
        <org.jenkinsci.plugins.gwt.GenericVariable>
          <expressionType>JSONPath</expressionType>
          <key>commentID</key>
          <value>comment.id</value>
          <regexpFilter/>
          <defaultValue/>
        </org.jenkinsci.plugins.gwt.GenericVariable>
        <org.jenkinsci.plugins.gwt.GenericVariable>
          <expressionType>JSONPath</expressionType>
          <key>jobTriggerTime</key>
          <value>comment.updated_at</value>
          <regexpFilter/>
          <defaultValue/>
        </org.jenkinsci.plugins.gwt.GenericVariable>
        <org.jenkinsci.plugins.gwt.GenericVariable>
          <expressionType>JSONPath</expressionType>
          <key>prCreateTime</key>
          <value>pull_request.created_at</value>
          <regexpFilter/>
          <defaultValue/>
        </org.jenkinsci.plugins.gwt.GenericVariable>
        <org.jenkinsci.plugins.gwt.GenericVariable>
          <expressionType>JSONPath</expressionType>
          <key>triggerLink</key>
          <value>comment.html_url</value>
          <regexpFilter/>
          <defaultValue/>
        </org.jenkinsci.plugins.gwt.GenericVariable>
        <org.jenkinsci.plugins.gwt.GenericVariable>
          <expressionType>JSONPath</expressionType>
          <key>PULL_NUMBER</key>
          <value>pull_request.number</value>
          <regexpFilter/>
          <defaultValue/>
        </org.jenkinsci.plugins.gwt.GenericVariable>
        <org.jenkinsci.plugins.gwt.GenericVariable>
          <expressionType>JSONPath</expressionType>
          <key>REPO_OWNER</key>
          <value>repository.namespace</value>
          <regexpFilter/>
          <defaultValue/>
        </org.jenkinsci.plugins.gwt.GenericVariable>
        <org.jenkinsci.plugins.gwt.GenericVariable>
          <expressionType>JSONPath</expressionType>
          <key>REPO_NAME</key>
          <value>repository.name</value>
          <regexpFilter/>
          <defaultValue/>
        </org.jenkinsci.plugins.gwt.GenericVariable>
      </genericVariables>
      <regexpFilterText>$giteeTargetNamespace $giteeRepoName $commentEOF</regexpFilterText>
      <regexpFilterExpression>MementoMoriCheng kernel ([\s]*Hi[\s\S]*|/retest)EOF</regexpFilterExpression>
      <printPostContent>false</printPostContent>
      <printContributedVariables>false</printContributedVariables>
      <causeString>"$giteeRepoName" trigger by pull request $giteePullRequestIid  [$giteeSourceNamespace:$giteeSourceBranch -&gt; $giteeTargetNamespace:$giteeTargetBranch]</causeString>
      <token/>
      <silentResponse>false</silentResponse>
      <overrideQuietPeriod>false</overrideQuietPeriod>
    </org.jenkinsci.plugins.gwt.GenericTrigger>
  </triggers>
  <concurrentBuild>false</concurrentBuild>
  <builders>
    <hudson.tasks.Shell>
      <command>#!/bin/bash
set +x
curl -X DELETE --header 'Content-Type: application/json;charset=UTF-8' https://gitee.com/api/v5/repos/${giteeTargetNamespace}/${giteeRepoName}/pulls/${giteePullRequestIid}/labels/ci_failed?access_token=${GiteeToken} 2&gt;&amp;1 &gt; /dev/null
curl -X DELETE --header 'Content-Type: application/json;charset=UTF-8' https://gitee.com/api/v5/repos/${giteeTargetNamespace}/${giteeRepoName}/pulls/${giteePullRequestIid}/labels/ci_successful?access_token=${GiteeToken} 2&gt;&amp;1 &gt; /dev/null
curl -X POST --header 'Content-Type: application/json;charset=UTF-8' https://gitee.com/api/v5/repos/${giteeTargetNamespace}/${giteeRepoName}/pulls/${giteePullRequestIid}/labels?access_token=${GiteeToken} -d [\"ci_processing\"] 2&gt;&amp;1 &gt; /dev/null
sudo cp -r /home/jenkins/.local/lib/python3.9/site-packages/* /usr/lib/python3.9/site-packages 2&gt;&amp;1 &gt; /dev/null
sudo cp /home/jenkins/.local/bin/scanoss-py /usr/bin 2&gt;&amp;1 &gt; /dev/null;
#shell_path="/home/jenkins/ci_check"
owner="openeuler"
shell_path=/home/jenkins/ci_check
mkdir -p ${shell_path}
rm -rf ${shell_path}
git clone -b for_test https://gitee.com/MementoMoriCheng/openeuler-jenkins.git ${shell_path}
ls ${shell_path}
export PYTHONPATH=/home/jenkins/ci_check
#export PYTHONPATH=${shell_path}
cat ${WORKSPACE}/${giteeRepoName}
python3 ${shell_path}/src/utils/scanoss_sbom_generator.py --repo $giteeRepoName --organization openeuler --target_path /home/jenkins/deny_list.sbom -w ${WORKSPACE} -t ${GiteeToken} -p ${giteePullRequestIid}
echo deny_list.sbom
cat /home/jenkins/deny_list.sbom
set -x
</command>
      <configuredLocalRules/>
    </hudson.tasks.Shell>
    <com.huawei.scanoss.business.SCABuilder plugin="scanosspr-jenkins@1.1.5-SNAPSHOT">
      <method>API</method>
      <methodChoose>1</methodChoose>
      <urlChoose>1</urlChoose>
      <credentialsId></credentialsId>
      <scanossCredentials/>
      <url>https://api.osinfra.cn</url>
      <sbomFile>/home/jenkins/deny_list.sbom</sbomFile>
      <authCode>eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJlbWFpbCI6InRlc3RANDMyMS5jb20ifQ.1WBjnBDgNsPfAVqxQyXDl-PS7r3L_h4OR45rNKPLJeE</authCode>
      <sourceFile></sourceFile>      
      <sudoOrder>sudo</sudoOrder>
    </com.huawei.scanoss.business.SCABuilder>
    <hudson.tasks.Shell>
      <command>#!/bin/bash

set +x
owner='openeuler'
#shell_path=/home/jenkins/ci_check2
#mkdir -p ${shell_path}
#rm -rf ${shell_path}
#git clone -b for_test https://gitee.com/MementoMoriCheng/openeuler-jenkins.git ${shell_path}       
export PYTHONPATH=/home/jenkins/ci_check
#export PYTHONPATH=/home/jenkins/ci_check
export PATH=$PATH:/home/jenkins/.local/bin
output="scanoss_result_"${BUILD_NUMBER}".json"
CodeCheckAPIKEY="q28abtBDCnrcsXeVRxulPEIeYwWdcM5g"
python3 /home/jenkins/ci_check/src/ac/framework/ac.py -w ${WORKSPACE} -r ${giteeRepoName} -o acfile -t ${GiteeToken} -p ${giteePullRequestIid} -b ${giteeTargetBranch} -a ${GiteeUserPassword} -x ${prCreateTime} -l ${triggerLink} -z ${jobTriggerTime} -m "${comment}" -i ${commentID} -e ${giteeCommitter} -c ${owner} --scanoss-output ${output} --codecheck-api-key ${CodeCheckAPIKEY}
set -x

</command>
      <configuredLocalRules/>
    </hudson.tasks.Shell>
    <EnvInjectBuilder plugin="envinject@2.3.0">
      <info>
        <propertiesFilePath>acfile</propertiesFilePath>
      </info>
    </EnvInjectBuilder>
  </builders>
  <publishers>
    <hudson.plugins.parameterizedtrigger.BuildTrigger plugin="parameterized-trigger@2.37">
      <configs>
        <hudson.plugins.parameterizedtrigger.BuildTriggerConfig>
          <configs>
            <hudson.plugins.parameterizedtrigger.PredefinedBuildParameters>
              <properties>repo=${giteeRepoName}
branch=${giteeSourceBranch}
tbranch=${giteeTargetBranch}
prid=${giteePullRequestIid}
committer=${giteeCommitter}
commentid=${commentID}</properties>
              <textParamValueOnNewLine>false</textParamValueOnNewLine>
            </hudson.plugins.parameterizedtrigger.PredefinedBuildParameters>
          </configs>
          <projects>multiarch-ci-test/openeuler/x86-64/kernel,multiarch-ci-test/openeuler/aarch64/kernel</projects>
          <condition>FAILED_OR_BETTER</condition>
          <triggerWithNoParameters>false</triggerWithNoParameters>
          <triggerFromChildProjects>false</triggerFromChildProjects>
        </hudson.plugins.parameterizedtrigger.BuildTriggerConfig>
      </configs>
    </hudson.plugins.parameterizedtrigger.BuildTrigger>
    <join.JoinTrigger plugin="join@1.21">
      <joinProjects/>
      <joinPublishers>
        <hudson.plugins.parameterizedtrigger.BuildTrigger plugin="parameterized-trigger@2.37">
          <configs>
            <hudson.plugins.parameterizedtrigger.BuildTriggerConfig>
              <configs>
                <hudson.plugins.parameterizedtrigger.PredefinedBuildParameters>
                  <properties>repo=${giteeRepoName}
branch=${giteeSourceBranch}
tbranch=${giteeTargetBranch}
prid=${giteePullRequestIid}
committer=${giteeCommitter}
commentid=${commentID}
ACL=${ACL}</properties>
                  <textParamValueOnNewLine>false</textParamValueOnNewLine>
                </hudson.plugins.parameterizedtrigger.PredefinedBuildParameters>
              </configs>
              <projects> multiarch-ci-test/openeuler/comment/kernel</projects>
              <condition>ALWAYS</condition>
              <triggerWithNoParameters>false</triggerWithNoParameters>
              <triggerFromChildProjects>false</triggerFromChildProjects>
            </hudson.plugins.parameterizedtrigger.BuildTriggerConfig>
          </configs>
        </hudson.plugins.parameterizedtrigger.BuildTrigger>
      </joinPublishers>
      <resultThreshold>
        <name>SUCCESS</name>
        <ordinal>0</ordinal>
        <color>BLUE</color>
        <completeBuild>true</completeBuild>
      </resultThreshold>
    </join.JoinTrigger>
  </publishers>
  <buildWrappers>
    <org.jenkinsci.plugins.credentialsbinding.impl.SecretBuildWrapper plugin="credentials-binding@1.23">
      <bindings>
        <org.jenkinsci.plugins.credentialsbinding.impl.StringBinding>
          <credentialsId>openeuler-ci-bot</credentialsId>
          <variable>GiteeToken</variable>
        </org.jenkinsci.plugins.credentialsbinding.impl.StringBinding>
        <org.jenkinsci.plugins.credentialsbinding.impl.UsernamePasswordBinding>
          <credentialsId>openeuler_ci_bot</credentialsId>
          <variable>GiteeUserPassword</variable>
        </org.jenkinsci.plugins.credentialsbinding.impl.UsernamePasswordBinding>
        <org.jenkinsci.plugins.credentialsbinding.impl.StringBinding>
          <credentialsId>scanoss-api-key</credentialsId>
          <variable>ScanOSSAPIKey</variable>
        </org.jenkinsci.plugins.credentialsbinding.impl.StringBinding>
        <org.jenkinsci.plugins.credentialsbinding.impl.StringBinding>
          <credentialsId>codecheck_static_key</credentialsId>
          <variable>CodeCheckAPIKEY</variable>
        </org.jenkinsci.plugins.credentialsbinding.impl.StringBinding>
        <org.jenkinsci.plugins.credentialsbinding.impl.FileBinding>
          <credentialsId>11608799-cfc7-42c1-8b38-462a4cbdcdee</credentialsId>
          <variable>SaveBuildRPM2Repo</variable>
        </org.jenkinsci.plugins.credentialsbinding.impl.FileBinding>
      </bindings>
    </org.jenkinsci.plugins.credentialsbinding.impl.SecretBuildWrapper>
    <hudson.plugins.ansicolor.AnsiColorBuildWrapper plugin="ansicolor@0.7.1">
      <colorMapName>vga</colorMapName>
    </hudson.plugins.ansicolor.AnsiColorBuildWrapper>
  </buildWrappers>
</project>
EOF

cat > hotfix.py << EOF
#!/usr/bin/python3
from src.proxy.jenkins_proxy import JenkinsProxy
import xml.etree.ElementTree as ET
import re
jp = JenkinsProxy("http://jenkins.jenkins", "$user", "$token")
#config = jp.get_config("$job")
#print(config)
new_config = open('new_config.xml').read( )
new_config = re.sub("pkgship", "${job}", new_config)
#print(new_config)

jp.update_job("${job_path}/${job}", new_config)
#jp.create_job("${job_path}/${job}", new_config)
EOF


rm -rf /home/jenkins/ci_check2
git clone -b master https://gitee.com/openeuler/openeuler-jenkins /home/jenkins/ci_check2

export PYTHONPATH=/home/jenkins/ci_check2
python3 hotfix.py
```



### 2.2.4、trigger页面各部分对应关系

| 配置内容部分                   | trigger页面部分   |
| ------------------------------ | ----------------- |
| plugin=git                     | 源码管理          |
| plugin=generic-webhook-trigger | 构建触发器        |
| plugin=credentials-binding     | 绑定              |
| plugin=envinject               | Post-Join Actions |
| 对应插件名，可能存在多个       | --------          |
| plugin=scanosspr-jenkins       | scanoss           |

构建部分如下
![](images/execute_shell.png)

```shell
在代码中找到想要修改的部分进行更改

#!/bin/bash
set +x
curl -X DELETE --header 'Content-Type: application/json;charset=UTF-8' https://gitee.com/api/v5/repos/${giteeTargetNamespace}/${giteeRepoName}/pulls/${giteePullRequestIid}/labels/ci_failed?access_token=${GiteeToken} 2&gt;&amp;1 &gt; /dev/null
curl -X DELETE --header 'Content-Type: application/json;charset=UTF-8' https://gitee.com/api/v5/repos/${giteeTargetNamespace}/${giteeRepoName}/pulls/${giteePullRequestIid}/labels/ci_successful?access_token=${GiteeToken} 2&gt;&amp;1 &gt; /dev/null
curl -X POST --header 'Content-Type: application/json;charset=UTF-8' https://gitee.com/api/v5/repos/${giteeTargetNamespace}/${giteeRepoName}/pulls/${giteePullRequestIid}/labels?access_token=${GiteeToken} -d [\"ci_processing\"] 2&gt;&amp;1 &gt; /dev/null
sudo cp -r /home/jenkins/.local/lib/python3.9/site-packages/* /usr/lib/python3.9/site-packages 2&gt;&amp;1 &gt; /dev/null
sudo cp /home/jenkins/.local/bin/scanoss-py /usr/bin 2&gt;&amp;1 &gt; /dev/null;
#shell_path="/home/jenkins/ci_check"
owner="openeuler"
shell_path=/home/jenkins/ci_check
mkdir -p ${shell_path}
rm -rf ${shell_path}
git clone -b for_test https://gitee.com/MementoMoriCheng/openeuler-jenkins.git ${shell_path}
ls ${shell_path}
export PYTHONPATH=/home/jenkins/ci_check
#export PYTHONPATH=${shell_path}
cat ${WORKSPACE}/${giteeRepoName}
python3 ${shell_path}/src/utils/scanoss_sbom_generator.py --repo $giteeRepoName --organization openeuler --target_path /home/jenkins/deny_list.sbom -w ${WORKSPACE} -t ${GiteeToken} -p ${giteePullRequestIid}
echo deny_list.sbom
cat /home/jenkins/deny_list.sbom
set -x

#!/bin/bash
set +x
owner='openeuler'
#shell_path=/home/jenkins/ci_check2
#mkdir -p ${shell_path}
#rm -rf ${shell_path}
#git clone -b for_test https://gitee.com/MementoMoriCheng/openeuler-jenkins.git ${shell_path}       
export PYTHONPATH=/home/jenkins/ci_check
#export PYTHONPATH=/home/jenkins/ci_check
export PATH=$PATH:/home/jenkins/.local/bin
output="scanoss_result_"${BUILD_NUMBER}".json"
CodeCheckAPIKEY="q28abtBDCnrcsXeVRxulPEIeYwWdcM5g"
python3 /home/jenkins/ci_check/src/ac/framework/ac.py -w ${WORKSPACE} -r ${giteeRepoName} -o acfile -t ${GiteeToken} -p ${giteePullRequestIid} -b ${giteeTargetBranch} -a ${GiteeUserPassword} -x ${prCreateTime} -l ${triggerLink} -z ${jobTriggerTime} -m "${comment}" -i ${commentID} -e ${giteeCommitter} -c ${owner} --scanoss-output ${output} --codecheck-api-key ${CodeCheckAPIKEY}
set -x

```

全部修改好之后进行下一步操作

### 2.2.5、build trigger config

![](images/build_trigger_config.png)

等待成功，trigger配置更新成功

## 三、插件配置

## 3.1、sacnnoss插件

###  3.1.1、介绍

SCA PR级jenkins插件目前应用于码云仓库进行pull request操作时触发使用。

## 3.2  安装及使用

### 3.2.1  安装scanoss-pr jenkins插件

登录jenkins客户端，将scanosspr-jenkins插件安装到jenkins上，插件可从 https://e.gitee.com/openMajun_enterprise/repos/openMajun_enterprise/majun-support/blob/master/scanoss-jenkins%E6%8F%92%E4%BB%B6%E5%AE%89%E8%A3%85%E5%8C%85/scanosspr-jenkins.hpi 进行下载获取。![](images/plugin.png)

![](images/upload_plugin.png)

插件安装完成后，重启jenkins服务，重启完成后即可使用该插件

### 3.2.2 scannoss插件配置

为适配不同方式触发jenkins job的构建，scannoss提供了两种方式来进行任务构建的触发，分别为通过构建参数直接进行构建和通过webhook配置触发，门禁工程中采用的是构建参数方式配置，因此只对此方式进行说明：

**入参：**

| 参数名称            | 参数类型 | 参数说明                  |
| :------------------ | -------- | ------------------------- |
|                     |          |                           |
| giteePullRequestIid | str      | pr编号                    |
| REPO_OWNER          | str      | 目标社区名称（openeuler） |
| giteeRepoName       | str      | 目标仓库名称              |

通过这三个参数调用Gitee API查询对应的PR信息，若需要查询的仓库为私仓，还需提供ACCESS_TOKEN(授权码)参数以授权查询。       

![](images/scannoss.png)

| 参数名称           | 参数说明                                |
| :----------------- | --------------------------------------- |
| scanossCredentials | 插件扫描凭据，默认为空                  |
| CredentialsId      | gitee仓库凭据，开源仓库不需要，私仓必填 |
| Url                | ultraSCA接口调用地址                    |
| SBOM文档           | sbom.json文档在执行服务器上的存放地址   |
| authCode           | ultraSCA接口调用授权码                  |
| Method             | 触发构建方式（构建参数/webhook）        |
| SourceFile         | 需要插件扫描的文件                      |

**说明：**

```json
1、授权码为访问ultraSCA接口的参数，当前已设置默认值，若该值无法使用，可联系ultraSCA开发人员wangdong wx1067201,wangkai wx1047660获取授权码。

2、ultraSCA生产环境接口调用地址为：https://api.osinfra.cn。

3、CredentialsId、scanossCredentials，均需在凭据管理中进行配置。

4、sbom.json文档用于对扫描结果的过滤配置，其内容格式如下所示:
{
"bomformat":"CycloneDX",
"specVersion":"1.2",
"serialNumber":"scanoss:p10-62bd6d2abf6f5820ca284c50d9cb4987",
"version":1,
"components":[{
"type":"library",
"name":"iSulad",
"publisher":"openeuler",
"version":"2.0.7",
"purl":"pkg:gitee/openeuler/isulad"
}]
}
老版本文档内容如下：
{
"comment": "Component Denylist",
"components": [
{
"publisher": "openeuler",
"name":"pkgship"
},
{
"publisher":"openeuler-mirror",
"name":"pkgship"
}]
}

5、插件扫描结果的日志信息输出至workspace路径下，以文件名scanoss_result_构建编号.json格式保存，用户可读取文件信息获取本次扫描的结果状态。
 
```

### 3.2.3 scannoss插件配置修改

```html
<configuredLocalRules/>
    </hudson.tasks.Shell>
    <com.huawei.scanoss.business.SCABuilder plugin="scanosspr-jenkins@1.1.5-SNAPSHOT">
      <method>API</method>
      <methodChoose>1</methodChoose> 触发构建方式（构建参数/webhook）
      <urlChoose>1</urlChoose> ultraSCA接口调用地址
      <credentialsId></credentialsId> gitee 凭据
      <scanossCredentials/> 插件扫描凭据
      <url>https://api.osinfra.cn</url>
      <sbomFile>/home/jenkins/deny_list.sbom</sbomFile> sbom.json文档在执行服务器上的存放地址
      <authCode>***</authCode> ultraSCA接口调用授权码
      <sourceFile></sourceFile>      需要插件扫描的文件路径
      <sudoOrder>sudo</sudoOrder>
    </com.huawei.scanoss.business.SCABuilder>
    <hudson.tasks.Shell>
```

在对应的位置修改内容，保存后构建，成功之后会更新到trigger界面
