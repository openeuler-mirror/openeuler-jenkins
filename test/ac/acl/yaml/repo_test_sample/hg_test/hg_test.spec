%global  _hardened_build     1
%global  nginx_user          nginx

%undefine _strict_symbol_defs_build

%bcond_with geoip

%global with_gperftools 1

%global with_mailcap_mimetypes 0

%global with_aio 1

Name:              nginx
Epoch:             1
Version:           1.18.0
Release:           2
Summary:           A HTTP server, reverse proxy and mail proxy server
License:           BSD
URL:               http://nginx.org/

Source0:           https://nginx.org/download/nginx-%{version}.tar.gz
Source10:          nginx.service
Source11:          nginx.logrotate
Source12:          nginx.conf
Source13:          nginx-upgrade
Source100:         index.html
Source102:         nginx-logo.png
Source103:         404.html
Source104:         50x.html
Source200:         README.dynamic
Source210:         UPGRADE-NOTES-1.6-to-1.10

Patch0:            nginx-auto-cc-gcc.patch
Patch2:            nginx-1.12.1-logs-perm.patch
BuildRequires:     gcc openssl-devel pcre-devel zlib-devel systemd gperftools-devel
Requires:          nginx-filesystem = %{epoch}:%{version}-%{release} openssl pcre
Requires:          nginx-all-modules = %{epoch}:%{version}-%{release}        
%if 0%{?with_mailcap_mimetypes}
Requires:          nginx-mimetypes
%endif
Requires(pre):     nginx-filesystem
Requires(post):    systemd
Requires(preun):   systemd
Requires(postun):  systemd
Provides:          webserver
Recommends:        logrotate

%description
NGINX is a free, open-source, high-performance HTTP server and reverse proxy, 
as well as an IMAP/POP3 proxy server.

%package all-modules
Summary:           Nginx modules
BuildArch:         noarch

%if %{with geoip}
Requires:          nginx-mod-http-geoip = %{epoch}:%{version}-%{release}
%endif
Requires:          nginx-mod-http-image-filter = %{epoch}:%{version}-%{release}
Requires:          nginx-mod-http-perl = %{epoch}:%{version}-%{release}
Requires:          nginx-mod-http-xslt-filter = %{epoch}:%{version}-%{release}
Requires:          nginx-mod-mail = %{epoch}:%{version}-%{release}
Requires:          nginx-mod-stream = %{epoch}:%{version}-%{release}

%description all-modules
NGINX is a free, open-source, high-performance HTTP server and reverse proxy, 
as well as an IMAP/POP3 proxy server.
This package is a meta package that installs all available Nginx modules.

%package filesystem
Summary:           Filesystem for the Nginx server
BuildArch:         noarch
Requires(pre):     shadow-utils

%description filesystem
NGINX is a free, open-source, high-performance HTTP server and reverse proxy, 
as well as an IMAP/POP3 proxy server.
The package contains the basic directory layout for the Nginx server.

%if %{with geoip}
%package mod-http-geoip
Summary:           HTTP geoip module for nginx
BuildRequires:     GeoIP-devel
Requires:          nginx GeoIP

%description mod-http-geoip
The package is the Nginx HTTP geoip module.
%endif

%package mod-http-image-filter
Summary:           HTTP image filter module for nginx
BuildRequires:     gd-devel
Requires:          nginx gd

%description mod-http-image-filter
Nginx HTTP image filter module.

%package mod-http-perl
Summary:           HTTP perl module for nginx
BuildRequires:     perl-devel perl(ExtUtils::Embed)
Requires:          nginx  perl(constant)
Requires:          perl(:MODULE_COMPAT_%(eval "`%{__perl} -V:version`"; echo $version))

%description mod-http-perl
Nginx HTTP perl module.

%package mod-http-xslt-filter
Summary:           XSLT module for nginx
BuildRequires:     libxslt-devel
Requires:          nginx

%description mod-http-xslt-filter
Nginx XSLT module.

%package mod-mail
Summary:           mail modules for nginx
Requires:          nginx

