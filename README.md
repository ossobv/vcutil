vcutil
======

Misc. simple version control utilities.


Check differences against ppa.osso.nl osso package:

```
dpkg -L vcutil |
while read f; do
  test -x $f && g=/usr/local/bin/${f##*/} &&
  test -f $g && echo $g && diff -pu $g $f
done
```
