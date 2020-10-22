%global __requires_exclude ^perl\\(Autom4te::
%global __provides_exclude ^perl\\(Autom4te::

Name:           autoconf
Version:        2.69
Release:        30
Summary:        An extensible package to automatically configure software source code packages
License:        GPLv2+ and GPLv3+ and GFDL
URL:            https://www.gnu.org/software/%{name}/
Source0:        http://ftp.gnu.org/gnu/%{name}/%{name}-%{version}.tar.xz
Source1:        config.site
Source2:        autoconf-el.el

# four patches backport from upstream to solve test suite failure
Patch1:         autoscan-port-to-perl-5.17.patch
Patch2:         Port-tests-to-Bash-5.patch
Patch3:         tests-avoid-spurious-test-failure-with-libtool-2.4.3.patch
#fix the failure of test 38 autotools and whitespace in file names
Patch4:         Fix-test-suite-with-modern-Perl.patch

Patch9000:      skip-one-test-at-line-1616-of-autotest.patch

BuildArch:      noarch

BuildRequires:  m4 emacs perl perl-generators help2man
Requires:       m4 emacs-filesystem
Requires(post): info
Requires(preun):info

%package_help

%description
Autoconf is an extensible package of M4 macros that produce shell scripts to automatically
configure software source code packages. These scripts can adapt the packages to many kinds
of UNIX-like systems without manual user intervention. Autoconf creates a configuration script
for a package from a template file that lists the operating system features that the package
can use, in the form of M4 macro calls.

%prep
%autosetup -n %{name}-%{version} -p1

%build
export EMACS=%{_bindir}/emacs
%configure --with-lispdir=%{_emacs_sitelispdir}/autoconf
%make_build

%check
make %{?_smp_mflags} check

%install
%make_install
install -p -D %{SOURCE1} %{buildroot}%{_datadir}
install -p -D %{SOURCE2} %{buildroot}%{_emacs_sitestartdir}/autoconf-el.el

%post help
/sbin/install-info %{_infodir}/autoconf.info %{_infodir}/dir || :

%preun help
if [ "$1" = 0 ]; then
    /sbin/install-info --delete %{_infodir}/autoconf.info %{_infodir}/dir || :
fi

%files
%doc  ChangeLog README THANKS
%license COPYING* AUTHORS doc/autoconf.info
%{_bindir}/*
%{_datadir}/autoconf/
%{_datadir}/config.site
%{_datadir}/emacs/site-lisp/*
%exclude %{_infodir}/standards*

%files help
%doc NEWS TODO
%{_infodir}/autoconf.info*
%{_mandir}/man1/*
%exclude %{_infodir}/dir


%changelog
* Sat Jan 4 2020 openEuler Buildteam <buildteam@openeuler.org> - 2.69-30
- Strengthen sources and patches

* Fri Oct 11 2019 openEuler Buildteam <buildteam@openeuler.org> - 2.69-29
- Package Init
