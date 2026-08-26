# SPDX-License-Identifier: CC0-1.0
NAME        := px13-audio-fix
VERSION     := 1.0
SPEC        := $(NAME).spec
TARBALL     := $(NAME)-$(VERSION).tar.gz
DISTDIR     := $(NAME)-$(VERSION)

RPMBUILD_DIR := $(CURDIR)/rpmbuild
SOURCEDIR    := $(RPMBUILD_DIR)/SOURCES
SPECDIR      := $(RPMBUILD_DIR)/SPECS
OUTDIR       ?= $(CURDIR)

# Everything the RPM ships lives in this repository.
DIST_FILES := \
	module \
	configs \
	lib \
	fedora \
	50-px13-soundwire \
	px13-soundwire-recover.sh \
	LICENSE \
	LICENSE.upstream \
	README.md

.PHONY: all tarball prepare srpm rpm clean install-deps

all: rpm

$(TARBALL): $(DIST_FILES)
	rm -rf $(DISTDIR)
	mkdir -p $(DISTDIR)
	cp -a $(DIST_FILES) $(DISTDIR)/
	tar -czf $(TARBALL) $(DISTDIR)
	rm -rf $(DISTDIR)

tarball: $(TARBALL)

prepare: tarball
	mkdir -p $(SOURCEDIR) $(SPECDIR) \
		$(RPMBUILD_DIR)/BUILD $(RPMBUILD_DIR)/BUILDROOT \
		$(RPMBUILD_DIR)/RPMS $(RPMBUILD_DIR)/SRPMS
	cp -f $(TARBALL) $(SOURCEDIR)/
	cp -f $(SPEC) $(SPECDIR)/

srpm: prepare
	rpmbuild -bs --define "_topdir $(RPMBUILD_DIR)" $(SPECDIR)/$(SPEC)
	cp -f $(RPMBUILD_DIR)/SRPMS/*.src.rpm $(OUTDIR)/

rpm: prepare
	rpmbuild -ba --define "_topdir $(RPMBUILD_DIR)" $(SPECDIR)/$(SPEC)
	cp -f $(RPMBUILD_DIR)/RPMS/noarch/*.rpm $(OUTDIR)/
	cp -f $(RPMBUILD_DIR)/SRPMS/*.src.rpm $(OUTDIR)/

install-deps:
	sudo dnf install -y rpm-build rpmdevtools systemd-rpm-macros bash \
		dkms gcc make binutils dwarves elfutils-libelf-devel kernel-devel \
		kernel-devel-matched alsa-ucm alsa-utils linux-firmware

clean:
	rm -rf $(RPMBUILD_DIR) $(DISTDIR) $(TARBALL) \
		$(NAME)-*.rpm $(NAME)-*.src.rpm
