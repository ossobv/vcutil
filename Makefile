DESTDIR =
PREFIX ?= /usr/local
BINDIR = $(PREFIX)/bin
SBINDIR = $(PREFIX)/sbin
SYSCONFDIR = /etc
SYSSBINDIR = /sbin

BINS = \
	2json.js \
	2json.py \
	2json.rs \
	2json.yaml \
	apt-find-foreign \
	argecho \
	bson2json \
	censored-for-email \
	cert-expiry-check \
	cert-expiry-finder \
	ctre \
	dbschemadiff \
	difftac \
	dpkg-repack0 \
	easycert \
	etccleaner \
	filespeed \
	gelf-payload-decode \
	gitbackhub \
	git-failed-msg \
	git-hook-postcommit-coloremail \
	git-reapply-patch \
	gitlab-hook-postcommit-coloremail \
	gounsafe \
	grepby \
	hostsort \
	ifupdown2netplan \
	ikvmocr \
	indirect-scp \
	interfaces2netplan \
	ip2net \
	ipmikvm \
	ipmiscrape \
	jsfold \
	keystone-swift-curl \
	kubectl-sh-bash \
	kubectl-sh-secret \
	kubectl-sh-wrapper \
	llssh \
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
	phpserde \
	psdiff \
	pwhashck \
	renum \
	rshall \
	sermon \
	sh-c \
	sshglob \
	sys-is-vm \
	udiff \
	uwsgi-list \
	uwsgi-log \
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
	_multi2json \

SBINS = \
	arpfix \
	efibootmirrorsetup \
	fwdiff \
	fwsniff \
	iperfplan \
	linux-kernel-autoremove \
	lldpscan \
	multilb-sanity-check \
	pve-macaddr-security \
	sadfscheck \
	snap-autoremove \
	tls-sniff-ciphers \
	uwsgi-kill \
	whatsmyboot \

SYSSBINS = \
	mount.zfs-non-legacy \

OTHER = \
	.gitignore \
	Makefile \
	README.rst \
	gitlab-hook-postcommit-coloremail.example \
	ikvmocr.js \
	psdiff.rst \
	tcpdump247.default \
	udiff.selftest \

OTHERX = \
	tcpdump247 \


.PHONY: all clean deb make_has_all_files all_bins_are_executable
.PHONY: all_other_has_no_x
all: make_has_all_files all_bins_are_executable all_other_has_no_x

clean:
	$(MAKE) -f udiff.selftest clean

test:
	RUNTESTS=1 ./fwsniff && printf '\342\234\205\n\n'
	RUNTESTS=1 ./hostsort && printf '\342\234\205\n\n'
	RUNTESTS=1 ./ip2net && printf '\342\234\205\n\n'
	RUNTESTS=1 ./llssh && printf '\342\234\205\n\n'
	RUNTESTS=1 ./mysqldumpdissect && printf '\342\234\205\n\n'
	RUNTESTS=1 ./renum && printf '\342\234\205\n\n'
	RUNTESTS=1 ./pwhashck && printf '\342\234\205\n\n'
	RUNTESTS=1 ./sshglob && printf '\342\234\205\n\n'
	RUNTESTS=1 ./_multi2json && printf '\342\234\205\n\n'
	$(MAKE) -f udiff.selftest && $(MAKE) -f udiff.selftest clean && \
	  printf '\342\234\205\n\n'
	python3 -m unittest discover tests

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

make_has_all_files:
	@bash -c "diff -pu <(git ls-files | grep -vF / | LC_ALL=C sort -V) \
	  <(echo $(BINS) $(SBINS) $(SYSSBINS) $(OTHER) $(OTHERX) | \
	    tr ' ' '\n' | LC_ALL=C sort -V)"

all_bins_are_executable:
	@ok=true; for bin in $(BINS) $(SBINS) $(SYSSBINDIR) $(OTHERX); do \
	  if ! test -x $$bin; then echo "$$bin: missing -x perms" >&2; \
	  ok=false; fi; done; $$ok

all_other_has_no_x:
	@ok=true; for nox in $(OTHER); do \
	  if ! test -f $$nox || test -x $$nox; then \
	    echo "$$nox: unexpected perms/availability" >&2; \
	    ok=false; fi; done; $$ok
