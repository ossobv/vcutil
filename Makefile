HASHES = $(wildcard *.hash)

DESTDIR =
PREFIX ?= /usr/local
BINDIR = $(PREFIX)/bin
SYSCONFDIR = /etc

BINS = \
	apt-find-foreign \
	bson2json \
	censored-for-email \
	cert-expiry-check \
	cert-expiry-finder \
	dbschemadiff \
	difftac \
	easycert \
	etccleaner \
	filespeed \
	gitbackhub \
	git-failed-msg \
	git-hook-postcommit-coloremail \
	git-reapply-patch \
	gitlab-hook-postcommit-coloremail \
	ifupdown2netplan \
	indirect-scp \
	interfaces2netplan \
	ipmikvm \
	kubectl-sh-bash \
	kubectl-sh-secret \
	kubectl-sh-wrapper \
	linux-kernel-autoremove \
	mysql2csv \
	pdns-mysql-slave-prune \
	psdiff \
	pve-macaddr-security \
	salt-highstate-pp \
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
	zabdig

OTHER = \
	.gitignore \
	Makefile \
	README.rst \
	gitlab-hook-postcommit-coloremail.example \
	psdiff.hash \
	psdiff.rst \
	tcpdump247 \
	tcpdump247.default \
	udiff.selftest \
	wsvreader.py

.PHONY: all clean deb hashes make_has_all_files
all: hashes make_has_all_files

clean:
	$(MAKE) -f udiff.selftest clean

test:
	python2 -m unittest wsvreader
	python3 -m unittest wsvreader
	$(MAKE) -f udiff.selftest && $(MAKE) -f udiff.selftest clean

deb:
	# Make sure a valid email with PGP key is in the changelog
	dpkg-buildpackage -sa

install:
	install -d $(DESTDIR)$(BINDIR)
	install $(BINS) $(DESTDIR)$(BINDIR)
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
		<(echo $(BINS) $(OTHER) | tr ' ' '\n' | sort -V)"

%.hash: % Makefile
	sha256sum $< > $@
