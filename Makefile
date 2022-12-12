HASHES = $(wildcard *.hash)

DESTDIR =
PREFIX ?= /usr/local
BINDIR = $(PREFIX)/bin
SBINDIR = $(PREFIX)/sbin
SYSCONFDIR = /etc
SYSSBINDIR = /sbin

BINS = \
	apt-find-foreign \
	argecho \
	bson2json \
	censored-for-email \
	cert-expiry-check \
	cert-expiry-finder \
	dbschemadiff \
	difftac \
	easycert \
	efibootmirrorsetup \
	etccleaner \
	filespeed \
	gelf-payload-decode \
	gitbackhub \
	git-failed-msg \
	git-hook-postcommit-coloremail \
	git-reapply-patch \
	gitlab-hook-postcommit-coloremail \
	ifupdown2netplan \
	ikvmocr \
	indirect-scp \
	interfaces2netplan \
	ipmikvm \
	ipmiscrape \
	keystone-swift-curl \
	kubectl-sh-bash \
	kubectl-sh-secret \
	kubectl-sh-wrapper \
	linux-kernel-autoremove \
	lldpscan \
	make-master-secret-log \
	mysql2csv \
	pdns-mysql-slave-prune \
	psdiff \
	pve-macaddr-security \
	sadfscheck \
	sh-c \
	snap-autoremove \
	sys-is-vm \
	tls-sniff-ciphers \
	udiff \
	uwsgi-list \
	uwsgi-log \
	uwsgi-kill \
	venvpatch \
	wcheckrestart \
	wdiffcount \
	wgrep \
	wtimedecode \
	wtimediff \
	wtimestamp \
	wtrunc \
	wvpn \
	zabdig

SBINS = \
	arpfix \
	fwdiff \
	multilb-sanity-check

SYSSBINS = \
	mount.zfs-non-legacy

OTHER = \
	.gitignore \
	Makefile \
	README.rst \
	gitlab-hook-postcommit-coloremail.example \
	ikvmocr.js \
	ikvmocr-1.png \
	ikvmocr-2.png \
	psdiff.hash \
	psdiff.rst \
	tcpdump247 \
	tcpdump247.default \
	udiff.selftest \

.PHONY: all clean deb hashes make_has_all_files
all: hashes make_has_all_files

clean:
	$(MAKE) -f udiff.selftest clean

test:
	$(MAKE) -f udiff.selftest && $(MAKE) -f udiff.selftest clean

deb:
	# Make sure a valid email with PGP key is in the changelog
	dpkg-buildpackage -sa

install:
	install -d $(DESTDIR)$(BINDIR)
	install $(BINS) $(DESTDIR)$(BINDIR)
	install -d $(DESTDIR)$(SBINDIR)
	install $(SBINS) $(DESTDIR)$(SBINDIR)
	install -d $(DESTDIR)$(SYSSBINDIR)
	install $(SYSSBINS) $(DESTDIR)$(SYSSBINDIR)
	#install -D -T tcpdump247 $(DESTDIR)$(SYSCONFDIR)/init.d/tcpdump247
	#install -m0600 -D -T \
	#  tcpdump247.default $(DESTDIR)$(SYSCONFDIR)/default/tcpdump247

# salt.states.file.managed likes to have hashes to download, to check
# whether it has the newest version. See:
# https://docs.saltstack.com/en/latest/ref/states/all/
#   salt.states.file.html#salt.states.file.managed
hashes: $(HASHES)

make_has_all_files:
	@bash -c "diff -pu <(git ls-files | grep -vF / | sort -V) \
	  <(echo $(BINS) $(SBINS) $(SYSSBINS) $(OTHER) | \
	    tr ' ' '\n' | sort -V)"

%.hash: % Makefile
	sha256sum $< > $@
