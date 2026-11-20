Environment Variables
=====================

If running Composapy in a DataLab, your environment variables will already be set up
on your running instance. If running outside of a DataLab instance, "APPLICATION_URI" can
optionally be set, however it is only used to create a Session object and can be passed in
as the "uri" argument.

APPLICATION_URI
---------------

See :doc:`/reference/composapy-session`.


COMPOSAPY_INI_DIR
-----------------

This can be set to change the read/write location of the "composapy.ini" configuration file. If
not specified, defaults to current working directory.


DATALAB_DLL_DIR and DATALAB_DLL_DIR_EXCLUDE
-------------------------------------------

Composapy does not read these. Earlier releases needed them to find the Composable assemblies;
a process or a saved configuration that still sets them keeps working, and the settings are
ignored. The same applies to the ``[environment]`` section of "composapy.ini".
