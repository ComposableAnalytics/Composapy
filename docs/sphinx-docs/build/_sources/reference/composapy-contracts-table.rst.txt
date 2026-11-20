Table
=====

.. code-block:: python

    from composapy.contracts import Table, to_table

A ``Table`` is what a DataFlow result or input of type Table holds: a table name, a SQL
query, its columns, and the execution handle it belongs to. The rows stay on the platform
until you ask for them. For convenience, a table is displayed as a pandas DataFrame when it
is the last value of a notebook cell.

.. code-block:: python

    table_run = DataFlow.get_run(138123)
    table_run.modules.first().result.value

    # .to_markdown() was used for markdown presentation purposes
    #
    # +----+-----+-----+-----+
    # |    | a   | o   | e   |
    # +====+=====+=====+=====+
    # |  0 | a   | o   | e   |
    # +----+-----+-----+-----+
    # |  1 | e   |     |     |
    # +----+-----+-----+-----+
    # |  2 | e   |     |     |
    # +----+-----+-----+-----+

to_pandas
---------

- table.to_pandas() -> pandas.DataFrame

Reads every row of the table and returns a pandas DataFrame whose column dtypes follow the
table's column types.

.. code-block:: python

    table = table_run.modules.first().result.value  # composapy.contracts.Table
    table_df = table.to_pandas()                    # pandas.DataFrame

Members
-------

A table carries the members of its contract:

- ``table.TableName``: the name of the table.
- ``table.Headers``: the column names, in order. A list with a few extra helper members
  (``Count``, ``Contains``, and others); see :doc:`composapy-contracts-values`.
- ``table.Columns``: the columns. Each has a ``Name`` and a ``Type``, and the collection can be
  indexed by name or by position.

to_table
--------

- to_table(df: pandas.DataFrame, execution_handle: ExecutionHandle, external_input_handles: list = None) -> Table

Creates a table on the platform from a pandas DataFrame, within the execution that
``execution_handle`` names, and returns its contract. This is how a script or notebook run by
a DLNBR module hands a DataFrame back to the platform.

.. code-block:: python

    import pandas as pd
    from composapy.contracts import to_table

    table = to_table(pd.DataFrame({"a": [1, 2, 3]}), execution_handle)

A DataFrame whose index is not the default range index keeps it as columns. Column names are
made valid for the platform: an empty name becomes ``col<position>``, runs of whitespace
become one space, and a name repeated, ignoring case, gets ``_2``, ``_3``, and so on. A
DataFrame with no columns raises ``ValueError``.
