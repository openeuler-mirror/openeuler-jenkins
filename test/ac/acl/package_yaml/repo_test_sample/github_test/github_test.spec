%global _name pyinotify
%global _description Pyinotify is a Python module for monitoring filesystems changes. \
Pyinotify relies on a Linux Kernel feature (merged in kernel 2.6.13) called inotify. \
inotify is an event-driven notifier, its notifications are exported from kernel space \
to user space through three system calls. pyinotify binds these system calls and provides \
an implementation on top of them offering a generic and abstract way to manipulate those \
functionalities.

Name:           python-inotify
Version:        0.9.6
Release:	16
Summary:        A Python module for monitoring filesystems changes
License:        MIT
URL:            https://github.com/seb-m/pyinotify
Source0:        https://github.com/seb-m/pyinotify/archive/%{version}.tar.gz#/%{_name}-%{version}.tar.gz

Patch0:         pyinotify-0.9.6-epoint.patch
BuildArch:      noarch
BuildRequires:	gmp-devel

%description
%{_description}

%package    -n python2-inotify
Summary:       python2 edition of %{name}

BuildRequires: python2-devel

Provides:      python2-inotify-examples

Obsoletes:     python2-inotify-examples

%{?python_provide:%python_provide python2-inotify}

%description -n python2-inotify
This package is the python2 edition of %{name}.

%package    -n python3-inotify
Summary:       python3 edition of %{name}

BuildRequires: python3-devel

%{?python_provide:%python_provide python3-inotify}

%description -n python3-inotify
This package is the python3 edition of %{name}.

%package_help

%prep
%autosetup -n %{_name}-%{version} -p1
sed -i '1c#! %{__python2}' python2/pyinotify.py
sed -i '1c#! %{__python3}' python3/pyinotify.py
sed -i '1c#! %{__python2}' python2/examples/*py
sed -i '1c#! %{__python3}' python3/examples/*py
cp -a . $RPM_BUILD_DIR/python3-%{_name}-%{version}

%build
%py2_build
cd $RPM_BUILD_DIR/python3-%{_name}-%{version}
%py3_build

%install
cd $RPM_BUILD_DIR/python3-%{_name}-%{version}
%py3_install
mv %{buildroot}%{_bindir}/%{_name} %{buildroot}%{_bindir}/python3-%{_name}
cd -
%py2_install

%files -n python2-inotify
%defattr(-,root,root)
%doc ACKS
%license COPYING
%doc python2/examples/*
%{_bindir}/%{_name}
%{python2_sitelib}/*.py*
%{python2_sitelib}/%{_name}*info/

%files -n python3-inotify
%defattr(-,root,root)
%doc ACKS
%license COPYING
%doc python3/examples/*
%{_bindir}/*3-%{_name}
%{python3_sitelib}/*.py*
%{python3_sitelib}/%{_name}*info/
%{python3_sitelib}/__pycache__/*.pyc

%files help
%defattr(-,root,root)
%doc README.md PKG-INFO

%changelog
* Mon Dec 23 2019 openEuler Buildteam <buildteam@openeuler.org> - 0.9.6-16
- Type:NA
- ID:NA
- SUG:NA
- DESC:delete unneeded comments

* Fri Sep 27 2019 shenyangyang<shenyangyang4@huawei.com> - 0.9.6-15
- Type:enhancement
- ID:NA
- SUG:NA
- DESC:move license file

* Thu Sep 12 2019 openEuler Buildteam <buildteam@openeuler.org> - 0.9.6-14
- Package init