%description mod-mail
Nginx mail modules

%package mod-stream
Summary:           stream modules for nginx
Requires:          nginx

%description mod-stream
Nginx stream modules.

%package_help

%prep
%autosetup -n %{name}-%{version} -p1
cp %{SOURCE200} %{SOURCE210} %{SOURCE10} %{SOURCE12} .

%build
export DESTDIR=%{buildroot}
nginx_ldopts="$RPM_LD_FLAGS -Wl,-E"
if ! ./configure \
    --prefix=%{_datadir}/nginx --sbin-path=%{_sbindir}/nginx --modules-path=%{_libdir}/nginx/modules \
    --conf-path=%{_sysconfdir}/nginx/nginx.conf --error-log-path=%{_localstatedir}/log/nginx/error.log \
    --http-log-path=%{_localstatedir}/log/nginx/access.log \
    --http-client-body-temp-path=%{_localstatedir}/lib/nginx/tmp/client_body \
    --http-fastcgi-temp-path=%{_localstatedir}/lib/nginx/tmp/fastcgi \
    --http-proxy-temp-path=%{_localstatedir}/lib/nginx/tmp/proxy \
    --http-scgi-temp-path=%{_localstatedir}/lib/nginx/tmp/scgi \
    --http-uwsgi-temp-path=%{_localstatedir}/lib/nginx/tmp/uwsgi \
    --pid-path=/run/nginx.pid --lock-path=/run/lock/subsys/nginx \
    --user=%{nginx_user} --group=%{nginx_user} \
%if 0%{?with_aio}
    --with-file-aio \
%endif
    --with-ipv6 --with-http_ssl_module --with-http_v2_module --with-http_realip_module \
    --with-http_addition_module --with-http_xslt_module=dynamic --with-http_image_filter_module=dynamic \
%if %{with geoip}
    --with-http_geoip_module=dynamic \
%endif
    --with-http_sub_module --with-http_dav_module --with-http_flv_module --with-http_mp4_module \
    --with-http_gunzip_module --with-http_gzip_static_module --with-http_random_index_module \
    --with-http_secure_link_module --with-http_degradation_module --with-http_slice_module \
    --with-http_perl_module=dynamic --with-http_auth_request_module \
    --with-mail=dynamic --with-mail_ssl_module --with-pcre --with-pcre-jit --with-stream=dynamic \
    --with-stream_ssl_module --with-google_perftools_module --with-debug \
    --with-cc-opt="%{optflags} $(pcre-config --cflags)" --with-ld-opt="$nginx_ldopts"; then
  : configure failed
  cat objs/autoconf.err
  exit 1
fi

%make_build


%install
%make_install INSTALLDIRS=vendor

find %{buildroot} -type f -empty -exec rm -f '{}' \;
find %{buildroot} -type f -name .packlist -exec rm -f '{}' \;
find %{buildroot} -type f -name perllocal.pod -exec rm -f '{}' \;
find %{buildroot} -type f -iname '*.so' -exec chmod 0755 '{}' \;

pushd %{buildroot}
install -p -D -m 0644 %{_builddir}/nginx-%{version}/nginx.service .%{_unitdir}/nginx.service
install -p -D -m 0644 %{SOURCE11} .%{_sysconfdir}/logrotate.d/nginx
install -p -d -m 0755 .%{_sysconfdir}/systemd/system/nginx.service.d
install -p -d -m 0755 .%{_unitdir}/nginx.service.d
install -p -d -m 0755 .%{_sysconfdir}/nginx/conf.d
install -p -d -m 0755 .%{_sysconfdir}/nginx/default.d
install -p -d -m 0700 .%{_localstatedir}/lib/nginx
install -p -d -m 0700 .%{_localstatedir}/lib/nginx/tmp
install -p -d -m 0700 .%{_localstatedir}/log/nginx
install -p -d -m 0755 .%{_datadir}/nginx/html
install -p -d -m 0755 .%{_datadir}/nginx/modules
install -p -d -m 0755 .%{_libdir}/nginx/modules
install -p -m 0644 %{_builddir}/nginx-%{version}/nginx.conf .%{_sysconfdir}/nginx
install -p -m 0644 %{SOURCE100} .%{_datadir}/nginx/html
install -p -m 0644 %{SOURCE102} .%{_datadir}/nginx/html
install -p -m 0644 %{SOURCE103} %{SOURCE104} .%{_datadir}/nginx/html

