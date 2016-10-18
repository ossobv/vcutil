IPtables + fail2ban firewall for Asterisk
=========================================

Place the files found here in the appropriate subdirectories in ``/etc/``.

Adjust ``/etc/init.d/firewall`` if needed.
Add your whitelist IPs into ``/etc/fail2ban/jail.d/custom.conf`` and
into ``/etc/default/firewall``.

Finally, ``insserv`` and start it.

.. note::

  NOTE: For SECURITY logging by Asterisk, you need to load the
  ``res_security_log.so`` module.
