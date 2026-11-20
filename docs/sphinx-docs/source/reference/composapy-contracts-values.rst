Contract values
===============

The objects a DataFlow or QueryView call returns are contracts: ``Table``, ``FileReference``
and its subclasses, and ``ExecutionHandle`` have their own classes in ``composapy.contracts``,
and every other contract is a ``ContractObject``, a dictionary whose members are also
attributes (``module.contract.ModuleType.Name``). Two kinds of value inside them carry
members beyond Python's.

Uri
---

.. code-block:: python

    from composapy.contracts.uri import Uri, RelativeUriError

``FileReference.Uri`` is a ``Uri``. It is a ``str``: it compares, hashes, and serializes as the
text the contract carries, so it can be used anywhere a string can. It also has members for the
parts of the URI:

``OriginalString``, ``AbsoluteUri``, ``AbsolutePath``, ``LocalPath``, ``Scheme``, ``Host``,
``Port``, ``IsFile``, ``IsUnc``, ``IsAbsoluteUri``, ``Query``, ``Fragment``, ``PathAndQuery``,
``Segments``, and ``ToString()``.

.. code-block:: python

    uri = run.modules.first().result.value.Uri
    uri.Scheme          # "file" or "http"
    uri.LocalPath       # the path on disk, for a file URI
    uri.OriginalString  # the text exactly as the contract holds it
    str(uri)            # the same as uri.ToString(): an absolute URI with its escapes decoded

A relative URI, such as the site-relative one the platform returns for an uploaded file,
answers ``OriginalString`` and ``ToString()`` only. Any other member raises
``RelativeUriError``, a ``ValueError``, because a relative URI has no scheme or host to report.

NetList
-------

A list inside a contract, such as ``Table.Headers``, is a ``NetList``. It is a ``list``: it
compares, pickles, and serializes as a list, and every list operation works on it. It also has
these helper members:

``Count``, ``Contains(item)``, ``IndexOf(item)``, ``LastIndexOf(item)``, ``ToArray()``,
``GetRange(index, count)``, ``Add(item)``, ``AddRange(items)``, ``Insert(index, item)``,
``Remove(item)``, ``RemoveAt(index)``, ``Reverse()``, ``Sort()``, and ``Clear()``.

.. code-block:: python

    table.Headers.Count               # the same as len(table.Headers)
    table.Headers.Contains("a")       # the same as "a" in table.Headers
    table.Headers.RemoveAt(5)         # the same as del table.Headers[5]; IndexError when there is no item 5

A collection of columns, ``Table.Columns``, can also be indexed by column name.

ContractSerializer
------------------

.. code-block:: python

    from composapy.contracts import ContractSerializer, Table

    text = ContractSerializer.Serialize(table)
    table = ContractSerializer.Deserialize[Table](text)

Converts a contract to its JSON text and back, in the form the platform exchanges.
``SerializeToFile`` writes the text to a path. The notebook and script runners that DataLab
launches use it to read parameters and write results.
