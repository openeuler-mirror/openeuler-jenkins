#!/bin/bash
sudo yum install -y \
  gdb \
  make \
  audit-libs-devel \
  augeas \
  autoconf \
  automake \
  bash-completion \
  cyrus-sasl-devel \
  dbus-devel \
  device-mapper-devel \
  dnsmasq \
  ebtables \
  firewalld-filesystem \
  gawk \
  gcc \
  gettext \
  gettext-devel \
  git \
  glib2-devel \
  glusterfs-api-devel \
  glusterfs-devel \
  gnutls-devel \
  iptables \
  iscsi-initiator-utils \
  libacl-devel \
  libattr-devel \
  libblkid-devel \
  libcap-ng-devel \
  libiscsi-devel \
  libnl3-devel \
  libpcap-devel \
  libpciaccess-devel \
  librados-devel \
  librbd-devel \
  libselinux-devel \
  libssh-devel \
  libssh2-devel \
  libtasn1-devel \
  libtirpc-devel \
  libtool \
  libxml2-devel \
  libxslt \
  lvm2 \
  module-init-tools \
  ncurses-devel \
  netcf-devel \
  nfs-utils \
  numactl-devel \
  numad \
  parted-devel \
  perl-interpreter \
  polkit \
  python3 \
  python3-docutils \
  qemu-img \
  radvd \
  readline-devel \
  rpcgen \
  sanlock-devel \
  scrub \
  systemd-devel \
  systemd-units \
  systemtap-sdt-devel \
  util-linux \
  wireshark-devel \
  xfsprogs-devel \
  yajl-devel \
  --downloadonly --downloaddir=./ --allowerasing --skip-broken --nobest
sudo rpm -ivh --force --nodeps *.rpm

cd ${repo}
git submodule update --init
autoreconf --verbose --force --install

mkdir aarch64-openEuler-linux-gnu
cd aarch64-openEuler-linux-gnu

../configure \
  --build=aarch64-openEuler-linux-gnu \
  --host=aarch64-openEuler-linux-gnu \
  --program-prefix= \
  --disable-dependency-tracking \
  --prefix=/usr \
  --exec-prefix=/usr \
  --bindir=/usr/bin \
  --sbindir=/usr/sbin \
  --sysconfdir=/etc \
  --datadir=/usr/share \
  --includedir=/usr/include \
  --libdir=/usr/lib64 \
  --libexecdir=/usr/libexec \
  --localstatedir=/var \
  --sharedstatedir=/var/lib \
  --mandir=/usr/share/man \
  --infodir=/usr/share/info \
  --enable-dependency-tracking \
  --with-runstatedir=/run \
  --with-qemu \
  --without-openvz \
  --without-lxc \
  --without-vbox \
  --without-libxl \
  --with-sasl \
  --with-polkit \
  --with-libvirtd \
  --without-esx \
  --without-hyperv \
  --without-vmware \
  --without-vz \
  --without-bhyve \
  --with-remote-default-mode=legacy \
  --with-interface \
  --with-network \
  --with-storage-fs \
  --with-storage-lvm \
  --with-storage-iscsi \
  --with-storage-iscsi-direct \
  --with-storage-scsi \
  --with-storage-disk \
  --with-storage-mpath \
  --with-storage-rbd \
  --without-storage-sheepdog \
  --with-storage-gluster \
  --without-storage-zfs \
  --without-storage-vstorage \
  --with-numactl \
  --with-numad \
  --with-capng \
  --without-fuse \
  --with-netcf \
  --with-selinux \
  --with-selinux-mount=/sys/fs/selinux \
  --without-apparmor \
  --without-hal \
  --with-udev \
  --with-yajl \
  --with-sanlock \
  --with-libpcap \
  --with-macvtap \
  --with-audit \
  --with-dtrace \
  --with-driver-modules \
  --with-firewalld \
  --with-firewalld-zone \
  --with-wireshark-dissector \
  --without-pm-utils \
  --with-nss-plugin \
  '--with-packager=http://openeuler.org, 2020-08-20-11:11:11, ' \
  --with-packager-version=7.oe1 \
  --with-qemu-user=qemu \
  --with-qemu-group=qemu \
  --with-tls-priority=@LIBVIRT,SYSTEM \
  --with-loader-nvram=/usr/share/edk2.git/ovmf-x64/OVMF_CODE-pure-efi.fd:/usr/share/edk2.git/ovmf-x64/OVMF_VARS-pure-efi.fd:/usr/share/edk2.git/ovmf-ia32/OVMF_CODE-pure-efi.fd:/usr/share/edk2.git/ovmf-ia32/OVMF_VARS-pure-efi.fd:/usr/share/edk2.git/aarch64/QEMU_EFI-pflash.raw:/usr/share/edk2.git/aarch64/vars-template-pflash.raw:/usr/share/edk2.git/arm/QEMU_EFI-pflash.raw:/usr/share/edk2.git/arm/vars-template-pflash.raw:/usr/share/edk2/ovmf/OVMF_CODE.fd:/usr/share/edk2/ovmf/OVMF_VARS.fd:/usr/share/edk2/ovmf-ia32/OVMF_CODE.fd:/usr/share/edk2/ovmf-ia32/OVMF_VARS.fd:/usr/share/edk2/aarch64/QEMU_EFI-pflash.raw:/usr/share/edk2/aarch64/vars-template-pflash.raw:/usr/share/edk2/arm/QEMU_EFI-pflash.raw:/usr/share/edk2/arm/vars-template-pflash.raw \
  --enable-werror \
  --enable-expensive-tests \
  --with-init-script=systemd \
  --without-login-shell || (cat config.log; exit 1)

make -j$(getconf _NPROCESSORS_ONLN) V=1
sed -i 's/while (kill(pid, 0) != -1)/for (int i = 0; kill(pid, 0) != -1 \&\& i < 300; i++)/' ../tests/commandtest.c
sed -i 's/while (kill(pid, SIGINT) != -1)/for (int i = 0; kill(pid, SIGINT) != -1 \&\& i < 300; i++)/' ../tests/commandtest.c
(set +x; for((i=0;i<3;i++)); do sleep 30; ps -fC make &>/dev/null || break; ps ww -e f; ps ww -ef | awk '$9~"tests/.libs/lt-commandtest"{print$2}' | xargs -n 1 pstack; done) &
timeout 120 make -j$(getconf _NPROCESSORS_ONLN) check VIR_TEST_DEBUG=1 || (cat tests/test-suite.log; exit 1)
