Migrating to 1.0
================

Composapy 1.0 talks to the platform over HTTP and carries its own Python versions of the
contract objects it returns. It no longer loads the Composable assemblies, so it needs no
.NET runtime, no ``pythonnet``, and no ``DATALAB_DLL_DIR``. ``import composapy`` takes about
0.6 seconds on Python 3.8, 3.11, and 3.13, where earlier releases took about 28 seconds.

The public API is the same: ``Session``, ``DataFlow``, ``Key``, ``QueryView``, ``to_table``,
and ``file_ref`` take the same arguments and return objects with the same members. Scripts and
notebooks that use only those keep working. This page lists what is different.

Exceptions
----------

A .NET exception type cannot exist without .NET, so the errors that reached your code as .NET
exceptions are Python exceptions with the same message.

.. list-table::
    :header-rows: 1
    :widths: 45 55

    * - Before
      - Now
    * - ``System.ServiceModel.FaultException`` from a service call
      - ``composapy.exceptions.ServiceFault``, with the server's message. It has
        ``ExceptionType``, ``StackTrace``, and ``status_code`` members; the message no longer has
        a .NET stack trace appended.
    * - ``System.ServiceModel.Security.MessageSecurityException`` for a bad token or password
      - ``composapy.exceptions.AuthenticationError``. A failed sign-in is still reported on the
        first service call.
    * - ``System.Net.WebException`` for a connection failure
      - ``ConnectionError``
    * - ``System.IO.DirectoryNotFoundException`` for a file that does not exist
      - ``FileNotFoundError``
    * - ``System.UnauthorizedAccessException`` for a directory given as a file
      - ``PermissionError``
    * - ``System.ArgumentOutOfRangeException`` from a list member
      - ``IndexError``
    * - ``System.Collections.Generic.KeyNotFoundException`` for a column name that is not there
      - ``KeyError``
    * - ``System.ArgumentException`` for a relative ``to_file`` folder
      - ``ValueError``
    * - ``System.InvalidOperationException`` from a member of a relative ``Uri``
      - ``composapy.contracts.uri.RelativeUriError``, a ``ValueError``

``composapy``'s own exception classes (``SessionException`` and its subclasses, ``QueryException``,
and the rest) keep their names and messages. Catch ``Exception`` or the Python class above; the
.NET class names no longer exist to catch.

An argument of the wrong type
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``pythonnet`` refused an argument of the wrong type, such as a text id where an integer was
expected, with a ``TypeError`` before any request. Composapy 1.0 sends it, the platform refuses
it, and you get a ``ServiceFault`` with the platform's message. ``QueryView.run`` still raises
``TypeError`` for a query that is not text, and a table input still raises ``TypeError`` for a
value that is not a DataFrame or ``Table``.

Contract objects
----------------

``Table``, ``FileReference`` and its subclasses, and ``ExecutionHandle`` are Python classes in
``composapy.contracts``. Every other contract is a ``ContractObject``. Members are read and
assigned as attributes, as before. The .NET methods and properties a contract class had beyond
that are gone, except these, which are kept because scripts called them:

- ``FileReference.Uri`` is a ``str`` with the members of ``System.Uri`` (``LocalPath``,
  ``AbsoluteUri``, ``Scheme``, and the rest). It compares equal to its text, which a
  ``System.Uri`` did not.
- A list inside a contract, such as ``Table.Headers``, is a ``list`` with the members of
  ``List<T>`` (``Count``, ``Contains``, ``IndexOf``, ``Add``, ``RemoveAt``, ...). Python's own
  behavior replaces some refusals: negative indexes and slices work, ``Contains`` of a value of
  another type is ``False``, and ``AddRange`` takes any iterable.

See :doc:`composapy-contracts-values`. ``isinstance(x, System.String)`` and the other checks
against .NET types do not work, because there is no ``System``.

Values
------

Numbers
~~~~~~~

- A module input or result declared ``System.Double`` or ``System.Single`` is a ``float``, and one
  declared ``System.Decimal`` is a ``decimal.Decimal``, as are lists of them.
- A Python ``float`` written to an input of type Object arrives as ``System.Decimal``, where the
  .NET wrappers sent ``System.Double``. The platform's JSON reader chooses the type of a bare
  number, and no form of the number makes it choose ``Double``. A typed Double input is not
  affected.
- An integer that does not fit in 32 bits is sent as a 64-bit integer. A script that returns one
  from a notebook no longer fails with ``OverflowError``.
- ``inf``, ``-inf``, and ``nan`` cannot be written in JSON. A DataFrame cell holding one reaches
  the platform as a missing value. Earlier releases stored ``0.0``.
