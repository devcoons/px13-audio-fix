%global debug_package %{nil}

# Vendored snapshot of https://github.com/ftoleedo/px13-audio-fix @ 0de5121
%global upstream_commit 0de512111635f5a5bf5cb5738fc42c289d81cb10
%global dkms_name snd-soc-tas2783-sdw-px13
%global dkms_ver  1.0

%{!?_udevrulesdir:%global _udevrulesdir %{_prefix}/lib/udev/rules.d}
%{!?_presetdir:%global _presetdir %{_prefix}/lib/systemd/system-preset}
%{!?_unitdir:%global _unitdir %{_prefix}/lib/systemd/system}

# brp-linkdupes calls selabel_open() and fails when SELinux file_contexts
# are missing. This package has no duplicate payload files to hardlink.
%undefine __brp_linkdupes

Name:           px13-audio-fix
Version:        1.0
Release:        1%{?dist}
Summary:        ASUS ProArt PX13 internal speaker fix (TAS2783 DKMS + ALSA UCM)

# Kernel module: GPL-2.0-only (derived from the upstream tas2783 driver).
# Packaging scripts and UCM helpers: CC0-1.0, matching upstream guide/scripts.
License:        GPL-2.0-only AND CC0-1.0
URL:            https://github.com/devcoons/px13-audio-fix
Source0:        %{name}-%{version}.tar.gz

BuildArch:      noarch

BuildRequires:  systemd-rpm-macros
BuildRequires:  bash

Requires:       dkms
Requires:       gcc
Requires:       make
Requires:       binutils
Requires:       dwarves
Requires:       elfutils-libelf-devel
Requires:       kernel-devel
Requires:       kernel-devel-matched
Requires:       alsa-ucm
Requires:       alsa-utils
Requires:       linux-firmware
Requires:       systemd
Requires:       bash
Requires(post): dkms
Requires(post): systemd
Requires(preun): dkms
Requires(preun): systemd
Requires(postun): systemd
Provides:       px13-audio-fix-dkms = %{version}-%{release}

%description
Restores stereo internal speakers on the ASUS ProArt PX13 (HN7306, AMD
Strix Halo / SoundWire TAS2783) under Fedora on stock kernels >= 7.1.

The stock kernel driver initializes both speaker amplifiers on the same
DSP channel, and the machine driver does not tag the ALSA card with
spk:tas2783, so PipeWire never exposes a speaker sink. This package
installs:

- a PX13-specific snd-soc-tas2783-sdw DKMS module (channel-selection
  control, rebuilds on every kernel update)
- ALSA UCM files plus a SKU-probed long-name override
- a oneshot service that writes the override for this machine's DMI
  card name

Fedora-specific change: the DKMS module is built with GCC (Fedora's
kernel toolchain). Building with LLVM/Clang fails against a GCC-built
kernel.

Based on https://github.com/ftoleedo/px13-audio-fix
(%{upstream_commit})
Packaged for Fedora by devcoons.

Secure Boot must be disabled, or the DKMS module must be signed and
enrolled, or the module will not load.

A reboot is required after the first install so the patched module can
replace the in-use stock codec.

%package resume
Summary:        Optional s2idle SoundWire resume recovery for ASUS ProArt PX13
Requires:       %{name} = %{version}-%{release}

%description resume
Optional systemd-sleep hook that recovers ASUS ProArt PX13 internal
speakers after s2idle. The TAS2783 DSP firmware and SoundWire slaves
can fail to come back after suspend even when mixer levels look fine.

Do not install this subpackage unless speakers actually stop working
after resume. Test boot -> speakers -> suspend -> resume first.

Based on https://github.com/ftoleedo/px13-audio-fix
Packaged for Fedora by devcoons.

%prep
%autosetup -n %{name}-%{version}

%build
# DKMS packages ship source; the module is built on the installed system.

%check
if grep -E '^(MAKE|CLEAN).*LLVM=1' module/dkms.conf; then
    echo "LLVM=1 must not remain in the DKMS MAKE/CLEAN lines on Fedora" >&2
    exit 1
fi
grep -F 'DEST_MODULE_LOCATION[0]="/extra"' module/dkms.conf
grep -F '/usr/share/px13-audio-fix/px13-detect.sh' px13-soundwire-recover.sh
grep -F '/usr/libexec/px13-audio-fix/px13-soundwire-recover' 50-px13-soundwire
bash -n fedora/px13-audio-fix-apply-ucm
bash -n px13-soundwire-recover.sh
bash -n 50-px13-soundwire

%install
install -d %{buildroot}%{_usrsrc}/%{dkms_name}-%{dkms_ver}
install -m644 module/tas2783-sdw.c module/tas2783.h module/Makefile module/dkms.conf \
    %{buildroot}%{_usrsrc}/%{dkms_name}-%{dkms_ver}/

install -d %{buildroot}%{_datadir}/%{name}
install -m644 lib/px13-detect.sh \
    %{buildroot}%{_datadir}/%{name}/px13-detect.sh
install -m644 configs/ucm-card-override.conf.in \
    %{buildroot}%{_datadir}/%{name}/ucm-card-override.conf.in

install -D -m644 configs/sof-soundwire_tas2783.conf \
    %{buildroot}%{_datadir}/alsa/ucm2/sof-soundwire/tas2783.conf
install -D -m644 configs/codecs_tas2783_init.conf \
    %{buildroot}%{_datadir}/alsa/ucm2/codecs/tas2783/init.conf

