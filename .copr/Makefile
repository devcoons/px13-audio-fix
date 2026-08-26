# Used by Copr SCM builds (srpm-build-method: make_srpm).
# Copr sets $(outdir) to the directory that should receive the source RPM.
# All sources are in this git repository; nothing is downloaded at build time.
outdir ?= .
srpm:
	dnf -y install rpm-build rpmdevtools systemd-rpm-macros make tar gzip
	$(MAKE) -C "$(dir $(lastword $(MAKEFILE_LIST)))/.." srpm OUTDIR="$(outdir)"
