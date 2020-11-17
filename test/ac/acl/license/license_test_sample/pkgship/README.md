[English](./README-en.md) | 简体中文

# pkgship

## 介绍
pkgship是一款管理OS软件包依赖关系，提供依赖和被依赖关系的完整图谱查询工具，pkgship提供软件包依赖，生命周期，补丁查询等功能。
1. 软件包依赖：方便社区人员在新引入、软件包更新和删除的时候能方便的了解软件的影响范围。
2. 生命周期管理：跟踪upstream软件包发布状态，方便维护人员了解当前软件状态，及时升级到合理的版本。
3. 补丁查询：方便社区人员了解openEuler软件包的补丁情况，方便的提取补丁内容


### 软件架构
系统采用flask-restful开发，使用SQLAlchemy ORM查询框架，同时支持mysql和sqlite数据库，通过配置文件的形式进行更改


安装教程
---
#### 方法一: 可以使用dnf挂载pkgship软件在所在repo源，直接下载安装pkgship及其依赖

```
dnf install pkgship(版本号)
```

#### 方法二: 可以直接下载pkgship的rpm包后安装软件包

```
rpm -ivh pkgship.rpm
```
或者
```
dnf install pkgship-(版本号)
```

系统配置
---
系统的默认配置文件存放在 /etc/pkgship/packge.ini，请根据实际情况进行配置更改

```
vim /etc/pkgship/package.ini
```
创建初始化数据库的yaml配置文件:
conf.yaml 文件默认存放在 /etc/pkgship/ 路径下，pkgship会通过该配置读取要建立的数据库名称以及需要导入的sqlite文件。conf.yaml 示例如下：

```
- dbname:openEuler-20.03-LTS
 src_db_file:
- /etc/pkgship/src.sqlite
 bin_db_file:
- /etc/pkgship/bin.sqlite
 status:enable
 priority:1
```

如需更改存放路径，请更改package.ini下的 init_conf_path 选项


服务启动和停止
---
pkgship使用uWSGI web服务器
```
pkgshipd start

pkgshipd stop
```
	
使用说明
---
#### 1. 数据库初始化
```
pkgship init
```
#### 2. 单包查询

查询源码包(sourceName)在所有数据库中的信息 
```
pkgship single sourceName
```
查询当前包(sourceName)在指定数据库(dbName)中的信息
```
pkgship single sourceName -db dbName
```
#### 3. 查询所有包
查询所有数据库下包含的所有包的信息
```
pkgship list
```
查询指定数据库(dbName)下的所有包的信息
```
pkgship list -db dbName
```  
#### 4. 安装依赖查询
查询二进制包(binaryName)的安装依赖，按照默认优先级查询数据库
``` 
pkgship installdep binaryName
``` 
在指定数据库(dbName)下查询二进制包(binaryName)的所有安装依赖
按照先后顺序指定数据库查询的优先级
``` 
pkgship installdep binaryName -dbs dbName1 dbName2...
``` 
#### 5. 编译依赖查询
查询源码包(sourceName)的所有编译依赖，按照默认优先级查询数据库
``` 
pkgship builddep sourceName
``` 
在指定数据库(dbName)下查询源码包(sourceName)的所有安装依赖
按照先后顺序指定数据库查询的优先级
``` 
pkgship builddep sourceName -dbs dbName1 dbName2...
``` 
#### 6. 自编译自安装依赖查询
查询二进制包(binaryName)的安装和编译依赖，按照默认优先级查询数据库
``` 
pkgship selfbuild binaryName
``` 
查询源码包(sourceName )的安装和编译依赖，按照默认优先级查询数据库
``` 
pkgship selfbuild sourceName -t source
``` 
其他参数:

-dbs 指定数据库优先级.
``` 
示例:pkgship selfbuild binaryName -dbs dbName1 dbName2 
``` 
-s 是否查询自编译依赖
默认为0不查询自编译依赖，可以指定0或1(表示查询自编译)
``` 
查询自编译示例:pkgship selfbuild sourceName -t source -s 1
``` 
-w 是否查询对应包的子包.默认为0，不查询对应子包，可以指定 0或1(表示查询对应子包)
``` 
查询子包示例:pkgship selfbuild binaryName -w 1
``` 
#### 7. 被依赖查询
查询源码包(sourceName)在某数据库(dbName)中被哪些包所依赖
查询结果默认不包含对应二进制包的子包 
``` 
pkgship bedepend sourceName -db dbName
``` 
使查询结果包含二进制包的子包 加入参数 -w
``` 
pkgship bedepend sourceName -db dbName -w 1 
``` 
#### 8. 修改包信息记录
变更数据库中(dbName)源码包(sourceName)的maintainer为Newmaintainer 
```
pkgship updatepkg sourceName db dbName -m Newmaintainer 
```
变更数据库中(dbName)源码包(sourceName)的maintainlevel为Newmaintainlevel，值在1～4之间
```
pkgship updatepkg sourceName db dbName -l Newmaintainlevel 
```
同时变更数据库中(dbName)源码包(sourceName)的maintainer 为Newmaintainer和变更maintainlevel为Newmaintainlevel
``` 
pkgship updatepkg sourceName db dbName -m Newmaintainer -l Newmaintainlevel
```
#### 9. 删除数据库
删除指定数据库(dbName)
```
pkgship rm db dbName
```

参与贡献
---
我们非常欢迎新贡献者加入到项目中来，也非常高兴能为新加入贡献者提供指导和帮助。在您贡献代码前，需要先签署[CLA](https://openeuler.org/en/cla.html)。

1. Fork 本仓库
2. 新建 Feat_xxx 分支
3. 提交代码
4. 新建 Pull Request


### 会议记录
1. 2020.5.18：https://etherpad.openeuler.org/p/aHIX4005bTY1OHtOd_Zc

