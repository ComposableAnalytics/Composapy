FileReference
=============

.. code-block:: python

    from composapy.contracts import FileReference

For DataFlows that contain values of type FileReference, the value property contains the
necessary information needed to retrieve the file. A FileReference has a to_file() method,
which downloads the file to your local workspace and returns a FileReference pointing to the
newly created file.

A file reference can be one of its subclasses, which the platform picks from the file's
extension: ``CsvFileReference``, ``ImageReference``, ``KmlReference``, ``KmzReference``,
``StlReference``, ``Mp3Reference``, ``WavReference``, ``VideoReference``, and
``AudioReference``. They are all in ``composapy.contracts``.

Members
-------

- ``file_reference.Uri``: where the file is. A string that also has members for the parts of
  a URI (``Scheme``, ``LocalPath``, and others); see :doc:`composapy-contracts-values`.
- ``file_reference.LocalFile``: the path of a file on this machine, when there is one.

to_file
-------

- file_reference.to_file(save_dir: pathlib.Path | str = None, file_name: str = None) -> FileReference

If no save_dir kwarg is provided, it uses the current working directory. If no file_name kwarg is
provided, it will use the source file name. Pass an absolute ``save_dir``: a relative one
downloads the file and then raises ``ValueError``, because the returned reference has to
point at an absolute path.

.. code-block:: python

    run = DataFlow.get_run(654321)
    run.modules.first().result.value.to_file(save_dir="C:/path/to/dir", file_name="optional_name.txt")

file_ref
--------

If you need to create a new file reference (to pass as external inputs to a DataFlow), you can
use the file_ref utility.

- file_ref(path_like: pathlib.Path | str) -> FileReference

.. code-block:: python

    from composapy import file_ref
    _ref = file_ref("path/to/file.txt")  # composapy.contracts.FileReference

The path is made absolute, so the reference points at the file where it is now. Uploading the
file to the platform happens when the reference is passed to a DataFlow, and the file's bytes
are stored exactly as they are on disk.
