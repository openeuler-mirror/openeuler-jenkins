Name:           spec_fail
Version:        1.1.0
Release:        1
Summary:        test case for spec license error.
License:        Mulan 2.0 and ADSL
URL:            https://gitee.com/openeuler/openEuler-Advisor
Source0:        https://gitee.com/openeuler/openEuler-Advisor/pkgship-%{version}.tar.gz

%description
test case for spec license error.

%prep
%autosetup

%build
%py3_build

%install
%py3_install

%check

%post

%postun


%files
%doc README.md
%{python3_sitelib}/*
%attr(0755,root,root) %config %{_sysconfdir}/pkgship/*
%attr(0755,root,root) %{_bindir}/pkgshipd
%attr(0755,root,root) %{_bindir}/pkgship

%changelog
* Mon Oct 19 2020 xxx  <xxx@xxx.com> - 1.0-0
- init package
