Name:           pkgship
Version:        1.1.0
Release:        14
Summary:        Pkgship implements rpm package dependence ,maintainer, patch query and so no.
License:        Mulan 2.0
URL:            https://gitee.com/openeuler/openEuler-Advisor
Source0:        https://gitee.com/openeuler/openEuler-Advisor/pkgship-%{version}.tar.gz

# Modify the query logic of package information, reduce redundant queries and align dnf query results, 
# extract multiplexing functions, add corresponding docString, and clear pylint
Patch0:         0001-solve-installation-dependency-query-error.patch

# Fix the problem of continuous spaces in message information in log records
Patch1:         0002-fix-the-problem-of-continuous-spaces.patch

# When initializing logging, modify the incoming class object to an instance of the class,
# ensure the execution of internal functions,and read configuration file content
Patch2:         0003-fix-log_level-configuration-item-not-work.patch

# Fix the error when executing query commands
Patch3:         0004-fix-the-error-when-executing-query-commands.patch

# Add the judgment of whether the subpack_name attribute exists, fix the code indentation problem, 
# and reduce the judgment branch of the old code.
Patch4:         0005-fix-the-error-when-source-package-has-no-sub-packages.patch
 
# Solve the problem of data duplication, increase the maximum queue length judgment, 
# and avoid occupying too much memory
Patch5:         0006-fix-memory_caused-service-crash-and-data-duplication-issue.patch

# Fix the problem of function parameters
Patch6:	        0007-correct-the-parameter-transfer-method-and-change-the-status-recording-method.patch

# Fix the selfbuild error message
Patch7:		0008-fix-selfbuild-error-message.patch

# Optimize-log-records-when-obtaining-issue-content
Patch8:         0009-optimize-log-records-when-obtaining-issue-content.patch
BuildArch:      noarch

BuildRequires: python3-flask-restful python3-flask python3 python3-pyyaml python3-sqlalchemy
BuildRequires: python3-prettytable python3-requests python3-flask-session python3-flask-script python3-marshmallow
BuildRequires: python3-Flask-APScheduler python3-pandas python3-retrying python3-xlrd python3-XlsxWriter
BuildRequires: python3-concurrent-log-handler
Requires: python3-pip python3-flask-restful python3-flask python3 python3-pyyaml
Requires: python3-sqlalchemy python3-prettytable python3-requests python3-concurrent-log-handler
Requires: python3-flask-session python3-flask-script python3-marshmallow python3-uWSGI
Requires: python3-pandas python3-dateutil python3-XlsxWriter python3-xlrd python3-Flask-APScheduler python3-retrying

%description
Pkgship implements rpm package dependence ,maintainer, patch query and so no.

%prep
%autosetup -n pkgship-%{version} -p1

%build
%py3_build

%install
%py3_install


%check
# The apscheduler cannot catch the local time, so a time zone must be assigned before running the test case.
export TZ=Asia/Shanghai
# change log_path to solve default log_path permission denied problem
log_path=`pwd`/tmp/
sed -i "/\[LOG\]/a\log_path=$log_path" test/common_files/package.ini
%{__python3} -m unittest test/init_test.py
%{__python3} -m unittest test/read_test.py
%{__python3} -m unittest test/write_test.py
rm -rf $log_path

%post

%postun