install -D -m755 fedora/px13-audio-fix-apply-ucm \
    %{buildroot}%{_libexecdir}/%{name}/apply-ucm
install -D -m644 fedora/px13-audio-fix-ucm.service \
    %{buildroot}%{_unitdir}/px13-audio-fix-ucm.service
install -D -m644 fedora/80-px13-audio-fix.preset \
    %{buildroot}%{_presetdir}/80-px13-audio-fix.preset
install -D -m644 fedora/90-px13-audio-fix.rules \
    %{buildroot}%{_udevrulesdir}/90-px13-audio-fix.rules

install -d %{buildroot}%{_sbindir}
ln -s ../libexec/%{name}/apply-ucm %{buildroot}%{_sbindir}/px13-audio-fix-apply

install -D -m755 px13-soundwire-recover.sh \
    %{buildroot}%{_libexecdir}/%{name}/px13-soundwire-recover
install -D -m755 50-px13-soundwire \
    %{buildroot}%{_prefix}/lib/systemd/system-sleep/50-px13-soundwire

# Generated at %post / first boot.
install -d %{buildroot}%{_sysconfdir}
touch %{buildroot}%{_sysconfdir}/px13-audio-fix.conf

%post
%systemd_post px13-audio-fix-ucm.service

if command -v mokutil >/dev/null 2>&1; then
    if mokutil --sb-state 2>/dev/null | grep -qi enabled; then
        echo "WARNING: Secure Boot is enabled. The DKMS module will not load unless it is signed and the key is enrolled." >&2
    fi
fi

# Re-register so source/release updates actually rebuild.
if dkms status -m %{dkms_name} -v %{dkms_ver} 2>/dev/null | grep -q '%{dkms_name}'; then
    dkms remove -m %{dkms_name} -v %{dkms_ver} --all --rpm_safe_upgrade >/dev/null 2>&1 || :
fi
dkms add -m %{dkms_name} -v %{dkms_ver} --rpm_safe_upgrade >/dev/null 2>&1 || \
    dkms add -m %{dkms_name} -v %{dkms_ver} >/dev/null 2>&1 || :

if [ -e "/lib/modules/$(uname -r)/build/Makefile" ]; then
    if ! dkms autoinstall -m %{dkms_name} >/dev/null 2>&1; then
        echo "WARNING: DKMS autoinstall failed for %{dkms_name}/%{dkms_ver}." >&2
        echo "         Install matching kernel-devel and run: dkms autoinstall" >&2
        echo "         Log: /var/lib/dkms/%{dkms_name}/%{dkms_ver}/build/make.log" >&2
    fi
else
    echo "WARNING: kernel-devel for $(uname -r) is not present; DKMS will build on the next kernel-install." >&2
fi

%{_libexecdir}/%{name}/apply-ucm >/dev/null 2>&1 || :

echo
echo "px13-audio-fix: reboot so the patched TAS2783 module can replace the stock driver."
echo "After reboot, verify:"
echo "  modinfo snd_soc_tas2783_sdw | grep '^filename:'"
echo "  wpctl status"
echo "  pw-play /usr/share/sounds/alsa/Front_Left.wav"
echo

%preun
%systemd_preun px13-audio-fix-ucm.service
if [ "$1" -eq 0 ]; then
    dkms remove -m %{dkms_name} -v %{dkms_ver} --all --rpm_safe_upgrade >/dev/null 2>&1 || :
    if [ -d %{_datadir}/alsa/ucm2/conf.d ]; then
        find %{_datadir}/alsa/ucm2/conf.d -type f -name '*.conf' \
            -exec grep -l 'px13-audio-fix' {} + 2>/dev/null \
            | while read -r f; do
                rm -f "$f"
            done || :
    fi
    rm -f %{_sysconfdir}/px13-audio-fix.conf
fi

%postun
%systemd_postun px13-audio-fix-ucm.service

%files
%license LICENSE LICENSE.upstream
%doc README.md
%dir %{_usrsrc}/%{dkms_name}-%{dkms_ver}
%{_usrsrc}/%{dkms_name}-%{dkms_ver}/*
%dir %{_datadir}/%{name}
%{_datadir}/%{name}/px13-detect.sh
%{_datadir}/%{name}/ucm-card-override.conf.in
%dir %{_datadir}/alsa/ucm2/codecs/tas2783
%{_datadir}/alsa/ucm2/sof-soundwire/tas2783.conf
%{_datadir}/alsa/ucm2/codecs/tas2783/init.conf
%dir %{_libexecdir}/%{name}
%{_libexecdir}/%{name}/apply-ucm
%{_sbindir}/px13-audio-fix-apply
%{_unitdir}/px13-audio-fix-ucm.service
%{_presetdir}/80-px13-audio-fix.preset
%{_udevrulesdir}/90-px13-audio-fix.rules
%ghost %config(noreplace) %{_sysconfdir}/px13-audio-fix.conf

%files resume
%{_libexecdir}/%{name}/px13-soundwire-recover
%attr(0755,root,root) %{_prefix}/lib/systemd/system-sleep/50-px13-soundwire

%changelog
* Wed Aug 26 2026 devcoons <devcoons@users.noreply.github.com> - 1.0-1
- Initial Fedora package for ASUS ProArt PX13 TAS2783 speakers
- Vendored ftoleedo/px13-audio-fix (0de5121)
- Build the DKMS module with GCC (no LLVM=1)
- Probe the UCM CardLongName at install/boot so every PX13 SKU works
