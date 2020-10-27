Name:           perl-HTML-Tagset
Version:        3.20
Release:        37
Summary:        HTML::Tagset - data tables useful in parsing HTML
License:        GPL+ or Artistic
URL:            https://metacpan.org/release/HTML-Tagset
Source0:        https://cpan.metacpan.org/authors/id/P/PE/PETDANCE/HTML-Tagset-%{version}.tar.gz

BuildArch:      noarch

BuildRequires:  perl-generators perl-interpreter perl(:VERSION) >= 5.4
BuildRequires:  perl(ExtUtils::MakeMaker) >= 6.76 perl(strict) perl(vars)
BuildRequires:  perl(Test) perl(Test::More)
BuildRequires:  perl(Test::Pod) >= 1.14

Requires:       perl(:MODULE_COMPAT_%(eval "`perl -V:version`"; echo $version))

%description
This module contains data tables useful in dealing with HTML.
It provides no functions or methods.

%package help
Summary:        Documentation for perl-HTML-Tagset

%description help
Documentation for perl-HTML-Tagset.

%prep
%autosetup -n HTML-Tagset-%{version} -p1

%build
perl Makefile.PL INSTALLDIRS=vendor NO_PACKLIST=1
%make_build

%install
make pure_install DESTDIR=%{buildroot}
%{_fixperms} %{buildroot}

%check
make test

%files
%{perl_vendorlib}/HTML/
%exclude  %{_libdir}/perl5/perllocal.pod

%files help
%doc Changes README
%{_mandir}/man3/


%changelog
* Tue Oct 22 2019 Zaiwang Li <lizaiwang1@huawei.com> - 3.20-37
- Init Package.

