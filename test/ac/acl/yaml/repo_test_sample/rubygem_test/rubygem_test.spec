%global gem_name idn
Name:                rubygem-%{gem_name}
Version:             0.0.2
Release:             1
Summary:             Ruby Bindings for the GNU LibIDN library
License:             ASL 2.0 and LGPLv2+
URL:                 https://rubygems.org/gems/idn
Source0:             https://rubygems.org/gems/%{gem_name}-%{version}.gem
Patch0:              rubygem-idn-0.0.2-Fix-for-ruby-1.9.x.patch
Patch1:              rubygem-idn-0.0.2-ruby2-encoding-in-tests-fix.patch
BuildRequires:       ruby(release) rubygems-devel ruby-devel gcc libidn-devel rubygem(test-unit)
%description
Ruby Bindings for the GNU LibIDN library, an implementation of the Stringprep,
Punycode and IDNA specifications defined by the IETF Internationalized Domain
Names (IDN) working group.

%package doc
Summary:             Documentation for %{name}
Requires:            %{name} = %{version}-%{release}
BuildArch:           noarch
%description doc
Documentation for %{name}.

%prep
%setup -q -n %{gem_name}-%{version}
%patch0 -p0
%patch1 -p1

%build
gem build ../%{gem_name}-%{version}.gemspec
%gem_install

%install
mkdir -p %{buildroot}%{gem_dir}
cp -a .%{gem_dir}/* \
        %{buildroot}%{gem_dir}/
mkdir -p %{buildroot}%{gem_extdir_mri}
cp -a .%{gem_extdir_mri}/{gem.build_complete,*.so} %{buildroot}%{gem_extdir_mri}/
rm -rf %{buildroot}%{gem_instdir}/ext/

%check
pushd .%{gem_instdir}
ruby -I$(dirs +1)%{gem_extdir_mri} -e 'Dir.glob "./test/tc_*.rb", &method(:require)'
popd

%files
%dir %{gem_instdir}
%{gem_extdir_mri}
%license %{gem_instdir}/LICENSE
%exclude %{gem_libdir}
%exclude %{gem_cache}
%{gem_spec}

%files doc
%doc %{gem_docdir}
%doc %{gem_instdir}/CHANGES
%doc %{gem_instdir}/NOTICE
%doc %{gem_instdir}/README
%{gem_instdir}/Rakefile
%{gem_instdir}/test

%changelog
* Sat Jul 25 2020 wutao <wutao61@huawei.com> - 0.0.2-1
- package init
