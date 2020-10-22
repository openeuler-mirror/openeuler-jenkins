Name:               python-idna	
Version:            2.10
Release:            1
Summary:            Internationalized Domain Names in Applications (IDNA)
License:            BSD and Python and Unicode         	
URL:                https://github.com/kjd/idna
Source0:            https://files.pythonhosted.org/packages/source/i/idna/idna-%{version}.tar.gz

BuildArch:          noarch
%if 0%{?with_python2}
BuildRequires:      python2-devel python2-setuptools 
%endif
%if 0%{?with_python3}
BuildRequires:      python3-devel python3-setuptools
%endif

%description
A library to support the Internationalised Domain Names in
Applications (IDNA) protocol as specified in RFC 5891
http://tools.ietf.org/html/rfc5891. This version of the protocol
is often referred to as “IDNA2008” and can produce different
results from the earlier standard from 2003.

The library is also intended to act as a suitable drop-in replacement
for the “encodings.idna” module that comes with the Python standard
library but currently only supports the older 2003 specification.

%if 0%{?with_python2}
%package -n         python2-idna
Summary:            Python2 package for python-idna
Provides:           python-idna = %{version}-%{release}
Obsoletes:          python-idna < %{version}-%{release}

%description -n     python2-idna
Python2 package for python-idna
%endif

%if 0%{?with_python3}
%package -n         python3-idna
Summary:            Python3 package for python-idna
%{?python_provide:  %python_provide python3-idna}

%description -n     python3-idna
Python3 package for python-idna
%endif

%prep
%autosetup -n idna-%{version} -p1

%build
%if 0%{?with_python2}
%py2_build
%endif

%if 0%{?with_python3}
%py3_build
%endif

%install
%if 0%{?with_python2}
%py2_install
%endif

%if 0%{?with_python3}
%py3_install
%endif

%check
%if 0%{?with_python2}
%{__python2} setup.py test
%endif

%if 0%{?with_python3}
%{__python3} setup.py test
%endif

%if 0%{?with_python2}
%files -n python2-idna
%defattr(-,root,root)
%doc README.rst HISTORY.rst
%license LICENSE.rst
%{python2_sitelib}/*
%endif

%if 0%{?with_python3}
%files -n python3-idna
%defattr(-,root,root)
%doc README.rst HISTORY.rst
%license LICENSE.rst
%{python3_sitelib}/*
%endif

%changelog
* Thu Jul 23 2020 zhouhaibo <zhouhaibo@huawei.com> - 2.10-1
- Package update

* Wed Jan 15 2020 openEuler Buildteam <buildteam@openeuler.org> - 2.8-3
- Type:bugfix
- Id:NA
- SUG:NA
- DESC:delete the python-idna

* Tue Jan 14 2020 openEuler Buildteam <buildteam@openeuler.org> - 2.8-2
- Type:bugfix
- Id:NA
- SUG:NA
- DESC:delete the python provides in python2

* Wed Sep 4 2019 openEuler Buildteam <buildteam@openeuler.org> - 2.8-1
- Package init