%if 0%{?with_mailcap_mimetypes}
rm -f .%{_sysconfdir}/nginx/mime.types
%endif

install -p -D -m 0644 %{_builddir}/nginx-%{version}/man/nginx.8 .%{_mandir}/man8/nginx.8
install -p -D -m 0755 %{SOURCE13} .%{_bindir}/nginx-upgrade
popd

for i in ftdetect indent syntax; do
    install -p -D -m644 contrib/vim/${i}/nginx.vim %{buildroot}%{_datadir}/vim/vimfiles/${i}/nginx.vim
done

%if %{with geoip}
echo 'load_module "%{_libdir}/nginx/modules/ngx_http_geoip_module.so";' \
    > %{buildroot}%{_datadir}/nginx/modules/mod-http-geoip.conf
%endif

pushd %{buildroot}
echo 'load_module "%{_libdir}/nginx/modules/ngx_http_image_filter_module.so";' \
    > .%{_datadir}/nginx/modules/mod-http-image-filter.conf
echo 'load_module "%{_libdir}/nginx/modules/ngx_http_perl_module.so";' \
    > .%{_datadir}/nginx/modules/mod-http-perl.conf
echo 'load_module "%{_libdir}/nginx/modules/ngx_http_xslt_filter_module.so";' \
    > .%{_datadir}/nginx/modules/mod-http-xslt-filter.conf
echo 'load_module "%{_libdir}/nginx/modules/ngx_mail_module.so";' \
    > .%{_datadir}/nginx/modules/mod-mail.conf
echo 'load_module "%{_libdir}/nginx/modules/ngx_stream_module.so";' \
    > .%{_datadir}/nginx/modules/mod-stream.conf
popd

%pre filesystem
getent group %{nginx_user} > /dev/null || groupadd -r %{nginx_user}
getent passwd %{nginx_user} > /dev/null || useradd -r -d %{_localstatedir}/lib/nginx -g %{nginx_user} \
    -s /sbin/nologin -c "Nginx web server" %{nginx_user}
exit 0

%post
%systemd_post nginx.service

%if %{with geoip}
%post mod-http-geoip
if [ $1 -eq 1 ]; then
    systemctl reload nginx.service >/dev/null 2>&1 || :
fi
%endif

%post mod-http-image-filter
if [ $1 -eq 1 ]; then
    systemctl reload nginx.service >/dev/null 2>&1 || :
fi

%post mod-http-perl
if [ $1 -eq 1 ]; then
    systemctl reload nginx.service >/dev/null 2>&1 || :
fi

%post mod-http-xslt-filter
if [ $1 -eq 1 ]; then
    systemctl reload nginx.service >/dev/null 2>&1 || :
fi

%post mod-mail
if [ $1 -eq 1 ]; then
    systemctl reload nginx.service >/dev/null 2>&1 || :
fi

%post mod-stream
if [ $1 -eq 1 ]; then
    systemctl reload nginx.service >/dev/null 2>&1 || :
fi

%preun
%systemd_preun nginx.service

%postun
%systemd_postun nginx.service
if [ $1 -ge 1 ]; then
    /usr/bin/nginx-upgrade >/dev/null 2>&1 || :
fi

