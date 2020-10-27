Name:           lame
Version:        3.100
Release:        7
Summary:        Free MP3 audio compressor
License:        GPLv2+
URL:            http://lame.sourceforge.net/
Source0:        http://downloads.sourceforge.net/sourceforge/lam/lam-3.100.tar.gz
Patch0001:      lame-noexecstack.patch
Patch0002:      libmp3lame-symbols.patch

BuildRequires:  ncurses-devel gtk+-devel

Provides:       %{name}-libs = %{version}-%{release}
Obsoletes:      %{name}-libs < %{version}-%{release}

%description
LAME is a high quality MPEG Audio Layer III (MP3) encoder.

%package        devel
Summary:        Development files for lame
Requires:       %{name} = %{version}-%{release}

%description    devel
The lame-devel package contains development files for lame.

%package        help
Summary:        man info for lame

%description    help
The lame-help Package contains man info for lame.

%package        mp3x
Summary:        MP3 frame analyzer
Requires:       %{name} = %{version}-%{release}

%description    mp3x
The lame-mp3x package contains the mp3x frame analyzer.


%prep
%autosetup -p1


%build
sed -i -e 's/^\(\s*hardcode_libdir_flag_spec\s*=\).*/\1/' configure
%configure \
  --disable-dependency-tracking --disable-static --enable-mp3x --enable-mp3rtp
%make_build


%install
%make_install
%delete_la
ln -sf lame/lame.h %{buildroot}%{_includedir}/lame.h


%check
make test

%post
/sbin/ldconfig

%postun
/sbin/ldconfig


%files
%exclude %{_docdir}/%{name}
%doc README TODO USAGE doc/html/*.html ChangeLog COPYING LICENSE
%{_bindir}/{lame,mp3rtp}
%{_libdir}/libmp3lame.so.0*

%files devel
%exclude %{_docdir}/%{name}
%doc API HACKING STYLEGUIDE
%{_libdir}/libmp3lame.so
%{_includedir}/{lame,lame.h}

%files help
%{_mandir}/man1/lame.1*

%files mp3x
%{_bindir}/mp3x

%changelog
* Thu Dec 12 2019 zoushuangshuang<zoushuangshuang@huawei.com> - 3.100-7
- Package init
