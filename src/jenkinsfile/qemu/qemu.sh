#!/bin/bash
sudo yum install -y \
  gcc \
  git \
  make \
  bison \
  brlapi-devel \
  bzip2-devel \
  chrpath \
  cyrus-sasl-devel \
  diffutils \
  device-mapper-multipath-devel \
  flex \
  gettext \
  gnutls-devel \
  gtk3-devel \
  kernel \
  libaio-devel \
  libattr-devel \
  libcap-devel \
  libcap-ng-devel \
  libcurl-devel \
  libepoxy-devel \
  libfdt-devel \
  libiscsi-devel \
  libjpeg-devel \
  libpng-devel \
  librbd-devel \
  libseccomp-devel \
  libtasn1-devel \
  libudev-devel \
  libusbx-devel \
  libusb-devel \
  libxml2-devel \
  lzo-devel \
  ncurses-devel \
  numactl-devel \
  meson \
  ninja-build \
  pam-devel \
  perl-Test-Harness \
  perl-podlators \
  pixman-devel \
  python-sphinx \
  python3-devel \
  rdma-core-devel \
  snappy-devel \
  systemd-devel \
  sphinx \
  texinfo \
  usbredir-devel \
  virglrenderer-devel \
  zlib-devel \
  --downloadonly --downloaddir=./
sudo rpm -ivh --force --nodeps *.rpm

cd ${repo}
git submodule update --init ui/keycodemapdb

mkdir aarch64-openEuler-linux-gnu
cd aarch64-openEuler-linux-gnu

if grep -qw -- "--disable-bluez" ../configure; then
    disable_bluez="--disable-bluez"
else
    disable_bluez=""
fi

../configure \
  --prefix=/usr \
  --target-list=aarch64-softmmu \
  '--extra-cflags=-O2 -g -pipe -Wall -Werror=format-security -Wp,-D_FORTIFY_SOURCE=2 -Wp,-D_GLIBCXX_ASSERTIONS -fexceptions -fstack-protector-strong -grecord-gcc-switches -specs=/usr/lib/rpm/openEuler/openEuler-hardened-cc1 -fasynchronous-unwind-tables -fstack-clash-protection -fPIE -DPIE -fPIC' \
  '--extra-ldflags=-Wl,--build-id -pie -Wl,-z,relro -Wl,-z,now -Wl,-z,noexecstack' \
  --datadir=/usr/share \
  --docdir=/usr/share/doc/qemu \
  --libdir=/usr/lib64 \
  --libexecdir=/usr/libexec \
  --localstatedir=/var \
  --sysconfdir=/etc \
  --interp-prefix=/usr/qemu-%M \
  --firmwarepath=/usr/share/qemu \
  --with-pkgversion=qemu-4.1.0-17.oe1 \
  --python=/usr/bin/python3 \
  --disable-strip \
  --disable-slirp \
  --enable-gtk \
  --enable-docs \
  --enable-guest-agent \
  --enable-pie \
  --enable-numa \
  --enable-mpath \
  --disable-libnfs \
  --disable-bzip2 \
  --enable-kvm \
  --enable-tcg \
  --enable-rdma \
  --enable-linux-aio \
  --enable-cap-ng \
  --enable-vhost-user \
  --enable-fdt \
  --enable-virglrenderer \
  --enable-cap-ng \
  --enable-libusb \
  ${disable_bluez} \
  --disable-dmg \
  --disable-qcow1 \
  --disable-vdi \
  --disable-vvfat \
  --disable-qed \
  --disable-parallels \
  --disable-sheepdog \
  --disable-capstone \
  --disable-smartcard \
  || (cat config.log; exit 1)

make -j$(getconf _NPROCESSORS_ONLN) VL_LDFLAGS=-Wl,--build-id V=1
make check V=1
