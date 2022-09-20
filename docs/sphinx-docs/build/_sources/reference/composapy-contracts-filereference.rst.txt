FileReference
=============

.. code-block:: python

    from CompAnalytics.Contracts import FileReference

For DataFlows that contain values of type FileReference, the value property contains the
necessary information needed to retrieve the file. Composapy adds a convenience method,
to_file(), directly on the FileReference class. This gives you the ability to call to_file()
directly on your FileReference object, which downloads the file to your local workspace
and returns a FileReference pointing to the newly created file.

to_file
-------

- file_reference.to_file(save_dir: pathlib.Path | str = None, file_name: str = None) -> CompAnalytics.Contracts.FileReference

If no save_dir kwarg is provided, it uses the current working directory. If no file_name kwarg is
provided, it will use the source file name.

.. code-block:: python

    run = DataFlow.get_run(654321)
    run.modules.first().result.value.to_file(save_dir="optional/relative/path/to/dir", file_name="optional_name.txt")

file_ref
--------

If you need to create a new file reference (to pass as external inputs to a DataFlow), you can
use the file_ref utility.

- file_ref(path_like: pathlib.Path | str) -> CompAnalytics.Contracts.FileReference

.. code-block:: python

    from composapy import file_ref
    _ref = file_ref("path/to/file.txt")  # CompAnalytics.Contracts.FileReference

You can find more information on the CompAnalytics.Contracts.FileReference contract `here <https://dev.composable.ai/api/CompAnalytics.Contracts.FileReference.html>`_.
