HASHES = $(wildcard *.hash)

.PHONY: all hashes
all: hashes

# salt.states.file.managed likes to have hashes to download, to check
# whether it has the newest version. See:
# https://docs.saltstack.com/en/latest/ref/states/all/
#   salt.states.file.html#salt.states.file.managed
hashes: $(HASHES)

%.hash: % Makefile
	sha256sum $< > $@
