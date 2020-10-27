Name:           gnome-dictionary
Version:        3.26.1
Release:        4
Summary:        A dictionary application for GNOME
License:        GPLv3+ and LGPLv2+ and GFDL
URL:            https://wiki.gnome.org/Apps/Dictionary
Source0:        https://download.gnome.org/sources/%{name}/3.26/%{name}-%{version}.tar.xz

BuildRequires:  desktop-file-utils docbook-style-xsl gettext itstool libappstream-glib libxslt
BuildRequires:  meson pkgconfig(gobject-introspection-1.0) pkgconfig(gtk+-3.0)
Obsoletes:      gnome-utils <= 1:3.3 gnome-utils-libs <= 1:3.3 gnome-utils-devel <= 1:3.3
Obsoletes:      gnome-dictionary-devel < 3.26.0 gnome-dictionary-libs < 3.26.0

%description
GNOME Dictionary is a simple, clean, elegant application to look up words in
online dictionaries using the DICT protocol.

%package help
Summary:        Help package for gnome-dictionary

%description help
This package contains some man help files for gnome-dictionary.

%prep
%autosetup -n %{name}-%{version} -p1

%build
%meson
%meson_build

%install
%meson_install
%find_lang %{name} --with-gnome

%check
appstream-util validate-relax --nonet %{buildroot}/%{_datadir}/appdata/*.appdata.xml
desktop-file-validate %{buildroot}/%{_datadir}/applications/*.desktop

%postun
if [ $1 -eq 0 ]; then
  glib-compile-schemas %{_datadir}/glib-2.0/schemas &>/dev/null || :
fi

%posttrans
glib-compile-schemas %{_datadir}/glib-2.0/schemas &>/dev/null || :

%files -f %{name}.lang
%doc COPYING* NEWS README.md
%{_bindir}/gnome-dictionary
%{_datadir}/*
%exclude %{_datadir}/man*

%files help
%{_mandir}/man1/gnome-dictionary.1*

%changelog
* Wed Dec 11 2019 lingsheng <lingsheng@huawei.com> - 3.26.1-4
- Package init
