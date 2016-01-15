Example psdiff.conf for celery (python3)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Celery (at least on python3) reorders its arguments -- probably because
argv passes through a dictionary at some point -- before it hands them
to the detached worker parent.  That means that the psdiff output
changes between celery restarts.  This example ``/etc/psdiff.conf``
checks for those processes and sorts the output:

.. code-block:: python

    import re
    
    class LocalFilteredProcessFormatter(
            FilteredProcessFormatter):
        # These processes have argv which is unordered. We sort $2.
        processes_with_unordered_argv = (
            '^([^ ]*python[^ ]* -m celery worker) (.*)',
        )
    
        processes_with_unordered_argv = tuple(
            re.compile(i) for i in processes_with_unordered_argv)
    
        def to_string(self, process, indent=0):
            # If the process cmdline matches anything in our
            # processes_with_unordered_argv list, we sort the second
            # matched group: that way we won't complain if the arguments
            # have a different order.
            for search in self.processes_with_unordered_argv:
                match = search.search(process.cmdline)
                if match:
                    head, tail = match.groups()
                    process.cmdline = ' '.join(
                        [head] + sorted(tail.split(' ')))
                    break
    
            return super(LocalFilteredProcessFormatter, self).to_string(
                process, indent=indent)