%files
%defattr(-,root,root)
%license LICENSE
%config(noreplace) %{_sysconfdir}/nginx/*
%config(noreplace) %{_sysconfdir}/logrotate.d/nginx
%exclude %{_sysconfdir}/nginx/conf.d
%exclude %{_sysconfdir}/nginx/default.d
%if 0%{?with_mailcap_mimetypes}
%exclude %{_sysconfdir}/nginx/mime.types
%endif
%{_bindir}/nginx-upgrade
%{_sbindir}/nginx
%dir %{_libdir}/nginx/modules
%attr(770,%{nginx_user},root) %dir %{_localstatedir}/lib/nginx
%attr(770,%{nginx_user},root) %dir %{_localstatedir}/lib/nginx/tmp
%{_unitdir}/nginx.service
%{_datadir}/nginx/html/*
%{_datadir}/vim/vimfiles/ftdetect/nginx.vim
%{_datadir}/vim/vimfiles/syntax/nginx.vim
%{_datadir}/vim/vimfiles/indent/nginx.vim
%attr(770,%{nginx_user},root) %dir %{_localstatedir}/log/nginx

%files all-modules

%files filesystem
%dir %{_sysconfdir}/nginx
%dir %{_sysconfdir}/nginx/{conf.d,default.d}
%dir %{_sysconfdir}/systemd/system/nginx.service.d
%dir %{_unitdir}/nginx.service.d
%dir %{_datadir}/nginx
%dir %{_datadir}/nginx/html

%if %{with geoip}
%files mod-http-geoip
%{_libdir}/nginx/modules/ngx_http_geoip_module.so
%{_datadir}/nginx/modules/mod-http-geoip.conf
%endif

%files mod-http-image-filter
%{_libdir}/nginx/modules/ngx_http_image_filter_module.so
%{_datadir}/nginx/modules/mod-http-image-filter.conf

%files mod-http-perl
%{_libdir}/nginx/modules/ngx_http_perl_module.so
%{_datadir}/nginx/modules/mod-http-perl.conf
%dir %{perl_vendorarch}/auto/nginx
%{perl_vendorarch}/nginx.pm
%{perl_vendorarch}/auto/nginx/nginx.so

%files mod-http-xslt-filter
%{_libdir}/nginx/modules/ngx_http_xslt_filter_module.so
%{_datadir}/nginx/modules/mod-http-xslt-filter.conf

%files mod-mail
%{_libdir}/nginx/modules/ngx_mail_module.so
%{_datadir}/nginx/modules/mod-mail.conf

%files mod-stream
%{_libdir}/nginx/modules/ngx_stream_module.so
%{_datadir}/nginx/modules/mod-stream.conf

%files help
%defattr(-,root,root)
%doc CHANGES README README.dynamic
%{_mandir}/man3/nginx.3pm*
%{_mandir}/man8/nginx.8*

%changelog
* Thu Sep 3 2020 yanan li <liyanan032@huawei.com> - 1:1.18.0-2
- add mime.types file to nginx packages

* Thu Jun 4 2020 huanghaitao <huanghaitao8@huawei.com> - 1:1.18.0-1
- Change source to latest update

* Fri May 22 2020 wutao <wutao61@huawei.com> - 1:1.16.1-4
- change and delete html

* Mon May 11 2020 wutao <wutao61@huawei.com> - 1:1.16.1-3
- modify patch and html

* Wed Mar 18 2020 yuxiangyang <yuxiangyang4@huawei.com> - 1:1.16.1-2
- delete http_stub_status_module.This configuration creates a simple
  web page with basic status data,but it will affect cpu scale-out because
  it use atomic cas.

* Mon Mar 16 2020 likexin <likexin4@huawei.com> - 1:1.16.1-1
- update to 1.16.1

* Mon Mar 16 2020 openEuler Buildteam <buildteam@openeuler.org> - 1:1.12.1-17
- Type:bugfix
- ID:NA
- SUG:restart
- DESC: fix CVE-2019-20372

* Sat Dec 28 2019 openEuler Buildteam <buildteam@openeuler.org> - 1:1.12.1-16
- Type:bugfix
- ID:NA
- SUG:NA
- DESC: add the with_mailcap_mimetypes

* Wed Dec 4 2019 openEuler Buildteam <buildteam@openeuler.org> - 1:1.12.1-15
- Package init

