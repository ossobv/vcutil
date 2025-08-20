vcutil
======

Misc. simple utilities to aid version control and host maintenance.

* `Highlights`_ describes a subset of the tools here.

*Many tools are intended to be used in other shell scripts. Because startup
speed is of the essence, you'll find little Python here. However,
since Python 3.10 and later, things have significantly improved.*

----------
Highlights
----------

Certificate management
~~~~~~~~~~~~~~~~~~~~~~

* ``cert-expiry-finder`` - Tries common locations of TLS certificates
  and checks their expiry date::

    $ sudo cert-expiry-finder --min
    -480

    $ sudo cert-expiry-finder
    -480    /etc/ssl/certs/ssl-cert-snakeoil.pem (CN = ubuntu)
    402     /opt/vault/tls/tls.crt (O = HashiCorp, CN = Vault)

* ``easycert`` - Has a ``-T`` mode to dump local or remote certificate info::

    $ easycert -T google.com 443
    Certificate chain
     0 s: {2B:57:88:15:00:ED:07:9F:F8:AF:53:1E:87:3B:AF:13:17:8E:13:62} [f6dbf7a7] CN = *.google.com
       i: {DE:1B:1E:ED:79:15:D4:3E:37:24:C3:21:BB:EC:34:39:6D:42:B2:30} [3c8b39ef] C = US, O = Google Trust Services, CN = WR2
     1 s: {DE:1B:1E:ED:79:15:D4:3E:37:24:C3:21:BB:EC:34:39:6D:42:B2:30} [3c8b39ef] C = US, O = Google Trust Services, CN = WR2
       i: {E4:AF:2B:26:71:1A:2B:48:27:85:2F:52:66:2C:EF:F0:89:13:71:3E} [1001acf7] C = US, O = Google Trust Services LLC, CN = GTS Root R1
     2 s: {E4:AF:2B:26:71:1A:2B:48:27:85:2F:52:66:2C:EF:F0:89:13:71:3E} [1001acf7] C = US, O = Google Trust Services LLC, CN = GTS Root R1
       i: {60:7B:66:1A:45:0D:97:CA:89:50:2F:7D:04:CD:34:A8:FF:FC:FD:4B} [5ad8a5d6] C = BE, O = GlobalSign nv-sa, OU = Root CA, CN = GlobalSign Root CA
    ---
    Expires in 40 days


Package / process management
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* ``apt-find-foreign`` - Shows the state of the installed .deb packages
  in your system. Run after dist-upgrade to see if there are stale
  packages lingering::

    $ apt-find-foreign
    Lists with corresponding package counts:
      17      (local only)
      2       (rc only)
      3656    http://archive.ubuntu.com/ubuntu
      1       http://packages.linuxmint.com

    Lists with very few packages (or with remarks):
      ...
      http://packages.linuxmint.com
        - chromium
      ...

* ``linux-kernel-autoremove`` - Removes unused Linux kernels. Not all
  *Debian* and *Ubuntu* releases have been that good with automatically
  removing kernels. On systems with unattended-upgrades, you could be
  hoarding boat loads of kernels. linux-kernel-autoremove will keep the
  latest and the currently running one::

    $ dpkg -l | awk '/linux-image-/{print $2}'
    linux-image-5.15.0-151-generic
    linux-image-6.8.0-1030-oracle
    linux-image-6.8.0-71-generic
    linux-image-generic

    $ linux-kernel-autoremove
    Supply -f to remove these packages:
      linux-image-5.15.0-151-generic
      linux-modules-5.15.0-151-generic
      linux-headers-5.15.0-151
      linux-headers-5.15.0-151-generic

* ``psdiff`` - Shows a list of running programs and compares it to a
  previously saved copy. Useful to show the state before and after
  reboot of a system::

    $ sudo psdiff write

    $ sudo reboot
    ...

    $ psdiff
    +     /usr/sbin/fsck  {user=root}
    -     /usr/sbin/irqbalance  {user=root}

  *So, there's a fsck running temporarily. And apparently irqbalance
  does not start automatically.*


Server management
~~~~~~~~~~~~~~~~~

* ``efibootmirrorsetup`` - Setup helper script to set EFI up on software-raid
  mirrored disks, and keep them in sync::

    $ efibootmirrorsetup /dev/nvme0n1 /dev/nvme1n1

