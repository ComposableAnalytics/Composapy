Environment Variables
=====================

If running Composapy in a DataLab, your environment variables will already be set up 
on your running instance. If running outside of a DataLab instance, you will need to
set "DATALAB_DLL_DIR". "APPLICATION_URI" can also optionally be set, however it is only
used to create a Session object and can be passed in as the "uri" argument.

DATALAB_DLL_DIR
---------------

The value of this should be a path to the required Composable dll's needed to run
Composapy. Composapy uses the `PythonNet <https://github.com/pythonnet/pythonnet>`_
package to bind to the Composable project dll's.


APPLICATION_URI
---------------

See :doc:`/reference/composapy-session`.


COMPOSAPY_INI_DIR
-----------------

This can be set to change the read/write location of the "composapy.ini" configuration file. If
not specified, defaults to current working directory.