%files
%doc README.md
%{python3_sitelib}/*
%attr(0755,root,root) %config %{_sysconfdir}/pkgship/*
%attr(0755,root,root) %{_bindir}/pkgshipd
%attr(0755,root,root) %{_bindir}/pkgship

%changelog
* Tue Oct 13 2020 ZhangTao <zhangtao307@huawei.com> 1.1.0-14
- correct-the-parameter-transfer-method-and-change-the-status-recording-method.

* Fri Sep 25 2020 Cheng Shaowei <chenshaowei3@huawei.com> 1.1.0-13
- Optimize-log-records-when-obtaining-issue-content

* Fri Sep 25 2020 Zhang Tao <zhangtao307@huawei.com> - 1.1.0-12
- In the selfbuild scenario, add the error message that the software package cannot be found 

* Fri Sep 25 2020 Zhang Tao <zhangtao307@huawei.com> - 1.1.0-11
- Fix the problem of function parameters

* Thu Sep 24 2020 Yiru Wang <wangyiru1@huawei.com> - 1.1.0-10
- rm queue_maxsize param from package.ini and this parameter is not customizable

* Tue Sep 21 2020 Shenmei Tu <tushenmei@huawei.com> - 1.0-0-9
- Solve the problem of data duplication, increase the maximum queue length judgment, 
- and avoid occupying too much memory

* Mon Sep 21 2020 Shenmei Tu <tushenmei@huawei.com> - 1.0-0-8
- Add the judgment of whether the subpack_name attribute exists, fix the code indentation problem, 
- and reduce the judgment branch of the old code.

* Mon Sep 21 2020 Shenmei Tu <tushenmei@huawei.com> - 1.0-0-7
- fix the error when executing query commands

* Mon Sep 21 2020 Shenmei Tu <tushenmei@huawei.com> - 1.0-0-6
- When initializing logging, modify the incoming class object to an instance of the class,
- ensure the execution of internal functions,and read configuration file content

* Mon Sep 21 2020 Shenmei Tu <tushenmei@huawei.com> - 1.0-0-5
- Fix the problem of continuous spaces in message information in log records

* Thu Sep 17 2020 Shenmei Tu <tushenmei@huawei.com> - 1.0-0-4
- Modify the query logic of package information, reduce redundant queries and align dnf query results, 
- extract multiplexing functions, add corresponding docString, and clear pylint

* Fri Sep 11 2020 Yiru Wang <wangyiru1@huawei.com> - 1.1.0-3
- #I1UCM8, #I1UC8G: Modify some config files' permission issue;
- #I1TIYQ: Add concurrent-log-handler module to fix log resource conflict issue
- #I1TML0: Fix the matching relationship between source_rpm and src_name

* Tue Sep 1 2020 Zhengtang Gong <gongzhengtang@huawei.com> - 1.1.0-2
- Delete the packaged form of pyinstaller and change the execution
  of the command in the form of a single file as the input

* Sat Aug 29 2020 Yiru Wang <wangyiru1@huawei.com> - 1.1.0-1
- Add package management features:
  RPM packages statically displayed in the version repository
  RPM packages used time displayed for current version in the version repository
  Issue management of packages in a version-management repository

* Fri Aug 21 2020 Chengqiang Bao < baochengqiang1@huawei.com > - 1.0.0-7
- Fixed a problem with command line initialization of the Filepath parameter where relative paths are not supported and paths are too long

* Wed Aug 12 2020 Zhang Tao <zhangtao306@huawei.com> - 1.0.0-6
- Fix the test content to adapt to the new data structure, add BuildRequires for running %check

* Mon Aug 10 2020 Zhengtang Gong <gongzhengtang@huawei.com> - 1.0-5
- Command line supports calling remote services

* Wed Aug 5 2020 Yiru Wang <wangyiru1@huawei.com> - 1.0-4
- change Requires rpm pakcages' name to latest one

* Mon Jul 13 2020 Yiru Wang <wangyiru1@huawei.com> - 1.0-3
- run test cases while building

* Sat Jul 4 2020 Yiru Wang <wangyiru1@huawei.com> - 1.0-2
- cheange requires python3.7 to python3,add check pyinstaller file.

* Tue Jun 30 2020 Yiru Wang <wangyiru1@huawei.com> - 1.0-1
- add pkgshipd file

* Thu Jun 11 2020 Feng Hu <solar.hu@foxmail.com> - 1.0-0
- add macro to build cli bin when rpm install

* Sat Jun 6 2020 Feng Hu  <solar.hu@foxmail.com> - 1.0-0
- init package