* ``ipmikvm`` - Wrapper script to simplify connecting to SuperMicro iKVM
  consoles. The script negates the need to go through a browser first::

    $ ipmikvm 10.20.30.40 -U ADMIN -P some-ipmi-password

  This should log in, fetch the appropriate *Java* files and start the
  *iKVM Java console*.

* ``lldpscan`` - Standalone script that listens for LLDP packets. Useful
  during server bootstrap to see what physical connections there are.
  Assumes the connected links are broadcasting LLDP frames::

    $ sudo lldpscan
    Please wait at least 30 seconds for LLDP frames to arrive...
    Hint: use "ip link set up promisc on dev DEV" for unused devices

    14:17:57.485728 00:30:ab:aa:bb:cc -> 01:80:c2:00:00:0e [enp129s0f0np0]
    [('Chassis ID', ('MAC address', '00:30:ab:aa:bb:cc')),
     ('Port ID', ('Interface name', 'swp9')),
     ('Time To Live', 120),
     ('System name', 'leaf1.example.network'),
     ('Port description', 'someserver.example.com enp129s0f0np0'),
     ('End of LLDPDU', None)]


Logging (time) helpers
~~~~~~~~~~~~~~~~~~~~~~

* ``wtimedecode`` - Decodes unixtime on stdin::

    $ echo '[1755677035]: This is a log message' | wtimedecode
    [2025-08-20T10:03:55+0200 (1755677035)]: This is a log message

* ``wtimestamp`` - Adds time to log messages::

    $ { echo 0; for x in 1 2 3; do sleep $x; echo $x; done; } | wtimestamp
    2025-08-20 10:05:47.683406+0200: 0
    2025-08-20 10:05:48.668759+0200: 1
    2025-08-20 10:05:50.670322+0200: 2
    2025-08-20 10:05:53.672211+0200: 3

* ``wtimediff`` - Show time differences/delta (useful when analyzing
  ``strace`` or ``tcpdump`` output)::

    $ { echo 0; for x in 1 2 3; do sleep $x; echo $x; done; } | wtimestamp | wtimediff
          0.0      2025-08-20 10:07:46.311052+0200: 0
         +0.989005 2025-08-20 10:07:47.300057+0200: 1
         +2.001705 2025-08-20 10:07:49.301762+0200: 2
         +3.001808 2025-08-20 10:07:52.303570+0200: 3

* ``wtrunc`` - Checks your terminal width (80 columns?) and truncates
  long lines of input. Useful when grepping through files that might contain
  long blobs of base64, css, javascript, json or whatever that you're likely
  not interested in::

    $ grep 'https://' *.html | wtrunc
    google.html:})();</script><div id="mngb"><div id=gbar><nobr><b class=gb1>Zoeken<
    random.html:  <a href="https://abc.com">ABC.com</a>
    random.html:  <a href="https://def.com">DEF.com</a>


GNOME / X helpers
~~~~~~~~~~~~~~~~~

* ``xdg-recent`` - Mark a file as being used recently. Useful when you're
  (mostly) working in the terminal and now want to upload a file from
  your browser. Marking it as "used recently" will place it in the *Recent*
  pseudo-folder available for quick access::

    $ mv tmp.pcap ~/Documents/anomaly-present-2025-08-20-bug-present.pcap

    $ xdg-recent ~/Documents/anomaly-present-2025-08-20-bug-present.pcap

  Now the mentioned pcap is available in the GUI file dialog at *Recent*.


Admin API helpers
~~~~~~~~~~~~~~~~~

* ``nbdig`` - Like (DNS) dig, but uses the `NetBox <https://netboxlabs.com/>`_
  API as data source::

    $ nbdig someserver.example.com
    217.1.2.211

    $ nbdig -x 217.1.2.211
    someserver.example.com

  *It does more, but this is the most common invocation.*

  This is only useful if you're using *NetBox* as your source of truth.

* ``zabdig`` - Like (DNS) dig, bus uses the `Zabbix <https://www.zabbix.com/>`_
  API as data source::

    $ zabdig intserver.example.com
    10.1.2.21

    $ zabdig -x 10.1.2.21
    intserver.example.com           10.1.2.21, 217.1.2.1 (zabbix-proxy.example.com)

  *It will also list open alerts, but this is the most common invocation.*

  This is only useful if you're using *Zabbix* for monitoring and have
  many hosts configured in it.
