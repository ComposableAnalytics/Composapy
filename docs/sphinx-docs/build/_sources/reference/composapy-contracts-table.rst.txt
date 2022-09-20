Tables.Table
============

.. code-block:: python

    from CompAnalytics.Contracts.Tables import Table

Table objects are container objects for queries. For convenience, their results are displayed
as a pandas DataFrame when inside a notebook environment.

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

You can also retrieve the value of the pandas DataFrame Table object with to_pandas().

.. code-block:: python

    table = table_run.modules.first().result.value  # CompAnalytics.Contracts.Tables.Table
    table_df = table.to_pandas()                    # pandas.DataFrame

You can find more information on the CompAnalytics.Contracts.Tables.Table contract `here <https://dev.composable.ai/api/CompAnalytics.Contracts.Tables.Table.html>`_.
