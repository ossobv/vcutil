vcutil
======

Misc. simple utilities to aid version control and host maintenance.


Checking differences of previously installed local files against
ppa.osso.nl osso package:

.. code-block:: shell

    dpkg -L vcutil |
    while read f; do
      test -x $f && g=/usr/local/bin/${f##*/} &&
      test -f $g && echo $g && diff -pu $g $f
    done
