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
	ctre \
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
	hostsort \
	ifupdown2netplan \
	ikvmocr \
	indirect-scp \
	interfaces2netplan \
	ip2net \
	ipmikvm \
	ipmiscrape \
	keystone-swift-curl \
	kubectl-sh-bash \
	kubectl-sh-secret \
	kubectl-sh-wrapper \
	linux-kernel-autoremove \
	lldpscan \
	logcolor \
	make-master-secret-log \
	mysql2csv \
	mysqldumpdissect \
	mysqlparseslow \
	mysql-slave-skip-one-table \
	mysql-slave-sync-table \
	nbdig \
	pdns-sql-slave-prune \
	pgpg \
	psdiff \
	pve-macaddr-security \
	sadfscheck \
	sermon \
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
	xdg-recent \
	zabdig \

SBINS = \
	arpfix \
	fwdiff \
	fwsniff \
	multilb-sanity-check \

SYSSBINS = \
	mount.zfs-non-legacy \

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
	tcpdump247.default \
	udiff.selftest \

OTHERX = \
	tcpdump247 \


.PHONY: all clean deb hashes make_has_all_files all_bins_are_executable
.PHONY: all_other_has_no_x
all: hashes make_has_all_files all_bins_are_executable all_other_has_no_x

clean:
	$(MAKE) -f udiff.selftest clean

test:
	RUNTESTS=1 ./fwsniff && printf '\342\234\205\n\n'
	RUNTESTS=1 ./ip2net && printf '\342\234\205\n\n'
	RUNTESTS=1 ./mysqldumpdissect && printf '\342\234\205\n\n'
	$(MAKE) -f udiff.selftest && $(MAKE) -f udiff.selftest clean && \
	  printf '\342\234\205\n\n'

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
	  <(echo $(BINS) $(SBINS) $(SYSSBINS) $(OTHER) $(OTHERX) | \
	    tr ' ' '\n' | sort -V)"

all_bins_are_executable:
	@ok=true; for bin in $(BINS) $(SBINS) $(SYSSBINDIR) $(OTHERX); do \
	  if ! test -x $$bin; then echo "$$bin: missing -x perms" >&2; \
	  ok=false; fi; done; $$ok

all_other_has_no_x:
	@ok=true; for nox in $(OTHER); do \
	  if ! test -f $$nox || test -x $$nox; then \
	    echo "$$nox: unexpected perms/availability" >&2; \
	    ok=false; fi; done; $$ok

%.hash: % Makefile
	sha256sum $< > $@
