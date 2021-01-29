Name:           perl-Date-Calc
Version:        6.4
Release:        12
Summary:        Gregorian calendar date calculations
License:        GPL+ or Artistic
URL:            https://metacpan.org/release/Date-Calc
Source0:        https://cpan.metacpan.org/authors/id/S/ST/STBEY/Date-Calc-%{version}.tar.gz
BuildArch:      noarch
BuildRequires:  perl-interpreter perl-generators perl(Config)
BuildRequires:  perl(strict) perl(ExtUtils::MakeMaker) >= 6.76
BuildRequires:  perl(Bit::Vector) >= 7.1 perl(bytes) perl(Carp::Clan) >= 6.04
BuildRequires:  perl(Exporter) perl(overload) perl(POSIX) perl(vars)
Requires:       perl(:MODULE_COMPAT_%(eval "$(perl -V:version)"; echo $version))
Requires:       perl(Bit::Vector) >= 7.1 perl(Carp::Clan) >= 6.04

%description
This package consists of a C library and a Perl module (which uses the C library,
internally) for all kinds of date calculations based on the Gregorian calendar
(the one used in all western countries today), thereby complying with all
relevant norms and standards: ISO/R 2015-1971, DIN 1355 and, to some extent,
ISO 8601 (where applicable).

%package_help

%prep
%autosetup -n Date-Calc-%{version}

%build
perl Makefile.PL INSTALLDIRS=vendor OPTIMIZE="%{optflags}" NO_PACKLIST=1
%make_build

%install
make pure_install DESTDIR=$RPM_BUILD_ROOT
find $RPM_BUILD_ROOT -type f -name '*.bs' -a -size 0 -exec rm -f {} +
chmod -R u+w $RPM_BUILD_ROOT/*
for file in $RPM_BUILD_ROOT%{_mandir}/man3/Date::Calc.3pm \
            CREDITS.txt; do
  iconv -f iso-8859-1 -t utf-8 < "$file" > "${file}_"
  mv -f "${file}_" "$file"
done

%check
make test

%files
%license license/Artistic.txt license/GNU_GPL.txt license/GNU_LGPL.txt
%{perl_vendorlib}/Date/

%files help
%doc CHANGES.txt CREDITS.txt README.txt
%{_mandir}/man3/*.3*

%changelog
* Tue Nov 19 2019 mengxian <mengxian@huawei.com> - 6.4-12
- Package init
