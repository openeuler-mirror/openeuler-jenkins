%bcond_with nls

Name:           help2man
Summary:        Create simple man pages from --help output
Version:        1.47.11
Release:        0
License:        GPLv3+
URL:            http://www.gnu.org/software/help2man
Source:         ftp://ftp.gnu.org/gnu/help2man/help2man-%{version}.tar.xz

%{!?with_nls:BuildArch: noarch}
BuildRequires:  gcc perl-generators perl(Getopt::Long) perl(POSIX) perl(Text::ParseWords) perl(Text::Tabs) perl(strict)
%{?with_nls:BuildRequires: perl(Locale::gettext) /usr/bin/msgfmt}
%{?with_nls:BuildRequires: perl(Encode)}
%{?with_nls:BuildRequires: perl(I18N::Langinfo)}
Requires(post): /sbin/install-info
Requires(preun): /sbin/install-info

%description
help2man is a tool for automatically generating simple manual pages from program output.

%package_help

%prep
%autosetup -n %{name}-%{version}

%build
%configure --%{!?with_nls:disable}%{?with_nls:enable}-nls --libdir=%{_libdir}/help2man
%{make_build}

%install
make install_l10n DESTDIR=$RPM_BUILD_ROOT
make install DESTDIR=$RPM_BUILD_ROOT
%find_lang %name --with-man

%post
%install_info %{_infodir}/help2man.info

%preun
if [ $1 -eq 0 ]; then
  %install_info_rm %{_infodir}/help2man.info
fi

%files -f %name.lang
%defattr(-,root,root)
%doc README NEWS THANKS
%license COPYING
%{_bindir}/help2man
%{_infodir}/*
%if %{with nls}
  %{_libdir}/help2man
%endif

%files help
%defattr(-,root,root)
%{_mandir}/man1/*

%changelog
* Thu Nov 07 2019 openEuler Buildtam <buildteam@openeuler.org> - 1.47.11-0
- Package Init
