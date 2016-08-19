HASHES = $(wildcard *.hash)

DESTDIR =
PREFIX ?= /usr/local
BINDIR = $(PREFIX)/bin

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
	psdiff \
	pve-macaddr-security \
	svn-diff \
	svn-hook-postcommit-coloremail \
	svn-merge-msg \
	svn-show-mergable \
	svn-status \
	udiff \
	uwsgi-kill \
	venvpatch \
	wcheckrestart \
	wdiffcount \
	wgrep \
	wtimediff \
	wtimestamp

OTHER = \
	tcpdump247

.PHONY: all deb hashes
all: hashes

deb:
	dpkg-buildpackage -us -uc -sa

install:
	install -d $(DESTDIR)$(BINDIR)
	install $(BINS) $(DESTDIR)$(BINDIR)

# salt.states.file.managed likes to have hashes to download, to check
# whether it has the newest version. See:
# https://docs.saltstack.com/en/latest/ref/states/all/
#   salt.states.file.html#salt.states.file.managed
hashes: $(HASHES)

%.hash: % Makefile
	sha256sum $< > $@
