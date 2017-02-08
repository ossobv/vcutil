HASHES = $(wildcard *.hash)

DESTDIR =
PREFIX ?= /usr/local
BINDIR = $(PREFIX)/bin
SYSCONFDIR = /etc

BINS = \
	asterisk-gitlog-find \
	bson2json \
	censored-for-email \
	cert-expiry-check \
	cert-expiry-finder \
	dbschemadiff \
	difftac \
	easycert \
	filespeed \
	gitbackhub \
	git-hook-postcommit-coloremail \
	gitlab-hook-postcommit-coloremail \
	indirect-scp \
	linux-kernel-autoremove \
	mysql2csv \
	pdns-mysql-slave-prune \
	psdiff \
	pve-macaddr-security \
	salt-highstate-pp \
	svn-diff \
	svn-hook-postcommit-coloremail \
	svn-merge-msg \
	svn-show-mergable \
	svn-status \
	tls-sniff-ciphers \
	udiff \
	uwsgi-list \
	uwsgi-kill \
	venvpatch \
	wcheckrestart \
	wdiffcount \
	wgrep \
	wtimediff \
	wtimestamp \
	wtrunc

OTHER = \
	Makefile \
	README.md \
	gitlab-hook-postcommit-coloremail.example \
	psdiff.hash \
	psdiff.rst \
	tcpdump247 \
	tcpdump247.default \
	udiff.selftest \
	wsvreader.py

.PHONY: all deb hashes make_has_all_files
all: hashes make_has_all_files

deb:
	dpkg-buildpackage -us -uc -sa

install:
	install -d $(DESTDIR)$(BINDIR)
	install $(BINS) $(DESTDIR)$(BINDIR)
	#install -D -T tcpdump247 $(DESTDIR)$(SYSCONFDIR)/init.d/tcpdump247
	#install -m0600 -D -T tcpdump247.default $(DESTDIR)$(SYSCONFDIR)/default/tcpdump247

# salt.states.file.managed likes to have hashes to download, to check
# whether it has the newest version. See:
# https://docs.saltstack.com/en/latest/ref/states/all/
#   salt.states.file.html#salt.states.file.managed
hashes: $(HASHES)

make_has_all_files:
	@bash -c "diff -pu <(git ls-files | grep -vF / | sort -V) \
		<(echo $(BINS) $(OTHER) | tr ' ' '\n' | sort -V)"

%.hash: % Makefile
	sha256sum $< > $@