- ``None`` for an input of a value type, such as an integer, is stored as that type's default,
  as before.

Files
~~~~~

Uploaded files are stored byte for byte. The .NET client read text files (``.txt``, ``.csv``, and
the like) in the system code page and stored them re-encoded as UTF-8, so the stored bytes could
differ from the file's. They no longer do.

The compatibility namespace
---------------------------

A script or a saved pickle that imports a .NET class by name still works for these names:

- ``CompAnalytics.Contracts``: ``FileReference``, its subclasses, and ``ExecutionHandle``
- ``CompAnalytics.Contracts.Tables``: ``Table``, ``TableColumn``, and ``TableColumnCollection``
- ``CompAnalytics.Contracts.QueryView``: ``LiteralInput`` and ``SearchInput``
- ``CompAnalytics.Core``: ``ContractSerializer``

They resolve to the classes in ``composapy.contracts``. ``LiteralInput()`` and ``SearchInput()``
return contract objects with the members the .NET classes had, so a script that builds an input and
adds it to ``driver.contract.LiteralInputs`` or ``SearchInputs`` runs unchanged. The lists of a
driver's contract have the members of ``List<T>``, such as ``Add`` and ``Clear``. Importing any other
module under ``CompAnalytics`` raises ``ModuleNotFoundError`` and lists these names. Importing
another name from one of these modules raises the usual ``ImportError``, which names only the
missing name. A session that loads the real assemblies through ``pythonnet`` itself gets the real
types.

Pickles
~~~~~~~

Pickles of ``Table``, ``FileReference``, and ``ExecutionHandle`` written by earlier releases load
in 1.0, including ``FileReference`` pickles whose URI is absolute. Pickles written by 1.0 cannot
be read by an earlier release.

Notebooks and scripts run by a DataLab
--------------------------------------

- A script runs in a single namespace, so a function defined in it can use the script's own
  imports and variables. Earlier releases raised ``NameError`` for that.
- A script parameter, or a DataFlow input, named ``token`` receives the value it was given. Earlier
  wrappers replaced it with the DataLab's API token. The session is registered from the token
  without defining a variable.
- A float parameter arrives as a Python ``float`` and can be returned from the script. Earlier
  wrappers handed the script a ``System.Decimal``, which the step that returns values refused.

Published DataLabs
~~~~~~~~~~~~~~~~~~

A published version of a DataLab runs in a worker that the platform starts and reuses between runs.
The earlier wrapper started a fresh process for every run, so these differ:

- A run started from a DataFlow is made as the DataFlow's owner. The session is registered from
  that user's token, so the owner's permissions decide what the script can read and run.
- ``composapy.ini`` is not read. The file a DataLab keeps beside its repository is not part of a
  published version, and the worker does not look for one. A script that needs a key registers it
  itself, by name or by id, before anything that uses it::

      from composapy.key.api import Key

      Key.get(name="a unique name").register()

  The owner needs permission to use the key. Put the call at the top of the entrypoint, before it
  imports the script's own modules. The worker clears the registered key before every run, and a
  module imported on an earlier run is not imported again, so a key registered while a module is
  being imported is gone on the next run in the same worker.
- Keep per-run state out of code that runs when a module is imported, for the same reason.

An entrypoint parameter that is not passed, or is passed as null, is a variable set to ``None``.
Earlier wrappers defined every parameter they were given, null ones included.

Installing
----------

- Python 3.8 through 3.13 are supported, with ``pandas`` older than 3. Pandas 3 changes the
  dtypes ``Table.to_pandas()`` returns.
- ``papermill`` is imported only by the notebook runner. ``import composapy`` no longer imports
  it, and no longer patches it.
- ``DATALAB_DLL_DIR``, ``DATALAB_DLL_DIR_EXCLUDE``, and the ``[environment]`` section of
  ``composapy.ini`` are accepted and ignored. See :doc:`environment-variables`.
- ``composapy.stream``, ``configure_binding``, ``add_dll_reference``, and the translator helpers in
  ``composapy.patch`` are gone.
- ``composapy.bindings`` is kept for one use: lifting a service's time limit. A request waits 60 seconds to connect
  and then up to 600 seconds for the reply, except for ``ApplicationService`` and ``QueryViewService``, which
  have no limit on the reply. A notebook written for 0.13 that sets
  ``bindings._service_binding_configs['TableService'] = bindings._service_binding_configs['ApplicationService']``
  still runs and still gives the table service no limit. The dictionary now holds a ``(connect, read)`` pair of
  seconds for each service, with ``None`` for no limit, and nothing else of the old module is there.
- ``Session`` gains ``close()`` and works as a context manager, because it holds an HTTP session.
