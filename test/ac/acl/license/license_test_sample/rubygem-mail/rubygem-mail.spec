%global gem_name mail
Name:                rubygem-%{gem_name}
Version:             2.6.4
Release:             2
Summary:             Mail provides a nice Ruby DSL for making, sending and reading emails
License:             MIT
URL:                 https://github.com/mikel/mail
Source0:             https://rubygems.org/gems/%{gem_name}-%{version}.gem
Source1:             https://github.com/mikel/mail/archive/%{version}.tar.gz
# Fix Ruby 2.4 compatibility.
# https://github.com/mikel/mail/commit/e8fde9cf1d77ee7e465c12e809501df8d27e8451
Patch0:              mail-2.6.4-Fix-deprecated-warnings-in-Ruby-2.4.0.patch
# https://github.com/mikel/mail/commit/48cb6db25b31eebe7bdd330d812c52d3c93aa328
Patch1:              mail-2.6.4-fix-new-warning-in-ruby-2.4.patch
BuildRequires:       ruby(release) rubygems-devel ruby rubygem(mime-types) >= 1.16 rubygem(rspec)
BuildArch:           noarch
%description
A really Ruby Mail handler.

%package doc
Summary:             Documentation for %{name}
Requires:            %{name} = %{version}-%{release}
BuildArch:           noarch
%description doc
Documentation for %{name}.

%prep
%setup -q -c -T
ln -s %{_builddir}/%{gem_name}-%{version}/spec ../spec
%gem_install -n %{SOURCE0}
pushd .%{gem_instdir}
%patch0 -p1
%patch1 -p1
popd

%build

%install
mkdir -p %{buildroot}%{gem_dir}
cp -a .%{gem_dir}/* \
        %{buildroot}%{gem_dir}/

%check
pushd .%{gem_instdir}
tar xzvf %{SOURCE1}
rspec spec
popd

%files
%dir %{gem_instdir}
%license %{gem_instdir}/MIT-LICENSE
%{gem_libdir}
%exclude %{gem_cache}
%{gem_spec}

%files doc
%doc %{gem_docdir}
%doc %{gem_instdir}/CHANGELOG.rdoc
%doc %{gem_instdir}/CONTRIBUTING.md
%doc %{gem_instdir}/Dependencies.txt
%{gem_instdir}/Gemfile*
%doc %{gem_instdir}/README.md
%{gem_instdir}/Rakefile
%doc %{gem_instdir}/TODO.rdoc

%changelog
* Tue Sep 8 2020 geyanan <geyanan2@huawei.com> - 2.6.4-2
- fix build fail

* Wed Aug 19 2020 geyanan <geyanan2@huawei.com> - 2.6.4-1
- package init
